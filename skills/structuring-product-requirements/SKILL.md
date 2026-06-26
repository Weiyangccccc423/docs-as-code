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

1. Build the chapter map in `product-meta.md`.
2. Create only chapters supported by the PRD.
3. Extract acceptance criteria into a stable chapter.
4. Extract success metrics when present.
5. Add cross-domain terms to glossary.
6. Register ambiguous requirements before deriving design.

## Stop Conditions

- A chapter needs invented product scope.
- Two terms appear to refer to the same concept with different names.
- Acceptance criteria and functional text conflict.
