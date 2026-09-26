"""Verify the docs/22 ordering rule at every row count the gate allows.

Supersedes verify_rule.py and verify_rule_v2.py. The independent review of
commit 741aaad (runtime/review-741aaad/verdict.json) showed the rule and its
check were wrong in four ways, and v2 confirmed a fifth:

  1. Step 4 put every pair above every single (the "class key"), which is the
     formulation the document's own table records as falsified. Class is no
     longer a key: tier, lane agreement, native rank, coordinate.
  2. verify_rule.py enumerated only 2- and 3-row files, where a promotion cannot
     cross a rank-point tier boundary. Here sizes 2 to 4 are enumerated in
     full and 5 to 10 are sampled with a fixed seed.
  3. The insertion-style promotion leapfrogged unrelated rows (v2 measured
     33,300 lowered comparisons at n=4 from exactly this). The promotion is now
     POSITION-PRESERVING: the pair and the singles that share an allele with it
     occupy a set of positions; the pair takes the topmost of those positions
     and the singles fill the rest in their original order. No other row moves.
  4. "Keeping a weaker allele-sharing pair below never scores lower than
     dropping it" was a 2-row measurement. Here the second pair is measured
     with bystanders under four policies, and the result is reported as a
     trade-off with counts, never as domination.
  5. Rank points and F-max are both reported. The earlier checks measured rank
     points only; the leaderboard shows both.

Every claim below is measured against the pinned official evaluator under
every compound-heterozygous truth in a 6-allele universe. Public and synthetic
only. Every variant is invented.
"""
from __future__ import annotations

import itertools
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/official-track1"))

import evaluation as off  # the pinned official scorer

UNIVERSE = [
    ("chr1", 1000, "A", "G"),
    ("chr1", 2000, "C", "T"),
    ("chr2", 3000, "G", "A"),
    ("chr2", 4000, "T", "C"),
    ("chr3", 5000, "A", "C"),
    ("chrX", 6000, "G", "T"),
]
LADDER = [0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05]
FULL_ENUM_MAX = 4
SAMPLE_PER_SIZE = 40_000
SEED = 20260926
EPS = 1e-12


def score(shapes, truth):
    rows = [
        off.SubmissionRow(variants=frozenset(s), epcr=LADDER[i], rank=i + 1, finding_type="primary")
        for i, s in enumerate(shapes)
    ]
    r = off.score_proband("P", rows, frozenset(truth))
    return r.rank_points, r.f_max


def promote_position_preserving(shapes):
    """For each pair row, top to bottom: collect the positions of the pair and
    of every SINGLE above it that shares an allele with it. Reassign those
    positions only: pair to the topmost, the singles to the rest in their
    original order. Every other row keeps its exact position."""
    out = list(shapes)
    for i in range(len(out)):
        row = out[i]
        if len(row) != 2:
            continue
        block = [j for j in range(i) if len(out[j]) == 1 and set(out[j]) & set(row)]
        if not block:
            continue
        positions = block + [i]
        movers = [out[j] for j in block]
        new_order = [row] + movers
        for pos, r in zip(positions, new_order):
            out[pos] = r
    return out


def orderings(n, shapes, rng):
    if n <= FULL_ENUM_MAX:
        yield from itertools.permutations(shapes, n)
    else:
        for _ in range(SAMPLE_PER_SIZE):
            yield tuple(rng.sample(shapes, n))


