"""Synthetic contracts for the Steps 4 to 7 runner and Amendment K."""
import csv
import io
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mva_prioritizer.candidate_selection import Candidate, build_submission_csv, order_rows, select_rows
from tests.test_candidate_pool import AUDIT_CORE, write_fixture
from scripts import build_candidate_pool

ROOT = Path(__file__).resolve().parents[1]


def candidate(pos=1000, tier="A", gene="SYN1", recessive=False):
    return Candidate(("chr1", pos, "A", "G"), gene, tier, False, 5, recessive)


def entry(chrom="1", pos=1000, confidence="high"):
    return {"gene": "SYN1", "transcript": "SYN_TX", "hgvs_c": "c.1A>G",
            "grch38": {"chrom": chrom, "pos": pos, "ref": "A", "alt": "G"},
            "mechanism": "synthetic", "confidence": confidence,
            "citations": ["https://example.org/synthetic"]}


class TierKTest(unittest.TestCase):
    def test_k_outranks_a_in_evidence_sort(self):
        rows = order_rows([candidate(tier="A"), candidate(9000, "K", "SYN2")])
        self.assertEqual([r.tier for r in rows], ["K", "A"])

    def test_k_pairs_with_a_b_k_without_recessive_annotation(self):
        for tier in ("A", "B", "K"):
            with self.subTest(tier=tier):
                rows = order_rows([candidate(tier="K"), candidate(2000, tier)])
                pairs = [r for r in rows if r.is_pair]
                self.assertEqual(len(pairs), 1)
                self.assertEqual(pairs[0].tier, "K")

    def test_k_never_pairs_with_c_d_or_another_gene(self):
        for tier, gene in (("C", "SYN1"), ("D", "SYN1"), ("A", "SYN2")):
            with self.subTest(tier=tier, gene=gene):
                rows = order_rows([candidate(tier="K", recessive=True), candidate(2000, tier, gene, True)])
                self.assertFalse(any(r.is_pair for r in rows))

    def test_k_does_not_enable_unannotated_a_b_pair(self):
        rows = order_rows([candidate(tier="K"), candidate(2000), candidate(3000, "B")])
        pairs = [r for r in rows if r.is_pair]
        self.assertEqual(len(pairs), 2)
        self.assertTrue(all(candidate().variant in r.variants for r in pairs))


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture = self.root / "fixture"
        fixture.mkdir()
        (fixture / "audit_core.py").write_text(AUDIT_CORE)
        write_fixture(fixture)
        build_candidate_pool.build(fixture, self.root / "pool", fixture / "audit_core.py")
        self.pool = self.root / "pool" / "pool.json"
        self.out = self.root / "run"

    def run_cli(self, *extra, out=None):
        return subprocess.run([sys.executable, str(ROOT / "scripts/select_candidates.py"),
                               "--pool", str(self.pool), "--out", str(out or self.out), *extra],
                              capture_output=True, text=True, timeout=20)

    def catalog(self, entries):
        path = self.root / "catalog.json"
        path.write_text(json.dumps(entries))
        return str(path)

    def test_end_to_end_and_counts_only(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(len(proc.stdout.splitlines()), 1)
        summary = json.loads((self.out / "selection-summary.json").read_text())
        self.assertEqual(json.loads(proc.stdout), summary)
        self.assertEqual(set(summary), {"rows", "pair_rows", "single_rows", "truncated_by_tier",
                                      "promotions", "demotions", "catalog_matches_by_tier", "catalog_null_entries",
                                      "catalog_direct_added"})
        self.assertEqual(summary["catalog_direct_added"], 0)
        self.assertEqual((summary["rows"], summary["pair_rows"], summary["single_rows"]), (7, 1, 6))
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o700)
        def counts_only(value):
            if isinstance(value, dict):
                for child in value.values():
                    counts_only(child)
            else:
                self.assertIs(type(value), int)
        counts_only(summary)
        for token in ("chr1", "1000", "SYN1", "c.1A>G", '"ref"', '"alt"'):
            self.assertNotIn(token, proc.stdout)
            self.assertNotIn(token, (self.out / "selection-summary.json").read_text())
        raw = json.loads(self.pool.read_text())
        fields = Candidate.__dataclass_fields__
        candidates = [Candidate(**{k: tuple(c[k]) if k == "variant" else c[k] for k in fields})
                      for c in raw["candidates"]]
        expected = build_submission_csv(select_rows(candidates)).encode()
        self.assertEqual((self.out / "submission.csv").read_bytes(), expected)

    def test_no_catalog_empty_and_zero_matches_are_byte_identical(self):
        self.assertEqual(self.run_cli().returncode, 0)
        expected = (self.out / "submission.csv").read_bytes()
        for i, entries in enumerate(([], [entry(pos=9000)], [entry(confidence="low")])):
            out = self.root / f"run-{i}"
            proc = self.run_cli("--catalog", self.catalog(entries), out=out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual((out / "submission.csv").read_bytes(), expected)

    def test_catalog_matches_count_original_tiers_and_ignore_null(self):
        null = entry(); null["grch38"] = None
        match = entry(chrom="4", pos=5000, confidence="medium")
        match["grch38"]["alt"] = "C"
        proc = self.run_cli("--catalog", self.catalog([match, null]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary["catalog_matches_by_tier"], {"A": 0, "B": 0, "C": 0, "D": 1})
        self.assertEqual(summary["catalog_null_entries"], 1)
        self.assertIn("tier=K", (self.out / "submission.csv").read_text().splitlines()[1])

    def test_contig_aliases_and_explicit_mitochondrial_confirmation(self):
        for i, chrom in enumerate(("1", "chr1", "M", "MT", "chrM", "chrMT")):
            raw = json.loads(self.pool.read_text())
            row = raw["candidates"][0]
            row["variant"] = ["chr1" if i < 2 else "chrM", 1000, "A", "G"]
            raw["candidates"] = [row]
            self.pool.write_text(json.dumps(raw))
            extra = [] if i < 2 else ["--mitochondrial-name", "chrMT"]
            out = self.root / f"alias-{i}"
            proc = self.run_cli("--catalog", self.catalog([entry(chrom=chrom)]), *extra, out=out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["catalog_matches_by_tier"]["A"], 1)
            if i >= 2:
                self.assertIn("chrMT", (out / "submission.csv").read_text())
        self.assert_refused(self.run_cli())

    def assert_refused(self, proc):
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "candidate selection refused\n")
        self.assertFalse(self.out.exists())

    def test_malformed_catalogs_are_refused(self):
        bad = [{}, {"entries": []}, [None]]
        for field in entry():
            item = entry(); del item[field]; bad.append([item])
            item = entry(); item[field] = 42; bad.append([item])
        for field, value in (("unknown", True), ("confidence", "HIGH"), ("confidence", "certain"),
                             ("citations", ["not a url"]), ("citations", [42]), ("gene", "")):
            item = entry(); item[field] = value; bad.append([item])
        for field, value in (("pos", True), ("pos", 1.5), ("pos", 0), ("pos", "1000"),
                             ("chrom", "chr99"), ("ref", "N"), ("alt", "g"), ("alt", ""),
                             ("alt", "A"), ("extra", 1)):
            item = entry(); item["grch38"][field] = value; bad.append([item])
        bad += [[entry(), entry(chrom="chr1")], [entry(confidence="low"), entry()]]
        for value in bad:
            with self.subTest(value=value):
                self.assert_refused(self.run_cli("--catalog", self.catalog(value)))

    def test_duplicate_json_keys_and_non_regular_inputs_refused(self):
        path = Path(self.catalog([]))
        path.write_text('[{"gene":"SYN1","gene":"SYN2"}]')
        self.assert_refused(self.run_cli("--catalog", str(path)))
        path.unlink(); path.symlink_to(self.pool)
        self.assert_refused(self.run_cli("--catalog", str(path)))
        self.assert_refused(self.run_cli("--catalog", str(self.root)))

    def test_malformed_pool_and_arguments_do_not_echo_input(self):
        for value in ({}, {"schema": "wrong"}, []):
            self.pool.write_text(json.dumps(value))
            self.assert_refused(self.run_cli())
        self.assert_refused(self.run_cli("--SYN1-secret", "chr1:1000"))

    def test_preexisting_out_directory_is_never_overwritten(self):
        self.out.mkdir()
        marker = self.out / "submission.csv"
        marker.write_text("unchanged")
        proc = self.run_cli()
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (2, "", "candidate selection refused\n"))
        self.assertEqual(marker.read_text(), "unchanged")
        self.assertEqual(list(self.out.iterdir()), [marker])

    def test_gate_disagreement_and_refusal_leave_no_output(self):
        from scripts import select_candidates as runner
        from mva_prioritizer.track1_submission import SubmissionError, parse_as_official
        def wrong_gate(text):
            result = parse_as_official(text)
            pid = next(iter(result))
            result[pid] = replace(result[pid], rows=result[pid].rows[:-1])
            return result
        for mock in (patch.object(runner, "parse_as_official", side_effect=wrong_gate),
                     patch.object(runner, "parse_submission", side_effect=SubmissionError("SYN1")),
                     # Review of 7b111e8: an over-limit CSV field raised csv.Error past the handler.
                     patch.object(runner, "parse_submission", side_effect=csv.Error("field larger than field limit"))):
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock, redirect_stdout(stdout), redirect_stderr(stderr):
                code = runner.main(["--pool", str(self.pool), "--out", str(self.out)])
            self.assertEqual((code, stdout.getvalue(), stderr.getvalue()), (2, "", "candidate selection refused\n"))
            self.assertFalse(self.out.exists())

    def extras(self, rows):
        path = self.root / "matches.json"
        path.write_text(json.dumps(rows))
        return str(path)

    def test_zero_direct_matches_preserve_part1_csv(self):
        catalog = self.catalog([entry()])
        self.assertEqual(self.run_cli("--catalog", catalog).returncode, 0)
        out = self.root / "empty-extras"
        proc = self.run_cli("--catalog", catalog, "--extra-candidates", self.extras([]), out=out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.out / "submission.csv").read_bytes(), (out / "submission.csv").read_bytes())
        self.assertEqual(json.loads(proc.stdout)["catalog_direct_added"], 0)

    def test_direct_pool_overlap_uses_pool_gene_rank_and_part1_tier(self):
        catalog = self.catalog([entry()])
        self.assertEqual(self.run_cli("--catalog", catalog).returncode, 0)
        for chrom in ("1", "chr1"):
            extra = {"variant": [chrom, 1000, "A", "G"], "gene": "OTHER_SYN", "genotype": "0/1"}
            out = self.root / chrom
            # Direct matches alone also establish the Part 1 K match.
            proc = self.run_cli("--extra-candidates", self.extras([extra]), out=out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual((self.out / "submission.csv").read_bytes(), (out / "submission.csv").read_bytes())
            summary = json.loads(proc.stdout)
            self.assertEqual(summary["catalog_direct_added"], 0)
            self.assertEqual(summary["catalog_matches_by_tier"]["A"], 1)

    def test_direct_added_k_pairs_with_same_gene_a_and_has_worst_rank(self):
        from scripts import select_candidates as runner
        pool = runner.load_pool(self.pool)
        extra = {"variant": ["1", 45000, "A", "G"], "gene": "SYN1", "genotype": "0/2"}
        path = self.extras([extra])
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(runner, "select_rows", wraps=select_rows) as select:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = runner.main(["--pool", str(self.pool), "--out", str(self.out),
                                    "--extra-candidates", path])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        candidates = select.call_args.args[0]
        added = [c for c in candidates if c.variant[1] == 45000]
        self.assertEqual(added, [Candidate(("chr1", 45000, "A", "G"), "SYN1", "K", False,
                                          max(c.native_rank for c in pool) + 1, False)])
        self.assertEqual(json.loads(stdout.getvalue())["catalog_direct_added"], 1)
        rows = select_rows(candidates).rows
        self.assertTrue(any(r.tier == "K" and r.variants == frozenset({added[0].variant,
                            ("chr1", 1000, "A", "G")}) for r in rows))

    def test_malformed_direct_inputs_refused(self):
        valid = {"variant": ["1", 45000, "A", "G"], "gene": "SYN1", "genotype": "0/1"}
        invalid = [None, {}, [None], [valid, valid]]
        for field, value in (("variant", ["1", True, "A", "G"]), ("gene", ""),
                             ("genotype", "./."), ("genotype", "0|0"), ("genotype", 1),
                             ("genotype", "0//1"), ("extra", True)):
            invalid.append([{**valid, field: value}])
        for rows in invalid:
            with self.subTest(rows=rows):
                self.assert_refused(self.run_cli("--extra-candidates", self.extras(rows)))


if __name__ == "__main__":
    unittest.main()
