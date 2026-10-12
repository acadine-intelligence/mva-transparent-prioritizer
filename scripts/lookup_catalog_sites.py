#!/usr/bin/env python3
"""Amendment K Part 2: exact, genotype-aware lookup in a local indexed VCF.

matches.json is private. Only fixed-schema counts are printed or summarized.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mva_prioritizer.bounded_input import InputRejected
from mva_prioritizer.catalog import load_catalog
from mva_prioritizer.catalog_lookup import MECHANISM_CLASSES, parse_header, parse_records

ERROR_MESSAGE = 'catalog lookup refused'


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        raise InputRejected('invalid arguments')


def bcftools_output(executable: str, args: list[str]) -> str:
    return subprocess.run([executable, *args], check=True, capture_output=True,
                          text=True, encoding='utf-8', timeout=60).stdout


def lookup_sites(vcf: Path, catalog_path: Path, bcftools: str = 'bcftools') -> tuple[list, dict]:
    catalog = load_catalog(catalog_path)
    # Check the large input without reading it into memory. bcftools enforces
    # indexed regional access, so there is no fallback scan of the whole VCF.
    fd = os.open(vcf, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise InputRejected('VCF must be regular')
    finally:
        os.close(fd)
    vcf_arg = str(vcf.absolute())
    contigs = parse_header(bcftools_output(bcftools, ['view', '-h', '--', vcf_arg]))
    matches = []
    summary = {'entries_counted': len(catalog.counted_entries), 'null_skipped': catalog.null_entries,
               'looked_up': 0, 'matched': 0,
               'matched_by_mechanism_class': {k: 0 for k in MECHANISM_CLASSES}}
    for entry in catalog.counted_entries:
        chrom, pos, _, _ = entry.variant
        if chrom not in contigs:
            raise InputRejected('catalog contig absent from VCF header')
        region = f'{contigs[chrom]}:{pos}-{pos}'
        text = bcftools_output(bcftools, ['view', '-H', '-r', region, '--', vcf_arg])
        genotype = parse_records(text, entry.variant)
        summary['looked_up'] += 1
        if genotype is not None:
            matches.append({'variant': list(entry.variant), 'genotype': genotype, 'gene': entry.gene})
            summary['matched'] += 1
            mechanism = entry.mechanism if entry.mechanism in MECHANISM_CLASSES else 'other'
            summary['matched_by_mechanism_class'][mechanism] += 1
    return matches, summary


def run(vcf: Path, catalog: Path, out: Path, bcftools: str = 'bcftools') -> dict:
    if os.path.lexists(out):
        raise InputRejected('output exists')
    matches, summary = lookup_sites(vcf, catalog, bcftools)
    out.mkdir(mode=0o700)
    try:
        out.chmod(0o700)
        # Summary is the completion marker and is always written last.
        for name, value in (('matches.json', matches), ('lookup-summary.json', summary)):
            with (out / name).open('x', encoding='utf-8', newline='') as handle:
                handle.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        for name in ('lookup-summary.json', 'matches.json'):
            (out / name).unlink(missing_ok=True)
        out.rmdir()
        raise
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = QuietParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--vcf', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bcftools', default='bcftools')
    try:
        args = parser.parse_args(argv)
        summary = run(args.vcf, args.catalog, args.out, args.bcftools)
    except (subprocess.SubprocessError, OSError, ValueError, TypeError, KeyError,
            OverflowError, RecursionError, csv.Error):
        print(ERROR_MESSAGE, file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
