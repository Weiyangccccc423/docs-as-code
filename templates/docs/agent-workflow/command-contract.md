# Agent Command Contract

## Command Table

| Name | Purpose | Cwd | Argv | Writes State | Approval Required | Evidence | Environment |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verify-governance | Run governance verification and update verification state. | `.` | `["bin/governance", "verify", "."]` | true | false | `docs/development/03-verification-log.md` | Core governance runtime |
| verify-check | Run read-only JSON verification without updating state. | `.` | `["bin/governance", "verify", ".", "--check", "--json"]` | false | false | `docs/development/03-verification-log.md` | Core governance runtime |
| governance-status | Print workflow state as JSON. | `.` | `["bin/governance", "status", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | Core governance runtime |
| workflow-plan | Print current workflow route and active queue summaries as JSON. | `.` | `["bin/governance", "workflow", "plan", ".", "--json"]` | false | false | `docs/development/03-verification-log.md` | Core governance runtime |
| check-env | Inventory local governance tools. | `.` | `["bin/governance", "env", "--target", "."]` | false | false | `docs/development/03-verification-log.md` | Core governance runtime |
| repair-env-check | Preview environment repair without writing files. | `.` | `["bin/governance", "env", "--repair", "--check", "--target", ".", "--json"]` | false | false | `.governance/env-repair.md` when repair is written | Core governance runtime |

## Project Commands

- Add project-specific build, lint, typecheck, unit, integration, contract, end-to-end, migration, and security commands after the implementation stack is selected.
- Keep `Cwd` as `.` or a normalized relative POSIX path inside the repository.
- Prefer structured `Argv` arrays over shell strings.
- Mark `Writes State` as `true` when the command changes files, databases, caches, generated artifacts, external services, or governance state.
- Mark `Approval Required` as `true` for dependency installation, credential access, production access, publishing, release, destructive migration, or external state mutation commands.
- Link command evidence to `docs/development/03-verification-log.md` or another local Markdown evidence file.

## Usage Rules

- Prefer command rows from this file before reconstructing commands from prose.
- Run read-only commands before state-writing commands when both exist.
- Do not run commands with `Approval Required` set to `true` unless the task explicitly authorizes them.
- Record skipped, unavailable, failed, flaky, and passing commands in `docs/development/03-verification-log.md`.
