#!/usr/bin/env python3
"""Run the ReMM 0.963 sensitivity recomputation against a frozen noncoding run.

Design: docs/18-private-sensitivity-design.md. This script is the private run.
It is exercised here only on synthetic trees (tests/test_run_sensitivity_driver.py).

Usage:
  run_sensitivity_remm963.py --frozen-run DIR --output-root DIR --proband NAME
                             --java PATH --exomiser-lib DIR --recompute-class-dir DIR

Preconditions, all checked before anything is created:
  - no component of the frozen run path from its parent downward is a symlink, and
    every file read from it is opened without following links (descriptor walk);
  - the frozen run holds exactly one results/<stem>.variants.tsv, the matching
    results/<stem>.jsonl, and <run>-receipt.json with state "completed";
  - both results files hash to the values in the receipt's outputs block;
  - the engine consumes a staged copy of the verified TSV bytes, not the frozen path;
  - the TSV and JSONL agree: same set of (gene, contig, start, ref, alt) keys, and
    every TSV MOI appears in the matching JSONL variant's compatible modes;
  - the output root does not exist, is a sibling of the frozen run, and is named
    <run>-sensitivity-remm963;
  - java runs, the exomiser lib holds exomiser-core-15.1.0.jar, and the class
    directory holds a regular Recompute.class.

After the engine runs, all three frozen inputs are re-read and hashed, and the
staged copy is re-hashed; all must match the verified bytes.
On any failure: exit 2, one bounded line on stderr naming no path or sample, and
no output root left behind. The frozen run is never opened for writing.
"""
from __future__ import annotations

import argparse
import csv
import errno
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mva_prioritizer.bounded_input import InputRejected, _reject_duplicate_keys  # noqa: E402
from mva_prioritizer.sensitivity_partition import PartitionError, partition_from_detail, partition_receipt  # noqa: E402

CUTOFF = 0.963
CORE_JAR = "exomiser-core-15.1.0.jar"
MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_TOOL_BYTES = 512 * 1024 * 1024
OUTPUT_SUFFIX = "-sensitivity-remm963"
MOI_ABBREVIATION = {"AD": "AUTOSOMAL_DOMINANT", "AR": "AUTOSOMAL_RECESSIVE", "XD": "X_DOMINANT",
                    "XR": "X_RECESSIVE", "MT": "MITOCHONDRIAL", "ANY": "ANY"}
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
CLOEXEC = getattr(os, "O_CLOEXEC", 0)


class Refused(Exception):
    """A precondition failed. The message is safe to print (no paths, no sample names)."""


# ---------------------------------------------------------------- descriptor walk

def _open_dir_nofollow(parent_fd: int, name: str) -> int:
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW | CLOEXEC, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK, errno.ENOTDIR):
            raise Refused("frozen run components must not be symlinks") from None
        raise
    if stat.S_ISLNK(os.fstat(fd).st_mode) or not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise Refused("frozen run components must not be symlinks")
    return fd


def _walk_to(root: Path) -> int:
    """Open ``root`` as a directory descriptor, refusing any symlink on the way from its parent."""
    parent = root.parent.resolve(strict=True)
    if not parent.is_dir():
        raise Refused("frozen run parent is not a directory")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | CLOEXEC)
    try:
        return _open_dir_nofollow(parent_fd, root.name)
    finally:
        os.close(parent_fd)


def _read_regular_at(dir_fd: int, name: str, max_bytes: int) -> bytes:
    try:
        fd = os.open(name, os.O_RDONLY | NOFOLLOW | getattr(os, "O_NONBLOCK", 0) | CLOEXEC, dir_fd=dir_fd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise Refused("frozen run components must not be symlinks") from None
        if exc.errno == errno.ENOENT:
            raise Refused("frozen input missing") from None
        raise
    try:
        status = os.fstat(fd)
        if not stat.S_ISREG(status.st_mode):
            raise Refused("frozen input must be a regular file")
        if status.st_size > max_bytes:
            raise Refused("frozen input exceeds size limit")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            raw = handle.read(max_bytes + 1)
    finally:
        if fd != -1:
            os.close(fd)
    if len(raw) > max_bytes:
        raise Refused("frozen input exceeds size limit")
    return raw


def _list_dir(dir_fd: int) -> list[str]:
    return sorted(os.listdir(dir_fd))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _strict_json(raw: bytes, what: str):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, RecursionError, ValueError, InputRejected):
        raise Refused(f"{what} is not strict JSON") from None


# ---------------------------------------------------------------- frozen inputs

