# Track 1 report: AI help for a child's genome, without the AI seeing the genome

Team: Acadine Intelligence. Track 1 (variant prediction), one model. Code: https://github.com/acadine-intelligence/mva-transparent-prioritizer (private during the hackathon, public afterwards as a privacy-scanned snapshot). This report contains no patient values.

## The problem we worked on

Families, foundations and small clinical teams want modern AI to help with an undiagnosed child's genome. They mostly cannot use it. A genome and a phenotype record cannot be pasted into a hosted model, and most teams have no secure compute of their own. So AI help stops at the door of the data.

We asked a narrower question than "can AI find the variant". We asked: can AI agents do almost all of the engineering, research and review for a rare-disease analysis while never seeing a single patient value, and can that claim be tested instead of trusted?

## What we built

**1. A sealed runtime with a counts-only door.** The genome, the phenotype document and every derived file stayed on one encrypted, offline machine. AI agents wrote and reviewed the code against synthetic fixtures. Code reached the sealed machine as a frozen, hash-checked commit. Only counts, hashes and exit codes came back out. Error output from private steps was thrown away, because error messages are a leak route. When we needed an answer about the real case during review, we wrote a small program that returned only booleans and ranks. For example: "is the top row a pair, and do both alleles sit in a gene we declared before looking at the case?"

**2. Established engines, kept honest.** We did not write a new ranking engine. Exomiser 15.1 runs separate coding and noncoding (Genomiser) lanes on a pinned GRCh38 reference, with VEP and ClinVar annotation. Source scores and inheritance annotations stay as the engines report them. We do not merge them into an invented clinical probability. A stricter noncoding threshold run (ReMM 0.963) shows which candidates depend on a borderline call. A full-evaluation replay makes filter rejections inspectable instead of silently dropped. Two 2025 studies later supported the same parameter direction.[1][2]

**3. A selection rule written before the evidence was read.** The step from evidence to a ten-row file is where human bias enters. We wrote the rule down first, tied every sentence to a test, and had it reviewed independently seven times against exact commits before it touched case data. Nine syndrome genes were declared from public literature before any case inspection. The rule fixes tiers, pairing, row order, the confidence ladder and the ten-row cap. A human may change a row only with a written reason.

**4. A pre-registered search for alleles that standard filters miss.** The literature on this syndrome includes families first reported with only one damaging allele, later solved by a second allele that standard filters remove, for example a regulatory change tens of kilobases upstream of the gene. We built a catalog of 27 published disease alleles, each with a GRCh38 position checked base for base against Ensembl, and froze it by SHA-256 before any lookup. Each entry was matched against the candidate pool and looked up directly in the original VCF. The rule promised that zero matches would leave the file byte-identical, and tests enforced it.

**5. We attacked our own privacy boundary.** A privacy claim that has only been checked by its authors is a hope. We wrote 21 synthetic tests: attacks plus controls against the real entry points. **12 attacks got through.** They included:

- error messages that echo a rejected value or a file path;
- values hidden by base64, hex, reversal or line splitting;
- a hash in a public summary that can be reversed when only a few values are possible;
- counts that reveal whether a known candidate is present;
- protected text in file names;
- identifier shapes and gene aliases the scanners did not recognise;
- scanners that checked working files instead of the bytes staged for commit.

The suite records each gap as a known failure. The four gaps that affect publication are fixed before the repository goes public.

**6. We audited the scorer.** We vendored the official evaluator, pinned its bytes, and scored 1,843,650 synthetic submission layouts. In 48,608 of them, adding a correct answer lowered the score, because a full match is scored ahead of a higher-ranked partial match. In 75 percent of those cases the cause was a speculative pair that named one right allele and one wrong one. That shaped our file: the leading pair sits in row 1, every confidence value is distinct, and no single allele sits above a pair that contains it.

## The result

The file has ten rows: two compound-heterozygous pairs and eight single alleles. Row 1 is a pair whose two alleles lie in the same gene, one of the nine declared before case inspection. Both alleles passed every filter in both lanes. No other alleles in those nine genes passed any lane. The data has no parents and no read-backed phase, so the pair is a ranked hypothesis that the alleles sit on different copies, not a proven one. The single-allele rows below it exist for that reason.

The published-allele search matched 0 of 27. The file is therefore byte-identical to the output of the original rule. That is a real negative: it rules out the documented "missing second allele" route for this child. It does not rule out new alleles, structural variants or variants missing from the supplied calls.

## Why this matters beyond one child

- **It lets AI help where it is currently shut out.** AI agents, under human direction, wrote the code, did the literature research and ran the adversarial reviews. None of them saw the data. A foundation or a hospital team can use the same pattern with any engine.
- **It turns "we kept the data private" into something a reviewer can check.** The leak suite is the reusable part. Any team that puts agents near sensitive data can run the same attack classes against its own boundary. Ours failed 12 times on first contact, which is the point.
- **Pre-registration makes N-of-1 work auditable.** A family or a reviewer can read the rule, read the file, and check that one produced the other.
- **Scorer audits help organisers.** The inversion we measured is general. Future challenge designers can run the same brute-force audit before launch.

## Reuse

Everything public is in the repository: the sealed-run scripts, the selection rule and its tests, the catalog lookup, the leak suite, and the scorer audit scripts. Synthetic fixtures replace all patient data. Patient files and outputs will be deleted under the challenge's 30-day rule.

## Limits

This is research software. It makes no diagnosis or treatment claim. Single-sample data cannot prove phase or inheritance. The supplied calls have no structural-variant fields. The confidence ladder orders rows; it is not a probability of causation. Independent software reviews checked the code, not the biology. No clinician reviewed the rows before upload.

## AI and software disclosure

AI agents did software development, public-literature research, drafting and code review, through subscription plans only: OpenAI ChatGPT Pro (Codex CLI; model-training setting: [TO CONFIRM]); Anthropic Claude Max (Claude Code; model-training setting: [TO CONFIRM]); Z.ai GLM Coding Plan (GLM 5.3); Moonshot Kimi membership (Kimi Code, Kimi K3); Nous Portal subscription. The provider list comes from the session ledger of every agent session that touched this repository. No protected record was sent to any model. One public-literature research brief to an OpenAI model contained one aggregate sentence derived from the case: that the known syndrome genes showed no clear biallelic coding result. We disclose it here. All case-level computation ran as deterministic programs on the encrypted machine.

Detailed methods: `docs/21-public-methods-packet.md` (pipeline), `docs/22-candidate-selection-rule.md` (selection rule and scorer audit), `docs/24-catalog-amendment.md` (published-allele search), `docs/25-leak-suite-spec.md` (leak suite; on branch `mva-leak-suite` until the public release).

## Sources

[1] https://link.springer.com/article/10.1186/s13073-025-01546-1
[2] https://pmc.ncbi.nlm.nih.gov/articles/PMC12452281/
