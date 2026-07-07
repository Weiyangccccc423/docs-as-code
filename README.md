# docs-as-code Workflow Pack

This repository contains a reusable workflow pack for turning an empty folder plus one product document into a governed, docs-as-code project workspace.

## Goal

Create reliable project governance before and during implementation:

- archive the original product document
- record product archive manifest metadata and SHA-256 evidence
- copy a target-local workflow, skill, reference, and template snapshot
- derive structured product, architecture, API, UI, backend, frontend, test, and delivery documents
- keep unresolved decisions explicit
- verify documentation structure and drift
- hand implementation tasks to agents with traceable specs and acceptance criteria
- execute Ready tasks with scoped code changes and local verification evidence

## Package Layout

```text
.
├── bin/          # command wrappers
├── scripts/      # deterministic checks and bootstrap utilities
├── skills/       # agent skills used by the workflow
├── references/   # supporting methods and practice references
├── templates/    # generated repository document templates
├── tests/        # workflow-pack tests
└── workflows/    # phase-by-phase operating procedures
```

## Template Files

- `templates/root/README.md`: generated target root README shape.
- `templates/docs/product/core/PRD.md`: PRD placeholder shape before product source conversion is reviewed.
- `templates/docs/agent-workflow/command-contract.md`: target-local command contract and project verification command registry shape.
- `templates/docs/agent-workflow/task-handoff.md`: agent task handoff and completion criteria shape.
- `templates/docs/api/00-conventions.md`: shared API conventions shape.
- `templates/docs/api/changelog.md`: API contract changelog shape.
- `templates/docs/api/endpoints/README.md`: endpoint contract index shape.
- `templates/docs/api/endpoints/01-endpoint-contract.md`: endpoint contract shape.
- `templates/docs/api/error-codes.md`: API error code registry shape.
- `templates/docs/architecture/01-system-context.md`: system context architecture shape.
- `templates/docs/architecture/02-containers.md`: runtime container architecture shape.
- `templates/docs/architecture/03-quality-attributes.md`: measurable architecture quality attributes shape.
- `templates/docs/backend/01-modules.md`: backend module boundary and API ownership shape.
- `templates/docs/backend/02-data-model.md`: backend data ownership and lifecycle shape.
- `templates/docs/backend/03-external-services.md`: backend external dependency and failure-mode shape.
- `templates/docs/decisions/ADR-template.md`: ADR shape for architecture decisions.
- `templates/docs/development/01-roadmap.md`: implementation roadmap shape.
- `templates/docs/development/02-task-board.md`: implementation task board shape.
- `templates/docs/development/03-verification-log.md`: completion evidence log shape for Done tasks.
- `templates/docs/frontend/01-modules.md`: frontend module, state, and route ownership shape.
- `templates/docs/frontend/02-api-consumption.md`: frontend API consumption and error handling shape.
- `templates/docs/tests/01-strategy.md`: test strategy and quality baseline shape.
- `templates/docs/tests/02-acceptance-matrix.md`: acceptance traceability matrix shape.
- `templates/docs/ui/01-interaction-model.md`: UI flows, states, errors, and accessibility shape.

## Reference Files

- `references/community-practices.md`: external practice calibration.
- `references/architecture-decision-record-checklist.md`: ADR trigger, context, options, rationale, consequences, lifecycle, traceability, and indexing checklist.
- `references/architecture-methods.md`: C4, arc42, ADR, and OpenAPI method notes.
- `references/architecture-quality-checklist.md`: architecture-description, quality-model, scenario, runtime, tradeoff, and implementation-readiness checklist.
- `references/api-design-checklist.md`: API contract, HTTP semantics, error, idempotency, collection, compatibility, and traceability checklist.
- `references/backend-design-checklist.md`: backend and data-design completion checklist.
- `references/backend-operability-checklist.md`: backend service-level, observability, configuration, runtime-control, logging, and runbook checklist.
- `references/data-model-design-checklist.md`: data ownership, identity, constraints, concurrency, indexing, migration, retention, and verification checklist.
- `references/frontend-interaction-checklist.md`: frontend interaction, accessibility, component behavior, state, routing, performance, and handoff checklist.
- `references/governance-verification-checklist.md`: verification command discipline, environment repair, drift refresh, phase gates, repair ordering, traceability, security, and completion-gate checklist.
- `references/implementation-execution-checklist.md`: Ready task intake, coding scope control, verification execution, evidence, security, and completion checklist.
- `references/implementation-readiness-checklist.md`: Ready task, Definition of Done, verification, integration, agent handoff, and supply-chain evidence checklist.
- `references/product-archive-checklist.md`: product source preservation, manifest evidence, conversion fidelity, Markdown portability, review closeout, unresolved import, and handoff-readiness checklist.
- `references/product-requirements-checklist.md`: product source fidelity, requirement quality, acceptance criteria, glossary, unresolved question, and design-readiness checklist.
- `references/repository-initialization-checklist.md`: empty-target safety, environment repair, governance entry points, runtime snapshot, product seed, Git readiness, baseline security, tooling, and handoff-readiness checklist.
- `references/release-readiness-checklist.md`: source-pack release gate, dry-run, export artifact integrity, environment, and release evidence checklist.
- `references/security-design-checklist.md`: security, abuse-case, and supply-chain design checklist.
- `references/test-strategy-checklist.md`: acceptance traceability, test portfolio, automation, test data, non-functional verification, and evidence checklist.
- `references/runtime-strategy.md`: core runtime, optional tooling, and repair policy.
- `references/workflow-routing-checklist.md`: workflow entry classification, JSON continuation, gate/advance, scaffold, repair routing, schema, source-of-truth, and normative-language checklist.

