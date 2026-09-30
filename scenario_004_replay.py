"""
scenario_004_replay.py - Scenario 004 Real Map Import Replay & Conformance Runner
Executes native real map ingestion against scenario_004_contract.json,
emits native_trace_004.jsonl, and performs 5-phase verification.
"""
import json
import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tools.map_metadata import MapsCsvReader
from tools.map_decoder import LegacyMapDecoder
from native_engine.movement import MovementEngine, can_move
from native_engine.model import Actor, Position, Inventory


def run_replay(legacy_root: str = "../Gemini/Lineage182c"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 65)
    print("      MODERN REPLAY 004 - CANONICAL REAL MAP IMPORT")
    print("=" * 65)

    # 1. Load Contract
    contract_file = "scenario_004_contract.json"
    with open(contract_file, "r", encoding="utf-8") as f:
        contract = json.load(f)

    map_spec = contract["map_specification"]
    map_id = map_spec["map_id"]
    print(f"[CONTRACT LOADED] Scenario: {contract['scenario_id']} (Scope: {contract['scope']})")
    print(f"                 Map ID:   {map_id} ({contract['provenance']['map_name']})")
    print(f"                 Bounds:   X=[{map_spec['bounds']['loc_x1']}..{map_spec['bounds']['loc_x2']}], Y=[{map_spec['bounds']['loc_y1']}..{map_spec['bounds']['loc_y2']}]")

    # Resolve paths
    maps_csv = os.path.join(legacy_root, "maps", "maps.csv")
    data_file = os.path.join(legacy_root, "maps", "Cache", f"{map_id}.data")

    # 2. Phase 1: Metadata & Format Verification
    print("\n" + "-" * 65)
    print(">>> PHASE 1: METADATA & BINARY FORMAT VERIFICATION")
    print("-" * 65)
    meta = MapsCsvReader.get_map(maps_csv, map_id)
    assert meta.loc_x1 == map_spec["bounds"]["loc_x1"]
    assert meta.loc_x2 == map_spec["bounds"]["loc_x2"]
    assert meta.loc_y1 == map_spec["bounds"]["loc_y1"]
    assert meta.loc_y2 == map_spec["bounds"]["loc_y2"]
    assert meta.width == map_spec["dimensions"]["width"]
    assert meta.height == map_spec["dimensions"]["height"]
    assert meta.cell_count == map_spec["total_cells"]
    print(f"[PASS] maps.csv metadata verified: {meta.width}x{meta.height} ({meta.cell_count} cells).")

    # 3. Phase 2: Canonical Decoding & Geometry Digest
    print("\n" + "-" * 65)
    print(">>> PHASE 2: CANONICAL DECODING & GEOMETRY DIGEST")
    print("-" * 65)
    canonical_map, src_sha = LegacyMapDecoder.decode_legacy_map(data_file, meta)
    assert src_sha == contract["provenance"]["source_artifact_sha256"]
    print(f"[PASS] Source binary SHA-256 verified: {src_sha}")

    expected_digest = map_spec["canonical_geometry_digest"]
    actual_digest = canonical_map.canonical_geometry_digest
    if actual_digest != expected_digest:
        print(f"[FAIL] Geometry digest mismatch!")
        print(f"  Expected: {expected_digest}")
        print(f"  Actual:   {actual_digest}")
        sys.exit(1)
    print(f"[PASS] Canonical Geometry Digest matched: {actual_digest}")

    # 4. Phase 3: Sample Coordinates Conformance
    print("\n" + "-" * 65)
    print(">>> PHASE 3: SAMPLE COORDINATES & BOUNDS CONFORMANCE")
    print("-" * 65)
    grid = canonical_map.to_grid()
    sample_observations = []

    for s in contract["sample_coordinates"]:
        sx, sy = s["x"], s["y"]
        expected_tile = s["expected_tile"]
        actual_tile = grid.get_tile(sx, sy)
        if actual_tile != expected_tile:
            print(f"[FAIL] Mismatch at ({sx}, {sy}): expected {expected_tile}, got {actual_tile}")
            sys.exit(1)

        pass_e = grid.is_through_object(sx, sy, 2)
        pass_n = grid.is_through_object(sx, sy, 0)
        zone = actual_tile & 0x30
        obs = {
            "x": sx,
            "y": sy,
            "raw_tile": actual_tile,
            "is_through_e": pass_e,
            "is_through_n": pass_n,
            "zone": zone,
            "desc": s["description"]
        }
        sample_observations.append(obs)
        print(f"  [PASS] ({sx}, {sy}) [{s['hex']}] -> PassE={pass_e}, PassN={pass_n}, Zone={zone} ({s['description']})")

    # Out of bounds check
    assert grid.get_tile(meta.loc_x1 - 1, meta.loc_y1) == 0
    assert grid.get_tile(meta.loc_x2 + 1, meta.loc_y2) == 0
    assert not grid.is_in_bounds(meta.loc_x1 - 1, meta.loc_y1)
    print("[PASS] Out-of-bounds boundaries return 0 and reject coordinates.")

    # 5. Phase 4: Movement Engine Real Map Smoke Tests
    print("\n" + "-" * 65)
    print(">>> PHASE 4: MOVEMENT ENGINE REAL MAP SMOKE TESTS")
    print("-" * 65)
    movement_engine = MovementEngine(grid)
    for c in contract["movement_smoke_cases"]:
        case_id = c["case_id"]
        fx, fy = c["from_x"], c["from_y"]
        h = c["heading"]
        exp_pass = c["expected_passable"]
        exp_reason = c["expected_reason"]

        act_pass, act_reason = can_move(grid, fx, fy, h)
        if act_pass != exp_pass or act_reason != exp_reason:
            print(f"[FAIL] {case_id}: expected ({exp_pass}, {exp_reason}), got ({act_pass}, {act_reason})")
            sys.exit(1)
        print(f"  [PASS] {case_id:<35} -> Pass={act_pass:<5} Reason={act_reason}")

    # 6. Phase 5: Deterministic Repeated Import Invariant
    print("\n" + "-" * 65)
    print(">>> PHASE 5: DETERMINISTIC REPEATED IMPORT INVARIANT")
    print("-" * 65)
    canonical_map_b, _ = LegacyMapDecoder.decode_legacy_map(data_file, meta)
    assert canonical_map.canonical_geometry_digest == canonical_map_b.canonical_geometry_digest
    assert canonical_map.raw_tiles == canonical_map_b.raw_tiles
    print("[PASS] Repeated import produces bit-identical CanonicalMapDefinition.")

    # 7. Write Native Trace
    native_trace_file = "native_trace_004.jsonl"
    with open(native_trace_file, "w", encoding="utf-8") as f:
        seq = 1
        hdr = {
            "seq": seq,
            "artifact": "NATIVE_MAP_TRACE",
            "scenario": "004",
            "map_id": map_id,
            "width": canonical_map.width,
            "height": canonical_map.height,
            "total_cells": meta.cell_count,
            "canonical_geometry_digest": actual_digest
        }
        f.write(json.dumps(hdr, ensure_ascii=False) + "\n")
        for obs in sample_observations:
            seq += 1
            entry = {
                "seq": seq,
                "record_type": "TILE_OBSERVATION",
                "x": obs["x"],
                "y": obs["y"],
                "raw_tile": obs["raw_tile"],
                "is_through_e": obs["is_through_e"],
                "is_through_n": obs["is_through_n"],
                "zone": obs["zone"]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n[TRACE ARTIFACT] Written native trace to {native_trace_file}")

    print("\n" + "=" * 65)
    print("               FINAL REPLAY CONFORMANCE VERDICT")
    print("=" * 65)
    print("  L1 Metadata & Format   PASS")
    print("  L2 Geometry Digest     PASS")
    print("  L3 Tile Samples        PASS")
    print("  L4 Movement Engine     PASS")
    print("  L5 Import Invariant    PASS")
    print("=" * 65)
    print("               >>>  OVERALL STATUS: PASS  <<<")
    print("=" * 65)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "../Gemini/Lineage182c"
    run_replay(root)
