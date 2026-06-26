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
Treat gate requirement `product_acceptance_chapter_present` as a product-structuring blocker: create a sourced `NN-*acceptance*.md` product chapter or register the missing acceptance criteria as unresolved.
Treat `governance_scaffold_placeholder` as a design-authoring blocker, not a formatting issue.
Treat `workflow_pack_file_hash_mismatch` and `workflow_pack_file_missing` as workflow-pack integrity blockers.
Treat `docs_local_markdown_link_missing` as a document-integrity blocker: repair the link or create/index the referenced Markdown file.
Treat `product_chapter_invalid_filename`, `product_chapter_duplicate_prefix`, `product_chapter_missing_prd_link`, and `product_meta_missing_chapter_link` as product-structuring blockers.
Treat `api_endpoint_invalid_filename` and `api_endpoint_duplicate_prefix` as API-contract routing blockers: rename endpoint files under `docs/api/endpoints/` to unique `NN-<slug>.md` names and update indexes/links.
Treat `api_endpoint_missing_sections` as an API-contract completeness blocker: add the required endpoint contract headings before implementation handoff.
Treat `api_endpoint_empty_sections` as an API-contract content blocker: replace `TBD`/`TODO` placeholders with sourced contract decisions or unresolved items.
Treat `api_endpoint_method_path_invalid` as an API-contract syntax blocker: write `Method and Path` as `METHOD /absolute-path`.
Treat `api_endpoint_error_codes_reference_missing` as an API-contract registry blocker: link `Error Codes` to `docs/api/error-codes.md` and define the referenced codes there.
Treat `api_endpoint_upstream_reference_missing` as an API-contract traceability blocker: link `Upstream Links` to existing local Markdown source documents.
Treat `api_endpoint_frontend_consumer_reference_missing` as an API-contract consumer-trace blocker: link `Frontend Consumers` to existing local UI or frontend API-consumption docs.
Treat `glossary_*` findings as product-terminology blockers: fill required fields, remove duplicate terms, or link `Source` to existing local Markdown.
Treat `unresolved_row_missing_fields` and `unresolved_duplicate_id` as ambiguity-registry blockers.
Treat `roadmap_task_status_conflict` as a delivery-planning blocker.
Treat `task_board_*` findings as implementation-readiness blockers.
Treat `task_board_invalid_status` as a task-routing blocker: normalize the row to the standard status vocabulary before implementation.
Treat `task_board_blocked_unresolved_missing` and `task_board_blocked_unresolved_link_missing` as ambiguity-trace blockers: either unblock the task or cite the unresolved item ID and link `docs/unresolved.md`.
Treat `task_board_done_evidence_missing` as a completion-evidence blocker: keep the task open or link the `Verification` field to existing local Markdown evidence.
Treat `task_board_duplicate_id` as a task-routing blocker.
Treat `task_board_trace_reference_missing` as a source-traceability blocker: repair the task board or create/index the referenced Markdown source before implementation.
Treat `task_board_acceptance_reference_missing` as an implementation-readiness blocker: link `Acceptance` to `docs/product/NN-*acceptance*.md`.

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
- product chapter filenames use `NN-<slug>.md` with unique `NN` prefixes
- a dedicated `NN-*acceptance*.md` product chapter exists before design derivation
- product chapters link back to `core/PRD.md`, and `product-meta.md` links to every product chapter
- API endpoint contract files under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes
- API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, errors, upstream links, and frontend consumers sections
- API endpoint `Method and Path` sections contain an HTTP method and an absolute path
- API endpoint `Error Codes` sections reference `docs/api/error-codes.md`
- API endpoint `Upstream Links` sections reference existing local Markdown source documents
- API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption docs
- glossary rows have unique `Term` values and filled `Meaning` and `Source` fields; `Source` links to existing local Markdown
- unresolved rows have unique IDs and filled `Domain` and `Description`
- unresolved items use `none`, `-`, `n/a`, `non-blocking`, or `resolved` for non-blocking scope; any other `Blocking Scope` fails verification
- roadmap tables with `ID` and `Status` columns agree with same-ID task board statuses
- implementation tasks use `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
- task board `Status` values are `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done`, or `Deferred`
- task board items marked `Blocked` cite an existing unresolved item ID and link `docs/unresolved.md`
- task board items marked `Done` link to existing local Markdown verification evidence
- task board IDs are unique
- task board `Product`, `Design`, `API`, and `Acceptance` fields contain existing local Markdown references
- task board `Acceptance` fields include a product acceptance chapter reference matching `docs/product/NN-*acceptance*.md`
- at least one implementation task is `Ready`

## Red Lines

- Do not declare governance complete while verification fails.
- Do not ignore unresolved items that affect implementation.
- Do not treat generated indexes as optional.