## Skill Files

- `skills/using-governance-workflow/SKILL.md`: workflow router.
- `skills/initializing-governance-repo/SKILL.md`: empty repository bootstrap.
- `skills/archiving-product-document/SKILL.md`: product source preservation and import.
- `skills/structuring-product-requirements/SKILL.md`: product chapter and acceptance structuring.
- `skills/designing-system-architecture/SKILL.md`: system architecture derivation.
- `skills/designing-ui-interactions/SKILL.md`: UI interaction model, flow, state, error, and accessibility design.
- `skills/designing-api-contracts/SKILL.md`: API contract derivation.
- `skills/designing-backend-modules/SKILL.md`: backend module design.
- `skills/designing-data-models/SKILL.md`: persistence and lifecycle design.
- `skills/designing-frontend-modules/SKILL.md`: frontend module, state, route, and API-consumption design.
- `skills/designing-test-strategy/SKILL.md`: test strategy and acceptance traceability design.
- `skills/capturing-architecture-decisions/SKILL.md`: ADR capture.
- `skills/planning-implementation-work/SKILL.md`: roadmap, task board, Ready task, and verification evidence planning.
- `skills/verifying-governance-docs/SKILL.md`: governance verification and repair routing.
- `skills/executing-implementation-task/SKILL.md`: scoped implementation, verification, evidence, and task status execution.

## Quick Start

Before using the pack on a real project, run the disposable source-pack dry run. It creates a temporary target, imports a sample product document, advances through product structuring and design derivation, builds the design authoring queues, and confirms the implementation gate remains blocked while scaffold placeholders are unresolved:

```bash
make dry-run
make dry-run-golden
python3 scripts/dry_run_workflow.py --json
python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json
```

Use the explicit product fixture command when you want a multi-acceptance dry run that proves API/backend/frontend/test/planning/ADR queues scale with more than one product acceptance criterion.

To hand this workflow pack to another workspace or agent environment, export a manifest-checked source pack:

```bash
make package
python3 scripts/export_workflow_pack.py --check --json
python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json
python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json
```

The export writes `pack-manifest.json` with SHA-256 evidence for every included source-pack file, runs `verify_pack` against the exported directory, and creates a tar.gz artifact that can be unpacked as a trusted source workflow-pack checkout.
The manifest verifier validates `pack-manifest.json` by recomputing SHA-256 hashes, `size_bytes`, executable flags, duplicate or invalid paths, and unmanifested files.

To prove the transfer artifact is self-contained, smoke-test the tar.gz by unpacking it and running checks from the unpacked workflow pack:

```bash
make artifact-smoke
python3 scripts/smoke_workflow_pack_artifact.py --json
```

Before tagging or handing off a workflow-pack release, run the release readiness gate from `references/release-readiness-checklist.md`:

```bash
make release-check
python3 scripts/release_readiness.py --json
```

```bash
bin/governance env --repair --check --target /path/to/new-project --json
bin/governance init --check --target /path/to/new-project --json
bin/governance init --target /path/to/new-project --profile web-app --project-name "Project Name"
bin/governance verify /path/to/new-project
bin/governance gate product-structuring /path/to/new-project --json
bin/governance status /path/to/new-project
```

If the target folder contains exactly one supported root product document (`.md`, `.markdown`, `.docx`, `.pdf`, `.html`, `.htm`, or `.txt`), `init` auto-discovers it and reports `product.selection: "auto-discovered"` in JSON. When the product document is outside the target or multiple candidates exist, pass `--product /path/to/product.md`; ambiguous discovery is a preflight conflict instead of a guess.

