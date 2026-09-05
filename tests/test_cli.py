from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
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


class SensitivityPartitionCliTests(unittest.TestCase):
    DETAIL = Path(__file__).resolve().parent / "fixtures" / "exomiser_recompute_detail.json"

    def run_cli(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_writes_count_only_receipt_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partition.json"
            code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(self.DETAIL), "--output", str(output)])
            self.assertEqual((code, err), (0, ""))
            status = json.loads(out)
            self.assertEqual(status["state"], "written")
            self.assertEqual(status["variant_partition"], {"retained": 5, "removed_by_cutoff": 3, "removed_by_inheritance": 1})
            self.assertEqual(status["gene_partition"], {"retained": 4, "removed_by_cutoff": 0, "removed_by_inheritance": 1})
            self.assertFalse(status["symbols_included"])
            written = json.loads(output.read_text())
            self.assertEqual(written["retained_genes_with_changed_mode_set_count"], 2)
            self.assertNotIn("retained_genes_with_changed_mode_set", written)
            self.assertNotIn("SYNG", output.read_text(), "no symbols unless asked")

    def test_include_symbols_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partition.json"
            code, out, _ = self.run_cli(["sensitivity-partition", "--detail", str(self.DETAIL), "--output", str(output), "--include-symbols"])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(out)["symbols_included"])
            self.assertEqual(json.loads(output.read_text())["retained_genes_with_changed_mode_set"], ["SYNG2", "SYNG6"])

    def test_refuses_to_overwrite_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partition.json"
            output.write_text("{}")
            code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(self.DETAIL), "--output", str(output)])
            self.assertEqual((code, out), (2, ""))
            self.assertEqual(json.loads(err), {"error": "input_rejected", "state": "failed_closed"})
            self.assertEqual(output.read_text(), "{}", "existing output untouched")

    def test_inconsistent_detail_fails_closed_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            detail = json.loads(self.DETAIL.read_text())
            detail["genes"]["SYNG1"]["strict_survivors"] = 0
            bad = Path(directory) / "detail.json"
            bad.write_text(json.dumps(detail))
            output = Path(directory) / "partition.json"
            code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(bad), "--output", str(output)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("failed_closed", err)
            self.assertFalse(output.exists())

    def test_malformed_json_fails_closed_with_one_bounded_line(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "detail.json"
            bad.write_text("{" + '"SYNTHETIC_CANARY"' * 50)
            output = Path(directory) / "partition.json"
            code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(bad), "--output", str(output)])
            self.assertEqual((code, out), (2, ""))
            self.assertEqual(err.count("\n"), 1)
            self.assertNotIn("SYNTHETIC_CANARY", err)
            self.assertFalse(output.exists())

    def test_duplicate_json_keys_are_rejected_not_last_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            text = self.DETAIL.read_text()
            self.assertTrue(text.lstrip().startswith("{"))
            dup = Path(directory) / "detail.json"
            dup.write_text('{"cutoff": 0.5, ' + text.lstrip()[1:])
            output = Path(directory) / "partition.json"
            code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(dup), "--output", str(output)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("failed_closed", err)
            self.assertFalse(output.exists())

    def test_symlink_and_non_regular_detail_are_rejected_at_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            link = root / "detail-link.json"
            link.symlink_to(self.DETAIL)
            fifo = root / "detail.fifo"
            os.mkfifo(fifo)
            for path in (link, fifo, root):
                output = root / f"partition-{path.name}.json"
                code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(path), "--output", str(output)])
                self.assertEqual((code, out), (2, ""), path)
                self.assertIn("failed_closed", err)
                self.assertFalse(output.exists(), path)

    def test_regular_file_decision_is_made_on_the_open_descriptor(self):
        # A FIFO opened non-blocking reads as empty and a directory read raises, so those
        # paths are rejected even without the S_ISREG guard. The guard's own job is the
        # descriptor that is not a regular file yet would still yield bytes: prove that
        # fstat is consulted and a non-regular mode is refused before any read happens.
        from mva_prioritizer import bounded_input
        with tempfile.TemporaryDirectory() as directory:
            regular = Path(directory) / "detail.json"
            regular.write_bytes(b"{}")
            real_fstat = os.fstat
            reads = []

            def fake_fstat(fd):
                status = real_fstat(fd)
                fields = list(status)
                fields[0] = (status.st_mode & ~0o170000) | 0o010000  # claim S_IFIFO
                return os.stat_result(fields)
            real_fdopen = os.fdopen

            def counting_fdopen(fd, *args, **kwargs):
                handle = real_fdopen(fd, *args, **kwargs)
                real_read = handle.read
                handle.read = lambda n=-1: (reads.append(n), real_read(n))[1]
                return handle
            with mock.patch.object(bounded_input.os, "fstat", fake_fstat), \
                 mock.patch.object(bounded_input.os, "fdopen", counting_fdopen):
                with self.assertRaises(bounded_input.InputRejected):
                    bounded_input.read_regular_file(regular, max_bytes=1024)
            self.assertEqual(reads, [], "non-regular descriptor refused before any read")

    def test_oversized_detail_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            big = Path(directory) / "detail.json"
            limit = 64 * 1024 * 1024
            with big.open("wb") as handle:
                handle.truncate(limit + 1)
            output = Path(directory) / "partition.json"
            code, out, err = self.run_cli(["sensitivity-partition", "--detail", str(big), "--output", str(output)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("failed_closed", err)
            self.assertFalse(output.exists())

    def test_oversized_detail_is_rejected_by_fstat_without_reading_it(self):
        # The descriptor's size is checked before any read, so an oversized file costs
        # no read at all. Patch the fdopen handle to prove no bytes were requested.
        from mva_prioritizer import bounded_input
        with tempfile.TemporaryDirectory() as directory:
            big = Path(directory) / "detail.json"
            with big.open("wb") as handle:
                handle.truncate(64 * 1024 * 1024 + 1)
            reads = []
            real_fdopen = os.fdopen

            def counting_fdopen(fd, *args, **kwargs):
                handle = real_fdopen(fd, *args, **kwargs)
                real_read = handle.read

                def read(n=-1):
                    reads.append(n)
                    return real_read(n)
                handle.read = read
                return handle
            with mock.patch.object(bounded_input.os, "fdopen", counting_fdopen):
                with self.assertRaises(bounded_input.InputRejected):
                    bounded_input.read_regular_file(big, max_bytes=64 * 1024 * 1024)
            self.assertEqual(reads, [], "size rejected on fstat, before any read")

    def test_file_that_grows_after_fstat_is_still_rejected(self):
        # fstat sees a small file; the read then returns more than the limit. The second
        # guard, on the bytes actually read, must reject it.
        from mva_prioritizer import bounded_input
        with tempfile.TemporaryDirectory() as directory:
            small = Path(directory) / "detail.json"
            small.write_bytes(b"{}")
            limit = 16
            real_fdopen = os.fdopen

            def growing_fdopen(fd, *args, **kwargs):
                handle = real_fdopen(fd, *args, **kwargs)
                handle.read = lambda n=-1: b"{" + b" " * limit + b"}"
                return handle
            with mock.patch.object(bounded_input.os, "fdopen", growing_fdopen):
                with self.assertRaises(bounded_input.InputRejected):
                    bounded_input.read_regular_file(small, max_bytes=limit)


if __name__ == "__main__":
    unittest.main()
