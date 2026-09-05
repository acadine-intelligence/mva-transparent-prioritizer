"""Pin the TSV-driven two-stage recomputation against the direct engine answer.

Fixtures come from one execution of ``runtime/exomiser-probe-20260905/RoundTrip.java``
and ``Recompute.java`` on 2026-09-05 against the hash-verified exomiser-core-15.1.0.jar:

- ``exomiser_roundtrip_variants.tsv``: what the real ``TsvVariantResultsWriter`` wrote for
  six synthetic genes after the baseline (0.914) filter and inheritance analysis.
- ``exomiser_recompute_from_tsv.json``: what ``Recompute`` produced by reading only that
  TSV, applying the filter mirror at 0.963, and asking the real ``InheritanceModeAnnotator``.
- ``exomiser_roundtrip_strict.json``: the direct engine answer at 0.963 for the same genes,
  built in memory without any serialization.

The private sensitivity design (docs/18) rests on the TSV route reproducing the direct
answer. These tests pin that agreement and the TSV row model the design relies on.
No private data: every row is synthetic (SYNG*, SYNTHETIC_PROBAND).
"""

import csv
import json
import unittest
from collections import defaultdict
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TSV = FIXTURES / "exomiser_roundtrip_variants.tsv"
RECOMPUTE = FIXTURES / "exomiser_recompute_from_tsv.json"
STRICT = FIXTURES / "exomiser_roundtrip_strict.json"

REQUIRED_COLUMNS = {"GENE_SYMBOL", "MOI", "WHITELIST_VARIANT", "CONTIG", "START", "END", "REF", "ALT",
                    "GENOTYPE", "FUNCTIONAL_CLASS", "ALL_FREQ", "ALL_PATH"}


def read_tsv():
    with TSV.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    return rows


class ExomiserTsvRecomputeFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_tsv()
        cls.recompute = json.loads(RECOMPUTE.read_text())
        cls.strict = json.loads(STRICT.read_text())

    def test_tsv_carries_every_column_the_design_reads(self):
        self.assertTrue(REQUIRED_COLUMNS <= set(self.rows[0]), sorted(REQUIRED_COLUMNS - set(self.rows[0])))
        self.assertEqual(self.rows[0]["#RANK"], "1")

    def test_tsv_row_model_is_one_row_per_variant_per_mode(self):
        keys = defaultdict(set)
        for row in self.rows:
            keys[(row["GENE_SYMBOL"], row["CONTIG"], row["START"], row["REF"], row["ALT"])].add(row["MOI"])
        self.assertEqual(len(self.rows), 18)
        self.assertEqual(len(keys), 10, "ten unique synthetic variants")
        self.assertEqual(keys[("SYNG1", "1", "100000", "A", "T")], {"AD", "AR"})
        self.assertEqual(keys[("SYNG3", "1", "300000", "A", "T")], {"AR"}, "1% survivor is recessive-only at baseline")
        self.assertEqual(keys[("SYNG5", "1", "500000", "G", "C")], {"AD"})
        self.assertEqual(keys[("SYNG4", "1", "400000", "A", "T")], {"ANY"}, "failed variant appears under the ANY placeholder")

    def test_tsv_fields_the_json_omits_are_present_here(self):
        by_start = {row["START"]: row for row in self.rows}
        self.assertEqual(by_start["100000"]["GENOTYPE"], "0/1")
        self.assertEqual(by_start["100000"]["FUNCTIONAL_CLASS"], "coding_transcript_intron_variant")
        self.assertEqual(by_start["600000"]["FUNCTIONAL_CLASS"], "regulatory_region_variant")
        self.assertEqual(by_start["500000"]["FUNCTIONAL_CLASS"], "missense_variant")
        self.assertEqual(by_start["100000"]["WHITELIST_VARIANT"], "0")
        self.assertEqual(by_start["300000"]["ALL_FREQ"], "GNOMAD_G_NFE=1.0")
        self.assertEqual(by_start["210000"]["ALL_PATH"], "REMM=0.95")
        self.assertEqual(by_start["500000"]["ALL_PATH"], "REVEL=0.1")

    def test_recomputation_from_tsv_reproduces_direct_engine_answer(self):
        self.assertEqual(self.recompute, self.strict)

    def test_recomputation_outcomes_the_design_depends_on(self):
        self.assertEqual(self.recompute["SYNG1"], {"strict_survivors": 2, "modes": {"AUTOSOMAL_DOMINANT": 2, "AUTOSOMAL_RECESSIVE": 2}})
        self.assertEqual(self.recompute["SYNG2"], {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}}, "partner lost, dominant survivor stays")
        self.assertEqual(self.recompute["SYNG3"], {"strict_survivors": 1, "modes": {}}, "partner lost, 1% survivor has no mode")
        self.assertEqual(self.recompute["SYNG4"], {"strict_survivors": 0, "modes": {}}, "below baseline, never a survivor")
        self.assertEqual(self.recompute["SYNG5"]["strict_survivors"], 1, "coding variant passes under NON_CODING target")
        self.assertEqual(self.recompute["SYNG6"], {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}})


if __name__ == "__main__":
    unittest.main()
