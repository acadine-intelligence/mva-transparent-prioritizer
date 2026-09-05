# Private sensitivity design: ReMM 0.963 on the frozen noncoding lane

Status: design for approval, revision 2. Nothing here has run against private data. Written 2026-09-05 after the engine probe in `docs/17-exomiser-probe.md`. Revision 2 corrects the output path and the input file after a public round-trip through the real `JsonResultsWriter`.

## Question

If the noncoding lane had used the engine's compiled `PATHOGENIC_THRESHOLD` (0.963) instead of `LIKELY_PATHOGENIC_THRESHOLD` (0.914), which of the 365 lane-2 variants and 243 genes would remain, and which recessive candidates would lose their partner and drop out?

This is a descriptive robustness question about the frozen run. It is not a diagnostic claim. A candidate surviving both cutoffs is a candidate with a stronger ReMM score, nothing more.

## Why the old script cannot answer it

The staged post-hoc script (`/tmp/mva-remm963-staged.sh`, never run) read the JSONL as flat variant records and kept rows above 0.963. Three defects, each now confirmed against the engine:

1. `JsonResultsWriter` emits one gene object per line, with variants nested under `variantEvaluations`. The flat reader would have parsed nothing.
2. Keeping a record keeps its baseline `compatibleInheritanceModes`. The probe showed the real annotator drops recessive compatibility when the partner is gone, and drops the survivor entirely when its own frequency exceeds the dominant cutoff.
3. The script changed permissions on the frozen directory to read it. The frozen lane must stay byte-identical.

## What the frozen JSONL does and does not contain

A public round-trip on 2026-09-05 serialized six synthetic genes through the real `JsonResultsWriter` from the hash-verified `exomiser-core-15.1.0.jar` (`runtime/exomiser-probe-20260905/roundtrip/`). The writer uses `JsonInclude.Include.NON_DEFAULT` and a mixin that exposes only the svart coordinate accessors. The variant objects it wrote contain: `contigName`, `start`, `end`, `ref`, `alt`, `type`, `length`, `filterStatus`, `passedFilterTypes`, `failedFilterTypes`, `frequencyData.frequencies[].source/.frequency`, `pathogenicityData.pathogenicityScores[].source/.score`, `compatibleInheritanceModes`, and the scalar scores.

They do not contain `variantEffect`, `nonCodingVariant`, `whiteListed`, `sampleGenotypes`, or `transcriptAnnotations`. The `@JsonPropertyOrder` on `VariantEvaluation` lists those names, but the fields carry no `@JsonProperty` and the accessors are not bean getters, so Jackson skips them. The gene objects likewise omit `compatibleInheritanceModes` when the analyser did not set them.

Consequence: the JSONL alone cannot drive the filter mirror (no coding/noncoding flag, no whitelist flag) or the annotator (no genotype). Revision 1 of this design was wrong on that point.

