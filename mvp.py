"""
mvp.py - L1J Headless MVP Entrypoint (Scenario 007 — Authentic World Hunting Simulation)

Usage:
  python mvp.py                        # Interactive S007 authentic hunting mode
  python mvp.py --demo                 # S006 backward-compat automated demo (legacy contract)
  python mvp.py --demo --s007          # S007 authentic hunting automated demo
  python mvp.py --kills N              # Demo with custom kill limit (default 3)

Architecture:
  - S006 --demo uses scenario_006_contract.json + old GameSession.select_hunting_area() + attack()
  - S007 --s007 / interactive uses scenario_007_contract.json + autonomous move_to() + hunt()
"""
import argparse
import json
import os
import sys
from typing import Optional, Dict, Any

from tools.map_metadata import MapsCsvReader
from tools.map_decoder import LegacyMapDecoder
from native_engine.world import World
from native_engine.model import Actor, Position, Inventory, Weapon, Item
from native_engine.transition import TransitionEngine, TransitionDefinition
from native_engine.world_route import StaticTransitionProvider
from native_engine.session import GameSession, HuntingArea, MonsterTemplate, Destination
from native_engine.population import PopulationManager
from native_engine.progression import ProgressionManager
from native_engine.equipment import EquipmentManager, build_weapon_from_contract
from native_engine.rng import NativeRng
from native_engine.clock import SimulationClock, VirtualClock, RealTimeClock


def resolve_path(path: str) -> str:
    """Resolve a relative path against CWD and repo root (script directory)."""
    if os.path.isabs(path) and os.path.exists(path):
        return path
    if os.path.exists(path):
        return os.path.abspath(path)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(script_dir, path)
    if os.path.exists(candidate):
        return candidate
    return path


def find_legacy_root(cli_root: Optional[str] = None) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        cli_root,
        "../182c",
        "../Lineage182c",
        os.path.join(script_dir, "../182c"),
        os.path.join(script_dir, "../Lineage182c"),
        "C:/Users/p0282768/Documents/Gemini/Lineage182c"
    ]
    for c in candidates:
        if c and os.path.isdir(c) and os.path.exists(os.path.join(c, "maps", "maps.csv")):
            return os.path.abspath(c)
    raise FileNotFoundError(
        "Could not locate Legacy Reference root (Eujenz/182c). "
        "Please specify --legacy-root <path_to_182c>."
    )


# ---------------------------------------------------------------------------
# S006 Legacy Session Initializer (backward compat for --demo)
# ---------------------------------------------------------------------------

