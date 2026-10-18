# Public methods packet: MVA Transparent Prioritizer

Release candidate, 10 September 2026. Aligned to the official Track 1 methods workbook.[1] Not submitted. Specialist review, account-specific AI disclosure and publication approval remain open. No candidate identities, case-level values or patient-derived rows appear in this document.

## Team and track

Team name: Acadine Intelligence (confirmed by Jonathan Bylos, 26 September 2026). Submitter identity for public use: the Hugging Face account that files the submission, not yet created. Track 1 (variant prediction). One model. Model number: pending; the official workbook assigns numbers at submission time (one per model, up to six).[1]

## Abstract

We built a local research workflow that keeps coding and noncoding evidence in separate, reviewable lanes for rare-disease candidate review. The workflow verifies source identity and reference compatibility before annotation, and it preserves source scores and inheritance annotations instead of producing a combined clinical probability. A sensitivity run tightens the noncoding ReMM threshold and recomputes inheritance compatibility, because removing one allele can change the interpretation of a surviving candidate. A diagnostic replay then re-runs the pinned analysis engine in its full-evaluation mode on a bounded, byte-preserved subset of the existing input, so that filter rejections and gene-assignment differences become inspectable instead of disappearing from the saved pass-only output. Positive controls from the frozen passing-variant tables are carried through the replay and must be preserved exactly. Synthetic tests, hash-bound independent software reviews and a separate recompute-and-compare verifier check the preparation and replay mechanics. The current evidence packet supports specialist review. A final submission shortlist is pending. We have not measured recovery against the challenge answer, and we make no clinical claim.

## Pipeline and prioritization logic

Input identity checks and reference compatibility come first. A project-approved contig mapping, recorded in the repository's reference bundle configuration, is applied to the supported assembly contigs, and the excluded decoy contig class is recorded. Normalization uses a pinned GRCh38 reference. Annotation uses VEP and ClinVar. Coding and noncoding Exomiser runs remain separate so a reviewer can inspect each lane's evidence.

The noncoding route uses the Genomiser configuration, including available SpliceAI scores above 0.1 or ReMM scores above 0.914 on their respective noncoding score branches. Frequency and inheritance conditions still apply. These thresholds define the tested workflow; they are not calibrated causal probabilities.

The sensitivity run raises the strict ReMM cutoff to greater than 0.963 within the reviewed noncoding filter branches and re-evaluates inheritance with Exomiser rather than deleting rows from the final ranked table. This matters when a removed allele supplied a possible compound-heterozygous partner. The frozen baseline evidence remains unchanged.

The review dossier joins evidence by gene symbol with cross-lane Entrez-ID checks. Variant joins use the complete contig, position, reference and alternate allele identity. Lane-specific rows and rankings are preserved.

## Rejection-evidence replay

Saved pass-only output cannot explain a rejected variant. The pinned pass-only runner removes failed variants from gene objects before writing.[3] Its sparse filter runner evaluates a later filter only when the variant passed earlier filters.[4]
The diagnostic replay selects the engine's full-evaluation mode, whose runner applies every ordinary variant filter across the variant list and retains the failures.[2][5]

The replay selects complete VCF records overlapping predeclared public-literature gene regions, plus every allele represented in either frozen passing-variant table as a positive control. Selection preserves multiallelic records and input order; the stored genotype determines which alternate alleles were called. Each lane copies its original analysis configuration and changes only the input path, the analysis mode and the output settings. Output includes JSONL and variant TSV; the engine's JSON writer applies an additional contributing-variants branch when that option is enabled, so the replay disables it.[6]

The report keeps the engine's variant statuses separate from the input caller's FILTER field. A missing output allele is labelled unobserved. An allele assigned to a gene outside its overlapping public region is recorded as a mapping difference. Neither is silently converted into a rejection reason. Control preservation is measured by identical allele key, gene symbol, Entrez identifier and inheritance mode.

This is a partial-input diagnostic. It does not reconstruct a complete genome-wide rejection history and does not establish complete gene coverage.

## Data sources and tools

The protected inputs are the organizer-provided phenotype document and variant call file.[7] All case-level computation ran in an encrypted local workspace. This packet does not include those inputs or their row-level derivatives.

