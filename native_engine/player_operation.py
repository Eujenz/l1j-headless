"""
native_engine/player_operation.py - Canonical Player Operation Layer

Product Architecture:
  Layer 1: Legacy Evidence (Eujenz/182c)
  Layer 2: Native L1J World
  Layer 3: Player Operation (Action Model - what a real human player can do)
  Layer 4: Configurable Automation (Hunting Helper - rules triggering Player Operations)

Player Operation defines the discrete, observable actions that a real L1J 1.82
player performs. It is NOT AI strategy; it is the universal player action interface
shared by manual players, automation configs, replays, and tests.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Any


class PlayerOperationType(Enum):
    """
    Enumeration of all discrete operations a real L1J player can perform.
    """
    STANDBY = auto()
    MOVE_STEP = auto()
    SELECT_TARGET = auto()
    ATTACK = auto()
    CAST_SKILL = auto()
    USE_ITEM = auto()
    LOOT = auto()
    EQUIP = auto()
    UNEQUIP = auto()
    NPC_INTERACT = auto()
    BUY_SUPPLY = auto()
    TRAVEL = auto()
    RETURN_TOWN = auto()
    TRANSITION_MAP = auto()
    ROAM = auto()

    # Backward compatibility alias
    USE_POTION = USE_ITEM


@dataclass
class PlayerOperation:
    """
    A concrete player action instance dispatched to the Native L1J World.
    """
    action_type: PlayerOperationType
    target: Optional[Any] = None
    item_id: Optional[int] = None
    count: int = 1
    skill_id: Optional[int] = None
    detail: str = ""

    @property
    def op_type(self) -> PlayerOperationType:
        return self.action_type
