# Track 1 report: AI help for a child's genome, with the patient data kept off the AI

Team: Acadine Intelligence. Track 1 (variant prediction), one model. Code: https://github.com/acadine-intelligence/mva-transparent-prioritizer (private during the hackathon; we will publish a privacy-scanned snapshot afterwards). This report contains no genotype, coordinate, gene symbol or other patient record. It reports aggregate counts and the shape of the submitted file.

## The problem we worked on

Families, foundations and small clinical teams want modern AI to help with an undiagnosed child's genome. A genome and a phenotype record cannot simply be pasted into a hosted model, and this challenge's terms limit how hosted models may handle the data. So AI help often stops at the door of the data.

We asked a narrower question than "can AI find the variant". Can AI agents do most of the engineering, research and review for a rare-disease analysis while the patient records stay on one sealed machine, and can that claim be tested instead of trusted?

## What we built

**1. A sealed runtime with a counts-only door.** The genome, the phenotype document and the case outputs stayed on one encrypted, offline machine, with the exceptions described below. AI agents wrote and reviewed the code against synthetic fixtures. Code reached the sealed machine as a frozen, hash-checked commit. Counts, hashes and exit codes came back out. Error output from private steps was thrown away, because error messages are a leak route. When we needed an answer about the real case during review, we wrote a small program that returned only booleans and ranks. For example: "is the top row a pair, and do both alleles sit in a gene we declared before looking at the case?"

The boundary was not perfect, and we record the slips. A claim-checking script copied case-derived gene symbols from a private report into a tracked file. Before an internal review caught it, that file was read by two hosted models: the decision model used for claim checks and a semantic leak scan, and the code reviewers. The file was fixed and a denylist gate was added. Separately, one public-literature research brief to an OpenAI model contained one aggregate sentence derived from the case. The genome, the phenotype document and the variant-level records were never sent to any model; case-derived information reached models only in these ways. The ten-row submission file left the sealed machine once, through the operator's own laptop, to be uploaded to this challenge.

**2. Established scoring engines, kept honest.** We did not write a new variant-scoring engine. Exomiser 15.1 runs separate coding and noncoding (Genomiser) lanes on a pinned GRCh38 reference, with VEP and ClinVar annotation. Source scores and inheritance annotations stay as the engines report them. We do not merge them into an invented clinical probability. A stricter noncoding threshold run (ReMM 0.963) shows which candidates depend on a borderline call. A full-evaluation replay makes filter rejections inspectable instead of silently dropped. Two 2025 studies support the same parameter direction.[1][2] Our own code is the selection layer that turns engine output into ten rows (section 3).

**3. A selection rule written before the evidence was read for selection.** The step from evidence to a ten-row file is where human bias enters. We wrote the rule down first and pinned its steps to tests. It went through seven independent reviews of the rule's text and code (six failed, the seventh passed) before it ran on case data. It is a partial pre-registration: earlier results, disclosed in `docs/22`, already constrained the shortlist. Nine syndrome genes were declared from public literature on 7 September 2026, before case inspection; the dated declaration is held with the private files. The rule fixes tiers, pairing, row order, the confidence ladder and the ten-row cap. A human may change a row only with a written reason.

**4. A pre-registered search for published alleles that standard filters miss.** The literature on this syndrome includes families first reported with only one damaging allele, later solved by a second allele that standard filters remove, for example a regulatory change tens of kilobases upstream of the gene. We built a catalog of 27 published disease alleles, each with a GRCh38 position whose reference bases we checked against Ensembl, and recorded its SHA-256 in `docs/24` before any lookup. Each entry was matched against the candidate pool and looked up directly in the original VCF. The rule promised that zero matches would leave the file byte-identical, and tests enforce that. The catalog itself stays private until the public release, because its gene names overlap the case's protected-token list.

**5. We attacked our own privacy boundary.** A privacy claim checked only by its authors is a hope. We wrote 21 synthetic tests, attacks plus controls, against the real entry points. **12 of the attack tests got through** (some cover several variants of one attack). They covered:

