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

## Endpoint Skeleton

Each endpoint must define:

- method and path
- auth
- idempotency
- request fields
- response fields
- error codes
- upstream product/design links
- frontend consumer links

## Procedure

1. Run the design gate:

   ```bash
   bin/governance gate design-derivation <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

2. Run `bin/governance scaffold design <target> --json` when standard API files are missing.
3. Replace scaffold placeholders in API files with product-derived content.
4. Derive endpoints from structured product chapters and architecture docs.
5. Keep field names, auth rules, idempotency, and error behavior traceable.
6. Update `docs/api/README.md` and endpoint indexes for every new Markdown file.

## Stop Conditions

- A field cannot be traced to product, UI, backend design, or an explicit decision.
- Error behavior is unclear.
- Auth boundary is unclear.
- The endpoint requires a DB schema that has not been designed.
