# MVA Transparent Prioritizer

An auditable, local research workflow for rare-disease variant prioritization, built by Acadine Intelligence for Track 1 of the **Rare Disease, Real Kid: MVA Hackathon 2026**.

The project separates AI-assisted software development from computation on controlled patient data. AI agents helped write and review software using synthetic fixtures. Deterministic programs ran the patient analysis on an encrypted, offline machine. The submission report records the privacy limitations and known disclosures.

Research software only. This project does not provide diagnosis or treatment advice.

## Read the submission

The submission work is on the [`mva-closeout` branch](https://github.com/acadine-intelligence/mva-transparent-prioritizer/tree/mva-closeout). Earlier branches contain intermediate implementation stages. Start with these documents on `mva-closeout`:

| Document | Contents |
| --- | --- |
| [Track 1 report](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/26-track1-report.md) | Submission overview, methods, privacy disclosures and AI assistance |
| [Recorded result](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/28-track1-result.md) | Scorer output from the single reviewed upload on 24 October 2026 |
| [Detailed methods](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/21-public-methods-packet.md) | Analysis pipeline, references and sensitivity checks; some status sections reflect earlier preparation stages |
| [Candidate-selection rule](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/22-candidate-selection-rule.md) | Selection logic, review history and scorer audit |
| [Published-allele search](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/24-catalog-amendment.md) | Literature catalog lookup and its predeclared effect on selection |

## Approach

The workflow uses established analysis tools rather than a new biological scoring model. Exomiser supplies separate coding and noncoding evidence lanes, with VEP and ClinVar annotation on GRCh38. A stricter noncoding sensitivity run checks how threshold changes affect inheritance compatibility.

The selection layer preserves source scores and applies a documented rule to produce the ranked submission. The rule is a partial pre-registration: earlier results had already constrained the shortlist. Its confidence values order candidates and do not represent calibrated probabilities of causation.

The software also includes synthetic tests for reproducibility and path confinement. A separate [privacy attack suite](https://github.com/acadine-intelligence/mva-transparent-prioritizer/tree/mva-leak-suite) tests ways that protected values can escape through reports or error messages. The submission report documents successful attacks and outstanding publication work. These checks do not certify the repository or its Git history as safe to publish.

## Recorded outcome

The project recorded one reviewed Track 1 upload on 24 October 2026. The scorer returned **100.0/100 rank points**, **F-max 1.000** and a **full match at rank 1**. See the [result note](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/28-track1-result.md) for the recorded output and interpretation.

This is a result on one case. It does not establish a general diagnostic success rate or clinical validity. Single-sample data cannot prove inheritance or phase, and the supplied variant calls limit which variant classes the workflow can assess.

## Run the synthetic checks

From a checkout of this repository, use Python 3 and Bash:

```bash
python3 -m mva_prioritizer.cli --help
bash scripts/verify.sh
```

These commands exercise the tracked software using synthetic fixtures. They do not download patient data or reproduce the controlled case analysis. Some private run-preparation scripts and the large reference assets are outside the tracked tree, so this repository alone is not a complete replay package for the submitted analysis.

## Data and AI assistance

Controlled patient inputs and variant-level results are excluded from this README. Access to challenge data remains subject to the organizers' terms. Do not put patient records in GitHub issues or send them to hosted models.

The [submission report](https://github.com/acadine-intelligence/mva-transparent-prioritizer/blob/mva-closeout/docs/26-track1-report.md#ai-and-software-disclosure) lists the AI services used and describes known case-derived disclosures. Independent software reviews assessed the code; they do not substitute for specialist biological review.

## Repository structure

- `mva_prioritizer/` contains the Python CLI and workflow modules.
- `tests/` contains automated tests and synthetic fixtures.
- `scripts/` contains verification and analysis utilities, with coverage varying by branch.
- `docs/` contains the design and methods records.

[`product.json`](product.json) records the project's scope and acceptance criteria. Contributors should read [`AGENTS.md`](AGENTS.md) before changing the software. Third-party tools and reference resources retain their own licensing and access conditions.
