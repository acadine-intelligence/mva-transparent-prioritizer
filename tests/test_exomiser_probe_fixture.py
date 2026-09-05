"""Pin the recorded behaviour of the pinned Exomiser 15.1.0 engine classes.

The fixture is the verbatim output of a synthetic class-level probe run against
the hash-verified public exomiser-core-15.1.0.jar. It is a record of engine
behaviour, not a patient result. See docs/17-exomiser-probe.md.
"""
import json
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "exomiser_probe_output.json"


class ExomiserProbeFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_probe_used_pinned_engine_constants(self):
        self.assertEqual(self.probe["likely_pathogenic_threshold"], 0.914)
        self.assertEqual(self.probe["pathogenic_threshold"], 0.963)
        self.assertEqual(self.probe["baseline_filter"],
                         "PathogenicityFilter{keepNonPathogenic=false, target=NON_CODING}")

    def test_mirror_agreed_with_engine_on_every_comparison(self):
        self.assertEqual(self.probe["mirror_engine_comparisons"], 17)
        self.assertEqual(self.probe["mirror_mismatches_at_baseline_cutoff"], 0)

    def test_cutoffs_are_strict_greater_than_at_float_boundaries(self):
        by_score = {case["remm_float"]: case for case in self.probe["threshold_cases"]}
        self.assertFalse(by_score[0.914]["baseline_pass"], "exact 0.914 must fail the baseline cutoff")
        self.assertTrue(by_score[0.9140001]["baseline_pass"], "next float above 0.914 must pass")
        self.assertFalse(by_score[0.963]["strict_pass"], "exact 0.963 must fail the strict cutoff")
        self.assertTrue(by_score[0.9630001]["strict_pass"], "next float above 0.963 must pass")
        for case in self.probe["threshold_cases"]:
            self.assertTrue(case["non_coding"])
            if case["strict_pass"]:
                self.assertTrue(case["baseline_pass"], "strict survivors are a subset of baseline survivors")

    def test_float_widening_stays_below_the_double_constant_at_the_boundary(self):
        by_score = {case["remm_float"]: case for case in self.probe["threshold_cases"]}
        self.assertLess(by_score[0.914]["remm_widened_double"], 0.914)
        self.assertLess(by_score[0.963]["remm_widened_double"], 0.963)

    def test_controls_behave_as_documented(self):
        coding = self.probe["coding_control"]
        self.assertFalse(coding["non_coding"])
        self.assertTrue(coding["baseline_pass"] and coding["strict_pass"],
                        "Target.NON_CODING must preserve coding variants under both cutoffs")
        no_score = self.probe["no_score_noncoding_control"]
        self.assertFalse(no_score["baseline_pass"] or no_score["strict_pass"])
        white = self.probe["whitelist_control"]
        self.assertTrue(white["baseline_pass"] and white["strict_pass"])

    def test_rerun_removes_recessive_mode_that_posthoc_filtering_would_keep(self):
        pair = self.probe["pair"]
        self.assertEqual(pair["baseline_survivors"], 2)
        self.assertEqual(pair["strict_survivors"], 1)
        self.assertEqual(pair["modes_after_baseline"], {"AUTOSOMAL_DOMINANT": 2, "AUTOSOMAL_RECESSIVE": 2})
        self.assertEqual(pair["modes_after_strict_rerun"], {"AUTOSOMAL_DOMINANT": 1})
        self.assertNotIn("AUTOSOMAL_RECESSIVE", pair["modes_after_strict_rerun"])

    def test_frequency_gated_pair_loses_all_modes_on_rerun(self):
        """A 1% variant is above the 0.1% dominant cutoff and below the 2% comp-het cutoff.

        With its partner present it is recessive-compatible only. Once the
        partner falls below the stricter pathogenicity cutoff, a rerun leaves
        the survivor with no compatible mode at all. Post-hoc filtering of the
        baseline records would carry the recessive label forward.
        """
        pair = self.probe["frequency_gated_pair"]
        self.assertEqual(pair["inheritance_options"], "InheritanceModeOptions.defaults()")
        self.assertEqual(pair["ad_max_freq_percent"], 0.1)
        self.assertEqual(pair["ar_max_freq_percent"], 2.0)
        self.assertEqual(pair["survivor_frequency_percent"], 1.0)
        self.assertEqual(pair["partner_frequency_percent"], 0.01)
        self.assertEqual(pair["survivor_remm"], 0.97)
        self.assertEqual(pair["partner_remm"], 0.95)
        self.assertEqual(pair["baseline_survivors"], 2)
        # The 0.01% partner is dominant-compatible on its own; the 1% survivor is recessive-only.
        self.assertEqual(pair["modes_after_baseline"], {"AUTOSOMAL_DOMINANT": 1, "AUTOSOMAL_RECESSIVE": 2})
        self.assertEqual(pair["modes_after_strict_rerun"], {})
        self.assertEqual(pair["strict_survivors"], 1)


if __name__ == "__main__":
    unittest.main()
