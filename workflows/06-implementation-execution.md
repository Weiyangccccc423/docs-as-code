# Phase 06: Implementation Execution

## Input

- Generated governance repository whose implementation gate has passed
- One `Ready` `TASK-NNN` row in `docs/development/02-task-board.md`
- Local product, design, API, acceptance, and verification sources linked from the task
- Target-local command contract at `docs/agent-workflow/command-contract.md`
- Optional `docs/agent-workflow/task-handoff.md`

## Skills

Load:

- `executing-implementation-task`
- `verifying-governance-docs`

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
   make work-package
   ```

   The implementation work package must select the same `TASK-NNN`, expose `requires_codebase_mapping: true`, resolve all required local and authority skills, and return `claim-implementation-task` before a Ready task is edited.

   Stop on `ok: false`; route repair through `verifying-governance-docs` and the owning design or planning skill before editing code. When these checks come from consumer bootstrap `implementation_readiness_preview`, follow its ordered `blockers[]`, `readiness_summary`, `next_blocker`, and `next_repair_action` instead of independently reordering verify findings, gate requirements, and implementation-plan errors.

3. Use `implementation plan --json` before editing code. Its `decision_policy` is `execute_exactly_one_ready_task`; inspect `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `read_order`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, and embedded `gate_command`, `start_command`, `verify_command`, `closeout_command`, and `refresh_command`. Stop successfully when `active_work.status` is `complete`. Stop for repair when `active_work.status` is not `ready`, `in_progress`, or `complete`, when `active_work.next_repair_action` is non-empty, or when a required authority-routing skill cannot be loaded from the agent environment.

4. Select exactly one `Ready` or `In Progress` `TASK-NNN` from `active_work.task_id` or the first actionable `tasks[]` item. Do not start multiple task rows in one implementation pass unless the task board explicitly groups them and their verification evidence is shared.

5. Claim a `Ready` task before editing code:

   ```bash
   bin/governance implementation start <target> --task TASK-NNN --json
   bin/governance implementation start <target> --task TASK-NNN --apply --json
   ```

   The preview payload uses `decision_policy: claim_exactly_one_ready_task_before_editing_code`; inspect `start_ready`, `requirements[]`, `blocking_requirements[]`, and `status_update_plan`. Only run apply when `status_update_plan.can_auto_apply` is true. If the selected task is already `In Progress`, treat the start command as an idempotent resume check before continuing.

6. Read every path in the selected task's `read_order`, including local Markdown sources linked from the task's `Product`, `Design`, `API`, `Acceptance`, and `Verification` cells, plus `docs/agent-workflow/command-contract.md` and `docs/agent-workflow/task-handoff.md` when it exists.

7. Inspect existing code, tests, build files, generated artifacts, and local conventions before editing. Use the task's allowed modules, linked source docs, and repository `AGENTS.md` files to constrain the change surface.

8. Implement in small coherent steps:
   - keep behavior within product, design, API, data, and security sources
   - update tests next to the changed surface
   - update generated clients, schemas, migrations, fixtures, snapshots, or lockfiles only when task scope and repository tooling require them
   - register missing or conflicting requirements in `docs/unresolved.md` instead of guessing

9. Register each project verification command in `docs/agent-workflow/command-contract.md`, then execute it through the target-local evidence runner:

   ```bash
   bin/governance implementation verify <target> --task TASK-NNN --command command-name --check --json
   bin/governance implementation verify <target> --task TASK-NNN --command command-name --json
   ```

   The runner reads the exact structured `Argv` and `Cwd`; it never reconstructs a shell string. The task must be `In Progress`. `--check` performs no execution and no writes. Rows marked `Approval Required: true` are refused; execute those only through an explicitly authorized external path and record the result honestly. Rows marked `Writes State: true` also require `--allow-writes`. Use `--timeout-seconds` and `--max-output-bytes` when project checks need bounds different from the defaults.

   Every execution derives pass/fail from the process return code, serializes evidence writers with a repository-local lock, applies best-effort redaction to common credential output, and atomically updates `docs/development/04-implementation-evidence.md`, `03-verification-log.md`, `02-task-board.md`, and the development README index. The evidence ledger preserves every run. The current verification log has one summary row per `(Task, Command)`, so rerunning the same command replaces only its summary row. Redaction is not a substitute for keeping secrets out of command arguments and output.

10. Re-run governance verification and refresh the implementation plan when docs, task status, or handoff evidence changes:

   ```bash
   bin/governance verify <target> --check --json
   bin/governance implementation plan <target> --json
   bin/governance implementation closeout <target> --task TASK-NNN --json
   bin/governance implementation closeout <target> --task TASK-NNN --apply --json
   ```

11. Before marking `Done`, run `implementation closeout --task TASK-NNN --json`. Its `decision_policy` is `do_not_mark_done_without_passing_evidence`; inspect `closeout_ready`, `requirements[]`, `blocking_requirements[]`, `evidence_summary.all_verification_results_passing`, and `status_update_plan`. Do not mark `Done` unless every current verification command for the task passes. When `status_update_plan.can_auto_apply` is true, run the returned `status_update_plan.apply_command.argv` or `implementation closeout --task TASK-NNN --apply --json` so the CLI updates `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` together.

12. Keep `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses synchronized:
   - `In Progress` only through `implementation start --apply` when one Ready task is claimed or resumed
   - `Done` only when code, tests, docs, and local Markdown evidence satisfy `references/implementation-readiness-checklist.md` and `references/implementation-execution-checklist.md`
   - `Blocked` when a required source, credential, environment, dependency approval, or unresolved decision prevents completion
   - `Deferred` when the task remains valid but is intentionally postponed

13. Produce a final implementation handoff that names changed files, commands run, evidence paths, failures, follow-ups, and remaining risks.

## Output

- Scoped code and test changes for one `TASK-NNN`
- Synchronized product-derived docs when implementation changes documented behavior
- Updated `docs/development/03-verification-log.md`
- Append-only `docs/development/04-implementation-evidence.md`
- Synchronized roadmap and task-board statuses
- Explicit unresolved, blocked, or deferred follow-ups when the task cannot be completed

## Verification

Implementation execution is complete when:

- `bin/governance verify <target> --check --json` reports `ok: true`
- task-specific verification commands have been run through `implementation verify` or honestly recorded as unavailable
- every current `(Task, Command)` summary result is passing before closeout
- project-specific verification commands are documented in `docs/agent-workflow/command-contract.md` before agents rely on them
- `docs/development/03-verification-log.md` contains matching `TASK-NNN` evidence
- any `Done` task links local Markdown evidence from its task-board `Verification` field
- the task satisfies `references/implementation-execution-checklist.md`

## Stop Conditions

- No single `Ready` or `In Progress` `TASK-NNN` is selected.
- The implementation gate or governance verification fails.
- Required product, design, API, acceptance, or verification links are missing.
- The task requires behavior that is not present in local Markdown sources.
- The required project command is not documented in `docs/agent-workflow/command-contract.md`.
- A command-contract row with `Approval Required` set to `true` needs approval that has not been granted.
- A state-writing command has not received explicit `--allow-writes` authorization.
- Verification fails and no blocker or follow-up is recorded.
