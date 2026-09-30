"""
native_engine/world.py - Multi-Map World Model & Entity Membership
Manages world maps, registered actors, and actor-to-map spatial membership.
"""
from typing import Dict, Optional, Set
from native_engine.map import WorldMapGrid

class World:
    def __init__(self):
        self.maps: Dict[int, WorldMapGrid] = {}
        self.actors: Dict[int, any] = {}
        self.map_actors: Dict[int, Set[int]] = {}

    def add_map(self, map_grid: WorldMapGrid):
        self.maps[map_grid.map_id] = map_grid
        if map_grid.map_id not in self.map_actors:
            self.map_actors[map_grid.map_id] = set()

    def get_map(self, map_id: int) -> Optional[WorldMapGrid]:
        return self.maps.get(map_id)

    def add_actor(self, actor, map_id: int):
        self.actors[actor.id] = actor
        actor.map_id = map_id
        if map_id in self.map_actors:
            self.map_actors[map_id].add(actor.id)
        else:
            self.map_actors[map_id] = {actor.id}

    def get_actor(self, actor_id: int) -> Optional[any]:
        return self.actors.get(actor_id)

    def get_actor_map(self, actor_id: int) -> Optional[int]:
        actor = self.actors.get(actor_id)
        return actor.map_id if actor else None

    def move_actor_to_map(self, actor_id: int, new_map_id: int, new_x: int, new_y: int, new_heading: int):
        """
        Atomic world membership and spatial mutation.
        Safely removes from old map, inserts into new map, and updates coordinates.
        """
        actor = self.actors.get(actor_id)
        if not actor:
            raise ValueError(f"Actor {actor_id} not found in world")

        old_map_id = actor.map_id
        if old_map_id in self.map_actors and actor_id in self.map_actors[old_map_id]:
            self.map_actors[old_map_id].remove(actor_id)

        # Mutate actor state
        actor.map_id = new_map_id
        actor.x = new_x
        actor.y = new_y
        actor.heading = new_heading

        # Register in new map
        if new_map_id not in self.map_actors:
            self.map_actors[new_map_id] = set()
        self.map_actors[new_map_id].add(actor_id)
