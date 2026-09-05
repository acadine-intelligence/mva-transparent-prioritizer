"""Prove the partition guards are live by removing each one and watching a test fail.

Each entry names one guard in ``mva_prioritizer/sensitivity_partition.py`` or
``mva_prioritizer/bounded_input.py`` by an exact source snippet, the replacement
that disables it, and the test that must fail once it is disabled. Each mutant
runs in a fresh subprocess against a temporary copy of the package, so the files
on disk are never touched and no import caching can mask the change.

This is the auditable form of the claim in docs/18 that every implementation
mutation fails the tests. A reviewer can read this file and rerun it.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "mva_prioritizer"
TESTS = ROOT / "tests"
PARTITION = "sensitivity_partition.py"
BOUNDED = "bounded_input.py"

# (module file, exact snippet to disable, replacement, test id that must fail)
MUTATIONS = [
    (PARTITION, '        if survivors != declared_survivors:\n            raise', '        if False:\n            raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_variant_that_passed_stage1_but_gene_has_no_survivors"),
    (PARTITION, '            if not passed and strict:\n                raise', '            if False:\n                raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_strict_mode_on_a_variant_that_failed_stage1"),
    (PARTITION, '        if union_strict != gene_strict:\n            raise', '        if False:\n            raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_gene_strict_modes_that_disagree_with_its_variants"),
    (PARTITION, '    if unknown:\n        raise', '    if False:\n        raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_unknown_mode_name"),
    (PARTITION, '        if not isinstance(variants, dict) or not variants:', '        if not isinstance(variants, dict):',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_empty_gene_block"),
    (PARTITION, '            if key in seen_keys:\n                raise', '            if False:\n                raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_same_variant_key_in_two_genes"),
    (PARTITION, '            if not strict <= baseline:\n                raise', '            if False:\n                raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_strict_mode_absent_from_baseline"),
    (PARTITION, '    if tsv_rows != baseline_rows:\n        raise', '    if False:\n        raise',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_tsv_rows_that_disagree_with_baseline_mode_multiplicity"),
    (PARTITION, 'set(detail) != {"tsv_rows", "cutoff", "genes"}', '{"tsv_rows", "cutoff", "genes"} - set(detail)',
     "tests.test_sensitivity_partition.PartitionFailsClosedTest.test_rejects_unexpected_fields_at_every_level"),
    (PARTITION, '            else:\n                variant_counts["removed_by_inheritance"] += 1', '            else:\n                variant_counts["removed_by_cutoff"] += 1',
     "tests.test_sensitivity_partition.PartitionFromDetailTest.test_variant_partition_is_exhaustive_and_disjoint"),
    (PARTITION, '            if gene_strict != gene_baseline:\n                changed_mode_genes.append(symbol)', '            changed_mode_genes.append(symbol)',
     "tests.test_sensitivity_partition.PartitionFromDetailTest.test_mode_changes_are_reported_only_for_retained_genes"),
    (PARTITION, '                strict_rows += len(strict)', '                strict_rows += 1',
     "tests.test_sensitivity_partition.PartitionReceiptTest.test_receipt_validates_against_count_basis_contract"),
    (PARTITION, '    if include_symbols:\n        receipt["retained_genes_with_changed_mode_set"]', '    if True:\n        receipt["retained_genes_with_changed_mode_set"]',
     "tests.test_sensitivity_partition.PartitionReceiptTest.test_receipt_carries_cutoff_and_no_symbols_by_default"),
    (BOUNDED, 'object_pairs_hook=_reject_duplicate_keys', 'object_pairs_hook=dict',
     "tests.test_cli.SensitivityPartitionCliTests.test_duplicate_json_keys_are_rejected_not_last_wins"),
    (BOUNDED, 'getattr(os, "O_NOFOLLOW", 0)', '0',
     "tests.test_cli.SensitivityPartitionCliTests.test_symlink_and_non_regular_detail_are_rejected_at_open"),
    (BOUNDED, '        if not stat.S_ISREG(status.st_mode):\n            raise', '        if False:\n            raise',
     "tests.test_cli.SensitivityPartitionCliTests.test_regular_file_decision_is_made_on_the_open_descriptor"),
    (BOUNDED, '        if status.st_size > max_bytes:\n            raise', '        if False:\n            raise',
     "tests.test_cli.SensitivityPartitionCliTests.test_oversized_detail_is_rejected_by_fstat_without_reading_it"),
    (BOUNDED, '    if len(raw) > max_bytes:\n        raise', '    if False:\n        raise',
     "tests.test_cli.SensitivityPartitionCliTests.test_file_that_grows_after_fstat_is_still_rejected"),
]


def _copy_tree(directory: Path) -> Path:
    """Copy the package, its contract schema and the tests into a scratch root so mutants never touch the repo."""
    scratch = directory / "tree"
    scratch.mkdir()
    shutil.copytree(PACKAGE, scratch / "mva_prioritizer", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(TESTS, scratch / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "schemas", scratch / "schemas")
    return scratch


def _run_test_in(scratch: Path, test_id: str) -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", test_id],
        cwd=scratch, capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(scratch)},
    )
    return completed.returncode == 0


class GuardMutationTest(unittest.TestCase):
    def test_every_disabled_guard_makes_its_test_fail(self):
        survivors = []
        with tempfile.TemporaryDirectory() as directory:
            scratch = _copy_tree(Path(directory))
            for module_file, old, new, test_id in MUTATIONS:
                target = scratch / "mva_prioritizer" / module_file
                original = target.read_text()
                self.assertEqual(original.count(old), 1, f"snippet must occur exactly once in {module_file}: {old!r}")
                self.assertTrue(_run_test_in(scratch, test_id), f"baseline must be green before mutating: {test_id}")
                target.write_text(original.replace(old, new, 1))
                try:
                    if _run_test_in(scratch, test_id):
                        survivors.append((module_file, old.strip().splitlines()[0], test_id.rsplit(".", 1)[1]))
                finally:
                    target.write_text(original)
        self.assertEqual(survivors, [], f"guards whose removal went undetected: {survivors}")
        self.assertEqual(len(MUTATIONS), 18)

    def test_repo_modules_are_untouched(self):
        for module_file in (PARTITION, BOUNDED):
            source = (PACKAGE / module_file).read_text()
            for entry in MUTATIONS:
                if entry[0] == module_file:
                    self.assertIn(entry[1], source, f"guard missing from {module_file}: {entry[1]!r}")


if __name__ == "__main__":
    unittest.main()
