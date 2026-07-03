---
name: using-governance-workflow
description: Use when starting or resuming a docs-as-code governance workflow from an empty or partially governed repository.
---

# Using Governance Workflow

Use this as the router skill for the workflow pack.

## Route

| Situation | Load next |
| --- | --- |
| Empty folder or missing root governance | `initializing-governance-repo` |
| Source product document needs import | `archiving-product-document` |
| PRD exists but product chapters are missing | `structuring-product-requirements` |
| Product is structured and design is needed | `designing-system-architecture`, then `designing-ui-interactions`, then `designing-api-contracts`, then `designing-backend-modules`, then `designing-data-models`, then `capturing-architecture-decisions`, then `designing-frontend-modules` when frontend docs are in scope, then `designing-test-strategy`, then `planning-implementation-work` |
| Any phase claims completion | `verifying-governance-docs` |

## Environment Preflight

Before repair or strict verification, preview environment changes without writing files or installing packages:

```bash
bin/governance env --repair --check --target <target> --json
```

Stop on `ok: false` when missing required tools block the current phase. Inspect `would_repair`, `install_commands`, and `needs_escalation`; run `bin/governance env --repair --target <target> --json` only when the repair plan should be written or approved package installation should proceed.

## Phase Gates

Before loading downstream skills or changing phase, run the target-local gate when available:

```bash
bin/governance gate product-structuring <target> --json
bin/governance gate design-derivation <target> --json
bin/governance gate implementation <target> --json
```

Stop on `ok: false`. Use `requirements[].code` to choose the repair skill, then rerun the gate.
When `gate --json` can read governance state, use returned `local_commands[].argv` for local checks; when the gate passes, use returned `next_actions[].argv` for the matching advance preflight.
When actually changing phase, run `bin/governance advance <phase> <target> --check --json`, then run it without `--check` so `.governance/state.json` records `phase_history`. `advance` records adjacent transitions one phase at a time and cannot skip phases; use `gate` for repeated checks or earlier-phase audits.
After a state-writing `product mark-ready --json` or `advance --json` succeeds, prefer the returned `local_commands` and `next_actions` instead of reconstructing commands or rerunning `status`.

After `design-derivation` passes, run `bin/governance scaffold design <target> --check --json` if standard design files are missing, then run it without `--check` when the plan is correct. Do not enter implementation while any `governance:scaffold-placeholder` marker remains.

When working inside a generated target without the source workflow-pack repository open, use `docs/agent-workflow/workflow-pack/` as the local copy of workflows, skills, references, and templates.

## Rules

- Do not derive design from an unarchived product source.
- Do not continue past a `docs/unresolved.md` row whose `Blocking Scope` is not empty, `-`, `none`, `n/a`, `non-blocking`, or `resolved`.
- Do not create a new docs directory unless it is registered in `docs/AGENTS.md`.
- Prefer scripts for deterministic checks; use skills for judgment-heavy classification.
- After initialization, prefer the target-local `bin/governance` runtime copied into the generated repository.
