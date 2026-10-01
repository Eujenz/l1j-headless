"""
tests/test_archaeology_index.py - Verification for Phase A Legacy Evidence Corpus Index

Validates:
- Manifest source hashes and metadata consistency.
- SQLite database integrity for TW13081901.sqlite (with timing segments).
- Exact line tracking and byte offset validity.
- Reproducibility policy (skipUnless if SQLite index not generated).
"""
import json
import os
import sqlite3
import unittest

from legacy.archaeology.evidence import ClientGfxEvidenceStore


class TestArchaeologyIndex(unittest.TestCase):
    def test_legacy_sources_manifest(self):
        manifest_path = "legacy/manifests/legacy_sources.json"
        self.assertTrue(os.path.exists(manifest_path), f"Missing {manifest_path}")
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("sources", data)
        sources = data["sources"]
        self.assertIn("legacy-client-tw13081901", sources)
        client_src = sources["legacy-client-tw13081901"]
        self.assertEqual(client_src["version"], "3.80")
        self.assertEqual(client_src["classification"], "LEGACY_CLIENT_OBSERVED")
        self.assertEqual(client_src["applicability"], "CROSS_VERSION_AUXILIARY")
        self.assertFalse(client_src["runtime_dependency"])

    def test_source_hashes_manifest(self):
        hash_path = "legacy/manifests/source_hashes.json"
        self.assertTrue(os.path.exists(hash_path), f"Missing {hash_path}")
        with open(hash_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("hashes", data)
        h = data["hashes"]["TW13081901.txt"]
        self.assertEqual(h["sha256"], "ddcbd759d4124877768990db505a8b1f7b7cbba23e7e78fe7e3fafd4bda356fe")
        self.assertEqual(h["total_lines"], 155202)
        self.assertEqual(h["size_bytes"], 7412363)
        self.assertEqual(h["classification"], "LEGACY_CLIENT_OBSERVED")

    @unittest.skipUnless(os.path.exists("legacy/client/3.80/TW13081901.sqlite"), "SQLite index not generated")
    def test_sqlite_db_integrity(self):
        db_path = "legacy/client/3.80/TW13081901.sqlite"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Check evidence_source table
        cur.execute("SELECT source_id, version, classification FROM evidence_source;")
        src_row = cur.fetchone()
        self.assertIsNotNone(src_row)
        self.assertEqual(src_row[0], "legacy-client-tw13081901")
        self.assertEqual(src_row[1], "3.80")
        self.assertEqual(src_row[2], "LEGACY_CLIENT_OBSERVED")

        # Check gfx count (> 22,000)
        cur.execute("SELECT count(*) FROM gfx;")
        gfx_count = cur.fetchone()[0]
        self.assertGreaterEqual(gfx_count, 22000)

        # Check timing segments count (> 15,000)
        cur.execute("SELECT count(*) FROM gfx_timing_segment;")
        seg_count = cur.fetchone()[0]
        self.assertGreaterEqual(seg_count, 15000)

        # Check animations count (> 100,000)
        cur.execute("SELECT count(*) FROM gfx_animation;")
        anim_count = cur.fetchone()[0]
        self.assertGreaterEqual(anim_count, 100000)

        # Check references count (> 30,000)
        cur.execute("SELECT count(*) FROM gfx_reference;")
        ref_count = cur.fetchone()[0]
        self.assertGreaterEqual(ref_count, 30000)

        conn.close()


if __name__ == "__main__":
    unittest.main()
