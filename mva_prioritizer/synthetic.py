from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from .contract import load_contract


CONTRACT = load_contract().value
SYNTHETIC_CONTRACT = CONTRACT["synthetic_fixture"]
SCORING_CONTRACT = CONTRACT["scoring_config"]
METHOD_VERSION = CONTRACT["method_version"]
REQUIRED_DISCLAIMER = SCORING_CONTRACT["required_disclaimer"]
CASE_ID_PATTERN = re.compile(SYNTHETIC_CONTRACT["case_id_pattern"])
FINDING_ID_PATTERN = re.compile(SYNTHETIC_CONTRACT["finding_id_pattern"])
SYNTHETIC_VARIANT_PATTERN = re.compile(SYNTHETIC_CONTRACT["variant_id_pattern"])
SYNTHETIC_GENE_PATTERN = re.compile(SYNTHETIC_CONTRACT["gene_pattern"])


@dataclass(frozen=True)
class RunSummary:
    state: str
    run_id: str
    finding_count: int
    external_actions: int


class _DuplicateKeyError(ValueError):
    pass


def run_synthetic(fixture_path: Path, config_path: Path, output_root: Path) -> RunSummary:
    fixture_bytes = fixture_path.read_bytes()
    config_bytes = config_path.read_bytes()
    fixture = _load_unique_json(fixture_bytes, "invalid_synthetic_fixture")
    config = _load_unique_json(config_bytes, "invalid_scoring_config")
    _validate_inputs(fixture, config)

    scored = [_score_finding(row, config) for row in fixture["findings"]]
    scored.sort(
        key=lambda row: (
            row["review_score"] is None,
            -Decimal(row["review_score"]) if row["review_score"] is not None else Decimal("0"),
            int(row["source_rank"]),
            row["finding_id"],
        )
    )
    state = "review_ready" if scored else "empty_result"

    run_seed = {
        "config": config,
        "fixture": fixture,
        "method_version": METHOD_VERSION,
    }
    run_id = "run-" + hashlib.sha256(_json_bytes(run_seed)).hexdigest()[:16]
    run_dir = output_root / run_id
    run_dir.mkdir(mode=0o700, parents=False, exist_ok=False)

    warning_count = sum(len(row["warnings"]) for row in scored)
    dossier = {
        "disclaimer": config["disclaimer"],
        "findings": scored,
        "method_version": METHOD_VERSION,
        "review_score_is_probability": False,
        "schema_version": 1,
        "state": state,
        "synthetic": True,
    }
    if not scored:
        dossier["next_analytical_gap"] = (
            "Review unresolved variant classes and coverage before requesting new source data."
        )
    type_counts: dict[str, int] = {}
    for row in scored:
        finding_type = row["finding_type"]
        type_counts[finding_type] = type_counts.get(finding_type, 0) + 1
    safe = {
        "external_actions": 0,
        "finding_count": len(scored),
        "finding_type_counts": type_counts,
        "method_version": METHOD_VERSION,
        "schema_version": 1,
        "state": state,
        "synthetic": True,
        "warning_count": warning_count,
    }
    run = {
        "external_actions": 0,
        "finding_count": len(scored),
        "method_version": METHOD_VERSION,
        "run_id": run_id,
        "schema_version": 1,
        "state": state,
        "synthetic": True,
        "warning_count": warning_count,
    }

    outputs = {
        "dossier.json": _json_bytes(dossier),
        "dossier.md": _render_markdown(dossier).encode("utf-8"),
        "run.json": _json_bytes(run),
        "safe-learnings.json": _json_bytes(safe),
    }
    for name, content in outputs.items():
        _write_private(run_dir / name, content)

    receipt = {
        "inputs": {
            "config.json": hashlib.sha256(config_bytes).hexdigest(),
            "synthetic-case.json": hashlib.sha256(fixture_bytes).hexdigest(),
        },
        "method_version": METHOD_VERSION,
        "outputs": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(outputs.items())
        },
        "run_id": run_id,
        "schema_version": 1,
        "synthetic": True,
    }
    _write_private(run_dir / "receipt.json", _json_bytes(receipt))

    return RunSummary(
        state=state,
        run_id=run_id,
        finding_count=len(scored),
        external_actions=0,
    )


