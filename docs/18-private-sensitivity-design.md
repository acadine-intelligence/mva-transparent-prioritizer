# Private sensitivity design: ReMM 0.963 on the frozen noncoding lane

Status: design for approval, revision 2. Nothing here has run against private data. Written 2026-09-05 after the engine probe in `docs/17-exomiser-probe.md`. Revision 2 corrects the output path and the input file after a public round-trip through the real `JsonResultsWriter`.

## Question

If the noncoding lane had used the engine's compiled `PATHOGENIC_THRESHOLD` (0.963) instead of `LIKELY_PATHOGENIC_THRESHOLD` (0.914), which of the 365 lane-2 variants and 243 genes would remain, and which recessive candidates would lose their partner and drop out?

This is a descriptive robustness question about the frozen run. It is not a diagnostic claim. A candidate surviving both cutoffs is a candidate with a stronger ReMM score, nothing more.

## Why the old script cannot answer it

The staged post-hoc script (a scratch shell script, never run, now deleted from the design) read the JSONL as flat variant records and kept rows above 0.963. Three defects, each now confirmed against the engine:

1. `JsonResultsWriter` emits one gene object per line, with variants nested under `variantEvaluations`. The flat reader would have parsed nothing.
2. Keeping a record keeps its baseline `compatibleInheritanceModes`. The probe showed the real annotator drops recessive compatibility when the partner is gone, and drops the survivor entirely when its own frequency exceeds the dominant cutoff.
3. The script changed permissions on the frozen directory to read it. The frozen lane must stay byte-identical.

## What the frozen JSONL does and does not contain

A public round-trip on 2026-09-05 serialized six synthetic genes through the real `JsonResultsWriter` from the hash-verified `exomiser-core-15.1.0.jar` (`runtime/exomiser-probe-20260905/roundtrip/`). The writer uses `JsonInclude.Include.NON_DEFAULT` and a mixin that exposes only the svart coordinate accessors. The variant objects it wrote contain: `contigName`, `start`, `end`, `ref`, `alt`, `type`, `length`, `filterStatus`, `passedFilterTypes`, `failedFilterTypes`, `frequencyData.frequencies[].source/.frequency`, `pathogenicityData.pathogenicityScores[].source/.score`, `compatibleInheritanceModes`, and the scalar scores.

They do not contain `variantEffect`, `nonCodingVariant`, `whiteListed`, `sampleGenotypes`, or `transcriptAnnotations`. The `@JsonPropertyOrder` on `VariantEvaluation` lists those names, but the fields carry no `@JsonProperty` and the accessors are not bean getters, so Jackson skips them. The gene objects likewise omit `compatibleInheritanceModes` when the analyser did not set them.

Consequence: the JSONL alone cannot drive the filter mirror (no coding/noncoding flag, no whitelist flag) or the annotator (no genotype). Revision 1 of this design was wrong on that point.