The pinned reference bundle records Ensembl release 116 and the associated GRCh38 reference. Annotation tools include VEP 116.1 and bcftools 1.24. Exomiser 15.1.0 supplies phenotype and inheritance analysis. The noncoding work uses the Exomiser hg38 data release 2602 and ReMM v0.4 GRCh38 resources. ClinVar and other bundled assets have exact acquisition identities in the project's manifests. Public literature context was frozen before any case inspection, and hosted reviewers received public code, public references and synthetic fixtures only.

SpliceAI licensing requires separate attention before redistribution or reuse beyond the approved workflow. Access to an annotation was not treated as permission to redistribute model weights.

## External validation of parameter choices

Two 2025 studies of Exomiser and Genomiser on real patient genomes support the direction of the parameter choices in this workflow. A Genome Medicine optimization study on Undiagnosed Diseases Network probands reported that parameter optimization raised the share of coding diagnostic variants ranked in the top ten from 49.7 percent to 85.5 percent on genome data, and from 67.3 percent to 88.2 percent on exome data, while the Genomiser noncoding top-ten share improved from 15.0 percent to 40.0 percent.[8] A separate 985-patient cohort study found that Genomiser's default behaviour placed high-scoring noncoding variants above true coding causes, and that applying a ReMM cutoff of 0.963 raised Genomiser's top-15 sensitivity to 92.54 percent from 89.55 percent.[9] This workflow's strict 0.963 ReMM sensitivity run was designed from local threshold testing before those publications appeared; the agreement is recorded as external support, not as a tuning source. That optimization study also recommends using Genomiser as a complementary noncoding tool alongside Exomiser rather than as a replacement, which matches how this workflow's lanes are arranged.[8]

## Manual review and curation status

The submission file was generated by program from the pre-registered selection rule (`docs/22-candidate-selection-rule.md`) and its amendment (`docs/24-catalog-amendment.md`), on 12 October 2026, on the encrypted host. It has ten rows: two compound-heterozygous pair rows and eight single-allele rows, with a fixed descending EPCR ladder. Program-generated ordering is the default. Any human change made before upload is listed below with its reason; a change without a recorded reason is not applied.

Manual changes: none recorded at the time of writing.

Independent software reviews checked joins, evidence preservation, replay mechanics, the selection runner and the catalog lookup at exact commits. They do not substitute for biological assessment.

## Public and proprietary data

The approach used publicly available reference data and the organizer-provided challenge inputs. No other proprietary data source was used. Public data used: Ensembl/VEP reference and annotation cache, ClinVar, Exomiser bundled data releases, ReMM and SpliceAI score resources, and peer-reviewed MVA literature identified before case inspection.

## Compound-heterozygous candidates

The inheritance analysis supports compound-heterozygous compatibility, and the submission validator supports a paired-variant row. An inheritance annotation alone does not establish that two alleles are in trans. The top row is a pair whose two alleles lie in the same gene, one of the nine genes declared from public MVA literature on 7 September 2026, before case inspection. Both alleles passed every filter in both evidence lanes. The single-sample input carries no read-backed phase linking the two loci and no parental data, so the pair is a ranked hypothesis of trans configuration, not established phase. The single-allele rows beneath it exist because the pair is unproven.

## Pre-registered search for published disease alleles

Standard filters can remove a known disease allele that sits outside coding sequence or carries a misleading annotation. The documented example is a regulatory allele about 44 kb upstream of a known MVA gene that explained families first reported with only one detectable allele. Before any lookup, we froze a catalog of 27 published MVA and related alleles (high or medium confidence, each GRCh38 tuple checked base for base against the Ensembl reference) by SHA-256 in `docs/24-catalog-amendment.md`. Each entry was matched against the candidate pool and looked up directly in the original VCF, with a match requiring identical position, reference and alternate allele and a genotype carrying that allele.

Result: 0 of 27 matched. As the amendment requires for zero matches, the submission file is byte-identical to the file the original rule produces. Zero matches means none of these 27 published alleles is present as a called variant in the supplied VCF. It does not exclude the mechanism, novel alleles, structural variants, or alleles absent from the supplied calls.

## Secondary findings

No secondary finding has been selected for submission. Any final secondary entry needs a reviewed rationale. This packet does not certify an incidental finding or recommend its clinical return.

## Run time and cost

A consolidated runtime and cost estimate has not been verified for the complete workflow. Individual run timings are available from execution receipts and will be included only if the release review approves those identifiers for publication.

