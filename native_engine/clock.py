"""
native_engine/clock.py - Simulation Clock System for L1J Headless

Architecture:
  - SimulationClock: Abstract base defining millisecond logical time interface.
  - VirtualClock: Deterministic instantaneous clock for replay, tests, and differential verification.
  - RealTimeClock: Wall-clock pacing adapter for interactive playtest with optional time scaling.

Invariant:
  Domain simulation logic MUST NOT call time.sleep() directly.
  All time passage and pacing must be governed through the active SimulationClock.
"""
from abc import ABC, abstractmethod
import time
from typing import Optional


class SimulationClock(ABC):
    """
    Abstract simulation clock operating in logical milliseconds.
    """
    def __init__(self, start_time_ms: int = 0):
        self._current_time_ms = start_time_ms

    @property
    def current_time_ms(self) -> int:
        return self._current_time_ms

    @abstractmethod
    def sleep_until(self, target_time_ms: int) -> None:
        """
        Advance clock to target_time_ms, pausing physical execution if required by clock mode.
        """
        pass

    def advance_by(self, delta_ms: int) -> None:
        """Advance time by delta_ms."""
        if delta_ms < 0:
            raise ValueError(f"Cannot advance backwards: delta_ms={delta_ms}")
        self.sleep_until(self._current_time_ms + delta_ms)


class VirtualClock(SimulationClock):
    """
    Deterministic instantaneous clock.
    Used for unit tests, differential conformance verification, and fast batch replays.
    Time advances immediately with 0 physical wall-clock delay.
    """
    def sleep_until(self, target_time_ms: int) -> None:
        if target_time_ms < self._current_time_ms:
            # Already past due
            return
        self._current_time_ms = target_time_ms


class RealTimeClock(SimulationClock):
    """
    Wall-clock synchronized adapter.
    Used for human interactive playtest, pacing actions at authentic Legacy cadence.
    Supports a time_scale multiplier (1.0 = true 1:1 Legacy speed, 2.0 = 2x speed, etc.).
    """
    def __init__(self, start_time_ms: int = 0, time_scale: float = 1.0):
        super().__init__(start_time_ms)
        self.time_scale = max(0.1, time_scale)
        self._wall_start = time.perf_counter()
        self._logical_start = start_time_ms

    def sleep_until(self, target_time_ms: int) -> None:
        if target_time_ms <= self._current_time_ms:
            return

        delta_logical_ms = target_time_ms - self._current_time_ms
        physical_wait_s = (delta_logical_ms / 1000.0) / self.time_scale

        if physical_wait_s > 0.001:
            time.sleep(physical_wait_s)

        self._current_time_ms = target_time_ms
