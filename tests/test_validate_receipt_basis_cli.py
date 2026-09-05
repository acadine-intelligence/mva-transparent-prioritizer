"""Tests for scripts/validate_receipt_basis.py (CLI validator)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_receipt_basis.py"


def run_validator(*paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(p) for p in paths]],
        capture_output=True, text=True,
    )


class ValidatorCliTest(unittest.TestCase):
    def test_valid_labeled_receipt_passes(self):
        receipt = {
            "lanes": {
                "l1": {"rows": {"basis": "tsv_rows", "count": 794},
                       "unique_keys": {"basis": "unique_keys", "count": 589}},
            },
            "partition": {"basis": "unique_keys", "shared": 165,
                          "only_l1": 424, "only_l2": 200, "total": 789},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(receipt, f)
            path = Path(f.name)
        result = run_validator(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)
        path.unlink()

    def test_unlabeled_count_fails_closed(self):
        receipt = {"lanes": {"l1": {"rows": 794}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(receipt, f)
            path = Path(f.name)
        result = run_validator(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("VIOLATION", result.stdout)
        path.unlink()

    def test_partition_sum_mismatch_fails_closed(self):
        receipt = {
            "lanes": {"l1": {"rows": {"basis": "tsv_rows", "count": 794}}},
            "partition": {"basis": "unique_keys", "shared": 165,
                          "only_l1": 424, "only_l2": 200, "total": 589},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(receipt, f)
            path = Path(f.name)
        result = run_validator(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("sums to 789", result.stdout)
        path.unlink()

    def test_missing_file_fails_closed(self):
        result = run_validator(Path("/nonexistent/receipt.json"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a file", result.stdout)


if __name__ == "__main__":
    unittest.main()
