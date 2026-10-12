"""Strict local VCF lookup and private match-file contract for Amendment K."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

from .bounded_input import InputRejected, load_strict_json
from .catalog import MAX_CATALOG_BYTES, Variant, lane_contig, variant_key

# Never copy free-text catalog mechanisms into a counts-only public summary.
MECHANISM_CLASSES = ('regulatory', 'splice', 'missense', 'nonsense', 'frameshift',
                     'loss_of_function', 'hypomorphic', 'other')
GT_PATTERN = re.compile(r'(?:\.|0|[1-9][0-9]*)(?:[/|](?:\.|0|[1-9][0-9]*))*')


def genotype_indices(gt: str, alt_count: Optional[int] = None) -> set[int]:
    """Return called indices; a partial no-call still carries its called allele."""
    if not isinstance(gt, str) or GT_PATTERN.fullmatch(gt) is None:
        raise InputRejected('invalid genotype')
    called = {int(a) for a in re.split(r'[/|]', gt) if a != '.'}
    if alt_count is not None and any(a > alt_count for a in called):
        raise InputRejected('genotype index out of range')
    return called


def parse_header(text: str) -> dict[str, str]:
    """Map canonical contigs to unique VCF spellings, requiring one sample."""
    lines = text.splitlines()
    if not lines or not re.fullmatch(r'##fileformat=VCFv4\.[1-5]', lines[0]):
        raise InputRejected('invalid VCF header')
    columns = ['#CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER', 'INFO', 'FORMAT']
    contigs = {}
    seen = set()
    for line in lines[1:-1]:
        if not line.startswith('##'):
            raise InputRejected('invalid VCF header')
        if line.startswith('##contig='):
            match = re.fullmatch(r'##contig=<ID=([^,<>\s]+)(?:,.*)?>', line)
            if match is None or match[1] in seen:
                raise InputRejected('invalid contig header')
            name = match[1]
            seen.add(name)
            try:
                key = lane_contig(name)
            except InputRejected:
                continue  # Unrelated decoy contigs do not participate in this rule.
            if key in contigs:
                raise InputRejected('ambiguous contig aliases')
            contigs[key] = name
    fields = lines[-1].split('\t')
    if len(fields) != 10 or fields[:9] != columns or not fields[9] or any(c.isspace() for c in fields[9]):
        raise InputRejected('VCF must have one sample')
    return contigs


def parse_records(text: str, variant: Variant) -> Optional[str]:
    """Validate each returned record, then match exact POS/REF/ALT and its GT index.

    Region queries may return overlapping deletions with an earlier POS. They
    are not exact matches. Multiple records carrying the same target are refused
    because the private match contract has only one genotype per tuple.
    """
    key = variant_key(*variant)
    matched = None
    for line in text.splitlines():
        fields = line.split('\t')
        if len(fields) != 10 or any(not f or any(c.isspace() for c in f) for f in fields):
            raise InputRejected('invalid VCF record')
        chrom, pos, _, ref, alt_text, qual, _, _, fmt, sample = fields
        chrom = lane_contig(chrom)
        if re.fullmatch(r'[1-9][0-9]*', pos) is None or re.fullmatch(r'[ACGTN]+', ref) is None:
            raise InputRejected('invalid VCF coordinate')
        alts = alt_text.split(',')
        # VCF 4.2 ALT forms: bases, '*', symbolic <ID>, and breakends
        # (t[p[, t]p], ]p]t, [p[t, single-breakend t. and .t).
        mate = r'(?:\[(?:<[^<>\s,]+>|[^\s,:\[\]<>]+):(?:0|[1-9][0-9]*)\[|\](?:<[^<>\s,]+>|[^\s,:\[\]<>]+):(?:0|[1-9][0-9]*)\])'
        breakend = r'[ACGTN]+' + mate + r'|' + mate + r'[ACGTN]+|[ACGTN]+\.|\.[ACGTN]+'
        if len(set(alts)) != len(alts) or any(
                re.fullmatch(r'[ACGTN]+|\*|<[^<>\s,]+>|\.|' + breakend, a) is None or a == ref for a in alts):
            raise InputRejected('invalid VCF alleles')
        if '.' in alts and alts != ['.']:
            raise InputRejected('invalid missing ALT')
        if qual != '.' and (not math.isfinite(float(qual)) or float(qual) < 0):
            raise InputRejected('invalid VCF quality')
        formats, values = fmt.split(':'), sample.split(':')
        if (formats[0] != 'GT' or len(set(formats)) != len(formats)
                or any(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', f) is None for f in formats)
                or len(values) > len(formats) or any(not v for v in values)):
            raise InputRejected('invalid VCF sample fields')
        gt = values[0]
        called = genotype_indices(gt, 0 if alts == ['.'] else len(alts))
        if (chrom, int(pos), ref) != key[:3] or key[3] not in alts:
            continue
        if alts.index(key[3]) + 1 in called:
            if matched is not None:
                raise InputRejected('ambiguous matching records')
            matched = gt
    return matched


def load_matches(path: Path) -> list[dict]:
    """Bounded private lookup output; GT refers to the original ALT list.

    ALT index membership was checked by lookup, before the ALT list was reduced
    to one matched tuple. Here only a well-formed non-reference call is required.
    """
    raw = load_strict_json(path, MAX_CATALOG_BYTES)
    if not isinstance(raw, list):
        raise InputRejected('invalid matches')
    result, seen = [], set()
    for row in raw:
        if not isinstance(row, dict) or set(row) != {'variant', 'gene', 'genotype'}:
            raise InputRejected('invalid match fields')
        v = row['variant']
        if not isinstance(v, list) or len(v) != 4:
            raise InputRejected('invalid match tuple')
        key = variant_key(*v)
        if key in seen or not isinstance(row['gene'], str) or not row['gene'].strip():
            raise InputRejected('invalid match gene or duplicate')
        if not (genotype_indices(row['genotype']) - {0}):
            raise InputRejected('match has no called ALT')
        seen.add(key)
        result.append({**row, 'variant': key})
    return result
