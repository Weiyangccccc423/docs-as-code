# Workflow Overview

This workflow turns an empty folder and a product document into a repository ready for reliable agent-driven implementation.

## Operating Model

Each phase has:

- **Input:** files or decisions required before starting
- **Skills:** agent skills to load before acting
- **Procedure:** ordered work steps
- **Output:** files that must exist after the phase
- **Verification:** deterministic checks or review gates
- **Stop conditions:** cases where the agent must ask instead of guessing

Use `references/community-practices.md` to calibrate this workflow against recognized docs-as-code, architecture, API, ADR, quality, and security practices without treating any single framework as a rigid template. Use `references/workflow-routing-checklist.md` when choosing or resuming phases, interpreting JSON continuation payloads, or deciding whether a blocker requires a phase-specific repair skill.

## Runtime Model

Core governance commands are implemented as POSIX shell wrappers plus Python standard-library scripts. Normal operation must run without package installation or network access; `env --repair` may install supported system packages only under the repair policy in `references/runtime-strategy.md`.

From the source workflow-pack checkout, run the disposable end-to-end dry run before relying on the pack for a new project:

```bash
make dry-run
make dry-run-golden
python3 scripts/dry_run_workflow.py --json
python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json
```

The dry run creates a temporary target, imports a sample product document, executes every fixed target-local Make entry exposed to agents, advances through product structuring and design derivation, builds the architecture, API, backend, data-model, UI interaction, frontend, test, implementation-planning, and ADR authoring queues, confirms the implementation gate remains blocked until design scaffold placeholders are replaced with source-backed content, then writes minimal source-backed design and delivery docs, advances to implementation, claims one Ready task as `In Progress`, proves implementation closeout blocks `Done` until passing local evidence is linked, applies synchronized closeout status updates through the CLI, confirms implementation/workflow plans report `complete`, and proves runtime refresh preserves that completion state.
The explicit product fixture command runs the same workflow against a realistic multi-acceptance product document so queue counts prove they scale beyond the one-criterion sample.

When the source workflow pack needs to move to another workspace or agent environment, export it instead of copying ad hoc files:

```bash
make package
python3 scripts/export_workflow_pack.py --check --json
python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json
python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json
```

The export writes `pack-manifest.json` with SHA-256 evidence for the included source-pack files, runs `verify_pack` on the exported directory, and can create a tar.gz artifact for transfer.
The manifest verifier validates `pack-manifest.json` by recomputing file hashes, sizes, executable flags, path safety, duplicate entries, missing files, and unmanifested files.
Use the source-pack authority-skill inventory before high-risk design or implementation routing when you need to audit which agent-environment specialist skills are required:

```bash
make authority-skills
python3 scripts/authority_skills.py --json
python3 scripts/authority_skills.py --strict --json
```

The non-strict inventory is a portable source-pack check. The strict form is an agent-environment readiness gate and should be used only when missing authority-routing skills such as `senior-architect`, `api-design-reviewer`, `senior-backend`, database design skills, `senior-security`, or `ci-cd-pipeline-builder` must stop the session before design guesses.

For a recipient environment that has already unpacked the source workflow-pack artifact, use the consumer bootstrap script to compose source-pack checks and target initialization without manually stitching commands:

```bash
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --check --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --strict-authority-skills --check --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --auto-repair-env --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --workflow-preset product-structure --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --workflow-preset implementation-routing --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-start-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-start-preview --implementation-start-apply --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --implementation-start-preview --implementation-start-apply --implementation-closeout-preview --json
python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --implementation-start-preview --implementation-start-apply --implementation-closeout-preview --implementation-closeout-apply --json
```

Use `--workflow-preset` for common fast paths while keeping the same underlying gates: `product-structure` expands through product structuring apply, `design-scaffold` expands through design scaffold apply, `design-routing` adds read-only design authoring queues, and `implementation-routing` adds read-only implementation readiness plus guarded implementation advance/start/closeout routing. Presets only set existing flags and never bypass source review, dependency checks, write-mode apply rules, or blocker-based skips. Inspect `workflow_preset_expanded_flags` in JSON before treating a preset run as approved.

