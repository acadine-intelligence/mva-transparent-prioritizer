"""Build the host-local denylist for scripts/verify_no_case_tokens.py.

Reads the private artifacts on this host (everything under runtime/ is
gitignored) and writes runtime/privacy/denied-tokens.txt, one token per
line. The output file is itself under runtime/ and never leaves the host.

Sources, in the order they are read:
  1. The frozen nine-gene interval map: symbol, HGNC id (prefixed and bare),
     Ensembl transcript ids (with and without version).
  2. The HGNC responses fetched for those nine genes: every alias symbol and
     previous symbol, so a renamed gene cannot slip through under an old
     name.
  3. The recurrent-gene aggregate report: every token shaped like an HGNC
     symbol, less a fixed list of schema and format vocabulary.

The gate that consumes this list fails closed when the list is missing. That
is deliberate: a checkout without the private artifacts cannot know which
plain words are protected, so it cannot claim the tree is clear of them.
Build OS verify therefore passes only on a host that holds the private
artifacts and has run this script. A public reviewer without them runs the
other seven verify commands and reads this one's failure as "not checkable
here", which is the truth.

Usage: python3 scripts/build_case_token_denylist.py
Exit 0 written, 2 when a source artifact is missing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERVAL_MAP = ROOT / "runtime" / "nine-gene-audit-20260909" / "gene-interval-map.json"
HGNC_DIR = ROOT / "runtime" / "internal-review-20260907" / "public-hgnc"
AGGREGATE_REPORT = ROOT / "runtime" / "recurrent-genes-20260911" / "aggregate-report.md"
OUT = ROOT / "runtime" / "privacy" / "denied-tokens.txt"

# Symbols that are ordinary words or public-method vocabulary and would
# block the whole tree: none at present. Add here with a reason if one
# appears, and record it in docs/22.
ALLOW: set[str] = set()


def from_interval_map(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tokens: set[str] = set()
    for gene in data.get("genes", []):
        symbol = gene.get("symbol")
        if symbol:
            tokens.add(str(symbol))
        hgnc = str(gene.get("hgnc_id") or "")
        if hgnc:
            tokens.add(hgnc)
            bare = hgnc.split(":")[-1]
            if len(bare) >= 5:
                tokens.add(bare)
        for transcript in gene.get("transcripts") or []:
            transcript = str(transcript)
            tokens.add(transcript)
            tokens.add(transcript.split(".")[0])
    return tokens


def from_hgnc_responses(directory: Path) -> set[str]:
    tokens: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for doc in (data.get("response") or {}).get("docs") or []:
            for key in ("symbol", "alias_symbol", "prev_symbol"):
                value = doc.get(key)
                for item in (value if isinstance(value, list) else [value]):
                    if item and len(str(item)) >= 3:
                        tokens.add(str(item))
    return tokens


SYMBOL = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9]{2,9}(?:-[A-Z0-9]+)?|C[0-9]+orf[0-9]+)(?![A-Za-z0-9_])")
# Report vocabulary that matches the symbol shape but is not a gene: contigs,
# assemblies, file formats, hash names, classification labels, abbreviations.
NOT_A_SYMBOL = re.compile(
    r"^(?:CHR[0-9XYM]+|GRCH3[78]|HG[0-9]+|HPO|VCF|CSV|TSV|JSON|MD-?5|SHA-?[0-9]*|UTF-?8|ISO-?[0-9]+|RFC-?[0-9]+|CC-BY|"
    r"TBD|VUS|ACMG|OMIM|GWAS|WGS|WES|SNV|SNP|CNV|INDEL|MAF|CADD|REMM|SIFT|MPC|API|CLI|URL|README|TODO|NOTE|"
    r"MVA|PASS|FAIL|TRUE|FALSE|NULL|NONE|ALL|ANY|MAX|MIN|SUM|AVG|TOP|ID)$"
)


def from_aggregate_report(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    found = set(SYMBOL.findall(text))
    return {t for t in found if not NOT_A_SYMBOL.match(t) and not t.isdigit()}


def main() -> int:
    missing = [p for p in (INTERVAL_MAP, HGNC_DIR, AGGREGATE_REPORT) if not p.exists()]
    if missing:
        for p in missing:
            print(f"missing private artifact: {p.relative_to(ROOT)}", file=sys.stderr)
        return 2
    tokens = (from_interval_map(INTERVAL_MAP) | from_hgnc_responses(HGNC_DIR) | from_aggregate_report(AGGREGATE_REPORT)) - ALLOW
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sorted(tokens)) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(OUT.relative_to(ROOT)), "tokens": len(tokens)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
