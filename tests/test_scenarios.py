"""
test_scenarios.py - Automated test suite executing certified scenario replays
and differential verification for L1J Headless Native Runtime.
"""

import subprocess
import sys
import unittest


class TestCertifiedScenarios(unittest.TestCase):
    def test_scenario_001_replay(self):
        res = subprocess.run([sys.executable, "scenario_001_replay.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 001 replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_002_replay(self):
        res = subprocess.run([sys.executable, "scenario_002_replay.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 002 replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_003_replay(self):
        res = subprocess.run([sys.executable, "scenario_003_replay.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 003 replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_003_differential(self):
        res = subprocess.run([sys.executable, "scenario_003_differential.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 003 differential verification failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 003 CONFORMANCE CERTIFICATION: PASS", res.stdout)

    def test_scenario_004_replay(self):
        res = subprocess.run([sys.executable, "scenario_004_replay.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 004 replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_004_differential(self):
        res = subprocess.run([sys.executable, "scenario_004_differential.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 004 differential verification failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 004 CONFORMANCE CERTIFICATION: PASS", res.stdout)

    def test_scenario_005_replay(self):
        res = subprocess.run([sys.executable, "scenario_005_replay.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 005 replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_005_differential(self):
        res = subprocess.run([sys.executable, "scenario_005_differential.py"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Scenario 005 differential verification failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 005 CONFORMANCE CERTIFICATION: PASS", res.stdout)

    def test_scenario_006_mvp_replay(self):
        res = subprocess.run([sys.executable, "mvp_replay.py"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"Scenario 006 MVP replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_006_mvp_demo(self):
        res = subprocess.run([sys.executable, "mvp.py", "--demo"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"Scenario 006 MVP demo failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("DEMO COMPLETED SUCCESSFULLY", res.stdout)

    def test_scenario_007_replay(self):
        res = subprocess.run([sys.executable, "scenario_007_replay.py"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"Scenario 007 replay failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("OVERALL STATUS: PASS", res.stdout)

    def test_scenario_007_differential(self):
        res = subprocess.run([sys.executable, "scenario_007_differential.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(res.returncode, 0, f"Scenario 007 differential verification failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 007 CONFORMANCE CERTIFICATION: PASS", res.stdout)

    def test_scenario_007_mvp_demo(self):
        res = subprocess.run([sys.executable, "mvp.py", "--demo", "--s007"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"Scenario 007 demo failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 007 DEMO COMPLETED", res.stdout)

    def test_scenario_008_autonomous_hunting(self):
        res = subprocess.run([sys.executable, "scenario_008_configurable_autonomous_hunting.py", "--duration", "600000"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"Scenario 008 failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 008 OVERALL STATUS: PASS", res.stdout)

    def test_scenario_009_headless_player_mvp(self):
        res = subprocess.run([sys.executable, "scenario_009_headless_player_mvp.py", "--duration", "600000"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"Scenario 009 failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("SCENARIO 009 OVERALL STATUS: PASS", res.stdout)


if __name__ == "__main__":
    unittest.main()