def initialize_s006_session(contract_path: str = "scenario_006_contract.json", legacy_root_arg: Optional[str] = None) -> GameSession:
    resolved_contract = resolve_path(contract_path)
    with open(resolved_contract, "r", encoding="utf-8") as f:
        contract = json.load(f)

    legacy_root = find_legacy_root(legacy_root_arg)
    maps_csv = os.path.join(legacy_root, "maps", "maps.csv")
    metadata_map = MapsCsvReader.read_metadata(maps_csv)

    world = World()
    for mid in [0, 1]:
        meta = metadata_map[mid]
        data_file = os.path.join(legacy_root, "maps", "Cache", f"{mid}.data")
        map_def, _ = LegacyMapDecoder.decode_legacy_map(data_file, meta)
        world.add_map(map_def.to_grid())

    trans = TransitionDefinition(
        transition_id="portal_ti_to_tid1",
        type="PORTAL",
        source_map=0, source_x=32477, source_y=32851,
        target_map=1, target_x=32669, target_y=32802, target_heading=4
    )
    trans_engine = TransitionEngine()
    trans_engine.register_transition(trans)
    provider = StaticTransitionProvider([trans])

    areas = {}
    for a in contract["hunting_areas"]:
        areas[a["id"]] = HuntingArea(a["id"], a["name"], a["map_id"], a["goal_x"], a["goal_y"], a["monster_type"])

    monsters = {}
    for name, m in contract["monsters"].items():
        monsters[name] = MonsterTemplate(m["id"], m["name"], m["level"], m["hp"], m["max_hp"], m["ac"], m["exp"], m["size"], m["atk_min"], m["atk_max"])

    p_data = contract["player"]
    wpn_data = p_data["weapon"]
    weapon = Weapon(
        item_id=wpn_data["item_id"], name=wpn_data["name"],
        weapon_type=wpn_data["weapon_type"],
        dmg_small=wpn_data["dmg_small"], dmg_large=wpn_data["dmg_large"],
        enchant=wpn_data["enchant"], bless=wpn_data["bless"]
    )
    player = Actor(
        id=p_data["id"], name=p_data["name"], class_type=p_data["class_type"],
        level=p_data["level"], hp=p_data["hp"], max_hp=p_data["max_hp"],
        str=p_data["str"], dex=p_data["dex"], con=p_data["con"],
        int=p_data["int"], wis=p_data["wis"], cha=p_data["cha"],
        pos=Position(p_data["start_x"], p_data["start_y"], p_data["start_map"]),
        heading=p_data["start_heading"], auto_pickup=False,
        inventory=Inventory(), equipped_weapon=weapon
    )
    world.add_actor(player, map_id=p_data["start_map"])

    seed = contract.get("rng_seed", 424242)

    # Minimal population/progression for S006 compat (no spawn data in S006 contract)
    empty_pop = PopulationManager({}, NativeRng(seed))
    prog = ProgressionManager({1: 0, 2: 20, 3: 45, 4: 80, 5: 630})
    equip = EquipmentManager([weapon])
    dests = {}

    return GameSession(
        world=world, player=player,
        transition_engine=trans_engine, transition_provider=provider,
        population=empty_pop, progression=prog, equipment_mgr=equip,
        destinations=dests, seed=seed,
        areas=areas, monsters=monsters
    )

# Alias for backward compatibility (mvp_replay.py imports initialize_session)
initialize_session = initialize_s006_session


# ---------------------------------------------------------------------------
# S007 Authentic Session Initializer
# ---------------------------------------------------------------------------

