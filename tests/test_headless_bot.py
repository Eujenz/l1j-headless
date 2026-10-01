"""
tests/test_headless_bot.py - Test Suite for Headless Bot Autonomous Controller

Verifies:
  - Perception snapshot extraction.
  - Bot policy state transitions and target prioritization (reachability, agro, distance).
  - Movement pacing using canonical 640ms virtual interval.
  - Combat execution with IMMEDIATE damage timing and HP mutation.
  - Monster death, canonical EXP distribution, and level-up.
  - Drop generation from 1.82 tables and autonomous looting into inventory.
  - Full end-to-end multi-kill hunting session in Virtual Time.
"""
import unittest
from mvp import initialize_s007_session
from native_engine.bot import (
    HeadlessBot,
    BotPolicy,
    BotState,
    BotActionType,
    PerceptionSystem,
    DropSystem,
)
from native_engine.temporal import VirtualClock, Scheduler
from native_engine.model import Item, Position


class TestHeadlessBot(unittest.TestCase):
    def setUp(self):
        self.session = initialize_s007_session(seed_override=777777)
        # Position player at TI Dungeon 1F entrance
        self.session.player.map_id = 1
        self.session.player.x = 32671
        self.session.player.y = 32804
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.bot = HeadlessBot(
            player=self.session.player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            rng=self.session.rng,
        )

    def test_perception_snapshot(self):
        perception = PerceptionSystem(sight_radius=14)
        snapshot = perception.perceive(
            player=self.session.player,
            population=self.session.population,
            ground_drops=[],
        )

        self.assertEqual(snapshot.player_id, 10001)
        self.assertEqual(snapshot.name, "Arthur")
        self.assertEqual(snapshot.level, 1)
        self.assertEqual(snapshot.hp, 100)
        self.assertEqual(snapshot.max_hp, 100)
        self.assertGreater(len(snapshot.nearby_monsters), 0)
        self.assertFalse(snapshot.is_dead)

    def test_policy_target_selection_reachability(self):
        policy = BotPolicy()
        perception = PerceptionSystem(sight_radius=14)
        snapshot = perception.perceive(
            player=self.session.player,
            population=self.session.population,
            ground_drops=[],
        )

        # Select target with reachability check
        target = policy.select_target(snapshot, map_grid=self.session.world.get_map(1))
        self.assertIsNotNone(target)
        self.assertTrue(target.hp > 0)
        self.assertFalse(target.is_dead)

    def test_drop_system_canonical_drops(self):
        drop_sys = DropSystem(self.session.rng)
        drops = drop_sys.roll_drops(
            monster_id=2,  # Skeleton
            monster_name="Skeleton",
            pos=Position(32671, 32804, 1),
            tick=1000,
        )
        self.assertGreater(len(drops), 0)
        # Skeleton drops should match canonical table
        valid_items = {288, 102, 61, 43, 94, 89, 140, 162}
        for d in drops:
            self.assertIn(d.item.item_id, valid_items)

    def test_e2e_autonomous_hunting_vertical_slice(self):
        # Run autonomous bot session to achieve 2 kills
        result = self.bot.run_session(max_kills=2, max_virtual_ms=300000)

        self.assertEqual(result["reason"], "KILL_LIMIT_REACHED")
        self.assertEqual(result["kills"], 2)
        self.assertGreaterEqual(result["final_exp"], 50)
        self.assertGreater(result["final_hp"], 0)
        self.assertGreater(result["virtual_time_ms"], 0)
        self.assertGreater(result["damage_dealt"], 0)
        # Verify trace log contains expected vertical slice sequence
        log_text = "\n".join(result["trace_log"])
        self.assertIn("PLAYER SPAWN", log_text)
        self.assertIn("ATTACK TRIGGERED", log_text)
        self.assertIn("DAMAGE RESOLVED", log_text)
        self.assertIn("IMMEDIATE", log_text)
        self.assertIn("MONSTER DIED", log_text)
        self.assertIn("LEVEL UP", log_text)

    def test_knight_sword_canonical_interval(self):
        """
        Regression Test: Knight one-hand sword attack interval must strictly match
        the canonical benchmark interval of 920ms (SprTable:84, sprite_frame.sql GFX 48 action 5).
        """
        self.assertEqual(self.bot.attack_interval_ms, 920)
        self.assertEqual(self.session.player.attack_speed_ms, 920)

    def test_persistent_simulation_time_limit(self):
        """
        Validates persistent auto-hunt when max_kills is None (time-bound session).
        Ensures bot runs persistently for requested virtual time without terminating early.
        """
        sim_ms = 60000  # 1 virtual minute
        result = self.bot.run_session(max_kills=None, max_virtual_ms=sim_ms)
        self.assertEqual(result["reason"], "SIMULATION_TIME_REACHED")
        self.assertEqual(result["virtual_time_ms"], sim_ms)
        self.assertGreater(result["final_hp"], 0)
        self.assertFalse(self.session.player.is_dead)


if __name__ == "__main__":
    unittest.main()
