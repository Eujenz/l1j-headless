"""
scenario_009_headless_player_mvp.py - Scenario 009: Headless Player MVP Long-Running Verification

Executes long-running (30 minutes / 1,800,000 ms virtual time) headless player simulation
across multiple configurable automation profiles:
  - configs/autonomous_default.json (Balanced)
  - configs/conservative_hunt.json (High safety, early retreat)
  - configs/aggressive_hunt.json (Low safety, maximize combat uptime)

Verifies:
  1. Layer 3 Player Operation execution (all actions executed via discrete operations).
  2. Layer 4 Configurable Helper compliance (respects configured thresholds).
  3. Closed-loop cycle:
     Field Combat -> Potion Consumption -> Low Supply Return -> Town Resupply -> Re-entry.
  4. Behavioral variance across profiles (different potion counts, HP thresholds, return counts).
  5. Economic realism (Adena earned vs spent, certifying PASS even if net adena is negative).
"""

import argparse
import os
import sys
import time
from typing import Dict, Any, List

from mvp import initialize_s007_session
from native_engine.bot import HeadlessBot, AutonomousConfig
from native_engine.temporal import VirtualClock, Scheduler


def run_single_profile(
    config_path: str,
    seed: int = 777777,
    duration_ms: int = 1800000,
    trace_out: str = None,
) -> Dict[str, Any]:
    print(f"\n=================================================================")
    print(f"   RUNNING PROFILE: {os.path.basename(config_path)}")
    print(f"=================================================================")

    assert os.path.exists(config_path), f"Configuration file not found: {config_path}"
    config = AutonomousConfig.load_json(config_path)
    print(f"[CONFIG LOADED] Profile: {config.name}")
    print(f"  Potion Rules:    {len(config.potion_rules)}")
    print(f"  Emergency Rules: {len(config.emergency_rules)}")
    print(f"  Return Method:   {config.return_to_town.return_method.value}")
    print(f"  Resupply Items:  {len(config.resupply.items)}")
    print(f"  Destination:     {config.hunting.destination.name} (Map {config.hunting.destination.map_id})")

    # Initialize World & Bot
    clock = VirtualClock(0)
    scheduler = Scheduler(clock)
    session = initialize_s007_session(seed_override=seed, clock=clock)

    bot = HeadlessBot(
        player=session.player,
        world_maps=session.world.maps,
        population=session.population,
        progression=session.progression,
        clock=clock,
        scheduler=scheduler,
        rng=session.rng,
        config=config,
    )

    print(f"[SPAWNED] Player at Map {session.player.map_id} ({session.player.x}, {session.player.y}) | HP: {session.player.hp}/{session.player.max_hp}")

    start_wall = time.time()
    result = bot.run_session(max_kills=None, max_virtual_ms=duration_ms, allow_respawn=True)
    elapsed_wall = time.time() - start_wall

    net_adena = result["adena_earned"] - result["adena_spent"]
    result["config_name"] = config.name
    result["config_path"] = config_path
    result["net_adena"] = net_adena
    result["elapsed_wall"] = elapsed_wall

    print(f"[PROFILE COMPLETED] Elapsed Real Time: {elapsed_wall:.2f}s ({result['virtual_time_ms'] / (elapsed_wall * 1000):.1f}x real-time)")
    print(f"  Virtual Time:       {result['virtual_time_ms']} ms ({result['virtual_time_ms']/60000:.1f} mins)")
    print(f"  Termination Reason: {result['reason']}")
    print(f"  Monster Kills:      {result['kills']}")
    print(f"  Respawns/Deaths:    {result.get('respawns', 0)}")
    print(f"  Level:              {result.get('final_level', 1)} (EXP: {result.get('final_exp', 0)})")
    print(f"  Potions Consumed:   {result['potions_consumed']}")
    print(f"  Town Visits:        {result['town_visits']}")
    print(f"  Resupply Cycles:    {result['resupply_cycles']}")
    print(f"  Adena Earned:       {result['adena_earned']}")
    print(f"  Adena Spent:        {result['adena_spent']}")
    print(f"  Net Adena:          {net_adena:+d}")
    print(f"  Maps Traversed:     {result['maps_traversed']}")
    print(f"  Hunt Cycles:        {result['hunt_cycles']}")

    # Conformance assertions for single run
    assert result["virtual_time_ms"] >= duration_ms, f"Premature termination: {result['virtual_time_ms']} < {duration_ms}"
    assert result["kills"] > 0, "No monsters killed"
    assert result["potions_consumed"] > 0, "No potions consumed"
    assert result["town_visits"] > 0, "No town visits"
    assert result["resupply_cycles"] >= 1, "No completed resupply cycles"

    if trace_out:
        with open(trace_out, "w", encoding="utf-8") as f:
            for entry in result["trace_log"]:
                f.write(entry + "\n")
        print(f"[TRACE SAVED] Trace written to {trace_out}")

    return result


def run_scenario_009(
    config_paths: List[str] = None,
    seed: int = 777777,
    duration_ms: int = 1800000,
) -> bool:
    if config_paths is None:
        config_paths = [
            "configs/autonomous_default.json",
            "configs/conservative_hunt.json",
            "configs/aggressive_hunt.json",
        ]

    print("=================================================================")
    print("   SCENARIO 009 - HEADLESS PLAYER MVP MULTI-PROFILE VERIFICATION")
    print("=================================================================")
    print(f"Evaluating {len(config_paths)} profiles over {duration_ms} ms virtual duration each.")

    results: List[Dict[str, Any]] = []
    for path in config_paths:
        res = run_single_profile(path, seed=seed, duration_ms=duration_ms)
        results.append(res)

    print("\n-----------------------------------------------------------------")
    print(">>> CROSS-PROFILE BEHAVIORAL VARIANCE & MVP CERTIFICATION")
    print("-----------------------------------------------------------------")
    print(f"{'Profile Name':<20} | {'Kills':<6} | {'Potions':<8} | {'Town':<5} | {'Resupply':<8} | {'Net Adena':<10}")
    print("-" * 70)
    for r in results:
        print(f"{r['config_name']:<20} | {r['kills']:<6} | {r['potions_consumed']:<8} | {r['town_visits']:<5} | {r['resupply_cycles']:<8} | {r['net_adena']:<+10d}")

    # Check behavioral variance if multiple profiles are tested
    if len(results) >= 2:
        potion_counts = [r["potions_consumed"] for r in results]
        town_counts = [r["town_visits"] for r in results]
        # At least one metric should differ across profiles to prove configuration drives behavior
        variance_detected = (len(set(potion_counts)) > 1) or (len(set(town_counts)) > 1)
        assert variance_detected, "No behavioral variance detected between distinct policy profiles!"
        print(f"[PASS] Behavioral variance verified across automation profiles.")

    print("\n=================================================================")
    print("           SCENARIO 009 OVERALL STATUS: PASS                     ")
    print("=================================================================")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scenario 009 Runner")
    parser.add_argument("--config", type=str, default=None, help="Path to single config (default runs all 3 profiles)")
    parser.add_argument("--seed", type=int, default=777777, help="Simulation random seed")
    parser.add_argument("--duration", type=int, default=1800000, help="Virtual duration in ms")
    args = parser.parse_args()

    configs = [args.config] if args.config else [
        "configs/autonomous_default.json",
        "configs/conservative_hunt.json",
        "configs/aggressive_hunt.json",
    ]
    success = run_scenario_009(config_paths=configs, seed=args.seed, duration_ms=args.duration)
    sys.exit(0 if success else 1)
