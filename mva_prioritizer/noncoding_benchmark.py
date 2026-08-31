from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional


MAX_JSON_BYTES = 1024 * 1024
METHOD_VERSION = "genomiser-noncoding-benchmark-v1"

EXPECTED_CONFIG: dict[str, Any] = {
    "analysis_mode": "PASS_ONLY",
    "assembly": "GRCh38",
    "clinical_probability": False,
    "coding_lane_immutable": True,
    "frequency_max_percent": "2.0",
    "hidden_top_n": None,
    "keep_non_pathogenic": False,
    "low_vaf_review_lane": True,
    "method_version": METHOD_VERSION,
    "pathogenicity_sources": [
        "REVEL",
        "MVP",
        "ALPHA_MISSENSE",
        "REMM",
        "SPLICE_AI",
    ],
    "pathogenicity_target": "NON_CODING",
    "priority_score_min": "0.501",
    "private_execution_authorized": False,
    "schema_version": 1,
    "step_order": [
        "hiPhivePrioritiser",
        "priorityScoreFilter",
        "geneBlacklistFilter",
        "failedVariantFilter",
        "alleleBalanceFilter",
        "regulatoryFeatureFilter",
        "frequencyFilter",
        "pathogenicityFilter",
        "inheritanceFilter",
        "omimPrioritiser",
    ],
    "thresholds": {"remm": "0.914", "spliceai": "0.1"},
}

EXPECTED_EXOMISER = {
    "cli_sha256": "47faa54d4791686c9dc3f896762834630e9eaf607ad3cf3399074353c3dda248",
    "cli_version": "15.1.0",
    "genome_data_sha256": "2ed14f8b63b5612068591648d8c3c6e34ce9d1c66c08a78990597f78031df447",
    "genome_data_version": "2602_hg38",
    "phenotype_data_sha256": "aa923530ca43cf5051ed2ba7b221bb73deb2b0dd66695b2ba60460db052f0493",
    "phenotype_data_version": "2602",
    "spliceai_source_state": "bundled-unverified",
}

EXPECTED_ARTIFACTS = [
    {
        "acquisition_authorized": False,
        "expected_bytes": 15_967_302_704,
        "expected_sha256": None,
        "filename": "ReMM.v0.4.hg38.tsv.gz",
        "license": "CC0-1.0",
        "name": "remm-data",
        "source_checksum": {
            "algorithm": "md5",
            "value": "2f8c8fcc75ea29f6798621d0446fe194",
        },
        "source_url": "https://kircherlab.bihealth.org/download/ReMM/ReMM.v0.4.hg38.tsv.gz",
        "version": "0.4",
    },
    {
        "acquisition_authorized": False,
        "expected_bytes": 2_755_625,
        "expected_sha256": None,
        "filename": "ReMM.v0.4.hg38.tsv.gz.tbi",
        "license": "CC0-1.0",
        "name": "remm-index",
        "source_checksum": {
            "algorithm": "md5",
            "value": "c477b123abbe72c4aa66bf3abc18d9ab",
        },
        "source_url": "https://kircherlab.bihealth.org/download/ReMM/ReMM.v0.4.hg38.tsv.gz.tbi",
        "version": "0.4",
    },
]

EXPECTED_CASES = (
    ("SYNTHETIC_NC_01", "coding_retention"),
    ("SYNTHETIC_NC_02", "splice_rescue"),
    ("SYNTHETIC_NC_03", "remm_rescue"),
    ("SYNTHETIC_NC_04", "decoy_preserves_evidence"),
    ("SYNTHETIC_NC_05", "exonic_discordance"),
    ("SYNTHETIC_NC_06", "compound_pair"),
    ("SYNTHETIC_NC_07", "low_vaf_review"),
    ("SYNTHETIC_NC_08", "missing_remm"),
    ("SYNTHETIC_NC_09", "assembly_mismatch"),
    ("SYNTHETIC_NC_10", "digest_mismatch"),
    ("SYNTHETIC_NC_11", "missing_spliceai"),
    ("SYNTHETIC_NC_12", "threshold_boundaries"),
    ("SYNTHETIC_NC_13", "deterministic_replay"),
    ("SYNTHETIC_NC_14", "canary_absence"),
)

