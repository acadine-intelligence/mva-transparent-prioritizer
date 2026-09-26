# Claim-provenance pass, docs/22 after the sixth review

Backend: Jev (`jev-latest`) through `~/projects/rlcd/bin/decide`, one call, 17,772 input tokens, 904 output tokens, 1,787 ms. Same question and builder as the previous passes (`build_claims.py`, excerpts from tracked or staged files only; the builder asserts no excerpt carries a denylisted token).

## Result

| bucket | claims |
|---|---|
| supported (Jev >= 0.5) | 42 |
| below 0.5, checked by hand against the source | 6 |
| host-local artifact, excerpt withheld by design | 2 |
| total | 50 |

New in this pass: the `batch_rank_reading.py` numbers (differ counts and means on five seeds), the rank a loser is judged at in `_demote_once`, the scored test for the review of `c1c2c34`, the corrected seed-margin range, and the blob and branch counts in docs/20. Nothing was found false.

### Below 0.5, checked by hand

- **c31** (0.46) The schedule test asserts the batch file and asserts the step file is not produced, on the pool from the review of 28761f8. Source `tests/test_candidate_selection.py`: the window opens after the test comment that names the pool; both assertions are inside the window. Claim holds.
- **c32** (0.35) The review of 25d0b47 found the tracked verify_module receipt was produced by an intermediate module and the schedule test did not separate the schedules. Source `verification/reviews/25d0b47.json`: the window holds finding B1 (the stale receipt) and ends before B2 (the schedule test), which is the next key of the file. Claim holds.
- **c35** (0.48) batch_rank_reading.py reports the module equal to the current-index reading on 3,000 of 3,000 pools on every seed. Source `verification/scorer-hedging/batch-rank-reading-result.txt`: the window shows seeds 20260926 and 1 with 3,000/3,000; seeds 2, 3 and 4 follow below the window with the same count. Claim holds.
- **c38** (0.39) _demote_once takes the loser's rank from its current index. Source `mva_prioritizer/candidate_selection.py`: the excerpt shows `_rank_points(j + 1)` where j is the enumerate index of the current table; the enumerate line is one line above the window. Claim holds.
- **c39** (0.44) The review of c1c2c34 found the Schedule sentence contradicted the code on the rank a loser is judged at. Source `verification/reviews/c1c2c34.json`: the window opens on the quoted docs/22 sentence; the evidence text stating the code's behaviour follows in the same finding. Claim holds.
- **c50** (0.35) docs/20 says the history scan found three historical blobs, that the fixture gene was pre-registered from literature and is also a case-flagged recurrent gene, and that both facts are checkable only from runtime/. Source `docs/20-track1-submission-gate.md`: the window opens mid-sentence after the literature clause; the three-blob count is earlier in the paragraph. Claim holds.

### Host-local, withheld

- **c46** (0.15) The frozen interval map at runtime/nine-gene-audit-20260909/gene-interval-map.json is host-local and not in the public tree. `runtime/nine-gene-audit-20260909/gene-interval-map.json` is ignored by Git and its contents are not excerpted.
- **c47** (0.20) The literature-overlay artifacts in runtime/internal-review-20260907/ are host-local. `runtime/internal-review-20260907/research-review.md` is ignored by Git and its contents are not excerpted.

### Supported

