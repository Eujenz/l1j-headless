"""
native_engine/temporal/clock.py - Deterministic Virtual & Real-Time Clocks

Architecture:
  - BaseClock: Abstract base defining canonical integer millisecond time interface.
  - VirtualClock: Deterministic instantaneous clock for replay, tests, and differential verification.
  - RealTimeClock: Wall-clock pacing adapter for interactive playtest with speed scaling.
  - Monotonically non-decreasing time progression.
  - Strictly no rewind or time travel.
  - Zero-advance (advance(0)) is legal and idempotent.
"""
from abc import ABC, abstractmethod
import time
from typing import Optional


class BaseClock(ABC):
    """
    Abstract simulation clock operating in logical integer milliseconds.

    Invariants:
    - Canonical time representation: integer milliseconds (int).
    - Monotonically non-decreasing: time can only advance forward or stay the same.
    - Strictly no rewind / time-travel: negative advances or backward sets raise ValueError.
    - Zero advance (advance(0)) is legal and idempotent.
    """

    def __init__(self, initial_time_ms: int = 0, start_time_ms: Optional[int] = None):
        init_time = start_time_ms if start_time_ms is not None else initial_time_ms
        if not isinstance(init_time, int):
            raise TypeError(f"initial_time_ms must be an int, got {type(init_time).__name__}")
        if init_time < 0:
            raise ValueError(f"initial_time_ms cannot be negative: {init_time}")
        self._current_time_ms: int = init_time

    def now(self) -> int:
        """Return the current logical time in integer milliseconds."""
        return self._current_time_ms

    @property
    def current_time_ms(self) -> int:
        """Compatibility property for SimulationClock."""
        return self._current_time_ms

    @abstractmethod
    def sleep_until(self, target_time_ms: int) -> None:
        """
        Advance clock to target_time_ms, pausing wall-clock execution if required.
        """
        pass

    def advance(self, delta_ms: int) -> int:
        """
        Advance clock forward by delta_ms milliseconds.
        delta_ms must be >= 0.
        Returns the new logical time.
        """
        if not isinstance(delta_ms, int):
            raise TypeError(f"delta_ms must be an int, got {type(delta_ms).__name__}")
        if delta_ms < 0:
            raise ValueError(f"Cannot advance clock backwards: delta_ms={delta_ms}")
        self.sleep_until(self._current_time_ms + delta_ms)
        return self._current_time_ms

    def advance_by(self, delta_ms: int) -> None:
        """Legacy compatibility method."""
        self.advance(delta_ms)

    def set(self, time_ms: int) -> int:
        """
        Set clock forward to time_ms milliseconds.
        time_ms must be >= now(). Rewind is strictly forbidden.
        Returns the new logical time.
        """
        if not isinstance(time_ms, int):
            raise TypeError(f"time_ms must be an int, got {type(time_ms).__name__}")
        if time_ms < self._current_time_ms:
            raise ValueError(
                f"Cannot set clock backwards: {time_ms} < {self._current_time_ms}"
            )
        self.sleep_until(time_ms)
        return self._current_time_ms


# Backward compatibility alias
SimulationClock = BaseClock


class VirtualClock(BaseClock):
    """
    Deterministic instantaneous clock operating in integer milliseconds.
    Used for unit tests, differential conformance verification, and fast batch replays.
    Time advances immediately with 0 physical wall-clock delay.
    """

    def sleep_until(self, target_time_ms: int) -> None:
        if not isinstance(target_time_ms, int):
            raise TypeError(f"target_time_ms must be an int, got {type(target_time_ms).__name__}")
        if target_time_ms < self._current_time_ms:
            raise ValueError(
                f"Cannot set clock backwards: {target_time_ms} < {self._current_time_ms}"
            )
        self._current_time_ms = target_time_ms

    def __repr__(self) -> str:
        return f"VirtualClock(now={self._current_time_ms}ms)"


class RealTimeClock(BaseClock):
    """
    Wall-clock synchronized adapter.
    Used for human interactive playtest, pacing actions at authentic Legacy cadence.
    Supports a time_scale multiplier (1.0 = true 1:1 Legacy speed, 2.0 = 2x speed, etc.).
    """

    def __init__(
        self,
        initial_time_ms: int = 0,
        time_scale: float = 1.0,
        start_time_ms: Optional[int] = None,
    ):
        super().__init__(initial_time_ms=initial_time_ms, start_time_ms=start_time_ms)
        self.time_scale: float = max(0.01, float(time_scale))
        self._wall_start: float = time.perf_counter()
        self._logical_start: int = self._current_time_ms

    def sleep_until(self, target_time_ms: int) -> None:
        if not isinstance(target_time_ms, int):
            raise TypeError(f"target_time_ms must be an int, got {type(target_time_ms).__name__}")
        if target_time_ms < self._current_time_ms:
            raise ValueError(
                f"Cannot set clock backwards: {target_time_ms} < {self._current_time_ms}"
            )
        if target_time_ms == self._current_time_ms:
            return

        expected_wall_elapsed = ((target_time_ms - self._logical_start) / 1000.0) / self.time_scale
        actual_wall_elapsed = time.perf_counter() - self._wall_start
        wait_s = expected_wall_elapsed - actual_wall_elapsed

        if wait_s > 0.001:
            time.sleep(wait_s)

        self._current_time_ms = target_time_ms

    def __repr__(self) -> str:
        return f"RealTimeClock(now={self._current_time_ms}ms, scale={self.time_scale}x)"
