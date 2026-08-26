# Product brief: MVA Transparent Prioritizer

## Primary user

Jonathan is the primary research operator. A qualified clinical or research specialist is the required reviewer before any finding can influence care.

## Painful job

The operator must turn a controlled phenotype document and a whole-genome VCF into a short, reviewable candidate list. Every row needs a visible reason, source provenance, input identity, tool version, and stated limit. The challenge clock creates urgency, while the child's privacy and the scientific uncertainty require restraint.

## Existing workaround and evidence

The current workflow combines command-line annotation tools, manual spreadsheets, and literature review. These parts can rank variants, yet they do not provide one reproducible receipt or a strict boundary between protected case data and public methods. The supplied challenge artifacts were inspected through content-free metadata on 2026-08-26. The protected files are available in an encrypted local workspace. The public challenge requires a ranked Track 1 result and a methods report.[1][2][3]

## Concrete output

The product creates a private candidate dossier and a machine-readable run receipt. It also creates a separate public-safe methods packet based on synthetic fixtures and non-identifying aggregate learnings.

## Value hypothesis and success metric

The operator can inspect why each candidate survived, rerun the same configuration, and hand a bounded dossier to a specialist. The first success metric is one byte-reproducible synthetic run plus one private run whose top candidate rows all carry provenance, quality evidence, phenotype evidence, inheritance notes, and explicit uncertainty.

## Kill criteria

Stop the run if reference identity remains unresolved, any protected value reaches stdout or the public repository, an input or output path escapes the private root, or a required reference receipt fails. If coding and targeted non-coding analysis yield no credible candidate, stop refining the same score. Record the analytical gap and decide whether read-level or structural-variant work is justified.

## Sources

[1] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/blob/main/tabs/rules.py — MVA Hackathon rules
[2] https://huggingface.co/datasets/SageBio/mva-hackathon-2026-data/blob/main/README.md — MVA Hackathon dataset card
[3] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/blob/main/tabs/submit_track1.py — MVA Hackathon Track 1 submission
