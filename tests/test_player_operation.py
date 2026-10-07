"""
tests/test_player_operation.py - Test Suite for Player Operation Layer & Architecture Equivalence

Architecture:
  - Layer 1: Legacy Evidence (182c)
  - Layer 2: Native L1J World
  - Layer 3: Player Operation (Action Model)
  - Layer 4: Configurable Automation (Hunting Helper)

Verifies:
  1. Discrete Player Operations in isolation (MOVE_STEP, SELECT_TARGET, ATTACK, USE_ITEM, LOOT, EQUIP, UNEQUIP, BUY_SUPPLY).
  2. Automation Rule emission (Conditions -> PlayerOperation).
  3. ARCHITECTURE EQUIVALENCE TEST (Section 46):
     Proves that Manual Player Operations and Automation-Generated Player Operations
     execute through the EXACT same Player Operation execution pipeline and produce
     identical world transitions.
"""
import unittest
from mvp import initialize_s007_session
from native_engine.bot import (
    HeadlessBot,
    BotPolicy,
    BotState,
    PerceptionSystem,
    PerceptionSnapshot,
    AutonomousConfig,
    PotionRule,
    PotionThresholdMode,
    EmergencyCondition,
    EmergencyConditionType,
    EmergencyOperator,
    EmergencyAction,
    EmergencyActionRule,
    ReturnTrigger,
    ReturnTriggerType,
    ReturnToTownPolicy,
    ResupplyItem,
    ResupplyProfile,
)
from native_engine.player_operation import PlayerOperationType, PlayerOperation
from native_engine.model import Actor, Inventory, Item, Position, Weapon
from native_engine.npc import PANDORA_SHOP
from native_engine.temporal import VirtualClock, Scheduler
from native_engine.bot.drop import GroundDrop


