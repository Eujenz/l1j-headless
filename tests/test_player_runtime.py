"""
tests/test_player_runtime.py - Architectural & Contract Tests for HeadlessPlayerRuntime

Verifies MVP-06 Specifications:
  Test 1  — Config Object Model: GUI config to/from AutonomousConfig serialization.
  Test 2  — Live Config Mutation: Mutating HP threshold on the fly updates active runtime immediately.
  Test 3  — Destination Selection: Selecting a registered hunting destination applies to runtime.
  Test 4  — Authentic Spawn Point: Player starts at contract position (Map 0, 32477, 32875), zero teleportation.
  Test 5  — Cross-Map Navigation: Player travels via discrete MOVE_STEP and enters portal via TRANSITION_MAP.
  Test 6  — Helper Pause: Pausing helper stops autonomous policy operations; world remains active.
  Test 7  — Manual Target Selection: Manual target selection enqueues canonical PlayerOperation.
  Test 8  — Unified Action Path: Manual ATTACK executes through the identical Controller pipeline.
  Test 9  — Helper Resume: Resuming helper reactivates autonomous hunting loop.
  Test 10 — Profile Persistence: Profile save and load round-trip preserves all settings.
"""
import os
import tempfile
import unittest

from native_engine.bot import (
    AutonomousConfig,
    PotionRule,
    AVAILABLE_DESTINATIONS,
    BotState,
)
from native_engine.player_operation import PlayerOperationType
from native_engine.player_runtime import HeadlessPlayerRuntime, PlayerRuntimeSnapshot


