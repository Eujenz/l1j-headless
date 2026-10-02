"""
native_engine/status.py - L1J 1.82 Status / Buff / Debuff Management

LEGACY_OBSERVED:
  - Source: BuffTimerInstance.java, HastePotion.java, Slow.java, CheckSpeed.java, NpcInstance.java
  - PC Haste (isSpeed): interval = int(interval * 0.75)
  - PC Slow (isSlow): interval = int(interval / 0.75)
  - PC Brave (isBrave): interval = int(interval * 0.75)
  - Monster Haste (isSpeed): speed = int(speed - speed * 0.3)
  - Monster Slow (isSlow): speed = int(speed + speed * 0.3)
  - Haste removes Slow (HastePotion.java:31); Slow removes Haste (Slow.java:43)
  - Pure Virtual Time expiration via Scheduler
"""
from enum import Enum
from typing import Dict, Optional, Callable, Any
from .temporal import VirtualClock, Scheduler, ScheduledEvent


class StatusType(str, Enum):
    HASTE = "HASTE"
    SLOW = "SLOW"
    BRAVE = "BRAVE"
    POISON = "POISON"


class StatusManager:
    """
    Manages active status effects on actors (PC & Monsters) in Virtual Time.
    """
    def __init__(self, scheduler: Scheduler, clock: VirtualClock):
        self.scheduler = scheduler
        self.clock = clock
        # Mapping: (actor_uid, status_type) -> ScheduledEvent
        self._active_timers: Dict[tuple, ScheduledEvent] = {}

    def has_status(self, actor: Any, status: StatusType) -> bool:
        uid = getattr(actor, "uid", getattr(actor, "id", None))
        return (uid, status) in self._active_timers

    def apply_status(
        self,
        actor: Any,
        status: StatusType,
        duration_ms: int,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Apply a status effect to an actor.
        Enforces canonical conflict resolution (Haste cancels Slow, Slow cancels Haste).
        """
        uid = getattr(actor, "uid", getattr(actor, "id", None))

        # 1. Conflict resolution per HastePotion.java:31 / Slow.java:43
        if status == StatusType.HASTE:
            if self.has_status(actor, StatusType.SLOW):
                self.remove_status(actor, StatusType.SLOW, log_callback=log_callback)
                # In L1J, if slow was removed by haste, the haste does not apply; it just neutralizes slow
                if log_callback:
                    log_callback(f"STATUS NEUTRALIZED: Slow removed by Haste on {actor.name}")
                return

        elif status == StatusType.SLOW:
            if self.has_status(actor, StatusType.HASTE):
                self.remove_status(actor, StatusType.HASTE, log_callback=log_callback)
                if log_callback:
                    log_callback(f"STATUS NEUTRALIZED: Haste removed by Slow on {actor.name}")
                return

        # 2. Cancel existing timer of the same status if refreshing
        if (uid, status) in self._active_timers:
            self.scheduler.cancel(self._active_timers[(uid, status)])

        # 3. Apply state flag to actor
        if status == StatusType.HASTE:
            actor.is_speed = True
        elif status == StatusType.SLOW:
            actor.is_slow = True
        elif status == StatusType.BRAVE:
            if hasattr(actor, "is_brave"):
                actor.is_brave = True

        if log_callback:
            log_callback(f"STATUS APPLIED: {status.value} on {actor.name} for {duration_ms}ms")

        # 4. Schedule expiration event on VirtualClock
        def _expire():
            self._on_expire(actor, status, log_callback)

        event = self.scheduler.schedule_after(
            duration_ms, _expire, name=f"status_expire_{uid}_{status.value}"
        )
        self._active_timers[(uid, status)] = event

    def apply_haste(
        self,
        actor: Any,
        duration_sec: int = 300,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Apply Haste for duration_sec seconds (defaults to 300s for Green Potion)."""
        self.apply_status(actor, StatusType.HASTE, duration_sec * 1000, log_callback=log_callback)

    def apply_slow(
        self,
        actor: Any,
        duration_sec: int = 60,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Apply Slow for duration_sec seconds."""
        self.apply_status(actor, StatusType.SLOW, duration_sec * 1000, log_callback=log_callback)

    def apply_brave(
        self,
        actor: Any,
        duration_sec: int = 300,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Apply Brave for duration_sec seconds."""
        self.apply_status(actor, StatusType.BRAVE, duration_sec * 1000, log_callback=log_callback)

    def remove_status(
        self,
        actor: Any,
        status: StatusType,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        uid = getattr(actor, "uid", getattr(actor, "id", None))
        key = (uid, status)
        if key in self._active_timers:
            self.scheduler.cancel(self._active_timers[key])
            del self._active_timers[key]

        if status == StatusType.HASTE:
            actor.is_speed = False
        elif status == StatusType.SLOW:
            actor.is_slow = False
        elif status == StatusType.BRAVE:
            if hasattr(actor, "is_brave"):
                actor.is_brave = False

        if log_callback:
            log_callback(f"STATUS REMOVED: {status.value} on {actor.name}")

    def clear_all(self, actor: Any, log_callback: Optional[Callable[[str], None]] = None) -> None:
        """Clear all active status effects on actor (e.g. on death)."""
        for status in [StatusType.HASTE, StatusType.SLOW, StatusType.BRAVE, StatusType.POISON]:
            if self.has_status(actor, status):
                self.remove_status(actor, status, log_callback=log_callback)

    def _on_expire(
        self,
        actor: Any,
        status: StatusType,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        uid = getattr(actor, "uid", getattr(actor, "id", None))
        key = (uid, status)
        if key in self._active_timers:
            del self._active_timers[key]

        if status == StatusType.HASTE:
            actor.is_speed = False
        elif status == StatusType.SLOW:
            actor.is_slow = False
        elif status == StatusType.BRAVE:
            if hasattr(actor, "is_brave"):
                actor.is_brave = False

        if log_callback:
            log_callback(f"STATUS EXPIRED: {status.value} on {actor.name}")
