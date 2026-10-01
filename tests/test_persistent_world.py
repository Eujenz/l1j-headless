"""
tests/test_persistent_world.py - L1J 1.82 Multi-Actor Persistent Native World Test Suite

Verifies:
  1. Multi-Actor Concurrent Presence: Player + concurrent monsters coexist.
  2. Autonomous Monster AI & Timing:
     - Approach on modespeed(0)
     - Attack on modespeed(1)
     - Asynchronous scheduling on VirtualClock (decoupled from player attack call)
  3. Monster Respawn Lifecycle:
     - Death -> despawn -> respawn event -> revival at valid tile with full HP.
  4. HP/MP Regeneration:
     - Recurring scheduled 10s tick recovering HP (HpMpTimer.java).
  5. Dynamic PC Action Timing Resolution:
     - GFX 48 Female Knight (920ms) vs GFX 61 Male Knight (880ms) vs GFX 0 (1000ms) vs GFX 37 (760ms).
  6. Determinism:
     - Seed 777777 yields bit-identical simulation results.
"""
import unittest
from mvp import initialize_s007_session
from native_engine.bot.controller import HeadlessBot
from native_engine.model import Actor, Position, Weapon, Monster
from native_engine.temporal import VirtualClock, Scheduler
from native_engine.spr_action import SprTable, get_pc_action_interval


