# API Consumption

## Product Links

- Product scope source
- Acceptance criteria source
- Frontend modules source: `docs/frontend/01-modules.md`

## API Links

- API conventions source: `docs/api/00-conventions.md`
- API error registry source: `docs/api/error-codes.md`
- Endpoint index source: `docs/api/endpoints/README.md`

## Consumption Map

| Flow or Screen | Frontend Module | Endpoint Contract | Request Trigger | Response Owner |
| --- | --- | --- | --- | --- |
| Example flow | ExampleModule | API endpoint source | User or system trigger | State owner from frontend modules |

## Loading States

- Map pending, optimistic, empty, stale, retrying, and disabled states to flows and endpoint calls.

## Error Actions

- Map API error codes to user-visible copy, recovery action, retry behavior, telemetry, and acceptance criteria.
