---
name: designing-data-models
description: Use when deriving database schemas, entity ownership, lifecycle states, indexes, idempotency constraints, or persistence rules from product and backend design.
---

# Designing Data Models

Data design must preserve product semantics and make runtime behavior testable.

## Required Decisions

- entity ownership
- table and field names
- lifecycle states
- uniqueness and idempotency constraints
- indexes and query patterns
- retention, soft delete, and audit behavior
- migration order

## Procedure

1. Start from product nouns and backend module ownership.
2. Define state machines before writing fields.
3. Add constraints for idempotency and cross-user isolation.
4. Document query paths that justify indexes.
5. Link schema choices to API contracts and acceptance criteria.

## Stop Conditions

- A field has unclear owner or source.
- State transitions are implicit.
- A uniqueness rule is needed but not documented.
- A migration would break existing data without a transition plan.