def initialize_s007_session(
    contract_path: str = "scenario_007_contract.json",
    legacy_root_arg: Optional[str] = None,
    seed_override: Optional[int] = None,
    clock: Optional[SimulationClock] = None,
) -> GameSession:
    resolved_contract = resolve_path(contract_path)
    with open(resolved_contract, "r", encoding="utf-8") as f:
        contract = json.load(f)

    legacy_root = find_legacy_root(legacy_root_arg)
    maps_csv = os.path.join(legacy_root, "maps", "maps.csv")
    metadata_map = MapsCsvReader.read_metadata(maps_csv)

    world = World()
    for mid in [0, 1]:
        meta = metadata_map[mid]
        data_file = os.path.join(legacy_root, "maps", "Cache", f"{mid}.data")
        map_def, _ = LegacyMapDecoder.decode_legacy_map(data_file, meta)
        world.add_map(map_def.to_grid())

    trans = TransitionDefinition(
        transition_id="portal_ti_to_tid1",
        type="PORTAL",
        source_map=0, source_x=32477, source_y=32851,
        target_map=1, target_x=32669, target_y=32802, target_heading=4
    )
    trans_engine = TransitionEngine()
    trans_engine.register_transition(trans)
    provider = StaticTransitionProvider([trans])

    seed = seed_override if seed_override is not None else contract.get("rng_seed", 777777)
    rng = NativeRng(seed)

    # Population from Legacy spawn data (validated against real WorldMapGrid collision)
    population = PopulationManager.from_contract(contract, rng, map_ids=[0, 1], map_grids=world.maps)

    # Progression from Legacy exp table
    progression = ProgressionManager.from_contract(contract, rng)

    # Player setup
    p_data = contract["player"]

    # Build weapons from inventory
    weapons_list = [build_weapon_from_contract(item) for item in p_data.get("inventory", [])]
    equip_mgr = EquipmentManager(weapons_list)

    # Default equipped weapon
    equipped_weapon = None
    default_weapon_id = p_data.get("equipped_weapon_id")
    if default_weapon_id:
        equipped_weapon = equip_mgr.get_weapon(default_weapon_id)

    inv = Inventory()
    for item_data in p_data.get("inventory", []):
        inv.add(Item(
            item_id=item_data["item_id"],
            name=item_data["name"],
            count=item_data.get("count", 1)
        ))

    player = Actor(
        id=p_data["id"], name=p_data["name"], class_type=p_data["class_type"],
        level=p_data["level"], hp=p_data["hp"], max_hp=p_data.get("max_hp", p_data["hp"]),
        mp=p_data.get("mp", 10), max_mp=p_data.get("max_mp", p_data.get("mp", 10)),
        str=p_data["str"], dex=p_data["dex"], con=p_data["con"],
        int=p_data["int"], wis=p_data["wis"], cha=p_data["cha"],
        pos=Position(p_data["start_x"], p_data["start_y"], p_data["start_map"]),
        heading=p_data.get("start_heading", 0), auto_pickup=False,
        inventory=inv,
        equipped_weapon=equipped_weapon,
        exp=p_data.get("exp", 0), lawful=p_data.get("lawful", 0), is_dead=False,
        gfx=p_data.get("gfx", 61),
        gfx_mode=p_data.get("gfx_mode", 4),
        move_speed_ms=p_data.get("move_speed_ms", 640),
        attack_speed_ms=p_data.get("attack_speed_ms", 920),
    )
    setattr(player, 'ac', p_data.get("ac", 10))  # Store AC for monster counter-attack

    world.add_actor(player, map_id=p_data["start_map"])

    # Destinations
    destinations = {}
    for d in contract.get("destinations", []):
        destinations[d["id"]] = Destination(d["id"], d["name"], d["map_id"], d["x"], d["y"])

    return GameSession(
        world=world, player=player,
        transition_engine=trans_engine, transition_provider=provider,
        population=population, progression=progression, equipment_mgr=equip_mgr,
        destinations=destinations, seed=seed, clock=clock,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_status(status: dict):
    p = status["player"]
    loc = status["location"]
    tgt = status.get("target")
    equip = status.get("equipment", {})
    nearby = status.get("nearby_monsters", [])
    equipped = equip.get("equipped")

    print("\n" + "=" * 50)
    print("                角色狀態 (STATUS)")
    print("=" * 50)
    print(f" 角色名稱: {p['name']} (等級 {p['level']})")
    print(f" 生命值  : {p['hp']} / {p['max_hp']} HP")
    print(f" 經驗值  : {p['exp']} EXP")
    print(f" 當前位置: 地圖 {loc['map_id']} ({loc['x']}, {loc['y']})")
    if loc.get("destination"):
        print(f" 目的地  : {loc['destination']}")
    if equipped:
        print(f" 武器    : {equipped['name']} (傷害 {equipped['dmg_small']}/{equipped['dmg_large']}+{equipped['enchant']})")
    else:
        print(" 武器    : 空手")
    if tgt:
        print(f" 鎖定目標: {tgt['name']} (等級 {tgt['level']}) - HP: {tgt['hp']} / {tgt['max_hp']}")
    if nearby:
        nearby_str = ", ".join(m["name"] + "(Lv" + str(m["level"]) + ")" for m in nearby[:3])
        print(f" 附近怪物: {nearby_str}")
    print(f" 擊殺數  : {status.get('kills_total', 0)}")
    print("=" * 50)


# ---------------------------------------------------------------------------
# S006 Demo (legacy compat)
# ---------------------------------------------------------------------------

def run_s006_demo(session: GameSession):
    print("==================================================")
    print("      L1J HEADLESS PLAYABLE MVP - DEMO MODE       ")
    print("==================================================")

    render_status(session.get_status())

    print("\n>>> 行動: 選擇前往 [話島地監 1F 狩獵場]...")
    ok, msg, events = session.select_hunting_area("map1_dungeon")
    assert ok, f"Navigation failed: {msg}"
    print(f"[導航完成] {msg} (共產生 {len(events)} 個實體事件)")
    render_status(session.get_status())

    print("\n>>> 行動: 探索狩獵區域 [Hunt]...")
    ok, monster, msg = session.s006_hunt()
    assert ok and monster, f"Encounter failed: {msg}"
    print(f"[遭遇怪物] 出現了 {monster.name} (等級 {monster.level}, HP: {monster.hp}/{monster.max_hp})!")

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

    render_status(session.get_status())
    print("\n==================================================")
    print("       >>> DEMO COMPLETED SUCCESSFULLY! <<<       ")
    print("==================================================")


# ---------------------------------------------------------------------------
# S007 Demo (authentic hunting)
# ---------------------------------------------------------------------------

def _log(kind: str, msg: str):
    print(msg)


def run_s007_demo(session: GameSession, kill_limit: int = 1):
    print("=" * 60)
    print("   L1J HEADLESS — AUTHENTIC WORLD HUNTING DEMO (S007)")
    print("=" * 60)
    pop_summary = session.population.summary()
    print(f"[世界人口] Map 0: {pop_summary.get(0, {}).get('alive', 0)} 隻怪物 | Map 1: {pop_summary.get(1, {}).get('alive', 0)} 隻怪物")
    render_status(session.get_status())

    # Move to dungeon
    print("\n>>> 玩家意圖: 前往話島地監 1F")
    print("-" * 40)
    ok, reason, events = session.move_to("ti_dungeon_1f", log_callback=_log)
    print(f"\n[移動完成] 狀態: {reason}  (共 {len(events)} 個事件)")
    render_status(session.get_status())

    if not ok and reason == "PLAYER_DIED_IN_TRAVEL":
        print("[遊戲結束] 旅途中陣亡！")
        return

    # Hunt in dungeon
    print(f"\n>>> 玩家意圖: 開始自動狩獵 (kill_limit={kill_limit})")
    print("-" * 40)
    ok, reason, events = session.hunt(kill_limit=kill_limit, log_callback=_log)
    print(f"\n[狩獵完成] 狀態: {reason}  (共 {len(events)} 個事件)")

    print("\n" + "=" * 60)
    render_status(session.get_status())
    print("\n>>> SCENARIO 007 DEMO COMPLETED!")
    print("=" * 60)


# ---------------------------------------------------------------------------
# S007 Interactive Mode
# ---------------------------------------------------------------------------

def run_s007_interactive(session: GameSession):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 50)
    print("   歡迎來到 L1J Headless — 真實世界狩獵模擬   ")
    print("=" * 50)
    pop = session.population.summary()
    print(f"[世界] Map 0: {pop.get(0, {}).get('alive', 0)} 隻怪物 | Map 1: {pop.get(1, {}).get('alive', 0)} 隻怪物")

    while True:
        status = session.get_status()
        state = status["session_state"]

        if state == "DEAD":
            print("\n[GAME OVER] 角色已陣亡。")
            render_status(status)
            break

        p = status["player"]
        print(f"\n[{p['name']} | Lv{p['level']} | HP:{p['hp']}/{p['max_hp']} | EXP:{p['exp']}]")
        print("----------------------------------------")
        print("[M] 移動/旅行  [H] 自動狩獵  [S] 狀態  [E] 裝備  [Q] 離開")
        print("----------------------------------------")

        try:
            cmd = input("指令 > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n感謝遊玩 L1J Headless，再見!")
            break

        if cmd == "Q":
            print("\n感謝遊玩 L1J Headless，再見!")
            break

        elif cmd == "S":
            render_status(session.get_status())

        elif cmd == "M":
            print("\n選擇目的地:")
            dests = list(session.destinations.values())
            for i, d in enumerate(dests, 1):
                print(f"  [{i}] {d.name} (Map {d.map_id})")
            try:
                choice = int(input("選擇 > ").strip()) - 1
                if 0 <= choice < len(dests):
                    dest = dests[choice]
                    print(f"\n[前往] {dest.name}...")
                    ok, reason, events = session.move_to(dest.id, log_callback=_log)
                    print(f"[完成] {reason}")
                    render_status(session.get_status())
                else:
                    print("無效選項")
            except (ValueError, EOFError):
                print("無效輸入")

        elif cmd == "H":
            print("\n[自動狩獵] 開始...")
            ok, reason, events = session.hunt(kill_limit=5, log_callback=_log)
            print(f"\n[狩獵結束] 原因: {reason}")
            render_status(session.get_status())

        elif cmd == "E":
            equip = session.equipment_mgr.status(session.player)
            equipped = equip.get("equipped")
            available = equip.get("available", [])
            print("\n[裝備管理]")
            print(f"  目前武器: {equipped['name']} ({equipped['dmg_small']}/{equipped['dmg_large']})" if equipped else "  目前武器: 空手")
            print("  可用武器:")
            for i, w in enumerate(available, 1):
                print(f"    [{i}] {w['name']} (傷害: {w['dmg_small']}/{w['dmg_large']})")
            try:
                choice = int(input("裝備武器編號 (0=取消) > ").strip())
                if 1 <= choice <= len(available):
                    item_id = available[choice - 1]["item_id"]
                    ok, reason, evts = session.equip(item_id)
                    print(f"[{'成功' if ok else '失敗'}] {reason}")
                elif choice != 0:
                    print("無效選項")
            except (ValueError, EOFError):
                print("取消")

        else:
            print("未知指令")


