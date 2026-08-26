from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .contract import load_contract
from .paths import read_regular_input
from .synthetic import run_synthetic


RUN_ID_PATTERN = re.compile(r"run-[0-9a-f]{16}")
EXPECTED_FILES = set(load_contract().value["run_artifacts"])


@dataclass(frozen=True)
class VerificationResult:
    state: str
    run_id: str
    file_count: int


def verify_synthetic_run(
    *,
    fixture_path: Path,
    config_path: Path,
    run_directory: Path,
) -> VerificationResult:
    run_id = run_directory.name
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("invalid_run_id")
    try:
        actual_names = set(run_directory.iterdir())
    except OSError:
        raise ValueError("invalid_run_tree") from None
    if {path.name for path in actual_names} != EXPECTED_FILES:
        raise ValueError("invalid_run_tree")

    fixture_bytes = read_regular_input(
        fixture_path.parent,
        fixture_path.name,
        max_bytes=16_777_216,
    )
    config_bytes = read_regular_input(
        config_path.parent,
        config_path.name,
        max_bytes=16_777_216,
    )
    actual = {
        name: read_regular_input(run_directory, name, max_bytes=67_108_864)
        for name in sorted(EXPECTED_FILES)
    }

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        fixture_copy = root / "fixture.json"
        config_copy = root / "config.json"
        fixture_copy.write_bytes(fixture_bytes)
        config_copy.write_bytes(config_bytes)
        expected_root = root / "expected"
        expected_root.mkdir(mode=0o700)
        expected_summary = run_synthetic(fixture_copy, config_copy, expected_root)
        if expected_summary.run_id != run_id:
            raise ValueError("stale_receipt")
        expected_directory = expected_root / expected_summary.run_id
        expected = {
            name: (expected_directory / name).read_bytes()
            for name in sorted(EXPECTED_FILES)
        }
    if actual != expected:
        raise ValueError("stale_receipt")
    return VerificationResult(state="verified", run_id=run_id, file_count=len(EXPECTED_FILES))
