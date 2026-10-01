"""
native_engine/world_route.py - World-Level Multi-Map Route Planner & Executor
Provides two-level routing:
  - WorldRoutePlanner: Topological graph search over world maps & transitions (BFS)
  - WorldRouteExecutor: Coordinates intra-map navigation, step movement, and transitions
Strictly decoupled from raw tile decoders, socket stacks, and legacy Java runtimes.
"""
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from native_engine.events import DomainEvent, WorldRoutePlanned, DestinationReached
from native_engine.map import WorldMapGrid
from native_engine.movement import MovementEngine
from native_engine.navigation import AutonomousNavigator
from native_engine.transition import TransitionDefinition, TransitionEngine
from native_engine.world import World


@dataclass
class WorldRoute:
    start_map: int
    goal_map: int
    map_sequence: List[int]
    transitions: List[TransitionDefinition]
    is_valid: bool = True
    error_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "start_map": self.start_map,
            "goal_map": self.goal_map,
            "map_sequence": self.map_sequence,
            "transition_ids": [t.transition_id for t in self.transitions],
            "is_valid": self.is_valid,
            "error_reason": self.error_reason
        }


class WorldTransitionProvider(ABC):
    """Abstract provider interface for querying outgoing transitions from maps."""
    @abstractmethod
    def transitions_from(self, map_id: int) -> List[TransitionDefinition]:
        pass

    @abstractmethod
    def get_all_transitions(self) -> List[TransitionDefinition]:
        pass


class StaticTransitionProvider(WorldTransitionProvider):
    """In-memory transition provider registering canonical transitions."""
    def __init__(self, transitions: Optional[List[TransitionDefinition]] = None):
        self._transitions: Dict[int, List[TransitionDefinition]] = {}
        if transitions:
            for t in transitions:
                self.register(t)

    def register(self, transition: TransitionDefinition):
        if transition.source_map not in self._transitions:
            self._transitions[transition.source_map] = []
        self._transitions[transition.source_map].append(transition)

    def transitions_from(self, map_id: int) -> List[TransitionDefinition]:
        return list(self._transitions.get(map_id, []))

    def get_all_transitions(self) -> List[TransitionDefinition]:
        res = []
        for t_list in self._transitions.values():
            res.extend(t_list)
        return res


class WorldRoutePlanner:
    """
    World-level topological route planner (MODERN_DESIGN).
    Computes a valid sequence of maps and transitions to travel between map nodes.
    """
    @classmethod
    def plan(
        cls,
        start_map: int,
        start_x: int,
        start_y: int,
        goal_map: int,
        goal_x: int,
        goal_y: int,
        transition_provider: WorldTransitionProvider,
        map_registry: Optional[Dict[int, WorldMapGrid]] = None
    ) -> WorldRoute:
        # 1. Map presence and spatial bounds validation
        if map_registry is not None:
            if start_map not in map_registry:
                return WorldRoute(start_map, goal_map, [], [], is_valid=False, error_reason="INVALID_START_MAP")
            if goal_map not in map_registry:
                return WorldRoute(start_map, goal_map, [], [], is_valid=False, error_reason="INVALID_GOAL_MAP")
            if not map_registry[start_map].is_in_bounds(start_x, start_y):
                return WorldRoute(start_map, goal_map, [], [], is_valid=False, error_reason="START_OUT_OF_BOUNDS")
            if not map_registry[goal_map].is_in_bounds(goal_x, goal_y):
                return WorldRoute(start_map, goal_map, [], [], is_valid=False, error_reason="GOAL_OUT_OF_BOUNDS")

        # 2. Intra-map trivial route
        if start_map == goal_map:
            return WorldRoute(
                start_map=start_map,
                goal_map=goal_map,
                map_sequence=[start_map],
                transitions=[],
                is_valid=True
            )

        # 3. BFS search across map graph
        queue = deque([(start_map, [start_map], [])])
        visited = {start_map}

        while queue:
            curr_map, map_seq, trans_seq = queue.popleft()

            for trans in transition_provider.transitions_from(curr_map):
                next_map = trans.target_map

                if next_map == goal_map:
                    return WorldRoute(
                        start_map=start_map,
                        goal_map=goal_map,
                        map_sequence=map_seq + [next_map],
                        transitions=trans_seq + [trans],
                        is_valid=True
                    )

                if next_map not in visited:
                    visited.add(next_map)
                    queue.append((next_map, map_seq + [next_map], trans_seq + [trans]))

        return WorldRoute(
            start_map=start_map,
            goal_map=goal_map,
            map_sequence=[],
            transitions=[],
            is_valid=False,
            error_reason="NO_ROUTE"
        )


