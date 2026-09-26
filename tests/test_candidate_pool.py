"""Steps 1 to 3 of docs/22 on a synthetic private tree. No case data.

The fixture is a miniature of the frozen ``review-work`` layout on the
encrypted host: two lanes of ``replay.jsonl`` and ``replay.variants.tsv``,
one ``input.vcf``, ``diagnostic-replay.json`` observations for the declared
regions, ``recurrent-genes.json`` and ``candidate-review.json``. Every value
is invented. Gene names are ``SYN1``..``SYN4``.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_candidate_pool as bcp  # noqa: E402


def _tsv(rows):
    fields = ["#RANK", "GENE_SYMBOL", "ENTREZ_GENE_ID", "MOI", "CONTIG", "START", "END", "REF", "ALT", "FILTER", "GENOTYPE"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, delimiter="\t", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fields})
    return buf.getvalue()


# Alleles. a1,a2 in SYN1 pass both lanes (Tier A, AR in both). b1 in SYN2
# passes coding only, sits in a declared region, AR in coding (Tier B). c1 in
# SYN3 fails both lanes; SYN3 is a recurrent gene (Tier C). d1 in SYN4 fails
# both, in a region, no other evidence (Tier D). q1 in SYN4 is in a region and
# carries a malformed AD field (quality drop). SYN2's region also holds r1,
# whose lanes disagree on the gene (coding says SYN2, noncoding says SYN3).
A1 = ("1", 1000, "A", "G"); A2 = ("1", 2000, "C", "T"); B1 = ("2", 3000, "G", "A")
C1 = ("3", 4000, "T", "C"); D1 = ("4", 5000, "A", "C"); Q1 = ("4", 6000, "G", "T"); R1 = ("2", 3500, "C", "G")

LANES = {
    "coding": {
        A1: ("SYN1", "PASSED", ["AD", "AR"], 1), A2: ("SYN1", "PASSED", ["AR"], 1),
        B1: ("SYN2", "PASSED", ["AR"], 2), C1: ("SYN3", "FAILED", ["ANY"], 99),
        D1: ("SYN4", "FAILED", ["ANY"], 99), Q1: ("SYN4", "FAILED", ["ANY"], 99), R1: ("SYN2", "FAILED", ["ANY"], 99),
    },
    "noncoding": {
        A1: ("SYN1", "PASSED", ["AR"], 3), A2: ("SYN1", "PASSED", ["AD", "AR"], 3),
        B1: ("SYN2", "FAILED", ["ANY"], 99), C1: ("SYN3", "FAILED", ["ANY"], 99),
        D1: ("SYN4", "FAILED", ["ANY"], 99), Q1: ("SYN4", "FAILED", ["ANY"], 99), R1: ("SYN3", "FAILED", ["ANY"], 99),
    },
}
REGION_ALLELES = {B1: ["SYN2"], R1: ["SYN2"], D1: ["SYN4"], Q1: ["SYN4"]}
FMT = {Q1: "0/1:30:20,5,1"}  # AD has three values for one alt: audit flags it


def write_fixture(root: Path) -> None:
    replay = root / "diagnostic-replay-20260909" / "replay-2"
    for lane, table in LANES.items():
        d = replay / lane / "results"; d.mkdir(parents=True)
        genes = {}
        for k, (sym, status, mois, rank) in table.items():
            genes.setdefault(sym, []).append((k, status, mois, rank))
        with open(replay / lane / "results" / "replay.jsonl", "w") as fh:
            for sym, items in genes.items():
                fh.write(json.dumps({
                    "geneSymbol": sym, "geneIdentifier": {"entrezId": "1"},
                    "variantEvaluations": [
                        {"contigName": k[0], "start": k[1], "ref": k[2], "alt": k[3], "filterStatus": status}
                        for k, status, _, _ in items],
                    "geneScores": [],
                }) + "\n")
        rows = []
        for k, (sym, status, mois, rank) in table.items():
            for moi in mois:
                rows.append({"#RANK": str(rank), "GENE_SYMBOL": sym, "ENTREZ_GENE_ID": "1", "MOI": moi,
                             "CONTIG": k[0], "START": str(k[1]), "END": str(k[1]), "REF": k[2], "ALT": k[3],
                             "FILTER": "PASS" if status == "PASSED" else "freq", "GENOTYPE": "0/1"})
        (d / "replay.variants.tsv").write_text(_tsv(rows))
        vcf = ["##fileformat=VCFv4.2", "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1"]
        for k in sorted(table):
            vcf.append("\t".join([k[0], str(k[1]), ".", k[2], k[3], "50", "PASS", ".", "GT:GQ:AD", FMT.get(k, "0/1:30:20,5")]))
        (replay / lane / "input.vcf").write_text("\n".join(vcf) + "\n")
    obs = [{"allele_key": list(k), "regional_gene_symbols": syms, "called_in_stored_genotype": True, "state": "observed"}
           for k, syms in REGION_ALLELES.items()]
    (replay / "diagnostic-replay.json").write_text(json.dumps({
        "lanes": {"coding": {"observations": obs}, "noncoding": {"observations": obs}},
        "reviewed_code_and_inputs": {"audit_core.py": bcp.sha256_file(root / "audit_core.py")},
    }))
    (replay / "receipt.json").write_text("{}\n")
    rec = root / "recurrent-genes-20260911" / "recurrent-1"; rec.mkdir(parents=True)
    (rec / "recurrent-genes.json").write_text(json.dumps({"recurrent_top30_symbols": ["SYN3"]}))
    cr = root / "candidate-review-20260906" / "candidate-review"; cr.mkdir(parents=True)
    (cr / "candidate-review.json").write_text(json.dumps({
        "inheritance_review": ["SYN1"],
        "genes": [{"symbol": "SYN1", "sensitivity_status": "retained",
                   "coding_variants": [{"CONTIG": A1[0], "START": str(A1[1]), "REF": A1[2], "ALT": A1[3]}],
                   "noncoding_variants": [],
                   "noncoding_sensitivity": {"baseline_modes": ["AUTOSOMAL_DOMINANT", "AUTOSOMAL_RECESSIVE"],
                                             "strict_modes": ["AUTOSOMAL_RECESSIVE"], "strict_survivors": 1,
                                             "variants": {"1|1000|A|G": {"baseline_modes": ["AUTOSOMAL_DOMINANT", "AUTOSOMAL_RECESSIVE"],
                                                                         "strict_modes": ["AUTOSOMAL_RECESSIVE"], "stage1_pass": True}}}}],
    }))


AUDIT_CORE = '''
import math, re
def recorded_quality_issues(qual, fmt, alt_count):
    issues = []
    value = fmt.get("AD")
    if value not in (None, "", "."):
        parts = value.split(",")
        if len(parts) != alt_count + 1: issues.append("AD_allele_count_mismatch")
    return issues
'''


class CandidatePoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "review-work"
        self.root.mkdir()
        (self.root / "audit_core.py").write_text(AUDIT_CORE)
        write_fixture(self.root)
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def run_pool(self):
        return bcp.build(self.root, self.out, self.root / "audit_core.py")

    def test_union_counts_every_source_before_exclusion(self):
        s = self.run_pool()["summary"]
        self.assertEqual(s["step1"]["pool_before_exclusion"], 7)
        self.assertEqual(s["step1"]["sources"]["passed_either_lane"], 3)
        self.assertEqual(s["step1"]["sources"]["region_called"], 4)
        # c1, plus r1: its noncoding lane assigns r1 to the recurrent gene
        self.assertEqual(s["step1"]["sources"]["recurrent_gene"], 2)
        self.assertEqual(s["step1"]["sources"]["dossier_inheritance_review"], 1)

    def test_quality_drop_uses_the_audit_module_and_is_counted(self):
        s = self.run_pool()["summary"]
        self.assertEqual(s["step2"]["dropped"], {"quality": 1, "representation": 0, "gene_assignment": 0})
        self.assertEqual(s["step2"]["pool_after_exclusion"], 6)

    def test_tiers(self):
        s = self.run_pool()["summary"]
        self.assertEqual(s["step3"]["tier_sizes"], {"A": 2, "B": 1, "C": 1, "D": 2})

    def test_pool_rows_carry_candidate_fields_with_chr_prefixed_contigs(self):
        r = self.run_pool()
        rows = {tuple(c["variant"]): c for c in r["pool"]}
        self.assertEqual(rows[("chr1", 1000, "A", "G")]["tier"], "A")
        self.assertTrue(rows[("chr1", 1000, "A", "G")]["both_lanes"])
        self.assertEqual(rows[("chr1", 1000, "A", "G")]["native_rank"], 3)  # stricter lane
        self.assertTrue(rows[("chr1", 1000, "A", "G")]["recessive_annotation"])
        self.assertEqual(rows[("chr2", 3000, "G", "A")]["native_rank"], 2)  # one lane passed
        self.assertFalse(rows[("chr2", 3000, "G", "A")]["both_lanes"])
        # lanes disagree on r1's gene; it passed neither; the region gene wins
        self.assertEqual(rows[("chr2", 3500, "C", "G")]["gene"], "SYN2")

    def test_summary_carries_no_symbols_or_coordinates(self):
        r = self.run_pool()
        text = json.dumps(r["summary"])
        for token in ("SYN1", "SYN2", "SYN3", "SYN4", "1000", "3500"):
            self.assertNotIn(token, text)

    def test_audit_module_hash_must_match_the_replay_pin(self):
        (self.root / "audit_core.py").write_text(AUDIT_CORE + "\n# changed\n")
        with self.assertRaises(bcp.PoolError):
            self.run_pool()

    def test_passed_both_lanes_with_disagreeing_genes_is_an_error(self):
        lane = self.root / "diagnostic-replay-20260909" / "replay-2" / "noncoding" / "results" / "replay.jsonl"
        text = lane.read_text().replace('"geneSymbol": "SYN1"', '"geneSymbol": "SYNX"')
        lane.write_text(text)
        with self.assertRaises(bcp.PoolError):
            self.run_pool()


if __name__ == "__main__":
    unittest.main()
