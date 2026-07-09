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
4. Run `bin/governance design architecture-authoring <target> --json`, inspect `authoring_summary` (`task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count`), and follow `authoring_tasks[]` by `sequence` before writing architecture content. The payload's `decision_policy` is `do_not_guess_architecture_boundaries`; the payload and each task list `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, and `stop_condition`, architecture `documents`, required `sections`, `required_links` with `required_links[].status`, `link_repair_actions` for non-satisfied links, including `repair_strategy`, `verify_command`, and `refresh_command`, unresolved `open_decisions` such as `system_boundary`, `container_responsibilities`, `quality_scenarios`, `deployment_assumptions`, and `adr_candidates`, `specialist_skills` including `senior-architect`, `senior-security`, `observability-designer`, and `slo-architect`, authority-routing `missing_policy`, and read-only command steps verify-architecture-authoring and refresh-architecture-authoring. Follow `skill_loading_plan.steps[]` by `sequence`; load authority-routing skills from the agent environment or follow `missing_policy: load_from_agent_environment_or_stop_before_guessing`.
5. Read `references/architecture-quality-checklist.md`.
6. Replace scaffold placeholders in architecture files with product-derived content.
7. Identify actors, systems, and external services.
8. Define containers without committing to unnecessary internal classes.
9. Write measurable quality scenarios for important availability, performance, security, observability, maintainability, deployment, or operability claims.
10. Document runtime success paths, failure paths, tradeoffs, risks, and verification hooks for high-risk quality scenarios.
11. Record cross-module decisions as ADRs.
12. Link every architecture claim to product, API, backend/frontend, test, decision, or unresolved sources.

## Stop Conditions

- A boundary decision changes product scope.
- A dependency is assumed without ownership or contract.
- A quality attribute is implied but not measurable.
- A tradeoff, deployment constraint, or runtime failure mode affects implementation but has no documented verification path.
