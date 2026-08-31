# Run 3 noncoding benchmark proposal

Decision recorded: 2026-08-31

State: public research proposal. This file authorizes no asset download, private execution, publication, upload, or challenge submission.

Privacy: this work used public sources, synthetic test design, and public project configuration. No protected row, HPO identifier, variant coordinate, sample metadata, private output, or private log left the encrypted M1 workspace.

## Decision

Prepare a separate Genomiser evidence lane based on the official Exomiser 15.1.0 whole-genome preset. Keep the frozen coding lane unchanged. Compare both lanes before any challenge-row ordering.

The official preset combines REVEL, MVP, AlphaMissense, ReMM, and the Exomiser `SPLICE_AI` source. It applies `target: NON_CODING`, which filters noncoding variants while passing coding variants through that pathogenicity step.[1][2][4]

A 2025 benchmark found that tuned Genomiser increased noncoding top-10 recovery from 15.0% to 40.0%.[10] A separate study of 778 previously negative genome cases reported 20 deep intronic candidates found by its optimized workflow.[11] These cohort results support a complementary test lane. They do not predict the result for this case.

## Proposed configuration

Start from the exact Exomiser 15.1.0 genome preset at release commit `98f4e0b6f2f3f5bf790a9f955808c98968559996`.[1][2]

The candidate configuration excerpt is:

```yaml
analysisMode: PASS_ONLY
pathogenicitySources: [REVEL, MVP, ALPHA_MISSENSE, REMM, SPLICE_AI]
steps:
  - hiPhivePrioritiser: {}
  - priorityScoreFilter: {priorityType: HIPHIVE_PRIORITY, minPriorityScore: 0.501}
  - geneBlacklistFilter: {}
  - failedVariantFilter: {}
  - alleleBalanceFilter: {}
  - regulatoryFeatureFilter: {}
  - frequencyFilter: {maxFrequency: 2.0}
  - pathogenicityFilter: {keepNonPathogenic: false, target: NON_CODING}
  - inheritanceFilter: {}
  - omimPrioritiser: {}
```

This excerpt omits the preset's `inheritanceModes` and `frequencySources` maps. Do not copy it as a complete configuration. The implementation must start from the complete pinned preset and preserve every official field, value, and order, including those maps.[2]

Exomiser 15.1.0 uses these default noncoding thresholds: CADD scaled score at least 15.0, SpliceAI score above 0.1, or ReMM score above 0.914. A variant can pass when one available score exceeds its threshold.[4]

The benchmark must test these defaults first. The ReMM value 0.963 from the Hong Kong study remains a separate comparison value. It cannot replace the official default without evidence from the synthetic benchmark and an explicit decision.[4][11]

Keep the existing low-allele-fraction review outside this preset. The preset includes `alleleBalanceFilter`, while the project requires a visible lane for calls that a strict germline balance rule could remove.[2]

## Asset plan

| Asset | Current proposal | Verification before use |
|---|---|---|
| Exomiser CLI | Keep pinned version 15.1.0. | Match the existing bundle receipt and executable digest. |
| Exomiser genome data | Keep pinned release 2602 for hg38. | Prove with synthetic variants that the `SPLICE_AI` source is present, emits a score, and affects the intended filter. Stop if any check fails. |
| Exomiser phenotype data | Keep pinned release 2602. | Match the existing receipt. Do not update phenotype data inside this comparison. |
| ReMM | Later acquire ReMM v0.4 for GRCh38 plus its tabix index. | Verify the public MD5 values, compute local SHA-256 values, verify tabix access, then freeze a new asset receipt. |
| Direct SpliceAI package or models | Do not acquire in this proposal. | Reconsider only if the Exomiser data fails the synthetic `SPLICE_AI` checks. |

The Exomiser preset names `SPLICE_AI`, while its application properties expose paths for ReMM and CADD and no path for a direct SpliceAI model.[2][3] This suggests that the pinned Exomiser data is the intended score source. The synthetic benchmark must prove that inference before private execution.

ReMM v0.4 is the current official release. The GRCh38 data file is 15,967,302,704 bytes, or 14.870709 GiB. Its index is 2,755,625 bytes, or 2.627969 MiB.[6][7]

The public metadata records these MD5 values:[7]

- `ReMM.v0.4.hg38.tsv.gz`: `2f8c8fcc75ea29f6798621d0446fe194`
- `ReMM.v0.4.hg38.tsv.gz.tbi`: `c477b123abbe72c4aa66bf3abc18d9ab`

A later acquisition pass must also calculate SHA-256 locally. The project must use the local SHA-256 values in the reference receipt.

Exomiser requires ReMM for its genome preset and stops when the source is selected without configured data.[3][5] The implementation must keep that failure visible and terminal for the attempted run.

## License decision

ReMM data is published as CC0 in the Zenodo record. The ReMM workflow repository uses the MIT license.[7][9]

The SpliceAI license needs care. Exomiser 15.1.0 documentation says GPLv3 for the source and CC BY NC 4.0 for its trained models.[4] The current upstream SpliceAI license says PolyForm Strict 1.0.0 for source code and CC BY NC 4.0 for models used in academic and noncommercial work.[8]

