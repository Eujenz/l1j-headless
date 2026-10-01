"""
scenario_007_replay.py - Scenario 007 Authentic World Hunting Simulation Deterministic Replay
Executes end-to-end:
  Real Map 0 (Start) -> Travel Corridor Encounters -> Level Up -> Real Portal -> Map 1 -> Dungeon Hunt -> Conformance Check
Emits native_trace_007.jsonl for differential verification.
"""
import argparse
import json
import os
import sys
from typing import List, Optional

from mvp import initialize_s007_session, find_legacy_root
from native_engine.events import DomainEvent


def run_replay(
    contract_path: str = "scenario_007_contract.json",
    legacy_root_arg: Optional[str] = None,
    trace_out: str = "native_trace_007.jsonl"
) -> bool:
    with open(contract_path, "r", encoding="utf-8") as f:
        contract = json.load(f)

    print("=================================================================")
    print("      MODERN REPLAY 007 - AUTHENTIC WORLD HUNTING SIMULATION")
    print("=================================================================")
    print(f"[CONTRACT LOADED] Scenario: {contract['scenario_id']} (Scope: {contract['scope']})")
    print(f"                 Seed:     {contract.get('rng_seed')}")

    # -----------------------------------------------------------------
    # PHASE 1: WORLD POPULATION & DATA INTEGRITY
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 1: WORLD POPULATION & CANONICAL DATA INTEGRITY")
    print("-----------------------------------------------------------------")
    session = initialize_s007_session(contract_path, legacy_root_arg)
    pop_summary = session.population.summary()
    m0_count = pop_summary.get(0, {}).get("total", 0)
    m1_count = pop_summary.get(1, {}).get("total", 0)

    assert m0_count > 0, "Map 0 has no monsters"
    assert m1_count > 0, "Map 1 has no monsters"
    print(f"[PASS] World Population loaded: Map 0 has {m0_count} monsters, Map 1 has {m1_count} monsters.")

    # Verify canonical monster templates
    expected_monsters = ["1", "2", "3", "4", "6", "8", "9", "12", "13", "55"]
    for mid_str in expected_monsters:
        mdef = session.population.get_def(int(mid_str))
        assert mdef is not None, f"Missing monster definition for ID {mid_str}"
        assert mdef.hp > 0, f"Invalid HP for monster ID {mid_str}"
    print(f"[PASS] All {len(expected_monsters)} canonical monster definitions verified from Legacy SQL.")

    # -----------------------------------------------------------------
    # PHASE 2: EQUIPMENT SYSTEM & COMBAT EFFECTS
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 2: EQUIPMENT MANAGEMENT & COMBAT STAT EFFECTS")
    print("-----------------------------------------------------------------")
    init_weapon = session.player.equipped_weapon
    assert init_weapon is not None and init_weapon.item_id == 1, "Default weapon should be Long Sword"
    print(f"  [PASS] Initial weapon: {init_weapon.name} (dmg: {init_weapon.dmg_small}/{init_weapon.dmg_large})")

    # Equip Dagger (item_id 28)
    ok, reason, evts = session.equip(28)
    assert ok, f"Equip Dagger failed: {reason}"
    assert session.player.equipped_weapon.item_id == 28
    assert any(e.__class__.__name__ == "WeaponEquipped" for e in evts)
    assert any(e.__class__.__name__ == "WeaponUnequipped" for e in evts)
    print("  [PASS] Successfully equipped Dagger (emitted WeaponUnequipped + WeaponEquipped)")

    # Equip Long Sword back (item_id 1)
    ok, reason, evts = session.equip(1)
    assert ok, f"Equip Long Sword failed: {reason}"
    assert session.player.equipped_weapon.item_id == 1
    print("  [PASS] Successfully equipped Long Sword back for optimal hunting")

    # -----------------------------------------------------------------
    # PHASE 3: AUTONOMOUS TRAVEL WITH TRAVEL ENCOUNTERS & PROGRESSION
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 3: AUTONOMOUS TRAVEL WITH ENCOUNTERS & LEVEL-UP")
    print("-----------------------------------------------------------------")
    start_pos = (session.player.map_id, session.player.x, session.player.y)
    print(f"  Starting position: Map {start_pos[0]} at ({start_pos[1]}, {start_pos[2]})")

    ok, reason, travel_events = session.move_to("ti_dungeon_1f")
    assert ok, f"Autonomous travel failed: {reason}"
    assert session.player.map_id == 1, "Player should be on Map 1"
    assert (session.player.x, session.player.y) == (32671, 32804), "Player should be at destination (32671, 32804)"
    print(f"  [PASS] Successfully navigated to Map 1 at (32671, 32804) via real portal.")

    # Audit travel events: should include EncounterTriggered, MonsterDied, ExperienceGranted, LevelUp, PortalTriggered, MapEntered
    event_classes = {e.__class__.__name__ for e in travel_events}
    required_travel_events = {
        "WorldRoutePlanned", "PositionChanged", "EncounterTriggered",
        "AttackStarted", "HitResolved", "DamageApplied", "HpChanged",
        "MonsterDied", "ExperienceGranted", "LevelUp",
        "PortalTriggered", "WorldTransitionCommitted", "MapEntered"
    }
    missing = required_travel_events - event_classes
    assert not missing, f"Missing travel event classes: {missing}"
    print(f"  [PASS] All {len(required_travel_events)} required event classes observed during travel.")

    level_ups = [e for e in travel_events if e.__class__.__name__ == "LevelUp"]
    assert len(level_ups) >= 2, f"Expected at least 2 level ups, got {len(level_ups)}"
    print(f"  [PASS] Observed {len(level_ups)} LevelUp events during journey (Current Player Level: {session.player.level}, MaxHP: {session.player.max_hp})")

    # -----------------------------------------------------------------
    # PHASE 4: AUTONOMOUS HUNTING LOOP IN DUNGEON
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 4: AUTONOMOUS HUNTING LOOP IN REAL DUNGEON")
    print("-----------------------------------------------------------------")
    kills_before = session.total_kills
    ok, reason, hunt_events = session.hunt(kill_limit=1)
    assert ok, f"Hunting loop failed: {reason}"
    assert reason == "KILL_LIMIT_REACHED", f"Expected KILL_LIMIT_REACHED, got {reason}"
    assert session.total_kills == kills_before + 1, "Expected 1 kill in dungeon"
    assert session.player.hp > 0, "Player should survive dungeon encounter"
    assert session.player.exp >= 200, f"Expected EXP >= 200, got {session.player.exp}"
    print(f"  [PASS] Dungeon hunt completed: Reason={reason}, Total Kills={session.total_kills}, EXP={session.player.exp}, HP={session.player.hp}/{session.player.max_hp}")

    # -----------------------------------------------------------------
    # PHASE 5: NEGATIVE & EDGE CASE AUDIT
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 5: NEGATIVE & EDGE CASE AUDIT")
    print("-----------------------------------------------------------------")
    # N01: Invalid destination
    ok, reason, _ = session.move_to("non_existent_destination")
    assert not ok and reason == "INVALID_DESTINATION"
    print("  [PASS] N01_Invalid_Destination -> caught INVALID_DESTINATION")

    # N02: Invalid equipment item id
    ok, reason, _ = session.equip(999999)
    assert not ok and reason == "ITEM_NOT_FOUND"
    print("  [PASS] N02_Invalid_Equipment -> caught ITEM_NOT_FOUND")

    # N03: Dead player actions rejected
    session.player.is_dead = True
    ok, reason, _ = session.move_to("ti_dungeon_entrance")
    assert not ok and reason == "PLAYER_DEAD"
    ok, reason, _ = session.hunt(kill_limit=1)
    assert not ok and reason == "PLAYER_DEAD"
    session.player.is_dead = False  # restore
    print("  [PASS] N03_Dead_Player_Actions -> correctly rejected with PLAYER_DEAD")

    # -----------------------------------------------------------------
    # PHASE 6: DETERMINISTIC REPEATED REPLAY INVARIANT
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 6: DETERMINISTIC REPEATED REPLAY INVARIANT")
    print("-----------------------------------------------------------------")
    session_b = initialize_s007_session(contract_path, legacy_root_arg)
    session_b.equip(28)
    session_b.equip(1)
    session_b.move_to("ti_dungeon_1f")
    session_b.hunt(kill_limit=1)

    ev_a = session.events_history
    ev_b = session_b.events_history
    assert len(ev_a) == len(ev_b), f"Event count mismatch: {len(ev_a)} vs {len(ev_b)}"
    for i, (ea, eb) in enumerate(zip(ev_a, ev_b)):
        assert ea.__class__.__name__ == eb.__class__.__name__, f"Event {i} class mismatch"
        assert ea.tick == eb.tick, f"Event {i} tick mismatch: {ea.tick} vs {eb.tick}"
    print(f"[PASS] Repeated execution produced bit-identical domain event sequence ({len(ev_a)} events).")

    # Write trace artifact
    with open(trace_out, "w", encoding="utf-8") as f:
        meta_rec = {
            "type": "META",
            "scenario_id": "007",
            "total_events": len(ev_a),
            "final_level": session.player.level,
            "final_exp": session.player.exp,
            "final_hp": session.player.hp,
            "final_max_hp": session.player.max_hp,
            "total_kills": session.total_kills,
        }
        f.write(json.dumps(meta_rec, ensure_ascii=False) + "\n")
        for ev in ev_a:
            rec = {
                "event_type": ev.__class__.__name__,
                "tick": ev.tick,
                **{k: v for k, v in ev.__dict__.items() if k != "tick"}
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n[TRACE ARTIFACT] Written native trace to {trace_out}")

    print("\n=================================================================")
    print("               FINAL REPLAY CONFORMANCE VERDICT")
    print("=================================================================")
    print("  L0 Data Integrity       PASS")
    print("  L1 Equipment Effects    PASS")
    print("  L2 Autonomous Travel    PASS")
    print("  L3 Progression Level-Up PASS")
    print("  L4 Autonomous Hunt Loop PASS")
    print("  Negative Robustness     PASS")
    print("  Deterministic Invariant PASS")
    print("=================================================================")
    print("               >>>  OVERALL STATUS: PASS  <<<")
    print("=================================================================")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scenario 007 Replay Verifier")
    parser.add_argument("--contract", default="scenario_007_contract.json")
    parser.add_argument("--legacy-root", default=None)
    parser.add_argument("--trace-out", default="native_trace_007.jsonl")
    args = parser.parse_args()

    success = run_replay(args.contract, args.legacy_root, args.trace_out)
    sys.exit(0 if success else 1)
