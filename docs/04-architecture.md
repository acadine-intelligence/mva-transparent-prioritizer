# Software architecture: MVA Transparent Prioritizer

## System context

The public source repository lives on the primary Mac. It contains code, schemas, public references, and synthetic fixtures. The private runtime lives on the 8 GB M1 inside the mounted encrypted APFS sparsebundle. Protected inputs and detailed outputs never cross that boundary. Public reference downloads may use the primary Mac, M1, or an isolated VM. The private run has network access disabled by policy and verified by an execution guard. Hosted agents see only the public source tree and public research questions. The challenge interface remains outside the product and requires a separate human-approved submission.

## Hermes integration decision

This is a standalone CLI. The product owns validation, scoring, files, receipts, and reports. Hermes owns public research support, orchestration, and content-free progress checks. Hermes cannot read or summarize the private dossier in a hosted-model session.

## Components and contracts

1. `mva-prioritize` exposes `verify-environment`, `synthetic-run`, `private-run`, `verify-run`, and `project-safe-learnings` commands.
2. `path_guard` opens the trusted private root and rejects repository overlap, symlinks, special files, traversal, and caller-controlled detailed output paths.
3. `manifest` validates controlled inputs and pinned public reference receipts before any analytical stage.
4. `phenotype` extracts explicit HPO identifiers locally and writes a private normalized set.
5. `bcftools_adapter` performs validation, normalization, statistics, and lane extraction with exact argument arrays.
6. `exomiser_adapter` runs a pinned offline release with bounded memory and threads. It preserves raw source scores in a private intermediate file.
7. `dossier` joins independent evidence lanes into versioned JSON and Markdown. It never treats a heuristic as calibrated probability.
8. `safe_projection` emits only schema-allowlisted method facts and aggregates.
9. `verify` rehashes every input, reference, intermediate, config, and output before review.

The CLI and JSON schemas are the only interfaces. There is no network API or long-running service. Schema versions follow semantic versioning. An unknown schema version fails closed.

## Data, privacy, and security

Public code and public references are shareable. Synthetic fixtures use invented identifiers and `.invalid` domains where a domain is needed. Protected inputs, HPO identifiers, variants, coordinates, genotypes, sample metadata, run logs, rankings, and dossier content stay under the encrypted private root. Private directories use mode `0700`; detailed files use mode `0600` or stricter. Source inputs remain read-only.

The recovery password stays in 1Password and enters `hdiutil` through standard input. The product never reads it. Run receipts exclude usernames, hostnames, absolute paths, secret references, and protected values. Controlled data and derived datasets follow the challenge deletion deadline. Source deletion remains a deliberate human-approved operation after recovery and submission needs are resolved.[1]

## Risks and mitigations

- Reference mismatch can corrupt normalization. The manifest binds the complete contig dictionary and reference digest. The run stops on any mismatch.
- Memory pressure can kill Exomiser or cause swapping. The adapter caps heap and threads, records peak memory, and supports staged lanes. An incomplete lane cannot produce a review-ready dossier.
- A single-sample VCF can make inheritance look stronger than the evidence supports. The dossier labels phase and parental status as unknown unless the input proves them.
- Missing structural calls can be mistaken for a negative finding. The QC stage detects caller capability from headers and emits an unresolved variant-class warning.
- Public export can leak private rows. The projector uses a fixed output schema, a seeded canary test, a forbidden-field scan, and a separate destination tree.
- A polished rank can be scientifically wrong. The dossier preserves raw evidence, source scores, conflicting lanes, and uncertainty. Independent review remains mandatory.
- Tool or reference drift can change rank. Every run binds exact versions and digests. A changed dependency creates a new run lineage.

## Operations

Bootstrap installs a project-local Python environment on the public host and a separate project runtime on the M1. A public asset script downloads pinned tools and references, verifies their published or recorded digests, and writes receipts. The private run begins with a health check for mount state, free space, memory, required binaries, reference identity, and private-root containment.

Each stage writes to a run-owned temporary directory and promotes it atomically after validation. A failed or interrupted run remains `incomplete`. Re-running the same run ID refuses overwrite. Rollback means selecting the prior verified code commit, reference bundle, and config receipt. The encrypted volume stays detached when idle.

## Sources

[1] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/blob/main/tabs/rules.py — MVA Hackathon rules
