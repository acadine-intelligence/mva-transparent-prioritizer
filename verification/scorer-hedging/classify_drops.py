"""Precisely classify the 48,608 rank-point drops.

The reviewer's challenge (2026-09-19): docs/22 asserts every drop was
"the exact true pair added below an existing SINGLE ALLELE of that pair",
but hedging_modes.py only verified the weaker property "the base had no full
match and the added rows contained one". A base row that pairs one true allele
with a WRONG partner also earns partial credit and is NOT a single allele.

This script resolves the distinction by asking, for each drop, what the official
scorer actually used as the higher-ranked partial match.

Public and synthetic only. Every variant below is invented.
"""
from __future__ import annotations

import itertools
import pathlib
import sys
from collections import Counter

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


def build(row_specs):
    rows = [(frozenset(v), float(e), "primary") for v, e in row_specs]
    rows_sorted = sorted(enumerate(rows), key=lambda x: (-x[1][1], x[0]))
    return [
        off.SubmissionRow(variants=v, epcr=e, rank=i + 1, finding_type=ft)
        for i, (_, (v, e, ft)) in enumerate(rows_sorted)
    ]


def score(row_specs, truth):
    r = off.score_proband("PROBAND01", build(row_specs), frozenset(truth))
    return r.rank_points, r.f_max, r


def shapes():
    s = [(v,) for v in UNIVERSE]
    s += [p for p in itertools.combinations(UNIVERSE, 2)]
    return s


def classify_partial(rows, truth):
    """Replicate the scorer's own partial-match search and describe the row it finds."""
    T = frozenset(truth)
    if len(T) != 2:
        return "truth_not_a_pair"
    for row in rows:
        if row.variants == T:
            return "full_match_present"
    for row in rows:
        if row.variants & T:                      # the scorer's own condition
            if len(row.variants) == 1:
                return "single_allele_of_the_pair"
            if len(row.variants) == 2:
                return "true_allele_paired_with_wrong_partner"
            return "other_shape"
    return "no_partial"


def main() -> int:
    S = shapes()
    truths = [(UNIVERSE[0],), (UNIVERSE[0], UNIVERSE[1])]

    kinds = Counter()
    examples = {}
    drops = 0

    for truth in truths:
        for base_n in (1, 2, 3):
            base_epcrs = [0.9, 0.8, 0.7][:base_n]
            for base_shapes in itertools.product(S, repeat=base_n):
                base = list(zip(base_shapes, base_epcrs))
                bp, _bf, _ = score(base, truth)

                for extra_n in (1, 2):
                    extra_epcrs = [0.6, 0.5][:extra_n]
                    for ex in itertools.product(S, repeat=extra_n):
                        combined = base + list(zip(ex, extra_epcrs))
                        pts, _f, _r = score(combined, truth)
                        if pts >= bp - 1e-12:
                            continue
                        drops += 1
                        kind = classify_partial(build(base), truth)
                        kinds[kind] += 1
                        examples.setdefault(kind, (truth, base, list(zip(ex, extra_epcrs)), bp, pts))

    print(f"total rank-point drops: {drops}\n")
    print("what the higher-ranked partial match actually was, in the BASE:")
    for kind, n in kinds.most_common():
        pct = 100.0 * n / drops if drops else 0.0
        print(f"  {kind:<42} {n:>7}  ({pct:5.1f}%)")

    print("\nworked example of each kind:")
    for kind in kinds:
        truth, base, ex, bp, pts = examples[kind]
        print(f"\n  [{kind}]")
        print(f"    truth = {truth}")
        print(f"    base  = {base}")
        print(f"    added = {ex}")
        print(f"    rank points {bp} -> {pts}")

    # The precise claim that docs/22 should make.
    single_only = kinds.get("single_allele_of_the_pair", 0)
    mixed = kinds.get("true_allele_paired_with_wrong_partner", 0)
    print("\n--- verdict on the document's wording ---")
    if mixed:
        print(f"'below an existing SINGLE ALLELE' is TOO NARROW: {mixed} of {drops} drops")
        print("had the partial credit coming from a row pairing a true allele with a WRONG")
        print("partner, which is a two-variant row, not a single allele.")
        print("Correct wording: 'below any existing row that already earns partial credit'.")
    else:
        print(f"'below an existing single allele' holds for all {single_only} drops.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
