# Claim-provenance pass, docs/22 after the third review

Backend: Jev (`jev-latest`) through `~/projects/rlcd/bin/decide`, one call, 10,654 input tokens, 562 output tokens, 1,752 ms. Question per claim: does the excerpt fully support the claim, every number, path and quoted line, with no contradiction (Noul).

Claim set: `claims-post-review-3.json`, built by `build_claims.py` from the corrected document. Every excerpt comes from a tracked file; excerpts from `runtime/` are refused by construction, and the builder asserts that no excerpt carries a token from the host-local denylist that `scripts/verify_no_case_tokens.py` enforces. That is the fix for finding B3 of the review of `1783250`, where the previous pass copied a private aggregate report's excerpt into a tracked request file.

## Result

| bucket | claims |
|---|---|
| supported (Jev >= 0.5) | 25 |
| below 0.5, checked by hand against the source | 4 |
| host-local artifact, excerpt withheld by design | 2 |
| total | 31 |

No claim in the document was found false. The three sentences the previous pass found false (the "tracked in this repository" interval map, `hedging_modes.py` "exits non-zero", `verify_determinism.py` "imports the evaluator") are corrected in the document and now sit in the supported bucket as c16, c17 and c18.

### Below 0.5, checked by hand

- **c04** (0.43) Direct promotion never scores below the plain sort. Source `verification/scorer-hedging/policy-probe-result.txt`: the excerpt's `direct+pays_gt` row shows 0 in the `below` column; the window cut the header that names the column. Claim holds.
- **c23** (0.45) The review of 1783250 returned FAIL with blocking findings B1, B2, B3. Source `verification/reviews/1783250.json`: the excerpt shows `"verdict": "FAIL"` and B1; B2 and B3 follow outside the window. Claim holds.
- **c24** (0.47) B1: the probe's demote_all wrapped the module's pays test so always-demote was never run. Source `verification/reviews/1783250.json`: the excerpt is the B1 evidence text itself, describing `demote_all` calling `_demote_once` with the pays test; the finding id sits one line above the window. Claim holds.
- **c25** (0.36) B2: promotion can lift a weaker pair above the evidence winner. Source `verification/reviews/1783250.json`: the excerpt is the tail of the B2 evidence ("evidence winner displaced"); the finding's claim text sits above the window. Claim holds.

### Host-local, withheld

- **c28** (0.14) The frozen interval map at runtime/nine-gene-audit-20260909/gene-interval-map.json is host-local and not in the public tree. `runtime/nine-gene-audit-20260909/gene-interval-map.json` is ignored by Git (`git check-ignore` confirms) and its contents are not excerpted; a reviewer with host access checks it there.
- **c29** (0.10) The literature-overlay artifacts in runtime/internal-review-20260907/ are host-local. `runtime/internal-review-20260907/research-review.md` is ignored by Git (`git check-ignore` confirms) and its contents are not excerpted; a reviewer with host access checks it there.

### Supported

- c01 (0.68) Insert-and-shift promotion lowered 5,220 scores in 327,600 comparisons at four rows (`verification/reviews/741aaad.json`)
- c02 (0.88) floor+pays_gt has mean rank points 43.438 (`verification/scorer-hedging/policy-probe-result.txt`)
- c03 (0.78) transitive+pays_gt has 579 comparisons below the plain sort (`verification/scorer-hedging/policy-probe-result.txt`)
- c05 (0.72) The module keeps a losing pair only where points(r) > 0.5 * points(q) (`mva_prioritizer/candidate_selection.py`)
- c06 (0.81) The probe's docstring states every policy is implemented inside the file and the module is measured as its own row (`verification/scorer-hedging/policy_probe.py`)
- c07 (0.61) The probe builds a policy for each of three promotion modes crossed with each STAGE3 entry, plus plain and module (`verification/scorer-hedging/policy_probe.py`)
- c08 (0.82) 27,594 truth comparisons over 4,000 random pools (`verification/scorer-hedging/policy-probe-result.txt`)
- c09 (0.91) direct+demote has 75 comparisons below the plain sort and mean rank points 46.574 (`verification/scorer-hedging/policy-probe-result.txt`)
- c10 (0.92) direct+pays_ge has 0 comparisons below the plain sort and mean rank points 46.557 (`verification/scorer-hedging/policy-probe-result.txt`)
- c11 (0.61) Demoting at equality (pays_gt) dominates with mean 46.833 and is the best eligible policy (`verification/scorer-hedging/policy-probe-result.txt`)
- c12 (0.69) The module coincides with direct+pays_gt on all 4,000 pools (`verification/scorer-hedging/policy-probe-result.txt`)
- c13 (0.73) verify_module.py reports zero pools with a permutation-dependent result (`verification/scorer-hedging/verify-module-result.txt`)
- c14 (0.87) verify_module.py reports zero rank-point comparisons lower than the plain sort over 20,245 (`verification/scorer-hedging/verify-module-result.txt`)
- c15 (0.90) verify_module.py reports zero kept sharing pairs at a rank that does not strictly pay (`verification/scorer-hedging/verify-module-result.txt`)
- c16 (0.70) brute_force_hedging.py returns 1 when strict violations are found, so it exits non-zero by design (`verification/scorer-hedging/brute_force_hedging.py`)
- c17 (0.82) hedging_modes.py main() returns 0, so it exits zero (`verification/scorer-hedging/hedging_modes.py`)
- c18 (0.59) verify_determinism.py imports only the standard library and does not import the evaluator (`verification/scorer-hedging/verify_determinism.py`)
- c19 (0.72) The evaluator bytes are pinned by SHA-256 in tests/test_track1_submission.py (`tests/test_track1_submission.py`)
- c20 (0.84) Rank points is metric 1 in the official evaluator (`tools/official-track1/evaluation.py`)
- c21 (0.74) case-token-scan running scripts/verify_no_case_tokens.py is a required Build OS command in product.json (`product.json`)
- c22 (0.87) The gate's default denylist path is runtime/privacy/denied-tokens.txt under the repository root (`scripts/verify_no_case_tokens.py`)
- c26 (0.52) B3: tracked Jev request files carried case-derived gene symbols from a private aggregate report (`verification/reviews/1783250.json`)
- c27 (0.57) The second Jev pass on 1783250 covered 71 claims in 4 calls (`verification/jev/claim-provenance/report-1783250.md`)
- c30 (0.78) The parser rejects repeated variant ids across rows unless --allow-repeated-pairings is passed (`mva_prioritizer/track1_submission.py`)
- c31 (0.68) Tier is the first key of the evidence sort, before lane count and native rank (`mva_prioritizer/candidate_selection.py`)