## Verification and privacy architecture

Synthetic acceptance tests and mutation-sensitive guards cover the tracked implementation. Runtime preparation, audit and replay scripts carry separate hash-bound independent reviews because they reside outside the tracked implementation. Each protected execution runs on the encrypted host with a pinned interpreter, pinned inputs, a deny-network sandbox and write confinement, and a separate verify pass recomputes the outputs from pinned sources and compares hashes without rerunning the engine.

Protected records, detailed logs and case-level reports remain on the encrypted host under the challenge deletion policy. Only fixed aggregate schemas and hashes leave it. This packet passes the project's public-tree privacy scan, a scripted check that runs on every verification pass; the scan's result is recorded in the verification evidence file.

## AI and software disclosure

AI assistance supported software development, public-source research and synthetic code review. The private evidence packets were generated by deterministic programs on the encrypted analysis host. Software reviewers assessed preparation mechanics; they did not perform clinical interpretation of protected rows.

Providers, from the session ledger of every agent session that touched this repository, all through subscription plans rather than per-call API keys: OpenAI ChatGPT Pro (Codex CLI; model-training setting: [TO CONFIRM]); Anthropic Claude Max (Claude Code; model-training setting: [TO CONFIRM]); Z.ai GLM Coding Plan (GLM 5.3); Moonshot Kimi membership (Kimi Code, Kimi K3); Nous Portal subscription. A pay-per-call decision-model API (TypeSafe Jev, standard account: TypeSafe states Jev is not trained on customer requests; no zero-data-retention agreement) scored claim-provenance checks and a semantic leak scan; one scanned file then carried case-derived gene symbols, later removed (see `docs/22`, review of `1783250`). No genome, phenotype document or variant-level record was sent to any model. One public-literature research brief sent to an OpenAI model contained a single aggregate statement derived from the case (that the known MVA genes showed no clear biallelic coding result); it is disclosed here for completeness.

## Current results and limits

The preparation receipt records 34 detailed first-pass gene entries with the complete 500-gene source set retained. The stricter run retained 263 of 365 variants. Twelve variants passed the numerical conditions but lost inheritance compatibility. The dossier flags 19 genes for inheritance review. These counts are members of the fixed preparation aggregate schema that the reviewed preparation receipt publishes; an independent fact check verified every figure against that receipt before the earlier methods draft was released for internal review. The diagnostic replay produced a verified restricted aggregate report; its case-specific counts remain internal until the release review approves disclosure.

These figures describe the evidence set and sensitivity effects. They do not measure diagnostic accuracy, disease causality or agreement with the hidden challenge answer. Structural-variant coverage and single-sample inheritance limits remain explicit. The workflow has not demonstrated a treatment benefit.

## Remaining steps before any release

Operator review of the ten submitted rows, the two account training settings above, and explicit approval of the upload. Before the repository becomes public after the hackathon: close the four publication-blocking gaps found by the leak suite (`docs/25-leak-suite-spec.md` on branch `mva-leak-suite`) and publish one scanned snapshot without historical commits. Controlled data deletion and its confirmation follow the organizers' 30-day rule. This packet creates no permission to upload data, contact the organizers or publish the repository.

## Sources

[1] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/resolve/1c761cc23d90aebe6a011fd5b0b99517df42408c/static/templates/methods_description_form.xlsx
[2] https://raw.githubusercontent.com/exomiser/Exomiser/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/analysis/SimpleAnalysisRunner.java
[3] https://raw.githubusercontent.com/exomiser/Exomiser/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/analysis/PassOnlyAnalysisRunner.java
[4] https://raw.githubusercontent.com/exomiser/Exomiser/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/filters/SparseVariantFilterRunner.java
[5] https://raw.githubusercontent.com/exomiser/Exomiser/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/filters/SimpleVariantFilterRunner.java
[6] https://raw.githubusercontent.com/exomiser/Exomiser/98f4e0b6f2f3f5bf790a9f955808c98968559996/exomiser-core/src/main/java/org/monarchinitiative/exomiser/core/writers/JsonResultsWriter.java
[7] https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/resolve/1c761cc23d90aebe6a011fd5b0b99517df42408c/tabs/rules.py
[8] https://link.springer.com/article/10.1186/s13073-025-01546-1
[9] https://pmc.ncbi.nlm.nih.gov/articles/PMC12452281/
