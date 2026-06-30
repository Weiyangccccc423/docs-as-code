---
name: designing-data-models
description: Use when deriving database schemas, entity ownership, lifecycle states, indexes, idempotency constraints, or persistence rules from product and backend design.
---

# Designing Data Models

Data design must preserve product semantics and make runtime behavior testable.

Read `references/backend-design-checklist.md` before writing data-model docs. Apply its Data Model, API Contract, Runtime Flow, Observability and Security, and Acceptance and Tests checks.

## Required Decisions

- entity ownership
- table and field names
- lifecycle states
- uniqueness and idempotency constraints
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

2. Run `bin/governance scaffold design <target> --check --json` when standard data-model files are missing, then run it without `--check` when the plan is correct.
3. Read `references/backend-design-checklist.md`.
4. Replace scaffold placeholders in data-model files with product-derived content.
5. Start from product nouns and backend module ownership.
6. Define state machines before writing fields.
7. Add constraints for idempotency and cross-user isolation.
8. Document query paths that justify indexes.
9. Link schema choices to API contracts and acceptance criteria.
10. Re-check data ownership, lifecycle states, constraints, indexes, migrations, and tests against the backend checklist.

## Stop Conditions

- A field has unclear owner or source.
- State transitions are implicit.
- A uniqueness rule is needed but not documented.
- A migration would break existing data without a transition plan.
