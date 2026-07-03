# API Design Checklist

Use this checklist before API endpoint contracts are used for backend, frontend, or test implementation tasks.

Calibrate against OpenAPI, HTTP Semantics, and Problem Details without treating any single format as the whole design process. OpenAPI is the future machine-readable contract target; Markdown endpoint files remain the human review layer.

## Contract Shape

- Does each endpoint have a stable method, absolute path, auth rule, idempotency rule, request schema, response schema, error list, upstream source links, and frontend consumer links?
- Are field names, types, required/optional status, defaults, validation rules, examples, and product sources explicit?
- Can the contract be translated to OpenAPI without adding unstated behavior?

Reference: `https://spec.openapis.org/oas/latest.html`

## HTTP Semantics

- Are safe, idempotent, and cacheable methods used consistently with RFC 9110 expectations?
- Are status codes chosen for product meaning, not framework convenience?
- Are headers, content types, redirects, conditional requests, and cache behavior documented when relevant?

Reference: `https://www.rfc-editor.org/rfc/rfc9110.html`

## Error Responses

- Are validation, authentication, authorization, not-found, conflict, rate-limit, dependency, and internal errors registered in `docs/api/error-codes.md`?
- Are retryability, user action, frontend state, telemetry, and audit expectations explicit for each user-visible error?
- Are machine-readable problem details considered for interoperable error payloads?

Reference: `https://www.rfc-editor.org/rfc/rfc9457.html`

## Idempotency and Concurrency

- Are retryable writes assigned an idempotency strategy, such as a project-defined `Idempotency-Key` policy?
- Are duplicate submission, out-of-order submission, stale update, and parallel update outcomes documented?
- Are conflict responses linked to backend transaction, uniqueness, and consistency decisions?

Reference: `https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/`

## Collection Operations

- Are pagination, filtering, sorting, default limits, maximum limits, and expensive-query constraints explicit?
- Are list response ordering, cursor stability, and empty-state behavior documented?
- Are bulk operations, partial success, and export/import formats documented when relevant?

## Compatibility and Change Control

- Are backward-compatible additions, deprecations, and breaking changes distinguishable?
- Are versioning, migration windows, client coordination, and changelog entries documented?
- Are generated clients, SDKs, or external consumers assigned owners and update paths?

## Traceability

- Does every endpoint link to product acceptance criteria, architecture/backend ownership, and frontend consumers?
- Are unresolved API contract decisions registered in `docs/unresolved.md` before implementation handoff?
- Are tests or manual-review paths identified for contract, compatibility, abuse-limit, and security-sensitive behavior?
