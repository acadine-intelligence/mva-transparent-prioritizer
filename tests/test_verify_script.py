from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VerifyScriptTests(unittest.TestCase):
    def test_verify_script_exercises_compile_known_bad_and_synthetic_journey(self) -> None:
        environment = os.environ.copy()
        environment["MVA_VERIFY_TEST_MODE"] = "1"
        completed = subprocess.run(
            ["bash", "scripts/verify.sh"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("compile=pass", completed.stdout)
        self.assertIn("known_bad=pass", completed.stdout)
        self.assertIn("public_source_scan=pass", completed.stdout)
        self.assertIn("synthetic_journey=pass", completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
