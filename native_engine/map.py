"""
native_engine/map.py - World Geometry & Grid Model
Encapsulates 2D tile grid and authentic 182 IsThroughObject bitmask semantics.
"""
from typing import Dict, Tuple, Optional

class WorldMapGrid:
    def __init__(self, map_id: int, loc_x1: int, loc_y1: int, width: int, height: int):
        self.map_id = map_id
        self.loc_x1 = loc_x1
        self.loc_y1 = loc_y1
        self.loc_x2 = loc_x1 + width - 1
        self.loc_y2 = loc_y1 + height - 1
        self.width = width
        self.height = height
        self.tiles: Dict[Tuple[int, int], int] = {}

    def set_tile(self, x: int, y: int, val: int):
        self.tiles[(x, y)] = val

    def get_tile(self, x: int, y: int) -> int:
        if x < self.loc_x1 or x > self.loc_x2 or y < self.loc_y1 or y > self.loc_y2:
            return 0
        return self.tiles.get((x, y), 0)

    def is_in_bounds(self, x: int, y: int) -> bool:
        return self.loc_x1 <= x <= self.loc_x2 and self.loc_y1 <= y <= self.loc_y2

    def is_through_object(self, x: int, y: int, heading: int) -> bool:
        """
        Authentic 182 WorldMap.IsThroughObject bitmask implementation.
        0: North
        1: North-East
        2: East
        3: South-East
        4: South
        5: South-West
        6: West
        7: North-West
        """
        # Out-of-bounds check for origin
        if not self.is_in_bounds(x, y):
            return False

        if heading == 0:  # North
            return (self.get_tile(x, y) & 0x02) > 0
        elif heading == 1:  # North-East
            return ((self.get_tile(x, y) & 0x02) > 0) and ((self.get_tile(x, y - 1) & 0x01) > 0)
        elif heading == 2:  # East
            return (self.get_tile(x, y) & 0x01) > 0
        elif heading == 3:  # South-East
            # De Morgan equivalent: (South then East) or (East then South)
            route1_blocked = (self.get_tile(x, y + 1) & 0x02) <= 0 or (self.get_tile(x, y + 1) & 0x01) <= 0
            route2_blocked = (self.get_tile(x, y) & 0x01) <= 0 or (self.get_tile(x + 1, y + 1) & 0x02) <= 0
            return not (route1_blocked and route2_blocked)
        elif heading == 4:  # South
            return (self.get_tile(x, y + 1) & 0x02) > 0
        elif heading == 5:  # South-West
            route1_blocked = (self.get_tile(x, y + 1) & 0x02) <= 0 or (self.get_tile(x - 1, y + 1) & 0x01) <= 0
            route2_blocked = (self.get_tile(x - 1, y) & 0x01) <= 0 or (self.get_tile(x - 1, y + 1) & 0x02) <= 0
            return not (route1_blocked and route2_blocked)
        elif heading == 6:  # West
            return (self.get_tile(x - 1, y) & 0x01) > 0
        elif heading == 7:  # North-West
            route1_blocked = (self.get_tile(x, y) & 0x02) <= 0 or (self.get_tile(x - 1, y - 1) & 0x01) <= 0
            route2_blocked = (self.get_tile(x - 1, y) & 0x01) <= 0 or (self.get_tile(x - 1, y) & 0x02) <= 0
            return not (route1_blocked and route2_blocked)
        return False
