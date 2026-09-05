# Track 1 submission gate: pinned official code, local validator, scorer mirror

Date: 2026-09-05. Public and synthetic only. This note authorizes no upload. Every example variant below is invented.

## Pinned official sources

Retrieved from the challenge Space at Git revision `1c761cc23d90aebe6a011fd5b0b99517df42408c` (last modified 2026-08-29T01:08:57Z per the Hub API), by `resolve/<revision>/<path>`, and compared byte for byte with `main` on the retrieval date (identical). SHA-256 prefixes:

| File | SHA-256 (16) | Pinned copy in tree |
|---|---|---|
| `evaluation.py` | `6d18b581e65a45e1` | `tools/official-track1/evaluation.py` (unchanged bytes) |
| `static/templates/track1_submission_template.csv` | `7b3ed41c091d34fb` | `tools/official-track1/track1_submission_template.csv` |
| `config.py` (`MAX_TRACK1_SUBMISSIONS = 6`) | `a65e67fca2fb698a` | not copied |
| `tabs/submit_track1.py` (instructions, 28 Aug AI disclosure) | `685a3b6d57ef3a1c` | not copied |
| `tabs/rules.py` | `dccb3740f6301b86` | not copied |
| `tabs/faq.py` | `36c3e51e9735a6d2` | not copied |
| Discussion #2 (LLM clarification, Sage CPO answer, 2026-08-26) | `0029a039fde5486e` (Hub API JSON) | not copied |

The Space is licensed CC-BY-4.0 (README front matter). `tests/test_track1_submission.py` pins the two copied files by full SHA-256; a drift in the pinned bytes fails the suite. The official `groundtruth.py` contains only a local development fallback pair of placeholder coordinates; the real answer key is loaded from a private dataset at run time and is not in the public code.

What the pinned rules say that our 2026-08-31 note (`docs/10`) did not yet carry:

- No submission deadline is stated in the pinned code or rules; the FAQ says results follow a 2 to 3 month judging window and the date will be posted in the Community tab. The 2026-10-24 date in our planning comes from elsewhere and must be re-verified against the Community tab before any submission planning depends on it.
- Data deletion within 30 days of Hackathon close, with an email attestation, applies to the VCF and any subset, slice or reformat, per-variant genotype tables at genotype scale, caches and notebook state holding them, and stored prompts or logs with pasted variant blocks. Ranked candidate list, HPO terms, gene and pathway rankings, code, report and pitch are kept. Our frozen lanes on the encrypted volume fall in the delete class at close; the receipts that carry only counts and hashes do not.
- Third-party LLM use is allowed only as a processor: no training on inputs or outputs, no rights taken, retention limited in time and purpose. Provider, plan or tier and the setting must appear in the methods description. Our private work sends nothing to any hosted model; the public research assistance disclosure still has to be written from the provider's account page, not inferred.
- Submissions are released CC-BY with the participant's name; the repository must become public after the Hackathon ends; an embargo on peer-reviewed manuscripts runs from close until the organizers' summary report.

## What the gate does with a file

`evaluation.load_submission` is permissive. It strips whitespace from chromosome text and uppercases alleles, accepts blank alleles, treats any row with a blank `chrom_2` or `pos_2` as a single, groups by `proband_id`, refuses more than 10 rows per proband, refuses EPCR outside (0, 1], refuses `finding_type` other than primary or secondary, then sorts by EPCR descending with file order breaking ties. Scoring matches the exact `(chrom, pos, ref, alt)` tuple against a `chr`-prefixed GRCh38 answer. A row that parses but does not match scores zero with no warning, and each upload spends one of six submissions.

Verified on the pinned code by `tests/test_track1_submission.py`, which runs the official file and our mirror on each case:

| Synthetic case | Rank points | F-max |
|---|---|---|
| Exact pair in one row at rank 1 | 100 | 1.0 |
| Same pair, members in the other order | 100 | 1.0 |
| The two members as separate single rows | 50 | 1.0 |
| One member paired with a wrong partner | 50 | 0.5 |
| Exact pair at rank 4 behind three decoys | 25 | 1.0 |
| Chromosome written without the `chr` prefix | 0 | 0.0 |

## Local validator and mirror

`mva_prioritizer/track1_submission.py`:

- `parse_submission` refuses, before upload, anything that would error at the gate or parse and then score zero: header not identical to the template, wrong column count, more than 10 rows, empty file, `proband_id` other than `PROBAND01`, chromosome not exactly one of `chr1..chr22, chrX, chrY, chrM`, non-positive-integer position, alleles empty or outside `ACGT`, `ref` equal to `alt`, a partially filled second variant, a pair naming the same variant twice, EPCR outside (0, 1] or non-numeric, `finding_type` outside the two values, line breaks in notes, a second proband group. By default it also refuses repeated variants, EPCR ties and unsorted rows; each has an explicit flag because each is legal at the gate and occasionally deliberate (alternative pairings for an uncertain partner).
- `parse_as_official` reproduces the gate's permissive loader exactly, so a file the validator refuses can still be scored to learn what the gate would have done.
- `score_submission` mirrors `score_proband`. `tests/test_sensitivity_partition_mutations.py` disables each of 25 guards and scoring constants in this module in turn and requires the named test to fail.
- `validate_against_lane_representation` maps submission chromosomes to the lane's contig naming (no prefix, `MT` for the mitochondrion) and requires every submitted variant to exist among the lane keys it is given. It receives keys, never rows, and reports counts only.

CLI: `python3 -m mva_prioritizer.cli track1-check --submission <file> [--synthetic-truth '[[chrom,pos,ref,alt],...]'] [--allow-ties] [--allow-unsorted] [--allow-repeated-pairings]`. One JSON line with counts on success; exit 2 with the fixed `input_rejected` line on refusal, never echoing a row. The file is opened with `O_NOFOLLOW`, decided on the descriptor, bounded at 1 MiB.

## What this does not do

It does not build a candidate file, rank anything, or touch the lanes. A candidate for the real case would come from the frozen lane outputs on the encrypted volume, be checked with `track1-check` and `validate_against_lane_representation` against lane keys there, and be uploaded only on Jonathan's explicit approval of that specific file. The synthetic scorer answers "would this file score as intended if the truth were X"; it says nothing about the real answer.
