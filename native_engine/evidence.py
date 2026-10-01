"""
native_engine/evidence.py - Legacy Evidence Corpus Query Layer & Provenance Model

Enforces strict separation:
- Raw sources are indexed into structured stores.
- Query API accesses Evidence Store without loading raw 7MB+ files into memory.
- All evidence claims carry full provenance (source_id, version, layer, classification, SHA256, line ranges).
"""
import dataclasses
from dataclasses import dataclass, field
import json
import os
import sqlite3
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class EvidenceRecord:
    source_id: str
    version: str
    layer: str
    classification: str
    sha256: str
    claim: str
    raw_reference: str
    notes: str = ""


@dataclass
class GfxAnimationRecord:
    gfx_id: int
    action_id: int
    action_name: str
    weapon: Optional[str]
    frame_count: Optional[int]
    frame_rate: Optional[int]
    raw_sequence: str
    start_line: int
    end_line: int


@dataclass
class GfxRecord:
    gfx_id: int
    sprite_id: int
    name: str
    version: str
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int
    framerate: Optional[int] = None
    animations: List[GfxAnimationRecord] = field(default_factory=list)
    references: List[Tuple[str, int]] = field(default_factory=list)


class ClientGfxEvidenceStore:
    """
    Evidence Query API for TW13081901.sqlite.
    Provides fast, indexed queries into 3.80 client animation tables.
    """
    DEFAULT_DB_PATH = "legacy/client/3.80/TW13081901.sqlite"

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self.DEFAULT_DB_PATH
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Client GFX SQLite database not found at '{self.db_path}'. "
                "Run `python tools/index_client_gfx.py` first."
            )
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def get_source_metadata(self) -> Dict[str, str]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM evidence_source LIMIT 1;")
        row = cur.fetchone()
        if not row:
            return {}
        return dict(row)

    def query_gfx(self, gfx_id: int) -> Optional[GfxRecord]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM gfx WHERE gfx_id = ? ORDER BY id ASC LIMIT 1;", (gfx_id,))
        row = cur.fetchone()
        if not row:
            return None

        # Fetch animations
        cur.execute("""
            SELECT * FROM gfx_animation 
            WHERE gfx_id = ? 
            ORDER BY action_id ASC;
        """, (gfx_id,))
        anim_rows = cur.fetchall()
        anims = [
            GfxAnimationRecord(
                gfx_id=r["gfx_id"],
                action_id=r["action_id"],
                action_name=r["action_name"],
                weapon=r["weapon"],
                frame_count=r["frame_count"],
                frame_rate=r["frame_rate"],
                raw_sequence=r["raw_sequence"],
                start_line=r["start_line"],
                end_line=r["end_line"]
            )
            for r in anim_rows
        ]

        # Extract framerate (if recorded on any animation row)
        fr = next((a.frame_rate for a in anims if a.frame_rate is not None), None)

        # Fetch references
        cur.execute("SELECT reference_type, reference_id FROM gfx_reference WHERE gfx_id = ?;", (gfx_id,))
        refs = [(r["reference_type"], r["reference_id"]) for r in cur.fetchall()]

        return GfxRecord(
            gfx_id=row["gfx_id"],
            sprite_id=row["sprite_id"],
            name=row["name"],
            version=row["version"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            framerate=fr,
            animations=anims,
            references=refs
        )

    def search_by_name(self, name_pattern: str, limit: int = 50) -> List[GfxRecord]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT gfx_id FROM gfx WHERE name LIKE ? ORDER BY gfx_id ASC LIMIT ?;",
            (f"%{name_pattern}%", limit)
        )
        return [self.query_gfx(r["gfx_id"]) for r in cur.fetchall() if r["gfx_id"] is not None]

    def query_actions(
        self,
        action_name: str,
        weapon: Optional[str] = None,
        gfx_id: Optional[int] = None,
        limit: int = 50
    ) -> List[GfxAnimationRecord]:
        cur = self.conn.cursor()
        query = "SELECT * FROM gfx_animation WHERE action_name = ?"
        params: List[any] = [action_name]

        if weapon is not None:
            query += " AND weapon = ?"
            params.append(weapon)

        if gfx_id is not None:
            query += " AND gfx_id = ?"
            params.append(gfx_id)

        query += " ORDER BY gfx_id ASC LIMIT ?;"
        params.append(limit)

        cur.execute(query, params)
        return [
            GfxAnimationRecord(
                gfx_id=r["gfx_id"],
                action_id=r["action_id"],
                action_name=r["action_name"],
                weapon=r["weapon"],
                frame_count=r["frame_count"],
                frame_rate=r["frame_rate"],
                raw_sequence=r["raw_sequence"],
                start_line=r["start_line"],
                end_line=r["end_line"]
            )
            for r in cur.fetchall()
        ]

    def close(self):
        self.conn.close()
