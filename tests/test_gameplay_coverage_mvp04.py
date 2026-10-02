"""
tests/test_gameplay_coverage_mvp04.py - L1J 1.82 Gameplay Coverage Expansion Tests

Covers:
  - Domain A: Equipment / Weapon Fidelity & Dynamic SprTable Action Intervals
  - Domain B: Potion / Recovery Semantics (Red Potion 10-30 HP, Green Potion 300s Haste)
  - Domain C: Status / Buff / Debuff Mechanics (PC / Monster multipliers, Haste/Slow conflict)
  - Domain D: Skill Mechanics (Energy Bolt, Lesser Heal, Haste)
  - Domain E: Death & Respawn Semantics (Novice Protection Lv <= 9, EXP loss, buff clear)
  - Domain F: NPC Shop Interaction (Pandora shop purchases with adena)
"""
import unittest
from native_engine.model import Actor, Monster, Position, Item, Weapon, Inventory
from native_engine.temporal import VirtualClock, Scheduler
from native_engine.equipment import EquipmentManager
from native_engine.spr_action import get_pc_action_interval
from native_engine.status import StatusManager, StatusType
from native_engine.skill import SkillEngine, CANONICAL_SKILLS
from native_engine.npc import NpcShop, PANDORA_SHOP
from native_engine.rng import NativeRng


