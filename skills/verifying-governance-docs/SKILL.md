---
name: verifying-governance-docs
description: Use when checking whether generated or edited governance documents are complete, indexed, consistent, and ready for implementation handoff.
---

# Verifying Governance Docs

Prefer deterministic checks before manual review.

## Commands

```bash
bin/governance verify <target> --check
bin/governance verify <target>
bin/governance env --strict --repair --check --target <target>
bin/governance gate product-structuring <target>
bin/governance gate design-derivation <target>
bin/governance gate implementation <target>
bin/governance advance implementation <target> --check
bin/governance advance implementation <target>
bin/governance runtime refresh <target> --check
bin/governance runtime refresh <target>
```

For agent automation, use JSON and branch on `ok`:

```bash
bin/governance verify <target> --check --json
bin/governance verify <target> --json
bin/governance env --strict --repair --check --target <target> --json
bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json
bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --json
bin/governance gate implementation <target> --json
bin/governance advance implementation <target> --check --json
bin/governance advance implementation <target> --json
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

Use `verify --check --json` `findings[].code` and `findings[].path` for deterministic repair routing without updating state. Use `verify --json` when recording `last_verification` in `.governance/state.json`. Use `errors` and `warnings` only for human-facing summaries.
Use `gate --json` `requirements[].code` for phase-transition repair routing; `verification.findings[]` contains the embedded structural verification result.
Use `advance --check --json` to inspect `would_state`; use `advance --json` when the next phase should be recorded in `.governance/state.json`. `advance` records adjacent transitions one phase at a time and cannot skip phases.

## Repair Order

Fix document-integrity findings first: `required_file_not_file`, `required_directory_not_directory`, `docs_readme_not_file`, `markdown_not_file`, and `markdown_invalid_encoding`. When these findings affect a referenced source, acceptance chapter, task board, unresolved registry, README, or verification evidence file, repair that file and rerun verification before interpreting downstream traceability findings for the same area.

Do not invent missing acceptance IDs, unresolved IDs, links, or evidence just to satisfy secondary findings while their referenced Markdown source is not readable. Restore the expected file shape and UTF-8 Markdown first, then use the next verification report as the source of repair work.

Treat gate requirement `product_import_ready` as a product-archiving blocker: finish product conversion, run `bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json`, then run it without `--check`, or repair `docs/product/core/source/source-manifest.json` by the embedded verification findings.
Treat gate requirement `product_acceptance_chapter_present` as a product-structuring blocker: create a sourced `NN-*acceptance*.md` product chapter or register the missing acceptance criteria as unresolved.
Treat gate requirement `acceptance_matrix_present` as an implementation-readiness blocker: create and index `docs/tests/02-acceptance-matrix.md` before marking tasks Ready for implementation.
Treat gate requirements `ui_docs_present` and `frontend_docs_present` as design-derivation blockers: complete and index `docs/ui/` and `docs/frontend/` design documents before implementation handoff.
Treat standard handoff `*_present` gate requirements as implementation-readiness blockers: create and index the exact reported `path` before implementation handoff.
Treat gate requirement `api_endpoint_contract_present` as an API-contract blocker: create at least one indexed `docs/api/endpoints/NN-<slug>.md` endpoint contract.
Treat `product_source_missing`, `product_source_archive_missing`, `product_source_hash_mismatch`, `product_source_size_mismatch`, `product_source_manifest_*`, `product_source_import_status_invalid`, and `product_source_import_inconsistent` as product-archiving blockers: repair the source archive and manifest before deriving product structure.
Treat `product_source_conversion_required` as a product-archiving blocker: replace the PRD conversion wrapper with reviewed Markdown and use `bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json`, then run it without `--check`.
Treat `governance_scaffold_placeholder` as an authoring blocker, not a formatting issue. If `path` starts with `docs/product/`, replace it with PRD-derived product content before design derivation; otherwise replace it with product-derived design, test, or planning content before implementation handoff.
Treat `runtime_manifest_*`, `runtime_file_missing`, `runtime_file_not_file`, `runtime_file_hash_mismatch`, `runtime_file_size_mismatch`, and `runtime_file_not_executable` as target-local governance runtime integrity blockers: run `bin/governance runtime refresh <target> --check --json` from a trusted source workflow-pack checkout, then run `bin/governance runtime refresh <target> --json` before trusting target-local commands.
Treat `workflow_pack_manifest_*`, `workflow_pack_file_hash_mismatch`, `workflow_pack_file_size_mismatch`, `workflow_pack_file_missing`, `workflow_pack_file_not_file`, and `workflow_pack_file_unmanifested` as workflow-pack integrity blockers: run `bin/governance runtime refresh <target> --check --json` from a trusted source workflow-pack checkout, then run `bin/governance runtime refresh <target> --json`.
Treat `state_file_*`, `state_phase_*`, `state_phase_history_*`, `state_last_verification_*`, and `state_product_*` findings as workflow-state integrity blockers: inspect `.governance/state.json`, restore product import cache fields from `docs/product/core/source/source-manifest.json`, restore a valid sequential phase history from recorded `advance` output, rerun the correct next-phase `advance` from a trusted state, or rerun `bin/governance verify <target> --json` to refresh invalid verification metadata.
Treat `required_file_not_file` as a document-integrity blocker: replace the reported directory or special path with the exact required file before continuing.
Treat `required_directory_not_directory` as a document-integrity blocker: replace the reported file or special path with the exact required directory before continuing.
Treat `markdown_not_file` as a document-integrity blocker: replace the reported directory or special path with the exact Markdown file before continuing.
Treat `markdown_invalid_encoding` as a document-integrity blocker: rewrite the reported Markdown file as UTF-8 before continuing.
Treat `docs_local_markdown_link_missing` as a document-integrity blocker: repair the link or create/index the referenced Markdown file.
Treat `product_chapter_invalid_filename`, `product_chapter_duplicate_prefix`, `product_chapter_missing_prd_link`, and `product_meta_missing_chapter_link` as product-structuring blockers.
Treat `product_acceptance_missing_ids` as a product-structuring blocker: assign stable `A-NNN` IDs inside the product acceptance chapter before deriving design.
Treat `product_acceptance_duplicate_id` as a product-structuring blocker: keep each product acceptance `A-NNN` ID unique across acceptance chapters.
Treat `api_conventions_missing_sections`, `api_conventions_empty_sections`, and `api_conventions_trace_reference_missing` as API-conventions blockers: complete Product Links, HTTP Conventions, Authentication, Idempotency, Compatibility, and Open Decisions in `docs/api/00-conventions.md`, and link to product scope plus product acceptance criteria.
Treat `api_error_codes_missing_sections`, `api_error_codes_empty_sections`, and `api_error_codes_trace_reference_missing` as API error-registry blockers: complete Product Links, Error Taxonomy, Error Codes, Retry Semantics, and Frontend Handling in `docs/api/error-codes.md`, and link to product scope plus product acceptance criteria.
Treat `api_changelog_missing_sections` and `api_changelog_empty_sections` as API changelog blockers: complete Change Log and Compatibility Notes in `docs/api/changelog.md`.
Treat `api_endpoint_invalid_filename` and `api_endpoint_duplicate_prefix` as API-contract routing blockers: rename endpoint files under `docs/api/endpoints/` to unique `NN-<slug>.md` names and update indexes/links.
Treat `api_endpoint_missing_sections` as an API-contract completeness blocker: add the required endpoint contract headings before implementation handoff.
Treat `api_endpoint_empty_sections` as an API-contract content blocker: replace `TBD`/`TODO` placeholders with sourced contract decisions or unresolved items.
Treat `api_endpoint_method_path_invalid` as an API-contract syntax blocker: write `Method and Path` as `METHOD /absolute-path`.
Treat `api_endpoint_error_codes_reference_missing` as an API-contract registry blocker: link `Error Codes` to `docs/api/error-codes.md` and define the referenced codes there.
Treat `api_endpoint_upstream_reference_missing` as an API-contract traceability blocker: link `Upstream Links` to existing local Markdown source documents.
Treat `api_endpoint_frontend_consumer_reference_missing` as an API-contract consumer-trace blocker: link `Frontend Consumers` to existing local UI or frontend API-consumption docs.
Treat `ui_interaction_model_missing_sections`, `ui_interaction_model_empty_sections`, and `ui_interaction_model_trace_reference_missing` as UI interaction blockers: complete Product Links, Primary Flows, Screens, States, Errors, and Accessibility in `docs/ui/01-interaction-model.md`, and link to product scope plus product acceptance criteria.
Treat `architecture_system_context_missing_sections`, `architecture_system_context_empty_sections`, and `architecture_system_context_trace_reference_missing` as system-context blockers: complete Product Links, Actors, External Systems, Trust Boundaries, and Open Decisions in `docs/architecture/01-system-context.md`, and link to product scope plus product acceptance criteria.
Treat `architecture_containers_missing_sections`, `architecture_containers_empty_sections`, and `architecture_containers_trace_reference_missing` as container-view blockers: complete Product Links, Containers, Runtime Responsibilities, Data Ownership, and Open Decisions in `docs/architecture/02-containers.md`, and link to `docs/architecture/01-system-context.md` plus product acceptance criteria.
Treat `architecture_quality_attributes_missing_sections`, `architecture_quality_attributes_empty_sections`, and `architecture_quality_attributes_trace_reference_missing` as quality-attribute blockers: complete Product Links, Availability, Performance, Security, Observability, and Tradeoffs in `docs/architecture/03-quality-attributes.md`, and link to containers plus product acceptance criteria.
Treat `backend_module_missing_sections`, `backend_module_empty_sections`, and `backend_module_trace_reference_missing` as backend-module blockers: complete Product Links, Architecture Links, Modules, API Ownership, Failure Modes, and Open Decisions in `docs/backend/01-modules.md`, and link to architecture docs, API docs, `docs/backend/02-data-model.md`, `docs/backend/03-external-services.md`, and a product acceptance chapter.
Treat `backend_data_model_missing_sections`, `backend_data_model_empty_sections`, and `backend_data_model_trace_reference_missing` as data-design blockers: complete Product Links, Owners, Entities, State Machines, Constraints, Indexes, and Migrations in `docs/backend/02-data-model.md`, and link to backend modules, API docs, and product acceptance criteria.
Treat `backend_external_services_missing_sections`, `backend_external_services_empty_sections`, and `backend_external_services_trace_reference_missing` as dependency-design blockers: complete Product Links, Dependencies, Contracts, Retries, Timeouts, Authentication, and Observability in `docs/backend/03-external-services.md`, and link to backend modules, API docs, and product acceptance criteria.
Treat `frontend_module_missing_sections`, `frontend_module_empty_sections`, and `frontend_module_trace_reference_missing` as frontend-module blockers: complete Product Links, UI Links, Modules, State Ownership, Routes, and Open Decisions in `docs/frontend/01-modules.md`, and link to UI docs, API docs, `docs/frontend/02-api-consumption.md`, and a product acceptance chapter.
Treat `frontend_api_consumption_missing_sections`, `frontend_api_consumption_empty_sections`, and `frontend_api_consumption_trace_reference_missing` as frontend API-consumption blockers: complete Product Links, API Links, Consumption Map, Loading States, and Error Actions in `docs/frontend/02-api-consumption.md`, and link to frontend modules, API docs, and product acceptance criteria.
Treat `test_strategy_missing_sections`, `test_strategy_empty_sections`, and `test_strategy_trace_reference_missing` as verification-strategy blockers: complete Product Links, Acceptance Links, Test Layers, Risk Coverage, and Non-Functional Checks in `docs/tests/01-strategy.md`, and link to product acceptance criteria, API docs, and architecture/backend/frontend design docs.
Treat `acceptance_matrix_missing_sections` and `acceptance_matrix_empty_sections` as acceptance-traceability blockers: complete Matrix and Uncovered Criteria in `docs/tests/02-acceptance-matrix.md`.
Treat `acceptance_matrix_*` findings as acceptance-traceability blockers: make `docs/tests/02-acceptance-matrix.md` use `Acceptance`, `Design`, `API`, and `Test` columns with local Markdown links to the matching source docs; each `Acceptance` row must include a unique `A-NNN` ID defined in the referenced product acceptance chapter, and every product-defined `A-NNN` must be mapped or listed under Uncovered Criteria using product-defined IDs only.
Treat `acceptance_matrix_api_endpoint_reference_missing` as an API-contract traceability blocker: replace generic API doc links in the Matrix `API` column with concrete `docs/api/endpoints/NN-<slug>.md` endpoint contract links.
Treat `acceptance_matrix_acceptance_anchor_mismatch` as an acceptance-traceability blocker: make the Acceptance link fragment match the row's `A-NNN` ID.
Treat `adr_missing_sections`, `adr_empty_sections`, and `adr_reference_missing` as ADR completeness blockers: add Context, Decision, Consequences, and References with local Markdown source links.
Treat `adr_invalid_filename` and `adr_duplicate_prefix` as ADR identity blockers: rename ADRs under `docs/decisions/` to unique `NNN-<slug>.md` files and update indexes/links.
Treat `glossary_*` findings as product-terminology blockers: fill required fields, remove duplicate terms, or link `Source` to existing local Markdown.
Treat `unresolved_row_missing_fields`, `unresolved_invalid_id`, and `unresolved_duplicate_id` as ambiguity-registry blockers: use unique `U-NNN` IDs and fill Domain and Description.
Treat `roadmap_missing_sections`, `roadmap_empty_sections`, and `roadmap_trace_reference_missing` as delivery-planning blockers: complete Product Links, Milestones, Sequencing, Risks, and Deferred Scope in `docs/development/01-roadmap.md`, and link to product scope plus product acceptance criteria.
Treat `roadmap_milestone_*` findings as roadmap-structure blockers: make the Milestones table use `ID`, `Status`, and `Milestone`, include at least one row, fill all fields, use `TASK-NNN` IDs, use the standard task status vocabulary, and keep IDs unique.
Treat `roadmap_task_missing` as a delivery-planning blocker: add the missing `TASK-NNN` row to `docs/development/02-task-board.md` or remove the roadmap milestone.
Treat `roadmap_task_status_conflict` as a delivery-planning blocker.
Treat `task_board_roadmap_missing` as an implementation-readiness blocker: add the task to roadmap Milestones or remove the unplanned task board row.
Treat `task_board_*` findings as implementation-readiness blockers.
Treat `task_board_missing_sections` and `task_board_empty_sections` as implementation-readiness blockers: complete Task Table, Status Policy, and Traceability Rules in `docs/development/02-task-board.md`.
Treat `task_board_invalid_id` as a task-routing blocker: rename the task row to `TASK-NNN` and update roadmap/status references to match.
Treat `task_board_invalid_status` as a task-routing blocker: normalize the row to the standard status vocabulary before implementation.
Treat `task_board_blocked_unresolved_missing` and `task_board_blocked_unresolved_link_missing` as ambiguity-trace blockers: either unblock the task or cite the unresolved item ID and link `docs/unresolved.md`.
Treat `task_board_done_evidence_missing` as a completion-evidence blocker: keep the task open or link the `Verification` field to existing local Markdown evidence.
Treat `task_board_duplicate_id` as a task-routing blocker.
Treat `task_board_trace_reference_missing` as a source-traceability blocker: repair the task board or create/index the referenced Markdown source before implementation.
Treat `task_board_trace_reference_mismatch` as a source-traceability blocker: link Product, Design, and API fields to matching product scope, design, and API docs.
Treat `task_board_acceptance_reference_missing` as an implementation-readiness blocker: link `Acceptance` to `docs/product/NN-*acceptance*.md`.
Treat `task_board_acceptance_id_missing` as an implementation-readiness blocker: include the matching `A-NNN` acceptance ID in the task row `Acceptance` field.
Treat `task_board_acceptance_id_unknown` as an implementation-readiness blocker: replace the row's `A-NNN` with an ID defined in the referenced product acceptance chapter, or add the missing sourced criterion there first.
Treat `task_board_acceptance_anchor_mismatch` as an implementation-readiness blocker: make the Acceptance link fragment match the row's `A-NNN` ID.
Treat `task_board_acceptance_matrix_missing` as an implementation-readiness blocker: map the task's `A-NNN` in `docs/tests/02-acceptance-matrix.md` with design, API, and test links before implementation, or remove/defer the task.

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
- runtime and workflow-pack manifests keep the expected schema, source, size, and hash identity
- non-empty docs directories have `README.md` and `AGENTS.md`
- non-template Markdown files are indexed in the README in the same directory
- explicit local Markdown links resolve to existing files
- product chapter filenames use `NN-<slug>.md` with unique `NN` prefixes
- a dedicated `NN-*acceptance*.md` product chapter exists before design derivation
- product acceptance criteria use stable unique `A-NNN` IDs
- product chapters link back to `core/PRD.md`, and `product-meta.md` links to every product chapter
- `docs/api/00-conventions.md` has non-placeholder Product Links, HTTP Conventions, Authentication, Idempotency, Compatibility, and Open Decisions sections, and links to product scope plus product acceptance criteria
- `docs/api/error-codes.md` has non-placeholder Product Links, Error Taxonomy, Error Codes, Retry Semantics, and Frontend Handling sections, and links to product scope plus product acceptance criteria
- `docs/api/changelog.md` has non-placeholder Change Log and Compatibility Notes sections
- API endpoint contract files under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes
- API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, errors, upstream links, and frontend consumers sections
- API endpoint `Method and Path` sections contain an HTTP method and an absolute path
- API endpoint `Error Codes` sections reference `docs/api/error-codes.md`
- API endpoint `Upstream Links` sections reference existing local Markdown source documents
- API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption docs
- `docs/ui/01-interaction-model.md` has non-placeholder Product Links, Primary Flows, Screens, States, Errors, and Accessibility sections, and links to product scope plus product acceptance criteria
- `docs/architecture/01-system-context.md` has non-placeholder Product Links, Actors, External Systems, Trust Boundaries, and Open Decisions sections, and links to product scope plus product acceptance criteria
- `docs/architecture/02-containers.md` has non-placeholder Product Links, Containers, Runtime Responsibilities, Data Ownership, and Open Decisions sections, and links to `docs/architecture/01-system-context.md` plus product acceptance criteria
- `docs/architecture/03-quality-attributes.md` has non-placeholder Product Links, Availability, Performance, Security, Observability, and Tradeoffs sections, and links to containers plus product acceptance criteria
- `docs/backend/01-modules.md` has non-placeholder Product Links, Architecture Links, Modules, API Ownership, Failure Modes, and Open Decisions sections, and links to architecture docs, API docs, `docs/backend/02-data-model.md`, `docs/backend/03-external-services.md`, and product acceptance criteria
- `docs/backend/02-data-model.md` has non-placeholder Product Links, Owners, Entities, State Machines, Constraints, Indexes, and Migrations sections, and links to backend modules, API docs, and product acceptance criteria
- `docs/backend/03-external-services.md` has non-placeholder Product Links, Dependencies, Contracts, Retries, Timeouts, Authentication, and Observability sections, and links to backend modules, API docs, and product acceptance criteria
- `docs/frontend/01-modules.md` has non-placeholder Product Links, UI Links, Modules, State Ownership, Routes, and Open Decisions sections, and links to UI docs, API docs, `docs/frontend/02-api-consumption.md`, and product acceptance criteria
- `docs/frontend/02-api-consumption.md` has non-placeholder Product Links, API Links, Consumption Map, Loading States, and Error Actions sections, and links to frontend modules, API docs, and product acceptance criteria
- `docs/tests/01-strategy.md` has non-placeholder Product Links, Acceptance Links, Test Layers, Risk Coverage, and Non-Functional Checks sections, and links to product acceptance criteria, API docs, and architecture/backend/frontend design docs
- `docs/tests/02-acceptance-matrix.md` has non-placeholder Matrix and Uncovered Criteria sections
- `docs/tests/02-acceptance-matrix.md` uses `Acceptance`, `Design`, `API`, and `Test` columns, each `Acceptance` row has a unique `A-NNN` ID defined in the referenced product acceptance chapter, Acceptance link fragments match row IDs when present, every product-defined `A-NNN` is mapped or listed as uncovered using product-defined IDs only, and each row links to matching local source docs; the `API` column links concrete `docs/api/endpoints/NN-<slug>.md` endpoint contracts
- ADR files under `docs/decisions/` use unique `NNN-<slug>.md` names
- ADRs under `docs/decisions/` include non-placeholder Context, Decision, Consequences, and References sections with local Markdown source links
- glossary rows have unique `Term` values and filled `Meaning` and `Source` fields; `Source` links to existing local Markdown
- unresolved rows have unique `U-NNN` IDs and filled `Domain` and `Description`
- unresolved items use `none`, `-`, `n/a`, `non-blocking`, or `resolved` for non-blocking scope; any other `Blocking Scope` fails verification
- `docs/development/01-roadmap.md` has non-placeholder Product Links, Milestones, Sequencing, Risks, and Deferred Scope sections, and links to product scope plus product acceptance criteria
- roadmap Milestones table uses `ID`, `Status`, and `Milestone`, has at least one row, has unique `TASK-NNN` IDs, and uses standard task status values
- roadmap tables with `ID` and `Status` columns have matching task board rows, no extra task board IDs, and agree with same-ID task board statuses
- `docs/development/02-task-board.md` has non-placeholder Task Table, Status Policy, and Traceability Rules sections
- implementation tasks use `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
- task board `Status` values are `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done`, or `Deferred`
- task board items marked `Blocked` cite an existing unresolved item ID and link `docs/unresolved.md`
- task board items marked `Done` link to existing local Markdown verification evidence
- task board IDs are unique, use `TASK-NNN`, and match roadmap milestones
- task board `Product`, `Design`, `API`, and `Acceptance` fields contain existing local Markdown references to matching source domains
- task board `Acceptance` fields include an `A-NNN` ID defined in the referenced product acceptance chapter, mapped in `docs/tests/02-acceptance-matrix.md`, a matching link fragment when present, and a product acceptance chapter reference matching `docs/product/NN-*acceptance*.md`
- at least one implementation task is `Ready`

## Red Lines

- Do not declare governance complete while verification fails.
- Do not ignore unresolved items that affect implementation.
- Do not treat generated indexes as optional.