class FrozenInputs:
    """Bytes of the frozen inputs read once through a descriptor walk, plus their hashes."""

    def __init__(self, frozen_run: Path):
        self.frozen_run = frozen_run
        run_fd = _walk_to(frozen_run)
        try:
            names = _list_dir(run_fd)
            receipt_name = f"{frozen_run.name}-receipt.json"
            if receipt_name not in names:
                raise Refused("freeze receipt missing")
            if "results" not in names:
                raise Refused("frozen run has no results directory")
            self.receipt_raw = _read_regular_at(run_fd, receipt_name, MAX_INPUT_BYTES)
            results_fd = _open_dir_nofollow(run_fd, "results")
            try:
                entries = _list_dir(results_fd)
                tsvs = [n for n in entries if n.endswith(".variants.tsv")]
                if len(tsvs) != 1:
                    raise Refused("frozen run must contain exactly one variants TSV")
                self.tsv_name = tsvs[0]
                self.jsonl_name = self.tsv_name[: -len(".variants.tsv")] + ".jsonl"
                if self.jsonl_name not in entries:
                    raise Refused("frozen run must contain the matching JSONL")
                self.tsv_raw = _read_regular_at(results_fd, self.tsv_name, MAX_INPUT_BYTES)
                self.jsonl_raw = _read_regular_at(results_fd, self.jsonl_name, MAX_INPUT_BYTES)
            finally:
                os.close(results_fd)
        finally:
            os.close(run_fd)
        self.tsv_sha = _sha256(self.tsv_raw)
        self.jsonl_sha = _sha256(self.jsonl_raw)
        self.receipt_sha = _sha256(self.receipt_raw)

    def reread_hashes(self) -> tuple[str, str, str]:
        again = FrozenInputs(self.frozen_run)
        return again.tsv_sha, again.jsonl_sha, again.receipt_sha

    def check_receipt(self) -> None:
        receipt = _strict_json(self.receipt_raw, "freeze receipt")
        if not isinstance(receipt, dict) or receipt.get("state") != "completed" or not isinstance(receipt.get("outputs"), dict):
            raise Refused("freeze receipt is not a completed run")
        for name, actual in ((self.tsv_name, self.tsv_sha), (self.jsonl_name, self.jsonl_sha)):
            entry = receipt["outputs"].get(name)
            if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
                raise Refused("freeze receipt lacks a hash for a frozen input")
            if actual != entry["sha256"]:
                raise Refused("frozen input hash disagrees with the freeze receipt")

    def check_consistency(self) -> None:
        """TSV keys equal JSONL keys; every TSV MOI appears in the matching JSONL variant."""
        try:
            rows = list(csv.DictReader(io.StringIO(self.tsv_raw.decode("utf-8")), delimiter="\t"))
        except (UnicodeDecodeError, csv.Error):
            raise Refused("frozen TSV unreadable") from None
        required = {"GENE_SYMBOL", "CONTIG", "START", "REF", "ALT", "MOI"}
        if not rows or not required <= set(rows[0]):
            raise Refused("frozen TSV lacks required columns")
        jsonl_modes: dict[tuple, set] = {}
        for line in self.jsonl_raw.decode("utf-8", errors="strict").splitlines():
            if not line.strip():
                continue
            gene = _strict_json(line.encode("utf-8"), "frozen JSONL")
            if not isinstance(gene, dict):
                raise Refused("frozen JSONL unreadable")
            for variant in gene.get("variantEvaluations", []):
                key = (gene.get("geneSymbol"), variant.get("contigName"), str(variant.get("start")), variant.get("ref"), variant.get("alt"))
                jsonl_modes[key] = set(variant.get("compatibleInheritanceModes", []))
        tsv_keys = {(r["GENE_SYMBOL"], r["CONTIG"], r["START"], r["REF"], r["ALT"]) for r in rows}
        if tsv_keys != set(jsonl_modes):
            raise Refused("frozen TSV and JSONL disagree")
        for r in rows:
            mode = MOI_ABBREVIATION.get(r["MOI"])
            if mode is None or mode not in jsonl_modes[(r["GENE_SYMBOL"], r["CONTIG"], r["START"], r["REF"], r["ALT"])]:
                raise Refused("frozen TSV and JSONL disagree")


# ---------------------------------------------------------------- other checks

def _check_output_root(output_root: Path, frozen_run: Path) -> None:
    if output_root.exists() or output_root.is_symlink():
        raise Refused("output root already exists")
    resolved_out = output_root.parent.resolve() / output_root.name
    resolved_run = frozen_run.resolve()
    if resolved_out == resolved_run or resolved_run in resolved_out.parents:
        raise Refused("output root must not be inside the frozen run")
    if resolved_out.parent != resolved_run.parent:
        raise Refused("output root must be a sibling of the frozen run")
    if output_root.name != frozen_run.name + OUTPUT_SUFFIX:
        raise Refused("output root name must be the frozen run name plus the sensitivity suffix")


