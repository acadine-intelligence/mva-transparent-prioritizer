"""Explicit count-basis labeling for receipt generators.

Receipts mix two counting bases:
- row basis: Exomiser TSV data rows. genes.tsv emits one row per gene x inheritance-mode;
  variants.tsv emits one row per variant-gene association.
- key basis: unique gene symbols; unique contig|pos|ref|alt variant keys.

An unlabeled mix reads as an arithmetic contradiction and costs review cycles.
This module makes the basis an explicit, validated part of every receipt payload.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class BasisError(ValueError):
    """Raised when a receipt payload mixes or omits count bases."""


GENE_ROWS_BASIS = "tsv_rows_gene_x_moi"
GENE_UNIQUE_BASIS = "unique_gene_symbols"
VARIANT_ROWS_BASIS = "tsv_rows_variant_x_gene_association"
VARIANT_KEYS_BASIS = "unique_contig_pos_ref_alt_keys"


def _labeled(basis: str, count: int) -> dict:
    return {"basis": basis, "count": count}


@dataclass(frozen=True)
class GeneCounts:
    rows: int
    unique: int
    multi_moi: int

    def __post_init__(self) -> None:
        if self.rows != self.unique + self.multi_moi:
            raise BasisError(
                f"gene counts violate identity rows({self.rows}) == "
                f"unique({self.unique}) + multi_moi({self.multi_moi})"
            )

    def to_json(self) -> str:
        return json.dumps({
            "rows": _labeled(GENE_ROWS_BASIS, self.rows),
            "unique_symbols": _labeled(GENE_UNIQUE_BASIS, self.unique),
            "multi_moi_symbols": {"basis": GENE_UNIQUE_BASIS, "count": self.multi_moi},
            "identity": "rows == unique + multi_moi",
        }, sort_keys=True)


def labeled_gene_counts(rows: int, unique: int, multi_moi: int) -> GeneCounts:
    return GeneCounts(rows=rows, unique=unique, multi_moi=multi_moi)


@dataclass(frozen=True)
class VariantCounts:
    rows: int
    unique_keys: int

    def __post_init__(self) -> None:
        if self.rows < self.unique_keys:
            raise BasisError(
                f"variant rows({self.rows}) cannot be fewer than unique keys({self.unique_keys})"
            )

    def to_json(self) -> str:
        return json.dumps({
            "rows": _labeled(VARIANT_ROWS_BASIS, self.rows),
            "unique_keys": _labeled(VARIANT_KEYS_BASIS, self.unique_keys),
            "identity": "rows >= unique_keys (rows carry per-gene associations)",
        }, sort_keys=True)


def labeled_variant_counts(rows: int, unique_keys: int) -> VariantCounts:
    return VariantCounts(rows=rows, unique_keys=unique_keys)


def partitions_sum(partition: dict) -> bool:
    """Validate a comparison partition block. Requires an explicit basis label.

    Partition semantics depend on basis: a unique-key partition sums shared + only_l1 + only_l2
    to the combined unique total; a row-basis partition sums to combined rows.
    """
    if "basis" not in partition:
        raise BasisError("partition block missing explicit 'basis' label")
    inner = partition["shared"] + partition["only_l1"] + partition["only_l2"]
    if partition["basis"].startswith("unique"):
        return inner == partition["total"]
    return inner == partition["total"]


def validate_receipt(payload: dict) -> None:
    """Fail closed when a receipt mixes row-basis totals with key-basis partitions unlabeled."""
    for lane in payload.get("lanes", {}).values():
        for key in ("rows", "unique_symbols", "unique_keys"):
            value = lane.get(key) if isinstance(lane, dict) else None
            if value is None:
                continue
            if isinstance(value, dict):
                if "basis" not in value:
                    raise BasisError(f"lane count '{key}' missing explicit 'basis' label")
            else:
                raise BasisError(f"lane count '{key}' must be a labeled block, got raw {type(value).__name__}")
    partition = payload.get("partition")
    if partition:
        partitions_sum(partition)
