"""Exercise the count-basis CLI with synthetic input files."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests.test_receipt_basis import synthetic_receipt

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_receipt_basis.py"


def run_validator(*paths):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, paths)],
                          capture_output=True, text=True, cwd=tempfile.gettempdir(), timeout=5)


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

    def test_size_limit_includes_exact_boundary(self):
        limit = 1024 * 1024  # Documented 1 MiB contract, independent of CLI constant.
        encoded = json.dumps(synthetic_receipt()).encode("utf-8")
        for size, expected in ((limit, 0), (limit + 1, 1)):
            with self.subTest(size=size), tempfile.TemporaryDirectory() as directory:
                raw = encoded + b" " * (size - len(encoded))
                path = Path(directory) / "receipt.json"
                path.write_bytes(raw)
                result = run_validator(path)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual(result.stderr, "")
                if expected:
                    self.assertIn("input exceeds size limit", result.stdout)
                self.assertEqual(path.read_bytes(), raw)

    def test_directory_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(synthetic_receipt()).encode("utf-8")
            target = root / "target.json"
            target.write_bytes(raw)
            link = root / "receipt.json"
            link.symlink_to(target.name)
            for candidate in (root, link):
                with self.subTest(kind="directory" if candidate == root else "symlink"):
                    result = run_validator(candidate)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("input must be a regular file", result.stdout)
                    self.assertEqual(result.stderr, "")
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_bytes(), raw)

    def test_open_itself_refuses_symlink_and_non_regular_descriptor(self):
        """The rejection must hold at open time, not only at a prior stat.

        Call the descriptor-level opener directly, so a path that becomes a
        symlink or FIFO between check and open is still rejected without any
        reliance on the earlier path check.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate_receipt_basis", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(synthetic_receipt()).encode("utf-8")
            target = root / "target.json"
            target.write_bytes(raw)
            link = root / "swapped.json"
            link.symlink_to(target.name)
            with self.assertRaises(module.BasisError):
                module.read_regular_file(link)
            if hasattr(os, "mkfifo"):
                fifo = root / "swapped.pipe"
                os.mkfifo(fifo)
                with self.assertRaises(module.BasisError):
                    module.read_regular_file(fifo)
            with self.assertRaises(module.BasisError):
                module.read_regular_file(root)
            self.assertEqual(module.read_regular_file(target), raw)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_fifo_is_rejected_without_waiting_for_a_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.pipe"
            os.mkfifo(path)
            result = run_validator(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("input must be a regular file", result.stdout)
            self.assertEqual(result.stderr, "")

    def test_invalid_utf8_has_bounded_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SYNTHETIC_CANARY.json"
            raw = b"\xffSYNTHETIC_CANARY"
            path.write_bytes(raw)
            result = run_validator(path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("input unreadable or invalid JSON", result.stdout)
            self.assertEqual(result.stderr, "")
            self.assertNotIn("SYNTHETIC_CANARY", result.stdout)
            self.assertEqual(path.read_bytes(), raw)

    def test_deep_json_has_bounded_error(self):
        # Whether the parser raises RecursionError at this depth varies by
        # interpreter (3.9 does, 3.14 does not). The contract is the same either
        # way: exit 1, one bounded VIOLATION line, no traceback, no input echo.
        raw = "[" * 2000 + '"SYNTHETIC_CANARY"' + "]" * 2000
        result = self.run_text(raw)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"^VIOLATION: input 1: (input unreadable or invalid JSON|unsupported receipt shape)\n$")
        self.assertEqual(result.stderr, "")
        self.assertNotIn("SYNTHETIC_CANARY", result.stdout)

    def test_no_arguments_fail(self):
        self.assertEqual(run_validator().returncode, 1)


if __name__ == "__main__":
    unittest.main()
