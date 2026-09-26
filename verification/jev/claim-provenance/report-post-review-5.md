# Claim-provenance pass, docs/22 after the fifth review

Backend: Jev (`jev-latest`) through `~/projects/rlcd/bin/decide`, one call, 14,875 input tokens, 760 output tokens, 1,693 ms. Same question and builder as the previous passes (`build_claims.py`, excerpts from tracked files only; the builder asserts no excerpt carries a denylisted token).

## Result

| bucket | claims |
|---|---|
| supported (Jev >= 0.5) | 38 |
| below 0.5, checked by hand against the source | 2 |
| host-local artifact, excerpt withheld by design | 2 |
| total | 42 |

New in this pass: the D4 count of the regenerated `verify-module-result.txt` (8,305), the schedule test's two assertions, the widened denylist fields, the measured divergence counts, and the review-history entry for `25d0b47`. Nothing was found false.

### Below 0.5, checked by hand

- **c30** (0.37) The schedule test asserts the batch file and asserts the step file is not produced, on the pool from the review of 28761f8. Source `tests/test_candidate_selection.py`: the excerpt window opens after the test's comment, which names the pool as the one from the review of 28761f8; the two assertions the claim names are inside the window. Claim holds.
- **c31** (0.38) The review of 25d0b47 found the tracked verify_module receipt was produced by an intermediate module and the schedule test did not separate the schedules. Source `verification/reviews/25d0b47.json`: the window holds finding B1 (the 7,982 against 8,305 receipt) and cuts before B2 (the schedule test); B2 is at the next key of the same file. Claim holds.

### Host-local, withheld

- **c38** (0.13) The frozen interval map at runtime/nine-gene-audit-20260909/gene-interval-map.json is host-local and not in the public tree. `runtime/nine-gene-audit-20260909/gene-interval-map.json` is ignored by Git and its contents are not excerpted.
- **c39** (0.16) The literature-overlay artifacts in runtime/internal-review-20260907/ are host-local. `runtime/internal-review-20260907/research-review.md` is ignored by Git and its contents are not excerpted.

### Supported

