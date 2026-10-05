"""
ui/game_events.py - Player-Visible Game Event Model for L1J Headless

Architecture:
  Strict separation between player-visible game events and internal debug trace.
  - PlayerGameEvent: structured, Chinese-language event for player consumption.
  - GameEventFormatter: converts raw bot log lines to PlayerGameEvent objects.
  - Game events flow into a bounded deque (max 500 entries) in HeadlessPlayerRuntime.
  - Debug trace stays separate and is only shown with --debug flag.

Event Categories:
  COMBAT_DAMAGE   - 你對 骷髏 造成 8 點傷害
  COMBAT_HEAL     - 你恢復了 22 HP (紅色藥水)
  MONSTER_DEATH   - 骷髏 被擊敗，獲得 50 EXP
  ITEM_USED       - 你使用了 紅色藥水
  LOOT_PICKED     - 拾取 金幣 x21
  TARGET_SELECTED - 鎖定目標：骷髏
  MAP_TRANSITION  - 進入 話島地監 1F
  LEVEL_UP        - ✦ 等級提升！達到 Lv 2
  PLAYER_DEATH    - 你已陣亡，正在重生...
  RETURN_STARTED  - 準備返回村莊
  SHOP_PURCHASE   - 向潘朵拉購買 紅色藥水 x50
  STATUS_CHANGE   - General status messages
  RESPAWN         - 你已重生
"""
from dataclasses import dataclass, field
from typing import Optional, List
import re
import time


# ---------------------------------------------------------------------------
# Chinese Localization Tables (UI presentation only, do NOT use in engine)
# ---------------------------------------------------------------------------

MAP_NAME_ZH = {
    0: "話島村莊",
    1: "話島地監 1F",
    2: "話島地監 2F",
}

BOT_STATE_ZH = {
    "SEARCH_TARGET": "搜尋目標中",
    "MOVE_TO_TARGET": "接近目標中",
    "ATTACK": "攻擊中",
    "RECOVER": "恢復中",
    "LOOT": "拾取中",
    "ROAM": "巡邏中",
    "TRAVELING_TO_HUNT": "前往獵場",
    "RETURNING_TO_TOWN": "返回村莊",
    "NAVIGATING_TO_SHOP": "前往商店",
    "BUYING_SUPPLIES": "補給中",
    "IDLE": "待機",
    "DEAD": "死亡",
    "RESPAWN": "重生中",
    "STANDBY": "等待",
}

ITEM_NAME_ZH = {
    "Red Potion": "紅色藥水",
    "Orange Potion": "橙色藥水",
    "Green Potion": "綠色藥水",
    "Escape Scroll": "回城卷軸",
    "Teleport Scroll": "傳送卷軸",
    "Adena": "金幣",
    "Long Sword": "長劍",
    "Short Sword": "短劍",
    "Leather Armor": "皮革護甲",
    "Katana": "武士刀",
    "Iron Sword": "鐵劍",
    "Bare Hands": "徒手",
}

DESTINATION_ZH = {
    "Talking Island Dungeon 1F": "話島地監 1F",
    "Talking Island Surface Field": "話島野外",
    "ti_dungeon_1f": "話島地監 1F",
    "ti_surface_field": "話島野外",
}

MODULE_ZH = {
    "auto_target": "自動選怪",
    "auto_attack": "自動攻擊",
    "auto_move": "自動移動",
    "auto_potion": "自動喝水",
    "auto_buff": "自動強化",
    "auto_loot": "自動撿物",
    "auto_return": "自動回城",
    "auto_resupply": "自動補給",
}

CLASS_NAME_ZH = {
    1: "騎士",
    2: "魔法師",
    3: "精靈",
    4: "黑暗精靈",
    5: "龍騎士",
    6: "幻術師",
}


def zh_item(name: str) -> str:
    """Translate item name to Traditional Chinese for UI display."""
    return ITEM_NAME_ZH.get(name, name)


def zh_map(map_id: int) -> str:
    """Translate map ID to Traditional Chinese name."""
    return MAP_NAME_ZH.get(map_id, f"地圖 {map_id}")


def zh_state(state_name: str) -> str:
    """Translate bot state name to Traditional Chinese."""
    return BOT_STATE_ZH.get(state_name, state_name)


