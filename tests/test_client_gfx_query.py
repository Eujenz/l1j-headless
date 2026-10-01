"""
tests/test_client_gfx_query.py - Verification for Client GFX Evidence Query API & CLI

Validates:
- GFX 18315 lookup returns exact metadata, framerate 36, and actions.
- GFX 18310 multi-framerate timing segments (Segment 1: 36, Segment 2: 59).
- Action & weapon queries (e.g. attack dagger).
- CLI execution and output formatting.
- Duplicate GFX header resilience.
- Reproducibility policy (skipUnless if SQLite index not generated).
"""
import os
import subprocess
import sys
import unittest

DB_EXISTS = os.path.exists("legacy/client/3.80/TW13081901.sqlite")

if DB_EXISTS:
    from legacy.archaeology.evidence import ClientGfxEvidenceStore


@unittest.skipUnless(DB_EXISTS, "SQLite index not generated; run python tools/index_client_gfx.py first")
class TestClientGfxQuery(unittest.TestCase):
    def setUp(self):
        self.store = ClientGfxEvidenceStore()

    def tearDown(self):
        self.store.close()

    def test_query_gfx_18315(self):
        rec = self.store.query_gfx(18315)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.gfx_id, 18315)
        self.assertEqual(rec.sprite_id, 56)
        self.assertEqual(rec.name, "tw xiaolongbao monster")
        self.assertEqual(rec.framerate, 36)
        self.assertEqual(rec.start_line, 127807)
        self.assertEqual(rec.end_line, 127830)
        self.assertEqual(len(rec.timing_segments), 1)
        self.assertEqual(rec.timing_segments[0].framerate, 36)

        # Check actions present
        action_names = {a.action_name for a in rec.animations}
        self.assertIn("walk", action_names)
        self.assertIn("attack", action_names)
        self.assertIn("death", action_names)
        self.assertIn("damage", action_names)

        # Check weapon-specific attack actions
        weapons = {a.weapon for a in rec.animations if a.action_name == "attack"}
        self.assertIn("sword", weapons)
        self.assertIn("dagger", weapons)
        self.assertIn("bow", weapons)
        self.assertIn("spear", weapons)

        # Check references
        ref_types = {r[0] for r in rec.references}
        self.assertIn("shadow", ref_types)
        self.assertIn("type", ref_types)
        self.assertIn("clothes", ref_types)

    def test_query_gfx_18310_multiple_framerate_segments(self):
        rec = self.store.query_gfx(18310)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.gfx_id, 18310)
        self.assertEqual(rec.sprite_id, 88)
        self.assertEqual(rec.name, "Legend_Silvia")
        
        # Must have exactly 2 active timing segments
        self.assertEqual(len(rec.timing_segments), 2)
        
        seg1 = rec.timing_segments[0]
        self.assertEqual(seg1.segment_index, 1)
        self.assertEqual(seg1.framerate, 36)
        self.assertEqual(seg1.start_line, 127658)
        self.assertEqual(seg1.end_line, 127670)
        self.assertEqual(seg1.action_count, 12)

        seg2 = rec.timing_segments[1]
        self.assertEqual(seg2.segment_index, 2)
        self.assertEqual(seg2.framerate, 59)
        self.assertEqual(seg2.start_line, 127671)
        self.assertEqual(seg2.action_count, 53)

        # Check actions assigned to Segment 1 (RunL, RunR)
        run_actions = [a for a in rec.animations if a.segment_id == seg1.segment_id]
        self.assertEqual(len(run_actions), 12)
        for a in run_actions:
            self.assertEqual(a.frame_rate, 36)
            self.assertTrue(a.action_name.startswith("Run"))

        # Check actions assigned to Segment 2 (Breath, Damage, Death, etc.)
        other_actions = [a for a in rec.animations if a.segment_id == seg2.segment_id]
        self.assertEqual(len(other_actions), 53)
        for a in other_actions:
            self.assertEqual(a.frame_rate, 59)

    def test_query_attack_dagger(self):
        anims = self.store.query_actions("attack", weapon="dagger", limit=10)
        self.assertGreaterEqual(len(anims), 1)
        xiaolong = next((a for a in anims if a.gfx_id == 18315), None)
        self.assertIsNotNone(xiaolong)
        self.assertEqual(xiaolong.action_id, 47)
        self.assertEqual(xiaolong.action_name, "attack")
        self.assertEqual(xiaolong.weapon, "dagger")
        self.assertEqual(xiaolong.frame_count, 6)
        self.assertEqual(xiaolong.start_line, 127817)

    def test_query_actions_by_segment(self):
        rec = self.store.query_gfx(18310)
        self.assertIsNotNone(rec)
        seg1_actions = self.store.query_actions_by_segment(rec.timing_segments[0].segment_id)
        self.assertEqual(len(seg1_actions), 12)
        self.assertEqual(seg1_actions[0].action_name, "RunL")

    def test_duplicate_gfx_header_handling(self):
        # GFX 22232 appears twice in TW13081901.txt
        rec = self.store.query_gfx(22232)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.gfx_id, 22232)

    def test_cli_execution(self):
        cmd = [sys.executable, "tools/query_client_gfx.py", "--gfx", "18315"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0)
        self.assertIn("18315", res.stdout)
        self.assertIn("tw xiaolongbao monster", res.stdout)
        self.assertIn("Classification:\n  LEGACY_CLIENT_OBSERVED", res.stdout)
        self.assertIn("FrameRate:", res.stdout)
        self.assertIn("TW13081901.txt:L127807-L127830", res.stdout)

    def test_cli_multi_segment_execution(self):
        cmd = [sys.executable, "tools/query_client_gfx.py", "--gfx", "18310"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Legend_Silvia", res.stdout)
        self.assertIn("Segment 1: framerate=36, actions=12", res.stdout)
        self.assertIn("Segment 2: framerate=59, actions=53", res.stdout)


if __name__ == "__main__":
    unittest.main()
