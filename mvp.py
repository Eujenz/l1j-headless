"""
mvp.py - L1J Headless Playable MVP Entrypoint (MODERN_DESIGN)
Interactive CLI and deterministic automated demo runner.
Usage:
  python mvp.py          # Interactive gameplay loop
  python mvp.py --demo   # Automated end-to-end demonstration
"""
import argparse
import json
import os
import sys
from typing import Optional

from tools.map_metadata import MapsCsvReader
from tools.map_decoder import LegacyMapDecoder
from native_engine.world import World
from native_engine.model import Actor, Position, Inventory, Weapon
from native_engine.transition import TransitionEngine, TransitionDefinition
from native_engine.world_route import StaticTransitionProvider
from native_engine.session import GameSession, HuntingArea, MonsterTemplate


def find_legacy_root(cli_root: Optional[str] = None) -> str:
    candidates = [
        cli_root,
        "../182c",
        "../Lineage182c",
        "C:/Users/p0282768/Documents/Gemini/Lineage182c"
    ]
    for c in candidates:
        if c and os.path.isdir(c) and os.path.exists(os.path.join(c, "maps", "maps.csv")):
            return os.path.abspath(c)
    raise FileNotFoundError(
        "Could not locate Legacy Reference root (Eujenz/182c). "
        "Please specify --legacy-root <path_to_182c>."
    )


def initialize_session(contract_path: str = "scenario_006_contract.json", legacy_root_arg: Optional[str] = None) -> GameSession:
    with open(contract_path, "r", encoding="utf-8") as f:
        contract = json.load(f)

    legacy_root = find_legacy_root(legacy_root_arg)
    maps_csv = os.path.join(legacy_root, "maps", "maps.csv")
    metadata_map = MapsCsvReader.read_metadata(maps_csv)

    # 1. Load Real Maps 0 and 1
    world = World()
    for mid in [0, 1]:
        meta = metadata_map[mid]
        data_file = os.path.join(legacy_root, "maps", "Cache", f"{mid}.data")
        map_def, _ = LegacyMapDecoder.decode_legacy_map(data_file, meta)
        world.add_map(map_def.to_grid())

    # 2. Register Canonical Portal
    trans = TransitionDefinition(
        transition_id="portal_ti_to_tid1",
        type="PORTAL",
        source_map=0,
        source_x=32477,
        source_y=32851,
        target_map=1,
        target_x=32669,
        target_y=32802,
        target_heading=4
    )
    trans_engine = TransitionEngine()
    trans_engine.register_transition(trans)
    provider = StaticTransitionProvider([trans])

    # 3. Setup Hunting Areas & Monsters from Contract
    areas = {}
    for a in contract["hunting_areas"]:
        areas[a["id"]] = HuntingArea(a["id"], a["name"], a["map_id"], a["goal_x"], a["goal_y"], a["monster_type"])

    monsters = {}
    for name, m in contract["monsters"].items():
        monsters[name] = MonsterTemplate(m["id"], m["name"], m["level"], m["hp"], m["max_hp"], m["ac"], m["exp"], m["size"], m["atk_min"], m["atk_max"])

    # 4. Setup Player
    p_data = contract["player"]
    wpn_data = p_data["weapon"]
    weapon = Weapon(
        item_id=wpn_data["item_id"],
        name=wpn_data["name"],
        weapon_type=wpn_data["weapon_type"],
        dmg_small=wpn_data["dmg_small"],
        dmg_large=wpn_data["dmg_large"],
        enchant=wpn_data["enchant"],
        bless=wpn_data["bless"]
    )
    player = Actor(
        id=p_data["id"],
        name=p_data["name"],
        class_type=p_data["class_type"],
        level=p_data["level"],
        hp=p_data["hp"],
        max_hp=p_data["max_hp"],
        str=p_data["str"],
        dex=p_data["dex"],
        con=p_data["con"],
        int=p_data["int"],
        wis=p_data["wis"],
        cha=p_data["cha"],
        pos=Position(p_data["start_x"], p_data["start_y"], p_data["start_map"]),
        heading=p_data["start_heading"],
        auto_pickup=False,
        inventory=Inventory(),
        equipped_weapon=weapon
    )
    world.add_actor(player, map_id=p_data["start_map"])

    seed = contract.get("rng_seed", 424242)
    return GameSession(world, player, trans_engine, provider, areas, monsters, seed=seed)


def render_status(status: dict):
    p = status["player"]
    loc = status["location"]
    tgt = status["target"]

    print("\n" + "=" * 50)
    print("                角色狀態 (STATUS)")
    print("=" * 50)
    print(f" 角色名稱: {p['name']} (等級 {p['level']})")
    print(f" 生命值  : {p['hp']} / {p['max_hp']} HP")
    print(f" 經驗值  : {p['exp']} EXP")
    print(f" 當前位置: 地圖 {loc['map_id']} ({loc['x']}, {loc['y']}) - [{loc['area_name']}]")
    if tgt:
        print(f" 鎖定目標: {tgt['name']} (等級 {tgt['level']}) - HP: {tgt['hp']} / {tgt['max_hp']}")
    print("=" * 50)


