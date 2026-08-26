from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mva_prioritizer.cli import main
from mva_prioritizer.reference_bundle import (
    ReferenceAcquisition,
    ReferenceBundleVerification,
)
from mva_prioritizer.reference_install import ReferenceInstallation
from mva_prioritizer.synthetic import run_synthetic

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_verify_environment_emits_only_content_free_counts(self) -> None:
        protected_canary = "protected-environment-canary"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / protected_canary
            public.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            stdout = io.StringIO()
            stderr = io.StringIO()
            result_value = mock.Mock(
                state="ready",
                check_count=10,
                artifact_count=22,
                installed_count=22,
                support_count=2,
                tool_count=7,
            )
            with (
                mock.patch(
                    "mva_prioritizer.cli.verify_environment",
                    return_value=result_value,
                    create=True,
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "verify-environment",
                        "--public-root",
                        str(public),
                        "--private-root",
                        str(private),
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "artifact_count": 22,
                "check_count": 10,
                "external_actions": 0,
                "installed_count": 22,
                "state": "ready",
                "support_count": 2,
                "tool_count": 7,
            },
        )
        self.assertNotIn(protected_canary, stdout.getvalue() + stderr.getvalue())

    def test_verify_environment_failure_does_not_reflect_private_context(self) -> None:
        protected_canary = "protected-environment-failure-canary"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / protected_canary
            public.mkdir(mode=0o700)
            private.mkdir(mode=0o700)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch(
                    "mva_prioritizer.cli.verify_environment",
                    side_effect=ValueError(protected_canary),
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "verify-environment",
                        "--public-root",
                        str(public),
                        "--private-root",
                        str(private),
                    ]
                )

        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            '{"error":"input_rejected","state":"failed_closed"}\n',
        )
        self.assertNotIn(protected_canary, stdout.getvalue() + stderr.getvalue())

    def test_reference_install_emits_only_content_free_counts(self) -> None:
        protected_canary = "protected-reference-install-canary"
        manifest = {
            "artifacts": [
                {
                    "expected_bytes": 11,
                    "expected_sha256": "a" * 64,
                    "filename": "tool-1.0.tar.gz",
                    "install_kind": "source-tar",
                    "name": protected_canary,
                    "role": "tool_source",
                    "source_checksum": {"algorithm": "sha256", "value": "a" * 64},
                    "source_url": "https://github.com/example/project/releases/download/1.0/tool-1.0.tar.gz",
                    "version": "1.0",
                }
            ],
            "assembly": "GRCh38",
            "bundle_version": "2026-08-26.2",
            "fastq_included": False,
            "network_during_private_run": False,
            "private_runtime": "m1-encrypted-workspace",
            "protected_data_allowed_on_public_compute": False,
            "schema_version": 2,
            "status": "verified",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / "private"
            config = public / "config"
            config.mkdir(parents=True, mode=0o700)
            private.mkdir(mode=0o700)
            (config / "reference-bundle.json").write_text(
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch(
                    "mva_prioritizer.cli.install_reference_artifact",
                    return_value=ReferenceInstallation(
                        state="installed",
                        file_count=1,
                        directory_count=1,
                        byte_count=11,
                    ),
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "reference-install",
                        "--public-root",
                        str(public),
                        "--private-root",
                        str(private),
                        "--artifact",
                        protected_canary,
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "byte_count": 11,
                "directory_count": 1,
                "external_actions": 0,
                "file_count": 1,
                "state": "installed",
            },
        )
        self.assertNotIn(protected_canary, stdout.getvalue() + stderr.getvalue())

    def test_reference_verify_emits_only_content_free_counts(self) -> None:
        protected_canary = "protected-reference-verify-canary"
        manifest = {
            "artifacts": [
                {
                    "expected_bytes": 11,
                    "expected_sha256": "a" * 64,
                    "filename": "tool-1.0.tar.gz",
                    "install_kind": "source-tar",
                    "name": protected_canary,
                    "role": "tool_source",
                    "source_checksum": {"algorithm": "sha256", "value": "a" * 64},
                    "source_url": "https://github.com/example/project/releases/download/1.0/tool-1.0.tar.gz",
                    "version": "1.0",
                }
            ],
            "assembly": "GRCh38",
            "bundle_version": "2026-08-26.2",
            "fastq_included": False,
            "network_during_private_run": False,
            "private_runtime": "m1-encrypted-workspace",
            "protected_data_allowed_on_public_compute": False,
            "schema_version": 2,
            "status": "verified",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / "private"
            config = public / "config"
            config.mkdir(parents=True, mode=0o700)
            private.mkdir(mode=0o700)
            (config / "reference-bundle.json").write_text(
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch(
                    "mva_prioritizer.cli.verify_reference_bundle",
                    return_value=ReferenceBundleVerification(
                        state="verified",
                        artifact_count=1,
                        byte_count=11,
                    ),
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "reference-verify",
                        "--public-root",
                        str(public),
                        "--private-root",
                        str(private),
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "artifact_count": 1,
                "byte_count": 11,
                "external_actions": 0,
                "state": "verified",
            },
        )
        self.assertNotIn(protected_canary, stdout.getvalue() + stderr.getvalue())

    def test_reference_acquire_emits_only_content_free_counts(self) -> None:
        protected_canary = "protected-reference-canary"
        manifest = {
            "artifacts": [
                {
                    "expected_bytes": 11,
                    "expected_sha256": "a" * 64,
                    "filename": "tool-1.0.tar.gz",
                    "install_kind": "source-tar",
                    "name": protected_canary,
                    "role": "tool_source",
                    "source_checksum": {"algorithm": "sha256", "value": "a" * 64},
                    "source_url": "https://github.com/example/project/releases/download/1.0/tool-1.0.tar.gz",
                    "version": "1.0",
                }
            ],
            "assembly": "GRCh38",
            "bundle_version": "2026-08-26.2",
            "fastq_included": False,
            "network_during_private_run": False,
            "private_runtime": "m1-encrypted-workspace",
            "protected_data_allowed_on_public_compute": False,
            "schema_version": 2,
            "status": "declared",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "public"
            private = root / "private"
            config = public / "config"
            config.mkdir(parents=True, mode=0o700)
            private.mkdir(mode=0o700)
            (config / "reference-bundle.json").write_text(
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch(
                    "mva_prioritizer.cli.acquire_reference_artifact",
                    return_value=ReferenceAcquisition(
                        state="verified",
                        verified_count=1,
                        pin_required_count=0,
                        byte_count=11,
                        measured_sha256="a" * 64,
                    ),
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "reference-acquire",
                        "--public-root",
                        str(public),
                        "--private-root",
                        str(private),
                        "--artifact",
                        protected_canary,
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "byte_count": 11,
                "external_actions": 1,
                "pin_required_count": 0,
                "state": "verified",
                "verified_count": 1,
            },
        )
        self.assertNotIn(protected_canary, stdout.getvalue() + stderr.getvalue())

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
