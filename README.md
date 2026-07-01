# docs-as-code Workflow Pack

This repository contains a reusable workflow pack for turning an empty folder plus one product document into a governed, docs-as-code project workspace.

## Goal

Create reliable project governance before implementation starts:

- archive the original product document
- record product archive manifest metadata and SHA-256 evidence
- copy a target-local workflow, skill, reference, and template snapshot
- derive structured product, architecture, API, UI, backend, frontend, test, and delivery documents
- keep unresolved decisions explicit
- verify documentation structure and drift
- hand implementation tasks to agents with traceable specs and acceptance criteria

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
- `templates/docs/agent-workflow/task-handoff.md`: agent task handoff and completion criteria shape.
- `templates/docs/api/00-conventions.md`: shared API conventions shape.
- `templates/docs/api/changelog.md`: API contract changelog shape.
- `templates/docs/api/error-codes.md`: API error code registry shape.
- `templates/docs/architecture/01-system-context.md`: system context architecture shape.
- `templates/docs/architecture/02-containers.md`: runtime container architecture shape.
- `templates/docs/architecture/03-quality-attributes.md`: measurable architecture quality attributes shape.
- `templates/docs/decisions/ADR-template.md`: ADR shape for architecture decisions.
- `templates/docs/development/01-roadmap.md`: implementation roadmap shape.
- `templates/docs/development/02-task-board.md`: implementation task board shape.
- `templates/docs/development/03-verification-log.md`: completion evidence log shape for Done tasks.
- `templates/docs/tests/01-strategy.md`: test strategy and quality baseline shape.
- `templates/docs/tests/02-acceptance-matrix.md`: acceptance traceability matrix shape.

## Reference Files

- `references/community-practices.md`: external practice calibration.
- `references/architecture-methods.md`: C4, arc42, ADR, and OpenAPI method notes.
- `references/backend-design-checklist.md`: backend and data-design completion checklist.
- `references/runtime-strategy.md`: core runtime, optional tooling, and repair policy.

## Skill Files

- `skills/using-governance-workflow/SKILL.md`: workflow router.
- `skills/initializing-governance-repo/SKILL.md`: empty repository bootstrap.
- `skills/archiving-product-document/SKILL.md`: product source preservation and import.
- `skills/structuring-product-requirements/SKILL.md`: product chapter and acceptance structuring.
- `skills/designing-system-architecture/SKILL.md`: system architecture derivation.
- `skills/designing-api-contracts/SKILL.md`: API contract derivation.
- `skills/designing-backend-modules/SKILL.md`: backend module design.
- `skills/designing-data-models/SKILL.md`: persistence and lifecycle design.
- `skills/capturing-architecture-decisions/SKILL.md`: ADR capture.
- `skills/verifying-governance-docs/SKILL.md`: governance verification and repair routing.

## Quick Start

```bash
bin/governance env --repair --check --target /path/to/new-project --json
bin/governance init --check --target /path/to/new-project --product /path/to/product.md --json
bin/governance init --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name"
bin/governance verify /path/to/new-project
bin/governance gate product-structuring /path/to/new-project --json
bin/governance status /path/to/new-project
```

For agent automation, append `--json` to `init`, `verify`, `status`, or `env`:

```bash
bin/governance verify /path/to/new-project --check --json
bin/governance verify /path/to/new-project --json
bin/governance env --repair --check --target /path/to/new-project --json
bin/governance env --repair --target /path/to/new-project --json
```

`verify --check --json` includes human-compatible `errors` and `warnings` plus structured `findings` with `code`, `severity`, `path`, and `message` without updating state. Use `verify --json` when you want to record `last_verification` in `.governance/state.json`.

Use `gate --json` before phase transitions. Supported gates are `product-structuring`, `design-derivation`, and `implementation`.
Use `advance --check --json` to preview phase state changes, then `advance --json` when actually moving phases; it runs the matching gate and records `phase_history` in `.governance/state.json`.
The `implementation` gate requires a traceable task board with at least one `Ready` task.

When a non-Markdown product source has been converted and `docs/product/core/PRD.md` has been manually reviewed against the archived original, close out the import state deterministically:

