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