- c01 (0.67) Insert-and-shift promotion lowered 5,220 scores in 327,600 comparisons at four rows (`verification/reviews/741aaad.json`)
- c02 (0.51) batch/floor+pays_gt has mean rank points 34.895 and 10 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c03 (0.85) batch/transitive+pays_gt has 589 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c04 (0.90) batch/direct+keep has 44 and batch/direct+demote has 34 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c05 (0.80) The module keeps a losing pair only where points(r) > 0.5 * points(q) (`mva_prioritizer/candidate_selection.py`)
- c06 (0.78) The module removes a losing pair when a single for its unshared allele already sits above it (`mva_prioritizer/candidate_selection.py`)
- c07 (0.66) resolve_rows promotes to a fixpoint, then demotes to a fixpoint, and repeats until a round changes nothing (`mva_prioritizer/candidate_selection.py`)
- c08 (0.76) The probe's docstring states every policy is implemented inside the file and the module is measured as its own row (`verification/scorer-hedging/policy_probe.py`)
- c09 (0.72) The probe defines two schedules, step and batch, and builds a policy for each schedule, promotion mode and STAGE3 entry (`verification/scorer-hedging/policy_probe.py`)
- c10 (0.78) 36,033 truth comparisons over 3,000 random pools from 10 alleles in 4 genes, 4/3/2/1 per gene, tiers A/B/C (`verification/scorer-hedging/policy-probe-result.txt`)
- c11 (0.85) batch/direct+pays_gt has 0 below and mean 36.357; step/direct+pays_gt has 0 below and mean 36.353 (`verification/scorer-hedging/policy-probe-result.txt`)
- c12 (0.70) docs/22 says batch is ahead of step on ten further seeds by 0.0002 to 0.0102 (`docs/22-candidate-selection-rule.md`)
- c13 (0.93) batch/direct+pays_ge has 0 below and mean 36.155 (`verification/scorer-hedging/policy-probe-result.txt`)
- c14 (0.92) batch/direct+demote has mean 36.296 and 34 below; batch/direct+keep has mean 35.899 and 44 below (`verification/scorer-hedging/policy-probe-result.txt`)
- c15 (0.57) The best eligible policy is batch/direct+pays_gt and the module coincides with it on every pool under two seeds (`verification/scorer-hedging/policy-probe-result.txt`)
- c16 (0.76) verify_module.py reports zero pools with a permutation-dependent result (`verification/scorer-hedging/verify-module-result.txt`)
- c17 (0.85) verify_module.py reports zero rank-point comparisons lower than the plain sort over 20,245 (`verification/scorer-hedging/verify-module-result.txt`)
- c18 (0.91) verify_module.py reports zero kept sharing pairs at a rank that does not strictly pay (`verification/scorer-hedging/verify-module-result.txt`)
- c19 (0.74) brute_force_hedging.py returns 1 when strict violations are found, so it exits non-zero by design (`verification/scorer-hedging/brute_force_hedging.py`)
- c20 (0.77) hedging_modes.py main() returns 0, so it exits zero (`verification/scorer-hedging/hedging_modes.py`)
- c21 (0.60) verify_determinism.py imports only the standard library and does not import the evaluator (`verification/scorer-hedging/verify_determinism.py`)
- c22 (0.70) The evaluator bytes are pinned by SHA-256 in tests/test_track1_submission.py (`tests/test_track1_submission.py`)
- c23 (0.86) Rank points is metric 1 in the official evaluator (`tools/official-track1/evaluation.py`)
- c24 (0.80) case-token-scan running scripts/verify_no_case_tokens.py is a required Build OS command in product.json (`product.json`)
- c25 (0.92) The gate exits 2 with denylist_missing when the denylist file is absent (`scripts/verify_no_case_tokens.py`)
- c26 (0.87) The gate has a --history flag that scans every blob reachable from any ref (`scripts/verify_no_case_tokens.py`)
- c27 (0.72) build_case_token_denylist.py reads the interval map, the HGNC responses and the aggregate report, and writes runtime/privacy/denied-tokens.txt (`scripts/build_case_token_denylist.py`)
- c28 (0.83) build_case_token_denylist.py takes alias_symbol and prev_symbol from the HGNC responses (`scripts/build_case_token_denylist.py`)
- c29 (0.68) build_case_token_denylist.py also takes Entrez, Ensembl gene, RefSeq, OMIM, CCDS, UniProt and MANE ids from the HGNC responses (`scripts/build_case_token_denylist.py`)
- c30 (0.92) verify-module-result.txt reports 8,305 comparisons with rank points higher than the plain sort and 0 lower (`verification/scorer-hedging/verify-module-result.txt`)
- c33 (0.82) The two schedules diverge on 22 of the 3,000 tracked pools (`docs/22-candidate-selection-rule.md`)
- c34 (0.77) batch_rank_reading.py reports the two readings differ on 1 of 3,000 pools on seed 20260926, with current-index mean 36.3574 and promoted-rank mean 36.3572, both 0 below (`verification/scorer-hedging/batch-rank-reading-result.txt`)
- c36 (0.84) On seed 4 the readings differ on 4 pools and the current-index mean 36.6161 is above the promoted-rank mean 36.6147 (`verification/scorer-hedging/batch-rank-reading-result.txt`)
- c37 (0.75) The pinned test for the review of c1c2c34 asserts 10 rank points for the shipped file and 5 for the frozen-rank file under the loser's own truth (`tests/test_candidate_selection.py`)
- c40 (0.83) docs/20 gives 330 blobs across three local branches at c1c2c34 (`docs/20-track1-submission-gate.md`)
- c41 (0.68) The review of 1783250 returned FAIL (`verification/reviews/1783250.json`)
- c42 (0.68) The review of 28761f8 returned FAIL with blocking findings B1 and B2 (`verification/reviews/28761f8.json`)
- c43 (0.71) B1 of 28761f8: the probe demoted to a fixpoint before re-promoting while the module re-promoted after every demotion, hidden by a universe with at most three alleles per gene (`verification/reviews/28761f8.json`)
- c44 (0.58) B2 of 28761f8: the sentence giving always-demote the highest raw mean at 46.574 was false against the tracked result, where direct+pays_gt scored 46.833 (`verification/reviews/28761f8.json`)
- c45 (0.76) The second Jev pass on 1783250 covered 71 claims in 4 calls (`verification/jev/claim-provenance/report-1783250.md`)
- c48 (0.85) The parser rejects repeated variant ids across rows unless allow_repeated_pairings is set (`mva_prioritizer/track1_submission.py`)
- c49 (0.74) Tier is the first key of the evidence sort, before lane count and native rank (`mva_prioritizer/candidate_selection.py`)
