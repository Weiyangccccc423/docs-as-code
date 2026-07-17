# Agent Command Contract

## Command Table

| Name | Purpose | Cwd | Argv | Writes State | Approval Required | Evidence | Environment |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verify-governance | Run governance verification and update verification state. | `.` | `["bin/governance", "verify", "."]` | true | false | `docs/development/03-verification-log.md` | core-governance |
| verify-check | Run read-only JSON verification without updating state. | `.` | `["bin/governance", "verify", ".", "--check", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| governance-status | Print workflow state as JSON. | `.` | `["bin/governance", "status", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| workflow-plan | Print current workflow route plus active queue and skill summaries as JSON. | `.` | `["bin/governance", "workflow", "plan", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| work-package | Print one evidence-selected agent work package with skill readiness as JSON. | `.` | `["bin/governance", "workflow", "work-package", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| workflow-resume | Select one evidence-derived next action with a stale-snapshot guard as JSON. | `.` | `["bin/governance", "workflow", "resume", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| product-plan | Print product structuring plan as JSON. | `.` | `["bin/governance", "product", "plan", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| design-plan | Print design derivation plan as JSON. | `.` | `["bin/governance", "design", "plan", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| implementation-plan | Print Ready implementation task execution plan as JSON. | `.` | `["bin/governance", "implementation", "plan", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| implementation-run-check | Preflight the selected implementation task without claiming or executing it. | `.` | `["bin/governance", "implementation", "run", ".", "--check", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| check-env | Inventory local governance tools as JSON. | `.` | `["bin/governance", "env", "--target", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |
| repair-env-check | Preview environment repair without writing files. | `.` | `["bin/governance", "env", "--repair", "--check", "--target", ".", "--json"]` | false | false | `.governance/env-repair.md` when repair is written | core-governance |
| project-env-plan | Print reviewed project runtime tool registration plan as JSON. | `.` | `["bin/governance", "project-env", "plan", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | core-governance |

## Project Commands

- Add project-specific build, lint, typecheck, unit, integration, contract, end-to-end, migration, and security commands after the implementation stack is selected.
- Keep `Cwd` as `.` or a normalized relative POSIX path inside the repository.
- Prefer structured `Argv` arrays over shell strings.
- Mark `Writes State` as `true` when the command changes files, databases, caches, generated artifacts, external services, or governance state.
- Mark `Approval Required` as `true` for dependency installation, credential access, production access, publishing, release, destructive migration, or external state mutation commands.
- Link command evidence to `docs/development/03-verification-log.md` or another local Markdown evidence file.
- Set `Environment` to an ID declared in `project-environment.json`; use `project-env register --reviewed --check` plus apply for reviewed tools, version requirements, probes, and repair sources before using `project-runtime`.

## Usage Rules

- Prefer command rows from this file before reconstructing commands from prose.
- Run read-only commands before state-writing commands when both exist.
- Do not run commands with `Approval Required` set to `true` unless the task explicitly authorizes them.
- Record skipped, unavailable, failed, flaky, and passing commands in `docs/development/03-verification-log.md`.
- Use `implementation run --check` to select one task and preflight all bound commands. Use `--apply-start` in a separate invocation before editing code, then use `--execute` only after the scoped code changes are complete.
- For an `In Progress` task, preflight registered project checks with `bin/governance implementation verify . --task TASK-NNN --command command-name --check --json`.
- Require `environment_readiness.ok: true` before execution. Inspect `required_tools` version evidence and follow only repair actions backed by `project-environment.json`; register unknown tools instead of guessing installation commands.
- Preview a `reviewed-command` repair with `project-env repair --tool-id <tool-id> --check`; request approval for its apply action and require completed repair evidence plus a passing post-repair version probe.
- Run the returned structured command to append `docs/development/04-implementation-evidence.md` and update the current `(Task, Command)` summary without deleting prior runs.
- `implementation verify` refuses approval-required rows and requires `--allow-writes` for state-writing rows.
