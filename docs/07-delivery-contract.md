# Delivery contract: MVA Transparent Prioritizer

## Completion contract

- [x] The Build OS architecture check passes before production code starts. Verified on 2026-08-26.
- [x] A reviewed local Git baseline and isolated implementation worktree exist. Baseline commit `eb2696d3965aa0a2cfbd853447c1fcb25a3b9e0e` and branch `mva-reference-setup` were verified locally on 2026-08-26. No push occurred.
- [x] Behavioral tests fail for the intended missing behavior before implementation. Verified through recorded RED and GREEN runs on 2026-08-26.
- [x] The synthetic journey produces byte-identical outputs on two clean runs. Verified by `bash scripts/verify.sh` on 2026-08-26.
- [x] Known-bad tests reject source-archive link attacks, traversal, repository overlap, unsafe download links, tampered or redirected receipts, stale references, score tampering, forbidden fields, canary leakage, and caller-selected private output paths. Verified by the 34-case `scripts/known_bad_tests.py` runner on 2026-08-26.
- [x] The M1 environment has pinned, hash-verified offline tools and references with a successful health check. A second content-free run on 2026-08-26 reverified 22 artifacts, 22 installations, seven tool entrypoints, two support trees, and the unchanged immutable receipt.
- [ ] The private run validates, normalizes, annotates, prioritizes, and writes a reviewable local dossier without protected stdout or network activity.
- [ ] The dossier covers single findings, proposed pairs, low-allele-fraction review, structural-call capability, targeted non-coding review, conflicting evidence, and an honest empty state.
- [ ] A second deterministic lane challenges the primary rank and records disagreement.
- [ ] An independent reviewer inspects the exact current commit and a separate scientific reviewer can inspect the local dossier.
- [x] The public projection passes a full-tree privacy scan and contains methods, synthetic fixtures, public citations, and non-identifying aggregates only. Verified by the projection, canary, forbidden-field, source-file, credential-shape, and source-machine-path tests on 2026-08-26.
- [ ] The private brief records results, evidence limits, retained uncertainty, retention deadline, and the reason for any later FASTQ request.
- [ ] External submission, public repository creation, push, publication, treatment claim, and source deletion remain pending human decisions.

## Automated verification

`product.json` declares exact argument arrays for compile, unit, known-bad, synthetic journey, privacy scan, contract check, and CLI help. The M1 private acceptance runner records its own content-free pass or fail receipt because protected details cannot enter the public Build OS evidence log.

## Representative user journeys

1. The operator runs `synthetic-run` with the frozen fixture and receives `review_ready`, a stable run ID, and byte-identical artifacts on replay.
2. The operator runs `private-run` against the encrypted manifest and receives content-free stage status. Detailed evidence stays in the private dossier.
3. The operator seeds a protected canary, runs `project-safe-learnings`, and confirms that the public tree contains no canary, private field, coordinate, genotype, or absolute private path.
4. The operator tampers with one reference receipt and receives `stale_receipt` before any candidate output is written.

## Independent review

A reviewer who did not implement the code must inspect the exact Git commit for specification fit, logic, security, privacy, scientific overclaim, and maintainability. Reviewer claims are reproduced with deterministic commands before they change the contract state. A fresh review follows every code change that affects behavior.

## Evidence packet

The packet binds the Git commit, source manifest schema, synthetic fixture hash, reference receipt hashes, tool versions, canonical configuration, command cwd, complete local logs, bounded content-free excerpts, and known limitations. Private evidence stays on the encrypted M1. The public packet contains only the synthetic run and safe projection verifier.
