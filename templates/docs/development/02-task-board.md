# Task Board

## Task Table

| ID | Status | Task | Product | Design | API | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-NNN | Backlog | Product-derived task | product source | design source | endpoint contract source | A-NNN acceptance source | command:<registered-name> verification evidence path |

## Status Policy

- Allowed statuses: Backlog, Ready, In Progress, Blocked, Done, Deferred.

## Traceability Rules

- Product, Design, API, and Acceptance cells must reference existing local Markdown sources.
- Ready and In Progress tasks must bind every required check as `command:<registered-name>` in Verification; each name must resolve to a valid non-approval row in `docs/agent-workflow/command-contract.md`.
- Keep the local Markdown evidence path in Verification so closeout can prove durable evidence after the bound commands pass.
- Done tasks must link Verification to local Markdown evidence.
