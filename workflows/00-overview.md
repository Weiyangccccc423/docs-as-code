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

The dry run creates a temporary target, imports a sample product document, advances through product structuring and design derivation, builds the API, backend, frontend, test, implementation-planning, and ADR authoring queues, and confirms the implementation gate remains blocked until design scaffold placeholders are replaced with source-backed content.
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

To prove the transfer artifact is self-contained, smoke-test it with a command that unpacks the tar.gz artifact and runs checks from the unpacked workflow pack:

```bash
make artifact-smoke
python3 scripts/smoke_workflow_pack_artifact.py --json
```

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
make check-env
make repair-env-check
```

Machine-readable `local_commands` entries include `cwd`, a human-readable `command`, structured `argv`, `writes_state`, and `approval_required`; agents should run `argv` from `cwd` instead of reparsing `command`, prefer `writes_state: false` entries for read-only inspection, and stop before any `approval_required: true` command unless the task explicitly authorizes it.

Machine-readable `init --json` and `status --json` success payloads include `local_commands` and `next_actions`. `env --json`, `verify --check --json`, and `verify --json` payloads include both fields when governance state is readable and the command is otherwise successful. `workflow plan --json` is read-only and returns the current `phase`, phase-specific queue `commands`, compact `queues[]` summaries, top-level and per-queue `active_work`, top-level and per-queue `skill_summary` objects for local workflow skills and authority-routing skills, top-level and per-queue `skill_loading_plan` objects with ordered load steps and stop conditions, `blocked`, `local_commands`, and `next_actions` without advancing state. Use top-level `active_work.queue_id`, `active_work.inspect_command`, `active_work.next_repair_action`, and embedded verify/refresh commands to resume from the first blocked queue before manually drilling into every task. Use `skill_summary.authority_routing_skills` to identify specialist skills such as `senior-architect`, `api-design-reviewer`, `senior-backend`, database design skills, and `senior-security`; use `skill_loading_plan.steps[]` to load local workflow skills first, then authority-routing skills from the agent environment before design guesses. `gate --json` payloads include `local_commands` when governance state is readable, and include `next_actions` only when the gate passes. Successful `product plan --json` payloads include `source_documents`, `available_chapters`, `prd_headings`, conservative `suggested_mappings`, `required_decisions`, `manual_authoring_tasks`, `manual_authoring_summary`, `active_work`, local workflow `skills`, `skill_requirements`, `authority_skill_requirements`, and executable `steps`, plus `local_commands` and `next_actions` when the recorded phase is `product-structuring`; agents should follow its `decision_policy: do_not_guess_product_meaning` before running scaffold or structure apply commands. `manual_authoring_summary` reports `task_count`, `open_decision_count`, `required_evidence_status_counts`, `non_satisfied_required_evidence_count`, and `evidence_repair_action_count` for queue routing before task inspection. `active_work` points at the first product manual-authoring task, blocker/open-decision counts, next required evidence, next repair action, stop condition, and verify/refresh commands. `manual_authoring_tasks[]` items stay `status: decision_required` until the PRD proves the chapter is supported, and list `execution`, `required_sections`, `required_links`, `required_evidence`, `evidence_repair_actions`, `open_decisions`, and verify/refresh steps. Each `required_evidence[]` item includes a conservative machine-readable `status` so agents can route missing files, missing indexes, missing metadata links, placeholders, pending manual review, and satisfied evidence without reinterpreting prose; `evidence_repair_actions` provide `repair_strategy`, `verify_command`, and `refresh_command` for every non-satisfied evidence item. Successful write-mode `scaffold product --json` and `scaffold design --json` payloads include both fields when the gate state is readable, plus `scaffold_phase` with recorded and expected workflow phase details. When `scaffold_phase.matches` is false, agents must keep following returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. When scaffolded files still contain `governance:scaffold-placeholder`, the payload also includes `next_actions_blocked_by`; agents must keep `next_actions` for later but must not run them until each listed blocker is resolved. Successful `design plan --json` payloads include `source_documents`, ordered `tracks` with required `skills`, authority-routing `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `references`, `documents`, per-track `blockers`, `active_work`, and executable `steps`, plus `local_commands` and `next_actions` when the recorded phase is `design-derivation`; agents should use these tracks to load architecture, API, backend, data-model, frontend, test, planning, and ADR skills in order before replacing placeholders. Each design authoring payload includes `authoring_summary` with `task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count` before `authoring_tasks[]`; it also includes `active_work` with the selected authoring task, next required link, next repair action, authority skill, stop condition, and verify/refresh commands. Each `skill_requirements[]` object declares `type`, `available_in_workflow_pack`, `availability_scope`, and `missing_policy`; each `skill_loading_plan.steps[]` item declares `action`, `load_from`, and `missing_policy`; authority-routing skills with `missing_policy: load_from_agent_environment_or_stop_before_guessing` must be loaded from the agent environment or treated as stop conditions before design guesses. Successful state-writing `product mark-ready --json`, `advance --json`, and `runtime refresh --json` commands also return both fields so agents can continue without rerunning `status`. Each action includes `cwd`, a human-readable `command`, structured `argv`, `writes_state`, `approval_required`, `sequence`, and `success_condition`; preflight actions include `preflight_for`, apply actions include `requires_action`. Agents should run `argv` from `cwd` instead of reparsing `command`, sort actions by `sequence`, execute `preflight` actions first, and run state-writing `apply` actions only after the action named by `requires_action` returns `ok: true`.

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
bin/governance design api-authoring <target> --json
bin/governance design backend-authoring <target> --json
bin/governance design frontend-authoring <target> --json
bin/governance design test-strategy-authoring <target> --json
bin/governance design implementation-planning-authoring <target> --json
bin/governance design architecture-decisions-authoring <target> --json
```

Use `--check` to inspect `would_create`, `would_skip`, and `would_index` before writing `governance:scaffold-placeholder` markers. The design scaffold includes the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md` and standard table skeletons for the acceptance matrix, roadmap, task board, and verification log. Scaffold placeholders block verification until replaced with product-derived content. Use `design plan --json` after the scaffold to inspect `source_documents`, ordered `tracks`, `sequence`, required local workflow `skills`, authority-routing `specialist_skills`, `skill_requirements`, `authority_skill_requirements`, `primary_skill`, `primary_specialist_skill`, `references`, `documents`, current `blockers`, `active_work`, and per-track `steps` before authoring design content. Use `design api-candidates --json` to extract source-backed API `candidates` from product acceptance criteria, including each `acceptance_id`, source `reference`, `suggested_endpoint_file`, `replaceable_starter_endpoint`, `open_decisions`, `active_work`, and `specialist_skills` such as `api-design-reviewer`, `senior-backend`, and `senior-security`; do not guess API method/path, fields, errors, auth, or frontend consumers from this candidate list alone. Design authoring `required_links[]` entries include machine-readable `required_links[].status` values for missing targets, unresolved anchors, scaffold placeholders, unreadable Markdown, and satisfied local links; `link_repair_actions` provide `repair_strategy`, `verify_command`, and `refresh_command` for every non-satisfied link while keeping `open_decisions` as unresolved design questions. Every design authoring payload includes `active_work`; use it for the current task, blocker/open-decision counts, next required link, next repair action, authority skill, stop condition, and verify/refresh commands before drilling into all tasks. Use `design api-authoring --json` next; its `decision_policy` is `do_not_guess_contract_details`, and the payload plus each `authoring_tasks[]` item lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, target `documents`, required `sections`, `required_links`, unresolved `open_decisions`, `specialist_skills` such as `api-design-reviewer`, `senior-backend`, and `senior-security`, plus read-only command steps verify-api-authoring and refresh-api-authoring. Use `design backend-authoring --json` for backend/data-model work; its `decision_policy` is `do_not_guess_backend_boundaries`, and the payload plus each `authoring_tasks[]` item lists `skill_requirements`, `authority_skill_requirements`, `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, backend `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `module_boundaries` and `transaction_boundaries`, `specialist_skills` such as `senior-backend`, `database-designer`, `database-schema-designer`, `migration-architect`, `observability-designer`, and `senior-security`, plus read-only command steps verify-backend-authoring and refresh-backend-authoring. Use `design frontend-authoring --json` for UI/frontend work; its `decision_policy` is `do_not_guess_frontend_behavior`, and `authoring_tasks[]` lists `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, UI/frontend `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `state_ownership` and `error_actions`, `specialist_skills` such as `senior-frontend`, `a11y-audit`, and `performance-profiler`, plus read-only command steps verify-frontend-authoring and refresh-frontend-authoring. Use `design test-strategy-authoring --json` for verification work; its `decision_policy` is `do_not_guess_verification_scope`, and `authoring_tasks[]` lists `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, test `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `acceptance_coverage` and `evidence_targets`, `specialist_skills` such as `senior-qa`, `playwright-pro`, `a11y-audit`, and `security-pen-testing`, plus read-only command steps verify-test-strategy-authoring and refresh-test-strategy-authoring. Use `design implementation-planning-authoring --json` for delivery planning work; its `decision_policy` is `do_not_guess_task_scope`, and `authoring_tasks[]` lists `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, development `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `task_scope`, `ready_criteria`, `verification_plan`, and `agent_handoff`, `specialist_skills` such as `senior-fullstack`, `ci-cd-pipeline-builder`, and `tech-debt-tracker`, plus read-only command steps verify-implementation-planning-authoring and refresh-implementation-planning-authoring. Use `design architecture-decisions-authoring --json` for ADR trigger review; its `decision_policy` is `do_not_guess_architecture_decisions`, and `authoring_tasks[]` lists `sequence`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`, ADR `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `adr_trigger`, `decision_scope`, and `alternatives`, `requires_adr: undetermined`, `specialist_skills` such as `senior-architect`, `migration-architect`, and `tech-stack-evaluator`, plus read-only command steps verify-architecture-decisions-authoring and refresh-architecture-decisions-authoring.
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
- Implementation execution changes exactly one Ready task at a time unless the task board explicitly groups the work.
