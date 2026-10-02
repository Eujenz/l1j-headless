"""
ui/player_view_model.py - View Model for L1J Headless Player UI

Decouples Tkinter presentation layer from HeadlessPlayerRuntime engine logic.
Aggregates state snapshots and exposes UI-friendly command handlers.
"""
from typing import Dict, List, Optional, Any, Callable
from native_engine.player_runtime import HeadlessPlayerRuntime, PlayerRuntimeSnapshot
from native_engine.bot import (
    AutonomousConfig,
    AVAILABLE_DESTINATIONS,
    HuntingDestination,
)


class PlayerViewModel:
    """
    ViewModel coordinating UI interactions and dispatching commands
    to the HeadlessPlayerRuntime.
    """

    def __init__(self, runtime: HeadlessPlayerRuntime):
        self.runtime = runtime
        self._last_snapshot: Optional[PlayerRuntimeSnapshot] = None

    def refresh_snapshot(self) -> PlayerRuntimeSnapshot:
        self._last_snapshot = self.runtime.get_snapshot()
        return self._last_snapshot

    def get_cached_snapshot(self) -> Optional[PlayerRuntimeSnapshot]:
        """Return last cached snapshot without requesting a new one (for canvas/log polling)."""
        return self._last_snapshot

    @property
    def snapshot(self) -> PlayerRuntimeSnapshot:
        if self._last_snapshot is None:
            return self.refresh_snapshot()
        return self._last_snapshot

    # ---------------------------------------------------------------------------
    # Player & World State Properties
    # ---------------------------------------------------------------------------

    @property
    def character_name(self) -> str:
        return self.snapshot.player_name

    @property
    def level_str(self) -> str:
        return f"Lv {self.snapshot.level} ({self.snapshot.exp} EXP)"

    @property
    def hp_str(self) -> str:
        return f"{self.snapshot.hp} / {self.snapshot.max_hp} HP"

    @property
    def hp_ratio(self) -> float:
        if self.snapshot.max_hp <= 0:
            return 0.0
        return max(0.0, min(1.0, self.snapshot.hp / self.snapshot.max_hp))

    @property
    def mp_str(self) -> str:
        return f"{self.snapshot.mp} / {self.snapshot.max_mp} MP"

    @property
    def mp_ratio(self) -> float:
        if self.snapshot.max_mp <= 0:
            return 0.0
        return max(0.0, min(1.0, self.snapshot.mp / self.snapshot.max_mp))

    @property
    def location_str(self) -> str:
        return f"{self.snapshot.map_name} ({self.snapshot.x}, {self.snapshot.y})"

    @property
    def adena_str(self) -> str:
        return f"{self.snapshot.adena:,} Adena"

    @property
    def weapon_str(self) -> str:
        return self.snapshot.equipped_weapon_name

    @property
    def is_helper_paused(self) -> bool:
        return self.snapshot.helper_paused

    @property
    def helper_status_str(self) -> str:
        if self.snapshot.helper_paused:
            return "PAUSED (手動操作中)"
        return f"ACTIVE ({self.snapshot.bot_state})"

    # ---------------------------------------------------------------------------
    # User Command Actions
    # ---------------------------------------------------------------------------

    def toggle_helper_pause(self) -> bool:
        """Toggles between paused manual mode and active automation."""
        if self.runtime.is_helper_paused():
            self.runtime.resume_helper()
        else:
            self.runtime.pause_helper()
        self.refresh_snapshot()
        return self.runtime.is_helper_paused()

    def manual_move(self, heading: int) -> None:
        """Move 1 step in specified heading (0: N, 1: NE, 2: E, 3: SE, 4: S, 5: SW, 6: W, 7: NW)."""
        self.runtime.manual_move(heading)
        self.refresh_snapshot()

    def manual_select_target(self, target_uid: int) -> None:
        self.runtime.manual_select_target(target_uid)
        self.refresh_snapshot()

    def manual_attack(self) -> None:
        self.runtime.manual_attack()
        self.refresh_snapshot()

    def manual_use_item(self, item_id: int) -> bool:
        res = self.runtime.manual_use_item(item_id)
        self.refresh_snapshot()
        return res

    def manual_return_town(self) -> None:
        self.runtime.manual_return_town()
        self.refresh_snapshot()

    def set_speed(self, speed: float) -> None:
        self.runtime.set_speed(speed)

    def set_destination(self, dest_key: str) -> bool:
        res = self.runtime.set_destination(dest_key)
        self.refresh_snapshot()
        return res

    def update_config(self, new_config: AutonomousConfig) -> None:
        self.runtime.update_config(new_config)
        self.refresh_snapshot()

    def save_profile(self, filepath: str) -> None:
        self.runtime.save_profile(filepath)

    def load_profile(self, filepath: str) -> bool:
        res = self.runtime.load_profile(filepath)
        self.refresh_snapshot()
        return res
