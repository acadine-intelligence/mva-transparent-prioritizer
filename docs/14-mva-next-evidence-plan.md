# MVA next evidence plan

Decision date: 2026-09-05. Scope: private local development and public synthetic tests. Jonathan asked to continue the MVA work. This does not authorize publication, repository push, or challenge submission.

## Selected next experiment

Test threshold changes in the pinned Exomiser implementation with synthetic input before interpreting private sensitivity results.

The useful question is whether stricter filtering preserves defensible findings after inheritance and ranking are recomputed. A larger candidate set by itself cannot answer that question.

The old post-hoc sensitivity script is superseded. Its JSONL reader does not match the frozen file. It also changes the frozen directory's permissions. Do not execute it or treat its staged hash as a validity check.

## Work completed in this pass

The count-basis validator now rejects empty or unrelated payloads. It validates count types and exact bases. Partitions must reconcile each lane as well as the union. The gene helper labels extra rows correctly. The CLI reports malformed JSON without dumping input values.

`verify.sh` now executes the count-basis fixture and the threshold counterexample alongside the existing checks. The counterexample produces one retained record under final-record filtering and zero after recomputing the pair requirement. It demonstrates a possible error in the shortcut. It does not measure that error in Exomiser.

A generic GLM-5.3 critique informed the counterexample. Its input contained no patient values. Its response is advice, with parent-run tests as the check on the implemented behavior.

## Pinned-source findings

A read-only inspection confirmed the clean Exomiser source checkout at `98f4e0b6f2f3f5bf790a9f955808c98968559996`.

- `JsonResultsWriter.writeFile` serializes one gene object per line. It does not write one top-level `variant.scores` object per line.
- `PathogenicityFilter.filterNonCoding` compares ReMM with the compiled `LIKELY_PATHOGENIC_THRESHOLD` constant. `RemmScore` defines that constant as 0.914 and a separate `PATHOGENIC_THRESHOLD` as 0.963. A properties-file edit alone has not been shown to change the filter.
- The genome preset puts pathogenicity filtering before inheritance filtering. Its priority-score filter and regulatory filter also differ from the exome preset. A coding-versus-genome comparison changes several factors at once.
- The filter preserves coding variants for `Target.NON_CODING` and has a whitelist bypass. Its generic implementation also has a CADD branch, although the inspected genome preset does not request CADD. A faithful sensitivity test must account for these branches.

Pinned source: [preset](https://github.com/exomiser/Exomiser/blob/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/analysis/AnalysisPresetBuilder.java), [filter](https://github.com/exomiser/Exomiser/blob/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/filters/PathogenicityFilter.java), [threshold constants](https://github.com/exomiser/Exomiser/blob/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/model/pathogenicity/RemmScore.java), [writer](https://github.com/exomiser/Exomiser/blob/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/writers/JsonResultsWriter.java).

## Execution sequence

Steps 1 to 3 were completed on 2026-09-05 at class level; see `docs/17-exomiser-probe.md`. The ReMM cutoff is a compiled constant with no configuration path in 15.1.0. A validated mirror of the filter logic reproduces the engine at the baseline constant on all 17 comparisons. The compound-pair probe against the real annotator confirms that a rerun drops the recessive mode that post-hoc filtering would retain. A full reference-backed CLI comparison at both cutoffs remains undone.

Work since that pass (all public and synthetic, see `docs/18-private-sensitivity-design.md`): the recomputation was pushed through the real writers and runners, the TSV-driven two-stage recomputation reproduces the direct engine answer on synthetic genes, the partition module and CLI turn a recomputation detail file into the count-basis receipt, and a driver script implements every precondition the private run must satisfy. Each stage passed an independent exact-commit review; the guards (36) are swept in-tree as part of the declared suite.

The two public sources identified in the loop-9 pass are now fetched and verified in full; verified claims, citation details and the limits of what they support are recorded in `docs/19-verified-public-sources.md`. PhEval supports only the reproducibility argument; the circularity/temporal-leakage framing is dropped for lack of a source.

The Track 1 gate is pinned at Space revision `1c761cc2` with a local validator and a scorer mirror verified against the official file (`docs/20-track1-submission-gate.md`); no candidate file exists and none is authorized.

1. ~~Select and test an explicit way to change the pinned engine's ReMM cutoff.~~ Done at class level. A full-pipeline stricter run requires a source change and rebuilt jar, or the validated mirror applied before inheritance annotation.
2. ~~Build a public synthetic fixture with a compound pair across the threshold boundary.~~ Done: `tests/fixtures/exomiser_probe_output.json`.
3. ~~Run the pinned implementation at both thresholds.~~ Done for the filter and annotator classes. Not done for the full CLI with reference data.
4. The private ReMM 0.963 recomputation is fully designed (`docs/18-private-sensitivity-design.md`), its driver implemented and adversarially reviewed on synthetic trees (`scripts/run_sensitivity_remm963.py`), and every command it executes exercised end to end on synthetic data. It runs only on Jonathan's explicit approval of that design; the approval request is open. It still requires, at run time, the encrypted volume mounted and the reference-backed CLI comparison at both cutoffs if that stage is separately approved.
5. Prepare a private specialist-review dossier from the verified lanes. Preserve uncertain phase and gene-disease validity. Keep candidate scores distinct from clinical probability.

Stop if the test depends on a guessed JSON field, reference mismatch, or altered frozen evidence. Resolve that defect before running private sensitivity.

## Submission package checklist

These items are preparation requirements. The rule values below come from the research captured on 2026-08-31. Re-fetch official instructions and scoring code before treating them as current.

- [ ] Pin current official instructions, evaluator code, template, and challenge configuration with retrieval dates and hashes.
- [ ] Verify the recorded Track 1 limits against those sources: at most 10 rows, EPCR in `(0, 1]`, and the current upload allowance. Recheck pair scoring and tie handling.
- [ ] Build the candidate CSV locally with explicit variant representation. Validate optional second-variant columns and repeated variants with a synthetic scorer first.
- [ ] Have a qualified reviewer assess the private findings. Preserve inheritance uncertainty and missing evidence.
- [ ] Write the methods report with exact software versions and reference provenance. Include sensitivity limits and the absence of diagnostic-performance validation.
- [ ] Complete the AI disclosure with verified provider plans and data settings. Audit prior private-derived model context before making any privacy claim.
- [ ] Create a clean export that excludes Git history and private artifacts. Review every exported file. A clean regex scan alone is insufficient.
- [ ] Obtain Jonathan's approval for the exact outgoing package and destination. Recheck its hash immediately before any upload.

No submission file has been generated in this pass. No upload allowance has been used by this pass.

## Official source pointers

- [Track 1 instructions](https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/tabs/submit_track1.py)
- [Evaluator](https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/evaluation.py)
- [CSV template](https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/static/templates/track1_submission_template.csv)
- [Challenge configuration](https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/config.py)

## Evidence locations

The count-basis contract is `docs/13-count-basis.md`. The corrected methods note is `docs/12-dual-lane-evidence.md`. This pass stores generic model requests, model responses, and execution logs under the ignored local directory `runtime/method-audit-20260905/`. Those logs are review inputs, not publication approval.
