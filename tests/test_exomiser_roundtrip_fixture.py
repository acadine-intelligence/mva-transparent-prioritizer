"""Pin what Exomiser 15.1.0's JsonResultsWriter actually serializes.

The fixture was produced by ``runtime/exomiser-probe-20260905/RoundTrip.java``
on 2026-09-05: six synthetic genes, built in memory, run through the real
baseline ``PathogenicityFilter`` and ``InheritanceModeAnalyser``, then written
by the real ``JsonResultsWriter`` from the hash-verified
``exomiser-core-15.1.0.jar``. No private data, no reference database.

These tests exist because the private sensitivity design (docs/18) depends on
which fields the frozen JSONL does and does not carry. If a later Exomiser
release changes the writer, the fixture must be regenerated and the design
re-read.
"""

import json
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROUNDTRIP = FIXTURES / "exomiser_roundtrip_output.jsonl"
STRICT = FIXTURES / "exomiser_roundtrip_strict.json"

# Fields the writer emits for a variant that carries frequency and pathogenicity data.
EMITTED = {
    "contigName", "start", "end", "ref", "alt", "type", "length",
    "filterStatus", "passedFilterTypes", "failedFilterTypes",
    "frequencyData", "pathogenicityData", "compatibleInheritanceModes",
    "variantScore", "frequencyScore", "pathogenicityScore", "predictedPathogenic",
}
# Fields named in VariantEvaluation's @JsonPropertyOrder that the writer never emits,
# because they carry no @JsonProperty and their accessors are not bean getters.
ABSENT = {"variantEffect", "nonCodingVariant", "whiteListed", "sampleGenotypes",
          "transcriptAnnotations", "contigId", "genomeAssembly"}


class ExomiserRoundTripFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.genes = [json.loads(line) for line in ROUNDTRIP.read_text().splitlines() if line.strip()]
        cls.strict = json.loads(STRICT.read_text())

    def variants(self):
        for gene in self.genes:
            for variant in gene["variantEvaluations"]:
                yield gene["geneSymbol"], variant

    def test_one_gene_object_per_line_with_nested_variants(self):
        self.assertEqual(len(self.genes), 6)
        for gene in self.genes:
            self.assertIn("geneSymbol", gene)
            self.assertIsInstance(gene["variantEvaluations"], list)
            self.assertTrue(gene["geneSymbol"].startswith("SYNG"))

    def test_writer_omits_fields_the_filter_mirror_would_need(self):
        seen = set()
        for _, variant in self.variants():
            seen |= set(variant)
        self.assertEqual(seen & ABSENT, set(), "writer now emits a field the design assumes absent")
        self.assertTrue(EMITTED <= seen, f"missing emitted fields: {sorted(EMITTED - seen)}")

    def test_pass_only_semantics_are_visible_in_filter_status(self):
        # SYNG4 has a single variant at REMM 0.90, below the baseline cutoff.
        statuses = {symbol: {v["filterStatus"] for v in gene["variantEvaluations"]}
                    for symbol, gene in ((g["geneSymbol"], g) for g in self.genes)}
        self.assertEqual(statuses["SYNG4"], {"FAILED"})
        for symbol in ("SYNG1", "SYNG2", "SYNG3", "SYNG5", "SYNG6"):
            self.assertEqual(statuses[symbol], {"PASSED"}, symbol)

    def test_remm_scores_survive_serialization_exactly(self):
        remm = {}
        for symbol, variant in self.variants():
            for score in variant.get("pathogenicityData", {}).get("pathogenicityScores", []):
                if score["source"] == "REMM":
                    remm[(symbol, variant["start"])] = score["score"]
        self.assertAlmostEqual(remm[("SYNG2", 200000)], 0.97, places=6)
        self.assertAlmostEqual(remm[("SYNG2", 210000)], 0.95, places=6)
        self.assertAlmostEqual(remm[("SYNG4", 400000)], 0.90, places=6)
        self.assertNotIn(("SYNG5", 500000), remm, "coding gene carries REVEL, not REMM")

    def test_direct_engine_answer_at_strict_cutoff(self):
        # Same six genes, rebuilt fresh, filtered at PATHOGENIC_THRESHOLD, annotated by the real engine.
        self.assertEqual(self.strict["SYNG1"], {"strict_survivors": 2, "modes": {"AUTOSOMAL_DOMINANT": 2, "AUTOSOMAL_RECESSIVE": 2}})
        self.assertEqual(self.strict["SYNG2"], {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}})
        self.assertEqual(self.strict["SYNG3"], {"strict_survivors": 1, "modes": {}})
        self.assertEqual(self.strict["SYNG4"], {"strict_survivors": 0, "modes": {}})
        self.assertEqual(self.strict["SYNG5"]["strict_survivors"], 1)
        self.assertEqual(self.strict["SYNG6"], {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}})

    def test_baseline_jsonl_modes_differ_from_strict_engine_answer_where_designed(self):
        # The JSONL carries baseline (0.914) modes per variant. The 1% SYNG3 survivor is
        # recessive-only at baseline (above the 0.1% dominant cutoff); its rare partner
        # carries both modes. Once the partner is gone, the strict answer has no mode.
        per_variant = {}
        for symbol, variant in self.variants():
            per_variant[(symbol, variant["start"])] = set(variant.get("compatibleInheritanceModes", []))
        self.assertEqual(per_variant[("SYNG1", 100000)], {"AUTOSOMAL_DOMINANT", "AUTOSOMAL_RECESSIVE"})
        self.assertEqual(per_variant[("SYNG3", 300000)], {"AUTOSOMAL_RECESSIVE"}, "1% survivor is recessive-only at baseline")
        self.assertEqual(per_variant[("SYNG3", 310000)], {"AUTOSOMAL_DOMINANT", "AUTOSOMAL_RECESSIVE"})
        self.assertEqual(set(self.strict["SYNG3"]["modes"]), set(), "and has no mode once the partner is gone")
        self.assertIn("AUTOSOMAL_RECESSIVE", per_variant[("SYNG2", 200000)])
        self.assertNotIn("AUTOSOMAL_RECESSIVE", self.strict["SYNG2"]["modes"])
        self.assertEqual(per_variant[("SYNG4", 400000)], set(), "failed variant carries no modes")


if __name__ == "__main__":
    unittest.main()
