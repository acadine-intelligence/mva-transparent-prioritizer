from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .environment import verify_environment
from .manifest import validate_manifest
from .noncoding_benchmark import run_noncoding_benchmark
from .paths import validate_root_pair
from .privacy_scan import scan_public_tree
from .reference_bundle import (
    acquire_reference_artifact,
    load_reference_bundle,
    verify_reference_bundle,
)
from .reference_install import install_reference_artifact
from .safe_projection import project_safe_learning, read_forbidden_values
from .synthetic import run_synthetic
from .verify import verify_synthetic_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mva-prioritizer")
    subcommands = parser.add_subparsers(dest="command", required=True)
    synthetic = subcommands.add_parser("synthetic-run")
    synthetic.add_argument("--fixture", required=True)
    synthetic.add_argument("--config", required=True)
    synthetic.add_argument("--output-root", required=True)
    noncoding = subcommands.add_parser("noncoding-benchmark")
    noncoding.add_argument("--fixture", required=True)
    noncoding.add_argument("--config", required=True)
    noncoding.add_argument("--acquisition-manifest", required=True)
    noncoding.add_argument("--output-root", required=True)
    verify = subcommands.add_parser("verify-run")
    verify.add_argument("--fixture", required=True)
    verify.add_argument("--config", required=True)
    verify.add_argument("--run-directory", required=True)
    manifest = subcommands.add_parser("validate-manifest")
    manifest.add_argument("--public-root", required=True)
    manifest.add_argument("--private-root", required=True)
    manifest.add_argument("--manifest", required=True)
    manifest.add_argument("--run-kind", choices=("private", "synthetic"), required=True)
    projection = subcommands.add_parser("project-safe")
    projection.add_argument("--public-root", required=True)
    projection.add_argument("--private-root", required=True)
    projection.add_argument("--source", required=True)
    projection.add_argument("--forbidden-values", required=True)
    privacy_scan = subcommands.add_parser("privacy-scan")
    privacy_scan.add_argument("--public-root", required=True)
    privacy_scan.add_argument("--private-root", required=True)
    privacy_scan.add_argument("--forbidden-values", required=True)
    reference_acquire = subcommands.add_parser("reference-acquire")
    reference_acquire.add_argument("--public-root", required=True)
    reference_acquire.add_argument("--private-root", required=True)
    reference_acquire.add_argument("--artifact", required=True)
    reference_verify = subcommands.add_parser("reference-verify")
    reference_verify.add_argument("--public-root", required=True)
    reference_verify.add_argument("--private-root", required=True)
    reference_install = subcommands.add_parser("reference-install")
    reference_install.add_argument("--public-root", required=True)
    reference_install.add_argument("--private-root", required=True)
    reference_install.add_argument("--artifact", required=True)
    verify_environment_command = subcommands.add_parser("verify-environment")
    verify_environment_command.add_argument("--public-root", required=True)
    verify_environment_command.add_argument("--private-root", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _dispatch(args)
    except Exception:
        print(
            '{"error":"input_rejected","state":"failed_closed"}',
            file=sys.stderr,
        )
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "synthetic-run":
        summary = run_synthetic(
            fixture_path=Path(args.fixture),
            config_path=Path(args.config),
            output_root=Path(args.output_root),
        )
        status = {
            "external_actions": summary.external_actions,
            "finding_count": summary.finding_count,
            "run_id": summary.run_id,
            "state": summary.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "noncoding-benchmark":
        summary = run_noncoding_benchmark(
            fixture_path=Path(args.fixture),
            config_path=Path(args.config),
            acquisition_manifest_path=Path(args.acquisition_manifest),
            output_root=Path(args.output_root),
        )
        status = {
            "case_count": summary.case_count,
            "external_actions": summary.external_actions,
            "passed_case_count": summary.passed_case_count,
            "private_execution_authorized": summary.private_execution_authorized,
            "run_id": summary.run_id,
            "state": summary.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "verify-run":
        result = verify_synthetic_run(
            fixture_path=Path(args.fixture),
            config_path=Path(args.config),
            run_directory=Path(args.run_directory),
        )
        status = {
            "external_actions": 0,
            "file_count": result.file_count,
            "run_id": result.run_id,
            "state": result.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "validate-manifest":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        result = validate_manifest(
            roots.private_root,
            args.manifest,
            expected_run_kind=args.run_kind,
        )
        status = {
            "artifact_count": result.artifact_count,
            "external_actions": 0,
            "manifest_sha256": result.manifest_sha256,
            "state": result.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "project-safe":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        forbidden_values = read_forbidden_values(
            roots.private_root,
            args.forbidden_values,
        )
        result = project_safe_learning(
            private_root=roots.private_root,
            source_relative_path=args.source,
            public_output_root=roots.public_root,
            forbidden_values=forbidden_values,
        )
        status = {
            "external_actions": result.external_actions,
            "output_name": result.output_name,
            "state": result.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "privacy-scan":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        forbidden_values = read_forbidden_values(
            roots.private_root,
            args.forbidden_values,
        )
        result = scan_public_tree(
            public_root=roots.public_root,
            forbidden_values=forbidden_values,
        )
        status = {
            "byte_count": result.byte_count,
            "external_actions": result.external_actions,
            "file_count": result.file_count,
            "state": result.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "reference-acquire":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        bundle = load_reference_bundle(roots.public_root / "config" / "reference-bundle.json")
        result = acquire_reference_artifact(
            roots.private_root,
            bundle,
            args.artifact,
        )
        status = {
            "byte_count": result.byte_count,
            "external_actions": 1,
            "pin_required_count": result.pin_required_count,
            "state": result.state,
            "verified_count": result.verified_count,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "reference-verify":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        bundle = load_reference_bundle(roots.public_root / "config" / "reference-bundle.json")
        result = verify_reference_bundle(roots.private_root, bundle)
        status = {
            "artifact_count": result.artifact_count,
            "byte_count": result.byte_count,
            "external_actions": 0,
            "state": result.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "reference-install":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        bundle = load_reference_bundle(roots.public_root / "config" / "reference-bundle.json")
        result = install_reference_artifact(
            roots.private_root,
            bundle,
            args.artifact,
        )
        status = {
            "byte_count": result.byte_count,
            "directory_count": result.directory_count,
            "external_actions": 0,
            "file_count": result.file_count,
            "state": result.state,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    if args.command == "verify-environment":
        roots = validate_root_pair(Path(args.public_root), Path(args.private_root))
        result = verify_environment(roots.public_root, roots.private_root)
        status = {
            "artifact_count": result.artifact_count,
            "check_count": result.check_count,
            "external_actions": 0,
            "installed_count": result.installed_count,
            "state": result.state,
            "support_count": result.support_count,
            "tool_count": result.tool_count,
        }
        print(json.dumps(status, separators=(",", ":"), sort_keys=True))
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
