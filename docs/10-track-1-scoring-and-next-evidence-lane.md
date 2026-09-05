# Track 1 scoring and next evidence lane

Decision recorded: 2026-08-31

State: research proposal only. This note does not change the frozen private runs, authorize a new private run, or authorize any submission.

Privacy: this pass used public sources and content-free project facts. No protected row, HPO identifier, variant coordinate, sample metadata, private output, or private log left the encrypted M1 workspace.

## Decision

Prepare a separate run 3 proposal for a complementary Genomiser lane. Verify the `SPLICE_AI` source in the pinned Exomiser data, then add a pinned ReMM v0.4 asset. Keep the existing Exomiser coding lane unchanged and visible. Do not replace it with one combined ranking. The full asset and benchmark decision is in `docs/11-run-3-noncoding-benchmark-proposal.md`.

This is the highest-value next lane because recent benchmarks report large gains from tuned Exomiser and Genomiser settings, with a specific gain for noncoding candidates.[3][4] A separate splice benchmark found that SpliceAI and Pangolin performed best overall among the tested predictors, while also finding meaningful limits for exonic splice effects, score cutoffs, and gene-model choice.[5]

This remains a research decision. A later implementation pass must define the bundle, synthetic benchmark, acceptance checks, and review route before it touches private evidence.

## What the official score rewards

Track 1 accepts at most 10 rows. Each row can hold one variant or one proposed compound-heterozygous pair. The evaluator sorts rows by descending EPCR and preserves input order for ties.[1]

Rank points use four tiers: rank 1 earns 100 points, ranks 2 to 3 earn 50, ranks 4 to 5 earn 25, and ranks 6 to 10 earn 10.[1] An exact compound-heterozygous pair earns the full rank value. If no exact pair appears, a row that contains one true member earns half of its rank value.[1]

F-max is calculated at the individual-variant level. At each distinct EPCR threshold, the evaluator unions all variants from qualifying rows, then measures precision and recall against the answer variants.[1]

The `finding_type` field is informational and does not change the automated score.[1] The methods report is required for judging but is not scored automatically.[2]

The official template uses `proband_id, chrom_1, pos_1, ref_1, alt_1, chrom_2, pos_2, ref_2, alt_2, epcr, finding_type, notes` in that order.[8] The second-variant columns and `notes` are optional to the evaluator. The primary variant fields, `proband_id`, and `epcr` are required.[1]

The current challenge configuration allows six Track 1 uploads per Hugging Face user.[7] The instructions say that only the best-scoring submission counts.[2] No upload should be spent on a schema or representation check.

These rules create practical effects:

1. Put a plausible compound-heterozygous pair in one row. Two correct singles can recover F-max, but they cannot earn full pair rank points.[1]
2. Protect the 10-row budget. Repeating a variant adds no F-max recall. Repeated pairings can still be useful when the partner is uncertain because an exact pair changes rank points.[1]
3. Treat EPCR as an ordering field until a calibration study proves more. The submission interface says relative ranking drives scoring, and F-max sweeps the submitted thresholds.[1][2]
4. Break EPCR ties deliberately. Stable tie handling means source order becomes the final ordering rule.[1]
5. Keep secondary findings separate for human review. The label leaves automated scoring unchanged. Every row still consumes capacity.[1]
6. Normalize the final submission representation explicitly. The evaluator strips surrounding whitespace from chromosome text and uppercases alleles; it does not add or remove a `chr` prefix or otherwise change chromosome names or variant representation, so a name in the lane's own form scores zero silently.[1] The pinned code, the local validator that refuses such files before upload, and a scorer mirror verified against the official file are in `docs/20-track1-submission-gate.md`.
7. Reject malformed rows before upload. Missing required fields, more than 10 rows, EPCR outside `(0, 1]`, invalid `finding_type`, and non-integer positions fail evaluation. Blank reference or alternate alleles can pass parsing and then fail to match.[1]

The official interface expects the single challenge proband, and the scoring path evaluates one proband group from an uploaded file.[2] A local synthetic scorer should reject any extra proband group rather than relying on that behavior.

## Candidate lane comparison

