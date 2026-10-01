"""
native_engine/bot/perception.py - Headless Perception System

Architecture:
  - Extracts immediate environmental, entity, and internal state for bot decision making.
  - Pure state extraction: zero graphics, zero OCR, zero framebuffer simulation.
  - Spatial perception queries canonical WorldMapGrid and PopulationManager.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from ..model import Actor, Monster, Position, Inventory, Weapon
from ..population import PopulationManager
from ..map import WorldMapGrid
from .drop import GroundDrop


@dataclass
class PerceptionSnapshot:
    """
    Immutable snapshot of the bot's perception at a single point in time.
    """
    player_id: int
    name: str
    level: int
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    pos: Position
    is_dead: bool
    combat_state: str           # "IDLE", "IN_COMBAT", "DEAD"
    equipped_weapon: Optional[Weapon]
    inventory: Inventory
    nearby_monsters: List[Monster]
    nearby_drops: List[GroundDrop]
    target_monster: Optional[Monster]
    target_distance: Optional[int]    # Chebyshev distance
    is_target_in_melee: bool


class PerceptionSystem:
    """
    Perception extractor querying the world state around the player.
    """
    def __init__(self, sight_radius: int = 14):
        self.sight_radius = sight_radius

    def perceive(
        self,
        player: Actor,
        population: PopulationManager,
        ground_drops: List[GroundDrop],
        active_target: Optional[Monster] = None,
        combat_state: str = "IDLE",
    ) -> PerceptionSnapshot:
        """
        Builds a comprehensive perception snapshot of the player and environment.
        """
        # 1. Query nearby alive monsters within sight radius
        nearby_monsters = population.get_monsters_near(
            map_id=player.map_id,
            x=player.x,
            y=player.y,
            radius=self.sight_radius
        )

        # 2. Filter target status
        target = None
        target_dist = None
        in_melee = False

        if active_target is not None and not active_target.is_dead and active_target.pos.map_id == player.map_id:
            target = active_target
            dx = abs(target.pos.x - player.x)
            dy = abs(target.pos.y - player.y)
            target_dist = max(dx, dy)
            in_melee = (target_dist == 1)

        # 3. Query nearby ground drops on the same map
        nearby_drops = [
            d for d in ground_drops
            if d.pos.map_id == player.map_id and max(abs(d.pos.x - player.x), abs(d.pos.y - player.y)) <= self.sight_radius
        ]

        # 4. Determine combat state
        if player.is_dead:
            effective_state = "DEAD"
        elif target is not None:
            effective_state = "IN_COMBAT"
        else:
            effective_state = combat_state

        return PerceptionSnapshot(
            player_id=player.id,
            name=player.name,
            level=player.level,
            hp=player.hp,
            max_hp=player.max_hp,
            mp=player.mp,
            max_mp=player.max_mp,
            pos=Position(player.x, player.y, player.map_id),
            is_dead=player.is_dead,
            combat_state=effective_state,
            equipped_weapon=player.equipped_weapon,
            inventory=player.inventory,
            nearby_monsters=nearby_monsters,
            nearby_drops=nearby_drops,
            target_monster=target,
            target_distance=target_dist,
            is_target_in_melee=in_melee,
        )