```bash
bin/governance product mark-ready /path/to/new-project --reviewed --method manual-reviewed-markdown --check --json
bin/governance product mark-ready /path/to/new-project --reviewed --method manual-reviewed-markdown --json
bin/governance gate product-structuring /path/to/new-project --json
```

After the product-structuring gate passes, scaffold only the product chapters supported by the PRD. Scaffolded product chapters contain `governance:scaffold-placeholder` and block verification until replaced with source-backed content.

```bash
bin/governance scaffold product /path/to/new-project --chapter goals-and-requirements --chapter acceptance-criteria --check --json
bin/governance scaffold product /path/to/new-project --chapter goals-and-requirements --chapter acceptance-criteria --json
```

Use `scaffold design --check --json` after the design-derivation gate to inspect the standard architecture, API, UI, backend, frontend, test, and development document shells before writing them. Scaffolded files contain `governance:scaffold-placeholder`; verification fails until the placeholders are replaced with product-derived content.

```bash
bin/governance advance design-derivation /path/to/new-project --check --json
bin/governance advance design-derivation /path/to/new-project --json
bin/governance scaffold design /path/to/new-project --check --json
bin/governance scaffold design /path/to/new-project --json
```

## Workflow Order

1. `workflows/01-empty-repo-initialization.md`
2. `workflows/02-product-document-archiving.md`
3. `workflows/03-product-structuring.md`
4. `workflows/04-design-derivation.md`
5. `workflows/05-verification-and-drift-control.md`

Read `workflows/00-overview.md` before running a phase.

## Verification

```bash
make test
python3 scripts/verify_pack.py --json
make verify-pack
```

`bin/governance env --repair --check --json` previews environment repairs without writing `.governance/env-repair.md` or installing packages. It reports `would_repair`, system/package-manager/Git status, and any supported `install_commands`. Run `bin/governance env --repair --json` only when the repair plan should be written or approved root package installation should proceed. Missing required tools make `ok: false`; missing recommended tools make `ok: false` only with `--strict`. The repair command never calls `sudo`; supported apt installs run only when the process already has root privileges. Project-specific dependency installation should be handled after the target stack is known.

`python3 scripts/verify_pack.py --json` checks this source workflow pack for required files, AGENTS purpose/editing/required-reading/verification/baseline guardrails, documented verification commands, Makefile verification targets and recipes, README Quick Start and agent automation commands, UTF-8 workflow-pack sources, runtime Python syntax, governance CLI command and subcommand surface, runtime wrapper executability, shell guards, root self-location, and command targets, README package layout, canonical phase identity, overview phase titles, ordered non-empty phase workflow sections, phase-map primary skills, router coverage, skill identity, frontmatter and routing, described skill/reference/template index coverage, template guardrails, local Markdown links, reference and template entry points, and workflow-pack snapshot coverage. `make verify-pack` runs the full test suite, pack verifier, and environment inventory.

`bin/governance init` runs a preflight check before writing files. Existing generated governance files cause initialization to fail unless `--force` is supplied. Use `init --check --json` to inspect conflicts without writing to the target.

## Runtime Strategy

Core governance commands use POSIX shell wrappers and Python standard-library scripts so empty target folders can be initialized without package installation. Generated targets receive their own `bin/` and `scripts/` runtime plus `docs/agent-workflow/runtime-manifest.json`; after initialization, run checks from the target repository with `bin/governance verify .` or `make verify-governance`.

Generated targets also receive `docs/agent-workflow/workflow-pack/`, a manifest-verified snapshot of this pack's workflows, skills, references, and templates. `verify` fails if a required runtime or workflow-pack snapshot file is missing, omitted from its manifest, or modified. From this source pack, run `bin/governance runtime refresh <target> --check --json` to inspect the repair plan, then `bin/governance runtime refresh <target> --json` to refresh only generated `bin/`, `scripts/`, and workflow-pack snapshot files.

Node.js belongs in project-specific documentation and frontend tooling. Rust is reserved for optional stable accelerators after verification rules mature. See `references/runtime-strategy.md`.

## State File

Generated target repositories contain:

```text
.governance/state.json
```

The state file records the current workflow phase, project profile, product source, generated archive path, product import readiness, and last verification result. `bin/governance status <target>` prints the same key product-import fields for quick human review.
