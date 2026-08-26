# Versioned reference data plan

Plan version: 1.1.1
Frozen on: 2026-08-26
Assembly: GRCh38
Private runtime: encrypted M1 workspace

## Separation rule

The M1 private runtime owns protected inputs and detailed outputs. Public tools and reference assets may be fetched on the M1, primary Mac, or an isolated VM. Each transferred public asset must pass a local SHA-256 check before use. Protected case data, HPO identifiers, variants, coordinates, sample metadata, and private logs cannot leave the M1 encrypted workspace.

## Pinned stack

| Component | Pin | Purpose |
|---|---|---|
| Python | 3.11.16 | Project runtime and deterministic wrapper |
| bcftools | 1.24 | VCF validation, statistics, normalization, lane extraction |
| htslib | 1.24 | bgzip and tabix runtime matched to bcftools |
| VEP htslib | 1.13 | Native runtime inside the Bio::DB::HTS support range |
| OpenJDK | 21 LTS | Exomiser runtime |
| Exomiser CLI | 15.1.0 | Primary phenotype and variant prioritization |
| Exomiser data | 2602, hg38 | Population, pathogenicity, phenotype, model-organism, and disease data |
| Ensembl reference | release 116, GRCh38 primary assembly | Candidate normalization reference pending source-reference identity proof |
| Ensembl VEP | code 116.1 at commit `97c24b205f4ba8b44ccc75b839512a1d59104019`; cache 116 | Independent consequence and transcript evidence lane |
| Ensembl Perl APIs | release 116 commits for core, variation, funcgen, compara, and IO | Pinned VEP dependencies |
| BioPerl | commit `f7d99adaad39ee0076a93dd93d0e866c184645fb` | Pinned VEP dependency |
| Bio::DB::HTS | 3.02 with htslib 1.13 | Native VEP VCF support verified by 979 upstream tests |
| Set::IntervalTree and Text::CSV | 0.12 and 2.06 | Pinned Perl dependencies |
| ClinVar | GRCh38 weekly snapshot frozen at acquisition | Independent clinical assertion evidence |

The acquisition receipt must replace every unresolved digest with a measured SHA-256 value. Mutable names such as `latest` are forbidden in an accepted bundle. Bundle `2026-08-26.2` contains 22 pinned artifacts. It distinguishes provider SHA-256 values, provider MD5 values, and locally frozen SHA-256 values. A provider MD5 mismatch stops acquisition before a local SHA-256 can be accepted.

## Acquisition states

An asset with a trusted SHA-256 moves into the verified directory only after its exact size and SHA-256 match. An asset without a published SHA-256 stays in quarantine after download. Its receipt records the measured SHA-256. The public manifest must then pin that SHA-256 before the same bytes can move into the verified directory. This promotion does not fetch the asset again.

The Ensembl FASTA and VEP cache publish legacy `CHECKSUMS` entries rather than SHA-256 values. Those entries remain source metadata. The workflow computes SHA-256 on the encrypted M1 and freezes it in a new bundle version. The ClinVar VCF uses the published MD5 as the first source check, followed by the same local SHA-256 freeze.

## Archive link policy

Source archives may contain relative symbolic links. The installer accepts a link only after it proves that the complete link chain ends at one unambiguous file or directory inside the same archive namespace. It rejects redundant separators and dot segments. A trailing slash is valid only when the resolved target is a directory. It materializes accepted links as regular files or directories. Installed trees contain no links. Absolute, escaping, broken, cyclic, hard, special-file, and ambiguous links fail before publication.

## Contig contract

The installed Ensembl FASTA is only a candidate normalization reference. Compatibility with the controlled VCF remains unresolved. Before normalization, the private runner must prove source-reference identity from local metadata, the complete VCF header dictionary, and the exact FASTA dictionary and digest. It must stop if any contig, length, naming rule, decoy, or source-build claim is missing or inconsistent. No rename map or contig selection is accepted before that proof. The private receipt binds the proof inputs, any later reviewed rename map, the selected-contig list, the reference dictionary, and the normalized output digest.

After compatibility is proven, excluded observations remain counted in QC. Their exclusion from an analytical lane must appear as a warning and count. The pipeline cannot describe excluded contigs as biologically negative.

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

The immutable environment receipt binds all 22 installed artifact inventories, seven tool entrypoints, and two native support trees. A second health run must reproduce the same receipt exactly. Health output contains counts and state only.

## FASTQ decision

FASTQ remains outside the current bundle. A request must name one unresolved issue such as coverage, read support, alignment ambiguity, structural variation, copy number, repeat expansion, or caller omission. The request must also name the minimum files, compute route, expected storage, and privacy controls.

## Update rule

A tool, data, ontology, transcript, or ClinVar update creates a new bundle version and a new run lineage. Existing run directories remain immutable. Candidate rank changes must be compared and explained before the new bundle becomes the default.
