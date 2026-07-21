# Phase 06: Implementation Execution

## Input

- Generated governance repository whose implementation gate has passed
- One `Ready` `TASK-NNN` row whose Verification cell binds every required check as `command:<registered-name>`
- Optional task-board `Risk` cell using only `risk:dependencies`, `risk:secrets`, and `risk:containers`
- Local product, design, API, acceptance, and verification sources linked from the task
- Target-local command contract at `docs/agent-workflow/command-contract.md`, with optional command `Risk` labels matching task risks
- Initialized Git work tree for immutable task-start change baselines
- Optional `docs/agent-workflow/task-handoff.md`

## Skills

Load:

- `executing-implementation-task`
- `verifying-governance-docs`
- every authority-routing specialist returned by the selected task's `skill_loading_plan`, derived from its linked architecture, API, backend, data-model, reliability, UI, frontend, test, and ADR sources plus explicit dependency, secret, and container risk labels
- authority-routing `code-reviewer` before closeout

## Procedure

1. Read `references/implementation-execution-checklist.md` and use it as the rubric for task intake, scope control, implementation loop, verification execution, evidence and status updates, security and supply-chain checks, and the completion gate.

2. Confirm implementation readiness from the target repository:

   ```bash
   bin/governance gate implementation <target> --json
   bin/governance verify <target> --check --json
   bin/governance workflow work-package <target> --json
   bin/governance implementation plan <target> --json
   ```

   When working inside the generated target, prefer:

   ```bash
   bin/governance gate implementation . --json
   bin/governance verify . --check --json
   bin/governance implementation plan . --json
   make implementation-plan
   make implementation-run-check
   make work-package
   ```

   The implementation work package must select the same `TASK-NNN`, expose `requires_codebase_mapping: true`, resolve all required local and authority skills, and return `claim-implementation-task` before a Ready task is edited. Inspect `verification_command_names`, `verification_commands`, `verification_command_summary`, `covered_risk_tags`, `missing_risk_command_bindings`, and `execution_contract`; every binding must be registered, non-approval, and ready before work starts, and every task Risk must be covered by a bound command carrying the same label.

   Stop on `ok: false`; route repair through `verifying-governance-docs` and the owning design or planning skill before editing code. When these checks come from consumer bootstrap `implementation_readiness_preview`, follow its ordered `blockers[]`, `readiness_summary`, `next_blocker`, and `next_repair_action` instead of independently reordering verify findings, gate requirements, and implementation-plan errors.

   A fresh-folder consumer bootstrap `--workflow-preset implementation-routing` normally stops at design authoring blockers; it must not imply that Agent-authored design or authority reviews happened inside initialization. After every design queue and review passes, run `python3 scripts/bootstrap_consumer_project.py --target <target> --resume --workflow-preset implementation-routing --json` from the unpacked workflow pack. Resume preserves authored files, records the adjacent implementation phase only when its preflight passes, then calls `implementation run --check --json` and returns `implementation_run_preview`; if the phase is already implementation, it refreshes runner state without replaying the write. Require `ok`, `implementation_routing_ok`, and `runner_contract_valid` before trusting runner fields; `ok` alone does not mean an action is ready. Continue only when `implementation_route_ready` is true: a Ready task requires `implementation_handoff_ready` and `status: ready_to_start`; an In Progress task may instead require `implementation_continuation_ready` with `status: verification_ready` or `closeout_ready`; treat `implementation_terminal: true` as complete. Execute only the structured `next_action.argv`; apply-start, execute, and closeout actions must carry the matching runner snapshot through `--expect-snapshot`. If an error reports `state_write_observed: true`, rerun resume to recover the already-recorded phase before any other write. If the preview is skipped, repair the upstream `blocked_by` stage and rerun resume; do not fall back to legacy bootstrap start/closeout apply flags.

