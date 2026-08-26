from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .contract import load_contract
from .paths import PathSecurityError, read_regular_input, validate_directory_root


PRIVACY_CONTRACT = load_contract().value["privacy_scan"]
MAX_FILE_BYTES = PRIVACY_CONTRACT["max_file_bytes"]
MAX_TREE_BYTES = PRIVACY_CONTRACT["max_tree_bytes"]
MAX_FILES = PRIVACY_CONTRACT["max_files"]


@dataclass(frozen=True)
class PrivacyScanResult:
    state: str
    file_count: int
    byte_count: int
    external_actions: int


def scan_public_tree(
    *,
    public_root: Path,
    forbidden_values: Iterable[bytes],
) -> PrivacyScanResult:
    forbidden = tuple(forbidden_values)
    if (
        not 0 < len(forbidden) <= PRIVACY_CONTRACT["max_forbidden_values"]
        or any(
            not isinstance(value, bytes)
            or not value
            or len(value) > PRIVACY_CONTRACT["max_forbidden_value_bytes"]
            for value in forbidden
        )
    ):
        raise ValueError("invalid_forbidden_values")
    try:
        root = validate_directory_root(public_root)
    except (OSError, PathSecurityError):
        raise ValueError("unsafe_public_tree") from None

    file_count = 0
    byte_count = 0

    def walk_error(_: OSError) -> None:
        raise ValueError("unsafe_public_tree")

    for current, directory_names, file_names in os.walk(
        root,
        topdown=True,
        onerror=walk_error,
        followlinks=False,
    ):
        directory_names.sort()
        file_names.sort()
        current_path = Path(current)
        for name in directory_names:
            node = current_path / name
            try:
                mode = node.lstat().st_mode
            except OSError:
                raise ValueError("unsafe_public_tree") from None
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ValueError("unsafe_public_tree")
        for name in file_names:
            node = current_path / name
            try:
                metadata = node.lstat()
            except OSError:
                raise ValueError("unsafe_public_tree") from None
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("unsafe_public_tree")
            if metadata.st_size > MAX_FILE_BYTES:
                raise ValueError("scan_limit")
            file_count += 1
            if file_count > MAX_FILES:
                raise ValueError("scan_limit")
            relative_path = node.relative_to(root).as_posix()
            try:
                payload = read_regular_input(root, relative_path, max_bytes=MAX_FILE_BYTES)
            except PathSecurityError:
                raise ValueError("unsafe_public_tree") from None
            byte_count += len(payload)
            if byte_count > MAX_TREE_BYTES:
                raise ValueError("scan_limit")
            if any(value in payload for value in forbidden):
                raise ValueError("privacy_blocked")
    return PrivacyScanResult(
        state="clear",
        file_count=file_count,
        byte_count=byte_count,
        external_actions=0,
    )
