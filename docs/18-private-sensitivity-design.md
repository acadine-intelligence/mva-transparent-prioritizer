# Private sensitivity design: ReMM 0.963 on the frozen noncoding lane

Status: design for approval. Nothing here has run against private data. Written 2026-09-05 after the engine probe in `docs/17-exomiser-probe.md`.

## Question

If the noncoding lane had used the engine's compiled `PATHOGENIC_THRESHOLD` (0.963) instead of `LIKELY_PATHOGENIC_THRESHOLD` (0.914), which of the 365 lane-2 variants and 243 genes would remain, and which recessive candidates would lose their partner and drop out?

This is a descriptive robustness question about the frozen run. It is not a diagnostic claim. A candidate surviving both cutoffs is a candidate with a stronger ReMM score, nothing more.

## Why the old script cannot answer it

The staged post-hoc script (`/tmp/mva-remm963-staged.sh`, never run) read the JSONL as flat variant records and kept rows above 0.963. Three defects, each now confirmed against the engine:

1. `JsonResultsWriter` emits one gene object per line, with variants nested under `variantEvaluations`. The flat reader would have parsed nothing.
2. Keeping a record keeps its baseline `compatibleInheritanceModes`. The probe showed the real annotator drops recessive compatibility when the partner is gone, and drops the survivor entirely when its own frequency exceeds the dominant cutoff.
3. The script changed permissions on the frozen directory to read it. The frozen lane must stay byte-identical.

## Method

Two-stage recomputation on the encrypted M1, reading the frozen JSONL read-only, writing to a new sibling directory.

Stage 1, filter. For each gene object and each variant in `variantEvaluations`: apply the validated mirror of `PathogenicityFilter.filterNonCoding` at 0.963. Inputs are exactly the serialized fields: `nonCodingVariant`, `whiteListed`, `pathogenicityData.pathogenicityScores[].source` and `.score`. Coding variants pass unchanged (`Target.NON_CODING`). Whitelisted variants pass. The CADD and SpliceAI branches are kept in the mirror even though the genome preset supplies no CADD, so the mirror cannot silently diverge from the engine.

Stage 2, inheritance. For each gene, feed the stage-1 survivors to the real `InheritanceModeAnnotator` with `InheritanceModeOptions.defaults()` and the single-proband pedigree. Reconstruct each `VariantEvaluation` from the serialized `contigId`, `start`, `ref`, `alt`, `variantEffect`, `sampleGenotypes`, `pathogenicityData`, and `frequencyData`. A gene with no compatible mode after stage 2 is removed.

Stage 2 runs the engine's own class on the M1 with the installed JDK and the installed `exomiser-core-15.1.0.jar`, both already hash-verified in the reference bundle. No source is modified. No reference database is opened. The probe in `runtime/exomiser-probe-20260905/` is the template.

## Outputs

All under a new directory `analysis/noncoding/2026-09-02/lane2-run-1/sensitivity-remm963/`, mode 0500 after freezing, never inside the frozen result tree:

- A receipt binding the frozen JSONL hash (input), the mirror source hash, the annotator jar hash, the JDK version, and the output hashes.
- Counts on both bases, using the count-basis receipt shape from `docs/13-count-basis.md`: variants retained by stage 1, genes retained by stage 2, unique keys and TSV-row equivalents kept separate.
- A partition of the 365 baseline variants: retained, removed by cutoff, removed by inheritance recomputation. Same for the 243 genes.
- A list of genes whose mode set changed without the gene being removed.
- The detailed per-variant and per-gene tables stay on the encrypted volume. Only the counts and the partition sizes are candidates for any later public-safe write-up, and only after Jonathan's separate approval of the exact figures.

## What it would not establish

No truth labels exist for this genome. Retention under a stricter cutoff is not evidence of causality. The private lane was run with the genome preset's filter order (pathogenicity before inheritance) and the recomputation reproduces that order, but it does not rerun phenotype scoring, gene ranking, the frequency filter, or the regulatory feature filter. Rank changes are therefore out of scope for this design; only membership and mode compatibility are recomputed.

## Prerequisites before running

1. Jonathan's explicit approval of this design.
2. A synthetic dry run on the M4: serialize the probe's synthetic pairs through the real `JsonResultsWriter`, then feed that JSONL through the two-stage recomputation and confirm it reproduces the probe's expected outcome. This closes the gap between "the mirror agrees with the engine on objects I built" and "the mirror agrees with the engine on objects the writer serialized."
3. Confirm the frozen JSONL hash matches `lane2-run-1-receipt.json` immediately before reading.

Step 2 is public work and can proceed without approval. Steps 1 and 3 gate the private run.

## Cost

Reading the frozen JSONL once and running the annotator class per gene is seconds of compute. No new reference download. No disk beyond the output directory. No network.
