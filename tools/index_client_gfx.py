"""
tools/index_client_gfx.py - One-time SQLite Indexer for TW13081901.txt

Classification:
  LEGACY_CLIENT_OBSERVED (CROSS_VERSION_AUXILIARY)

Parses TW13081901.txt line-by-line and builds a high-performance SQLite index
at legacy/client/3.80/TW13081901.sqlite.
Tracks exact line ranges and byte offsets for byte-level provenance.
Supports multi-framerate timing segments (e.g. GFX 18310).
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time

SOURCE_ID = "legacy-client-tw13081901"
VERSION = "3.80"
LAYER = "client"
CLASSIFICATION = "LEGACY_CLIENT_OBSERVED"
EXPECTED_SHA256 = "ddcbd759d4124877768990db505a8b1f7b7cbba23e7e78fe7e3fafd4bda356fe"

HEADER_RE = re.compile(r"^#(\d+)\s+([^=\s]+)(?:=(\S+))?(?:\s+(.*))?$")
ACTION_RE = re.compile(r"^(\d+)\.([^(]*)\((.*)\)$")
FRAME_COUNT_RE = re.compile(r"^\d+\s+(\d+),")


def create_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS evidence_source (
        source_id TEXT PRIMARY KEY,
        version TEXT,
        layer TEXT,
        classification TEXT,
        path TEXT,
        sha256 TEXT,
        notes TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gfx (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gfx_id INTEGER,
        sprite_id INTEGER,
        name TEXT,
        version TEXT,
        start_line INTEGER,
        end_line INTEGER,
        start_offset INTEGER,
        end_offset INTEGER
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gfx_timing_segment (
        segment_id INTEGER PRIMARY KEY,
        gfx_id INTEGER,
        segment_index INTEGER,
        framerate INTEGER,
        start_line INTEGER,
        end_line INTEGER,
        action_count INTEGER,
        FOREIGN KEY(gfx_id) REFERENCES gfx(gfx_id)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gfx_animation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gfx_id INTEGER,
        segment_id INTEGER,
        action_id INTEGER,
        action_name TEXT,
        weapon TEXT,
        frame_count INTEGER,
        frame_rate INTEGER,
        raw_sequence TEXT,
        start_line INTEGER,
        end_line INTEGER,
        FOREIGN KEY(gfx_id) REFERENCES gfx(gfx_id),
        FOREIGN KEY(segment_id) REFERENCES gfx_timing_segment(segment_id)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gfx_reference (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gfx_id INTEGER,
        reference_type TEXT,
        reference_id INTEGER,
        FOREIGN KEY(gfx_id) REFERENCES gfx(gfx_id)
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gfx_id ON gfx(gfx_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_gfx_name ON gfx(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_segment_gfx_id ON gfx_timing_segment(gfx_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anim_gfx_id ON gfx_animation(gfx_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anim_segment_id ON gfx_animation(segment_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anim_action_name ON gfx_animation(action_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anim_weapon ON gfx_animation(weapon);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anim_action_weapon ON gfx_animation(action_name, weapon);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ref_gfx_id ON gfx_reference(gfx_id);")
    conn.commit()


def compute_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha.update(chunk)
    return sha.hexdigest()


def index_client_gfx(
    source_path: str = "TW13081901.txt",
    db_path: str = "legacy/client/3.80/TW13081901.sqlite",
    verify_hash: bool = True
):
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    print(f"[INDEXER] Reading raw source: {source_path}")
    file_size = os.path.getsize(source_path)
    print(f"          Size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")

    if verify_hash:
        print("[INDEXER] Verifying SHA256 hash...")
        actual_sha = compute_sha256(source_path)
        if actual_sha != EXPECTED_SHA256:
            raise ValueError(f"Hash mismatch! Expected {EXPECTED_SHA256}, got {actual_sha}")
        print(f"          SHA256 OK: {actual_sha}")
    else:
        actual_sha = EXPECTED_SHA256

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    create_schema(conn)

    # Insert evidence_source record
    conn.cursor().execute("""
    INSERT INTO evidence_source (source_id, version, layer, classification, path, sha256, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        SOURCE_ID,
        VERSION,
        LAYER,
        CLASSIFICATION,
        os.path.abspath(source_path),
        actual_sha,
        "TW 3.80 client animation and sprite metadata definition table (TW13081901.txt)"
    ))

    t0 = time.perf_counter()
    print("[INDEXER] Scanning lines and building SQLite index...")

    gfx_records = []
    anim_records = []
    ref_records = []
    timing_segments = []

    segment_id_counter = 1

    current_gfx = None
    current_seg_index = 0
    active_segment = None

    line_num = 0

    with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            line_start_offset = f.tell()
            line = f.readline()
            if not line:
                break
            line_num += 1
            line_str = line.strip()

            if line_str.startswith("#"):
                # Finalize previous GFX and its active segment
                if current_gfx:
                    current_gfx["end_line"] = line_num - 1
                    current_gfx["end_offset"] = line_start_offset
                    gfx_records.append((
                        current_gfx["gfx_id"],
                        current_gfx["sprite_id"],
                        current_gfx["name"],
                        VERSION,
                        current_gfx["start_line"],
                        current_gfx["end_line"],
                        current_gfx["start_offset"],
                        current_gfx["end_offset"]
                    ))

                if active_segment:
                    if active_segment["action_count"] > 0:
                        active_segment["end_line"] = line_num - 1
                        timing_segments.append(active_segment)
                    active_segment = None

                m = HEADER_RE.match(line_str)
                if m:
                    gfx_id = int(m.group(1))
                    try:
                        sprite_id = int(m.group(2))
                    except ValueError:
                        sprite_id = 0
                    name = m.group(4) or ""
                    current_gfx = {
                        "gfx_id": gfx_id,
                        "sprite_id": sprite_id,
                        "name": name,
                        "start_line": line_num,
                        "start_offset": line_start_offset,
                        "end_line": line_num,
                        "end_offset": line_start_offset
                    }
                    current_seg_index = 0
                    active_segment = None
                else:
                    current_gfx = None
                    current_seg_index = 0
                    active_segment = None

            elif current_gfx and line_str:
                m = ACTION_RE.match(line_str)
                if m:
                    act_id = int(m.group(1))
                    raw_act_name = m.group(2).strip()
                    content = m.group(3).strip()

                    # Framerate segment boundary
                    if raw_act_name == "framerate" or act_id == 110:
                        try:
                            fr_val = int(content)
                        except ValueError:
                            fr_val = None

                        if active_segment is not None and active_segment["action_count"] > 0:
                            # Finalize previous segment with actions
                            active_segment["end_line"] = line_num - 1
                            timing_segments.append(active_segment)
                            active_segment = None

                        if active_segment is None:
                            current_seg_index += 1
                            active_segment = {
                                "segment_id": segment_id_counter,
                                "gfx_id": current_gfx["gfx_id"],
                                "segment_index": current_seg_index,
                                "framerate": fr_val,
                                "start_line": line_num,
                                "end_line": line_num,
                                "action_count": 0
                            }
                            segment_id_counter += 1
                        else:
                            # Immediate consecutive framerate without intervening actions (override)
                            active_segment["framerate"] = fr_val
                            active_segment["start_line"] = line_num
                            active_segment["end_line"] = line_num
                        continue

                    # References
                    if raw_act_name in ("shadow", "type", "clothes") or act_id in (101, 102, 105):
                        ref_type = raw_act_name if raw_act_name else str(act_id)
                        tokens = content.split()
                        if ref_type == "clothes" and len(tokens) >= 2:
                            for cid in tokens[1:]:
                                try:
                                    ref_records.append((current_gfx["gfx_id"], ref_type, int(cid)))
                                except ValueError:
                                    pass
                        else:
                            for token in tokens:
                                try:
                                    ref_records.append((current_gfx["gfx_id"], ref_type, int(token)))
                                except ValueError:
                                    pass
                        continue

                    # Regular Actions
                    act_name = raw_act_name
                    weapon = None
                    if raw_act_name.startswith("attack "):
                        act_name = "attack"
                        weapon = raw_act_name[7:].strip()
                    elif raw_act_name == "attack":
                        act_name = "attack"
                        weapon = None

                    # If an action appears before any framerate declaration
                    if active_segment is None:
                        current_seg_index += 1
                        active_segment = {
                            "segment_id": segment_id_counter,
                            "gfx_id": current_gfx["gfx_id"],
                            "segment_index": current_seg_index,
                            "framerate": None,
                            "start_line": line_num,
                            "end_line": line_num,
                            "action_count": 0
                        }
                        segment_id_counter += 1

                    active_segment["action_count"] += 1
                    active_segment["end_line"] = line_num

                    # Extract frame count
                    frame_count = None
                    f_match = FRAME_COUNT_RE.match(content)
                    if f_match:
                        try:
                            frame_count = int(f_match.group(1))
                        except ValueError:
                            frame_count = None

                    anim_records.append((
                        current_gfx["gfx_id"],
                        active_segment["segment_id"],
                        act_id,
                        act_name,
                        weapon,
                        frame_count,
                        active_segment["framerate"],
                        content,
                        line_num,
                        line_num
                    ))

        # Close final GFX and final segment
        if current_gfx:
            current_gfx["end_line"] = line_num
            current_gfx["end_offset"] = f.tell()
            gfx_records.append((
                current_gfx["gfx_id"],
                current_gfx["sprite_id"],
                current_gfx["name"],
                VERSION,
                current_gfx["start_line"],
                current_gfx["end_line"],
                current_gfx["start_offset"],
                current_gfx["end_offset"]
            ))

        if active_segment and active_segment["action_count"] > 0:
            active_segment["end_line"] = line_num
            timing_segments.append(active_segment)

    print(f"[INDEXER] Parsing complete in {time.perf_counter() - t0:.2f}s.")
    print(f"          Total GFX parsed:             {len(gfx_records):,}")
    print(f"          Total Timing Segments parsed: {len(timing_segments):,}")
    print(f"          Total Animations parsed:      {len(anim_records):,}")
    print(f"          Total References parsed:      {len(ref_records):,}")

    t1 = time.perf_counter()
    print("[INDEXER] Writing batches to SQLite...")
    cur = conn.cursor()
    cur.executemany("""
    INSERT INTO gfx (gfx_id, sprite_id, name, version, start_line, end_line, start_offset, end_offset)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, gfx_records)

    cur.executemany("""
    INSERT INTO gfx_timing_segment (segment_id, gfx_id, segment_index, framerate, start_line, end_line, action_count)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (s["segment_id"], s["gfx_id"], s["segment_index"], s["framerate"], s["start_line"], s["end_line"], s["action_count"])
        for s in timing_segments
    ])

    cur.executemany("""
    INSERT INTO gfx_animation (gfx_id, segment_id, action_id, action_name, weapon, frame_count, frame_rate, raw_sequence, start_line, end_line)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, anim_records)

    cur.executemany("""
    INSERT INTO gfx_reference (gfx_id, reference_type, reference_id)
    VALUES (?, ?, ?)
    """, ref_records)

    conn.commit()
    conn.close()

    db_size = os.path.getsize(db_path)
    print(f"[INDEXER] SQLite commit completed in {time.perf_counter() - t1:.2f}s.")
    print(f"[INDEXER] Created SQLite database at: {db_path} ({db_size / (1024*1024):.2f} MB)")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TW13081901 SQLite Indexer")
    parser.add_argument("--source", default="TW13081901.txt", help="Path to raw TW13081901.txt")
    parser.add_argument("--db", default="legacy/client/3.80/TW13081901.sqlite", help="Target SQLite path")
    parser.add_argument("--no-verify", action="store_true", help="Skip SHA256 check")
    args = parser.parse_args()

    success = index_client_gfx(source_path=args.source, db_path=args.db, verify_hash=not args.no_verify)
    sys.exit(0 if success else 1)
