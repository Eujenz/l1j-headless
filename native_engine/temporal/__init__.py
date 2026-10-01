"""
native_engine/temporal - Deterministic Virtual Temporal Runtime Core

Exports:
  - VirtualClock: Integer-millisecond virtual clock.
  - ScheduledEvent: Deterministically-ordered scheduled event.
  - Scheduler: Priority-queue event scheduler driven by VirtualClock.
"""
from .clock import VirtualClock
from .event import ScheduledEvent
from .scheduler import Scheduler

__all__ = ["VirtualClock", "ScheduledEvent", "Scheduler"]
