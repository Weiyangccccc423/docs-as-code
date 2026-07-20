---
name: archiving-product-document
description: Use when importing, converting, preserving, or normalizing an original product document before deriving project specs.
---

# Archiving Product Document

Archive first, interpret second.

## Procedure

1. Read `references/product-archive-checklist.md`.
2. Copy the untouched source to `docs/product/core/source/`.
3. Write `docs/product/core/source/source-manifest.json` with source path, archived path, byte size, SHA-256, conversion method, import status, and `can_derive_design`.
4. Convert readable product text to `docs/product/core/PRD.md`.
5. Record source, conversion method, hash evidence, and review status in `product-meta.md`.
6. Preserve tables, acceptance rules, diagrams, and field names.
7. Register conversion losses in `docs/unresolved.md`.
8. For DOCX/HTML, run `bin/governance env --repair --require-tool pandoc --check --target <target> --json` and follow only its reviewed repair actions. For TXT, no external converter is required.
9. Run `bin/governance product convert <target> --check --json`; apply with `bin/governance product convert <target> --json` only when preflight is `ok: true`. Require `conversion-report.json`, bounded no-shell execution evidence where Pandoc is used, and `product_conversion_status: pending_review`. Never treat conversion as review.
10. Compare the converted PRD against the archive, including tables, acceptance criteria, constraints, links, and diagrams. After manual review, run `bin/governance product mark-ready <target> --reviewed --method <review_method> --check --json`, inspect `would_update`, then run the same command without `--check` when `ok` is true. `review_method` comes from the conversion payload; use `manual-reviewed-markdown` only for a fully manual conversion. Use the write command's `local_commands` for target-local checks and `next_actions` for the next transition, running each `argv` from its `cwd`; sort by `sequence`, pair commands with `preflight_for` and `requires_action`, require `success_condition: ok:true`, and do not infer the next phase manually.
11. Run `bin/governance verify <target> --check --json`, then record with `bin/governance verify <target> --json` and run `bin/governance gate product-structuring <target> --json`.

## Conversion Rules

| Source | Preferred | Stop if |
| --- | --- | --- |
| Markdown | copy directly | encoding is broken |
| DOCX | use pandoc | tables or lists are lost |
| PDF | extract text, then review | layout or tables are ambiguous |
| HTML | use pandoc | scripts or hidden content affect meaning |
| TXT | use the built-in UTF-8 conversion | encoding is invalid or formatting carries unstated meaning |
| PDF | stop for reviewed manual extraction | layout, tables, or diagrams are ambiguous |

## Red Lines

- Do not summarize instead of archiving.
- Do not fix product meaning during conversion.
- Do not derive API, DB, or UI specs from a conversion-marked PRD.
- Do not continue if the source manifest hash does not match the archived source.
