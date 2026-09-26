# Track 1 submission gate: pinned official code, local validator, scorer mirror

Date: 2026-09-05. Public and synthetic only. This note authorizes no upload. Every example variant below is invented.

Correction, 2026-09-07: the original source check omitted the About page. Its timeline supplies the submission deadline. The Space revision and the vendored evaluator and CSV template are unchanged.

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
| `tabs/about.py` (timeline, checked 2026-09-07) | `1867b07f24d987fb` | not copied |
| Discussion #2 (LLM clarification, Sage CPO answer, 2026-08-26) | `0029a039fde5486e` (Hub API JSON) | not copied |

The Space is licensed CC-BY-4.0 (README front matter). `tests/test_track1_submission.py` pins the two copied files by full SHA-256; a drift in the pinned bytes fails the suite. The official `groundtruth.py` contains only a local development fallback pair of placeholder coordinates; the real answer key is loaded from a private dataset at run time and is not in the public code.

What the pinned rules say that our 2026-08-31 note (`docs/10`) did not yet carry:

- The [About-page timeline](https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/resolve/1c761cc23d90aebe6a011fd5b0b99517df42408c/tabs/about.py) states that submissions close on 24 October 2026 at 23:59 UTC (25 October at 01:59 SAST). The earlier claim that no deadline was stated was incorrect: the source check had omitted this page. The timeline says dates may change, so recheck it and Community announcements before submission. The timeline and the FAQ give different descriptions of the judging period; do not treat the judging schedule as settled.
- Data deletion within 30 days of Hackathon close, with an email attestation, applies to the VCF and any subset, slice or reformat, per-variant genotype tables at genotype scale, caches and notebook state holding them, and stored prompts or logs with pasted variant blocks. Ranked candidate list, HPO terms, gene and pathway rankings, code, report and pitch are kept. Our frozen lanes on the encrypted volume fall in the delete class at close; the receipts that carry only counts and hashes do not.
- Third-party LLM use is allowed only as a processor: no training on inputs or outputs, no rights taken, retention limited in time and purpose. Provider, plan or tier and the setting must appear in the methods description. Our private work sends nothing to any hosted model; the public research assistance disclosure still has to be written from the provider's account page, not inferred.
- Submissions are released CC-BY with the participant's name; the repository must become public after the Hackathon ends; an embargo on peer-reviewed manuscripts runs from close until the organizers' summary report.

The 3-minute pitch video is a Track 2 requirement in `tabs/submit_track2.py`. Track 1 requires a prediction CSV and a methods report. Its form also requires a repository link. The Track 1 instructions do not state a pitch-video requirement. The official workbook still says one final Track 2 submission, while the submission interface and organizer update allow three attempts with only the latest reviewed. Treat those as three attempts toward one reviewed final entry.

## Making the repository public: history is not the working tree

The repository must become public after close, and the public object is the whole Git history, every blob reachable from every branch. The privacy gates run on the working tree. A token that was in a file at the baseline commit and later replaced stays in the history and becomes public with it.

Known state at commit `25d0b47` and after: `scripts/build_case_token_denylist.py` builds the case-token denylist from the private artifacts (218 tokens: the nine pre-registered gene symbols with their HGNC, Entrez, Ensembl gene, RefSeq, OMIM, CCDS, UniProt, MANE and model-organism ids, aliases, previous symbols and Ensembl transcript ids, with and without versions; plus every symbol in the recurrent-gene aggregate report). A scan of all 318 blobs reachable from both branches found three historical blobs carrying one: the two Jev request files the review of `1783250` reported (fixed in `28761f8`) and `tests/test_synthetic_journey.py`, which from the baseline commit to `28761f8` used one of the nine pre-registered genes as its "not a synthetic gene" example. That gene was declared from public MVA literature on 7 September, before any case inspection, and it is also one of the eleven recurrent genes the case audit flagged, which is why the denylist carries it; both facts are checkable only from the host-local artifacts under `runtime/` (the literature catalog and the recurrent-gene report), not from anything tracked. The fixture now uses a literal that matches no real gene.

Rule for publication: before the visibility change, rebuild the denylist, run `scripts/verify_no_case_tokens.py --history` (every blob reachable from any ref; 302 blobs at `28761f8`), and either confirm the only hits are the three known blobs with literature-only or already-redacted content, or rewrite history to drop the offending blobs before the push that makes it public. A history rewrite is destructive and needs Jonathan's approval; the audit is not and runs at every review. Nothing under `runtime/` is in any blob.

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