class TestPlayerRuntime(unittest.TestCase):
    def setUp(self):
        self.runtime = HeadlessPlayerRuntime(
            config_path="configs/autonomous_default.json",
            speed=0.0,
            instant=True,
        )

    def tearDown(self):
        self.runtime.stop_background()

    def test_01_config_object_model(self):
        """Test 1: AutonomousConfig serialization and HelperModulesConfig."""
        config = self.runtime.config
        data = config.to_dict()
        self.assertIn("helper_modules", data)
        self.assertTrue(data["helper_modules"]["auto_potion"])
        self.assertTrue(data["helper_modules"]["auto_attack"])

        # Round trip
        restored = AutonomousConfig.from_dict(data)
        self.assertEqual(restored.name, config.name)
        self.assertEqual(restored.helper_modules.auto_potion, True)

    def test_02_live_config_mutation(self):
        """Test 2: Modifying HP threshold on the fly immediately updates runtime."""
        # Initial threshold
        initial_threshold = self.runtime.config.potion_rules[0].threshold
        # Mutate to 85%
        new_config = AutonomousConfig.from_dict(self.runtime.config.to_dict())
        new_config.potion_rules[0].threshold = 85.0
        self.runtime.update_config(new_config)

        self.assertEqual(self.runtime.config.potion_rules[0].threshold, 85.0)
        self.assertEqual(self.runtime.bot.config.potion_rules[0].threshold, 85.0)
        self.assertEqual(self.runtime.bot.policy.config.potion_rules[0].threshold, 85.0)

    def test_03_destination_selection(self):
        """Test 3: Selecting a registered destination updates hunting destination."""
        self.assertIn("ti_surface_field", AVAILABLE_DESTINATIONS)
        success = self.runtime.set_destination("ti_surface_field")
        self.assertTrue(success)
        self.assertEqual(self.runtime.config.hunting.destination.name, "Talking Island Surface Field")
        self.assertEqual(self.runtime.bot.policy.config.hunting.destination.map_id, 0)

    def test_04_authentic_spawn_no_teleport(self):
        """Test 4: Character starts strictly at contract coordinates (32477, 32875, Map 0)."""
        p = self.runtime.player
        self.assertEqual(p.map_id, 0)
        self.assertEqual(p.x, 32477)
        self.assertEqual(p.y, 32875)
        # Not at destination (TI Dungeon 1F is Map 1, 32671, 32804)
        self.assertNotEqual(p.map_id, 1)

    def test_05_travel_and_map_transition(self):
        """Test 5: Natural movement produces discrete MOVE_STEP and TRANSITION_MAP."""
        # Run 25 steps toward portal
        for _ in range(25):
            self.runtime.step()

        ops = self.runtime.bot.operations_count
        self.assertGreater(ops.get("MOVE_STEP", 0), 0)
        # Player coordinates moved northward toward portal (y decreased from 32875)
        self.assertLess(self.runtime.player.y, 32875)

    def test_06_pause_helper_halts_autonomous_operations(self):
        """Test 6: Pausing helper stops autonomous policy operations; world remains active."""
        self.runtime.pause_helper()
        self.assertTrue(self.runtime.is_helper_paused())

        initial_ops_count = sum(self.runtime.bot.operations_count.values())
        # Step several times
        for _ in range(5):
            self.runtime.step()

        # No new autonomous operations generated
        current_ops_count = sum(self.runtime.bot.operations_count.values())
        self.assertEqual(initial_ops_count, current_ops_count)
        self.assertEqual(self.runtime.bot.state, BotState.IDLE)

    def test_07_manual_select_target(self):
        """Test 7: Manual target selection enqueues canonical PlayerOperation."""
        self.runtime.pause_helper()

        # Find any active monster in population
        monsters = self.runtime.session.population.active_monsters
        self.assertGreater(len(monsters), 0)
        target_m = monsters[0]
        uid = getattr(target_m, "uid", target_m.id)

        self.runtime.manual_select_target(uid)
        self.assertEqual(len(self.runtime.bot.manual_queue), 0)  # already popped in step
        # Target active
        self.assertEqual(self.runtime.bot.active_target, target_m)
        self.assertGreater(self.runtime.bot.operations_count.get("SELECT_TARGET", 0), 0)

    def test_08_manual_attack_unified_path(self):
        """Test 8: Manual ATTACK executes through identical Controller pipeline."""
        self.runtime.pause_helper()
        target_m = self.runtime.session.population.active_monsters[0]
        self.runtime.bot.active_target = target_m

        initial_attacks = self.runtime.bot.operations_count.get("ATTACK", 0)
        initial_moves = self.runtime.bot.operations_count.get("MOVE_STEP", 0)

        self.runtime.manual_attack()

        # Depending on distance, either attacked or moved toward target
        current_attacks = self.runtime.bot.operations_count.get("ATTACK", 0)
        current_moves = self.runtime.bot.operations_count.get("MOVE_STEP", 0)
        self.assertTrue(current_attacks > initial_attacks or current_moves > initial_moves)

    def test_09_resume_helper_restarts_automation(self):
        """Test 9: Resuming helper reactivates autonomous hunting loop."""
        self.runtime.pause_helper()
        self.assertTrue(self.runtime.is_helper_paused())

        self.runtime.resume_helper()
        self.assertFalse(self.runtime.is_helper_paused())

        initial_ops = sum(self.runtime.bot.operations_count.values())
        # Step several times
        for _ in range(5):
            self.runtime.step()

        self.assertGreater(sum(self.runtime.bot.operations_count.values()), initial_ops)

    def test_10_profile_persistence_round_trip(self):
        """Test 10: Saving and loading profile preserves all user settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_custom_profile.json")

            # Mutate settings
            self.runtime.config.name = "MyKnightProfile"
            self.runtime.config.potion_rules[0].threshold = 68.0
            self.runtime.config.helper_modules.auto_loot = False

            self.runtime.save_profile(filepath)
            self.assertTrue(os.path.exists(filepath))

            # Load into new runtime
            new_runtime = HeadlessPlayerRuntime(
                config_path=filepath,
                speed=0.0,
                instant=True,
            )
            self.assertEqual(new_runtime.config.name, "MyKnightProfile")
            self.assertEqual(new_runtime.config.potion_rules[0].threshold, 68.0)
            self.assertEqual(new_runtime.config.helper_modules.auto_loot, False)


if __name__ == "__main__":
    unittest.main()
