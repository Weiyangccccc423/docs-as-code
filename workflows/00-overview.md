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

## Runtime Model

Core governance commands are implemented as POSIX shell wrappers plus Python standard-library scripts. Normal operation must run without package installation or network access; `env --repair` may install supported system packages only under the repair policy in `references/runtime-strategy.md`.

Generated target repositories receive their own copy of `bin/` and `scripts/`. After initialization, prefer the target-local CLI:

```bash
bin/governance verify .
bin/governance env --repair --target .
```

Node.js tooling is an optional project-specific enhancement layer. Rust is reserved for future stable accelerators or single-binary distribution. See `references/runtime-strategy.md`.

## Phase Map

| Phase | Purpose | Primary skill |
| --- | --- | --- |
| 01 | Empty repository initialization | `initializing-governance-repo` |
| 02 | Product document archiving | `archiving-product-document` |
| 03 | Product structuring | `structuring-product-requirements` |
| 04 | Design derivation | `designing-system-architecture`, `designing-api-contracts` |
| 05 | Verification and drift control | `verifying-governance-docs` |

Before moving between phases, run the matching gate:

```bash
bin/governance gate product-structuring <target> --json
bin/governance gate design-derivation <target> --json
bin/governance gate implementation <target> --json
```

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
- Implementation tasks link back to product, design, API, and acceptance sources.
- Governance verification passes before implementation starts.
