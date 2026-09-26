"""Which rank does a loser see under the batch schedule: its current index,
or its rank in the promoted table? Synthetic only.

The review of c1c2c34 found that the Schedule sentence of docs/22 said
"judged at its rank in the promoted table" while the module judges each
loser at its current index, after removals and duplicate drops earlier in
the same round have moved it up. This script measures both readings as
policies with the same promotion (direct) and the same stage-3 rule
(pays_gt), on the same universe and seeds as policy_probe.py, and reports
where the files differ and which reading scores higher. Every function is
implemented here; the module is measured as its own row.

Run from the repo root: python3 verification/scorer-hedging/batch_rank_reading.py
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
    return off.score_proband("P", sub, frozenset(truth)).rank_points


def _points(rank):
    return 100 if rank == 1 else 50 if rank <= 3 else 25 if rank <= 5 else 10 if rank <= 10 else 0


def pays_gt(r, q):
    return _points(r) > 0.5 * _points(q)


def promote(rows):
    out = list(rows)
    for _ in range(len(out) * len(out) + 1):
        moved = False
        for j, pair in enumerate(out):
            if not pair.is_pair:
                continue
            singles = [i for i in range(j) if not out[i].is_pair and (out[i].variants & pair.variants)]
            if not singles:
                continue
            for s, r in zip(singles + [j], [pair] + [out[i] for i in singles]):
                out[s] = r
            moved = True
            break
        if not moved:
            return out
    raise RuntimeError("promotion did not converge")


def demote_at_index(rows):
    """Current-index reading: one loser at a time, topmost first, each judged
    at its index in the table as the earlier demotions left it."""
    out = list(rows)
    while True:
        claimed = {}
        changed = False
        for j, r in enumerate(out):
            if not r.is_pair:
                continue
            shared = r.variants & set(claimed)
            if not shared:
                for v in r.variants:
                    claimed[v] = j
                continue
            q = min(claimed[v] for v in shared) + 1
            if pays_gt(j + 1, q):
                for v in r.variants:
                    claimed.setdefault(v, j)
                continue
            unshared = r.variants - shared
            if not unshared:
                del out[j]
            else:
                (u,) = unshared
                if any(not x.is_pair and x.variants == frozenset({u}) for x in out[:j]):
                    del out[j]
                else:
                    out[j] = replace(r, variants=frozenset({u}), demoted_from=r.variants)
                    out = out[:j + 1] + [x for x in out[j + 1:] if x.is_pair or x.variants != frozenset({u})]
            changed = True
            break
        if not changed:
            return out


def demote_at_promoted_rank(rows):
    """Frozen-rank reading: every loser in the table is judged at its rank in
    the promoted table, then all decisions are applied at once; repeat."""
    out = list(rows)
    while True:
        claimed = {}
        decisions = {}
        for j, r in enumerate(out):
            if not r.is_pair:
                continue
            shared = r.variants & set(claimed)
            if not shared:
                for v in r.variants:
                    claimed[v] = j
                continue
            q = min(claimed[v] for v in shared) + 1
            if pays_gt(j + 1, q):
                for v in r.variants:
                    claimed.setdefault(v, j)
                continue
            decisions[j] = r.variants - shared
        if not decisions:
            return out
        new = []
        seen = set()
        for j, r in enumerate(out):
            if j in decisions:
                if not decisions[j]:
                    continue
                (u,) = decisions[j]
                if u in seen:
                    continue
                new.append(replace(r, variants=frozenset({u}), demoted_from=r.variants))
                seen.add(u)
            elif not r.is_pair:
                (v,) = r.variants
                if v in seen:
                    continue
                new.append(r)
                seen.add(v)
            else:
                new.append(r)
        out = new


def joint(rows, demote):
    out = list(rows)
    for _ in range(400):
        out = promote(out)
        nxt = demote(out)
        if [r.variants for r in nxt] == [r.variants for r in out]:
            return out
        out = nxt
    raise RuntimeError("joint resolution did not converge")


POLICIES = {
    "plain": lambda rows: rows,
    "batch/current-index": lambda rows: joint(rows, demote_at_index),
    "batch/promoted-rank": lambda rows: joint(rows, demote_at_promoted_rank),
    "module": lambda rows: resolve_rows(rows)[0],
}


def random_pool(rng):
    k = rng.randint(2, 8)
    return [Candidate(v, GENE[v[0]], rng.choice(TIERS), rng.choice([True, False]), rng.randint(1, 9), True)
            for v in rng.sample(UNIVERSE, k)]


def main():
    print("Two readings of the batch schedule, direct promotion, pays_gt, on policy_probe.py's universe.")
    print("differ: pools where the two readings write different files. below: comparisons under the plain sort.\n")
    for seed in (20260926, 1, 2, 3, 4):
        rng = random.Random(seed)
        total = {p: 0.0 for p in POLICIES}
        below = {p: 0 for p in POLICIES}
        n = differ = same_module = 0
        for _ in range(3000):
            pool = random_pool(rng)
            base = order_rows(pool)
            outs = {p: f(list(base)) for p, f in POLICIES.items()}
            if [r.variants for r in outs["batch/current-index"]] != [r.variants for r in outs["batch/promoted-rank"]]:
                differ += 1
            if [r.variants for r in outs["module"]] == [r.variants for r in outs["batch/current-index"]]:
                same_module += 1
            for truth in itertools.combinations([c.variant for c in pool], 2):
                n += 1
                plain = score(base, truth)
                for p in POLICIES:
                    rp = score(outs[p], truth)
                    total[p] += rp
                    if rp < plain - EPS:
                        below[p] += 1
        print(f"seed {seed}: {n:,} comparisons, differ {differ}/3,000, module == current-index on {same_module:,}/3,000")
        for p in POLICIES:
            print(f"  {p:22s} below {below[p]:>4}  mean {total[p] / n:.4f}")
        print()


if __name__ == "__main__":
    main()
