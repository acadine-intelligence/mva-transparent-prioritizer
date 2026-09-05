"""A synthetic counterexample, not an Exomiser implementation or patient test.

Assume a recessive finding needs two variants in trans. A final-record filter
can keep one record whose partner failed the new cutoff. Recomputing the pair
requirement removes that record. Toy scores have no clinical interpretation.
"""
from decimal import Decimal
import json

FIXTURE = (
    {"id": "SYNTHETIC_VARIANT_A", "gene": "SYNTHETIC_GENE_A", "score": "0.85"},
    {"id": "SYNTHETIC_VARIANT_B", "gene": "SYNTHETIC_GENE_A", "score": "0.72"},
)


def full_pipeline(records, threshold):
    survivors = [dict(record) for record in records if Decimal(record["score"]) > threshold]
    # This toy fixture assumes the two variants are in trans. It does not infer phase.
    findings = []
    for record in survivors:
        partners = sorted(other["id"] for other in survivors
                          if other["gene"] == record["gene"] and other["id"] != record["id"])
        if partners:
            findings.append({**record, "partners": partners})
    return findings


def experiment():
    baseline = full_pipeline(FIXTURE, Decimal("0.70"))
    posthoc = [record for record in baseline if Decimal(record["score"]) > Decimal("0.80")]
    rerun = full_pipeline(FIXTURE, Decimal("0.80"))
    return {
        "scope": "synthetic_counterexample_only",
        "baseline_record_count": len(baseline),
        "posthoc_record_count": len(posthoc),
        "full_rerun_record_count": len(rerun),
        "posthoc_equals_full_rerun": posthoc == rerun,
        "clinical_probability": False,
        "hidden_top_n": None,
        "external_actions": 0,
    }


if __name__ == "__main__":
    print(json.dumps(experiment(), sort_keys=True))
