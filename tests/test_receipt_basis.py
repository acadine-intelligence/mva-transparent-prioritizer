"""Synthetic count-basis regression tests. No case-derived fixtures."""
import copy
import json
import unittest
from mva_prioritizer.receipt_basis import (
    BasisError, GeneCounts, VariantCounts, labeled_gene_counts,
    labeled_variant_counts, partitions_sum, validate_receipt,
)


def synthetic_receipt():
    return {
        "lanes": {
            "l1": json.loads(VariantCounts(8, 5).to_json()),
            "l2": json.loads(VariantCounts(6, 4).to_json()),
        },
        "partition": {"basis": "unique_contig_pos_ref_alt_keys", "shared": 2,
                      "only_l1": 3, "only_l2": 2, "total": 7},
    }


class BasisLabelingTest(unittest.TestCase):
    def test_empty_and_unrecognized_receipts_are_rejected(self):
        for payload in ({}, {"status": "ready"}, {"lanes": {}}, {"lanes": {"l1": {}}}):
            with self.subTest(payload=payload), self.assertRaises(BasisError):
                validate_receipt(payload)

    def test_gene_extra_rows_are_not_multiple_mode_gene_count(self):
        # SYNTHETIC_GENE_A has four rows; SYNTHETIC_GENE_B has one.
        # Three extra rows come from just one repeated gene.
        payload = json.loads(labeled_gene_counts(5, 2, 3).to_json())
        self.assertNotIn("multi_moi_symbols", payload)
        self.assertEqual(payload["extra_rows"], {
            "basis": "extra_tsv_rows_beyond_unique_gene_symbols", "count": 3})
        self.assertEqual(payload["identity"], "rows == unique_symbols + extra_rows")

    def test_variant_counts_carry_explicit_basis(self):
        payload = json.loads(labeled_variant_counts(rows=8, unique_keys=5).to_json())
        self.assertEqual(payload["rows"]["basis"], "tsv_rows_variant_x_gene_association")
        self.assertEqual(payload["unique_keys"]["basis"], "unique_contig_pos_ref_alt_keys")

    def test_identity_violation_is_rejected(self):
        with self.assertRaises(BasisError):
            GeneCounts(5, 2, 2)

    def test_valid_partition_and_missing_basis(self):
        partition = synthetic_receipt()["partition"]
        self.assertTrue(partitions_sum(partition))
        del partition["basis"]
        with self.assertRaises(BasisError):
            partitions_sum(partition)

    def test_unlabeled_lane_count_is_rejected(self):
        payload = synthetic_receipt()
        validate_receipt(payload)
        payload["lanes"]["l1"]["rows"] = 8
        with self.assertRaises(BasisError):
            validate_receipt(payload)

    def test_malformed_receipts_are_rejected(self):
        changes = [
            lambda p: p.update(unrecognized=1),
            lambda p: p.update(partition={}),
            lambda p: p.update(partition=None),
            lambda p: p["lanes"].update(l1=None),
            lambda p: p["lanes"]["l1"].update(rows=None),
            lambda p: p["lanes"]["l1"].pop("unique_keys"),
            lambda p: p["lanes"]["l1"].update(ignored_count=99),
            lambda p: p["lanes"]["l1"]["rows"].update(basis="made_up"),
            lambda p: p["lanes"]["l1"]["rows"].update(basis="unique_gene_symbols"),
            lambda p: p["lanes"]["l1"]["rows"].pop("count"),
            lambda p: p["lanes"]["l1"]["rows"].update(count=True),
            lambda p: p["lanes"]["l1"]["rows"].update(count=-1),
            lambda p: p["lanes"]["l1"]["rows"].update(count=8.0),
            lambda p: p["lanes"]["l1"]["rows"].update(count="8"),
            lambda p: p["lanes"]["l1"]["rows"].update(count=4),
            lambda p: p["partition"].update(basis="unique_wrong"),
            lambda p: p["partition"].update(shared=True),
            lambda p: p["partition"].update(shared=-1),
            lambda p: p["partition"].pop("only_l2"),
            lambda p: p["partition"].update(ignored=1),
            lambda p: p["lanes"].pop("l2"),
            lambda p: p["lanes"]["l1"]["unique_keys"].update(count=6),
        ]
        for index, change in enumerate(changes):
            payload = synthetic_receipt()
            change(payload)
            with self.subTest(index=index), self.assertRaises(BasisError):
                validate_receipt(payload)

    def test_constructor_counts_require_nonnegative_integers(self):
        for value in (True, -1, 2.0, "2", None):
            with self.subTest(value=value), self.assertRaises(BasisError):
                VariantCounts(value, value)
        with self.assertRaises(BasisError):
            GeneCounts(-1, -1, 0)

    def test_library_rejects_incorrect_partition_total(self):
        payload = synthetic_receipt()
        payload["partition"]["total"] = 5
        with self.assertRaises(BasisError):
            validate_receipt(payload)


if __name__ == "__main__":
    unittest.main()
