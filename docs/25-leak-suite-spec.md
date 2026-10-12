# Privacy boundary leak suite

## Boundary and adversary

Protected inputs and all row-level derivatives belong inside the local encrypted
runtime. Hosted models and agents receive public code, synthetic fixtures and
approved content-free status. The public repository exposes files, filenames,
staged commit content and history to anyone. The organiser is also outside this
boundary: a separately approved submission can disclose selected rows, but a
validator run is not submission approval. No test uploads anything.

Every stdout line, stderr message, exception, summary JSON field, public file,
filename, directory name, exit code and elapsed time is an observable channel.
The suite treats hashes and counts as disclosures when a stated, small hypothesis
set makes them reversible. It does not assume the attacker already knows the
answer. Knowing a file template or a shortlist is an explicit attack assumption.
Private pool files are inspected only as synthetic controls, not treated as
public exports.

An adversary can choose protected input fields, malformed values, output names
and public export content. They may know serialization rules and compare public
outputs across runs. The trusted operator, source code and audit module are not
replaced by malicious code. Tests call real library boundaries and subprocesses,
without mocking scanners, parsers or projection. All inputs are invented locally.

## Attacks and expected protection

1. **Direct echo.** Put an invented gene or HPO-shaped identifier into a rejected
   Track 1 cell, an allowlisted projection field and a public file. Require a
   bounded refusal with no reflected value and no projection file. The CLI,
   raw-byte scanner and populated projection denylist should catch these.
   Calling the Track 1 library directly is expected to expose rejected values
   in exception messages. Exercise that boundary separately.

2. **Encoded echo.** Export base64, hex, percent encoding, reversed text and
   fragments split across lines or JSON fields. Decode or join them in the test
   to prove recoverability, then demand scanner rejection. Also put a hex-encoded
   canary in the projection's method version. Current byte comparisons are
   expected to miss these transformations, even with the original canary planted.

3. **Count inference.** Project zero and one findings in a single-candidate
   synthetic world. An outsider who knows the sole candidate can infer its
   presence. Current projection validation checks arithmetic, not disclosure.
   Build a miniature candidate-pool tree with one recurrent invented gene chosen
   from eight possibilities. Read the actual emitted summary file and brute-force
   its recurrent-input SHA-256 using the known JSON template. Current summaries
   publish this digest and should fail the privacy assertion. This demonstrates
   dictionary recovery, not a general SHA-256 break or recovery of real cases.

4. **Filename and path leakage.** Plant canaries in file and run-directory names
   while keeping contents harmless. Both tree scanners are expected to miss
   these names. Trigger a token hit in a canary-named file: the case-token script
   is expected to echo the path. Trigger a missing candidate-pool input under a
   canary-named run root: its uncaught exception should expose a traceback.
   The main CLI's equivalent failure should remain content-free.

5. **Injection.** Insert instructions and terminal escapes into synthetic VCF
   INFO and Track 1 notes. Require no payload in exported summaries or streams;
   these paths should discard or withhold the fields. Put the same instruction
   payload into a malformed candidate-pool numeric field to provoke a parser
   error. Its traceback is expected to reflect the payload. This tests delivery
   to a downstream reader, not whether a hosted model follows instructions.

6. **Gate bypass.** Try alternate coordinate spellings, HGVS-shaped text,
   invented rsID and ClinVar-shaped identifiers, HPO-shaped identifiers and an
   invented gene alias. The source scanner currently recognises secrets and
   machine paths, not biomedical value classes, despite the case-token script's
   introductory claim. Exact denylist hits should block; aliases and suffixed
   tokens should evade its whole-word matching. Also stage a canary-bearing blob,
   replace the working copy with harmless text and test the prepublication gates.
   They are expected to inspect the working copy rather than pending commit bytes.

## Evidence and limits

Write the specification before tests. Each known gap has a numbered finding,
severity and one-line reason on an `unittest.expectedFailure` test. Assertions
express the desired protection, never “the leak is acceptable.” Passing control
tests prove fixtures reach the intended boundary; an unexpected success demands
review. Aggregate attacks collect every result before asserting, so the first
miss does not conceal later attempts.

Run full unittest discovery, the verification script, the public-tree gate and
Build OS verification. Report ordinary failures separately from expected failures.
No commits, installs, network calls or real case discovery are permitted. Temporary
Git indexes exercise pending commit content without creating commits. Historical
commit messages, organiser uploads and statistical timing attacks remain outside
this first suite. Exit status and bounded stream shape are checked; subprocess
timeouts prevent hangs but do not establish constant-time execution. A passing
suite with documented expected failures is evidence of gaps, not release approval.
