"""
native_engine/npc.py - L1J 1.82 NPC Interaction Vertical Slice

LEGACY_OBSERVED:
  - Source: npc.sql (npcid 3 '潘朵拉' Shop, gfxid 98), npc_shop.sql (item 104 Red Potion 37 adena, item 108 Haste Potion 120 adena)
  - Pure in-process vertical slice: Dialogue / Trade interaction without socket or GUI.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from .model import Actor, Item, Position


@dataclass
class ShopItem:
    item_id: int
    name: str
    price: int


class NpcShop:
    """
    Pandora's Shop on Talking Island (npcid 3).
    Catalog from L1J 1.82 legacy npc_shop.sql (npcid '3').
    """
    def __init__(self):
        self.npcid = 3
        self.name = "Pandora"
        self.gfx = 98
        self.pos = Position(32644, 32955, map_id=0)
        self.catalog: Dict[int, ShopItem] = {
            104: ShopItem(item_id=104, name="Red Potion", price=37),
            108: ShopItem(item_id=108, name="Green Potion", price=120),
            139: ShopItem(item_id=139, name="Escape Scroll", price=120),
            103: ShopItem(item_id=103, name="Orange Potion", price=150),
        }

    def buy_item(self, player: Actor, item_id: int, count: int = 1, check_proximity: bool = False) -> Tuple[bool, str]:
        """
        Execute purchase of item from shop.
        Deducts adena (Item 40308 / 'Adena') from player and adds bought item.
        If check_proximity is True, player must be within 3 tiles of NPC in the same map.
        """
        if check_proximity:
            if player.map_id != self.pos.map_id or max(abs(player.x - self.pos.x), abs(player.y - self.pos.y)) > 3:
                return False, "OUT_OF_RANGE"

        if item_id not in self.catalog:
            return False, "ITEM_NOT_IN_SHOP"
        if count <= 0:
            return False, "INVALID_COUNT"

        item = self.catalog[item_id]
        total_cost = item.price * count

        # Check player adena
        adena_item = next((i for i in player.inventory.items if i.name == "Adena" or i.item_id == 40308), None)
        if adena_item is None or adena_item.count < total_cost:
            return False, "INSUFFICIENT_ADENA"

        # Deduct adena
        adena_item.count -= total_cost
        if adena_item.count == 0:
            player.inventory.items.remove(adena_item)

        # Add bought item to inventory
        player.inventory.add(Item(item_id=item.item_id, name=item.name, count=count))
        return True, "SUCCESS"


PANDORA_SHOP = NpcShop()

