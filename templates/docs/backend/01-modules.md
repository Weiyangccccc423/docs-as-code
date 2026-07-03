# Backend Modules

## Product Links

- Product scope source
- Acceptance criteria source

## Architecture Links

- System context source
- Container source
- Quality attributes source
- Data model source: `docs/backend/02-data-model.md`
- External services source: `docs/backend/03-external-services.md`

## Modules

| Module | Responsibility | Upstream | Downstream | Owner |
| --- | --- | --- | --- | --- |
| ExampleModule | One primary backend responsibility derived from product and architecture sources. | API endpoint or caller source | Data model, external service, or downstream module source | Owner role |

## API Ownership

- Link owned API endpoints under `docs/api/endpoints/`.
- Separate internal-only behavior from API-visible behavior.

## Failure Modes

- Document success path, failure path, retry, timeout, compensation, transaction boundaries, consistency expectations, concurrency conflicts, duplicate-submission handling, observability, and security behavior.
- Document sensitive data, authorization, audit, abuse-limit, and least-privilege dependency behavior where the module is security-sensitive.

## Open Decisions

- Link unresolved module-boundary, API ownership, data ownership, or external dependency questions.
