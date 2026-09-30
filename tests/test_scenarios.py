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


if __name__ == "__main__":
    unittest.main()