The bootstrap script runs `verify_pack_manifest`, `verify_pack`, non-strict `authority_skill_inventory`, `env --repair --check`, `init --check`, write-mode `init`, then target-local `bin/governance verify . --check --json`, `make governance-status`, and `make workflow-plan`. Its success payload includes `authority_skill_inventory`, `strict_authority_skills`, `local_commands`, and `next_actions` so agents can continue from the generated target without rerunning `status`. Use `--strict-authority-skills` when missing authority-routing skills must fail before environment checks or target writes.
When `--auto-repair-env` is supplied, the bootstrap script may run write-mode `env --repair --json` and then re-run `env --repair --check --json`, but only when the initial preflight reports `repair_decision.decision: run_repair_actions`, no approval/manual action IDs, and `repair_execution.can_auto_apply: true`. Inspect `env_auto_repair.applied`, `env_auto_repair.skipped`, `env_auto_repair.skip_reason`, `env_auto_repair.decision`, `env_auto_repair.status`, `env_auto_repair.stop_before_workflow`, `env_auto_repair.can_continue`, `env_auto_repair.can_auto_apply`, `env_auto_repair.requires_approval`, `env_auto_repair.manual_repair_required`, `env_auto_repair.runnable_action_ids`, `env_auto_repair.approval_action_ids`, `env_auto_repair.manual_action_ids`, `env_auto_repair.next_step`, `env_auto_repair.final_env_check_ok`, `env_auto_repair.final_missing_required`, and `env_auto_repair.final_env_check` before continuing.
When `--advance-product-structuring` is supplied, it additionally runs target-local product-structuring advance preflight/apply commands and `make product-plan`, so the returned payload includes the product authoring queue. Treat that option as a state-writing shortcut, not a read-only inspection.
When `--product-scaffold-preview` is supplied with `--advance-product-structuring`, the bootstrap script uses `product_plan.suggested_mappings` to run target-local `bin/governance scaffold product . --chapter <chapter> ... --check --json`. The returned `product_scaffold_preview` payload reports selected chapters, `command_args`, unresolved `required_decisions`, and the scaffold preflight's `would_create`, `would_skip`, and `would_index` without writing product chapter files. If no conservative mappings exist, the preview is skipped instead of guessing chapter support.
When `--product-structure-preview` is also supplied, the bootstrap script copies the initialized target into a temporary sandbox, applies the selected product scaffold inside that sandbox, then runs `bin/governance product structure . --chapter "key=PRD Heading" ... --check --json` from conservative `product_plan.suggested_mappings[].command_arg` values. The returned `product_structure_preview` payload uses `preview_mode: sandboxed_no_target_writes`, reports `would_update`, and must still be treated as a source-review aid rather than approval to write real product chapters.
When `--product-structure-apply` is also supplied, the bootstrap script writes the selected product scaffold to the real target, runs `product structure --check --json`, then applies `product structure --json` using only conservative `product_plan.suggested_mappings[].command_arg` values. The returned `product_structure_apply` payload uses `writes_state: true`, includes scaffold, structure preflight, structure apply, post-status, and post-workflow-plan payloads, and still does not resolve unsupported chapters or manual authoring decisions.
When `--advance-design-derivation` is also supplied, the bootstrap script requires `--product-structure-apply`, runs target-local `bin/governance verify . --check --json`, advances to `design-derivation` with preflight/apply commands, refreshes target-local status and workflow plan, and returns `make design-plan` output as `design_derivation` and top-level `design_plan`. It does not run `scaffold design`; design scaffold placeholders are a separate authoring step and must not be treated as completed design.
When `--design-scaffold-preview` is also supplied, the bootstrap script requires `--advance-design-derivation`, runs target-local `bin/governance scaffold design . --check --json`, and returns `design_scaffold_preview` with `writes_state: false`, `would_create`, `would_skip`, and `would_index`. Treat it as the consumer bootstrap form of `scaffold design --check --json`. It does not write design placeholders, so follow-on design authoring still needs explicit approval before running write-mode `scaffold design`.
When `--design-scaffold-apply` is also supplied, the bootstrap script requires `--design-scaffold-preview`, runs target-local write-mode `scaffold design`, then runs `verify --check --json` expecting `governance_scaffold_placeholder` blockers. The returned `design_scaffold_apply` payload uses `writes_state: true`, includes scaffold output, post-status, post-workflow-plan, the failing post-verify payload, and `post_verify_blocked_by_placeholders: true`; agents must treat that as the design authoring queue being prepared, not completed.
When `--design-authoring-preview` is also supplied, the bootstrap script requires `--design-scaffold-apply`, runs read-only target-local `design architecture-authoring`, `design api-authoring`, `design backend-authoring`, and the remaining design authoring queue commands, and returns `design_authoring_preview` with queue payloads for skill loading, blockers, active work, and repair actions without writing design content.
When `--implementation-readiness-preview` is also supplied, the bootstrap script requires `--design-authoring-preview`, runs read-only target-local `verify --check`, `gate implementation`, and `implementation plan` commands, and returns `implementation_readiness_preview` with readiness booleans plus the raw blocker payloads without advancing implementation or claiming a task.
When `--implementation-advance-preview` is also supplied, the bootstrap script requires `--implementation-readiness-preview`, runs read-only target-local `advance implementation --check`, and returns `implementation_advance_preview` with `advance_ready`, `would_advance`, gate blockers, and `would_state` from the raw preflight payload without recording the implementation phase.
When `--implementation-advance-apply` is also supplied, the bootstrap script requires `--implementation-advance-preview`, records the implementation phase only after the advance preflight passes, refreshes target-local verify/status/workflow/implementation routing with `make implementation-plan`, and returns `implementation_advance_apply`; when the preview is blocked, it skips without writing state.
When `--implementation-start-preview` is also supplied, the bootstrap script requires `--implementation-readiness-preview`, reads `implementation_plan.active_work.task_id`, and runs read-only target-local `implementation start` for the selected `TASK-NNN` only when readiness passes. The returned `implementation_start_preview` reports `start_ready`, blockers, and status update planning without applying task status updates.
When `--implementation-start-apply` is also supplied, the bootstrap script requires `--implementation-start-preview`, applies the safe `In Progress` task status update only after the start preview passes, refreshes target-local verify/status/workflow/implementation routing with `make implementation-plan`, and returns `implementation_start_apply`; when the preview is blocked, it skips without writing state.
When `--implementation-closeout-preview` is also supplied, the bootstrap script requires `--implementation-start-apply`, reads the active `TASK-NNN` from the post-start implementation plan, and runs read-only target-local `implementation closeout`. The returned `implementation_closeout_preview` reports `closeout_ready`, verification evidence blockers, and status update planning without applying `Done` status updates.
When `--implementation-closeout-apply` is also supplied, the bootstrap script requires `--implementation-closeout-preview`, applies the synchronized `Done` status update only after closeout evidence passes, refreshes target-local verify/status/workflow/implementation routing with `make implementation-plan`, and returns `implementation_closeout_apply`; when closeout blockers remain, it skips without writing state.
Implementation-routing preview/apply payloads that skip a downstream action keep the human `skip_reason` and also expose `skip_code`, `blocked_by`, and the relevant prerequisite boolean such as `required_preview_ready`, `required_readiness_ok`, or `required_start_applied`; branch on those fields before interpreting prose.

