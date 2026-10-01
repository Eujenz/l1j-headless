"""
native_engine/model.py - Minimal Domain Models for L1J Headless
Strictly decoupled from socket, packet, database, and Java runtime classes.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .map import WorldMapGrid

@dataclass
class Position:
    x: int
    y: int
    map_id: int

@dataclass
class Weapon:
    item_id: int
    name: str
    weapon_type: int   # 1 = Sword
    dmg_small: int
    dmg_large: int
    enchant: int = 0
    bless: int = 0     # 0 = Blessed, 1 = Normal, 2 = Cursed

@dataclass
class Item:
    item_id: int
    name: str
    count: int

@dataclass
class Inventory:
    items: List[Item] = field(default_factory=list)

    def add(self, item: Item):
        for existing in self.items:
            if existing.item_id == item.item_id:
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
    next_move_at: int = 0
    next_attack_at: int = 0

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
    next_move_at: int = 0
    next_attack_at: int = 0

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