- c01 (0.67) Insert-and-shift promotion lowered 5,220 scores in 327,600 comparisons at four rows (`verification/reviews/741aaad.json`)
- c02 (0.57) batch/floor+pays_gt has mean rank points 34.895 and 10 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c03 (0.81) batch/transitive+pays_gt has 589 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c04 (0.90) batch/direct+keep has 44 and batch/direct+demote has 34 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c05 (0.77) The module keeps a losing pair only where points(r) > 0.5 * points(q) (`mva_prioritizer/candidate_selection.py`)
- c06 (0.74) The module removes a losing pair when a single for its unshared allele already sits above it (`mva_prioritizer/candidate_selection.py`)
- c07 (0.62) resolve_rows promotes to a fixpoint, then demotes to a fixpoint, and repeats until a round changes nothing (`mva_prioritizer/candidate_selection.py`)
- c08 (0.82) The probe's docstring states every policy is implemented inside the file and the module is measured as its own row (`verification/scorer-hedging/policy_probe.py`)
- c09 (0.75) The probe defines two schedules, step and batch, and builds a policy for each schedule, promotion mode and STAGE3 entry (`verification/scorer-hedging/policy_probe.py`)
- c10 (0.74) 36,033 truth comparisons over 3,000 random pools from 10 alleles in 4 genes, 4/3/2/1 per gene, tiers A/B/C (`verification/scorer-hedging/policy-probe-result.txt`)
- c11 (0.84) batch/direct+pays_gt has 0 below and mean 36.357; step/direct+pays_gt has 0 below and mean 36.353 (`verification/scorer-hedging/policy-probe-result.txt`)
- c12 (0.94) batch/direct+pays_ge has 0 below and mean 36.155 (`verification/scorer-hedging/policy-probe-result.txt`)
- c13 (0.89) batch/direct+demote has mean 36.296 and 34 below; batch/direct+keep has mean 35.899 and 44 below (`verification/scorer-hedging/policy-probe-result.txt`)
- c14 (0.69) The best eligible policy is batch/direct+pays_gt and the module coincides with it on every pool under two seeds (`verification/scorer-hedging/policy-probe-result.txt`)
- c15 (0.78) verify_module.py reports zero pools with a permutation-dependent result (`verification/scorer-hedging/verify-module-result.txt`)
- c16 (0.83) verify_module.py reports zero rank-point comparisons lower than the plain sort over 20,245 (`verification/scorer-hedging/verify-module-result.txt`)
- c17 (0.91) verify_module.py reports zero kept sharing pairs at a rank that does not strictly pay (`verification/scorer-hedging/verify-module-result.txt`)
- c18 (0.73) brute_force_hedging.py returns 1 when strict violations are found, so it exits non-zero by design (`verification/scorer-hedging/brute_force_hedging.py`)
- c19 (0.83) hedging_modes.py main() returns 0, so it exits zero (`verification/scorer-hedging/hedging_modes.py`)
- c20 (0.59) verify_determinism.py imports only the standard library and does not import the evaluator (`verification/scorer-hedging/verify_determinism.py`)
- c21 (0.74) The evaluator bytes are pinned by SHA-256 in tests/test_track1_submission.py (`tests/test_track1_submission.py`)
- c22 (0.85) Rank points is metric 1 in the official evaluator (`tools/official-track1/evaluation.py`)
- c23 (0.78) case-token-scan running scripts/verify_no_case_tokens.py is a required Build OS command in product.json (`product.json`)
- c24 (0.92) The gate exits 2 with denylist_missing when the denylist file is absent (`scripts/verify_no_case_tokens.py`)
- c25 (0.85) The gate has a --history flag that scans every blob reachable from any ref (`scripts/verify_no_case_tokens.py`)
- c26 (0.59) build_case_token_denylist.py reads the interval map, the HGNC responses and the aggregate report, and writes runtime/privacy/denied-tokens.txt (`scripts/build_case_token_denylist.py`)
- c27 (0.81) build_case_token_denylist.py takes alias_symbol and prev_symbol from the HGNC responses (`scripts/build_case_token_denylist.py`)
- c28 (0.66) build_case_token_denylist.py also takes Entrez, Ensembl gene, RefSeq, OMIM, CCDS, UniProt and MANE ids from the HGNC responses (`scripts/build_case_token_denylist.py`)
- c29 (0.92) verify-module-result.txt reports 8,305 comparisons with rank points higher than the plain sort and 0 lower (`verification/scorer-hedging/verify-module-result.txt`)
- c32 (0.69) The two schedules diverge on 22 of the 3,000 tracked pools (`docs/22-candidate-selection-rule.md`)
- c33 (0.64) The review of 1783250 returned FAIL (`verification/reviews/1783250.json`)
- c34 (0.64) The review of 28761f8 returned FAIL with blocking findings B1 and B2 (`verification/reviews/28761f8.json`)
- c35 (0.69) B1 of 28761f8: the probe demoted to a fixpoint before re-promoting while the module re-promoted after every demotion, hidden by a universe with at most three alleles per gene (`verification/reviews/28761f8.json`)
- c36 (0.51) B2 of 28761f8: the sentence giving always-demote the highest raw mean at 46.574 was false against the tracked result, where direct+pays_gt scored 46.833 (`verification/reviews/28761f8.json`)
- c37 (0.60) The second Jev pass on 1783250 covered 71 claims in 4 calls (`verification/jev/claim-provenance/report-1783250.md`)
- c40 (0.83) The parser rejects repeated variant ids across rows unless allow_repeated_pairings is set (`mva_prioritizer/track1_submission.py`)
- c41 (0.68) Tier is the first key of the evidence sort, before lane count and native rank (`mva_prioritizer/candidate_selection.py`)
- c42 (0.53) docs/20 says the history scan found three historical blobs, that the fixture gene was pre-registered from literature and is also a case-flagged recurrent gene, and that both facts are checkable only from runtime/ (`docs/20-track1-submission-gate.md`)
