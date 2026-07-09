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
3. Run `bin/governance design data-model-authoring <target> --json`, inspect `authoring_summary` (`task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count`), and use `authoring_tasks[]` by `sequence` before writing data-model content. The payload's `decision_policy` is `do_not_guess_data_model`; the payload and each task list `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, and `stop_condition`, target `documents`, required `sections`, `required_links` with `required_links[].status`, `link_repair_actions` for non-satisfied links, including `repair_strategy`, `verify_command`, and `refresh_command`, unresolved `open_decisions` such as `entity_ownership`, `transaction_boundaries`, `migration_order`, and `rollback_strategy`, `specialist_skills` including `database-designer`, `database-schema-designer`, `migration-architect`, `senior-backend`, and `senior-security`, and read-only command steps verify-data-model-authoring and refresh-data-model-authoring. Follow `skill_loading_plan.steps[]` by `sequence`; load authority-routing skills from the agent environment or follow `missing_policy: load_from_agent_environment_or_stop_before_guessing`.
4. Read `references/backend-design-checklist.md` and `references/data-model-design-checklist.md`.
5. Replace scaffold placeholders in data-model files with product-derived content.
6. Start from product nouns and backend module ownership.
7. Define state machines before writing fields.
8. Add constraints for idempotency and cross-user isolation.
9. Define transaction boundaries, consistency expectations, and concurrency conflict handling for each state-changing operation.
10. Document query paths that justify indexes.
11. Link schema choices to API contracts and acceptance criteria.
12. Re-check data ownership, lifecycle states, constraints, transaction boundaries, indexes, migrations, retention, audit, and tests against both checklists.

## Stop Conditions

- A field has unclear owner or source.
- State transitions are implicit.
- A uniqueness rule is needed but not documented.
- A state-changing operation lacks transaction or concurrency behavior.
- A migration would break existing data without a transition plan.
