# Candidate selection rule for the Track 1 submission

Written 19 September 2026, before the protected shortlist run. Public and synthetic only. Every example variant below is invented. This note authorizes no upload.

This document fixes how a Track 1 candidate file is built from the frozen evidence, and it is written before that evidence is read for selection purposes. A rule written after looking is not a rule; it is a description of a choice already made. The value of writing it now is that a reader can check the submitted file against it.

## What is already known, stated so the reader can discount it

This is a partial pre-registration, not a blind one. Work since 5 September has already produced results that constrain the plausible shortlist. Naming them here is the honest alternative to implying a clean slate. An independent review of the first draft found this list incomplete, and the two missing items are marked below.

- Nine gene regions were declared from public MVA literature on 7 September, before any case inspection: the dated literature-overlay artifacts in `runtime/internal-review-20260907/` (`literature-catalog.json`, `public-gene-identities.json`, `research-review.md`) are the first work that named them. The frozen interval map is `runtime/nine-gene-audit-20260909/gene-interval-map.json` (nine genes, GRCh38, with the reference and identity-source hashes it was built from). Everything under `runtime/` is ignored by Git and stays on this host and the encrypted volume; it is cited here by path so a reviewer with host access can check it, and it is not in the public tree.
- The nine-gene audit (9 September) established that all nine regions carry recorded alternate genotypes in both the stored original and the prepared analysis VCF, and that two regional records per input matched saved filtered rows.
- The diagnostic replay (`replay-2`, verified) produced full-evaluation output for both lanes over those regions plus the frozen passing controls.
- The recurrent-gene run (11 September, verified) flagged eleven genes appearing in the top thirty of both lanes, of which one lies inside a predeclared region.
- The specialist packet (10 September, verified; `runtime/specialist-review-20260910/`, and the release-candidate methods packet `docs/21-public-methods-packet.md` is dated the same day) covers the alleles that passed every filter in each lane and nineteen inheritance-sensitive entries.
- **Added after review.** The ReMM 0.963 sensitivity run was executed on 6 September, not merely designed. It retained 263 of 365 unique variants and 175 of 243 genes; 90 variants fell to the cutoff and 12 more lost inheritance compatibility; 7 retained genes changed inheritance mode. Receipt `d5ba10df94dcf684…` in `runtime/candidate-review-20260906/completion.json`. Tier C consumes this output, so omitting it from the first draft was a real gap.
- **Added after review.** The candidate review dossier (6 September, verified) is a separate artifact from the specialist packet. It preserved 421 coding gene rows with 794 variant associations and 290 noncoding gene rows with 454 associations over a 500-gene union, and it is the source of the nineteen inheritance-review entries. Step 1 consumes it.

What remains genuinely undecided, and what this rule governs: the final cut, the row ordering, the EPCR values, and the row count. Tier A membership is a narrower claim than it may appear. The alleles passing every filter in both lanes were already determinable from the disclosed `replay-2` and specialist-packet outputs before this rule was written, so which alleles sit in the top tier was knowable at writing time. What was not fixed, and what this document fixes, is how they are turned into rows.

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

A brute-force check over 1,843,650 scored combinations against the pinned official bytes (`verification/scorer-hedging/`) found:

| Behaviour tested | Cases where the score dropped |
|---|---:|
| Rows appended strictly below every existing row lowered rank points | 48,608 |
| Rows appended strictly below every existing row lowered F-max | 0 |
| A row added at an EPCR equal to an existing row lowered F-max | 44,090 |
| A row added at an EPCR equal to an existing row lowered rank points | 7,216 |

The equal-EPCR row costs points two ways. Losing F-max is the larger count, and the rank-point loss happens because the gate breaks a tie by file order, which can push a partial match down a scoring tier. A reader running `brute_force_hedging.py` will see `48,252` for the equal-EPCR arm rather than `44,090`: that script counts a case when either metric drops, while the table separates them. The arms are 1,735,200 strictly-below comparisons plus 108,450 equal-EPCR comparisons, totalling the 1,843,650 above. The prescribed ladder makes every EPCR distinct, so the submitted file avoids both failures.

Every one of the 48,608 rank-point drops is the same inversion: the exact true pair added below a higher-ranked row that already earned partial credit. A second classifier (`classify_drops.py`) asked what that higher row actually was, and the answer is not what a first reading suggests:

