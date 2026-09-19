# Candidate selection rule for the Track 1 submission

Written 19 September 2026, before the protected shortlist run. Public and synthetic only. Every example variant below is invented. This note authorizes no upload.

This document fixes how a Track 1 candidate file is built from the frozen evidence, and it is written before that evidence is read for selection purposes. A rule written after looking is not a rule; it is a description of a choice already made. The value of writing it now is that a reader can check the submitted file against it.

## What is already known, stated so the reader can discount it

This is a partial pre-registration, not a blind one. Work since 5 September has already produced results that constrain the plausible shortlist. Naming them here is the honest alternative to implying a clean slate.

- Nine gene regions were declared from public MVA literature on 7 September, before any case inspection. The frozen map is `runtime/nine-gene-audit-20260909/gene-interval-map.json` on the encrypted host.
- The nine-gene audit (9 September) established that all nine regions carry recorded alternate genotypes in both the stored original and the prepared analysis VCF, and that two regional records per input matched saved filtered rows.
- The diagnostic replay (`replay-2`, verified) produced full-evaluation output for both lanes over those regions plus the frozen passing controls.
- The recurrent-gene run (11 September, verified) flagged eleven genes appearing in the top thirty of both lanes, of which one lies inside a predeclared region.
- The specialist packet (10 September, verified) covers the alleles that passed every filter in each lane and nineteen inheritance-sensitive entries.

What remains genuinely undecided, and what this rule governs: which specific alleles enter the file, in which rows, at which EPCR values, and how many rows are used.

## Stop conditions that outrank the rule

The rule below produces a candidate file. It does not authorize sending one.

- No specialist has reviewed the packet. Until one has, the file is a prepared artifact, not a submission.
- Selection is a research judgment expressed as an ordering. It is not a clinical classification, and the file carries no calibrated probability of causation.
- If the procedure yields no allele meeting Tier A or Tier B, the honest output is a short file or no file, never a padded one. An empty result stays explicit.

## Row ordering rule, and why it is not obvious

The official scorer awards a full match unconditionally, even when a higher-ranked partial match would have scored more:

```python
if full_match_rank is not None:
    rank_points = float(_rank_to_points(full_match_rank))
elif partial_match_rank is not None:
    rank_points = 0.5 * _rank_to_points(partial_match_rank)
```

A full match at rank 4 scores 25. A partial match at rank 1 scores 50. So submitting the correct pair, placed below a single allele of that pair, can score **less** than not submitting the pair at all. Adding the right answer in the wrong row is a penalty.

A brute-force check over 1,843,650 scored combinations against the pinned official bytes (`runtime/scorer-hedging-20260919/`) found:

| Behaviour tested | Cases where the score dropped |
|---|---:|
| Rows appended strictly below every existing row lowered rank points | 48,608 |
| Rows appended strictly below every existing row lowered F-max | 0 |
| A row added at an EPCR equal to an existing row lowered F-max | 44,090 |

Every one of the 48,608 rank-point drops was the same inversion: the exact true pair added below an existing single allele of that pair. None had another cause.

The rules that follow from the measurement:

1. **A compound-heterozygous pair occupies row 1.** Full-match tiers are 100 at rank 1, 50 at ranks 2 to 3, 25 at ranks 4 to 5, 10 at ranks 6 to 10. A pair below rank 3 scores worse than the partial credit its own single allele would have earned at rank 1.
2. **Never place a single allele above the pair it belongs to.**
3. **Every EPCR is distinct.** Ties cost F-max in 44,090 measured cases and the gate breaks ties by file order, which is not a ranking anyone should rely on.
4. **Singles below the pair are free and are worth including.** Measured on the recommended shape: if the pair is correct, 100 points and F-max 1.000; if only one of the two alleles is truly causal, 50 points, where a pair-only file scores 0. No tested case scored worse.

## Selection procedure

Executed once, read-only, against the frozen verified outputs on the encrypted host. No new variant calling, no re-ranking, no threshold change.

**Step 1. Assemble the pool.** Take the union of: alleles passing every filter in either lane of `replay-2`; alleles inside the nine predeclared regions carrying a recorded alternate genotype; alleles belonging to the flagged recurrent genes; and the inheritance-sensitive entries from the candidate dossier. Record the pool size before any exclusion.

**Step 2. Apply the exclusions, deterministically.** Drop an allele when the recorded quality evidence fails the lane's own criteria, when its representation cannot be resolved to an exact GRCh38 `(chrom, pos, ref, alt)` tuple, or when it appears only outside a transcript span with no annotation evidence supporting the gene assignment. Every drop is counted with its reason. A drop for any other reason invalidates this run.

**Step 3. Tier what remains.**

- **Tier A.** Alleles passing every filter in both lanes.
- **Tier B.** Alleles passing in one lane inside a predeclared region, with an inheritance mode compatible with a recessive mechanism.
- **Tier C.** Alleles in recurrent genes, or surviving the 0.963 sensitivity run with changed inheritance compatibility.
- **Tier D.** Everything else in the pool.

**Step 4. Form the rows.** Within Tier A and Tier B, any two alleles in the same gene with a mode of inheritance compatible with compound heterozygosity form a pair row. Pair rows rank above single rows. Within a tier, order by lane agreement (both lanes above one), then by the stricter lane's native rank, then by the pinned contig order and position. This ordering is fully determined by the evidence; no discretionary reordering is permitted after the pool is read.

**Step 5. Assign EPCR.** Descending, distinct, from a fixed ladder assigned by row position, not chosen per candidate: 0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05. EPCR expresses this file's internal ranking. It is not a probability of causation and the report says so.

**Step 6. Cap at ten rows.** The gate refuses eleven. If more rows qualify, the lowest tier is truncated and the count of truncated candidates is recorded.

**Step 7. Validate.** Run `track1-check` with the canonical parser and the gate mirror, and `validate_against_lane_representation` against the lane keys on the encrypted host. Any refusal stops the run. A mitochondrial row blocks the file until the organizers confirm the contig spelling.

## Phase, and what the file can honestly claim

The supplied data is a singleton VCF with no read-backed phase linking distant loci and no parental data. Two heterozygous alleles in one gene cannot be shown to be in trans from this input alone. An Exomiser inheritance annotation records compatibility, which is a weaker statement.

The pair row therefore asserts a ranked hypothesis, not established phase. The report states the available phasing evidence for any submitted pair, and states its absence where absent. The single-allele rows below the pair exist precisely because the pair is unproven.

Another team raised the same limitation publicly on 18 September (Space discussion 24), asking the organizers whether transmission or phase was established. Any answer they publish applies to every participant and would be new evidence; it changes the file only through this rule, never around it.

## Manual changes

Program-generated ordering is the default and the report distinguishes it from any later human change. A specialist may reorder, drop or add a row. Each such change is recorded with its reason in the methods report, as the official workbook requires. A change with no recorded reason is not applied.

## Verification of this rule

The row-ordering claims are reproducible from the artifacts in `runtime/scorer-hedging-20260919/`: `brute_force_hedging.py` scores the full combination space, `hedging_modes.py` separates the failure modes, and `result.txt` holds the output. Both scripts import the vendored official evaluator at `tools/official-track1/evaluation.py`, whose bytes are pinned by SHA-256 in `tests/test_track1_submission.py`.
