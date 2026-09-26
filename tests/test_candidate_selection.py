"""Tests for the executable form of docs/22, the candidate selection rule.

Every allele here is invented. The module under test turns a pool of candidate
alleles (with their tier evidence) into the ordered Track 1 rows the rule
prescribes. Each test names the sentence of docs/22 it pins, so a change to the
rule that is not mirrored in the document fails loudly here.
"""

import itertools
import random
import unittest

from mva_prioritizer.candidate_selection import (
    EPCR_LADDER,
    Candidate,
    SelectionError,
    SelectionResult,
    build_submission_csv,
    order_rows,
    select_rows,
)


def allele(chrom, pos, ref="A", alt="G"):
    return (chrom, pos, ref, alt)


def cand(a, gene, tier, both_lanes=True, rank=1, recessive=True):
    return Candidate(
        variant=a, gene=gene, tier=tier, both_lanes=both_lanes,
        native_rank=rank, recessive_annotation=recessive,
    )


class RowFormation(unittest.TestCase):
    def test_two_recessive_alleles_in_one_gene_form_a_pair_row(self):
        # Step 4: "any two alleles in the same gene, both in Tier A or Tier B,
        # with the recorded recessive annotation, form a pair row."
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "A")]
        result = select_rows(pool)
        self.assertEqual(len(result.rows), 3)  # one pair, two singles
        self.assertEqual(len(result.rows[0].variants), 2)

    def test_pairing_spans_tier_a_and_tier_b(self):
        # Step 4: "Pairing operates across the union of Tier A and Tier B,
        # not within each tier separately."
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "B")]
        result = select_rows(pool)
        pairs = [r for r in result.rows if len(r.variants) == 2]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].tier, "B")  # "takes the weaker of the two tiers"

    def test_tier_c_alleles_never_pair(self):
        pool = [cand(allele("chr1", 1000), "G1", "C"), cand(allele("chr1", 2000), "G1", "C")]
        result = select_rows(pool)
        self.assertTrue(all(len(r.variants) == 1 for r in result.rows))

    def test_alleles_without_recessive_annotation_never_pair(self):
        pool = [
            cand(allele("chr1", 1000), "G1", "A", recessive=False),
            cand(allele("chr1", 2000), "G1", "A", recessive=False),
        ]
        result = select_rows(pool)
        self.assertTrue(all(len(r.variants) == 1 for r in result.rows))

    def test_three_alleles_form_three_pairs_and_all_are_kept(self):
        # Step 4: "With three or more qualifying alleles in a gene, C(k,2) pair
        # rows form" and "When two candidate pairs share an allele, both are kept."
        pool = [cand(allele("chr1", p), "G1", "A") for p in (1000, 2000, 3000)]
        result = select_rows(pool)
        pairs = [r for r in result.rows if len(r.variants) == 2]
        self.assertEqual(len(pairs), 3)


class TotalOrder(unittest.TestCase):
    def test_pairs_before_singles(self):
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "A"),
                cand(allele("chr2", 5000), "G2", "A")]
        rows = select_rows(pool).rows
        classes = [len(r.variants) for r in rows]
        self.assertEqual(classes, sorted(classes, reverse=True))

    def test_tier_orders_within_a_class(self):
        pool = [cand(allele("chr2", 5000), "G2", "C"), cand(allele("chr3", 5000), "G3", "A"),
                cand(allele("chr4", 5000), "G4", "B")]
        rows = select_rows(pool).rows
        self.assertEqual([r.tier for r in rows], ["A", "B", "C"])

    def test_both_lanes_before_one_lane_within_a_tier(self):
        pool = [cand(allele("chr2", 5000), "G2", "A", both_lanes=False),
                cand(allele("chr3", 5000), "G3", "A", both_lanes=True)]
        rows = select_rows(pool).rows
        self.assertEqual([r.both_lanes for r in rows], [True, False])

    def test_native_rank_orders_within_lane_agreement(self):
        pool = [cand(allele("chr2", 5000), "G2", "A", rank=7),
                cand(allele("chr3", 5000), "G3", "A", rank=2)]
        rows = select_rows(pool).rows
        self.assertEqual([r.native_rank for r in rows], [2, 7])

    def test_pair_native_rank_is_the_better_of_its_alleles(self):
        # Step 4 key 4: "For a pair row this is the better (numerically lower)
        # rank of its two alleles"
        pool = [cand(allele("chr1", 1000), "G1", "A", rank=9), cand(allele("chr1", 2000), "G1", "A", rank=3)]
        pair = [r for r in select_rows(pool).rows if len(r.variants) == 2][0]
        self.assertEqual(pair.native_rank, 3)

    def test_coordinate_breaks_the_final_tie_by_contig_then_position_then_alleles(self):
        pool = [cand(allele("chr10", 100), "G1", "A"), cand(allele("chr2", 900), "G2", "A"),
                cand(allele("chr2", 100, "C", "T"), "G3", "A"), cand(allele("chr2", 100, "A", "T"), "G4", "A")]
        rows = select_rows(pool).rows
        variants = [next(iter(r.variants)) for r in rows]
        # chr2 before chr10 (numeric contig order, not lexical); position; then ref
        self.assertEqual(variants, [allele("chr2", 100, "A", "T"), allele("chr2", 100, "C", "T"),
                                    allele("chr2", 900), allele("chr10", 100)])

    def test_order_is_independent_of_input_order(self):
        # docs/22: "Every input permutation of the same pool produced the identical file."
        pool = [cand(allele("chr1", 1000), "G1", "A", rank=4), cand(allele("chr1", 2000), "G1", "B", rank=2),
                cand(allele("chr5", 100), "G5", "C", both_lanes=False), cand(allele("chrX", 7), "GX", "A")]
        baseline = [r.variants for r in select_rows(pool).rows]
        for perm in itertools.permutations(pool):
            self.assertEqual([r.variants for r in select_rows(list(perm)).rows], baseline)

    def test_no_two_distinct_rows_share_a_sort_key(self):
        rng = random.Random(22)
        universe = [allele("chr1", 1000), allele("chr1", 2000), allele("chr2", 3000),
                    allele("chr2", 4000), allele("chr3", 5000), allele("chr1", 1000, "A", "T")]
        for _ in range(300):
            k = rng.randint(2, 6)
            pool = [cand(v, rng.choice(["G1", "G2"]), rng.choice("ABCD"), rng.choice([True, False]),
                         rng.randint(1, 30)) for v in rng.sample(universe, k)]
            rows = select_rows(pool).rows
            keys = [r.sort_key for r in rows]
            self.assertEqual(len(keys), len(set(keys)))


