"""Tests for the sensitivity partition built from a Recompute detail file.

The detail fixture was produced by ``runtime/exomiser-probe-20260905/Recompute.java``
from the PASS_ONLY synthetic TSV on 2026-09-05. It is public and synthetic. The
partition module must turn it into the count-basis receipt shape from docs/13 and the
three-way variant partition the private sensitivity design (docs/18) promises, without
ever reading a TSV or a JSONL itself.
"""

import json
import unittest
from pathlib import Path

from mva_prioritizer.receipt_basis import BasisError, validate_receipt
from mva_prioritizer.sensitivity_partition import (
    PartitionError,
    partition_from_detail,
    partition_receipt,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DETAIL = FIXTURES / "exomiser_recompute_detail.json"
STRICT = FIXTURES / "exomiser_roundtrip_strict.json"


def load_detail():
    return json.loads(DETAIL.read_text())


class PartitionFromDetailTest(unittest.TestCase):
    def setUp(self):
        self.detail = load_detail()
        self.partition = partition_from_detail(self.detail)

    def test_variant_partition_is_exhaustive_and_disjoint(self):
        variants = self.partition["variants"]
        total = variants["baseline_unique_keys"]
        self.assertEqual(total, 9)
        classes = ("retained", "removed_by_cutoff", "removed_by_inheritance")
        self.assertEqual(sum(variants[c] for c in classes), total)
        self.assertEqual(variants["retained"], 5)
        self.assertEqual(variants["removed_by_cutoff"], 3, "0.95 partners in SYNG2, SYNG3, SYNG6")
        self.assertEqual(variants["removed_by_inheritance"], 1, "the 1% SYNG3 survivor with no mode left")

    def test_gene_partition_is_exhaustive_and_disjoint(self):
        genes = self.partition["genes"]
        self.assertEqual(genes["baseline_unique_symbols"], 5)
        self.assertEqual(genes["retained"] + genes["removed_by_cutoff"] + genes["removed_by_inheritance"], 5)
        self.assertEqual(genes["retained"], 4)
        self.assertEqual(genes["removed_by_cutoff"], 0, "no gene lost every variant at stage 1")
        self.assertEqual(genes["removed_by_inheritance"], 1, "SYNG3")

    def test_mode_changes_are_reported_only_for_retained_genes(self):
        changed = self.partition["retained_genes_with_changed_mode_set"]
        self.assertEqual(sorted(changed), ["SYNG2", "SYNG6"])
        self.assertNotIn("SYNG3", changed, "a removed gene is not a mode change")
        self.assertNotIn("SYNG1", changed, "unchanged mode set")

    def test_tsv_row_count_is_carried_through_as_row_basis(self):
        self.assertEqual(self.partition["variants"]["baseline_tsv_rows"], 16)

    def test_partition_agrees_with_direct_engine_answer(self):
        strict = json.loads(STRICT.read_text())
        for gene, block in self.detail["genes"].items():
            self.assertEqual(block["strict_survivors"], strict[gene]["strict_survivors"], gene)
            self.assertEqual(set(block["strict_modes"]), set(strict[gene]["modes"]), gene)


class PartitionReceiptTest(unittest.TestCase):
    def test_receipt_validates_against_count_basis_contract(self):
        receipt = partition_receipt(partition_from_detail(load_detail()))
        validate_receipt(receipt["baseline"])
        validate_receipt(receipt["strict"])
        self.assertEqual(receipt["baseline"]["lanes"]["l2"]["unique_keys"]["count"], 9)
        self.assertEqual(receipt["strict"]["lanes"]["l2"]["unique_keys"]["count"], 5)
        self.assertEqual(receipt["strict"]["lanes"]["l2"]["rows"]["count"], 7, "one row per retained variant per strict mode")

    def test_receipt_carries_cutoff_and_no_symbols_by_default(self):
        receipt = partition_receipt(partition_from_detail(load_detail()))
        self.assertEqual(receipt["cutoff"], 0.963)
        self.assertNotIn("retained_genes_with_changed_mode_set", receipt)
        self.assertNotIn("SYNG2", json.dumps(receipt))


class PartitionFailsClosedTest(unittest.TestCase):
    def test_rejects_variant_that_passed_stage1_but_gene_has_no_survivors(self):
        detail = load_detail()
        detail["genes"]["SYNG1"]["strict_survivors"] = 0
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_strict_mode_on_a_variant_that_failed_stage1(self):
        detail = load_detail()
        detail["genes"]["SYNG2"]["variants"]["1|210000|A|T"]["strict_modes"] = ["AUTOSOMAL_DOMINANT"]
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_gene_strict_modes_that_disagree_with_its_variants(self):
        detail = load_detail()
        detail["genes"]["SYNG1"]["strict_modes"] = ["AUTOSOMAL_DOMINANT"]
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_missing_cutoff(self):
        detail = load_detail()
        del detail["cutoff"]
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_unknown_mode_name(self):
        # Rename a mode consistently at gene and variant level so every union check still
        # agrees; only the mode-name guard can reject this.
        detail = load_detail()
        gene = detail["genes"]["SYNG1"]
        gene["baseline_modes"] = ["MADE_UP", "AUTOSOMAL_RECESSIVE"]
        gene["strict_modes"] = ["MADE_UP", "AUTOSOMAL_RECESSIVE"]
        for entry in gene["variants"].values():
            entry["baseline_modes"] = ["MADE_UP", "AUTOSOMAL_RECESSIVE"]
            entry["strict_modes"] = ["MADE_UP", "AUTOSOMAL_RECESSIVE"]
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_empty_gene_block(self):
        detail = load_detail()
        detail["genes"]["SYNG9"] = {"baseline_modes": [], "strict_modes": [], "strict_survivors": 0, "variants": {}}
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_row_count_below_unique_keys_fails_the_basis_contract(self):
        # The receipt layer re-checks the count-basis identity on its own, independent of
        # the multiplicity guard upstream.
        partition = partition_from_detail(load_detail())
        partition["variants"]["baseline_tsv_rows"] = 3
        with self.assertRaises(BasisError):
            partition_receipt(partition)

    def test_rejects_same_variant_key_in_two_genes(self):
        # A CONTIG|START|REF|ALT key names one variant. The unique-key basis counts it once,
        # so a detail that lists it under two genes cannot be summarized on that basis.
        # tsv_rows is adjusted so the multiplicity guard stays satisfied and only the
        # duplicate-key guard can reject.
        detail = load_detail()
        source = detail["genes"]["SYNG1"]["variants"]["1|100000|A|T"]
        target = detail["genes"]["SYNG5"]
        target["variants"]["1|100000|A|T"] = json.loads(json.dumps(source))
        target["strict_survivors"] += 1
        target["baseline_modes"] = sorted(set(target["baseline_modes"]) | set(source["baseline_modes"]))
        target["strict_modes"] = sorted(set(target["strict_modes"]) | set(source["strict_modes"]))
        detail["tsv_rows"] += len(source["baseline_modes"])
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_strict_mode_absent_from_baseline(self):
        # A stricter cutoff can only remove variants, so no variant can gain a mode.
        # Add the mode consistently at variant and gene level so only the subset guard fires.
        detail = load_detail()
        gene = detail["genes"]["SYNG5"]
        variant = gene["variants"]["1|500000|G|C"]
        variant["strict_modes"] = sorted(set(variant["strict_modes"]) | {"AUTOSOMAL_RECESSIVE"})
        gene["strict_modes"] = sorted(set(gene["strict_modes"]) | {"AUTOSOMAL_RECESSIVE"})
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_tsv_rows_that_disagree_with_baseline_mode_multiplicity(self):
        # The TSV has one row per variant per baseline mode, so tsv_rows must equal the sum
        # of baseline mode counts over all variants. Anything else means the detail file
        # and the TSV it claims to summarize are not the same run.
        detail = load_detail()
        detail["tsv_rows"] += 1
        with self.assertRaises(PartitionError):
            partition_from_detail(detail)

    def test_rejects_unexpected_fields_at_every_level(self):
        for path in ((), ("genes", "SYNG1"), ("genes", "SYNG1", "variants", "1|100000|A|T")):
            detail = load_detail()
            node = detail
            for step in path:
                node = node[step]
            node["extra"] = 1
            with self.assertRaises(PartitionError, msg=path):
                partition_from_detail(detail)


if __name__ == "__main__":
    unittest.main()
