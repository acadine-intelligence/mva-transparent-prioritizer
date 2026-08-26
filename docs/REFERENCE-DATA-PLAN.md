# Versioned reference data plan

Plan version: 1.0.0
Frozen on: 2026-08-26
Assembly: GRCh38
Private runtime: encrypted M1 workspace

## Separation rule

The M1 private runtime owns protected inputs and detailed outputs. Public tools and reference assets may be fetched on the M1, primary Mac, or an isolated VM. Each transferred public asset must pass a local SHA-256 check before use. Protected case data, HPO identifiers, variants, coordinates, sample metadata, and private logs cannot leave the M1 encrypted workspace.

## Pinned stack

| Component | Pin | Purpose |
|---|---|---|
| Python | 3.11 | Project runtime and deterministic wrapper |
| bcftools | 1.24 | VCF validation, statistics, normalization, lane extraction |
| htslib | 1.24 | bgzip and tabix runtime matched to bcftools |
| OpenJDK | 21 LTS | Exomiser runtime |
| Exomiser CLI | 15.1.0 | Primary phenotype and variant prioritization |
| Exomiser data | 2602, hg38 | Population, pathogenicity, phenotype, model-organism, and disease data |
| Ensembl reference | release 116, GRCh38 primary assembly | Canonical-contig normalization reference |
| Ensembl VEP | release 116 | Independent consequence and transcript evidence lane |
| ClinVar | GRCh38 weekly snapshot frozen at acquisition | Independent clinical assertion evidence |

The acquisition receipt must replace every unresolved digest with a measured SHA-256 value. Mutable names such as `latest` are forbidden in an accepted bundle.

## Contig contract

The input VCF declares unprefixed GRCh38 contigs and decoys. The first analytical lane selects `1` through `22`, `X`, `Y`, and `M`. It maps `M` to `MT` before normalization against the Ensembl primary assembly. The receipt binds the original header dictionary, rename map, selected-contig list, reference dictionary, and normalized output digest.

Non-canonical and decoy observations remain counted in QC. Their exclusion from the primary lane must appear as a warning and count. The pipeline cannot describe excluded contigs as biologically negative.

## Execution profile

Exomiser runs with one worker and an initial heap cap of 5 GiB. The private runner records exit status and peak resident memory. It retries only after a declared configuration change. It never treats an interrupted lane as complete.

The first Exomiser lane uses coding and splice-region evidence. A targeted genome lane follows for MVA pathway genes and strong phenotype genes. VEP and ClinVar form an independent evidence lane. A low-allele-fraction review keeps calls that a strict germline filter could remove.

## Receipt fields

Each asset receipt includes:

- logical name and version;
- source URL and retrieval date;
- expected and measured byte size;
- SHA-256 digest;
- archive member inventory when applicable;
- license or use note;
- assembly and contig dictionary digest;
- installation path label without username or absolute private path;
- verification command and exit status.

## FASTQ decision

FASTQ remains outside the current bundle. A request must name one unresolved issue such as coverage, read support, alignment ambiguity, structural variation, copy number, repeat expansion, or caller omission. The request must also name the minimum files, compute route, expected storage, and privacy controls.

## Update rule

A tool, data, ontology, transcript, or ClinVar update creates a new bundle version and a new run lineage. Existing run directories remain immutable. Candidate rank changes must be compared and explained before the new bundle becomes the default.
