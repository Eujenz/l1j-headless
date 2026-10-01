"""
native_engine/temporal/clock.py - Deterministic Virtual Clock

Architecture:
  - Canonical time representation: integer milliseconds (int).
  - Monotonically increasing time progression.
  - Strictly no rewind or time travel.
  - Zero-advance (advance(0)) is legal and idempotent.
"""


class VirtualClock:
    """
    Deterministic virtual clock operating in integer milliseconds.

    Invariants:
    - Monotonically non-decreasing: time can only advance forward or stay the same.
    - Strictly no rewind / time-travel: negative advances or backward sets raise ValueError.
    - Zero advance (advance(0)) is legal and idempotent.
    - Canonical unit: integer milliseconds (int).
    """

    def __init__(self, initial_time_ms: int = 0):
        if not isinstance(initial_time_ms, int):
            raise TypeError(f"initial_time_ms must be an int, got {type(initial_time_ms).__name__}")
        if initial_time_ms < 0:
            raise ValueError(f"initial_time_ms cannot be negative: {initial_time_ms}")
        self._current_time_ms: int = initial_time_ms

    def now(self) -> int:
        """Return the current virtual time in integer milliseconds."""
        return self._current_time_ms

    def advance(self, delta_ms: int) -> int:
        """
        Advance virtual clock forward by delta_ms milliseconds.

        delta_ms must be >= 0.
        Returns the new virtual time.
        """
        if not isinstance(delta_ms, int):
            raise TypeError(f"delta_ms must be an int, got {type(delta_ms).__name__}")
        if delta_ms < 0:
            raise ValueError(f"Cannot advance clock backwards: delta_ms={delta_ms}")
        self._current_time_ms += delta_ms
        return self._current_time_ms

    def set(self, time_ms: int) -> int:
        """
        Set virtual clock forward to time_ms milliseconds.

        time_ms must be >= now(). Rewind is strictly forbidden.
        Returns the new virtual time.
        """
        if not isinstance(time_ms, int):
            raise TypeError(f"time_ms must be an int, got {type(time_ms).__name__}")
        if time_ms < self._current_time_ms:
            raise ValueError(
                f"Cannot set clock backwards: {time_ms} < {self._current_time_ms}"
            )
        self._current_time_ms = time_ms
        return self._current_time_ms

    def __repr__(self) -> str:
        return f"VirtualClock(now={self._current_time_ms}ms)"
