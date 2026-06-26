---
name: archiving-product-document
description: Use when importing, converting, preserving, or normalizing an original product document before deriving project specs.
---

# Archiving Product Document

Archive first, interpret second.

## Procedure

1. Copy the untouched source to `docs/product/core/source/`.
2. Convert readable product text to `docs/product/core/PRD.md`.
3. Record source, conversion method, and review status in `product-meta.md`.
4. Preserve tables, acceptance rules, diagrams, and field names.
5. Register conversion losses in `docs/unresolved.md`.

## Conversion Rules

| Source | Preferred | Stop if |
| --- | --- | --- |
| Markdown | copy directly | encoding is broken |
| DOCX | use pandoc | tables or lists are lost |
| PDF | extract text, then review | layout or tables are ambiguous |
| HTML | use pandoc | scripts or hidden content affect meaning |

## Red Lines

- Do not summarize instead of archiving.
- Do not fix product meaning during conversion.
- Do not derive API, DB, or UI specs from a conversion-marked PRD.
