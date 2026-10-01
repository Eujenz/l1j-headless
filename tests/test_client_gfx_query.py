"""
tests/test_client_gfx_query.py - Verification for Client GFX Evidence Query API & CLI

Validates:
- GFX 18315 lookup returns exact metadata, framerate 36, and actions.
- Action & weapon queries (e.g. attack dagger).
- Exact raw line range tracking against TW13081901.txt.
"""
import os
import subprocess
import sys
import unittest

from native_engine.evidence import ClientGfxEvidenceStore


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

    def test_cli_execution(self):
        cmd = [sys.executable, "tools/query_client_gfx.py", "--gfx", "18315"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0)
        self.assertIn("18315", res.stdout)
        self.assertIn("tw xiaolongbao monster", res.stdout)
        self.assertIn("FrameRate:", res.stdout)
        self.assertIn("TW13081901.txt:L127807-L127830", res.stdout)


if __name__ == "__main__":
    unittest.main()
