from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mva_prioritizer.synthetic import run_synthetic

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_synthetic_run_emits_one_content_free_status_record(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / "output"
            output.mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "synthetic-run",
                    "--fixture",
                    str(fixture),
                    "--config",
                    str(config),
                    "--output-root",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        records = completed.stdout.splitlines()
        self.assertEqual(len(records), 1)
        status = json.loads(records[0])
        self.assertEqual(
            set(status),
            {"external_actions", "finding_count", "run_id", "state"},
        )
        self.assertEqual(status["state"], "review_ready")
        self.assertEqual(status["external_actions"], 0)
        for protected_token in ("SYNTHETIC_CASE_ALPHA", "SYNVAR_A", "SYNGENE_ALPHA"):
            self.assertNotIn(protected_token, completed.stdout + completed.stderr)

    def test_synthetic_failure_does_not_reflect_a_caller_path(self) -> None:
        config = ROOT / "config" / "scoring-v1.json"
        protected_token = "PROTECTED_CANARY_CASE_7721"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            output = root / "output"
            output.mkdir()
            missing = root / f"{protected_token}.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "synthetic-run",
                    "--fixture",
                    str(missing),
                    "--config",
                    str(config),
                    "--output-root",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(
            completed.stderr,
            '{"error":"input_rejected","state":"failed_closed"}\n',
        )
        self.assertNotIn(protected_token, completed.stdout + completed.stderr)

    def test_verify_run_emits_only_verification_status(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / "output"
            output.mkdir()
            summary = run_synthetic(fixture, config, output)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "verify-run",
                    "--fixture",
                    str(fixture),
                    "--config",
                    str(config),
                    "--run-directory",
                    str(output / summary.run_id),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        status = json.loads(completed.stdout)
        self.assertEqual(
            set(status),
            {"external_actions", "file_count", "run_id", "state"},
        )
        self.assertEqual(status["state"], "verified")
        self.assertEqual(status["external_actions"], 0)

    def test_validate_manifest_emits_only_receipt_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / "private"
            public.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            source = private / "case.json"
            source_bytes = b'{"synthetic":true}\n'
            source.write_bytes(source_bytes)
            source.chmod(0o400)
            manifest = {
                "artifacts": [
                    {
                        "bytes": len(source_bytes),
                        "class": "input",
                        "format": "json",
                        "name": "synthetic-case",
                        "privacy_class": "synthetic",
                        "relative_path": "case.json",
                        "sha256": hashlib.sha256(source_bytes).hexdigest(),
                    }
                ],
                "assembly": "GRCh38",
                "run_kind": "synthetic",
                "sample_count": 1,
                "schema_version": 1,
                "tools": [
                    {
                        "binary_sha256": "0" * 64,
                        "name": "python",
                        "version": "3.9.6",
                    }
                ],
            }
            manifest_path = private / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path.chmod(0o400)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "validate-manifest",
                    "--public-root",
                    str(public),
                    "--private-root",
                    str(private),
                    "--manifest",
                    "manifest.json",
                    "--run-kind",
                    "synthetic",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        status = json.loads(completed.stdout)
        self.assertEqual(
            set(status),
            {"artifact_count", "external_actions", "manifest_sha256", "state"},
        )
        self.assertEqual(status["state"], "validated")
        self.assertEqual(status["artifact_count"], 1)
        self.assertEqual(status["external_actions"], 0)
        self.assertNotIn("synthetic-case", completed.stdout + completed.stderr)

    def test_project_safe_writes_the_fixed_projection_without_echoing_the_canary(self) -> None:
        canary = "synthetic-protected-canary-9981"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / "private"
            public.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            safe_learning = {
                "external_actions": 0,
                "finding_count": 1,
                "finding_type_counts": {"single": 1},
                "method_version": "transparent-review-v1",
                "schema_version": 1,
                "state": "review_ready",
                "synthetic": True,
                "warning_count": 0,
            }
            source = private / "safe-learnings.json"
            source.write_text(
                json.dumps(safe_learning, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            source.chmod(0o400)
            forbidden = private / "forbidden-values.json"
            forbidden.write_text(
                json.dumps(
                    {"schema_version": 1, "values": [canary]},
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            forbidden.chmod(0o400)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "project-safe",
                    "--public-root",
                    str(public),
                    "--private-root",
                    str(private),
                    "--source",
                    "safe-learnings.json",
                    "--forbidden-values",
                    "forbidden-values.json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            projected = public / "safe-learnings.json"
            projected_value = json.loads(projected.read_bytes()) if projected.exists() else None

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "external_actions": 0,
                "output_name": "safe-learnings.json",
                "state": "projected",
            },
        )
        self.assertEqual(projected_value, safe_learning)
        self.assertNotIn(canary, completed.stdout + completed.stderr)

    def test_privacy_scan_emits_counts_without_echoing_forbidden_values(self) -> None:
        canary = "synthetic-protected-canary-5512"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / "private"
            public.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            safe = public / "safe-learnings.json"
            safe.write_bytes(b'{"state":"projected"}\n')
            expected_bytes = safe.stat().st_size
            forbidden = private / "forbidden-values.json"
            forbidden.write_text(
                json.dumps(
                    {"schema_version": 1, "values": [canary]},
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            forbidden.chmod(0o400)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "privacy-scan",
                    "--public-root",
                    str(public),
                    "--private-root",
                    str(private),
                    "--forbidden-values",
                    "forbidden-values.json",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {
                "byte_count": expected_bytes,
                "external_actions": 0,
                "file_count": 1,
                "state": "clear",
            },
        )
        self.assertNotIn(canary, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
