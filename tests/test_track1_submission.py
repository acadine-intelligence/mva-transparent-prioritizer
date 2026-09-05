"""Tests for the Track 1 submission validator and the local scorer mirror.

The official scorer is pinned unchanged at ``tools/official-track1/evaluation.py``
(Space revision 1c761cc2, retrieved 2026-09-05). These tests load that file directly
and require the local mirror to agree with it on every synthetic case, including the
adversarial ones. Every variant here is invented; no private coordinate appears.
"""

import csv
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

from mva_prioritizer.track1_submission import (
    HEADER,
    SubmissionError,
    parse_as_official,
    parse_submission,
    score_submission,
    validate_against_lane_representation,
)

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL = ROOT / "tools" / "official-track1" / "evaluation.py"
OFFICIAL_SHA256 = "6d18b581e65a45e1ccc120071d588e740c2e42e983ff50704c60a40232b19180"
TEMPLATE = ROOT / "tools" / "official-track1" / "track1_submission_template.csv"
TEMPLATE_SHA256 = "7b3ed41c091d34fb6c5622d049c7a3f46124211fc7ec02947e69daef8752755a"

TRUTH_PAIR = frozenset([("chr2", 1000, "A", "T"), ("chr15", 2000, "G", "C")])
TRUTH_SINGLE = frozenset([("chr7", 3000, "C", "T")])