| The higher-ranked partial match was | Share of the 48,608 drops |
|---|---:|
| A row pairing one true allele with a **wrong partner** | 36,456 (75.0%) |
| A **single allele** of the true pair | 12,152 (25.0%) |

Three quarters of the damage comes from the case that looks least like a hedge. The scorer's partial-match test is `row.variants & true_variants`, an intersection, so a two-variant row naming one correct allele and one incorrect one earns the same partial credit as that allele alone. A speculative pair is therefore not a safe way to express an uncertain partner: it blocks the correct pair placed beneath it exactly as a single allele would.

The rules that follow from the measurement:

1. **A compound-heterozygous pair occupies row 1.** Full-match tiers are 100 at rank 1, 50 at ranks 2 to 3, 25 at ranks 4 to 5, 10 at ranks 6 to 10. A pair below rank 3 scores worse than the partial credit its own allele would have earned at rank 1.
2. **Never place a single allele row above a pair row that shares an allele with it.** This is the constraint whose violation produced all 48,608 drops. It applies to single rows only. Two pair rows sharing an allele are competing hypotheses. Stage 1 orders them by evidence; Stage 2 may lift the lower one over the higher when a shared single sits above both (this is measured and deliberate, see Step 4); Stage 3 then decides by arithmetic whether the loser keeps its pair row.
3. **Alternative pairings for an uncertain partner rank below the primary pair, never above it.** The canonical validator's `--allow-repeated-pairings` flag exists for this shape, and the ordering constraint in rule 2 governs its use.
4. **Every EPCR is distinct.** Ties cost F-max in 44,090 measured cases and the gate breaks ties by file order, which is not a ranking anyone should rely on.
5. **Rows below the top pair are worth including, and the price is stated.** Measured on the recommended shape (pair on top, its alleles alone beneath): if the pair is correct, 100 points and F-max 1.000; if only one of its two alleles is truly causal, 50 points where a pair-only file scores 0, and F-max falls from 1.000 to 0.667 because the pair row is then a false positive. Rank points is metric 1 in the official evaluator (`tools/official-track1/evaluation.py`, the `# --- Rank points (metric 1) ---` block) and the rule trades F-max for it on purpose; the trade is recorded here rather than described as free.

## Selection procedure

Executed once, read-only, against the frozen verified outputs on the encrypted host. No new variant calling, no re-ranking, no threshold change.

**Step 1. Assemble the pool.** Take the union of: alleles passing every filter in either lane of `replay-2`; alleles inside the nine predeclared regions carrying a recorded alternate genotype; alleles belonging to the flagged recurrent genes; and the inheritance-sensitive entries from the candidate review dossier (the 6 September artifact disclosed above, distinct from the specialist packet). Record the pool size before any exclusion.

**Step 2. Apply the exclusions, deterministically.** An allele is dropped only for one of these three reasons, each pinned to a named source so two operators reach the same set:

1. **Quality.** The allele's recorded quality evidence fails its lane's own criteria, as recorded by the already-reviewed audit module in `runtime/nine-gene-audit-20260909/`. The criteria are the lane's, not new ones; this step applies no threshold of its own.
2. **Representation.** The allele cannot be resolved to an exact GRCh38 `(chrom, pos, ref, alt)` tuple by the normalization already applied to the analysis VCF, using the pinned reference in `config/reference-bundle.json`. Resolution means the tuple is read from the frozen record, never reconstructed by hand. If a multiallelic record leaves the alternate ambiguous, the allele is dropped and counted; it is not guessed.
3. **Gene assignment.** The allele falls outside every transcript span in the pinned Ensembl database for its gene, and no annotation record in the frozen lane output assigns it to that gene. Both conditions must hold. An allele inside a span is never dropped by this rule, and an allele outside a span with a lane annotation is never dropped by it either.

Every drop is counted with its reason. A drop for any other reason, or a judgment call inside these three, invalidates this run.

The same pinning applies to Tier B below. "An inheritance mode compatible with a recessive mechanism" means the frozen Exomiser output records `AUTOSOMAL_RECESSIVE` for that allele's gene (the token as it appears in the engine's output; the public fixture `tests/fixtures/exomiser_probe_output.json` and `mva_prioritizer/sensitivity_partition.py` carry it verbatim), in the lane being read. It is the recorded annotation vocabulary, not an assessment. The sensitivity run showed this distinction has teeth: twelve variants kept their numerical scores and lost recessive compatibility, so "compatible" must name the annotation and the run it came from.

