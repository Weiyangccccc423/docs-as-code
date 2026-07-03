---
name: designing-test-strategy
description: Use when deriving test strategy, acceptance traceability matrices, risk coverage, verification layers, non-functional checks, or implementation-readiness evidence from product, API, architecture, backend, and frontend design docs.
---

# Designing Test Strategy

Test design turns acceptance criteria and design risks into implementation-ready verification scope.

Read `references/security-design-checklist.md` before assigning security, abuse-case, sensitive-data, dependency, or manual-review verification layers.

## Required Context

- `docs/product/NN-*acceptance*.md`
- `docs/api/`
- `docs/architecture/`
- `docs/backend/`
- `docs/frontend/`
- `docs/ui/`
- `docs/unresolved.md`

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --check --json` when test files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Replace scaffold placeholders in `docs/tests/01-strategy.md` and `docs/tests/02-acceptance-matrix.md` with source-backed content.
4. Build `docs/tests/01-strategy.md` from acceptance criteria, endpoint contracts, architecture quality attributes, backend failure modes, frontend states, and UI accessibility expectations.
5. Assign test layers for each risk: unit, integration, contract, end-to-end, accessibility, performance, security, observability, or manual review.
6. Map auth, authorization, abuse limits, sensitive logging, and dependency-failure checks from `references/security-design-checklist.md` into test strategy or explicit manual review.
7. Build `docs/tests/02-acceptance-matrix.md` with `Acceptance`, `Design`, `API`, and `Test` columns.
8. Map every product-defined `A-NNN` acceptance ID to design, API endpoint contract, and test evidence, or list it under Uncovered Criteria with a product-backed reason.
9. Use only product-defined `A-NNN` IDs; do not invent acceptance criteria in the matrix.
10. Link every row to existing local Markdown sources.
11. Register blocking verification gaps in `docs/unresolved.md` before implementation handoff.

## Stop Conditions

- A product acceptance criterion has no testable interpretation.
- A matrix row needs an API endpoint that is not documented.
- A design risk has no feasible verification layer.
- A non-functional expectation is implied but not measurable.
- A security-sensitive behavior has no test or manual-review path.
- Uncovered acceptance criteria lack an explicit product-backed reason.
