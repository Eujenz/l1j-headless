"""
tests/test_autonomous_policy.py - Test Suite for Player-Configurable Autonomous Policy

Verifies:
  - Potion rules evaluation (Absolute HP vs HP percent, priorities, disabled, fallbacks).
  - Emergency action triggers and executions.
  - Town resupply logic (calculating target difference, partial funds, multiple items).
  - Town navigation and Pandora NPC proximity checks.
  - Autonomous closed loop: Hunt -> Low Supply -> Return Town -> Resupply -> Dungeon Re-entry -> Resume Hunt.
  - JSON configuration persistence and behavioral variance without code changes.
"""
import copy
import json
import unittest

from mvp import initialize_s007_session
from native_engine.bot import (
    HeadlessBot,
    BotPolicy,
    BotState,
    BotActionType,
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
    ReturnMethod,
    ReturnToTownPolicy,
    ResupplyItem,
    ResupplyProfile,
    HuntingDestination,
    HuntingPolicy,
)
from native_engine.model import Actor, Inventory, Item, Position
from native_engine.npc import PANDORA_SHOP, NpcShop
from native_engine.temporal import VirtualClock, Scheduler


class TestAutonomousPolicy(unittest.TestCase):
    def setUp(self):
        self.session = initialize_s007_session(seed_override=777777)
        self.clock = VirtualClock(0)
        self.scheduler = Scheduler(self.clock)
        self.config = AutonomousConfig()

    def _create_actor(self, x=32644, y=32955, map_id=0, hp=100, max_hp=100):
        return Actor(
            id=10001,
            name="Arthur",
            class_type=1,
            level=1,
            hp=hp,
            max_hp=max_hp,
            str=16,
            dex=12,
            con=14,
            int=8,
            wis=9,
            cha=12,
            pos=Position(x, y, map_id),
            heading=0,
            auto_pickup=True,
            inventory=Inventory(),
        )

    def _create_snapshot(self, hp=100, max_hp=100, mp=50, max_mp=50, map_id=1, x=32671, y=32804, items=None, is_speed=True):
        inv = Inventory()
        if items:
            for it in items:
                inv.add(it)
        return PerceptionSnapshot(
            player_id=10001,
            name="Arthur",
            level=1,
            hp=hp,
            max_hp=max_hp,
            mp=mp,
            max_mp=max_mp,
            pos=Position(x, y, map_id),
            is_dead=False,
            combat_state="IDLE",
            equipped_weapon=None,
            inventory=inv,
            nearby_monsters=[],
            nearby_drops=[],
            target_monster=None,
            target_distance=None,
            is_target_in_melee=False,
            is_speed=is_speed,
        )

    # -------------------------------------------------------------------------
    # 1. Potion Rules Tests
    # -------------------------------------------------------------------------
    def test_potion_rule_absolute_hp(self):
        config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.ABSOLUTE_HP, threshold=40.0, item="Red Potion", item_id=104, priority=100)
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)

        # HP = 50 (> 40) -> Should NOT drink
        items = [Item(item_id=104, name="Red Potion", count=10)]
        snap_safe = self._create_snapshot(hp=50, max_hp=100, items=items)
        state, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap_safe)
        self.assertNotEqual(action.action_type, BotActionType.USE_POTION)

        # HP = 40 (<= 40) -> Should drink Red Potion
        snap_trigger = self._create_snapshot(hp=40, max_hp=100, items=items)
        state, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap_trigger)
        self.assertEqual(action.action_type, BotActionType.USE_POTION)
        self.assertEqual(action.target.item_id, 104)

    def test_potion_rule_hp_percent(self):
        config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=35.0, item="Red Potion", item_id=104, priority=100)
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)

        items = [Item(item_id=104, name="Red Potion", count=10)]
        # Max HP 200, HP 80 = 40% -> Not triggered
        snap_safe = self._create_snapshot(hp=80, max_hp=200, items=items)
        _, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap_safe)
        self.assertNotEqual(action.action_type, BotActionType.USE_POTION)

        # Max HP 200, HP 70 = 35% -> Triggered
        snap_trigger = self._create_snapshot(hp=70, max_hp=200, items=items)
        _, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap_trigger)
        self.assertEqual(action.action_type, BotActionType.USE_POTION)
        self.assertEqual(action.target.item_id, 104)

    def test_multiple_potion_rule_priority(self):
        # Priority 200 (Orange at 20%) should take precedence over Priority 100 (Red at 50%) when HP <= 20%
        config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=50.0, item="Red Potion", item_id=104, priority=100),
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=20.0, item="Orange Potion", item_id=103, priority=200),
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)
        items = [
            Item(item_id=104, name="Red Potion", count=10),
            Item(item_id=103, name="Orange Potion", count=5),
        ]

        # HP 30% -> Orange Potion (threshold 20%) not met, Red Potion (threshold 50%) met
        snap_mid = self._create_snapshot(hp=30, max_hp=100, items=items)
        _, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap_mid)
        self.assertEqual(action.action_type, BotActionType.USE_POTION)
        self.assertEqual(action.target.item_id, 104)

        # HP 18% -> Orange Potion rule evaluated first (priority 200) and triggered!
        snap_low = self._create_snapshot(hp=18, max_hp=100, items=items)
        _, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap_low)
        self.assertEqual(action.action_type, BotActionType.USE_POTION)
        self.assertEqual(action.target.item_id, 103)

    def test_disabled_potion_rule(self):
        config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=False, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=50.0, item="Red Potion", item_id=104, priority=100),
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)
        items = [Item(item_id=104, name="Red Potion", count=10)]
        snap = self._create_snapshot(hp=20, max_hp=100, items=items)
        _, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertNotEqual(action.action_type, BotActionType.USE_POTION)

    def test_missing_potion_fallback(self):
        # Configured for Red Potion, but inventory has 0 Red Potions; has MP -> falls back to Lesser Heal
        config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=40.0, item="Red Potion", item_id=104, priority=100),
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)
        snap = self._create_snapshot(hp=30, max_hp=100, mp=10, items=[])
        _, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertEqual(action.action_type, BotActionType.CAST_SKILL)
        self.assertEqual(action.skill_id, 1)  # Lesser Heal

    # -------------------------------------------------------------------------
    # 2. Emergency Action Tests
    # -------------------------------------------------------------------------
    def test_emergency_escape_trigger(self):
        config = AutonomousConfig(
            emergency_rules=[
                EmergencyActionRule(
                    enabled=True,
                    condition=EmergencyCondition(type=EmergencyConditionType.HP_PERCENT, operator=EmergencyOperator.LE, value=15.0),
                    action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
                    priority=500
                )
            ],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)
        items = [
            Item(item_id=104, name="Red Potion", count=10),
            Item(item_id=139, name="Escape Scroll", count=2),
        ]
        # HP = 12% <= 15% -> Emergency trigger
        snap = self._create_snapshot(hp=12, max_hp=100, items=items)
        state, action = policy.decide_next_action(BotState.ATTACK, snap)
        self.assertEqual(state, BotState.RETURNING_TO_TOWN)
        self.assertEqual(action.action_type, BotActionType.USE_ITEM)
        self.assertEqual(action.target.item_id, 139)

    def test_emergency_rule_not_triggered(self):
        config = AutonomousConfig(
            emergency_rules=[
                EmergencyActionRule(
                    enabled=True,
                    condition=EmergencyCondition(type=EmergencyConditionType.HP_PERCENT, operator=EmergencyOperator.LE, value=10.0),
                    action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
                )
            ]
        )
        policy = BotPolicy(config=config)
        items = [Item(item_id=139, name="Escape Scroll", count=2)]
        snap = self._create_snapshot(hp=20, max_hp=100, items=items)
        state, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertNotEqual(action.action_type, BotActionType.USE_ITEM)

    def test_emergency_item_missing(self):
        # Emergency condition met, but Escape Scroll not in inventory -> does not crash, falls through
        config = AutonomousConfig(
            emergency_rules=[
                EmergencyActionRule(
                    enabled=True,
                    condition=EmergencyCondition(type=EmergencyConditionType.HP_PERCENT, operator=EmergencyOperator.LE, value=15.0),
                    action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
                )
            ],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        policy = BotPolicy(config=config)
        snap = self._create_snapshot(hp=10, max_hp=100, items=[])
        state, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertNotEqual(action.action_type, BotActionType.USE_ITEM)

    # -------------------------------------------------------------------------
    # 3. Resupply Tests
    # -------------------------------------------------------------------------
    def test_resupply_to_target_quantity(self):
        player = self._create_actor(x=32644, y=32955, map_id=0)
        player.inventory.add(Item(item_id=40308, name="Adena", count=5000))
        player.inventory.add(Item(item_id=104, name="Red Potion", count=8))

        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=30)]
            )
        )
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=config,
        )

        bot._execute_buy_supply(PANDORA_SHOP.pos)
        red_count = sum(i.count for i in player.inventory.items if i.item_id == 104)
        self.assertEqual(red_count, 30)  # Bought 30 - 8 = 22 red potions
        # Cost: 22 * 37 = 814 adena
        adena_count = sum(i.count for i in player.inventory.items if i.item_id == 40308)
        self.assertEqual(adena_count, 5000 - 814)
        self.assertEqual(bot.resupply_cycles, 1)

    def test_resupply_noop_when_already_full(self):
        player = self._create_actor(x=32644, y=32955, map_id=0)
        player.inventory.add(Item(item_id=40308, name="Adena", count=5000))
        player.inventory.add(Item(item_id=104, name="Red Potion", count=50))

        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=50)]
            )
        )
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=config,
        )

        bot._execute_buy_supply(PANDORA_SHOP.pos)
        red_count = sum(i.count for i in player.inventory.items if i.item_id == 104)
        self.assertEqual(red_count, 50)
        adena_count = sum(i.count for i in player.inventory.items if i.item_id == 40308)
        self.assertEqual(adena_count, 5000)

    def test_resupply_partial_funds(self):
        # Target 50, current 0, needed 50 (price 37 each = 1850 total), but only 370 adena -> can buy exactly 10
        player = self._create_actor(x=32644, y=32955, map_id=0)
        # Clear inventory
        player.inventory.items.clear()
        player.inventory.add(Item(item_id=40308, name="Adena", count=370))

        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=50)]
            )
        )
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=config,
            provide_starter_supplies=False,
        )

        bot._execute_buy_supply(PANDORA_SHOP.pos)
        red_count = sum(i.count for i in player.inventory.items if i.item_id == 104)
        self.assertEqual(red_count, 10)
        adena_count = sum(i.count for i in player.inventory.items if i.item_id == 40308)
        self.assertEqual(adena_count, 0)
        self.assertIn("PARTIAL_RESUPPLY", "".join(bot.trace_log))

    def test_resupply_multiple_items(self):
        player = self._create_actor(x=32644, y=32955, map_id=0)
        player.inventory.items.clear()
        player.inventory.add(Item(item_id=40308, name="Adena", count=10000))
        player.inventory.add(Item(item_id=104, name="Red Potion", count=5))

        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[
                    ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=30, priority=100),
                    ResupplyItem(enabled=True, item="Green Potion", item_id=108, target_quantity=5, priority=80),
                    ResupplyItem(enabled=True, item="Escape Scroll", item_id=139, target_quantity=3, priority=60),
                ]
            )
        )
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=config,
            provide_starter_supplies=False,
        )

        bot._execute_buy_supply(PANDORA_SHOP.pos)
        self.assertEqual(sum(i.count for i in player.inventory.items if i.item_id == 104), 30)
        self.assertEqual(sum(i.count for i in player.inventory.items if i.item_id == 108), 5)
        self.assertEqual(sum(i.count for i in player.inventory.items if i.item_id == 139), 3)

    def test_resupply_missing_shop_item(self):
        player = self._create_actor(x=32644, y=32955, map_id=0)
        player.inventory.add(Item(item_id=40308, name="Adena", count=10000))

        # Item 9999 is not in Pandora's catalog
        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Nonexistent Item", item_id=9999, target_quantity=5)]
            )
        )
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
            config=config,
        )

        bot._execute_buy_supply(PANDORA_SHOP.pos)
        self.assertIn("ITEM_NOT_IN_SHOP", "".join(bot.trace_log))

    # -------------------------------------------------------------------------
    # 4. Town Navigation & Proximity Tests
    # -------------------------------------------------------------------------
    def test_navigate_to_pandora(self):
        # When in Town (map 0) and needing supplies but far from Pandora, policy must emit NAVIGATING_TO_SHOP
        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=30)]
            )
        )
        policy = BotPolicy(config=config)
        # Position in town center (32599, 32931) map 0; Pandora is at (32644, 32955)
        snap = self._create_snapshot(map_id=0, x=32599, y=32931, items=[])
        state, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertEqual(state, BotState.NAVIGATING_TO_SHOP)
        self.assertEqual(action.action_type, BotActionType.MOVE_STEP)
        self.assertEqual(action.target.x, 32644)
        self.assertEqual(action.target.y, 32955)

    def test_shop_interaction_requires_proximity(self):
        # Adjacent to Pandora (e.g. dist <= 2) -> Emits BUY_SUPPLY
        config = AutonomousConfig(
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=30)]
            )
        )
        policy = BotPolicy(config=config)
        snap = self._create_snapshot(map_id=0, x=32643, y=32955, items=[])
        state, action = policy.decide_next_action(BotState.NAVIGATING_TO_SHOP, snap)
        self.assertEqual(state, BotState.BUYING_SUPPLIES)
        self.assertEqual(action.action_type, BotActionType.BUY_SUPPLY)

    # -------------------------------------------------------------------------
    # 5. Full Autonomous Resupply Loop Tests
    # -------------------------------------------------------------------------
    def test_low_supply_triggers_return(self):
        # When red potions < threshold in dungeon, return to town is triggered
        config = AutonomousConfig(
            return_to_town=ReturnToTownPolicy(
                enabled=True,
                return_method=ReturnMethod.USE_ESCAPE_ITEM,
                triggers=[ReturnTrigger(type=ReturnTriggerType.LOW_POTION, item="Red Potion", item_id=104, threshold=5)]
            )
        )
        policy = BotPolicy(config=config)
        items = [
            Item(item_id=104, name="Red Potion", count=2),  # < 5!
            Item(item_id=139, name="Escape Scroll", count=3),
            Item(item_id=40308, name="Adena", count=1000),
        ]
        snap = self._create_snapshot(map_id=1, x=32671, y=32804, items=items)
        state, action = policy.decide_next_action(BotState.SEARCH_TARGET, snap)
        self.assertEqual(state, BotState.RETURNING_TO_TOWN)
        self.assertEqual(action.action_type, BotActionType.USE_ITEM)
        self.assertEqual(action.target.item_id, 139)

    def test_return_to_town_execution(self):
        player = self._create_actor(x=32671, y=32804, map_id=1)
        scroll = Item(item_id=139, name="Escape Scroll", count=2)
        player.inventory.add(scroll)

        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
        )

        bot._execute_use_item(scroll)
        self.assertEqual(player.map_id, 0)
        self.assertEqual(player.x, 32599)
        self.assertEqual(player.y, 32931)
        self.assertEqual(scroll.count, 1)
        self.assertEqual(bot.town_visits, 1)

    def test_cross_map_reentry(self):
        player = self._create_actor(x=32477, y=32851, map_id=0)
        bot = HeadlessBot(
            player=player,
            world_maps=self.session.world.maps,
            population=self.session.population,
            progression=self.session.progression,
            clock=self.clock,
            scheduler=self.scheduler,
        )

        portal_pos = Position(32477, 32851, map_id=0)
        bot._execute_transition_map(portal_pos)
        self.assertEqual(player.map_id, 1)
        self.assertEqual(player.x, 32669)
        self.assertEqual(player.y, 32802)
        self.assertEqual(bot.maps_traversed, 1)

    # -------------------------------------------------------------------------
    # 6. Config Persistence & Behavioral Variance Tests
    # -------------------------------------------------------------------------
    def test_config_json_round_trip(self):
        orig_config = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=45.0, item="Red Potion", item_id=104, priority=120)
            ],
            emergency_rules=[
                EmergencyActionRule(
                    enabled=True,
                    condition=EmergencyCondition(type=EmergencyConditionType.HP_PERCENT, operator=EmergencyOperator.LE, value=8.0),
                    action=EmergencyAction(type="USE_ITEM", item="Escape Scroll", item_id=139),
                    priority=300
                )
            ],
            resupply=ResupplyProfile(
                enabled=True,
                items=[ResupplyItem(enabled=True, item="Red Potion", item_id=104, target_quantity=75)]
            )
        )
        json_str = orig_config.to_json()
        loaded_config = AutonomousConfig.from_json(json_str)

        self.assertEqual(orig_config.to_dict(), loaded_config.to_dict())
        self.assertEqual(loaded_config.potion_rules[0].threshold, 45.0)
        self.assertEqual(loaded_config.emergency_rules[0].condition.value, 8.0)
        self.assertEqual(loaded_config.resupply.items[0].target_quantity, 75)

    def test_config_changes_behavior_without_code_change(self):
        # Two identical bots with different configs given the SAME perception snapshot
        config_a = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=30.0, item="Red Potion", item_id=104)
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )
        config_b = AutonomousConfig(
            potion_rules=[
                PotionRule(enabled=True, threshold_mode=PotionThresholdMode.HP_PERCENT, threshold=60.0, item="Red Potion", item_id=104)
            ],
            emergency_rules=[],
            return_to_town=ReturnToTownPolicy(enabled=False),
        )

        policy_a = BotPolicy(config=config_a)
        policy_b = BotPolicy(config=config_b)

        items = [Item(item_id=104, name="Red Potion", count=10)]
        # HP is 45%
        snap = self._create_snapshot(hp=45, max_hp=100, items=items)

        _, action_a = policy_a.decide_next_action(BotState.SEARCH_TARGET, snap)
        _, action_b = policy_b.decide_next_action(BotState.SEARCH_TARGET, snap)

        # Bot A should NOT drink (45% > 30%)
        self.assertNotEqual(action_a.action_type, BotActionType.USE_POTION)
        # Bot B SHOULD drink (45% <= 60%)
        self.assertEqual(action_b.action_type, BotActionType.USE_POTION)


if __name__ == "__main__":
    unittest.main()