To prove the transfer artifact is self-contained, smoke-test it with a command that unpacks the tar.gz artifact and runs checks from the unpacked workflow pack:

```bash
make artifact-smoke
python3 scripts/smoke_workflow_pack_artifact.py --json
python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json
```

The default artifact smoke exports a temporary archive before checking it. Use `--archive` after `make package` to validate the exact tar.gz artifact intended for handoff. The artifact smoke also initializes a separate fresh target directory that contains only a product document, verifies the target-local `bin/governance`, `make governance-status`, and `make workflow-plan` commands from that generated target, and runs consumer bootstrap from the unpacked artifact with `--auto-repair-env --workflow-preset product-structure`, `--auto-repair-env --workflow-preset design-scaffold`, `--auto-repair-env --workflow-preset design-routing`, and `--auto-repair-env --workflow-preset implementation-routing`. The implementation-routing smoke proves guarded implementation commands route correctly and stay blocked while scaffold placeholders remain.

Before tagging or handing off a source workflow-pack release, run the release readiness gate and use `references/release-readiness-checklist.md` as the rubric:

```bash
make release-check
python3 scripts/release_readiness.py --json
```

Generated target repositories receive their own copy of `bin/` and `scripts/` plus `docs/agent-workflow/runtime-manifest.json`. After initialization, prefer the target-local CLI:

