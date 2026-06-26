# Phase 02: Product Document Archiving

## Input

- Original product document
- Initialized governance repository

## Skills

Load:

- `archiving-product-document`
- `structuring-product-requirements`
- `verifying-governance-docs`

## Procedure

1. Preserve the original under `docs/product/core/source/`.
2. Convert or copy the readable product text into `docs/product/core/PRD.md`.
3. Record source metadata in `docs/product/core/product-meta.md`:
   - source filename
   - import date
   - conversion method
   - current review status
4. Do not edit product meaning during archiving.
5. If conversion is incomplete, register the limitation in `docs/unresolved.md` and stop before design derivation.

## Recommended Conversion Rules

| Source type | Preferred handling | Fallback |
| --- | --- | --- |
| Markdown | copy to `PRD.md` | preserve source and copy text manually |
| DOCX | convert with `pandoc` | archive source and create conversion-required PRD wrapper |
| PDF | extract text with a PDF tool | archive source and ask for a Markdown export |
| HTML | convert with `pandoc` | archive source and normalize manually |

## Output

- `docs/product/core/source/<original>`
- `docs/product/core/PRD.md`
- updated `docs/product/core/product-meta.md`

## Verification

```bash
python3 scripts/verify_governance.py <target>
```

Manual review must confirm that `PRD.md` preserves the original meaning.

## Stop Conditions

- Text extraction loses tables, constraints, diagrams, or acceptance rules.
- Product terms are ambiguous enough to affect API, DB, UI, or module boundaries.
- The user wants to change scope during archiving.
