"""Test the public synthetic counterexample to post-hoc equivalence."""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_threshold_equivalence.py"


class ThresholdEquivalenceTest(unittest.TestCase):
    def test_counterexample_is_executable(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["scope"], "synthetic_counterexample_only")
        self.assertFalse(report["posthoc_equals_full_rerun"])
        self.assertEqual(report["baseline_record_count"], 2)
        self.assertEqual(report["posthoc_record_count"], 1)
        self.assertEqual(report["full_rerun_record_count"], 0)
        self.assertFalse(report["clinical_probability"])
        self.assertIsNone(report["hidden_top_n"])
        self.assertEqual(report["external_actions"], 0)


if __name__ == "__main__":
    unittest.main()
