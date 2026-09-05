"""Pin the TSV-driven two-stage recomputation against the direct engine answer.

Fixtures come from one execution of ``runtime/exomiser-probe-20260905/RoundTrip.java``
and ``Recompute.java`` on 2026-09-05 against the hash-verified exomiser-core-15.1.0.jar:

- ``exomiser_roundtrip_variants.tsv``: what the real ``TsvVariantResultsWriter`` wrote for
  the synthetic genes after the baseline (0.914) filter, inheritance analysis, and PASS_ONLY
  removal (failed variants dropped, empty genes dropped), the mode the frozen lane ran in.
- ``exomiser_recompute_from_tsv.json``: what ``Recompute`` produced by reading only that
  TSV, applying the filter mirror at 0.963, and asking the real ``InheritanceModeAnnotator``.
- ``exomiser_roundtrip_strict.json``: the direct engine answer at 0.963 for all six synthetic
  genes, built in memory without any serialization. It includes SYNG4, which PASS_ONLY removes
  before writing, so the recomputation can never see it.
- ``exomiser_recompute_mutations/``: nine mutated TSVs, the recomputation's output for each
  (or its failure), and ``manifest.json`` classifying each as changed, unchanged, or
  failed_closed. Every number docs/18 cites about the mutation sweep is recomputed here.

No private data: every row is synthetic (SYNG*, SYNTHETIC_PROBAND).
"""

import csv
import io
import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TSV = FIXTURES / "exomiser_roundtrip_variants.tsv"
JSONL = FIXTURES / "exomiser_roundtrip_output.jsonl"
RECOMPUTE = FIXTURES / "exomiser_recompute_from_tsv.json"
STRICT = FIXTURES / "exomiser_roundtrip_strict.json"
MUTATIONS = FIXTURES / "exomiser_recompute_mutations"

REQUIRED_COLUMNS = {"GENE_SYMBOL", "MOI", "WHITELIST_VARIANT", "CONTIG", "START", "END", "REF", "ALT",
                    "GENOTYPE", "FUNCTIONAL_CLASS", "ALL_FREQ", "ALL_PATH"}
MOI_ABBREVIATION = {"AD": "AUTOSOMAL_DOMINANT", "AR": "AUTOSOMAL_RECESSIVE", "XD": "X_DOMINANT",
                    "XR": "X_RECESSIVE", "MT": "MITOCHONDRIAL", "ANY": "ANY"}


def read_tsv(text):
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


class ExomiserTsvRecomputeFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_tsv(TSV.read_text())
        cls.genes = [json.loads(line) for line in JSONL.read_text().splitlines() if line.strip()]
        cls.recompute = json.loads(RECOMPUTE.read_text())
        cls.strict = json.loads(STRICT.read_text())
        cls.manifest = json.loads((MUTATIONS / "manifest.json").read_text())

    def test_tsv_carries_every_column_the_design_reads(self):
        self.assertTrue(REQUIRED_COLUMNS <= set(self.rows[0]), sorted(REQUIRED_COLUMNS - set(self.rows[0])))
        self.assertEqual(self.rows[0]["#RANK"], "1")

    def test_pass_only_drops_the_failed_gene_before_writing(self):
        tsv_genes = {row["GENE_SYMBOL"] for row in self.rows}
        jsonl_genes = {gene["geneSymbol"] for gene in self.genes}
        self.assertEqual(tsv_genes, {"SYNG1", "SYNG2", "SYNG3", "SYNG5", "SYNG6"})
        self.assertEqual(jsonl_genes, tsv_genes)
        self.assertNotIn("SYNG4", tsv_genes, "its only variant failed at 0.914; PASS_ONLY removes it")
        self.assertIn("SYNG4", self.strict, "the direct in-memory answer still covers it")
        self.assertEqual(self.strict["SYNG4"], {"strict_survivors": 0, "modes": {}})
        for gene in self.genes:
            for variant in gene["variantEvaluations"]:
                self.assertEqual(variant["filterStatus"], "PASSED")

    def test_tsv_row_model_is_exactly_one_row_per_variant_per_mode(self):
        per_row = Counter((r["GENE_SYMBOL"], r["CONTIG"], r["START"], r["REF"], r["ALT"], r["MOI"]) for r in self.rows)
        self.assertEqual(len(self.rows), 16)
        self.assertEqual(max(per_row.values()), 1, f"duplicate rows: {[k for k, c in per_row.items() if c > 1]}")
        modes = defaultdict(set)
        for r in self.rows:
            modes[(r["GENE_SYMBOL"], r["CONTIG"], r["START"], r["REF"], r["ALT"])].add(r["MOI"])
        self.assertEqual(len(modes), 9, "nine unique synthetic variants after PASS_ONLY")
        self.assertEqual(sum(len(m) for m in modes.values()), 16, "row count equals the sum of per-variant mode counts")
        self.assertEqual(modes[("SYNG1", "1", "100000", "A", "T")], {"AD", "AR"})
        self.assertEqual(modes[("SYNG3", "1", "300000", "A", "T")], {"AR"}, "1% survivor is recessive-only at baseline")
        self.assertEqual(modes[("SYNG5", "1", "500000", "G", "C")], {"AD"})

    def test_every_tsv_moi_appears_in_the_matching_jsonl_variant(self):
        # The consistency check docs/18 requires before either stage runs.
        jsonl_modes = {(g["geneSymbol"], str(v["start"]), v["ref"], v["alt"]): set(v.get("compatibleInheritanceModes", []))
                       for g in self.genes for v in g["variantEvaluations"]}
        tsv_keys = {(r["GENE_SYMBOL"], r["START"], r["REF"], r["ALT"]) for r in self.rows}
        self.assertEqual(tsv_keys, set(jsonl_modes))
        for r in self.rows:
            key = (r["GENE_SYMBOL"], r["START"], r["REF"], r["ALT"])
            self.assertIn(MOI_ABBREVIATION[r["MOI"]], jsonl_modes[key], key)

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
        self.assertEqual(set(self.recompute), set(self.strict) - {"SYNG4"})
        for gene, answer in self.recompute.items():
            self.assertEqual(answer, self.strict[gene], gene)

    def test_recomputation_outcomes_the_design_depends_on(self):
        self.assertEqual(self.recompute["SYNG1"], {"strict_survivors": 2, "modes": {"AUTOSOMAL_DOMINANT": 2, "AUTOSOMAL_RECESSIVE": 2}})
        self.assertEqual(self.recompute["SYNG2"], {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}}, "partner lost, dominant survivor stays")
        self.assertEqual(self.recompute["SYNG3"], {"strict_survivors": 1, "modes": {}}, "partner lost, 1% survivor has no mode")
        self.assertEqual(self.recompute["SYNG5"]["strict_survivors"], 1, "coding variant passes under NON_CODING target")
        self.assertEqual(self.recompute["SYNG6"], {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}})

    def test_mutation_sweep_breakdown_is_recomputed_from_files(self):
        self.assertEqual(len(self.manifest), 9)
        self.assertEqual(Counter(m["status"] for m in self.manifest), {"changed": 6, "unchanged": 1, "failed_closed": 2})
        by_name = {m["name"]: m for m in self.manifest}
        self.assertEqual(by_name["SYNG6_survivor_just_above"]["status"], "unchanged")
        self.assertEqual({n for n, m in by_name.items() if m["status"] == "failed_closed"}, {"drop_GENOTYPE_column", "unknown_SO_term"})
        baseline = self.recompute
        for m in self.manifest:
            mutated_tsv = MUTATIONS / m["input"]
            self.assertTrue(mutated_tsv.is_file(), m["input"])
            self.assertNotEqual(mutated_tsv.read_text(), TSV.read_text(), "each mutation must differ from the baseline TSV")
            if m["status"] == "failed_closed":
                self.assertIsNone(m["output"])
                self.assertFalse((MUTATIONS / f"{m['name']}.json").exists(), "a failed-closed run must write no output")
                self.assertIn("Exception", (MUTATIONS / f"{m['name']}.stderr.txt").read_text())
                continue
            result = json.loads((MUTATIONS / m["output"]).read_text())
            observed_diff = {g: result.get(g) for g in baseline if result.get(g) != baseline[g]}
            self.assertEqual(set(observed_diff), set(m["diff"]), m["name"])
            for gene, entry in m["diff"].items():
                self.assertEqual(entry["baseline_strict"], baseline[gene], m["name"])
                self.assertEqual(entry["mutated"], result[gene], m["name"])
            self.assertEqual(m["status"], "changed" if observed_diff else "unchanged", m["name"])

    def test_specific_mutations_move_in_the_direction_the_engine_predicts(self):
        by_name = {m["name"]: m for m in self.manifest}
        self.assertEqual(by_name["raise_SYNG2_partner_remm"]["diff"]["SYNG2"]["mutated"],
                         {"strict_survivors": 2, "modes": {"AUTOSOMAL_DOMINANT": 2, "AUTOSOMAL_RECESSIVE": 2}})
        self.assertEqual(by_name["lower_SYNG3_survivor_freq"]["diff"]["SYNG3"]["mutated"],
                         {"strict_survivors": 1, "modes": {"AUTOSOMAL_DOMINANT": 1}})
        self.assertEqual(by_name["SYNG6_survivor_at_exact_cutoff"]["diff"]["SYNG6"]["mutated"],
                         {"strict_survivors": 0, "modes": {}}, "exactly 0.963 fails the strict comparison")
        self.assertEqual(by_name["whitelist_SYNG2_partner"]["diff"]["SYNG2"]["mutated"]["strict_survivors"], 2)
        self.assertEqual(by_name["SYNG5_becomes_noncoding"]["diff"]["SYNG5"]["mutated"], {"strict_survivors": 0, "modes": {}})
        homalt = by_name["SYNG1_homalt"]["diff"]["SYNG1"]["mutated"]
        self.assertNotIn("AUTOSOMAL_DOMINANT", homalt["modes"], "homozygous alt in a single proband is recessive-only")


if __name__ == "__main__":
    unittest.main()