ALLOWED_OUTCOMES = {
    "absent",
    "boundaries_match",
    "byte_identical",
    "failed_closed",
    "missing_visible",
    "noncoding_candidate",
    "pair_preserved",
    "preserved",
    "retained",
    "review",
}

SYNVAR_PATTERN = re.compile(r"SYNVAR_[A-Z0-9_]+")
SYNGENE_PATTERN = re.compile(r"SYNGENE_[A-Z0-9_]+")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class NoncodingAcquisitionArtifact:
    name: str
    version: str
    filename: str
    source_url: str
    expected_bytes: int
    source_checksum_algorithm: str
    source_checksum_value: str
    expected_sha256: Optional[str]
    license: str
    acquisition_authorized: bool


@dataclass(frozen=True)
class NoncodingAcquisitionManifest:
    state: str
    assembly: str
    artifacts: tuple[NoncodingAcquisitionArtifact, ...]
    acquisition_authorized: bool
    private_execution_authorized: bool
    direct_spliceai_acquisition: bool

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def pin_required_count(self) -> int:
        return sum(artifact.expected_sha256 is None for artifact in self.artifacts)


@dataclass(frozen=True)
class NoncodingBenchmarkSummary:
    state: str
    run_id: str
    case_count: int
    passed_case_count: int
    external_actions: int
    private_execution_authorized: bool


class _DuplicateKeyError(ValueError):
    pass


def load_noncoding_acquisition_manifest(path: Path) -> NoncodingAcquisitionManifest:
    _, value = _load_json_file(Path(path), "invalid_noncoding_acquisition_manifest")
    return _parse_acquisition_manifest(value)


def run_noncoding_benchmark(
    fixture_path: Path,
    config_path: Path,
    acquisition_manifest_path: Path,
    output_root: Path,
) -> NoncodingBenchmarkSummary:
    fixture_bytes, fixture = _load_json_file(
        Path(fixture_path),
        "invalid_noncoding_fixture",
    )
    config_bytes, config = _load_json_file(
        Path(config_path),
        "invalid_noncoding_config",
    )
    acquisition_bytes, acquisition_value = _load_json_file(
        Path(acquisition_manifest_path),
        "invalid_noncoding_acquisition_manifest",
    )

    _validate_config(config)
    acquisition = _parse_acquisition_manifest(acquisition_value)
    if acquisition.acquisition_authorized or acquisition.private_execution_authorized:
        raise ValueError("invalid_noncoding_acquisition_manifest")
    _validate_fixture(fixture, config)
    _validate_output_root(Path(output_root))

    case_results = []
    for case in fixture["cases"]:
        observed_outcome, details = _evaluate_case(case, config)
        case_results.append(
            {
                "case_id": case["case_id"],
                "details": details,
                "expected_outcome": case["expected_outcome"],
                "observed_outcome": observed_outcome,
                "passed": observed_outcome == case["expected_outcome"],
                "scenario": case["scenario"],
            }
        )

    passed_case_count = sum(row["passed"] for row in case_results)
    case_count = len(case_results)
    state = "ready_for_tool_smoke" if passed_case_count == case_count else "benchmark_failed"

    run_seed = {
        "acquisition_manifest": acquisition_value,
        "config": config,
        "fixture": fixture,
        "method_version": METHOD_VERSION,
    }
    run_id = "benchmark-" + hashlib.sha256(_json_bytes(run_seed)).hexdigest()[:16]
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(run_dir, 0o700)

    config_sha256 = hashlib.sha256(config_bytes).hexdigest()
    acquisition_sha256 = hashlib.sha256(acquisition_bytes).hexdigest()
    report = {
        "acquisition_manifest_sha256": acquisition_sha256,
        "cases": case_results,
        "clinical_probability": False,
        "config_sha256": config_sha256,
        "external_actions": 0,
        "hidden_top_n": None,
        "method_version": METHOD_VERSION,
        "private_execution_authorized": False,
        "schema_version": 1,
        "state": state,
        "synthetic": True,
    }
    public = {
        "case_count": case_count,
        "external_actions": 0,
        "passed_case_count": passed_case_count,
        "private_execution_authorized": False,
        "schema_version": 1,
        "state": state,
        "synthetic": True,
    }

    outputs = {
        "benchmark-public.json": _json_bytes(public),
        "benchmark-report.json": _json_bytes(report),
    }
    for name, content in sorted(outputs.items()):
        _write_readonly(run_dir / name, content)

    receipt = {
        "inputs": {
            "acquisition-manifest.json": acquisition_sha256,
            "config.json": config_sha256,
            "synthetic-benchmark-cases.json": hashlib.sha256(fixture_bytes).hexdigest(),
        },
        "method_version": METHOD_VERSION,
        "outputs": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(outputs.items())
        },
        "run_id": run_id,
        "schema_version": 1,
        "state": state,
        "synthetic": True,
    }
    receipt_bytes = _json_bytes(receipt)
    _write_readonly(run_dir / "receipt.json", receipt_bytes)
    _verify_output_tree(run_dir, {**outputs, "receipt.json": receipt_bytes})

    return NoncodingBenchmarkSummary(
        state=state,
        run_id=run_id,
        case_count=case_count,
        passed_case_count=passed_case_count,
        external_actions=0,
        private_execution_authorized=False,
    )


