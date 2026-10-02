"""
scenario_008_configurable_autonomous_hunting.py - Scenario 008 Replay & Verification

Scenario 008: Configurable Autonomous Hunting & Town Resupply Cycle
Scope:
  - Long-Running Autonomous Gameplay: 30 minutes (1,800,000 ms) in Virtual Time.
  - Strict separation of World Rules vs Player Autonomous Policy.
  - Autonomous closed loop:
      Field Hunting
        ↓
      Configured Potion Rules (Threshold % / Absolute)
        ↓
      Loot & Adena Accumulation
        ↓
      Supply Depletion & Low Potion Trigger
        ↓
      Emergency / Town Return (Escape Scroll)
        ↓
      Talking Island Town Navigation
        ↓
      Pandora NPC Shop Interaction (Target Quantities & Adena Deduction)
        ↓
      Surface Navigation to Dungeon Portal
        ↓
      Cross-Map Transition (Map 0 -> Map 1)
        ↓
      Dungeon Re-Entry & Resume Hunting
        ↓
      Repeat (>= 1 Full Resupply Cycle)
"""
import argparse
import os
import sys
import time

from mvp import initialize_s007_session
from native_engine.bot import HeadlessBot, AutonomousConfig
from native_engine.model import Item, Position
from native_engine.temporal import VirtualClock, Scheduler


def run_scenario_008(
    config_path: str = "configs/autonomous_default.json",
    seed: int = 777777,
    duration_ms: int = 1800000,
    trace_out: str = "scenario_008_trace.jsonl",
) -> bool:
    print("=================================================================")
    print("   SCENARIO 008 - CONFIGURABLE AUTONOMOUS HUNTING & RESUPPLY")
    print("=================================================================")

    # 1. Load Autonomous Configuration
    assert os.path.exists(config_path), f"Config file not found: {config_path}"
    config = AutonomousConfig.load_json(config_path)
    print(f"[CONFIG LOADED] Loaded policy profile from: {config_path}")
    print(f"  Potion Rules:    {len(config.potion_rules)}")
    print(f"  Emergency Rules: {len(config.emergency_rules)}")
    print(f"  Return Method:   {config.return_to_town.return_method.value}")
    print(f"  Resupply Items:  {len(config.resupply.items)}")
    print(f"  Destination:     {config.hunting.destination.name} (Map {config.hunting.destination.map_id})")

    # 2. Initialize World & Headless Bot
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 1: INITIALIZE WORLD & HEADLESS PLAYER AGENT")
    print("-----------------------------------------------------------------")
    session = initialize_s007_session(seed_override=seed)
    clock = VirtualClock(0)
    scheduler = Scheduler(clock)

    # Position player at configured hunting destination
    dest = config.hunting.destination
    session.player.map_id = dest.map_id
    session.player.x = dest.target_x
    session.player.y = dest.target_y

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

    print(f"[PASS] HeadlessBot spawned at Map {session.player.map_id} ({session.player.x}, {session.player.y}) with HP: {session.player.hp}/{session.player.max_hp}")

    # 3. Execute 30-Minute Virtual Simulation
    print("\n-----------------------------------------------------------------")
    print(f">>> PHASE 2: RUN PERSISTENT AUTONOMOUS CYCLE ({duration_ms} ms / {duration_ms/60000:.1f} mins)")
    print("-----------------------------------------------------------------")
    start_wall = time.time()
    result = bot.run_session(max_kills=None, max_virtual_ms=duration_ms, allow_respawn=True)
    elapsed_wall = time.time() - start_wall

    print(f"[SIMULATION COMPLETED] Elapsed Real Time: {elapsed_wall:.2f}s ({result['virtual_time_ms'] / (elapsed_wall * 1000):.1f}x real-time)")
    print(f"  Virtual Time:       {result['virtual_time_ms']} ms")
    print(f"  Termination Reason: {result['reason']}")
    print(f"  Monster Kills:      {result['kills']}")
    print(f"  Potions Consumed:   {result['potions_consumed']}")
    print(f"  Emergency Returns:  {result['emergency_returns']}")
    print(f"  Town Visits:        {result['town_visits']}")
    print(f"  Shop Purchases:     {result['shop_purchases']}")
    print(f"  Resupply Cycles:    {result['resupply_cycles']}")
    print(f"  Adena Earned:       {result['adena_earned']}")
    print(f"  Adena Spent:        {result['adena_spent']}")
    print(f"  Maps Traversed:     {result['maps_traversed']}")
    print(f"  Hunt Cycles:        {result['hunt_cycles']}")

    # 4. Conformance & Success Verification
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 3: SCENARIO 008 CONFORMANCE & VERIFICATION")
    print("-----------------------------------------------------------------")

    # A. Time-based termination
    assert result["virtual_time_ms"] >= duration_ms, f"Simulation ended prematurely at {result['virtual_time_ms']} ms"
    print(f"[PASS] Virtual duration requirement met: {result['virtual_time_ms']} >= {duration_ms} ms.")

    # B. Kills & progression
    assert result["kills"] > 0, "No monsters killed during 30-minute simulation"
    print(f"[PASS] Monster combat executed: {result['kills']} monsters slain.")

    # C. Potion rules executed
    assert result["potions_consumed"] > 0, "No potions consumed according to configured rules"
    print(f"[PASS] Potion rules actively executed: {result['potions_consumed']} potions consumed.")

    # D. Town visits & Escape Scroll
    assert result["town_visits"] > 0, "Bot never visited town"
    print(f"[PASS] Town return cycle executed: {result['town_visits']} town visits.")

    # E. Pandora Shop Purchases & Resupply
    assert result["shop_purchases"] > 0, "No shop purchases executed"
    assert result["resupply_cycles"] >= 1, f"Expected at least 1 resupply cycle, got {result['resupply_cycles']}"
    print(f"[PASS] Town resupply cycle certified: {result['resupply_cycles']} full cycle(s) with {result['shop_purchases']} purchases ({result['adena_spent']} adena spent).")

    # F. Cross-map navigation & re-entry
    assert result["maps_traversed"] >= 2, f"Expected cross-map traversals, got {result['maps_traversed']}"
    assert result["hunt_cycles"] >= 1, f"Expected return to hunting grounds, got {result['hunt_cycles']}"
    print(f"[PASS] Bi-directional cross-map travel verified: {result['maps_traversed']} map transitions, {result['hunt_cycles']} hunting re-entries.")

    # G. Write trace file
    with open(trace_out, "w", encoding="utf-8") as f:
        for entry in result["trace_log"]:
            f.write(entry + "\n")
    print(f"[PASS] Execution trace saved to: {trace_out}")

    print("\n=================================================================")
    print("           SCENARIO 008 OVERALL STATUS: PASS                     ")
    print("=================================================================")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scenario 008 Runner")
    parser.add_argument("--config", type=str, default="configs/autonomous_default.json")
    parser.add_argument("--seed", type=int, default=777777)
    parser.add_argument("--duration", type=int, default=1800000)
    args = parser.parse_args()

    success = run_scenario_008(config_path=args.config, seed=args.seed, duration_ms=args.duration)
    sys.exit(0 if success else 1)
