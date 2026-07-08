---
name: verifying-governance-docs
description: Use when checking whether generated or edited governance documents are complete, indexed, consistent, and ready for implementation handoff.
---

# Verifying Governance Docs

Prefer deterministic checks before manual review.

Read `references/governance-verification-checklist.md` before declaring a phase complete, repairing drift, or approving implementation handoff. Read `references/release-readiness-checklist.md` before tagging, exporting, or handing off this source workflow pack.

## Commands

For source workflow-pack health before using the pack on a real target:

```bash
make dry-run
make dry-run-golden
python3 scripts/dry_run_workflow.py --json
python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json
make package
python3 scripts/export_workflow_pack.py --check --json
python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json
python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json
make artifact-smoke
python3 scripts/smoke_workflow_pack_artifact.py --json
make release-check
python3 scripts/release_readiness.py --json
```

```bash
bin/governance verify <target> --check
bin/governance verify <target>
bin/governance env --strict --repair --check --target <target>
bin/governance gate product-structuring <target>
bin/governance gate design-derivation <target>
bin/governance gate implementation <target>
bin/governance advance implementation <target> --check
bin/governance advance implementation <target>
bin/governance product plan <target>
bin/governance design plan <target>
bin/governance design api-candidates <target>
bin/governance design api-authoring <target>
bin/governance design backend-authoring <target>
bin/governance design frontend-authoring <target>
bin/governance design test-strategy-authoring <target>
bin/governance design implementation-planning-authoring <target>
bin/governance design architecture-decisions-authoring <target>
bin/governance implementation plan <target>
bin/governance implementation closeout <target> --task TASK-NNN
bin/governance workflow plan <target>
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
bin/governance product plan <target> --json
bin/governance design plan <target> --json
bin/governance design api-candidates <target> --json
bin/governance design api-authoring <target> --json
bin/governance design backend-authoring <target> --json
bin/governance design frontend-authoring <target> --json
bin/governance design test-strategy-authoring <target> --json
bin/governance design implementation-planning-authoring <target> --json
bin/governance design architecture-decisions-authoring <target> --json
bin/governance implementation plan <target> --json
bin/governance implementation closeout <target> --task TASK-NNN --json
bin/governance workflow plan <target> --json
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

Use `verify --check --json` `findings[].code` and `findings[].path` for deterministic repair routing without updating state. Use `verify --json` when recording `last_verification` in `.governance/state.json`. When governance state is readable, use returned `local_commands[].argv` and `next_actions[].argv` to continue without rerunning `status`; use `workflow plan --json` when the agent needs the current phase plus active queue summaries, top-level/per-queue `active_work`, local/authority skill routing summaries, ordered skill loading plans, and read-only queue commands in one payload. Use `active_work.queue_id`, `active_work.inspect_command`, `active_work.next_repair_action`, and embedded verify/refresh commands to resume the first blocked queue before manually scanning every task. Sort `next_actions` by `sequence`, pair preflight/apply commands with `preflight_for` and `requires_action`, and run apply only after the referenced preflight reports `success_condition: ok:true`. Stop before any returned command with `approval_required: true`. Use `errors` and `warnings` only for human-facing summaries.
When the recorded phase is `implementation`, use `implementation plan --json` or target-local `make implementation-plan` after repairing verification findings. Inspect `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `read_order`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `next_repair_action`, and embedded `gate_command`, `verify_command`, `closeout_command`, and `refresh_command`; keep `active_work.status != ready`, `gate_ok: false`, missing local workflow skills, and unavailable authority-routing skills as blockers before implementation edits. Before a task is marked `Done`, use `implementation closeout --task TASK-NNN --json`; keep `closeout_ready: false`, non-empty `blocking_requirements[]`, missing verification-log rows, non-passing results, missing local evidence links, and unsynchronized task/roadmap statuses as closeout blockers.
Use successful `env --json` `local_commands[].argv` and `next_actions[].argv` when governance state is readable. For repair preflights, inspect `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, `repair_execution`, `repair_decision`, and returned `approval_required` fields. Use `repair_decision.decision`, `repair_decision.stop_before_workflow`, `repair_decision.runnable_action_ids`, `repair_decision.approval_action_ids`, and `repair_decision.manual_action_ids` for the first branch, then use `repair_execution.status`, `repair_execution.can_auto_apply`, `repair_execution.install_attempted`, `repair_execution.install_failed`, `repair_execution.post_repair_missing_required`, `repair_execution.post_repair_missing_recommended`, and `repair_execution.next_step` for detail. Sort `repair_actions` by `sequence`; run actions with `argv` only when `approval_required` is false or approval is explicit, and present `manual-repair` actions to the user. Keep `ok: false`, non-empty `manual_repairs`, `needs_escalation: true`, `applied_but_unresolved`, `repair_decision.stop_before_workflow: true`, and unapproved `approval_required: true` as stop conditions before running installs or downstream state-writing commands.
Use `gate --json` `requirements[].code` for phase-transition repair routing; `verification.findings[]` contains the embedded structural verification result. When governance state is readable, use returned `local_commands[].argv`; when the gate passes, use returned `next_actions[].argv` for the next advance preflight/apply sequence.
Use `advance --check --json` to inspect `would_state`; use `advance --json` when the next phase should be recorded in `.governance/state.json`. `advance` records adjacent transitions one phase at a time and cannot skip phases.
After successful state-writing `product mark-ready --json` or `advance --json`, use returned `local_commands[].argv` for target-local checks and `next_actions[].argv` for the next preflight/apply sequence.
After successful `product plan --json`, use returned `source_documents`, `available_chapters`, `prd_headings`, `suggested_mappings`, `required_decisions`, `manual_authoring_tasks`, `manual_authoring_summary`, `active_work`, `skills`, `skill_requirements`, `authority_skill_requirements`, and ordered `steps` to drive product structuring. Its `decision_policy` is `do_not_guess_product_meaning`; use `manual_authoring_summary` for queue counts and `active_work` for the selected task, next required evidence, next repair action, stop condition, and verify/refresh commands before drilling into task details. Do not run a scaffold or structure apply command until the selected `key=PRD Heading` mapping is source-backed or the required decision is resolved manually. Use `manual_authoring_tasks[]` by `sequence` for PRD-backed manual chapters; each `status: decision_required` task lists `execution`, `required_sections`, `required_links`, `required_evidence`, `evidence_repair_actions`, `open_decisions`, and verify/refresh steps. Use `required_evidence[].status` to distinguish missing files, unindexed chapters, unlinked metadata, scaffold placeholders, pending manual review, and satisfied evidence; use `evidence_repair_actions[]` with `repair_strategy`, `verify_command`, and `refresh_command` to route non-satisfied evidence repairs.
After successful write-mode `scaffold product --json` or `scaffold design --json`, use returned `local_commands[].argv` for checks and inspect `scaffold_phase`; if `scaffold_phase.matches` is false, follow returned `next_actions[].argv` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until each blocker is resolved.
After successful `design plan --json`, use returned `source_documents`, `active_work`, `tracks[].sequence`, `tracks[].skills`, `tracks[].specialist_skills`, `tracks[].skill_requirements`, `tracks[].authority_skill_requirements`, `tracks[].skill_loading_plan`, `tracks[].primary_skill`, `tracks[].primary_specialist_skill`, `tracks[].references`, `tracks[].documents`, `tracks[].blockers`, and `tracks[].steps` to route authoring work to the correct local and authority-routing design skills without guessing from raw verification output. Each requirement records `type`, `available_in_workflow_pack`, `availability_scope`, and `missing_policy`; each loading step records `action`, `load_from`, and `missing_policy`; local workflow skill absence is a workflow-pack integrity error, and authority-routing skill absence must follow `missing_policy: load_from_agent_environment_or_stop_before_guessing`. Treat `authoring_blocked` tracks as the active repair queue until every listed blocker is replaced with source-backed content, then run each read-only command step such as `verify-track` and `refresh-design-plan`.
For every design authoring payload, inspect `authoring_summary` (`task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count`) for queue counts, then use `active_work` for the selected task, next required link, next repair action, authority skill, stop condition, and verify/refresh commands before running `authoring_tasks[]` by `sequence` and following `execution.primary_skill`, `execution.primary_specialist_skill`, `execution.verify_step`, `execution.refresh_step`, and `execution.stop_condition`. Use `required_links[].status` and `link_repair_actions` with `repair_strategy`, `verify_command`, and `refresh_command` for deterministic link repair routing; treat `open_decisions` as separate unresolved design questions.
After successful `design api-candidates --json`, use returned `candidates[].acceptance_id`, source `reference`, `suggested_endpoint_file`, `replaceable_starter_endpoint`, `open_decisions`, and `specialist_skills` including `api-design-reviewer`, `senior-backend`, and `senior-security` to route API authoring. Treat every `open_decisions` item as unresolved until the API contract links product, architecture/UI/backend/frontend, security, and test sources.
After successful `design api-authoring --json`, use `decision_policy: do_not_guess_contract_details`, `skill_requirements`, `authority_skill_requirements`, and `authoring_tasks[]` to drive API contract edits. Each task lists target `documents`, required `sections`, `required_links`, unresolved `open_decisions`, `specialist_skills` including `api-design-reviewer`, `senior-backend`, and `senior-security`, and command steps such as verify-api-authoring and refresh-api-authoring; run those read-only commands before considering the API track repaired.
After successful `design backend-authoring --json`, use `decision_policy: do_not_guess_backend_boundaries`, `skill_requirements`, `authority_skill_requirements`, and `authoring_tasks[]` to drive backend module and data-model edits. Each task lists backend/data-model `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `module_boundaries` and `transaction_boundaries`, `specialist_skills` including `senior-backend`, `database-designer`, `database-schema-designer`, `migration-architect`, `observability-designer`, and `senior-security`, and command steps such as verify-backend-authoring and refresh-backend-authoring; run those read-only commands before considering the backend track repaired.
After successful `design frontend-authoring --json`, use `decision_policy: do_not_guess_frontend_behavior` and `authoring_tasks[]` to drive UI interaction, frontend module, and API-consumption edits. Each task lists UI/frontend `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `state_ownership` and `error_actions`, `specialist_skills` including `senior-frontend`, `a11y-audit`, and `performance-profiler`, and command steps such as verify-frontend-authoring and refresh-frontend-authoring; run those read-only commands before considering the frontend track repaired.
After successful `design test-strategy-authoring --json`, use `decision_policy: do_not_guess_verification_scope` and `authoring_tasks[]` to drive test strategy and acceptance-matrix edits. Each task lists test `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `acceptance_coverage` and `evidence_targets`, `specialist_skills` including `senior-qa`, `playwright-pro`, `a11y-audit`, and `security-pen-testing`, and command steps such as verify-test-strategy-authoring and refresh-test-strategy-authoring; run those read-only commands before considering the verification track repaired.
After successful `design implementation-planning-authoring --json`, use `decision_policy: do_not_guess_task_scope` and `authoring_tasks[]` to drive roadmap, task-board, and verification-log edits. Each task lists development `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `task_scope`, `ready_criteria`, `verification_plan`, and `agent_handoff`, `specialist_skills` including `senior-fullstack`, `ci-cd-pipeline-builder`, and `tech-debt-tracker`, and command steps such as verify-implementation-planning-authoring and refresh-implementation-planning-authoring; run those read-only commands before considering the delivery-planning track repaired.
After successful `design architecture-decisions-authoring --json`, use `decision_policy: do_not_guess_architecture_decisions` and `authoring_tasks[]` to drive ADR trigger review and ADR authoring. Each task lists ADR `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `adr_trigger`, `decision_scope`, and `alternatives`, keeps `requires_adr: undetermined` until sources prove the trigger, returns `specialist_skills` including `senior-architect`, `migration-architect`, and `tech-stack-evaluator`, and includes command steps such as verify-architecture-decisions-authoring and refresh-architecture-decisions-authoring; run those read-only commands before considering the ADR track repaired.
After successful write-mode `runtime refresh --json`, use returned `local_commands[].argv` before trusting target-local checks and `next_actions[].argv` for the next workflow transition. Keep `runtime refresh --check --json` as a no-write plan only.

