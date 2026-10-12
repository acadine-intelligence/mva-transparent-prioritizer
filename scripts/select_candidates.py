#!/usr/bin/env python3
"""Steps 4 to 7 of docs/22, optionally applying docs/24 Amendment K.

Only the CSV carries allele values. Status and summary use a fixed count schema.
Inputs are bounded regular files; a fresh output directory is required.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mva_prioritizer.bounded_input import InputRejected, load_strict_json
from mva_prioritizer.candidate_selection import Candidate, build_submission_csv, select_rows
from mva_prioritizer.catalog import Catalog, load_catalog, variant_key
from mva_prioritizer.catalog_lookup import load_matches
from mva_prioritizer.track1_submission import (
    DEFAULT_MITOCHONDRIAL, MITOCHONDRIAL_NAMES, parse_as_official, parse_submission,
    validate_against_lane_representation,
)

MAX_POOL_BYTES = 32 * 1024 * 1024
POOL_FIELDS = {"schema", "rule", "candidates", "dropped", "summary"}
CANDIDATE_FIELDS = set(Candidate.__dataclass_fields__) | {"rank_lane", "passed_in", "in_region", "sources"}
SOURCES = {"passed_either_lane", "region_called", "recurrent_gene", "dossier_inheritance_review"}
ERROR_MESSAGE = "candidate selection refused"


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise InputRejected("invalid arguments")


def load_pool(path: Path) -> List[Candidate]:
    raw = load_strict_json(path, MAX_POOL_BYTES)
    if not isinstance(raw, dict) or set(raw) != POOL_FIELDS:
        raise InputRejected("invalid pool")
    if raw["schema"] != "mva-candidate-pool-v1" or raw["rule"] != "docs/22-candidate-selection-rule.md":
        raise InputRejected("invalid pool version")
    if not isinstance(raw["candidates"], list) or not isinstance(raw["dropped"], list) or not isinstance(raw["summary"], dict):
        raise InputRejected("invalid pool fields")
    pool = []
    seen = set()
    for row in raw["candidates"]:
        if not isinstance(row, dict) or set(row) != CANDIDATE_FIELDS:
            raise InputRejected("invalid candidate fields")
        v = row["variant"]
        if not isinstance(v, list) or len(v) != 4:
            raise InputRejected("invalid variant")
        key = variant_key(*v)
        if v[0] not in {"chr" + key[0], "chrM" if key[0] == "MT" else "chr" + key[0]} or key in seen:
            raise InputRejected("invalid pool representation")
        seen.add(key)
        if not isinstance(row["gene"], str) or not row["gene"].strip() or row["tier"] not in ("A", "B", "C", "D"):
            raise InputRejected("invalid candidate evidence")
        if type(row["native_rank"]) is not int or row["native_rank"] < 1:
            raise InputRejected("invalid native rank")
        if any(type(row[k]) is not bool for k in ("both_lanes", "recessive_annotation", "in_region")):
            raise InputRejected("invalid evidence flag")
        if row["rank_lane"] not in ("coding", "noncoding"):
            raise InputRejected("invalid rank lane")
        for field, allowed in (("passed_in", {"coding", "noncoding"}), ("sources", SOURCES)):
            values = row[field]
            if (not isinstance(values, list) or any(not isinstance(v, str) or v not in allowed for v in values)
                    or len(values) != len(set(values))):
                raise InputRejected("invalid evidence list")
        if row["both_lanes"] != (len(row["passed_in"]) == 2):
            raise InputRejected("inconsistent lane evidence")
        pool.append(Candidate(**{k: tuple(row[k]) if k == "variant" else row[k]
                                 for k in Candidate.__dataclass_fields__}))
    return pool


def run(pool_path: Path, out: Path, catalog_path: Optional[Path] = None,
        mitochondrial_name: Optional[str] = None, extra_candidates: Optional[Path] = None) -> dict:
    # lexists also refuses dangling output symlinks. mkdir below is the atomic check.
    if os.path.lexists(out):
        raise InputRejected("output exists")
    if mitochondrial_name is not None and mitochondrial_name not in MITOCHONDRIAL_NAMES:
        raise InputRejected("invalid mitochondrial name")
    pool = load_pool(pool_path)
    catalog = load_catalog(catalog_path) if catalog_path is not None else Catalog(frozenset())
    extras = load_matches(extra_candidates) if extra_candidates is not None else []
    catalog_keys = catalog.counted_variants | {row["variant"] for row in extras}
    matches = {tier: 0 for tier in "ABCD"}
    selected_pool = []
    mito = mitochondrial_name or DEFAULT_MITOCHONDRIAL
    lane_keys = {variant_key(*c.variant) for c in pool}
    for c in pool:
        key = variant_key(*c.variant)
        if key in catalog_keys:
            matches[c.tier] += 1
            c = replace(c, tier="K")
        if key[0] == "MT":
            c = replace(c, variant=(mito, *key[1:]))
        selected_pool.append(c)
    direct_added = 0
    direct_keys = set()
    native_rank = max((c.native_rank for c in pool), default=0) + 1
    for row in extras:
        key = row["variant"]
        if key in lane_keys:
            continue
        chrom = mito if key[0] == "MT" else "chr" + key[0]
        selected_pool.append(Candidate((chrom, *key[1:]), row["gene"], "K", False, native_rank, False))
        direct_keys.add(key)
        direct_added += 1
    result = select_rows(selected_pool)
    if result.mitochondrial_rows and mitochondrial_name is None:
        raise InputRejected("mitochondrial spelling unconfirmed")
    csv_text = build_submission_csv(result)
    canonical = parse_submission(csv_text, allow_repeated_pairings=True, mitochondrial_name=mito)
    official = parse_as_official(csv_text)
    def signature(submission):
        return [(r.variants, r.epcr, r.rank, r.finding_type, r.file_order) for r in submission.rows]
    if set(official) != {canonical.proband_id} or signature(canonical) != signature(official[canonical.proband_id]):
        raise InputRejected("parser disagreement")
    if [(r.variants, r.epcr) for r in canonical.rows] != [(r.variants, r.epcr) for r in result.rows]:
        raise InputRejected("selection disagreement")
    # Every selected tuple must come from the pool or validated direct matches.
    # Direct matches are VCF evidence, not independent lane evidence. The original
    # lane receipt verification still belongs to Step 7 on the encrypted host.
    validate_against_lane_representation(canonical, lane_keys | direct_keys, mitochondrial_name=mito)
    pairs = sum(r.is_pair for r in result.rows)
    summary = {
        "rows": len(result.rows), "pair_rows": pairs, "single_rows": len(result.rows) - pairs,
        "truncated_by_tier": {t: result.truncated_by_tier.get(t, 0) for t in "KABCD"},
        "promotions": result.promotions, "demotions": result.demoted_pairs + result.removed_pairs,
        "catalog_matches_by_tier": matches, "catalog_null_entries": catalog.null_entries,
        "catalog_direct_added": direct_added,
    }
    out.mkdir(mode=0o700)
    out.chmod(0o700)
    # Summary is written last so a partial write is never reported as successful.
    for name, text in (("submission.csv", csv_text),
                       ("selection-summary.json", json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")):
        with (out / name).open("x", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = QuietParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--pool", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--extra-candidates", type=Path)
    parser.add_argument("--mitochondrial-name", choices=MITOCHONDRIAL_NAMES)
    try:
        args = parser.parse_args(argv)
        summary = run(args.pool, args.out, args.catalog, args.mitochondrial_name, args.extra_candidates)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError, csv.Error):
        print(ERROR_MESSAGE, file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
