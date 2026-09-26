#!/usr/bin/env python3
"""Steps 1 to 3 of docs/22-candidate-selection-rule.md: assemble, exclude, tier.

Runs on the encrypted host against the frozen ``review-work`` tree, read-only
on its inputs, under a sandbox that denies the network and confines writes to
one output directory. Two files come out:

- ``pool.json``: every allele with its tier and Candidate fields. Private. It
  stays on the host; Step 4 reads it there.
- ``summary.json``: counts and input hashes only. No symbol, no coordinate, no
  identifier. This is the file that crosses to the public tree.

Pinned readings the document leaves to the runner, stated here and in the
document before the first run:

- "Passing every filter" in a lane is ``filterStatus == "PASSED"`` on the
  variant evaluation in that lane's ``replay.jsonl``.
- "Its gene": the gene both lanes assign when the allele passed both (they
  must agree, else the run is invalid); the passing lane's gene when it passed
  one; the declared region's gene when it passed neither and sits in a region;
  the agreed lane gene otherwise. Any remaining ambiguity invalidates the run.
- "Transcript span": the ``start``..``end`` interval of the gene's entry in the
  frozen interval map (one based, inclusive). Upstream inspection windows are
  not transcript spans. Genes absent from the map have no pinned span, so the
  first condition of exclusion 3 cannot be established for them and they are
  never dropped by it.
- "Stricter lane": the lane with fewer ``PASSED`` alleles in ``replay.jsonl``;
  on a tie, the lane whose name sorts first. Its native rank is the smallest
  ``#RANK`` among the allele's rows in that lane's ``replay.variants.tsv``.
- "Recorded recessive annotation": a row for the allele with ``MOI == "AR"``
  in the ``replay.variants.tsv`` of a lane where the allele passed (such rows
  exist only for passed alleles).
- Tier C's sensitivity clause, at the variant level: the allele has an entry
  in a gene's ``noncoding_sensitivity.variants`` with ``stage1_pass`` true and
  its own ``baseline_modes`` different from its ``strict_modes``.
- The quality criteria are ``recorded_quality_issues`` from the reviewed audit
  module, whose SHA-256 must equal the pin in ``diagnostic-replay.json``,
  applied to the allele's record in the lane ``input.vcf``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

Allele = Tuple[str, int, str, str]

SCHEMA = "mva-candidate-pool-v1"
RULE = "docs/22-candidate-selection-rule.md"
LANES = ("coding", "noncoding")
NUCLEAR = {str(i) for i in range(1, 23)} | {"X", "Y"}
MITO_PUBLIC = "chrM"
BASES = set("ACGT")


class PoolError(ValueError):
    """The frozen inputs are inconsistent with the rule; no pool is produced."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contig(value: str) -> str:
    """The lane spelling: bare number, X, Y, MT."""
    if value.startswith("chr") and value[3:] in NUCLEAR | {"M", "MT"}:
        value = value[3:]
    return "MT" if value == "M" else value


def public_contig(value: str) -> str:
    """The submission spelling Candidate expects."""
    c = contig(value)
    return MITO_PUBLIC if c == "MT" else "chr" + c


