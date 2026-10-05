"""
tests/test_game_events.py - Unit tests for PlayerGameEvent model and GameEventFormatter

Tests:
  1. Event queue bounded at 500 entries
  2. Combat damage → correct Chinese text
  3. Monster death → Chinese name + EXP
  4. Item use → Chinese item name
  5. Map transition → Chinese map name
  6. Loot → Chinese item name and count
  7. Level up event
  8. Shop purchase event
  9. Return to town event
 10. Time format utility
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from collections import deque
from ui.game_events import (
    PlayerGameEvent,
    GameEventFormatter,
    ITEM_NAME_ZH,
    BOT_STATE_ZH,
    MAP_NAME_ZH,
    zh_state,
    zh_map,
    zh_item,
)


class TestGameEventFormatter(unittest.TestCase):

    def test_combat_damage_event(self):
        """Combat damage log line → Chinese damage text."""
        line = "[COMBAT] Player deals 8 damage to Skeleton (HP:45->37)"
        evt = GameEventFormatter.parse(line, 5000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "COMBAT_DAMAGE")
        self.assertIn("8", evt.text)
        self.assertIn("Skeleton", evt.text)
        self.assertIn("傷害", evt.text)

    def test_monster_death_with_exp(self):
        """Monster death log with EXP → death event with EXP amount."""
        line = "Monster Skeleton died EXP +50"
        evt = GameEventFormatter.parse(line, 10000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "MONSTER_DEATH")
        self.assertIn("50", evt.text)
        self.assertIn("EXP", evt.text)
        self.assertIn("Skeleton", evt.text)

    def test_item_use_red_potion(self):
        """USE_ITEM Red Potion → Chinese potion name."""
        line = "[ACTION] USE_ITEM Red Potion consumed"
        evt = GameEventFormatter.parse(line, 15000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "ITEM_USED")
        self.assertIn("紅色藥水", evt.text)

    def test_map_transition(self):
        """TRANSITION_MAP line → Chinese map destination."""
        line = "TRANSITION_MAP to map_id=1"
        evt = GameEventFormatter.parse(line, 20000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "MAP_TRANSITION")
        self.assertIn("進入", evt.text)

    def test_loot_adena(self):
        """Loot Adena → Chinese currency name and count."""
        line = "[LOOT] picked item=Adena x21"
        evt = GameEventFormatter.parse(line, 25000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "LOOT_PICKED")
        self.assertIn("拾取", evt.text)

    def test_level_up(self):
        """LEVEL UP log → Chinese level up event."""
        line = "LEVEL_UP reached level 2"
        evt = GameEventFormatter.parse(line, 30000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "LEVEL_UP")
        self.assertIn("等級提升", evt.text)
        self.assertIn("2", evt.text)

    def test_return_to_town(self):
        """Return to town → return started event."""
        line = "RETURNING_TO_TOWN triggered"
        evt = GameEventFormatter.parse(line, 35000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "RETURN_STARTED")
        self.assertIn("村莊", evt.text)

    def test_shop_purchase(self):
        """BUY_SUPPLY log → shop purchase event with item name."""
        line = "BUY_SUPPLY Red Potion x50 purchased"
        evt = GameEventFormatter.parse(line, 40000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "SHOP_PURCHASE")
        self.assertIn("紅色藥水", evt.text)

    def test_internal_logs_return_none(self):
        """Internal POLICY/PERCEPTION logs should NOT produce player events."""
        internal_lines = [
            "[POLICY] evaluating state SEARCH_TARGET",
            "[PERCEPTION] scanning radius=14",
            "scheduler tick at t=5000",
            "Action gate scheduled at 5640ms",
            "[DEBUG] HP=50 max=100",
        ]
        for line in internal_lines:
            evt = GameEventFormatter.parse(line, 0)
            self.assertIsNone(evt, f"Expected None for internal log: {line!r}")

    def test_time_format(self):
        """Format_time utility returns MM:SS."""
        self.assertEqual(GameEventFormatter.format_time(0), "00:00")
        self.assertEqual(GameEventFormatter.format_time(60000), "01:00")
        self.assertEqual(GameEventFormatter.format_time(125000), "02:05")

    def test_event_queue_bounded(self):
        """Bounded deque of game events caps at maxlen without memory growth."""
        q = deque(maxlen=500)
        for i in range(600):
            q.append(PlayerGameEvent(
                type="COMBAT_DAMAGE",
                text=f"傷害 {i}",
                timestamp_ms=i * 100,
            ))
        self.assertEqual(len(q), 500)
        # Oldest events dropped, newest kept
        self.assertIn("傷害 599", q[-1].text)
        self.assertIn("傷害 100", q[0].text)

    def test_chinese_localization_tables(self):
        """Verify key localization table entries are correct Chinese."""
        self.assertEqual(ITEM_NAME_ZH.get("Red Potion"), "紅色藥水")
        self.assertEqual(ITEM_NAME_ZH.get("Escape Scroll"), "回城卷軸")
        self.assertEqual(ITEM_NAME_ZH.get("Adena"), "金幣")
        self.assertEqual(MAP_NAME_ZH.get(0), "話島村莊")
        self.assertEqual(MAP_NAME_ZH.get(1), "話島地監 1F")
        self.assertEqual(BOT_STATE_ZH.get("ATTACK"), "攻擊中")
        self.assertEqual(BOT_STATE_ZH.get("TRAVELING_TO_HUNT"), "前往獵場")
        self.assertEqual(BOT_STATE_ZH.get("RETURNING_TO_TOWN"), "返回村莊")
        self.assertEqual(BOT_STATE_ZH.get("BUYING_SUPPLIES"), "補給中")


class TestChineseHelpers(unittest.TestCase):

    def test_zh_state_known(self):
        self.assertEqual(zh_state("ATTACK"), "攻擊中")
        self.assertEqual(zh_state("ROAM"), "巡邏中")

    def test_zh_state_unknown_fallback(self):
        """Unknown state → return raw state name."""
        self.assertEqual(zh_state("UNKNOWN_STATE"), "UNKNOWN_STATE")

    def test_zh_map_known(self):
        self.assertEqual(zh_map(0), "話島村莊")
        self.assertEqual(zh_map(1), "話島地監 1F")

    def test_zh_map_unknown(self):
        self.assertIn("2", zh_map(2))  # 話島地監 2F or similar

    def test_zh_item_known(self):
        self.assertEqual(zh_item("Red Potion"), "紅色藥水")
        self.assertEqual(zh_item("Green Potion"), "綠色藥水")

    def test_zh_item_unknown_fallback(self):
        """Unknown item → return original name."""
        self.assertEqual(zh_item("Mystery Herb"), "Mystery Herb")


class TestRealControllerEvents(unittest.TestCase):
    """Verifies that the actual log strings emitted by controller.py parse correctly."""

    def test_real_controller_attack_hit_and_miss(self):
        hit_line = "[T=1000] [PLAYER] ATTACK Skeleton#101 | HIT for 12 dmg (IMMEDIATE) | Target HP: 23/35"
        evt = GameEventFormatter.parse(hit_line, 1000)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "COMBAT_DAMAGE")
        self.assertIn("12", evt.text)
        self.assertIn("Skeleton", evt.text)
        self.assertEqual(evt.metadata.get("damage"), 12)

        miss_line = "[T=1200] [PLAYER] ATTACK Orc#102 | MISS for 0 dmg (IMMEDIATE) | Target HP: 40/40"
        evt_miss = GameEventFormatter.parse(miss_line, 1200)
        self.assertIsNotNone(evt_miss)
        self.assertEqual(evt_miss.type, "COMBAT_MISS")
        self.assertIn("沒有命中", evt_miss.text)

    def test_real_controller_monster_attack(self):
        line = "[T=1400] MONSTER ATTACK: Stone Golem→Player for 18 dmg | Player HP: 82/100"
        evt = GameEventFormatter.parse(line, 1400)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "MONSTER_HIT")
        self.assertIn("Stone Golem", evt.text)
        self.assertIn("18", evt.text)
        self.assertEqual(evt.metadata.get("damage"), 18)

    def test_real_controller_skill_cast(self):
        magic_line = "SKILL CAST: Energy Bolt -> Hit Werewolf for 15 magic dmg (IMMEDIATE) | Target HP: 10/25 MP: 5/10"
        evt = GameEventFormatter.parse(magic_line, 1600)
        self.assertIsNotNone(evt)
        self.assertEqual(evt.type, "COMBAT_DAMAGE")
        self.assertIn("能量箭", evt.text)
        self.assertIn("15", evt.text)

        heal_line = "SKILL CAST: Lesser Heal -> Restored 20 HP | Player HP: 95/100 MP: 2/10"
        evt_h = GameEventFormatter.parse(heal_line, 1800)
        self.assertIsNotNone(evt_h)
        self.assertEqual(evt_h.type, "COMBAT_HEAL")
        self.assertIn("初級治癒術", evt_h.text)
        self.assertEqual(evt_h.metadata.get("amount"), 20)

    def test_real_controller_ground_drop_and_loot(self):
        drop_line = "[PLAYER] GROUND DROP: Skeleton dropped Adena x30 at (32671, 32804)"
        evt_d = GameEventFormatter.parse(drop_line, 2000)
        self.assertIsNotNone(evt_d)
        self.assertEqual(evt_d.type, "LOOT_DROP")
        self.assertIn("金幣", evt_d.text)

        loot_line = "LOOT: Picked up Adena x30 -> Added to Inventory"
        evt_l = GameEventFormatter.parse(loot_line, 2200)
        self.assertIsNotNone(evt_l)
        self.assertEqual(evt_l.type, "LOOT_PICKED")
        self.assertIn("金幣", evt_l.text)
        self.assertEqual(evt_l.metadata.get("count"), 30)

    def test_real_controller_player_died_and_respawn(self):
        died_line = "PLAYER DIED: Slain by Lycanthrope. Novice protection active (Lv1 <= 9), 0 EXP lost."
        evt_d = GameEventFormatter.parse(died_line, 2400)
        self.assertIsNotNone(evt_d)
        self.assertEqual(evt_d.type, "PLAYER_DEATH")
        self.assertIn("Lycanthrope", evt_d.text)

        respawn_line = "PLAYER RESPAWN: Revived at Town (32477, 32875) with HP: 100/100"
        evt_r = GameEventFormatter.parse(respawn_line, 2600)
        self.assertIsNotNone(evt_r)
        self.assertEqual(evt_r.type, "RESPAWN")
        self.assertIn("復活", evt_r.text)

    def test_real_controller_portal_transition(self):
        portal_line = "PORTAL_TRANSITION: Entered TI Dungeon 1F at (32671, 32804) Map 1"
        evt_p = GameEventFormatter.parse(portal_line, 2800)
        self.assertIsNotNone(evt_p)
        self.assertEqual(evt_p.type, "MAP_TRANSITION")
        self.assertIn("話島地監 1F", evt_p.text)


class TestWorldCanvasTerrain(unittest.TestCase):
    """Tests the real map terrain row builder and boundary recognition."""

    def test_terrain_rows_structure_and_boundaries(self):
        from native_engine.map import WorldMapGrid
        from ui.world_canvas import build_terrain_rows, COLOR_FLOOR, COLOR_WALL, COLOR_WALL_EDGE, COLOR_VOID

        # Create a tiny 5x5 grid with bounds (10, 10) to (14, 14)
        # Center (12, 12) is walkable floor (east edge open = 0x01)
        grid = WorldMapGrid(map_id=99, loc_x1=10, loc_y1=10, width=5, height=5)
        grid.set_tile(12, 12, 0x01)

        # Build 5x5 viewport centered at (12, 12), so origin is (10, 10)
        rows = build_terrain_rows(grid, origin_x=10, origin_y=10, w=5, h=5)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(rows[0]), 5)

        # Center tile (relative 2, 2) must be COLOR_FLOOR
        self.assertEqual(rows[2][2], COLOR_FLOOR)

        # Tile directly north (relative 2, 1) touches floor -> must be COLOR_WALL_EDGE
        self.assertEqual(rows[1][2], COLOR_WALL_EDGE)

        # Outside bounds (origin_x - 1, origin_y - 1) -> must be COLOR_VOID
        rows_with_void = build_terrain_rows(grid, origin_x=8, origin_y=8, w=3, h=3)
        self.assertEqual(rows_with_void[0][0], COLOR_VOID)


if __name__ == "__main__":
    unittest.main()

