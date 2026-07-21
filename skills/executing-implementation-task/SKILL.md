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
- `docs/development/05-code-review-evidence.json`
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
   bin/governance implementation run . --check --json
   ```

   Stop on `ok: false` and route repair through `verifying-governance-docs`.

2. Inspect `implementation plan --json` before editing. Its `decision_policy` is `execute_exactly_one_ready_task`; use `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `risk_tags`, `read_order`, `verification_command_names`, `verification_commands`, `verification_command_summary`, `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `gate_command`, `start_command`, `verify_command`, `closeout_command`, and `refresh_command` to choose the task and repair blockers. Load local workflow skills first, then every returned authority-routing specialist. Linked design paths route architecture, container/deployment, quality, API, backend, data-model/migration, reliability, UI, frontend, test, and ADR authority. Explicit `risk:dependencies`, `risk:secrets`, and `risk:containers` labels route `dependency-auditor`, `env-secrets-manager`, and `docker-development` plus `senior-devops`; never substitute task-title keyword guesses. Stop successfully when `active_work.status` is `complete`; stop for repair when it is not `ready`, `in_progress`, or `complete`.
3. Select exactly one task row from `active_work.task_id` or the first actionable `tasks[]` item. Confirm it uses a stable `TASK-NNN` ID, links local Markdown Product, Design, API, Acceptance, and Verification sources, references a product-defined `A-NNN` mapped in `docs/tests/02-acceptance-matrix.md`, binds every required check as `command:<registered-name>`, and declares every applicable supported Risk label before dependency, secret/environment, or container changes.
4. Claim a `Ready` task through `implementation run`: execute `bin/governance implementation run . --task TASK-NNN --check --json`, then use its returned `next_action.argv` or run `bin/governance implementation run . --task TASK-NNN --apply-start --expect-snapshot <snapshot-id> --json`. Require `status: implementation_required`, `start_applied: true`, `executed: false`, and `baseline_capture.captured: true` or `already_current: true`, then stop the controller for code mapping and edits. The claim stores the immutable pre-edit Git inventory in `.governance/implementation-change-baselines.json`; never reconstruct it after edits. Never combine `--apply-start` with `--execute` or `--closeout`. Use lower-level `implementation start` only for diagnosis.
5. Read the selected task `read_order`, the acceptance matrix row, and the task handoff before editing implementation files.
6. Inspect existing code, tests, generated files, build scripts, and local conventions around the changed surface.
7. Keep edits limited to the selected task. Register missing requirements, conflicting docs, missing credentials, or unsafe dependency changes in `docs/unresolved.md` instead of guessing.
8. Implement in small coherent steps and add or update tests next to the changed behavior.
9. Load `configuring-project-runtime`, run `project-env plan`, and register each reviewed tool through `project-env register --reviewed --check` plus apply before registering task commands with those environment IDs in `docs/agent-workflow/command-contract.md`. After code edits, run `implementation run --task TASK-NNN --check --json`; require every `verification_preflights[]` item ready and `verification_summary.ready_count == required_count` before executing the returned snapshot-guarded action. `implementation run --execute` runs all bindings sequentially with structured argv and stops on the first failure. Use `--auto-repair` only for registered routes; only `can_auto_apply: true` governance repairs may run without approval, and `reviewed-command` repairs require `--approve-repairs`. For one-command diagnosis, use `verification_commands[].preflight_command.argv` or `bin/governance implementation verify . --task TASK-NNN --command command-name --check --json`, require `environment_readiness.ok: true`, then inspect `required_tools` and use `verification_commands[].execute_command.argv`. Run `project-env repair --check` only through the returned registered route and require completed `.governance/project-environment-repairs.json` evidence. Only allowlisted bounded version probes may execute during preflight; the task command and evidence writes remain disabled. Follow reviewed instructions for `manual`, and register unknown tools without inventing packages. Do not reconstruct a shell string.
10. The evidence runner refuses `Approval Required: true` rows and requires `--allow-writes` for `Writes State: true` rows. It derives the result from the return code, enforces timeout and output bounds, appends immutable history to `docs/development/04-implementation-evidence.md`, and upserts the current `(Task, Command)` summary in `docs/development/03-verification-log.md`.
11. Synchronize `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses through start and closeout apply when available.
12. Refresh `bin/governance implementation plan . --json` and confirm the selected task state, `gate_ok`, and evidence are consistent before claiming completion.
13. When runner execution routes to `code_review_required` or `closeout_blocked` with sole blocker `code_review_evidence_current`, run `bin/governance implementation review . --task TASK-NNN --json`. Load the returned `authority_review_context.required_reads`, including authority `code-reviewer`, and review the complete hashed change set. Write the structured result to `.governance/code-review-reports/TASK-NNN.json`, then run `implementation review . --task TASK-NNN --report .governance/code-review-reports/TASK-NNN.json --reviewed --check --json` before the matching apply command without `--check`. Resolve all open and critical/high findings. Require `evidence_current: true`; changes to code, task traceability, verification rows, or authority provenance require a fresh review.
14. After a new runner check returns `status: closeout_ready`, use its returned `next_action.argv` or run `implementation run --task TASK-NNN --closeout --expect-snapshot <snapshot-id> --json`. Inspect embedded `closeout_preview`; require `required_verification_commands_registered`, `required_verification_commands_passing`, empty `missing_verification_commands`, `evidence_summary.all_verification_results_passing`, and `code_review_evidence_current`. Use lower-level `implementation closeout` only for diagnosis.
15. Mark `Done` only when the runner reports `status: complete` and `closeout_applied: true`, and code, tests, synchronized docs, local verification/review evidence, `references/implementation-readiness-checklist.md`, and `references/implementation-execution-checklist.md` are satisfied.

## Stop Conditions

- More than one task is being changed without explicit task-board grouping.
- The task is not `Ready` or `In Progress`.
- `implementation plan --json` reports `active_work.status` other than `ready`, `in_progress`, or `complete`.
- A specialist required by the selected task's source-derived `skill_loading_plan` is unavailable or has invalid provenance.
- `implementation closeout --task TASK-NNN --json` reports `closeout_ready: false` before a `Done` status change.
- Required local Markdown sources are missing or contradictory.
- A `risk:*` label is unknown, or the task omits a required dependency, secret/environment, or container risk label.
- The acceptance ID is not mapped in `docs/tests/02-acceptance-matrix.md`.
- A required `command:<registered-name>` binding is missing, invalid, approval-required, or absent from `docs/agent-workflow/command-contract.md`.
- A command environment, required tool, version probe, version constraint, or reviewed repair source is missing from `docs/agent-workflow/project-environment.json`.
- `environment_readiness.ok` is false and its explicit repair or registration route has not completed.
- A command-contract row with `Approval Required` set to `true` needs unapproved escalation.
- A command-contract row writes state but explicit `--allow-writes` authorization is absent.
- The runner snapshot is stale, its implementation lock is unavailable, or its repair route requires unapproved/manual action.
- The task-start Git baseline is unavailable, the locked `code-reviewer` skill is missing or drifted, review findings remain open, or `code_review_evidence_current` is false.
- Verification cannot pass and no `Blocked`, `Deferred`, or unresolved follow-up is recorded.
