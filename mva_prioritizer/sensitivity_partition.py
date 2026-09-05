"""Turn a Recompute detail file into the sensitivity partition docs/18 promises.

Input is the JSON written by ``Recompute.java`` as its fourth argument: per gene,
the baseline and strict mode sets, the strict survivor count, and per variant key
the baseline modes, the stage-1 verdict, and the strict modes. This module never
reads a TSV or JSONL; it only does arithmetic and consistency checks on that file.

Classes, per unique variant key:

- ``retained``: passed stage 1 and holds at least one mode after stage 2.
- ``removed_by_cutoff``: failed stage 1 (score at or below the stricter cutoff).
- ``removed_by_inheritance``: passed stage 1 but the real annotator left it no mode.

Per gene: ``retained`` if any variant is retained; ``removed_by_cutoff`` if no variant
passed stage 1; ``removed_by_inheritance`` otherwise. A retained gene whose strict mode
set differs from its baseline mode set is listed by symbol; that list stays out of the
receipt unless the caller asks for it, because symbols from a private run are not
public-safe by default.
"""
from __future__ import annotations

import json

from mva_prioritizer.receipt_basis import labeled_variant_counts

KNOWN_MODES = {
    "ANY", "AUTOSOMAL_DOMINANT", "AUTOSOMAL_RECESSIVE", "X_DOMINANT", "X_RECESSIVE", "MITOCHONDRIAL",
}
CLASSES = ("retained", "removed_by_cutoff", "removed_by_inheritance")


class PartitionError(ValueError):
    """A detail file is inconsistent and must not be summarized."""


def _modes(value: object, where: str) -> frozenset:
    if not isinstance(value, list) or not all(isinstance(m, str) for m in value):
        raise PartitionError(f"{where}: modes must be a list of strings")
    unknown = set(value) - KNOWN_MODES
    if unknown:
        raise PartitionError(f"{where}: unknown mode names {sorted(unknown)}")
    return frozenset(value)


def _int(value: object, where: str) -> int:
    if type(value) is not int or value < 0:
        raise PartitionError(f"{where}: expected a nonnegative integer")
    return value


