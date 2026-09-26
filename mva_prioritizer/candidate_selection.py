"""Executable form of docs/22, the pre-registered candidate selection rule.

This module turns a pool of candidate alleles, each carrying the tier evidence
the rule names, into the ordered Track 1 rows the rule prescribes. It is the
code that makes docs/22 checkable: if the document and this module disagree,
one of them is wrong and ``tests/test_candidate_selection.py`` says which
sentence.

It handles no data. The caller assembles the pool from the frozen verified
outputs on the encrypted host (Steps 1 to 3 of docs/22, which read private
files and therefore run there). This module performs Steps 4 to 6 and writes
the canonical CSV shape that ``track1_submission.parse_submission`` accepts.
Every example in the tests is invented.

Step 4 has three stages, applied in this order:

1. The evidence sort. Tier, lane agreement, native rank, coordinate. Row
   class (pair or single) is only a final tiebreak, never a primary key: an
   earlier draft sorted every pair above every single and the measurement
   arm of docs/22 had already falsified that formulation.
2. Promotion. A pair row takes the topmost slot among itself and the single
   rows above it that share one of its alleles; those singles fill the
   block's remaining slots in their existing order. Rows outside the block
   keep their positions, so the promotion can never push an unrelated row
   across a rank-point tier boundary.
3. Demotion. A pair row that shares an allele with a pair row kept above it
   is a competing hypothesis that lost on evidence. Under its own truth it
   already earns the partial value of the winner's rank (half the winner's
   points), and a full match preempts a partial, so it stays a pair only
   where its own full-match points at its rank are strictly above that
   partial value. Otherwise it becomes a single row for its unshared
   allele, in the same position, or is removed when both alleles are
   claimed above. ``verification/scorer-hedging/policy_probe.py`` measures
   twelve promotion and demotion policies, each implemented in the probe,
   against one bar first (never scoring below the plain evidence sort
   under any truth) and mean rank points second; this rule is the best
   policy that clears the bar, and the probe checks that the module
   coincides with it.

Rule version: docs/22 at the commit that introduced this ordering. The CSV
notes column names that version so a file can be traced to the rule that
built it.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from .track1_submission import HEADER, MAX_ROWS, EXPECTED_PROBAND, MITOCHONDRIAL_NAMES

Variant = Tuple[str, int, str, str]

RULE_VERSION = "docs/22"

# Step 5: "Descending, distinct, from a fixed ladder assigned by row position".
EPCR_LADDER: Tuple[float, ...] = (0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05)

TIERS: Tuple[str, ...] = ("A", "B", "C", "D")
PAIRING_TIERS: FrozenSet[str] = frozenset({"A", "B"})

# Step 4 coordinate key: "the pinned contig order". Numeric autosomes, then X,
# Y, and the mitochondrion under either accepted spelling.
CONTIG_ORDER: Dict[str, int] = {f"chr{i}": i for i in range(1, 23)}
CONTIG_ORDER.update({"chrX": 23, "chrY": 24})
CONTIG_ORDER.update({name: 25 for name in MITOCHONDRIAL_NAMES})


class SelectionError(ValueError):
    """The pool violates a precondition of the rule. No file is produced."""


@dataclass(frozen=True)
class Candidate:
    """One allele from the pool after Steps 1 to 3, with its tier evidence."""

    variant: Variant
    gene: str
    tier: str
    both_lanes: bool
    native_rank: int
    recessive_annotation: bool


@dataclass(frozen=True)
class Row:
    variants: FrozenSet[Variant]
    gene: str
    tier: str
    both_lanes: bool
    native_rank: int
    sort_key: Tuple
    epcr: float = 0.0
    # Alleles of the single rows this pair was promoted past (stage 2).
    promoted_over: Tuple[Variant, ...] = ()
    # The pair this single row stands in for after demotion (stage 3).
    demoted_from: Optional[FrozenSet[Variant]] = None

    @property
    def is_pair(self) -> bool:
        return len(self.variants) == 2

    def ordered_variants(self) -> Tuple[Variant, ...]:
        return tuple(sorted(self.variants, key=_variant_key))


@dataclass(frozen=True)
class SelectionResult:
    rows: Tuple[Row, ...]
    pool_size: int
    pair_rows_formed: int
    truncated_by_tier: Dict[str, int] = field(default_factory=dict)
    mitochondrial_rows: int = 0
    promotions: int = 0
    demoted_pairs: int = 0
    removed_pairs: int = 0


def _variant_key(v: Variant) -> Tuple[int, int, str, str]:
    chrom, pos, ref, alt = v
    return (CONTIG_ORDER[chrom], pos, ref, alt)


def _validate_pool(pool: Sequence[Candidate]) -> None:
    if not pool:
        raise SelectionError("empty pool")
    seen = set()
    for c in pool:
        if c.tier not in TIERS:
            raise SelectionError("unknown tier")
        if c.variant[0] not in CONTIG_ORDER:
            raise SelectionError("unknown contig")
        if c.variant in seen:
            raise SelectionError("duplicate variant in pool")
        seen.add(c.variant)
        if c.native_rank < 1:
            raise SelectionError("native rank must be positive")


def _weaker_tier(a: str, b: str) -> str:
    return a if TIERS.index(a) >= TIERS.index(b) else b


def _make_row(variants: Iterable[Variant], gene: str, tier: str, both_lanes: bool, native_rank: int) -> Row:
    vs = frozenset(variants)
    ordered = tuple(sorted(vs, key=_variant_key))
    # Step 4 stage 1, the keys in order: tier, lane agreement, native rank,
    # first allele coordinate, class (pair before single) as the tiebreak
    # between a pair and the single of its own first allele, second allele.
    key = (
        TIERS.index(tier),
        0 if both_lanes else 1,
        native_rank,
        _variant_key(ordered[0]),
        0 if len(vs) == 2 else 1,
        _variant_key(ordered[1]) if len(vs) == 2 else (),
    )
    return Row(variants=vs, gene=gene, tier=tier, both_lanes=both_lanes, native_rank=native_rank, sort_key=key)


def _form_rows(pool: Sequence[Candidate]) -> List[Row]:
    rows: List[Row] = []
    for c in pool:
        rows.append(_make_row([c.variant], c.gene, c.tier, c.both_lanes, c.native_rank))

    # Step 4: pairing across the union of Tier A and Tier B, same gene, both
    # carrying the recessive annotation. A cross-tier pair takes the weaker tier.
    by_gene: Dict[str, List[Candidate]] = {}
    for c in pool:
        if c.tier in PAIRING_TIERS and c.recessive_annotation:
            by_gene.setdefault(c.gene, []).append(c)
    for gene, members in by_gene.items():
        members = sorted(members, key=lambda c: _variant_key(c.variant))
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                rows.append(_make_row(
                    [a.variant, b.variant], gene,
                    _weaker_tier(a.tier, b.tier),
                    a.both_lanes and b.both_lanes,
                    min(a.native_rank, b.native_rank),
                ))
    return rows


def order_rows(pool: Sequence[Candidate]) -> List[Row]:
    """Step 4 stage 1 only: the evidence sort, before promotion and demotion."""
    _validate_pool(pool)
    return sorted(_form_rows(pool), key=lambda r: r.sort_key)


def _promote_once(rows: List[Row]) -> Tuple[List[Row], bool]:
    """One promotion: the topmost pair that has a sharing single above it takes
    the topmost slot of its block; the sharing singles fill the block's other
    slots in their existing order. Rows outside the block keep their
    positions, which is what makes the move safe under every truth: the
    top slot of the block still holds every allele it held before.

    The block may reach above a pair row the evidence ranked higher than
    this one, when a sharing single sits above both. The pair then lands
    above the evidence winner. This is deliberate and measured (docs/22
    Step 4 stage 2): the alternative that preserves pair order pushes the
    single's allele down and loses the partial credit it was earning."""
    for j, pair in enumerate(rows):
        if not pair.is_pair:
            continue
        above = [i for i in range(j) if not rows[i].is_pair and (rows[i].variants & pair.variants)]
        if not above:
            continue
        slots = above + [j]
        movers = [rows[i] for i in above]
        promoted = replace(
            pair,
            promoted_over=pair.promoted_over + tuple(
                v for r in movers for v in sorted(r.variants, key=_variant_key)),
        )
        out = list(rows)
        out[slots[0]] = promoted
        for slot, mover in zip(slots[1:], movers):
            out[slot] = mover
        return out, True
    return rows, False


