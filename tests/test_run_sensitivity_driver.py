"""Tests for the private sensitivity run driver, exercised only on synthetic trees.

The driver never runs here against private data. These tests build a fake frozen run
directory (mode 0400 files, a freeze receipt with sha256 per output) and a fake install
layout, then check that the driver:

- refuses to start unless every precondition holds (hashes match the receipt, the
  output root is a sibling and never inside the frozen run, the tools exist);
- passes exactly the arguments docs/18 specifies to the two commands;
- writes its own receipt binding inputs, tool hashes and outputs;
- never modifies the frozen run (verified by hashing every frozen file before and after).

The Java step is stubbed by a tiny executable that copies canned outputs into place,
because the real engine cannot run without the pinned jar; the stub's arguments are
asserted exactly.
"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "scripts" / "run_sensitivity_remm963.py"
FIXTURES = ROOT / "tests" / "fixtures"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict:
    return {str(p.relative_to(root)): (sha256(p), oct(p.stat().st_mode & 0o777)) for p in sorted(root.rglob("*")) if p.is_file()}


class SyntheticPrivateTree:
    """A fake encrypted-volume layout with one frozen run and a pinned toolchain."""

    def __init__(self, base: Path):
        self.base = base
        self.run = base / "analysis" / "noncoding" / "2026-09-02" / "lane2-run-1"
        results = self.run / "results"
        results.mkdir(parents=True)
        (results / "lane2-genome.variants.tsv").write_bytes((FIXTURES / "exomiser_roundtrip_variants.tsv").read_bytes())
        (results / "lane2-genome.jsonl").write_bytes((FIXTURES / "exomiser_roundtrip_output.jsonl").read_bytes())
        outputs = {}
        for p in sorted(results.iterdir()):
            outputs[p.name] = {"bytes": p.stat().st_size, "mode": "0400", "sha256": sha256(p)}
            p.chmod(0o400)
        (self.run / "lane2-run-1-receipt.json").write_text(json.dumps({"kind": "noncoding-lane2-run-1", "state": "completed", "outputs": outputs}, sort_keys=True))
        (self.run / "lane2-run-1-receipt.json").chmod(0o400)
        results.chmod(0o500)
        self.run.chmod(0o500)
        # Fake toolchain: a "java" that is really a stub, and a jar directory with one file.
        self.java = base / "references" / "installed" / "openjdk" / "bin" / "java"
        self.java.parent.mkdir(parents=True)
        self.lib = base / "references" / "installed" / "exomiser-cli" / "exomiser-cli-15.1.0" / "lib"
        self.lib.mkdir(parents=True)
        (self.lib / "exomiser-core-15.1.0.jar").write_bytes(b"not a real jar, hashed only")
        self.write_java_stub(ok=True)

    def write_java_stub(self, ok: bool):
        # Records its argv, then writes canned Recompute outputs where the driver asked.
        detail = FIXTURES / "exomiser_recompute_detail.json"
        summary = FIXTURES / "exomiser_recompute_from_tsv.json"
        body = f"""#!/bin/sh
