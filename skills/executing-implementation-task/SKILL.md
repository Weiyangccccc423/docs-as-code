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
- `docs/development/04-implementation-evidence.md` when prior runs exist
- `docs/agent-workflow/command-contract.md`
- `docs/agent-workflow/project-environment.json`
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

2. Inspect `implementation plan --json` before editing. Its `decision_policy` is `execute_exactly_one_ready_task`; use `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `read_order`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `gate_command`, `start_command`, `verify_command`, `closeout_command`, and `refresh_command` to choose the task and repair blockers. Stop successfully when `active_work.status` is `complete`; stop for repair when it is not `ready`, `in_progress`, or `complete`.
3. Select exactly one task row from `active_work.task_id` or the first actionable `tasks[]` item. Confirm it uses a stable `TASK-NNN` ID, links local Markdown Product, Design, API, Acceptance, and Verification sources, and references a product-defined `A-NNN` mapped in `docs/tests/02-acceptance-matrix.md`.
4. Claim a `Ready` task before editing code with `bin/governance implementation start . --task TASK-NNN --json`, then run the returned apply command or `bin/governance implementation start . --task TASK-NNN --apply --json` when `status_update_plan.can_auto_apply` is true. If the task is already `In Progress`, treat start as an idempotent resume check.
5. Read the selected task `read_order`, the acceptance matrix row, and the task handoff before editing implementation files.
6. Inspect existing code, tests, generated files, build scripts, and local conventions around the changed surface.
7. Keep edits limited to the selected task. Register missing requirements, conflicting docs, missing credentials, or unsafe dependency changes in `docs/unresolved.md` instead of guessing.
8. Implement in small coherent steps and add or update tests next to the changed behavior.
9. Load `configuring-project-runtime`, run `project-env plan`, and register each reviewed tool through `project-env register --reviewed --check` plus apply before registering task commands with those environment IDs in `docs/agent-workflow/command-contract.md`. Preflight with `bin/governance implementation verify . --task TASK-NNN --command command-name --check --json`; require `environment_readiness.ok: true` and inspect `environment_contract`, `required_tools`, observed versions, `repair_actions`, `repair_decision`, `would_write`, and `execute_command`. Only allowlisted bounded version probes may execute during preflight; the task command and evidence writes remain disabled. Run `repair_preflight_command` for `governance-env`; for `reviewed-command`, run `project-env repair --check`, request explicit approval before its apply action, and require completed `.governance/project-environment-repairs.json` evidence plus a passing post-repair version probe. Follow reviewed instructions for `manual`, and register unknown tools without inventing packages. Do not reconstruct a shell string.
10. The evidence runner refuses `Approval Required: true` rows and requires `--allow-writes` for `Writes State: true` rows. It derives the result from the return code, enforces timeout and output bounds, appends immutable history to `docs/development/04-implementation-evidence.md`, and upserts the current `(Task, Command)` summary in `docs/development/03-verification-log.md`.
11. Synchronize `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses through start and closeout apply when available.
12. Refresh `bin/governance implementation plan . --json` and confirm the selected task state, `gate_ok`, and evidence are consistent before claiming completion.
13. Run `bin/governance implementation closeout . --task TASK-NNN --json` before marking `Done`. Its `decision_policy` is `do_not_mark_done_without_passing_evidence`; require `evidence_summary.all_verification_results_passing: true` in addition to complete local evidence links and synchronized task/roadmap status. When `status_update_plan.can_auto_apply` is true, run `status_update_plan.apply_command.argv` or `bin/governance implementation closeout . --task TASK-NNN --apply --json`.
14. Mark `Done` only when closeout reports `closeout_ready: true` and code, tests, synchronized docs, local evidence, `references/implementation-readiness-checklist.md`, and `references/implementation-execution-checklist.md` are satisfied.

## Stop Conditions

- More than one task is being changed without explicit task-board grouping.
- The task is not `Ready` or `In Progress`.
- `implementation plan --json` reports `active_work.status` other than `ready`, `in_progress`, or `complete`.
- `implementation closeout --task TASK-NNN --json` reports `closeout_ready: false` before a `Done` status change.
- Required local Markdown sources are missing or contradictory.
- The acceptance ID is not mapped in `docs/tests/02-acceptance-matrix.md`.
- A required project command is missing from `docs/agent-workflow/command-contract.md`.
- A command environment, required tool, version probe, version constraint, or reviewed repair source is missing from `docs/agent-workflow/project-environment.json`.
- `environment_readiness.ok` is false and its explicit repair or registration route has not completed.
- A command-contract row with `Approval Required` set to `true` needs unapproved escalation.
- A command-contract row writes state but explicit `--allow-writes` authorization is absent.
- Verification cannot pass and no `Blocked`, `Deferred`, or unresolved follow-up is recorded.