class AlleleSharingConstraint(unittest.TestCase):
    def test_pair_is_promoted_above_a_single_that_shares_its_allele(self):
        # docs/22 rule 2: a pair row is promoted above every single row that
        # shares an allele with it.
        # A Tier A single that shares an allele with a Tier B pair: the tier
        # order would place the single first; the constraint moves the pair up.
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "B")]
        rows = select_rows(pool).rows
        self.assertEqual(len(rows[0].variants), 2)

    def test_two_pair_rows_are_never_reordered_by_the_constraint(self):
        # docs/22: "The relative order of two pair rows is never changed by this step."
        pool = [cand(allele("chr1", p), "G1", "A", rank=r) for p, r in ((1000, 5), (2000, 1), (3000, 9))]
        ordered = order_rows(pool)
        pair_order_before = [r.variants for r in ordered if len(r.variants) == 2]
        final = select_rows(pool).rows
        pair_order_after = [r.variants for r in final if len(r.variants) == 2]
        self.assertEqual(pair_order_before, pair_order_after)

    def test_unrelated_single_is_not_displaced_by_a_pair(self):
        # The falsified "every pair above every single" formulation. A Tier A
        # single from another gene keeps its evidence position relative to a
        # Tier B pair it shares nothing with... except that class ordering puts
        # pairs first by Step 4 key 1. This test pins that the constraint itself
        # only fires on shared alleles: the pair's position comes from key 1,
        # and the single's promotion_reason stays empty.
        pool = [cand(allele("chr1", 1000), "G1", "B"), cand(allele("chr1", 2000), "G1", "B"),
                cand(allele("chr9", 9), "G9", "A")]
        rows = select_rows(pool).rows
        single = [r for r in rows if r.variants == frozenset({allele("chr9", 9)})][0]
        self.assertFalse(single.promoted_over)


class EpcrAndCap(unittest.TestCase):
    def test_ladder_has_ten_distinct_descending_values_in_unit_interval(self):
        self.assertEqual(len(EPCR_LADDER), 10)
        self.assertEqual(list(EPCR_LADDER), sorted(EPCR_LADDER, reverse=True))
        self.assertEqual(len(set(EPCR_LADDER)), 10)
        self.assertTrue(all(0 < e <= 1 for e in EPCR_LADDER))

    def test_epcr_is_assigned_by_row_position(self):
        pool = [cand(allele("chr1", p), "G1", "A") for p in (1000, 2000)]
        rows = select_rows(pool).rows
        self.assertEqual([r.epcr for r in rows], list(EPCR_LADDER[: len(rows)]))

    def test_cap_at_ten_truncates_from_the_bottom_and_records_by_tier(self):
        # Step 6: "remove rows from the bottom of the Step 4 order, one at a
        # time, until ten remain ... The count of truncated candidates is
        # recorded, by tier."
        pool = [cand(allele("chr1", 100 * i), f"G{i}", "A" if i < 6 else "D", recessive=False)
                for i in range(1, 14)]
        result = select_rows(pool)
        self.assertEqual(len(result.rows), 10)
        self.assertEqual(sum(result.truncated_by_tier.values()), 3)
        self.assertEqual(result.truncated_by_tier.get("D"), 3)

    def test_cap_climbs_tiers_when_the_lowest_is_exhausted(self):
        pool = [cand(allele("chr1", 100 * i), f"G{i}", "A" if i < 12 else "B", recessive=False)
                for i in range(1, 14)]
        result = select_rows(pool)
        self.assertEqual(len(result.rows), 10)
        self.assertEqual(result.truncated_by_tier, {"B": 2, "A": 1})


