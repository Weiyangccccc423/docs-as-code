---
name: structuring-product-requirements
description: Use when splitting an archived PRD into product chapters, extracting glossary terms, acceptance criteria, success metrics, or unresolved questions.
---

# Structuring Product Requirements

Turn a preserved PRD into navigable product truth without changing its meaning.

## Output Layers

| Layer | Purpose |
| --- | --- |
| `core/PRD.md` | canonical product source |
| `core/product-meta.md` | summary and navigation |
| `NN-*.md` chapters | derived views |
| `docs/unresolved.md` | ambiguity registry |
| `docs/glossary.md` | cross-domain terms |

## Procedure

1. Run the product gate:

   ```bash
   bin/governance advance product-structuring <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Read `core/source/source-manifest.json`.
3. Stop if `can_derive_design` is not true or the manifest hash does not verify.
4. Build the chapter map in `product-meta.md`.
5. Create only chapters supported by the PRD, using `NN-<slug>.md` filenames with unique `NN` prefixes.
6. Link every chapter back to `core/PRD.md`.
7. Link every `NN-*.md` chapter from `core/product-meta.md`.
8. Extract acceptance criteria into a stable `NN-*acceptance*.md` chapter before design derivation.
9. Extract success metrics when present.
10. Add cross-domain terms to glossary with unique `Term`, filled `Meaning`, and a `Source` link to the local Markdown definition.
11. Register ambiguous requirements before deriving design. Use unique `U-NNN` IDs and fill `Domain` and `Description`; use `none`, `-`, `n/a`, `non-blocking`, or `resolved` only for items that do not block downstream work.

## Stop Conditions

- A chapter needs invented product scope.
- Two terms appear to refer to the same concept with different names.
- Acceptance criteria and functional text conflict.
- The archived source manifest reports `conversion_required`.
- `docs/unresolved.md` has any row with a blocking `Blocking Scope`.