- error messages that echo a rejected value or a file path;
- values hidden by base64, hex, reversal or line splitting;
- a hash in a public summary that can be reversed when only a few values are possible;
- counts that reveal whether a known candidate is present;
- protected text in file names;
- identifier shapes and gene aliases the scanners did not recognise;
- scanners that checked working files instead of the bytes staged for commit.

The suite records each gap as a known failure. We will fix the gaps that affect publication before the repository goes public.

**6. We audited the scorer.** We vendored the official evaluator, pinned its bytes, and scored 1,843,650 synthetic submission layouts. In 48,608 of them, adding a correct answer lowered the score, because a full match is scored ahead of a higher-ranked partial match. In 75 percent of those cases the cause was a speculative pair that named one right allele and one wrong one. That shaped our file: the leading pair sits in row 1, every confidence value is distinct, and no single allele sits above a pair that contains it.

## The result

The file has ten rows: two compound-heterozygous pairs and eight single alleles. Row 1 is a pair whose two alleles lie in the same gene, one of the nine declared before case inspection. Both alleles passed every filter in both lanes. The data has no parents and no read-backed phase, so the pair is a ranked hypothesis that the alleles sit on different copies, not a proven one. The single-allele rows below it exist for that reason.

The published-allele search matched 0 of 27, so the file is byte-identical to the output of the original rule. Zero matches means none of these 27 published alleles is present as a called variant in the supplied VCF. It does not exclude the mechanism, new alleles, structural variants or variants missing from the supplied calls.

## Why this matters beyond one child

- **It lets AI help where it is often shut out.** AI agents, under human direction, wrote the code, did the literature research and ran the adversarial reviews, while the patient records stayed on one machine. The same pattern can wrap other engines.
- **It turns "we kept the data private" into something a reviewer can check.** The leak suite is the reusable part. Any team that puts agents near sensitive data can run the same attack classes against its own boundary. Twelve of our attack tests got through, which is the point: the suite found real gaps.
- **Pre-registration makes N-of-1 work auditable.** A family or a reviewer can read the rule, read the file, and check that one produced the other.
- **Scorer audits help organisers.** The inversion we measured is general. Future challenge designers can run the same brute-force audit before launch.

## Reuse

The public snapshot will contain the selection rule and its tests, the catalog lookup, the leak suite, the scorer audit scripts and synthetic fixtures. Some run-preparation scripts lived with the private data and are not yet in the tracked tree; the release will add the ones needed for reuse or list what is missing. Controlled genotype data will be deleted under the challenge's 30-day rule.

## Limits

This is research software. It makes no diagnosis or treatment claim. Single-sample data cannot prove phase or inheritance. The supplied calls have no structural-variant fields. The confidence ladder orders rows; it is not a probability of causation. Independent software reviews checked the code, not the biology. No clinician has reviewed the rows.

## AI and software disclosure

AI agents did software development, public-literature research, drafting and code review, through subscription plans: OpenAI ChatGPT Pro (Codex CLI; model-training setting off); Anthropic Claude Max (Claude Code; model-training setting off); Z.ai GLM Coding Plan (GLM 5.3); Moonshot Kimi membership (Kimi Code, Kimi K3); Nous Portal subscription. Separately, a pay-per-call decision-model API (TypeSafe Jev, standard account: TypeSafe states Jev is not trained on customer requests; no zero-data-retention agreement) scored claim-provenance checks and the semantic leak scan. The agent provider list comes from our local ledger of every agent session that touched this repository; the decision-model calls are recorded in the repository's verification files. All case-level computation ran as deterministic programs on the encrypted machine. The privacy slips are described in section 1.

Detailed methods: `docs/21-public-methods-packet.md` (pipeline), `docs/22-candidate-selection-rule.md` (selection rule, review history and scorer audit), `docs/24-catalog-amendment.md` (published-allele search), `docs/25-leak-suite-spec.md` (leak suite; on branch `mva-leak-suite` until the public release).

## Sources

[1] https://link.springer.com/article/10.1186/s13073-025-01546-1
[2] https://pmc.ncbi.nlm.nih.gov/articles/PMC12452281/
