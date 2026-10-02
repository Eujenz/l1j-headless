"""
native_engine/temporal - Deterministic Virtual Temporal Runtime Core

Exports:
  - BaseClock: Abstract base defining canonical integer millisecond interface.
  - SimulationClock: Alias for BaseClock for compatibility.
  - VirtualClock: Deterministic instantaneous clock operating in integer milliseconds.
  - RealTimeClock: Wall-clock pacing adapter with optional speed scaling.
  - ScheduledEvent: Deterministically-ordered scheduled event.
  - Scheduler: Priority-queue event scheduler driven by BaseClock.
"""
from .clock import BaseClock, SimulationClock, VirtualClock, RealTimeClock
from .event import ScheduledEvent
from .scheduler import Scheduler

__all__ = [
    "BaseClock",
    "SimulationClock",
    "VirtualClock",
    "RealTimeClock",
    "ScheduledEvent",
    "Scheduler",
]