def load_audit_module(path: Path, pinned_sha: str):
    actual = sha256_file(path)
    if actual != pinned_sha:
        raise PoolError("audit_core_hash_mismatch")
    spec = importlib.util.spec_from_file_location("frozen_audit_core", path)
    if spec is None or spec.loader is None:
        raise PoolError("audit_core_not_loadable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "recorded_quality_issues", None)):
        raise PoolError("audit_core_missing_recorded_quality_issues")
    return module


def read_lane(replay: Path, lane: str) -> dict:
    genes: Dict[Allele, str] = {}
    status: Dict[Allele, str] = {}
    for line in (replay / lane / "results" / "replay.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        g = json.loads(line)
        symbol = g["geneSymbol"]
        for v in g.get("variantEvaluations", []):
            k = (contig(v["contigName"]), int(v["start"]), v["ref"], v["alt"])
            if k in genes:
                raise PoolError("duplicate_allele_in_lane_output")
            genes[k] = symbol
            status[k] = v.get("filterStatus", "not_established")
    ranks: Dict[Allele, List[int]] = defaultdict(list)
    ar: Set[Allele] = set()
    with open(replay / lane / "results" / "replay.variants.tsv", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            k = (contig(r["CONTIG"]), int(r["START"]), r["REF"], r["ALT"])
            ranks[k].append(int(r["#RANK"]))
            if r["MOI"] == "AR":
                ar.add(k)
    return {"gene": genes, "status": status, "ranks": ranks, "ar": ar,
            "passed": {k for k, s in status.items() if s == "PASSED"}}


def read_input_vcf(path: Path) -> Dict[Allele, dict]:
    records: Dict[Allele, dict] = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        alts = f[4].split(",")
        fmt: Dict[str, str] = {}
        if len(f) >= 10:
            fmt = dict(zip(f[8].split(":"), f[9].split(":")))
        for alt in alts:
            k = (contig(f[0]), int(f[1]), f[3], alt)
            records[k] = {"qual": f[5], "fmt": fmt, "alt_count": 0 if alts == ["."] else len(alts),
                          "multiallelic": len(alts) > 1, "alt": alt}
    return records


def build(review_root: Path, out_dir: Path, audit_core: Path, interval_map: Optional[Path] = None) -> dict:
    replay = review_root / "diagnostic-replay-20260909" / "replay-2"
    diag_path = replay / "diagnostic-replay.json"
    diag = json.loads(diag_path.read_text())
    pins = diag.get("reviewed_code_and_inputs", {})
    audit = load_audit_module(audit_core, pins.get("audit_core.py", ""))

    spans: Dict[str, Tuple[int, int]] = {}
    interval_map_sha = None
    if interval_map is not None:
        interval_map_sha = sha256_file(interval_map)
        if pins.get("gene-interval-map.json") not in (None, interval_map_sha):
            raise PoolError("interval_map_hash_mismatch")
        for g in json.loads(interval_map.read_text())["genes"]:
            spans[g["symbol"]] = (int(g["start"]), int(g["end"]))

    lanes = {lane: read_lane(replay, lane) for lane in LANES}
    vcf = {lane: read_input_vcf(replay / lane / "input.vcf") for lane in LANES}
    if vcf["coding"] != vcf["noncoding"]:
        raise PoolError("lane_inputs_differ")
    records = vcf["coding"]

    # Step 1. Sources.
    passed_either = lanes["coding"]["passed"] | lanes["noncoding"]["passed"]
    region: Dict[Allele, List[str]] = {}
    for lane in LANES:
        for o in diag["lanes"][lane]["observations"]:
            if o.get("called_in_stored_genotype"):
                region[tuple(o["allele_key"])] = list(o["regional_gene_symbols"])  # type: ignore[arg-type]
    rec_path = review_root / "recurrent-genes-20260911" / "recurrent-1" / "recurrent-genes.json"
    recurrent = set(json.loads(rec_path.read_text())["recurrent_top30_symbols"])
    recurrent_alleles = {k for lane in LANES for k, g in lanes[lane]["gene"].items() if g in recurrent}
    cr_path = review_root / "candidate-review-20260906" / "candidate-review" / "candidate-review.json"
    dossier = json.loads(cr_path.read_text())
    review_genes = set(dossier["inheritance_review"])
    dossier_alleles: Set[Allele] = set()
    sensitivity_changed: Set[Allele] = set()
    for g in dossier["genes"]:
        if g["symbol"] in review_genes:
            for field in ("coding_variants", "noncoding_variants"):
                for v in g[field]:
                    dossier_alleles.add((contig(v["CONTIG"]), int(v["START"]), v["REF"], v["ALT"]))
        ns = g.get("noncoding_sensitivity")
        if ns:
            for key, entry in ns["variants"].items():
                c, p, r, a = key.split("|")
                if entry["stage1_pass"] and set(entry["baseline_modes"]) != set(entry["strict_modes"]):
                    sensitivity_changed.add((contig(c), int(p), r, a))
    sources = {"passed_either_lane": passed_either, "region_called": set(region),
               "recurrent_gene": recurrent_alleles, "dossier_inheritance_review": dossier_alleles}
    pool: Set[Allele] = set().union(*sources.values())
    step1 = {"pool_before_exclusion": len(pool), "sources": {n: len(s) for n, s in sources.items()}}

    # Gene resolution, then Step 2.
    dropped: Dict[str, int] = {"quality": 0, "representation": 0, "gene_assignment": 0}
    drops: List[dict] = []
    kept: List[dict] = []
    span_unknown = 0
    for k in sorted(pool):
        passed_in = [lane for lane in LANES if k in lanes[lane]["passed"]]
        lane_genes = {lane: lanes[lane]["gene"].get(k) for lane in LANES}
        if len(passed_in) == 2:
            if lane_genes["coding"] != lane_genes["noncoding"]:
                raise PoolError("passed_both_lanes_gene_disagreement")
            gene = lane_genes["coding"]
        elif len(passed_in) == 1:
            gene = lane_genes[passed_in[0]]
        elif k in region and len(region[k]) == 1:
            gene = region[k][0]
        elif k in region and set(region[k]) & {g for g in lane_genes.values() if g}:
            match = sorted(set(region[k]) & {g for g in lane_genes.values() if g})
            if len(match) != 1:
                raise PoolError("gene_ambiguous")
            gene = match[0]
        elif lane_genes["coding"] == lane_genes["noncoding"] and lane_genes["coding"]:
            gene = lane_genes["coding"]
        else:
            raise PoolError("gene_ambiguous")

        rec = records.get(k)
        reason = None
        if rec is None or rec["multiallelic"] or not (set(k[2]) <= BASES and set(k[3]) <= BASES) \
                or k[0] not in NUCLEAR | {"MT"}:
            reason = "representation"
        elif audit.recorded_quality_issues(rec["qual"], rec["fmt"], rec["alt_count"]):
            reason = "quality"
        else:
            lane_assigns = gene in {g for g in lane_genes.values() if g}
            if gene in spans:
                inside = spans[gene][0] <= k[1] <= spans[gene][1]
            else:
                inside = None
                span_unknown += 1
            if inside is False and not lane_assigns:
                reason = "gene_assignment"
        if reason:
            dropped[reason] += 1
            drops.append({"variant": list(k), "gene": gene, "reason": reason})
            continue

        # Step 3.
        in_region = k in region
        recessive = any(k in lanes[lane]["ar"] for lane in passed_in)
        if len(passed_in) == 2:
            tier = "A"
        elif len(passed_in) == 1 and in_region and recessive:
            tier = "B"
        elif gene in recurrent or k in sensitivity_changed:
            tier = "C"
        else:
            tier = "D"
        kept.append({"variant": k, "gene": gene, "tier": tier, "passed_in": passed_in,
                     "in_region": in_region, "recessive": recessive,
                     "sources": sorted(n for n, s in sources.items() if k in s)})

    # Stricter lane and native rank.
    pass_counts = {lane: len(lanes[lane]["passed"]) for lane in LANES}
    stricter = sorted(LANES, key=lambda lane: (pass_counts[lane], lane))[0]
    candidates = []
    for c in kept:
        lane = c["passed_in"][0] if len(c["passed_in"]) == 1 else stricter
        rows = lanes[lane]["ranks"].get(c["variant"])
        if not rows:
            raise PoolError("allele_without_tsv_rank")
        k = c["variant"]
        candidates.append({
            "variant": [public_contig(k[0]), k[1], k[2], k[3]], "gene": c["gene"], "tier": c["tier"],
            "both_lanes": len(c["passed_in"]) == 2, "native_rank": min(rows),
            "recessive_annotation": c["recessive"], "rank_lane": lane,
            "passed_in": c["passed_in"], "in_region": c["in_region"], "sources": c["sources"],
        })

    tier_sizes = Counter(c["tier"] for c in candidates)
    summary = {
        "schema": SCHEMA, "rule": RULE, "read_only_inputs": True, "case_rows_exported": False,
        "inputs": {
            "diagnostic_replay_sha256": sha256_file(diag_path),
            "replay_receipt_sha256": sha256_file(replay / "receipt.json"),
            "recurrent_genes_sha256": sha256_file(rec_path),
            "candidate_review_sha256": sha256_file(cr_path),
            "audit_core_sha256": pins.get("audit_core.py"),
            "interval_map_sha256": interval_map_sha,
            "lane_input_vcf_sha256": sha256_file(replay / "coding" / "input.vcf"),
        },
        "lane_passed_counts": pass_counts, "stricter_lane": stricter,
        "step1": step1,
        "step2": {"dropped": dropped, "pool_after_exclusion": len(candidates),
                  "gene_span_not_pinned": span_unknown},
        "step3": {
            "tier_sizes": {t: tier_sizes.get(t, 0) for t in "ABCD"},
            "both_lanes": sum(1 for c in candidates if c["both_lanes"]),
            "in_region_by_tier": {t: sum(1 for c in candidates if c["tier"] == t and c["in_region"]) for t in "ABCD"},
            "recessive_by_tier": {t: sum(1 for c in candidates if c["tier"] == t and c["recessive_annotation"]) for t in "ABCD"},
            "genes_by_tier": {t: len({c["gene"] for c in candidates if c["tier"] == t}) for t in "ABCD"},
            "pairable_genes": sum(1 for g, n in Counter(c["gene"] for c in candidates
                                                       if c["tier"] in "AB" and c["recessive_annotation"]).items() if n >= 2),
            "sensitivity_changed_survivors_in_pool": sum(
                1 for c in candidates
                if (contig(c["variant"][0]), c["variant"][1], c["variant"][2], c["variant"][3]) in sensitivity_changed),
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pool.json").write_text(json.dumps(
        {"schema": SCHEMA, "rule": RULE, "candidates": candidates, "dropped": drops,
         "summary": summary}, indent=1, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return {"summary": summary, "pool": candidates, "dropped": drops}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Steps 1 to 3 of docs/22")
    ap.add_argument("--review-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--audit-core", required=True, type=Path)
    ap.add_argument("--interval-map", type=Path)
    args = ap.parse_args(argv)
    try:
        result = build(args.review_root, args.out, args.audit_core, args.interval_map)
    except PoolError as exc:
        print(json.dumps({"state": "invalid", "error": str(exc)}))
        return 2
    print(json.dumps(result["summary"], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
