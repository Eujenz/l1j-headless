"""
tests/test_player_config_ui.py - Automated Headless Smoke & Integration Tests for Player UI

Runs Tkinter widgets headlessly (root.withdraw()) to guarantee 100% UI stability,
widget lifecycle, config panel round-trips, and manual control dispatch.
"""
import os
import tempfile
import tkinter as tk
import unittest

from native_engine.bot import AutonomousConfig
from native_engine.player_runtime import HeadlessPlayerRuntime
from ui import PlayerViewModel, ConfigPanel, PlayerWindow


class TestPlayerConfigUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create hidden root window for entire test class
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.runtime = HeadlessPlayerRuntime(
            config_path="configs/autonomous_default.json",
            speed=0.0,
            instant=True,
        )
        self.vm = PlayerViewModel(self.runtime)

    def tearDown(self):
        self.runtime.stop_background()

    def test_01_view_model_projection(self):
        """Verifies PlayerViewModel projects state accurately from runtime."""
        self.assertEqual(self.vm.character_name, "Arthur")
        self.assertIn("Lv 1", self.vm.level_str)
        self.assertEqual(self.vm.hp_ratio, 1.0)
        self.assertEqual(self.vm.mp_ratio, 1.0)
        self.assertIn("Adena", self.vm.adena_str)
        self.assertFalse(self.vm.is_helper_paused)

    def test_02_config_panel_load_and_build(self):
        """Verifies ConfigPanel loads from config and builds back cleanly."""
        frame = tk.Frame(self.root)
        panel = ConfigPanel(frame, view_model=self.vm)
        panel.p1_thresh_var.set(80.0)
        panel.p2_thresh_var.set(40.0)
        panel.dest_var.set("ti_surface_field")
        panel.mod_vars["auto_loot"].set(False)

        built_cfg = panel.build_config()
        self.assertEqual(built_cfg.potion_rules[0].threshold, 80.0)
        self.assertEqual(built_cfg.potion_rules[1].threshold, 40.0)
        self.assertEqual(built_cfg.hunting.destination.name, "Talking Island Surface Field")
        self.assertFalse(built_cfg.helper_modules.auto_loot)

    def test_03_config_panel_apply_to_game(self):
        """Verifies clicking apply immediately updates live runtime config."""
        frame = tk.Frame(self.root)
        panel = ConfigPanel(frame, view_model=self.vm)
        panel.p1_thresh_var.set(65.0)
        panel.apply_to_game()

        self.assertEqual(self.runtime.config.potion_rules[0].threshold, 65.0)
        self.assertEqual(self.runtime.bot.policy.config.potion_rules[0].threshold, 65.0)

    def test_04_player_window_smoke_test(self):
        """Smoke test verifying PlayerWindow initialization, updates, and controls."""
        win_frame = tk.Toplevel(self.root)
        win_frame.withdraw()

        app = PlayerWindow(win_frame, runtime=self.runtime)
        app.update_ui()

        # Check widget texts
        self.assertIn("Arthur", app.char_name_lbl.cget("text"))
        self.assertIn("ACTIVE", app.helper_badge_lbl.cget("text"))

        # Test toggle pause
        app._on_toggle_pause()
        self.assertTrue(self.runtime.is_helper_paused())
        self.assertIn("PAUSED", app.helper_badge_lbl.cget("text"))

        # Test resume
        app._on_toggle_pause()
        self.assertFalse(self.runtime.is_helper_paused())

        # Test manual move via D-pad
        app.vm.manual_move(0)  # North
        self.assertGreater(len(self.runtime.bot.manual_queue), 0)

        # Test manual attack button
        app._on_manual_attack()

        # Clean close
        app.on_close()


if __name__ == "__main__":
    unittest.main()