**Step 3. Tier what remains.**

- **Tier A.** Alleles passing every filter in both lanes.
- **Tier B.** Alleles passing in one lane inside a predeclared region, with an inheritance mode compatible with a recessive mechanism.
- **Tier C.** Alleles in recurrent genes, or surviving the 0.963 sensitivity run with changed inheritance compatibility.
- **Tier D.** Everything else in the pool.

**Step 4. Form the rows.** Pairing operates across the union of Tier A and Tier B, not within each tier separately: any two alleles in the same gene, both in Tier A or Tier B, with the recorded recessive annotation, form a pair row. A pair row formed from alleles in different tiers takes the weaker of the two tiers. With three or more qualifying alleles in a gene, `C(k,2)` pair rows form; which of them survive is decided in stage 3 below, by a stated test.

Rows are then placed by three stages, in this order. Each stage is executed by `mva_prioritizer/candidate_selection.py`, and `tests/test_candidate_selection.py` pins every sentence of this step to a synthetic case.

**Stage 1, the evidence sort.** One total order, applied in sequence so no step leaves a choice open:

1. **Tier.** A before B before C before D.
2. **Lane agreement.** Within a tier, rows appearing in both lanes before rows appearing in one.
3. **Native rank.** Then by the stricter lane's native output rank. For a pair row this is the better (numerically lower) rank of its two alleles, since the pair is at least as strong as its stronger member.
4. **First allele coordinate.** Then by the pinned contig order, then position, then reference allele, then alternate allele. For a pair row, its first allele under this ordering.
5. **Class.** Then a pair row before the single row of its own first allele. This is the only place row class enters the sort, as the last tiebreak; an earlier draft made "all pairs before all singles" the first key, and the measurement arm below had already falsified that formulation. The review of commit `741aaad` caught the contradiction.
6. **Second allele coordinate.** Then a pair row's second allele.

Every comparison resolves at one of these six keys: two distinct rows cannot tie at key 6, because two rows with identical allele coordinates are the same row. The order is therefore total.

**Stage 2, promotion.** A pair row takes the topmost slot among itself and the single rows above it that share one of its alleles; those singles fill the block's remaining slots in their existing order. Rows outside the block keep their positions. This is the form rule 2 takes in code, and the position-preserving shape matters: an earlier draft inserted the pair at the single's slot and shifted everything between them down one rank, which at four rows or more pushed an unrelated row across the 50-to-25 tier boundary (5,220 lowered scores in 327,600 comparisons at four rows, found by the review of `741aaad`). Promotion moves only the block, so it cannot.

The block may reach above a pair row the evidence ranked higher, when a sharing single sits above both pairs. The lower pair then lands above the evidence winner, and the review of `1783250` reported this as the evidence being overruled. It is a measured choice. `policy_probe.py` compares this promotion ("direct") with a variant whose block never passes a higher pair ("floor") and one that carries the intervening pairs up with it in evidence order ("transitive"). With the shipped demotion policy, floor leaves the single's allele stranded below and loses the partial credit it was earning: 34.895 mean rank points against 36.357, and it scores below the plain sort in 10 comparisons. Transitive scores below the plain sort in 589 of 36,033 comparisons, because lifting the higher pair pushes rows beneath it across tier boundaries. Direct with the shipped demotion policy never scores below the plain sort; direct with always-keep or always-demote does (44 and 34 comparisons), so the property belongs to the promotion and demotion pair, not to the promotion alone. The evidence winner that is passed keeps every allele it held in a row at or above its old rank, so under its own truth it never loses the partial credit it had; what it can lose is the full-match bonus, which Stage 3 then weighs.

**Stage 3, resolution of competing pairs.** A pair row at rank r that shares an allele with a pair row kept above it at rank q lost on evidence. Under its own truth it already earns the partial value of the winner's rank, half of points(q), and a full match preempts a partial. So it keeps its pair row only where its own full-match points at its rank are strictly above that partial, points(r) > 0.5 x points(q). Otherwise the row can only equal or lower the score under its own truth, and it becomes a single row for its unshared allele in the same position, with any lower single for that allele dropped as a duplicate; it is removed instead when both of its alleles are claimed by pairs above it, or when a single for its unshared allele already sits above it (a remnant there would duplicate a row, which the parser rejects). In the official tiers: a pair sharing an allele with the rank-1 pair is demoted from rank 2 down (50 is not above 50); one sharing with a rank-2 or rank-3 pair stays at rank 3 (50 above 25) and is demoted from rank 4 down; one sharing with a rank-4 or rank-5 pair stays at rank 5 and is demoted from rank 6.