def promote_rows(rows: List[Row]) -> Tuple[List[Row], int]:
    """Step 4 stage 2 to a fixpoint. Returns the rows and the promotion count."""
    out = list(rows)
    count = 0
    for _ in range(len(out) * len(out) + 1):
        out, moved = _promote_once(out)
        if not moved:
            return out, count
        count += 1
    raise SelectionError("allele-sharing promotion did not converge")


def _rank_points(rank: int) -> int:
    """The official rank-point tiers (tools/official-track1/evaluation.py)."""
    return 100 if rank == 1 else 50 if rank <= 3 else 25 if rank <= 5 else 10 if rank <= 10 else 0


def _demote_once(rows: List[Row]) -> Tuple[List[Row], Optional[str]]:
    """One demotion. Walk top to bottom. A pair at rank r that shares an
    allele with a pair kept above it at rank q lost on evidence. Under its
    own truth it already earns the partial value 0.5 * points(q) through
    that winner, and the scorer takes a full match over a better partial.
    So the pair row is demoted whenever its own full-match value points(r)
    is no better than that partial: it becomes a single row for its
    unshared allele in the same position, and a lower single for that
    allele is dropped as a duplicate. It is removed outright when both of
    its alleles are claimed by pairs above it.

    Where points(r) is strictly better than the partial, the pair stays.
    That is the one demotion policy that never scores below the plain
    evidence sort under any truth (verification/scorer-hedging/
    policy_probe.py measures every alternative against that bar); always
    demoting has a marginally higher mean over uniformly random truths and
    loses that guarantee.

    This runs after promotion has reached a fixpoint, so no single row that
    shares an allele with a pair sits above that pair here."""
    claimed: Dict[Variant, int] = {}
    for j, row in enumerate(rows):
        if not row.is_pair:
            continue
        shared = row.variants & set(claimed)
        if not shared:
            for v in row.variants:
                claimed[v] = j
            continue
        winner_rank = min(claimed[v] for v in shared) + 1
        if _rank_points(j + 1) > 0.5 * _rank_points(winner_rank):
            for v in row.variants:
                claimed.setdefault(v, j)
            continue
        unshared = row.variants - shared
        out = list(rows)
        if not unshared:
            del out[j]
            return out, "removed"
        (u,) = unshared
        remnant = Row(
            variants=frozenset({u}), gene=row.gene, tier=row.tier, both_lanes=row.both_lanes,
            native_rank=row.native_rank, sort_key=row.sort_key, demoted_from=row.variants,
        )
        out[j] = remnant
        # The remnant now carries this allele; a lower single for the same
        # allele is a duplicate and adds nothing.
        for k in range(len(out) - 1, j, -1):
            if not out[k].is_pair and out[k].variants == remnant.variants:
                del out[k]
        return out, "demoted"
    return rows, None


