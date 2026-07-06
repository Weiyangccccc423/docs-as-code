---
name: planning-implementation-work
description: Use when deriving implementation roadmaps, traceable task boards, Ready task criteria, Done evidence expectations, verification logs, or agent handoff work items from product, design, API, and test documentation.
---

# Planning Implementation Work

Implementation planning converts completed product and design documents into traceable work items without adding product meaning.

Read `references/implementation-readiness-checklist.md` before marking tasks `Ready`, creating agent handoffs, or accepting `Done` evidence. Read `references/implementation-execution-checklist.md` before writing or updating a task handoff for an implementation agent.

## Required Context

- `docs/product/core/PRD.md`
- structured product chapters and product acceptance criteria
- `docs/architecture/`, `docs/ui/`, `docs/api/`, `docs/backend/`, and `docs/frontend/`
- `docs/tests/01-strategy.md`
- `docs/tests/02-acceptance-matrix.md`
- `docs/unresolved.md`

## Procedure

1. Run the implementation gate in check mode before planning:

   ```bash
   bin/governance advance implementation <target> --check --json
   ```

   Use `requirements[].code` and `verification.findings[]` to identify missing design, test, or traceability inputs.

2. Run `bin/governance scaffold design <target> --check --json` when development files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Read `references/implementation-readiness-checklist.md` and `references/implementation-execution-checklist.md`.
4. Replace scaffold placeholders in `docs/development/01-roadmap.md`, `docs/development/02-task-board.md`, and `docs/development/03-verification-log.md`.
5. Derive roadmap milestones from product acceptance IDs, architecture/API/backend/frontend dependencies, and test strategy risk order.
6. Assign stable `TASK-NNN` IDs in `docs/development/01-roadmap.md`; use standard statuses only.
7. Create matching `TASK-NNN` rows in `docs/development/02-task-board.md` with `Product`, `Design`, `API`, `Acceptance`, and `Verification` fields.
8. Mark a task `Ready` only when its Product, Design, API, Acceptance, and Verification cells link existing local Markdown sources, its `A-NNN` ID is mapped in `docs/tests/02-acceptance-matrix.md`, and its Ready contract satisfies `references/implementation-readiness-checklist.md`.
9. Keep task board statuses synchronized with roadmap milestone statuses.
10. Initialize `docs/development/03-verification-log.md` as the stable target for Done evidence; add matching `TASK-NNN` rows when tasks are completed.
11. Accept `Done` only when verification evidence is recorded, documentation is synchronized, and the task satisfies the Definition of Done in `references/implementation-readiness-checklist.md` plus the execution rubric in `references/implementation-execution-checklist.md`.
12. Register blockers in `docs/unresolved.md` instead of marking speculative tasks Ready.

## Stop Conditions

- A task lacks product or acceptance source.
- A task requires an API endpoint, design document, or test mapping that does not exist.
- A Ready task references an unmapped `A-NNN` acceptance ID.
- A Ready task lacks a verification plan, implementation constraints, or agent handoff context.
- Roadmap and task board statuses disagree.
- A Done task lacks local Markdown verification evidence.
