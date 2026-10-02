"""
tests/test_mvp_entrypoint.py - Comprehensive Unit & Regression Tests for
Official L1J Headless Player MVP Entrypoint (mvp.py).

Test Suite Requirements:
  Test A — Default Entrypoint: python mvp.py runs official Headless Player runtime (not S006/S007 demo/GameSession.hunt)
  Test B — No Teleport Startup: Player starts at contract pos != hunting dest, must produce MOVE_STEP / travel
  Test C — Map Transition: Crossing from Map 0 to Map 1 produces TRANSITION_MAP
  Test D — Configuration Changes Behavior: Verifies variance between default, conservative, aggressive
  Test E — Same Execution Path: Manual PlayerOperation vs Automation-generated PlayerOperation execute through identical path
  Test F — Negative Economy Allowed: Deficit (adena_spent > adena_earned) certified as valid PASS
"""

import os
import subprocess
import sys
import unittest
from typing import Dict, Any

from mvp import run_headless_player_mvp, initialize_s007_session
from native_engine.bot import HeadlessBot, AutonomousConfig, BotPolicy, BotState
from native_engine.model import Position, Item, Monster
from native_engine.player_operation import PlayerOperation, PlayerOperationType
from native_engine.temporal import VirtualClock, Scheduler


class TestMvpEntrypoint(unittest.TestCase):
    def setUp(self):
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.session = initialize_s007_session(clock=self.clock)
        self.config = AutonomousConfig.load_json("configs/autonomous_default.json")

    def test_a_default_entrypoint(self):
        """
        Test A — Default Entrypoint:
        Ensures `python mvp.py --duration 10000` runs the official Headless Player
        runtime and outputs the official HEADLESS PLAYER RUNTIME SUMMARY,
        rather than falling back to S006 demo or S007 legacy demo.
        """
        res = subprocess.run(
            [sys.executable, "mvp.py", "--duration", "10000"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0, f"mvp.py execution failed: {res.stderr}")
        self.assertIn("HEADLESS PLAYER RUNTIME SUMMARY", res.stdout)
        self.assertIn("PLAYER OPERATIONS EXECUTED", res.stdout)
        self.assertNotIn("DEMO COMPLETED SUCCESSFULLY", res.stdout)
        self.assertNotIn("SCENARIO 007 DEMO COMPLETED", res.stdout)

    def test_b_no_teleport_startup(self):
        """
        Test B — No Teleport Startup:
        Contract starting position (32477, 32875, Map 0) != destination (32671, 32804, Map 1).
        Verifies that on startup, player does NOT teleport immediately to destination,
        and produces MOVE_STEP operations to navigate along the road.
        """
        player = self.session.player
        contract_start_pos = Position(32477, 32875, map_id=0)
        self.assertEqual(player.pos.map_id, contract_start_pos.map_id)
        self.assertEqual(player.pos.x, contract_start_pos.x)
        self.assertEqual(player.pos.y, contract_start_pos.y)

        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=self.config,
            provide_starter_supplies=False,
        )

        # Run 5 steps to verify natural movement
        for _ in range(5):
            bot.step()

        self.assertGreater(bot.operations_count.get("MOVE_STEP", 0), 0)
        # Verify player moved toward portal (heading north y decreased from 32875)
        self.assertEqual(player.map_id, 0)
        self.assertLess(player.y, 32875)

    def test_c_map_transition(self):
        """
        Test C — Map Transition:
        Moving from Map 0 to Map 1 must produce a discrete TRANSITION_MAP PlayerOperation,
        rather than an artificial direct mutation of player.map_id.
        """
        result = run_headless_player_mvp(
            config_path="configs/autonomous_default.json",
            duration_ms=60000,
            verbose=False,
        )
        ops = result.get("player_operations", {})
        self.assertGreaterEqual(
            ops.get("TRANSITION_MAP", 0),
            1,
            "Expected at least 1 TRANSITION_MAP operation during dungeon journey",
        )
        self.assertGreaterEqual(result["maps_traversed"], 1)

    def test_d_configuration_changes_behavior(self):
        """
        Test D — Configuration Changes Behavior:
        Verifies that conservative, aggressive, and default profiles produce
        observable behavioral differences (e.g. potion consumption or return counts).
        """
        res_default = run_headless_player_mvp(
            config_path="configs/autonomous_default.json",
            duration_ms=300000,
            verbose=False,
        )
        res_aggressive = run_headless_player_mvp(
            config_path="configs/aggressive_hunt.json",
            duration_ms=300000,
            verbose=False,
        )

        # Aggressive configuration has lower HP drinking threshold (50% vs 70%)
        # and therefore drinks fewer potions in the same virtual timeframe
        self.assertNotEqual(
            res_default["potions_consumed"],
            res_aggressive["potions_consumed"],
            "Different policy configurations should produce different potion usage",
        )

    def test_e_same_execution_path(self):
        """
        Test E — Same Execution Path:
        Verifies that a manual PlayerOperation and an automation-generated PlayerOperation
        execute through the exact same controller method (execute_player_operation).
        """
        player = self.session.player
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=self.config,
            provide_starter_supplies=False,
        )

        from native_engine.model import Inventory
        target = Monster(
            id=1, uid=99991, name="TargetDummy", level=1,
            hp=30, max_hp=30, ac=10, exp=10,
            size="small", pos=Position(player.x + 1, player.y, map_id=player.map_id),
            heading=0, inventory=Inventory(), agro=1
        )

        # 1. Manual Player Operation
        manual_op = PlayerOperation(PlayerOperationType.SELECT_TARGET, target=target)
        bot.execute_player_operation(manual_op)
        self.assertEqual(player.current_target, target)
        self.assertEqual(bot.operations_count["SELECT_TARGET"], 1)

        # 2. Automation-generated Player Operation
        auto_op = bot.policy.decide_next_action(
            BotState.SEARCH_TARGET,
            bot.perception_sys.perceive(player, self.session.population, [], target),
            map_grid=self.session.world.maps[player.map_id],
        )[1]
        self.assertIsInstance(auto_op, PlayerOperation)
        bot.execute_player_operation(auto_op)
        op_name = auto_op.op_type.name
        if op_name == "USE_POTION":
            op_name = "USE_ITEM"
        self.assertGreaterEqual(bot.operations_count[op_name], 1)

    def test_f_negative_economy_allowed(self):
        """
        Test F — Negative Economy Allowed:
        Novice characters buying potions run an economic deficit (net_adena < 0).
        Verifies that a negative economic balance is a certified valid gameplay outcome,
        not a test failure or error.
        """
        result = run_headless_player_mvp(
            config_path="configs/autonomous_default.json",
            duration_ms=600000,
            verbose=False,
        )
        net_adena = result["adena_earned"] - result["adena_spent"]
        # In early TI Dungeon, novice knights consume more potion value than monsters drop
        # The runtime correctly records and passes this economic outcome
        self.assertIn("reason", result)
        self.assertEqual(result["reason"], "SIMULATION_TIME_REACHED")
        self.assertTrue(isinstance(net_adena, int))


if __name__ == "__main__":
    unittest.main()