3. Use `implementation plan --json` before editing code. Its `decision_policy` is `execute_exactly_one_ready_task`; inspect `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `risk_tags`, `read_order`, `verification_command_names`, `verification_commands`, `verification_command_summary`, `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, and embedded `gate_command`, `start_command`, `verify_command`, `closeout_command`, and `refresh_command`. Specialist routing follows the task's actual source paths: architecture loads architecture authority, container/deployment and quality sources add DevOps/operability/performance authority, data-model and migration sources add database/migration authority, reliability sources add observability/SLO authority, and UI/frontend/test sources add their matching accessibility, performance, E2E, and security authority. Explicit `risk:dependencies`, `risk:secrets`, and `risk:containers` labels additionally load `dependency-auditor`, `env-secrets-manager`, and the `docker-development` plus `senior-devops` pair. Load only the returned requirements in order; do not infer a skill or risk from task-title keywords. Stop successfully when `active_work.status` is `complete`. Stop for repair when `active_work.status` is not `ready`, `in_progress`, or `complete`, when any required verification command is missing, invalid, or approval-required, when `active_work.next_repair_action` is non-empty, or when a required authority-routing skill cannot be loaded from the agent environment.

4. Select exactly one `Ready` or `In Progress` `TASK-NNN` from `active_work.task_id` or the first actionable `tasks[]` item. Do not start multiple task rows in one implementation pass unless the task board explicitly groups them and their verification evidence is shared.

5. Use the guarded runner to claim a `Ready` task before editing code:

   ```bash
   bin/governance implementation run <target> --task TASK-NNN --check --json
   bin/governance implementation run <target> --task TASK-NNN --apply-start --expect-snapshot <snapshot-id> --json
   ```

   Use the first payload's `snapshot.id` or returned `next_action.argv`; never copy an older snapshot from conversation memory. The apply-start invocation must return `status: implementation_required`, set `start_applied: true`, leave `executed: false`, and route `next_action.kind: edit_selected_task`. Stop the controller at this point, map the codebase, and perform the scoped code/test edits. `--apply-start` must never be combined with `--execute` or `--closeout`.

   Claim also captures the pre-edit Git inventory in `.governance/implementation-change-baselines.json`. Require `baseline_capture.captured: true` or `already_current: true` before editing. The response exposes only its ID, digest, file count, and byte count; never recapture a missing baseline after an `In Progress` task has been edited.

   `implementation start --task TASK-NNN --json` and its apply form remain available as lower-level diagnostics. The runner reuses their requirements and synchronized task-board/roadmap updates.

6. Read every path in the selected task's `read_order`, including local Markdown sources linked from the task's `Product`, `Design`, `API`, `Acceptance`, and `Verification` cells, plus `docs/agent-workflow/command-contract.md` and `docs/agent-workflow/task-handoff.md` when it exists.

7. Inspect existing code, tests, build files, generated artifacts, and local conventions before editing. Use the task's allowed modules, linked source docs, and repository `AGENTS.md` files to constrain the change surface.

8. Implement in small coherent steps:
   - keep behavior within product, design, API, data, and security sources
   - update tests next to the changed surface
   - update generated clients, schemas, migrations, fixtures, snapshots, or lockfiles only when task scope and repository tooling require them
   - register missing or conflicting requirements in `docs/unresolved.md` instead of guessing
   - for dependency, secret/environment, or container changes, require the matching task Risk label and returned authority specialist before changing manifests, lockfiles, environment contracts, secret handling, Dockerfiles, or container runtime configuration

