"""Exercise the count-basis CLI with synthetic input files."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests.test_receipt_basis import synthetic_receipt

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_receipt_basis.py"


def run_validator(*paths):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, paths)],
                          capture_output=True, text=True, cwd=tempfile.gettempdir())


class ValidatorCliTest(unittest.TestCase):
    def run_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(text)
            return run_validator(path)

    def test_valid_labeled_receipt_passes(self):
        result = self.run_text(json.dumps(synthetic_receipt()))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_unlabeled_count_fails_closed(self):
        payload = synthetic_receipt()
        payload["lanes"]["l1"]["rows"] = 8
        result = self.run_text(json.dumps(payload))
        self.assertEqual(result.returncode, 1)
        self.assertIn("VIOLATION", result.stdout)

    def test_partition_sum_mismatch_fails_closed(self):
        payload = synthetic_receipt()
        payload["partition"]["total"] = 5
        result = self.run_text(json.dumps(payload))
        self.assertEqual(result.returncode, 1)
        self.assertIn("partition total mismatch", result.stdout)

    def test_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_validator(Path(directory) / "missing.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("VIOLATION", result.stdout)

    def test_bad_json_has_bounded_errors(self):
        duplicate = json.dumps(synthetic_receipt())[:-1] + ',"lanes":{}}'
        for text in ("{", "null", "[]", '"SYNTHETIC_CANARY"', "{}", duplicate, '{"lanes":NaN}'):
            with self.subTest(text=text):
                result = self.run_text(text)
                self.assertEqual(result.returncode, 1)
                self.assertIn("VIOLATION", result.stdout)
                self.assertEqual(result.stderr, "")
                self.assertNotIn("SYNTHETIC_CANARY", result.stdout)

    def test_cli_rejects_unrecognized_flat_shape(self):
        payload = {"genes": synthetic_receipt()["lanes"]["l1"]}
        result = self.run_text(json.dumps(payload))
        self.assertEqual(result.returncode, 1)

    def test_batch_reports_each_file_and_fails_if_one_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("bad.json", "good.json")]
            paths[0].write_text("{")
            paths[1].write_text(json.dumps(synthetic_receipt()))
            result = run_validator(*paths)
        self.assertEqual(result.returncode, 1)
        self.assertIn("input 1", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_no_arguments_fail(self):
        self.assertEqual(run_validator().returncode, 1)


if __name__ == "__main__":
    unittest.main()