def zh_dest(dest_name: str) -> str:
    """Translate destination name to Traditional Chinese."""
    return DESTINATION_ZH.get(dest_name, dest_name)


def zh_class(class_type: int) -> str:
    """Translate class type to Traditional Chinese name."""
    return CLASS_NAME_ZH.get(class_type, "冒險者")


# ---------------------------------------------------------------------------
# PlayerGameEvent - Player-Visible Game Event
# ---------------------------------------------------------------------------

@dataclass
class PlayerGameEvent:
    """
    A player-visible game event displayed in the activity log.
    Must NOT contain internal debug information.
    """
    type: str          # e.g. "COMBAT_DAMAGE"
    text: str          # e.g. "你對 骷髏 造成 8 點傷害" (Traditional Chinese)
    timestamp_ms: int  # virtual game time in ms
    metadata: dict = field(default_factory=dict)  # optional structured data for UI
    seq: int = 0  # monotonic sequence assigned by runtime (incremental consumption)


# ---------------------------------------------------------------------------
# GameEventFormatter - Convert bot trace logs to PlayerGameEvents
# ---------------------------------------------------------------------------

class GameEventFormatter:
    """
    Parses raw bot trace log strings and produces player-visible Chinese game events.
    
    Input: raw log strings like "[COMBAT] Player deals 8 damage to Skeleton (HP:45->37)"
    Output: PlayerGameEvent with Chinese text for display in Activity Log.
    """

    # Patterns to match in raw log lines
    # These patterns correspond to what controller.py emits
    _DAMAGE_PATTERN = re.compile(
        r"Player deals (\d+) damage to (.+?) \(HP:(\d+)->(\d+)\)", re.IGNORECASE
    )
    _MONSTER_DEATH_PATTERN = re.compile(
        r"Monster (.+?) (?:died|dead|HP=0)", re.IGNORECASE
    )
    _EXP_PATTERN = re.compile(r"EXP[: ]+\+?(\d+)", re.IGNORECASE)
    _LEVEL_UP_PATTERN = re.compile(r"LEVEL[_ ]?UP.*?(\d+)", re.IGNORECASE)
    _USE_ITEM_PATTERN = re.compile(r"USE_ITEM.*?(?:item=)?(.+?)(?:\s|$)", re.IGNORECASE)
    _LOOT_PATTERN = re.compile(r"LOOT.*?(\S+)\s+x?(\d+)", re.IGNORECASE)
    _MAP_TRANSITION_PATTERN = re.compile(r"TRANSITION_MAP.*?map[_\s]?(\d+)", re.IGNORECASE)
    _RETURN_PATTERN = re.compile(r"RETURN(?:ING)?_TO_TOWN|Escaping to town|return.*town", re.IGNORECASE)
    _BUY_PATTERN = re.compile(r"BUY.*?(\S+)\s+x(\d+)|purchased\s+(\d+)\s+x\s+(.+)", re.IGNORECASE)
    _RESPAWN_PATTERN = re.compile(r"RESPAWN|respawned|player.*respawn", re.IGNORECASE)
    _DEATH_PATTERN = re.compile(r"PLAYER.*(?:DIED|DEATH)|player.*dead|character.*died", re.IGNORECASE)
    _HEAL_PATTERN = re.compile(r"Healing.*\+(\d+)|hp.*restored.*(\d+)|heal.*(\d+)", re.IGNORECASE)
    _TARGET_PATTERN = re.compile(r"SELECT_TARGET.*?[:#]?\s*(.+?)(?:\s*#\d+)?$", re.IGNORECASE)

    @classmethod
    def parse(cls, log_line: str, virtual_time_ms: int) -> Optional["PlayerGameEvent"]:
        """
        Parse a raw bot trace log line and produce a PlayerGameEvent, or None if
        this log line should not generate a player-visible event.
        """
        line = log_line.strip()
        if not line:
            return None

        body = re.sub(r"^\[T=\d+\]\s*", "", line)
        if body.startswith(("[POLICY]", "[PERCEPTION]", "[MANUAL]", "[HELPER]")):
            return None
        real = cls._parse_real(body, virtual_time_ms)
        if real is not None:
            return real
        if cls._is_known_internal(body):
            return None

        # Combat damage
        m = cls._DAMAGE_PATTERN.search(line)
        if m:
            dmg = int(m.group(1))
            monster_name = m.group(2).strip()
            return PlayerGameEvent(
                type="COMBAT_DAMAGE",
                text=f"你對 {monster_name} 造成 {dmg} 點傷害",
                timestamp_ms=virtual_time_ms,
                metadata={"damage": dmg, "monster": monster_name},
            )

        # Heal / potion use with heal amount
        m = cls._HEAL_PATTERN.search(line)
        if m:
            amount = int(m.group(1) or m.group(2) or m.group(3) or 0)
            if amount > 0:
                return PlayerGameEvent(
                    type="COMBAT_HEAL",
                    text=f"你恢復了 {amount} HP",
                    timestamp_ms=virtual_time_ms,
                    metadata={"amount": amount},
                )

        # Level up
        m = cls._LEVEL_UP_PATTERN.search(line)
        if m:
            level = int(m.group(1))
            return PlayerGameEvent(
                type="LEVEL_UP",
                text=f"✦ 等級提升！達到 Lv {level}",
                timestamp_ms=virtual_time_ms,
                metadata={"level": level},
            )

        # Monster death (EXP gain)
        if "died" in line.lower() or ("HP=0" in line and "monster" in line.lower()):
            m_name = cls._MONSTER_DEATH_PATTERN.search(line)
            m_exp = cls._EXP_PATTERN.search(line)
            name = m_name.group(1).strip() if m_name else "怪物"
            exp = int(m_exp.group(1)) if m_exp else 0
            if exp > 0:
                return PlayerGameEvent(
                    type="MONSTER_DEATH",
                    text=f"{name} 被擊敗，獲得 {exp} EXP",
                    timestamp_ms=virtual_time_ms,
                    metadata={"monster": name, "exp": exp},
                )
            else:
                return PlayerGameEvent(
                    type="MONSTER_DEATH",
                    text=f"{name} 被擊敗",
                    timestamp_ms=virtual_time_ms,
                    metadata={"monster": name, "exp": 0},
                )

        # Item used (potion/scroll)
        if "USE_ITEM" in line or "USE_POTION" in line or "Drinking" in line:
            # Try to extract item name
            for eng, zh in ITEM_NAME_ZH.items():
                if eng.lower() in line.lower():
                    return PlayerGameEvent(
                        type="ITEM_USED",
                        text=f"你使用了 {zh}",
                        timestamp_ms=virtual_time_ms,
                        metadata={"item": eng},
                    )
            return PlayerGameEvent(
                type="ITEM_USED",
                text="你使用了物品",
                timestamp_ms=virtual_time_ms,
            )

        # Loot picked up
        if "LOOT" in line and ("item" in line.lower() or "picked" in line.lower() or "Adena" in line or "Potion" in line):
            for eng, zh in ITEM_NAME_ZH.items():
                if eng.lower() in line.lower():
                    m_count = re.search(r"x(\d+)|count[= ](\d+)|(\d+)\s*(?:pieces|units)?", line)
                    count = int(m_count.group(1) or m_count.group(2) or m_count.group(3)) if m_count else 1
                    return PlayerGameEvent(
                        type="LOOT_PICKED",
                        text=f"拾取 {zh} x{count}",
                        timestamp_ms=virtual_time_ms,
                        metadata={"item": eng, "count": count},
                    )
            return PlayerGameEvent(
                type="LOOT_PICKED",
                text="拾取掉落物品",
                timestamp_ms=virtual_time_ms,
            )

        # Map transition
        m = cls._MAP_TRANSITION_PATTERN.search(line)
        if m or "TRANSITION_MAP" in line:
            map_id = int(m.group(1)) if m else -1
            dest_name = zh_map(map_id) if map_id >= 0 else "新地圖"
            return PlayerGameEvent(
                type="MAP_TRANSITION",
                text=f"進入 {dest_name}",
                timestamp_ms=virtual_time_ms,
                metadata={"map_id": map_id},
            )

        # Return to town
        if cls._RETURN_PATTERN.search(line):
            return PlayerGameEvent(
                type="RETURN_STARTED",
                text="準備返回村莊",
                timestamp_ms=virtual_time_ms,
            )

        # Shop purchase
        if "BUY_SUPPLY" in line or "purchased" in line.lower():
            for eng, zh in ITEM_NAME_ZH.items():
                if eng.lower() in line.lower():
                    m_count = re.search(r"x(\d+)|(\d+)\s+(?:units|pieces)?", line)
                    count = int(m_count.group(1) or m_count.group(2)) if m_count else 1
                    return PlayerGameEvent(
                        type="SHOP_PURCHASE",
                        text=f"向潘朵拉購買 {zh} x{count}",
                        timestamp_ms=virtual_time_ms,
                        metadata={"item": eng, "count": count},
                    )
            return PlayerGameEvent(
                type="SHOP_PURCHASE",
                text="在商店補給完成",
                timestamp_ms=virtual_time_ms,
            )

        # Player death
        if cls._DEATH_PATTERN.search(line):
            return PlayerGameEvent(
                type="PLAYER_DEATH",
                text="你已陣亡，正在重生...",
                timestamp_ms=virtual_time_ms,
            )

        # Respawn
        if cls._RESPAWN_PATTERN.search(line) and "PLAYER" in line.upper():
            return PlayerGameEvent(
                type="RESPAWN",
                text="你已重生",
                timestamp_ms=virtual_time_ms,
            )

        # SELECT_TARGET (suppressed - too frequent, only show when player manually targets)
        # These are filtered at the queue level

        # No match → not a player-visible event (internal debug only)
        return None

    @classmethod
    def format_time(cls, virtual_ms: int) -> str:
        """Format virtual_ms as MM:SS for activity log timestamps."""
        total_s = virtual_ms // 1000
        m = (total_s // 60) % 60
        s = total_s % 60
        return f"{m:02d}:{s:02d}"

    # ------------------------------------------------------------------
    # Parsers for the REAL native controller log formats
    # ------------------------------------------------------------------
    _R_ATTACK = re.compile(r"\[PLAYER\] ATTACK (.+?)#\d+ \| (HIT|MISS) for (\d+) dmg")
    _R_MAGIC = re.compile(r"SKILL CAST: Energy Bolt -> Hit (.+?) for (\d+) magic dmg")
    _R_HEAL_SKILL = re.compile(r"SKILL CAST: Lesser Heal -> Restored (\d+) HP")
    _R_MON_ATK = re.compile(r"MONSTER ATTACK: (.+?)\u2192Player for (\d+) dmg")
    _R_DIED = re.compile(r"MONSTER DIED: (.+?) slain.*?\+(\d+) EXP")
    _R_LEVEL = re.compile(r"LEVEL UP: .*?Lv(\d+)\D+Lv(\d+)")
    _R_DROP = re.compile(r"GROUND DROP: .+? dropped (.+?) x(\d+) at")
    _R_LOOT = re.compile(r"LOOT: Picked up (.+?) x(\d+)")
    _R_PDIED = re.compile(r"PLAYER DIED: Slain by (.+?)\.")
    _R_ITEM = re.compile(r"\[PLAYER\] USE_ITEM (.+?) (?:\(\+(\d+) HP\)|->)")
    _R_SELECT = re.compile(r"\[PLAYER\] SELECT_TARGET -> (.+?)#\d+")
    _R_SHOP = re.compile(r"\[SHOP\] (?:PARTIAL_RESUPPLY: )?(.+?) current=\d+ target=\d+ price=\d+ buy=(\d+) cost=(\d+)")
    _R_PORTAL = re.compile(r"PORTAL_TRANSITION: .*Map (\d+)\s*$")
    _SKILL_ZH = {"Energy Bolt": "能量箭", "Lesser Heal": "初級治癒術", "Haste": "加速術"}

    _INTERNAL_PREFIXES = (
        "[PLAYER]", "[SHOP]", "MOVE", "PATROL", "HP_REGEN", "MP_REGEN", "ATTACK TRIGGERED",
        "DAMAGE RESOLVED", "RESPAWN:", "PLAYER SPAWN", "SESSION END", "MONSTER MOVE",
        "SKILL FAILED", "SKILL CAST", "GROUND DROP", "MONSTER DIED", "LEVEL UP",
    )

    @classmethod
    def _is_known_internal(cls, body: str) -> bool:
        return body.startswith(cls._INTERNAL_PREFIXES)

    @classmethod
    def _parse_real(cls, body: str, t: int) -> Optional["PlayerGameEvent"]:
        m = cls._R_ATTACK.search(body)
        if m:
            name, res, dmg = m.group(1), m.group(2), int(m.group(3))
            if res == "MISS":
                return PlayerGameEvent("COMBAT_MISS", f"你的攻擊沒有命中 {name}", t, {"monster": name})
            return PlayerGameEvent("COMBAT_DAMAGE", f"你對 {name} 造成 {dmg} 點傷害", t,
                                   {"damage": dmg, "monster": name})
        m = cls._R_MAGIC.search(body)
        if m:
            name, dmg = m.group(1), int(m.group(2))
            return PlayerGameEvent("COMBAT_DAMAGE", f"你的魔法「能量箭」對 {name} 造成 {dmg} 點傷害", t,
                                   {"damage": dmg, "monster": name})
        m = cls._R_HEAL_SKILL.search(body)
        if m:
            amt = int(m.group(1))
            return PlayerGameEvent("COMBAT_HEAL", f"你的魔法「初級治癒術」恢復了 {amt} HP", t, {"amount": amt})
        m = cls._R_MON_ATK.search(body)
        if m:
            name, dmg = m.group(1), int(m.group(2))
            text = f"{name} 對你造成 {dmg} 點傷害" if dmg > 0 else f"{name} 的攻擊沒有傷到你"
            return PlayerGameEvent("MONSTER_HIT", text, t, {"damage": dmg, "monster": name})
        m = cls._R_DIED.search(body)
        if m:
            name, exp = m.group(1), int(m.group(2))
            return PlayerGameEvent("MONSTER_DEATH", f"{name} 被擊敗，獲得 {exp} EXP", t,
                                   {"monster": name, "exp": exp})
        m = cls._R_LEVEL.search(body)
        if m:
            lv = int(m.group(2))
            return PlayerGameEvent("LEVEL_UP", f"✦ 等級提升！達到 Lv {lv}", t, {"level": lv})
        m = cls._R_DROP.search(body)
        if m:
            return PlayerGameEvent("LOOT_DROP", f"掉落了 {zh_item(m.group(1))} x{m.group(2)}", t)
        m = cls._R_LOOT.search(body)
        if m:
            item, cnt = m.group(1), int(m.group(2))
            return PlayerGameEvent("LOOT_PICKED", f"拾取 {zh_item(item)} x{cnt}", t,
                                   {"item": item, "count": cnt})
        m = cls._R_PDIED.search(body)
        if m:
            return PlayerGameEvent("PLAYER_DEATH", f"你被 {m.group(1)} 殺死了", t)
        if body.startswith("PLAYER RESPAWN"):
            return PlayerGameEvent("RESPAWN", "你在村莊復活了", t)
        m = cls._R_ITEM.search(body)
        if m:
            item, heal = m.group(1), m.group(2)
            if heal:
                return PlayerGameEvent("COMBAT_HEAL", f"使用 {zh_item(item)}，恢復 {heal} HP", t,
                                       {"amount": int(heal), "item": item})
            if item == "Escape Scroll":
                return PlayerGameEvent("RETURN_STARTED", "使用回城卷軸，傳送回村莊", t)
            return PlayerGameEvent("ITEM_USED", f"你使用了 {zh_item(item)}", t, {"item": item})
        m = cls._R_SELECT.search(body)
        if m:
            return PlayerGameEvent("TARGET_SELECTED", f"鎖定目標：{m.group(1)}", t)
        m = cls._R_SHOP.search(body)
        if m and int(m.group(2)) > 0:
            return PlayerGameEvent("SHOP_PURCHASE",
                                   f"向潘朵拉購買 {zh_item(m.group(1))} x{m.group(2)}（花費 {m.group(3)} 金幣）", t,
                                   {"item": m.group(1), "count": int(m.group(2))})
        m = cls._R_PORTAL.search(body)
        if m:
            return PlayerGameEvent("MAP_TRANSITION", f"進入 {zh_map(int(m.group(1)))}", t,
                                   {"map_id": int(m.group(1))})
        if body.startswith("[PLAYER] RETURN_TOWN"):
            return PlayerGameEvent("RETURN_STARTED", "準備返回村莊", t)
        return None