For agent automation, append `--json` to `init`, `verify`, `status`, `env`, `product mark-ready`, or `advance`:

```bash
bin/governance verify /path/to/new-project --check --json
bin/governance verify /path/to/new-project --json
bin/governance env --repair --check --target /path/to/new-project --json
bin/governance env --repair --target /path/to/new-project --json
```

`verify --check --json` includes human-compatible `errors` and `warnings` plus structured `findings` with `code`, `severity`, `path`, and `message` without updating state. Use `verify --json` when you want to record `last_verification` in `.governance/state.json`. When governance state is readable, both JSON forms include `local_commands` and `next_actions` for continuing from the verified state.

Use `gate --json` before phase transitions. Supported gates are `product-structuring`, `design-derivation`, and `implementation`; readable-state gate payloads include `local_commands`, and passing gates also include `next_actions`.
Use `advance --check --json` to preview phase state changes, then `advance --json` when actually moving phases; it runs the matching gate and records `phase_history` in `.governance/state.json`.
Successful state-writing `product mark-ready --json` and `advance --json` payloads include `local_commands` and `next_actions` so agents can continue from the returned command contract.
Each `next_actions` entry includes `sequence`, `success_condition`, and either `preflight_for` for read-only preflight actions or `requires_action` for state-writing apply actions; sort by `sequence`, run preflight first, and run apply only after the referenced action returns `ok: true`.
`advance` records adjacent transitions one phase at a time and cannot skip phases; use `gate --json` for repeated checks or earlier-phase audits instead of moving the recorded phase backward.
The `implementation` gate requires the standard design handoff files, a traceable task board with at least one `Ready` task, and `docs/development/03-verification-log.md` as the stable evidence target for completed work.

When a non-Markdown product source has been converted and `docs/product/core/PRD.md` has been manually reviewed against the archived original, close out the import state deterministically:

```bash
bin/governance product mark-ready /path/to/new-project --reviewed --method manual-reviewed-markdown --check --json
bin/governance product mark-ready /path/to/new-project --reviewed --method manual-reviewed-markdown --json
bin/governance gate product-structuring /path/to/new-project --json
```

After the product-structuring gate passes, scaffold only the product chapters supported by the PRD. Scaffolded product chapters contain `governance:scaffold-placeholder` and block verification until replaced with source-backed content.
Successful scaffold write payloads include `scaffold_phase`, showing the recorded workflow phase and the phase this scaffold belongs to. When `scaffold_phase.matches` is false, keep following returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. Payloads also include `next_actions_blocked_by` while placeholders remain; keep returned `next_actions` for later, but do not run them until every listed blocker is resolved.

```bash
bin/governance scaffold product /path/to/new-project --chapter goals-and-requirements --chapter acceptance-criteria --check --json
bin/governance scaffold product /path/to/new-project --chapter goals-and-requirements --chapter acceptance-criteria --json
```

