"""
native_engine/session.py - Authentic Hunting Game Session Orchestrator (Scenario 007)

Replaces the S006 turn-by-turn MVP with a macro-level intent-driven simulation:
  Player issues high-level commands (move, hunt, equip, status, quit).
  The runtime autonomously executes travel, encounter detection, combat, and progression.

Architecture:
  GameSession
    ├── PopulationManager  (world monster population from Legacy spawn data)
    ├── EncounterSystem    (proximity-based detection)
    ├── ProgressionManager (EXP/level-up from Legacy exp table)
    ├── EquipmentManager   (weapon equip/unequip)
    ├── CanonicalCombat    (certified S001 combat primitives)
    └── WorldRoutePlanner + WorldRouteExecutor (certified S005 navigation)

BACKWARD COMPATIBILITY:
  S006 MonsterTemplate / HuntingArea classes are preserved as LegacyMvpFixture
  so mvp.py --demo continues to work unchanged.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .combat import CanonicalCombat
from .encounter import EncounterSystem
from .equipment import EquipmentManager, build_weapon_from_contract
from .events import (
    DomainEvent,
    AttackStarted, HitResolved, DamageApplied, HpChanged,
    MonsterDied, ExperienceGranted, DropTransferred,
    LevelUp as LevelUpEvent,
    EncounterTriggered, WeaponEquipped, WeaponUnequipped,
)
from .model import Actor, Monster, Position, Inventory, Weapon
from .clock import SimulationClock, VirtualClock
from .navigation import AStarPlanner
from .movement import MovementEngine
from .population import PopulationManager
from .progression import ProgressionManager
from .rng import NativeRng
from .transition import TransitionEngine
from .world import World
from .world_route import WorldRoutePlanner, WorldRouteExecutor, WorldTransitionProvider


# ---------------------------------------------------------------------------
# S006 Legacy MVP fixtures — kept for backward compatibility (mvp.py --demo)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HuntingArea:
    """LEGACY MVP FIXTURE — S006 compatibility. Do not use in S007 paths."""
    id: str
    name: str
    map_id: int
    goal_x: int
    goal_y: int
    monster_type: str


@dataclass(frozen=True)
class MonsterTemplate:
    """LEGACY MVP FIXTURE — S006 compatibility. Do not use in S007 paths."""
    id: int
    name: str
    level: int
    hp: int
    max_hp: int
    ac: int
    exp: int
    size: str
    atk_min: int
    atk_max: int


# ---------------------------------------------------------------------------
# Destination: high-level named location for autonomous travel
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Destination:
    id: str
    name: str
    map_id: int
    x: int
    y: int


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------

class GameSession:
    """
    Authentic World Hunting Game Session.

    Player commands (macro-level):
      move_to(destination_id)  → autonomous travel with encounter interrupts
      hunt(kill_limit)         → autonomous hunting loop
      equip(item_id)           → weapon equip
      get_status()             → full status dict
      unequip()                → remove weapon

    S006 compatibility methods (used by mvp.py --demo):
      select_hunting_area()
      attack()
    """

    def __init__(
        self,
        world: World,
        player: Actor,
        transition_engine: TransitionEngine,
        transition_provider: WorldTransitionProvider,
        population: PopulationManager,
        progression: ProgressionManager,
        equipment_mgr: EquipmentManager,
        destinations: Dict[str, Destination],
        seed: int = 777777,
        clock: Optional[SimulationClock] = None,
        # S006 legacy compat
        areas: Optional[Dict[str, HuntingArea]] = None,
        monsters: Optional[Dict[str, MonsterTemplate]] = None,
    ):
        self.world = world
        self.player = player
        self.transition_engine = transition_engine
        self.transition_provider = transition_provider
        self.population = population
        self.progression = progression
        self.equipment_mgr = equipment_mgr
        self.destinations = destinations
        self.rng = NativeRng(seed)
        self.clock = clock or VirtualClock()

        # S006 compat
        self.areas = areas or {}
        self.monsters = monsters or {}

        self.state = "MENU"
        self.current_area: Optional[HuntingArea] = None   # S006 compat
        self.current_destination: Optional[Destination] = None
        self.active_monster: Optional[Monster] = None
        self.events_history: List[DomainEvent] = []
        self.tick = 100

        # Counters for hunt session
        self.kills_this_hunt: int = 0
        self.total_kills: int = 0

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Returns structured, machine-readable player and session state."""
        nearby = self.population.get_monsters_near(
            self.player.map_id, self.player.x, self.player.y, radius=20
        )
        equip_status = self.equipment_mgr.status(self.player)
        return {
            "player": {
                "name": self.player.name,
                "class_type": self.player.class_type,
                "level": self.player.level,
                "hp": self.player.hp,
                "max_hp": self.player.max_hp,
                "exp": self.player.exp,
                "str": self.player.str,
                "dex": self.player.dex,
                "con": self.player.con,
                "map_id": self.player.map_id,
                "x": self.player.x,
                "y": self.player.y,
                "heading": self.player.heading,
                "alive": not self.player.is_dead,
            },
            "location": {
                "map_id": self.player.map_id,
                "x": self.player.x,
                "y": self.player.y,
                "destination": self.current_destination.name if self.current_destination else None,
            },
            "equipment": equip_status,
            "target": {
                "name": self.active_monster.name,
                "level": self.active_monster.level,
                "hp": self.active_monster.hp,
                "max_hp": self.active_monster.max_hp,
                "alive": not self.active_monster.is_dead,
            } if self.active_monster and not self.active_monster.is_dead else None,
            "nearby_monsters": [
                {"name": m.name, "level": m.level, "hp": m.hp, "dist": max(abs(m.pos.x - self.player.x), abs(m.pos.y - self.player.y))}
                for m in nearby[:5]
            ],
            "session_state": self.state,
            "kills_total": self.total_kills,
        }

    # ------------------------------------------------------------------
    # Equipment
    # ------------------------------------------------------------------

    def equip(self, item_id: int) -> Tuple[bool, str, List[DomainEvent]]:
        self.tick += 1
        ok, reason, evts = self.equipment_mgr.equip(self.player, item_id, self.tick)
        self.events_history.extend(evts)
        return ok, reason, evts

    def unequip(self) -> Tuple[bool, str, List[DomainEvent]]:
        self.tick += 1
        ok, reason, evts = self.equipment_mgr.unequip(self.player, self.tick)
        self.events_history.extend(evts)
        return ok, reason, evts

    # ------------------------------------------------------------------
    # Autonomous Travel (move_to)
    # ------------------------------------------------------------------

    def move_to(
        self, destination_id: str, log_callback=None
    ) -> Tuple[bool, str, List[DomainEvent]]:
        """
        Autonomously travels to destination_id.

        Executes route step by step. After each step, checks for nearby aggressive
        monsters (aggro=1). If encounter found, auto-resolves combat, then resumes.

        Returns: (success, reason, all_events)
        """
        if self.player.is_dead:
            return False, "PLAYER_DEAD", []

        dest = self.destinations.get(destination_id)
        if not dest:
            return False, "INVALID_DESTINATION", []

        if (self.player.map_id, self.player.x, self.player.y) == (dest.map_id, dest.x, dest.y):
            self.current_destination = dest
            self.state = "HUNTING"
            return True, "ALREADY_AT_DESTINATION", []

        self.state = "TRAVELING"
        all_events: List[DomainEvent] = []

        # Plan world route
        route = WorldRoutePlanner.plan(
            start_map=self.player.map_id,
            start_x=self.player.x,
            start_y=self.player.y,
            goal_map=dest.map_id,
            goal_x=dest.x,
            goal_y=dest.y,
            transition_provider=self.transition_provider,
            map_registry=self.world.maps,
        )

        if not route.is_valid:
            self.state = "MENU"
            return False, f"ROUTE_FAILED_{route.error_reason}", []

        # Execute route step-by-step with encounter checks
        ok, nav_events, status = WorldRouteExecutor.execute_with_encounter_hook(
            world=self.world,
            actor_id=self.player.id,
            route=route,
            start_pos=(self.player.x, self.player.y),
            goal_pos=(dest.x, dest.y),
            transition_engine=self.transition_engine,
            start_tick=self.tick,
            encounter_hook=self._travel_encounter_hook,
            log_callback=log_callback,
        )

        all_events.extend(nav_events)
        self.events_history.extend(nav_events)
        if nav_events:
            self.tick = nav_events[-1].tick + 10

        if not ok:
            if self.player.is_dead:
                self.state = "DEAD"
                return False, "PLAYER_DIED_IN_TRAVEL", all_events
            self.state = "MENU"
            return False, f"EXECUTION_FAILED_{status}", all_events

        self.current_destination = dest
        self.state = "HUNTING"
        return True, "ARRIVED", all_events

    def _travel_encounter_hook(self, log_callback=None) -> List[DomainEvent]:
        """
        Called after each movement step during travel.
        Checks for monsters nearby within radius 2.
        If found, auto-resolves combat and returns events.
        """
        enc = EncounterSystem.check_encounter(
            self.player, self.population, radius=2, aggressive_only=False
        )
        if enc is None:
            return []
        # Encountered a monster during travel
        evts = self._run_auto_combat(enc, log_callback=log_callback)
        return evts

    # ------------------------------------------------------------------
    # Autonomous Hunt & Real-Time Simulation Loop (S007.2)
    # ------------------------------------------------------------------

    def approach_target(self, target: Monster, log_callback=None) -> Tuple[bool, List[DomainEvent]]:
        """
        Approaches target step-by-step until within melee attack range (Chebyshev distance <= 1).
        Uses A* pathfinding on the current map grid.
        Advances simulation clock by player.move_speed_ms per step.
        """
        events: List[DomainEvent] = []
        grid = self.world.get_map(self.player.map_id)
        if not grid:
            return False, events

        move_engine = MovementEngine(grid)
        dist = max(abs(self.player.x - target.pos.x), abs(self.player.y - target.pos.y))
        if dist <= 1:
            return True, events

        if log_callback:
            log_callback("approach", f"[接近目標] 發現 {target.name} ({target.pos.x}, {target.pos.y})，距離 {dist} 格，開始前進...")

        headings = AStarPlanner.find_path(grid, self.player.x, self.player.y, target.pos.x, target.pos.y)
        if not headings:
            return False, events

        for h in headings:
            cur_dist = max(abs(self.player.x - target.pos.x), abs(self.player.y - target.pos.y))
            if cur_dist <= 1:
                break
            if self.player.is_dead:
                return False, events

            self.tick += 10
            self.clock.advance_by(self.player.move_speed_ms)
            step_evs = move_engine.execute_cmd_move(self.player, h, tick=self.tick)
            events.extend(step_evs)

            if log_callback:
                rem_dist = max(abs(self.player.x - target.pos.x), abs(self.player.y - target.pos.y))
                log_callback("step", f"  邁步走向目標: ({self.player.x}, {self.player.y}) [剩餘 {rem_dist} 格]")

            if any(ev.__class__.__name__ == 'MoveBlocked' for ev in step_evs):
                break

        final_dist = max(abs(self.player.x - target.pos.x), abs(self.player.y - target.pos.y))
        return final_dist <= 1, events

    def roam_search(self, radius: int = 14, max_steps: int = 15, log_callback=None) -> Tuple[Optional[Monster], List[DomainEvent]]:
        """
        Roams the map in search of monsters when none are in immediate sight (14 tiles).
        Paces movement with clock.advance_by(player.move_speed_ms).
        Re-scans for monsters after each step. Returns (target, events) if found.
        """
        events: List[DomainEvent] = []
        grid = self.world.get_map(self.player.map_id)
        if not grid:
            return None, events

        move_engine = MovementEngine(grid)
        if log_callback:
            log_callback("roam", f"[巡邏漫遊] 當前視野內無怪物，展開周邊巡邏漫遊 (最長 {max_steps} 步)...")

        for step_idx in range(max_steps):
            if self.player.is_dead:
                return None, events

            # Check if monster entered sight
            target = EncounterSystem.find_hunt_target(self.player, self.population, radius=radius)
            if target is not None:
                if log_callback:
                    log_callback("roam", f"[發現獵物] 巡邏時發現 {target.name} ({target.pos.x}, {target.pos.y})！")
                return target, events

            # Pick a passable heading
            cand_headings = list(range(8))
            chosen_h = None
            for h in cand_headings:
                dest_x, dest_y = MovementEngine._apply_heading(self.player.x, self.player.y, h)
                if grid.is_in_bounds(dest_x, dest_y) and grid.is_passable(dest_x, dest_y):
                    chosen_h = h
                    break

            if chosen_h is None:
                break

            self.tick += 10
            self.clock.advance_by(self.player.move_speed_ms)
            step_evs = move_engine.execute_cmd_move(self.player, chosen_h, tick=self.tick)
            events.extend(step_evs)

            target = EncounterSystem.find_hunt_target(self.player, self.population, radius=radius)
            if target is not None:
                if log_callback:
                    log_callback("roam", f"[發現獵物] 巡邏時發現 {target.name} ({target.pos.x}, {target.pos.y})！")
                return target, events

        return None, events

    def hunt(
        self, kill_limit: int = 5, log_callback=None
    ):
        """
        Autonomous hunting loop (S007.2 Authentic World Runtime).
        Features:
          - Target acquisition within 14-tile sight
          - Autonomous Approaching (A* step-by-step advance to melee range)
          - Autonomous Roaming when no targets in sight
          - Cadenced combat matching Legacy action cadence
        """
        if self.current_area is not None and self.monsters and not self.destinations:
            return self.s006_hunt()

        if self.player.is_dead:
            return False, "PLAYER_DEAD", []

        self.state = "HUNTING"
        all_events: List[DomainEvent] = []
        self.kills_this_hunt = 0

        while self.kills_this_hunt < kill_limit:
            if self.player.is_dead:
                self.state = "DEAD"
                return False, "PLAYER_DEAD", all_events

            # 1. Target Acquisition (Legacy sight radius = 14)
            target = EncounterSystem.find_hunt_target(
                self.player, self.population, radius=14
            )

            # 2. Roaming if no targets in sight
            if target is None:
                target, roam_evts = self.roam_search(radius=14, max_steps=15, log_callback=log_callback)
                all_events.extend(roam_evts)
                self.events_history.extend(roam_evts)
                if target is None:
                    break

            # 3. Approaching Target
            reached_melee, app_evts = self.approach_target(target, log_callback=log_callback)
            all_events.extend(app_evts)
            self.events_history.extend(app_evts)
            if not reached_melee:
                continue

            # 4. Cadenced Combat
            evts = self._run_auto_combat(target, log_callback=log_callback)
            all_events.extend(evts)

            if self.player.is_dead:
                self.state = "DEAD"
                return False, "PLAYER_DEAD", all_events

        reason = "KILL_LIMIT_REACHED" if self.kills_this_hunt >= kill_limit else "NO_TARGETS"
        self.state = "HUNTING"
        return True, reason, all_events

    # ------------------------------------------------------------------
    # Auto Combat Engine
    # ------------------------------------------------------------------

    def _run_auto_combat(
        self, monster: Monster, log_callback=None
    ) -> List[DomainEvent]:
        """
        Fully automatic combat loop against a single monster.

        LEGACY_OBSERVED combat cadence:
        - Player Attack: player.attack_speed_ms (880ms for Male Knight sword)
        - Monster Counter-Attack: monster.attack_speed_ms from sprite_frame.sql
        """
        if monster.is_dead or self.player.is_dead:
            return []

        events: List[DomainEvent] = []
        self.active_monster = monster

        # Emit encounter event
        self.tick += 10
        events.append(EncounterTriggered(
            tick=self.tick,
            actor_id=self.player.id,
            monster_id=monster.uid,
            monster_name=monster.name,
            x=monster.pos.x,
            y=monster.pos.y,
        ))

        if log_callback:
            log_callback("encounter", f"[遭遇] {monster.name} (Lv{monster.level} HP:{monster.hp})")

        # Combat loop
        max_rounds = 200  # Safety limit
        for _round in range(max_rounds):
            if self.player.is_dead or monster.is_dead:
                break

            self.tick += 30
            cur_tick = self.tick
            self.clock.advance_by(self.player.attack_speed_ms)

            # --- Player attacks Monster ---
            events.append(AttackStarted(tick=cur_tick, attacker_id=self.player.id, target_id=monster.uid))

            weapon = self.player.equipped_weapon
            if weapon:
                is_hit = CanonicalCombat.resolve_hit(self.player, monster, weapon, self.rng)
            else:
                is_hit = True

            events.append(HitResolved(tick=cur_tick, attacker_id=self.player.id, target_id=monster.uid, is_hit=is_hit))

            p_dmg = 0
            if is_hit:
                if weapon:
                    p_dmg = CanonicalCombat.calculate_damage(self.player, monster, weapon, self.rng)
                else:
                    p_dmg = self.rng.rand(0, 1, "BareHand")
                events.append(DamageApplied(tick=cur_tick, attacker_id=self.player.id, target_id=monster.uid, damage=p_dmg))

            old_m_hp = monster.hp
            new_m_hp = max(0, old_m_hp - p_dmg)
            monster.hp = new_m_hp
            if p_dmg > 0 or old_m_hp != new_m_hp:
                events.append(HpChanged(tick=cur_tick, entity_id=monster.uid, old_hp=old_m_hp, new_hp=new_m_hp))

            if log_callback:
                log_callback("combat", f"  Player→{monster.name}: {'命中' if is_hit else '未中'} {p_dmg} | HP: {new_m_hp}/{monster.max_hp}")

            # Check monster death
            if new_m_hp == 0:
                monster.is_dead = True
                self.population.despawn(monster)
                events.append(MonsterDied(tick=cur_tick, monster_id=monster.uid))

                exp_gained = monster.exp
                self.player.exp += exp_gained
                events.append(ExperienceGranted(
                    tick=cur_tick,
                    actor_id=self.player.id,
                    exp_gained=exp_gained,
                    total_exp=self.player.exp,
                    lawful=self.player.lawful,
                ))

                self.kills_this_hunt += 1
                self.total_kills += 1

                if log_callback:
                    log_callback("kill", f"[擊殺] {monster.name} +{exp_gained} EXP (total: {self.player.exp})")

                # Check level-up
                lu = self.progression.check_level_up(self.player)
                if lu:
                    old_lv, new_lv, new_max_hp = lu
                    events.append(LevelUpEvent(
                        tick=cur_tick,
                        actor_id=self.player.id,
                        old_level=old_lv,
                        new_level=new_lv,
                        new_max_hp=new_max_hp,
                    ))
                    if log_callback:
                        log_callback("levelup", f"[升級!] Lv{old_lv} → Lv{new_lv}! MaxHP: {new_max_hp}")

                self.active_monster = None
                self.events_history.extend(events)
                return events

            # --- Monster counter-attacks Player ---
            # LEGACY_OBSERVED: Character.java L1491-1499
            # dmg = rand(min_dmg, max_dmg) - rand(1, total_ac); no HitFigure
            self.tick += 30
            cur_tick = self.tick
            self.clock.advance_by(monster.attack_speed_ms)

            m_min = monster.min_dmg
            m_max = monster.max_dmg
            if m_max > 0:
                m_raw = self.rng.rand(m_min, m_max, "MonsterDmg")
            else:
                m_raw = 0  # Monster has no attack (e.g. Floating Eye min_dmg=0 max_dmg=0)

            # LEGACY_OBSERVED: monster attack reduces by rand(1, totalAc) if player has AC
            player_ac = getattr(self.player, 'ac', 10)
            if player_ac > 0 and m_raw > 0:
                ac_reduce = self.rng.rand(1, player_ac, "MonsterAcReduce")
                m_dmg = max(0, m_raw - ac_reduce)
            else:
                m_dmg = m_raw

            if m_dmg > 0:
                events.append(DamageApplied(tick=cur_tick, attacker_id=monster.uid, target_id=self.player.id, damage=m_dmg))

            old_p_hp = self.player.hp
            new_p_hp = max(0, old_p_hp - m_dmg)
            self.player.hp = new_p_hp
            if m_dmg > 0:
                events.append(HpChanged(tick=cur_tick, entity_id=self.player.id, old_hp=old_p_hp, new_hp=new_p_hp))

            if log_callback:
                log_callback("combat", f"  {monster.name}→Player: {m_dmg} | HP: {new_p_hp}/{self.player.max_hp}")

            # Check player death
            if new_p_hp == 0:
                self.player.is_dead = True
                self.state = "DEAD"
                self.active_monster = None
                self.events_history.extend(events)
                if log_callback:
                    log_callback("death", "[死亡] 玩家陣亡！")
                return events

        self.events_history.extend(events)
        return events

    # ------------------------------------------------------------------
    # S006 Backward Compatibility (used by mvp.py --demo / mvp_replay.py)
    # ------------------------------------------------------------------

    def select_hunting_area(self, area_id: str) -> Tuple[bool, str, List[DomainEvent]]:
        """S006 legacy: navigate to a HuntingArea."""
        if area_id not in self.areas:
            return False, "INVALID_AREA", []
        if self.player.is_dead:
            return False, "PLAYER_DEAD", []

        target_area = self.areas[area_id]
        if (self.player.map_id, self.player.x, self.player.y) == (target_area.map_id, target_area.goal_x, target_area.goal_y):
            self.current_area = target_area
            self.state = "HUNTING"
            return True, "ALREADY_AT_DESTINATION", []

        self.state = "TRAVELING"

        route = WorldRoutePlanner.plan(
            start_map=self.player.map_id,
            start_x=self.player.x,
            start_y=self.player.y,
            goal_map=target_area.map_id,
            goal_x=target_area.goal_x,
            goal_y=target_area.goal_y,
            transition_provider=self.transition_provider,
            map_registry=self.world.maps,
        )

        if not route.is_valid:
            self.state = "MENU"
            return False, f"ROUTE_FAILED_{route.error_reason}", []

        success, nav_events, status = WorldRouteExecutor.execute(
            world=self.world,
            actor_id=self.player.id,
            route=route,
            start_pos=(self.player.x, self.player.y),
            goal_pos=(target_area.goal_x, target_area.goal_y),
            transition_engine=self.transition_engine,
            start_tick=self.tick,
        )

        self.events_history.extend(nav_events)
        if nav_events:
            self.tick = nav_events[-1].tick + 10

        if not success:
            self.state = "MENU"
            return False, f"EXECUTION_FAILED_{status}", nav_events

        self.current_area = target_area
        self.state = "HUNTING"
        self.active_monster = None
        return True, "ARRIVED", nav_events

    def _spawn_s006_monster(self) -> Optional[Monster]:
        """S006 legacy: spawn a fixed MonsterTemplate-based monster."""
        if not self.current_area:
            return None
        tmpl = self.monsters.get(self.current_area.monster_type)
        if not tmpl:
            return None
        return Monster(
            id=tmpl.id, uid=tmpl.id,
            name=tmpl.name, level=tmpl.level,
            hp=tmpl.hp, max_hp=tmpl.max_hp,
            ac=tmpl.ac, exp=tmpl.exp, size=tmpl.size,
            pos=Position(self.player.x, self.player.y, self.player.map_id),
            heading=4, inventory=Inventory(), is_dead=False,
            min_dmg=tmpl.atk_min, max_dmg=tmpl.atk_max,
        )

    def s006_hunt(self) -> Tuple[bool, Optional[Monster], str]:
        """S006 legacy: triggers a single monster encounter from MonsterTemplate."""
        if self.player.is_dead:
            return False, None, "PLAYER_DEAD"
        if not self.current_area:
            return False, None, "NO_HUNTING_AREA_SELECTED"
        monster = self._spawn_s006_monster()
        if not monster:
            return False, None, "UNKNOWN_MONSTER_TEMPLATE"
        self.active_monster = monster
        self.state = "COMBAT"
        return True, monster, "ENCOUNTER_STARTED"

    # Keep the old `hunt()` callable name for S006 compat via explicit call site
    # (mvp.py calls session.hunt() which now maps to the NEW autonomous hunt)
    # For S006 replay scripts that need the old single-spawn behavior, they call s006_hunt()

    def attack(self) -> Tuple[bool, dict, str]:
        """
        S006 legacy: single turn of turn-based combat.
        Uses the active_monster set by s006_hunt().
        """
        if self.player.is_dead:
            return False, {}, "PLAYER_DEAD"
        if not self.active_monster or self.active_monster.is_dead:
            return False, {}, "NO_ACTIVE_TARGET"

        self.tick += 10
        cur_tick = self.tick

        # Player attacks
        self.events_history.append(AttackStarted(tick=cur_tick, attacker_id=self.player.id, target_id=self.active_monster.id))
        weapon = self.player.equipped_weapon
        is_hit = CanonicalCombat.resolve_hit(self.player, self.active_monster, weapon, self.rng) if weapon else True
        self.events_history.append(HitResolved(tick=cur_tick, attacker_id=self.player.id, target_id=self.active_monster.id, is_hit=is_hit))

        p_dmg = 0
        if is_hit:
            if weapon:
                p_dmg = CanonicalCombat.calculate_damage(self.player, self.active_monster, weapon, self.rng)
            else:
                p_dmg = self.rng.rand(0, 1, "BareHand")
            self.events_history.append(DamageApplied(tick=cur_tick, attacker_id=self.player.id, target_id=self.active_monster.id, damage=p_dmg))

        old_m_hp = self.active_monster.hp
        new_m_hp = max(0, old_m_hp - p_dmg)
        self.active_monster.hp = new_m_hp
        self.events_history.append(HpChanged(tick=cur_tick, entity_id=self.active_monster.id, old_hp=old_m_hp, new_hp=new_m_hp))

        if new_m_hp == 0:
            self.active_monster.is_dead = True
            self.events_history.append(MonsterDied(tick=cur_tick, monster_id=self.active_monster.id))
            exp_gained = self.active_monster.exp
            self.player.exp += exp_gained
            self.events_history.append(ExperienceGranted(
                tick=cur_tick, actor_id=self.player.id,
                exp_gained=exp_gained, total_exp=self.player.exp, lawful=self.player.lawful,
            ))
            self.state = "HUNTING"
            turn_result = {
                "player_hit": is_hit, "player_dmg": p_dmg,
                "monster_hp": 0, "monster_max_hp": self.active_monster.max_hp,
                "monster_hit": False, "monster_dmg": 0,
                "player_hp": self.player.hp, "player_max_hp": self.player.max_hp,
                "exp_gained": exp_gained, "outcome": "VICTORY",
            }
            return True, turn_result, "VICTORY"

        # Monster counter-attack (LEGACY_OBSERVED formula)
        self.tick += 10
        cur_tick = self.tick
        m_min = self.active_monster.min_dmg
        m_max = self.active_monster.max_dmg
        # Fall back to template atk_min/max if min_dmg==0 (S006 compat)
        if m_max == 0:
            tmpl = self.monsters.get(self.current_area.monster_type if self.current_area else "")
            if tmpl:
                m_min, m_max = tmpl.atk_min, tmpl.atk_max

        hit_roll = self.rng.rand(1, 20, "MonsterHitCheck")
        m_hit = hit_roll >= 5
        m_dmg = 0
        if m_hit:
            if m_max > 0:
                m_dmg = self.rng.rand(m_min, m_max, "MonsterDmgRoll")
            self.events_history.append(DamageApplied(tick=cur_tick, attacker_id=self.active_monster.id, target_id=self.player.id, damage=m_dmg))

        old_p_hp = self.player.hp
        new_p_hp = max(0, old_p_hp - m_dmg)
        self.player.hp = new_p_hp
        self.events_history.append(HpChanged(tick=cur_tick, entity_id=self.player.id, old_hp=old_p_hp, new_hp=new_p_hp))

        if new_p_hp == 0:
            self.player.is_dead = True
            self.state = "DEAD"
            outcome = "DEFEAT"
        else:
            outcome = "ONGOING"

        turn_result = {
            "player_hit": is_hit, "player_dmg": p_dmg,
            "monster_hp": self.active_monster.hp, "monster_max_hp": self.active_monster.max_hp,
            "monster_hit": m_hit, "monster_dmg": m_dmg,
            "player_hp": self.player.hp, "player_max_hp": self.player.max_hp,
            "exp_gained": 0, "outcome": outcome,
        }
        return True, turn_result, outcome
