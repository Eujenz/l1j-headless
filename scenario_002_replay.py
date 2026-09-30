"""
scenario_002_replay.py - Scenario 002 Conformance Verifier & Replay Driver.
Tests Movement Geometry, Collision Arbitration, and Autonomous Navigation.
"""
import json
import os
import sys
from dataclasses import dataclass
from typing import List

from native_engine.map import WorldMapGrid
from native_engine.movement import MovementEngine, can_move, HEADING_DELTA
from native_engine.navigation import AutonomousNavigator, AStarPlanner
from native_engine.events import DomainEvent

@dataclass
class ReplayActor:
    id: int
    name: str
    x: int
    y: int
    heading: int

def run_replay(contract_path: str = "scenario_002_contract.json", trace_out: str = "native_trace_002.jsonl"):
    with open(contract_path, "r", encoding="utf-8") as f:
        contract = json.load(f)

    print("=================================================================")
    print("      MODERN REPLAY 002 - NATIVE COMPATIBILITY SIMULATOR")
    print("=================================================================")
    print(f"[CONTRACT LOADED] Scenario: {contract['scenario_id']} (Fixture v{contract['fixture_version']})")
    print(f"                 Scope:    {contract['scope']}")
    print(f"                 Source:   {contract['source']}")

    cmap = contract["map"]
    grid = WorldMapGrid(
        map_id=cmap["map_id"],
        loc_x1=cmap["loc_x1"],
        loc_y1=cmap["loc_y1"],
        width=cmap["width"],
        height=cmap["height"]
    )
    for tile in cmap["tiles"]:
        grid.set_tile(tile["x"], tile["y"], tile["val"])

    engine = MovementEngine(grid)
    test_cases = contract["test_cases"]

    trace_records = []
    seq = 0

    # Phase 1: L1 Movement State & Geometry Audit (Cases 1 - 12)
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 1: L1 MOVEMENT STATE & GEOMETRY CONFORMANCE")
    print("-----------------------------------------------------------------")
    l1_pass = True
    l2_pass = True

    for tc in test_cases:
        if tc["type"] == "COLLISION":
            cid = tc["case_id"]
            name = tc["name"]
            sx, sy, d = tc["x"], tc["y"], tc["dir"]
            expected_pass = tc["expected_passable"]

            # Independent Native Evaluation
            native_pass, reason = can_move(grid, sx, sy, d)

            if native_pass != expected_pass:
                print(f"[FAIL] Case {cid} ({name}): Expected pass={expected_pass}, got native={native_pass} ({reason})")
                l1_pass = False
                break

            # Execute via MovementEngine
            actor = ReplayActor(id=1000 + cid, name=f"Actor_{cid}", x=sx, y=sy, heading=0)
            events = engine.execute_cmd_move(actor, d, tick=100 + cid * 10)

            # Audit State Mutation
            if expected_pass:
                dx, dy = HEADING_DELTA[d]
                expected_x = sx + dx
                expected_y = sy + dy
                if actor.x != expected_x or actor.y != expected_y or actor.heading != d:
                    print(f"[FAIL] Case {cid} ({name}): State mismatch! Expected ({expected_x},{expected_y}), got ({actor.x},{actor.y})")
                    l1_pass = False
                    break
                # Event audit: MoveAccepted and PositionChanged
                has_accepted = any(ev.__class__.__name__ == 'MoveAccepted' for ev in events)
                has_pos_changed = any(ev.__class__.__name__ == 'PositionChanged' for ev in events)
                if not (has_accepted and has_pos_changed):
                    print(f"[FAIL] Case {cid} ({name}): Missing expected MoveAccepted/PositionChanged events!")
                    l2_pass = False
                    break
            else:
                if actor.x != sx or actor.y != sy:
                    print(f"[FAIL] Case {cid} ({name}): Blocked move mutated actor position!")
                    l1_pass = False
                    break
                has_blocked = any(ev.__class__.__name__ == 'MoveBlocked' for ev in events)
                if not has_blocked:
                    print(f"[FAIL] Case {cid} ({name}): Missing expected MoveBlocked event!")
                    l2_pass = False
                    break

            for ev in events:
                seq += 1
                trace_records.append({
                    "seq": seq,
                    "tick": ev.tick,
                    "channel": "OUTPUT",
                    "record_type": "DOMAIN_EVENT",
                    "name": ev.__class__.__name__,
                    "payload": ev.__dict__
                })
            print(f"  [PASS] Case {cid:02d} ({name:26s}) -> Passable={native_pass!s:5s} Reason={reason:15s}")

    assert l1_pass, "Phase 1 Conformance Failed!"
    print("[PASS] All 12 single-step movement cases match 100% with Legacy Geometry Contract.")

    # Phase 2: L2 Movement Events Audit
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 2: L2 MOVEMENT DOMAIN EVENT SEQUENCE AUDIT")
    print("-----------------------------------------------------------------")
    assert l2_pass, "Phase 2 Conformance Failed!"
    print(f"[PASS] Emitted {len(trace_records)} valid movement domain events (MoveAttempted/MoveAccepted/MoveBlocked/PositionChanged).")

    # Phase 3: L3 Autonomous Navigation Outcome (Cases 13 & 14)
    print("\n-----------------------------------------------------------------")
    print(">>> PHASE 3: L3 AUTONOMOUS NAVIGATION OUTCOME")
    print("-----------------------------------------------------------------")
    l3_pass = True
    nav_cases = [tc for tc in test_cases if tc["type"] == "NAVIGATION"]

    for tc in nav_cases:
        cid = tc["case_id"]
        name = tc["name"]
        sx, sy = tc["start"]["x"], tc["start"]["y"]
        tx, ty = tc["target"]["x"], tc["target"]["y"]

        nav_actor = ReplayActor(id=2000 + cid, name=f"NavActor_{cid}", x=sx, y=sy, heading=0)
        success, nav_events = AutonomousNavigator.goto(nav_actor, tx, ty, engine, start_tick=200 + cid * 20)

        if not success:
            print(f"[FAIL] Case {cid} ({name}): Autonomous navigation failed to reach target ({tx}, {ty})!")
            l3_pass = False
            break

        if nav_actor.x != tx or nav_actor.y != ty:
            print(f"[FAIL] Case {cid} ({name}): Actor stopped at ({nav_actor.x}, {nav_actor.y}), expected ({tx}, {ty})")
            l3_pass = False
            break

        has_reached = any(ev.__class__.__name__ == 'DestinationReached' for ev in nav_events)
        if not has_reached:
            print(f"[FAIL] Case {cid} ({name}): DestinationReached event not emitted!")
            l3_pass = False
            break

        for ev in nav_events:
            seq += 1
            trace_records.append({
                "seq": seq,
                "tick": ev.tick,
                "channel": "OUTPUT",
                "record_type": "DOMAIN_EVENT",
                "name": ev.__class__.__name__,
                "payload": ev.__dict__
            })

        print(f"  [PASS] Case {cid:02d} ({name:20s}) -> Start=({sx},{sy}) Target=({tx},{ty}) Steps={len(nav_events)//2} Reached=True")

    assert l3_pass, "Phase 3 Conformance Failed!"
    print("[PASS] Autonomous navigation successfully routed direct paths and circumnavigated static wall obstacles.")

    # Write Native Trace
    with open(trace_out, "w", encoding="utf-8") as f:
        for r in trace_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n[TRACE ARTIFACT] Written {len(trace_records)} native events to {trace_out}")

    print("\n=================================================================")
    print("               FINAL REPLAY CONFORMANCE VERDICT")
    print("=================================================================")
    print("  L1 Movement State      PASS")
    print("  L2 Movement Events     PASS")
    print("  L3 Navigation Outcome  PASS")
    print("=================================================================")
    print("               >>>  OVERALL STATUS: PASS  <<<")
    print("=================================================================")

if __name__ == '__main__':
    run_replay()
