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
| Product is structured and design is needed | `designing-system-architecture`, then `designing-api-contracts` |
| Any phase claims completion | `verifying-governance-docs` |

## Phase Gates

Before loading downstream skills or changing phase, run the target-local gate when available:

```bash
bin/governance gate product-structuring <target> --json
bin/governance gate design-derivation <target> --json
bin/governance gate implementation <target> --json
```

Stop on `ok: false`. Use `requirements[].code` to choose the repair skill, then rerun the gate.
When actually changing phase, run `bin/governance advance <phase> <target> --json` so `.governance/state.json` records `phase_history`.

After `design-derivation` passes, run `bin/governance scaffold design <target> --json` if standard design files are missing. Do not enter implementation while any `governance:scaffold-placeholder` marker remains.

When working inside a generated target without the source workflow-pack repository open, use `docs/agent-workflow/workflow-pack/` as the local copy of workflows, skills, references, and templates.

## Rules

- Do not derive design from an unarchived product source.
- Do not continue past a `docs/unresolved.md` row whose `Blocking Scope` is not empty, `-`, `none`, `n/a`, `non-blocking`, or `resolved`.
- Do not create a new docs directory unless it is registered in `docs/AGENTS.md`.
- Prefer scripts for deterministic checks; use skills for judgment-heavy classification.
- After initialization, prefer the target-local `bin/governance` runtime copied into the generated repository.
