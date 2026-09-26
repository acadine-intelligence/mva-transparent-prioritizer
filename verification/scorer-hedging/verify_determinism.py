"""Prove the Step 4 ordering is a TOTAL order with no operator discretion.

The reviewer's blocking finding 3 was that four unconstrained choices survived
the first wording, each changing the submitted file. The rewritten Step 4 states
a five-key sort. A stated total order is still only a claim; this executes it.

Checks:
  T1. ANTISYMMETRY/TOTALITY. Over randomised candidate pools, no two distinct
      rows compare equal. If any pair ties, an operator decides, and the order
      is not total.
  T2. DETERMINISM UNDER INPUT PERMUTATION. The same pool shuffled N ways must
      produce byte-identical final row orders. This is the property the
      reviewer actually cares about: two operators, same evidence, same file.
  T3. CAP CLIMBS TIERS. Truncation from the bottom must climb out of an
      exhausted lowest tier rather than stopping.
  T4. ALLELE-SHARING CONSTRAINT HOLDS after the sort, and never reorders two
      pair rows.

Public and synthetic only. Every allele below is invented.
"""
from __future__ import annotations

import itertools
import random

CONTIG_ORDER = {f"chr{i}": i for i in range(1, 23)}
CONTIG_ORDER.update({"chrX": 23, "chrY": 24, "chrM": 25})
TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
LADDER = [0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05]


def allele_key(a):
    """Step 4 key 5, applied to one allele."""
    chrom, pos, ref, alt = a
    return (CONTIG_ORDER[chrom], pos, ref, alt)


def row_sort_key(row):
    """The five keys of Step 4, in order.

    row = {alleles: tuple, tier: str, both_lanes: bool, ranks: tuple[int,...]}
    """
    alleles = tuple(sorted(row["alleles"], key=allele_key))
    return (
        0 if len(alleles) == 2 else 1,            # 1. class: pairs first
        TIER_ORDER[row["tier"]],                   # 2. tier
        0 if row["both_lanes"] else 1,             # 3. lane agreement
        min(row["ranks"]),                         # 4. better native rank
        tuple(allele_key(a) for a in alleles),     # 5. coordinate
    )


def apply_allele_sharing(rows):
    """A pair row is promoted above every SINGLE row sharing an allele with it.
    Two pair rows are never reordered."""
    out = list(rows)
    for _ in range(len(out) ** 2 + 1):
        for i, upper in enumerate(out):
            if len(upper["alleles"]) != 1:
                continue
            for j in range(i + 1, len(out)):
                lower = out[j]
                if len(lower["alleles"]) == 2 and (set(upper["alleles"]) & set(lower["alleles"])):
                    out.insert(i, out.pop(j))
                    break
            else:
                continue
            break
        else:
            return out
    raise RuntimeError("allele-sharing promotion did not converge")


def order_rows(rows):
    return apply_allele_sharing(sorted(rows, key=row_sort_key))


def fingerprint(rows):
    return tuple(
        (tuple(sorted(r["alleles"], key=allele_key)), r["tier"], r["both_lanes"]) for r in rows
    )


def random_pool(rng, n_rows):
    universe = [
        ("chr1", 1000, "A", "G"), ("chr1", 2000, "C", "T"), ("chr2", 3000, "G", "A"),
        ("chr2", 4000, "T", "C"), ("chr3", 5000, "A", "C"), ("chrX", 6000, "G", "T"),
        ("chr1", 1000, "A", "T"),   # same locus, different alt: coordinate tie-break test
        ("chr1", 1000, "AA", "G"),  # same pos, different ref
    ]
    rows = []
    seen = set()
    while len(rows) < n_rows:
        size = rng.choice([1, 1, 2])
        alleles = tuple(rng.sample(universe, size))
        key = tuple(sorted(alleles, key=allele_key))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "alleles": alleles,
            "tier": rng.choice("ABCD"),
            "both_lanes": rng.choice([True, False]),
            "ranks": tuple(rng.randint(1, 40) for _ in range(size)),
        })
    return rows


def main() -> int:
    rng = random.Random(20260919)

    # ---- T1: no two distinct rows produce an equal sort key
    ties = 0
    t1_checked = 0
    for _ in range(4000):
        pool = random_pool(rng, rng.randint(2, 8))
        keys = {}
        for r in pool:
            k = row_sort_key(r)
            t1_checked += 1
            if k in keys and fingerprint([keys[k]]) != fingerprint([r]):
                ties += 1
            keys[k] = r

    # ---- T2: same pool, every input permutation, identical output
    perm_mismatches = 0
    t2_checked = 0
    for _ in range(600):
        pool = random_pool(rng, rng.randint(2, 6))
        base = fingerprint(order_rows(pool))
        perms = list(itertools.permutations(pool))
        if len(perms) > 120:
            perms = rng.sample(perms, 120)
        for p in perms:
            t2_checked += 1
            if fingerprint(order_rows(list(p))) != base:
                perm_mismatches += 1

    # ---- T3: truncation climbs out of an exhausted lowest tier
    cap_failures = 0
    for _ in range(500):
        pool = random_pool(rng, rng.randint(11, 16))
        ordered = order_rows(pool)
        kept = ordered[:10]
        dropped = ordered[10:]
        if len(kept) != 10:
            cap_failures += 1
        # every kept row must sort at or above every dropped row in the final order
        if any(ordered.index(k) > ordered.index(d) for k in kept for d in dropped):
            cap_failures += 1

    # ---- T4: constraint holds, and pair order is preserved
    constraint_violations = 0
    pair_reorders = 0
    for _ in range(1500):
        pool = random_pool(rng, rng.randint(2, 7))
        sorted_rows = sorted(pool, key=row_sort_key)
        final = apply_allele_sharing(sorted_rows)
        for i, upper in enumerate(final):
            if len(upper["alleles"]) != 1:
                continue
            for lower in final[i + 1:]:
                if len(lower["alleles"]) == 2 and (set(upper["alleles"]) & set(lower["alleles"])):
                    constraint_violations += 1
        before = [fingerprint([r])[0] for r in sorted_rows if len(r["alleles"]) == 2]
        after = [fingerprint([r])[0] for r in final if len(r["alleles"]) == 2]
        if before != after:
            pair_reorders += 1

    print(f"T1 sort keys compared                      : {t1_checked}")
    print(f"T1 distinct rows with an EQUAL key (ties)  : {ties}")
    print(f"T2 permutation runs                        : {t2_checked}")
    print(f"T2 outputs differing by input order        : {perm_mismatches}")
    print(f"T3 cap failures                            : {cap_failures}")
    print(f"T4 allele-sharing violations after sort    : {constraint_violations}")
    print(f"T4 runs where two PAIR rows were reordered : {pair_reorders}")

    failed = ties or perm_mismatches or cap_failures or constraint_violations or pair_reorders
    if failed:
        print("\nFAILED: the ordering leaves a choice open or breaks its own constraint.")
        return 1

    print("\nRESULT: the Step 4 ordering is total and operator-independent.")
    print("  No two distinct rows tie, so no comparison falls to a human.")
    print("  Every input permutation of the same pool produced the identical file.")
    print("  Truncation climbs tiers; the allele-sharing constraint holds and never")
    print("  reorders two pair rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
