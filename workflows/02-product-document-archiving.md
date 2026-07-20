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
8. For TXT, DOCX, HTML, or HTM input, run the deterministic conversion preflight and apply pair. DOCX/HTML conversion requires Pandoc; request only that operation-specific environment capability instead of enabling every recommended tool:

   ```bash
   bin/governance env --repair --require-tool pandoc --check --target <target> --json
   bin/governance env --repair --require-tool pandoc --target <target> --json
   bin/governance product convert <target> --check --json
   bin/governance product convert <target> --json
   ```

   `product convert --check` is no-write. Write mode validates the archived size and SHA-256 first, uses bounded no-shell execution, writes `docs/product/core/PRD.md`, records `docs/product/core/source/conversion-report.json`, and leaves `product_conversion_status: pending_review`. TXT uses the Python standard library; DOCX/HTML use Pandoc to GitHub-Flavored Markdown. The command does not resolve `U-001` and does not allow design derivation.
9. PDF remains a manual stop: archive it, extract Markdown with a reviewed PDF tool, record fidelity limits, and do not claim automatic support.
10. Compare the readable Markdown PRD against the archived source. Use the `review_method` returned by `product convert` when conversion evidence exists; `manual-reviewed-markdown` remains the method for a fully manual conversion. Then use the deterministic closeout command instead of editing manifest metadata by hand:

   ```bash
   bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json
   bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --json
   ```

   The `--check` command reports `would_update` without writing files. When `conversion-report.json` exists, closeout binds both the generated output hash and the final reviewed PRD hash, updates report review status, updates `source-manifest.json`, refreshes `product-meta.md`, records state, marks the bootstrap conversion blocker `U-001` as `resolved`, and returns `local_commands` plus `next_actions` for the product-structuring transition. Sort returned `next_actions` by `sequence`; run apply actions only after the action named by `requires_action` reports `success_condition: ok:true`.

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
