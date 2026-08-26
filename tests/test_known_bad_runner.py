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
                "archive_absolute_link",
                "archive_ambiguous_link",
                "archive_ambiguous_path",
                "archive_ambiguous_target",
                "archive_broken_link",
                "archive_cyclic_link",
                "archive_directory_form_file",
                "archive_escaping_link",
                "archive_hard_link",
                "archive_special_member",
                "canary_projection",
                "canary_tree_scan",
                "caller_selected_private_output",
                "duplicate_json_key",
                "environment_reference_tamper",
                "environment_receipt_tamper",
                "environment_support_symlink",
                "environment_support_tamper",
                "environment_tool_tamper",
                "environment_unsafe_state",
                "environment_writable_tool",
                "forbidden_fields",
                "manifest_stale_receipt",
                "no_clobber_projection",
                "public_source_artifact",
                "reference_fetcher_symlink",
                "reference_receipt_symlink",
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
