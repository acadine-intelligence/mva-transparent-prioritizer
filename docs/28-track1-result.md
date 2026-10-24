# Track 1 result

Date: 2026-10-24. Public-safe: this note holds the scorer's output only, with no genotype, coordinate, gene symbol or patient record.

The operator uploaded one reviewed entry to the Track 1 form on 2026-10-24, before the 23:59 UTC close. Files:

- Predictions: the frozen ten-row file built on the sealed machine on 2026-10-12 (SHA-256 prefix `e0fef7dc3321`), checked for format on the sealed machine before it left.
- Report: `docs/26-track1-report.md` at commit `fe96f7e`.

## Scorer output

| Metric | Value |
|---|---|
| Rank points | 100.0 / 100 |
| F-max | 1.000 |
| F-max EPCR threshold | 0.9 |
| Match | Full match at rank 1 |

## What the numbers mean

- The first row matched the confirmed answer exactly, on every chromosome, position and allele.
- Only the first row carried an EPCR of 0.9 or more, so at that threshold precision and recall are both 1.
- The first row was the pair produced by the pre-written selection rule (`docs/22`). Its gene was one of the nine syndrome genes declared from public literature on 2026-09-07, before case inspection.

## What the numbers do not show

- This is one case. A perfect score on one proband is not evidence of a general success rate.
- The shortlist was partly constrained by earlier results, as `docs/22` discloses, so the rule is a partial pre-registration.
- We do not know how many other teams also matched at rank 1. The leaderboard was not read for this note.

No further uploads were made. The scorer was not probed.
