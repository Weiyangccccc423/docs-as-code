# Phase 04: Design Derivation

## Input

- Structured product documents
- Dedicated acceptance criteria product chapter
- `docs/unresolved.md`
- `docs/glossary.md`

## Skills

Load according to the design track:

- System architecture: `designing-system-architecture`
- API contract: `designing-api-contracts`
- Backend modules: `designing-backend-modules`
- Data model: `designing-data-models`
- Architecture decisions: `capturing-architecture-decisions`
- Frontend modules: use UI/API docs first, then frontend-specific local skill if available
- Governance check: `verifying-governance-docs`

## Procedure

1. Confirm product structure is ready for design derivation:

   ```bash
   bin/governance advance design-derivation <target> --json
   ```

   The gate requires at least one `docs/product/NN-*acceptance*.md` chapter.

2. Create the standard design document scaffold when files are missing:

   ```bash
   bin/governance scaffold design <target> --json
   ```

   Replace `governance:scaffold-placeholder` markers with product-derived content before implementation handoff.

3. Create or complete `docs/architecture/` views:
   - system context
   - containers
   - major quality attributes
   - external dependencies
   - deployment assumptions
4. Create or complete `docs/api/`:
   - `00-conventions.md`
   - `endpoints/README.md`
   - endpoint files
   - `error-codes.md`
   - `changelog.md`
5. Create or complete `docs/ui/` from product interaction needs or imported design assets.
6. Create or complete `docs/backend/` implementation design:
   - architecture overview
   - module documents
   - database schema
   - external service contracts
7. Create database and lifecycle design:
   - entity ownership
   - state machines
   - idempotency constraints
   - indexes and migration order
8. Create or complete `docs/frontend/` implementation design:
   - architecture overview
   - module documents
   - API consumption map
   - error action map
9. Create or complete `docs/tests/01-strategy.md` from product acceptance, API contracts, and architecture/backend/frontend design risks.
10. Create or complete `docs/tests/02-acceptance-matrix.md` with Matrix and Uncovered Criteria sections, and `Acceptance`, `Design`, `API`, and `Test` columns; every `Acceptance` row must include a unique product-defined `A-NNN` ID.
11. Create or complete `docs/development/01-roadmap.md` with product links, a Milestones table using `TASK-NNN` `ID`, `Status`, and `Milestone`, sequencing, risks, and deferred scope.
12. Create or complete `docs/development/02-task-board.md` with Task Table, Status Policy, and Traceability Rules sections; task IDs must use `TASK-NNN`, cover roadmap milestone IDs, and `Acceptance` fields must include `A-NNN` IDs defined in referenced product acceptance chapters.
13. Create ADRs in `docs/decisions/` for cross-module or high-cost decisions, named as unique `NNN-<slug>.md` files.
14. Keep all design and planning documents linked to product and acceptance sources.
15. Update the same-directory `README.md` for every new Markdown document, except underscore-prefixed templates such as `_template.md`.

## Output

Design documents sufficient for creating a task board without guessing product meaning.

## Verification

- API endpoints have request, response, error code, auth, and idempotency notes.
- `docs/api/00-conventions.md` has non-placeholder Product Links, HTTP Conventions, Authentication, Idempotency, Compatibility, and Open Decisions sections, and links to product scope plus product acceptance criteria.
- `docs/api/error-codes.md` has non-placeholder Product Links, Error Taxonomy, Error Codes, Retry Semantics, and Frontend Handling sections, and links to product scope plus product acceptance criteria.
- `docs/api/changelog.md` has non-placeholder Change Log and Compatibility Notes sections.
- API endpoint contract files under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes.
- API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, error code, upstream link, and frontend consumer sections.
- API endpoint `Method and Path` sections contain an HTTP method and absolute path.
- API endpoint `Error Codes` sections reference `docs/api/error-codes.md`.
- API endpoint `Upstream Links` sections reference existing local source Markdown.
- API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption Markdown.
- `docs/ui/01-interaction-model.md` has non-placeholder Product Links, Primary Flows, Screens, States, Errors, and Accessibility sections, and links to product scope plus product acceptance criteria.
- `docs/architecture/01-system-context.md` has non-placeholder Product Links, Actors, External Systems, Trust Boundaries, and Open Decisions sections, and links to product scope plus product acceptance criteria.
- `docs/architecture/02-containers.md` has non-placeholder Product Links, Containers, Runtime Responsibilities, Data Ownership, and Open Decisions sections, and links to `docs/architecture/01-system-context.md` plus product acceptance criteria.
- `docs/architecture/03-quality-attributes.md` has non-placeholder Product Links, Availability, Performance, Security, Observability, and Tradeoffs sections, and links to containers plus product acceptance criteria.
- Backend modules link to API, schema, external services, and acceptance criteria.
- `docs/backend/01-modules.md` has non-placeholder Product Links, Architecture Links, Modules, API Ownership, Failure Modes, and Open Decisions sections, and links to architecture docs, API docs, `docs/backend/02-data-model.md`, `docs/backend/03-external-services.md`, and product acceptance criteria.
- `docs/backend/02-data-model.md` has non-placeholder Product Links, Owners, Entities, State Machines, Constraints, Indexes, and Migrations sections, and links to backend modules, API docs, and product acceptance criteria.
- `docs/backend/03-external-services.md` has non-placeholder Product Links, Dependencies, Contracts, Retries, Timeouts, Authentication, and Observability sections, and links to backend modules, API docs, and product acceptance criteria.
- Frontend modules link to UI, API, state, and acceptance criteria.
- `docs/frontend/01-modules.md` has non-placeholder Product Links, UI Links, Modules, State Ownership, Routes, and Open Decisions sections, and links to UI docs, API docs, `docs/frontend/02-api-consumption.md`, and product acceptance criteria.
- `docs/frontend/02-api-consumption.md` has non-placeholder Product Links, API Links, Consumption Map, Loading States, and Error Actions sections, and links to frontend modules, API docs, and product acceptance criteria.
- `docs/tests/01-strategy.md` has non-placeholder Product Links, Acceptance Links, Test Layers, Risk Coverage, and Non-Functional Checks sections, and links to product acceptance criteria, API docs, and architecture/backend/frontend design docs.
- `docs/tests/02-acceptance-matrix.md` has non-placeholder Matrix and Uncovered Criteria sections, maps unique product-defined `A-NNN` acceptance criteria to design, API, and test sources with local Markdown links.
- `docs/development/01-roadmap.md` has non-placeholder Product Links, Milestones, Sequencing, Risks, and Deferred Scope sections, links to product scope plus product acceptance criteria, and uses a Milestones table with `TASK-NNN` `ID`, `Status`, and `Milestone`.
- `docs/development/02-task-board.md` has non-placeholder Task Table, Status Policy, and Traceability Rules sections, uses `TASK-NNN` IDs matching roadmap milestones, and links tasks to product-defined `A-NNN` acceptance IDs.
- ADR files under `docs/decisions/` use unique `NNN-<slug>.md` names.
- ADRs have context, decision, consequences, and references.
- ADR `References` sections link to existing local Markdown source documents.
- Each non-template Markdown document is indexed by the README in the same directory.
- No document contains `governance:scaffold-placeholder`.

Run:

```bash
bin/governance verify <target> --json
```

## Stop Conditions

- A design needs an API field not present in product or acceptance sources.
- A design needs a DB table or field without documented ownership.
- A design changes product meaning.
- An external dependency is assumed but not documented.
- `docs/unresolved.md` has any blocking row.
