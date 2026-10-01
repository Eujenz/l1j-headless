"""
tests/test_client_gfx_parser.py - Pure Unit Tests for Client GFX Parser

Reproducibility Policy:
- ZERO external dependencies. Does not require 7MB TW13081901.txt or SQLite index.
- Validates all edge cases of client definition parsing using memory streams.
"""
import io
import unittest

from tools.index_client_gfx import parse_client_gfx_stream


class TestClientGfxParser(unittest.TestCase):
    def test_multiple_framerate_segments(self):
        """
        Validates GFX with multiple framerate declarations (e.g. Silvia #18310 pattern):
        - Consecutive framerate lines without actions: 52 then 36 -> framerate 36
        - Segment 1: actions with framerate 36
        - Segment 2: declared framerate 59 with actions
        """
        raw = io.StringIO(
            "#18310 88 Legend_Silvia\n"
            "        110.framerate(52)\n"
            "        110.framerate(36)\n"
            "        0.RunL(1 8,16.0:2 16.1:2)\n"
            "        4.RunR OnehandSword(1 8,8.0:2 8.1:2)\n"
            "        110.framerate(59)\n"
            "        3.Breath(1 12,24.0:4 24.1:4)\n"
            "        2.Damage(1 3,64.0:4 64.1:4)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(gfx), 1)
        self.assertEqual(gfx[0][0], 18310)

        # Must generate exactly 2 timing segments
        self.assertEqual(len(segments), 2)

        seg1 = segments[0]
        self.assertEqual(seg1["segment_index"], 1)
        self.assertEqual(seg1["framerate"], 36)
        self.assertEqual(seg1["action_count"], 2)

        seg2 = segments[1]
        self.assertEqual(seg2["segment_index"], 2)
        self.assertEqual(seg2["framerate"], 59)
        self.assertEqual(seg2["action_count"], 2)

        # Check action mappings
        self.assertEqual(len(anims), 4)
        self.assertEqual(anims[0][1], seg1["segment_id"])
        self.assertEqual(anims[0][6], 36)  # frame_rate
        self.assertEqual(anims[1][1], seg1["segment_id"])
        self.assertEqual(anims[1][6], 36)

        self.assertEqual(anims[2][1], seg2["segment_id"])
        self.assertEqual(anims[2][6], 59)
        self.assertEqual(anims[3][1], seg2["segment_id"])
        self.assertEqual(anims[3][6], 59)

    def test_gfx_without_framerate(self):
        """Validates a GFX that declares actions but never declares a framerate."""
        raw = io.StringIO(
            "#999 10 No_Framerate_Mob\n"
            "        0.walk(1 4,0.0:2 0.1:2)\n"
            "        8.death(1 4,8.0:2 8.1:2)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(gfx), 1)
        self.assertEqual(len(segments), 1)
        self.assertIsNone(segments[0]["framerate"])
        self.assertEqual(segments[0]["action_count"], 2)

        self.assertEqual(len(anims), 2)
        self.assertIsNone(anims[0][6])  # frame_rate is None
        self.assertIsNone(anims[1][6])

    def test_action_before_framerate(self):
        """Validates an action appearing before any framerate declaration."""
        raw = io.StringIO(
            "#1001 20 Early_Action\n"
            "        0.walk(1 4,0.0:2 0.1:2)\n"
            "        110.framerate(45)\n"
            "        1.attack(1 6,10.0:2 10.1:2)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(gfx), 1)
        self.assertEqual(len(segments), 2)

        # First segment (early action without framerate)
        self.assertIsNone(segments[0]["framerate"])
        self.assertEqual(segments[0]["action_count"], 1)

        # Second segment (with framerate 45)
        self.assertEqual(segments[1]["framerate"], 45)
        self.assertEqual(segments[1]["action_count"], 1)

        self.assertIsNone(anims[0][6])
        self.assertEqual(anims[1][6], 45)

    def test_action_after_framerate(self):
        """Standard canonical pattern: framerate followed by actions."""
        raw = io.StringIO(
            "#18315 56 tw xiaolongbao monster\n"
            "        110.framerate(36)\n"
            "        0.walk(1 8,0.0:4 0.1:4)\n"
            "        1.attack(1 6,8.0:4 8.1:4)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(gfx), 1)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["framerate"], 36)
        self.assertEqual(segments[0]["action_count"], 2)
        self.assertEqual(anims[0][6], 36)
        self.assertEqual(anims[1][6], 36)

    def test_weapon_specific_action(self):
        """Validates parsing of weapon-specific action names like 'attack dagger'."""
        raw = io.StringIO(
            "#18315 56 tw xiaolongbao monster\n"
            "        110.framerate(36)\n"
            "        47.attack dagger(1 6,8.0:4 16.0:4)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(anims), 1)
        act = anims[0]
        self.assertEqual(act[2], 47)          # action_id
        self.assertEqual(act[3], "attack")    # action_name
        self.assertEqual(act[4], "dagger")    # weapon
        self.assertEqual(act[5], 6)           # frame_count

    def test_reference_with_multiple_ids(self):
        """Validates reference parsing for multi-id lines (e.g. clothes with multiple IDs)."""
        raw = io.StringIO(
            "#18315 56 tw xiaolongbao monster\n"
            "        101.shadow(18316)\n"
            "        102.type(10)\n"
            "        105.clothes(2 18317 18318)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(refs), 4)
        ref_pairs = [(r[1], r[2]) for r in refs]
        self.assertIn(("shadow", 18316), ref_pairs)
        self.assertIn(("type", 10), ref_pairs)
        self.assertIn(("clothes", 18317), ref_pairs)
        self.assertIn(("clothes", 18318), ref_pairs)

    def test_duplicate_gfx_header_behavior(self):
        """
        Validates behavior when the same GFX ID appears multiple times
        (as GFX 22232 does in TW13081901.txt).
        Both GFX blocks are parsed and preserved.
        """
        raw = io.StringIO(
            "#22232 0 First_Appearance\n"
            "        110.framerate(30)\n"
            "        0.walk(1 4,0.0:2 0.1:2)\n"
            "#22232 0 Second_Appearance\n"
            "        110.framerate(40)\n"
            "        1.attack(1 6,1.0:2 1.1:2)\n"
        )
        gfx, segments, anims, refs = parse_client_gfx_stream(raw)
        self.assertEqual(len(gfx), 2)
        self.assertEqual(gfx[0][0], 22232)
        self.assertEqual(gfx[0][2], "First_Appearance")
        self.assertEqual(gfx[1][0], 22232)
        self.assertEqual(gfx[1][2], "Second_Appearance")


if __name__ == "__main__":
    unittest.main()
