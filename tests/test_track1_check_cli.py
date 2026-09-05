"""CLI contract for ``track1-check``: one JSON status line, fail closed with no echo.

Every file here is synthetic. The refusal path must never print a submitted row,
a chromosome, or a position; a candidate file for the real case would carry the
lane's variant coordinates, and stderr may end up in a log.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = "proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes\n"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "mva_prioritizer.cli", "track1-check", *args],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )


class Track1CheckCliTests(unittest.TestCase):
    def write(self, directory, name, text):
        path = Path(directory) / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_valid_file_emits_one_content_free_status_line(self):
        text = HEADER + (
            "PROBAND01,chr2,1000,A,T,chr15,2000,G,C,0.9,primary,\n"
            "PROBAND01,chr7,3000,C,T,,,,,0.3,secondary,unrelated\n"
        )
        with tempfile.TemporaryDirectory() as scratch:
            path = self.write(scratch, "candidate.csv", text)
            completed = run_cli("--submission", str(path))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        lines = completed.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        status = json.loads(lines[0])
        self.assertEqual(
            status,
            {
                "external_actions": 0,
                "pair_rows": 1,
                "row_count": 2,
                "secondary_rows": 1,
                "state": "valid",
                "unique_variants": 3,
            },
        )
        for token in ("chr2", "chr15", "chr7", "1000", "2000", "3000"):
            self.assertNotIn(token, completed.stdout)

    def test_synthetic_truth_scores_the_file_with_the_mirror(self):
        text = HEADER + "PROBAND01,chr2,1000,A,T,chr15,2000,G,C,0.9,primary,\n"
        with tempfile.TemporaryDirectory() as scratch:
            path = self.write(scratch, "candidate.csv", text)
            completed = run_cli(
                "--submission", str(path),
                "--synthetic-truth", '[["chr2",1000,"A","T"],["chr15",2000,"G","C"]]',
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        status = json.loads(completed.stdout)
        self.assertEqual(
            status["synthetic_score"],
            {"f_max": 1.0, "f_max_threshold": 0.9, "full_match_rank": 1, "partial_match_rank": None, "rank_points": 100.0},
        )

    def test_refused_file_exits_2_with_one_bounded_line_and_no_echo(self):
        canary_position = "987654321"
        text = HEADER + f"PROBAND01,7,{canary_position},C,T,,,,,0.9,primary,\n"  # no chr prefix: would score zero
        with tempfile.TemporaryDirectory() as scratch:
            path = self.write(scratch, "candidate.csv", text)
            completed = run_cli("--submission", str(path))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(completed.stderr.splitlines(), ['{"error":"input_rejected","state":"failed_closed"}'])
        self.assertNotIn(canary_position, completed.stderr)

    def test_eleven_rows_and_bad_truth_shape_are_refused(self):
        rows = "".join(f"PROBAND01,chr1,{i},A,C,,,,,0.{99 - i},primary,\n" for i in range(1, 12))
        with tempfile.TemporaryDirectory() as scratch:
            path = self.write(scratch, "eleven.csv", HEADER + rows)
            self.assertEqual(run_cli("--submission", str(path)).returncode, 2)
            good = self.write(scratch, "one.csv", HEADER + "PROBAND01,chr1,1,A,C,,,,,0.9,primary,\n")
            self.assertEqual(run_cli("--submission", str(good), "--synthetic-truth", "[]").returncode, 2)
            self.assertEqual(run_cli("--submission", str(good), "--synthetic-truth", '{"a":1}').returncode, 2)

    def test_symlinked_submission_is_refused_at_open(self):
        text = HEADER + "PROBAND01,chr1,1,A,C,,,,,0.9,primary,\n"
        with tempfile.TemporaryDirectory() as scratch:
            real = self.write(scratch, "real.csv", text)
            link = Path(scratch) / "link.csv"
            os.symlink(real, link)
            completed = run_cli("--submission", str(link))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")

    def test_oversized_submission_is_refused(self):
        text = HEADER + "PROBAND01,chr1,1,A,C,,,,,0.9,primary," + ("x" * (1024 * 1024)) + "\n"
        with tempfile.TemporaryDirectory() as scratch:
            path = self.write(scratch, "big.csv", text)
            completed = run_cli("--submission", str(path))
        self.assertEqual(completed.returncode, 2)

    def test_flags_relax_only_the_named_guard(self):
        tie = HEADER + "PROBAND01,chr1,1,A,C,,,,,0.5,primary,\nPROBAND01,chr1,2,A,C,,,,,0.5,primary,\n"
        with tempfile.TemporaryDirectory() as scratch:
            path = self.write(scratch, "tie.csv", tie)
            self.assertEqual(run_cli("--submission", str(path)).returncode, 2)
            self.assertEqual(run_cli("--submission", str(path), "--allow-unsorted").returncode, 2)
            self.assertEqual(run_cli("--submission", str(path), "--allow-ties").returncode, 0)


if __name__ == "__main__":
    unittest.main()