def _validate_inputs(fixture: dict[str, Any], config: dict[str, Any]) -> None:
    expected_fixture_fields = set(SYNTHETIC_CONTRACT["top_fields"])
    if (
        not isinstance(fixture, dict)
        or set(fixture) != expected_fixture_fields
        or fixture.get("schema_version") != 1
        or fixture.get("synthetic") is not True
        or not isinstance(fixture.get("case_id"), str)
        or CASE_ID_PATTERN.fullmatch(fixture["case_id"]) is None
        or not isinstance(fixture.get("findings"), list)
    ):
        raise ValueError("invalid_synthetic_fixture")
    expected_config_fields = set(SCORING_CONTRACT["top_fields"])
    if (
        not isinstance(config, dict)
        or set(config) != expected_config_fields
        or config.get("schema_version") != 1
        or config.get("rule_set") != METHOD_VERSION
        or not _valid_scoring_config(config)
    ):
        raise ValueError("invalid_scoring_config")
    if not _valid_synthetic_findings(fixture["findings"], config):
        raise ValueError("invalid_synthetic_fixture")


def _score_finding(finding: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    required = {
        "clinical_evidence",
        "finding_id",
        "finding_type",
        "inheritance",
        "mva_relation",
        "phase",
        "phenotype_score",
        "population_frequency",
        "source_rank",
        "source_score",
        "variants",
    }
    if set(finding) != required:
        raise ValueError("invalid_finding_fields")
    variants = finding["variants"]
    expected_variants = 2 if finding["finding_type"] == "pair" else 1
    if not isinstance(variants, list) or len(variants) != expected_variants:
        raise ValueError("invalid_finding_shape")

    impact_values = config["impact_values"]
    impacts = [Decimal(impact_values[variant["impact"]]) for variant in variants]
    impact_score = sum(impacts, Decimal("0")) / Decimal(len(impacts))
    frequency = (
        None
        if finding["population_frequency"] is None
        else Decimal(finding["population_frequency"])
    )
    rarity_score = (
        None if frequency is None else _rarity_score(frequency, config["rarity_thresholds"])
    )
    phenotype_score = (
        None if finding["phenotype_score"] is None else Decimal(finding["phenotype_score"])
    )
    source_score = None if finding["source_score"] is None else Decimal(finding["source_score"])
    components: dict[str, Optional[Decimal]] = {
        "clinical_evidence": Decimal(config["clinical_values"][finding["clinical_evidence"]]),
        "impact": impact_score,
        "mva_relation": Decimal(config["mva_relation_values"][finding["mva_relation"]]),
        "phenotype_score": phenotype_score,
        "rarity": rarity_score,
        "source_score": source_score,
    }
    warnings: list[str] = []
    if finding["finding_type"] == "pair" and finding["phase"] == "unknown":
        warnings.append("phase_unresolved")
    if any(value is None for value in components.values()):
        score = None
        warnings.append("review_score_incomplete")
    else:
        score = sum(
            components[name] * Decimal(config["weights"][name])
            for name in config["weights"]
        ).quantize(Decimal("0.000001"))

    return {
        **finding,
        "review_score": None if score is None else format(score, "f"),
        "review_score_components": {
            name: None if value is None else format(value.quantize(Decimal("0.000001")), "f")
            for name, value in sorted(components.items())
        },
        "warnings": warnings,
    }


def _rarity_score(frequency: Decimal, thresholds: list[dict[str, str]]) -> Decimal:
    if frequency < 0 or frequency > 1:
        raise ValueError("invalid_population_frequency")
    for row in thresholds:
        if frequency <= Decimal(row["maximum_frequency"]):
            return Decimal(row["value"])
    raise ValueError("rarity_threshold_gap")


def _valid_scoring_config(config: dict[str, Any]) -> bool:
    if config["disclaimer"] != REQUIRED_DISCLAIMER:
        return False
    expected_weights = set(SCORING_CONTRACT["weight_fields"])
    weights = _unit_interval_map(config["weights"], expected_weights)
    impact_values = _unit_interval_map(
        config["impact_values"],
        set(SCORING_CONTRACT["impact_keys"]),
    )
    clinical_values = _unit_interval_map(
        config["clinical_values"],
        set(SCORING_CONTRACT["clinical_keys"]),
    )
    mva_values = _unit_interval_map(
        config["mva_relation_values"],
        set(SCORING_CONTRACT["mva_relation_keys"]),
    )
    if any(value is None for value in (weights, impact_values, clinical_values, mva_values)):
        return False
    if sum(weights.values(), Decimal("0")) != Decimal("1"):
        return False

    thresholds = config["rarity_thresholds"]
    if not isinstance(thresholds, list) or not thresholds:
        return False
    previous_maximum = Decimal("-1")
    previous_value = Decimal("2")
    for row in thresholds:
        if not isinstance(row, dict) or set(row) != {"maximum_frequency", "value"}:
            return False
        maximum = _unit_interval_decimal(row["maximum_frequency"])
        value = _unit_interval_decimal(row["value"])
        if (
            maximum is None
            or value is None
            or maximum <= previous_maximum
            or value > previous_value
        ):
            return False
        previous_maximum = maximum
        previous_value = value
    return previous_maximum == Decimal("1")


def _valid_synthetic_findings(findings: list[Any], config: dict[str, Any]) -> bool:
    expected_finding_fields = set(SYNTHETIC_CONTRACT["finding_fields"])
    expected_variant_fields = set(SYNTHETIC_CONTRACT["variant_fields"])
    finding_ids: set[str] = set()
    variant_ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != expected_finding_fields:
            return False
        finding_id = finding["finding_id"]
        if (
            not isinstance(finding_id, str)
            or FINDING_ID_PATTERN.fullmatch(finding_id) is None
            or finding_id in finding_ids
            or finding["finding_type"] not in set(SYNTHETIC_CONTRACT["finding_types"])
            or finding["inheritance"] not in set(SYNTHETIC_CONTRACT["inheritance_values"])
            or finding["clinical_evidence"] not in config["clinical_values"]
            or finding["mva_relation"] not in config["mva_relation_values"]
            or not _is_positive_integer(finding["source_rank"])
            or not _optional_unit_interval_decimal(finding["source_score"])
            or not _optional_unit_interval_decimal(finding["phenotype_score"])
            or not _optional_unit_interval_decimal(finding["population_frequency"])
        ):
            return False
        finding_ids.add(finding_id)

        variants = finding["variants"]
        expected_count = 2 if finding["finding_type"] == "pair" else 1
        if not isinstance(variants, list) or len(variants) != expected_count:
            return False
        genes: set[str] = set()
        for variant in variants:
            if not isinstance(variant, dict) or set(variant) != expected_variant_fields:
                return False
            variant_id = variant["variant_id"]
            gene = variant["gene"]
            if (
                not isinstance(variant_id, str)
                or SYNTHETIC_VARIANT_PATTERN.fullmatch(variant_id) is None
                or variant_id in variant_ids
                or not isinstance(gene, str)
                or SYNTHETIC_GENE_PATTERN.fullmatch(gene) is None
                or variant["impact"] not in config["impact_values"]
                or variant["quality"] not in set(SYNTHETIC_CONTRACT["quality_values"])
            ):
                return False
            variant_ids.add(variant_id)
            genes.add(gene)
        if len(genes) != 1:
            return False
        if (
            finding["finding_type"] == "single"
            and finding["phase"] != SYNTHETIC_CONTRACT["single_phase"]
        ):
            return False
        if (
            finding["finding_type"] == "pair"
            and finding["phase"] not in set(SYNTHETIC_CONTRACT["pair_phase_values"])
        ):
            return False
    return True


def _is_positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _optional_unit_interval_decimal(value: Any) -> bool:
    return value is None or _unit_interval_decimal(value) is not None


def _unit_interval_map(value: Any, expected_keys: set[str]) -> Optional[dict[str, Decimal]]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        return None
    parsed: dict[str, Decimal] = {}
    for key, raw in value.items():
        decimal = _unit_interval_decimal(raw)
        if decimal is None:
            return None
        parsed[key] = decimal
    return parsed


def _unit_interval_decimal(value: Any) -> Optional[Decimal]:
    if not isinstance(value, str):
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed < 0 or parsed > 1:
        return None
    return parsed


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


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


def _render_markdown(dossier: dict[str, Any]) -> str:
    lines = [
        "# Synthetic candidate dossier",
        "",
        dossier["disclaimer"],
        "",
        f"Method: `{dossier['method_version']}`",
        "",
    ]
    if not dossier["findings"]:
        lines.extend(
            [
                "No candidate finding survived the declared synthetic rules.",
                "",
                f"Next analytical gap: {dossier['next_analytical_gap']}",
                "",
            ]
        )
    for index, finding in enumerate(dossier["findings"], start=1):
        lines.extend(
            [
                f"## {index}. {finding['finding_id']}",
                "",
                f"- Finding type: `{finding['finding_type']}`",
                f"- Review score: `{finding['review_score'] if finding['review_score'] is not None else 'unknown'}` (heuristic, not probability)",
                f"- Source rank: `{finding['source_rank']}`",
                f"- Phase: `{finding['phase']}`",
                f"- Warnings: `{', '.join(finding['warnings']) if finding['warnings'] else 'none'}`",
                "",
            ]
        )
    return "\n".join(lines)


def _write_private(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