def _validate_config(value: Any) -> None:
    if value != EXPECTED_CONFIG:
        raise ValueError("invalid_noncoding_config")


def _parse_acquisition_manifest(value: Any) -> NoncodingAcquisitionManifest:
    expected_fields = {
        "artifacts",
        "assembly",
        "direct_spliceai_acquisition",
        "exomiser",
        "network_during_private_run",
        "private_execution_authorized",
        "redistribution_authorized",
        "schema_version",
        "state",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected_fields
        or value.get("schema_version") != 1
        or value.get("state") != "proposal"
        or value.get("assembly") != "GRCh38"
        or value.get("private_execution_authorized") is not False
        or value.get("network_during_private_run") is not False
        or value.get("direct_spliceai_acquisition") is not False
        or value.get("redistribution_authorized") is not False
        or value.get("exomiser") != EXPECTED_EXOMISER
        or value.get("artifacts") != EXPECTED_ARTIFACTS
    ):
        raise ValueError("invalid_noncoding_acquisition_manifest")

    artifacts = tuple(
        NoncodingAcquisitionArtifact(
            name=row["name"],
            version=row["version"],
            filename=row["filename"],
            source_url=row["source_url"],
            expected_bytes=row["expected_bytes"],
            source_checksum_algorithm=row["source_checksum"]["algorithm"],
            source_checksum_value=row["source_checksum"]["value"],
            expected_sha256=row["expected_sha256"],
            license=row["license"],
            acquisition_authorized=row["acquisition_authorized"],
        )
        for row in value["artifacts"]
    )
    return NoncodingAcquisitionManifest(
        state=value["state"],
        assembly=value["assembly"],
        artifacts=artifacts,
        acquisition_authorized=any(row.acquisition_authorized for row in artifacts),
        private_execution_authorized=value["private_execution_authorized"],
        direct_spliceai_acquisition=value["direct_spliceai_acquisition"],
    )


def _validate_fixture(value: Any, config: dict[str, Any]) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"cases", "schema_version", "suite_id", "synthetic"}
        or value.get("schema_version") != 1
        or value.get("suite_id") != "SYNTHETIC_NONCODING_BENCHMARK_V1"
        or value.get("synthetic") is not True
        or not isinstance(value.get("cases"), list)
        or len(value["cases"]) != len(EXPECTED_CASES)
    ):
        raise ValueError("invalid_noncoding_fixture")

    for case, expected_identity in zip(value["cases"], EXPECTED_CASES):
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "expected_outcome", "input", "scenario"}
            or (case.get("case_id"), case.get("scenario")) != expected_identity
            or case.get("expected_outcome") not in ALLOWED_OUTCOMES
            or not isinstance(case.get("input"), dict)
        ):
            raise ValueError("invalid_noncoding_fixture")
        _evaluate_case(case, config)


