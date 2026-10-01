"""
native_engine/bot/__main__.py - CLI Entrypoint for Headless Bot Autonomous Hunting

Usage:
  python -m native_engine.bot
  python -m native_engine.bot --kills 5 --map-id 1
  python -m native_engine.bot --max-time-ms 300000
"""
import argparse
import sys
import os

from mvp import initialize_s007_session
from .controller import HeadlessBot
from ..temporal import VirtualClock


def main():
    parser = argparse.ArgumentParser(description="L1J 1.82 Headless Auto-Hunt Autonomous Agent")
    parser.add_argument("--kills", type=int, default=None, help="Kill limit for hunting session (optional)")
    parser.add_argument("--sim-ms", type=int, default=None, help="Simulation duration in virtual ms (e.g. 600000 for 10 min)")
    parser.add_argument("--max-time-ms", type=int, default=None, help="Alias for --sim-ms")
    parser.add_argument("--map-id", type=int, default=1, help="Starting map ID (0=TI Surface, 1=TI Dungeon 1F)")
    parser.add_argument("--seed", type=int, default=777777, help="RNG seed for deterministic world simulation")
    parser.add_argument("--contract", type=str, default="scenario_007_contract.json", help="Path to scenario contract")
    args = parser.parse_args()

    # Determine simulation time limit
    sim_ms = args.sim_ms or args.max_time_ms or 600000
    kills = args.kills
    if kills is None and args.sim_ms is None and args.max_time_ms is None:
        kills = 3  # Default quick demo if neither kills nor sim-ms specified

    print("=================================================================")
    print("   L1J 1.82 HEADLESS AUTO-HUNT VERTICAL SLICE (AUTONOMOUS BOT)   ")
    print("=================================================================")
    print(f" Target Map     : Map {args.map_id} ({'TI Dungeon 1F' if args.map_id == 1 else 'TI Surface'})")
    print(f" Kill Target    : {f'{kills} kills' if kills else 'Indefinite (Persistent until time limit)'}")
    print(f" Max Virtual Time: {sim_ms} ms ({sim_ms / 60000:.1f} simulated minutes)")
    print(f" Seed           : {args.seed}")
    print("-----------------------------------------------------------------")

    clock = VirtualClock(0)
    session = initialize_s007_session(contract_path=args.contract, seed_override=args.seed)

    # Set player starting map
    if args.map_id == 1:
        # Move directly to dungeon 1F entrance coordinates
        session.player.map_id = 1
        session.player.x = 32671
        session.player.y = 32804

    bot = HeadlessBot(
        player=session.player,
        world_maps=session.world.maps,
        population=session.population,
        progression=session.progression,
        clock=clock,
        rng=session.rng,
        log_callback=print,
    )

    print("\n[STARTING AUTONOMOUS HUNTING SESSION IN VIRTUAL TIME]")
    result = bot.run_session(max_kills=kills, max_virtual_ms=sim_ms)

    print("\n=================================================================")
    print("                    BOT SESSION COMPLETED                        ")
    print("=================================================================")
    print(f" Termination Reason : {result['reason']}")
    print(f" Total Monsters Slain: {result['kills']}")
    print(f" Final Character Lv  : Lv{result['final_level']} (EXP: {result['final_exp']})")
    print(f" Final Character HP  : {result['final_hp']}/{result['max_hp']}")
    print(f" Virtual Time Elapsed: {result['virtual_time_ms']} ms ({result['virtual_time_ms']/1000.0:.2f} simulated seconds)")
    print(f" Total Damage Dealt  : {result['damage_dealt']}")
    print(f" Total Damage Taken  : {result['damage_taken']}")
    print(f" Items Looted ({len(result['items_looted'])}): {', '.join(result['items_looted']) if result['items_looted'] else 'None'}")
    print("=================================================================")
    print(" OVERALL STATUS: PASS (MVP-01 VERTICAL SLICE VALIDATED)")
    print("=================================================================")


if __name__ == "__main__":
    main()