Use `scaffold design --check --json` after the design-derivation gate to inspect `would_create`, `would_skip`, and `would_index` for the standard architecture, API, UI, backend, frontend, test, and development document shells before writing them. The scaffold includes the starter endpoint contract at `docs/api/endpoints/01-endpoint-contract.md` and table skeletons for the acceptance matrix, roadmap, task board, and verification log. Scaffolded files contain `governance:scaffold-placeholder`; verification fails until the placeholders are replaced with product-derived content.
Successful scaffold write payloads include `scaffold_phase`, showing the recorded workflow phase and the phase this scaffold belongs to. When `scaffold_phase.matches` is false, keep following returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. Payloads also include `next_actions_blocked_by` while placeholders remain; keep returned `next_actions` for later, but do not run them until every listed blocker is resolved.
After the recorded phase is `design-derivation`, run `design plan --json` to route scaffold blockers into ordered design tracks. The plan returns `source_documents`, `tracks` with `sequence`, required local workflow `skills`, authority-routing `specialist_skills`, `primary_skill`, `primary_specialist_skill`, `references`, `documents`, per-track `blockers`, and ordered `steps`, plus `local_commands` and `next_actions`; use it to load `designing-system-architecture`, `designing-api-contracts`, `designing-backend-modules`, `designing-data-models`, and the remaining design skills in a deterministic order before replacing placeholders.
For the API track, run `design api-candidates --json` to extract source-backed endpoint candidates from product acceptance criteria. It returns `candidates` with `acceptance_id`, source `reference`, `suggested_endpoint_file`, `replaceable_starter_endpoint`, `open_decisions`, and `specialist_skills` including `api-design-reviewer`, `senior-backend`, and `senior-security`; agents must use `designing-api-contracts` and the API/security checklists to resolve those decisions instead of guessing method/path, fields, errors, auth, or frontend consumers.
Then run `design api-authoring --json` to turn candidates into API contract authoring work. The payload uses `decision_policy: do_not_guess_contract_details` and returns `authoring_tasks[]` with `sequence`, `execution` metadata (`primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`), target `documents`, required `sections`, `required_links`, unresolved `open_decisions`, `specialist_skills` including `api-design-reviewer`, `senior-backend`, and `senior-security`, and command steps named verify-api-authoring and refresh-api-authoring.
For backend work, run `design backend-authoring --json` after architecture/API sources exist. The payload uses `decision_policy: do_not_guess_backend_boundaries` and returns `authoring_tasks[]` with `sequence`, `execution` metadata (`primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`), backend/data-model `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `module_boundaries` and `transaction_boundaries`, `specialist_skills` including `senior-backend`, `database-designer`, `database-schema-designer`, `migration-architect`, `observability-designer`, and `senior-security`, and command steps named verify-backend-authoring and refresh-backend-authoring.
For UI and frontend work, run `design frontend-authoring --json` after product/API sources exist. The payload uses `decision_policy: do_not_guess_frontend_behavior` and returns `authoring_tasks[]` with `sequence`, `execution` metadata (`primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`), UI/frontend `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `state_ownership` and `error_actions`, `specialist_skills` including `senior-frontend`, `a11y-audit`, and `performance-profiler`, and command steps named verify-frontend-authoring and refresh-frontend-authoring.
For verification work, run `design test-strategy-authoring --json` after product/design/API sources exist. The payload uses `decision_policy: do_not_guess_verification_scope` and returns `authoring_tasks[]` with `sequence`, `execution` metadata (`primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`), test `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `acceptance_coverage` and `evidence_targets`, `specialist_skills` including `senior-qa`, `playwright-pro`, `a11y-audit`, and `security-pen-testing`, and command steps named verify-test-strategy-authoring and refresh-test-strategy-authoring.
For implementation planning work, run `design implementation-planning-authoring --json` after product/design/API/test sources exist. The payload uses `decision_policy: do_not_guess_task_scope` and returns `authoring_tasks[]` with `sequence`, `execution` metadata (`primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`), development `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `task_scope`, `ready_criteria`, `verification_plan`, and `agent_handoff`, `specialist_skills` including `senior-fullstack`, `ci-cd-pipeline-builder`, and `tech-debt-tracker`, plus command steps named verify-implementation-planning-authoring and refresh-implementation-planning-authoring.
For architecture decision work, run `design architecture-decisions-authoring --json` after design sources exist. The payload uses `decision_policy: do_not_guess_architecture_decisions` and returns `authoring_tasks[]` with `sequence`, `execution` metadata (`primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, `stop_condition`), ADR `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `adr_trigger`, `decision_scope`, and `alternatives`, `requires_adr: undetermined`, `specialist_skills` including `senior-architect`, `migration-architect`, and `tech-stack-evaluator`, and command steps named verify-architecture-decisions-authoring and refresh-architecture-decisions-authoring.

```bash
bin/governance advance design-derivation /path/to/new-project --check --json
bin/governance advance design-derivation /path/to/new-project --json
bin/governance scaffold design /path/to/new-project --check --json
bin/governance scaffold design /path/to/new-project --json
bin/governance design plan /path/to/new-project --json
bin/governance design api-candidates /path/to/new-project --json
bin/governance design api-authoring /path/to/new-project --json
bin/governance design backend-authoring /path/to/new-project --json
bin/governance design frontend-authoring /path/to/new-project --json
bin/governance design test-strategy-authoring /path/to/new-project --json
bin/governance design implementation-planning-authoring /path/to/new-project --json
bin/governance design architecture-decisions-authoring /path/to/new-project --json
```

## Workflow Order

1. `workflows/01-empty-repo-initialization.md`
2. `workflows/02-product-document-archiving.md`
3. `workflows/03-product-structuring.md`
4. `workflows/04-design-derivation.md`
5. `workflows/05-verification-and-drift-control.md`
6. `workflows/06-implementation-execution.md`

Read `workflows/00-overview.md` before running a phase.

## Verification

```bash
make test
make dry-run
make dry-run-golden
python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json
make package
python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json
make artifact-smoke
make release-check
python3 scripts/verify_pack.py --json
make verify-pack
```

`bin/governance env --repair --check --json` previews environment repairs without writing `.governance/env-repair.md` or installing packages. It reports `would_repair`, system/package-manager/Git status, supported `install_commands`, structured `repair_commands` with `argv`, `cwd`, `writes_state`, and `approval_required`, unsupported in-scope `manual_repairs`, `needs_escalation`, and `repair_execution` with `status`, `can_auto_apply`, and `next_step` for agent branching. Run `bin/governance env --repair --json` only when the repair plan should be written or approved root package installation should proceed. Missing required tools make `ok: false`; missing recommended tools make `ok: false` only with `--strict`. The repair command never calls `sudo`; supported apt installs run only when the process already has root privileges. Project-specific dependency installation should be handled after the target stack is known.

`python3 scripts/dry_run_workflow.py --json` checks the user-facing source-pack workflow on a disposable generated target. `python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json` runs the same flow against a realistic multi-acceptance product fixture. `python3 scripts/export_workflow_pack.py --check --json` previews a source-pack export without writing files; the write form exports `dist/docs-as-code-workflow-pack`, writes `pack-manifest.json`, verifies the exported pack, and optionally creates `dist/docs-as-code-workflow-pack.tar.gz`. `python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json` validates `pack-manifest.json` for SHA-256, size, executable-bit, duplicate-path, invalid-path, missing-file, and unmanifested-file drift. `python3 scripts/smoke_workflow_pack_artifact.py --json` unpacks the tar.gz artifact and runs manifest verification, `verify_pack`, plus dry-run checks from the unpacked workflow pack. `python3 scripts/release_readiness.py --json` runs the release readiness gate from `references/release-readiness-checklist.md`: whitespace checks, unit tests, pack verification, environment inventory, default and multi-acceptance fresh-target dry runs, source-pack export verification, and release artifact smoke validation. `python3 scripts/verify_pack.py --json` checks this source workflow pack for required files, AGENTS purpose/editing/required-reading/verification/baseline guardrails, documented verification commands, Makefile verification targets and recipes, dry-run workflow entry points, source-pack export entry points, pack manifest verification entry points, artifact smoke entry points, release readiness entry points, README Quick Start and agent automation commands, UTF-8 workflow-pack sources, runtime Python syntax, governance CLI command and subcommand surface, local command source/schema, workflow action schema, command/argv consistency, and phase-skill alignment, runtime wrapper executability, shell guards, root self-location, and command targets, README package layout, canonical phase identity, overview phase titles, ordered non-empty phase workflow sections, phase-map primary skills, product archive closeout docs, product scaffold docs, design scaffold docs, design plan docs, scaffold continuation docs, implementation handoff docs, runtime refresh docs, router coverage, critical initialization, product, and design reference routing, method reference baselines, skill identity, frontmatter and routing, described skill/reference/template index coverage, template guardrails, local Markdown links, reference and template entry points, and workflow-pack snapshot coverage. `make verify-pack` runs the full test suite, pack verifier, and environment inventory.

`bin/governance init` runs a preflight check before writing files. It auto-discovers exactly one supported product document in the target root when `--product` is omitted, and reports ambiguous candidates as conflicts. Existing generated governance files cause initialization to fail unless `--force` is supplied. Use `init --check --json` to inspect conflicts without writing to the target.

## Runtime Strategy

Core governance commands use POSIX shell wrappers and Python standard-library scripts so empty target folders can be initialized without package installation. Generated targets receive their own `bin/` and `scripts/` runtime plus `docs/agent-workflow/runtime-manifest.json`; after initialization, run checks from the target repository with `bin/governance verify .` or the target Makefile entries:

```bash
make verify-governance
make verify-check
make governance-status
make check-env
make repair-env-check
```

Generated targets also receive `docs/agent-workflow/workflow-pack/`, a manifest-verified snapshot of this pack's workflows, skills, references, and templates. `verify` fails if a required runtime or workflow-pack snapshot file is missing, omitted from its manifest, or modified. From this source pack, run `bin/governance runtime refresh <target> --check --json` to inspect `would_refresh` and `would_remove` without writing, then `bin/governance runtime refresh <target> --json` to refresh only generated `bin/`, `scripts/`, `docs/agent-workflow/runtime-manifest.json`, and workflow-pack snapshot files without rewriting product, design, planning, or implementation documents.

Node.js belongs in project-specific documentation and frontend tooling. Rust is reserved for optional stable accelerators after verification rules mature. See `references/runtime-strategy.md`.

## State File

Generated target repositories contain:

```text
.governance/state.json
```

The state file records the current workflow phase, project profile, product source, generated archive path, product import readiness, and last verification result. `bin/governance status <target>` prints the same key product-import fields for quick human review.
