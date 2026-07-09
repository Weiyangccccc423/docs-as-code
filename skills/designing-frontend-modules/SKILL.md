---
name: designing-frontend-modules
description: Use when deriving frontend module boundaries, route ownership, UI state, API consumption, loading states, or user-visible error handling from product, UI, and API specs.
---

# Designing Frontend Modules

Frontend design translates product interaction and API contracts into implementable UI module boundaries without inventing behavior.

Read `references/frontend-interaction-checklist.md` before writing frontend module, route, state ownership, API-consumption, user-visible error, accessibility, or performance-sensitive frontend design.

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

2. Run `bin/governance scaffold design <target> --check --json` when standard frontend files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Run `bin/governance design frontend-authoring <target> --json`, inspect `authoring_summary` (`task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count`), and follow `authoring_tasks[]` by `sequence`. The payload's `decision_policy` is `do_not_guess_frontend_behavior`; each task lists `skill_requirements`, `authority_skill_requirements`, authority-routing `missing_policy`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, and `stop_condition`, target frontend module and API-consumption `documents`, required `sections`, `required_links` with `required_links[].status`, `link_repair_actions` for non-satisfied links, including `repair_strategy`, `verify_command`, and `refresh_command`, unresolved `open_decisions` such as `state_ownership` and `error_actions`, `specialist_skills` including `senior-frontend`, `a11y-audit`, and `performance-profiler`, and read-only command steps verify-frontend-authoring and refresh-frontend-authoring.
4. Read `references/frontend-interaction-checklist.md`.
5. Replace scaffold placeholders in `docs/frontend/01-modules.md` and `docs/frontend/02-api-consumption.md` with product-derived content.
6. Derive frontend modules from UI flows, screens, routes, and acceptance criteria.
7. Assign state ownership for local, shared, server-derived, cached, optimistic, persisted, and URL/route state.
8. Link every server-derived state and mutation to concrete API endpoint contracts.
9. Map loading, empty, disabled, stale, retrying, success, and error states to UI flows.
10. Map API error codes to user-visible copy, recovery actions, retry behavior, telemetry, and acceptance criteria.
11. Document route access, deep links, redirects, cache invalidation, performance-sensitive screens, and accessibility handoff expectations when relevant.
12. Link frontend modules to UI, API, product, and acceptance sources.
13. Register unresolved route, state, endpoint, accessibility, performance, or copy decisions in `docs/unresolved.md`.

## Stop Conditions

- A frontend state has no documented owner.
- A UI flow requires an endpoint not defined in `docs/api/endpoints/`.
- Error handling needs a code not registered in `docs/api/error-codes.md`.
- A route or screen changes product meaning.
- Accessibility behavior is unclear for a primary flow.
- State ownership, cache invalidation, or performance-sensitive behavior is unclear for a primary flow.