```bash
bin/governance verify .
bin/governance env --repair --check --target . --json
bin/governance env --repair --target . --json
```

Generated targets also provide stable Makefile entries for common agent checks:

```bash
make verify-governance
make verify-check
make governance-status
make workflow-plan
make product-plan
make design-plan
make implementation-plan
make check-env
make repair-env-check
```

Machine-readable `local_commands` entries include `cwd`, a human-readable `command`, structured `argv`, `writes_state`, and `approval_required`; agents should run `argv` from `cwd` instead of reparsing `command`, prefer `writes_state: false` entries for read-only inspection, and stop before any `approval_required: true` command unless the task explicitly authorizes it.

Machine-readable `init --json` and `status --json` success payloads include `local_commands` and `next_actions`. `env --json`, `verify --check --json`, and `verify --json` payloads include both fields when governance state is readable and the command is otherwise successful. `workflow plan --json` is read-only and returns the current `phase`, phase-specific queue `commands`, compact `queues[]` summaries, top-level and per-queue `active_work`, top-level and per-queue `skill_summary` objects for local workflow skills and authority-routing skills, top-level and per-queue `skill_loading_plan` objects with ordered load steps and stop conditions, `blocked`, `local_commands`, and `next_actions` without advancing state. Use top-level `active_work.queue_id`, `active_work.inspect_command`, `active_work.next_repair_action`, and embedded verify/refresh commands to resume from the first blocked queue before manually drilling into every task. Use `skill_summary.authority_routing_skills` to identify specialist skills such as `senior-architect`, `api-design-reviewer`, `senior-backend`, database design skills, `senior-frontend`, `a11y-audit`, and `senior-security`; use `skill_loading_plan.steps[]` to load local workflow skills first, then authority-routing skills from the agent environment before design guesses. `gate --json` payloads include `local_commands` when governance state is readable, and include `next_actions` only when the gate passes. Successful `product plan --json` payloads include `source_documents`, `available_chapters`, `prd_headings`, conservative `suggested_mappings`, `required_decisions`, `manual_authoring_tasks`, `manual_authoring_summary`, `active_work`, local workflow `skills`, `skill_requirements`, `authority_skill_requirements`, and executable `steps`, plus `local_commands` and `next_actions` when the recorded phase is `product-structuring`; agents should follow its `decision_policy: do_not_guess_product_meaning` before running scaffold or structure apply commands. `manual_authoring_summary` reports `task_count`, `open_decision_count`, `required_evidence_status_counts`, `non_satisfied_required_evidence_count`, and `evidence_repair_action_count` for queue routing before task inspection. `active_work` points at the first product manual-authoring task, blocker/open-decision counts, next required evidence, next repair action, stop condition, and verify/refresh commands. `manual_authoring_tasks[]` items stay `status: decision_required` until the PRD proves the chapter is supported, and list `execution`, `required_sections`, `required_links`, `required_evidence`, `evidence_repair_actions`, `open_decisions`, and verify/refresh steps. Each `required_evidence[]` item includes a conservative machine-readable `status` so agents can route missing files, missing indexes, missing metadata links, placeholders, pending manual review, and satisfied evidence without reinterpreting prose; `evidence_repair_actions` provide `repair_strategy`, `verify_command`, and `refresh_command` for every non-satisfied evidence item. Successful write-mode `scaffold product --json` and `scaffold design --json` payloads include both fields when the gate state is readable, plus `scaffold_phase` with recorded and expected workflow phase details. When `scaffold_phase.matches` is false, agents must keep following returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. When scaffolded files still contain `governance:scaffold-placeholder`, the payload also includes `next_actions_blocked_by`; agents must keep `next_actions` for later but must not run them until each listed blocker is resolved. Successful `design plan --json` payloads include `source_documents`, ordered `tracks` with required `skills`, authority-routing `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `references`, `documents`, per-track `blockers`, `active_work`, and executable `steps`, plus `local_commands` and `next_actions` when the recorded phase is `design-derivation`; agents should use these tracks to load architecture, API, backend, data-model, UI interaction, frontend, test, planning, and ADR skills in order before replacing placeholders. Each design authoring payload includes `authoring_summary` with `task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count` before `authoring_tasks[]`; it also includes `active_work` with the selected authoring task, next required link, next repair action, authority skill, stop condition, and verify/refresh commands. Each `skill_requirements[]` object declares `type`, `available_in_workflow_pack`, `availability_scope`, and `missing_policy`; each `skill_loading_plan.steps[]` item declares `action`, `load_from`, and `missing_policy`; authority-routing skills with `missing_policy: load_from_agent_environment_or_stop_before_guessing` must be loaded from the agent environment or treated as stop conditions before design guesses. Successful `implementation plan --json` payloads include `source_documents`, `implementation_summary`, `gate`, `gate_ok`, `active_work`, `tasks[]`, `source_references`, `read_order`, local workflow `skills`, authority-routing `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, and embedded `gate_command`, `start_command`, `verify_command`, `closeout_command`, and `refresh_command`; agents must follow `decision_policy: execute_exactly_one_ready_task`, use `implementation start --task TASK-NNN --json` plus the returned apply command to claim one Ready task as `In Progress`, and treat `active_work.status: in_progress` as a resumable execution state. Successful `implementation start --task TASK-NNN --json` payloads include `decision_policy: claim_exactly_one_ready_task_before_editing_code`, `start_ready`, `requirements[]`, `blocking_requirements[]`, and `status_update_plan`; when `status_update_plan.can_auto_apply` is true, run the returned `apply_command.argv` or `implementation start --apply --json`, which returns `apply_requested`, `applied`, `updated_paths`, `pre_apply_status_update_plan`, and `post_apply_status_update_plan`. Treat `implementation_summary.execution_complete: true` plus `active_work.status: complete` as the normal terminal state. Successful `implementation closeout --task TASK-NNN --json` payloads include `decision_policy: do_not_mark_done_without_passing_evidence`, `closeout_ready`, `requirements[]`, `blocking_requirements[]`, `evidence_summary`, and `status_update_plan` so agents can prove verification evidence before marking `Done`; when `status_update_plan.can_auto_apply` is true, run the returned `apply_command.argv` or `implementation closeout --apply --json`, which returns `apply_requested`, `applied`, `updated_paths`, `pre_apply_status_update_plan`, and `post_apply_status_update_plan`. When the recorded phase is `implementation`, `workflow plan --json` exposes an `implementation-plan` queue and top-level `active_work` for the first actionable Ready or In Progress `TASK-NNN`, the next repair blocker, or `status: complete` when every task is Done with passing verification evidence. Successful state-writing `product mark-ready --json`, `advance --json`, `runtime refresh --json`, `implementation start --apply --json`, and `implementation closeout --apply --json` commands return machine-readable continuation fields where available so agents can continue without rerunning `status`. Each action includes `cwd`, a human-readable `command`, structured `argv`, `writes_state`, `approval_required`, `sequence`, and `success_condition`; preflight actions include `preflight_for`, apply actions include `requires_action`. Agents should run `argv` from `cwd` instead of reparsing `command`, sort actions by `sequence`, execute `preflight` actions first, and run state-writing `apply` actions only after the action named by `requires_action` returns `ok: true`.

