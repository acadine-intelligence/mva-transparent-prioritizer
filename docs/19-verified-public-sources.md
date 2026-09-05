# Verified public sources: Exomiser optimization and benchmarking

Date verified: 2026-09-05, by fetching both pages in full and quoting from the retrieved text. This closes the citation-verification item left open in the loop-9 pass. Verified facts only; no private values.

## Source 1: Cooperstein et al., Genome Medicine 2025

- Citation: Cooperstein IB, Marwaha S, Ward A, Kobren SN, Carter JN, Wheeler MT, Marth GT. "An optimized variant prioritization process for rare disease diagnostics: recommendations for Exomiser and Genomiser." Genome Medicine 2025 Oct 21;17:127. doi:10.1186/s13073-025-01546-1. PMCID PMC12539062, PMID 41121346. Received 2025-04-16, accepted 2025-09-03. CC BY-NC-ND 4.0.
- Cohort: 386 diagnosed UDN probands, coding and noncoding diagnostic variants.
- Verified headline result (from the abstract): parameter optimization raised top-10 ranking of coding diagnostic variants in GS from 49.7% to 85.5%, in ES from 67.3% to 88.2%; for noncoding variants prioritized with Genomiser, top-10 improved from 15.0% to 40.0%.
- Verified statements relevant to the dual-lane and sensitivity work:
  - "Genomiser has been shown to be effective in identifying compound heterozygous diagnoses in cases where one diagnostic variant is regulatory, and the other is coding or splice-altering."
  - The GS Genomiser cohort is defined as "GS cases with diagnostic variants in noncoding regions or compound heterozygous diagnoses involving noncoding variant(s)". Compound diagnoses of one SNV/indel plus one structural variant were excluded.
  - Inheritance-mode-stratified evaluation "observed no strong differences in performance between inheritance modes in the GS Exomiser cohort".
  - Accuracy of family/variant data matters: reanalyzed with proband-only data, 21 of 24 diagnostic variants were recovered; manually correcting relatives' affected status also recovered diagnostic variants; some variants were recovered proband-only but not prioritized with corrected pedigrees. (Pedigree sensitivity, directly relevant to a single-proband lane.)
  - Known limitation: many diagnostic variants "were not prioritized using Exomiser or Genomiser default parameters on raw, unfiltered input VCFs", hence the optimization work.
- Relevance, stated carefully: this is a retrospective optimization study on UDN cases. It supports (a) Genomiser-style noncoding analysis being productive for compound diagnoses with a noncoding partner, and (b) top-N and inheritance-stratified evaluation as the outcome measures, not gene rank alone. It is not a validation of any threshold choice on our genome, and it does not study the effect of ReMM cutoff changes.

## Source 2: Bridges et al., BMC Bioinformatics 2025 (PhEval)

- Citation: Bridges Y, Souza Vd, Cortes KG, et al. "Towards a standard benchmark for phenotype-driven variant and gene prioritisation algorithms: PhEval - Phenotypic inference Evaluation framework." BMC Bioinformatics 2025 Mar 22;26:87. doi:10.1186/s12859-025-06105-4. Open access (CC BY-NC-ND per Springer page). Received 2024-08-13, accepted 2025-03-05.
- Verified statements: benchmarking of variant and gene prioritisation algorithms "has been difficult to measure"; assertions "are often not reproducible, in part because there is no standardised, empirical framework and openly available patient data"; PhEval provides standardized test corpora so benchmarks are "transparent, portable, comparable and reproducible"; "many of these benchmarks face challenges with reproducibility due to insufficient documentation of benchmarking methodologies and closed data sets."
- Circularity and temporal-leakage: the specific terms did not appear in the retrieved text as named failure modes. What the paper supports is the weaker claim that without standardized corpora and controlled configuration, benchmark claims are hard to reproduce and compare. Our prior notes should cite it only for that claim. Any statement about data-leakage between reference releases and benchmark corpora must cite a different source or be dropped.

## What this means for our write-ups

1. The sensitivity question we probe (does a stricter ReMM cutoff change membership and mode compatibility after inheritance recomputation?) is not answered by either paper. Cooperstein evaluates parameter changes on labeled cohorts; we have no truth labels. Cite Cooperstein only for the evaluation practice (top-N, stratified) and the compound-with-noncoding-partner precedent.
2. The public noncoding benchmark and the probe work should be described as synthetic, class-level evidence; PhEval's reproducibility argument motivates the fixture-pinned, deterministically verifiable form they take.
3. The offline-lane counts must never be compared against Cooperstein's recovery percentages as if they were the same measurement (different cohort, labels, and pipeline).
