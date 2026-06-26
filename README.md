# docs-as-code Workflow Pack

This repository contains a reusable workflow pack for turning an empty folder plus one product document into a governed, docs-as-code project workspace.

## Goal

Create reliable project governance before implementation starts:

- archive the original product document
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
├── templates/    # generated repository document templates
├── tests/        # workflow-pack tests
└── workflows/    # phase-by-phase operating procedures
```

## Quick Start

```bash
bin/governance env --repair --target /path/to/new-project
bin/governance init --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name "Project Name"
bin/governance verify /path/to/new-project
bin/governance status /path/to/new-project
```

For agent automation, append `--json` to `init`, `verify`, `status`, or `env`:

```bash
bin/governance verify /path/to/new-project --json
bin/governance env --repair --target /path/to/new-project --json
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
make verify-pack
```

The current scripts intentionally avoid unsupervised system package installation. `bin/governance env --repair` creates `.governance/env-repair.md` and applies safe local repairs such as creating governance state directories. Project-specific dependency installation should be handled after the target stack is known.

## Runtime Strategy

Core governance commands use POSIX shell wrappers and Python standard-library scripts so empty target folders can be initialized without package installation. Generated targets receive their own `bin/` and `scripts/` runtime; after initialization, run checks from the target repository with `bin/governance verify .` or `make verify-governance`.

Node.js belongs in project-specific documentation and frontend tooling. Rust is reserved for optional stable accelerators after verification rules mature. See `references/runtime-strategy.md`.

## State File

Generated target repositories contain:

```text
.governance/state.json
```

The state file records the current workflow phase, project profile, product source, generated archive path, and last verification result.
