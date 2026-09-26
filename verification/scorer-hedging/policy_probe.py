"""Probe: which sharing-pair policy to ship. Public and synthetic only."""
from __future__ import annotations
import itertools, pathlib, random, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools/official-track1"))
import evaluation as off
from dataclasses import replace
from mva_prioritizer.candidate_selection import (EPCR_LADDER, Candidate, Row, order_rows,
                                                 promote_rows, _demote_once, _variant_key)

UNIVERSE = [("chr1", 1000, "A", "G"), ("chr1", 2000, "C", "T"), ("chr1", 3000, "G", "A"),
            ("chr2", 3000, "G", "A"), ("chr2", 4000, "T", "C"), ("chr3", 5000, "A", "C")]
GENE = {"chr1": "G1", "chr2": "G2", "chr3": "G3"}
EPS = 1e-9

def score(rows, truth):
    sub = [off.SubmissionRow(variants=r.variants, epcr=EPCR_LADDER[i], rank=i + 1, finding_type="primary")
           for i, r in enumerate(rows[:10])]
    res = off.score_proband("P", sub, frozenset(truth)); return res.rank_points, res.f_max

def demote_all(rows):
    out = list(rows)
    for _ in range(100):
        out, what = _demote_once(out)
        if what is None: return out
    raise RuntimeError

def _points(rank):
    return 100 if rank == 1 else 50 if rank <= 3 else 25 if rank <= 5 else 10 if rank <= 10 else 0

def demote_when_it_pays(rows):
    """Walk top to bottom. A pair sharing an allele with a kept pair above it
    at rank q, itself at rank r, is kept when its own full-match value
    points(r) is at least the partial value the winner already gives it,
    0.5*points(q); otherwise it becomes its unshared single in place (or is
    removed when both alleles are claimed, or when its single already sits
    above). Iterated to a fixpoint because a removal shifts ranks."""
    out = list(rows)
    for _ in range(50):
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
            if _points(j + 1) >= 0.5 * _points(q):
                for v in r.variants: claimed.setdefault(v, j)
                continue
            unshared = r.variants - shared
            if not unshared or any(not x.is_pair and x.variants == unshared for x in out[:j]):
                del out[j]
            else:
                (u,) = unshared
                out[j] = replace(r, variants=frozenset({u}), demoted_from=r.variants)
                out = out[:j + 1] + [x for x in out[j + 1:] if x.is_pair or x.variants != frozenset({u})]
            changed = True
            break
        if not changed:
            return out
    raise RuntimeError

POLICIES = {
    "plain":                lambda rows: rows,
    "promote_keep":         lambda rows: promote_rows(rows)[0],
    "demote_then_promote":  lambda rows: promote_rows(demote_all(rows))[0],
    "promote_then_demote":  lambda rows: demote_all(promote_rows(rows)[0]),
    "promote_then_pays":    lambda rows: demote_when_it_pays(promote_rows(rows)[0]),
}

def main():
    rng = random.Random(20260926)
    names = list(POLICIES)
    wins = {p: {q: 0 for q in names} for p in names}
    fwins = {p: {q: 0 for q in names} for p in names}
    total = {p: 0.0 for p in names}; ftotal = {p: 0.0 for p in names}
    n = 0
    for _ in range(4000):
        k = rng.randint(2, 6)
        pool = [Candidate(v, GENE[v[0]], rng.choice("AB"), rng.choice([True, False]), rng.randint(1, 9), True)
                for v in rng.sample(UNIVERSE, k)]
        base = order_rows(pool)
        outs = {p: f(list(base)) for p, f in POLICIES.items()}
        for truth in itertools.combinations([c.variant for c in pool], 2):
            n += 1
            sc = {p: score(outs[p], truth) for p in names}
            for p in names:
                total[p] += sc[p][0]; ftotal[p] += sc[p][1]
                for q in names:
                    if p != q:
                        if sc[p][0] > sc[q][0] + EPS: wins[p][q] += 1
                        if sc[p][1] > sc[q][1] + EPS: fwins[p][q] += 1
    print(f"{n:,} truth comparisons over 4,000 random pools\n")
    print("mean rank points / mean F-max per policy")
    for p in names: print(f"  {p:22s} {total[p]/n:7.3f}   {ftotal[p]/n:.4f}")
    print("\nrank-point wins[row over column]")
    print(" " * 24 + "".join(f"{q[:12]:>13s}" for q in names))
    for p in names: print(f"  {p:22s}" + "".join(f"{wins[p][q]:>13,}" for q in names))
    print("\nF-max wins[row over column]")
    print(" " * 24 + "".join(f"{q[:12]:>13s}" for q in names))
    for p in names: print(f"  {p:22s}" + "".join(f"{fwins[p][q]:>13,}" for q in names))

main()