printf '%s\\n' "$@" > "$(dirname "$0")/java-argv.txt"
{'' if ok else 'exit 7'}
# args: -cp <cp> Recompute <tsv> <proband> <summary> <detail>
cp {summary} "$6"
cp {detail} "$7"
echo '{{"tsv_rows":16}}'
"""
        self.java.write_text(body)
        self.java.chmod(0o755)

    def unfreeze_all(self):
        for p in self.run.rglob("*"):
            p.chmod(0o700 if p.is_dir() else 0o600)
        self.run.chmod(0o700)


def run_driver(args, env_extra=None):
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(DRIVER), *args], capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)


class SensitivityDriverTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = SyntheticPrivateTree(Path(self._tmp.name))
        self.before = tree_hashes(self.tree.run)
        self.proband = "SYNTHETIC_PROBAND"
        self.out = self.tree.run.parent / "lane2-run-1-sensitivity-remm963"

    def tearDown(self):
        self.tree.unfreeze_all()
        self._tmp.cleanup()

    def base_args(self, out=None):
        return ["--frozen-run", str(self.tree.run), "--output-root", str(out or self.out), "--proband", self.proband,
                "--java", str(self.tree.java), "--exomiser-lib", str(self.tree.lib), "--recompute-class-dir", str(FIXTURES)]

    def test_happy_path_writes_sibling_and_leaves_frozen_run_byte_identical(self):
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        status = json.loads(completed.stdout)
        self.assertEqual(status["state"], "completed")
        self.assertEqual(tree_hashes(self.tree.run), self.before, "frozen run must be byte-identical and mode-identical")
        self.assertTrue(self.out.is_dir())
        self.assertFalse(self.out.is_relative_to(self.tree.run))
        receipt = json.loads((self.out / "sensitivity-receipt.json").read_text())
        self.assertEqual(receipt["inputs"]["variants_tsv_sha256"], self.before["results/lane2-genome.variants.tsv"][0])
        self.assertEqual(receipt["inputs"]["jsonl_sha256"], self.before["results/lane2-genome.jsonl"][0])
        self.assertEqual(receipt["inputs"]["freeze_receipt_sha256"], self.before["lane2-run-1-receipt.json"][0])
        self.assertEqual(receipt["tools"]["exomiser_core_jar_sha256"], sha256(self.tree.lib / "exomiser-core-15.1.0.jar"))
        self.assertEqual(receipt["cutoff"], 0.963)
        self.assertEqual(receipt["partition"]["variant_partition"], {"retained": 5, "removed_by_cutoff": 3, "removed_by_inheritance": 1})
        for name in ("recompute-summary.json", "recompute-detail.json", "partition-receipt.json"):
            path = self.out / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400, name)
            self.assertEqual(receipt["outputs"][name], sha256(path), name)
        self.assertNotIn("sensitivity-receipt.json", receipt["outputs"], "a file cannot carry its own hash")
        self.assertEqual(stat.S_IMODE((self.out / "sensitivity-receipt.json").stat().st_mode), 0o400)
        self.assertEqual(status["sensitivity_receipt_sha256"], sha256(self.out / "sensitivity-receipt.json"))
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o500)
        partition_text = (self.out / "partition-receipt.json").read_text()
        self.assertNotIn(self.proband, partition_text, "proband name stays out of the count receipt")
        self.assertNotIn("retained_genes_with_changed_mode_set\"", partition_text, "gene symbols stay out of the count receipt")
        self.assertNotIn("SYNG", partition_text)
        self.assertNotIn("SYNG", (self.out / "sensitivity-receipt.json").read_text())

    def test_java_invocation_matches_the_design(self):
        run_driver(self.base_args())
        argv = (self.tree.java.parent / "java-argv.txt").read_text().splitlines()
        self.assertEqual(argv[0], "-cp")
        self.assertIn(str(FIXTURES), argv[1])
        self.assertIn(str(self.tree.lib), argv[1])
        self.assertEqual(argv[2], "Recompute")
        self.assertEqual(argv[3], str(self.tree.run / "results" / "lane2-genome.variants.tsv"))
        self.assertEqual(argv[4], self.proband)
        self.assertEqual(argv[5], str(self.out / "recompute-summary.json"))
        self.assertEqual(argv[6], str(self.out / "recompute-detail.json"))

    def test_refuses_output_inside_frozen_run(self):
        for inside in (self.tree.run / "sensitivity-remm963", self.tree.run / "results" / "x-sensitivity-remm963"):
            completed = run_driver(self.base_args(out=inside))
            self.assertEqual(completed.returncode, 2, inside)
            self.assertEqual(json.loads(completed.stderr)["error"], "output root must not be inside the frozen run", inside)
            self.assertEqual(tree_hashes(self.tree.run), self.before)
        # The frozen run itself is refused earlier, as an existing path.
        completed = run_driver(self.base_args(out=self.tree.run))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "output root already exists")
        self.assertEqual(tree_hashes(self.tree.run), self.before)

    def test_refuses_output_that_is_not_a_sibling(self):
        completed = run_driver(self.base_args(out=self.tree.base / "elsewhere-sensitivity-remm963"))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "output root must be a sibling of the frozen run")

    def test_refuses_output_without_the_sensitivity_suffix(self):
        completed = run_driver(self.base_args(out=self.tree.run.parent / "lane2-run-1-other"))
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "output root name must carry the sensitivity suffix")

    def test_refuses_existing_output_root(self):
        self.out.mkdir()
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "output root already exists")
        self.assertEqual(list(self.out.iterdir()), [], "nothing written into a pre-existing output root")
        self.assertTrue(self.out.is_dir(), "a pre-existing directory is never removed")

    def test_refuses_when_tsv_hash_disagrees_with_freeze_receipt(self):
        self.tree.unfreeze_all()
        tsv = self.tree.run / "results" / "lane2-genome.variants.tsv"
        tsv.write_bytes(tsv.read_bytes() + b"\n")
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertIn("failed_closed", completed.stderr)
        self.assertFalse(self.out.exists(), "no output root created when a precondition fails")

    def test_refuses_when_freeze_receipt_missing_or_not_completed(self):
        self.tree.unfreeze_all()
        receipt = self.tree.run / "lane2-run-1-receipt.json"
        data = json.loads(receipt.read_text()); data["state"] = "failed"
        receipt.write_text(json.dumps(data))
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        receipt.unlink()
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_refuses_symlinked_frozen_input(self):
        self.tree.unfreeze_all()
        tsv = self.tree.run / "results" / "lane2-genome.variants.tsv"
        real = self.tree.base / "elsewhere.tsv"
        real.write_bytes(tsv.read_bytes())
        tsv.unlink(); tsv.symlink_to(real)
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_java_failure_leaves_no_partial_output_claiming_completion(self):
        self.tree.write_java_stub(ok=False)
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "recomputation did not complete")
        self.assertFalse(self.out.exists(), "a failed run leaves no output root behind")
        self.assertEqual(tree_hashes(self.tree.run), self.before)

    def test_java_nonzero_exit_is_refused_even_when_it_wrote_outputs(self):
        # The stub writes both files and then exits 7. The return code alone must refuse.
        body = self.tree.java.read_text().replace("exit 7\n", "").rstrip("\n") + "\nexit 7\n"
        self.tree.java.write_text(body)
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "recomputation did not complete")
        self.assertFalse(self.out.exists())

    def test_failed_run_removes_its_partial_output_root(self):
        # Force a failure after the output root exists: the stub writes a detail file whose
        # cutoff is wrong, so the recomputation completes but the cutoff pin refuses it.
        detail = json.loads((FIXTURES / "exomiser_recompute_detail.json").read_text())
        detail["cutoff"] = 0.914
        bad = self.tree.base / "bad-detail.json"
        bad.write_text(json.dumps(detail))
        self.tree.java.write_text(self.tree.java.read_text().replace(str(FIXTURES / "exomiser_recompute_detail.json"), str(bad)))
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "recomputation cutoff is not the designed cutoff")
        self.assertFalse(self.out.exists(), "partial output root removed on failure")

    def test_missing_java_or_jar_fails_before_touching_anything(self):
        completed = run_driver(self.base_args()[:-6] + ["--java", str(self.tree.base / "nope"), "--exomiser-lib", str(self.tree.lib), "--recompute-class-dir", str(FIXTURES)])
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "java executable not found")
        self.assertFalse(self.out.exists())
        (self.tree.lib / "exomiser-core-15.1.0.jar").unlink()
        completed = run_driver(self.base_args())
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["error"], "exomiser core jar not found")
        self.assertFalse(self.out.exists())

    def test_stderr_is_one_bounded_line_without_paths(self):
        completed = run_driver(self.base_args(out=self.tree.run / "inside"))
        self.assertEqual(completed.stderr.count("\n"), 1)
        self.assertNotIn(str(self.tree.base), completed.stderr)
        self.assertNotIn(self.proband, completed.stderr)


if __name__ == "__main__":
    unittest.main()