def run_demo(session: GameSession):
    print("==================================================")
    print("      L1J HEADLESS PLAYABLE MVP - DEMO MODE       ")
    print("==================================================")

    # 1. Initial State
    render_status(session.get_status())

    # 2. Select Map 1 Dungeon Area
    print("\n>>> 行動: 選擇前往 [話島地監 1F 狩獵場] (跨圖世界導航)...")
    ok, msg, events = session.select_hunting_area("map1_dungeon")
    assert ok, f"Navigation failed: {msg}"
    print(f"[導航完成] {msg} (共產生 {len(events)} 個實體事件)")
    render_status(session.get_status())

    # 3. Trigger Encounter
    print("\n>>> 行動: 探索狩獵區域 [Hunt]...")
    ok, monster, msg = session.hunt()
    assert ok and monster, f"Encounter failed: {msg}"
    print(f"[遭遇怪物] 出現了 {monster.name} (等級 {monster.level}, HP: {monster.hp}/{monster.max_hp})!")

    # 4. Turn-based Combat Loop
    turn = 1
    while not session.active_monster.is_dead:
        print(f"\n--- 回合 {turn} ---")
        ok, res, outcome = session.attack()
        assert ok, "Attack failed"

        if res["player_hit"]:
            print(f"  玩家攻擊 -> 命中! 對 {monster.name} 造成 {res['player_dmg']} 點傷害 (剩餘 HP: {res['monster_hp']}/{res['monster_max_hp']})")
        else:
            print(f"  玩家攻擊 -> 未命中!")

        if outcome == "VICTORY":
            print(f"\n>>> 戰鬥勝利! {monster.name} 被擊敗了! 獲得 {res['exp_gained']} EXP!")
            break

        if res["monster_hit"]:
            print(f"  {monster.name} 反擊 -> 命中! 對玩家造成 {res['monster_dmg']} 點傷害 (玩家剩餘 HP: {res['player_hp']}/{res['player_max_hp']})")
        else:
            print(f"  {monster.name} 反擊 -> 未命中!")

        turn += 1

    # 5. Final State
    render_status(session.get_status())
    print("\n==================================================")
    print("       >>> DEMO COMPLETED SUCCESSFULLY! <<<       ")
    print("==================================================")


def run_interactive(session: GameSession):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("==================================================")
    print("      歡迎來到 L1J Headless Playable MVP!         ")
    print("==================================================")

    while True:
        status = session.get_status()
        state = status["session_state"]

        if state == "DEAD":
            print("\n[GAME OVER] 角色已陣亡。")
            break

        print("\n請選擇指令:")
        print("  [1] 前往 話島地表狩獵場 (Map 0 Field)")
        print("  [2] 前往 話島地監1F狩獵場 (Map 1 Dungeon - 跨圖世界路徑)")
        print("  [H] 探索狩獵 (Hunt)")
        if session.active_monster and not session.active_monster.is_dead:
            print(f"  [A] 攻擊當前目標 ({session.active_monster.name})")
        print("  [S] 查看角色狀態 (Status)")
        print("  [Q] 離開遊戲 (Quit)")

        cmd = input("\n請輸入指令 > ").strip().upper()

        if cmd == "Q":
            print("\n感謝遊玩 L1J Headless MVP，再見!")
            break
        elif cmd == "S":
            render_status(session.get_status())
        elif cmd == "1":
            print("\n規劃路徑前往話島地表狩獵場...")
            ok, msg, evs = session.select_hunting_area("map0_field")
            print(f"[{'成功' if ok else '失敗'}] {msg}")
            render_status(session.get_status())
        elif cmd == "2":
            print("\n規劃路徑前往話島地監1F狩獵場 (將自動尋路至真實傳送點並跨圖)...")
            ok, msg, evs = session.select_hunting_area("map1_dungeon")
            print(f"[{'成功' if ok else '失敗'}] {msg}")
            render_status(session.get_status())
        elif cmd == "H":
            ok, m, msg = session.hunt()
            if ok:
                print(f"\n[遭遇怪物] 發現了 {m.name}! (HP: {m.hp}/{m.max_hp})")
            else:
                print(f"\n[失敗] {msg}")
        elif cmd == "A":
            if not session.active_monster or session.active_monster.is_dead:
                print("\n當前沒有可攻擊的目標! 請先按 [H] 探索狩獵。")
                continue
            ok, res, outcome = session.attack()
            if res["player_hit"]:
                print(f"\n玩家攻擊 -> 命中! 造成 {res['player_dmg']} 點傷害! (怪物剩餘 HP: {res['monster_hp']}/{res['monster_max_hp']})")
            else:
                print("\n玩家攻擊 -> 未命中!")

            if outcome == "VICTORY":
                print(f"★ 戰鬥勝利! 目標被擊倒，獲得 {res['exp_gained']} EXP!")
            elif outcome == "DEFEAT":
                print("☠ 玩家受到致命傷害陣亡!")
            else:
                if res["monster_hit"]:
                    print(f"怪物反擊 -> 命中! 受到 {res['monster_dmg']} 點傷害! (玩家剩餘 HP: {res['player_hp']}/{res['player_max_hp']})")
                else:
                    print("怪物反擊 -> 未命中!")
        else:
            print("\n未知指令，請重新輸入。")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="L1J Headless Playable MVP")
    parser.add_argument("--demo", action="store_true", help="Run automated demonstration mode")
    parser.add_argument("--contract", default="scenario_006_contract.json", help="Contract path")
    parser.add_argument("--legacy-root", default=None, help="Path to Eujenz/182c")
    args = parser.parse_args()

    session = initialize_session(args.contract, args.legacy_root)

    if args.demo:
        run_demo(session)
    else:
        run_interactive(session)


if __name__ == "__main__":
    main()
