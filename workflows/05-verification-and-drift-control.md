# Phase 05: Verification and Drift Control

## Input

- Generated governance repository
- Product and design documents
- Optional code directories

## Skills

Load:

- `verifying-governance-docs`

## Procedure

1. Run structural verification:

   ```bash
   bin/governance verify <target>
   ```

   For agent-controlled verification, prefer machine-readable output:

   ```bash
   bin/governance verify <target> --json
   ```

   Use `findings[].code` for automation. Keep `errors` and `warnings` for human-readable summaries.

   When already inside an initialized target repository, prefer:

   ```bash
   bin/governance verify .
   ```

2. Run environment check:

   ```bash
   bin/governance env --strict --repair --target <target>
   ```

   Agents may use `--json` and must treat `ok: false` as a stop condition. If `needs_escalation` is true, do not run the reported install command without explicit approval.

3. If the target project has a Makefile, run its verification entry:

   ```bash
   make verify-governance
   ```

4. Before implementation starts, run the implementation gate:

   ```bash
   bin/governance advance implementation <target> --json
   ```

5. Before implementation starts, confirm:
   - no unregistered docs directories
   - no stale reserved markers
   - no `governance:scaffold-placeholder` markers
   - no `docs/unresolved.md` rows with a blocking `Blocking Scope`
   - no `docs/unresolved.md` rows with missing `ID`, `Domain`, or `Description`, invalid `U-NNN` IDs, or duplicate unresolved IDs
   - no `docs/glossary.md` rows with missing `Term`, `Meaning`, or `Source`, duplicate terms, or missing local Markdown sources
   - no non-template Markdown files missing from their same-directory README
   - no explicit local Markdown link pointing to a missing file
   - product chapter filenames use `NN-<slug>.md` with unique `NN` prefixes
   - a dedicated `NN-*acceptance*.md` product chapter exists before design derivation or implementation handoff and exposes stable `A-NNN` criteria IDs
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
   - `docs/tests/02-acceptance-matrix.md` uses `Acceptance`, `Design`, `API`, and `Test` columns with unique `A-NNN` acceptance IDs defined in referenced product acceptance chapters and local Markdown links to matching source docs
   - ADR files under `docs/decisions/` use unique `NNN-<slug>.md` names
   - ADRs under `docs/decisions/` include non-placeholder Context, Decision, Consequences, and References sections with local Markdown source links
   - `docs/development/01-roadmap.md` has non-placeholder Product Links, Milestones, Sequencing, Risks, and Deferred Scope sections, and links to product scope plus product acceptance criteria
   - roadmap Milestones table uses `ID`, `Status`, and `Milestone`, has at least one row, has unique `TASK-NNN` IDs, and uses standard task status values
   - roadmap tables with `ID` and `Status` columns agree with same-ID task board statuses
   - `docs/development/02-task-board.md` has non-placeholder Task Table, Status Policy, and Traceability Rules sections
   - task board items have `ID`, `Status`, `Task`, `Product`, `Design`, `API`, `Acceptance`, and `Verification`
   - task board `Status` values are one of `Backlog`, `Ready`, `In Progress`, `Blocked`, `Done`, or `Deferred`
   - task board items marked `Blocked` cite an existing unresolved item ID and link to `docs/unresolved.md`
   - task board items marked `Done` link to existing local Markdown verification evidence
   - task board item IDs are unique and use `TASK-NNN`
   - task board `Product`, `Design`, `API`, and `Acceptance` fields point to existing local Markdown files
   - task board `Acceptance` fields include an `A-NNN` ID defined in the referenced product acceptance chapter and a product acceptance chapter reference matching `docs/product/NN-*acceptance*.md`
   - at least one task board item is `Ready` before implementation starts

## Output

A verification report and a list of fixes, or a clean governance baseline.

## Stop Conditions

- Verification fails on source-of-truth conflicts.
- The acceptance matrix lacks Matrix or Uncovered Criteria content.
- ADR identity is unstable because filenames are unnumbered or duplicate numbered.
- The task board claims completion without evidence.
- The task board lacks status policy or traceability rules.
- The roadmap lacks a valid milestone table.
- Roadmap status conflicts with task board status.
- A generated document is not indexed by its parent README.
