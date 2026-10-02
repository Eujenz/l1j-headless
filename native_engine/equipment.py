"""
native_engine/equipment.py - Equipment Manager (LEGACY_OBSERVED data, MODERN_DESIGN orchestration)

Handles weapon equip/unequip. Affects combat stats via Actor.equipped_weapon.

LEGACY_OBSERVED:
- Weapons occupy Slot 11 (ItemWeaponInstance.java)
- dmg_small (for small targets), dmg_large (for large targets)
- add_hit bonus applied to HitFigure basic_flee
- enchant bonus applied to DmgWeaponFigure
- Equipping/unequipping emits WeaponEquipped/WeaponUnequipped domain events

MODERN_DESIGN:
- Inventory is a simple list; equip replaces current weapon slot
- No durability, no set bonus, no enchant UI
"""
from __future__ import annotations
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .model import Actor, Weapon, Inventory
    from .events import WeaponEquipped, WeaponUnequipped
    from .rng import NativeRng

from .model import Weapon


def build_weapon_from_contract(item: dict) -> Weapon:
    """Build a Weapon dataclass from a contract inventory item dict."""
    return Weapon(
        item_id=item["item_id"],
        name=item["name"],
        weapon_type=1,   # Default sword/dagger
        dmg_small=item.get("dmg_small", 0),
        dmg_large=item.get("dmg_large", 0),
        enchant=item.get("enchant", 0),
        bless=item.get("bless", 1),   # 1 = Normal (not blessed, not cursed)
    )


class EquipmentManager:
    """
    Manages weapon equip/unequip for the player.

    Each call to equip() replaces the currently equipped weapon and returns
    domain events (WeaponEquipped, WeaponUnequipped).

    LEGACY_OBSERVED: Slot 11 = weapon slot. Only one weapon at a time.
    """

    def __init__(self, available_weapons: List[Weapon]):
        """
        available_weapons: list of Weapon objects the player has in inventory.
        """
        self._weapons: dict[int, Weapon] = {w.item_id: w for w in available_weapons}

    def get_weapon(self, item_id: int) -> Optional[Weapon]:
        return self._weapons.get(item_id)

    def list_weapons(self) -> List[Weapon]:
        return sorted(self._weapons.values(), key=lambda w: w.item_id)

    def equip(self, actor: "Actor", item_id: int, tick: int) -> Tuple[bool, str, list]:
        """
        Equips the weapon with given item_id on actor.

        Returns: (success, reason, events)
        """
        from .events import WeaponEquipped, WeaponUnequipped

        weapon = self._weapons.get(item_id)
        if weapon is None:
            return False, "ITEM_NOT_FOUND", []

        events = []

        # Unequip current if any
        if actor.equipped_weapon is not None:
            old = actor.equipped_weapon
            events.append(WeaponUnequipped(
                tick=tick,
                actor_id=actor.id,
                item_id=old.item_id,
                name=old.name,
            ))

        actor.equipped_weapon = weapon
        from .spr_action import get_pc_action_interval
        actor.attack_speed_ms = get_pc_action_interval(actor.gfx, weapon)
        events.append(WeaponEquipped(
            tick=tick,
            actor_id=actor.id,
            item_id=weapon.item_id,
            name=weapon.name,
        ))

        return True, "EQUIPPED", events

    def unequip(self, actor: "Actor", tick: int) -> Tuple[bool, str, list]:
        """Unequips current weapon (bare-hands)."""
        from .events import WeaponUnequipped
        from .spr_action import get_pc_action_interval

        if actor.equipped_weapon is None:
            return False, "NO_WEAPON_EQUIPPED", []

        old = actor.equipped_weapon
        actor.equipped_weapon = None
        actor.attack_speed_ms = get_pc_action_interval(actor.gfx, None)
        return True, "UNEQUIPPED", [WeaponUnequipped(
            tick=tick, actor_id=actor.id, item_id=old.item_id, name=old.name
        )]

    def status(self, actor: "Actor") -> dict:
        """Returns equipment status dict."""
        w = actor.equipped_weapon
        return {
            "equipped": {
                "item_id": w.item_id,
                "name": w.name,
                "dmg_small": w.dmg_small,
                "dmg_large": w.dmg_large,
                "enchant": w.enchant,
            } if w else None,
            "available": [
                {"item_id": x.item_id, "name": x.name,
                 "dmg_small": x.dmg_small, "dmg_large": x.dmg_large}
                for x in self.list_weapons()
            ]
        }
