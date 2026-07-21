# Task Board

## Task Table

| ID | Status | Task | Product | Design | API | Acceptance | Verification | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK-NNN | Backlog | Product-derived task | product source | design source | endpoint contract source | A-NNN acceptance source | command:<registered-name> verification evidence path | none |

## Status Policy

- Allowed statuses: Backlog, Ready, In Progress, Blocked, Done, Deferred.

## Traceability Rules

- Product, Design, API, and Acceptance cells must reference existing local Markdown sources.
- Ready and In Progress tasks must bind every required check as `command:<registered-name>` in Verification; each name must resolve to a valid non-approval row in `docs/agent-workflow/command-contract.md`.
- Keep the local Markdown evidence path in Verification so closeout can prove durable evidence after the bound commands pass.
- Use only `risk:dependencies`, `risk:secrets`, and `risk:containers` in the optional Risk cell; use `none` when no listed risk applies.
- Add every applicable Risk label from the expected change surface. Unknown `risk:*` labels block implementation until the workflow pack defines their authority route.
- Done tasks must link Verification to local Markdown evidence.
