---
name: verifying-governance-docs
description: Use when checking whether generated or edited governance documents are complete, indexed, consistent, and ready for implementation handoff.
---

# Verifying Governance Docs

Prefer deterministic checks before manual review.

## Commands

```bash
bin/governance verify <target>
bin/governance env --strict --repair --target <target>
bin/governance gate product-structuring <target>
bin/governance gate design-derivation <target>
bin/governance gate implementation <target>
bin/governance advance implementation <target>
```

For agent automation, use JSON and branch on `ok`:

```bash
bin/governance verify <target> --json
bin/governance env --strict --repair --target <target> --json
bin/governance gate implementation <target> --json
bin/governance advance implementation <target> --json
```

Use `verify --json` `findings[].code` and `findings[].path` for deterministic repair routing. Use `errors` and `warnings` only for human-facing summaries.
Use `gate --json` `requirements[].code` for phase-transition repair routing; `verification.findings[]` contains the embedded structural verification result.
Use `advance --json` when the phase should be recorded in `.governance/state.json`.
Treat `governance_scaffold_placeholder` as a design-authoring blocker, not a formatting issue.
Treat `workflow_pack_file_hash_mismatch` and `workflow_pack_file_missing` as workflow-pack integrity blockers.
Treat `docs_local_markdown_link_missing` as a document-integrity blocker: repair the link or create/index the referenced Markdown file.
Treat `product_chapter_missing_prd_link` and `product_meta_missing_chapter_link` as product-structuring blockers.
Treat `unresolved_row_missing_fields` and `unresolved_duplicate_id` as ambiguity-registry blockers.
Treat `roadmap_task_status_conflict` as a delivery-planning blocker.
Treat `task_board_*` findings as implementation-readiness blockers.
Treat `task_board_invalid_status` as a task-routing blocker: normalize the row to the standard status vocabulary before implementation.
Treat `task_board_duplicate_id` as a task-routing blocker.
Treat `task_board_trace_reference_missing` as a source-traceability blocker: repair the task board or create/index the referenced Markdown source before implementation.

Treat `ok: false` as blocking. Treat `needs_escalation: true` as requiring explicit approval before running the reported package-manager command.

When already inside an initialized target repository, prefer target-local checks:

```bash
bin/governance verify .
make verify-governance
make ci
```

## Manual Checks

- no unregistered `docs/` directories
- no stale reserved markers
- no `governance:scaffold-placeholder` markers
- workflow-pack snapshot manifest hashes still match
- non-empty docs directories have `README.md` and `AGENTS.md`
- non-template Markdown files are indexed in the README in the same directory
- explicit local Markdown links resolve to existing files
- product chapters link back to `core/PRD.md`, and `product-meta.md` links to every product chapter
- unresolved rows have unique IDs and filled `Domain` and `Description`
- unresolved items use `none`, `-`, `n/a`, `non-blocking`, or `resolved` for non-blocking scope; any other `Blocking Scope` fails verification
- roadmap tables with `ID` and `Status` columns agree with same-ID task board statuses
- implementation tasks use `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
- task board `Status` values are `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done`, or `Deferred`
- task board IDs are unique
- task board `Product`, `Design`, `API`, and `Acceptance` fields contain existing local Markdown references
- at least one implementation task is `Ready`

## Red Lines

- Do not declare governance complete while verification fails.
- Do not ignore unresolved items that affect implementation.
- Do not treat generated indexes as optional.
