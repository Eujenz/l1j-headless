"""
native_engine/clock.py - Simulation Clock System for L1J Headless

Re-exports unified clock system from native_engine.temporal.clock for full backward compatibility:
  - BaseClock / SimulationClock: Abstract base defining canonical integer millisecond interface.
  - VirtualClock: Deterministic instantaneous clock for replay, tests, and differential verification.
  - RealTimeClock: Wall-clock pacing adapter for interactive playtest with optional speed scaling.
"""
from native_engine.temporal.clock import (
    BaseClock,
    SimulationClock,
    VirtualClock,
    RealTimeClock,
)

__all__ = ["BaseClock", "SimulationClock", "VirtualClock", "RealTimeClock"]
