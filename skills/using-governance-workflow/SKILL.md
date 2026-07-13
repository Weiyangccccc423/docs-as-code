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
| Implementation gate passes and one Ready or In Progress task should be coded | `executing-implementation-task` |
| Any phase claims completion | `verifying-governance-docs` |

## Environment Preflight

Before repair or strict verification, preview environment changes without writing files or installing packages:

```bash
bin/governance env --repair --check --target <target> --json
```

Stop on `ok: false` when missing required tools block the current phase. Inspect `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, `repair_execution`, and `repair_decision`; use `repair_decision.decision`, `repair_decision.stop_before_workflow`, `repair_decision.runnable_action_ids`, `repair_decision.approval_action_ids`, and `repair_decision.manual_action_ids` for the first branch, then use `repair_execution.status`, `repair_execution.can_auto_apply`, `repair_execution.install_attempted`, `repair_execution.install_failed`, `repair_execution.post_repair_missing_required`, `repair_execution.post_repair_missing_recommended`, and `repair_execution.next_step` for detail. Sort `repair_actions` by `sequence`; run actions with `argv` only when `approval_required` is false or approval is explicit, and present `manual-repair` actions to the user. Run `bin/governance env --repair --target <target> --json` only when the repair plan should be written or approved package installation should proceed. Treat `applied_but_unresolved` as a stop state before retrying repairs. When an initialized target returns `local_commands` or `next_actions`, use them to resume from the readable state.

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
When resuming an initialized target, run `bin/governance workflow plan <target> --json` or target-local `make workflow-plan` to inspect the current phase, `blocked` status, active queue summaries, top-level/per-queue `active_work`, local/authority skill routing summaries, ordered `skill_loading_plan` steps, read-only queue commands, `local_commands`, and `next_actions` before choosing a phase-specific skill. Use target-local `make product-plan` or `make design-plan` when the current phase needs the phase-specific authoring plan directly. Use `active_work.queue_id`, `active_work.inspect_command`, `active_work.next_repair_action`, and embedded verify/refresh commands as the first recovery route.

For a single-session execution contract, run `bin/governance workflow work-package <target> --json` or `make work-package`; target-local `.agents/skills` and `.codex/skills` are scanned automatically, and `--skill-root <path>` adds another root. Start only when `package_available` and `can_start` are true. Load `skill_readiness.resolved_requirements`, read every target-local `work_package.read_order` path, including `docs/agent-workflow/workflow-pack/references/` entries, constrain edits to `work_package.write_scope`, follow `next_action`, then verify and refresh. In design derivation, follow `work_stage` in authoring, integration, threat-review, machine-review, reliability-review, review order: `author-design-documents` completes track files, architecture `run-threat-review` records STRIDE/DREAD evidence, API `run-api-review` records contract evidence, backend `run-reliability-review` records SLO applicability and required tool evidence, and `record-design-review` records authority judgment.

When the recorded phase is `implementation`, run `bin/governance implementation plan <target> --json` or target-local `make implementation-plan` before editing code. Use `decision_policy: execute_exactly_one_ready_task`, `implementation_summary`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `read_order`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, and embedded `gate_command`, `start_command`, `verify_command`, `closeout_command`, and `refresh_command` to select one actionable Ready or In Progress `TASK-NNN`, route the next repair blocker, or stop when `active_work.status` is `complete`. For a Ready task, run `implementation start --task TASK-NNN --json` and then the returned apply command or `implementation start --task TASK-NNN --apply --json` before editing code; treat `active_work.status: in_progress` as the resumable execution state. Before marking `Done`, run `bin/governance implementation closeout <target> --task TASK-NNN --json` and require `decision_policy: do_not_mark_done_without_passing_evidence`, `closeout_ready: true`, empty `blocking_requirements[]`, passing `evidence_summary`, and a synchronized `status_update_plan`; when `status_update_plan.can_auto_apply` is true, run the returned `apply_command.argv` or `implementation closeout --task TASK-NNN --apply --json`. Load `executing-implementation-task` and `verifying-governance-docs` from the workflow pack first, then load authority-routing skills such as `senior-fullstack`, `senior-backend`, `senior-qa`, `senior-security`, or `api-design-reviewer` from the agent environment when the plan requires them.
If implementation verification reports `api_review_evidence_stale`, load `api-design-reviewer` and repeat `design api-review --reviewed --min-grade B --check` plus apply before renewing the affected API design review. For `design_review_stale`, run the affected authoring command as a read-only drift plan, load its primary authority skill, and repeat `design review --check` plus apply for that track/work. Do not roll the phase backward or edit stored hashes directly.
If it reports `threat_review_evidence_stale`, refresh architecture scope or mitigations, load `senior-security`, and repeat `design threat-review --reviewed --check` plus apply before renewing the architecture design review.
If it reports `reliability_review_evidence_stale`, refresh backend scope, policy, or source evidence, load `slo-architect`, and repeat `design reliability-review --reviewed --check` plus apply before renewing the backend design review. Do not replace a source-backed `not-applicable` decision with an invented target.

When the recorded phase is `product-structuring`, run `bin/governance product plan <target> --json` before scaffolding product chapters. Use returned `source_documents`, `available_chapters`, `prd_headings`, `suggested_mappings`, `required_decisions`, `chapter_dispositions`, `stale_chapter_dispositions`, `disposition_summary`, `manual_authoring_tasks`, `manual_authoring_summary`, `active_work`, local workflow `skills`, `skill_requirements`, `authority_skill_requirements`, and ordered `steps` to select PRD-supported chapters without guessing. The `decision_policy` is `do_not_guess_product_meaning`; use `manual_authoring_summary` for queue counts and `active_work` for the selected task, next required evidence, next repair action, stop condition, and verify/refresh commands before drilling into task details. When `next_action.kind` is `decide-product-chapter`, run `product disposition` with a concrete reason, `--reviewed`, and `--check` before apply; use `author-required` to keep the evidence-backed authoring task or `omit-unsupported` only for optional chapters absent from the PRD. The decision file is bound to the current PRD hash, and stale dispositions stop verification. Run scaffold and structure command `argv` from the plan only after source review confirms the `key=PRD Heading` mappings. Follow `manual_authoring_tasks[]` by stable `PRODUCT-AUTHOR-NNN` sequence and satisfy `required_evidence[]` before phase verification. Use `required_evidence[].status` and `evidence_repair_actions[]` with `repair_strategy`, `verify_command`, and `refresh_command` to route deterministic repairs before manual review.

After `design-derivation` passes, run `bin/governance scaffold design <target> --check --json` if standard design files are missing, inspect `would_create`, `would_skip`, and `would_index`, then run it without `--check` when the plan is correct. Expect the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md` and table skeletons for the acceptance matrix, roadmap, task board, and verification log. Use successful scaffold `local_commands` for checks and inspect `scaffold_phase`; if `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` lists a `governance:scaffold-placeholder`, retain continuation commands but stop before downstream writes.

