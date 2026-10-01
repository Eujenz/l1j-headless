"""
native_engine/bot - L1J 1.82 Autonomous Headless Game Agent Package

Exports:
  - HeadlessBot: Core autonomous controller operating in Virtual Time.
  - BotPolicy, BotState, BotAction, BotActionType: Decision engine.
  - PerceptionSystem, PerceptionSnapshot: Zero-graphics perception extractor.
  - DropSystem, GroundDrop: Canonical 1.82 item drop & looting system.
"""
from .controller import HeadlessBot
from .policy import BotPolicy, BotState, BotAction, BotActionType
from .perception import PerceptionSystem, PerceptionSnapshot
from .drop import DropSystem, GroundDrop

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
]
