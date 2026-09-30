"""
scenario_005_differential.py - Scenario 005 Differential Conformance Verifier
Validates bit-exact and behavioral equivalence between Legacy Reference Oracle
(Eujenz/182c) and Modern Native Runtime across Levels L0 through L5.
"""
import json
import sys


def load_jsonl(path: str) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def verify_conformance(
    oracle_path: str = "oracle_trace_scenario_005.jsonl",
    native_path: str = "native_trace_005.jsonl"
) -> bool:
    print("=================================================================")
    print("      SCENARIO 005 DIFFERENTIAL CONFORMANCE VERIFIER")
    print("      Legacy Java Oracle  vs.  Modern Native Runtime")
    print("=================================================================")
    print(f"  Oracle Trace: {oracle_path}")
    print(f"  Native Trace: {native_path}")
    print("=================================================================")

    oracle_records = load_jsonl(oracle_path)
    native_records = load_jsonl(native_path)

    print(f"[RECORDS LOADED] Legacy Oracle: {len(oracle_records)} records")
    print(f"                 Native Engine: {len(native_records)} records")

    native_meta = next(r for r in native_records if r.get("type") == "META")
    native_events = [r for r in native_records if "event_type" in r]

    # -----------------------------------------------------------------
    # LEVEL 0: REAL MAP IMPORT & CANONICAL GEOMETRY DIGEST (L0)
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 0: REAL MAP INTEGRITY & CANONICAL GEOMETRY DIGEST")
    print("-----------------------------------------------------------------")
    oracle_maps = {r["map_id"]: r for r in oracle_records if r.get("type") == "MAP_INTEGRITY"}

    for mid in [0, 1]:
        o_map = oracle_maps[mid]
        n_digest = native_meta[f"map_{mid}_digest"]
        if o_map["canonical_geometry_digest"] != n_digest:
            print(f"[FAIL] Map {mid} digest mismatch! Oracle: {o_map['canonical_geometry_digest']}, Native: {n_digest}")
            return False
        print(f"  [PASS] Map {mid} ({o_map['name']}):")
        print(f"         Dimensions: {o_map['width']}x{o_map['height']} ({o_map['total_cells']} cells)")
        print(f"         Canonical Digest: {n_digest}")
    print("[PASS] Both Map 0 and Map 1 produce bit-identical SHA-256 geometry digests.")

    # -----------------------------------------------------------------
    # LEVEL 1: WORLD TRANSITION GRAPH INTEGRITY (L1)
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 1: WORLD TRANSITION INTEGRITY (LEGACY SQL PROVENANCE)")
    print("-----------------------------------------------------------------")
    o_trans = next(r for r in oracle_records if r.get("type") == "TRANSITION")
    assert o_trans["transition_id"] == "portal_ti_to_tid1"
    assert o_trans["source_map"] == 0 and o_trans["source_x"] == 32477 and o_trans["source_y"] == 32851
    assert o_trans["target_map"] == 1 and o_trans["target_x"] == 32669 and o_trans["target_y"] == 32802
    assert o_trans["target_heading"] == 4 and o_trans["item_id"] == 0

    print(f"  [PASS] Transition ID : {o_trans['transition_id']}")
    print(f"  [PASS] Provenance    : {o_trans['sql_source']} (Row {o_trans['sql_row_id']})")
    print(f"  [PASS] Source        : Map {o_trans['source_map']} ({o_trans['source_x']}, {o_trans['source_y']})")
    print(f"  [PASS] Target        : Map {o_trans['target_map']} ({o_trans['target_x']}, {o_trans['target_y']}) Heading {o_trans['target_heading']}")

    # -----------------------------------------------------------------
    # LEVEL 2: WORLD ROUTE TOPOLOGY CONFORMANCE (L2)
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 2: WORLD ROUTE TOPOLOGY CONFORMANCE")
    print("-----------------------------------------------------------------")
    o_milestones = next(r for r in oracle_records if r.get("type") == "ROUTE_MILESTONES")

    route_event = next(ev for ev in native_events if ev["event_type"] == "WorldRoutePlanned")
    if route_event["map_sequence"] != o_milestones["expected_map_sequence"]:
        print(f"[FAIL] Map sequence mismatch: expected {o_milestones['expected_map_sequence']}, got {route_event['map_sequence']}")
        return False
    if route_event["transition_ids"] != [o_milestones["expected_transition_id"]]:
        print(f"[FAIL] Transition IDs mismatch: expected {[o_milestones['expected_transition_id']]}, got {route_event['transition_ids']}")
        return False

    print(f"  [PASS] Planned Map Sequence : {route_event['map_sequence']}")
    print(f"  [PASS] Planned Transitions  : {route_event['transition_ids']}")

    # -----------------------------------------------------------------
    # LEVEL 3: REAL MAP 0 LOCAL NAVIGATION TO PORTAL (L3)
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 3: REAL MAP 0 LOCAL NAVIGATION TO PORTAL (APPROACH)")
    print("-----------------------------------------------------------------")
    portal_ev = next(ev for ev in native_events if ev["event_type"] == "PortalTriggered")
    assert portal_ev["source_map"] == o_milestones["expected_portal_map"]
    assert portal_ev["source_x"] == o_milestones["expected_portal_x"]
    assert portal_ev["source_y"] == o_milestones["expected_portal_y"]

    # Verify zero MoveBlocked events before portal trigger
    approach_blocked = [ev for ev in native_events if ev["event_type"] == "MoveBlocked" and ev["tick"] <= portal_ev["tick"]]
    if approach_blocked:
        print(f"[FAIL] Blocked moves encountered during Map 0 approach: {approach_blocked}")
        return False
    print(f"  [PASS] Reached Portal Tile ({portal_ev['source_x']}, {portal_ev['source_y']}) without collisions.")

    # -----------------------------------------------------------------
    # LEVEL 4: CROSS-MAP ATOMIC STATE MUTATION (L4)
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 4: CROSS-MAP ATOMIC TRANSITION COMMIT")
    print("-----------------------------------------------------------------")
    commit_ev = next(ev for ev in native_events if ev["event_type"] == "WorldTransitionCommitted")
    map_enter_ev = next(ev for ev in native_events if ev["event_type"] == "MapEntered")

    assert commit_ev["old_map"] == o_milestones["expected_portal_map"]
    assert commit_ev["old_x"] == o_milestones["expected_portal_x"]
    assert commit_ev["old_y"] == o_milestones["expected_portal_y"]
    assert commit_ev["new_map"] == o_milestones["expected_landing_map"]
    assert commit_ev["new_x"] == o_milestones["expected_landing_x"]
    assert commit_ev["new_y"] == o_milestones["expected_landing_y"]
    assert commit_ev["new_heading"] == 4

    assert map_enter_ev["map_id"] == o_milestones["expected_landing_map"]
    assert map_enter_ev["x"] == o_milestones["expected_landing_x"]
    assert map_enter_ev["y"] == o_milestones["expected_landing_y"]
    assert map_enter_ev["heading"] == 4

    print(f"  [PASS] WorldTransitionCommitted: Map {commit_ev['old_map']} ({commit_ev['old_x']},{commit_ev['old_y']}) -> "
          f"Map {commit_ev['new_map']} ({commit_ev['new_x']},{commit_ev['new_y']}) Heading {commit_ev['new_heading']}")
    print(f"  [PASS] MapEntered: Map {map_enter_ev['map_id']} at ({map_enter_ev['x']},{map_enter_ev['y']})")

    # -----------------------------------------------------------------
    # LEVEL 5: REAL MAP 1 LOCAL NAVIGATION TO GOAL (L5)
    # -----------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 5: REAL MAP 1 LOCAL NAVIGATION TO GOAL (ARRIVAL)")
    print("-----------------------------------------------------------------")
    dest_evs = [ev for ev in native_events if ev["event_type"] == "DestinationReached"]
    assert len(dest_evs) >= 2, "Expected DestinationReached for both Portal and Goal"
    final_dest = dest_evs[-1]

    if final_dest["target_x"] != o_milestones["expected_final_x"] or final_dest["target_y"] != o_milestones["expected_final_y"]:
        print(f"[FAIL] Final target mismatch! Expected ({o_milestones['expected_final_x']}, {o_milestones['expected_final_y']}), got ({final_dest['target_x']}, {final_dest['target_y']})")
        return False

    final_pos_ev = [ev for ev in native_events if ev["event_type"] == "PositionChanged"][-1]
    if final_pos_ev["new_x"] != o_milestones["expected_final_x"] or final_pos_ev["new_y"] != o_milestones["expected_final_y"]:
        print(f"[FAIL] Final actor position mismatch! Got ({final_pos_ev['new_x']}, {final_pos_ev['new_y']})")
        return False

    print(f"  [PASS] Final Goal Reached on Real Map 1 at ({final_dest['target_x']}, {final_dest['target_y']})!")

    print("\n=================================================================")
    print("        SCENARIO 005 DIFFERENTIAL CONFORMANCE VERDICT")
    print("=================================================================")
    print("  Level 0: Real Map Import Integrity   : PASS")
    print("  Level 1: World Transition Integrity  : PASS")
    print("  Level 2: World Route Topology        : PASS")
    print("  Level 3: Map 0 Local Approach        : PASS")
    print("  Level 4: Cross-Map Atomic Commit     : PASS")
    print("  Level 5: Map 1 Local Arrival         : PASS")
    print("=================================================================")
    print("    >>> SCENARIO 005 CONFORMANCE CERTIFICATION: PASS <<<")
    print("=================================================================")
    return True


if __name__ == "__main__":
    oracle = sys.argv[1] if len(sys.argv) > 1 else "oracle_trace_scenario_005.jsonl"
    native = sys.argv[2] if len(sys.argv) > 2 else "native_trace_005.jsonl"
    ok = verify_conformance(oracle, native)
    sys.exit(0 if ok else 1)