The trade in keeping a paying pair: under its own truth it earns its full-match points where the demoted form would earn only the partial through the winner; under any other truth its row occupies a slot that the demoted single or the rows beneath would otherwise fill, and those rows may cross a tier boundary. The probe shows the keep side wins on balance for paying ranks (pays_gt against demote, 36.357 against 36.296) and never costs a truth its plain-sort score, which always-demote does.

Schedule. Stages 2 and 3 run to a joint fixpoint: promote to a fixpoint, then demote to a fixpoint, and repeat until a full round changes nothing. The order matters. Demoting to a fixpoint before any re-promotion judges every loser in a round at its rank in the promoted table; the alternative, one demotion then re-promotion, lets a single created by a demotion be promoted over first, which lifts a later loser one slot and can change whether it pays. The review of `28761f8` found the module on the second schedule while the probe measured the first, a difference that a universe with at most three alleles per gene cannot show (the two schedules diverge on 22 of the 3,000 tracked pools once a gene carries four alleles, and on 28 to 48 per 3,000 across ten further seeds). The probe now measures both schedules; batch scores higher on every seed (36.357 against 36.353 on the tracked run, ahead on ten further seeds by 0.0004 to 0.010), both never below the plain sort, and the module ships the batch schedule.

The policy for the losing pair was chosen by measurement in `policy_probe.py`, which implements every candidate inside the script (none calls the module) and measures the shipped module as its own row, so no two rows can be the same function unnoticed; the first version of that probe at commit `1783250` had exactly that fault, and the review of `1783250` caught it. The review of `28761f8` then found the probe's `direct+pays_gt` was not the module's function either (schedule and a removal branch differed), hidden by a universe too small to separate them. The probe now runs 24 combinations of two schedules, three promotions and four demotion policies on 36,033 truth comparisons over 3,000 random pools drawn from ten alleles in four genes (four in one gene, so schedules can differ), tiers A to C, and checks coincidence with the module on a second seed as well. The first number that decides is domination: how often the policy scores BELOW the plain evidence sort under some truth, which no truth-blind rule may do. Four policies clear that bar, all direct promotion with a pays test; demoting at equality beats keeping at equality (36.357 against 36.155), and the batch schedule edges the step schedule. Always-demote scores 36.296 and fails the bar (34 comparisons below the plain sort); always-keep scores 35.899 and fails it (44). That is the shipped rule, `batch/direct+pays_gt`, and the probe's last two lines confirm the module coincides with it on all 3,000 pools under each of two seeds. The mean is over uniformly random pair truths, which assumes every pair is equally likely, the opposite of what the evidence sort says, so it ranks only among policies that already dominate.

This ordering is fully determined by the evidence; no discretionary reordering is permitted after the pool is read.

**Step 5. Assign EPCR.** Descending, distinct, from a fixed ladder assigned by row position, not chosen per candidate: 0.90, 0.75, 0.60, 0.50, 0.40, 0.30, 0.20, 0.15, 0.10, 0.05. EPCR expresses this file's internal ranking. It is not a probability of causation and the report says so.

**Step 6. Cap at ten rows.** The gate refuses eleven. If more than ten rows qualify, remove rows from the bottom of the Step 4 order, one at a time, until ten remain. Truncation therefore climbs through tiers when the lowest tier is exhausted, and it cuts from the tail of each tier's own ordering. The count of truncated candidates is recorded, by tier.

**Step 7. Validate.** Run `track1-check --allow-repeated-pairings` with the canonical parser and the gate mirror, and `validate_against_lane_representation` against the lane keys on the encrypted host. The flag is required, not optional: the rule's shape repeats each pair's alleles as single rows below it on purpose, and the canonical parser refuses repeats by default because they add no F-max recall. The parser's other defaults (no ties, sorted rows) stay in force; the ladder satisfies both. Any refusal stops the run. A mitochondrial row blocks the file until the organizers confirm the contig spelling.

