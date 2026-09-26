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

    def test_three_alleles_form_three_pairs_before_resolution(self):
        # Step 4: "With three or more qualifying alleles in a gene, C(k,2) pair
        # rows form". Formation is stage 1; which survive is stage 3's job.
        pool = [cand(allele("chr1", p), "G1", "A") for p in (1000, 2000, 3000)]
        pairs = [r for r in order_rows(pool) if len(r.variants) == 2]
        self.assertEqual(len(pairs), 3)
        self.assertEqual(select_rows(pool).pair_rows_formed, 3)


class TotalOrder(unittest.TestCase):
    def test_tier_outranks_class(self):
        # docs/22 Step 4 stage 1: tier is the first key. An earlier draft put
        # every pair above every single; the measurement arm had falsified
        # that (1,020 cases) and the review of 741aaad caught the contradiction.
        # Reviewer's counterexample, verbatim: Tier B pair, Tier A single.
        pool = [cand(allele("chr2", 3000, "G", "A"), "G2", "B"), cand(allele("chr2", 4000, "T", "C"), "G2", "B"),
                cand(allele("chr1", 1000), "G1", "A")]
        rows = select_rows(pool).rows
        self.assertEqual(rows[0].variants, frozenset({allele("chr1", 1000)}))
        self.assertTrue(rows[1].is_pair)

    def test_tier_outranks_class_scores_as_the_review_said(self):
        # The same counterexample, scored: truth is the Tier A single plus a
        # partner excluded at Step 2. The old order scored 25 (partial at rank
        # 4 after three Tier B rows); tier-first scores 50 (partial at rank 1).
        from mva_prioritizer.track1_submission import parse_submission, score_submission
        pool = [cand(allele("chr2", 3000, "G", "A"), "G2", "B"), cand(allele("chr2", 4000, "T", "C"), "G2", "B"),
                cand(allele("chr1", 1000), "G1", "A")]
        parsed = parse_submission(build_submission_csv(select_rows(pool)), allow_repeated_pairings=True)
        scored = score_submission(parsed, frozenset({allele("chr1", 1000), allele("chr1", 2000)}))
        self.assertEqual(scored.rank_points, 50.0)

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
        # Step 4 key: "For a pair row this is the better (numerically lower)
        # rank of its two alleles"
        pool = [cand(allele("chr1", 1000), "G1", "A", rank=9), cand(allele("chr1", 2000), "G1", "A", rank=3)]
        pair = [r for r in select_rows(pool).rows if len(r.variants) == 2][0]
        self.assertEqual(pair.native_rank, 3)

    def test_pair_ties_its_own_first_single_and_wins_the_tiebreak(self):
        # Two alleles with identical evidence: the pair and the single of its
        # first allele tie on every evidence key; class breaks the tie, pair
        # first. That is the same outcome promotion would give, reached at
        # stage 1 so the promotion count stays honest.
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "A")]
        result = select_rows(pool)
        self.assertTrue(result.rows[0].is_pair)
        self.assertEqual(result.promotions, 0)

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
            rows = order_rows(pool)
            keys = [r.sort_key for r in rows]
            self.assertEqual(len(keys), len(set(keys)))


