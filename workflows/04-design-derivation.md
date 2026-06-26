# Phase 04: Design Derivation

## Input

- Structured product documents
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

1. Run governance verification and stop if `docs/unresolved.md` contains blocking rows:

   ```bash
   bin/governance verify <target> --json
   ```

2. Create `docs/architecture/` views:
   - system context
   - containers
   - major quality attributes
   - external dependencies
   - deployment assumptions
3. Create `docs/api/`:
   - `00-conventions.md`
   - `endpoints/README.md`
   - endpoint files
   - `error-codes.md`
   - `changelog.md`
4. Create `docs/ui/` from product interaction needs or imported design assets.
5. Create `docs/backend/` implementation design:
   - architecture overview
   - module documents
   - database schema
   - external service contracts
6. Create database and lifecycle design:
   - entity ownership
   - state machines
   - idempotency constraints
   - indexes and migration order
7. Create `docs/frontend/` implementation design:
   - architecture overview
   - module documents
   - API consumption map
   - error action map
8. Create ADRs in `docs/decisions/` for cross-module or high-cost decisions.
9. Keep all design documents linked to product and acceptance sources.
10. Update the same-directory `README.md` for every new Markdown document, except underscore-prefixed templates such as `_template.md`.

## Output

Design documents sufficient for creating a task board without guessing product meaning.

## Verification

- API endpoints have request, response, error code, auth, and idempotency notes.
- Backend modules link to API, schema, external services, and acceptance criteria.
- Frontend modules link to UI, API, state, and acceptance criteria.
- ADRs have context, decision, consequences, and references.
- Each non-template Markdown document is indexed by the README in the same directory.

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
