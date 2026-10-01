"""
native_engine/temporal/event.py - Scheduled Event Abstraction

Architecture:
  - Represents an event scheduled to fire at an absolute virtual timestamp.
  - Deterministic total ordering based on (timestamp, sequence).
  - Explicit avoidance of callback comparison to guarantee heap safety.
"""
from dataclasses import dataclass
from typing import Callable, Any


@dataclass(order=False)
class ScheduledEvent:
    """
    Represents an event scheduled in virtual time.

    Fields:
    - timestamp: Absolute virtual time in integer milliseconds when the event should execute.
    - sequence: Monotonic sequence number assigned by Scheduler to break ties deterministically.
    - callback: Callable to execute when the event fires.
    - cancelled: Boolean flag indicating if this event has been cancelled.
    - name: Optional descriptive label for tracing and debugging.
    """
    timestamp: int
    sequence: int
    callback: Callable[[], Any]
    cancelled: bool = False
    name: str = ""

    def cancel(self) -> None:
        """Mark this event as cancelled."""
        self.cancelled = True

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, ScheduledEvent):
            return NotImplemented
        return (self.timestamp, self.sequence) < (other.timestamp, other.sequence)

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, ScheduledEvent):
            return NotImplemented
        return (self.timestamp, self.sequence) <= (other.timestamp, other.sequence)

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, ScheduledEvent):
            return NotImplemented
        return (self.timestamp, self.sequence) > (other.timestamp, other.sequence)

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, ScheduledEvent):
            return NotImplemented
        return (self.timestamp, self.sequence) >= (other.timestamp, other.sequence)

    def __repr__(self) -> str:
        status = "CANCELLED" if self.cancelled else "ACTIVE"
        name_str = f" '{self.name}'" if self.name else ""
        return f"<ScheduledEvent{name_str} @ {self.timestamp}ms seq={self.sequence} [{status}]>"
