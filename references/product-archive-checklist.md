# Product Archive Checklist

Use this checklist before a product source is marked ready for product structuring or design derivation.

Calibrate against provenance, hash integrity, document conversion, and Markdown portability practices. The goal is not to perfect the product text during import; it is to preserve source evidence and make conversion loss visible before downstream work depends on it.

## Source Preservation

- Is the untouched original copied under `docs/product/core/source/` before any conversion or normalization?
- Is the archived file path relative, local, and inside `docs/product/core/source/`?
- Is the original filename or normalized archive filename stable enough for future manifest verification?
- Are multiple source files, attachments, diagrams, or exports either archived together or registered as unresolved import scope?

Reference: `https://www.w3.org/TR/prov-overview/`

## Manifest Evidence

- Does `docs/product/core/source/source-manifest.json` record source path, archived path, byte size, SHA-256, conversion method, import status, and `can_derive_design`?
- Do source and archive size/hash values match when the archive is an untouched copy?
- Is SHA-256 used as integrity evidence, and is every hash recalculated from the file that will remain in the repository?
- Is `.governance/state.json` consistent with manifest archive path and product import readiness?

Reference: `https://csrc.nist.gov/pubs/fips/180-4/upd1/final`

## Conversion Fidelity

- Is `docs/product/core/PRD.md` a readable Markdown representation of the archived product source, not a summary?
- Are tables, acceptance rules, field names, constraints, diagrams, and hidden or linked content checked after conversion?
- Are format-specific conversion limitations, such as complex tables or layout-dependent PDF meaning, documented before closeout?
- Is `conversion_required` retained when conversion or manual review is incomplete?

Reference: `https://pandoc.org/MANUAL.html`

## Markdown Portability

- Is the converted PRD valid UTF-8 Markdown with headings, lists, tables, code blocks, and links preserved in a portable form?
- Are local links, images, and attachments either made repository-local or registered as unresolved source dependencies?
- Are Markdown extensions used only when they are intentional and do not hide product meaning from common Markdown readers?

Reference: `https://spec.commonmark.org/0.31.2/`

## Review Closeout

- Has a human or responsible reviewer compared `docs/product/core/PRD.md` against the archived original before `product mark-ready --reviewed` is run?
- Does `product-meta.md` record source, conversion method, hash evidence, review status, and import readiness?
- Does `bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json` report the intended `would_update` before write mode is used?
- Is the write-mode closeout command used instead of hand-editing manifest readiness fields?

## Unresolved Import Limits

- Are conversion losses, missing attachments, ambiguous diagrams, unreadable tables, or external source dependencies registered in `docs/unresolved.md`?
- Does any unresolved import issue that could affect API, DB, UI, module, security, or acceptance design keep `can_derive_design` false?
- Is the bootstrap conversion blocker `U-001` resolved only by deterministic closeout after manual review?

## Handoff Readiness

- Does `bin/governance verify <target> --check --json` pass before recorded verification?
- Does `bin/governance verify <target> --json` record the current evidence after closeout?
- Does `bin/governance gate product-structuring <target> --json` pass before product structuring starts?
