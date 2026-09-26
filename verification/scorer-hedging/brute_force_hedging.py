"""Exhaustive check of the hedging claim against the PINNED official Track 1 scorer.

Claim under test (asserted to Jonathan on 2026-09-19):
  Adding extra candidate rows BELOW your best row is free: it can never lower
  rank points and can never lower F-max.

Method: brute force over a small variant universe using the official
evaluation.py bytes vendored at tools/official-track1/evaluation.py.
Public and synthetic only. Every variant below is invented.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/official-track1"))

import evaluation as off  # the pinned official scorer

# Invented variant universe. Nothing here comes from any case.
UNIVERSE = [
    ("chr1", 1000, "A", "G"),
    ("chr1", 2000, "C", "T"),
    ("chr2", 3000, "G", "A"),
    ("chr2", 4000, "T", "C"),
    ("chr3", 5000, "A", "C"),
]


def build_rows(row_specs):
    """row_specs: list of (variant_tuple_or_pair, epcr). Returns SubmissionRow list
    exactly as load_submission would after its sort."""
    rows = []
    for variants, epcr in row_specs:
        rows.append((frozenset(variants), float(epcr), "primary"))
    rows_sorted = sorted(enumerate(rows), key=lambda x: (-x[1][1], x[0]))
    return [
        off.SubmissionRow(variants=v, epcr=e, rank=i + 1, finding_type=ft)
        for i, (_, (v, e, ft)) in enumerate(rows_sorted)
    ]


def score(row_specs, truth):
    rows = build_rows(row_specs)
    r = off.score_proband("PROBAND01", rows, frozenset(truth))
    return r.rank_points, r.f_max


def candidate_row_shapes():
    """Every single-variant row and every two-variant pair over the universe."""
    shapes = [(v,) for v in UNIVERSE]
    shapes += [p for p in itertools.combinations(UNIVERSE, 2)]
    return shapes


def main() -> int:
    shapes = candidate_row_shapes()
    truths = [(UNIVERSE[0],), (UNIVERSE[0], UNIVERSE[1])]

    strict_violations = []
    equal_violations = []
    checked = 0

    for truth in truths:
        # Base submissions of 1..3 rows with strictly decreasing distinct EPCRs.
        for base_n in (1, 2, 3):
            base_epcrs = [0.9, 0.8, 0.7][:base_n]
            for base_shapes in itertools.product(shapes, repeat=base_n):
                base = list(zip(base_shapes, base_epcrs))
                base_pts, base_f = score(base, truth)

                # ---- Arm 1: append 1 or 2 hedge rows STRICTLY below every base row
                for extra_n in (1, 2):
                    extra_epcrs = [0.6, 0.5][:extra_n]
                    for extra_shapes in itertools.product(shapes, repeat=extra_n):
                        combined = base + list(zip(extra_shapes, extra_epcrs))
                        pts, f = score(combined, truth)
                        checked += 1
                        if pts < base_pts - 1e-12 or f < base_f - 1e-12:
                            strict_violations.append(
                                (truth, base, list(zip(extra_shapes, extra_epcrs)),
                                 (base_pts, base_f), (pts, f))
                            )

                # ---- Arm 2: append ONE hedge row at an EPCR EQUAL to the top row
                for extra_shape in shapes:
                    combined = base + [(extra_shape, base_epcrs[0])]
                    pts, f = score(combined, truth)
                    checked += 1
                    if pts < base_pts - 1e-12 or f < base_f - 1e-12:
                        equal_violations.append(
                            (truth, base, [(extra_shape, base_epcrs[0])],
                             (base_pts, base_f), (pts, f))
                        )

    print(f"scored combinations: {checked}")
    print(f"strictly-lower hedge violations: {len(strict_violations)}")
    print(f"equal-EPCR hedge violations:     {len(equal_violations)}")

    if strict_violations:
        print("\n!! STRICT CLAIM FALSIFIED. First 3 counterexamples:")
        for v in strict_violations[:3]:
            truth, base, extra, before, after = v
            print(f"  truth={truth}")
            print(f"  base={base}")
            print(f"  added={extra}")
            print(f"  before (pts,f)={before}  after={after}")
    else:
        print("\nStrictly-lower hedging never reduced rank points or F-max.")

    if equal_violations:
        print(f"\nEqual-EPCR hedging DID reduce the score in {len(equal_violations)} cases.")
        truth, base, extra, before, after = equal_violations[0]
        print("  example:")
        print(f"    truth={truth}")
        print(f"    base={base}")
        print(f"    added={extra}")
        print(f"    before (pts,f)={before}  after={after}")

    return 1 if strict_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
