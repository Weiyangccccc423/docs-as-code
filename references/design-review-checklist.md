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

## Structured Authority Report

- Was `report_contract` read from the current authoring task, work package, or failed/preflight `design review` payload instead of reconstructing the schema from memory?
- Is the report a regular JSON file directly under `.governance/design-review-reports/` and below the returned size limit?
- Do `track`, `work_id`, and `acceptance_id` match the selected work package?
- Does every `required_decision_ids` value appear exactly once with an `approved` or source-backed `not-applicable` status, concrete rationale, and existing repository-relative evidence?
- Are unknown, duplicate, or missing decisions absent?
- Are all findings resolved or false-positive, except explicitly retained medium/low accepted risks under `approved-with-suggestions`? Open findings and accepted critical/high risks block signoff.
- Does the preflight include `--report <path>` and show the report content plus SHA-256 under `review.authority_report` before apply?

## API Machine Review

- Before API authority review, is `work_stage: machine-review` complete and `docs/api/reviews/review-evidence.json` current?
- Did `api_linter.py`, `breaking_change_detector.py`, and `api_scorecard.py` run from the loaded `api-design-reviewer` skill with their script hashes recorded?
- Are lint errors and warnings both zero, breaking and potentially breaking changes both zero, and the scorecard grade B or better?
- Does the API design review snapshot `docs/api/openapi.json`, the baseline, all three reports, and machine review evidence?

## Architecture Threat Review

- Before architecture authority review, is `work_stage: threat-review` complete and `docs/architecture/threat-model/review-evidence.json` current?
- Did `threat_modeler.py` run from `senior-security` for every scoped DFD element with its script hash recorded?
- Does scope prove type-specific STRIDE coverage, and does every DREAD score at or above 7 have an owner, mitigation, and repository evidence?
- Does the architecture review snapshot scope, mitigations, normalized report, and machine evidence?

## Backend Reliability Review

- Before backend authority review, is `work_stage: reliability-review` complete and `docs/backend/reliability/review-evidence.json` current?
- Is the `required` or `not-applicable` decision backed by product acceptance, architecture quality attributes, backend modules, and external-service sources?
- In required mode, did `slo_designer.py`, `error_budget_calculator.py`, and `slo_review.py` run with zero findings, and are skill/tool/report hashes recorded?
- Does the backend design review snapshot the scope, error-budget policy when required, generated reports, source documents, and machine evidence?
- In not-applicable mode, are owner, reason, source references, and revisit triggers reviewed without inventing SLO targets?

## Data-Model Migration Review

- Before data-model authority review, is `work_stage: migration-review` complete and `docs/backend/migrations/review-evidence.json` current?
- Is the `required` or `not-applicable` decision supported by product acceptance, architecture quality attributes, backend ownership, and the authored data model?
- In required mode, did `migration_planner.py`, `compatibility_checker.py`, and `rollback_generator.py` run from the loaded `migration-architect` skill, with `database-schema-designer` and all tool hashes recorded?
- Does every breaking or potentially breaking compatibility issue have a stable ID plus written owner, reason, mitigation, and repository evidence, with no orphaned acceptances?
- Does the data-model design review snapshot the scope, schemas, migration specification, compatibility acceptances, generated plan/report/runbook, source documents, and machine evidence?
- In not-applicable mode, do owner, reason, source references, and revisit triggers prove the absence of a persistent schema lifecycle without fabricating migration artifacts?

## Freshness

- Does `--check` succeed before writing the review record?
- Do source and evidence snapshots match current repository file hashes?
- Does the authority report file still match the embedded content and SHA-256?
- After PRD, acceptance, or design evidence changes, is the stale review repeated before implementation?
- During implementation, are only roadmap/task-board `Status`, task-board `Verification`, and verification-log evidence changes exempted from full-file freshness?
- Does `semantic_sha256` still detect task scope, milestone, product/design/API/acceptance traceability, and other reviewed planning changes?
- If design evidence changes during implementation, is the affected authoring command rerun and the track/work review renewed without rolling phase state backward?
