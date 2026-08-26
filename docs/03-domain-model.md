# Domain model: MVA Transparent Prioritizer

## Core entities and relationships

- `InputManifest` binds each controlled file to size, digest, format, assembly, privacy class, and expected sample count. It never stores the sample name in the public project.
- `ReferenceBundle` binds a public reference asset to version, source URL, digest, assembly, contig dictionary, license, and retrieval receipt.
- `PhenotypeSet` stores HPO identifiers and negation state inside the private workspace.
- `VariantObservation` stores normalized private variant facts, genotype evidence, quality evidence, and annotation evidence.
- `CandidateFinding` represents either one variant or a proposed pair. It points to its source observations and keeps phase uncertainty explicit.
- `EvidenceRecord` names a claim, source, date, and evidence system: human, patient-derived cell, mammalian, invertebrate, or computational.
- `RunReceipt` binds inputs, references, tools, config, stage outputs, and warnings.
- `SafeLearning` contains only allowlisted method facts and non-identifying aggregates.

## State transitions

`declared` can move to `validated`, then `processed`, then `review_ready`. A validation or execution fault moves the run to `failed_closed`. An interrupted run moves to `incomplete` and cannot be reviewed until a clean replay succeeds. Human review can move a candidate to `retain_for_submission_review`, `defer`, or `reject`. Only the operator can start an external submission.

## Deterministic rules

- Exact digests, schema versions, tool versions, and reference dictionaries must match before processing.
- The private root must be disjoint from the repository after symlink resolution.
- The engine derives all output paths. The caller cannot select a detailed report path.
- Candidate ordering uses declared evidence fields and a versioned rule set. Missing values remain unknown and cannot become zero.
- Exomiser score and rank stay intact as one evidence lane. MVA-specific review flags stay separate and cannot silently rewrite the source score.
- Proposed pairs require two observations in one gene or a declared digenic rule. Unphased pairs carry an explicit phase warning.
- Structural-call absence creates a coverage warning. It cannot become a biological negative.
- Every public field comes from an allowlist. The public projector has no generic object serializer.

## Generative boundaries

Hosted models can inspect public code, synthetic fixtures, public papers, and redacted method questions. They cannot inspect private HPO identifiers, variants, coordinates, sample metadata, private rankings, private logs, or dossier text. A local offline model may draft private prose later, but it cannot alter candidate facts, evidence tiers, scores, or state. The deterministic renderer is the required fallback.

## Example trace

A synthetic VCF contains a rare loss-of-function observation and two rare missense observations in one synthetic disease gene. The manifest and reference receipts pass. The pipeline normalizes all observations, preserves the single finding and proposed pair shapes, attaches synthetic phenotype and quality evidence, and writes a ranked dossier. A changed reference digest makes replay fail before candidate generation. The public projection reports the method and aggregate counts without emitting a coordinate or genotype.
