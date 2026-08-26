from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contract import load_contract
from .paths import PathSecurityError, read_regular_input, validate_relative_path


SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9._+-]{0,63}")
MANIFEST_CONTRACT = load_contract().value["manifest"]


class _DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class ManifestValidation:
    state: str
    run_kind: str
    artifact_count: int
    sample_count: int
    manifest_sha256: str


def validate_manifest(
    private_root: Path,
    manifest_relative_path: str,
    *,
    expected_run_kind: str,
) -> ManifestValidation:
    manifest_bytes = read_regular_input(private_root, manifest_relative_path, max_bytes=1_048_576)
    try:
        manifest = json.loads(manifest_bytes, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError("invalid_manifest") from None
    expected_fields = set(MANIFEST_CONTRACT["top_fields"])
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise ValueError("invalid_manifest")
    if (
        manifest["schema_version"] != 1
        or manifest["run_kind"] not in set(MANIFEST_CONTRACT["run_kinds"])
        or manifest["assembly"] != MANIFEST_CONTRACT["assembly"]
        or not _is_integer(manifest["sample_count"])
        or manifest["sample_count"] != MANIFEST_CONTRACT["sample_count"]
    ):
        raise ValueError("invalid_manifest")
    if manifest["run_kind"] != expected_run_kind:
        raise ValueError("run_kind_mismatch")
    expected_artifact_fields = set(MANIFEST_CONTRACT["artifact_fields"])
    if not isinstance(manifest["artifacts"], list) or not manifest["artifacts"]:
        raise ValueError("invalid_manifest")
    names: set[str] = set()
    paths: set[str] = set()
    for artifact in manifest["artifacts"]:
        if not isinstance(artifact, dict) or set(artifact) != expected_artifact_fields:
            raise ValueError("invalid_manifest")
        if not _valid_artifact(artifact, manifest["run_kind"]):
            raise ValueError("invalid_manifest")
        if artifact["name"] in names or artifact["relative_path"] in paths:
            raise ValueError("invalid_manifest")
        names.add(artifact["name"])
        paths.add(artifact["relative_path"])

    expected_tool_fields = set(MANIFEST_CONTRACT["tool_fields"])
    if not isinstance(manifest["tools"], list) or not manifest["tools"]:
        raise ValueError("invalid_manifest")
    tool_names: set[str] = set()
    for tool in manifest["tools"]:
        if not isinstance(tool, dict) or set(tool) != expected_tool_fields:
            raise ValueError("invalid_manifest")
        if (
            not _valid_token(tool["name"])
            or tool["name"] in tool_names
            or not _valid_version(tool["version"])
            or not _valid_sha256(tool["binary_sha256"])
        ):
            raise ValueError("invalid_manifest")
        tool_names.add(tool["name"])

    for artifact in manifest["artifacts"]:
        try:
            content = read_regular_input(private_root, artifact["relative_path"], max_bytes=artifact["bytes"])
        except PathSecurityError as exc:
            if str(exc) in {"input_unavailable", "path_changed", "size_limit"}:
                raise ValueError("stale_receipt") from None
            raise
        if len(content) != artifact["bytes"]:
            raise ValueError("stale_receipt")
        if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
            raise ValueError("stale_receipt")
    return ManifestValidation(
        state="validated",
        run_kind=manifest["run_kind"],
        artifact_count=len(manifest["artifacts"]),
        sample_count=manifest["sample_count"],
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


def _valid_artifact(artifact: dict[str, Any], run_kind: str) -> bool:
    if not _valid_token(artifact["name"]) or not _valid_token(artifact["format"]):
        return False
    if artifact["class"] not in set(MANIFEST_CONTRACT["artifact_classes"]):
        return False
    allowed_privacy = set(MANIFEST_CONTRACT["privacy_by_run_kind"][run_kind])
    if artifact["privacy_class"] not in allowed_privacy:
        return False
    if not _is_integer(artifact["bytes"]) or artifact["bytes"] < 0:
        return False
    if not _valid_sha256(artifact["sha256"]):
        return False
    try:
        validate_relative_path(artifact["relative_path"])
    except PathSecurityError:
        return False
    return True


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _valid_token(value: Any) -> bool:
    return isinstance(value, str) and TOKEN_PATTERN.fullmatch(value) is not None


def _valid_version(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value.encode("utf-8")) <= 128
        and all(32 <= ord(character) <= 126 for character in value)
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result