class Promotion(unittest.TestCase):
    def test_pair_is_promoted_above_a_single_that_shares_its_allele(self):
        # docs/22 rule 2: a pair row is promoted above every single row that
        # shares an allele with it. A Tier A single that shares an allele with
        # a Tier B pair: tier puts the single first; promotion moves the pair up.
        pool = [cand(allele("chr1", 1000), "G1", "A"), cand(allele("chr1", 2000), "G1", "B")]
        result = select_rows(pool)
        self.assertTrue(result.rows[0].is_pair)
        self.assertEqual(result.promotions, 1)
        self.assertEqual(result.rows[0].promoted_over, (allele("chr1", 1000),))

    def test_promotion_is_position_preserving(self):
        # Review of 741aaad, logic error 2: the old insert-and-shift moved every
        # row between the single and the pair down one rank, and at four rows
        # that crossed the 50-to-25 tier boundary. Now the pair takes the
        # topmost slot of its block and the sharing singles fill the rest of
        # the block in order; bystanders stay put. Reviewer's rows, verbatim:
        # singles chr1:1000, chr1:2000, chr2:3000, then the pair.
        from mva_prioritizer.candidate_selection import promote_rows
        a, b, c = allele("chr1", 1000), allele("chr1", 2000), allele("chr2", 3000)
        before = [_row([a], "A", rank=1), _row([b], "A", rank=2), _row([c], "A", rank=3), _row([a, b], "A", rank=4)]
        after, n = promote_rows(before)
        self.assertEqual(n, 1)
        self.assertEqual([r.variants for r in after],
                         [frozenset({a, b}), frozenset({a}), frozenset({c}), frozenset({b})])
        self.assertEqual(after[2].variants, frozenset({c}))  # the bystander did not move

    def test_promotion_never_lowers_rank_points_at_four_rows(self):
        # The reviewer's scored counterexample: truth chr2:3000 + chr2:4000.
        # The old promotion pushed the chr2:3000 single from rank 3 to rank 4
        # (partial 25 to 12.5). Position-preserving promotion leaves it at 3.
        from mva_prioritizer.candidate_selection import promote_rows
        from mva_prioritizer.track1_submission import parse_submission, score_submission
        a, b, c = allele("chr1", 1000), allele("chr1", 2000), allele("chr2", 3000)
        before = [_row([a], "A", rank=1), _row([b], "A", rank=2), _row([c], "A", rank=3), _row([a, b], "A", rank=4)]
        after, _ = promote_rows(before)
        parsed = parse_submission(build_submission_csv(_result(after)), allow_repeated_pairings=True)
        scored = score_submission(parsed, frozenset({c, allele("chr2", 4000)}))
        self.assertEqual(scored.rank_points, 25.0)

    def test_unrelated_single_keeps_its_evidence_position(self):
        # Tier A single from another gene above a Tier B pair it shares
        # nothing with: nothing moves it.
        pool = [cand(allele("chr1", 1000), "G1", "B"), cand(allele("chr1", 2000), "G1", "B"),
                cand(allele("chr9", 9), "G9", "A")]
        result = select_rows(pool)
        self.assertEqual(result.rows[0].variants, frozenset({allele("chr9", 9)}))
        self.assertEqual(result.promotions, 0)


