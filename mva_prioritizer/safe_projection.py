from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .contract import load_contract
from .paths import read_regular_input, validate_root_pair


METHOD_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
CONTRACT = load_contract().value
SAFE_LEARNING_CONTRACT = CONTRACT["safe_learning"]
PRIVACY_CONTRACT = CONTRACT["privacy_scan"]


class _DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectionResult:
    state: str
    external_actions: int
    output_name: str


def read_forbidden_values(private_root: Path, relative_path: str) -> tuple[bytes, ...]:
    payload = read_regular_input(private_root, relative_path, max_bytes=1_048_576)
    try:
        value = json.loads(payload, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError("invalid_forbidden_values") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "values"}
        or value["schema_version"] != 1
        or not isinstance(value["values"], list)
        or not 0 < len(value["values"]) <= PRIVACY_CONTRACT["max_forbidden_values"]
    ):
        raise ValueError("invalid_forbidden_values")
    encoded: list[bytes] = []
    for item in value["values"]:
        if not isinstance(item, str):
            raise ValueError("invalid_forbidden_values")
        raw = item.encode("utf-8")
        if not raw or len(raw) > PRIVACY_CONTRACT["max_forbidden_value_bytes"] or raw in encoded:
            raise ValueError("invalid_forbidden_values")
        encoded.append(raw)
    return tuple(encoded)


def project_safe_learning(
    *,
    private_root: Path,
    source_relative_path: str,
    public_output_root: Path,
    forbidden_values: Iterable[bytes],
) -> ProjectionResult:
    roots = validate_root_pair(public_output_root, private_root)
    source = read_regular_input(roots.private_root, source_relative_path, max_bytes=1_048_576)
    try:
        value = json.loads(source, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError("invalid_safe_learning") from None
    _validate_safe_learning(value)
    output_bytes = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")
    for forbidden in forbidden_values:
        if (
            not isinstance(forbidden, bytes)
            or not forbidden
            or len(forbidden) > PRIVACY_CONTRACT["max_forbidden_value_bytes"]
        ):
            raise ValueError("invalid_forbidden_value")
        if forbidden in output_bytes:
            raise ValueError("privacy_blocked")
    output_name = SAFE_LEARNING_CONTRACT["output_name"]
    output_path = roots.public_root / output_name
    temporary = roots.public_root / (output_name + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(output_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        try:
            os.link(temporary, output_path, follow_symlinks=False)
        except FileExistsError:
            raise ValueError("output_exists") from None
    finally:
        temporary.unlink(missing_ok=True)
    return ProjectionResult(state="projected", external_actions=0, output_name=output_name)


def _validate_safe_learning(value: Any) -> None:
    expected = set(SAFE_LEARNING_CONTRACT["top_fields"])
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("invalid_safe_learning")
    if (
        value["schema_version"] != 1
        or value["external_actions"] != 0
        or not _is_count(value["finding_count"])
        or not _is_count(value["warning_count"])
        or not isinstance(value["synthetic"], bool)
        or value["state"] not in set(SAFE_LEARNING_CONTRACT["states"])
        or not isinstance(value["method_version"], str)
        or METHOD_PATTERN.fullmatch(value["method_version"]) is None
    ):
        raise ValueError("invalid_safe_learning")
    type_counts = value["finding_type_counts"]
    if (
        not isinstance(type_counts, dict)
        or not set(type_counts).issubset(set(SAFE_LEARNING_CONTRACT["finding_type_keys"]))
        or any(not _is_count(count) for count in type_counts.values())
        or sum(type_counts.values()) != value["finding_count"]
    ):
        raise ValueError("invalid_safe_learning")


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result
