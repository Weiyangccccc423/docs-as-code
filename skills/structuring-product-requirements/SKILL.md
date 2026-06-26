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

1. Read `core/source/source-manifest.json`.
2. Stop if `can_derive_design` is not true or the manifest hash does not verify.
3. Build the chapter map in `product-meta.md`.
4. Create only chapters supported by the PRD.
5. Extract acceptance criteria into a stable chapter.
6. Extract success metrics when present.
7. Add cross-domain terms to glossary.
8. Register ambiguous requirements before deriving design. Use `none`, `-`, `n/a`, `non-blocking`, or `resolved` only for items that do not block downstream work.

## Stop Conditions

- A chapter needs invented product scope.
- Two terms appear to refer to the same concept with different names.
- Acceptance criteria and functional text conflict.
- The archived source manifest reports `conversion_required`.
- `docs/unresolved.md` has any row with a blocking `Blocking Scope`.