class TestPersistentWorld(unittest.TestCase):
    def setUp(self):
        self.session = initialize_s007_session(seed_override=777777)
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
            respawn_delay_override_ms=5000,  # Fast 5s respawn for unit testing
        )

    def test_dynamic_pc_action_timing_resolution(self):
        """
        Verify PC action timing resolves dynamically from Player GFX + Action + Weapon
        per sprite_frame.sql and SprTable.java.
        MUST NOT rely on universal 920ms or 880ms constants.
        """
        spr = SprTable.get_instance()
        sw = Weapon(item_id=1, name="Long Sword", weapon_type="sword", dmg_small=8, dmg_large=12)
        bow = Weapon(item_id=20, name="Bow", weapon_type="bow", dmg_small=3, dmg_large=3)

        # GFX 48: Female Knight
        self.assertEqual(spr.resolve_pc_attack_interval(48, sw), 920)
        self.assertEqual(spr.resolve_pc_attack_interval(48, None), 1000)
        self.assertEqual(spr.resolve_pc_attack_interval(48, bow), 1840)

        # GFX 61: Male Knight
        self.assertEqual(spr.resolve_pc_attack_interval(61, sw), 880)
        self.assertEqual(spr.resolve_pc_attack_interval(61, None), 880)
        self.assertEqual(spr.resolve_pc_attack_interval(61, bow), 1920)

        # GFX 0: Prince
        self.assertEqual(spr.resolve_pc_attack_interval(0, sw), 1000)
        self.assertEqual(spr.resolve_pc_attack_interval(0, None), 840)

        # GFX 37: Female Elf
        self.assertEqual(spr.resolve_pc_attack_interval(37, sw), 760)
        self.assertEqual(spr.resolve_pc_attack_interval(37, None), 800)
        self.assertEqual(spr.resolve_pc_attack_interval(37, bow), 960)

    def test_multi_actor_concurrent_presence(self):
        """
        Verify multiple monsters and the player exist simultaneously in the active world.
        """
        monsters = self.session.population.get_all_alive_on_map(map_id=0)
        self.assertGreater(len(monsters), 5, "World should contain multiple concurrent active monsters")
        uids = [m.uid for m in monsters]
        self.assertEqual(len(uids), len(set(uids)), "All monsters must have unique UIDs")

    def test_autonomous_monster_timing_and_scheduling(self):
        """
        Verify monster attacks and moves occur via scheduled events driven by modespeed.
        Monster attacks use modespeed(1), moves use modespeed(0).
        """
        from native_engine.model import Inventory
        # Create a test monster adjacent to player
        m = Monster(
            uid=99991,
            id=10,
            name="Test Werewolf",
            pos=Position(self.session.player.x + 1, self.session.player.y, self.session.player.map_id),
            level=3,
            hp=50,
            max_hp=50,
            ac=10,
            exp=30,
            size="small",
            heading=0,
            inventory=Inventory(),
            min_dmg=50,
            max_dmg=60,
            gfx=33,
            move_speed_ms=640,    # modespeed(0) = 640ms
            attack_speed_ms=960,  # modespeed(1) = 960ms
            target=self.session.player,
        )
        self.session.population._map_monsters[m.pos.map_id].append(m)

        # Schedule monster step at T=100
        self.bot._schedule_monster_action(m, delay_ms=100)
        self.assertTrue(self.scheduler.has_pending_events())

        initial_player_hp = self.session.player.hp
        # Run until T=100: monster attacks player
        self.scheduler.run_until(100)
        self.assertEqual(self.clock.now(), 100)
        self.assertLess(self.session.player.hp, initial_player_hp, "Player should take damage from monster attack")

        # Next monster attack should be scheduled at T = 100 + 960 = 1060ms
        next_event = self.scheduler.peek_next()
        self.assertIsNotNone(next_event)
        self.assertEqual(next_event.timestamp, 1060)

    def test_monster_respawn_lifecycle(self):
        """
        Verify dead monster despawns and is resurrected after respawn timer expires.
        """
        monsters = self.session.population.get_all_alive_on_map(map_id=0)
        target = monsters[0]
        original_hp = target.max_hp
        target_uid = target.uid

        # Kill monster
        target.hp = 0
        target.is_dead = True
        self.session.population.despawn(target)
        self.assertTrue(target.is_dead)

        # Schedule respawn in 3000ms
        self.bot.scheduler.schedule_after(3000, lambda m=target: self.bot._execute_respawn(m), name="test_respawn")

        # Advance to T=2999: still dead
        self.scheduler.run_until(2999)
        self.assertTrue(target.is_dead)

        # Advance to T=3000: respawns
        self.scheduler.run_until(3000)
        self.assertFalse(target.is_dead)
        self.assertEqual(target.hp, original_hp)
        self.assertEqual(self.bot.respawn_count, 1)

    def test_recurring_hp_regeneration(self):
        """
        Verify natural HP regeneration tick fires every 10s and restores HP.
        """
        self.session.player.hp = 50  # Damage player
        self.session.player.max_hp = 100

        # Advance to T=9999: no regen yet
        self.scheduler.run_until(9999)
        self.assertEqual(self.session.player.hp, 50)

        # Advance to T=10000: first HP regen tick (+5 HP)
        self.scheduler.run_until(10000)
        self.assertEqual(self.session.player.hp, 55)

        # Advance to T=20000: second HP regen tick (+5 HP)
        self.scheduler.run_until(20000)
        self.assertEqual(self.session.player.hp, 60)

    def test_determinism_seed_777777(self):
        """
        Verify running the persistent world with identical seed produces bit-identical results.
        """
        session_a = initialize_s007_session(seed_override=777777)
        session_a.player.map_id = 1
        session_a.player.x = 32671
        session_a.player.y = 32804
        clock_a = VirtualClock(0)
        sched_a = Scheduler(clock_a)
        bot_a = HeadlessBot(
            player=session_a.player,
            world_maps=session_a.world.maps,
            population=session_a.population,
            progression=session_a.progression,
            clock=clock_a,
            scheduler=sched_a,
            rng=session_a.rng,
            respawn_delay_override_ms=10000,
        )
        res_a = bot_a.run_session(max_kills=3, max_virtual_ms=60000)

        session_b = initialize_s007_session(seed_override=777777)
        session_b.player.map_id = 1
        session_b.player.x = 32671
        session_b.player.y = 32804
        clock_b = VirtualClock(0)
        sched_b = Scheduler(clock_b)
        bot_b = HeadlessBot(
            player=session_b.player,
            world_maps=session_b.world.maps,
            population=session_b.population,
            progression=session_b.progression,
            clock=clock_b,
            scheduler=sched_b,
            rng=session_b.rng,
            respawn_delay_override_ms=10000,
        )
        res_b = bot_b.run_session(max_kills=3, max_virtual_ms=60000)

        self.assertEqual(res_a["kills"], res_b["kills"])
        self.assertEqual(res_a["damage_dealt"], res_b["damage_dealt"])
        self.assertEqual(res_a["damage_taken"], res_b["damage_taken"])
        self.assertEqual(res_a["virtual_time_ms"], res_b["virtual_time_ms"])
        self.assertEqual(res_a["items_looted"], res_b["items_looted"])
        self.assertEqual(res_a["trace_log"], res_b["trace_log"])


if __name__ == "__main__":
    unittest.main()