These sources disagree on the source-code license. Use the current upstream license for any new direct acquisition until a review resolves the history. Do not redistribute SpliceAI code, models, or extracted score assets through this repository under the present proposal.

The proposed lane uses Exomiser's bundled score source if synthetic tests confirm it. Before any public release, record the Exomiser bundle's provenance and confirm that the planned public artifact contains no restricted model or score data.

## Synthetic benchmark contract

Build this benchmark before inspecting any new private output. Use invented HPO terms, genes, alleles, genotypes, coordinates, and expected outcomes.

1. A coding single-nucleotide variant stays visible in the unchanged coding lane.
2. A deep intronic variant with a synthetic SpliceAI score above 0.1 appears in the noncoding lane.
3. A regulatory variant with a synthetic ReMM score above 0.914 appears in the noncoding lane.
4. A high-ReMM benign decoy cannot erase the injected expected candidates from the evidence report.
5. An exonic splice candidate remains visible for review when predictors disagree. The splice benchmark found lower concordance for exonic variants than intronic variants.[12]
6. A coding plus noncoding compound-heterozygous pair stays linked as one proposed pair with phase marked unknown.
7. A low-allele-fraction injected candidate remains visible in the separate review lane when the preset balance filter removes it.
8. A missing ReMM file or index stops before analysis.
9. An assembly or transcript-model mismatch stops before candidate generation.
10. A changed asset, config, or receipt digest stops before protected input is read.
11. A missing `SPLICE_AI` score stays explicit. The system must never convert absence into zero.
12. Threshold tests cover SpliceAI values below, equal to, and above 0.1. They also cover ReMM values below, equal to, and above 0.914. Exomiser documents strict greater-than comparisons for both scores.[4]
13. Two clean synthetic replays produce byte-identical evidence files and receipts.
14. A seeded public-output canary remains absent from every public projection.

The benchmark report must show the reason each candidate passed, the source score, the threshold, the evidence lane, and the configuration digest. It must label all outputs as research evidence. It must calculate no clinical probability.

## Acceptance checks

A run 3 implementation can request private execution only after all checks pass:

- The frozen coding run remains byte-identical and read-only.
- Every known-bad synthetic case fails at its named step.
- The Exomiser `SPLICE_AI` source passes presence, score, and filtering tests against synthetic inputs.
- ReMM data and index match the pinned receipt and support tabix queries on synthetic positions.
- The noncoding lane keeps full evidence rows and applies no hidden top-10 cutoff.
- The merge comparison explains every rank movement and preserves candidates unique to either lane.
- Content-free stdout contains no synthetic canary and no private field name reserved by the project.
- A separate synthetic scorer reproduces the official Track 1 pair, rank-point, duplicate, EPCR-tie, and F-max behavior already recorded in `docs/10-track-1-scoring-and-next-evidence-lane.md`.
- An independent reviewer checks the exact config, acquisition receipt, benchmark code, and benchmark output.
- The operator records a new approval before any private execution.

## Resource limit

Exomiser documents 8 GB RAM as the minimum for a genome analysis and recommends 16 GB for comfortable use.[5] The protected machine has an 8 GB limit in `product.json`. Keep `PASS_ONLY`, one worker, the existing heap limit, peak-memory capture, and explicit interruption handling. A memory failure must end the attempted run without a retry under the same configuration.

## Stop point

This proposal stops before asset download and implementation. The next bounded action is a public-only implementation ticket for the synthetic benchmark and acquisition manifest. That ticket must leave frozen private runs untouched.

## Sources

[1] https://github.com/exomiser/Exomiser/releases/tag/15.1.0 : Exomiser 15.1.0 release
[2] https://raw.githubusercontent.com/exomiser/Exomiser/15.1.0/exomiser-cli/src/main/resources/examples/preset-genome-analysis.yml : Official Exomiser 15.1.0 genome preset
[3] https://raw.githubusercontent.com/exomiser/Exomiser/15.1.0/exomiser-cli/src/main/resources/application.properties : Exomiser 15.1.0 application properties
[4] https://exomiser.readthedocs.io/en/15.1.0/_sources/advanced_analysis.rst.txt : Exomiser 15.1.0 advanced analysis documentation
[5] https://exomiser.readthedocs.io/en/15.1.0/_sources/installation.rst.txt : Exomiser 15.1.0 installation documentation
[6] https://remm.bihealth.org/download : Official ReMM downloads
[7] https://zenodo.org/api/records/6576087 : ReMM v0.4 Zenodo metadata
[8] https://raw.githubusercontent.com/Illumina/SpliceAI/master/LICENSE : Current upstream SpliceAI license
[9] https://raw.githubusercontent.com/kircherlab/ReMM/master/LICENSE : ReMM workflow license
[10] https://pmc.ncbi.nlm.nih.gov/articles/PMC12539062 : Exomiser and Genomiser optimization study
[11] https://pmc.ncbi.nlm.nih.gov/articles/PMC12452281 : Genomiser clinical optimization study
[12] https://pmc.ncbi.nlm.nih.gov/articles/PMC10187268 : Splice predictor benchmark