def resolve_rows(rows: List[Row]) -> Tuple[List[Row], int, int, int]:
    """Step 4 stages 2 and 3 to a joint fixpoint. Returns the rows and the
    promotion, demotion and removal counts."""
    out = list(rows)
    promotions = demoted = removed = 0
    for _ in range(len(out) * len(out) + 1):
        out, n = promote_rows(out)
        promotions += n
        out, what = _demote_once(out)
        if what is None:
            return out, promotions, demoted, removed
        if what == "demoted":
            demoted += 1
        else:
            removed += 1
    raise SelectionError("pair resolution did not converge")


def select_rows(pool: Sequence[Candidate]) -> SelectionResult:
    """Steps 4 to 6 of docs/22 over an assembled pool. Returns the ordered rows
    with EPCR assigned and the truncation counts by tier."""
    ordered = order_rows(pool)
    pair_count = sum(1 for r in ordered if r.is_pair)
    resolved, promotions, demoted, removed = resolve_rows(ordered)

    # Step 6: cap at ten, cutting from the bottom of the final order one row at
    # a time, so truncation climbs through tiers when the lowest is exhausted.
    truncated: Dict[str, int] = {}
    kept = list(resolved)
    while len(kept) > MAX_ROWS:
        dropped = kept.pop()
        truncated[dropped.tier] = truncated.get(dropped.tier, 0) + 1

    # Step 5: EPCR from the ladder by row position.
    final = tuple(replace(r, epcr=EPCR_LADDER[i]) for i, r in enumerate(kept))
    mito = sum(1 for r in final for v in r.variants if v[0] in MITOCHONDRIAL_NAMES)
    return SelectionResult(
        rows=final, pool_size=len(pool), pair_rows_formed=pair_count,
        truncated_by_tier=truncated, mitochondrial_rows=mito,
        promotions=promotions, demoted_pairs=demoted, removed_pairs=removed,
    )


def build_submission_csv(result: SelectionResult, proband_id: str = EXPECTED_PROBAND) -> str:
    """The canonical CSV shape ``parse_submission`` accepts. Notes carry the tier
    and the rule version only; no gene symbol and no evidence text."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADER)
    for r in result.rows:
        vs = r.ordered_variants()
        first = vs[0]
        second: Optional[Variant] = vs[1] if len(vs) == 2 else None
        writer.writerow([
            proband_id,
            first[0], str(first[1]), first[2], first[3],
            second[0] if second else "", str(second[1]) if second else "",
            second[2] if second else "", second[3] if second else "",
            f"{r.epcr:.2f}",
            "primary",
            f"tier={r.tier} rule={RULE_VERSION}",
        ])
    return buf.getvalue()
