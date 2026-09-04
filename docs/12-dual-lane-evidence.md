# 12 — Dual-lane evidence: coding and genome-wide noncoding prioritisation

Status: private draft, awaiting approval gate. Date anchor: 2026-09-04.
This document contains no protected rows. All counts are content-free and match frozen receipts.

## 1. Question

Does whole-genome noncoding prioritisation, run on the same protected genome as the coding
(uff exome-style) lane, surface candidate evidence the exome lane structurally cannot see, and
can that be demonstrated with a fully reconciled, content-free evidence chain?

## 2. Method

- Reference: Exomiser 15.1.0 (source commit `98f4e0b6f2f3f5bf790a9f955808c98968559996`),
  JDK `jdk-21.0.12.1+1`, data `2602_hg38` + ReMM v0.4 GRCh38 (acquisition run 1, closure
  receipt `7313f5d8…`).
- Lane 1 (coding): lane1-run-4, receipt `87904b1b…` (Exomiser exome preset).
- Lane 2 (noncoding): lane2-run-1, Genomiser whole-genome preset, PASS_ONLY, noncoding
  pathogenicity = ReMM > 0.914 OR SpliceAI > 0.1, HPO-driven priority, inheritance filter,
  `clinical_probability: false`, `hidden_top_n: null`. Run receipt `691454eb…`.
- Input: 5,035,176 normalized records (SHA `ad232416…`), identical for both lanes.
- Execution: encrypted volume only, no network during runs, coding lane untouched.

## 3. Results (content-free)

| Quantity | Lane 1 coding | Lane 2 noncoding |
| --- | --- | --- |
| Genes (unique symbols) | 364 (421 rows, 57 multi-MOI) | 243 (290 rows, 47 multi-MOI) |
| Variants (unique keys) | 589 (794 association rows) | 365 (454 association rows) |
| Shared | 107 genes | 165 variant keys |
| Lane-unique | 257 genes | 136 genes (noncoding-only), 424 variant keys (coding-only) |

- 161 of 165 shared variant keys change rank between lanes; delta −77 … +87.
- Top noncoding-only genes by lane-2 rank: KCNJ1 (4, pheno 0.76, var 0.98), WWTR1 (7, 0.70,
  0.93), NOS3 (14, 0.56, 0.98), COL5A1 (15), NAGPA (21), SOS1 (22), GRIA2 (26), HNRNPA2B1 (27),
  THRB (27), MEIS2 (32). 93 of 136 noncoding-only genes carry phenotype score ≥ 0.5.
- Largest shared-variant gain: rank 89 → 12 in the gene improving 41 → 8 (RBMX, disclosed with
  approval of aggregate-only framing).

Interpretation: the lanes are complementary, not redundant. The noncoding lane adds ~37% more
candidate genes than coding alone, and the additions are phenotype-supported, not noise.

## 4. Evidence custody and review protocol (methods contribution)

1. Every artifact frozen read-only, SHA-256 lineage, exact hashes not timestamps.
2. Comparison receipts state the counting basis explicitly (row-basis vs unique-key-basis);
   a reconciliation receipt (`d6c463b4…`) documents the mapping.
3. Detached review: a redacted bundle (sample redacted, coordinates and gene symbols
   pseudonymized) was reviewed by two independent reviewers with no host, network, or data
   access. Both PASS, zero blocking findings. Verdicts frozen (`2a78f34f…`, `33dd2b28…`).
4. Failed runs are preserved as failure receipts, never overwritten.

## 5. Limitations

- One protected genome; no cohort claims.
- Single threshold pair (ReMM 0.914, SpliceAI 0.1); a 0.963 sensitivity comparison is staged
  (post-hoc re-threshold of the frozen JSONL) and pending approval.
- Exomiser gene-level funnel granularity switches between stages; documented, chainability
  verified from stage 2 onward.
- No clinical interpretation, treatment claim, or diagnostic use. Research evidence only.

## 6. AI-method disclosure

Per the 2026-08-28 requirement: all analysis was executed by deterministic open-source tools
(Exomiser, bcftools, VEP); Claude/GLM agents were used for orchestration, verification authoring,
and review coordination; every substantive claim in this document traces to a frozen receipt.

## 7. Relation to the public synthetic benchmark

The public repository carries a deterministic synthetic benchmark of the same method contract
(`benchmark-4df1927aced6a317`, 14 cases, run against staged fixtures: missing scores, strict
thresholds, low-VAF retention, coding-lane preservation, compound-pair preservation). The
private lane execution is the same contract applied to the protected genome: identical
thresholds (ReMM > 0.914, SpliceAI > 0.1), identical step order, identical fail-closed
receipts. The benchmark proves the method behaves correctly on known inputs; the private run
demonstrates its evidence yield on real data without exposing that data. This separation is
deliberate: public artifacts are fully publishable, private artifacts are fully custody-bound.

## 8. Next

- Approval gate: public claims list (iteration-6 packet), write-up, ReMM 0.963 sensitivity
  (staged as a post-hoc re-threshold of frozen JSONL: `e13da6c2…`, no second run needed).
- If approved: sensitivity table joins section 3; submission package prep remains Jonathan's gate.