## Repair Order

Fix document-integrity findings first: `required_file_not_file`, `required_directory_not_directory`, `docs_readme_not_file`, `markdown_not_file`, and `markdown_invalid_encoding`. When these findings affect a referenced source, acceptance chapter, task board, unresolved registry, README, or verification evidence file, repair that file and rerun verification before interpreting downstream traceability findings for the same area.

Do not invent missing acceptance IDs, unresolved IDs, links, or evidence just to satisfy secondary findings while their referenced Markdown source is not readable. Restore the expected file shape and UTF-8 Markdown first, then use the next verification report as the source of repair work.

Treat gate requirement `product_import_ready` as a product-archiving blocker: finish product conversion, run `bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json`, then run it without `--check`, or repair `docs/product/core/source/source-manifest.json` by the embedded verification findings.
Treat gate requirement `product_acceptance_chapter_present` as a product-structuring blocker: create a sourced `NN-*acceptance*.md` product chapter or register the missing acceptance criteria as unresolved.
Treat gate requirement `product_acceptance_ids_present` as a product-structuring blocker: assign stable product-defined `A-NNN` IDs inside the sourced acceptance chapter before design derivation.
Treat gate requirement `product_chapters_traceable` as a product-structuring blocker: repair product chapter filenames, `docs/product/README.md` indexing, `core/PRD.md` source links, local Markdown links, and `core/product-meta.md` chapter links before design derivation.
Treat gate requirement `product_acceptance_ids_unique` as a product-structuring blocker: resolve duplicate `A-NNN` IDs across product acceptance chapters without changing product meaning.
Treat gate requirement `product_glossary_traceable` as a product-terminology blocker: fill glossary rows, keep terms unique, and link each `Source` to an existing local Markdown definition.
Treat gate requirement `product_unresolved_clear` as an ambiguity blocker: fill unresolved rows, use unique `U-NNN` IDs, and resolve or explicitly mark non-blocking every `Blocking Scope` before design derivation.
Treat gate requirement `acceptance_matrix_present` as an implementation-readiness blocker: create and index `docs/tests/02-acceptance-matrix.md` before marking tasks Ready for implementation.
Treat gate requirements `ui_docs_present` and `frontend_docs_present` as design-derivation blockers: complete and index `docs/ui/` and `docs/frontend/` design documents before implementation handoff.
Treat standard handoff `*_present` gate requirements as implementation-readiness blockers: create and index the exact reported `path` before implementation handoff.
Treat gate requirement `api_endpoint_contract_present` as an API-contract blocker: create at least one indexed `docs/api/endpoints/NN-<slug>.md` endpoint contract.
Treat gate requirement `architecture_design_ready` as an architecture-design blocker: complete architecture sections, trace links, indexes, and placeholders under `docs/architecture/`.
Treat gate requirement `api_contracts_ready` as an API-contract blocker: complete API conventions, error registry, changelog, endpoint contract identity, endpoint sections, method/path syntax, upstream links, error-code links, frontend consumer links, indexes, and placeholders under `docs/api/`.
Treat gate requirement `backend_design_ready` as a backend-design blocker: complete backend modules, data model, external services, trace links, indexes, and placeholders under `docs/backend/`.
Treat gate requirement `frontend_design_ready` as a frontend-design blocker: complete UI interaction and frontend module/API-consumption docs, trace links, indexes, and placeholders under `docs/ui/` and `docs/frontend/`.
Treat gate requirement `verification_strategy_ready` as a verification-strategy blocker: complete test strategy and acceptance matrix structure, trace links, product acceptance coverage, endpoint links, indexes, and placeholders under `docs/tests/`.
Treat gate requirement `delivery_plan_ready` as an implementation-readiness blocker: complete roadmap, task board, verification log, task IDs/statuses, roadmap/task alignment, Ready task traceability, verification evidence rules, indexes, and placeholders under `docs/development/`.
Treat `product_source_missing`, `product_source_archive_missing`, `product_source_hash_mismatch`, `product_source_size_mismatch`, `product_source_manifest_*`, `product_source_import_status_invalid`, and `product_source_import_inconsistent` as product-archiving blockers: repair the source archive and manifest before deriving product structure.
Treat `product_source_conversion_required` as a product-archiving blocker: replace the PRD conversion wrapper with reviewed Markdown and use `bin/governance product mark-ready <target> --reviewed --method manual-reviewed-markdown --check --json`, then run it without `--check`.
Treat `governance_scaffold_placeholder` and `governance_structured_placeholder` as authoring blockers, not formatting issues. If `path` starts with `docs/product/`, replace it with PRD-derived product content before design derivation; otherwise replace scaffold IDs, paths, fields, and rows such as `A-NNN`, `TASK-NNN`, `METHOD /product-derived-path`, `NN-*`, or `field_name` with product-derived design, test, or planning content before implementation handoff.
Treat `runtime_manifest_*`, `runtime_file_missing`, `runtime_file_not_file`, `runtime_file_hash_mismatch`, `runtime_file_size_mismatch`, and `runtime_file_not_executable` as target-local governance runtime integrity blockers: run `bin/governance runtime refresh <target> --check --json` from a trusted source workflow-pack checkout, then run `bin/governance runtime refresh <target> --json` before trusting target-local commands.
Treat `workflow_pack_manifest_*`, `workflow_pack_file_hash_mismatch`, `workflow_pack_file_size_mismatch`, `workflow_pack_file_missing`, `workflow_pack_file_not_file`, and `workflow_pack_file_unmanifested` as workflow-pack integrity blockers: run `bin/governance runtime refresh <target> --check --json` from a trusted source workflow-pack checkout, then run `bin/governance runtime refresh <target> --json`.
Treat `state_file_*`, `state_phase_*`, `state_phase_history_*`, `state_last_verification_*`, `state_product_*`, and `state_timestamp_*` findings as workflow-state integrity blockers: inspect `.governance/state.json`, restore product import cache fields from `docs/product/core/source/source-manifest.json`, restore a valid sequential phase history from recorded `advance` output, rerun the correct next-phase `advance` from a trusted state, or rerun `bin/governance verify <target> --json` to refresh invalid verification metadata and timestamps.
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
make verify-check
make governance-status
make workflow-plan
make product-plan
make design-plan
make implementation-plan
make check-env
make repair-env-check
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
