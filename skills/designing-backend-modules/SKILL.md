---
name: designing-backend-modules
description: Use when deriving backend module boundaries, service responsibilities, runtime flows, external dependencies, or implementation design documents from product, API, or architecture specs.
---

# Designing Backend Modules

Use architecture first, then module design.

## Required Context

- `docs/product/core/PRD.md`
- structured product chapters and acceptance criteria
- `docs/architecture/`
- `docs/api/`
- `docs/unresolved.md`

Read `references/backend-design-checklist.md` when the module touches data, async work, external services, or auth.

## Procedure

1. Identify module responsibility and boundaries.
2. Name upstream and downstream modules.
3. Link owned API endpoints from `docs/api/`.
4. Define data ownership and lifecycle states.
5. Document external dependencies, retries, timeouts, and failure modes.
6. Define observability and auth behavior.
7. Link acceptance criteria and test strategy.

## Stop Conditions

- A module needs an API field not defined in `docs/api/`.
- A module needs a table or field not defined in the data model.
- A module changes product meaning.
- An external dependency lacks an owner or contract.
