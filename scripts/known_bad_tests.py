from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASES = {
    "archive_absolute_link": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_absolute_tar_link",
    "archive_ambiguous_link": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_ambiguous_link_namespace",
    "archive_ambiguous_path": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_ambiguous_link_path_syntax",
    "archive_ambiguous_target": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_ambiguous_link_target_syntax",
    "archive_broken_link": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_broken_tar_link",
    "archive_cyclic_link": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_cyclic_tar_links",
    "archive_directory_form_file": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_a_directory_form_link_to_a_file",
    "archive_escaping_link": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_tar_link_that_escapes_the_archive_root",
    "archive_hard_link": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_tar_hard_link",
    "archive_special_member": "tests.test_reference_install.ReferenceInstallationTests.test_rejects_special_tar_member",
    "canary_projection": "tests.test_safe_projection.SafeProjectionTests.test_blocks_a_forbidden_value_inside_an_allowlisted_field",
    "canary_tree_scan": "tests.test_privacy_scan.PrivacyScanTests.test_blocks_a_canary_without_reporting_its_value_or_location",
    "caller_selected_private_output": "tests.test_safe_projection.SafeProjectionTests.test_rejects_a_caller_selected_output_inside_the_private_root",
    "duplicate_json_key": "tests.test_manifest.ManifestTests.test_rejects_duplicate_json_keys",
    "environment_reference_tamper": "tests.test_environment.EnvironmentHealthTests.test_rejects_an_installed_reference_changed_without_changing_its_size",
    "environment_receipt_tamper": "tests.test_environment.EnvironmentHealthTests.test_rejects_a_changed_immutable_health_receipt",
    "environment_support_symlink": "tests.test_environment.EnvironmentHealthTests.test_rejects_a_symlink_inside_a_support_tree",
    "environment_support_tamper": "tests.test_environment.EnvironmentHealthTests.test_rejects_a_support_tree_changed_after_the_receipt_was_written",
    "environment_tool_tamper": "tests.test_environment.EnvironmentHealthTests.test_rejects_a_tool_changed_after_the_receipt_was_written",
    "environment_unsafe_state": "tests.test_environment.EnvironmentHealthTests.test_rejects_each_unsafe_system_state",
    "environment_writable_tool": "tests.test_environment.EnvironmentHealthTests.test_rejects_a_writable_tool_entrypoint",
    "forbidden_fields": "tests.test_safe_projection.SafeProjectionTests.test_rejects_an_unknown_field_without_writing_or_reflecting_it",
    "manifest_stale_receipt": "tests.test_manifest.ManifestTests.test_rejects_an_input_changed_after_manifest_freeze",
    "no_clobber_projection": "tests.test_safe_projection.SafeProjectionTests.test_refuses_to_replace_an_existing_public_projection",
    "public_source_artifact": "tests.test_public_source_scan.PublicSourceScanTests.test_blocks_genomic_artifacts_and_credential_shapes",
    "reference_fetcher_symlink": "tests.test_reference_bundle.ReferenceBundleTests.test_rejects_a_fetcher_created_symlink_without_changing_its_target",
    "reference_receipt_symlink": "tests.test_reference_bundle.ReferenceBundleTests.test_rejects_a_symlinked_temporary_acquisition_receipt",
    "root_overlap": "tests.test_path_guards.PathGuardTests.test_rejects_equal_nested_and_ancestor_roots",
    "score_tamper_rehash": "tests.test_verify.RunVerificationTests.test_rejects_score_tampering_after_local_hashes_are_recomputed",
    "source_machine_path": "tests.test_public_source_scan.PublicSourceScanTests.test_blocks_source_machine_paths_without_reflecting_them",
    "symlink_special_oversize": "tests.test_path_guards.PathGuardTests.test_rejects_symlink_root_symlink_input_directory_fifo_and_oversize",
    "symlink_tree_scan": "tests.test_privacy_scan.PrivacyScanTests.test_rejects_a_symlink_in_the_public_tree",
    "unknown_as_zero": "tests.test_synthetic_journey.SyntheticJourneyTests.test_missing_score_input_stays_unknown_instead_of_becoming_zero",
    "unsafe_relative_path": "tests.test_path_guards.PathGuardTests.test_rejects_unsafe_relative_names_before_open",
}


def main() -> int:
    failures: list[str] = []
    loader = unittest.TestLoader()
    for case_name, test_name in CASES.items():
        suite = loader.loadTestsFromName(test_name)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        if not result.wasSuccessful():
            failures.append(case_name)
    status = {
        "case_count": len(CASES),
        "cases": list(CASES),
        "external_actions": 0,
        "state": "failed" if failures else "passed",
    }
    if failures:
        status["failed_cases"] = failures
    print(json.dumps(status, separators=(",", ":"), sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
