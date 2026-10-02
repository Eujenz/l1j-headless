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


if __name__ == "__main__":
    unittest.main()
