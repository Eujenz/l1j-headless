"""
autonomous.py - L1J 1.82 Configurable Autonomous Player CLI Entrypoint

Executes long-running autonomous gameplay in Native L1J 1.82 World:
  User Config -> Perception -> Policy Evaluation -> Action Intent -> Native World -> Persistent Loop

Usage:
  python autonomous.py --config configs/autonomous_default.json --seed 777777 --duration 1800000 --instant
"""
import argparse
import os
import sys
import time
from typing import Optional

from mvp import initialize_s007_session
from native_engine.bot import HeadlessBot, AutonomousConfig
from native_engine.model import Item
from native_engine.temporal import VirtualClock, Scheduler


def run_autonomous_session(
    config_path: str = "configs/autonomous_default.json",
    seed: int = 777777,
    duration_ms: int = 1800000,
    instant: bool = True,
    speed: float = 1.0,
    verbose: bool = False,
):
    print("=" * 70)
    print(" L1J 1.82 NATIVE HEADLESS RUNTIME - AUTONOMOUS GAMEPLAY")
    print("=" * 70)

    # 1. Load Player Policy Configuration
    if os.path.exists(config_path):
        print(f"Loading autonomous configuration from: {config_path}")
        config = AutonomousConfig.load_json(config_path)
    else:
        print(f"Warning: Configuration file {config_path} not found. Using defaults.")
        config = AutonomousConfig()

    print(f"  Potion Rules: {len(config.potion_rules)} rule(s)")
    for idx, pr in enumerate(config.potion_rules):
        print(f"    [{idx+1}] {pr.item} when HP <= {pr.threshold} ({pr.threshold_mode.value}) (priority: {pr.priority}, enabled: {pr.enabled})")

    print(f"  Emergency Rules: {len(config.emergency_rules)} rule(s)")
    for idx, er in enumerate(config.emergency_rules):
        print(f"    [{idx+1}] Action={er.action.type} Item={er.action.item} when {er.condition.type.value} {er.condition.operator.value} {er.condition.value} (enabled: {er.enabled})")

    print(f"  Return to Town: Enabled={config.return_to_town.enabled}, Method={config.return_to_town.return_method.value}")
    for idx, rt in enumerate(config.return_to_town.triggers):
        print(f"    Trigger [{idx+1}]: {rt.type.value} on {rt.item} < {rt.threshold}")

    print(f"  Resupply: Enabled={config.resupply.enabled}, Shop NPC ID={config.resupply.shop_npc_id}")
    for idx, ri in enumerate(config.resupply.items):
        print(f"    Item [{idx+1}]: {ri.item} (ID {ri.item_id}) -> Target: {ri.target_quantity} (enabled: {ri.enabled})")

    print(f"  Hunting Destination: {config.hunting.destination.name} (Map {config.hunting.destination.map_id})")
    print("-" * 70)

    # 2. Initialize World & Session
    print(f"Initializing World with Seed: {seed}...")
    session = initialize_s007_session(seed_override=seed)
    clock = VirtualClock(0)
    scheduler = Scheduler(clock)

    # Place player at dungeon entrance or configured map
    dest = config.hunting.destination
    session.player.map_id = dest.map_id
    session.player.x = dest.target_x
    session.player.y = dest.target_y

    def log_callback(msg: str):
        if verbose:
            print(msg)

    bot = HeadlessBot(
        player=session.player,
        world_maps=session.world.maps,
        population=session.population,
        progression=session.progression,
        clock=clock,
        scheduler=scheduler,
        rng=session.rng,
        log_callback=log_callback,
        config=config,
    )

    print(f"Starting Autonomous Loop for {duration_ms} ms virtual time ({duration_ms / 60000:.1f} simulated minutes)...")
    real_start_time = time.time()

    # 3. Run Autonomous Loop
    result = bot.run_session(max_kills=None, max_virtual_ms=duration_ms, allow_respawn=True)
    real_elapsed = time.time() - real_start_time

    # 4. Report Metrics & Results
    print("\n" + "=" * 70)
    print(" AUTONOMOUS SIMULATION METRICS REPORT")
    print("=" * 70)
    print(f"  Termination Reason:     {result['reason']}")
    print(f"  Virtual Time Elapsed:   {result['virtual_time_ms']} ms ({result['virtual_time_ms'] / 60000:.2f} mins)")
    print(f"  Wall-Clock Time:        {real_elapsed:.2f} seconds")
    if real_elapsed > 0:
        print(f"  Time Acceleration:      {result['virtual_time_ms'] / (real_elapsed * 1000):.1f}x real-time")
    print(f"  Monster Kills:          {result['kills']}")
    print(f"  Player Deaths/Respawns: {result['respawns']}")
    print(f"  Final Character Level:  Lv{result['final_level']} (EXP: {result['final_exp']})")
    print(f"  Final Character HP:     {result['final_hp']}/{result['max_hp']}")
    print(f"  Total Damage Dealt:     {result['damage_dealt']}")
    print(f"  Total Damage Taken:     {result['damage_taken']}")
    print(f"  Potions Consumed:       {result['potions_consumed']}")
    print(f"  Emergency Returns:      {result['emergency_returns']}")
    print(f"  Town Visits:            {result['town_visits']}")
    print(f"  Shop Purchases:         {result['shop_purchases']}")
    print(f"  Resupply Cycles:        {result['resupply_cycles']}")
    print(f"  Adena Earned:           {result['adena_earned']}")
    print(f"  Adena Spent:            {result['adena_spent']}")
    print(f"  Loot Items Picked:      {result['loot_picked']}")
    print(f"  Maps Traversed:         {result['maps_traversed']}")
    print(f"  Hunt Cycles:            {result['hunt_cycles']}")
    print("=" * 70)

    return result


def main():
    parser = argparse.ArgumentParser(description="L1J 1.82 Configurable Autonomous Player")
    parser.add_argument("--config", type=str, default="configs/autonomous_default.json", help="Path to config JSON")
    parser.add_argument("--seed", type=int, default=777777, help="RNG seed")
    parser.add_argument("--duration", type=int, default=1800000, help="Simulation duration in virtual ms (default: 1800000 = 30 min)")
    parser.add_argument("--instant", action="store_true", default=True, help="Execute at maximum virtual speed")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier if not instant")
    parser.add_argument("--verbose", action="store_true", help="Print all event log messages")
    args = parser.parse_args()

    run_autonomous_session(
        config_path=args.config,
        seed=args.seed,
        duration_ms=args.duration,
        instant=args.instant,
        speed=args.speed,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