9. After code edits, confirm each `command:<registered-name>` binding resolves in `docs/agent-workflow/command-contract.md`, then preflight every bound command before any task command executes:

   ```bash
   bin/governance implementation run <target> --task TASK-NNN --check --json
   bin/governance implementation run <target> --task TASK-NNN --execute --expect-snapshot <snapshot-id> --json
   ```

   Require `status: verification_ready`, `verification_summary.all_ready: true`, and `ready_count == required_count` before using the returned snapshot-guarded execute action. Execution is sequential and stops at the first failure while preserving evidence and `In Progress` status. Use `--auto-repair` only for registered repair routes; the runner may auto-apply only repairs reporting `can_auto_apply: true`. A `reviewed-command` repair additionally requires `--approve-repairs`; manual, unknown-source, and approval-required task commands remain stop conditions.

   For one-command diagnosis, use each work-package `verification_commands[].preflight_command.argv`, followed only on readiness by `verification_commands[].execute_command.argv`; these preserve the exact task ID, command name, and required `--allow-writes` flag:

   ```bash
   bin/governance implementation verify <target> --task TASK-NNN --command command-name --check --json
   bin/governance implementation verify <target> --task TASK-NNN --command command-name --json
   ```

   Before adding the row, load `configuring-project-runtime`, run `project-env plan`, and use `project-env register --reviewed --check` plus apply to record the reviewed environment in `docs/agent-workflow/project-environment.json` using `references/project-environment-contract.md`. The `Environment` cell is a required environment ID. Set optional command `Risk` to `none` or the supported task risks the command actually checks. Declare every required external tool, an allowlisted read-only version probe, numeric version constraints, and a reviewed manual or exact reviewed-command repair source. Use the routed authority specialist to select a real project-native dependency, secret, or container audit; authority skill loading is not evidence by itself.

   The runner reads the exact structured `Argv` and `Cwd`; it never reconstructs a shell string. The task must be `In Progress`. `--check` does not execute the registered task command and writes no evidence, but after governance verification passes it executes declared version probes with no shell, a five-second timeout, and bounded output. Inspect `environment_readiness.ok`, `environment_contract`, `environment_probe_executed`, `required_tools`, `repair_actions`, `repair_decision`, `repair_preflight_command`, and `refresh_command` before execution. Bare tools resolve through the effective `PATH`; repository executable paths resolve from `Cwd` and must stay inside the repository. Missing or incompatible `governance-env` tools route to `env --repair --check --strict`; reviewed-command tools route to `project-env repair --check` and an approval-required apply action; manual and undeclared tools never receive guessed installation commands. Approved repair is not successful until the post-repair probe passes and audit evidence is complete.

   Rows marked `Approval Required: true` are refused; execute those only through an explicitly authorized external path and record the result honestly. Rows marked `Writes State: true` also require `--allow-writes`. Use `--timeout-seconds` and `--max-output-bytes` when project checks need bounds different from the defaults.

   Every execution derives pass/fail from the process return code, serializes evidence writers with a repository-local lock, applies best-effort redaction to common credential output, and atomically updates `docs/development/04-implementation-evidence.md`, `03-verification-log.md`, `02-task-board.md`, and the development README index. The evidence ledger preserves every run. The current verification log has one summary row per `(Task, Command)`, so rerunning the same command replaces only its summary row. Redaction is not a substitute for keeping secrets out of command arguments and output.

10. After every required command passes, review the complete task change set before closeout. Run the read-only inspection, load every path in `authority_review_context.required_reads` including the provenance-locked `code-reviewer`, and inspect every `change_set.changed_paths` entry:

   ```bash
   bin/governance implementation review <target> --task TASK-NNN --json
   ```

   Write the reviewer result to `.governance/code-review-reports/TASK-NNN.json` using the returned `report_contract`. It must identify the reviewer and approved verdict and resolve, reject, or explicitly accept only permitted low/medium findings. Preflight and then record it:

   ```bash
   bin/governance implementation review <target> --task TASK-NNN --report .governance/code-review-reports/TASK-NNN.json --reviewed --check --json
   bin/governance implementation review <target> --task TASK-NNN --report .governance/code-review-reports/TASK-NNN.json --reviewed --json
   ```

   Require `evidence_current: true` and the recorded entry in `docs/development/05-code-review-evidence.json`. The evidence binds the task fields, baseline, per-file content, type and Git mode changes, verification rows, and authority skill digest. Any later code, task traceability, verification evidence, or `code-reviewer` provenance change makes it stale and requires a fresh review. Runner `status: code_review_required` or `closeout_blocked` with sole blocker `code_review_evidence_current` is the normal review handoff, not permission to close.

   When routing through consumer bootstrap resume, require top-level `implementation_review_ready: true`, preview `review_ready: true`, and the exact `inspect-implementation-code-review` action before review. That action must use the selected `TASK-NNN`, the target `cwd`, `writes_state: false`, and `approval_required: false`. It is a read-only review inspection and therefore has no snapshot guard and does not set `implementation_continuation_ready`; execute and closeout remain the only continuation routes.

11. Re-run governance verification and refresh the implementation plan when docs, task status, review, or handoff evidence changes. Only after a runner check returns `status: closeout_ready`, use its returned snapshot-guarded closeout action:

   ```bash
   bin/governance verify <target> --check --json
   bin/governance implementation plan <target> --json
   bin/governance implementation run <target> --task TASK-NNN --closeout --expect-snapshot <snapshot-id> --json
   bin/governance implementation closeout <target> --task TASK-NNN --json
   ```

