from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mva_prioritizer.synthetic import run_synthetic


class SyntheticJourneyTests(unittest.TestCase):
    def test_two_clean_runs_are_byte_identical_and_keep_scores_nonclinical(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"

        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            summary_a = run_synthetic(fixture, config, Path(first))
            summary_b = run_synthetic(fixture, config, Path(second))

            self.assertEqual(summary_a.state, "review_ready")
            self.assertEqual(summary_a, summary_b)
            self.assertEqual(summary_a.finding_count, 2)
            self.assertEqual(summary_a.external_actions, 0)

            tree_a = self._relative_bytes(Path(first))
            tree_b = self._relative_bytes(Path(second))
            self.assertEqual(tree_a, tree_b)

            dossier = json.loads(tree_a[f"{summary_a.run_id}/dossier.json"])
            self.assertFalse(dossier["review_score_is_probability"])
            self.assertIn("Research prioritization only", dossier["disclaimer"])
            self.assertEqual([row["finding_id"] for row in dossier["findings"]], ["single-alpha", "pair-beta"])
            self.assertEqual(dossier["findings"][1]["phase"], "unknown")
            self.assertIn("phase_unresolved", dossier["findings"][1]["warnings"])

            safe = json.loads(tree_a[f"{summary_a.run_id}/safe-learnings.json"])
            self.assertEqual(set(safe), {
                "external_actions",
                "finding_count",
                "finding_type_counts",
                "method_version",
                "schema_version",
                "state",
                "synthetic",
                "warning_count",
            })
            safe_text = tree_a[f"{summary_a.run_id}/safe-learnings.json"].decode("utf-8")
            for forbidden in ("SYNVAR", "SYNGENE", "single-alpha", "pair-beta"):
                self.assertNotIn(forbidden, safe_text)

    def test_empty_result_stays_honest_and_names_the_next_gap(self) -> None:
        fixture_source = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"
        fixture = json.loads(fixture_source.read_bytes())
        fixture["case_id"] = "SYNTHETIC_EMPTY_CASE"
        fixture["findings"] = []

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty_fixture = root / "empty.json"
            empty_fixture.write_text(
                json.dumps(fixture, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            output = root / "output"
            output.mkdir()

            summary = run_synthetic(empty_fixture, config, output)
            dossier = json.loads((output / summary.run_id / "dossier.json").read_bytes())
            safe = json.loads((output / summary.run_id / "safe-learnings.json").read_bytes())

        self.assertEqual(summary.state, "empty_result")
        self.assertEqual(dossier["state"], "empty_result")
        self.assertEqual(dossier["findings"], [])
        self.assertEqual(
            dossier["next_analytical_gap"],
            "Review unresolved variant classes and coverage before requesting new source data.",
        )
        self.assertNotIn("rank", dossier)
        self.assertEqual(safe["state"], "empty_result")
        self.assertEqual(safe["finding_count"], 0)

    def test_missing_score_input_stays_unknown_instead_of_becoming_zero(self) -> None:
        fixture_source = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"
        fixture = json.loads(fixture_source.read_bytes())
        fixture["findings"][0]["phenotype_score"] = None

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete_fixture = root / "incomplete.json"
            incomplete_fixture.write_text(
                json.dumps(fixture, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            output = root / "output"
            output.mkdir()
            summary = run_synthetic(incomplete_fixture, config, output)
            dossier = json.loads((output / summary.run_id / "dossier.json").read_bytes())

        incomplete = next(row for row in dossier["findings"] if row["finding_id"] == "single-alpha")
        self.assertIsNone(incomplete["phenotype_score"])
        self.assertIsNone(incomplete["review_score"])
        self.assertIsNone(incomplete["review_score_components"]["phenotype_score"])
        self.assertIn("review_score_incomplete", incomplete["warnings"])
        self.assertEqual(dossier["findings"][-1]["finding_id"], "single-alpha")

    def test_missing_frequency_and_source_score_stay_unknown(self) -> None:
        fixture_source = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config = ROOT / "config" / "scoring-v1.json"
        fixture = json.loads(fixture_source.read_bytes())
        fixture["findings"][0]["population_frequency"] = None
        fixture["findings"][0]["source_score"] = None

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete_fixture = root / "incomplete.json"
            incomplete_fixture.write_text(
                json.dumps(fixture, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            output = root / "output"
            output.mkdir()
            summary = run_synthetic(incomplete_fixture, config, output)
            dossier = json.loads((output / summary.run_id / "dossier.json").read_bytes())

        incomplete = next(row for row in dossier["findings"] if row["finding_id"] == "single-alpha")
        self.assertIsNone(incomplete["review_score"])
        self.assertIsNone(incomplete["review_score_components"]["rarity"])
        self.assertIsNone(incomplete["review_score_components"]["source_score"])

    def test_scoring_config_rejects_unknown_fields(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config_source = ROOT / "config" / "scoring-v1.json"
        config = json.loads(config_source.read_bytes())
        config["clinical_probability"] = True

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unsafe_config = root / "unsafe-config.json"
            unsafe_config.write_text(
                json.dumps(config, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
            output = root / "output"
            output.mkdir()

            with self.assertRaisesRegex(ValueError, "invalid_scoring_config"):
                run_synthetic(fixture, unsafe_config, output)

    def test_scoring_config_rejects_duplicate_json_keys(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        config_source = ROOT / "config" / "scoring-v1.json"
        raw = config_source.read_text(encoding="utf-8")
        duplicate = raw.replace("{", '{"schema_version":1,', 1)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "duplicate-config.json"
            config.write_text(duplicate, encoding="utf-8")
            output = root / "output"
            output.mkdir()

            with self.assertRaisesRegex(ValueError, "invalid_scoring_config"):
                run_synthetic(fixture, config, output)

    def test_scoring_config_rejects_out_of_range_or_inconsistent_values(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "synthetic_case.json"
        source = json.loads((ROOT / "config" / "scoring-v1.json").read_bytes())
        malformed: list[dict[str, object]] = []

        bad_weights = copy.deepcopy(source)
        bad_weights["weights"]["source_score"] = "1.20"
        malformed.append(bad_weights)

        bad_impact = copy.deepcopy(source)
        bad_impact["impact_values"]["high"] = "2.0"
        malformed.append(bad_impact)

        bad_clinical = copy.deepcopy(source)
        bad_clinical["clinical_values"]["pathogenic"] = "-0.1"
        malformed.append(bad_clinical)

        bad_thresholds = copy.deepcopy(source)
        bad_thresholds["rarity_thresholds"][0]["maximum_frequency"] = "0.01"
        malformed.append(bad_thresholds)

        bad_disclaimer = copy.deepcopy(source)
        bad_disclaimer["disclaimer"] = "This value is a diagnosis."
        malformed.append(bad_disclaimer)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, config in enumerate(malformed):
                with self.subTest(index=index):
                    config_path = root / f"config-{index}.json"
                    config_path.write_text(
                        json.dumps(config, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    output = root / f"output-{index}"
                    output.mkdir()
                    with self.assertRaises(ValueError) as captured:
                        run_synthetic(fixture, config_path, output)
                    self.assertEqual(str(captured.exception), "invalid_scoring_config")

    def test_synthetic_fixture_rejects_realistic_or_malformed_identifiers(self) -> None:
        source = json.loads((ROOT / "tests" / "fixtures" / "synthetic_case.json").read_bytes())
        config = ROOT / "config" / "scoring-v1.json"
        malformed: list[dict[str, object]] = []

        extra_top = copy.deepcopy(source)
        extra_top["sample_id"] = "PERSON_001"
        malformed.append(extra_top)

        bad_case = copy.deepcopy(source)
        bad_case["case_id"] = "PERSON_001"
        malformed.append(bad_case)

        duplicate_finding = copy.deepcopy(source)
        duplicate_finding["findings"][1]["finding_id"] = duplicate_finding["findings"][0]["finding_id"]
        malformed.append(duplicate_finding)

        bad_score = copy.deepcopy(source)
        bad_score["findings"][0]["source_score"] = "1.5"
        malformed.append(bad_score)

        bad_rank = copy.deepcopy(source)
        bad_rank["findings"][0]["source_rank"] = 0
        malformed.append(bad_rank)

        bad_phase = copy.deepcopy(source)
        bad_phase["findings"][1]["phase"] = "not_applicable"
        malformed.append(bad_phase)

        bad_gene = copy.deepcopy(source)
        bad_gene["findings"][0]["variants"][0]["gene"] = "NOTSYNGENE1"
        malformed.append(bad_gene)

        extra_variant_field = copy.deepcopy(source)
        extra_variant_field["findings"][0]["variants"][0]["coordinate"] = "chr1:123"
        malformed.append(extra_variant_field)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, fixture in enumerate(malformed):
                with self.subTest(index=index):
                    fixture_path = root / f"fixture-{index}.json"
                    fixture_path.write_text(
                        json.dumps(fixture, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    output = root / f"output-{index}"
                    output.mkdir()
                    with self.assertRaises(ValueError) as captured:
                        run_synthetic(fixture_path, config, output)
                    self.assertEqual(str(captured.exception), "invalid_synthetic_fixture")

    @staticmethod
    def _relative_bytes(root: Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