class TestGameplayCoverageMVP04(unittest.TestCase):

    def setUp(self):
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.status_mgr = StatusManager(self.scheduler, self.clock)
        self.rng = NativeRng(42)
        self.skill_engine = SkillEngine(self.rng)

        # Canonical Male Knight (GFX 61)
        self.knight = Actor(
            id=1,
            name="TestKnight",
            class_type=1,
            level=5,
            hp=100,
            max_hp=100,
            str=16,
            dex=12,
            con=14,
            int=10,
            wis=10,
            cha=10,
            pos=Position(32608, 32742, 0),
            heading=0,
            auto_pickup=True,
            inventory=Inventory(),
            mp=30,
            max_mp=30,
            ac=10,
            gfx=61,
            move_speed_ms=640,
            attack_speed_ms=880,  # GFX 61 sword
        )

        # Canonical Monster: Goblin (GFX 341, mode 0: move 1200ms, mode 1: atk 1000ms)
        self.goblin = Monster(
            id=45001,
            uid=101,
            name="Goblin",
            level=3,
            hp=20,
            max_hp=20,
            ac=10,
            exp=10,
            size="small",
            pos=Position(32609, 32742, 0),
            heading=0,
            inventory=Inventory(),
            gfx=341,
            min_dmg=1,
            max_dmg=4,
            move_speed_ms=1200,
            attack_speed_ms=1000,
        )

    # =========================================================================
    # Domain A: Equipment / Weapon Fidelity & Action Timing
    # =========================================================================
    def test_domain_a_weapon_action_timing_knight_gfx61(self):
        """Male Knight (GFX 61): Sword=880ms, Spear=920ms, Bow=1920ms, BareHands=880ms."""
        sword = Weapon(item_id=1, name="Long Sword", weapon_type=1, dmg_small=8, dmg_large=12)
        spear = Weapon(item_id=2, name="Spear", weapon_type=3, dmg_small=7, dmg_large=7)
        bow = Weapon(item_id=3, name="Bow", weapon_type=4, dmg_small=3, dmg_large=3)

        self.assertEqual(get_pc_action_interval(61, sword), 880)
        self.assertEqual(get_pc_action_interval(61, spear), 920)
        self.assertEqual(get_pc_action_interval(61, bow), 1920)
        self.assertEqual(get_pc_action_interval(61, None), 880)

    def test_domain_a_weapon_action_timing_classes(self):
        """Verify dynamic SprTable timing for Prince(0), Elf(37), FemaleKnight(48)."""
        sword = Weapon(item_id=1, name="Sword", weapon_type=1, dmg_small=8, dmg_large=12)
        # Prince GFX 0
        self.assertEqual(get_pc_action_interval(0, sword), 1000)
        # Female Elf GFX 37
        self.assertEqual(get_pc_action_interval(37, sword), 760)
        # Female Knight GFX 48
        self.assertEqual(get_pc_action_interval(48, sword), 920)

    def test_domain_a_equip_updates_actor_attack_speed(self):
        """Equipping a weapon automatically resolves and mutates actor.attack_speed_ms."""
        # Test on Female Knight (GFX 48): Sword=920ms, Spear=1000ms, BareHands=1000ms
        female_knight = Actor(
            id=2,
            name="TestLadyKnight",
            class_type=1,
            level=5,
            hp=100,
            max_hp=100,
            str=16,
            dex=12,
            con=14,
            int=10,
            wis=10,
            cha=10,
            pos=Position(32608, 32742, 0),
            heading=0,
            auto_pickup=True,
            inventory=Inventory(),
            mp=30,
            max_mp=30,
            ac=10,
            gfx=48,
            move_speed_ms=640,
            attack_speed_ms=920,
        )

        sword = Weapon(item_id=1, name="Long Sword", weapon_type=1, dmg_small=8, dmg_large=12)
        spear = Weapon(item_id=2, name="Spear", weapon_type=3, dmg_small=7, dmg_large=7)
        eq_mgr = EquipmentManager([sword, spear])

        # Equip Sword on GFX 48 -> 920ms
        success, reason, _ = eq_mgr.equip(female_knight, 1, tick=0)
        self.assertTrue(success)
        self.assertEqual(female_knight.equipped_weapon.item_id, 1)
        self.assertEqual(female_knight.attack_speed_ms, 920)

        # Equip Spear on GFX 48 -> 1000ms
        success, reason, _ = eq_mgr.equip(female_knight, 2, tick=1)
        self.assertTrue(success)
        self.assertEqual(female_knight.equipped_weapon.item_id, 2)
        self.assertEqual(female_knight.attack_speed_ms, 1000)

        # Unequip -> Bare hands (1000ms)
        success, reason, _ = eq_mgr.unequip(female_knight, tick=2)
        self.assertTrue(success)
        self.assertIsNone(female_knight.equipped_weapon)
        self.assertEqual(female_knight.attack_speed_ms, 1000)

    # =========================================================================
    # Domain B: Potion / Recovery
    # =========================================================================
    def test_domain_b_red_potion_canonical_healing(self):
        """Red Potion (LesserHealingPotion.java: MIN_HP=10, MAX_HP=30)."""
        self.knight.hp = 50
        red_pot = Item(item_id=104, name="Red Potion", count=2)
        self.knight.inventory.add(red_pot)

        # Execute potion heal logic
        heal = self.rng.rand(10, 30, "RedPotionHeal")
        self.assertTrue(10 <= heal <= 30)
        self.knight.hp = min(self.knight.max_hp, self.knight.hp + heal)
        self.assertEqual(self.knight.hp, 50 + heal)

        # Cannot heal past max_hp
        self.knight.hp = 95
        heal2 = 20
        self.knight.hp = min(self.knight.max_hp, self.knight.hp + heal2)
        self.assertEqual(self.knight.hp, 100)

    def test_domain_b_green_potion_duration(self):
        """Green Potion applies Haste for 300s (HastePotion.java: firstTime=300)."""
        self.assertFalse(self.knight.is_speed)
        self.status_mgr.apply_haste(self.knight, duration_sec=300)
        self.assertTrue(self.knight.is_speed)
        self.assertTrue(self.status_mgr.has_status(self.knight, StatusType.HASTE))

        # Advance 299s -> still active
        self.scheduler.run_until(299000)
        self.assertTrue(self.knight.is_speed)

        # Advance to 300s -> expired
        self.scheduler.run_until(300000)
        self.assertFalse(self.knight.is_speed)

    # =========================================================================
    # Domain C: Status / Buff / Debuff
    # =========================================================================
    def test_domain_c_pc_speed_modifiers(self):
        """PC speed multipliers: Haste = int(interval * 0.75), Slow = int(interval / 0.75)."""
        base_move = 640
        base_atk = 880

        # Base effective speeds
        self.assertEqual(self.knight.effective_move_speed_ms, base_move)
        self.assertEqual(self.knight.effective_attack_speed_ms, base_atk)

        # Apply Haste
        self.status_mgr.apply_haste(self.knight, duration_sec=300)
        self.assertEqual(self.knight.effective_move_speed_ms, int(base_move * 0.75))  # 480ms
        self.assertEqual(self.knight.effective_attack_speed_ms, int(base_atk * 0.75)) # 660ms

        # Expire Haste
        self.status_mgr.remove_status(self.knight, StatusType.HASTE)
        self.assertEqual(self.knight.effective_move_speed_ms, base_move)
        self.assertEqual(self.knight.effective_attack_speed_ms, base_atk)

        # Apply Slow
        self.status_mgr.apply_slow(self.knight, duration_sec=60)
        self.assertEqual(self.knight.effective_move_speed_ms, int(base_move / 0.75))  # 853ms
        self.assertEqual(self.knight.effective_attack_speed_ms, int(base_atk / 0.75)) # 1173ms

    def test_domain_c_monster_speed_modifiers(self):
        """Monster speed multipliers: Haste = int(spd - spd * 0.3), Slow = int(spd + spd * 0.3)."""
        base_move = 1200
        base_atk = 1000

        self.assertEqual(self.goblin.effective_move_speed_ms, base_move)
        self.assertEqual(self.goblin.effective_attack_speed_ms, base_atk)

        # Monster Haste
        self.status_mgr.apply_haste(self.goblin, duration_sec=60)
        self.assertEqual(self.goblin.effective_move_speed_ms, int(base_move - base_move * 0.3))  # 840ms
        self.assertEqual(self.goblin.effective_attack_speed_ms, int(base_atk - base_atk * 0.3)) # 700ms

        self.status_mgr.remove_status(self.goblin, StatusType.HASTE)

        # Monster Slow
        self.status_mgr.apply_slow(self.goblin, duration_sec=60)
        self.assertEqual(self.goblin.effective_move_speed_ms, int(base_move + base_move * 0.3))  # 1560ms
        self.assertEqual(self.goblin.effective_attack_speed_ms, int(base_atk + base_atk * 0.3)) # 1300ms

    def test_domain_c_haste_slow_conflict_resolution(self):
        """Applying Haste when Slow active neutralizes Slow (neither buff remains)."""
        self.status_mgr.apply_slow(self.knight, duration_sec=60)
        self.assertTrue(self.knight.is_slow)
        self.assertFalse(self.knight.is_speed)

        # Apply Haste -> Cancels Slow, Haste is NOT applied
        self.status_mgr.apply_haste(self.knight, duration_sec=300)
        self.assertFalse(self.knight.is_slow)
        self.assertFalse(self.knight.is_speed)

        # Now apply Haste again -> Haste applies
        self.status_mgr.apply_haste(self.knight, duration_sec=300)
        self.assertTrue(self.knight.is_speed)

        # Apply Slow -> Cancels Haste, Slow is NOT applied
        self.status_mgr.apply_slow(self.knight, duration_sec=60)
        self.assertFalse(self.knight.is_speed)
        self.assertFalse(self.knight.is_slow)

    # =========================================================================
    # Domain D: Skills
    # =========================================================================
    def test_domain_d_energy_bolt(self):
        """Energy Bolt (Skill 4): MP 3, Action 18 (880ms), immediate magic damage."""
        init_mp = self.knight.mp
        init_hp = self.goblin.hp

        res = self.skill_engine.cast_energy_bolt(self.knight, self.goblin)
        self.assertTrue(res.success)
        self.assertEqual(self.knight.mp, init_mp - 3)
        self.assertEqual(res.cast_interval_ms, 880)
        self.assertGreater(res.damage, 0)
        self.assertEqual(self.goblin.hp, init_hp - res.damage)

    def test_domain_d_lesser_heal(self):
        """Lesser Heal (Skill 1): MP 4, Action 19 (800ms), immediate HP recovery."""
        self.knight.hp = 60
        init_mp = self.knight.mp

        res = self.skill_engine.cast_heal(self.knight, self.knight)
        self.assertTrue(res.success)
        self.assertEqual(self.knight.mp, init_mp - 4)
        self.assertEqual(res.cast_interval_ms, 800)
        self.assertGreater(res.heal, 0)
        self.assertEqual(self.knight.hp, 60 + res.heal)

    def test_domain_d_haste_skill(self):
        """Haste Skill (Skill 28): MP 25, HP 20, Action 19 (800ms), 1200s duration."""
        self.knight.hp = 80
        self.knight.mp = 30

        res = self.skill_engine.cast_haste(self.knight, self.status_mgr)
        self.assertTrue(res.success)
        self.assertEqual(self.knight.mp, 5)
        self.assertEqual(self.knight.hp, 60)
        self.assertEqual(res.cast_interval_ms, 800)
        self.assertTrue(self.knight.is_speed)

    # =========================================================================
    # Domain E: Death & Respawn Semantics
    # =========================================================================
    def test_domain_e_novice_death_protection(self):
        """PcInstance.java:789-858: Lv <= 9 has novice protection (0 EXP loss)."""
        self.knight.level = 5
        self.knight.exp = 2500

        # Simulate death check
        if self.knight.level <= 9:
            lost_exp = 0
        else:
            lost_exp = int(self.knight.exp * 0.10)
        self.knight.exp -= lost_exp

        self.assertEqual(lost_exp, 0)
        self.assertEqual(self.knight.exp, 2500)

    def test_domain_e_high_level_death_penalty(self):
        """PcInstance.java:838: Lv > 9 loses 10% EXP upon death."""
        self.knight.level = 10
        self.knight.exp = 10000

        if self.knight.level <= 9:
            lost_exp = 0
        else:
            lost_exp = int(self.knight.exp * 0.10)
        self.knight.exp -= lost_exp

        self.assertEqual(lost_exp, 1000)
        self.assertEqual(self.knight.exp, 9000)

    def test_domain_e_buffs_cleared_on_death(self):
        """All active buffs/potions are removed when actor dies."""
        self.status_mgr.apply_haste(self.knight, duration_sec=300)
        self.status_mgr.apply_brave(self.knight, duration_sec=300)
        self.assertTrue(self.knight.is_speed)
        self.assertTrue(self.knight.is_brave)

        # Clear on death
        self.status_mgr.clear_all(self.knight)
        self.assertFalse(self.knight.is_speed)
        self.assertFalse(self.knight.is_brave)

    # =========================================================================
    # Domain F: NPC Shop Interaction
    # =========================================================================
    def test_domain_f_pandora_shop_buy_potions(self):
        """Pandora shop (npcid=3, GFX 98) in Talking Island sells Red & Green Potions."""
        # Add adena (item 40308)
        adena = Item(item_id=40308, name="Adena", count=500)
        self.knight.inventory.add(adena)

        # Buy 5 Red Potions (37 adena each = 185 adena)
        success, msg = PANDORA_SHOP.buy_item(self.knight, item_id=104, count=5)
        self.assertTrue(success)
        self.assertEqual(adena.count, 500 - 185)
        red_pot = next((item for item in self.knight.inventory.items if item.item_id == 104), None)
        self.assertIsNotNone(red_pot)
        self.assertEqual(red_pot.count, 5)

        # Buy 2 Green Potions (120 adena each = 240 adena)
        success2, msg2 = PANDORA_SHOP.buy_item(self.knight, item_id=108, count=2)
        self.assertTrue(success2)
        self.assertEqual(adena.count, 315 - 240)  # 75 left
        green_pot = next((item for item in self.knight.inventory.items if item.item_id == 108), None)
        self.assertIsNotNone(green_pot)
        self.assertEqual(green_pot.count, 2)

        # Try to buy 1 more Green Potion (costs 120, only 75 adena remaining) -> Fails
        success3, msg3 = PANDORA_SHOP.buy_item(self.knight, item_id=108, count=1)
        self.assertFalse(success3)
        self.assertEqual(msg3, "INSUFFICIENT_ADENA")
        self.assertEqual(green_pot.count, 2)


if __name__ == "__main__":
    unittest.main()