| Lane | Expected contribution | Present fit | Decision |
|---|---|---|---|
| Splicing and noncoding prioritization | Can recover deep intronic or regulatory candidates missed by a coding-first lane.[3][4] | Fits the pinned Exomiser family and the existing offline model. It needs a verified bundled `SPLICE_AI` source, a new ReMM asset, and a new run lineage. | Prepare run 3 proposal first. |
| Structural variation | Can find a different class of cause. | The current content-free inspection in `docs/01-research.md` found no structural-variant header fields. A serious caller lane needs named BAM, CRAM, or FASTQ inputs and a larger compute and privacy plan. | Defer until input evidence supports it. |
| ClinGen gene-disease validity | Can test whether a candidate gene has expert-reviewed disease validity. ClinGen publishes a real-time Gene-Disease Validity download.[6] | Useful after candidate generation. It is unlikely to recover a variant omitted by the current calling and prioritization lanes. | Add to the future curation layer after snapshot pinning. |
| Updated phenotype-gene data | Can change phenotype similarity and gene order. | Exomiser data release 2602 is already pinned. Any update creates a new bundle and run lineage under `docs/REFERENCE-DATA-PLAN.md`. | Compare only after the noncoding benchmark is specified. |

## Research basis and limits

A 2025 Undiagnosed Diseases Network benchmark reported that parameter tuning increased top-10 recovery for coding diagnostic variants from 49.7% to 85.5% on genome data and from 67.3% to 88.2% on exome data. Its Genomiser top-10 result for noncoding variants increased from 15.0% to 40.0%.[3] The same study recommends Genomiser as a complementary lane because noncoding noise can lower coding-variant ranks.[3]

A 2025 Hong Kong Genome Project study used a tuned Genomiser workflow on 778 previously negative genome cases. It reported 20 deep intronic candidates, five of which were classified as pathogenic or likely pathogenic, and a 2.6% added yield for that workflow.[4] Those results came from a specific cohort, tool version, filter set, and review process. They do not prove the same yield here.

The Hong Kong study evaluated a ReMM threshold of 0.963 and reported 92.54% top-15 sensitivity in its benchmark.[4] Run 3 must treat 0.963 as a candidate test value rather than a universal threshold. A threshold copied from another cohort can overfit its noise and remove true noncoding variants.

The splice benchmark tested 3,616 variants across five genes and found lower concordance for exonic variants than intronic variants.[5] It also found that cutoff choice and gene-model annotation materially affect results.[5] A high SpliceAI score is therefore supporting evidence. It is not a diagnosis or a substitute for functional evidence.

## Run 3 proposal requirements

A future proposal should pass these checks before execution:

- Pin the exact Genomiser configuration, assembly, transcript model, source URL, size, SHA-256, and license note. Verify `SPLICE_AI` score availability and provenance in the pinned Exomiser data. Pin ReMM separately.
- Resolve noncommercial or restricted-use terms before acquisition or execution.
- Keep coding and noncoding outputs as independent evidence lanes. Show any later merge rule explicitly.
- Build the synthetic benchmark before inspecting private output.
- Include synthetic coding retention, deep intronic rescue, compound-pair recovery, false high-ReMM noise, exonic splice uncertainty, low-allele-fraction retention, and tampered-provenance cases.
- Test the official rank-point and F-max logic with synthetic truths. Include exact pairs, singles, repeated variants, repeated pairings, and EPCR ties.
- Stop on an assembly, transcript, asset, role, mode, path, hash, or receipt mismatch.
- Keep the private run offline and confined to the encrypted M1 workspace.
- Preserve full evidence rows for specialist review. Render no clinical score and apply no hidden top-N cutoff inside an evidence lane.

The proposal should compare the unchanged coding lane against the complementary lane before defining any final challenge-row ordering. It should explain each rank movement and retain candidates that only one lane finds.

## Submission method update

The Track 1 instructions added an AI disclosure on 28 August 2026. A methods report must record the provider, plan or tier, and relevant data-handling setting when an LLM or AI assistant was used.[2]

Create one verified disclosure row per provider used in the work. Record the exact account plan and data setting from the provider or account page. Do not infer or invent either value. Keep protected-case handling separate from public research assistance in the methods text.

## Sources

[1] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/evaluation.py : Official Track 1 scoring code
[2] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/tabs/submit_track1.py : Official Track 1 submission instructions
[3] https://pmc.ncbi.nlm.nih.gov/articles/PMC12539062 : Exomiser and Genomiser optimization study
[4] https://pmc.ncbi.nlm.nih.gov/articles/PMC12452281 : Genomiser clinical optimization study
[5] https://pmc.ncbi.nlm.nih.gov/articles/PMC10187268 : Splice predictor benchmark
[6] https://search.clinicalgenome.org/kb/downloads : ClinGen downloads
[7] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/config.py : Official challenge configuration
[8] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/static/templates/track1_submission_template.csv : Official Track 1 CSV template
