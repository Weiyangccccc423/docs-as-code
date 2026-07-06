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
   ```

   When working inside the generated target, prefer:

   ```bash
   bin/governance gate implementation . --json
   bin/governance verify . --check --json
   ```

   Stop on `ok: false`; route repair through `verifying-governance-docs` and the owning design or planning skill before editing code.

3. Select exactly one `Ready` `TASK-NNN` from `docs/development/02-task-board.md`. Do not start multiple task rows in one implementation pass unless the task board explicitly groups them and their verification evidence is shared.

4. Read every local Markdown source linked from the task's `Product`, `Design`, `API`, `Acceptance`, and `Verification` cells, plus `docs/agent-workflow/command-contract.md` and `docs/agent-workflow/task-handoff.md` when it exists.

5. Inspect existing code, tests, build files, generated artifacts, and local conventions before editing. Use the task's allowed modules, linked source docs, and repository `AGENTS.md` files to constrain the change surface.

6. Implement in small coherent steps:
   - keep behavior within product, design, API, data, and security sources
   - update tests next to the changed surface
   - update generated clients, schemas, migrations, fixtures, snapshots, or lockfiles only when task scope and repository tooling require them
   - register missing or conflicting requirements in `docs/unresolved.md` instead of guessing

7. Run the exact task verification commands. Prefer target-local `local_commands[].argv`, `docs/agent-workflow/command-contract.md` `Argv` rows, and task-board or handoff commands over reconstructed shell strings. Record unavailable, flaky, skipped, failed, and passing checks in `docs/development/03-verification-log.md`.

8. Re-run governance verification when docs, task status, or handoff evidence changes:

   ```bash
   bin/governance verify <target> --check --json
   ```

9. Update `docs/development/02-task-board.md` and `docs/development/01-roadmap.md` statuses together:
   - `Done` only when code, tests, docs, and local Markdown evidence satisfy `references/implementation-readiness-checklist.md` and `references/implementation-execution-checklist.md`
   - `Blocked` when a required source, credential, environment, dependency approval, or unresolved decision prevents completion
   - `Deferred` when the task remains valid but is intentionally postponed

10. Produce a final implementation handoff that names changed files, commands run, evidence paths, failures, follow-ups, and remaining risks.

## Output

- Scoped code and test changes for one `TASK-NNN`
- Synchronized product-derived docs when implementation changes documented behavior
- Updated `docs/development/03-verification-log.md`
- Synchronized roadmap and task-board statuses
- Explicit unresolved, blocked, or deferred follow-ups when the task cannot be completed

## Verification

Implementation execution is complete when:

- `bin/governance verify <target> --check --json` reports `ok: true`
- task-specific verification commands have been run or honestly recorded as unavailable
- project-specific verification commands are documented in `docs/agent-workflow/command-contract.md` before agents rely on them
- `docs/development/03-verification-log.md` contains matching `TASK-NNN` evidence
- any `Done` task links local Markdown evidence from its task-board `Verification` field
- the task satisfies `references/implementation-execution-checklist.md`

## Stop Conditions

- No single `Ready` `TASK-NNN` is selected.
- The implementation gate or governance verification fails.
- Required product, design, API, acceptance, or verification links are missing.
- The task requires behavior that is not present in local Markdown sources.
- The required project command is not documented in `docs/agent-workflow/command-contract.md`.
- Dependency installation, credential access, production access, package publishing, or release artifact creation needs approval that has not been granted.
- Verification fails and no blocker or follow-up is recorded.
