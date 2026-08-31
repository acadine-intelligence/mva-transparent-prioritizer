from __future__ import annotations

import copy
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.noncoding_benchmark import (
    load_noncoding_acquisition_manifest,
    run_noncoding_benchmark,
)


class NoncodingBenchmarkTests(unittest.TestCase):
    fixture = ROOT / "tests" / "fixtures" / "noncoding_benchmark_cases.json"
    config = ROOT / "config" / "noncoding-benchmark-v1.json"
    acquisition = ROOT / "config" / "noncoding-acquisition-v1.json"

    def test_checked_in_suite_is_deterministic_and_ready_for_tool_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            summary_a = run_noncoding_benchmark(
                self.fixture,
                self.config,
                self.acquisition,
                first_root,
            )
            summary_b = run_noncoding_benchmark(
                self.fixture,
                self.config,
                self.acquisition,
                second_root,
            )

            self.assertEqual(summary_a, summary_b)
            self.assertEqual(summary_a.state, "ready_for_tool_smoke")
            self.assertEqual(summary_a.case_count, 14)
            self.assertEqual(summary_a.passed_case_count, 14)
            self.assertEqual(summary_a.external_actions, 0)
            self.assertFalse(summary_a.private_execution_authorized)

            tree_a = self._relative_bytes(first_root)
            tree_b = self._relative_bytes(second_root)
            self.assertEqual(tree_a, tree_b)
            self.assertEqual(
                set(tree_a),
                {
                    f"{summary_a.run_id}/benchmark-public.json",
                    f"{summary_a.run_id}/benchmark-report.json",
                    f"{summary_a.run_id}/receipt.json",
                },
            )
            for path in (first_root / summary_a.run_id).iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)

            report = json.loads(tree_a[f"{summary_a.run_id}/benchmark-report.json"])
            self.assertFalse(report["clinical_probability"])
            self.assertIsNone(report["hidden_top_n"])
            self.assertFalse(report["private_execution_authorized"])
            self.assertTrue(all(row["passed"] for row in report["cases"]))

            public_bytes = tree_a[f"{summary_a.run_id}/benchmark-public.json"]
            public = json.loads(public_bytes)
            self.assertEqual(
                set(public),
                {
                    "case_count",
                    "external_actions",
                    "passed_case_count",
                    "private_execution_authorized",
                    "schema_version",
                    "state",
                    "synthetic",
                },
            )
            for forbidden in (
                b"SYNTHETIC_PUBLIC_CANARY",
                b"SYNTHETIC_NC_",
                b"SYNVAR_",
                b"SYNGENE_",
            ):
                self.assertNotIn(forbidden, public_bytes)

    def test_threshold_boundaries_use_strict_greater_than(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = run_noncoding_benchmark(
                self.fixture,
                self.config,
                self.acquisition,
                root,
            )
            report = json.loads(
                (root / summary.run_id / "benchmark-report.json").read_bytes()
            )

        threshold_case = next(
            row for row in report["cases"] if row["scenario"] == "threshold_boundaries"
        )
        self.assertEqual(threshold_case["details"]["spliceai_pass"], [False, False, True])
        self.assertEqual(threshold_case["details"]["remm_pass"], [False, False, True])

    def test_missing_spliceai_score_stays_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = run_noncoding_benchmark(
                self.fixture,
                self.config,
                self.acquisition,
                root,
            )
            report_path = root / summary.run_id / "benchmark-report.json"
            report = json.loads(report_path.read_bytes())
            report_text = report_path.read_text(encoding="utf-8")

        missing = next(
            row for row in report["cases"] if row["scenario"] == "missing_spliceai"
        )
        self.assertEqual(missing["observed_outcome"], "missing_visible")
        self.assertEqual(missing["details"], {"score_state": "missing"})
        self.assertNotIn('"spliceai_score":"0"', report_text)

    def test_checked_in_acquisition_manifest_is_proposal_only(self) -> None:
        manifest = load_noncoding_acquisition_manifest(self.acquisition)

        self.assertEqual(manifest.state, "proposal")
        self.assertEqual(manifest.assembly, "GRCh38")
        self.assertEqual(manifest.artifact_count, 2)
        self.assertEqual(manifest.pin_required_count, 2)
        self.assertFalse(manifest.acquisition_authorized)
        self.assertFalse(manifest.private_execution_authorized)
        self.assertFalse(manifest.direct_spliceai_acquisition)
        self.assertEqual(
            [artifact.expected_bytes for artifact in manifest.artifacts],
            [15_967_302_704, 2_755_625],
        )
        self.assertEqual(
            [artifact.source_checksum_value for artifact in manifest.artifacts],
            [
                "2f8c8fcc75ea29f6798621d0446fe194",
                "c477b123abbe72c4aa66bf3abc18d9ab",
            ],
        )
        self.assertTrue(all(artifact.expected_sha256 is None for artifact in manifest.artifacts))

    def test_manifest_rejects_any_authorization_or_direct_spliceai_acquisition(self) -> None:
        source = self._load_json(self.acquisition)
        malformed = []
        for field in (
            "private_execution_authorized",
            "direct_spliceai_acquisition",
            "redistribution_authorized",
        ):
            payload = copy.deepcopy(source)
            payload[field] = True
            malformed.append(payload)
        payload = copy.deepcopy(source)
        payload["artifacts"][0]["acquisition_authorized"] = True
        malformed.append(payload)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, payload in enumerate(malformed):
                with self.subTest(index=index):
                    path = root / f"manifest-{index}.json"
                    self._write_json(path, payload)
                    with self.assertRaisesRegex(
                        ValueError,
                        "invalid_noncoding_acquisition_manifest",
                    ):
                        load_noncoding_acquisition_manifest(path)

    def test_config_rejects_threshold_drift_and_hidden_top_n(self) -> None:
        source = self._load_json(self.config)
        malformed = []
        threshold = copy.deepcopy(source)
        threshold["thresholds"]["spliceai"] = "0.2"
        malformed.append(threshold)
        hidden_cutoff = copy.deepcopy(source)
        hidden_cutoff["hidden_top_n"] = 10
        malformed.append(hidden_cutoff)
        clinical = copy.deepcopy(source)
        clinical["clinical_probability"] = True
        malformed.append(clinical)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, payload in enumerate(malformed):
                with self.subTest(index=index):
                    config = root / f"config-{index}.json"
                    self._write_json(config, payload)
                    output = root / f"output-{index}"
                    output.mkdir()
                    with self.assertRaisesRegex(ValueError, "invalid_noncoding_config"):
                        run_noncoding_benchmark(
                            self.fixture,
                            config,
                            self.acquisition,
                            output,
                        )
                    self.assertEqual(list(output.iterdir()), [])

    def test_changed_expected_outcome_fails_the_benchmark_without_authorizing_execution(self) -> None:
        fixture = self._load_json(self.fixture)
        fixture["cases"][1]["expected_outcome"] = "failed_closed"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            changed_fixture = root / "changed-fixture.json"
            self._write_json(changed_fixture, fixture)
            output = root / "output"
            output.mkdir()
            summary = run_noncoding_benchmark(
                changed_fixture,
                self.config,
                self.acquisition,
                output,
            )

        self.assertEqual(summary.state, "benchmark_failed")
        self.assertEqual(summary.passed_case_count, 13)
        self.assertFalse(summary.private_execution_authorized)

    def test_cli_emits_one_content_free_status_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mva_prioritizer.cli",
                    "noncoding-benchmark",
                    "--fixture",
                    str(self.fixture),
                    "--config",
                    str(self.config),
                    "--acquisition-manifest",
                    str(self.acquisition),
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
        self.assertEqual(
            set(json.loads(completed.stdout)),
            {
                "case_count",
                "external_actions",
                "passed_case_count",
                "private_execution_authorized",
                "run_id",
                "state",
            },
        )
        for forbidden in (
            "SYNTHETIC_PUBLIC_CANARY",
            "SYNTHETIC_NC_",
            "SYNVAR_",
            "SYNGENE_",
        ):
            self.assertNotIn(forbidden, completed.stdout)

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        return json.loads(path.read_bytes())

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _relative_bytes(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
