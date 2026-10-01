"""
native_engine/progression.py - Character Progression Manager (LEGACY_OBSERVED)

Handles EXP accumulation and level-up events.

LEGACY_OBSERVED basis (PcInstance.java:552-598, Character.java:948-1033):
- Level threshold: exp >= ExpTable.get_bonus(level) triggers level up
- exp_table format: {level: {"cumulative_exp": N, "hp_increase": ...}}
- For Knight (class_type=1): HP increase = max(6, con-9) + rand(1..6) per level
  Simplified: we use con-based increase with deterministic RNG.

CONTROLLED_SUBSTITUTION for HP increase:
- Full Legacy uses complex rand(1,64) distribution tables
- We implement max(6, con-9) + fixed increment=3 (midpoint of 1..6) for determinism
  unless rng is provided, in which case we sample.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Actor
    from .events import LevelUp
    from .rng import NativeRng


@dataclass
class ExpTableEntry:
    level: int
    cumulative_exp: int     # LEGACY_OBSERVED: 'bonus' field from exp.sql


class ProgressionManager:
    """
    Manages character EXP and level-up logic derived from Legacy ExpTable.

    LEGACY_OBSERVED: PcInstance.addExp() → expChange() → level up detection
    Loop: find highest level where exp >= bonus_cumulative
    """

    def __init__(self, exp_table: Dict[int, int], rng: Optional["NativeRng"] = None):
        """
        exp_table: dict mapping level (int) -> cumulative_exp threshold (int)
        e.g. {1: 0, 2: 20, 3: 45, 4: 80, 5: 630, ...}
        """
        self.exp_table = exp_table  # level -> min_cumulative_exp_to_reach_level
        self.rng = rng

    @classmethod
    def from_contract(cls, contract: dict, rng: Optional["NativeRng"] = None) -> "ProgressionManager":
        raw = contract.get("exp_table", {})
        # Convert string keys to int keys, value is cumulative exp needed
        table = {}
        for k, v in raw.items():
            lv = int(k)
            table[lv] = v["cumulative_exp"] if isinstance(v, dict) else int(v)
        return cls(table, rng)

    def check_level_up(self, actor: "Actor") -> Optional[Tuple[int, int, int]]:
        """
        Checks if actor should level up based on current EXP.
        Returns (old_level, new_level, new_max_hp) if level-up occurred, else None.

        LEGACY_OBSERVED: iterates level thresholds from low to high,
        finds the highest level where exp >= threshold.
        """
        current_level = actor.level
        new_level = current_level

        # Find highest achievable level
        for lv in sorted(self.exp_table.keys()):
            if lv <= current_level:
                continue
            threshold = self.exp_table[lv]
            if actor.exp >= threshold:
                new_level = lv

        if new_level <= current_level:
            return None

        # Apply level-up
        old_level = actor.level
        actor.level = new_level

        # HP increase per level gained (CONTROLLED_SUBSTITUTION: midpoint of Legacy formula)
        # Legacy Knight: max(6, con-9) + rand(1..6) per level, then full restore
        hp_increase = 0
        for _ in range(new_level - old_level):
            base = max(6, actor.con - 9)
            if self.rng:
                rand_bonus = self.rng.rand(1, 6, "LevelUpHp")
            else:
                rand_bonus = 3  # Deterministic midpoint
            hp_increase += base + rand_bonus

        actor.max_hp += hp_increase
        # LEGACY_OBSERVED: Level up fully restores HP and MP
        actor.hp = actor.max_hp

        return (old_level, new_level, actor.max_hp)

    def get_exp_for_level(self, level: int) -> int:
        """Returns cumulative EXP required to reach the given level."""
        return self.exp_table.get(level, 0)

    def next_level_exp(self, actor: "Actor") -> Optional[int]:
        """Returns EXP needed for next level, or None if max level in table."""
        next_lv = actor.level + 1
        return self.exp_table.get(next_lv)
