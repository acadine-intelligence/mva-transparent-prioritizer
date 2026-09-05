"""Validate the supported count-basis receipt shape.

This module checks arithmetic and labels. It does not inspect source TSVs,
validate arbitrary run receipts, or establish biological validity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


class BasisError(ValueError):
    """A count-basis receipt is invalid."""


GENE_ROWS_BASIS = "tsv_rows_gene_x_moi"
GENE_UNIQUE_BASIS = "unique_gene_symbols"
GENE_EXTRA_BASIS = "extra_tsv_rows_beyond_unique_gene_symbols"
VARIANT_ROWS_BASIS = "tsv_rows_variant_x_gene_association"
VARIANT_KEYS_BASIS = "unique_contig_pos_ref_alt_keys"
GENE_IDENTITY = "rows == unique_symbols + extra_rows"
VARIANT_IDENTITY = "rows >= unique_keys (rows carry per-gene associations)"


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise BasisError("counts must be nonnegative integers")
    return value


def _labeled(basis: str, count: int) -> dict:
    return {"basis": basis, "count": _count(count)}


def _read_count(value: object, basis: str) -> int:
    if not isinstance(value, dict) or set(value) != {"basis", "count"}:
        raise BasisError("count requires exactly basis and count")
    if value["basis"] != basis:
        raise BasisError("count basis does not match its field")
    return _count(value["count"])


@dataclass(frozen=True)
class GeneCounts:
    rows: int
    unique: int
    extra_rows: int

    def __post_init__(self) -> None:
        for value in (self.rows, self.unique, self.extra_rows):
            _count(value)
        if self.rows != self.unique + self.extra_rows:
            raise BasisError("gene row identity mismatch")
        if (self.rows == 0) != (self.unique == 0):
            raise BasisError("empty rows and unique counts must agree")

    def to_json(self) -> str:
        return json.dumps({
            "rows": _labeled(GENE_ROWS_BASIS, self.rows),
            "unique_symbols": _labeled(GENE_UNIQUE_BASIS, self.unique),
            "extra_rows": _labeled(GENE_EXTRA_BASIS, self.extra_rows),
            "identity": GENE_IDENTITY,
        }, sort_keys=True)


def labeled_gene_counts(rows: int, unique: int, extra_rows: int) -> GeneCounts:
    return GeneCounts(rows, unique, extra_rows)


@dataclass(frozen=True)
class VariantCounts:
    rows: int
    unique_keys: int

    def __post_init__(self) -> None:
        _count(self.rows)
        _count(self.unique_keys)
        if self.rows < self.unique_keys:
            raise BasisError("variant rows cannot be fewer than unique keys")
        if (self.rows == 0) != (self.unique_keys == 0):
            raise BasisError("empty rows and unique counts must agree")

    def to_json(self) -> str:
        return json.dumps({
            "rows": _labeled(VARIANT_ROWS_BASIS, self.rows),
            "unique_keys": _labeled(VARIANT_KEYS_BASIS, self.unique_keys),
            "identity": VARIANT_IDENTITY,
        }, sort_keys=True)


def labeled_variant_counts(rows: int, unique_keys: int) -> VariantCounts:
    return VariantCounts(rows, unique_keys)


def partitions_sum(partition: dict) -> bool:
    """Check a unique-entity union. Invalid shape or types raise BasisError."""
    expected = {"basis", "shared", "only_l1", "only_l2", "total"}
    if not isinstance(partition, dict) or set(partition) != expected:
        raise BasisError("partition requires exact fields and explicit basis")
    if partition["basis"] not in (GENE_UNIQUE_BASIS, VARIANT_KEYS_BASIS):
        raise BasisError("partition requires a supported unique-entity basis")
    for field in expected - {"basis"}:
        _count(partition[field])
    return partition["shared"] + partition["only_l1"] + partition["only_l2"] == partition["total"]


def _validate_lane(lane: object) -> tuple[str, int]:
    if not isinstance(lane, dict):
        raise BasisError("lane must be an object")
    if "unique_symbols" in lane:
        required = {"rows", "unique_symbols"}
        allowed = required | {"extra_rows", "identity"}
        if not required <= set(lane) <= allowed:
            raise BasisError("gene lane fields invalid")
        rows = _read_count(lane["rows"], GENE_ROWS_BASIS)
        unique = _read_count(lane["unique_symbols"], GENE_UNIQUE_BASIS)
        extra = _read_count(lane["extra_rows"], GENE_EXTRA_BASIS) if "extra_rows" in lane else rows - unique
        GeneCounts(rows, unique, extra)
        basis, identity = GENE_UNIQUE_BASIS, GENE_IDENTITY
    else:
        required = {"rows", "unique_keys"}
        if not required <= set(lane) <= required | {"identity"}:
            raise BasisError("variant lane fields invalid")
        rows = _read_count(lane["rows"], VARIANT_ROWS_BASIS)
        unique = _read_count(lane["unique_keys"], VARIANT_KEYS_BASIS)
        VariantCounts(rows, unique)
        basis, identity = VARIANT_KEYS_BASIS, VARIANT_IDENTITY
    if "identity" in lane and lane["identity"] != identity:
        raise BasisError("identity text does not match the lane")
    return basis, unique


def validate_receipt(payload: dict) -> None:
    """Check a count-basis receipt. Original run receipts need an explicit adapter."""
    if not isinstance(payload, dict) or not {"lanes"} <= set(payload) <= {"lanes", "partition"}:
        raise BasisError("unsupported receipt shape")
    lanes = payload["lanes"]
    if not isinstance(lanes, dict) or not lanes or not set(lanes) <= {"l1", "l2"}:
        raise BasisError("receipt requires named l1 or l2 lanes")
    totals = {name: _validate_lane(lane) for name, lane in lanes.items()}
    if "partition" not in payload:
        return
    partition = payload["partition"]
    if not partitions_sum(partition):
        raise BasisError("partition total mismatch")
    if set(totals) != {"l1", "l2"}:
        raise BasisError("partition requires both lanes")
    for name, only in (("l1", "only_l1"), ("l2", "only_l2")):
        basis, unique = totals[name]
        if partition["basis"] != basis:
            raise BasisError("partition basis differs from lane basis")
        if partition["shared"] + partition[only] != unique:
            raise BasisError("partition differs from lane unique total")