12. Before marking `Done`, inspect the runner's embedded `closeout_preview`. It reuses `implementation closeout` and its `decision_policy: do_not_mark_done_without_passing_evidence`; inspect `closeout_ready`, `requirements[]`, `blocking_requirements[]`, `evidence_summary.required_verification_commands`, `missing_verification_commands`, `failing_verification_commands`, `verification_commands_registered`, `required_verification_commands_passing`, `required_risk_tags`, `missing_risk_command_bindings`, `missing_risk_verification_evidence`, `required_risk_verification_passing`, `evidence_summary.all_verification_results_passing`, `evidence_summary.code_review_evidence_current`, and `status_update_plan`. Do not mark `Done` unless every bound command is registered and passing, every task Risk has current passing evidence from a matching command, every additional current verification row also passes, and `code_review_evidence_current` is satisfied. Successful runner closeout must return `status: complete`, `closeout_applied: true`, and synchronized `Done` status in `docs/development/02-task-board.md` and `docs/development/01-roadmap.md`.

13. Keep `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses synchronized:
   - `In Progress` only through `implementation start --apply` when one Ready task is claimed or resumed
   - `Done` only when code, tests, docs, and local Markdown evidence satisfy `references/implementation-readiness-checklist.md` and `references/implementation-execution-checklist.md`
   - `Blocked` when a required source, credential, environment, dependency approval, or unresolved decision prevents completion
   - `Deferred` when the task remains valid but is intentionally postponed

14. Produce a final implementation handoff that names changed files, commands run, review evidence, failures, follow-ups, and remaining risks.

## Output

- Scoped code and test changes for one `TASK-NNN`
- Synchronized product-derived docs when implementation changes documented behavior
- Updated `docs/development/03-verification-log.md`
- Append-only `docs/development/04-implementation-evidence.md`
- Current `docs/development/05-code-review-evidence.json`
- Synchronized roadmap and task-board statuses
- Explicit unresolved, blocked, or deferred follow-ups when the task cannot be completed

## Verification

Implementation execution is complete when:

- `bin/governance verify <target> --check --json` reports `ok: true`
- task-specific verification commands have been run through `implementation verify` or honestly recorded as unavailable
- every Ready or In Progress task binds required checks as `command:<registered-name>` and the work package resolves exact preflight and execute `argv`
- closeout reports both `required_verification_commands_registered` and `required_verification_commands_passing` satisfied
- `implementation run` proves snapshot-guarded start and closeout, all-command preflight before execution, and `status: complete`
- every current `(Task, Command)` summary result is passing before closeout
- `code_review_evidence_current` proves a provenance-bound `code-reviewer` review covers the complete current task change set
- project-specific verification commands are documented in `docs/agent-workflow/command-contract.md` before agents rely on them
- `docs/development/03-verification-log.md` contains matching `TASK-NNN` evidence
- any `Done` task links local Markdown evidence from its task-board `Verification` field
- the task satisfies `references/implementation-execution-checklist.md`

## Stop Conditions

- No single `Ready` or `In Progress` `TASK-NNN` is selected.
- The implementation gate or governance verification fails.
- Required product, design, API, acceptance, or verification links are missing.
- A task Risk label is unknown, or the expected dependency, secret/environment, or container change surface lacks its matching supported label.
- The task requires behavior that is not present in local Markdown sources.
- A required `command:<registered-name>` binding is missing, unknown, malformed, approval-required, or not documented in `docs/agent-workflow/command-contract.md`.
- The command `Environment` ID, required tool, safe version probe, version constraint, or reviewed repair source is absent from `docs/agent-workflow/project-environment.json`.
- `environment_readiness.ok` is false, or its repair decision requires environment preflight, manual tool registration, or executable-path repair.
- A command-contract row with `Approval Required` set to `true` needs approval that has not been granted.
- A state-writing command has not received explicit `--allow-writes` authorization.
- The runner reports `status: stale` or its repository-local implementation lock is unavailable.
- The immutable Git baseline is missing, the authority `code-reviewer` is unavailable or drifted, a review finding remains open, or code review evidence is stale.
- Auto-repair requires approval, manual action, or an unregistered repair source.
- Verification fails and no blocker or follow-up is recorded.