From a trusted source workflow-pack checkout, refresh generated target runtime and workflow-pack snapshot files without rewriting product or design documents:

```bash
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

Use `runtime refresh --check --json` as a no-write plan. After successful write-mode `runtime refresh --json`, follow returned `local_commands[].argv` and `next_actions[].argv` from their reported `cwd`.

Generated targets also receive `docs/agent-workflow/workflow-pack/`, a hash-manifested snapshot of this pack's workflows, skills, references, and templates. Use it as the target-local operating manual when the source pack repository is not open.

Node.js tooling is an optional project-specific enhancement layer. Rust is reserved for future stable accelerators or single-binary distribution. See `references/runtime-strategy.md`.

## Phase Map

| Phase | Purpose | Primary skill |
| --- | --- | --- |
| 01 | Empty repository initialization | `initializing-governance-repo` |
| 02 | Product document archiving | `archiving-product-document` |
| 03 | Product structuring | `structuring-product-requirements` |
| 04 | Design derivation | `designing-system-architecture`, `designing-ui-interactions`, `designing-api-contracts`, `designing-backend-modules`, `designing-data-models`, `capturing-architecture-decisions`, `designing-frontend-modules`, `designing-test-strategy`, `planning-implementation-work` |
| 05 | Verification and drift control | `verifying-governance-docs` |
| 06 | Implementation execution | `executing-implementation-task` |

Before moving between phases, run the matching gate:

```bash
bin/governance gate product-structuring <target> --json
bin/governance gate design-derivation <target> --json
bin/governance gate implementation <target> --json
```

When the phase is actually changing, prefer `advance`; it runs the matching gate and records the transition in `.governance/state.json`. `advance` records adjacent transitions one phase at a time and cannot skip phases; use `gate` for repeated checks or earlier-phase audits:

```bash
bin/governance advance product-structuring <target> --check --json
bin/governance advance product-structuring <target> --json
bin/governance advance design-derivation <target> --check --json
bin/governance advance design-derivation <target> --json
bin/governance advance implementation <target> --check --json
bin/governance advance implementation <target> --json
```

After the product-structuring gate passes, build a read-only product structuring plan, then use the deterministic product scaffold to create only source-supported product chapters:

```bash
bin/governance product plan <target> --json
bin/governance scaffold product <target> --chapter goals-and-requirements --chapter acceptance-criteria --check --json
bin/governance scaffold product <target> --chapter goals-and-requirements --chapter acceptance-criteria --json
```

Use `product plan --json` to inspect `source_documents`, `available_chapters`, `prd_headings`, `suggested_mappings`, `required_decisions`, `manual_authoring_tasks`, `manual_authoring_summary`, `active_work`, `skills`, `skill_requirements`, `authority_skill_requirements`, and ordered `steps` before selecting product chapters. Its `decision_policy` is `do_not_guess_product_meaning`; only run returned scaffold and structure `argv` after source review confirms the `key=PRD Heading` mapping or the required decision is manually resolved. Use `manual_authoring_summary` to scan evidence status counts and repair-action counts, then use `active_work` for the current task, next evidence repair, stop condition, and verify/refresh commands before drilling into `manual_authoring_tasks[]` for unsupported-by-heading chapters. Satisfy each task's `required_evidence` before phase verification. Use `required_evidence[].status` as the repair signal before reading the longer `condition`, then follow `evidence_repair_actions[]` by `sequence` for its `repair_strategy`, `verify_command`, and `refresh_command`.

After the design-derivation gate passes, use the deterministic design scaffold when standard design files are missing:

```bash
bin/governance scaffold design <target> --check --json
bin/governance scaffold design <target> --json
bin/governance design plan <target> --json
bin/governance design api-candidates <target> --json
bin/governance design architecture-authoring <target> --json
bin/governance design api-authoring <target> --json
bin/governance design backend-authoring <target> --json
bin/governance design data-model-authoring <target> --json
bin/governance design ui-interaction-authoring <target> --json
bin/governance design frontend-authoring <target> --json
bin/governance design test-strategy-authoring <target> --json
bin/governance design implementation-planning-authoring <target> --json
bin/governance design architecture-decisions-authoring <target> --json
```

Use `--check` to inspect `would_create`, `would_skip`, and `would_index` before writing `governance:scaffold-placeholder` markers. The design scaffold includes the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md` and standard table skeletons for the acceptance matrix, roadmap, task board, and verification log. Scaffold placeholders block verification until replaced with product-derived content. Use `design plan --json` after the scaffold to inspect `source_documents`, ordered `tracks`, `sequence`, required local workflow `skills`, authority-routing `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `primary_skill`, `primary_specialist_skill`, `references`, `documents`, current `blockers`, `active_work`, and per-track `steps` before authoring design content. Use `design api-candidates --json` to extract source-backed API `candidates` from product acceptance criteria, including each `acceptance_id`, source `reference`, `suggested_endpoint_file`, `replaceable_starter_endpoint`, `open_decisions`, `active_work`, and `specialist_skills` such as `api-design-reviewer`, `senior-backend`, and `senior-security`; do not guess API method/path, fields, errors, auth, or frontend consumers from this candidate list alone. Design authoring `required_links[]` entries include machine-readable `required_links[].status` values for missing targets, unresolved anchors, scaffold placeholders, unreadable Markdown, and satisfied local links; `link_repair_actions` provide `repair_strategy`, `verify_command`, and `refresh_command` for every non-satisfied link while keeping `open_decisions` as unresolved design questions. Every design authoring payload includes `active_work`; use it for the current task, blocker/open-decision counts, next required link, next repair action, authority skill, stop condition, and verify/refresh commands before drilling into all tasks. Use `design architecture-authoring --json` before downstream design work; its `decision_policy` is `do_not_guess_architecture_boundaries`, and the payload plus each `authoring_tasks[]` item lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, architecture `documents`, required `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, unresolved `open_decisions` such as `system_boundary`, `container_responsibilities`, `quality_scenarios`, `deployment_assumptions`, and `adr_candidates`, `specialist_skills` such as `senior-architect`, `senior-security`, `observability-designer`, and `slo-architect`, authority-routing `missing_policy`, plus read-only command steps verify-architecture-authoring and refresh-architecture-authoring. Use `design api-authoring --json` next; its `decision_policy` is `do_not_guess_contract_details`, and the payload plus each `authoring_tasks[]` item lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, target `documents`, required `sections`, `required_links`, unresolved `open_decisions`, `specialist_skills` such as `api-design-reviewer`, `senior-backend`, and `senior-security`, plus read-only command steps verify-api-authoring and refresh-api-authoring. Use `design backend-authoring --json` for backend module and external-service work; its `decision_policy` is `do_not_guess_backend_boundaries`, and the payload plus each `authoring_tasks[]` item lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, backend `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `module_boundaries` and `observability`, `specialist_skills` such as `senior-backend`, `observability-designer`, and `senior-security`, plus read-only command steps verify-backend-authoring and refresh-backend-authoring. Use `design data-model-authoring --json` for entity/schema/migration work; its `decision_policy` is `do_not_guess_data_model`, and the payload plus each `authoring_tasks[]` item lists data-model `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `entity_ownership`, `transaction_boundaries`, `migration_order`, and `rollback_strategy`, `specialist_skills` such as `database-designer`, `database-schema-designer`, `migration-architect`, `senior-backend`, and `senior-security`, plus read-only command steps verify-data-model-authoring and refresh-data-model-authoring. Use `design ui-interaction-authoring --json` for visible flow, screen, state, error, accessibility, and copy work; its `decision_policy` is `do_not_guess_ui_behavior`, and the payload plus each `authoring_tasks[]` item lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, UI `documents`, required `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, unresolved `open_decisions` such as `primary_flows`, `screens`, `states`, `error_actions`, `accessibility`, and `copy_and_content`, `specialist_skills` such as `senior-frontend` and `a11y-audit`, authority-routing `missing_policy`, plus read-only command steps verify-ui-interaction-authoring and refresh-ui-interaction-authoring. Use `design frontend-authoring --json` for frontend module and API-consumption work after UI interaction exists; its `decision_policy` is `do_not_guess_frontend_behavior`, and `authoring_tasks[]` lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, frontend `documents`, required `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, unresolved `open_decisions` such as `state_ownership` and `error_actions`, `specialist_skills` such as `senior-frontend`, `a11y-audit`, and `performance-profiler`, authority-routing `missing_policy`, plus read-only command steps verify-frontend-authoring and refresh-frontend-authoring. Use `design test-strategy-authoring --json` for verification work; its `decision_policy` is `do_not_guess_verification_scope`, and `authoring_tasks[]` lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, test `documents`, required `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, unresolved `open_decisions` such as `acceptance_coverage` and `evidence_targets`, `specialist_skills` such as `senior-qa`, `playwright-pro`, `a11y-audit`, and `security-pen-testing`, authority-routing `missing_policy`, plus read-only command steps verify-test-strategy-authoring and refresh-test-strategy-authoring. Use `design implementation-planning-authoring --json` for delivery planning work; its `decision_policy` is `do_not_guess_task_scope`, and `authoring_tasks[]` lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, development `documents`, required `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, unresolved `open_decisions` such as `task_scope`, `ready_criteria`, `verification_plan`, and `agent_handoff`, `specialist_skills` such as `senior-fullstack`, `ci-cd-pipeline-builder`, and `tech-debt-tracker`, authority-routing `missing_policy`, plus read-only command steps verify-implementation-planning-authoring and refresh-implementation-planning-authoring. Use `design architecture-decisions-authoring --json` for ADR trigger review; its `decision_policy` is `do_not_guess_architecture_decisions`, and `authoring_tasks[]` lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, ADR `documents`, required `sections`, `required_links`, `required_links[].status`, `required_link_status_counts`, `non_satisfied_required_link_count`, `link_repair_actions`, `link_repair_action_count`, `repair_strategy`, `verify_command`, `refresh_command`, unresolved `open_decisions` such as `adr_trigger`, `decision_scope`, and `alternatives`, `requires_adr: undetermined`, `specialist_skills` such as `senior-architect`, `migration-architect`, and `tech-stack-evaluator`, authority-routing `missing_policy`, plus read-only command steps verify-architecture-decisions-authoring and refresh-architecture-decisions-authoring.
After successful write-mode scaffold commands, use returned `local_commands[].argv` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, continue phase advancement through returned `next_actions[].argv` in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, do not run downstream state-writing actions until each listed placeholder blocker is replaced with source-backed content.

## Source-of-Truth Flow

```text
original product document
  -> docs/product/core/PRD.md
  -> docs/product/core/product-meta.md
  -> docs/product/NN-*.md
  -> docs/ui + docs/api + docs/architecture
  -> docs/backend + docs/frontend + docs/tests
  -> docs/development task board
  -> code implementation
  -> docs/development verification evidence
```

## Minimal Success Criteria

- The original product document is preserved.
- Derived documents never silently invent product meaning.
- All open questions are registered in `docs/unresolved.md`.
- Every non-empty docs domain has `README.md` and `AGENTS.md`.
- Implementation tasks link back to existing local Markdown product, design, API, and acceptance sources.
- Governance verification passes before implementation starts.
- Implementation execution changes exactly one `Ready` or `In Progress` task at a time unless the task board explicitly groups the work.
