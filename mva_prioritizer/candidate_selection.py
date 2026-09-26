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

Rule version: docs/22 at the commit that introduced this module. The CSV notes
column names that version so a file can be traced to the rule that built it.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

from .track1_submission import HEADER, MAX_ROWS, EXPECTED_PROBAND, MITOCHONDRIAL_NAMES

Variant = Tuple[str, int, str, str]

RULE_VERSION = "docs/22"

# Step 5: "Descending, distinct, from a fixed ladder assigned by row position".
EPCR_LADDER: Tuple[float, ...] = (0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05)

TIERS: Tuple[str, ...] = ("A", "B", "C", "D")
PAIRING_TIERS: FrozenSet[str] = frozenset({"A", "B"})

# Step 4 key 5: "the pinned contig order". Numeric autosomes, then X, Y, and
# the mitochondrion under either accepted spelling.
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
    promoted_over: Tuple[Variant, ...] = ()

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
    # Step 4, the five keys in order: class, tier, lane agreement, native rank, coordinate.
    key = (
        0 if len(vs) == 2 else 1,
        TIERS.index(tier),
        0 if both_lanes else 1,
        native_rank,
        tuple(_variant_key(v) for v in ordered),
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
    """Steps 4 keys 1 to 5 only: the total order, before the allele-sharing constraint."""
    _validate_pool(pool)
    return sorted(_form_rows(pool), key=lambda r: r.sort_key)


def _apply_allele_sharing(rows: List[Row]) -> List[Row]:
    """docs/22 rule 2: a pair row is promoted above every single row that shares
    an allele with it. The relative order of two pair rows is never changed."""
    out = list(rows)
    for _ in range(len(out) * len(out) + 1):
        moved = False
        for i, upper in enumerate(out):
            if upper.is_pair:
                continue
            for j in range(i + 1, len(out)):
                lower = out[j]
                if lower.is_pair and (upper.variants & lower.variants):
                    promoted = out.pop(j)
                    promoted = Row(
                        variants=promoted.variants, gene=promoted.gene, tier=promoted.tier,
                        both_lanes=promoted.both_lanes, native_rank=promoted.native_rank,
                        sort_key=promoted.sort_key,
                        promoted_over=promoted.promoted_over + tuple(sorted(upper.variants, key=_variant_key)),
                    )
                    out.insert(i, promoted)
                    moved = True
                    break
            if moved:
                break
        if not moved:
            return out
    raise SelectionError("allele-sharing promotion did not converge")


def select_rows(pool: Sequence[Candidate]) -> SelectionResult:
    """Steps 4 to 6 of docs/22 over an assembled pool. Returns the ordered rows
    with EPCR assigned and the truncation counts by tier."""
    ordered = order_rows(pool)
    constrained = _apply_allele_sharing(ordered)
    pair_count = sum(1 for r in constrained if r.is_pair)

    # Step 6: cap at ten, cutting from the bottom of the final order one row at
    # a time, so truncation climbs through tiers when the lowest is exhausted.
    truncated: Dict[str, int] = {}
    kept = list(constrained)
    while len(kept) > MAX_ROWS:
        dropped = kept.pop()
        truncated[dropped.tier] = truncated.get(dropped.tier, 0) + 1

    # Step 5: EPCR from the ladder by row position.
    final = tuple(
        Row(variants=r.variants, gene=r.gene, tier=r.tier, both_lanes=r.both_lanes,
            native_rank=r.native_rank, sort_key=r.sort_key, epcr=EPCR_LADDER[i],
            promoted_over=r.promoted_over)
        for i, r in enumerate(kept)
    )
    mito = sum(1 for r in final for v in r.variants if v[0] in MITOCHONDRIAL_NAMES)
    return SelectionResult(
        rows=final, pool_size=len(pool), pair_rows_formed=pair_count,
        truncated_by_tier=truncated, mitochondrial_rows=mito,
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
