"""
scenario_004_differential.py - Scenario 004 Differential Conformance Verifier
Compares the Legacy Java Oracle trace against the Modern Native Map trace.
Verifies bit-exact parity of metadata, 262,144 cell geometry digest, and sample tiles.
"""
import json
import os
import sys


def run_differential_verification():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    oracle_file = "oracle_trace_scenario_004.jsonl"
    native_file = "native_trace_004.jsonl"

    print("=" * 65)
    print("      SCENARIO 004 DIFFERENTIAL CONFORMANCE VERIFIER")
    print("      Legacy Java Oracle  vs.  Modern Native Runtime")
    print("=" * 65)
    print(f"  Oracle Trace: {oracle_file}")
    print(f"  Native Trace: {native_file}")
    print("=" * 65)

    if not os.path.exists(oracle_file):
        print(f"[FAIL] Missing Oracle trace: {oracle_file}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(native_file):
        print(f"[FAIL] Missing Native trace: {native_file}", file=sys.stderr)
        sys.exit(1)

    # 1. Load traces
    with open(oracle_file, "r", encoding="utf-8") as f:
        oracle_records = [json.loads(line) for line in f if line.strip()]

    with open(native_file, "r", encoding="utf-8") as f:
        native_records = [json.loads(line) for line in f if line.strip()]

    print(f"[RECORDS LOADED] Legacy Oracle: {len(oracle_records)} records")
    print(f"                 Native Engine: {len(native_records)} records")

    # 2. Level 1: Map Metadata & Dimensions Parity
    print("\n" + "-" * 65)
    print(">>> LEVEL 1: MAP METADATA & DIMENSIONS PARITY")
    print("-" * 65)
    oracle_meta = oracle_records[0]
    native_meta = native_records[0]

    for key in ["map_id", "width", "height", "total_cells"]:
        o_val = oracle_meta.get(key)
        n_val = native_meta.get(key)
        if o_val != n_val:
            print(f"[FAIL] Metadata mismatch for {key}: Oracle={o_val}, Native={n_val}")
            sys.exit(1)
        print(f"  [PASS] {key:<15}: {o_val}")
    print("[PASS] Map dimensions and total grid cell count identical.")

    # 3. Level 2: Full Canonical Geometry Digest Parity
    print("\n" + "-" * 65)
    print(">>> LEVEL 2: FULL CANONICAL GEOMETRY DIGEST PARITY (262,144 CELLS)")
    print("-" * 65)
    o_digest = oracle_meta["canonical_geometry_digest"]
    n_digest = native_meta["canonical_geometry_digest"]

    print(f"  Legacy Oracle Digest: {o_digest}")
    print(f"  Native Engine Digest: {n_digest}")

    if o_digest != n_digest:
        print("[FAIL] Full geometry digest mismatch between Legacy and Native!")
        sys.exit(1)
    print("[PASS] Bit-exact SHA-256 match across all 262,144 coordinates!")

    # 4. Level 3: Sample Tile Observation & Collision Semantics Parity
    print("\n" + "-" * 65)
    print(">>> LEVEL 3: SAMPLED TILE OBSERVATION & COLLISION PARITY")
    print("-" * 65)
    oracle_samples = {f"{r['x']},{r['y']}": r for r in oracle_records[1:] if r.get("record_type") == "TILE_OBSERVATION"}
    native_samples = {f"{r['x']},{r['y']}": r for r in native_records[1:] if r.get("record_type") == "TILE_OBSERVATION"}

    for key, o_obs in oracle_samples.items():
        if key not in native_samples:
            print(f"[FAIL] Sample at {key} missing from Native trace!")
            sys.exit(1)
        n_obs = native_samples[key]

        # Compare tile value, passability, zone
        for prop in ["raw_tile", "is_through_e", "is_through_n", "zone"]:
            if o_obs.get(prop) != n_obs.get(prop):
                print(f"[FAIL] Mismatch at {key} for {prop}: Oracle={o_obs.get(prop)}, Native={n_obs.get(prop)}")
                sys.exit(1)

        print(f"  [PASS] Tile ({o_obs['x']}, {o_obs['y']}) -> Val=0x{o_obs['raw_tile']:02X} PassE={o_obs['is_through_e']} PassN={o_obs['is_through_n']} Zone={o_obs['zone']}")

    print("[PASS] All representative tile semantics match 100% with Legacy Oracle.")

    print("\n" + "=" * 65)
    print("        SCENARIO 004 DIFFERENTIAL CONFORMANCE VERDICT")
    print("=" * 65)
    print("  Level 1: Map Metadata Parity         : PASS")
    print("  Level 2: Canonical Geometry Digest   : PASS")
    print("  Level 3: Sampled Collision Parity    : PASS")
    print("=" * 65)
    print("    >>> SCENARIO 004 CONFORMANCE CERTIFICATION: PASS <<<")
    print("=" * 65)


if __name__ == "__main__":
    run_differential_verification()
