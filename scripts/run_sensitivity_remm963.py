#!/usr/bin/env python3
"""Run the ReMM 0.963 sensitivity recomputation against a frozen noncoding run.

Design: docs/18-private-sensitivity-design.md. This script is the private run.
It is exercised here only on synthetic trees (tests/test_run_sensitivity_driver.py).

Usage:
  run_sensitivity_remm963.py --frozen-run DIR --output-root DIR --proband NAME
                             --java PATH --exomiser-lib DIR --recompute-class-dir DIR

Preconditions, all checked before anything is created:
  - the frozen run holds results/<stem>.variants.tsv, results/<stem>.jsonl and a
    freeze receipt named <run>-receipt.json with state "completed";
  - both results files are regular files (not symlinks) whose sha256 matches the
    receipt's outputs block;
  - the output root does not exist, is a sibling of the frozen run (same parent),
    and does not have the frozen run as an ancestor;
  - java, the exomiser lib directory with exomiser-core-15.1.0.jar, and the
    compiled Recompute class all exist.

On any failure: exit 2, one bounded line on stderr, no output root left behind
claiming completion. The frozen run is never opened for writing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mva_prioritizer.bounded_input import InputRejected, load_strict_json, read_regular_file  # noqa: E402
from mva_prioritizer.sensitivity_partition import PartitionError, partition_from_detail, partition_receipt  # noqa: E402

CUTOFF = 0.963
CORE_JAR = "exomiser-core-15.1.0.jar"
MAX_INPUT_BYTES = 256 * 1024 * 1024
OUTPUT_SUFFIX = "-sensitivity-remm963"


class Refused(Exception):
    """A precondition failed. The message is safe to print (no paths, no sample names)."""


def _sha256_regular(path: Path, max_bytes: int) -> str:
    try:
        return hashlib.sha256(read_regular_file(path, max_bytes)).hexdigest()
    except InputRejected as exc:
        raise Refused(f"frozen input rejected: {exc}") from None


def _locate_frozen(frozen_run: Path) -> tuple[Path, Path, Path]:
    if not frozen_run.is_dir() or frozen_run.is_symlink():
        raise Refused("frozen run must be a real directory")
    receipt = frozen_run / f"{frozen_run.name}-receipt.json"
    results = frozen_run / "results"
    tsvs = sorted(results.glob("*.variants.tsv")) if results.is_dir() else []
    if len(tsvs) != 1:
        raise Refused("frozen run must contain exactly one variants TSV")
    tsv = tsvs[0]
    jsonl = results / (tsv.name[: -len(".variants.tsv")] + ".jsonl")
    if not jsonl.exists():
        raise Refused("frozen run must contain the matching JSONL")
    return receipt, tsv, jsonl


def _check_receipt(receipt_path: Path, tsv: Path, jsonl: Path) -> tuple[dict, str, str, str]:
    try:
        receipt = load_strict_json(receipt_path, MAX_INPUT_BYTES)
    except (InputRejected, OSError):
        raise Refused("freeze receipt missing or unreadable") from None
    if not isinstance(receipt, dict) or receipt.get("state") != "completed" or not isinstance(receipt.get("outputs"), dict):
        raise Refused("freeze receipt is not a completed run")
    outputs = receipt["outputs"]
    hashes = {}
    for path in (tsv, jsonl):
        entry = outputs.get(path.name)
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise Refused("freeze receipt lacks a hash for a frozen input")
        actual = _sha256_regular(path, MAX_INPUT_BYTES)
        if actual != entry["sha256"]:
            raise Refused("frozen input hash disagrees with the freeze receipt")
        hashes[path.name] = actual
    return receipt, hashes[tsv.name], hashes[jsonl.name], _sha256_regular(receipt_path, MAX_INPUT_BYTES)


def _check_output_root(output_root: Path, frozen_run: Path) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise Refused("output root already exists")
    resolved_out = output_root.parent.resolve() / output_root.name
    resolved_run = frozen_run.resolve()
    if resolved_out == resolved_run or resolved_run in resolved_out.parents:
        raise Refused("output root must not be inside the frozen run")
    if resolved_out.parent != resolved_run.parent:
        raise Refused("output root must be a sibling of the frozen run")
    if not output_root.name.endswith(OUTPUT_SUFFIX):
        raise Refused("output root name must carry the sensitivity suffix")


def _check_tools(java: Path, lib: Path, class_dir: Path) -> str:
    if not java.is_file() or not os.access(java, os.X_OK):
        raise Refused("java executable not found")
    jar = lib / CORE_JAR
    if not lib.is_dir() or not jar.is_file():
        raise Refused("exomiser core jar not found")
    if not class_dir.is_dir():
        raise Refused("Recompute class directory not found")
    return _sha256_regular(jar, 512 * 1024 * 1024)


def _write_new(path: Path, payload: bytes) -> str:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
    os.chmod(path, 0o400)
    return hashlib.sha256(payload).hexdigest()


def run(args: argparse.Namespace) -> dict:
    frozen_run = Path(args.frozen_run)
    output_root = Path(args.output_root)
    java, lib, class_dir = Path(args.java), Path(args.exomiser_lib), Path(args.recompute_class_dir)

    receipt_path, tsv, jsonl = _locate_frozen(frozen_run)
    _, tsv_sha, jsonl_sha, receipt_sha = _check_receipt(receipt_path, tsv, jsonl)
    _check_output_root(output_root, frozen_run)
    jar_sha = _check_tools(java, lib, class_dir)

    output_root.mkdir(mode=0o700)
    completed = False
    try:
        summary = output_root / "recompute-summary.json"
        detail = output_root / "recompute-detail.json"
        classpath = f"{class_dir}:{lib}/*"
        result = subprocess.run(
            [str(java), "-cp", classpath, "Recompute", str(tsv), args.proband, str(summary), str(detail)],
            capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0 or not summary.is_file() or not detail.is_file():
            raise Refused("recomputation did not complete")
        os.chmod(summary, 0o400)
        os.chmod(detail, 0o400)

        detail_data = load_strict_json(detail, 64 * 1024 * 1024)
        partition = partition_from_detail(detail_data)
        if partition["cutoff"] != CUTOFF:
            raise Refused("recomputation cutoff is not the designed cutoff")
        receipt = partition_receipt(partition, include_symbols=False)
        partition_path = output_root / "partition-receipt.json"
        outputs = {
            "recompute-summary.json": _sha256_regular(summary, 64 * 1024 * 1024),
            "recompute-detail.json": _sha256_regular(detail, 64 * 1024 * 1024),
            "partition-receipt.json": _write_new(partition_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()),
        }
        sensitivity = {
            "kind": "noncoding-sensitivity-remm963",
            "state": "completed",
            "cutoff": CUTOFF,
            "design": "docs/18-private-sensitivity-design.md",
            "inputs": {
                "frozen_run_name": frozen_run.name,
                "variants_tsv_sha256": tsv_sha,
                "jsonl_sha256": jsonl_sha,
                "freeze_receipt_sha256": receipt_sha,
            },
            "tools": {
                "exomiser_core_jar_sha256": jar_sha,
                "recompute_java_sha256": _sha256_regular(class_dir / "Recompute.java", 1024 * 1024) if (class_dir / "Recompute.java").is_file() else None,
            },
            "partition": {k: receipt[k] for k in ("variant_partition", "gene_partition", "genes_baseline_unique_symbols", "retained_genes_with_changed_mode_set_count")},
            "outputs": outputs,
        }
        payload = (json.dumps(sensitivity, indent=2, sort_keys=True) + "\n").encode()
        receipt_sha256 = _write_new(output_root / "sensitivity-receipt.json", payload)
        os.chmod(output_root, 0o500)
        completed = True
        return {"state": "completed", "external_actions": 0, "partition": sensitivity["partition"],
                "sensitivity_receipt_sha256": receipt_sha256}
    finally:
        if not completed:
            os.chmod(output_root, 0o700)
            for child in output_root.iterdir():
                child.chmod(0o600)
            shutil.rmtree(output_root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="run_sensitivity_remm963")
    parser.add_argument("--frozen-run", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--proband", required=True)
    parser.add_argument("--java", required=True)
    parser.add_argument("--exomiser-lib", required=True)
    parser.add_argument("--recompute-class-dir", required=True)
    args = parser.parse_args(argv)
    try:
        status = run(args)
    except Refused as exc:
        print(json.dumps({"error": str(exc), "state": "failed_closed"}), file=sys.stderr)
        return 2
    except (InputRejected, PartitionError, OSError, subprocess.SubprocessError, ValueError):
        print('{"error":"run_rejected","state":"failed_closed"}', file=sys.stderr)
        return 2
    print(json.dumps(status, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
