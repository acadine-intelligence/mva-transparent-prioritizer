from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .contract import load_contract
from .paths import PathSecurityError, read_regular_input, validate_directory_root


CONTRACT = load_contract().value
SOURCE_SCAN_CONTRACT = CONTRACT["public_source_scan"]
PRIVACY_CONTRACT = CONTRACT["privacy_scan"]


@dataclass(frozen=True)
class PublicSourceScanResult:
    state: str
    file_count: int
    byte_count: int
    external_actions: int


def scan_public_source_tree(public_root: Path) -> PublicSourceScanResult:
    try:
        root = validate_directory_root(public_root)
    except (OSError, PathSecurityError):
        raise ValueError("unsafe_public_tree") from None

    try:
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise ValueError("source_scan_unavailable") from None
    if (
        completed.returncode != 0
        or completed.stderr
        or len(completed.stdout) > SOURCE_SCAN_CONTRACT["max_git_listing_bytes"]
    ):
        raise ValueError("source_scan_unavailable")

    raw_paths = [item for item in completed.stdout.split(b"\0") if item]
    if len(raw_paths) > PRIVACY_CONTRACT["max_files"] or len(set(raw_paths)) != len(raw_paths):
        raise ValueError("scan_limit")

    try:
        relative_paths = sorted(item.decode("utf-8") for item in raw_paths)
    except UnicodeDecodeError:
        raise ValueError("unsafe_public_tree") from None

    byte_count = 0
    for relative_path in relative_paths:
        _validate_public_name(relative_path)
        try:
            payload = read_regular_input(
                root,
                relative_path,
                max_bytes=PRIVACY_CONTRACT["max_file_bytes"],
            )
        except PathSecurityError:
            raise ValueError("unsafe_public_tree") from None
        byte_count += len(payload)
        if byte_count > PRIVACY_CONTRACT["max_tree_bytes"]:
            raise ValueError("scan_limit")
        if _contains_blocked_content(payload):
            raise ValueError("privacy_blocked")

    return PublicSourceScanResult(
        state="clear",
        file_count=len(relative_paths),
        byte_count=byte_count,
        external_actions=0,
    )


def _validate_public_name(relative_path: str) -> None:
    path = Path(relative_path)
    name = path.name.lower()
    allowed_names = set(SOURCE_SCAN_CONTRACT["allowed_names"])
    if name not in allowed_names and (
        name in SOURCE_SCAN_CONTRACT["denied_names"]
        or any(name.startswith(prefix) for prefix in SOURCE_SCAN_CONTRACT["denied_name_prefixes"])
    ):
        raise ValueError("privacy_blocked")
    if any(name.endswith(suffix) for suffix in SOURCE_SCAN_CONTRACT["denied_suffixes"]):
        raise ValueError("privacy_blocked")
    if any(part.lower() in SOURCE_SCAN_CONTRACT["denied_path_segments"] for part in path.parts):
        raise ValueError("privacy_blocked")


def _contains_blocked_content(payload: bytes) -> bool:
    rules = set(SOURCE_SCAN_CONTRACT["content_rules"])
    checks = {
        "aws_access_key": re.compile(b"AKIA" + rb"[0-9A-Z]{16}").search,
        "bearer_token": re.compile(b"Bearer" + rb"[ \t]+[A-Za-z0-9._~+/=-]{20,}").search,
        "openai_style_key": re.compile(
            rb"(?<![A-Za-z0-9])" + b"sk-" + rb"[A-Za-z0-9_-]{20,}"
        ).search,
        "private_key": re.compile(
            b"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?" + b"PRIVATE KEY-----"
        ).search,
        "source_machine_path": lambda value: any(
            signature in value
            for signature in (
                b"/" + b"Users" + b"/",
                b"/" + b"Volumes" + b"/",
                b"C:" + b"\\" + b"Users" + b"\\",
            )
        ),
    }
    return any(checks[rule](payload) for rule in rules)