The frozen lane was written with `outputFormats: [JSON, TSV_GENE, TSV_VARIANT, VCF]`, `outputFileName: lane2-genome`, `outputContributingVariantsOnly: false`, `numGenes: 0`, and `analysisMode: PASS_ONLY` (from the run's own analysis file, private path redacted here). PASS_ONLY means variants that failed the baseline 0.914 filter were never written, so the recomputation can only move variants out of the lane, never in; that is the intended direction for a stricter cutoff.

The frozen lane also contains `lane2-genome.variants.tsv`. `TsvVariantResultsWriter` emits per row: `GENOTYPE` from `genotypeString()`, `FUNCTIONAL_CLASS` from `variantEffect().getSequenceOntologyTerm()`, `WHITELIST_VARIANT` as 0/1, `CONTIG`, `START`, `END`, `REF`, `ALT`, `MOI`, `ALL_FREQ` as `source=value,...`, and `ALL_PATH` as `source=value,...`. Every field both stages need is there, with one row per variant per compatible mode.

## Method

Two-stage recomputation on the encrypted M1, reading the frozen TSV read-only, writing to a new directory that is a sibling of the frozen run.

Stage 1, filter. Collapse TSV rows to unique `CONTIG|START|REF|ALT` keys within each gene. For each key, apply the validated mirror of `PathogenicityFilter.filterNonCoding` at 0.963. Inputs: `WHITELIST_VARIANT`; coding/noncoding decided by mapping `FUNCTIONAL_CLASS` back to `VariantEffect` and calling `VariantEffects.isNonCodingVariant`; the REMM, SpliceAI, and CADD entries parsed from `ALL_PATH`. Coding variants pass unchanged (`Target.NON_CODING`). Whitelisted variants pass.

Stage 2, inheritance. For each gene, rebuild each stage-1 survivor as a `VariantEvaluation` from `CONTIG`, `START`, `REF`, `ALT`, the `VariantEffect` from `FUNCTIONAL_CLASS`, the genotype from `GENOTYPE`, and `FrequencyData` from `ALL_FREQ`. Feed the survivors to the real `InheritanceModeAnnotator` with `InheritanceModeOptions.defaults()` and the single-proband pedigree. A gene with no compatible mode after stage 2 is removed.

Stage 2 runs the engine's own class on the M1 with the installed JDK and the installed `exomiser-core-15.1.0.jar`, both already hash-verified in the reference bundle. No source is modified. No reference database is opened. `runtime/exomiser-probe-20260905/RoundTrip.java` is the template for object construction.

Consistency check before either stage: the set of unique keys in the TSV must equal the set of variant `start`/`ref`/`alt` triples across the JSONL gene objects, and each TSV row's `MOI` must appear in the matching JSONL variant's `compatibleInheritanceModes`. Any mismatch stops the run.

## Paths

Frozen input, read-only, hash checked against `receipt.json` in the frozen run directory immediately before reading:
`analysis/noncoding/2026-09-02/lane2-run-1/results/lane2-genome.variants.tsv`
`analysis/noncoding/2026-09-02/lane2-run-1/results/lane2-genome.jsonl` (consistency check only)

Output, a sibling of the frozen run, created fresh and set to mode 0500 after freezing:
`analysis/noncoding/2026-09-02/lane2-run-1-sensitivity-remm963/`

Nothing is written under `lane2-run-1/`. The run script asserts that its output root does not have `lane2-run-1` as an ancestor before creating anything.

## Outputs

- A receipt binding the frozen TSV and JSONL hashes (input), the run script hash, the annotator jar hash, the JDK version, and the output hashes.
- Counts on both bases, using the count-basis receipt shape from `docs/13-count-basis.md`: variants retained by stage 1, genes retained by stage 2, unique keys and TSV-row equivalents kept separate.
- A partition of the 365 baseline variants: retained, removed by cutoff, removed by inheritance recomputation. Same for the 243 genes.
- A list of genes whose mode set changed without the gene being removed.
- The detailed per-variant and per-gene tables stay on the encrypted volume. Only the counts and the partition sizes are candidates for any later public-safe write-up, and only after Jonathan's separate approval of the exact figures.

## What it would not establish

No truth labels exist for this genome. Retention under a stricter cutoff is not evidence of causality. The private lane was run with the genome preset's filter order (pathogenicity before inheritance) and the recomputation reproduces that order, but it does not rerun phenotype scoring, gene ranking, the frequency filter, or the regulatory feature filter. Rank changes are therefore out of scope for this design; only membership and mode compatibility are recomputed.

## Prerequisites before running

1. Jonathan's explicit approval of this design.
2. A synthetic dry run on the M4, extending the round-trip already done: write the six synthetic genes through both the real `JsonResultsWriter` and the real `TsvVariantResultsWriter`, run the two-stage recomputation on that TSV, and confirm it reproduces the direct engine answer recorded in `runtime/exomiser-probe-20260905/roundtrip/engine-strict-direct.json` for all six genes. This is public work and can proceed without approval.
3. Confirm the frozen TSV and JSONL hashes match `receipt.json` in the frozen run directory immediately before reading.

Steps 1 and 3 gate the private run.

## Cost

Reading two frozen files once and running the annotator class per gene is seconds of compute. No new reference download. No disk beyond the output directory. No network.
