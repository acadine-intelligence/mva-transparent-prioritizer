# Loop 8: CLI boundary checks

Date: 2026-09-05. This iteration improves reproducible software checks. It establishes no new biological result.

## Work performed

A fresh local check found a clean worktree at `b3131692b5752c7c7a12e862456736d8ea5615e0`. The M1 Exomiser probe remained blocked on its unanswered approval request. This iteration did not retry that operation or use another route to obtain the blocked result.

One bounded `glm-5.3` request reviewed the existing public CLI and its synthetic tests. The returned model was `glm-5.3`; the response finished normally. It identified missing coverage, with no code defect found in that scope. The model received only the two files listed in `runtime/loop-8-20260905/input-manifest.json`. It had no tools or private inputs.

The parent added five regression tests to `tests/test_validate_receipt_basis_cli.py`. They exercise the exact file-size limit and the next byte above it, reject directories and symlinks, reject a FIFO without waiting for a writer, and check bounded errors for invalid UTF-8 and deeply nested JSON. Fixture checks verify that tested input bytes remain unchanged. CLI test subprocesses now have a five-second timeout.

Production CLI and library code are unchanged. These tests extend the existing supported-shape arithmetic utility. They do not establish a protected-file access boundary or prove that real source counts are correct.

## Executed results

| Check | Observed result |
| --- | --- |
| Baseline CLI suite | 8 tests passed |
| Extended CLI suite | 13 tests passed |
| Full `scripts/verify.sh` sequence | Exit 0; 125 tests passed |
| Existing known-bad harness | 34 cases passed, counted separately from the unit suite |
| Disposable mutation checks | All 4 seeded faults triggered the target test assertion |
| Build OS architecture check | Passed before the test changes |
| Build OS full verification | All 7 declared commands returned exit 0 |

The seeded faults removed the size guard, changed its comparison to reject the exact allowed size, removed the symlink guard, and removed the recursion exception handler. Each fault ran in its own disposable public-source copy. The target test exited 1 with an assertion failure in every case. The original source hashes remained unchanged during these mutation checks.

The mutation receipt binds the tested working-tree files by SHA-256. These results cover uncommitted test changes on the stated base commit. They must not be represented as an exact-commit review of a new revision.

## Corrections to model advice

The GLM response printed an incorrect numeric expansion of one MiB. The parent calculated `1024 * 1024 = 1048576` locally and kept the test tied to that contract.

The response also described the existing missing-file test as covering the exception path. Source inspection shows that an ordinary missing path returns through the regular-file check. That test does not prove the `OSError` handler ran.

The parent rejected the suggestion to weaken the exact-limit success assertion. An executed padded, valid JSON fixture passed at exactly one MiB. The stronger assertion remains.

## Review and research limits

The earlier Codex review covers its eight-file snapshot. Its independent CLI execution was incomplete because its sandbox could not create temporary files. A scoped PASS with that limitation does not satisfy the project's full-repository review requirement. The new tests have parent execution and mutation evidence; they have no independent exact-commit review yet.

A fixture test should distinguish source read-only policy from permission to create disposable test files. A future review needs a writable, isolated temporary directory while keeping the candidate source unchanged.

The next useful scientific step is still the synthetic Exomiser probe against the installed engine, followed by a justified decision on private sensitivity analysis. Further changes to this arithmetic helper will not answer that scientific question. M1 inspection and synthetic probe execution still require the pending approval. No new private analysis, submission, or publication occurred in this iteration.

## Local evidence

The ignored directory `runtime/loop-8-20260905/` contains the fixed model request and response, provider status, source manifest, mutation script and receipt, four mutation logs, and `verify.log`. The mutation script uses only generated public-source copies and synthetic fixtures.