def _stage_verified_bytes(output_root: Path, name: str, raw: bytes) -> Path:
    """Write the verified bytes into the output root; the engine consumes this copy."""
    staged = output_root / name
    _write_new(staged, raw)
    return staged


def _hash_regular(path: Path, max_bytes: int, what: str) -> str:
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | CLOEXEC)
    try:
        try:
            return _sha256(_read_regular_at(parent_fd, path.name, max_bytes))
        except Refused:
            raise Refused(f"{what} not found") from None
    finally:
        os.close(parent_fd)


def _check_tools(java: Path, lib: Path, class_dir: Path) -> dict:
    if not java.is_file() or not os.access(java, os.X_OK):
        raise Refused("java executable not found")
    jar = lib / CORE_JAR
    if not lib.is_dir() or not jar.is_file():
        raise Refused("exomiser core jar not found")
    class_file = class_dir / "Recompute.class"
    if not class_dir.is_dir() or not class_file.is_file() or class_file.is_symlink():
        raise Refused("compiled Recompute class not found")
    try:
        version = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        raise Refused("java did not report a version") from None
    if version.returncode != 0:
        raise Refused("java did not report a version")
    java_source = class_dir / "Recompute.java"
    return {
        "exomiser_core_jar_sha256": _hash_regular(jar, MAX_TOOL_BYTES, "exomiser core jar"),
        "recompute_class_sha256": _hash_regular(class_file, MAX_TOOL_BYTES, "compiled Recompute class"),
        "recompute_java_sha256": _hash_regular(java_source, 1024 * 1024, "Recompute source") if java_source.is_file() else None,
        "driver_script_sha256": _hash_regular(Path(__file__).resolve(), 1024 * 1024, "driver script"),
        "java_version": (version.stderr or version.stdout).strip().splitlines()[0],
    }


def _write_new(path: Path, payload: bytes) -> str:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW | CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
    os.chmod(path, 0o400)
    return _sha256(payload)


# ---------------------------------------------------------------- run

def run(args: argparse.Namespace) -> dict:
    frozen_run = Path(args.frozen_run)
    output_root = Path(args.output_root)
    java, lib, class_dir = Path(args.java), Path(args.exomiser_lib), Path(args.recompute_class_dir)

    inputs = FrozenInputs(frozen_run)
    inputs.check_receipt()
    inputs.check_consistency()
    _check_output_root(output_root, frozen_run)
    tools = _check_tools(java, lib, class_dir)

    output_root.mkdir(mode=0o700)
    completed = False
    try:
        summary = output_root / "recompute-summary.json"
        detail = output_root / "recompute-detail.json"
        staged_tsv = _stage_verified_bytes(output_root, "input.variants.tsv", inputs.tsv_raw)
        classpath = f"{class_dir}:{lib}/*"
        result = subprocess.run(
            [str(java), "-cp", classpath, "Recompute", str(staged_tsv), args.proband, str(summary), str(detail)],
            capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0 or not summary.is_file() or not detail.is_file():
            raise Refused("recomputation did not complete")
        if inputs.reread_hashes() != (inputs.tsv_sha, inputs.jsonl_sha, inputs.receipt_sha):
            raise Refused("frozen input changed during the run")
        os.chmod(summary, 0o400)
        os.chmod(detail, 0o400)
        staged_sha = _hash_regular(staged_tsv, MAX_INPUT_BYTES, "staged input")
        if staged_sha != inputs.tsv_sha:
            raise Refused("staged input does not match the verified bytes")

        detail_raw = _read_regular_at(os.open(output_root, os.O_RDONLY | os.O_DIRECTORY | CLOEXEC), "recompute-detail.json", 64 * 1024 * 1024)
        partition = partition_from_detail(_strict_json(detail_raw, "recompute detail"))
        if partition["cutoff"] != CUTOFF:
            raise Refused("recomputation cutoff is not the designed cutoff")
        receipt = partition_receipt(partition, include_symbols=False)
        outputs = {
            "input.variants.tsv": staged_sha,
            "recompute-summary.json": _hash_regular(summary, 64 * 1024 * 1024, "recompute summary"),
            "recompute-detail.json": _sha256(detail_raw),
            "partition-receipt.json": _write_new(output_root / "partition-receipt.json", (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()),
        }
        sensitivity = {
            "kind": "noncoding-sensitivity-remm963",
            "state": "completed",
            "cutoff": CUTOFF,
            "design": "docs/18-private-sensitivity-design.md",
            "inputs": {
                "variants_tsv_sha256": inputs.tsv_sha,
                "jsonl_sha256": inputs.jsonl_sha,
                "freeze_receipt_sha256": inputs.receipt_sha,
            },
            "tools": tools,
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
