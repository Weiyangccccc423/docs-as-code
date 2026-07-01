# API Error Codes

## Product Links

- Product scope source
- Acceptance criteria source

## Error Taxonomy

- Validation, authentication, authorization, not-found, conflict, rate-limit, dependency, and internal errors.

## Error Codes

| Code | HTTP Status | Product Meaning | Retryable | User Action |
| --- | --- | --- | --- | --- |
| ERR_EXAMPLE | 400 | Replace with a product-derived error condition. | No | Explain the user-visible recovery path. |

## Retry Semantics

- Mark every retryable error explicitly and define backoff, idempotency, and duplicate-submission expectations.

## Frontend Handling

- Map each user-visible error to copy, UI state, recovery action, and telemetry expectations.