class TestPlayerOperations(unittest.TestCase):
    """
    Test individual Player Operations executing directly on Native World (Layer 3 -> Layer 2).
    """
    def setUp(self):
        self.session = initialize_s007_session(seed_override=42)
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.player = Actor(
            id=10001,
            name="Arthur",
            class_type=1,
            level=1,
            hp=100,
            max_hp=100,
            str=16,
            dex=12,
            con=14,
            int=8,
            wis=9,
            cha=12,
            pos=Position(32671, 32804, 1),
            heading=0,
            auto_pickup=True,
            inventory=Inventory(items=[]),
            equipped_weapon=Weapon(
                item_id=2,
                name="Short Sword",
                weapon_type=1,
                dmg_small=8,
                dmg_large=8,
            ),
        )
        self.bot = HeadlessBot(
            player=self.player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            rng=self.session.population.rng,
            provide_starter_supplies=False,
        )

    def test_op_select_target(self):
        monster = self.session.population.get_all_alive_on_map(1)[0]
        self.assertIsNone(self.player.current_target)

        op = PlayerOperation(PlayerOperationType.SELECT_TARGET, target=monster)
        self.bot.execute_player_operation(op)

        self.assertEqual(self.player.current_target, monster)
        self.assertEqual(self.bot.active_target, monster)

    def test_op_attack_selected_target(self):
        monster = self.session.population.get_all_alive_on_map(1)[0]
        # Place player adjacent to monster
        self.player.x = monster.x + 1
        self.player.y = monster.y
        initial_hp = monster.hp

        # Select target first
        self.bot.execute_player_operation(PlayerOperation(PlayerOperationType.SELECT_TARGET, target=monster))
        self.assertEqual(self.player.current_target, monster)

        # Attack selected target
        op = PlayerOperation(PlayerOperationType.ATTACK)
        self.bot.execute_player_operation(op)

        # Immediate damage resolved
        self.assertLess(monster.hp, initial_hp)
        self.assertGreater(self.bot.total_damage_dealt, 0)

    def test_op_use_item_potion(self):
        potion = Item(item_id=104, name="Red Potion", count=5)
        self.player.inventory.add(potion)
        self.player.hp = 50

        op = PlayerOperation(PlayerOperationType.USE_ITEM, item_id=104)
        self.bot.execute_player_operation(op)

        self.assertGreater(self.player.hp, 50)
        self.assertEqual(potion.count, 4)
        self.assertEqual(self.bot.potions_consumed, 1)

    def test_op_use_item_escape_scroll(self):
        scroll = Item(item_id=139, name="Escape Scroll", count=2)
        self.player.inventory.add(scroll)
        self.player.pos.map_id = 1
        self.player.pos.x = 32671
        self.player.pos.y = 32804

        op = PlayerOperation(PlayerOperationType.USE_ITEM, item_id=139)
        self.bot.execute_player_operation(op)

        self.assertEqual(self.player.map_id, 0)
        self.assertEqual(self.player.x, 32599)
        self.assertEqual(self.player.y, 32931)
        self.assertEqual(scroll.count, 1)
        self.assertEqual(self.bot.town_visits, 1)

    def test_op_use_item_unusable_item_preserves_count_and_hp(self):
        """
        Legacy L1J Invariant: ItemInstance.java:182-184
        Clicking an unhandled item (e.g. Adena 40308, materials) emits S_ServerMessage(74)
        ('沒有任何事情發生'). It MUST NOT deduct item count and MUST NOT mutate player HP.
        """
        adena = Item(item_id=40308, name="Adena", count=1000)
        self.player.inventory.add(adena)
        self.player.hp = 50
        initial_potions_consumed = self.bot.potions_consumed

        op = PlayerOperation(PlayerOperationType.USE_ITEM, item_id=40308)
        self.bot.execute_player_operation(op)

        self.assertEqual(self.player.hp, 50, "Unusable item must not heal HP")
        self.assertEqual(adena.count, 1000, "Unusable item count must remain unchanged")
        self.assertEqual(self.bot.potions_consumed, initial_potions_consumed)
        self.assertTrue(any("Message 74" in log or "no active function" in log for log in self.bot.trace_log))


    def test_op_loot_ground_drop(self):
        drop_pos = Position(self.player.x, self.player.y, self.player.map_id)
        adena = Item(item_id=40308, name="Adena", count=500)
        drop = GroundDrop(item=adena, pos=drop_pos, dropped_at_tick=0, monster_name="Werewolf")
        self.bot.drop_system.ground_drops.append(drop)

        op = PlayerOperation(PlayerOperationType.LOOT, target=drop)
        self.bot.execute_player_operation(op)

        # Drop collected into player inventory
        inv_item = next((i for i in self.player.inventory.items if i.item_id == 40308), None)
        self.assertIsNotNone(inv_item)
        self.assertEqual(inv_item.count, 500)
        self.assertEqual(self.bot.adena_earned, 500)
        self.assertNotIn(drop, self.bot.drop_system.ground_drops)

    def test_op_equip_unequip(self):
        sword = Weapon(item_id=2, name="Short Sword", weapon_type=1, dmg_small=8, dmg_large=8)
        self.bot.execute_player_operation(PlayerOperation(PlayerOperationType.UNEQUIP, target=sword))
        self.assertIsNone(self.player.equipped_weapon)

        self.bot.execute_player_operation(PlayerOperation(PlayerOperationType.EQUIP, target=sword))
        self.assertEqual(self.player.equipped_weapon, sword)

    def test_op_buy_supply(self):
        # Position player at Pandora's shop (map 0, 32644, 32955)
        self.player.map_id = 0
        self.player.x = 32644
        self.player.y = 32955
        self.player.inventory.add(Item(item_id=40308, name="Adena", count=1000))

        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=10, priority=100)]
            )
        )
        self.bot.policy.config = config

        op = PlayerOperation(PlayerOperationType.BUY_SUPPLY, target=PANDORA_SHOP.pos)
        self.bot.execute_player_operation(op)

        potions = next((i for i in self.player.inventory.items if i.item_id == 104), None)
        self.assertIsNotNone(potions)
        self.assertEqual(potions.count, 10)
        self.assertEqual(self.bot.adena_spent, 370)  # 10 * 37


