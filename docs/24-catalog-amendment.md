# Amendment K: published disease alleles

12 October 2026. Pre-registered before any catalog lookup against case data.
For case evidence, the author has seen only the Step 1 to 3 counts in
`verification/candidate-pool/run-1-summary.json`. No case allele, gene,
HGVS or catalog match has been inspected for this amendment. Development
and tests use public code and invented synthetic inputs only.

1. A public catalog lists published MVA/PCS disease alleles as exact GRCh38
   `(chrom, pos, ref, alt)` tuples with a `confidence` field. Only `high` and
   `medium` entries count.
2. A pool allele whose exact tuple matches a counted entry is Tier K.
   Matching uses the pool's contig convention: remove one `chr` prefix and
   map `M` and `MT` to `MT`; nuclear names are 1 to 22, X and Y. Positions
   and alleles must match exactly. Tier K outranks Tier A in the Stage 1
   evidence sort. Catalog gene and transcript text do not change the pool's
   gene assignment.
3. Pairing gains one clause: a Tier K allele pairs with any Tier A, B or K
   allele in the same gene, with no recessive-annotation requirement,
   because hypomorphic and frequent disease alleles lose that annotation
   when a frequency filter removes them. A pair containing a Tier K allele
   takes Tier K. All other pairing is unchanged.
4. With no catalog, or a catalog with zero matches, the output file must
   be byte-identical to the docs/22 output. Synthetic tests enforce this.
5. Stages 2 and 3, the EPCR ladder, the ten-row cap and Step 7 are unchanged.

## File contract

The catalog is a JSON array. Each entry has exactly `gene`, `transcript`,
`hgvs_c`, `grch38`, `mechanism`, `confidence` and `citations`. Text fields
are nonempty strings. Confidence is exactly `high`, `medium` or `low`.
Citations is a list of HTTP or HTTPS URLs. No URL is fetched by the runner.
`grch38` is null or an object with exactly `chrom` (string), `pos` (positive
integer), `ref` and `alt` (distinct, nonempty uppercase ACGT strings).
Null entries are ignored and counted. Unknown fields, incorrect types,
duplicate tuples after contig mapping, duplicate JSON keys and malformed
entries fail closed, including entries with low confidence.

Run `python3 scripts/select_candidates.py --pool <pool.json> --out <new-dir>`
and optionally add `--catalog <catalog.json>`. The output directory must
not exist and is created with mode 0700. Inputs must be regular files,
not symlinks, limited to 32 MiB for the pool and 16 MiB for the catalog.
`submission.csv` contains the selected rows. Tier K notes identify docs/24;
other rows retain docs/22 notes.

`selection-summary.json` and the single stdout JSON line contain only counts:
rows, pair rows, single rows, truncations by tier, promotions, demotions
(including removed competing pairs), catalog matches by original pool tier,
and null catalog entries. Failures exit 2 with the fixed message
`candidate selection refused` on stderr.

The runner checks the canonical parser with repeated pairings enabled and
cross-checks the gate mirror, retaining the sorted-row and no-tie defaults.
It also checks lane representation against the retained pool tuples.
The pool does not contain independent lane keys, so this is not a fresh
verification against original lane files or their receipts; that Step 7
check remains an encrypted-host prerequisite before use of the file.
A selected mitochondrial row requires `--mitochondrial-name chrM` or
`--mitochondrial-name chrMT`, supplied only after organizer confirmation.
This amendment authorizes no upload and makes no phase or clinical claim.

## Part 2: direct site lookup

12 October 2026. Written before any lookup. Development and tests use
synthetic inputs only.

1. Every counted catalog entry (confidence high or medium, non-null grch38)
   is looked up by exact position in the original single-sample VCF with
   bcftools, after the same contig mapping as Part 1.
2. A record matches only when POS and REF are identical and the catalog ALT
   is one of the record's ALT alleles, and the sample genotype carries that
   ALT (any non-reference call containing that allele index; missing or
   reference-only genotypes do not match).
3. A matched allele not already in the pool joins the selection as a Tier K
   candidate with the catalog's gene, `both_lanes` false, no recessive
   annotation, and a native rank worse than every pool rank (use one more
   than the maximum pool rank). If its tuple is already in the pool, the
   pool candidate is used and Part 1 applies; no duplicate is created.
4. Nothing else changes. With zero lookup matches the output is
   byte-identical to the Part 1 output.

Run `python3 scripts/lookup_catalog_sites.py --vcf <original.vcf.gz>
--catalog <catalog.json> --out <new-dir>` with an indexed, bgzipped VCF.
Use `--bcftools <path>` to select a local executable. No command uses a shell.
The runner reads the header with `bcftools view -h`, requires exactly one
sample, and resolves the Part 1 contig aliases to the header's spelling.
Ambiguous aliases or a missing catalog contig refuse the run. Each counted
entry gets its own `bcftools view -H -r <contig>:<pos>-<pos>` call. bcftools
must provide indexed regional access; there is no full-file scan fallback.
Overlapping records with a different POS are not matches. The GT allele
indices are checked against the original ALT list, so `0/2` can carry the
second ALT. A partial no-call containing the target allele still carries
that allele. Duplicate matching records refuse as ambiguous.

`matches.json` is a private JSON array. Each object contains exactly
`variant` (the mapped four-element tuple as an array), `genotype` (the original
GT string) and `gene` (the catalog gene). This file must stay with the private
VCF. `lookup-summary.json` and the single stdout JSON line contain only
`entries_counted`, `null_skipped`, `looked_up`, `matched` and
`matched_by_mechanism_class`. Null entries are counted regardless of confidence.
The mechanism count keys are fixed: `regulatory`, `splice`, `missense`,
`nonsense`, `frameshift`, `loss_of_function`, `hypomorphic` and `other`.
Only an exact catalog mechanism equal to one of these keys gets that class;
all other text counts as `other`. Free-text mechanisms are never echoed.
All summary values, including nested values, are integer counts.

The output directory must be new and is created with mode 0700. The summary
is written last. Lookup failures exit 2 and print only `catalog lookup refused`
on stderr. Failed lookups create no output directory; failed writes remove
the new partial output when the filesystem permits cleanup. Catalog and
match inputs use the existing 16 MiB bounded regular-file JSON reader.

Pass the private result to selection with
`--extra-candidates <lookup-dir/matches.json>`. The catalog option remains
optional. A direct match overlapping the pool applies Part 1 using the pool's
gene, evidence and native rank, including when no separate catalog is supplied.
New direct matches all receive one plus the maximum original pool rank
(rank 1 if the pool is empty). `catalog_direct_added` is always present in
the selection summary and stdout, defaulting to 0. It counts distinct new
candidates entering selection, before pairing and the ten-row cap, rather
than final CSV rows. Overlapping pool matches still count by original tier
in `catalog_matches_by_tier`.

The byte-identical guarantee concerns `submission.csv`; summaries gain the
new count. The representation check accepts the union of retained pool tuples
and direct VCF match tuples. A direct tuple does not establish lane support.
Step 7 still requires original lane checks on the encrypted host, and selected
mitochondrial rows still require the confirmed mitochondrial name option.

## Frozen catalog for the case run

12 October 2026, before any lookup against case data. The catalog used for the
case run has 27 counted entries (confidence high or medium, each with a GRCh38
tuple whose reference bases were checked against Ensembl GRCh38). It was built
from two public literature reviews and is held host-local until the
publication pass, because its gene symbols overlap the case-token denylist.
SHA-256: `ee0545c31e860d68022a1ddc6944a81e0f2b0f13b352eda8e6880602fedb2d01`.
A run against any other catalog bytes is not this pre-registered run.
