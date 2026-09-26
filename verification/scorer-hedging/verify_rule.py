"""Verify the corrected docs/22 ordering rule under the challenge's stated answer-key shape.

Two earlier drafts of this check were wrong, and both errors are recorded here
because they change what the rule may claim:

  Draft 1 compared the rule against the BEST possible ordering. That is an
  oracle that already knows the answer key, so no rule can match it and the
  comparison proves nothing. The meaningful claim is domination: the rule must
  never LOWER the score relative to not applying it.

  Draft 2 ran over every truth shape, including a single-variant answer key.
  Under a single-variant truth, moving a pair above a single that exactly
  matches it costs 50 points. But the official scorer states its own answer-key
  shape in its docstring:

      "simplified for a single proband ("N-of-1") with a clinically validated
       compound-heterozygous answer key"

  and partial credit is gated on it at line 133: is_compound_het = len(true_variants) == 2.
  So the answer key is a PAIR. This script states that assumption explicitly and
  tests under it. If the organizers ever contradict it, this check must be re-run.

Claims under test, all without access to the answer key:
  R1. Placing every pair row above every single row never lowers the score.
  R2. Keeping a weaker allele-sharing pair BELOW dominates dropping it.

Public and synthetic only. Every variant below is invented.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/official-track1"))

import evaluation as off

UNIVERSE = [
    ("chr1", 1000, "A", "G"),
    ("chr1", 2000, "C", "T"),
    ("chr2", 3000, "G", "A"),
    ("chr2", 4000, "T", "C"),
    ("chr3", 5000, "A", "C"),
]

LADDER = [0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05]


def score_ordering(ordered_shapes, truth):
    specs = list(zip(ordered_shapes, LADDER[: len(ordered_shapes)]))
    rows = [(frozenset(v), float(e), "primary") for v, e in specs]
    rows_sorted = sorted(enumerate(rows), key=lambda x: (-x[1][1], x[0]))
    built = [
        off.SubmissionRow(variants=v, epcr=e, rank=i + 1, finding_type=ft)
        for i, (_, (v, e, ft)) in enumerate(rows_sorted)
    ]
    r = off.score_proband("PROBAND01", built, frozenset(truth))
    return r.rank_points


def promote_allele_sharing(ordered_shapes):
    """The rule as it survives measurement: promote a pair above every SINGLE row
    that shares an allele with it. Relative order of two pairs is NEVER changed.

    Two earlier formulations were falsified by this script:

      "every pair above every single" moves an UNRELATED pair above a true
      single and costs 25 points (draft 3, 1,020 cases).

      "every pair above any row sharing an allele" reorders two allele-sharing
      PAIRS, and since the rule cannot know which of them is true, the swap
      demotes the true pair half the time (draft 4, 420 cases).

    Pair-versus-pair precedence is a question about which hypothesis is stronger.
    That is evidence, decided by tier in Step 3, not by this ordering rule.
    """
    rows = list(ordered_shapes)
    for _ in range(len(rows) ** 2 + 1):
        for i, upper in enumerate(rows):
            if len(upper) != 1:          # only a SINGLE row can be leapfrogged
                continue
            for j in range(i + 1, len(rows)):
                lower = rows[j]
                if len(lower) == 2 and (set(upper) & set(lower)):
                    rows.insert(i, rows.pop(j))
                    break
            else:
                continue
            break
        else:
            return rows
    return rows


def main() -> int:
    singles = [(v,) for v in UNIVERSE]
    pairs = [p for p in itertools.combinations(UNIVERSE, 2)]
    all_shapes = singles + pairs

    # The answer key is a compound-heterozygous PAIR, per the official docstring.
    truths = pairs

    r1_lowered, r1_raised, r1_checked = [], 0, 0
    for n in (2, 3):
        for combo in itertools.permutations(all_shapes, n):
            original = list(combo)
            ruled = promote_allele_sharing(original)
            raised_here = False
            for truth in truths:
                o = score_ordering(original, truth)
                r = score_ordering(ruled, truth)
                r1_checked += 1
                if r < o - 1e-12:
                    r1_lowered.append((truth, original, ruled, o, r))
                if r > o + 1e-12:
                    raised_here = True
            if raised_here:
                r1_raised += 1

    # R2: for every pair of allele-sharing pairs, keeping the weaker one below
    # against dropping it entirely.
    r2_drop_better, r2_keep_better, r2_equal, r2_checked = [], 0, 0, 0
    for a, b in itertools.permutations(pairs, 2):
        if not (set(a) & set(b)):
            continue
        keep = [a, b]      # stronger first, weaker kept below
        drop = [a]         # weaker discarded
        for truth in truths:
            k = score_ordering(keep, truth)
            d = score_ordering(drop, truth)
            r2_checked += 1
            if d > k + 1e-12:
                r2_drop_better.append((truth, keep, drop, k, d))
            elif k > d + 1e-12:
                r2_keep_better += 1
            else:
                r2_equal += 1

    print("ASSUMPTION: the answer key is a compound-heterozygous pair")
    print("            (official evaluation.py docstring; partial credit gated at line 133)\n")

    print(f"R1  allele-sharing promotion, comparisons : {r1_checked}")
    print(f"R1  the rule LOWERED the score            : {len(r1_lowered)}")
    print(f"R1  row sets where it RAISED it           : {r1_raised}")
    print()
    print(f"R2  allele-sharing pair comparisons       : {r2_checked}")
    print(f"R2  dropping beat keeping-below           : {len(r2_drop_better)}")
    print(f"R2  keeping-below beat dropping           : {r2_keep_better}")
    print(f"R2  equal                                 : {r2_equal}")

    failed = False
    if r1_lowered:
        failed = True
        print("\n!! R1 FAILED. First 3:")
        for truth, o, r, op, rp in r1_lowered[:3]:
            print(f"  truth={truth}\n  orig ={o} -> {op}\n  ruled={r} -> {rp}")
    if r2_drop_better:
        failed = True
        print("\n!! R2 FAILED. First 3:")
        for truth, k, d, kp, dp in r2_drop_better[:3]:
            print(f"  truth={truth}\n  keep={k} -> {kp}\n  drop={d} -> {dp}")

    if not failed:
        print("\nRESULT: both rules hold under a compound-heterozygous answer key.")
        print("  R1 promoting a pair above only the rows SHARING AN ALLELE with it")
        print(f"     never lowered the score, and raised it on {r1_raised} row sets.")
        print("  R2 keeping a weaker allele-sharing pair below never scored lower than")
        print(f"     dropping it, and scored higher in {r2_keep_better} comparisons.")
        print("     Step 4 must therefore KEEP the conflicting pair, not drop it.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
