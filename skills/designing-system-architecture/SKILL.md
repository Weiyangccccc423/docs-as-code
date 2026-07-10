---
name: designing-system-architecture
description: Use when deriving system architecture, boundaries, C4-style views, quality attributes, deployment assumptions, or cross-module decisions from structured product docs.
---

# Designing System Architecture

Use product truth to define system boundaries before implementation design.

Read `references/architecture-methods.md` before producing architecture documents.
Read `references/architecture-quality-checklist.md` before producing architecture quality attributes, runtime/failure flows, tradeoff notes, or implementation-readiness claims.

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
3. Run `bin/governance scaffold design <target> --check --json` when standard design files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
4. Run `bin/governance design architecture-authoring <target> --json`, inspect `authoring_summary` (`document_status_counts`, `non_authored_document_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count`), and follow `authoring_tasks[]` by `sequence`. Each task exposes `required_decisions`, current `open_decisions`, `review_status`, `document_blockers`, and link blockers. Follow `skill_loading_plan.steps[]`; load `senior-architect` and the remaining authority-routing skills from the agent environment or stop under `load_from_agent_environment_or_stop_before_guessing`.
5. Use `workflow work-package --json` stages in order: author architecture documents, integrate links after owning tracks exist, then read `references/design-review-checklist.md` and run `design review --track architecture --work <WORK-ID> --result approved --reason "<authority-review explanation>" --reviewed --check --json` before apply. The Git-tracked review binds PRD, acceptance, architecture evidence, and the loaded `senior-architect` skill SHA-256; changing evidence reopens every architecture decision.
6. Read `references/architecture-quality-checklist.md`.
7. Replace scaffold placeholders in architecture files with product-derived content.
8. Identify actors, systems, and external services.
9. Define containers without committing to unnecessary internal classes.
10. Write measurable quality scenarios for important availability, performance, security, observability, maintainability, deployment, or operability claims.
11. Document runtime success paths, failure paths, tradeoffs, risks, and verification hooks for high-risk quality scenarios.
12. Record cross-module decisions as ADRs.
13. Link every architecture claim to product, API, backend/frontend, test, decision, or unresolved sources.

## Stop Conditions

- A boundary decision changes product scope.
- A dependency is assumed without ownership or contract.
- A quality attribute is implied but not measurable.
- A tradeoff, deployment constraint, or runtime failure mode affects implementation but has no documented verification path.
