---
name: executing-implementation-task
description: Use when implementing, verifying, blocking, or completing one Ready TASK-NNN item from a governed docs-as-code repository after product, design, API, test, and task-board sources exist.
---

# Executing Implementation Task

Implement exactly one traceable task without inventing product meaning.

Read `references/implementation-execution-checklist.md` before editing code, changing task status, or claiming `Done`.

## Required Context

- `docs/development/02-task-board.md`
- `docs/development/03-verification-log.md`
- `docs/agent-workflow/command-contract.md`
- linked Product, Design, API, Acceptance, and Verification sources for the selected `TASK-NNN`
- `docs/tests/02-acceptance-matrix.md`
- `docs/agent-workflow/task-handoff.md` when present
- repository `AGENTS.md` files that apply to changed paths

## Procedure

1. Run implementation readiness checks before code edits:

   ```bash
   bin/governance gate implementation . --json
   bin/governance verify . --check --json
   bin/governance implementation plan . --json
   ```

   Stop on `ok: false` and route repair through `verifying-governance-docs`.

2. Inspect `implementation plan --json` before editing. Its `decision_policy` is `execute_exactly_one_ready_task`; use `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `read_order`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `gate_command`, `verify_command`, and `refresh_command` to choose the task and repair blockers. Stop when `active_work.status` is not `ready`.
3. Select exactly one task row from `active_work.task_id` or the first actionable `tasks[]` item. Confirm it uses a stable `TASK-NNN` ID, links local Markdown Product, Design, API, Acceptance, and Verification sources, and references a product-defined `A-NNN` mapped in `docs/tests/02-acceptance-matrix.md`.
4. Read the selected task `read_order`, the acceptance matrix row, and the task handoff before editing implementation files.
5. Inspect existing code, tests, generated files, build scripts, and local conventions around the changed surface.
6. Keep edits limited to the selected task. Register missing requirements, conflicting docs, missing credentials, or unsafe dependency changes in `docs/unresolved.md` instead of guessing.
7. Implement in small coherent steps and add or update tests next to the changed behavior.
8. Run the task's verification commands. Prefer `local_commands[].argv`, `docs/agent-workflow/command-contract.md` `Argv` rows, and task-provided commands over reconstructed shell strings. Stop and ask before running any command-contract row with `Approval Required` set to `true` unless the task explicitly authorizes it.
9. Record command, result, date, notes, and evidence path in `docs/development/03-verification-log.md`.
10. Synchronize `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses.
11. Refresh `bin/governance implementation plan . --json` and confirm the selected task state, `gate_ok`, and evidence are consistent before claiming completion.
12. Mark `Done` only when code, tests, synchronized docs, local evidence, `references/implementation-readiness-checklist.md`, and `references/implementation-execution-checklist.md` are satisfied.

## Stop Conditions

- More than one task is being changed without explicit task-board grouping.
- The task is not `Ready`.
- `implementation plan --json` reports `active_work.status` other than `ready`.
- Required local Markdown sources are missing or contradictory.
- The acceptance ID is not mapped in `docs/tests/02-acceptance-matrix.md`.
- A required project command is missing from `docs/agent-workflow/command-contract.md`.
- A command-contract row with `Approval Required` set to `true` needs unapproved escalation.
- Verification cannot pass and no `Blocked`, `Deferred`, or unresolved follow-up is recorded.
