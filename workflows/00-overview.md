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

Use `references/community-practices.md` to calibrate this workflow against recognized docs-as-code, architecture, API, ADR, quality, and security practices without treating any single framework as a rigid template.

## Runtime Model

Core governance commands are implemented as POSIX shell wrappers plus Python standard-library scripts. Normal operation must run without package installation or network access; `env --repair` may install supported system packages only under the repair policy in `references/runtime-strategy.md`.

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
make check-env
make repair-env-check
```

Machine-readable `init --json` and `status --json` success payloads include `next_actions`. Successful state-writing `product mark-ready --json` and `advance --json` commands also return the next `next_actions` set. Each action includes `cwd`; agents must run its `command` from that directory. Agents should execute `preflight` actions first and run state-writing `apply` actions only after the referenced preflight returns `ok: true`.

From a trusted source workflow-pack checkout, refresh generated target runtime and workflow-pack snapshot files without rewriting product or design documents:

```bash
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

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

After the product-structuring gate passes, use the deterministic product scaffold to create only source-supported product chapters:

```bash
bin/governance scaffold product <target> --chapter goals-and-requirements --chapter acceptance-criteria --check --json
bin/governance scaffold product <target> --chapter goals-and-requirements --chapter acceptance-criteria --json
```

After the design-derivation gate passes, use the deterministic design scaffold when standard design files are missing:

```bash
bin/governance scaffold design <target> --check --json
bin/governance scaffold design <target> --json
```

Use `--check` to inspect `would_create`, `would_skip`, and `would_index` before writing scaffold placeholders. Scaffold placeholders block verification until replaced with product-derived content.

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
```

## Minimal Success Criteria

- The original product document is preserved.
- Derived documents never silently invent product meaning.
- All open questions are registered in `docs/unresolved.md`.
- Every non-empty docs domain has `README.md` and `AGENTS.md`.
- Implementation tasks link back to existing local Markdown product, design, API, and acceptance sources.
- Governance verification passes before implementation starts.
