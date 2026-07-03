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

1. Read `references/product-archive-checklist.md` and use it as the rubric for source preservation, manifest evidence, conversion fidelity, review closeout, unresolved import limits, and handoff readiness.
2. Preserve the original under `docs/product/core/source/`.
3. Record source evidence in `docs/product/core/source/source-manifest.json`:
   - source filename
   - archived path
   - source and archive SHA-256
   - byte size
   - conversion method
   - import status
   - whether design derivation is allowed
4. Convert or copy the readable product text into `docs/product/core/PRD.md`.
5. Record navigational metadata in `docs/product/core/product-meta.md`.
6. Do not edit product meaning during archiving.
7. If conversion is incomplete, register the limitation in `docs/unresolved.md` and stop before design derivation. Bootstrap registers `U-001` automatically for conversion-required sources.
8. After the readable Markdown PRD has been manually reviewed against the archived source, use the deterministic closeout command instead of editing manifest metadata by hand:

   ```bash
   bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json
   bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --json
   ```

   The `--check` command reports `would_update` without writing files. The write command updates `source-manifest.json`, refreshes `product-meta.md`, records state, marks the bootstrap conversion blocker `U-001` as `resolved`, and returns `local_commands` plus `next_actions` for the product-structuring transition.

## Recommended Conversion Rules

| Source type | Preferred handling | Fallback |
| --- | --- | --- |
| Markdown | copy to `PRD.md` | preserve source and copy text manually |
| DOCX | convert with `pandoc` | archive source and create conversion-required PRD wrapper |
| PDF | extract text with a PDF tool | archive source and ask for a Markdown export |
| HTML | convert with `pandoc` | archive source and normalize manually |

## Output

- `docs/product/core/source/<original>`
- `docs/product/core/source/source-manifest.json`
- `docs/product/core/PRD.md`
- updated `docs/product/core/product-meta.md`

## Verification

```bash
bin/governance verify <target> --check --json
bin/governance verify <target> --json
bin/governance gate product-structuring <target> --json
```

Verification checks that the archived source still matches the manifest hash and byte size, and that `can_derive_design` is true. Manual review must confirm that `PRD.md` preserves the original meaning before `product mark-ready --reviewed` is run.

Source preservation, manifest evidence, conversion fidelity, review closeout, unresolved import limits, and handoff readiness must satisfy `references/product-archive-checklist.md`.

## Stop Conditions

- `source-manifest.json` is missing, invalid, or has a hash/size mismatch.
- `source-manifest.json` reports `conversion_required` or `can_derive_design: false`.
- Text extraction loses tables, constraints, diagrams, or acceptance rules.
- Product terms are ambiguous enough to affect API, DB, UI, or module boundaries.
- The user wants to change scope during archiving.
