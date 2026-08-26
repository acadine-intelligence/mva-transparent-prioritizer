from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class KnownBadRunnerTests(unittest.TestCase):
    def test_runner_executes_the_exact_named_adversarial_set(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/known_bad_tests.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        status = json.loads(completed.stdout)
        self.assertEqual(status["state"], "passed")
        self.assertEqual(status["external_actions"], 0)
        self.assertEqual(status["case_count"], len(status["cases"]))
        self.assertEqual(
            status["cases"],
            [
                "canary_projection",
                "canary_tree_scan",
                "caller_selected_private_output",
                "duplicate_json_key",
                "forbidden_fields",
                "manifest_stale_receipt",
                "no_clobber_projection",
                "public_source_artifact",
                "root_overlap",
                "score_tamper_rehash",
                "source_machine_path",
                "symlink_special_oversize",
                "symlink_tree_scan",
                "unknown_as_zero",
                "unsafe_relative_path",
            ],
        )


if __name__ == "__main__":
    unittest.main()
