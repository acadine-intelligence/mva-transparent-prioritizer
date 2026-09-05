# Dual-lane prioritisation methods

Private working note, revised 2026-09-05. This checkout is not approved for sharing.

## Research question

How do separate coding and genome-wide prioritisation lanes change the candidate set on the same input? Which differences persist when configuration and reference versions are controlled?

Candidate-set expansion describes the output of a search. It does not establish diagnostic improvement. A high phenotype score is a prioritisation signal whose clinical relevance needs specialist review and additional evidence.

## Existing method

The project has a coding lane and a complementary Genomiser lane. The noncoding configuration uses ReMM > 0.914 OR SpliceAI > 0.1. The recorded tool is Exomiser 15.1.0, with hg38 data release 2602 and ReMM v0.4. Public acquisition provenance is documented separately.

The original private runs and their comparisons remain frozen on the encrypted analysis host. A read-only check on 2026-09-05 matched the noncoding run receipt to its recorded SHA-256. That check establishes receipt identity; it does not revalidate every referenced output or the whole analysis.

`clinical_probability: false` and `hidden_top_n: null` remain required. Detailed candidate review belongs inside the private workspace.

## Count interpretation

Report TSV rows separately from unique entities. A gene table can repeat a gene for different inheritance modes. A variant table can repeat a variant across associations.

The difference between gene rows and unique genes is the number of extra rows. It does not identify how many genes have multiple inheritance modes. For example, one synthetic gene with four rows and another with one row produce three extra rows, although only one gene repeats.

The count-basis utility now checks a specific receipt shape. It checks arithmetic and field meaning. It does not read original TSVs or automatically validate frozen run receipts. See [the count-basis contract](13-count-basis.md).

## Review limits

Two earlier detached reviews checked the derivative bundle they received. Their conclusions apply to that bundle. They do not establish clinical validity or the privacy of the entire workflow.

Earlier revisions of this note included case-derived candidate details and unsupported claims about clinical signal. This revision removes those details and withdraws those claims. Git history and prior chat still contain the earlier material. A pattern scan of the current tree cannot establish that the repository or previous interactions are safe to publish. Sharing requires a reviewed clean export and a separate disclosure assessment.

## Threshold sensitivity

ReMM 0.963 is a candidate research threshold discussed in the cited literature in [the Track 1 research](10-track-1-scoring-and-next-evidence-lane.md). It is not a universal clinical threshold.

The previously staged post-hoc script is superseded and must not run. A read-only schema probe found that its assumed `variant.scores` structure is absent from the first frozen JSONL record. The script also changes permissions on the frozen run directory before reading. Its error path can leave that directory writable.

Even a corrected reader would answer only a survivor-retention question. Filtering final records can leave gene scores or compound-pair evidence inconsistent with the new candidate set. It cannot be called equivalent to a full rerun without demonstrating that equivalence for the actual pipeline.

The executable synthetic counterexample in `scripts/check_threshold_equivalence.py` illustrates the problem. Filtering final records retains one record after its partner fails the stricter cutoff. Recomputing the pair requirement retains zero records. This is a toy counterexample, not an Exomiser result or patient analysis.

## Public synthetic benchmark

The existing 14-case benchmark tests selected behaviors in the project's Python implementation. Its run identifier is `benchmark-4df1927aced6a317`. Passing those fixtures establishes those checks only. It does not prove that the full Exomiser workflow implements the same semantics or that it improves diagnosis.

The next test should exercise the pinned Exomiser implementation directly with public synthetic input. The same configuration and references should run at both thresholds. Comparison must include compound pairs and reranked output.

## AI disclosure

On 2026-09-05, a GLM-5.3 request received a fixed generic methods question with no patient values. The response raised the pair-dependency counterexample. The parent implemented and executed a synthetic test rather than accepting the model's advice as proof. The model's suggested minimum number of test cases has no established statistical justification here.

The complete methods disclosure still needs a verified record of every provider used, account plan, and applicable data-handling settings. It must distinguish public research from any private-derived material that entered earlier model context. A blanket claim of zero exposure is unsupported.

## Next work

The implementation sequence and submission checklist are in [the next evidence plan](14-mva-next-evidence-plan.md). Publication and challenge submission require Jonathan's separate approval.
