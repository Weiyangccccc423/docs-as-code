# Phase 05: Verification and Drift Control

## Input

- Generated governance repository
- Product and design documents
- Optional code directories

## Skills

Load:

- `verifying-governance-docs`

## Procedure

1. Read `references/governance-verification-checklist.md` and use it as the rubric for command discipline, environment repair control, drift refresh, phase gates, repair ordering, traceability evidence, security and supply-chain sanity, and completion gates.

2. Run structural verification:

   ```bash
   bin/governance verify <target>
   ```

   For agent-controlled verification, prefer machine-readable output:

   ```bash
   bin/governance verify <target> --check --json
   bin/governance verify <target> --json
   ```

   Use `--check` when automation only needs findings and should not update `.governance/state.json`. Use the command without `--check` when recording `last_verification`. Use `findings[].code` for automation. Keep `errors` and `warnings` for human-readable summaries. When governance state is readable, both JSON forms include `local_commands` and `next_actions` for continuing from the verified state.

   When already inside an initialized target repository, prefer:

   ```bash
   bin/governance verify .
   ```

3. Run environment check:

   ```bash
   bin/governance env --strict --repair --check --target <target> --json
   ```

   Agents must treat `ok: false` as a stop condition. `--check` reports `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, and `repair_execution` without writing `.governance/env-repair.md` or installing packages. Use `repair_execution.status`, `repair_execution.can_auto_apply`, `repair_execution.install_attempted`, `repair_execution.install_failed`, `repair_execution.post_repair_missing_required`, `repair_execution.post_repair_missing_recommended`, and `repair_execution.next_step` for branching. Sort `repair_actions` by `sequence`; run actions with `argv` only when approved by policy, and route `manual-repair` actions to the user. If `needs_escalation` is true or any `repair_commands[].approval_required` value is true, do not run `repair_commands`, `install_commands`, or `install_command` without explicit approval. Treat `applied_but_unresolved` as a stop state before retrying repairs.
   When governance state is readable and the environment result is `ok: true`, JSON includes `local_commands` and `next_actions` for continuing from the checked target state.

4. If the target project has a Makefile, run its verification entry:

   ```bash
   make verify-governance
   make verify-check
   make governance-status
   make check-env
   make repair-env-check
   ```

   `governance-status` runs `bin/governance status . --json`; on success, its payload includes `local_commands` with `cwd`, `argv`, `writes_state`, and `approval_required` so resumed agents can rediscover and execute the target-local `make` command contract without re-running initialization. Readable-state `gate --json` payloads include the same `local_commands` contract, and passing gates also include `next_actions`. Successful state-writing `product mark-ready --json` and `advance --json` payloads include both fields for the next state transition. Each `next_actions` entry includes `sequence`, `success_condition`, and either `preflight_for` or `requires_action`; resumed agents must sort by `sequence` and run apply actions only after the named preflight returns `ok: true`.

5. If verification reports target-local runtime or workflow-pack snapshot drift, inspect the refresh plan from a trusted source workflow-pack checkout before writing repairs:

   ```bash
   bin/governance runtime refresh <target> --check --json
   bin/governance runtime refresh <target> --json
   ```

   Treat the `--check` form as the no-write repair plan. After the write-mode refresh succeeds, use returned `local_commands[].argv` for target-local checks and `next_actions[].argv` for the next workflow transition.

6. Before implementation starts, run the implementation gate:

   ```bash
   bin/governance advance implementation <target> --check --json
   bin/governance advance implementation <target> --json
   ```

   `advance` records adjacent transitions one phase at a time and cannot skip phases; use `gate implementation <target> --json` for repeated checks. The implementation gate requires the standard handoff files from Phase 04, including the API endpoint index, at least one endpoint contract, task board, and verification log; arbitrary Markdown in a docs domain is not enough. The gate also exposes domain readiness requirements for repair routing: `architecture_design_ready`, `api_contracts_ready`, `backend_design_ready`, `frontend_design_ready`, `verification_strategy_ready`, and `delivery_plan_ready`.

7. Read `references/implementation-execution-checklist.md` before assigning an implementation agent to a `Ready` `TASK-NNN`. Use it as the execution rubric for task intake, scope control, implementation loop, verification commands, evidence updates, security and supply-chain handling, and completion status.

8. Before implementation starts, confirm:
   - no unregistered docs directories
   - no stale reserved markers
   - no `governance:scaffold-placeholder` markers or structured scaffold placeholders such as `A-NNN`, `TASK-NNN`, `METHOD /product-derived-path`, `NN-*`, or `field_name`
   - no `docs/unresolved.md` rows with a blocking `Blocking Scope`
   - no `docs/unresolved.md` rows with missing `ID`, `Domain`, or `Description`, invalid `U-NNN` IDs, or duplicate unresolved IDs
   - no `docs/glossary.md` rows with missing `Term`, `Meaning`, or `Source`, duplicate terms, or missing local Markdown sources
   - no non-template Markdown files missing from their same-directory README
   - no explicit local Markdown link pointing to a missing file
   - product chapter filenames use `NN-<slug>.md` with unique `NN` prefixes
   - a dedicated `NN-*acceptance*.md` product chapter exists before design derivation or implementation handoff and exposes stable unique `A-NNN` criteria IDs
   - `docs/api/00-conventions.md` has non-placeholder Product Links, HTTP Conventions, Authentication, Idempotency, Compatibility, and Open Decisions sections, and links to product scope plus product acceptance criteria
   - `docs/api/error-codes.md` has non-placeholder Product Links, Error Taxonomy, Error Codes, Retry Semantics, and Frontend Handling sections, and links to product scope plus product acceptance criteria
   - `docs/api/changelog.md` has non-placeholder Change Log and Compatibility Notes sections
   - API endpoint contract filenames under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes
   - API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, error, upstream link, and frontend consumer sections
   - API endpoint `Method and Path` sections contain an HTTP method and absolute path
   - API endpoint `Error Codes` sections reference `docs/api/error-codes.md`
   - API endpoint `Upstream Links` sections reference existing local source Markdown
   - API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption Markdown
   - product, API, architecture, backend, frontend, tests, and development docs link to each other
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
   - `docs/tests/02-acceptance-matrix.md` uses `Acceptance`, `Design`, `API`, and `Test` columns with unique `A-NNN` acceptance IDs defined in referenced product acceptance chapters, uses matching Acceptance link fragments when present, maps every product-defined `A-NNN` or lists it under Uncovered Criteria using product-defined IDs only, and uses local Markdown links to matching source docs; the `API` column must link concrete endpoint contracts under `docs/api/endpoints/NN-<slug>.md`
   - ADR files under `docs/decisions/` use unique `NNN-<slug>.md` names
   - ADRs under `docs/decisions/` include non-placeholder Context, Decision, Consequences, and References sections with local Markdown source links
   - `docs/development/01-roadmap.md` has non-placeholder Product Links, Milestones, Sequencing, Risks, and Deferred Scope sections, and links to product scope plus product acceptance criteria
   - roadmap Milestones table uses `ID`, `Status`, and `Milestone`, has at least one row, has unique `TASK-NNN` IDs, and uses standard task status values
   - roadmap tables with `ID` and `Status` columns have matching task board rows, no extra task board IDs, and agree with same-ID task board statuses
   - `docs/development/02-task-board.md` has non-placeholder Task Table, Status Policy, and Traceability Rules sections
   - `docs/development/03-verification-log.md` has non-placeholder Verification Runs, Artifacts, and Open Follow-ups sections, and its Verification Runs table uses `Task`, `Command`, `Result`, `Date`, and `Notes` columns
   - task board items have `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
   - task board `Status` values are one of `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done`, or `Deferred`
   - task board items marked `Blocked` cite an existing unresolved item ID and link to `docs/unresolved.md`
   - task board items marked `Done` link to existing local Markdown verification evidence, and when they link `docs/development/03-verification-log.md`, the log has a matching `TASK-NNN` run row
   - task board item IDs are unique, use `TASK-NNN`, and match roadmap milestones
   - task board `Product`, `Design`, `API`, and `Acceptance` fields point to existing local Markdown files in the matching source domains
   - task board `Acceptance` fields include an `A-NNN` ID defined in the referenced product acceptance chapter, mapped in `docs/tests/02-acceptance-matrix.md`, a matching link fragment when present, and a product acceptance chapter reference matching `docs/product/NN-*acceptance*.md`
   - at least one task board item is `Ready` before implementation starts

## Output

A verification report and a list of fixes, or a clean governance baseline.

## Verification

Verification is complete when the relevant checks in the procedure pass and any state-changing command was preceded by its `--check --json` preflight. Source workflow-pack maintainers must also run:

```bash
make verify-pack
make release-check
python3 scripts/release_readiness.py --json
```

Command discipline, environment repair control, drift refresh, phase gates, repair ordering, traceability evidence, security and supply-chain sanity, and completion gates must satisfy `references/governance-verification-checklist.md`. Source workflow-pack release handoff must satisfy `references/release-readiness-checklist.md`. Single-task implementation execution must satisfy `references/implementation-execution-checklist.md` before a task is marked `Done`.

## Stop Conditions

- Verification fails on source-of-truth conflicts.
- The acceptance matrix lacks Matrix or Uncovered Criteria content.
- ADR identity is unstable because filenames are unnumbered or duplicate numbered.
- The task board claims completion without evidence.
- The task board includes a `TASK-NNN` item absent from roadmap milestones.
- The task board references an acceptance ID not mapped in the acceptance matrix.
- The task board lacks status policy or traceability rules.
- The roadmap lacks a valid milestone table.
- Roadmap status conflicts with task board status.
- A generated document is not indexed by its parent README.
