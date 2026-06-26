# Backend Design Checklist

Use this checklist before creating implementation tasks.

## Module Boundary

- Does the module have one primary responsibility?
- Are upstream and downstream modules named?
- Are internal-only behaviors separated from API behaviors?
- Is each external dependency named and owned?

## Data Model

- Are tables, fields, indexes, and ownership documented?
- Are lifecycle states and state transitions explicit?
- Are idempotency keys and uniqueness constraints defined?
- Are soft-delete and retention rules defined when relevant?

## API Contract

- Is each endpoint documented under `docs/api/`?
- Are request fields, response fields, auth, idempotency, and error codes explicit?
- Can frontend and tests consume the contract without reading backend code?

## Runtime Flow

- Are success and failure paths documented?
- Are retries, timeouts, and compensation behavior explicit?
- Are long-running jobs and async state changes traceable?

## Observability and Security

- Are auth boundaries documented?
- Are audit logs, trace IDs, and sensitive fields handled?
- Are cross-user or admin behaviors explicit?

## Acceptance and Tests

- Does the module link to product acceptance criteria?
- Are unit, integration, and contract tests identifiable?
- Are unresolved questions registered before implementation?
