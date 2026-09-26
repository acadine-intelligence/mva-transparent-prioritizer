"""Probe: which promotion, which losing-pair policy and which schedule to ship.
Synthetic only.

Every policy here is implemented inside this file, independent of the module,
so no two rows can silently be the same function (the fault the review of
1783250 found in the first version). The shipped module is measured as its
own row at the end and must coincide with exactly one named policy on every
pool, in a universe wide enough for the policies to differ (the review of
28761f8 found a 3-alleles-per-gene universe hid a schedule difference that a
fourth allele exposes; this universe has 4 alleles in one gene, 3 in another,
2 in a third and 1 in a fourth, and the module is also checked on a second
seed).

Two numbers per policy. The one that decides is DOMINATION: the count of
truth comparisons where the policy scores BELOW the plain evidence sort.
A policy with a non-zero count can hurt the file relative to doing nothing,
under some truth, and no truth-blind rule may do that. The mean over
uniformly random pair truths is reported second; it assumes every pair is
equally likely, which is exactly what the evidence sort denies, so it only
ranks policies that already dominate.

Promotion variants (stage 2), all block moves that leave bystanders in place:
  direct      a pair takes the topmost slot among itself and every sharing
              single above it, even above a pair the evidence ranked higher
  floor       the same, but the block never reaches above a pair that sits
              above this pair; sharing singles above that pair stay put, so
              rule 2 can be left violated
  transitive  the block also carries every pair between the topmost sharing
              single and this pair, pairs first in evidence order, then this
              pair, then the singles; pair order is preserved
Losing-pair policies (stage 3), a losing pair being one that shares an allele
with a pair kept above it (winner at rank q, loser at rank r):
  keep        keep it
  demote      always demote it to its unshared single in place (remove it
              when both alleles are claimed above, or when that single
              already sits above it)
  pays_ge     demote only when points(r) <  0.5 * points(q)   (keep at equality)
  pays_gt     demote only when points(r) <= 0.5 * points(q)   (demote at equality)
Schedules for reaching the joint fixpoint of stages 2 and 3:
  step        promote to a fixpoint, then ONE demotion, and repeat; a single
              created by a demotion is promoted over before the next loser
              is judged (this is what resolve_rows does)
  batch       promote to a fixpoint, then demote to a fixpoint, and repeat
The two schedules judge later losers against different tables and can
produce different files from the same pool.
"""
from __future__ import annotations
import itertools, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools/official-track1"))
import evaluation as off
from dataclasses import replace
from mva_prioritizer.candidate_selection import EPCR_LADDER, Candidate, order_rows, resolve_rows

UNIVERSE = [("chr1", 1000, "A", "G"), ("chr1", 2000, "C", "T"), ("chr1", 3000, "G", "A"), ("chr1", 4000, "T", "C"),
            ("chr2", 3000, "G", "A"), ("chr2", 4000, "T", "C"), ("chr2", 5000, "A", "T"),
            ("chr3", 5000, "A", "C"), ("chr3", 6000, "C", "G"),
            ("chr4", 7000, "G", "T")]
GENE = {"chr1": "G1", "chr2": "G2", "chr3": "G3", "chr4": "G4"}
TIERS = "ABC"
EPS = 1e-9

def score(rows, truth):
    sub = [off.SubmissionRow(variants=r.variants, epcr=EPCR_LADDER[i], rank=i + 1, finding_type="primary")
           for i, r in enumerate(rows[:10])]
    res = off.score_proband("P", sub, frozenset(truth)); return res.rank_points, res.f_max

def _points(rank):
    return 100 if rank == 1 else 50 if rank <= 3 else 25 if rank <= 5 else 10 if rank <= 10 else 0

def _promote(rows, mode):
    out = list(rows)
    for _ in range(len(out) * len(out) + 1):
        moved = False
        for j, pair in enumerate(out):
            if not pair.is_pair:
                continue
            floor = max([i for i in range(j) if out[i].is_pair], default=-1)
            lo = floor + 1 if mode == "floor" else 0
            singles = [i for i in range(lo, j) if not out[i].is_pair and (out[i].variants & pair.variants)]
            if not singles:
                continue
            if mode == "transitive":
                top = singles[0]
                pairs = [i for i in range(top, j) if out[i].is_pair]
                slots = sorted(singles + pairs + [j])
                fill = [out[i] for i in pairs] + [pair] + [out[i] for i in singles]
            else:
                slots = singles + [j]
                fill = [pair] + [out[i] for i in singles]
            for s, r in zip(slots, fill):
                out[s] = r
            moved = True
            break
        if not moved:
            return out
    raise RuntimeError("promotion did not converge")

