"""
native_engine/movement.py - Movement Arbiter & Rules Engine
Validates single-step moves, queries collision, and safely mutates state.
"""
from typing import Tuple, List, Optional
from native_engine.map import WorldMapGrid
from native_engine.events import (
    DomainEvent,
    MoveAttempted,
    MoveAccepted,
    MoveBlocked,
    PositionChanged
)

# Canonical 8-direction clockwise mapping
HEADING_DELTA = {
    0: (0, -1),   # North
    1: (1, -1),   # North-East
    2: (1, 0),    # East
    3: (1, 1),    # South-East
    4: (0, 1),    # South
    5: (-1, 1),   # South-West
    6: (-1, 0),   # West
    7: (-1, -1)   # North-West
}

def can_move(map_grid: WorldMapGrid, from_x: int, from_y: int, heading: int) -> Tuple[bool, str]:
    """
    Arbitrates legality of 1-step move.
    Returns: (is_legal: bool, reason: str)
      Reasons: 'PASS', 'OUT_OF_BOUNDS', 'STATIC_WALL'
    """
    if heading not in HEADING_DELTA:
        return False, "INVALID_HEADING"

    dx, dy = HEADING_DELTA[heading]
    target_x = from_x + dx
    target_y = from_y + dy

    # 1. Bounds check
    if not map_grid.is_in_bounds(from_x, from_y) or not map_grid.is_in_bounds(target_x, target_y):
        return False, "OUT_OF_BOUNDS"

    # 2. Static Map Collision check
    if not map_grid.is_through_object(from_x, from_y, heading):
        return False, "STATIC_WALL"

    return True, "PASS"

class MovementEngine:
    def __init__(self, map_grid: WorldMapGrid):
        self.map_grid = map_grid

    def execute_cmd_move(self, actor, heading: int, tick: int = 0) -> List[DomainEvent]:
        """
        Executes a single step movement command.
        Emits domain events:
          - MoveAttempted
          - MoveAccepted + PositionChanged (if pass)
          - MoveBlocked (if blocked)
        """
        events: List[DomainEvent] = []
        from_x, from_y = actor.x, actor.y
        events.append(MoveAttempted(tick=tick, entity_id=actor.id, from_x=from_x, from_y=from_y, heading=heading))

        is_allowed, reason = can_move(self.map_grid, from_x, from_y, heading)

        if not is_allowed:
            events.append(MoveBlocked(tick=tick, entity_id=actor.id, from_x=from_x, from_y=from_y, heading=heading, reason=reason))
            return events

        dx, dy = HEADING_DELTA[heading]
        to_x = from_x + dx
        to_y = from_y + dy

        # State Mutation performed ONLY by Movement Engine
        actor.x = to_x
        actor.y = to_y
        actor.heading = heading

        events.append(MoveAccepted(tick=tick, entity_id=actor.id, from_x=from_x, from_y=from_y, to_x=to_x, to_y=to_y, heading=heading))
        events.append(PositionChanged(tick=tick, entity_id=actor.id, old_x=from_x, old_y=from_y, new_x=to_x, new_y=to_y, heading=heading))
        return events
