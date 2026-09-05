# Verification note for 2026-09-05

This pass corrects count-basis validation and adds an executable synthetic counterexample to final-record threshold filtering. It also corrects the methods note and records the next experiment.

## Executed checks

`env -u MVA_VERIFY_TEST_MODE bash scripts/verify.sh` returned exit 0. The full unit suite passed 120 tests. Compilation and the known-bad checks passed. The synthetic count-basis CLI fixture passed. The threshold counterexample produced the expected mismatch. The existing synthetic journey and 14-case noncoding benchmark passed. The configured current-tree source scan passed.

The known-bad harness reported 34 cases. That number is separate from the unit-test count. A passed current-tree scan does not establish that Git history or previous model context is safe for publication.

Regression tests first reproduced empty-receipt acceptance and ignored partition-total failures. Further tests reproduced invalid count types and unbounded JSON error handling. The final code rejected those inputs.

## Model review status

A generic methods critique completed on the requested and returned model `glm-5.3`. Its fixed input contained no patient values. The critique proposed a compound-pair counterexample. The parent implemented and executed a synthetic version.

Separate static code-review requests received the listed public code and synthetic tests only. Both attempts exhausted their output allowance in reasoning and returned no verdict. These attempts are incomplete reviews. The code must not be described as independently approved. A fresh bounded code review remains required before promotion beyond local development.

The model status files and exact supplied code hashes are under the ignored `runtime/method-audit-20260905/` directory. The parent-run verification log is there as well.

## Private state checked

A read-only connection reached the encrypted analysis host. No matching Exomiser or sensitivity process appeared in the process check. The frozen noncoding receipt matched its recorded hash. Its run directory remained read-only. A type-only probe rejected the staged script's expected first-record score shape without printing patient values.

This pass did not execute the staged script or start a new private analysis. It did not alter the private run. It did not push, publish, or submit the project.

## Next work

Follow `docs/14-mva-next-evidence-plan.md`. Preserve the original engine and all frozen results. Resolve the independent code review separately from the scientific experiment. The old post-hoc script is superseded.
