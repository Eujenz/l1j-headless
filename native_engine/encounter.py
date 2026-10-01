"""
native_engine/encounter.py - Encounter System (MODERN_DESIGN + LEGACY_OBSERVED semantics)

Handles proximity-based monster encounter detection.

LEGACY_OBSERVED basis:
- MonsterInstance.java SearchPlayer / toFight: monsters detect players within ~2-cell range
- agro=1 monsters actively seek players; agro=0 monsters are passive (only attacked first)
- For MVP: passive monsters CAN be targeted by player hunting loop (player approaches them)
  but will not independently chase player before being targeted.

CONTROLLED_SUBSTITUTION:
- Full L1J AOI grid is not implemented. We use Chebyshev distance radius=2 as the
  detection boundary, matching the archaeology finding of 2-grid proximity semantics.
"""
from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Actor, Monster
    from .population import PopulationManager


class EncounterSystem:
    """
    Detects and selects encounter targets based on world population and player position.

    PROVENANCE: CONTROLLED_SUBSTITUTION
    - Detection radius 2 derived from Legacy MonsterInstance SearchPlayer proximity analysis
    - Agro monsters are considered 'hostile and pursuing'; passive monsters are
      'available as hunt targets' (player can engage but they don't self-trigger)
    """

    @staticmethod
    def check_encounter(
        player: "Actor",
        population: "PopulationManager",
        radius: int = 2,
        aggressive_only: bool = False,
    ) -> Optional["Monster"]:
        """
        Returns the nearest valid encounter target within radius of the player.

        Parameters:
        - aggressive_only: if True, only returns monsters with agro=1 (like Legacy
          SearchPlayer which only agro monsters self-trigger).
          If False (default for hunt mode): returns any alive monster in range.

        Returns None if no valid target found.
        """
        nearby = population.get_monsters_near(
            map_id=player.map_id,
            x=player.x,
            y=player.y,
            radius=radius,
        )
        for monster in nearby:
            if monster.is_dead:
                continue
            if aggressive_only and monster.agro == 0:
                continue
            return monster  # First (nearest + lowest uid) is selected
        return None

    @staticmethod
    def find_hunt_target(
        player: "Actor",
        population: "PopulationManager",
        radius: int = 20,
    ) -> Optional["Monster"]:
        """
        Finds the nearest available monster within a wider 'hunt radius'.
        Used by the hunting loop to locate the next target after a kill.

        MODERN_DESIGN: hunt radius=20 is a design choice for MVP.
        In Legacy, player-initiated hunt means walking toward monsters.
        """
        nearby = population.get_monsters_near(
            map_id=player.map_id,
            x=player.x,
            y=player.y,
            radius=radius,
        )
        for monster in nearby:
            if not monster.is_dead:
                return monster
        return None

    @staticmethod
    def is_valid_target(monster: "Monster") -> bool:
        """Basic target validity check."""
        return not monster.is_dead