class TestAutomationRuleEmission(unittest.TestCase):
    """
    Test that Configurable Automation Rules emit appropriate Player Operations (Layer 4 -> Layer 3).
    """
    def _create_snapshot(self, hp=100, max_hp=100, mp=10, max_mp=10, items=None, nearby_monsters=None, target_monster=None, in_melee=False):
        inv = Inventory(items=items or [])
        return PerceptionSnapshot(
            player_id=10001,
            name="Arthur",
            level=1,
            hp=hp,
            max_hp=max_hp,
            mp=mp,
            max_mp=max_mp,
            pos=Position(32671, 32804, 1),
            is_dead=False,
            combat_state="IDLE",
            equipped_weapon=None,
            inventory=inv,
            nearby_monsters=nearby_monsters or [],
            nearby_drops=[],
            target_monster=target_monster,
            target_distance=1 if in_melee else 5,
            is_target_in_melee=in_melee,
        )

    def test_low_hp_emits_use_item(self):
        config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=60.0, item="Red Potion", item_id=104, priority=100)
            ]
        )
        policy = BotPolicy(config=config)
        items = [Item(item_id=104, name="Red Potion", count=10)]
        snap = self._create_snapshot(hp=40, max_hp=100, items=items)

        state, op = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertEqual(op.action_type, PlayerOperationType.USE_ITEM)
        self.assertEqual(op.target.item_id, 104)

    def test_new_target_emits_select_target(self):
        policy = BotPolicy(config=AutonomousConfig())
        monster = Actor(id=20001, name="Werewolf", class_type=0, level=3, hp=50, max_hp=50, str=10, dex=10, con=10, int=10, wis=10, cha=10, pos=Position(32672, 32804, 1), heading=0, auto_pickup=False, inventory=Inventory())
        snap = self._create_snapshot(nearby_monsters=[monster], target_monster=None)

        state, op = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertEqual(op.action_type, PlayerOperationType.SELECT_TARGET)
        self.assertEqual(op.target, monster)

    def test_selected_target_in_melee_emits_attack(self):
        policy = BotPolicy(config=AutonomousConfig())
        monster = Actor(id=20001, name="Werewolf", class_type=0, level=3, hp=50, max_hp=50, str=10, dex=10, con=10, int=10, wis=10, cha=10, pos=Position(32672, 32804, 1), heading=0, auto_pickup=False, inventory=Inventory())
        # Target already selected, in melee range, MP depleted -> emits physical ATTACK
        snap = self._create_snapshot(target_monster=monster, in_melee=True, mp=0)

        state, op = policy.decide_next_action(BotState.MOVE_TO_TARGET, snap)
        self.assertEqual(op.action_type, PlayerOperationType.ATTACK)
        self.assertEqual(op.target, monster)


