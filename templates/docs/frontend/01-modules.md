# Frontend Modules

## Product Links

- Product scope source
- Acceptance criteria source

## UI Links

- Interaction model source: `docs/ui/01-interaction-model.md`
- API consumption source: `docs/frontend/02-api-consumption.md`

## Modules

| Module | Responsibility | UI Surface | API Dependency | Owner |
| --- | --- | --- | --- | --- |
| ExampleModule | One primary frontend responsibility derived from UI and product flows. | Screen or flow source | API endpoint source | Owner role |

## State Ownership

- Document local, shared, server-derived, cached, optimistic, and persisted state ownership.
- Link each server-derived state to the API endpoint contract that owns it.

## Routes

| Route | Screen or Flow | Access Rule | Product Source |
| --- | --- | --- | --- |
| /example | Example screen or flow | Auth, role, or public access rule | Product or UI source |

## Open Decisions

- Link unresolved frontend module, state, route, API, or accessibility questions.
