"""
native_engine/bot - L1J 1.82 Autonomous Headless Game Agent Package

Exports:
  - HeadlessBot: Core autonomous controller operating in Virtual Time.
  - BotPolicy, BotState, BotAction, BotActionType: Decision engine.
  - PerceptionSystem, PerceptionSnapshot: Zero-graphics perception extractor.
  - DropSystem, GroundDrop: Canonical 1.82 item drop & looting system.
"""
from ..player_operation import PlayerOperationType, PlayerOperation
from .controller import HeadlessBot
from .policy import BotPolicy, BotState, BotAction, BotActionType
from .perception import PerceptionSystem, PerceptionSnapshot
from .drop import DropSystem, GroundDrop
from .config import (
    AutonomousConfig,
    CharacterConfig,
    TargetingConfig,
    MovementConfig,
    LootConfig,
    SkillRule,
    BuffRule,
    PotionRule,
    PotionThresholdMode,
    EmergencyCondition,
    EmergencyConditionType,
    EmergencyOperator,
    EmergencyAction,
    EmergencyActionRule,
    ReturnTrigger,
    ReturnTriggerType,
    ReturnMethod,
    ReturnToTownPolicy,
    ResupplyItem,
    ResupplyProfile,
    HuntingDestination,
    HuntingPolicy,
)

__all__ = [
    "HeadlessBot",
    "BotPolicy",
    "BotState",
    "BotAction",
    "BotActionType",
    "PerceptionSystem",
    "PerceptionSnapshot",
    "DropSystem",
    "GroundDrop",
    "AutonomousConfig",
    "PotionRule",
    "PotionThresholdMode",
    "EmergencyCondition",
    "EmergencyConditionType",
    "EmergencyOperator",
    "EmergencyAction",
    "EmergencyActionRule",
    "ReturnTrigger",
    "ReturnTriggerType",
    "ReturnMethod",
    "ReturnToTownPolicy",
    "ResupplyItem",
    "ResupplyProfile",
    "HuntingDestination",
    "HuntingPolicy",
]