class TestArchitectureSameExecutionPath(unittest.TestCase):
    """
    CRITICAL ARCHITECTURAL TEST (Section 46):
    Proves that Manual Player Operations and Automation-Generated Player Operations
    route through the EXACT same execute_player_operation pipeline and produce
    indistinguishable world state transitions.
    """
    def setUp(self):
        self.session_manual = initialize_s007_session(seed_override=99999)
        self.session_auto = initialize_s007_session(seed_override=99999)

        self.clock_manual = VirtualClock(0)
        self.scheduler_manual = Scheduler(self.clock_manual)
        self.player_manual = Actor(
            id=10001, name="Arthur", class_type=1, level=10, hp=100, max_hp=100, mp=0, max_mp=10,
            str=16, dex=12, con=14, int=8, wis=9, cha=12, pos=Position(32671, 32804, 1),
            heading=0, auto_pickup=True, inventory=Inventory(items=[]),
            equipped_weapon=Weapon(item_id=2, name="Short Sword", weapon_type=1, dmg_small=8, dmg_large=8),
        )
        self.bot_manual = HeadlessBot(
            player=self.player_manual,
            world_maps=self.session_manual.world.maps,
            population=self.session_manual.population,
            progression=self.session_manual.progression,
            clock=self.clock_manual,
            scheduler=self.scheduler_manual,
            rng=self.session_manual.population.rng,
            provide_starter_supplies=False,
        )

        self.clock_auto = VirtualClock(0)
        self.scheduler_auto = Scheduler(self.clock_auto)
        self.player_auto = Actor(
            id=10001, name="Arthur", class_type=1, level=10, hp=100, max_hp=100, mp=0, max_mp=10,
            str=16, dex=12, con=14, int=8, wis=9, cha=12, pos=Position(32671, 32804, 1),
            heading=0, auto_pickup=True, inventory=Inventory(items=[]),
            equipped_weapon=Weapon(item_id=2, name="Short Sword", weapon_type=1, dmg_small=8, dmg_large=8),
        )
        self.bot_auto = HeadlessBot(
            player=self.player_auto,
            world_maps=self.session_auto.world.maps,
            population=self.session_auto.population,
            progression=self.session_auto.progression,
            clock=self.clock_auto,
            scheduler=self.scheduler_auto,
            rng=self.session_auto.population.rng,
            provide_starter_supplies=False,
        )

    def test_manual_vs_automation_path_equivalence(self):
        # 1. Spawn identical monster in both sessions
        m_manual = self.session_manual.population.get_all_alive_on_map(1)[0]
        m_auto = self.session_auto.population.get_all_alive_on_map(1)[0]
        self.assertEqual(m_manual.id, m_auto.id)
        self.assertEqual(m_manual.hp, m_auto.hp)

        # Place player 1 tile away
        self.player_manual.x = m_manual.x + 1
        self.player_manual.y = m_manual.y
        self.player_auto.x = m_auto.x + 1
        self.player_auto.y = m_auto.y

        # Path A: Manual Player Command
        manual_select_op = PlayerOperation(PlayerOperationType.SELECT_TARGET, target=m_manual)
        self.bot_manual.execute_player_operation(manual_select_op)

        manual_attack_op = PlayerOperation(PlayerOperationType.ATTACK, target=m_manual)
        self.bot_manual.execute_player_operation(manual_attack_op)

        # Path B: Automation Configured Policy (Perceive -> Policy -> PlayerOperation)
        snap = self.bot_auto.perception_sys.perceive(
            player=self.player_auto,
            population=self.session_auto.population,
            ground_drops=self.bot_auto.drop_system.ground_drops,
            active_target=None
        )
        _, auto_select_op = self.bot_auto.policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertEqual(auto_select_op.action_type, PlayerOperationType.SELECT_TARGET)
        self.bot_auto.execute_player_operation(auto_select_op)

        snap2 = self.bot_auto.perception_sys.perceive(
            player=self.player_auto,
            population=self.session_auto.population,
            ground_drops=self.bot_auto.drop_system.ground_drops,
            active_target=self.bot_auto.active_target
        )
        _, auto_attack_op = self.bot_auto.policy.decide_next_action(BotState.MOVE_TO_TARGET, snap2)
        self.assertEqual(auto_attack_op.action_type, PlayerOperationType.ATTACK)
        self.bot_auto.execute_player_operation(auto_attack_op)

        # Assert Equivalence:
        # Both manual and automation operations produced identical monster HP, damage dealt, and player state!
        self.assertEqual(m_manual.hp, m_auto.hp)
        self.assertEqual(self.bot_manual.total_damage_dealt, self.bot_auto.total_damage_dealt)
        self.assertEqual(self.player_manual.x, self.player_auto.x)
        self.assertEqual(self.player_manual.y, self.player_auto.y)
        self.assertEqual(self.player_manual.current_target.id, self.player_auto.current_target.id)

    def test_manual_movement_respects_action_cadence(self):
        """
        Verifies that manual movement respects _player_busy_until.
        Spamming multiple manual operations within the move interval cannot bypass cooldown.
        """
        from native_engine.temporal import RealTimeClock
        rt_clock = RealTimeClock(initial_time_ms=0, time_scale=1.0)
        self.bot_manual.clock = rt_clock
        self.bot_manual.scheduler.clock = rt_clock
        self.bot_manual._player_busy_until = 0

        self.bot_manual.pause_helper()
        self.assertTrue(self.bot_manual.helper_paused)

        init_x = self.player_manual.x
        init_y = self.player_manual.y

        # Issue 1st manual move step (Heading 0: North)
        op1 = PlayerOperation(
            PlayerOperationType.MOVE_STEP,
            target=Position(init_x, init_y - 1, map_id=self.player_manual.map_id)
        )
        self.bot_manual.enqueue_manual_operation(op1)

        # 1st move executed immediately because player was idle
        self.assertEqual(self.player_manual.y, init_y - 1)
        self.assertEqual(self.bot_manual._player_busy_until, self.player_manual.effective_move_speed_ms)

        # Issue 2nd manual move step while player is still busy walking (at t=0, busy until 640)
        op2 = PlayerOperation(
            PlayerOperationType.MOVE_STEP,
            target=Position(init_x, init_y - 2, map_id=self.player_manual.map_id)
        )
        self.bot_manual.enqueue_manual_operation(op2)

        # 2nd move MUST NOT execute immediately (still at init_y - 1, queued in manual_queue)
        self.assertEqual(self.player_manual.y, init_y - 1)
        self.assertEqual(len(self.bot_manual.manual_queue), 1)

        # Advance real-time clock and scheduler to completion of 1st move interval (640ms)
        rt_clock._logical_start = self.player_manual.effective_move_speed_ms
        self.scheduler_manual.run_until(self.player_manual.effective_move_speed_ms)

        # Now 2nd move is popped and executed by scheduled gate
        self.assertEqual(self.player_manual.y, init_y - 2)
        self.assertEqual(len(self.bot_manual.manual_queue), 0)
        self.assertEqual(self.bot_manual._player_busy_until, self.player_manual.effective_move_speed_ms * 2)

    def test_equip_weapon_updates_attack_speed_dynamically(self):
        """
        Equipping and unequipping weapon dynamically recalculates player attack_speed_ms.
        """
        # Female Knight (GFX 48): BareHands=1000ms, Long Sword (type 1)=920ms, Bow=1840ms
        self.player_manual.gfx = 48
        self.player_manual.attack_speed_ms = 1000
        sword = Weapon(item_id=1, name="Long Sword", weapon_type=1, dmg_small=8, dmg_large=12)

        equip_op = PlayerOperation(PlayerOperationType.EQUIP, target=sword)
        self.bot_manual.execute_player_operation(equip_op)

        self.assertEqual(self.player_manual.equipped_weapon.item_id, 1)
        self.assertEqual(self.player_manual.attack_speed_ms, 920)

        # Unequip -> returns to bare-hands cadence (1000ms)
        unequip_op = PlayerOperation(PlayerOperationType.UNEQUIP, target=sword)
        self.bot_manual.execute_player_operation(unequip_op)

        self.assertIsNone(self.player_manual.equipped_weapon)
        self.assertEqual(self.player_manual.attack_speed_ms, 1000)

    def test_polymorph_spr_table_speed_resolution(self):
        """
        Verifies SprTable resolves move speed for polymorph/monster GFX (Golem, Zombie, Werewolf).
        """
        from native_engine.spr_action import SprTable
        spr = SprTable.get_instance()
        # Stone Golem GFX 49 -> 1280ms
        self.assertEqual(spr.get_move_speed(49), 1280)
        # Zombie GFX 52 -> 1640ms
        self.assertEqual(spr.get_move_speed(52), 1640)
        # Werewolf GFX 54 -> 560ms
        self.assertEqual(spr.get_move_speed(54), 560)
        # Skeleton GFX 30 -> 640ms
        self.assertEqual(spr.get_move_speed(30), 640)

    def test_brave_potion_and_elven_wafer_class_restrictions(self):
        """
        Legacy L1J Archaeology:
          - PotionofBravery.java:30: Only Knight (class_type == 1) can use Bravery Potion.
          - ElvenWafer.java:29: Only Elf (class_type == 2) can use Elven Wafer.
          - Ineligible classes get Message 79 (no buff applied).
        """
        brave_item = Item(item_id=110, count=1, name="Bravery Potion")
        wafer_item = Item(item_id=56, count=1, name="Elven Wafer")

        # 1. Knight (class_type = 1) using Bravery Potion -> SUCCESS
        self.player_manual.class_type = 1
        self.player_manual.inventory.add(brave_item)
        op_knight_brave = PlayerOperation(PlayerOperationType.USE_ITEM, target=brave_item)
        self.bot_manual.execute_player_operation(op_knight_brave)
        self.assertTrue(self.player_manual.is_brave)
        self.assertEqual(self.player_manual.effective_move_speed_ms, int(640 * 0.75))

        # Reset brave status
        self.bot_manual.status_mgr.remove_status(self.player_manual, "BRAVE")
        self.assertFalse(self.player_manual.is_brave)

        # 2. Knight using Elven Wafer -> FAIL (Message 79)
        self.player_manual.inventory.add(wafer_item)
        op_knight_wafer = PlayerOperation(PlayerOperationType.USE_ITEM, target=wafer_item)
        self.bot_manual.execute_player_operation(op_knight_wafer)
        self.assertFalse(self.player_manual.is_brave)

        # 3. Elf (class_type = 2) using Bravery Potion -> FAIL (Message 79)
        self.player_manual.class_type = 2
        self.player_manual.inventory.add(brave_item)
        op_elf_brave = PlayerOperation(PlayerOperationType.USE_ITEM, target=brave_item)
        self.bot_manual.execute_player_operation(op_elf_brave)
        self.assertFalse(self.player_manual.is_brave)

        # 4. Elf using Elven Wafer -> SUCCESS
        wafer_elf = Item(item_id=56, count=1, name="Elven Wafer")
        self.player_manual.inventory.add(wafer_elf)
        op_elf_wafer = PlayerOperation(PlayerOperationType.USE_ITEM, target=wafer_elf)
        self.bot_manual.execute_player_operation(op_elf_wafer)
        self.assertTrue(self.player_manual.is_brave)
        self.assertEqual(self.player_manual.effective_move_speed_ms, int(640 * 0.75))


if __name__ == "__main__":
    unittest.main()
