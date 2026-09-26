"""Verify the SHIPPED selection module, not a copy of it.

The review of commit 741aaad (runtime/review-741aaad/verdict.json) found that
verify_determinism.py re-implemented the rule inside the script, so it could
pass while the module diverged, and that its allele-sharing check was vacuous
because the sort it tested had already placed every pair above every single.

This script imports ``mva_prioritizer.candidate_selection`` and checks, over
random pools whose evidence keys are drawn so that promotion and demotion
actually fire:

  D1  DETERMINISM. Every input permutation of a pool yields the identical
      final row list (variants, EPCR, tier).
  D2  INVARIANTS. In every final list: no single row sits above a pair row
      that shares an allele with it; a kept pair that shares an allele with
      a kept pair above it sits only where its own full-match points are
      strictly above the partial it earns through that winner; EPCRs are the
      ladder prefix; at most ten rows.
  D3  FIRING. Promotion and demotion each changed the order in a non-trivial
      share of pools, so D2 was not vacuous.
  D4  DOMINATION AGAINST THE PLAIN EVIDENCE SORT. For every pool and every
      compound-het truth drawn from its alleles, rank points of the resolved
      file are never below rank points of the stage-1 sort alone. F-max is
      reported, not asserted, because the promotion trades F-max for rank
      points by design (docs/22 states the leaderboard's primary metric).

Public and synthetic only. Every allele below is invented.
"""
from __future__ import annotations

import itertools
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/official-track1"))

import evaluation as off  # noqa: E402  the pinned official scorer
from mva_prioritizer.candidate_selection import (  # noqa: E402
    EPCR_LADDER, Candidate, _rank_points, order_rows, select_rows,
)

SEED = 20260926
POOLS = 3000
PERMS_PER_POOL = 24
EPS = 1e-9

UNIVERSE = [("chr1", 1000, "A", "G"), ("chr1", 2000, "C", "T"), ("chr1", 3000, "G", "A"),
            ("chr2", 3000, "G", "A"), ("chr2", 4000, "T", "C"), ("chr3", 5000, "A", "C")]
GENE = {"chr1": "G1", "chr2": "G2", "chr3": "G3"}


def score(rows, truth):
    sub = [off.SubmissionRow(variants=r.variants, epcr=r.epcr or EPCR_LADDER[i], rank=i + 1,
                             finding_type="primary") for i, r in enumerate(rows)]
    res = off.score_proband("P", sub, frozenset(truth))
    return res.rank_points, res.f_max


def signature(rows):
    return tuple((tuple(sorted(r.variants)), r.epcr, r.tier) for r in rows)


def main() -> int:
    rng = random.Random(SEED)
    d1_fail = 0
    d2_single_above_pair = d2_pair_overlap = d2_epcr = d2_cap = 0
    d3_promoted = d3_demoted = d3_changed = 0
    d4_cmp = d4_rp_low = d4_rp_high = d4_f_low = d4_f_high = 0
    first_rp_low = None

    for _ in range(POOLS):
        k = rng.randint(2, 6)
        pool = [Candidate(v, GENE[v[0]], rng.choice("AB"), rng.choice([True, False]),
                          rng.randint(1, 9), True) for v in rng.sample(UNIVERSE, k)]
        base = select_rows(pool)
        base_sig = signature(base.rows)

        # D1
        perms = list(itertools.permutations(pool)) if k <= 4 else [
            rng.sample(pool, k) for _ in range(PERMS_PER_POOL)]
        for perm in perms:
            if signature(select_rows(list(perm)).rows) != base_sig:
                d1_fail += 1
                break

        # D2
        rows = base.rows
        claimed: dict = {}
        for j, r in enumerate(rows):
            if r.is_pair:
                shared = r.variants & set(claimed)
                if shared:
                    q = min(claimed[v] for v in shared) + 1
                    if _rank_points(j + 1) <= 0.5 * _rank_points(q):
                        d2_pair_overlap += 1
                for v in r.variants:
                    claimed.setdefault(v, j)
                for i in range(j):
                    if not rows[i].is_pair and (rows[i].variants & r.variants):
                        d2_single_above_pair += 1
        if [r.epcr for r in rows] != list(EPCR_LADDER[: len(rows)]):
            d2_epcr += 1
        if len(rows) > 10:
            d2_cap += 1

        # D3
        d3_promoted += base.promotions > 0
        d3_demoted += (base.demoted_pairs + base.removed_pairs) > 0
        plain = order_rows(pool)
        if [r.variants for r in plain] != [r.variants for r in rows]:
            d3_changed += 1

        # D4: every compound-het truth over the pool's alleles
        alleles = [c.variant for c in pool]
        for truth in itertools.combinations(alleles, 2):
            prp, pf = score(plain[:10], truth)
            rrp, rf = score(rows, truth)
            d4_cmp += 1
            if rrp < prp - EPS:
                d4_rp_low += 1
                if first_rp_low is None:
                    first_rp_low = (truth, [sorted(r.variants) for r in plain[:10]], prp,
                                    [sorted(r.variants) for r in rows], rrp)
            elif rrp > prp + EPS:
                d4_rp_high += 1
            if rf < pf - EPS:
                d4_f_low += 1
            elif rf > pf + EPS:
                d4_f_high += 1

    print(f"Module under test: mva_prioritizer.candidate_selection (imported, not copied)")
    print(f"Pools: {POOLS:,}  seed {SEED}  universe {len(UNIVERSE)} alleles, tiers A/B, ranks 1-9\n")
    print(f"D1  determinism: pools with a permutation-dependent result   {d1_fail}")
    print(f"D2  single above a sharing pair                              {d2_single_above_pair}")
    print(f"D2  kept sharing pair at a rank that does not strictly pay    {d2_pair_overlap}")
    print(f"D2  EPCR not the ladder prefix                               {d2_epcr}")
    print(f"D2  more than ten rows                                       {d2_cap}")
    print(f"D3  pools where promotion fired                              {d3_promoted:,}")
    print(f"D3  pools where demotion or removal fired                    {d3_demoted:,}")
    print(f"D3  pools where the final order differs from the plain sort  {d3_changed:,}")
    print(f"D4  truth comparisons, resolved vs plain evidence sort       {d4_cmp:,}")
    print(f"D4  rank points LOWER than the plain sort                    {d4_rp_low}")
    print(f"D4  rank points higher than the plain sort                   {d4_rp_high:,}")
    print(f"D4  F-max lower / higher than the plain sort                 {d4_f_low:,} / {d4_f_high:,}")
    if first_rp_low:
        t, p, prp, r, rrp = first_rp_low
        print(f"\n!! first rank-point lowering: truth={t}\n   plain={p} -> {prp}\n   ruled={r} -> {rrp}")

    failed = d1_fail or d2_single_above_pair or d2_pair_overlap or d2_epcr or d2_cap or d4_rp_low
    vacuous = d3_promoted < POOLS * 0.05 or d3_demoted < POOLS * 0.05
    print()
    if failed:
        print("FAILED: the shipped module violates the rule it implements.")
        return 1
    if vacuous:
        print("FAILED: promotion or demotion fired too rarely for D2 to mean anything.")
        return 1
    print("RESULT: the shipped module is deterministic, satisfies the docs/22 invariants,")
    print("        exercised both stages, and never scored below the plain evidence sort.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
