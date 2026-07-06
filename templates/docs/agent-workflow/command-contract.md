# Agent Command Contract

## Command Table

| Name | Purpose | Cwd | Argv | Writes State | Evidence | Environment |
| --- | --- | --- | --- | --- | --- | --- |
| verify-check | Read-only governance verification before or after task work. | `.` | `["bin/governance", "verify", ".", "--check", "--json"]` | false | `docs/development/03-verification-log.md` | Core governance runtime |
| verify-governance | Record governance verification state after evidence is ready. | `.` | `["bin/governance", "verify", "."]` | true | `docs/development/03-verification-log.md` | Core governance runtime |
| check-env | Preview core environment repairs without installing packages. | `.` | `["bin/governance", "env", "--repair", "--check", "--target", ".", "--json"]` | false | `.governance/env-repair.md` when repair is written | Core governance runtime |

## Project Commands

- Add project-specific build, lint, typecheck, unit, integration, contract, end-to-end, migration, and security commands after the implementation stack is selected.
- Prefer structured `Argv` arrays over shell strings.
- Mark `Writes State` as `true` when the command changes files, databases, caches, generated artifacts, external services, or governance state.
- Link command evidence to `docs/development/03-verification-log.md` or another local Markdown evidence file.

## Usage Rules

- Prefer command rows from this file before reconstructing commands from prose.
- Run read-only commands before state-writing commands when both exist.
- Do not run dependency installation, credential access, production access, publishing, or release commands unless the task explicitly authorizes them.
- Record skipped, unavailable, failed, flaky, and passing commands in `docs/development/03-verification-log.md`.
