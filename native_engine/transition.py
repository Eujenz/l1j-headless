"""
native_engine/transition.py - Cross-Map Transition Engine
Detects portal triggers, validates preconditions, and executes atomic world state mutations.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List
from native_engine.world import World
from native_engine.events import (
    DomainEvent,
    PortalTriggered,
    WorldTransitionCommitted,
    MapEntered
)

@dataclass
class TransitionDefinition:
    transition_id: str
    type: str  # 'PORTAL', 'NPC_TELEPORT', 'BOAT', etc.
    source_map: int
    source_x: int
    source_y: int
    target_map: int
    target_x: int
    target_y: int
    target_heading: int
    requirements: dict = field(default_factory=dict)

class TransitionEngine:
    def __init__(self):
        # Index: (source_map, source_x, source_y) -> TransitionDefinition
        self.transitions: Dict[Tuple[int, int, int], TransitionDefinition] = {}

    def register_transition(self, definition: TransitionDefinition):
        key = (definition.source_map, definition.source_x, definition.source_y)
        self.transitions[key] = definition

    def find_transition(self, map_id: int, x: int, y: int) -> Optional[TransitionDefinition]:
        return self.transitions.get((map_id, x, y))

    def trigger_transition(self, world: World, actor_id: int, tick: int = 0) -> List[DomainEvent]:
        """
        Executes atomic transition if actor is currently standing on a registered transition portal.
        Emits:
          - PortalTriggered
          - WorldTransitionCommitted
          - MapEntered
        """
        events: List[DomainEvent] = []
        actor = world.get_actor(actor_id)
        if not actor:
            return events

        trans = self.find_transition(actor.map_id, actor.x, actor.y)
        if not trans:
            return events

        # Requirement checks (item_id, etc.)
        required_item = trans.requirements.get("item_id", 0)
        if required_item > 0:
            # Future extension for keys/tickets
            pass

        old_map = actor.map_id
        old_x = actor.x
        old_y = actor.y

        # 1. Event: PortalTriggered
        events.append(PortalTriggered(
            tick=tick,
            entity_id=actor_id,
            transition_id=trans.transition_id,
            source_map=trans.source_map,
            source_x=trans.source_x,
            source_y=trans.source_y
        ))

        # 2. Atomic State Mutation in World Model
        world.move_actor_to_map(
            actor_id=actor_id,
            new_map_id=trans.target_map,
            new_x=trans.target_x,
            new_y=trans.target_y,
            new_heading=trans.target_heading
        )

        # 3. Event: WorldTransitionCommitted
        events.append(WorldTransitionCommitted(
            tick=tick,
            entity_id=actor_id,
            old_map=old_map,
            old_x=old_x,
            old_y=old_y,
            new_map=trans.target_map,
            new_x=trans.target_x,
            new_y=trans.target_y,
            new_heading=trans.target_heading
        ))

        # 4. Event: MapEntered
        events.append(MapEntered(
            tick=tick,
            entity_id=actor_id,
            map_id=trans.target_map,
            x=trans.target_x,
            y=trans.target_y,
            heading=trans.target_heading
        ))

        return events