def main() -> int:
    rng = random.Random(SEED)
    singles = [(v,) for v in UNIVERSE]
    pairs = list(itertools.combinations(UNIVERSE, 2))
    shapes = singles + pairs
    truths = pairs  # compound-heterozygous answer key, per the official docstring

    # C1: the promotion never lowers rank points; F-max reported separately.
    per_size = {}
    tot = {"cmp": 0, "rp_low": 0, "rp_high_sets": 0, "f_low": 0, "f_high": 0}
    first_rp_low = None
    first_f_low = None
    # C2: no row outside the pair's own block changes position.
    c2_fired = c2_outside_moved = 0

    for n in range(2, 11):
        chk = rp_low = f_low = f_high = 0
        for combo in orderings(n, shapes, rng):
            original = list(combo)
            ruled = promote_position_preserving(original)
            if ruled != original:
                c2_fired += 1
                moved_pairs = [s for s in ruled if len(s) == 2 and ruled.index(s) != original.index(s)]
                touched = set(a for p in moved_pairs for a in p)
                for pos, (o, r) in enumerate(zip(original, ruled)):
                    if o != r and not (set(o) & touched):
                        c2_outside_moved += 1
                        break
            raised_here = False
            for truth in truths:
                orp, of = score(original, truth)
                rrp, rf = score(ruled, truth)
                chk += 1
                if rrp < orp - EPS:
                    rp_low += 1
                    if first_rp_low is None:
                        first_rp_low = (n, truth, original, ruled, orp, rrp)
                elif rrp > orp + EPS:
                    raised_here = True
                if rf < of - EPS:
                    f_low += 1
                    if first_f_low is None:
                        first_f_low = (n, truth, original, ruled, of, rf)
                elif rf > of + EPS:
                    f_high += 1
            if raised_here:
                tot["rp_high_sets"] += 1
        per_size[n] = (chk, rp_low, f_low, f_high)
        tot["cmp"] += chk
        tot["rp_low"] += rp_low
        tot["f_low"] += f_low
        tot["f_high"] += f_high

    # C3: a second pair sharing an allele with a higher pair, with 0-3
    # bystanders between them. Four policies, scored on rank points.
    def policies(a, bystanders, b):
        shared = set(a) & set(b)
        unshared = tuple(x for x in b if x not in shared)
        return {
            "keep_in_place": [a, *bystanders, b],
            "drop": [a, *bystanders],
            "unshared_single": [a, *bystanders, unshared],
            "directly_below": [a, b, *bystanders],
        }

    names = ["keep_in_place", "drop", "unshared_single", "directly_below"]
    wins = {p: {q: 0 for q in names} for p in names}   # wins[p][q]: p scored higher than q
    c3_cmp = 0
    for a, b in itertools.permutations(pairs, 2):
        if not (set(a) & set(b)):
            continue
        others = [s for s in shapes if s not in (a, b) and not (set(s) & set(b))]
        for k in range(0, 4):
            for bystanders in itertools.combinations(others, k):
                pol = policies(a, bystanders, b)
                sc = {p: {t: score(pol[p], t)[0] for t in truths} for p in names}
                for t in truths:
                    c3_cmp += 1
                    for p in names:
                        for q in names:
                            if p != q and sc[p][t] > sc[q][t] + EPS:
                                wins[p][q] += 1

    print("ASSUMPTION: the answer key is a compound-heterozygous pair")
    print("            (official evaluation.py docstring; partial credit gated on len(true_variants) == 2)\n")
    print(f"Universe {len(UNIVERSE)} alleles, {len(shapes)} row shapes, {len(truths)} truths.")
    print(f"Sizes 2..{FULL_ENUM_MAX} enumerated in full; sizes {FULL_ENUM_MAX + 1}..10 sampled "
          f"{SAMPLE_PER_SIZE:,} orderings each, seed {SEED}.\n")

    print("C1  position-preserving promotion, against leaving the order alone")
    print("    size   kind    comparisons   rank-pts lowered   F-max lowered   F-max raised")
    for n, (chk, rl, fl, fh) in per_size.items():
        tag = "full" if n <= FULL_ENUM_MAX else "sample"
        print(f"    n={n:2d}  {tag:6s} {chk:>12,} {rl:>15,} {fl:>15,} {fh:>14,}")
    print(f"    total           {tot['cmp']:>12,} {tot['rp_low']:>15,} {tot['f_low']:>15,} {tot['f_high']:>14,}")
    print(f"    row sets where rank points ROSE: {tot['rp_high_sets']:,}")
    if first_rp_low:
        n, t, o, r, op, rp = first_rp_low
        print(f"    !! first rank-point lowering at n={n}: truth={t}\n       orig={o} -> {op}\n       ruled={r} -> {rp}")
    if first_f_low:
        n, t, o, r, of, rf = first_f_low
        print(f"    first F-max lowering at n={n}: truth={t}\n       orig={o} -> {of:.3f}\n       ruled={r} -> {rf:.3f}")
    print()
    print("C2  the promotion moves only the pair and its own singles")
    print(f"    orderings where it fired                    {c2_fired:,}")
    print(f"    orderings where a row OUTSIDE the block moved {c2_outside_moved:,}")
    print()
    print(f"C3  second allele-sharing pair, 0-3 bystanders, {c3_cmp:,} truth comparisons per policy")
    print("    wins[row policy] over [column policy], rank points:")
    print("    " + " " * 16 + "".join(f"{q:>16s}" for q in names))
    for p in names:
        print(f"    {p:16s}" + "".join(f"{wins[p][q]:>16,}" for q in names))

    failed = tot["rp_low"] > 0 or c2_outside_moved > 0
    print()
    if failed:
        print("FAILED: the corrected rule does not hold as stated.")
        return 1
    print("RESULT: C1 (rank points) and C2 hold at every row count the gate allows.")
    print("        F-max and C3 are reported as measured trade-offs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
