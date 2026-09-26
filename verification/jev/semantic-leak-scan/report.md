# Semantic Leak Scan - 2026-09-19

Scanner: Jev calibrated decision model (jev-latest) via the rlcd `bin/decide` CLI, TypeSafe System One request shape.
Scope: all 120 files in `git ls-files` of the public tree (branch mva-reference-setup). No binary files present; all files were text and were read.
Companion layer: scripts/verify_public_tree.py (regex) reports clear; this is the semantic layer on top of it.

## Summary

- Files scanned: 120
- Chunks: 393 (max 2,500 chars, split on line boundaries)
- Requests made: 34 (each at most 40 rows and at most 35,000 serialized characters; max actual serialized size 33,855)
- Buckets: 0 flagged (p >= 0.50), 3 review (0.30 <= p < 0.50), 390 clear (p < 0.30)
- Prefilter flagged: 199 of 393 chunks (chr+position, HP:, PROBAND/proband, genotype, 0/1, 1/1, het, hom, VCF)

## Probability distribution

- min: 0.1
- max: 0.34
- mean: 0.1791

| band | chunks |
|------|--------|
| 0.0-0.1 | 0 |
| 0.1-0.2 | 269 |
| 0.2-0.3 | 121 |
| 0.3-0.4 | 3 |
| 0.4-0.5 | 0 |
| 0.5-0.6 | 0 |
| 0.6-0.7 | 0 |
| 0.7-0.8 | 0 |
| 0.8-0.9 | 0 |
| 0.9-1.0 | 0 |

## Flagged and review chunks

### docs/20-track1-submission-gate.md#4

- probability: 0.34
- prefilter flag: True (PROBAND, proband, het)
- bucket: review
- first 300 chars: `parse_as_official` reproduces the gate's loader exactly, quirks included: default codec (so a UTF-8 BOM joins the first header name and the gate raises `KeyError('proband_id')` when it reads a data row; a BOM-only file yields an empty result in both parsers), whitespace stripped from chromosome tex

### docs/20-track1-submission-gate.md#5

- probability: 0.3
- prefilter flag: True (het)
- bucket: review
- first 300 chars: CLI: `python3 -m mva_prioritizer.cli track1-check --submission <file> [--synthetic-truth '[[chrom,pos,ref,alt],...]'] [--mitochondrial-name chrM|chrMT] [--allow-ties] [--allow-unsorted] [--allow-repeated-pairings]`. One JSON line with counts on success; the file is opened with `O_NOFOLLOW`, decided 

### mva_prioritizer/track1_submission.py#2

- probability: 0.3
- prefilter flag: True (proband)
- bucket: review
- first 300 chars: NUCLEAR_CHROMOSOMES = frozenset([f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]) NUCLEAR_LANE_TO_SUBMISSION = {**{str(i): f"chr{i}" for i in range(1, 23)}, "X": "chrX", "Y": "chrY"}   def accepted_chromosomes(mitochondrial_name: str = DEFAULT_MITOCHONDRIAL) -> FrozenSet[str]:     if mitochondri

## Assessment of each elevated chunk

- docs/20-track1-submission-gate.md#4 (p=0.34): Synthetic / documentation. This is part of docs/20, whose example variants are invented by design. The chunk documents parser behavior (BOM handling, whitespace, allele uppercasing, grouping by proband) with no real coordinates, genotype calls, identifiers, or phenotype lists. Needs no human read.
- docs/20-track1-submission-gate.md#5 (p=0.3): Synthetic / documentation. CLI usage text including the `--synthetic-truth` flag; no patient data. Needs no human read.
- mva_prioritizer/track1_submission.py#2 (p=0.3): Code. Chromosome-name constants (chr1..chr22, chrX, chrY) and a mapping table; code that handles such data without containing any. Needs no human read.

## Prefilter vs Jev

- Every chunk at or above 0.30 was also caught by the prefilter; Jev found nothing above 0.30 that the prefilter missed (max probability among prefilter-clear chunks: 0.28).
- Read Jev as the semantic backstop: it scored 194 chunks that the regex prefilter saw nothing suspicious in, all below 0.30, which supports (but does not by itself prove) that no phrasing-level leak hides in the low-signal bulk of the tree.

## Verdict

No chunk reached the 0.50 flag threshold and no chunk contains real case data. All three review chunks are documented-benign categories (docs/20 invented examples, code constants, CLI docs). The public tree is clean at the semantic layer; publishing the repository does not disclose protected data.

## Artifacts

The 34 answer files (leak-scan-ans-001.json .. leak-scan-ans-034.json) are alongside this report; each carries the chunk ids, file paths, and per-chunk verdicts. The request files and chunks.jsonl were copies of the public tree at commit 580bf55 split into chunks, so they are not kept; `git show 580bf55` reproduces the scanned bytes.
