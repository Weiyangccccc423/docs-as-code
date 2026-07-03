---
name: designing-data-models
description: Use when deriving database schemas, entity ownership, lifecycle states, indexes, idempotency constraints, or persistence rules from product and backend design.
---

# Designing Data Models

Data design must preserve product semantics and make runtime behavior testable.

Read `references/backend-design-checklist.md` and `references/data-model-design-checklist.md` before writing data-model docs. Apply the backend checklist for module/API/runtime/test alignment and the data-model checklist for ownership, identity, constraints, concurrency, indexes, migration, retention, audit, and verification decisions.

## Required Decisions

- entity ownership
- table and field names
- lifecycle states
- uniqueness and idempotency constraints
- transaction boundaries and consistency expectations
- concurrency conflict handling
- indexes and query patterns
- retention, soft delete, and audit behavior
- migration order

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --check --json` when standard data-model files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Read `references/backend-design-checklist.md` and `references/data-model-design-checklist.md`.
4. Replace scaffold placeholders in data-model files with product-derived content.
5. Start from product nouns and backend module ownership.
6. Define state machines before writing fields.
7. Add constraints for idempotency and cross-user isolation.
8. Define transaction boundaries, consistency expectations, and concurrency conflict handling for each state-changing operation.
9. Document query paths that justify indexes.
10. Link schema choices to API contracts and acceptance criteria.
11. Re-check data ownership, lifecycle states, constraints, transaction boundaries, indexes, migrations, retention, audit, and tests against both checklists.

## Stop Conditions

- A field has unclear owner or source.
- State transitions are implicit.
- A uniqueness rule is needed but not documented.
- A state-changing operation lacks transaction or concurrency behavior.
- A migration would break existing data without a transition plan.
