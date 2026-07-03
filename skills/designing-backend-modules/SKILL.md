---
name: designing-backend-modules
description: Use when deriving backend module boundaries, service responsibilities, runtime flows, external dependencies, or implementation design documents from product, API, or architecture specs.
---

# Designing Backend Modules

Use architecture first, then module design.

## Required Context

- `docs/product/core/PRD.md`
- structured product chapters and acceptance criteria
- `docs/architecture/`
- `docs/api/`
- `docs/unresolved.md`

Read `references/backend-design-checklist.md` before writing backend design docs. Use it as the completion checklist for module boundaries, data ownership, API ownership, runtime flows, transaction boundaries, consistency, observability, security, acceptance, and tests.
Read `references/backend-operability-checklist.md` before writing service-level, observability, configuration, runtime-control, logging, runbook, or support expectations.
Read `references/security-design-checklist.md` before writing auth, authorization, sensitive-data, dependency-trust, or abuse-case backend decisions.

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --check --json` when standard backend files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Read `references/backend-design-checklist.md`.
4. Read `references/backend-operability-checklist.md`.
5. Replace scaffold placeholders in backend files with product-derived content.
6. Identify module responsibility and boundaries.
7. Name upstream and downstream modules.
8. Link owned API endpoints from `docs/api/`.
9. Link `docs/backend/01-modules.md` to `docs/backend/02-data-model.md`.
10. Link `docs/backend/01-modules.md` to `docs/backend/03-external-services.md`, even when the document states there are no external services.
11. Define data ownership and lifecycle states.
12. Document transaction boundaries, consistency expectations, concurrency conflicts, and duplicate-submission behavior for state-changing operations.
13. Document external dependencies, retries, timeouts, and failure modes.
14. Define service levels, observability signals, configuration/secrets handling, runtime controls, operational logs, and runbook/support expectations against `references/backend-operability-checklist.md`.
15. Define observability and auth behavior.
16. Check sensitive data, secret handling, least-privilege dependency access, audit trails, and abuse limits against `references/security-design-checklist.md`.
17. Link acceptance criteria and test strategy.
18. Re-check the backend and operability checklists before considering implementation tasks ready.

## Stop Conditions

- A module needs an API field not defined in `docs/api/`.
- A module needs a table or field not defined in the data model.
- A state-changing operation lacks transaction, consistency, or duplicate-submission behavior.
- Sensitive data, authorization, or dependency trust is unclear.
- A production-impacting module lacks service-level, telemetry, runtime-control, or support expectations.
- A module changes product meaning.
- An external dependency lacks an owner or contract.
