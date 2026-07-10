# Phase 04: Design Derivation

## Input

- Structured product documents
- Dedicated acceptance criteria product chapter
- `docs/unresolved.md`
- `docs/glossary.md`

## Skills

Load according to the design track:

- System architecture: `designing-system-architecture`
- UI interaction model: `designing-ui-interactions`
- API contract: `designing-api-contracts`
- Backend modules: `designing-backend-modules`
- Data model: `designing-data-models`
- Architecture decisions: `capturing-architecture-decisions`
- Frontend modules: `designing-frontend-modules`
- Test strategy: `designing-test-strategy`
- Implementation planning: `planning-implementation-work`
- Governance check: `verifying-governance-docs`

## Procedure

1. Confirm product structure is ready for design derivation:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   The gate requires at least one `docs/product/NN-*acceptance*.md` chapter.

2. Create the standard design document scaffold when files are missing:

   ```bash
   bin/governance scaffold design <target> --check --json
   bin/governance scaffold design <target> --json
   bin/governance design plan <target> --json
   bin/governance design api-candidates <target> --json
   bin/governance design architecture-authoring <target> --json
   bin/governance design api-authoring <target> --json
   bin/governance design backend-authoring <target> --json
   bin/governance design data-model-authoring <target> --json
   bin/governance design ui-interaction-authoring <target> --json
   bin/governance design frontend-authoring <target> --json
   bin/governance design test-strategy-authoring <target> --json
   bin/governance design implementation-planning-authoring <target> --json
   bin/governance design architecture-decisions-authoring <target> --json
   ```

   `--check` reports `would_create`, `would_skip`, and `would_index` without writing placeholders. The scaffold creates the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md`, the acceptance matrix, and the verification log when those standard files are missing. The write command returns `local_commands`, `next_actions`, and `scaffold_phase` when gate state is readable; when scaffold placeholders remain, it also returns `next_actions_blocked_by`.

   If `scaffold_phase.matches` is false, use returned `next_actions` to advance recorded phases in order before treating the scaffold as current phase work. Keep the next actions for later, and do not run downstream phase actions until every blocker listed in `next_actions_blocked_by` is resolved.

   After the recorded phase is `design-derivation`, `workflow plan --json` exposes top-level and per-queue `active_work`, `skill_summary`, and `skill_loading_plan` objects. Use `design plan --json` to inspect `source_documents`, ordered tracks, `available_in_workflow_pack` skill requirements, and track `blockers` before replacing placeholders. Use `active_work` to resume the first blocked queue, then load local workflow skills first and authority-routing skills such as `senior-architect`, `api-design-reviewer`, `senior-backend`, database design skills, `observability-designer`, and `senior-security` before resolving architecture, API, backend, or data decisions.

   When consumer bootstrap returns `design_authoring_preview`, inspect ordered `queue_summaries[]` and aggregate `authoring_summary` first. Use `queue_status_counts`, total task/decision/link-repair counts, `next_queue_id`, `next_active_work`, and top-level `active_work.queue_id` to choose the first non-ready queue; only then open that queue's full payload under `queues` and follow its verify/refresh commands.

   Use `design api-candidates --json` and `design api-authoring --json` for API work. API candidates include `acceptance_id`, `suggested_endpoint_file`, `replaceable_starter_endpoint`, and open decisions before a contract is authored. API authoring uses `decision_policy: do_not_guess_contract_details` and exposes `authoring_tasks`, `authoring_summary`, `required_links[].status`, `link_repair_actions`, `verify-api-authoring`, and `refresh-api-authoring`.

   Use `design architecture-authoring --json` for system context, container, and quality-attribute work before downstream design. It uses `decision_policy: do_not_guess_architecture_boundaries`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, architecture `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, `open_decisions` such as `system_boundary`, `container_responsibilities`, `quality_scenarios`, `deployment_assumptions`, and `adr_candidates`, `specialist_skills` such as `senior-architect`, `senior-security`, `observability-designer`, and `slo-architect`, and command steps `verify-architecture-authoring` and `refresh-architecture-authoring`.

   Use `design backend-authoring --json` for backend module and external-service work. It uses `decision_policy: do_not_guess_backend_boundaries`, `open_decisions` such as `module_boundaries` and `observability`, `specialist_skills` such as `senior-backend`, `observability-designer`, and `senior-security`, and command steps `verify-backend-authoring` and `refresh-backend-authoring`.

   Use `design data-model-authoring --json` for entity/schema/migration work. It uses `decision_policy: do_not_guess_data_model`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, `open_decisions` such as `entity_ownership`, `transaction_boundaries`, `migration_order`, and `rollback_strategy`, `specialist_skills` such as `database-designer`, `database-schema-designer`, `migration-architect`, `senior-backend`, and `senior-security`, and command steps `verify-data-model-authoring` and `refresh-data-model-authoring`.

   Use `design ui-interaction-authoring --json` for visible flow, screen, state, error, accessibility, and copy work. It uses `decision_policy: do_not_guess_ui_behavior`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, UI `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, unresolved `open_decisions` such as `primary_flows`, `screens`, `states`, `error_actions`, `accessibility`, and `copy_and_content`, `specialist_skills` such as `senior-frontend` and `a11y-audit`, and command steps `verify-ui-interaction-authoring` and `refresh-ui-interaction-authoring`.

   Use `design frontend-authoring --json` for frontend module and API-consumption work after UI interaction exists. It uses `decision_policy: do_not_guess_frontend_behavior`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, frontend `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, unresolved `open_decisions` such as `state_ownership` and `error_actions`, `specialist_skills` such as `senior-frontend`, `a11y-audit`, and `performance-profiler`, and command steps `verify-frontend-authoring` and `refresh-frontend-authoring`.

   Use `design test-strategy-authoring --json` for verification work. It uses `decision_policy: do_not_guess_verification_scope`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, test `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, unresolved `open_decisions` such as `acceptance_coverage` and `evidence_targets`, `specialist_skills` such as `senior-qa`, `playwright-pro`, `a11y-audit`, and `security-pen-testing`, and command steps `verify-test-strategy-authoring` and `refresh-test-strategy-authoring`.

   Use `design implementation-planning-authoring --json` for delivery planning work. It uses `decision_policy: do_not_guess_task_scope`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, development `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, unresolved `open_decisions` such as `task_scope`, `ready_criteria`, `verification_plan`, and `agent_handoff`, `specialist_skills` such as `senior-fullstack`, `ci-cd-pipeline-builder`, and `tech-debt-tracker`, and command steps `verify-implementation-planning-authoring` and `refresh-implementation-planning-authoring`.

   Use `design architecture-decisions-authoring --json` for ADR trigger review. It uses `decision_policy: do_not_guess_architecture_decisions`, `authoring_tasks`, `authoring_summary`, `sequence`, `execution`, `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, ADR `documents`, `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, `authority-routing`, `skill_requirements`, `authority_skill_requirements`, `missing_policy`, unresolved `open_decisions` such as `adr_trigger`, `decision_scope`, and `alternatives`, `requires_adr: undetermined`, `specialist_skills` such as `senior-architect`, `migration-architect`, and `tech-stack-evaluator`, and command steps `verify-architecture-decisions-authoring` and `refresh-architecture-decisions-authoring`.

   Replace all `governance:scaffold-placeholder` markers before implementation handoff.

   Design plan tracks include `sequence`, `primary_skill`, `primary_specialist_skill`, `skill_requirements`, `authority_skill_requirements`, and `skill_loading_plan`. Design authoring payloads include queue-level `active_work`; use it to inspect the selected task, next repair action, and verify/refresh commands before running `authoring_tasks[]` by sequence. Design authoring tasks include `sequence`, `skill_loading_plan`, plus `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, and `stop_condition`; run tasks in sequence and stop when `stop_condition` is true.

3. Read `references/architecture-methods.md` and `references/architecture-quality-checklist.md`, then create or complete `docs/architecture/` views:
   - system context
   - containers
   - major quality attributes
   - external dependencies
   - deployment assumptions
4. Read `references/api-design-checklist.md`, then create or complete `docs/api/`:
   - `00-conventions.md`
   - `endpoints/README.md`
   - endpoint files
   - `error-codes.md`
   - `changelog.md`
5. Read `references/security-design-checklist.md`, then document authentication, authorization, abuse limits, sensitive data, dependency trust, and security verification expectations in API, backend, frontend, and test design.
6. Read `references/frontend-interaction-checklist.md`, then create or complete `docs/ui/` from product interaction needs or imported design assets.
7. Read `references/backend-design-checklist.md`, `references/data-model-design-checklist.md`, and `references/backend-operability-checklist.md`, then create or complete `docs/backend/` implementation design:
   - architecture overview
   - module documents
   - database schema
   - external service contracts
   - `references/backend-design-checklist.md` checklist coverage
   - `references/data-model-design-checklist.md` checklist coverage
   - `references/backend-operability-checklist.md` checklist coverage
8. Create database and lifecycle design:
   - entity ownership
   - state machines
   - idempotency constraints
   - indexes and migration order
   - `references/data-model-design-checklist.md` checklist coverage
9. Read `references/frontend-interaction-checklist.md`, then create or complete `docs/frontend/` implementation design:
   - architecture overview
   - module documents
   - API consumption map
   - error action map
10. Read `references/test-strategy-checklist.md`, then create or complete `docs/tests/01-strategy.md` from product acceptance, API contracts, and architecture/backend/frontend design risks.
11. Create or complete `docs/tests/02-acceptance-matrix.md` with Matrix and Uncovered Criteria sections, and `Acceptance`, `Design`, `API`, and `Test` columns; every `Acceptance` row must include a unique product-defined `A-NNN` ID, the `API` column must link a concrete `docs/api/endpoints/NN-<slug>.md` endpoint contract, link fragments must match row IDs when present, and every product-defined `A-NNN` must be mapped or listed under Uncovered Criteria using product-defined IDs only.
12. Read `references/implementation-readiness-checklist.md`, then create or complete `docs/development/01-roadmap.md` with product links, a Milestones table using `TASK-NNN` `ID`, `Status`, and `Milestone`, sequencing, risks, and deferred scope.
13. Create or complete `docs/development/02-task-board.md` with Task Table, Status Policy, and Traceability Rules sections; task IDs must use `TASK-NNN`, match roadmap milestone IDs, `Product`, `Design`, and `API` fields must link to matching source domains, `Acceptance` fields must include `A-NNN` IDs defined in referenced product acceptance chapters and mapped in `docs/tests/02-acceptance-matrix.md` with matching link fragments when present, and `Ready`/`Done` transitions must satisfy `references/implementation-readiness-checklist.md`.
14. Create or initialize `docs/development/03-verification-log.md` so Done task evidence has a stable local Markdown target.
15. Read `references/architecture-decision-record-checklist.md`, then create ADRs in `docs/decisions/` for cross-module or high-cost decisions, named as unique `NNN-<slug>.md` files.
16. Keep all design and planning documents linked to product and acceptance sources.
17. Update the same-directory `README.md` for every new Markdown document, except underscore-prefixed templates such as `_template.md`.

## Output

Design documents sufficient for creating a task board without guessing product meaning.

## Verification

- API endpoints have request, response, error code, auth, and idempotency notes.
- Architecture documents are checked against `references/architecture-quality-checklist.md` for architecture-description coverage, quality model coverage, measurable quality scenarios, runtime/failure flow, tradeoffs, and implementation readiness.
- API contracts are checked against `references/api-design-checklist.md` for contract shape, HTTP semantics, error responses, idempotency, collection operations, compatibility, and traceability.
- Security-sensitive API, backend, frontend, and test design decisions are checked against `references/security-design-checklist.md`.
- `docs/api/00-conventions.md` has non-placeholder Product Links, HTTP Conventions, Authentication, Idempotency, Compatibility, and Open Decisions sections, and links to product scope plus product acceptance criteria.
- `docs/api/error-codes.md` has non-placeholder Product Links, Error Taxonomy, Error Codes, Retry Semantics, and Frontend Handling sections, and links to product scope plus product acceptance criteria.
- `docs/api/changelog.md` has non-placeholder Change Log and Compatibility Notes sections.
- API endpoint contract files under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes.
- API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, error code, upstream link, and frontend consumer sections.
- API endpoint `Method and Path` sections contain an HTTP method and absolute path.
- API endpoint `Error Codes` sections reference `docs/api/error-codes.md`.
- API endpoint `Upstream Links` sections reference existing local source Markdown.
- API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption Markdown.
- UI and frontend interaction design is checked against `references/frontend-interaction-checklist.md` for interaction model, accessibility and semantics, component behavior, API consumption and error UX, state/routing, performance, and handoff evidence.
- `docs/ui/01-interaction-model.md` has non-placeholder Product Links, Primary Flows, Screens, States, Errors, and Accessibility sections, and links to product scope plus product acceptance criteria.
- `docs/architecture/01-system-context.md` has non-placeholder Product Links, Actors, External Systems, Trust Boundaries, and Open Decisions sections, and links to product scope plus product acceptance criteria.
- `docs/architecture/02-containers.md` has non-placeholder Product Links, Containers, Runtime Responsibilities, Data Ownership, and Open Decisions sections, and links to `docs/architecture/01-system-context.md` plus product acceptance criteria.
- `docs/architecture/03-quality-attributes.md` has non-placeholder Product Links, Availability, Performance, Security, Observability, and Tradeoffs sections, and links to containers plus product acceptance criteria.
- Backend modules link to API, schema, external services, and acceptance criteria.
- Data model design is checked against `references/data-model-design-checklist.md` for product traceability, identity, constraints, state/concurrency, query paths/indexes, migration/backfill, retention/audit, and verification coverage.
- Backend operability is checked against `references/backend-operability-checklist.md` for service levels, observability signals, configuration and secrets, runtime controls, operational logs, and runbooks.
- `docs/backend/01-modules.md` has non-placeholder Product Links, Architecture Links, Modules, API Ownership, Failure Modes, and Open Decisions sections, and links to architecture docs, API docs, `docs/backend/02-data-model.md`, `docs/backend/03-external-services.md`, and product acceptance criteria.
- `docs/backend/02-data-model.md` has non-placeholder Product Links, Owners, Entities, State Machines, Constraints, Indexes, and Migrations sections, and links to backend modules, API docs, and product acceptance criteria.
- `docs/backend/03-external-services.md` has non-placeholder Product Links, Dependencies, Contracts, Retries, Timeouts, Authentication, and Observability sections, and links to backend modules, API docs, and product acceptance criteria.
- Frontend modules link to UI, API, state, and acceptance criteria.
- `docs/frontend/01-modules.md` has non-placeholder Product Links, UI Links, Modules, State Ownership, Routes, and Open Decisions sections, and links to UI docs, API docs, `docs/frontend/02-api-consumption.md`, and product acceptance criteria.
- `docs/frontend/02-api-consumption.md` has non-placeholder Product Links, API Links, Consumption Map, Loading States, and Error Actions sections, and links to frontend modules, API docs, and product acceptance criteria.
- Test strategy is checked against `references/test-strategy-checklist.md` for acceptance traceability, test portfolio, automation and feedback, test data and environments, non-functional verification, and evidence maintenance.
- `docs/tests/01-strategy.md` has non-placeholder Product Links, Acceptance Links, Test Layers, Risk Coverage, and Non-Functional Checks sections, and links to product acceptance criteria, API docs, and architecture/backend/frontend design docs.
- `docs/tests/02-acceptance-matrix.md` has non-placeholder Matrix and Uncovered Criteria sections, maps unique product-defined `A-NNN` acceptance criteria to design, API endpoint contract, and test sources with local Markdown links whose fragments match row IDs when present, or lists explicitly uncovered product-defined acceptance IDs.
- Implementation readiness is checked against `references/implementation-readiness-checklist.md` for Ready task contracts, Definition of Done, verification plans, change integration, agent handoff, and supply-chain evidence.
- `docs/development/01-roadmap.md` has non-placeholder Product Links, Milestones, Sequencing, Risks, and Deferred Scope sections, links to product scope plus product acceptance criteria, and uses a Milestones table with `TASK-NNN` `ID`, `Status`, and `Milestone`.
- `docs/development/02-task-board.md` has non-placeholder Task Table, Status Policy, and Traceability Rules sections, uses `TASK-NNN` IDs matching roadmap milestones, links Product, Design, and API fields to matching source domains, and links tasks to product-defined `A-NNN` acceptance IDs mapped in `docs/tests/02-acceptance-matrix.md` with matching fragments when present.
- ADR files under `docs/decisions/` use unique `NNN-<slug>.md` names.
- ADR trigger, context, options, rationale, consequences, lifecycle, traceability, and indexing satisfy `references/architecture-decision-record-checklist.md`.
- ADRs have context, decision, consequences, and references.
- ADR `References` sections link to existing local Markdown source documents.
- Each non-template Markdown document is indexed by the README in the same directory.
- No document contains `governance:scaffold-placeholder`.

Run:

```bash
bin/governance verify <target> --check --json
bin/governance verify <target> --json
```

## Stop Conditions

- A design needs an API field not present in product or acceptance sources.
- A design needs a DB table or field without documented ownership.
- A design changes product meaning.
- An external dependency is assumed but not documented.
- `docs/unresolved.md` has any blocking row.
