"""
native_engine/population.py - World Population Manager (MODERN_DESIGN orchestration, LEGACY_OBSERVED data)

Manages SpawnDefinitions and active MonsterInstances for the world.
Derived from Legacy monster_spawnlist.sql semantics:
  - loc_size > 0: monsters spawn within center +/- loc_size range
  - loc_size == 0: monsters spawn randomly across the entire map

Provenance: spawn positions are CONTROLLED_SUBSTITUTION (deterministic seeded RNG
replaces Legacy's server-startup random placement, preserving spatial semantics).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import json

from .model import Monster, Position, Inventory
from .rng import NativeRng


# --- Canonical Map bounds (from maps.csv / CanonicalMapDefinition) ---
MAP_BOUNDS: Dict[int, Tuple[int, int, int, int]] = {
    0: (32256, 32767, 32768, 33279),   # x1, x2, y1, y2  — TI Surface 512×512
    1: (32640, 32767, 32768, 32895),   # TI Dungeon 1F 128×128 (loc_x1=32640, loc_x2=32767)
}


@dataclass
class SpawnDefinition:
    """
    A single spawn record from monster_spawnlist.sql.
    Provenance: LEGACY_OBSERVED from Eujenz/182c monster_spawnlist.sql
    """
    spawn_uid: int
    monster_id: int
    map_id: int
    spawn_x: int            # 0 if loc_size==0 (map-wide random)
    spawn_y: int            # 0 if loc_size==0 (map-wide random)
    count: int              # Number of instances to spawn
    loc_size: int           # 0 = full map random; >0 = center ± loc_size
    re_spawn: int           # Respawn interval in seconds (not used at runtime for MVP)
    provenance: str = "LEGACY_OBSERVED"


@dataclass
class MonsterDefinition:
    """
    A canonical monster template loaded from canonical_monsters in contract.
    Provenance: LEGACY_OBSERVED from Eujenz/182c monster.sql
    """
    id: int
    name: str
    level: int
    hp: int
    ac: int
    min_dmg: int
    max_dmg: int
    exp: int
    agro: int
    undead: int
    size: str
    gfx: int = 0
    move_speed_ms: int = 800
    attack_speed_ms: int = 1200


class PopulationManager:
    """
    Manages the world's monster population for Scenario 007.

    Responsibilities:
    - Load SpawnDefinitions from contract
    - Load MonsterDefinitions from contract
    - Place MonsterInstances at spawn time (seeded RNG, deterministic)
    - Provide spatial query: get_monsters_near(map_id, x, y, radius)
    - Track alive/dead state
    """

    def __init__(self, contract: dict, rng: NativeRng):
        self.rng = rng
        self._next_instance_id = 20000   # Unique instance IDs starting above player/static IDs

        # Load monster definitions
        self.monster_defs: Dict[int, MonsterDefinition] = {}
        for k, v in contract.get("canonical_monsters", {}).items():
            mid = int(k)
            self.monster_defs[mid] = MonsterDefinition(
                id=mid,
                name=v["name"],
                level=v["level"],
                hp=v["hp"],
                ac=v.get("ac", 0),
                min_dmg=v.get("min_dmg", 0),
                max_dmg=v.get("max_dmg", 0),
                exp=v["exp"],
                agro=v.get("agro", 0),
                undead=v.get("undead", 0),
                size=v.get("size", "small"),
                gfx=v.get("gfx", 0),
                move_speed_ms=v.get("move_speed_ms", 800),
                attack_speed_ms=v.get("attack_speed_ms", 1200),
            )

        # Load spawn definitions
        self.spawn_defs: List[SpawnDefinition] = []
        for s in contract.get("spawn_definitions", []):
            self.spawn_defs.append(SpawnDefinition(
                spawn_uid=s["spawn_uid"],
                monster_id=s["monster_id"],
                map_id=s["map_id"],
                spawn_x=s["spawn_x"],
                spawn_y=s["spawn_y"],
                count=s["count"],
                loc_size=s["loc_size"],
                re_spawn=s["re_spawn"],
                provenance=s.get("provenance", "LEGACY_OBSERVED"),
            ))

        # Per-map active monster lists
        self._map_monsters: Dict[int, List[Monster]] = {}
        self._all_monsters: List[Monster] = []

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize_population(
        self, map_ids: List[int], map_grids: Optional[Dict[int, any]] = None
    ) -> List[Monster]:
        """
        Place monsters on the specified maps using deterministic seeded RNG.

        LEGACY_OBSERVED parity:
        Replicates MonsterSpawnTable.java retry loop (up to 50 attempts) validating
        candidate coordinates against real WorldMapGrid geometry. If all 50 attempts fail,
        the spawn instance is skipped as in Legacy server startup.
        """
        from .movement import can_move

        placed: List[Monster] = []
        for sd in self.spawn_defs:
            if sd.map_id not in map_ids:
                continue
            mdef = self.monster_defs.get(sd.monster_id)
            if not mdef:
                continue
            bounds = MAP_BOUNDS.get(sd.map_id)
            if not bounds:
                continue
            x1, x2, y1, y2 = bounds
            grid = map_grids.get(sd.map_id) if map_grids else None

            for _ in range(sd.count):
                # Legacy MonsterSpawnTable: up to 50 attempts to find valid passable tile
                placed_ok = False
                mx, my = sd.spawn_x, sd.spawn_y

                for _attempt in range(50):
                    if sd.loc_size == 0:
                        cand_x = self.rng.rand(x1, x2, "SpawnX")
                        cand_y = self.rng.rand(y1, y2, "SpawnY")
                    else:
                        lo_x = max(x1, sd.spawn_x - sd.loc_size)
                        hi_x = min(x2, sd.spawn_x + sd.loc_size)
                        lo_y = max(y1, sd.spawn_y - sd.loc_size)
                        hi_y = min(y2, sd.spawn_y + sd.loc_size)
                        cand_x = self.rng.rand(lo_x, hi_x, "SpawnX")
                        cand_y = self.rng.rand(lo_y, hi_y, "SpawnY")

                    if grid is not None:
                        if not grid.is_in_bounds(cand_x, cand_y):
                            continue
                        if not any(can_move(grid, cand_x, cand_y, h)[0] for h in range(8)):
                            continue

                    mx, my = cand_x, cand_y
                    placed_ok = True
                    break

                if not placed_ok:
                    continue  # Dropped if no valid position found in 50 attempts

                iid = self._next_instance_id
                self._next_instance_id += 1

                monster = Monster(
                    id=mdef.id,
                    uid=iid,
                    name=mdef.name,
                    level=mdef.level,
                    hp=mdef.hp,
                    max_hp=mdef.hp,
                    ac=mdef.ac,
                    exp=mdef.exp,
                    size=mdef.size,
                    pos=Position(mx, my, sd.map_id),
                    heading=4,
                    inventory=Inventory(),
                    is_dead=False,
                    min_dmg=mdef.min_dmg,
                    max_dmg=mdef.max_dmg,
                    agro=mdef.agro,
                    undead=mdef.undead,
                    spawn_uid=sd.spawn_uid,
                    gfx=mdef.gfx,
                    move_speed_ms=mdef.move_speed_ms,
                    attack_speed_ms=mdef.attack_speed_ms,
                    re_spawn=sd.re_spawn,
                )
                if sd.map_id not in self._map_monsters:
                    self._map_monsters[sd.map_id] = []
                self._map_monsters[sd.map_id].append(monster)
                self._all_monsters.append(monster)
                placed.append(monster)

        return placed

    # ------------------------------------------------------------------
    # Spatial Query
    # ------------------------------------------------------------------

    def get_monsters_near(self, map_id: int, x: int, y: int, radius: int) -> List[Monster]:
        """
        Returns alive monsters within Chebyshev distance (radius) of (x, y) on map_id.
        Chebyshev distance = max(|dx|, |dy|) — matches L1J grid movement semantics.

        Result is sorted deterministically: by distance ASC, then spawn_uid ASC (tie-breaker).
        """
        monsters = self._map_monsters.get(map_id, [])
        result = []
        for m in monsters:
            if m.is_dead:
                continue
            dx = abs(m.pos.x - x)
            dy = abs(m.pos.y - y)
            dist = max(dx, dy)  # Chebyshev distance
            if dist <= radius:
                result.append((dist, m.uid, m))
        result.sort(key=lambda t: (t[0], t[1]))
        return [t[2] for t in result]

    def get_all_alive_on_map(self, map_id: int) -> List[Monster]:
        """Returns all alive monsters on a map, sorted by uid for determinism."""
        monsters = self._map_monsters.get(map_id, [])
        return sorted([m for m in monsters if not m.is_dead], key=lambda m: m.uid)

    def despawn(self, monster: Monster) -> None:
        """Mark monster as dead (despawned)."""
        monster.is_dead = True
        monster.target = None

    def respawn_monster(self, monster: Monster, map_grid: Optional[any] = None) -> Position:
        """
        Respawn dead monster instance back to life using its SpawnDefinition.
        LEGACY_OBSERVED parity: MonsterInstance.reSpawn() (MonsterInstance.java:527-551)
        Finds a valid passable tile within spawn bounds and resets HP/alive status.
        """
        from .movement import can_move

        sd = next((s for s in self.spawn_defs if s.spawn_uid == monster.spawn_uid), None)
        bounds = MAP_BOUNDS.get(monster.pos.map_id)
        if bounds:
            x1, x2, y1, y2 = bounds
        else:
            x1, x2, y1, y2 = (monster.pos.x - 5, monster.pos.x + 5, monster.pos.y - 5, monster.pos.y + 5)

        new_x, new_y = monster.pos.x, monster.pos.y
        if sd:
            for _ in range(50):
                if sd.loc_size == 0:
                    cand_x = self.rng.rand(x1, x2, "RespawnX")
                    cand_y = self.rng.rand(y1, y2, "RespawnY")
                else:
                    cand_x = self.rng.rand(max(x1, sd.spawn_x - sd.loc_size), min(x2, sd.spawn_x + sd.loc_size), "RespawnX")
                    cand_y = self.rng.rand(max(y1, sd.spawn_y - sd.loc_size), min(y2, sd.spawn_y + sd.loc_size), "RespawnY")

                if map_grid is not None:
                    if not map_grid.is_in_bounds(cand_x, cand_y):
                        continue
                    if not any(can_move(map_grid, cand_x, cand_y, h)[0] for h in range(8)):
                        continue
                new_x, new_y = cand_x, cand_y
                break

        monster.hp = monster.max_hp
        monster.is_dead = False
        monster.pos.x = new_x
        monster.pos.y = new_y
        monster.target = None
        return monster.pos

    def get_def(self, monster_id: int) -> Optional[MonsterDefinition]:
        """Returns the MonsterDefinition for a given monster_id."""
        return self.monster_defs.get(monster_id)

    def summary(self) -> dict:
        """Returns a summary of population state."""
        result = {}
        for map_id, monsters in self._map_monsters.items():
            alive = sum(1 for m in monsters if not m.is_dead)
            result[map_id] = {"total": len(monsters), "alive": alive}
        return result

    # ------------------------------------------------------------------
    # Factory: build from contract file
    # ------------------------------------------------------------------

    @classmethod
    def from_contract(
        cls, contract: dict, rng: NativeRng, map_ids: List[int],
        map_grids: Optional[Dict[int, any]] = None
    ) -> "PopulationManager":
        mgr = cls(contract, rng)
        mgr.initialize_population(map_ids, map_grids=map_grids)
        return mgr
