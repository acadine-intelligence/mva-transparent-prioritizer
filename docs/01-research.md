# Research: MVA Transparent Prioritizer

## User workflow evidence

The official Track 1 interface accepts up to ten candidate rows. A row can describe one variant or a proposed pair. The evaluation sorts rows by submitted confidence and scores ranked matches.[3][4] The controlled dataset provides a phenotype document and a GRCh38 VCF, which makes a VCF-first workflow the smallest informative route.[2]

Local content-free inspection found one VCF sample, GRCh38 contigs with decoys, genotype depth and quality fields, and explicit HPO identifiers in the phenotype document. The VCF header did not advertise structural-variant fields or precomputed consequence annotations. These facts define the first pipeline stage without exposing a patient value.

## Existing alternatives

Exomiser combines phenotype, inheritance, population frequency, pathogenicity, and model-organism evidence. It is the preferred primary prioritizer because it runs offline and has a documented local analysis model.[5]

bcftools provides normalization, filtering, statistics, and reproducible VCF transformations.[6] Ensembl VEP and ClinVar provide independent consequence and clinical evidence layers.[7][8]

A manual spreadsheet remains useful for final specialist review. It is a poor source of execution provenance and replay evidence. Hosted models can help with public literature and public code. They cannot receive the protected phenotype, HPO set, variants, coordinates, sample identity, private result rows, or private logs under the current privacy decision.

## Gap worth solving

The missing layer is a small offline wrapper that proves input and reference identity, confines private paths, runs pinned tools, preserves independent evidence lanes, and renders each research candidate with visible reasons. The wrapper must also produce a public projection that cannot contain row-level protected data.

## Constraints and falsifiers

- The protected runtime is an 8 GB Apple Silicon M1. Memory limits shape tool and thread settings.
- The encrypted workspace has about 500 GB logical capacity. Public reference assets need version, hash, source, and storage receipts.
- The private run must make no network request. Reference downloads happen in a separate public-data stage.
- A single-sample VCF limits inheritance claims. Compound-heterozygous pairs remain unphased unless the VCF proves phase.
- Absence of structural calls in this VCF cannot establish absence of a structural variant.
- The product must delete controlled source data and derived datasets under the challenge retention terms.[1]
- A working ranker can still be scientifically wrong. Independent review and specialist judgment remain required.

The thesis fails if path isolation cannot be proven, reference identity cannot be matched, the transparent wrapper adds no review value over direct Exomiser output, or synthetic known-bad tests can pass after provenance or score tampering.

## Sources

[1] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/blob/main/tabs/rules.py — MVA Hackathon rules
[2] https://huggingface.co/datasets/SageBio/mva-hackathon-2026-data/blob/main/README.md — MVA Hackathon dataset card
[3] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/blob/main/tabs/submit_track1.py — MVA Hackathon Track 1 submission
[4] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/blob/main/evaluation.py — MVA Hackathon Track 1 evaluation
[5] https://exomiser.readthedocs.io/en/stable — Exomiser stable documentation
[6] https://samtools.github.io/bcftools/bcftools.html — bcftools manual
[7] https://www.ensembl.org/info/docs/tools/vep/script/vep_cache.html — Ensembl VEP cache documentation
[8] https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38 — NCBI ClinVar GRCh38 VCF directory
