# Data Model

## Product Links

- Product scope source
- Acceptance criteria source
- Backend modules source: `docs/backend/01-modules.md`
- API endpoint source

## Owners

| Entity | Owning Module | API Owner | Data Steward |
| --- | --- | --- | --- |
| ExampleEntity | Backend module source | API endpoint source | Owner role |

## Entities

| Entity | Field | Type | Required | Source | Notes |
| --- | --- | --- | --- | --- | --- |
| ExampleEntity | id | string | Yes | Product or API source | Stable identifier and ownership boundary. |

## State Machines

| Entity | State | Allowed Transition | Trigger | Source |
| --- | --- | --- | --- | --- |
| ExampleEntity | draft | draft -> active | Product workflow trigger | Acceptance criteria source |

## Constraints

- Document uniqueness, idempotency keys, cross-user isolation, transaction boundaries, consistency expectations, concurrency conflicts, retention, soft-delete, and audit constraints.

## Indexes

| Entity | Index | Query Path | Justification |
| --- | --- | --- | --- |
| ExampleEntity | example_lookup_idx | API endpoint or module query source | Product or performance requirement source |

## Migrations

- Document creation order, backfill strategy, compatibility window, rollback expectation, and data safety checks.
