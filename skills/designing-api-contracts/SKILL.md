---
name: designing-api-contracts
description: Use when creating or changing HTTP API contracts, endpoint documentation, error codes, auth rules, idempotency, or OpenAPI alignment.
---

# Designing API Contracts

API contracts are shared truth between frontend, backend, tests, and agents.

## Required Files

- `docs/api/00-conventions.md`
- `docs/api/endpoints/README.md`
- `docs/api/endpoints/NN-*.md`
- `docs/api/error-codes.md`
- `docs/api/changelog.md`

Endpoint files under `docs/api/endpoints/` must use `NN-<slug>.md` with unique `NN` prefixes.

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
   bin/governance advance design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --json` when standard API files are missing.
3. Replace scaffold placeholders in API files with product-derived content.
4. Derive endpoints from structured product chapters and architecture docs.
5. Name endpoint files with the next unique `NN-<slug>.md` prefix.
6. Keep field names, auth rules, idempotency, upstream links, frontend consumers, and error behavior traceable.
7. Update `docs/api/README.md` and endpoint indexes for every new Markdown file.

## Stop Conditions

- A field cannot be traced to product, UI, backend design, or an explicit decision.
- Error behavior is unclear.
- Auth boundary is unclear.
- The endpoint requires a DB schema that has not been designed.
