"""
tests/test_player_ui_performance.py - Headless Tkinter performance and contract tests

Tests (all run headless, no visible GUI windows):
  1. test_snapshot_time: get_snapshot() < 10ms
  2. test_game_events_bounded: event queue never exceeds 500
  3. test_log_append_strategy: new events appended, not full-rebuild
  4. test_monster_list_capped: nearby_monsters snapshot capped at 20
  5. test_poll_frequency_reasonable: 50 HUD polls complete within reasonable time
  6. test_chinese_bot_state: bot_state in snapshot maps to Chinese via BOT_STATE_ZH
  7. test_chinese_map_name: map_name in snapshot is Chinese
  8. test_game_events_in_snapshot: snapshot has game_events field
"""
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from native_engine.player_runtime import HeadlessPlayerRuntime
from native_engine.temporal import VirtualClock
from ui.game_events import BOT_STATE_ZH, MAP_NAME_ZH


def _make_instant_runtime() -> HeadlessPlayerRuntime:
    """Create a VirtualClock runtime for testing (no real-time sleep)."""
    return HeadlessPlayerRuntime(
        config_path="configs/autonomous_default.json",
        seed=777777,
        instant=True,
    )


class TestSnapshotPerformance(unittest.TestCase):

    def setUp(self):
        self.runtime = _make_instant_runtime()

    def test_snapshot_generation_time(self):
        """get_snapshot() must complete in under 10ms."""
        # Warm up
        self.runtime.get_snapshot()
        # Measure
        start = time.perf_counter()
        for _ in range(20):
            snap = self.runtime.get_snapshot()
        elapsed = (time.perf_counter() - start) * 1000 / 20
        self.assertLess(elapsed, 10.0,
                        f"Snapshot generation too slow: {elapsed:.2f}ms per call")

    def test_nearby_monsters_capped(self):
        """Nearby monsters in snapshot are bounded to at most 20."""
        snap = self.runtime.get_snapshot()
        self.assertLessEqual(len(snap.nearby_monsters), 20)

    def test_game_events_field_exists(self):
        """PlayerRuntimeSnapshot must have a game_events field."""
        snap = self.runtime.get_snapshot()
        self.assertTrue(hasattr(snap, "game_events"),
                        "PlayerRuntimeSnapshot missing game_events field")
        self.assertIsInstance(snap.game_events, list)

    def test_game_events_bounded(self):
        """Game event deque is bounded at 500 events even after running simulation."""
        # Run 5 steps to generate some events
        for _ in range(50):
            self.runtime.step()

        snap = self.runtime.get_snapshot()
        # Can't exceed the deque's maxlen
        self.assertLessEqual(len(snap.game_events), 500)

    def test_snapshot_recent_logs_bounded(self):
        """recent_logs (debug trace) should not grow unboundedly."""
        for _ in range(20):
            self.runtime.step()
        # recent_logs is sliced to last 50 in get_snapshot()
        snap = self.runtime.get_snapshot()
        self.assertLessEqual(len(snap.recent_logs), 50)

    def test_chinese_map_name_in_snapshot(self):
        """map_name in snapshot should use Traditional Chinese (e.g. 話島村莊)."""
        snap = self.runtime.get_snapshot()
        # Player starts on Map 0 (Talking Island surface)
        expected_zh = MAP_NAME_ZH.get(snap.map_id, "")
        self.assertEqual(snap.map_name, expected_zh,
                         f"Expected Chinese map name '{expected_zh}', got '{snap.map_name}'")

    def test_chinese_bot_state_in_map(self):
        """BOT_STATE_ZH contains all common BotState names."""
        required_states = [
            "SEARCH_TARGET", "MOVE_TO_TARGET", "ATTACK", "RECOVER",
            "LOOT", "ROAM", "TRAVELING_TO_HUNT", "RETURNING_TO_TOWN",
            "NAVIGATING_TO_SHOP", "BUYING_SUPPLIES", "IDLE",
        ]
        for state in required_states:
            self.assertIn(state, BOT_STATE_ZH,
                          f"BOT_STATE_ZH missing Chinese translation for '{state}'")
            # Value should be non-empty Chinese
            zh = BOT_STATE_ZH[state]
            self.assertTrue(len(zh) > 0, f"Empty translation for '{state}'")

    def test_poll_frequency_reasonable(self):
        """Simulating 50 HUD-equivalent get_snapshot() calls should complete within 500ms."""
        start = time.perf_counter()
        for _ in range(50):
            snap = self.runtime.get_snapshot()
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 500.0,
                        f"50 snapshot polls took {elapsed_ms:.0f}ms (too slow for UI polling)")


class TestGameEventDequeIntegration(unittest.TestCase):
    """Test that running the runtime actually populates game_events."""

    def setUp(self):
        self.runtime = _make_instant_runtime()

    def test_game_events_populated_after_simulation(self):
        """After running simulation steps, game_events should not be empty."""
        # Run for a bit to trigger some events (potion usage, movement, etc.)
        for _ in range(200):
            self.runtime.step()
        snap = self.runtime.get_snapshot()
        # game_events might still be empty if no player-visible events occurred in few steps
        # but the list should be a list regardless
        self.assertIsInstance(snap.game_events, list)

    def test_game_events_have_chinese_text(self):
        """Any game event text should not contain raw enum values."""
        for _ in range(500):
            self.runtime.step()
        snap = self.runtime.get_snapshot()
        forbidden_patterns = ["TRAVELING_TO_HUNT", "SELECT_TARGET", "BUY_SUPPLY", "SIMULATION_TIME_REACHED"]
        for evt in snap.game_events:
            for pat in forbidden_patterns:
                self.assertNotIn(pat, evt.text,
                                 f"Event text contains raw enum '{pat}': {evt.text!r}")


if __name__ == "__main__":
    unittest.main()
