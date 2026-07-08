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

Stop on `ok: false` when missing required tools block the current phase. Inspect `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, and `repair_execution`; use `repair_execution.status`, `repair_execution.can_auto_apply`, `repair_execution.install_attempted`, `repair_execution.install_failed`, `repair_execution.post_repair_missing_required`, `repair_execution.post_repair_missing_recommended`, and `repair_execution.next_step` for branching. Sort `repair_actions` by `sequence`; run actions with `argv` only when `approval_required` is false or approval is explicit, and present `manual-repair` actions to the user. Run `bin/governance env --repair --target <target> --json` only when the repair plan should be written or approved package installation should proceed. Treat `applied_but_unresolved` as a stop state before retrying repairs. When an initialized target returns `local_commands` or `next_actions`, use them to resume from the readable state.

## Phase Gates

Before loading downstream skills or changing phase, run the target-local gate when available:

```bash
bin/governance gate product-structuring <target> --json
bin/governance gate design-derivation <target> --json
bin/governance gate implementation <target> --json
```

Stop on `ok: false`. Use `requirements[].code` to choose the repair skill, then rerun the gate.
When `gate --json` can read governance state, use returned `local_commands[].argv` for local checks; when the gate passes, use returned `next_actions[].argv` for the matching advance preflight. Sort `next_actions` by `sequence`, use `preflight_for` and `requires_action` to pair preflight/apply commands, and run apply only after the referenced preflight reports the declared `success_condition` of `ok:true`. Treat any returned command with `approval_required: true` as a stop-and-ask action.
When actually changing phase, run `bin/governance advance <phase> <target> --check --json`, then run it without `--check` so `.governance/state.json` records `phase_history`. `advance` records adjacent transitions one phase at a time and cannot skip phases; use `gate` for repeated checks or earlier-phase audits.
After a state-writing `product mark-ready --json` or `advance --json` succeeds, prefer the returned `local_commands` and `next_actions` instead of reconstructing commands or rerunning `status`.
When resuming an initialized target, run `bin/governance workflow plan <target> --json` or target-local `make workflow-plan` to inspect the current phase, `blocked` status, active queue summaries, top-level/per-queue `active_work`, local/authority skill routing summaries, ordered `skill_loading_plan` steps, read-only queue commands, `local_commands`, and `next_actions` before choosing a phase-specific skill. Use `active_work.queue_id`, `active_work.inspect_command`, `active_work.next_repair_action`, and embedded verify/refresh commands as the first recovery route.

When the recorded phase is `product-structuring`, run `bin/governance product plan <target> --json` before scaffolding product chapters. Use returned `source_documents`, `available_chapters`, `prd_headings`, `suggested_mappings`, `required_decisions`, `manual_authoring_tasks`, `manual_authoring_summary`, `active_work`, local workflow `skills`, `skill_requirements`, `authority_skill_requirements`, and ordered `steps` to select PRD-supported chapters without guessing. The `decision_policy` is `do_not_guess_product_meaning`; use `manual_authoring_summary` for queue counts and `active_work` for the selected task, next required evidence, next repair action, stop condition, and verify/refresh commands before drilling into task details. Run scaffold and structure command `argv` from the plan only after source review confirms the `key=PRD Heading` mappings. Follow `manual_authoring_tasks[]` by `sequence` only after resolving `status: decision_required` with PRD evidence or an omission decision, and satisfy `required_evidence[]` before phase verification. Use `required_evidence[].status` and `evidence_repair_actions[]` with `repair_strategy`, `verify_command`, and `refresh_command` to route deterministic repairs before manual review.

After `design-derivation` passes, run `bin/governance scaffold design <target> --check --json` if standard design files are missing, inspect `would_create`, `would_skip`, and `would_index`, then run it without `--check` when the plan is correct. Expect the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md` and table skeletons for the acceptance matrix, roadmap, task board, and verification log. Use successful scaffold `local_commands` for checks and inspect `scaffold_phase`; if `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved. When the recorded phase is `design-derivation`, run `bin/governance design plan <target> --json`; use returned `source_documents`, `tracks`, `active_work`, `sequence`, local workflow `skills`, authority-routing `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `primary_skill`, `primary_specialist_skill`, `references`, `documents`, `blockers`, and `steps` to load the architecture, UI, API, backend, data-model, frontend, test, planning, and ADR skills in order before replacing placeholders. Follow each requirement's `type`, `available_in_workflow_pack`, `availability_scope`, and `missing_policy`; follow `skill_loading_plan.steps[]` by `sequence`, loading local workflow skills from the workflow-pack path before authority-routing skills from the agent environment. If an authority-routing requirement cannot be loaded from the agent environment, obey `missing_policy: load_from_agent_environment_or_stop_before_guessing`. For design authoring payloads, inspect `authoring_summary` for queue counts and use `active_work` for the selected task, next required link, next repair action, authority skill, stop condition, and verify/refresh commands before following `authoring_tasks[]` by `sequence`; use `required_links[].status` and `link_repair_actions` with `repair_strategy`, `verify_command`, and `refresh_command` to repair missing, placeholder, unreadable, or anchor-missing local sources, and use `execution.primary_skill`, `execution.primary_specialist_skill`, `execution.verify_step`, `execution.refresh_step`, `execution.stop_condition`, and `skill_loading_plan` before editing. Do not enter implementation while any `governance:scaffold-placeholder` marker remains.

When working inside a generated target without the source workflow-pack repository open, use `docs/agent-workflow/workflow-pack/` as the local copy of workflows, skills, references, and templates.

## Rules

- Do not derive design from an unarchived product source.
- Do not continue past a `docs/unresolved.md` row whose `Blocking Scope` is not empty, `-`, `none`, `n/a`, `non-blocking`, or `resolved`.
- Do not create a new docs directory unless it is registered in `docs/AGENTS.md`.
- Prefer scripts for deterministic checks; use skills for judgment-heavy classification.
- After initialization, prefer the target-local `bin/governance` runtime copied into the generated repository.
