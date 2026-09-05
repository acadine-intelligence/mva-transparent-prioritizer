"""Validate supported count-basis receipts without changing their files.

Usage: python3 scripts/validate_receipt_basis.py receipt.json [receipt.json ...]
Exit 0 means all supplied count-basis receipts passed. Exit 1 means a failure.
This checks labels and arithmetic only. It does not validate arbitrary Exomiser
receipts or prove that counts match source records. See docs/13-count-basis.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mva_prioritizer.receipt_basis import BasisError, validate_receipt  # noqa: E402

MAX_BYTES = 1024 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BasisError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(_value):
    raise BasisError("non-finite JSON value")


def validate_file(path: Path) -> list[str]:
    try:
        if not path.is_file() or path.is_symlink():
            return ["input must be a regular file"]
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return ["input exceeds size limit"]
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        validate_receipt(payload)
    except BasisError as exc:
        return [str(exc)]
    except (OSError, ValueError, RecursionError):
        return ["input unreadable or invalid JSON"]
    return []


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    failed = False
    for index, arg in enumerate(argv[1:], 1):
        for problem in validate_file(Path(arg)):
            failed = True
            print(f"VIOLATION: input {index}: {problem}")
    if failed:
        return 1
    print(f"OK: {len(argv) - 1} count-basis receipt(s) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
