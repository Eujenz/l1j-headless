"""
native_engine/temporal/scheduler.py - Deterministic Virtual Event Scheduler

Architecture:
  - Operates purely in Virtual Time using integer milliseconds.
  - Priority-queue (min-heap) scheduling with O(log N) operations.
  - Fully deterministic ordering: (timestamp, sequence) tie-breaking guarantees reproducibility.
  - Re-entrant & dynamic: Callbacks may schedule future events, same-time events, or self-reschedule.
  - Exception-safe: Exceptions in callbacks propagate immediately without corrupting heap structure.
  - Strictly decoupled from gameplay domains (combat, movement, world, session).
"""
import heapq
from typing import Callable, Any, Optional
from .clock import BaseClock, VirtualClock
from .event import ScheduledEvent


class Scheduler:
    """
    Deterministic priority-queue event scheduler driven by VirtualClock.

    Invariants:
    - All times are integer milliseconds.
    - Zero real-world delay, no time.sleep(), no threading timers.
    - Events with identical timestamps execute strictly in creation sequence order (FIFO).
    - In run_until(target_time_ms), clock.now() advances to event.timestamp before the callback runs.
    - After run_until(target_time_ms) finishes, clock.now() == target_time_ms.
    """

    def __init__(self, clock: Optional[BaseClock] = None):
        self.clock: BaseClock = clock if clock is not None else VirtualClock(0)
        self._queue: list[ScheduledEvent] = []
        self._sequence_counter: int = 0
        self._active_count: int = 0

    def schedule_at(
        self, timestamp_ms: int, callback: Callable[[], Any], name: str = ""
    ) -> ScheduledEvent:
        """
        Schedule an event to execute at an absolute virtual timestamp in milliseconds.

        timestamp_ms must be >= clock.now().
        """
        if not isinstance(timestamp_ms, int):
            raise TypeError(f"timestamp_ms must be an int, got {type(timestamp_ms).__name__}")
        if timestamp_ms < self.clock.now():
            raise ValueError(
                f"Cannot schedule event in the past: timestamp_ms={timestamp_ms} < now={self.clock.now()}"
            )
        if not callable(callback):
            raise TypeError("callback must be callable")

        self._sequence_counter += 1
        event = ScheduledEvent(
            timestamp=timestamp_ms,
            sequence=self._sequence_counter,
            callback=callback,
            cancelled=False,
            name=name,
        )
        heapq.heappush(self._queue, event)
        self._active_count += 1
        return event

    def schedule_after(
        self, delay_ms: int, callback: Callable[[], Any], name: str = ""
    ) -> ScheduledEvent:
        """
        Schedule an event to execute after delay_ms milliseconds relative to current virtual time.

        delay_ms must be >= 0.
        Event timestamp will be clock.now() + delay_ms.
        """
        if not isinstance(delay_ms, int):
            raise TypeError(f"delay_ms must be an int, got {type(delay_ms).__name__}")
        if delay_ms < 0:
            raise ValueError(f"delay_ms cannot be negative: {delay_ms}")
        return self.schedule_at(self.clock.now() + delay_ms, callback, name=name)

    def cancel(self, event: ScheduledEvent) -> bool:
        """
        Cancel a scheduled event.

        Uses lazy cancellation. Returns True if event was active and cancelled,
        False if event was already cancelled.
        """
        if event.cancelled:
            return False
        event.cancel()
        self._active_count = max(0, self._active_count - 1)
        return True

    def has_pending_events(self) -> bool:
        """Return True if there are any active (uncancelled) scheduled events."""
        return self._active_count > 0

    def pending_count(self) -> int:
        """Return the count of active (uncancelled) scheduled events."""
        return self._active_count

    def peek_next(self) -> Optional[ScheduledEvent]:
        """
        Peek at the next active event without removing it.
        Discards cancelled events at the top of the heap.
        """
        while self._queue and self._queue[0].cancelled:
            heapq.heappop(self._queue)
        return self._queue[0] if self._queue else None

    def run_due(self) -> int:
        """
        Execute all active events scheduled at or before the current clock.now().

        Clock is NOT advanced beyond its current value.
        Returns the count of executed events.
        """
        executed_count = 0
        while self._queue:
            top = self._queue[0]
            if top.cancelled:
                heapq.heappop(self._queue)
                continue
            if top.timestamp > self.clock.now():
                break

            event = heapq.heappop(self._queue)
            if event.cancelled:
                continue

            self._active_count = max(0, self._active_count - 1)
            executed_count += 1
            event.callback()

        return executed_count

    def run_until(self, target_time_ms: int) -> int:
        """
        Advance virtual time incrementally to target_time_ms, executing all scheduled
        events with timestamp <= target_time_ms in deterministic order.

        Invariants:
        - When a callback executes, clock.now() == event.timestamp.
        - After all due events are executed, clock.now() == target_time_ms.
        - target_time_ms must be >= clock.now().
        - Returns the count of executed events.
        """
        if not isinstance(target_time_ms, int):
            raise TypeError(f"target_time_ms must be an int, got {type(target_time_ms).__name__}")
        if target_time_ms < self.clock.now():
            raise ValueError(
                f"Cannot run_until backwards: target_time_ms={target_time_ms} < now={self.clock.now()}"
            )

        executed_count = 0
        while self._queue:
            top = self._queue[0]
            if top.cancelled:
                heapq.heappop(self._queue)
                continue
            if top.timestamp > target_time_ms:
                break

            event = heapq.heappop(self._queue)
            if event.cancelled:
                continue

            self._active_count = max(0, self._active_count - 1)

            # Advance clock to event timestamp BEFORE callback execution
            if event.timestamp > self.clock.now():
                self.clock.set(event.timestamp)

            executed_count += 1
            # Execute callback with clock.now() == event.timestamp guaranteed
            event.callback()

        # Advance clock to target_time_ms if it hasn't reached it yet
        if self.clock.now() < target_time_ms:
            self.clock.set(target_time_ms)

        return executed_count
