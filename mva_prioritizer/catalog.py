"""Strict public disease-allele catalog input for Amendment K. No network I/O."""
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Tuple
from urllib.parse import urlsplit

from .bounded_input import InputRejected, load_strict_json

Variant = Tuple[str, int, str, str]
MAX_CATALOG_BYTES = 16 * 1024 * 1024
ENTRY_FIELDS = {"gene", "transcript", "hgvs_c", "grch38", "mechanism", "confidence", "citations"}
NUCLEAR = {str(i) for i in range(1, 23)} | {"X", "Y"}


@dataclass(frozen=True)
class CatalogEntry:
    variant: Variant
    gene: str
    mechanism: str


@dataclass(frozen=True)
class Catalog:
    counted_variants: FrozenSet[Variant]
    null_entries: int = 0
    counted_entries: Tuple[CatalogEntry, ...] = ()


def lane_contig(chrom: str) -> str:
    """Explicit aliases only: chr prefix, then M/MT to the lane's MT."""
    if not isinstance(chrom, str):
        raise InputRejected("invalid contig")
    bare = chrom[3:] if chrom.startswith("chr") else chrom
    if bare in {"M", "MT"}:
        return "MT"
    if bare not in NUCLEAR:
        raise InputRejected("invalid contig")
    return bare


def variant_key(chrom, pos, ref, alt) -> Variant:
    if type(pos) is not int or pos < 1:
        raise InputRejected("invalid position")
    if any(not isinstance(a, str) or not a or not set(a) <= set("ACGT") for a in (ref, alt)) or ref == alt:
        raise InputRejected("invalid allele")
    return (lane_contig(chrom), pos, ref, alt)


def load_catalog(path: Path) -> Catalog:
    """A JSON array of exact-schema entries; validate even ignored entries."""
    entries = load_strict_json(path, MAX_CATALOG_BYTES)
    if not isinstance(entries, list):
        raise InputRejected("invalid catalog")
    seen, counted = set(), set()
    counted_entries = []
    null_entries = 0
    for item in entries:
        if not isinstance(item, dict) or set(item) != ENTRY_FIELDS:
            raise InputRejected("invalid catalog entry")
        for field in ("gene", "transcript", "hgvs_c", "mechanism", "confidence"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise InputRejected("invalid catalog field")
        if item["confidence"] not in {"high", "medium", "low"}:
            raise InputRejected("invalid confidence")
        citations = item["citations"]
        if not isinstance(citations, list):
            raise InputRejected("invalid citations")
        for citation in citations:
            if not isinstance(citation, str) or any(c.isspace() or ord(c) < 32 for c in citation):
                raise InputRejected("invalid citation")
            url = urlsplit(citation)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise InputRejected("invalid citation")
            # Accessing port also rejects malformed and out-of-range ports.
            _ = url.port
        grch38 = item["grch38"]
        if grch38 is None:
            null_entries += 1
            continue
        if not isinstance(grch38, dict) or set(grch38) != {"chrom", "pos", "ref", "alt"}:
            raise InputRejected("invalid GRCh38 tuple")
        key = variant_key(**grch38)
        if key in seen:
            raise InputRejected("duplicate catalog tuple")
        seen.add(key)
        if item["confidence"] in {"high", "medium"}:
            counted.add(key)
            counted_entries.append(CatalogEntry(key, item["gene"], item["mechanism"]))
    return Catalog(frozenset(counted), null_entries, tuple(counted_entries))
