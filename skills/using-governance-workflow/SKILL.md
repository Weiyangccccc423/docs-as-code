---
name: using-governance-workflow
description: Use when starting or resuming a docs-as-code governance workflow from an empty or partially governed repository.
---

# Using Governance Workflow

Use this as the router skill for the workflow pack.

Read `references/workflow-routing-checklist.md` before selecting a phase, resuming from `local_commands` or `next_actions`, or repairing a blocked workflow transition.

## Route

| Situation | Load next |
| --- | --- |
| Empty folder or missing root governance | `initializing-governance-repo` |
| Source product document needs import | `archiving-product-document` |
| PRD exists but product chapters are missing | `structuring-product-requirements` |
| Product is structured and design is needed | `designing-system-architecture`, then `designing-ui-interactions`, then `designing-api-contracts`, then `designing-backend-modules`, then `designing-data-models`, then `capturing-architecture-decisions`, then `designing-frontend-modules` when frontend docs are in scope, then `designing-test-strategy`, then `planning-implementation-work` |
| Implementation gate passes and one Ready task should be coded | `executing-implementation-task` |
| Any phase claims completion | `verifying-governance-docs` |

## Environment Preflight

Before repair or strict verification, preview environment changes without writing files or installing packages:

```bash
bin/governance env --repair --check --target <target> --json
```

Stop on `ok: false` when missing required tools block the current phase. Inspect `would_repair`, `install_commands`, `repair_commands`, `manual_repairs`, `needs_escalation`, and `repair_execution`; use `repair_execution.status`, `repair_execution.can_auto_apply`, and `repair_execution.next_step` for branching. Run `repair_commands[].argv` from `repair_commands[].cwd` only when `approval_required` is false or approval is explicit. Run `bin/governance env --repair --target <target> --json` only when the repair plan should be written or approved package installation should proceed. When an initialized target returns `local_commands` or `next_actions`, use them to resume from the readable state.

## Phase Gates

Before loading downstream skills or changing phase, run the target-local gate when available:

```bash
bin/governance gate product-structuring <target> --json
bin/governance gate design-derivation <target> --json
bin/governance gate implementation <target> --json
```

Stop on `ok: false`. Use `requirements[].code` to choose the repair skill, then rerun the gate.
When `gate --json` can read governance state, use returned `local_commands[].argv` for local checks; when the gate passes, use returned `next_actions[].argv` for the matching advance preflight. Treat any returned command with `approval_required: true` as a stop-and-ask action.
When actually changing phase, run `bin/governance advance <phase> <target> --check --json`, then run it without `--check` so `.governance/state.json` records `phase_history`. `advance` records adjacent transitions one phase at a time and cannot skip phases; use `gate` for repeated checks or earlier-phase audits.
After a state-writing `product mark-ready --json` or `advance --json` succeeds, prefer the returned `local_commands` and `next_actions` instead of reconstructing commands or rerunning `status`.

After `design-derivation` passes, run `bin/governance scaffold design <target> --check --json` if standard design files are missing, inspect `would_create`, `would_skip`, and `would_index`, then run it without `--check` when the plan is correct. Expect the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md` and table skeletons for the acceptance matrix, roadmap, task board, and verification log. Use successful scaffold `local_commands` for checks and inspect `scaffold_phase`; if `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved. When the recorded phase is `design-derivation`, run `bin/governance design plan <target> --json`; use returned `source_documents`, `tracks`, local workflow `skills`, authority-routing `specialist_skills`, `references`, `documents`, `blockers`, and `steps` to load the architecture, UI, API, backend, data-model, frontend, test, planning, and ADR skills in order before replacing placeholders. Do not enter implementation while any `governance:scaffold-placeholder` marker remains.

When working inside a generated target without the source workflow-pack repository open, use `docs/agent-workflow/workflow-pack/` as the local copy of workflows, skills, references, and templates.

## Rules

- Do not derive design from an unarchived product source.
- Do not continue past a `docs/unresolved.md` row whose `Blocking Scope` is not empty, `-`, `none`, `n/a`, `non-blocking`, or `resolved`.
- Do not create a new docs directory unless it is registered in `docs/AGENTS.md`.
- Prefer scripts for deterministic checks; use skills for judgment-heavy classification.
- After initialization, prefer the target-local `bin/governance` runtime copied into the generated repository.
