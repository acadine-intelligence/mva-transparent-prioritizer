# Claim provenance check: docs/22-candidate-selection-rule.md

Run 26 September 2026. Jev calibrated decision model (TypeSafe System One, Noul questions),
4 decide calls over 3 request files (32 claims, one question per claim, each instruction
addressing its claim by claim_id). Buckets: supported >= 0.70, unsupported <= 0.30, uncertain between.
Deterministic grep ran first over all allowed artifacts for every number, with and without separators.

## Totals

- Total checkable claims extracted: 40 (32 paired with an artifact, 8 with no source in the allowed set)
- Supported: 18
- Unsupported: 1
- Uncertain: 13
- No source: 8

## Deterministic misses (grep over all allowed artifacts)

Numbers and tokens in docs/22 that appear in NO allowed artifact:

- 48,252
- 1,735,200
- 108,450
- '7 September' (date of the nine-region declaration)
- '10 September' (date of the specialist packet)
- '18 September' / 'discussion 24' (the other team's public question)
- 'gene-interval-map.json' (the named frozen map file)
- 'AUTOSOMAL_RECESSIVE' (the annotation vocabulary string)

All other numbers in the document (48,608 / 36,456 / 12,152 / 1,020 / 420 / 29,400 / 480 / 600 /
120 / 19,779 / 32,612 / 44,090 / 7,216 / 1,843,650 / 263 / 365 / 175 / 243 / 90 / 12 / 7 / 421 /
794 / 290 / 454 / 500 / 19 / 11 / 9, the EPCR ladder, tier points, receipt prefix d5ba10df94dcf684,
quoted scorer lines and file paths) were found verbatim in at least one artifact.

## Unsupported claims

### c19 (p=0.27)

Claim: On the recommended shape (exact pair on top, each allele alone below): if the pair is correct it scores 100 points with F-max 1.000; if only one of the two alleles is truly causal it scores 50 points, where a pair-only file scores 0; no tested case scored worse.

Source: runtime/scorer-hedging-20260919/result.txt

Excerpt:

```
--- recommended shape under both truths ---
  truth=(('chr1', 1000, 'A', 'G'), ('chr1', 2000, 'C', 'T'))         rank_points= 100.0 f_max=1.000
  truth=(('chr1', 1000, 'A', 'G'),)                                  rank_points=  50.0 f_max=0.667
  truth=(('chr1', 2000, 'C', 'T'),)                                  rank_points=  50.0 f_max=0.667
  truth=(('chr2', 3000, 'G', 'A'),)                                  rank_points=   0.0 f_max=0.000

--- pair-only, no hedge rows ---
  truth=(('chr1', 1000, 'A', 'G'), ('chr1', 2000, 'C', 'T'))         rank_points= 100.0 f_max=1.000
  truth=(('chr1', 1000, 'A', 'G'),)                                  rank_points=   0.0 f_max=0.667
  truth=(('chr1', 2000, 'C', 'T'),)                                  rank_points=   0.0 f_max=0.667
```

## Uncertain claims

### c01 (p=0.44)

Claim: The nine-gene audit (9 September) established that all nine regions carry recorded alternate genotypes in both the stored original VCF and the prepared analysis VCF, and that two regional records per input matched saved filtered rows.

Source: runtime/nine-gene-audit-20260909/audit-summary.md

Excerpt:

```
9 September 2026

All nine target regions contained recorded alternate genotypes in both the stored original VCF and the prepared analysis VCF. All eight genes missing from the filtered 500-gene packet had regional records in both input files.

The authorized read-only audit is complete. A separate verification run recomputed the audit from its sources and reproduced the saved output bytes.

## Recorded evidence

| Measure | Original VCF | Prepared analysis VCF |
| --- | ---: | ---: |
| Records scanned | 5,012,204 | 5,035,176 |
| Records in the inspected regions | 1,272 | 1,283 |
| Regional records with an exact allele-key match in saved filtered rows | 2 | 2 |
| Regional records that triggered the reader's quality flags | 0 | 0 |

Every regional record counted above contained a recorded alternate genotype. These are record counts. A multiallelic record can contain several alleles. An exact match means that at least one of its allele keys matched a saved filtered row. The match counts provide a trace into existing outputs; clinical relevance remains unassessed.
```

### c02 (p=0.45)

Claim: The diagnostic replay, named replay-2 and verified, is the run whose outputs the later recurrent-gene analysis read, and the run's regional selection included the nine target regions plus the frozen passing controls.

Source: runtime/recurrent-genes-20260911/recurrent-pins.json + runtime/recurrent-genes-20260911/aggregate-report.md

Excerpt:

```
{
  "output_directory": "recurrent-1",
  "replay_directory": "review-work/diagnostic-replay-20260909/replay-2",
  "replay_receipt_sha256": "09769e3e027d5afb443930222f8559fab2b20bcdc9b021aede02397301718142",
  "replay_result_sha256": "1a62e8cc91514b1d5bf6240558fd00668f139ff0929446916566fda4943e5d47",
  "schema": "mva-recurrent-genes-pins-v1",
  "stage": "review-work/recurrent-genes-20260911",
  "top_n": [10, 30]
}
...
## What this does and does not mean

- One of the eleven recurrent genes sits in a predeclared public-literature region. This is a diagnostic observation about ranking behaviour in a bounded regional run, not a discovery and not a clinical finding.
- The run's regional selection includes the nine target regions plus the frozen passing controls, so recurrence partly reflects that selection. It does not describe the whole genome.
- Rank here is native output order only. No score, filter state or pathogenicity conclusion is asserted.
```

### c08 (p=0.6)

Claim: The official scorer awards the full match unconditionally once found: a full match at rank 4 scores 25 points and a partial match at rank 1 scores 50, so the full-match branch wins even when the partial match would have scored more.

Source: tools/official-track1/evaluation.py

Excerpt:

```
# Rank-point scale, compressed from CAGI's RGP weighting to fit a single
# proband with a max of 10 submitted candidates (rather than CAGI's
# multi-family, up-to-100-candidate benchmark).
RANK_POINT_TIERS = [
    (1, 100),
    (3, 50),
    (5, 25),
    (10, 10),
]
...
    # --- Rank points (metric 1) ---
    if full_match_rank is not None:
        rank_points = float(_rank_to_points(full_match_rank))
    elif partial_match_rank is not None:
        # CAGI-style partial credit: half weight for recovering only one
        # of two causal variants in a compound-het pair.
        rank_points = 0.5 * _rank_to_points(partial_match_rank)
```

### c10 (p=0.57)

Claim: A pair placed below rank 3 scores worse than the partial credit its own single allele would have earned at rank 1 (a pair at rank 4 or 5 earns 25, while a partial match at rank 1 earns half of 100, i.e. 50).

Source: tools/official-track1/evaluation.py

Excerpt:

```
RANK_POINT_TIERS = [
    (1, 100),
    (3, 50),
    (5, 25),
    (10, 10),
]
...
    elif partial_match_rank is not None:
        # CAGI-style partial credit: half weight for recovering only one
        # of two causal variants in a compound-het pair.
        rank_points = 0.5 * _rank_to_points(partial_match_rank)
```

### c11 (p=0.64)

Claim: The scorer's partial-match test is row.variants & true_variants, an intersection, so a two-variant row naming one correct allele and one incorrect one earns the same partial credit as that allele alone.

Source: tools/official-track1/evaluation.py

Excerpt:

```
    if is_compound_het and full_match_rank is None:
        # Look for a row containing exactly one of the two true variants -
        # either proposed alone, or paired with an incorrect second variant.
        for row in submission_rows:
            if row.variants & true_variants:
                partial_match_rank = row.rank
                break
```

### c12 (p=0.64)

Claim: The official scorer refuses a submission with more than 10 rows per proband (so an eleventh row is refused).

Source: tools/official-track1/evaluation.py

Excerpt:

```
    for pid, rows in by_proband.items():
        if len(rows) > 10:
            raise ValueError(f"Proband {pid} has {len(rows)} rows; max is 10")
```

### c13 (p=0.31)

Claim: A brute-force check scored 1,843,650 combinations against the pinned official evaluator vendored at tools/official-track1/evaluation.py, with results stored under runtime/scorer-hedging-20260919/.

Source: runtime/scorer-hedging-20260919/result.txt + runtime/scorer-hedging-20260919/brute_force_hedging.py

Excerpt:

```
combinations scored: 1843650

...
ROOT = pathlib.Path.home() / "projects/mva-transparent-prioritizer/.worktrees/reference-setup"
sys.path.insert(0, str(ROOT / "tools/official-track1"))

import evaluation as off  # the pinned official scorer
```

### c17 (p=0.63)

Claim: Three wider ordering formulations were tested against the pinned scorer and recorded in verify_rule.py: 'every pair above every single row' lowered the score in 1,020 cases; 'every pair above any row sharing an allele' lowered it in 420 cases; 'a pair above every single sharing an allele' never lowered the score in 29,400 comparisons and raised it on 480 row sets.

Source: runtime/scorer-hedging-20260919/verify_rule.py + runtime/scorer-hedging-20260919/verify-rule-result.txt

Excerpt:

```
def promote_allele_sharing(ordered_shapes):
    """The rule as it survives measurement: promote a pair above every SINGLE row
    that shares an allele with it. Relative order of two pairs is NEVER changed.

    Two earlier formulations were falsified by this script:

      "every pair above every single" moves an UNRELATED pair above a true
      single and costs 25 points (draft 3, 1,020 cases).

      "every pair above any row sharing an allele" reorders two allele-sharing
      PAIRS, and since the rule cannot know which of them is true, the swap
      demotes the true pair half the time (draft 4, 420 cases).

    Pair-versus-pair precedence is a question about which hypothesis is stronger.
    That is evidence, decided by tier in Step 3, not by this ordering rule.
...
ASSUMPTION: the answer key is a compound-heterozygous pair
            (official evaluation.py docstring; partial credit gated at line 133)

R1  allele-sharing promotion, comparisons : 29400
R1  the rule LOWERED the score            : 0
R1  row sets where it RAISED it           : 480
```

### c22 (p=0.58)

Claim: The scorer-hedging scripts import the vendored official evaluator at tools/official-track1/evaluation.py, whose bytes are pinned by full SHA-256 in tests/test_track1_submission.py (6d18b581e65a45e1...).

Source: runtime/scorer-hedging-20260919/brute_force_hedging.py + tests/test_track1_submission.py

Excerpt:

```
ROOT = pathlib.Path.home() / "projects/mva-transparent-prioritizer/.worktrees/reference-setup"
sys.path.insert(0, str(ROOT / "tools/official-track1"))

import evaluation as off  # the pinned official scorer
...
ROOT = Path(__file__).resolve().parent.parent
OFFICIAL = ROOT / "tools" / "official-track1" / "evaluation.py"
OFFICIAL_SHA256 = "6d18b581e65a45e1ccc120071d588e740c2e42e983ff50704c60a40232b19180"
TEMPLATE = ROOT / "tools" / "official-track1" / "track1_submission_template.csv"
TEMPLATE_SHA256 = "7b3ed41c091d34fb6c5622d049c7a3f46124211fc7ec02947e69daef8752755a"
```

### c23 (p=0.31)

Claim: The five scripts brute_force_hedging.py, hedging_modes.py, classify_drops.py, verify_rule.py and verify_determinism.py exist in runtime/scorer-hedging-20260919/, and verify_determinism.py executes the Step 4 ordering as code, confirming the order is total and operator-independent.

Source: runtime/scorer-hedging-20260919/ (listing + verify-determinism-result.txt)

Excerpt:

```
ripgrep file listing of runtime/scorer-hedging-20260919/ (2026-09-26): hedging_modes.py, brute_force_hedging.py, verify_determinism.py, verify_rule.py, classify_drops.py (plus result.txt, classify-result.txt, verify-rule-result.txt, verify-determinism-result.txt, __pycache__).
...
verify-determinism-result.txt lines 9-13:
RESULT: the Step 4 ordering is total and operator-independent.
  No two distinct rows tie, so no comparison falls to a human.
  Every input permutation of the same pool produced the identical file.
  Truncation climbs tiers; the allele-sharing constraint holds and never
  reorders two pair rows.
```

### c25 (p=0.56)

Claim: The Step 4 allele-sharing constraint promotes a pair row above every single row that shares an allele with it, and the relative order of two pair rows is never changed by this step.

Source: runtime/scorer-hedging-20260919/verify_determinism.py

Excerpt:

```
def apply_allele_sharing(rows):
    """A pair row is promoted above every SINGLE row sharing an allele with it.
    Two pair rows are never reordered."""
    out = list(rows)
    for _ in range(len(out) ** 2 + 1):
        for i, upper in enumerate(out):
            if len(upper["alleles"]) != 1:
                continue
            for j in range(i + 1, len(out)):
                lower = out[j]
                if len(lower["alleles"]) == 2 and (set(upper["alleles"]) & set(lower["alleles"])):
                    out.insert(i, out.pop(j))
                    break
            else:
                continue
            break
        else:
            return out
```

### c27 (p=0.56)

Claim: track1-check runs the canonical parser together with the gate mirror, and validate_against_lane_representation checks every submitted variant against the lane contig keys it is given.

Source: docs/20-track1-submission-gate.md

Excerpt:

```
`score_submission` mirrors `score_proband`. `validate_against_lane_representation` maps submission chromosomes to the lane's contig naming (no prefix, `MT` for the mitochondrion) and requires every submitted variant to exist among the lane keys it is given; it receives keys, never rows, and reports counts only.

`tests/test_sensitivity_partition_mutations.py` disables each of 30 guards and scoring constants in this module and 2 in the CLI boundary in turn and requires the named test to fail.

CLI: `python3 -m mva_prioritizer.cli track1-check --submission <file> [--synthetic-truth '[[chrom,pos,ref,alt],...]'] [--mitochondrial-name chrM|chrMT] [--allow-ties] [--allow-unsorted] [--allow-repeated-pairings]`. One JSON line with counts on success; the file is opened with `O_NOFOLLOW`, decided on the descriptor, bounded at 1 MiB; after the canonical parse the CLI also runs the gate mirror and refuses if the two ranked variant lists differ. Every refusal, including argument errors (argument parsing runs inside the same boundary, with usage output suppressed), exits 2 with the fixed `input_rejected` line and never echoes a row or an argument.
```

### c29 (p=0.37)

Claim: The supplied data is a singleton VCF with no read-backed phase linking distant loci and no parental data, so two heterozygous alleles in one gene cannot be shown to be in trans from this input alone.

Source: docs/17-exomiser-probe.md

Excerpt:

```
It does not measure how often this happens in the private genome. It does not exercise phenotype scoring, gene ranking, the frequency filter, regulatory feature filtering, or the full CLI. Single-proband unphased data cannot distinguish cis from trans; the engine's recessive annotation reflects that ambiguity and so does this probe.
```

## Claims with no source in the allowed artifacts

No supporting artifact exists for these in the read set; none was invented.

- **n01** Nine gene regions were declared from public MVA literature on 7 September, before any case inspection. (No allowed artifact states this date or the declaration event; '7 September' appears nowhere.)
- **n02** The frozen map is runtime/nine-gene-audit-20260909/gene-interval-map.json on the encrypted host. (No file of that name exists in that directory, and the string appears in no allowed artifact.)
- **n03** The specialist packet (10 September, verified) covers the alleles that passed every filter in each lane and nineteen inheritance-sensitive entries. (No allowed artifact names or dates a specialist packet; '10 September' appears nowhere.)
- **n04** Another team raised the phasing limitation publicly on 18 September in Space discussion 24. (No allowed artifact mentions this discussion or date.)
- **n05** A reader running brute_force_hedging.py will see 48,252 for the equal-EPCR arm. (The number 48,252 appears in no allowed artifact; result.txt reports no such count.)
- **n06** The comparison arms are 1,735,200 strictly-below comparisons plus 108,450 equal-EPCR comparisons. (Neither number appears in any allowed artifact; only the 1,843,650 total is recorded.)
- **n07** The frozen Exomiser output records the annotation string AUTOSOMAL_RECESSIVE for a gene's recessive compatibility. (The token appears in no allowed artifact; docs/17 describes modes in prose only.)
- **n08** The document's first draft received an independent review verdict of FAIL with five blocking findings. (The review artifacts are outside the allowed read set; no allowed artifact records this verdict.)

## Files

- claims.json: every paired claim with claim_id, claim, excerpt, source_path, deterministic_hit, jev_probability, bucket
- no-source.json: the no_source claims
- request-1/2/3.json, answer-1/2/3.json: the exact Jev requests and raw answers

## Reading notes

- c19 (unsupported, 0.27): the doc's rule 5 says 'No tested case scored worse' for the recommended
  shape. result.txt shows the four recommended-shape scores but contains no line asserting that no
  tested case scored worse; that generalization is not quoted from any artifact.
- The uncertain band is mostly derivation claims: statements that require combining an artifact line
  with arithmetic or code semantics (c08, c10, c11, c12, c17, c22, c25, c27), provenance framing
  slightly beyond the excerpt (c01, c02, c13, c23), and c29, whose only support is a prose sentence in
  docs/17 that states the engine-side fact, not the input-data description the doc gives.
- The three deterministic number misses are claims the document attributes to measured runs
  (48,252; 1,735,200; 108,450) that no saved result file records.