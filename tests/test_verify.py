from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.synthetic import run_synthetic
from mva_prioritizer.verify import verify_synthetic_run


class RunVerificationTests(unittest.TestCase):
    def test_accepts_an_untouched_deterministic_synthetic_run(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / "output"
            output.mkdir()
            summary = run_synthetic(fixture, config, output)

            result = verify_synthetic_run(
                fixture_path=fixture,
                config_path=config,
                run_directory=output / summary.run_id,
            )

        self.assertEqual(result.state, "verified")
        self.assertEqual(result.run_id, summary.run_id)
        self.assertEqual(result.file_count, 5)

    def test_rejects_score_tampering_after_local_hashes_are_recomputed(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / "output"
            output.mkdir()
            summary = run_synthetic(fixture, config, output)
            run_directory = output / summary.run_id
            dossier_path = run_directory / "dossier.json"
            dossier = json.loads(dossier_path.read_bytes())
            dossier["findings"][0]["review_score"] = "1.000000"
            dossier_bytes = self._json_bytes(dossier)
            dossier_path.chmod(0o600)
            dossier_path.write_bytes(dossier_bytes)

            receipt_path = run_directory / "receipt.json"
            receipt = json.loads(receipt_path.read_bytes())
            receipt["outputs"]["dossier.json"] = hashlib.sha256(dossier_bytes).hexdigest()
            receipt_path.chmod(0o600)
            receipt_path.write_bytes(self._json_bytes(receipt))

            with self.assertRaisesRegex(ValueError, "stale_receipt"):
                verify_synthetic_run(
                    fixture_path=fixture,
                    config_path=config,
                    run_directory=run_directory,
                )

    @staticmethod
    def _json_bytes(value: object) -> bytes:
        return (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