Steps 4 to 6 are executable: `mva_prioritizer/candidate_selection.py` implements them, and `tests/test_candidate_selection.py` pins each sentence above to a synthetic case, so a change to this document that is not mirrored in the code fails the suite. The module handles no data; Steps 1 to 3 read private files and run only on the encrypted host.

## Phase, and what the file can honestly claim

The supplied data is a singleton VCF with no read-backed phase linking distant loci and no parental data. Two heterozygous alleles in one gene cannot be shown to be in trans from this input alone. An Exomiser inheritance annotation records compatibility, which is a weaker statement.

The pair row therefore asserts a ranked hypothesis, not established phase. The report states the available phasing evidence for any submitted pair, and states its absence where absent. The single-allele rows below the pair exist precisely because the pair is unproven.

Another team raised the same limitation publicly on 18 September in discussion 24 of the hackathon Space (`huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/discussions/24`), asking the organizers whether transmission or phase was established. The organizers declined on 25 September, in writing, for every team: confirming trans-phase for a two-variant hypothesis is equivalent to confirming the answer, and any such information would go to all participants at once, after the challenge closes. Any answer they publish applies to every participant and would be new evidence; it changes the file only through this rule, never around it.

## Manual changes

Program-generated ordering is the default and the report distinguishes it from any later human change. A specialist may reorder, drop or add a row. Each such change is recorded with its reason in the methods report (`docs/21-public-methods-packet.md` carries that section). A change with no recorded reason is not applied.

## Verification of this rule

Every ordering claim above rests on one stated assumption: **the answer key is a compound-heterozygous pair.** The official evaluator says so in its own docstring, "simplified for a single proband (N-of-1) with a clinically validated compound-heterozygous answer key", and it gates partial credit on `is_compound_het = len(true_variants) == 2`. If the organizers ever contradict this, `verify_rule.py` must be re-run before the file is built, because under a single-variant key the pair-promotion rule loses points instead of gaining them.

The claims are reproducible from `verification/scorer-hedging/`:

| Script | What it establishes |
|---|---|
| `brute_force_hedging.py` | Scores the full combination space and finds the 48,608 rank-point drops. Its equal-EPCR count is 48,252 because it counts a case when either metric drops; `hedging_modes.py` separates them into 44,090 and 7,216. `brute_force_hedging.py` exits non-zero by design because it reports a falsified claim; `hedging_modes.py` exits zero. |
| `hedging_modes.py` | Separates the three failure modes and measures the recommended shape |
| `classify_drops.py` | Classifies what the blocking higher-ranked row actually was (75% wrong-partner pairs) |
| `verify_rule.py` | Superseded. It measured the promotion only at two and three rows, where a shift cannot cross a tier boundary; kept for the record of the three formulations it falsified |
| `verify_rule_v3.py` | Measures position-preserving promotion at every row count the gate allows: 2 to 4 enumerated in full, 5 to 10 sampled, 5,880,600 comparisons, 0 rank-point drops, and moves only the block in all 230,332 orderings where it fired |
| `policy_probe.py` | Scores 24 policies (two schedules, three promotions, four losing-pair rules), each implemented in the probe, against the plain sort on 36,033 truth comparisons, and checks which one the module coincides with on two seeds; the numbers behind Stage 2 and Stage 3 |
| `verify_module.py` | Imports the shipped module rather than a copy of it, and checks determinism, the Stage 2 and Stage 3 invariants, that both stages actually fired, and that the resolved file never scores below the plain evidence sort: 3,000 pools, 20,245 truth comparisons, 0 lowered |
| `verify_determinism.py` | Superseded by `verify_module.py`. It re-implemented the sort inside the script and, because that sort placed every pair above every single, its promotion check could never fire; the review of `741aaad` found both faults |

Every script that scores a file imports the vendored official evaluator at `tools/official-track1/evaluation.py`, whose bytes are pinned by SHA-256 in `tests/test_track1_submission.py`; the superseded `verify_determinism.py` scores nothing and imports only the standard library. They locate the worktree relative to their own path, not to a home directory.

The determinism claim is the one this document exists to make, so it is measured against the code that will build the file. Across 3,000 random pools, every input permutation produced the identical rows and EPCRs, no single row sat above a pair sharing its allele, no kept sharing pair sat below the rank where it pays, and the promotion and resolution stages each changed the order in a non-trivial share of pools, so the invariants were exercised rather than vacuously true.

