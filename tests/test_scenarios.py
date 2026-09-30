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


if __name__ == "__main__":
    unittest.main()
