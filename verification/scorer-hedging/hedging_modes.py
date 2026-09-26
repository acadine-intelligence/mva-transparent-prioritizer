"""Separate the two failure modes found in the hedging brute force.

Against the PINNED official scorer (tools/official-track1/evaluation.py).
Public and synthetic only. Every variant below is invented.

Modes under test:
  A. Does appending rows STRICTLY BELOW every existing row ever lower RANK POINTS?
  B. Does appending rows STRICTLY BELOW every existing row ever lower F-MAX?
  C. Does appending a row at an EPCR EQUAL to an existing row ever lower F-MAX?
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


def score(row_specs, truth):
    rows = [(frozenset(v), float(e), "primary") for v, e in row_specs]
    rows_sorted = sorted(enumerate(rows), key=lambda x: (-x[1][1], x[0]))
    built = [
        off.SubmissionRow(variants=v, epcr=e, rank=i + 1, finding_type=ft)
        for i, (_, (v, e, ft)) in enumerate(rows_sorted)
    ]
    r = off.score_proband("PROBAND01", built, frozenset(truth))
    return r.rank_points, r.f_max


def shapes():
    s = [(v,) for v in UNIVERSE]
    s += [p for p in itertools.combinations(UNIVERSE, 2)]
    return s


def main() -> int:
    S = shapes()
    truths = [(UNIVERSE[0],), (UNIVERSE[0], UNIVERSE[1])]

    a_pts_drop = []   # strictly-below hedging lowers rank points
    b_f_drop = []     # strictly-below hedging lowers F-max
    c_f_drop = []     # equal-EPCR hedging lowers F-max
    c_pts_drop = []   # equal-EPCR hedging lowers rank points
    n = 0
    n_strict = 0
    n_equal = 0

    for truth in truths:
        for base_n in (1, 2, 3):
            base_epcrs = [0.9, 0.8, 0.7][:base_n]
            for base_shapes in itertools.product(S, repeat=base_n):
                base = list(zip(base_shapes, base_epcrs))
                bp, bf = score(base, truth)

                for extra_n in (1, 2):
                    extra_epcrs = [0.6, 0.5][:extra_n]
                    for ex in itertools.product(S, repeat=extra_n):
                        pts, f = score(base + list(zip(ex, extra_epcrs)), truth)
                        n += 1
                        n_strict += 1
                        if pts < bp - 1e-12:
                            a_pts_drop.append((truth, base, list(zip(ex, extra_epcrs)), (bp, bf), (pts, f)))
                        if f < bf - 1e-12:
                            b_f_drop.append((truth, base, list(zip(ex, extra_epcrs)), (bp, bf), (pts, f)))

                for ex in S:
                    pts, f = score(base + [(ex, base_epcrs[0])], truth)
                    n += 1
                    n_equal += 1
                    if f < bf - 1e-12:
                        c_f_drop.append((truth, base, [(ex, base_epcrs[0])], (bp, bf), (pts, f)))
                    if pts < bp - 1e-12:
                        c_pts_drop.append((truth, base, [(ex, base_epcrs[0])], (bp, bf), (pts, f)))

    print(f"combinations scored: {n}")
    print(f"  strictly-below arm: {n_strict}   equal-EPCR arm: {n_equal}")
    either = len({(str(x[0]), str(x[1]), str(x[2])) for x in c_f_drop} | {(str(x[0]), str(x[1]), str(x[2])) for x in c_pts_drop})
    print(f"  equal-EPCR cases where EITHER metric dropped (brute_force_hedging.py counts these): {either}\n")
    print(f"A. strictly-below hedging lowered RANK POINTS : {len(a_pts_drop)}")
    print(f"B. strictly-below hedging lowered F-MAX       : {len(b_f_drop)}")
    print(f"C. equal-EPCR hedging lowered F-MAX           : {len(c_f_drop)}")
    print(f"   equal-EPCR hedging lowered RANK POINTS     : {len(c_pts_drop)}")

    # Characterise mode A: is it always the partial-beats-full inversion?
    if a_pts_drop:
        inversion = 0
        other = []
        for truth, base, ex, before, after in a_pts_drop:
            if len(truth) != 2:
                other.append((truth, base, ex, before, after))
                continue
            # before: partial match only. after: a full match appeared lower down.
            rows_before = [(frozenset(v), e) for v, e in base]
            had_full = any(fs == frozenset(truth) for fs, _ in rows_before)
            added_full = any(frozenset(v) == frozenset(truth) for v, _ in ex)
            if (not had_full) and added_full:
                inversion += 1
            else:
                other.append((truth, base, ex, before, after))
        print(f"\n   of which 'added the exact true pair lower than an existing partial': {inversion}")
        print(f"   unexplained by that inversion: {len(other)}")
        if other:
            print("   first unexplained case:")
            t, b, e, bef, aft = other[0]
            print(f"     truth={t}\n     base={b}\n     added={e}\n     before={bef} after={aft}")

    if b_f_drop:
        print("\n   B first case:")
        t, b, e, bef, aft = b_f_drop[0]
        print(f"     truth={t}\n     base={b}\n     added={e}\n     before={bef} after={aft}")

    # The recommended shape: exact pair on top, each allele alone below.
    print("\n--- recommended shape under both truths ---")
    v1, v2 = UNIVERSE[0], UNIVERSE[1]
    rec = [((v1, v2), 0.9), ((v1,), 0.6), ((v2,), 0.5)]
    for truth in [(v1, v2), (v1,), (v2,), (UNIVERSE[2],)]:
        pts, f = score(rec, truth)
        print(f"  truth={truth!s:<60} rank_points={pts:>6} f_max={f:.3f}")

    print("\n--- pair-only, no hedge rows ---")
    pair_only = [((v1, v2), 0.9)]
    for truth in [(v1, v2), (v1,), (v2,), (UNIVERSE[2],)]:
        pts, f = score(pair_only, truth)
        print(f"  truth={truth!s:<60} rank_points={pts:>6} f_max={f:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