def load_official():
    spec = importlib.util.spec_from_file_location("official_track1_evaluation", OFFICIAL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rows_to_csv(rows, header=HEADER):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def row(v1, v2=None, epcr="0.5", finding="primary", notes="", pid="PROBAND01"):
    second = list(v2) if v2 else ["", "", "", ""]
    return [pid, *[str(x) for x in v1], *[str(x) for x in second], epcr, finding, notes]


class PinnedOfficialFilesTest(unittest.TestCase):
    def test_official_scorer_and_template_are_the_pinned_bytes(self):
        import hashlib

        self.assertEqual(hashlib.sha256(OFFICIAL.read_bytes()).hexdigest(), OFFICIAL_SHA256)
        self.assertEqual(hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(), TEMPLATE_SHA256)

    def test_template_header_matches_our_header(self):
        with TEMPLATE.open(newline="") as handle:
            header = next(csv.reader(handle))
        self.assertEqual(header, list(HEADER))


class MirrorAgreesWithOfficialTest(unittest.TestCase):
    """Each case: score with the pinned official code and with the mirror; require equality."""

    CASES = {
        "exact_pair_rank1": ([row(("chr2", 1000, "A", "T"), ("chr15", 2000, "G", "C"), "0.9")], TRUTH_PAIR),
        "pair_reversed_order_still_exact": (
            [row(("chr15", 2000, "G", "C"), ("chr2", 1000, "A", "T"), "0.9")],
            TRUTH_PAIR,
        ),
        "two_singles_recover_fmax_but_half_rank_points": (
            [row(("chr2", 1000, "A", "T"), None, "0.9"), row(("chr15", 2000, "G", "C"), None, "0.8")],
            TRUTH_PAIR,
        ),
        "wrong_partner_gives_partial_credit": (
            [row(("chr2", 1000, "A", "T"), ("chr15", 9999, "G", "C"), "0.9")],
            TRUTH_PAIR,
        ),
        "exact_pair_at_rank4_after_three_decoys": (
            [
                row(("chr1", 1, "A", "C"), None, "0.9"),
                row(("chr1", 2, "A", "C"), None, "0.8"),
                row(("chr1", 3, "A", "C"), None, "0.7"),
                row(("chr2", 1000, "A", "T"), ("chr15", 2000, "G", "C"), "0.6"),
            ],
            TRUTH_PAIR,
        ),
        "unsorted_input_is_sorted_by_epcr": (
            [row(("chr1", 1, "A", "C"), None, "0.2"), row(("chr7", 3000, "C", "T"), None, "0.9")],
            TRUTH_SINGLE,
        ),
        "epcr_tie_keeps_file_order": (
            [row(("chr1", 1, "A", "C"), None, "0.5"), row(("chr7", 3000, "C", "T"), None, "0.5")],
            TRUTH_SINGLE,
        ),
        "lowercase_alleles_are_uppercased": ([row(("chr7", 3000, "c", "t"), None, "0.9")], TRUTH_SINGLE),
        "chromosome_without_prefix_scores_zero": ([row(("7", 3000, "C", "T"), None, "0.9")], TRUTH_SINGLE),
        "repeated_variant_adds_nothing": (
            [row(("chr7", 3000, "C", "T"), None, "0.9"), row(("chr7", 3000, "C", "T"), None, "0.8")],
            TRUTH_SINGLE,
        ),
        "secondary_row_does_not_change_score": (
            [
                row(("chr7", 3000, "C", "T"), None, "0.9"),
                row(("chr1", 1, "A", "C"), None, "0.3", "secondary", "unrelated"),
            ],
            TRUTH_SINGLE,
        ),
        "ten_decoys_no_match": (
            [row(("chr1", i, "A", "C"), None, f"0.{99 - i}") for i in range(1, 11)],
            TRUTH_SINGLE,
        ),
        "single_truth_pair_row_containing_it_is_exact_only_if_equal": (
            [row(("chr7", 3000, "C", "T"), ("chr1", 1, "A", "C"), "0.9")],
            TRUTH_SINGLE,
        ),
    }

    def test_every_case_matches_the_official_scorer(self):
        official = load_official()
        for name, (rows, truth) in self.CASES.items():
            with self.subTest(case=name):
                text = rows_to_csv(rows)
                with tempfile.TemporaryDirectory() as scratch:
                    path = Path(scratch) / "sub.csv"
                    path.write_bytes(text.encode("utf-8"))
                    theirs = official.score_proband("PROBAND01", official.load_submission(str(path))["PROBAND01"], truth)
                ours = score_submission(parse_as_official(text)["PROBAND01"], truth)
                self.assertEqual(ours.rank_points, theirs.rank_points)
                self.assertEqual(ours.f_max, theirs.f_max)
                self.assertEqual(ours.f_max_threshold, theirs.f_max_threshold)
                self.assertEqual(ours.full_match_rank, theirs.full_match_rank)
                self.assertEqual(ours.partial_match_rank, theirs.partial_match_rank)
                self.assertEqual(ours.n_predictions_at_f_max, theirs.n_predictions_at_f_max)

    def test_strict_parser_agrees_with_official_parser_on_everything_it_accepts(self):
        """A file the validator passes must score the same whether the gate or the mirror ranks it."""
        accepted = 0
        for name, (rows, truth) in self.CASES.items():
            text = rows_to_csv(rows)
            try:
                strict = parse_submission(text)
            except SubmissionError:
                continue
            accepted += 1
            with self.subTest(case=name):
                self.assertEqual(score_submission(strict, truth), score_submission(parse_as_official(text)["PROBAND01"], truth))
        self.assertGreaterEqual(accepted, 6)

    def test_pinned_expectations_on_key_cases(self):
        """Numbers the docs cite, pinned so a doc edit cannot drift from the code."""
        exact = score_submission(parse_submission(rows_to_csv(self.CASES["exact_pair_rank1"][0])), TRUTH_PAIR)
        self.assertEqual((exact.rank_points, exact.f_max), (100.0, 1.0))
        singles = score_submission(
            parse_submission(rows_to_csv(self.CASES["two_singles_recover_fmax_but_half_rank_points"][0])), TRUTH_PAIR
        )
        self.assertEqual((singles.rank_points, singles.f_max), (50.0, 1.0))
        partner = score_submission(
            parse_submission(rows_to_csv(self.CASES["wrong_partner_gives_partial_credit"][0])), TRUTH_PAIR
        )
        self.assertEqual(partner.rank_points, 50.0)
        self.assertEqual(partner.f_max, 0.5)  # one true of two predicted, one of two truth found
        rank4 = score_submission(
            parse_submission(rows_to_csv(self.CASES["exact_pair_at_rank4_after_three_decoys"][0])), TRUTH_PAIR
        )
        self.assertEqual(rank4.rank_points, 25.0)
        noprefix_text = rows_to_csv(self.CASES["chromosome_without_prefix_scores_zero"][0])
        noprefix = score_submission(parse_as_official(noprefix_text)["PROBAND01"], TRUTH_SINGLE)
        self.assertEqual((noprefix.rank_points, noprefix.f_max), (0.0, 0.0))
        with self.assertRaises(SubmissionError):
            parse_submission(noprefix_text)  # the strict validator stops this before upload


class ValidatorRefusesTrapsTest(unittest.TestCase):
    """Canonical-form refusals.

    Most shapes here would upload and then error or score zero at the gate, burning
    one of six submissions. A few (marked in their test names) are shapes the gate
    would normalize and score fully; the canonical validator refuses them anyway and
    the test shows the gate view alongside.
    """

    def assert_refused(self, text, fragment, **kwargs):
        with self.assertRaises(SubmissionError) as caught:
            parse_submission(text, **kwargs)
        self.assertIn(fragment, str(caught.exception))

    def test_header_must_match_template_exactly(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T"))], header=[h.upper() for h in HEADER])
        self.assert_refused(text, "header")

    def test_more_than_ten_rows(self):
        self.assert_refused(rows_to_csv([row(("chr1", i, "A", "C")) for i in range(1, 12)]), "10")

    def test_zero_rows(self):
        self.assert_refused(rows_to_csv([]), "no rows")

    def test_epcr_out_of_range_and_non_numeric(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="0")]), "epcr")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="1.0001")]), "epcr")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="high")]), "epcr")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="nan")]), "epcr")

    def test_non_integer_or_negative_position(self):
        self.assert_refused(rows_to_csv([row(("chr7", "3000.0", "C", "T"))]), "pos_1")
        self.assert_refused(rows_to_csv([row(("chr7", "-5", "C", "T"))]), "pos_1")

    def test_blank_alleles_pass_official_parsing_but_are_refused_here(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "", "T"))]), "ref_1")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", ""))]), "alt_1")

    def test_allele_must_be_acgt_only(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "N", "T"))]), "ref_1")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T,A"))]), "alt_1")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "*"))]), "alt_1")

    def test_ref_equal_to_alt(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "C"))]), "identical")

    def test_chromosome_must_carry_chr_prefix_and_be_a_known_name(self):
        self.assert_refused(rows_to_csv([row(("7", 3000, "C", "T"))]), "chrom_1")
        self.assert_refused(rows_to_csv([row(("chrMT", 3000, "C", "T"))]), "chrom_1")
        self.assert_refused(rows_to_csv([row(("chr7 ", 3000, "C", "T"))]), "chrom_1")
        self.assert_refused(rows_to_csv([row(("Chr7", 3000, "C", "T"))]), "chrom_1")

    def test_partial_second_variant_is_refused(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T"), ("chr1", "", "", ""))])
        self.assert_refused(text, "second variant")
        text = rows_to_csv([row(("chr7", 3000, "C", "T"), ("", 5, "A", "C"))])
        self.assert_refused(text, "second variant")

    def test_pair_with_both_members_identical(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T"), ("chr7", 3000, "C", "T"))])
        self.assert_refused(text, "pair")

    def test_finding_type_values(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), finding="incidental")]), "finding_type")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), finding="")]), "finding_type")

    def test_second_proband_group_is_refused(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T")), row(("chr1", 1, "A", "C"), pid="PROBAND02")])
        self.assert_refused(text, "proband")

    def test_proband_id_must_be_the_expected_one(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), pid="PROBAND01 ")]), "proband_id")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), pid="proband01")]), "proband_id")

    def test_repeated_variant_across_rows_is_refused_by_default(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="0.9"), row(("chr7", 3000, "C", "T"), epcr="0.8")])
        self.assert_refused(text, "repeat")

    def test_repeated_variant_in_different_pairings_is_allowed_when_asked(self):
        text = rows_to_csv(
            [
                row(("chr7", 3000, "C", "T"), ("chr1", 1, "A", "C"), epcr="0.9"),
                row(("chr7", 3000, "C", "T"), ("chr1", 2, "A", "C"), epcr="0.8"),
            ]
        )
        self.assert_refused(text, "repeat")
        parsed = parse_submission(text, allow_repeated_pairings=True)
        self.assertEqual(len(parsed.rows), 2)

    def test_epcr_ties_are_refused_by_default(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="0.5"), row(("chr1", 1, "A", "C"), epcr="0.5")])
        self.assert_refused(text, "tie")
        parsed = parse_submission(text, allow_ties=True)
        self.assertEqual([r.rank for r in parsed.rows], [1, 2])
        # File order decides the tie in both parsers: the truth row came first, so rank 1.
        for candidate in (parsed, parse_as_official(text)["PROBAND01"]):
            self.assertEqual(score_submission(candidate, TRUTH_SINGLE).full_match_rank, 1)
        reversed_text = rows_to_csv([row(("chr1", 1, "A", "C"), epcr="0.5"), row(("chr7", 3000, "C", "T"), epcr="0.5")])
        for candidate in (parse_submission(reversed_text, allow_ties=True), parse_as_official(reversed_text)["PROBAND01"]):
            self.assertEqual(score_submission(candidate, TRUTH_SINGLE).full_match_rank, 2)

    def test_official_parser_trims_chromosome_text_and_uppercases_alleles(self):
        official = load_official()
        text = rows_to_csv([row((" chr7 ", 3000, "c", "t"), epcr="0.9")])
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "sub.csv"
            path.write_bytes(text.encode("utf-8"))
            theirs = official.load_submission(str(path))["PROBAND01"][0].variants
        ours = parse_as_official(text)["PROBAND01"].rows[0].variants
        self.assertEqual(ours, theirs)
        self.assertEqual(ours, frozenset([("chr7", 3000, "C", "T")]))
        with self.assertRaises(SubmissionError):
            parse_submission(text)  # the strict validator refuses padding and lowercase outright

    def test_unsorted_rows_are_refused_by_default(self):
        text = rows_to_csv([row(("chr1", 1, "A", "C"), epcr="0.2"), row(("chr7", 3000, "C", "T"), epcr="0.9")])
        self.assert_refused(text, "sorted")
        parsed = parse_submission(text, allow_unsorted=True)
        self.assertEqual(parsed.rows[0].epcr, 0.9)

    def test_crlf_is_accepted(self):
        text = rows_to_csv([row(("chr7", 3000, "C", "T"))]).replace("\n", "\r\n")
        parsed = parse_submission(text)
        self.assertEqual(len(parsed.rows), 1)

    def test_utf8_bom_breaks_the_gate_and_is_refused_by_both_parsers(self):
        """The official loader opens with the default codec; the BOM joins the first header name."""
        official = load_official()
        text = "\ufeff" + rows_to_csv([row(("chr7", 3000, "C", "T"))])
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "bom.csv"
            path.write_bytes(text.encode("utf-8"))
            with self.assertRaises(KeyError):
                official.load_submission(str(path))
        with self.assertRaises(SubmissionError):
            parse_as_official(text)
        self.assert_refused(text, "BOM")

    def test_gate_normalized_forms_are_refused_here_but_score_at_the_gate(self):
        """Deliberate narrowing: the gate would normalize these; the canonical validator refuses them
        so that a passing file needs no normalization to reason about. parse_as_official shows the gate view."""
        shapes = {
            "padded chromosome and lowercase alleles": rows_to_csv([row((" chr7 ", 3000, "c", "t"), epcr="0.9")]),
            "ten-column header without finding_type and notes": rows_to_csv(
                [row(("chr7", 3000, "C", "T"), epcr="0.9")[:10]], header=list(HEADER[:10])
            ),
            "blank finding_type defaults to primary at the gate": rows_to_csv(
                [row(("chr7", 3000, "C", "T"), epcr="0.9", finding="")]
            ),
            "quoted multiline notes": rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="0.9", notes="a\nb")]),
        }
        official = load_official()
        for name, text in shapes.items():
            with self.subTest(shape=name):
                with self.assertRaises(SubmissionError):
                    parse_submission(text)
                with tempfile.TemporaryDirectory() as scratch:
                    path = Path(scratch) / "shape.csv"
                    path.write_bytes(text.encode("utf-8"))
                    theirs = official.score_proband(
                        "PROBAND01", official.load_submission(str(path))["PROBAND01"], TRUTH_SINGLE
                    )
                ours = score_submission(parse_as_official(text)["PROBAND01"], TRUTH_SINGLE)
                self.assertEqual((theirs.rank_points, theirs.f_max), (100.0, 1.0))
                self.assertEqual((ours.rank_points, ours.f_max), (100.0, 1.0))

    def test_short_row_crashes_the_gate_and_the_mirror_says_so(self):
        """DictReader fills missing cells with None; the gate strips None and raises AttributeError."""
        official = load_official()
        text = "proband_id,chrom_1,pos_1,epcr,ref_1,alt_1\nPROBAND01,chr1,100,0.5\n"
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "short.csv"
            path.write_bytes(text.encode("utf-8"))
            with self.assertRaises(AttributeError):
                official.load_submission(str(path))
        with self.assertRaises(SubmissionError) as caught:
            parse_as_official(text)
        self.assertIn("short row", str(caught.exception))
        self.assert_refused(text, "header")

    def test_official_mirror_raises_where_the_gate_raises(self):
        official = load_official()
        bad = {
            "non-integer position": rows_to_csv([row(("chr7", "30a", "C", "T"))]),
            "non-numeric epcr": rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="high")]),
            "epcr zero": rows_to_csv([row(("chr7", 3000, "C", "T"), epcr="0")]),
            "eleven rows": rows_to_csv([row(("chr1", i, "A", "C"), epcr=f"0.{99 - i}") for i in range(1, 12)]),
            "bad finding_type": rows_to_csv([row(("chr7", 3000, "C", "T"), finding="incidental")]),
        }
        for name, text in bad.items():
            with self.subTest(shape=name):
                with tempfile.TemporaryDirectory() as scratch:
                    path = Path(scratch) / "bad.csv"
                    path.write_bytes(text.encode("utf-8"))
                    with self.assertRaises(ValueError):
                        official.load_submission(str(path))
                with self.assertRaises(SubmissionError):
                    parse_as_official(text)

    def test_mitochondrial_name_is_configurable_and_unverified(self):
        chrm = rows_to_csv([row(("chrM", 10, "A", "G"))])
        chrmt = rows_to_csv([row(("chrMT", 10, "A", "G"))])
        self.assertEqual(len(parse_submission(chrm).rows), 1)
        self.assert_refused(chrmt, "chrom_1")
        self.assertEqual(len(parse_submission(chrmt, mitochondrial_name="chrMT").rows), 1)
        self.assert_refused(chrm, "chrom_1", mitochondrial_name="chrMT")
        # An unprefixed spelling can never be configured in: the gate matches a chr-prefixed key.
        unprefixed = rows_to_csv([row(("MT", 10, "A", "G"))])
        with self.assertRaises(SubmissionError) as caught:
            parse_submission(unprefixed, mitochondrial_name="MT")
        self.assertIn("must be one of ('chrM', 'chrMT')", str(caught.exception))
        # The gate itself matches whichever spelling the private key uses; both score against their own.
        for text, truth_name in ((chrm, "chrM"), (chrmt, "chrMT")):
            ours = score_submission(parse_as_official(text)["PROBAND01"], frozenset([(truth_name, 10, "A", "G")]))
            self.assertEqual(ours.rank_points, 100.0)

    def test_extra_or_missing_columns(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T")) + ["extra"]]), "columns")
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"))[:-1]]), "columns")

    def test_notes_must_not_smuggle_line_breaks(self):
        self.assert_refused(rows_to_csv([row(("chr7", 3000, "C", "T"), notes="line1\nline2")]), "notes")


class LaneRepresentationTest(unittest.TestCase):
    """The lane writes contigs without a prefix; the submission must carry `chr`."""

    def test_lane_contig_maps_to_submission_chromosome(self):
        parsed = parse_submission(rows_to_csv([row(("chr7", 3000, "C", "T")), row(("chrM", 10, "A", "G"), epcr="0.1")]))
        lane_keys = {("7", 3000, "C", "T"), ("MT", 10, "A", "G")}
        validate_against_lane_representation(parsed, lane_keys)
        alt = parse_submission(
            rows_to_csv([row(("chr7", 3000, "C", "T")), row(("chrMT", 10, "A", "G"), epcr="0.1")]),
            mitochondrial_name="chrMT",
        )
        validate_against_lane_representation(alt, lane_keys, mitochondrial_name="chrMT")

    def test_submission_variant_absent_from_lane_is_refused(self):
        parsed = parse_submission(rows_to_csv([row(("chr7", 3000, "C", "T"))]))
        with self.assertRaises(SubmissionError) as caught:
            validate_against_lane_representation(parsed, {("7", 3001, "C", "T")})
        self.assertIn("not present", str(caught.exception))

    def test_lane_keys_carrying_a_prefix_are_a_representation_error(self):
        parsed = parse_submission(rows_to_csv([row(("chr7", 3000, "C", "T"))]))
        with self.assertRaises(SubmissionError) as caught:
            validate_against_lane_representation(parsed, {("chr7", 3000, "C", "T")})
        self.assertIn("representation", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