def _demote_one(rows, keep_when):
    """One demotion or removal, topmost loser first. Returns (rows, changed)."""
    out = list(rows)
    claimed = {}
    for j, r in enumerate(out):
        if not r.is_pair:
            continue
        shared = r.variants & set(claimed)
        if not shared:
            for v in r.variants: claimed[v] = j
            continue
        q = min(claimed[v] for v in shared) + 1
        if keep_when(j + 1, q):
            for v in r.variants: claimed.setdefault(v, j)
            continue
        unshared = r.variants - shared
        if not unshared:
            del out[j]
        else:
            (u,) = unshared
            # A remnant that would duplicate a single already above adds
            # nothing; drop the pair instead. Otherwise the remnant takes
            # the pair's slot and lower duplicates go.
            if any(not x.is_pair and x.variants == frozenset({u}) for x in out[:j]):
                del out[j]
            else:
                out[j] = replace(r, variants=frozenset({u}), demoted_from=r.variants)
                out = out[:j + 1] + [x for x in out[j + 1:] if x.is_pair or x.variants != frozenset({u})]
        return out, True
    return out, False

def _joint(rows, mode, keep_when, schedule):
    out = list(rows)
    for _ in range(400):
        out = _promote(out, mode)
        if schedule == "step":
            out, changed = _demote_one(out, keep_when)
            if not changed:
                return out
        else:
            nxt = out
            while True:
                nxt, changed = _demote_one(nxt, keep_when)
                if not changed:
                    break
            if [r.variants for r in nxt] == [r.variants for r in out]:
                return out
            out = nxt
    raise RuntimeError("joint resolution did not converge")

STAGE3 = {
    "keep":    lambda r, q: True,
    "demote":  lambda r, q: False,
    "pays_ge": lambda r, q: _points(r) >= 0.5 * _points(q),
    "pays_gt": lambda r, q: _points(r) > 0.5 * _points(q),
}
POLICIES = {"plain": lambda rows: rows}
for schedule in ("step", "batch"):
    for mode in ("direct", "floor", "transitive"):
        for name, keep in STAGE3.items():
            POLICIES[f"{schedule}/{mode}+{name}"] = (
                lambda m, k, s: lambda rows: _joint(rows, m, k, s))(mode, keep, schedule)
POLICIES["module"] = lambda rows: resolve_rows(rows)[0]

def random_pool(rng):
    k = rng.randint(2, 8)
    return [Candidate(v, GENE[v[0]], rng.choice(TIERS), rng.choice([True, False]), rng.randint(1, 9), True)
            for v in rng.sample(UNIVERSE, k)]

def main():
    rng = random.Random(20260926)
    names = list(POLICIES)
    total = {p: 0.0 for p in names}; ftotal = {p: 0.0 for p in names}
    below = {p: 0 for p in names}; above = {p: 0 for p in names}
    same = {p: 0 for p in names}
    n = pools = 0
    for _ in range(3000):
        pool = random_pool(rng)
        base = order_rows(pool)
        outs = {p: f(list(base)) for p, f in POLICIES.items()}
        pools += 1
        mod = [r.variants for r in outs["module"]]
        for p in names:
            if [r.variants for r in outs[p]] == mod:
                same[p] += 1
        for truth in itertools.combinations([c.variant for c in pool], 2):
            n += 1
            plain_rp = score(base, truth)[0]
            for p in names:
                rp, f = score(outs[p], truth)
                total[p] += rp; ftotal[p] += f
                if rp < plain_rp - EPS: below[p] += 1
                if rp > plain_rp + EPS: above[p] += 1
    print(f"{n:,} truth comparisons over {pools:,} random pools "
          f"(10 alleles in 4 genes, 4/3/2/1 per gene, 2 to 8 candidates, tiers A/B/C, ranks 1-9).")
    print("below/above: comparisons where the policy's rank points are below/above the plain evidence sort.")
    print("A policy with below > 0 can hurt the file under some truth and is not eligible.\n")
    print(f"  {'policy':28s} {'below':>7s} {'above':>7s} {'mean rp':>9s} {'mean F-max':>11s} {'= module':>9s}")
    for p in names:
        print(f"  {p:28s} {below[p]:>7,} {above[p]:>7,} {total[p]/n:>9.3f} {ftotal[p]/n:>11.4f} {same[p]:>9,}")
    eligible = [p for p in names if below[p] == 0 and p not in ("plain", "module")]
    ranked = sorted(eligible, key=lambda p: (total[p], ftotal[p]), reverse=True)
    print(f"\nEligible policies (never below the plain sort), best first:")
    for p in ranked[:6]:
        print(f"  {p:28s} mean {total[p]/n:.3f}  F-max {ftotal[p]/n:.4f}")
    coincide = [p for p in names if p != "module" and same[p] == pools]
    print(f"\nModule coincides on every pool with: {coincide}")

    # Second seed, module against the named policies only, for the coincidence claim.
    rng2 = random.Random(1)
    agree = {p: 0 for p in names if p != "module"}
    for _ in range(3000):
        base = order_rows(random_pool(rng2))
        mod = [r.variants for r in resolve_rows(list(base))[0]]
        for p in agree:
            if [r.variants for r in POLICIES[p](list(base))] == mod:
                agree[p] += 1
    print(f"Second seed (3,000 pools): module coincides on every pool with: {[p for p, c in agree.items() if c == 3000]}")

main()
