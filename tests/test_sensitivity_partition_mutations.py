"""Prove the partition and driver guards are live by removing each one and watching a test fail.

Each entry names one guard in ``mva_prioritizer/sensitivity_partition.py``,
``mva_prioritizer/bounded_input.py`` or ``scripts/run_sensitivity_remm963.py`` by an exact source snippet, the replacement
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
DRIVER = "scripts/run_sensitivity_remm963.py"

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
    # Private-run driver preconditions (scripts/run_sensitivity_remm963.py).
    (DRIVER, '    if resolved_out == resolved_run or resolved_run in resolved_out.parents:\n        raise', '    if False:\n        raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_output_inside_frozen_run"),
    (DRIVER, '    if resolved_out.parent != resolved_run.parent:\n        raise', '    if False:\n        raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_output_that_is_not_a_sibling"),
    (DRIVER, '    if output_root.name != frozen_run.name + OUTPUT_SUFFIX:\n        raise', '    if False:\n        raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_output_name_is_derived_from_the_frozen_run_name"),
    (DRIVER, '    if output_root.exists() or output_root.is_symlink():\n        raise', '    if False:\n        raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_existing_output_root"),
    (DRIVER, '            if actual != entry["sha256"]:\n                raise', '            if False:\n                raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_when_tsv_hash_disagrees_with_freeze_receipt"),
    (DRIVER, 'receipt.get("state") != "completed"', 'False',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_when_freeze_receipt_missing_or_not_completed"),
    (DRIVER, '        if exc.errno in (errno.ELOOP, errno.EMLINK):\n            raise Refused("frozen run components must not be symlinks") from None\n        if exc.errno == errno.ENOENT:', '        if exc.errno == errno.ENOENT:',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_symlinked_frozen_input"),
    (DRIVER, 'os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW | CLOEXEC, dir_fd=parent_fd', 'os.O_RDONLY | os.O_DIRECTORY | CLOEXEC, dir_fd=parent_fd',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_refuses_symlinked_results_directory"),
    (DRIVER, '        if tsv_keys != set(jsonl_modes):\n            raise', '        if False:\n            raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_tsv_jsonl_consistency_check_stops_the_run"),
    (DRIVER, '            if mode is None or mode not in jsonl_modes[', '            if False and mode not in jsonl_modes[',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_tsv_jsonl_consistency_check_stops_the_run"),
    (DRIVER, '        if inputs.reread_hashes() != (inputs.tsv_sha, inputs.jsonl_sha):\n            raise', '        if False:\n            raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_tsv_changed_during_the_engine_run_is_refused"),
    (DRIVER, '        if result.returncode != 0 or not summary.is_file() or not detail.is_file():\n            raise', '        if not summary.is_file() or not detail.is_file():\n            raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_java_nonzero_exit_is_refused_even_when_it_wrote_outputs"),
    (DRIVER, '        if not completed:\n            os.chmod(output_root, 0o700)', '        if False:\n            os.chmod(output_root, 0o700)',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_failed_run_removes_its_partial_output_root"),
    (DRIVER, '    if not java.is_file() or not os.access(java, os.X_OK):\n        raise', '    if False:\n        raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_missing_java_or_jar_fails_before_touching_anything"),
    # The jar and Recompute.class existence checks are backed a second time by _hash_regular,
    # which opens each tool with O_NOFOLLOW through the same descriptor reader the frozen
    # inputs use; removing the explicit check changes no observable behaviour, so those two
    # are deliberately not listed. Their behaviour is tested directly in
    # test_missing_java_or_jar_fails_before_touching_anything and test_requires_compiled_recompute_class.
    (DRIVER, '    os.chmod(path, 0o400)\n    return', '    return',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_happy_path_writes_sibling_and_leaves_frozen_run_byte_identical"),
    (DRIVER, '        if partition["cutoff"] != CUTOFF:\n            raise', '        if False:\n            raise',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_failed_run_removes_its_partial_output_root"),
    (DRIVER, 'receipt = partition_receipt(partition, include_symbols=False)', 'receipt = partition_receipt(partition, include_symbols=True)',
     "tests.test_run_sensitivity_driver.SensitivityDriverTest.test_receipts_carry_no_symbols_even_when_run_name_matches_proband"),
]


def _copy_tree(directory: Path) -> Path:
    """Copy the package, its contract schema and the tests into a scratch root so mutants never touch the repo."""
    scratch = directory / "tree"
    scratch.mkdir()
    shutil.copytree(PACKAGE, scratch / "mva_prioritizer", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(TESTS, scratch / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "schemas", scratch / "schemas")
    shutil.copytree(ROOT / "scripts", scratch / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "tools", scratch / "tools")
    return scratch


def _target(scratch: Path, module_file: str) -> Path:
    return scratch / module_file if "/" in module_file else scratch / "mva_prioritizer" / module_file


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
                target = _target(scratch, module_file)
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
        self.assertEqual(len(MUTATIONS), 35)

    def test_repo_modules_are_untouched(self):
        for module_file in (PARTITION, BOUNDED, DRIVER):
            source = _target(ROOT, module_file).read_text() if "/" in module_file else (PACKAGE / module_file).read_text()
            for entry in MUTATIONS:
                if entry[0] == module_file:
                    self.assertIn(entry[1], source, f"guard missing from {module_file}: {entry[1]!r}")


if __name__ == "__main__":
    unittest.main()
