---
name: designing-ui-interactions
description: Use when deriving UI interaction models, user flows, screens, states, user-visible errors, accessibility expectations, or design-asset interpretation from product and acceptance specs.
---

# Designing UI Interactions

UI interaction design turns product behavior into user-visible flows and states before frontend implementation starts.

Read `references/frontend-interaction-checklist.md` before writing UI interaction models, accessibility expectations, component behavior, user-visible error behavior, or performance-sensitive flow notes.

## Required Context

- `docs/product/core/PRD.md`
- structured product chapters and acceptance criteria
- `docs/api/00-conventions.md` and `docs/api/error-codes.md` when API behavior exists
- imported design assets or notes, if present
- `docs/unresolved.md`

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --check --json` when `docs/ui/01-interaction-model.md` is missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Read `references/frontend-interaction-checklist.md`.
4. Replace scaffold placeholders in `docs/ui/01-interaction-model.md` with product-derived content.
5. Derive primary flows from actors, goals, triggers, success paths, and acceptance criteria.
6. Define screens for each flow, including entry points, exits, permissions, and empty states.
7. Map loading, disabled, empty, success, validation-error, permission-error, retryable-failure, and irreversible-action states.
8. Map user-visible errors to API error codes when API docs exist; otherwise register the missing contract in `docs/unresolved.md`.
9. Document accessibility expectations for keyboard flow, focus order, labels, contrast, status messages, and screen reader state against `references/frontend-interaction-checklist.md`.
10. Document component behavior, route/state assumptions, performance-sensitive interactions, and handoff evidence when relevant.
11. Link every flow, screen, state, and error claim to product scope or acceptance sources.

## Stop Conditions

- A flow changes product meaning.
- A screen or state has no product or acceptance source.
- Error handling needs an API code that is not documented.
- Accessibility behavior is unclear for a primary flow.
- Component behavior, route behavior, or performance-sensitive interaction behavior is unclear for a primary flow.
- Imported design assets conflict with product text.
