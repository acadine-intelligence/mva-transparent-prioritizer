"""Probe: which promotion and which losing-pair policy to ship. Synthetic only.

Every policy here is implemented inside this file, independent of the module,
so no two rows can silently be the same function (the fault the review of
1783250 found in the first version). The shipped module is measured as its
own row at the end and must coincide with one of the named policies.

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
              when both alleles are claimed above)
  pays_ge     demote only when points(r) <  0.5 * points(q)   (keep at equality)
  pays_gt     demote only when points(r) <= 0.5 * points(q)   (demote at equality)
"""
from __future__ import annotations
import itertools, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools/official-track1"))
import evaluation as off
from dataclasses import replace
from mva_prioritizer.candidate_selection import EPCR_LADDER, Candidate, order_rows, resolve_rows

UNIVERSE = [("chr1", 1000, "A", "G"), ("chr1", 2000, "C", "T"), ("chr1", 3000, "G", "A"),
            ("chr2", 3000, "G", "A"), ("chr2", 4000, "T", "C"), ("chr3", 5000, "A", "C")]
GENE = {"chr1": "G1", "chr2": "G2", "chr3": "G3"}
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

def _demote(rows, keep_when):
    out = list(rows)
    for _ in range(100):
        claimed = {}
        changed = False
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
            changed = True
            break
        if not changed:
            return out
    raise RuntimeError("demotion did not converge")

def _joint(rows, mode, keep_when):
    out = list(rows)
    for _ in range(100):
        out = _promote(out, mode)
        nxt = _demote(out, keep_when)
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
for mode in ("direct", "floor", "transitive"):
    for name, keep in STAGE3.items():
        POLICIES[f"{mode}+{name}"] = (lambda m, k: lambda rows: _joint(rows, m, k))(mode, keep)
POLICIES["module"] = lambda rows: resolve_rows(rows)[0]

def main():
    rng = random.Random(20260926)
    names = list(POLICIES)
    total = {p: 0.0 for p in names}; ftotal = {p: 0.0 for p in names}
    below = {p: 0 for p in names}; above = {p: 0 for p in names}
    same = {p: 0 for p in names}
    n = pools = 0
    for _ in range(4000):
        k = rng.randint(2, 6)
        pool = [Candidate(v, GENE[v[0]], rng.choice("AB"), rng.choice([True, False]), rng.randint(1, 9), True)
                for v in rng.sample(UNIVERSE, k)]
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
    print(f"{n:,} truth comparisons over {pools:,} random pools (6 alleles, tiers A/B, ranks 1-9).")
    print("below/above: comparisons where the policy's rank points are below/above the plain evidence sort.")
    print("A policy with below > 0 can hurt the file under some truth and is not eligible.\n")
    print(f"  {'policy':20s} {'below':>7s} {'above':>7s} {'mean rp':>9s} {'mean F-max':>11s} {'= module':>9s}")
    for p in names:
        print(f"  {p:20s} {below[p]:>7,} {above[p]:>7,} {total[p]/n:>9.3f} {ftotal[p]/n:>11.4f} {same[p]:>9,}")
    eligible = [p for p in names if below[p] == 0 and p not in ("plain", "module")]
    best = max(eligible, key=lambda p: (total[p], ftotal[p]))
    print(f"\nBest policy that never scores below the plain sort: {best} "
          f"(mean {total[best]/n:.3f}, F-max {ftotal[best]/n:.4f}).")
    print(f"Module coincides with: {[p for p in names if p not in ('module',) and same[p] == pools]}")

main()
