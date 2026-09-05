"""Validate count-basis labeling in lane-comparison receipts.

Closes the tooling loop for the review lesson (2026-09-04): every count in a receipt
must carry an explicit basis label, and partition blocks must sum on their stated basis.

Usage:
    python3 scripts/validate_receipt_basis.py receipt1.json [receipt2.json ...]

Exit codes: 0 = all receipts valid, 1 = violation found (fail closed).
The validator reads only content-free receipt payloads; it never touches protected rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mva_prioritizer.receipt_basis import BasisError, validate_receipt  # noqa: E402

LANE_COUNT_KEYS = ("rows", "unique_symbols", "unique_keys")


def normalize_lane_receipt(payload: dict) -> dict:
    """Accept either the validate_receipt 'lanes' shape or a flat single-lane receipt."""
    if "lanes" in payload:
        return payload
    lanes = {}
    for key in ("genes", "variants"):
        block = payload.get(key)
        if isinstance(block, dict):
            lanes[key] = block
    if lanes:
        return {"lanes": lanes, "partition": payload.get("rank_movement") or payload.get("partition")}
    return payload


def validate_file(path: Path) -> list[str]:
    payload = json.loads(path.read_text())
    problems: list[str] = []
    normalized = normalize_lane_receipt(payload)
    try:
        validate_receipt(normalized)
    except BasisError as exc:
        problems.append(f"{path.name}: {exc}")
    # Partition sums must hold on their stated basis.
    partition = normalized.get("partition")
    if isinstance(partition, dict) and "basis" in partition:
        inner = partition.get("shared", 0) + partition.get("only_l1", 0) + partition.get("only_l2", 0)
        if inner != partition.get("total"):
            problems.append(
                f"{path.name}: partition sums to {inner}, total says {partition.get('total')}"
            )
    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    all_problems: list[str] = []
    for arg in argv[1:]:
        path = Path(arg)
        if not path.is_file():
            all_problems.append(f"{path}: not a file")
            continue
        all_problems.extend(validate_file(path))
    if all_problems:
        for problem in all_problems:
            print(f"VIOLATION: {problem}")
        return 1
    print(f"OK: {len(argv) - 1} receipt(s) pass basis-labeling validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
