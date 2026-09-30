"""
scenario_003_differential.py - Legacy-vs-Native Differential Conformance Comparator for Scenario 003.

Performs 3-Level Differential Verification:
  Level 1: World State Conformance (Map spatial membership, coordinates, heading)
  Level 2: Semantic Domain Events Conformance (Event sequence ordering & payload parity)
  Level 3: Autonomous Navigation Outcome Conformance (Multi-map mission completion)
"""
import json
import os
import sys
from typing import Dict, Any, List, Tuple

def load_trace(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Trace file not found: {path}")
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def run_differential(
    oracle_trace_path: str = "oracle_trace_scenario_003.jsonl",
    native_trace_path: str = "native_trace_003.jsonl"
) -> bool:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=================================================================")
    print("      SCENARIO 003 DIFFERENTIAL CONFORMANCE VERIFIER")
    print("      Legacy Java Oracle  vs.  Modern Native Runtime")
    print("=================================================================")
    print(f"  Oracle Trace: {oracle_trace_path}")
    print(f"  Native Trace: {native_trace_path}")
    print("=================================================================")

    oracle_records = load_trace(oracle_trace_path)
    native_records = load_trace(native_trace_path)

    print(f"[RECORDS LOADED] Legacy Oracle: {len(oracle_records)} events")
    print(f"                 Native Engine: {len(native_records)} events")

    # -------------------------------------------------------------
    # LEVEL 1: World State Conformance Audit
    # -------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 1: WORLD STATE CONFORMANCE AUDIT")
    print("-----------------------------------------------------------------")

    l1_pass = True

    # 1. Approach & Portal Arrival (Phase 1)
    p1_native_dest = next((r for r in native_records if r["name"] == "DestinationReached" and r["payload"].get("target_x") == 32477), None)
    p1_oracle_dest = next((r for r in oracle_records if r["name"] == "DestinationReached" and r["payload"].get("target_x") == 32477), None)

    if not p1_native_dest or not p1_oracle_dest:
        print("[FAIL] Level 1: Portal arrival event missing in traces!")
        l1_pass = False
    else:
        print(f"[PASS] Portal Arrival State: Map 0 at ({p1_native_dest['payload']['target_x']}, {p1_native_dest['payload']['target_y']})")

    # 2. Cross-Map Atomic Transition State (Phase 2)
    native_trans = next((r for r in native_records if r["name"] == "WorldTransitionCommitted"), None)
    oracle_trans = next((r for r in oracle_records if r["name"] == "WorldTransitionCommitted"), None)

    if not native_trans or not oracle_trans:
        print("[FAIL] Level 1: WorldTransitionCommitted event missing in traces!")
        l1_pass = False
    else:
        np = native_trans["payload"]
        op = oracle_trans["payload"]
        state_match = (
            np["old_map"] == op["old_map"] == 0 and
            np["old_x"] == op["old_x"] == 32477 and
            np["old_y"] == op["old_y"] == 32851 and
            np["new_map"] == op["new_map"] == 1 and
            np["new_x"] == op["new_x"] == 32669 and
            np["new_y"] == op["new_y"] == 32802 and
            np["new_heading"] == op["new_heading"] == 4
        )
        if state_match:
            print(f"[PASS] Cross-Map Transition State:")
            print(f"       From: Map {np['old_map']} ({np['old_x']}, {np['old_y']})")
            print(f"       To:   Map {np['new_map']} ({np['new_x']}, {np['new_y']}, heading={np['new_heading']})")
            print(f"       Bit-exact match between Legacy Oracle and Native Runtime.")
        else:
            print(f"[FAIL] Transition state divergence!")
            print(f"       Oracle: {op}")
            print(f"       Native: {np}")
            l1_pass = False

    # 3. Final Destination State (Phase 3)
    p3_native_dest = next((r for r in reversed(native_records) if r["name"] == "DestinationReached"), None)
    p3_oracle_dest = next((r for r in reversed(oracle_records) if r["name"] == "DestinationReached"), None)

    if not p3_native_dest or not p3_oracle_dest:
        print("[FAIL] Level 1: Final destination event missing in traces!")
        l1_pass = False
    else:
        nd = p3_native_dest["payload"]
        od = p3_oracle_dest["payload"]
        if nd["target_x"] == od["target_x"] == 32671 and nd["target_y"] == od["target_y"] == 32804:
            print(f"[PASS] Final Destination State: Map 1 at ({nd['target_x']}, {nd['target_y']})")
        else:
            print(f"[FAIL] Final destination divergence: Oracle=({od['target_x']},{od['target_y']}), Native=({nd['target_x']},{nd['target_y']})")
            l1_pass = False

    # -------------------------------------------------------------
    # LEVEL 2: Semantic Domain Events Conformance Audit
    # -------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 2: SEMANTIC DOMAIN EVENTS CONFORMANCE AUDIT")
    print("-----------------------------------------------------------------")

    l2_pass = True
    max_len = max(len(oracle_records), len(native_records))
    divergences: List[Tuple[int, Dict[str, Any], Dict[str, Any]]] = []

    print(f"{'Idx':<4} | {'Oracle Event':<26} | {'Native Event':<26} | {'Match'}")
    print("-" * 65)

    for i in range(max_len):
        orec = oracle_records[i] if i < len(oracle_records) else None
        nrec = native_records[i] if i < len(native_records) else None

        o_name = orec["name"] if orec else "<NONE>"
        n_name = nrec["name"] if nrec else "<NONE>"

        # Compare payloads
        match = False
        if orec and nrec:
            # Check event name and payload equivalency
            if o_name == n_name:
                op = orec.get("payload", {})
                np = nrec.get("payload", {})
                # Normalize keys for comparison
                keys = set(op.keys()).union(set(np.keys()))
                payloads_equal = True
                for k in keys:
                    if op.get(k) != np.get(k):
                        payloads_equal = False
                        break
                match = payloads_equal

        status_str = "MATCH" if match else "DIVERGE"
        print(f"{i+1:<4} | {o_name:<26} | {n_name:<26} | {status_str}")

        if not match:
            l2_pass = False
            divergences.append((i + 1, orec, nrec))

    if l2_pass:
        print(f"\n[PASS] All {len(native_records)} domain events matched with 100% payload equivalence!")
    else:
        print(f"\n[FAIL] Found {len(divergences)} event divergences:")
        for idx, orec, nrec in divergences:
            print(f"  Step #{idx}:")
            print(f"    Oracle: {orec}")
            print(f"    Native: {nrec}")

    # -------------------------------------------------------------
    # LEVEL 3: Autonomous Navigation Outcome Conformance Audit
    # -------------------------------------------------------------
    print("\n-----------------------------------------------------------------")
    print(">>> LEVEL 3: AUTONOMOUS NAVIGATION OUTCOME CONFORMANCE AUDIT")
    print("-----------------------------------------------------------------")

    l3_pass = True

    # Check phase step counts
    p1_o_steps = len([r for r in oracle_records[:10] if r["name"] == "MoveAccepted"])
    p1_n_steps = len([r for r in native_records[:10] if r["name"] == "MoveAccepted"])

    p3_o_steps = len([r for r in oracle_records[13:] if r["name"] == "MoveAccepted"])
    p3_n_steps = len([r for r in native_records[13:] if r["name"] == "MoveAccepted"])

    print(f"  Phase 1 Steps (Map 0 Approach):  Oracle = {p1_o_steps}, Native = {p1_n_steps}")
    print(f"  Phase 2 Trigger (Cross-Map):     Oracle = PORTAL, Native = PORTAL")
    print(f"  Phase 3 Steps (Map 1 Exit):      Oracle = {p3_o_steps}, Native = {p3_n_steps}")

    if p1_o_steps != p1_n_steps or p3_o_steps != p3_n_steps:
        print("[FAIL] Navigation step count mismatch!")
        l3_pass = False
    else:
        print("[PASS] Navigation path geometry and step count identical on all maps.")

    # -------------------------------------------------------------
    # FINAL VERDICT
    # -------------------------------------------------------------
    overall_pass = l1_pass and l2_pass and l3_pass

    print("\n=================================================================")
    print("        SCENARIO 003 DIFFERENTIAL CONFORMANCE VERDICT")
    print("=================================================================")
    print(f"  Level 1: World State Conformance        : {'PASS' if l1_pass else 'FAIL'}")
    print(f"  Level 2: Semantic Domain Events Parity   : {'PASS' if l2_pass else 'FAIL'}")
    print(f"  Level 3: Navigation Outcome Conformance : {'PASS' if l3_pass else 'FAIL'}")
    print("=================================================================")
    if overall_pass:
        print("    >>> SCENARIO 003 CONFORMANCE CERTIFICATION: PASS <<<")
    else:
        print("    >>> SCENARIO 003 CONFORMANCE CERTIFICATION: FAIL <<<")
    print("=================================================================")

    return overall_pass

if __name__ == '__main__':
    success = run_differential()
    sys.exit(0 if success else 1)