## Review history

This document has been independently reviewed five times, each time against the exact bytes of a commit, by a reviewer with no part in writing it. Every verdict was FAIL. Every finding is fixed above, and the corrections are visible rather than silent.

**Review of the first draft** (verdict recorded at `verification/reviews/ea68d94.json`): five blocking findings.

| Finding | Resolution |
|---|---|
| "All 48,608 drops came from a single allele above the pair" was false | Reclassified: 75% were wrong-partner pairs. The claim and the rule both changed. |
| Rule 2 guarded only single rows, while Step 4 creates the wrong-partner pair shape | Pair-versus-pair precedence moved to the evidence keys, then to the Stage 3 test |
| Four unconstrained choices survived the ordering wording | Replaced with a total order, then verified by execution |
| The 0.963 sensitivity run was consumed by Tier C but never disclosed | Added to the disclosure with its executed counts and receipt |
| Two drop conditions were unpinned human judgments | Each pinned to a named source and vocabulary |

**Review of commit `741aaad`** (verdict at `verification/reviews/741aaad.json`): four logic errors, two blocking. This review found that the fixes to the first review had introduced their own faults, and that the verification scripts did not support the claims at the row counts the gate allows.

| Finding | Resolution |
|---|---|
| Step 4's first sort key, "all pairs before all singles", was the formulation the document's own table had falsified | Class demoted to the last tiebreak; tier is the first key. Scored counterexample pinned in the tests: 25 became 50 |
| `verify_rule.py` measured promotion only at 2 and 3 rows; at 4 rows the insert-and-shift lowered 5,220 scores by pushing bystanders across a tier boundary | Promotion rewritten to move only its block; `verify_rule_v3.py` measures it at every row count, 0 drops |
| "Two pair rows are never reordered" was false for the committed code and vacuous in the pipeline, because the sort had already placed every pair first | The claim is withdrawn; `verify_module.py` tests the shipped module on pools where promotion actually fires |
| "Keeping the losing pair never scored lower" was measured only on two-row files; with bystanders it re-admits the headline failure | Replaced by the Stage 3 arithmetic test, chosen by `policy_probe.py` over three alternatives |

**Review of commit `1783250`** (verdict at `verification/reviews/1783250.json`): three blocking findings and five notes. This review found that the fixes to the second review had a measurement fault at their centre and a privacy fault at their edge.

| Finding | Resolution |
|---|---|
| `policy_probe.py` listed four policies but two called the same module function; "always demote" was never run, and re-implemented it beat the shipped rule on the probe's own metric | Probe rewritten with every policy implemented inside the script and the module measured as its own row; the decision now rests on domination first (never below the plain sort) and mean second. The shipped rule changed: a losing pair is demoted at equality, not kept |
| Stage 2 can lift a weaker pair over the evidence winner when a shared single sits above both, while the text said the contest was "decided by tier" | The text now states the behaviour, its measured alternatives ("floor", "transitive") and why direct promotion is kept; the reviewer's pool is a pinned test that scores both truths |
| Two tracked Jev request files carried an excerpt copied from a private aggregate report, naming eleven case-derived gene symbols; every scan in force passed them | Excerpts from private artifacts withheld from the tracked copies; a new gate, `scripts/verify_no_case_tokens.py`, refuses any tracked file containing a token from a host-local denylist, wired into Build OS verify and proven to fail on the bytes of `1783250`. The denylist is built by `scripts/build_case_token_denylist.py` from the private artifacts (nine-gene interval map and HGNC responses: symbols, aliases, previous symbols, HGNC, Entrez, Ensembl, RefSeq, OMIM and other database ids, transcript ids; every symbol in the recurrent-gene report), 218 tokens, and the gate fails closed when it is absent, so Build OS verify passes only on a host that holds the private artifacts. `--history` scans every reachable blob for the pre-publication check (docs/20) |
| Notes: the "single already sits above" removal branch was unreachable under the step schedule of that commit; the losses attributed to "an unrelated true pair" crossing rank 5 were mostly other row types; `verify_module.py`'s D2 docstring did not match its check; the domination direction of the keep case was a trade, not a guarantee | Branch removed at `28761f8` and restored at `25d0b47`, where the batch schedule makes it reachable; the loss description corrected; D2 restated to the invariant the rule enforces; the trade is now stated in Stage 3 |