When the recorded phase is `design-derivation`, run `bin/governance design plan <target> --json`. Route from ordered `tracks` and each track's `specialist_skills`, `primary_skill`, `primary_specialist_skill`, `blockers`, and requirements; require local skills with `available_in_workflow_pack: true`, and enforce each authority skill `missing_policy` before design judgment. Route system boundaries through `design architecture-authoring`, backend boundaries through `design backend-authoring`, and persistence through `design data-model-authoring`. Inspect `document_status_counts` before link status. For API work, author `docs/api/openapi.json`, then follow `next_action.kind: run-api-review` and preflight `design api-review` before apply; require zero lint errors/warnings, no breaking or potentially breaking changes, and scorecard grade B or better. For backend work, follow `next_action.kind: run-reliability-review`, choose `required` or `not-applicable` from repository sources, and preflight `design reliability-review` before apply. Only then read `references/design-review-checklist.md` and execute `record-design-review`. Do not enter implementation while threat, API, reliability, or design-review evidence is missing, malformed, orphaned, or stale, or while any scaffold placeholder remains.
Full authority coverage remains recorded in `docs/decisions/design-reviews.json`; never substitute machine reports for the track/acceptance authority decision.

When working inside a generated target without the source workflow-pack repository open, use `docs/agent-workflow/workflow-pack/` as the local copy of workflows, skills, references, and templates.

## Rules

- Do not derive design from an unarchived product source.
- Do not continue past a `docs/unresolved.md` row whose `Blocking Scope` is not empty, `-`, `none`, `n/a`, `non-blocking`, or `resolved`.
- Do not create a new docs directory unless it is registered in `docs/AGENTS.md`.
- Prefer scripts for deterministic checks; use skills for judgment-heavy classification.
- After initialization, prefer the target-local `bin/governance` runtime copied into the generated repository.