def _evaluate_case(
    case: dict[str, Any],
    config: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    scenario = case["scenario"]
    value = case["input"]
    spliceai_threshold = Decimal(config["thresholds"]["spliceai"])
    remm_threshold = Decimal(config["thresholds"]["remm"])

    if scenario == "coding_retention":
        _require_fields(value, {"lane", "preset_target"})
        outcome = (
            "retained"
            if value["lane"] == "coding" and value["preset_target"] == "NON_CODING"
            else "lost"
        )
        return outcome, {"coding_lane_retained": outcome == "retained"}

    if scenario == "splice_rescue":
        _require_fields(value, {"region", "spliceai_score"})
        score = _score(value["spliceai_score"])
        passed = value["region"] == "deep_intronic" and score > spliceai_threshold
        return (
            "noncoding_candidate" if passed else "filtered",
            {"strict_threshold_pass": passed},
        )

    if scenario == "remm_rescue":
        _require_fields(value, {"region", "remm_score"})
        score = _score(value["remm_score"])
        passed = value["region"] == "regulatory" and score > remm_threshold
        return (
            "noncoding_candidate" if passed else "filtered",
            {"strict_threshold_pass": passed},
        )

    if scenario == "decoy_preserves_evidence":
        _require_fields(value, {"reported_ids", "required_ids"})
        reported = _synthetic_variant_ids(value["reported_ids"], minimum=2)
        required = _synthetic_variant_ids(value["required_ids"], minimum=1)
        preserved = required.issubset(reported)
        return "preserved" if preserved else "evidence_lost", {"required_ids_present": preserved}

    if scenario == "exonic_discordance":
        _require_fields(value, {"predictor_relation", "region", "spliceai_score"})
        _score(value["spliceai_score"])
        review = value["region"] == "exonic" and value["predictor_relation"] == "discordant"
        return "review" if review else "resolved", {"discordance_visible": review}

    if scenario == "compound_pair":
        _require_fields(value, {"gene", "phase", "variants"})
        gene = value["gene"]
        variants = value["variants"]
        if not isinstance(gene, str) or SYNGENE_PATTERN.fullmatch(gene) is None:
            raise ValueError("invalid_noncoding_fixture")
        if not isinstance(variants, list) or len(variants) != 2:
            raise ValueError("invalid_noncoding_fixture")
        identifiers: set[str] = set()
        lanes: set[str] = set()
        for variant in variants:
            _require_fields(variant, {"lane", "variant_id"})
            variant_id = variant["variant_id"]
            if not isinstance(variant_id, str) or SYNVAR_PATTERN.fullmatch(variant_id) is None:
                raise ValueError("invalid_noncoding_fixture")
            identifiers.add(variant_id)
            lanes.add(variant["lane"])
        preserved = (
            len(identifiers) == 2
            and lanes == {"coding", "noncoding"}
            and value["phase"] == "unknown"
        )
        return "pair_preserved" if preserved else "pair_lost", {"pair_visible": preserved}

    if scenario == "low_vaf_review":
        _require_fields(value, {"preset_balance_pass", "review_lane_present"})
        if not isinstance(value["preset_balance_pass"], bool) or not isinstance(
            value["review_lane_present"], bool
        ):
            raise ValueError("invalid_noncoding_fixture")
        review = not value["preset_balance_pass"] and value["review_lane_present"]
        return "review" if review else "filtered", {"review_lane_present": review}

    if scenario == "missing_remm":
        _require_fields(value, {"data_present", "index_present"})
        if not isinstance(value["data_present"], bool) or not isinstance(
            value["index_present"], bool
        ):
            raise ValueError("invalid_noncoding_fixture")
        failed_closed = not (value["data_present"] and value["index_present"])
        return "failed_closed" if failed_closed else "ready", {"failed_closed": failed_closed}

    if scenario == "assembly_mismatch":
        _require_fields(value, {"expected", "observed"})
        if not all(isinstance(value[key], str) and value[key] for key in ("expected", "observed")):
            raise ValueError("invalid_noncoding_fixture")
        mismatch = value["expected"] != value["observed"]
        return "failed_closed" if mismatch else "ready", {"assembly_mismatch": mismatch}

    if scenario == "digest_mismatch":
        _require_fields(value, {"expected", "observed"})
        if not all(
            isinstance(value[key], str) and SHA256_PATTERN.fullmatch(value[key]) is not None
            for key in ("expected", "observed")
        ):
            raise ValueError("invalid_noncoding_fixture")
        mismatch = value["expected"] != value["observed"]
        return "failed_closed" if mismatch else "ready", {"digest_mismatch": mismatch}

    if scenario == "missing_spliceai":
        _require_fields(value, {"missing_policy", "score"})
        if value["score"] is None and value["missing_policy"] == "explicit":
            return "missing_visible", {"score_state": "missing"}
        _score(value["score"])
        return "score_present", {"score_state": "present"}

    if scenario == "threshold_boundaries":
        _require_fields(value, {"remm", "spliceai"})
        spliceai_scores = _score_list(value["spliceai"])
        remm_scores = _score_list(value["remm"])
        spliceai_pass = [score > spliceai_threshold for score in spliceai_scores]
        remm_pass = [score > remm_threshold for score in remm_scores]
        expected = [False, False, True]
        matches = spliceai_pass == expected and remm_pass == expected
        return (
            "boundaries_match" if matches else "boundary_mismatch",
            {"remm_pass": remm_pass, "spliceai_pass": spliceai_pass},
        )

    if scenario == "deterministic_replay":
        _require_fields(value, {"payload", "replays"})
        if not isinstance(value["payload"], dict) or not isinstance(value["replays"], int):
            raise ValueError("invalid_noncoding_fixture")
        first = _json_bytes(value["payload"])
        second = _json_bytes(value["payload"])
        identical = value["replays"] == 2 and hashlib.sha256(first).digest() == hashlib.sha256(second).digest()
        return "byte_identical" if identical else "replay_drift", {"byte_identical": identical}

    if scenario == "canary_absence":
        _require_fields(value, {"canary", "projection"})
        canary = value["canary"]
        if (
            not isinstance(canary, str)
            or not canary.startswith("SYNTHETIC_")
            or not isinstance(value["projection"], dict)
        ):
            raise ValueError("invalid_noncoding_fixture")
        absent = canary.encode("utf-8") not in _json_bytes(value["projection"])
        return "absent" if absent else "present", {"canary_present": not absent}

    raise ValueError("invalid_noncoding_fixture")


def _require_fields(value: Any, expected: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("invalid_noncoding_fixture")


def _score(value: Any) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("invalid_noncoding_fixture")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid_noncoding_fixture") from None
    if not parsed.is_finite() or parsed < 0 or parsed > 1:
        raise ValueError("invalid_noncoding_fixture")
    return parsed


def _score_list(value: Any) -> list[Decimal]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("invalid_noncoding_fixture")
    return [_score(item) for item in value]


def _synthetic_variant_ids(value: Any, minimum: int) -> set[str]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError("invalid_noncoding_fixture")
    identifiers: set[str] = set()
    for item in value:
        if not isinstance(item, str) or SYNVAR_PATTERN.fullmatch(item) is None:
            raise ValueError("invalid_noncoding_fixture")
        identifiers.add(item)
    if len(identifiers) != len(value):
        raise ValueError("invalid_noncoding_fixture")
    return identifiers


def _validate_output_root(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError:
        raise ValueError("invalid_noncoding_output_root") from None
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError("invalid_noncoding_output_root")


def _load_json_file(path: Path, error_code: str) -> tuple[bytes, Any]:
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size <= 0
            or metadata.st_size > MAX_JSON_BYTES
        ):
            raise ValueError(error_code)
        payload = path.read_bytes()
    except ValueError:
        raise
    except OSError:
        raise ValueError(error_code) from None
    if len(payload) != metadata.st_size:
        raise ValueError(error_code)
    return payload, _load_unique_json(payload, error_code)


def _load_unique_json(payload: bytes, error_code: str) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise _DuplicateKeyError
            value[key] = item
        return value

    try:
        return json.loads(payload, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKeyError):
        raise ValueError(error_code) from None


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_readonly(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    os.chmod(path, 0o400)
    if path.read_bytes() != content or stat.S_IMODE(path.stat().st_mode) != 0o400:
        raise RuntimeError("noncoding_output_readback_failed")


def _verify_output_tree(run_dir: Path, expected: dict[str, bytes]) -> None:
    actual = {path.name for path in run_dir.iterdir()}
    if actual != set(expected):
        raise RuntimeError("noncoding_output_set_mismatch")
    for name, content in expected.items():
        path = run_dir / name
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o400
            or path.read_bytes() != content
        ):
            raise RuntimeError("noncoding_output_readback_failed")
