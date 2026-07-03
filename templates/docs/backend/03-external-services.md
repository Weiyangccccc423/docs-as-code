# External Services

## Product Links

- Product scope source
- Acceptance criteria source
- Backend modules source: `docs/backend/01-modules.md`
- API endpoint source

## Dependencies

| Service | Owner | Purpose | Criticality | Data Shared |
| --- | --- | --- | --- | --- |
| ExampleService | External or internal owner | Product-derived dependency purpose | Critical or optional | Data classification and fields |

- Document dependency trust boundary, update path, version-drift risk, and ADR link for high-risk dependencies.

## Contracts

- Link service API, event, file, queue, or manual contract source.
- Document request fields, response fields, error behavior, and compatibility expectations.

## Retries

- Document retryable failures, backoff policy, idempotency behavior, compensation, and duplicate-submission handling.

## Timeouts

- Document timeout budget, fallback behavior, user-visible impact, and upstream/downstream cancellation policy.

## Authentication

- Document credential owner, auth mechanism, secret storage, rotation, least-privilege access, and access boundary.

## Observability

- Document logs, metrics, traces, audit events, alerting, and sensitive-field handling.