The frozen lane was written with `outputFormats: [JSON, TSV_GENE, TSV_VARIANT, VCF]`, an output file stem for the lane, `outputContributingVariantsOnly: false`, `numGenes: 0`, and `analysisMode: PASS_ONLY` (from the run's own analysis file, private path redacted here). PASS_ONLY means variants that failed the baseline 0.914 filter were never written, so the recomputation can only move variants out of the lane, never in; that is the intended direction for a stricter cutoff.

The frozen lane also contains a `<stem>.variants.tsv` written by the same run. `TsvVariantResultsWriter` emits per row: `GENOTYPE` from `genotypeString()`, `FUNCTIONAL_CLASS` from `variantEffect().getSequenceOntologyTerm()`, `WHITELIST_VARIANT` as 0/1, `CONTIG`, `START`, `END`, `REF`, `ALT`, `MOI`, `ALL_FREQ` as `source=value,...`, and `ALL_PATH` as `source=value,...`. Every field both stages need is there, with one row per variant per compatible mode.

## Method

Two-stage recomputation on the encrypted M1, reading the frozen TSV read-only, writing to a new directory that is a sibling of the frozen run.

Stage 1, filter. Collapse TSV rows to unique `CONTIG|START|REF|ALT` keys within each gene. For each key, apply the validated mirror of `PathogenicityFilter.filterNonCoding` at 0.963. Inputs: `WHITELIST_VARIANT`; coding/noncoding decided by mapping `FUNCTIONAL_CLASS` back to `VariantEffect` and calling `VariantEffects.isNonCodingVariant`; the REMM, SpliceAI, and CADD entries parsed from `ALL_PATH`. Coding variants pass unchanged (`Target.NON_CODING`). Whitelisted variants pass.

Stage 2, inheritance. For each gene, rebuild each stage-1 survivor as a `VariantEvaluation` from `CONTIG`, `START`, `REF`, `ALT`, the `VariantEffect` from `FUNCTIONAL_CLASS`, the genotype from `GENOTYPE`, and `FrequencyData` from `ALL_FREQ`. Feed the survivors to the real `InheritanceModeAnnotator` with `InheritanceModeOptions.defaults()` and the single-proband pedigree. A gene with no compatible mode after stage 2 is removed.

Stage 2 runs the engine's own class on the M1 with the installed JDK and the installed `exomiser-core-15.1.0.jar`, both already hash-verified in the reference bundle. No source is modified. No reference database is opened. `runtime/exomiser-probe-20260905/RoundTrip.java` is the template for object construction.

Row model. `TsvVariantResultsWriter` walks `GeneScoreRanker.rankedVariants()`: one gene score per compatible mode, and under each, every variant compatible with that mode. A variant compatible with both dominant and recessive therefore appears twice, once per `MOI`. Collapsing rows to `CONTIG|START|REF|ALT` within a gene recovers the unique variant; the set of `MOI` values across its rows recovers its baseline mode set. The lane's 454 rows over 365 unique keys are this multiplicity.

Consistency check before either stage: the set of unique `CONTIG|START|REF|ALT` keys in the TSV must equal the set of `contigName`/`start`/`ref`/`alt` tuples across the JSONL gene objects, and each TSV row's `MOI` must appear in the matching JSONL variant's `compatibleInheritanceModes`. The key carries the contig because on whole-genome data start/ref/alt alone can collide across chromosomes. Any mismatch stops the run.

## Paths

The frozen run directory and the sensitivity output directory are named in the private run script on the encrypted volume, never in this public tree. Their relationship is what matters here:

- Frozen input: the `results/` directory of the frozen noncoding run, opened read-only. The variants TSV is the working input; the JSONL is read only for the consistency check. Both hashes are checked against the freeze receipt in the frozen run directory (its `outputs` block keys each results file by name with `bytes`, `mode` and `sha256`; TSV entries also carry `rows_excluding_header`) immediately before reading.
- Output: a new directory that is a sibling of the frozen run directory, its name derived from the frozen run's name plus a `-sensitivity-remm963` suffix, created fresh and set to mode 0500 after freezing.

Nothing is written under the frozen run directory. The run script asserts that its output root does not have the frozen run directory as an ancestor before creating anything.

## Commands the private run executes

Two commands, both already exercised on the synthetic fixtures in this tree:

1. `java -cp <exomiser-core jars> Recompute <frozen variants TSV> <proband> <sibling>/recompute-summary.json <sibling>/recompute-detail.json`, using `runtime/exomiser-probe-20260905/Recompute.java` unchanged, compiled against the installed and hash-verified `exomiser-core-15.1.0.jar` on the encrypted volume. It reads the TSV once, writes the two JSON files, and prints one line of counts.
2. `python3 -m mva_prioritizer.cli sensitivity-partition --detail <sibling>/recompute-detail.json --output <sibling>/partition-receipt.json`. This turns the detail file into the count-basis receipt from `docs/13-count-basis.md` plus the three-way partitions below. The detail file is opened once without following symlinks, checked as a regular file on the open descriptor, bounded at 64 MiB on `fstat` and again on the bytes read, and parsed with duplicate object keys rejected. Any internal inconsistency, an existing output file, or a non-regular input fails closed with exit 2 and one bounded line on stderr. Gene symbols are omitted unless `--include-symbols` is passed. The symbol list stays on the encrypted volume.

`mva_prioritizer/sensitivity_partition.py` and `tests/test_sensitivity_partition.py` pin the arithmetic on the synthetic detail file (`tests/fixtures/exomiser_recompute_detail.json`): 9 baseline keys partition into 5 retained, 3 removed by cutoff, 1 removed by inheritance; 5 genes into 4 retained, 0 removed by cutoff, 1 removed by inheritance; 2 retained genes change mode set. The module fails closed on: a variant key listed under two genes (the unique-key basis counts each key once), a strict mode set that is not a subset of the baseline (a stricter cutoff cannot add a mode), `tsv_rows` that differs from the sum of baseline mode counts (one row per variant per mode), unexpected fields at any level, survivor counts or mode unions that disagree between gene and variant level, and unknown mode names. `tests/test_sensitivity_partition_mutations.py` disables each of the 18 guards in `sensitivity_partition.py` and `bounded_input.py` in turn, in a scratch copy, and asserts the named test fails; it runs as part of the declared test suite, so the claim is checked on every verification run rather than asserted here.

## Outputs

- A receipt binding the frozen TSV and JSONL hashes (input), the run script hash, the annotator jar hash, the JDK version, and the output hashes.
- Counts on both bases, using the count-basis receipt shape from `docs/13-count-basis.md`: variants retained by stage 1, genes retained by stage 2, unique keys and TSV-row equivalents kept separate.
- A partition of the 365 baseline variants: retained, removed by cutoff, removed by inheritance recomputation. Same for the 243 genes. Produced by `sensitivity-partition`, with the strict lane's row-basis count being one row per retained variant per strict mode, the same multiplicity the frozen TSV uses.
- A count of retained genes whose mode set changed; the symbols themselves only with `--include-symbols`, and only on the encrypted volume.
- The detailed per-variant and per-gene tables stay on the encrypted volume. Only the counts and the partition sizes are candidates for any later public-safe write-up, and only after Jonathan's separate approval of the exact figures.

## What it would not establish

No truth labels exist for this genome. Retention under a stricter cutoff is not evidence of causality. The private lane was run with the genome preset's filter order (pathogenicity before inheritance) and the recomputation reproduces that order, but it does not rerun phenotype scoring, gene ranking, the frequency filter, or the regulatory feature filter. Rank changes are therefore out of scope for this design; only membership and mode compatibility are recomputed.

## Prerequisites before running

1. Jonathan's explicit approval of this design.
2. Done 2026-09-05. The six synthetic genes were run through the baseline filter and inheritance analysis, reduced with PASS_ONLY semantics exactly as `PassOnlyAnalysisRunner.getGenesWithVariants` does (failed variants removed, empty genes dropped; SYNG4 disappears), then written through the real `TsvVariantResultsWriter` (16 rows, 9 unique variants, 5 genes, no duplicate rows). `runtime/exomiser-probe-20260905/Recompute.java` read only that TSV, applied the mirror at 0.963, rebuilt survivors, and asked the real `InheritanceModeAnnotator`. Its output equals the direct in-memory engine answer on every written gene (`tests/fixtures/exomiser_recompute_from_tsv.json` against `exomiser_roundtrip_strict.json`, pinned by `tests/test_exomiser_tsv_recompute_fixture.py`). Nine input mutations were run against the recomputation; the mutated TSVs, each output or failure, and a manifest are checked in under `tests/fixtures/exomiser_recompute_mutations/`, and a test recomputes the breakdown from those files: six changed the answer as the engine logic predicts (partner REMM raised, survivor frequency lowered, genotype made homozygous, coding class changed to intronic, partner whitelisted, REMM placed exactly at 0.963), one left it unchanged by design (REMM 0.9630001, strict `>`), and two failed closed (renamed GENOTYPE column, unknown SO term). `Recompute.java` is the script the private run would execute unchanged, with the frozen TSV path and the real proband name as arguments.
3. Confirm the frozen TSV and JSONL hashes match the freeze receipt in the frozen run directory immediately before reading.

Steps 1 and 3 gate the private run. Step 2 is complete.

## Cost

Reading two frozen files once and running the annotator class per gene is seconds of compute. No new reference download. No disk beyond the output directory. No network.
