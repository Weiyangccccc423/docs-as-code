---
name: designing-api-contracts
description: Use when creating or changing HTTP API contracts, endpoint documentation, error codes, auth rules, idempotency, or OpenAPI alignment.
---

# Designing API Contracts

API contracts are shared truth between frontend, backend, tests, and agents.

Read `references/architecture-methods.md` before writing API contracts. Use its OpenAPI note to keep Markdown endpoint files aligned with a future machine-readable contract.
Read `references/api-design-checklist.md` before writing API contracts. Use it as the completion checklist for contract shape, HTTP semantics, error responses, idempotency, collection operations, compatibility, and traceability.
Read `references/security-design-checklist.md` before writing auth, authorization, abuse-limit, sensitive-data, or dependency-trust contract decisions.

## Required Files

- `docs/api/00-conventions.md`
- `docs/api/endpoints/README.md`
- `docs/api/endpoints/NN-*.md`
- `docs/api/error-codes.md`
- `docs/api/changelog.md`

Endpoint files under `docs/api/endpoints/` must use `NN-<slug>.md` with unique `NN` prefixes.

## API Convention Sections

`docs/api/00-conventions.md` must include these headings:

- `## Product Links`
- `## HTTP Conventions`
- `## Authentication`
- `## Idempotency`
- `## Compatibility`
- `## Open Decisions`

Do not leave required sections empty or as `TBD`/`TODO`; link `Product Links` to product scope and a product acceptance chapter.

## Error Code Registry Sections

`docs/api/error-codes.md` must include these headings:

- `## Product Links`
- `## Error Taxonomy`
- `## Error Codes`
- `## Retry Semantics`
- `## Frontend Handling`

Do not leave required sections empty or as `TBD`/`TODO`; link `Product Links` to product scope and a product acceptance chapter.

## API Changelog Sections

`docs/api/changelog.md` must include these headings:

- `## Change Log`
- `## Compatibility Notes`

Do not leave required sections empty or as `TBD`/`TODO`; record the initial contract baseline and downstream compatibility impact.

## Endpoint Sections

Each endpoint file must include these headings:

- `## Method and Path`
- `## Auth`
- `## Idempotency`
- `## Request Fields`
- `## Response Fields`
- `## Error Codes`
- `## Upstream Links`
- `## Frontend Consumers`

Do not leave required sections empty or as `TBD`/`TODO`; register unknown contract decisions in `docs/unresolved.md`.
Write `Method and Path` as an HTTP method plus absolute path, for example `POST /users`.
Link `Error Codes` to `docs/api/error-codes.md` so endpoint errors stay in the central registry.
Link `Upstream Links` to existing local product, architecture, UI, backend/frontend, decision, or unresolved Markdown sources.
Link `Frontend Consumers` to existing local UI or frontend API-consumption Markdown docs.

## Procedure

1. Run the design gate:

   ```bash
   bin/governance advance design-derivation <target> --check --json
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --check --json` when standard API files are missing, then run it without `--check` when the plan is correct; use returned `local_commands` for checks and inspect `scaffold_phase`. If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.
3. Run `bin/governance design api-candidates <target> --json` to extract source-backed endpoint candidates from product acceptance criteria. Use returned `candidates[].acceptance_id`, source `reference`, `suggested_endpoint_file`, `replaceable_starter_endpoint`, `open_decisions`, and `specialist_skills` including `api-design-reviewer`, `senior-backend`, and `senior-security` as the API authoring queue; do not guess method/path, fields, errors, auth, or frontend consumers from a candidate alone.
4. Run `bin/governance design api-authoring <target> --json`, inspect `authoring_summary` (`task_count`, `open_decision_count`, `required_link_status_counts`, `non_satisfied_required_link_count`, and `link_repair_action_count`), and follow `authoring_tasks[]` by `sequence`. The payload's `decision_policy` is `do_not_guess_contract_details`; the payload and each task list `skill_requirements`, `authority_skill_requirements`, `skill_loading_plan`, `execution` metadata with `primary_skill`, `primary_specialist_skill`, `verify_step`, `refresh_step`, and `stop_condition`, target `documents`, required `sections`, `required_links` with `required_links[].status`, `link_repair_actions` for non-satisfied links, including `repair_strategy`, `verify_command`, and `refresh_command`, unresolved `open_decisions`, `specialist_skills` including `api-design-reviewer`, `senior-backend`, and `senior-security`, and read-only command steps verify-api-authoring and refresh-api-authoring. Follow `skill_loading_plan.steps[]` by `sequence`; load authority-routing skills from the agent environment or follow `missing_policy: load_from_agent_environment_or_stop_before_guessing`.
5. Read `references/api-design-checklist.md`.
6. Replace scaffold placeholders in API files with product-derived content.
7. Derive endpoints from structured product chapters and architecture docs.
8. Name endpoint files with the next unique `NN-<slug>.md` prefix.
9. Keep field names, auth rules, idempotency, upstream links, frontend consumers, and error behavior traceable.
10. Check contract shape, HTTP semantics, error responses, idempotency, collection behavior, compatibility, and traceability against `references/api-design-checklist.md`.
11. Check object-level authorization, function-level authorization, mass-assignment, rate-limit, sensitive-field, and logging expectations against `references/security-design-checklist.md`.
12. Update `docs/api/README.md` and endpoint indexes for every new Markdown file.

## Stop Conditions

- A field cannot be traced to product, UI, backend design, or an explicit decision.
- Error behavior is unclear.
- Auth boundary is unclear.
- Authorization or abuse-limit behavior is unclear.
- Compatibility, versioning, pagination, retry, or duplicate-submission behavior is unclear for a contract that needs it.
- The endpoint requires a DB schema that has not been designed.