class WorldRouteExecutor:
    """
    World-level route execution orchestrator (MODERN_DESIGN).
    Executes a pre-planned WorldRoute by coordinating Local A* navigation,
    MovementEngine step physics, and TransitionEngine state mutations.
    """
    @staticmethod
    def execute(
        world: World,
        actor_id: int,
        route: WorldRoute,
        start_pos: Tuple[int, int],
        goal_pos: Tuple[int, int],
        transition_engine: TransitionEngine,
        start_tick: int = 100
    ) -> Tuple[bool, List[DomainEvent], str]:
        all_events: List[DomainEvent] = []
        actor = world.get_actor(actor_id)
        if not actor:
            return False, all_events, "ACTOR_NOT_FOUND"

        if not route.is_valid:
            return False, all_events, f"INVALID_ROUTE_{route.error_reason}"

        # Revalidate actor initial position
        if actor.map_id != route.start_map or (actor.x, actor.y) != start_pos:
            return False, all_events, "ACTOR_NOT_AT_START_POSITION"

        # Emit WorldRoutePlanned event
        cur_tick = start_tick
        all_events.append(WorldRoutePlanned(
            tick=cur_tick,
            entity_id=actor_id,
            start_map=route.start_map,
            goal_map=route.goal_map,
            map_sequence=list(route.map_sequence),
            transition_ids=[t.transition_id for t in route.transitions]
        ))

        # Execute intermediate transition legs
        for trans in route.transitions:
            if actor.map_id != trans.source_map:
                return False, all_events, f"MAP_MISMATCH_EXPECTED_{trans.source_map}_GOT_{actor.map_id}"

            cur_grid = world.get_map(actor.map_id)
            if not cur_grid:
                return False, all_events, f"MAP_GRID_NOT_FOUND_{actor.map_id}"

            # 1. Local Navigation to Transition Source
            leg_engine = MovementEngine(cur_grid)
            ok, nav_events = AutonomousNavigator.goto(
                actor=actor,
                target_x=trans.source_x,
                target_y=trans.source_y,
                engine=leg_engine,
                start_tick=cur_tick
            )
            all_events.extend(nav_events)
            if not ok or (actor.x, actor.y) != (trans.source_x, trans.source_y):
                return False, all_events, f"FAILED_APPROACH_TO_{trans.transition_id}"

            cur_tick = all_events[-1].tick if all_events else cur_tick + 10

            # 2. Trigger Cross-Map Transition
            cur_tick += 10
            trans_events = transition_engine.trigger_transition(world, actor_id, tick=cur_tick)
            all_events.extend(trans_events)

            # Verify actor is now on target map and target coordinates
            if actor.map_id != trans.target_map or (actor.x, actor.y) != (trans.target_x, trans.target_y):
                return False, all_events, f"TRANSITION_EXECUTION_FAILED_{trans.transition_id}"

            cur_tick = all_events[-1].tick if all_events else cur_tick + 10

        # Final Local Navigation to Goal on Destination Map
        dest_grid = world.get_map(route.goal_map)
        if not dest_grid:
            return False, all_events, f"DEST_MAP_GRID_NOT_FOUND_{route.goal_map}"

        final_engine = MovementEngine(dest_grid)
        ok, final_nav_events = AutonomousNavigator.goto(
            actor=actor,
            target_x=goal_pos[0],
            target_y=goal_pos[1],
            engine=final_engine,
            start_tick=cur_tick
        )
        all_events.extend(final_nav_events)

        if not ok or (actor.x, actor.y) != goal_pos:
            return False, all_events, "FAILED_NAVIGATION_TO_GOAL"

        return True, all_events, "SUCCESS"

    @staticmethod
    def execute_with_encounter_hook(
        world: World,
        actor_id: int,
        route: WorldRoute,
        start_pos: Tuple[int, int],
        goal_pos: Tuple[int, int],
        transition_engine: TransitionEngine,
        start_tick: int = 100,
        encounter_hook=None,
        log_callback=None,
    ) -> Tuple[bool, List[DomainEvent], str]:
        """
        Same as execute(), but calls encounter_hook() after every movement step.
        encounter_hook() -> List[DomainEvent]  (combat events if encounter occurred)

        If player dies inside encounter_hook, execution stops early.
        """
        all_events: List[DomainEvent] = []
        actor = world.get_actor(actor_id)
        if not actor:
            return False, all_events, "ACTOR_NOT_FOUND"
        if not route.is_valid:
            return False, all_events, f"INVALID_ROUTE_{route.error_reason}"
        if actor.map_id != route.start_map or (actor.x, actor.y) != start_pos:
            return False, all_events, "ACTOR_NOT_AT_START_POSITION"

        cur_tick = start_tick
        all_events.append(WorldRoutePlanned(
            tick=cur_tick,
            entity_id=actor_id,
            start_map=route.start_map,
            goal_map=route.goal_map,
            map_sequence=list(route.map_sequence),
            transition_ids=[t.transition_id for t in route.transitions]
        ))

        # --- Execute intermediate transition legs ---
        for trans in route.transitions:
            if actor.map_id != trans.source_map:
                return False, all_events, f"MAP_MISMATCH_EXPECTED_{trans.source_map}_GOT_{actor.map_id}"

            cur_grid = world.get_map(actor.map_id)
            if not cur_grid:
                return False, all_events, f"MAP_GRID_NOT_FOUND_{actor.map_id}"

            # Navigate step-by-step to transition source, checking encounter after each step
            from native_engine.navigation import AutonomousNavigator
            from native_engine.movement import MovementEngine

            leg_engine = MovementEngine(cur_grid)
            ok, nav_events = AutonomousNavigator.goto_with_hook(
                actor=actor,
                target_x=trans.source_x,
                target_y=trans.source_y,
                engine=leg_engine,
                start_tick=cur_tick,
                step_hook=encounter_hook,
                log_callback=log_callback,
            )
            all_events.extend(nav_events)

            if actor.is_dead:
                return False, all_events, "PLAYER_DEAD"

            if not ok or (actor.x, actor.y) != (trans.source_x, trans.source_y):
                return False, all_events, f"FAILED_APPROACH_TO_{trans.transition_id}"

            cur_tick = all_events[-1].tick if all_events else cur_tick + 10

            # Trigger portal transition
            cur_tick += 10
            if log_callback:
                log_callback("portal", f"[傳送門] Map {actor.map_id} → Map {trans.target_map}")
            trans_events = transition_engine.trigger_transition(world, actor_id, tick=cur_tick)
            all_events.extend(trans_events)

            if actor.map_id != trans.target_map or (actor.x, actor.y) != (trans.target_x, trans.target_y):
                return False, all_events, f"TRANSITION_EXECUTION_FAILED_{trans.transition_id}"

            if log_callback:
                log_callback("map_enter", f"[進入] Map {actor.map_id} 位置 ({actor.x},{actor.y})")

            cur_tick = all_events[-1].tick if all_events else cur_tick + 10

        # --- Final navigation on destination map ---
        dest_grid = world.get_map(route.goal_map)
        if not dest_grid:
            return False, all_events, f"DEST_MAP_GRID_NOT_FOUND_{route.goal_map}"

        from native_engine.movement import MovementEngine
        from native_engine.navigation import AutonomousNavigator

        final_engine = MovementEngine(dest_grid)
        ok, final_nav_events = AutonomousNavigator.goto_with_hook(
            actor=actor,
            target_x=goal_pos[0],
            target_y=goal_pos[1],
            engine=final_engine,
            start_tick=cur_tick,
            step_hook=encounter_hook,
            log_callback=log_callback,
        )
        all_events.extend(final_nav_events)

        if actor.is_dead:
            return False, all_events, "PLAYER_DEAD"

        if not ok or (actor.x, actor.y) != goal_pos:
            return False, all_events, "FAILED_NAVIGATION_TO_GOAL"

        return True, all_events, "SUCCESS"