class Refusals(unittest.TestCase):
    def test_empty_pool_is_refused(self):
        with self.assertRaises(SelectionError):
            select_rows([])

    def test_duplicate_variant_in_pool_is_refused(self):
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 1000), "G1", "B")]
        with self.assertRaises(SelectionError):
            select_rows(pool)

    def test_unknown_tier_is_refused(self):
        with self.assertRaises(SelectionError):
            select_rows([cand(allele("chr1", 1000), "G1", "E")])

    def test_unknown_contig_is_refused(self):
        with self.assertRaises(SelectionError):
            select_rows([cand(allele("chr99", 1000), "G1", "A")])

    def test_mitochondrial_row_is_reported_not_silently_accepted(self):
        # Step 7: "A mitochondrial row blocks the file until the organizers
        # confirm the contig spelling."
        result = select_rows([cand(allele("chrM", 100), "MT1", "A")])
        self.assertEqual(result.mitochondrial_rows, 1)


class CsvOutput(unittest.TestCase):
    # The rule's shape (pair row, then its single alleles below) repeats
    # variants on purpose. The canonical parser refuses repeats by default
    # because they add no F-max recall, and the flag exists for exactly this
    # deliberate case. Step 7 of docs/22 therefore runs track1-check with
    # --allow-repeated-pairings. The test below pins that interaction so it
    # cannot be discovered at upload time.
    def test_default_parser_refuses_the_rule_shape_and_the_flag_admits_it(self):
        from mva_prioritizer.track1_submission import SubmissionError, parse_submission
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "A")]
        text = build_submission_csv(select_rows(pool))
        with self.assertRaises(SubmissionError):
            parse_submission(text)
        parse_submission(text, allow_repeated_pairings=True)

    def test_csv_round_trips_through_the_canonical_parser(self):
        from mva_prioritizer.track1_submission import parse_submission
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "A"),
                cand(allele("chr7", 3000, "C", "T"), "G7", "C", both_lanes=False, recessive=False)]
        result = select_rows(pool)
        text = build_submission_csv(result)
        parsed = parse_submission(text, allow_repeated_pairings=True)
        self.assertEqual(len(parsed.rows), len(result.rows))
        self.assertEqual([r.epcr for r in parsed.rows], [r.epcr for r in result.rows])
        self.assertEqual(parsed.rows[0].variants, result.rows[0].variants)

    def test_csv_notes_carry_the_tier_and_rule_version_only(self):
        pool = [cand(allele("chr1", 1000), "G1", "A")]
        text = build_submission_csv(select_rows(pool))
        line = text.splitlines()[1]
        self.assertIn("tier=A", line)
        self.assertIn("rule=docs/22", line)
        self.assertNotIn("G1", line)  # no gene symbol in the public row

    def test_csv_scores_100_when_the_pair_is_the_truth(self):
        from mva_prioritizer.track1_submission import parse_submission, score_submission
        a, b = allele("chr1", 1000), allele("chr1", 2000)
        pool = [cand(a, "G1", "A"), cand(b, "G1", "A"), cand(allele("chr9", 9), "G9", "C", recessive=False)]
        parsed = parse_submission(build_submission_csv(select_rows(pool)), allow_repeated_pairings=True)
        scored = score_submission(parsed, frozenset({a, b}))
        self.assertEqual(scored.rank_points, 100.0)
        self.assertEqual(scored.f_max, 1.0)

    def test_csv_under_a_single_variant_truth_keeps_rank_points_and_pays_in_f_max(self):
        # The hedge the singles exist for: a single-variant truth still earns
        # rank points from the single row below the pair. The price is F-max,
        # because the pair row counts as a false positive under that truth.
        # This is the trade-off docs/22 states under "Verification of this
        # rule": the shape assumes a compound-heterozygous key. The exact
        # figure is pinned so the trade-off can never be described loosely.
        from mva_prioritizer.track1_submission import parse_submission, score_submission
        a, b = allele("chr1", 1000), allele("chr1", 2000)
        pool = [cand(a, "G1", "A"), cand(b, "G1", "A")]
        parsed = parse_submission(build_submission_csv(select_rows(pool)), allow_repeated_pairings=True)
        scored = score_submission(parsed, frozenset({a}))
        self.assertEqual(scored.rank_points, 50.0)   # single a at rank 2 earns the 2-3 tier
        self.assertAlmostEqual(scored.f_max, 2 / 3)   # pair row is a false positive


if __name__ == "__main__":
    unittest.main()
