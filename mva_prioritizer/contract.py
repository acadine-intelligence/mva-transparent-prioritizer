from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "schemas" / "harness-v1.json"
EXPECTED_TOP_FIELDS = {
    "dossier",
    "manifest",
    "method_version",
    "privacy_scan",
    "public_source_scan",
    "run_artifacts",
    "run_receipt",
    "safe_learning",
    "schema_version",
    "scoring_config",
    "synthetic_fixture",
}


class _DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class HarnessContract:
    value: dict[str, Any]
    sha256: str


def load_contract() -> HarnessContract:
    metadata = CONTRACT_PATH.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1_048_576:
        raise ValueError("invalid_contract")
    payload = CONTRACT_PATH.read_bytes()
    try:
        value = json.loads(payload, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError("invalid_contract") from None
    if (
        not isinstance(value, dict)
        or set(value) != EXPECTED_TOP_FIELDS
        or value["schema_version"] != 1
        or value["method_version"] != "transparent-review-v1"
        or value["run_artifacts"]
        != [
            "dossier.json",
            "dossier.md",
            "receipt.json",
            "run.json",
            "safe-learnings.json",
        ]
        or value["safe_learning"].get("output_name") != "safe-learnings.json"
        or set(value["public_source_scan"])
        != {
            "allowed_names",
            "content_rules",
            "denied_name_prefixes",
            "denied_names",
            "denied_path_segments",
            "denied_suffixes",
            "max_git_listing_bytes",
        }
        or set(value["public_source_scan"]["content_rules"])
        != {
            "aws_access_key",
            "bearer_token",
            "openai_style_key",
            "private_key",
            "source_machine_path",
        }
    ):
        raise ValueError("invalid_contract")
    return HarnessContract(value=value, sha256=hashlib.sha256(payload).hexdigest())


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateKeyError
        value[key] = item
    return value
