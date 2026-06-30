---
name: archiving-product-document
description: Use when importing, converting, preserving, or normalizing an original product document before deriving project specs.
---

# Archiving Product Document

Archive first, interpret second.

## Procedure

1. Copy the untouched source to `docs/product/core/source/`.
2. Write `docs/product/core/source/source-manifest.json` with source path, archived path, byte size, SHA-256, conversion method, import status, and `can_derive_design`.
3. Convert readable product text to `docs/product/core/PRD.md`.
4. Record source, conversion method, hash evidence, and review status in `product-meta.md`.
5. Preserve tables, acceptance rules, diagrams, and field names.
6. Register conversion losses in `docs/unresolved.md`.
7. After manual review, run `bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json`, then run the same command without `--check` when `ok` is true.
8. Run `bin/governance verify <target> --check --json`, then record with `bin/governance verify <target> --json` and run `bin/governance gate product-structuring <target> --json`.

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
- Do not continue if the source manifest hash does not match the archived source.
