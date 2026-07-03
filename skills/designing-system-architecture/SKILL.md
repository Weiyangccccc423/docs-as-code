---
name: designing-system-architecture
description: Use when deriving system architecture, boundaries, C4-style views, quality attributes, deployment assumptions, or cross-module decisions from structured product docs.
---

# Designing System Architecture

Use product truth to define system boundaries before implementation design.

Read `references/architecture-methods.md` before producing architecture documents.

## Required Views

- system context
- containers
- external dependencies
- runtime flow for critical user paths
- quality attributes
- deployment assumptions
- major risks
- ADR candidates

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Read product scope and acceptance criteria.
3. Run `bin/governance scaffold design <target> --check --json` when standard design files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and keep returned `next_actions` for later.
4. Replace scaffold placeholders in architecture files with product-derived content.
5. Identify actors, systems, and external services.
6. Define containers without committing to unnecessary internal classes.
7. Record cross-module decisions as ADRs.
8. Link every architecture claim to product, API, or decision sources.

## Stop Conditions

- A boundary decision changes product scope.
- A dependency is assumed without ownership or contract.
- A quality attribute is implied but not measurable.
