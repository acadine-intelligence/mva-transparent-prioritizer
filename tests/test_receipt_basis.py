"""Tests for explicit count-basis labeling in receipt generators.

Lesson from lane-comparison review round 2 (2026-09-04): receipts that mix row-basis
counts (Exomiser TSV rows, one per gene x inheritance-mode or per variant-gene
association) with unique-key-basis counts (distinct gene symbols, distinct
contig|pos|ref|alt keys) must label the basis of every count field. An unlabeled mix
reads as an arithmetic contradiction (424+165=589 != 794) and costs review cycles.
"""

import json
import unittest

from mva_prioritizer.receipt_basis import (
    BasisError,
    GeneCounts,
    VariantCounts,
    labeled_gene_counts,
    labeled_variant_counts,
    partitions_sum,
    validate_receipt,
)


class BasisLabelingTest(unittest.TestCase):
    def test_gene_counts_carry_explicit_basis(self):
        counts = labeled_gene_counts(rows=421, unique=364, multi_moi=57)
        payload = json.loads(counts.to_json())
        self.assertEqual(payload["rows"]["basis"], "tsv_rows_gene_x_moi")
        self.assertEqual(payload["rows"]["count"], 421)
        self.assertEqual(payload["unique_symbols"]["basis"], "unique_gene_symbols")
        self.assertEqual(payload["unique_symbols"]["count"], 364)
        self.assertEqual(payload["multi_moi_symbols"]["count"], 57)
        self.assertEqual(payload["identity"], "rows == unique + multi_moi")

    def test_variant_counts_carry_explicit_basis(self):
        counts = labeled_variant_counts(rows=794, unique_keys=589)
        payload = json.loads(counts.to_json())
        self.assertEqual(payload["rows"]["basis"], "tsv_rows_variant_x_gene_association")
        self.assertEqual(payload["unique_keys"]["basis"], "unique_contig_pos_ref_alt_keys")
        self.assertNotIn("shared", payload)  # partitions belong to comparison receipts

    def test_identity_violation_is_rejected(self):
        with self.assertRaises(BasisError):
            GeneCounts(rows=421, unique=365, multi_moi=57)

    def test_partitions_must_state_their_basis(self):
        # Union across both lanes: shared(165) + only_l1(424) + only_l2(200) = 789.
        # Lane totals are shared+only per lane: l1=589, l2=365.
        self.assertTrue(partitions_sum({"basis": "unique_keys", "shared": 165,
                                        "only_l1": 424, "only_l2": 200, "total": 789}))
        with self.assertRaises(BasisError):
            partitions_sum({"shared": 165, "only_l1": 424, "only_l2": 200, "total": 789})

    def test_unlabeled_lane_count_alongside_partition_fails_closed(self):
        payload = {
            "lanes": {"l1": {"rows": {"basis": "tsv_rows", "count": 794},
                             "unique_keys": {"basis": "unique_contig_pos_ref_alt_keys",
                                             "count": 589}}},
            "partition": {"basis": "unique_keys", "shared": 165,
                          "only_l1": 424, "only_l2": 200, "total": 789},
        }
        validate_receipt(payload)
        bad = {
            "lanes": {"l1": {"rows": 794}},
            "partition": {"basis": "unique_keys", "shared": 165,
                          "only_l1": 424, "only_l2": 200, "total": 789},
        }
        with self.assertRaises(BasisError):
            validate_receipt(bad)


if __name__ == "__main__":
    unittest.main()
