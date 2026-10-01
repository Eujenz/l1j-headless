"""
native_engine/spr_action.py - L1J 1.82 SprTable & Action Timing Resolution

LEGACY_OBSERVED:
  - Source: C:/Users/p0282768/Documents/Gemini/Lineage182c/db/lineage/sprite_frame.sql
  - Consumer: net.database.SprTable, net.check.CheckSpeed
  - Canonical Timing Spec: docs/archaeology/canonical_timing_spec.md
"""
from typing import Dict, Optional, Tuple
from .model import Weapon


# Canonical action IDs for PC physical attacks
ACTION_WALK_DEFAULT = 0
ACTION_ATTACK_BARE = 1
ACTION_WALK_SWORD = 4
ACTION_ATTACK_SWORD = 5
ACTION_WALK_AXE = 11
ACTION_ATTACK_AXE = 12
ACTION_SPELL_DIR = 18
ACTION_SPELL_NODIR = 19
ACTION_WALK_BOW = 20
ACTION_ATTACK_BOW = 21
ACTION_WALK_SPEAR = 24
ACTION_ATTACK_SPEAR = 25
ACTION_WALK_STAFF = 40
ACTION_ATTACK_STAFF = 41
ACTION_ATTACK_DUALBLADE = 47
ACTION_ATTACK_CLAW = 51

# Canonical Embedded Timing Data extracted from db/lineage/sprite_frame.sql
# Format: gfx: {action_id: cadence_ms}
CANONICAL_SPRITE_FRAME: Dict[int, Dict[int, int]] = {
    # 0: 王子 (Prince)
    0: {0: 640, 1: 840, 4: 640, 5: 1000, 18: 880, 19: 800, 20: 640, 21: 1600, 24: 640, 25: 880},
    # 1: 公主 (Princess)
    1: {0: 640, 1: 880, 4: 640, 5: 960, 18: 880, 19: 800, 20: 640, 21: 1520, 24: 640, 25: 1040},
    # 37: 女妖精 (Female Elf)
    37: {0: 640, 1: 800, 4: 640, 5: 760, 18: 880, 19: 800, 20: 640, 21: 960, 24: 640, 25: 1120},
    # 48: 女騎士 (Female Knight)
    48: {0: 640, 1: 1000, 4: 640, 5: 920, 11: 640, 12: 920, 18: 800, 19: 800, 20: 640, 21: 1840, 24: 640, 25: 1000, 40: 640, 41: 920},
    # 61: 男騎士 (Male Knight)
    61: {0: 640, 1: 880, 4: 640, 5: 880, 11: 640, 12: 880, 18: 880, 19: 800, 20: 640, 21: 1920, 24: 640, 25: 920, 40: 640, 41: 880},
    # 138: 男妖精 (Male Elf)
    138: {0: 640, 1: 760, 4: 640, 5: 800, 11: 640, 12: 1040, 18: 880, 19: 800, 20: 640, 21: 960, 24: 640, 25: 1080, 40: 640, 41: 920},
    # 734: 男法師 (Male Wizard)
    734: {0: 640, 1: 960, 4: 640, 5: 1120, 18: 880, 19: 800, 20: 640, 21: 2280, 24: 640, 25: 1200, 40: 640, 41: 1200},
    # 1186: 女法師 (Female Wizard)
    1186: {0: 640, 1: 1000, 4: 640, 5: 1120, 11: 640, 12: 1080, 18: 880, 19: 800, 20: 640, 21: 2240, 24: 640, 25: 1160, 40: 640, 41: 1160},
}


class SprTable:
    """
    Python equivalent of net.database.SprTable.
    Resolves movement, attack, and skill cadence for player and monster sprites.
    """
    _instance: Optional["SprTable"] = None

    def __init__(self, table_data: Optional[Dict[int, Dict[int, int]]] = None):
        self.table = table_data if table_data is not None else CANONICAL_SPRITE_FRAME

    @classmethod
    def get_instance(cls) -> "SprTable":
        if cls._instance is None:
            cls._instance = SprTable()
        return cls._instance

    def get_move_speed(self, gfx: int, act_id: int = ACTION_WALK_DEFAULT) -> int:
        """
        Legacy observed: SprTable.getMoveSpeed(sprid, actid)
        Fallback: if actid != 0, returns moveSpeed.get(0, 640).
        """
        actions = self.table.get(gfx)
        if actions:
            if act_id in actions:
                return actions[act_id]
            if 0 in actions:
                return actions[0]
        return 640

    def get_attack_speed(self, gfx: int, act_id: int = ACTION_ATTACK_BARE) -> int:
        """
        Legacy observed: SprTable.getAttackSpeed(sprid, actid)
        Fallback: if actid != 1, returns attackSpeed.get(1, 920).
        """
        actions = self.table.get(gfx)
        if actions:
            if act_id in actions:
                return actions[act_id]
            if ACTION_ATTACK_BARE in actions:
                return actions[ACTION_ATTACK_BARE]
        return 920

    def resolve_pc_attack_interval(
        self,
        gfx: int,
        weapon: Optional[Weapon] = None,
        action: Optional[int] = None,
        fallback: int = 920,
    ) -> int:
        """
        Dynamically determine PC attack interval from Player GFX + Action + Weapon.
        Matches CheckSpeed.java: getRightInterval(ACT_TYPE.ATTACK):
          interval = SprTable.getAttackSpeed(pc.getGfx(), pc.getGfxMode() + 1)
        """
        if action is not None:
            return self.get_attack_speed(gfx, action)

        if weapon is None:
            return self.get_attack_speed(gfx, ACTION_ATTACK_BARE)

        if isinstance(weapon.weapon_type, str):
            w_type = weapon.weapon_type.lower()
        else:
            # Integer or fallback: check name
            name_lower = weapon.name.lower()
            if "bow" in name_lower or "crossbow" in name_lower:
                w_type = "bow"
            elif "spear" in name_lower or "lance" in name_lower:
                w_type = "spear"
            elif "axe" in name_lower:
                w_type = "axe"
            elif "staff" in name_lower or "wand" in name_lower:
                w_type = "staff"
            elif "claw" in name_lower:
                w_type = "claw"
            elif "dual" in name_lower or "edoryu" in name_lower:
                w_type = "dualblade"
            else:
                w_type = "sword"

        if w_type in ("sword", "dagger", "short_sword", "long_sword"):
            act_id = ACTION_ATTACK_SWORD
        elif w_type in ("bow", "crossbow"):
            act_id = ACTION_ATTACK_BOW
        elif w_type in ("spear", "lance"):
            act_id = ACTION_ATTACK_SPEAR
        elif w_type in ("axe", "blunt"):
            act_id = ACTION_ATTACK_AXE
        elif w_type in ("staff", "wand"):
            act_id = ACTION_ATTACK_STAFF
        elif w_type in ("dualblade", "edoryu"):
            act_id = ACTION_ATTACK_DUALBLADE
        elif w_type in ("claw",):
            act_id = ACTION_ATTACK_CLAW
        else:
            act_id = ACTION_ATTACK_SWORD

        return self.get_attack_speed(gfx, act_id)


def get_pc_action_interval(
    gfx: int,
    weapon: Optional[Weapon] = None,
    action: Optional[int] = None,
    fallback: int = 920,
) -> int:
    """Convenience helper to resolve PC action timing dynamically."""
    return SprTable.get_instance().resolve_pc_attack_interval(
        gfx=gfx, weapon=weapon, action=action, fallback=fallback
    )
