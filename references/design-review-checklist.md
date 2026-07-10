# Design Review Checklist

Use this checklist before recording `docs/decisions/design-reviews.json` for one acceptance criterion and design track.

Calibrate architecture review against ISO/IEC/IEEE 42010 and ISO/IEC 25010, API review against OpenAPI and HTTP Semantics, and security review against OWASP ASVS and the project security checklist. The repository Markdown remains the reviewed design source; the JSON record is provenance and freshness evidence, not a replacement for design content.

## Source Scope

- Does the review identify the current `A-NNN` acceptance criterion and canonical PRD?
- Are all declared track decisions addressed in design evidence or explicitly registered in `docs/unresolved.md`?
- Does the review preserve product meaning rather than inventing requirements?

## Document Stage

- Is every task `documents[].status` value either `authored` or `reference_template`?
- Are required sections present and all `governance:scaffold-placeholder` markers removed?
- Was the track's primary local workflow skill loaded before authoring?

## Integration Stage

- Is every `required_links[].status` `satisfied`?
- Do API, backend, data, frontend, test, and planning references point to the current local Markdown contracts?
- Were cross-track links repaired only after each owning track authored its own documents?

## Authority Review

- Was the task's `primary_specialist_skill` loaded from the agent environment?
- Does the review record the authority skill name and SHA-256 without embedding a machine-specific path?
- Does the reason name what was reviewed and why the evidence is sufficient?
- Is `not-applicable` used only for ADR-trigger review with a concrete no-ADR reason?
- If an ADR is approved, is a numbered `docs/decisions/NNN-<slug>.md` supplied as additional evidence?

## Freshness

- Does `--check` succeed before writing the review record?
- Do source and evidence snapshots match current repository file hashes?
- After PRD, acceptance, or design evidence changes, is the stale review repeated before implementation?
- During implementation, are only roadmap/task-board `Status`, task-board `Verification`, and verification-log evidence changes exempted from full-file freshness?
- Does `semantic_sha256` still detect task scope, milestone, product/design/API/acceptance traceability, and other reviewed planning changes?
- If design evidence changes during implementation, is the affected authoring command rerun and the track/work review renewed without rolling phase state backward?
