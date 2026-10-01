"""
tools/query_server_spr.py - Targeted Archaeology Query CLI for L1J 1.82 sprite_frame.sql

Classification:
  LEGACY_OBSERVED (PRIMARY_DATA_AUTHORITY)

Queries C:/Users/p0282768/Documents/Gemini/Lineage182c/db/lineage/sprite_frame.sql directly.
"""
import argparse
import os
import re
import sys
from typing import Dict, List, Optional

DEFAULT_SQL_PATH = r"C:\Users\p0282768\Documents\Gemini\Lineage182c\db\lineage\sprite_frame.sql"


def load_sprite_frame_records(sql_path: str = DEFAULT_SQL_PATH) -> List[Dict]:
    if not os.path.exists(sql_path):
        raise FileNotFoundError(f"1.82 sprite_frame.sql not found at: {sql_path}")

    records = []
    with open(sql_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("INSERT INTO"):
                m = re.search(r"VALUES \((.*)\);", line)
                if m:
                    parts = [p.strip(" '\"") for p in m.group(1).split(",")]
                    if len(parts) >= 5:
                        records.append({
                            "name": parts[0],
                            "gfx": int(parts[1]),
                            "action": int(parts[2]),
                            "action_name": parts[3],
                            "frame_ms": int(parts[4])
                        })
    return records


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Query 1.82 Legacy Server sprite_frame.sql")
    parser.add_argument("--sql", default=DEFAULT_SQL_PATH, help="Path to sprite_frame.sql")
    parser.add_argument("--gfx", type=int, default=None, help="Filter by GFX ID")
    parser.add_argument("--name", default=None, help="Filter by name substring")
    parser.add_argument("--action", type=int, default=None, help="Filter by action ID")
    args = parser.parse_args()

    records = load_sprite_frame_records(args.sql)

    filtered = records
    if args.gfx is not None:
        filtered = [r for r in filtered if r["gfx"] == args.gfx]
    if args.name is not None:
        filtered = [r for r in filtered if args.name.lower() in r["name"].lower()]
    if args.action is not None:
        filtered = [r for r in filtered if r["action"] == args.action]

    if not filtered:
        print("[NOT FOUND] No records matching criteria.")
        sys.exit(1)

    print(f"L1J 1.82 Legacy sprite_frame Evidence ({len(filtered)} records):\n")
    print(f"{'GFX':<6} {'Name':<14} {'Action':<8} {'Action Name':<22} {'Cadence (ms)':<12}")
    print("-" * 65)
    for r in filtered:
        print(f"{r['gfx']:<6} {r['name']:<14} {r['action']:<8} {r['action_name']:<22} {r['frame_ms']:<12}")


if __name__ == "__main__":
    main()