class Demotion(unittest.TestCase):
    def test_losing_pair_at_an_equal_paying_rank_is_demoted(self):
        # docs/22 Step 4 stage 3. Three alleles in one gene form three pairs.
        # (a,b) is the strongest pair at rank 1 and claims a and b. (a,c) at
        # rank 2 shares a: a full match there is worth 50, the same as the
        # partial it already earns through the winner, so keeping it gains
        # nothing and it becomes its unshared single c in place; the lone c
        # below is dropped as a duplicate. (b,c) is then promoted over that
        # remnant c (rule 2), shares b with (a,b) at a non-paying rank, and
        # is demoted to c in the same slot. Net: one pair, then the three
        # singles, and two demotions.
        a, b, c = allele("chr1", 1000), allele("chr1", 2000), allele("chr1", 3000)
        pool = [cand(a, "G1", "A", rank=1), cand(b, "G1", "A", rank=2), cand(c, "G1", "A", rank=3)]
        result = select_rows(pool)
        self.assertEqual(result.pair_rows_formed, 3)
        self.assertEqual([r.variants for r in result.rows],
                         [frozenset({a, b}), frozenset({c}), frozenset({a}), frozenset({b})])
        self.assertEqual((result.demoted_pairs, result.removed_pairs), (2, 0))

    def test_losing_pair_stays_only_where_its_full_match_strictly_pays(self):
        # The rule's arithmetic, pinned. Winner at rank 2 gives a partial worth
        # 25. A sharing pair at rank 3 (full match 50) stays; at rank 4 (full
        # match 25, equal to the partial) it is demoted. Commit 1783250 kept
        # the pair at equality; policy_probe.py measured that choice 0.28
        # points behind demoting at equality, and both never score below the
        # plain sort.
        from mva_prioritizer.candidate_selection import resolve_rows
        a, b, c, e, f = (allele("chr1", 1000), allele("chr1", 2000), allele("chr1", 3000),
                         allele("chr3", 5000), allele("chr2", 4000))
        win = _row([a, b], "A", rank=1)
        resolved, _, demoted, _ = resolve_rows([_row([e], "A", 1), win, _row([a, c], "A", 3)])
        self.assertEqual(demoted, 0)
        self.assertTrue(resolved[2].is_pair)
        resolved, _, demoted, _ = resolve_rows([_row([e], "A", 1), win, _row([f], "A", 3), _row([a, c], "A", 4)])
        self.assertEqual(demoted, 1)
        self.assertEqual(resolved[3].variants, frozenset({c}))

    def test_removal_when_both_alleles_are_claimed_above(self):
        # Two kept pairs claim all four alleles; a lower pair sharing one
        # allele with each has nothing unshared and is removed.
        from mva_prioritizer.candidate_selection import resolve_rows
        a, b, c, d, e, f = (allele("chr1", 1000), allele("chr1", 2000), allele("chr1", 3000),
                            allele("chr1", 4000), allele("chr3", 5000), allele("chr2", 4000))
        rows = [_row([a, c], "A", 1), _row([b, d], "A", 2), _row([e], "A", 3), _row([f], "A", 4), _row([c, d], "A", 5)]
        resolved, _, demoted, removed = resolve_rows(rows)
        self.assertEqual((demoted, removed), (0, 1))
        self.assertEqual(len(resolved), 4)

    def test_kept_sharing_pairs_sit_only_where_they_strictly_pay(self):
        # Stage 3 invariant over random pools: a kept pair that shares an
        # allele with a kept pair above it at rank q sits at a rank r where
        # points(r) > 0.5 * points(q).
        from mva_prioritizer.candidate_selection import _rank_points
        rng = random.Random(3)
        universe = [allele("chr1", p) for p in (1000, 2000, 3000, 4000)]
        for _ in range(500):
            k = rng.randint(2, 4)
            pool = [cand(v, "G1", rng.choice("AB"), rng.choice([True, False]), rng.randint(1, 9))
                    for v in rng.sample(universe, k)]
            claimed = {}
            for j, r in enumerate(select_rows(pool).rows):
                if r.is_pair:
                    shared = r.variants & set(claimed)
                    if shared:
                        q = min(claimed[v] for v in shared) + 1
                        self.assertGreater(_rank_points(j + 1), 0.5 * _rank_points(q), (pool, r))
                    for v in r.variants:
                        claimed.setdefault(v, j)

    def test_no_single_above_a_pair_shares_its_allele_after_resolution(self):
        # docs/22 rule 2 as an invariant over random pools: after stages 2 and
        # 3, no single row sits above a pair row that shares an allele with it.
        rng = random.Random(741)
        universe = [allele("chr1", p) for p in (1000, 2000, 3000)] + [allele("chr2", p) for p in (3000, 4000)]
        for _ in range(500):
            k = rng.randint(2, 5)
            pool = [cand(v, "G1" if v[0] == "chr1" else "G2", rng.choice("AB"), rng.choice([True, False]),
                         rng.randint(1, 9)) for v in rng.sample(universe, k)]
            rows = select_rows(pool).rows
            for j, pair in enumerate(rows):
                if pair.is_pair:
                    for i in range(j):
                        if not rows[i].is_pair:
                            self.assertFalse(rows[i].variants & pair.variants, (pool, rows))

    def test_promotion_may_lift_a_weaker_pair_over_the_evidence_winner(self):
        # Review of 1783250, finding B2, pinned as a decision rather than a
        # defect. Single c (Tier A, rank 5) sits above pair (a,b) (Tier B,
        # both lanes, rank 1) by evidence. Pair (a,c) shares c with that
        # single and is promoted into its slot, landing ABOVE (a,b). The
        # evidence winner (a,b) then shares a with the kept pair and is
        # demoted to its single b. Under its own truth the file scores 50
        # where an order that kept it first would score 100; under truth
        # (a,c) the file scores 100 where that order would score 50.
        # policy_probe.py measured this promotion ("direct") ahead of the
        # variant that never passes a higher pair ("floor", 46.574 against
        # 43.395), because the floor variant leaves the single's allele
        # stranded below and loses the partial credit it was earning.
        from mva_prioritizer.track1_submission import parse_submission, score_submission
        a, b, c = allele("chr1", 1000), allele("chr1", 2000, "C", "T"), allele("chr1", 3000, "G", "A")
        pool = [cand(c, "G1", "A", both_lanes=False, rank=5), cand(a, "G1", "B", rank=1), cand(b, "G1", "B", rank=1)]
        result = select_rows(pool)
        self.assertEqual([r.variants for r in result.rows],
                         [frozenset({a, c}), frozenset({b}), frozenset({c}), frozenset({a})])
        parsed = parse_submission(build_submission_csv(result), allow_repeated_pairings=True)
        self.assertEqual(score_submission(parsed, frozenset({a, b})).rank_points, 50.0)
        self.assertEqual(score_submission(parsed, frozenset({a, c})).rank_points, 100.0)

    def test_reviewers_r2_counterexample_now_scores_50(self):
        # Review of 741aaad, logic error 3: keeping the losing pair at rank 4
        # scored 25 under truth chr1:1000+chr1:2000, while dropping it scored
        # 50 and lost F-max (0.500). In-place demotion of the losing pair
        # (which shares chr1:1000 with the kept pair chr1:1000+chr2:3000)
        # scores 50 AND keeps the dropped policy's lost recall (F-max 0.571).
        from mva_prioritizer.candidate_selection import resolve_rows
        from mva_prioritizer.track1_submission import parse_submission, score_submission
        a, b, c, e, f = (allele("chr1", 1000), allele("chr1", 2000), allele("chr2", 3000),
                         allele("chr3", 5000), allele("chr2", 4000))
        win = _row([a, c], "A", rank=1)
        bystander1 = _row([e], "A", rank=2)
        bystander2 = _row([f], "A", rank=3)
        lose = _row([a, b], "A", rank=4)
        resolved, _, demoted, _ = resolve_rows([win, bystander1, bystander2, lose])
        self.assertEqual(demoted, 1)
        self.assertEqual([r.variants for r in resolved],
                         [frozenset({a, c}), frozenset({e}), frozenset({f}), frozenset({b})])
        parsed = parse_submission(build_submission_csv(_result(resolved)), allow_repeated_pairings=True)
        scored = score_submission(parsed, frozenset({a, b}))
        self.assertEqual(scored.rank_points, 50.0)
        self.assertAlmostEqual(scored.f_max, 4 / 7, places=3)


def _row(variants, tier, rank, both=True):
    from mva_prioritizer.candidate_selection import _make_row
    return _make_row(variants, "G", tier, both, rank)


def _result(rows):
    """Wrap already-resolved rows as a SelectionResult with ladder EPCRs."""
    from dataclasses import replace
    return SelectionResult(
        rows=tuple(replace(r, epcr=EPCR_LADDER[i]) for i, r in enumerate(rows)),
        pool_size=len(rows), pair_rows_formed=sum(1 for r in rows if r.is_pair),
    )


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
