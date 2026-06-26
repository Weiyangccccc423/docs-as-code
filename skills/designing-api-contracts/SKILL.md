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

## Stop Conditions

- A field cannot be traced to product, UI, backend design, or an explicit decision.
- Error behavior is unclear.
- Auth boundary is unclear.
- The endpoint requires a DB schema that has not been designed.
