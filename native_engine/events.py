"""
native_engine/events.py - L2 Domain Events
Pure domain events representing gameplay occurrences without packet or network semantics.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class DomainEvent:
    tick: int

@dataclass
class AttackStarted(DomainEvent):
    attacker_id: int
    target_id: int

@dataclass
class HitResolved(DomainEvent):
    attacker_id: int
    target_id: int
    is_hit: bool

@dataclass
class DamageApplied(DomainEvent):
    attacker_id: int
    target_id: int
    damage: int

@dataclass
class HpChanged(DomainEvent):
    entity_id: int
    old_hp: int
    new_hp: int

@dataclass
class MonsterDied(DomainEvent):
    monster_id: int

@dataclass
class ExperienceGranted(DomainEvent):
    actor_id: int
    exp_gained: int
    total_exp: int
    lawful: int

@dataclass
class DropTransferred(DomainEvent):
    monster_id: int
    item_id: int
    count: int
    x: int
    y: int
    recipient_id: Optional[int]

@dataclass
class InventoryChanged(DomainEvent):
    owner_id: int
    item_id: int
    count: int

# --- MOVEMENT DOMAIN EVENTS ---
@dataclass
class MoveAttempted(DomainEvent):
    entity_id: int
    from_x: int
    from_y: int
    heading: int

@dataclass
class MoveAccepted(DomainEvent):
    entity_id: int
    from_x: int
    from_y: int
    to_x: int
    to_y: int
    heading: int

@dataclass
class MoveBlocked(DomainEvent):
    entity_id: int
    from_x: int
    from_y: int
    heading: int
    reason: str

@dataclass
class PositionChanged(DomainEvent):
    entity_id: int
    old_x: int
    old_y: int
    new_x: int
    new_y: int
    heading: int

@dataclass
class DestinationReached(DomainEvent):
    entity_id: int
    target_x: int
    target_y: int

# --- TRANSITION DOMAIN EVENTS ---
@dataclass
class PortalTriggered(DomainEvent):
    entity_id: int
    transition_id: str
    source_map: int
    source_x: int
    source_y: int

@dataclass
class WorldTransitionCommitted(DomainEvent):
    entity_id: int
    old_map: int
    old_x: int
    old_y: int
    new_map: int
    new_x: int
    new_y: int
    new_heading: int

@dataclass
class MapEntered(DomainEvent):
    entity_id: int
    map_id: int
    x: int
    y: int
    heading: int


# --- WORLD ROUTE PLANNING EVENTS (MODERN_DESIGN) ---
@dataclass
class WorldRoutePlanned(DomainEvent):
    entity_id: int
    start_map: int
    goal_map: int
    map_sequence: list
    transition_ids: list


# --- SCENARIO 007 GAMEPLAY & PROGRESSION EVENTS ---
@dataclass
class LevelUp(DomainEvent):
    actor_id: int
    old_level: int
    new_level: int
    new_max_hp: int

@dataclass
class WeaponEquipped(DomainEvent):
    actor_id: int
    item_id: int
    name: str

@dataclass
class WeaponUnequipped(DomainEvent):
    actor_id: int
    item_id: int
    name: str

@dataclass
class EncounterTriggered(DomainEvent):
    actor_id: int
    monster_id: int
    monster_name: str
    x: int
    y: int
