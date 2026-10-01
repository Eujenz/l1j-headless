"""
tools/query_monster_modespeed.py - Targeted Archaeology Query CLI for L1J 1.82 Monster modespeed & list.spr

Classification:
  LEGACY_OBSERVED (PRIMARY_DATA_AUTHORITY)

Parses client/list.spr using the exact ClientFileLoad algorithm (units * 40 ms)
and cross-references with db/lineage/monster.sql.
"""
import argparse
import os
import re
import sys
from typing import Dict, List, Optional

DEFAULT_LIST_SPR = r"C:\Users\p0282768\Documents\Gemini\Lineage182c\client\list.spr"
DEFAULT_MONSTER_SQL = r"C:\Users\p0282768\Documents\Gemini\Lineage182c\db\lineage\monster.sql"


def parse_list_spr(list_spr_path: str = DEFAULT_LIST_SPR) -> Dict[int, Dict]:
    if not os.path.exists(list_spr_path):
        raise FileNotFoundError(f"list.spr not found at: {list_spr_path}")

    gfx_map = {}
    with open(list_spr_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#"):
                continue

            parts = line.split(None, 3)
            if len(parts) < 3:
                continue

            try:
                gfx_id = int(parts[0][1:])
                sprite_id = int(parts[1])
            except ValueError:
                continue

            name = parts[2]
            action_content = parts[3] if len(parts) > 3 else ""

            modes = {}
            for m in re.finditer(r"(\d+)\.([^(]+)\(([^)]*)\)", action_content):
                mode_id = int(m.group(1))
                action_name = m.group(2).strip()
                seq = m.group(3).strip()

                tokens = seq.split(":")
                total_units = 0
                if len(tokens) > 1:
                    for token in tokens[1:]:
                        if not token:
                            continue
                        c0 = token[0]
                        v0 = ord(c0) - ord("0") if c0.isdigit() else 0
                        v1 = -1
                        if len(token) > 1 and token[1].isdigit():
                            v1 = ord(token[1]) - ord("0")

                        if 0 <= v1 <= 9:
                            val = v0 + v1
                            if val >= 20:
                                val = v0
                        else:
                            val = v0
                        total_units += val

                speed = total_units * 40
                if gfx_id == 1080:
                    speed = 0

                modes[mode_id] = {
                    "action_name": action_name,
                    "units": total_units,
                    "speed_ms": speed
                }

            gfx_map[gfx_id] = {
                "gfx_id": gfx_id,
                "sprite_id": sprite_id,
                "name": name,
                "modes": modes
            }
    return gfx_map


def load_monsters(monster_sql_path: str = DEFAULT_MONSTER_SQL) -> List[Dict]:
    if not os.path.exists(monster_sql_path):
        return []

    monsters = []
    fields = [
        "uid", "name", "name_id", "gfx", "level", "hp", "mp", "min_dmg", "max_dmg",
        "ac", "mr", "exp", "lawful", "size", "die", "tribal_id", "agro", "poly",
        "item_pick", "tameable", "runtype", "attack", "areaatk", "resurrection",
        "tough_skin", "undead", "drop_adena"
    ]
    with open(monster_sql_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("INSERT INTO `monster`"):
                m = re.search(r"VALUES\s*\((.*)\);?", line)
                if m:
                    content = m.group(1)
                    tokens = [p.strip(" '\"") for p in content.split(",")]
                    if len(tokens) >= len(fields):
                        monsters.append(dict(zip(fields, tokens[:len(fields)])))
    return monsters


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Query L1J 1.82 Monster modespeed & list.spr")
    parser.add_argument("--spr", default=DEFAULT_LIST_SPR, help="Path to list.spr")
    parser.add_argument("--sql", default=DEFAULT_MONSTER_SQL, help="Path to monster.sql")
    parser.add_argument("--gfx", type=int, default=None, help="Filter by GFX ID")
    parser.add_argument("--name", default=None, help="Filter by monster or sprite name")
    parser.add_argument("--mode", type=int, default=None, help="Filter by mode ID (0=move, 1=attack)")
    args = parser.parse_args()

    gfx_data = parse_list_spr(args.spr)
    monsters = load_monsters(args.sql)

    # Index monsters by GFX
    mon_by_gfx = {}
    for mon in monsters:
        g = int(mon["gfx"])
        if g not in mon_by_gfx:
            mon_by_gfx[g] = []
        mon_by_gfx[g].append(mon)

    matched_gfxs = set()
    if args.gfx is not None:
        if args.gfx in gfx_data:
            matched_gfxs.add(args.gfx)
    elif args.name is not None:
        q = args.name.lower()
        for gid, ginfo in gfx_data.items():
            if q in ginfo["name"].lower():
                matched_gfxs.add(gid)
        for mon in monsters:
            if q in mon["name"].lower():
                matched_gfxs.add(int(mon["gfx"]))
    else:
        # Show first 10 monsters
        for mon in monsters[:10]:
            matched_gfxs.add(int(mon["gfx"]))

    if not matched_gfxs:
        print("[NOT FOUND] No matching monsters or GFX found.")
        sys.exit(1)

    print(f"L1J 1.82 Monster modespeed Evidence ({len(matched_gfxs)} GFX matched):\n")
    for gid in sorted(matched_gfxs):
        ginfo = gfx_data.get(gid)
        mons = mon_by_gfx.get(gid, [])
        mon_names = ", ".join([f"{m['name']}(ID:{m['uid']})" for m in mons]) or "(no monster linked)"
        spr_name = ginfo["name"] if ginfo else "(not in list.spr)"
        sprite_id = ginfo["sprite_id"] if ginfo else "N/A"

        print(f"GFX {gid:4d} | Sprite {sprite_id} | Client Name: {spr_name} | Monsters: {mon_names}")
        if ginfo and ginfo["modes"]:
            modes_to_show = ginfo["modes"]
            if args.mode is not None:
                modes_to_show = {k: v for k, v in modes_to_show.items() if k == args.mode}

            for mid in sorted(modes_to_show.keys()):
                minfo = modes_to_show[mid]
                sem = "Move" if mid == 0 else ("Attack" if mid == 1 else "Action")
                print(f"    Mode {mid:2d} ({sem:<6s} {minfo['action_name']:15s}): {minfo['speed_ms']:4d} ms ({minfo['units']:2d} units * 40ms)")
        else:
            print("    [Fallback: All modes -> 1000 ms]")
        print("-" * 75)


if __name__ == "__main__":
    main()
