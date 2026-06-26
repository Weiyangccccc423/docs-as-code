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
10. Create or complete `docs/tests/02-acceptance-matrix.md` with `Acceptance`, `Design`, `API`, and `Test` columns.
11. Create ADRs in `docs/decisions/` for cross-module or high-cost decisions.
12. Keep all design documents linked to product and acceptance sources.
13. Update the same-directory `README.md` for every new Markdown document, except underscore-prefixed templates such as `_template.md`.

## Output

Design documents sufficient for creating a task board without guessing product meaning.

## Verification

- API endpoints have request, response, error code, auth, and idempotency notes.
- API endpoint contract files under `docs/api/endpoints/` use `NN-<slug>.md` with unique `NN` prefixes.
- API endpoint contract files include non-placeholder method/path, auth, idempotency, request, response, error code, upstream link, and frontend consumer sections.
- API endpoint `Method and Path` sections contain an HTTP method and absolute path.
- API endpoint `Error Codes` sections reference `docs/api/error-codes.md`.
- API endpoint `Upstream Links` sections reference existing local source Markdown.
- API endpoint `Frontend Consumers` sections reference existing local UI or frontend API-consumption Markdown.
- `docs/architecture/01-system-context.md` links to product scope and product acceptance criteria.
- Backend modules link to API, schema, external services, and acceptance criteria.
- `docs/backend/01-modules.md` links to API docs, `docs/backend/02-data-model.md`, `docs/backend/03-external-services.md`, and product acceptance criteria.
- Frontend modules link to UI, API, state, and acceptance criteria.
- `docs/frontend/01-modules.md` links to UI docs, API docs, `docs/frontend/02-api-consumption.md`, and product acceptance criteria.
- `docs/tests/01-strategy.md` links to product acceptance criteria, API docs, and architecture/backend/frontend design docs.
- `docs/tests/02-acceptance-matrix.md` maps acceptance criteria to design, API, and test sources with local Markdown links.
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
