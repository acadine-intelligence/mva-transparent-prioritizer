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

## Open representation risk: the mitochondrial contig

Public sources name the answer key's chromosome form only by example (`chr15`, `chr1`, `chr7`, `chr2`). Nothing public says whether a mitochondrial variant would be written `chrM` (UCSC and GRCh38 no-alt analysis-set convention) or `chrMT`; the private key could plausibly use either. The validator therefore takes the spelling as a parameter (`mitochondrial_name`, CLI `--mitochondrial-name`, values `chrM` or `chrMT`, default `chrM`) and never accepts an unprefixed form. `track1-check` reports `mitochondrial_rows`. A candidate file that carries a mitochondrial row must not be uploaded until the organizers confirm the spelling in the Community tab, or the candidate set is known to be nuclear.

## Local validator and mirror

`mva_prioritizer/track1_submission.py` holds two parsers with different jobs.

`parse_as_official` reproduces the gate's loader exactly, quirks included: default codec (so a UTF-8 BOM joins the first header name and the gate raises `KeyError('proband_id')` when it reads a data row; a BOM-only file yields an empty result in both parsers), whitespace stripped from chromosome text, alleles uppercased, blank alleles accepted, missing optional second-variant columns defaulted, short rows crashing as the gate crashes (`None` cells), `int()` and `float()` failures raised, grouping by proband, EPCR sort with stable ties. It is the oracle for "what would the gate compute for this file". `tests/test_track1_submission.py` runs the pinned official file and this mirror on every synthetic case, including the gate-normalized shapes and the gate-error shapes, and requires identical outcomes.

`parse_submission` is deliberately narrower than the gate. It accepts one canonical form and refuses everything else: header identical to the template (all twelve columns), `proband_id` exactly `PROBAND01`, chromosome exactly one of `chr1..chr22`, `chrX`, `chrY` or the configured mitochondrial spelling, positive-integer positions, non-empty upper-case `ACGT` alleles with `ref` different from `alt`, a second variant complete or entirely blank, a pair naming two distinct variants, EPCR numeric in (0, 1], `finding_type` written out, notes without line breaks, no BOM, one proband, at most 10 rows. By default it also refuses repeated variants, EPCR ties and unsorted rows; each has a flag because each is legal at the gate and occasionally deliberate (alternative pairings for an uncertain partner). Forms the gate would normalize for us, such as ` chr1 ` or lowercase alleles or a ten-column header, are refused on purpose: a file that passes the canonical check is one whose gate parse is unambiguous by inspection, and `tests/test_track1_submission.py` shows for each such shape both what the validator does and what the gate would score.

`score_submission` mirrors `score_proband`. `validate_against_lane_representation` maps submission chromosomes to the lane's contig naming (no prefix, `MT` for the mitochondrion) and requires every submitted variant to exist among the lane keys it is given; it receives keys, never rows, and reports counts only.

`tests/test_sensitivity_partition_mutations.py` disables each of 30 guards and scoring constants in this module and 2 in the CLI boundary in turn and requires the named test to fail.

CLI: `python3 -m mva_prioritizer.cli track1-check --submission <file> [--synthetic-truth '[[chrom,pos,ref,alt],...]'] [--mitochondrial-name chrM|chrMT] [--allow-ties] [--allow-unsorted] [--allow-repeated-pairings]`. One JSON line with counts on success; the file is opened with `O_NOFOLLOW`, decided on the descriptor, bounded at 1 MiB; after the canonical parse the CLI also runs the gate mirror and refuses if the two ranked variant lists differ. Every refusal, including argument errors (argument parsing runs inside the same boundary, with usage output suppressed), exits 2 with the fixed `input_rejected` line and never echoes a row or an argument.

## What this does not do

It does not build a candidate file, rank anything, or touch the lanes. A candidate for the real case would come from the frozen lane outputs on the encrypted volume, be checked with `track1-check` and `validate_against_lane_representation` against lane keys there, and be uploaded only on Jonathan's explicit approval of that specific file. The synthetic scorer answers "would this file score as intended if the truth were X"; it says nothing about the real answer.
