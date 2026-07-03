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
3. Read `references/api-design-checklist.md`.
4. Replace scaffold placeholders in API files with product-derived content.
5. Derive endpoints from structured product chapters and architecture docs.
6. Name endpoint files with the next unique `NN-<slug>.md` prefix.
7. Keep field names, auth rules, idempotency, upstream links, frontend consumers, and error behavior traceable.
8. Check contract shape, HTTP semantics, error responses, idempotency, collection behavior, compatibility, and traceability against `references/api-design-checklist.md`.
9. Check object-level authorization, function-level authorization, mass-assignment, rate-limit, sensitive-field, and logging expectations against `references/security-design-checklist.md`.
10. Update `docs/api/README.md` and endpoint indexes for every new Markdown file.

## Stop Conditions

- A field cannot be traced to product, UI, backend design, or an explicit decision.
- Error behavior is unclear.
- Auth boundary is unclear.
- Authorization or abuse-limit behavior is unclear.
- Compatibility, versioning, pagination, retry, or duplicate-submission behavior is unclear for a contract that needs it.
- The endpoint requires a DB schema that has not been designed.