def partition_from_detail(detail: object) -> dict:
    if not isinstance(detail, dict) or set(detail) != {"tsv_rows", "cutoff", "genes"}:
        raise PartitionError("detail requires exactly tsv_rows, cutoff and genes")
    cutoff = detail["cutoff"]
    if not isinstance(cutoff, (int, float)) or isinstance(cutoff, bool) or not 0 < cutoff < 1:
        raise PartitionError("cutoff must be a number strictly between 0 and 1")
    tsv_rows = _int(detail["tsv_rows"], "tsv_rows")
    genes = detail["genes"]
    if not isinstance(genes, dict) or not genes:
        raise PartitionError("genes must be a non-empty object")

    variant_counts = dict.fromkeys(CLASSES, 0)
    gene_counts = dict.fromkeys(CLASSES, 0)
    changed_mode_genes: list[str] = []
    strict_rows = 0
    baseline_rows = 0
    seen_keys: set[str] = set()

    for symbol, block in genes.items():
        where = f"gene {symbol}"
        if not isinstance(block, dict) or set(block) != {"baseline_modes", "strict_modes", "strict_survivors", "variants"}:
            raise PartitionError(f"{where}: block requires exactly baseline_modes, strict_modes, strict_survivors, variants")
        gene_baseline = _modes(block["baseline_modes"], where)
        gene_strict = _modes(block["strict_modes"], where)
        declared_survivors = _int(block["strict_survivors"], where)
        variants = block["variants"]
        if not isinstance(variants, dict) or not variants:
            raise PartitionError(f"{where}: a written gene carries at least one variant")

        survivors = 0
        any_retained = False
        union_strict: set[str] = set()
        union_baseline: set[str] = set()
        for key, entry in variants.items():
            vwhere = f"{where} variant {key}"
            if not isinstance(key, str) or key.count("|") != 3 or any(not part for part in key.split("|")):
                raise PartitionError(f"{vwhere}: key must be CONTIG|START|REF|ALT")
            if key in seen_keys:
                raise PartitionError(f"{vwhere}: variant key listed under more than one gene")
            seen_keys.add(key)
            if not isinstance(entry, dict) or set(entry) != {"baseline_modes", "stage1_pass", "strict_modes"}:
                raise PartitionError(f"{vwhere}: entry requires exactly baseline_modes, stage1_pass, strict_modes")
            baseline = _modes(entry["baseline_modes"], vwhere)
            strict = _modes(entry["strict_modes"], vwhere)
            passed = entry["stage1_pass"]
            if type(passed) is not bool:
                raise PartitionError(f"{vwhere}: stage1_pass must be a boolean")
            if not baseline:
                raise PartitionError(f"{vwhere}: a written variant had at least one baseline mode")
            if not passed and strict:
                raise PartitionError(f"{vwhere}: strict modes on a variant that failed stage 1")
            if not strict <= baseline:
                raise PartitionError(f"{vwhere}: a stricter cutoff cannot add a mode")
            baseline_rows += len(baseline)
            union_baseline |= baseline
            if not passed:
                variant_counts["removed_by_cutoff"] += 1
                continue
            survivors += 1
            if strict:
                variant_counts["retained"] += 1
                any_retained = True
                union_strict |= strict
                strict_rows += len(strict)
            else:
                variant_counts["removed_by_inheritance"] += 1

        if survivors != declared_survivors:
            raise PartitionError(f"{where}: strict_survivors {declared_survivors} but {survivors} variants passed stage 1")
        if union_strict != gene_strict:
            raise PartitionError(f"{where}: gene strict modes disagree with its variants")
        if union_baseline != gene_baseline:
            raise PartitionError(f"{where}: gene baseline modes disagree with its variants")

        if any_retained:
            gene_counts["retained"] += 1
            if gene_strict != gene_baseline:
                changed_mode_genes.append(symbol)
        elif survivors == 0:
            gene_counts["removed_by_cutoff"] += 1
        else:
            gene_counts["removed_by_inheritance"] += 1

    if tsv_rows != baseline_rows:
        raise PartitionError(f"tsv_rows {tsv_rows} but baseline modes sum to {baseline_rows} rows")

    return {
        "cutoff": cutoff,
        "variants": {"baseline_tsv_rows": tsv_rows, "baseline_unique_keys": len(seen_keys),
                     "strict_tsv_rows_equivalent": strict_rows, **variant_counts},
        "genes": {"baseline_unique_symbols": len(genes), **gene_counts},
        "retained_genes_with_changed_mode_set": sorted(changed_mode_genes),
    }


def partition_receipt(partition: dict, include_symbols: bool = False) -> dict:
    """Count-basis receipt for the baseline and strict lanes. Symbols stay out unless asked."""
    v = partition["variants"]
    baseline = labeled_variant_counts(v["baseline_tsv_rows"], v["baseline_unique_keys"])
    strict = labeled_variant_counts(v["strict_tsv_rows_equivalent"], v["retained"])
    receipt = {
        "cutoff": partition["cutoff"],
        "baseline": {"lanes": {"l2": json.loads(baseline.to_json())}},
        "strict": {"lanes": {"l2": json.loads(strict.to_json())}},
        "variant_partition": {c: v[c] for c in CLASSES},
        "gene_partition": {c: partition["genes"][c] for c in CLASSES},
        "genes_baseline_unique_symbols": partition["genes"]["baseline_unique_symbols"],
        "retained_genes_with_changed_mode_set_count": len(partition["retained_genes_with_changed_mode_set"]),
    }
    if include_symbols:
        receipt["retained_genes_with_changed_mode_set"] = list(partition["retained_genes_with_changed_mode_set"])
    return receipt