def run_headless_player_mvp(
    config_path: str = "configs/autonomous_default.json",
    contract_path: Optional[str] = None,
    seed: Optional[int] = 777777,
    duration_ms: int = 600000,
    speed: Optional[float] = None,
    instant: bool = False,
    verbose: bool = True,
    legacy_root_arg: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Official L1J Headless Player MVP Entrypoint.
    Executes autonomous player driven by player-configurable automation helper.
    """
    from native_engine.bot import HeadlessBot, AutonomousConfig
    from native_engine.temporal import BaseClock, VirtualClock, RealTimeClock, Scheduler
    from native_engine.model import Item

    print("=================================================================")
    print("             L1J HEADLESS PLAYER MVP (L1J 1.82)                  ")
    print("=================================================================")

    # 1. Load Autonomous Configuration Profile
    resolved_config = resolve_path(config_path)
    if not os.path.exists(resolved_config):
        print(f"[ERROR] Config file not found: {resolved_config}, using default AutonomousConfig()")
        config = AutonomousConfig()
    else:
        config = AutonomousConfig.load_json(resolved_config)

    # 2. Unified Simulation Clock & Scheduler
    if speed is not None and speed > 0:
        clock = RealTimeClock(time_scale=speed)
    else:
        clock = VirtualClock(0)
    scheduler = Scheduler(clock)

    # 3. Initialize World Session
    resolved_contract = resolve_path(contract_path or "scenario_007_contract.json")
    session = initialize_s007_session(
        contract_path=resolved_contract,
        legacy_root_arg=legacy_root_arg,
        seed_override=seed,
        clock=clock,
    )

    # 4. Initialize Headless Player (Authentic starting position from Contract - NO TELEPORT)
    player = session.player

    def print_trace(msg: str):
        if verbose:
            print(f"[T={clock.now():06d}] {msg}")

    bot = HeadlessBot(
        player=player,
        world_maps=session.world.maps,
        population=session.population,
        progression=session.progression,
        clock=clock,
        scheduler=scheduler,
        rng=session.population.rng,
        log_callback=print_trace,
        config=config,
        provide_starter_supplies=False,
    )

    # Display Player & Automation Status
    adena_item = next((i for i in player.inventory.items if i.item_id == 40308 or i.name == "Adena"), None)
    adena_cnt = adena_item.count if adena_item else 0
    weapon_name = player.equipped_weapon.name if player.equipped_weapon else "BareHand"

    print("\nPLAYER")
    print("─────────────────────────────────────────────────────────────────")
    print(f"Name:     {player.name} (Class: Knight)")
    print(f"Level:    Lv {player.level} (EXP: {player.exp})")
    print(f"HP / MP:  {player.hp}/{player.max_hp} HP | {player.mp}/{player.max_mp} MP")
    print(f"Adena:    {adena_cnt}")
    print(f"Position: ({player.x}, {player.y}) Map {player.map_id}")
    print(f"Weapon:   {weapon_name}")

    print("\nAUTOMATION (Helper Profile)")
    print("─────────────────────────────────────────────────────────────────")
    print(f"Profile:         {config.name} (v{config.version})")
    print(f"Potion Rules:    {len(config.potion_rules)} rule(s)")
    for pr in config.potion_rules:
        mode_str = "%" if pr.threshold_mode == "HP_PERCENT" else " HP"
        print(f"  • {pr.item}: when HP < {pr.threshold}{mode_str} (Priority {pr.priority})")
    print(f"Emergency Rules: {len(config.emergency_rules)} rule(s)")
    for er in config.emergency_rules:
        print(f"  • {er.action.item}: when HP <= {er.condition.value}% (Priority {er.priority})")
    print(f"Return to Town:  {config.return_to_town.return_method.value} (triggers: {[t.type.value for t in config.return_to_town.triggers]})")
    print(f"Resupply:        NPC {config.resupply.shop_npc_id} (Pandora) - {len(config.resupply.items)} target item(s)")
    print(f"Destination:     {config.hunting.destination.name} (Map {config.hunting.destination.map_id})")

    print("\nACTIVITY / TRACE MONITOR")
    print("─────────────────────────────────────────────────────────────────")
    import time
    start_real = time.time()

    # 5. Run Persistent Autonomous Session
    try:
        result = bot.run_session(max_kills=None, max_virtual_ms=duration_ms, allow_respawn=True)
    except KeyboardInterrupt:
        print("\n\n[!] 玩家手動中斷 (KeyboardInterrupt received) - 正在生成階段結算報告...")
        duration = clock.now()
        result = {
            "reason": "USER_INTERRUPTED",
            "kills": bot.kills,
            "respawns": bot.respawn_count,
            "final_level": bot.player.level,
            "final_exp": bot.player.exp,
            "final_hp": bot.player.hp,
            "max_hp": bot.player.max_hp,
            "virtual_time_ms": duration,
            "damage_dealt": bot.total_damage_dealt,
            "damage_taken": bot.total_damage_taken,
            "items_looted": [f"{item.name} x{item.count}" for item in bot.items_looted],
            "potions_consumed": bot.potions_consumed,
            "emergency_returns": bot.emergency_escapes,
            "town_visits": bot.town_visits,
            "shop_purchases": bot.shop_purchases,
            "adena_earned": bot.adena_earned,
            "adena_spent": bot.adena_spent,
            "loot_picked": len(bot.items_looted),
            "maps_traversed": bot.maps_traversed,
            "hunt_cycles": bot.hunt_cycles,
            "resupply_cycles": bot.resupply_cycles,
            "player_operations": dict(bot.operations_count),
            "trace_log": bot.trace_log,
        }

    elapsed_real = time.time() - start_real
    speedup = (result["virtual_time_ms"] / 1000.0) / max(0.001, elapsed_real)

    # 6. Display Final Summary
    net_adena = result["adena_earned"] - result["adena_spent"]
    print("\n=================================================================")
    print("                   HEADLESS PLAYER RUNTIME SUMMARY               ")
    print("=================================================================")
    print(f"Simulation Result:  {result['reason']}")
    print(f"Virtual Duration:   {result['virtual_time_ms']} ms ({result['virtual_time_ms']/60000:.1f} mins) [Elapsed: {elapsed_real:.2f}s, {speedup:.1f}x]")
    print(f"Monsters Slain:     {result['kills']}")
    print(f"Deaths / Respawns:  {result['respawns']}")
    print(f"Final Level:        Lv {result['final_level']} (EXP: {result['final_exp']})")
    print(f"Final HP / MP:      {result['final_hp']}/{result['max_hp']} HP")
    print(f"Potions Consumed:   {result['potions_consumed']}")
    print(f"Adena Earned:       {result['adena_earned']}")
    print(f"Adena Spent:        {result['adena_spent']}")
    print(f"Net Adena:          {net_adena} ({'PROFIT' if net_adena >= 0 else 'DEFICIT (LEGACY ECONOMY)'})")
    print(f"Town Visits:        {result['town_visits']}")
    print(f"Resupply Cycles:    {result['resupply_cycles']}")
    print(f"Map Transitions:    {result['maps_traversed']}")
    print(f"Looted Items:       {result['loot_picked']} items")

    print("\nPLAYER OPERATIONS EXECUTED:")
    print("─────────────────────────────────────────────────────────────────")
    ops = result.get("player_operations", {})
    if ops:
        for op_name, count in sorted(ops.items()):
            print(f"  {op_name:<20}: {count}")
    else:
        print("  None recorded")
    print("=================================================================")
    return result


# Backward compatibility alias
run_autonomous_mvp = run_headless_player_mvp


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="L1J Headless Player MVP Entrypoint")
    parser.add_argument("--gui", action="store_true", default=False, help="Launch interactive Tkinter GUI (default)")
    parser.add_argument("--headless", "--batch", dest="headless", action="store_true", default=False, help="Run in headless batch mode")
    parser.add_argument("--demo", action="store_true", help="Automated demo (S006/S007 legacy compat)")
    parser.add_argument("--legacy-demo", action="store_true", help="Alias for --demo")
    parser.add_argument("--interactive", action="store_true", help="Interactive text UI mode (legacy compat)")
    parser.add_argument("--s007", action="store_true", help="Use S007 legacy demo")
    parser.add_argument("--kills", type=int, default=1, help="Kill limit for legacy demo (default 1)")
    parser.add_argument("--seed", type=int, default=777777, help="Deterministic PRNG seed override (default 777777)")
    parser.add_argument("--contract", default=None, help="Path to scenario contract JSON (default: scenario_007_contract.json)")
    parser.add_argument("--legacy-root", default=None, help="Path to Eujenz/182c")
    parser.add_argument("--config", default="configs/autonomous_default.json", help="Path to autonomous config JSON")
    parser.add_argument("--duration", type=int, default=None, help="Simulation duration in virtual ms (batch mode, default 600000 = 10m)")
    parser.add_argument("--speed", type=float, default=None, help="Playback speed multiplier for real-time mode (e.g. 5.0)")
    parser.add_argument("--instant", action="store_true", default=False, help="Force instant execution (VirtualClock)")
    parser.add_argument("--verbose", action="store_true", default=True, help="Output real-time trace log")
    args = parser.parse_args()

    is_demo = args.demo or args.legacy_demo

    if is_demo and not args.s007:
        # S006 legacy demo
        contract_path = args.contract or "scenario_006_contract.json"
        session = initialize_s006_session(contract_path, args.legacy_root)
        run_s006_demo(session)
    elif is_demo and args.s007:
        # S007 legacy demo
        contract_path = args.contract or "scenario_007_contract.json"
        clock = VirtualClock(0)
        session = initialize_s007_session(contract_path, args.legacy_root, seed_override=args.seed, clock=clock)
        run_s007_demo(session, kill_limit=args.kills)
    elif args.interactive:
        # S007 interactive mode
        contract_path = args.contract or "scenario_007_contract.json"
        speed = args.speed if args.speed is not None else 1.0
        clock = RealTimeClock(time_scale=speed)
        session = initialize_s007_session(contract_path, args.legacy_root, seed_override=args.seed, clock=clock)
        run_s007_interactive(session)
    elif args.headless or args.instant or (args.duration is not None and not args.gui):
        # Official MVP-05 Headless Player Autonomous Gameplay Entrypoint (Batch / Headless Mode)
        duration_ms = args.duration if args.duration is not None else 600000
        run_headless_player_mvp(
            config_path=args.config,
            contract_path=args.contract,
            seed=args.seed,
            duration_ms=duration_ms,
            speed=args.speed,
            instant=args.instant,
            verbose=args.verbose,
            legacy_root_arg=args.legacy_root,
        )
    else:
        # Official MVP-06 Interactive Headless Player GUI Client (Default)
        from ui.player_window import main as run_player_ui
        run_player_ui(
            config_path=args.config,
            contract_path=args.contract,
            seed=args.seed,
            speed=args.speed if args.speed is not None else 1.0,
            legacy_root=args.legacy_root,
        )


if __name__ == "__main__":
    main()
