"""
native_engine/model.py - Minimal Domain Models for L1J Headless
Strictly decoupled from socket, packet, database, and Java runtime classes.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .map import WorldMapGrid

@dataclass
class Position:
    x: int
    y: int
    map_id: int

# ==============================================================================
# Canonical 14 Equipment Slots from Legacy 182c (PcInventory.java:42, Item.java:60-83)
# ==============================================================================
SLOT_HELM = 0       # TYPE_HELM = 12
SLOT_EARRING = 1    # TYPE_EARRING = 13
SLOT_NECKLACE = 2   # TYPE_NECKLACE = 14
SLOT_SHIRT = 3      # TYPE_SHIRT = 15
SLOT_ARMOR = 4      # TYPE_ARMOR = 16
SLOT_CLOAK = 5      # TYPE_CLOAK = 17
SLOT_RING1 = 6      # TYPE_RING = 18
SLOT_RING2 = 7      # TYPE_RING = 18
SLOT_BELT = 8       # TYPE_BELT = 19
SLOT_GLOVE = 9      # TYPE_GLOVE = 20
SLOT_SHIELD = 10    # TYPE_SHIELD = 21
SLOT_WEAPON = 11    # TYPE_WEAPON = 22
SLOT_BOOTS = 12     # TYPE_BOOTS = 23
SLOT_RUNE = 13      # TYPE = 10 (Accessory/Rune)

SLOT_NAMES: Dict[int, str] = {
    0: "頭盔 (Helm)",
    1: "耳環 (Earring)",
    2: "項鍊 (Necklace)",
    3: "內衣 (T-Shirt)",
    4: "盔甲 (Armor)",
    5: "斗篷 (Cloak)",
    6: "戒指1 (Ring 1)",
    7: "戒指2 (Ring 2)",
    8: "腰帶 (Belt)",
    9: "手套 (Glove)",
    10: "盾牌 (Shield)",
    11: "武器 (Weapon)",
    12: "長靴 (Boots)",
    13: "符石 (Rune)",
}

@dataclass
class Weapon:
    item_id: int
    name: str
    weapon_type: int   # 1 = Sword
    dmg_small: int
    dmg_large: int
    enchant: int = 0
    bless: int = 0     # 0 = Blessed, 1 = Normal, 2 = Cursed
    weight: int = 50
    type1: int = 1     # 1 = Weapon
    equip_slot: int = 11
    is_equipped: bool = False

@dataclass
class Item:
    item_id: int
    name: str
    count: int
    weight: int = 10
    type1: int = 0         # 0: consumable/etc, 1: weapon, 2: armor
    equip_slot: int = -1   # 0..13 for equip slot
    ac: int = 0            # AC defense modifier (e.g. 3, 5, 8)
    add_str: int = 0
    add_dex: int = 0
    add_con: int = 0
    add_int: int = 0
    add_wis: int = 0
    add_cha: int = 0
    add_mr: int = 0
    add_hp: int = 0
    add_mp: int = 0
    enchant: int = 0
    bless: int = 1         # 0: Blessed, 1: Normal, 2: Cursed
    is_equipped: bool = False

@dataclass
class Inventory:
    items: List[Item] = field(default_factory=list)

    def add(self, item: Item):
        for existing in self.items:
            if existing.item_id == item.item_id and not existing.is_equipped and not item.is_equipped:
                existing.count += item.count
                return
        self.items.append(item)

@dataclass
class Actor:
    id: int
    name: str
    class_type: int    # 1 = Knight
    level: int
    hp: int
    max_hp: int
    str: int
    dex: int
    con: int
    int: int
    wis: int
    cha: int
    pos: Position
    heading: int
    auto_pickup: bool
    inventory: Inventory
    equipped_weapon: Optional[Weapon] = None
    equipped_slots: Dict[int, Optional[Any]] = field(default_factory=dict)
    exp: int = 0
    lawful: int = 0
    is_dead: bool = False
    ac: int = 10
    mp: int = 10
    max_mp: int = 10
    # LEGACY_OBSERVED: L1J 1.82 Knight one-hand sword canonical interval = 920ms (GFX 48 action 5, SprTable:84, canonical_timing_spec.md)
    gfx: int = 61
    gfx_mode: int = 4
    move_speed_ms: int = 640
    attack_speed_ms: int = 920
    is_speed: bool = False
    is_slow: bool = False
    is_brave: bool = False
    current_target: Optional[Any] = None

    @property
    def effective_move_speed_ms(self) -> int:
        speed = self.move_speed_ms
        if self.is_speed:
            speed = int(speed * 0.75)
        if self.is_slow:
            speed = int(speed / 0.75)
        if self.is_brave:
            speed = int(speed * 0.75)
        return max(1, speed)

    @property
    def effective_attack_speed_ms(self) -> int:
        speed = self.attack_speed_ms
        if self.is_speed:
            speed = int(speed * 0.75)
        if self.is_slow:
            speed = int(speed / 0.75)
        if self.is_brave:
            speed = int(speed * 0.75)
        return max(1, speed)

    def __post_init__(self):
        if not self.equipped_slots:
            self.equipped_slots = {slot: None for slot in range(14)}
        if self.equipped_weapon and not self.equipped_slots.get(SLOT_WEAPON):
            self.equipped_slots[SLOT_WEAPON] = self.equipped_weapon
            self.equipped_weapon.is_equipped = True

    # -------------------------------------------------------------------------
    # Legacy Stats & Vitals (Character.java:586-635, S_CharacterStat.java)
    # -------------------------------------------------------------------------
    @property
    def total_str(self) -> int:
        bonus = sum(getattr(it, "add_str", 0) for it in self.equipped_slots.values() if it)
        return self.str + bonus

    @property
    def total_dex(self) -> int:
        bonus = sum(getattr(it, "add_dex", 0) for it in self.equipped_slots.values() if it)
        return self.dex + bonus

    @property
    def total_con(self) -> int:
        bonus = sum(getattr(it, "add_con", 0) for it in self.equipped_slots.values() if it)
        return self.con + bonus

    @property
    def total_int(self) -> int:
        bonus = sum(getattr(it, "add_int", 0) for it in self.equipped_slots.values() if it)
        return self.int + bonus

    @property
    def total_wis(self) -> int:
        bonus = sum(getattr(it, "add_wis", 0) for it in self.equipped_slots.values() if it)
        return self.wis + bonus

    @property
    def total_cha(self) -> int:
        bonus = sum(getattr(it, "add_cha", 0) for it in self.equipped_slots.values() if it)
        return self.cha + bonus

    @property
    def ac_dex(self) -> int:
        # Legacy L1J 1.82 Dex AC modifier (Character.java:621)
        if self.total_dex >= 18:
            return 4
        elif self.total_dex >= 16:
            return 3
        elif self.total_dex >= 14:
            return 2
        elif self.total_dex >= 12:
            return 1
        return 0

    @property
    def total_ac(self) -> int:
        # Base AC (10) - Dex Bonus - Armor AC - Enchants
        armor_ac = sum((getattr(it, "ac", 0) + getattr(it, "enchant", 0)) for it in self.equipped_slots.values() if it)
        return self.ac - self.ac_dex - armor_ac

    @property
    def total_mr(self) -> int:
        # Base MR (Class dependent: Elf=25, Mage=15, Knight=0) + Wis bonus + Armor MR
        base_mr = 25 if self.class_type == 2 else (15 if self.class_type == 3 else 0)
        wis_mr = max(0, (self.total_wis - 10) * 3) if self.total_wis > 10 else 0
        gear_mr = sum(getattr(it, "add_mr", 0) for it in self.equipped_slots.values() if it)
        return base_mr + wis_mr + gear_mr

    @property
    def max_weight(self) -> int:
        # PcInventory.java:331-336: (str + con + 1) / 2 * 150 * 2
        base = int(((self.total_str + self.total_con + 1) / 2.0) * 150.0 * 2.0)
        belt = self.equipped_slots.get(SLOT_BELT)
        if belt:
            name = getattr(belt, "name", "")
            if "Ogre" in name or "歐吉" in name:
                base = int(base * 1.2)
            elif "Troll" in name or "多羅" in name:
                base = int(base * 1.1)
        return max(100, base)

    @property
    def current_weight(self) -> int:
        return sum(getattr(it, "weight", 10) * getattr(it, "count", 1) for it in self.inventory.items)

    @property
    def weight_pct(self) -> int:
        return int((self.current_weight / self.max_weight) * 100.0) if self.max_weight > 0 else 0

    @property
    def weight_30_bar(self) -> int:
        # Legacy r = (int)(weight / max_weight * 30.0) (PcInventory.java:318)
        return min(29, int((self.current_weight / self.max_weight) * 30.0)) if self.max_weight > 0 else 0

    def equip_item(self, item: Any) -> bool:
        """
        Equip weapon or armor piece into canonical slot (ItemArmorInstance.java, ItemWeaponInstance.java).
        Returns True if equipped successfully.
        """
        if isinstance(item, Weapon):
            self.equipped_weapon = item
            self.equipped_slots[SLOT_WEAPON] = item
            item.is_equipped = True
            return True

        if hasattr(item, "equip_slot") and item.equip_slot in SLOT_NAMES:
            slot_id = item.equip_slot
            # Ring handling: if slot 6 occupied, use slot 7 (ItemArmorInstance.java:49)
            if slot_id == SLOT_RING1 and self.equipped_slots.get(SLOT_RING1) is not None:
                slot_id = SLOT_RING2
            # Unequip existing item in that slot if any
            existing = self.equipped_slots.get(slot_id)
            if existing:
                existing.is_equipped = False
            self.equipped_slots[slot_id] = item
            item.is_equipped = True
            if slot_id == SLOT_WEAPON:
                self.equipped_weapon = item
            return True
        return False

    def unequip_slot(self, slot_id: int) -> Optional[Any]:
        """
        Unequip item from canonical slot. Returns the removed item.
        """
        item = self.equipped_slots.get(slot_id)
        if item:
            item.is_equipped = False
            self.equipped_slots[slot_id] = None
            if slot_id == SLOT_WEAPON:
                self.equipped_weapon = None
        return item

    @property
    def x(self) -> int:
        return self.pos.x

    @x.setter
    def x(self, val: int):
        self.pos.x = val

    @property
    def y(self) -> int:
        return self.pos.y

    @y.setter
    def y(self, val: int):
        self.pos.y = val

    @property
    def map_id(self) -> int:
        return self.pos.map_id

    @map_id.setter
    def map_id(self, val: int):
        self.pos.map_id = val

@dataclass
class Monster:
    id: int
    uid: int
    name: str
    level: int
    hp: int
    max_hp: int
    ac: int
    exp: int
    size: str
    pos: Position
    heading: int
    inventory: Inventory
    is_dead: bool = False
    # LEGACY_OBSERVED: from monster.sql (min_dmg/max_dmg used in Character.java counter-attack)
    min_dmg: int = 0
    max_dmg: int = 0
    # LEGACY_OBSERVED: agro=1 means monster actively seeks players; undead>0 means undead type
    agro: int = 0
    undead: int = 0
    # spawn_uid: links back to spawn_definitions record for provenance
    spawn_uid: int = 0
    # LEGACY_OBSERVED: timing from sprite_frame.sql
    gfx: int = 0
    move_speed_ms: int = 800
    attack_speed_ms: int = 1200
    target: Optional[Any] = None
    re_spawn: int = 300
    is_speed: bool = False
    is_slow: bool = False

    @property
    def effective_move_speed_ms(self) -> int:
        speed = self.move_speed_ms
        if self.is_speed:
            speed = int(speed - speed * 0.3)
        if self.is_slow:
            speed = int(speed + speed * 0.3)
        return max(1, speed)

    @property
    def effective_attack_speed_ms(self) -> int:
        speed = self.attack_speed_ms
        if self.is_speed:
            speed = int(speed - speed * 0.3)
        if self.is_slow:
            speed = int(speed + speed * 0.3)
        return max(1, speed)

    @property
    def x(self) -> int:
        return self.pos.x

    @x.setter
    def x(self, val: int):
        self.pos.x = val

    @property
    def y(self) -> int:
        return self.pos.y

    @y.setter
    def y(self, val: int):
        self.pos.y = val

    @property
    def map_id(self) -> int:
        return self.pos.map_id

    @map_id.setter
    def map_id(self, val: int):
        self.pos.map_id = val

@dataclass
class CanonicalMapDefinition:
    """
    Canonical, decoupled map geometry representation.
    Encapsulates static terrain boundaries and contiguous tile memory.
    """
    map_id: int
    loc_x1: int
    loc_x2: int
    loc_y1: int
    loc_y2: int
    width: int
    height: int
    raw_tiles: bytes
    canonical_geometry_digest: str = ""

    def to_grid(self) -> 'WorldMapGrid':
        from .map import WorldMapGrid
        return WorldMapGrid(
            map_id=self.map_id,
            loc_x1=self.loc_x1,
            loc_y1=self.loc_y1,
            width=self.width,
            height=self.height,
            dense_tiles=self.raw_tiles
        )
