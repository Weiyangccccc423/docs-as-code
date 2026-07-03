---
name: planning-implementation-work
description: Use when deriving implementation roadmaps, traceable task boards, Ready task criteria, Done evidence expectations, verification logs, or agent handoff work items from product, design, API, and test documentation.
---

# Planning Implementation Work

Implementation planning converts completed product and design documents into traceable work items without adding product meaning.

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

2. Run `bin/governance scaffold design <target> --check --json` when development files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and keep returned `next_actions` for later.
3. Replace scaffold placeholders in `docs/development/01-roadmap.md`, `docs/development/02-task-board.md`, and `docs/development/03-verification-log.md`.
4. Derive roadmap milestones from product acceptance IDs, architecture/API/backend/frontend dependencies, and test strategy risk order.
5. Assign stable `TASK-NNN` IDs in `docs/development/01-roadmap.md`; use standard statuses only.
6. Create matching `TASK-NNN` rows in `docs/development/02-task-board.md` with `Product`, `Design`, `API`, `Acceptance`, and `Verification` fields.
7. Mark a task `Ready` only when its Product, Design, API, Acceptance, and Verification cells link existing local Markdown sources and its `A-NNN` ID is mapped in `docs/tests/02-acceptance-matrix.md`.
8. Keep task board statuses synchronized with roadmap milestone statuses.
9. Initialize `docs/development/03-verification-log.md` as the stable target for Done evidence; add matching `TASK-NNN` rows when tasks are completed.
10. Register blockers in `docs/unresolved.md` instead of marking speculative tasks Ready.

## Stop Conditions

- A task lacks product or acceptance source.
- A task requires an API endpoint, design document, or test mapping that does not exist.
- A Ready task references an unmapped `A-NNN` acceptance ID.
- Roadmap and task board statuses disagree.
- A Done task lacks local Markdown verification evidence.
