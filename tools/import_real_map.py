#!/usr/bin/env python3
"""
tools/import_real_map.py - Canonical Real Map Ingestion CLI
Decodes a Lineage 1.82 legacy map from an external legacy reference root
into a CanonicalMapDefinition and verifies its canonical geometry digest.
"""
import argparse
import json
import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.map_metadata import MapsCsvReader
from tools.map_decoder import LegacyMapDecoder


def parse_args():
    parser = argparse.ArgumentParser(
        description="L1J Headless Real Map Ingestion Tool"
    )
    parser.add_argument(
        "--legacy-root",
        type=str,
        required=True,
        help="Path to external Legacy Reference repository root (e.g. ../182c)"
    )
    parser.add_argument(
        "--map-id",
        type=int,
        default=0,
        help="Map ID to import (default: 0)"
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default="",
        help="Optional path to write canonical map metadata JSON"
    )
    return parser.parse_args()


def import_map(legacy_root: str, map_id: int, output_json: str = ""):
    maps_csv_path = os.path.join(legacy_root, "maps", "maps.csv")
    data_path = os.path.join(legacy_root, "maps", "Cache", f"{map_id}.data")

    if not os.path.exists(maps_csv_path):
        print(f"[ERROR] maps.csv not found at: {maps_csv_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(data_path):
        print(f"[ERROR] Map data file not found at: {data_path}", file=sys.stderr)
        sys.exit(1)

    metadata = MapsCsvReader.get_map(maps_csv_path, map_id)
    canonical_map, source_sha256 = LegacyMapDecoder.decode_legacy_map(data_path, metadata)

    report = {
        "map_id": canonical_map.map_id,
        "bounds": {
            "loc_x1": canonical_map.loc_x1,
            "loc_x2": canonical_map.loc_x2,
            "loc_y1": canonical_map.loc_y1,
            "loc_y2": canonical_map.loc_y2
        },
        "width": canonical_map.width,
        "height": canonical_map.height,
        "cell_count": metadata.cell_count,
        "decoded_size_bytes": len(canonical_map.raw_tiles),
        "format": "Headerless Raw Byte Grid (Legacy 2-Byte Truncation Resolved)",
        "source_sha256": source_sha256,
        "canonical_geometry_digest": canonical_map.canonical_geometry_digest
    }

    print("=" * 65)
    print(f"       L1J HEADLESS REAL MAP IMPORT: MAP {canonical_map.map_id}")
    print("=" * 65)
    print(f"Map ID:                     {report['map_id']}")
    print(f"Bounds:                     X=[{report['bounds']['loc_x1']}..{report['bounds']['loc_x2']}], Y=[{report['bounds']['loc_y1']}..{report['bounds']['loc_y2']}]")
    print(f"Dimensions:                 Width={report['width']}, Height={report['height']}")
    print(f"Total Cells:                {report['cell_count']}")
    print(f"Decoded Size:               {report['decoded_size_bytes']} bytes")
    print(f"Format:                     {report['format']}")
    print(f"Source SHA-256:             {report['source_sha256']}")
    print(f"Canonical Geometry Digest:  {report['canonical_geometry_digest']}")
    print("=" * 65)
    print("[STATUS] Import Successful.")

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[OUTPUT] Metadata written to {output_json}")

    return canonical_map, report


if __name__ == "__main__":
    args = parse_args()
    import_map(args.legacy_root, args.map_id, args.output_json)