**Review of commit `28761f8`** (verdict at `verification/reviews/28761f8.json`): two blocking findings and five notes, on the commit that resolved the third review.

| Finding | Resolution |
|---|---|
| The probe's `direct+pays_gt` was still not the module's function: the probe demoted to a fixpoint before re-promoting while the module re-promoted after every single demotion, and the probe kept a removal branch the module had dropped. The probe's universe (at most three alleles per gene) could not separate them, so "coincides on all 4,000 pools" was true of the wrong function, the same class of fault as the previous B1 | Schedule made an explicit policy dimension and both measured in a universe with four alleles in one gene; batch scores higher on every seed and the module now ships it, with the removal branch restored. Coincidence is checked on two seeds. The reviewer's pool is a pinned test |
| The sentence "always demoting has the highest raw mean in one promotion family (46.574)" was carried over from the previous rule; the tracked result showed the shipped rule ahead on mean in every family | Every number in Step 4 and the module docstring now comes from the current result file, and the claim-provenance pass below checks them |
| Notes: "direct never scores below the plain sort" holds only with a pays demotion; the keep-versus-drop trade was claimed as stated and was not; a test comment quoted rejected-family means; "reviewed twice" and "four policies" were stale; the denylist gate fails closed on any host without the list | Stage 2 names the pair the property belongs to; the trade is written into Stage 3; the comment, counts and the gate's documentation corrected |

**Review of commit `25d0b47`** (verdict at `verification/reviews/25d0b47.json`): two blocking findings and six notes, on the commit that resolved the fourth review.

| Finding | Resolution |
|---|---|
| The tracked `verify-module-result.txt` was not the output of the shipped module: it was generated between the schedule change and the restoration of the removal branch, so it measured an intermediate module (D4 higher 7,982 against 8,305 from the shipped code). The invariants D1, D2 and D4-lower were 0 on the real re-run, so the claims held; the receipt did not | Receipt regenerated from the shipped module and checked byte-equal to a fresh run before commit; the claim-provenance pass now pins the D4 number |
| The schedule test did not separate the schedules: it passed on the step schedule too, and the pool it used was not the reviewer's pool the commit message said was pinned | The test now uses the reviewer's pool from the review of `28761f8`, asserts the batch file, asserts the step file is not produced, and was run against a scratch copy of the module with the step loop restored, where it fails on the third row |
| Notes: the module docstring said twelve policies (24); the `_demote_once` docstring described only the first call in a round; the denylist skipped Entrez, Ensembl gene, RefSeq and OMIM ids present in the artifacts it reads; the fixture gene in docs/20 is also a case-flagged recurrent gene, and the literature claim is checkable only from `runtime/`; the `1783250` notes row read as self-contradictory; "one pool in eighty" was 1 in 136 on the tracked seed | All corrected; the denylist now carries every database id field of the HGNC responses (218 tokens), docs/20 states both facts about the fixture gene and where they are checkable, and the divergence counts are the measured ones (22 of 3,000 on the tracked seed, 28 to 48 on ten further seeds) |

**Claim-provenance pass.** After the second review, every checkable claim in this document was paired with its supporting excerpt and put to the Jev decision model (`verification/jev/claim-provenance/`): 40 claims, 4 model calls. It found eight claims with no supporting artifact in its read set. Four were the result of that read set being narrower than the tree (the gene-interval map, the sensitivity token, the specialist packet date, the review verdicts) and are now cited by path above; four were real: the 48,252 figure and the arm sizes existed only as prose, and the 7 September declaration and the Space discussion had no citation. The arm sizes and the discussion are now cited to their sources; the 7 September date rests on the dated literature-overlay artifacts in `runtime/internal-review-20260907/`, which is the first work that named the nine genes. A second pass on the rewritten document at `1783250` (`report-1783250.md` alongside, 71 claims, 4 calls) found three sentences that were false as written: the interval map was called "tracked in this repository" while `runtime/` is ignored; `hedging_modes.py` was said to exit non-zero and it exits zero; `verify_determinism.py` was said to import the evaluator and it imports nothing of the kind. All three are corrected above, and the private-artifact citations now say plainly that they are host-local.

Most of the findings across these reviews were errors the author could not see by reading. They were found by reviewers asking what the scorer did rather than what the document said. That is the reason this project commissions reviews against exact bytes, and the reason this section exists.
