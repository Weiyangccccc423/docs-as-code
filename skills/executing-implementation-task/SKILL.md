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
   ```

   Stop on `ok: false` and route repair through `verifying-governance-docs`.

2. Select exactly one task row with `Status` set to `Ready`. Confirm it uses a stable `TASK-NNN` ID, links local Markdown Product, Design, API, Acceptance, and Verification sources, and references a product-defined `A-NNN` mapped in `docs/tests/02-acceptance-matrix.md`.
3. Read the selected task sources, the acceptance matrix row, and the task handoff before editing implementation files.
4. Inspect existing code, tests, generated files, build scripts, and local conventions around the changed surface.
5. Keep edits limited to the selected task. Register missing requirements, conflicting docs, missing credentials, or unsafe dependency changes in `docs/unresolved.md` instead of guessing.
6. Implement in small coherent steps and add or update tests next to the changed behavior.
7. Run the task's verification commands. Prefer `local_commands[].argv`, `docs/agent-workflow/command-contract.md` `Argv` rows, and task-provided commands over reconstructed shell strings.
8. Record command, result, date, notes, and evidence path in `docs/development/03-verification-log.md`.
9. Synchronize `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses.
10. Mark `Done` only when code, tests, synchronized docs, local evidence, `references/implementation-readiness-checklist.md`, and `references/implementation-execution-checklist.md` are satisfied.

## Stop Conditions

- More than one task is being changed without explicit task-board grouping.
- The task is not `Ready`.
- Required local Markdown sources are missing or contradictory.
- The acceptance ID is not mapped in `docs/tests/02-acceptance-matrix.md`.
- A required project command is missing from `docs/agent-workflow/command-contract.md`.
- A dependency, credential, production access, release, or publishing action needs unapproved escalation.
- Verification cannot pass and no `Blocked`, `Deferred`, or unresolved follow-up is recorded.
