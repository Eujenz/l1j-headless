"""
tools/query_client_gfx.py - Targeted Archaeology Query CLI for Client GFX Evidence

Classification:
  LEGACY_CLIENT_OBSERVED_3_80 (CROSS_VERSION_AUXILIARY)

Queries legacy/client/3.80/TW13081901.sqlite directly without reading raw files.
"""
import argparse
import os
import sys

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from native_engine.evidence import ClientGfxEvidenceStore


def format_action_label(a) -> str:
    if a.weapon:
        return f"{a.action_name}[{a.weapon}] (Action {a.action_id}, {a.frame_count or '?'} frames)"
    return f"{a.action_name} (Action {a.action_id}, {a.frame_count or '?'} frames)"


def display_gfx(rec, meta, show_framerate_only: bool = False, specific_action=None, specific_weapon=None):
    source_id = meta.get("source_id", "legacy-client-tw13081901")
    version = meta.get("version", "3.80")
    classification = meta.get("classification", "LEGACY_CLIENT_OBSERVED_3_80")
    sha256 = meta.get("sha256", "UNKNOWN")

    print(f"Source:")
    print(f"  {source_id}")
    print(f"\nVersion:")
    print(f"  {version}")
    print(f"\nClassification:")
    print(f"  {classification}")
    print(f"\nSHA256:")
    print(f"  {sha256}")
    print(f"\nGFX:")
    print(f"  {rec.gfx_id}")
    print(f"\nSprite:")
    print(f"  {rec.sprite_id}")
    print(f"\nName:")
    print(f"  {rec.name or '(unnamed)'}")
    print(f"\nFrameRate:")
    print(f"  {rec.framerate if rec.framerate is not None else 'UNKNOWN'}")

    if show_framerate_only:
        print(f"\nRaw evidence:")
        print(f"  TW13081901.txt:L{rec.start_line}-L{rec.end_line}")
        return

    # Filter actions if specific action/weapon was requested
    filtered_anims = rec.animations
    if specific_action:
        filtered_anims = [a for a in filtered_anims if a.action_name.lower() == specific_action.lower()]
    if specific_weapon:
        filtered_anims = [a for a in filtered_anims if a.weapon and a.weapon.lower() == specific_weapon.lower()]

    if specific_action or specific_weapon:
        print(f"\nTargeted Action Evidence ({len(filtered_anims)} matched):")
        for a in filtered_anims:
            lbl = format_action_label(a)
            print(f"  - Action {a.action_id}: {lbl}")
            print(f"      Frames:        {a.frame_count}")
            print(f"      FrameRate:     {a.frame_rate or rec.framerate or 'UNKNOWN'}")
            print(f"      Sequence:      {a.raw_sequence[:60]}{'...' if len(a.raw_sequence) > 60 else ''}")
            print(f"      Raw evidence:  TW13081901.txt:L{a.start_line}-L{a.end_line}")
    else:
        print(f"\nActions ({len(rec.animations)} total):")
        for a in rec.animations:
            print(f"  {format_action_label(a)}")

    if rec.references:
        print(f"\nReferences:")
        for rtype, rid in rec.references:
            print(f"  {rtype} -> {rid}")

    print(f"\nRaw evidence:")
    print(f"  TW13081901.txt:L{rec.start_line}-L{rec.end_line}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Query Client GFX Archaeology Database")
    parser.add_argument("--db", default=None, help="Path to TW13081901.sqlite")
    parser.add_argument("--gfx", type=int, default=None, help="Lookup by GFX ID")
    parser.add_argument("--action", default=None, help="Filter by action name (walk, attack, death, breath, etc.)")
    parser.add_argument("--weapon", default=None, help="Filter by weapon variant (sword, dagger, bow, etc.)")
    parser.add_argument("--name", default=None, help="Search by name substring")
    parser.add_argument("--framerate", action="store_true", help="Display framerate metadata")
    parser.add_argument("--limit", type=int, default=10, help="Max results for list/search queries")
    args = parser.parse_args()

    store = ClientGfxEvidenceStore(args.db)
    meta = store.get_source_metadata()

    # Case 1: Specific GFX lookup
    if args.gfx is not None:
        rec = store.query_gfx(args.gfx)
        if not rec:
            print(f"[NOT FOUND] GFX ID {args.gfx} not found in client database.")
            sys.exit(1)
        display_gfx(rec, meta, show_framerate_only=args.framerate, specific_action=args.action, specific_weapon=args.weapon)
        return

    # Case 2: Name search
    if args.name is not None:
        recs = store.search_by_name(args.name, limit=args.limit)
        if not recs:
            print(f"[NOT FOUND] No GFX found matching name '{args.name}'.")
            sys.exit(1)
        print(f"Found {len(recs)} matching GFX records for '{args.name}':\n")
        for r in recs:
            display_gfx(r, meta, show_framerate_only=args.framerate, specific_action=args.action, specific_weapon=args.weapon)
            print("-" * 50)
        return

    # Case 3: Action & Weapon cross-GFX search
    if args.action is not None:
        anims = store.query_actions(args.action, weapon=args.weapon, limit=args.limit)
        if not anims:
            print(f"[NOT FOUND] No actions matching '{args.action}' (weapon={args.weapon}).")
            sys.exit(1)
        print(f"Targeted Action Evidence: {len(anims)} results for action='{args.action}', weapon={args.weapon}\n")
        for a in anims:
            gfx_rec = store.query_gfx(a.gfx_id)
            gname = gfx_rec.name if gfx_rec else "unknown"
            lbl = format_action_label(a)
            print(f"GFX {a.gfx_id:5d} ({gname}):")
            print(f"  Action:        {lbl}")
            print(f"  FrameRate:     {a.frame_rate or (gfx_rec.framerate if gfx_rec else None) or 'UNKNOWN'}")
            print(f"  Raw evidence:  TW13081901.txt:L{a.start_line}-L{a.end_line}")
            print(f"  Sequence:      {a.raw_sequence[:60]}...")
            print("-" * 40)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
