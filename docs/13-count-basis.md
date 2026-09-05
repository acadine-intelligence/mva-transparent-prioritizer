# Count-basis receipt contract

The validator accepts one fixed count-basis shape. It rejects unrelated run receipts. The repository's frozen Exomiser receipts do not automatically conform to this shape.

Run the synthetic example:

```sh
python3 scripts/validate_receipt_basis.py tests/fixtures/count_basis_receipt.json
```

Run the full verification sequence:

```sh
bash scripts/verify.sh
```

## Supported fields

The root contains `lanes` and an optional `partition`. `lanes` is a nonempty object with `l1`, `l2`, or both. Each lane describes one entity type. Unknown fields fail validation.

Every count block contains exactly `basis` and `count`. Counts must be nonnegative integers. Booleans, strings, and fractional values fail validation. Row counts must be at least as large as unique counts. Zero rows and zero unique entities must agree.

| Entity | Count field | Required basis |
| --- | --- | --- |
| Gene | `rows` | `tsv_rows_gene_x_moi` |
| Gene | `unique_symbols` | `unique_gene_symbols` |
| Gene | optional `extra_rows` | `extra_tsv_rows_beyond_unique_gene_symbols` |
| Variant | `rows` | `tsv_rows_variant_x_gene_association` |
| Variant | `unique_keys` | `unique_contig_pos_ref_alt_keys` |

Both `rows` and the relevant unique field are required. `extra_rows` equals gene rows minus unique gene symbols. It is not a count of repeated genes. The optional `identity` text must match the exact identity emitted by `GeneCounts.to_json()` or `VariantCounts.to_json()`.

A partition requires both lanes with the same entity type. It contains exactly `basis`, `shared`, `only_l1`, `only_l2`, and `total`. Its basis must equal each lane's unique-count basis.

The validator checks:

```text
shared + only_l1 = l1 unique count
shared + only_l2 = l2 unique count
shared + only_l1 + only_l2 = union total
```

## Failure behavior

The CLI returns 0 only if all supplied files pass. It returns 1 for a schema violation or unreadable input. It reports input positions rather than filenames or raw payload values. Duplicate JSON fields and non-finite numbers fail. The file limit is 1 MiB.

The CLI does not silently convert flat receipts. It never rewrites a receipt. A future adapter must name its source schema and bind the derived counts to source hashes. Existing frozen evidence must remain unchanged.

## Limits

Valid labels and arithmetic do not prove that a producer counted source rows correctly. The caller still needs to recompute counts from the original files under the relevant privacy rules. This CLI is a local arithmetic utility for explicit input paths. It is not the project's protected-file access boundary.

The old gene helper used `multi_moi` for extra rows. That name has been removed. Producers must use `extra_rows`. This change corrects the meaning of the field. It does not recompute the original frozen receipts.
