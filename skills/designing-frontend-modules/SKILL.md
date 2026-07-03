---
name: designing-frontend-modules
description: Use when deriving frontend module boundaries, route ownership, UI state, API consumption, loading states, or user-visible error handling from product, UI, and API specs.
---

# Designing Frontend Modules

Frontend design translates product interaction and API contracts into implementable UI module boundaries without inventing behavior.

## Required Context

- `docs/product/core/PRD.md`
- structured product chapters and acceptance criteria
- `docs/ui/01-interaction-model.md`
- `docs/api/00-conventions.md`
- `docs/api/error-codes.md`
- `docs/api/endpoints/`
- `docs/unresolved.md`

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --check --json` when standard frontend files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and keep returned `next_actions` for later.
3. Replace scaffold placeholders in `docs/frontend/01-modules.md` and `docs/frontend/02-api-consumption.md` with product-derived content.
4. Derive frontend modules from UI flows, screens, routes, and acceptance criteria.
5. Assign state ownership for local, shared, server-derived, cached, optimistic, and persisted state.
6. Link every server-derived state and mutation to concrete API endpoint contracts.
7. Map loading, empty, disabled, stale, retrying, success, and error states to UI flows.
8. Map API error codes to user-visible copy, recovery actions, retry behavior, telemetry, and acceptance criteria.
9. Link frontend modules to UI, API, product, and acceptance sources.
10. Register unresolved route, state, endpoint, accessibility, or copy decisions in `docs/unresolved.md`.

## Stop Conditions

- A frontend state has no documented owner.
- A UI flow requires an endpoint not defined in `docs/api/endpoints/`.
- Error handling needs a code not registered in `docs/api/error-codes.md`.
- A route or screen changes product meaning.
- Accessibility behavior is unclear for a primary flow.
