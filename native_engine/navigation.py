"""
native_engine/navigation.py - Autonomous Navigation & Path Planner
Uses Modern A* search with PriorityQueue to generate CmdMove heading sequences.
Decoupled: Planner NEVER directly mutates actor coordinates.
"""
import heapq
from typing import List, Tuple, Optional, Set, Dict
from native_engine.map import WorldMapGrid
from native_engine.movement import MovementEngine, can_move, HEADING_DELTA
from native_engine.events import DomainEvent, DestinationReached

class AStarPlanner:
    LIMIT_LOOP = 200

    @staticmethod
    def heuristic(x: int, y: int, tx: int, ty: int) -> int:
        """Euclidean squared distance, matching 182 AStar.java integer heuristic."""
        return (tx - x) * (tx - x) + (ty - y) * (ty - y)

    @classmethod
    def find_path(cls, map_grid: WorldMapGrid, sx: int, sy: int, tx: int, ty: int) -> Optional[List[int]]:
        """
        Finds path from (sx, sy) to (tx, ty) on map_grid.
        Returns list of headings [h1, h2, ...].
        """
        if sx == tx and sy == ty:
            return []

        # Priority queue entries: (f_score, g_score, count, x, y, path_headings)
        open_set = []
        counter = 0
        h_start = cls.heuristic(sx, sy, tx, ty)
        heapq.heappush(open_set, (h_start, 0, counter, sx, sy, []))

        # Track best g_score for visited coordinates
        g_scores: Dict[Tuple[int, int], int] = {(sx, sy): 0}
        closed_set: Set[Tuple[int, int]] = set()

        loops = 0
        while open_set and loops < cls.LIMIT_LOOP:
            loops += 1
            f, g, _, curr_x, curr_y, headings = heapq.heappop(open_set)

            if curr_x == tx and curr_y == ty:
                return headings

            if (curr_x, curr_y) in closed_set and g > g_scores.get((curr_x, curr_y), float('inf')):
                continue

            closed_set.add((curr_x, curr_y))

            # Expand 8 directions
            for heading in range(8):
                is_pass, _ = can_move(map_grid, curr_x, curr_y, heading)
                if not is_pass:
                    continue

                dx, dy = HEADING_DELTA[heading]
                next_x = curr_x + dx
                next_y = curr_y + dy

                next_g = g + 1
                if next_g < g_scores.get((next_x, next_y), float('inf')):
                    g_scores[(next_x, next_y)] = next_g
                    next_h = cls.heuristic(next_x, next_y, tx, ty)
                    next_f = next_g + next_h
                    counter += 1
                    heapq.heappush(open_set, (next_f, next_g, counter, next_x, next_y, headings + [heading]))

        return None

class AutonomousNavigator:
    @staticmethod
    def goto(actor, target_x: int, target_y: int, engine: MovementEngine, start_tick: int = 100) -> Tuple[bool, List[DomainEvent]]:
        """
        High-level autonomous goal: GoTo(target_x, target_y).
        Plans path via A* and drives MovementEngine with CmdMove(heading).
        """
        all_events: List[DomainEvent] = []
        headings = AStarPlanner.find_path(engine.map_grid, actor.x, actor.y, target_x, target_y)

        if headings is None:
            return False, all_events

        cur_tick = start_tick
        for h in headings:
            cur_tick += 10
            step_events = engine.execute_cmd_move(actor, h, tick=cur_tick)
            all_events.extend(step_events)
            # If any step was blocked, stop navigation
            if any(ev.__class__.__name__ == 'MoveBlocked' for ev in step_events):
                return False, all_events

        if actor.x == target_x and actor.y == target_y:
            all_events.append(DestinationReached(tick=cur_tick, entity_id=actor.id, target_x=target_x, target_y=target_y))
            return True, all_events

        return False, all_events
