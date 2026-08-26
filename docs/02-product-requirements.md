# Product requirements: MVA Transparent Prioritizer

## Hero workflow

The operator verifies the encrypted mount and pinned reference receipts. The operator runs the synthetic journey, then starts the private workflow. The product validates the manifest, extracts the private HPO set locally, checks and normalizes the VCF, runs independent prioritization lanes, and writes a private candidate dossier. A privacy scanner then builds a separate methods packet from an explicit aggregate allowlist. Submission remains a manual, separately approved action.

## Scope

- A public-safe Python CLI and schema set with no patient data.
- Synthetic fixtures for single variants, proposed pairs, mosaic allele fractions, empty results, malformed inputs, and path attacks.
- A private runner that accepts one trusted manifest under a disjoint private root.
- Pinned offline bcftools and Exomiser adapters, with independent ClinVar or VEP evidence where resources permit.
- Separate coding, targeted non-coding, low-allele-fraction, and structural-call-presence checks.
- A private Markdown and JSON candidate dossier, plus content-free run status.
- A public-safe methods and learnings projection.

## Non-goals

- Diagnosis, treatment selection, dosing, or a claim of clinical benefit.
- Automatic submission, publication, messaging, repository push, or public release.
- Hosted processing of protected case data.
- Reconstruction or use of the hidden confirmed answer.
- FASTQ download or reprocessing without a named coverage, quality, alignment, structural, or calling gap.
- A generic web dashboard.

## Testable acceptance outcomes

1. Given a frozen synthetic fixture and config, two runs produce byte-identical JSON, Markdown, and receipts.
2. Given a valid private manifest, the workflow writes detailed artifacts only below the resolved private output root and emits content-free status to stdout.
3. Given a symlink, traversal path, repository ancestor, protected path inside the public repository, or caller-selected report path, the workflow rejects before reading or writing case content.
4. Given a changed input, reference, config, tool binary, or intermediate extraction, the verifier rejects the stale receipt.
5. Given one synthetic causal single variant and one synthetic compound pair, the dossier preserves both finding shapes and explains every deterministic reason.
6. Given no surviving candidate, the workflow writes an honest empty-state report and names the next analytical gap. It does not fabricate a rank.
7. Given the public projection step, a seeded protected canary and row-level fields do not appear in the output tree.

## Success and telemetry

Each run records input digests, reference digests, tool versions, canonical config, stage results, candidate counts, warnings, and verification status. Wall-clock time may appear in an operational log, while deterministic output excludes current time, hostname, username, and absolute paths. Review happens after every reference update and before each challenge submission.
