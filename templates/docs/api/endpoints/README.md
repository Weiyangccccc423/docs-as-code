# API Endpoints

## Index

| Endpoint | Method and Path | Product Source | Frontend Consumer |
| --- | --- | --- | --- |
| [01-endpoint-contract.md](01-endpoint-contract.md) | POST /example | Product requirement source | Frontend consumer source |

## Naming Rules

- Endpoint files must use `NN-<slug>.md` with unique `NN` prefixes.
- Keep `01-endpoint-contract.md` only as the starter endpoint contract until replaced or renamed from product-derived API design.

## Traceability Rules

- Every listed endpoint must link to a local endpoint contract file.
- Endpoint contracts must reference `docs/api/error-codes.md`.
- Endpoint contracts must link upstream product, architecture, backend, decision, or unresolved Markdown sources.
- Endpoint contracts must link local UI or frontend API-consumption Markdown consumers.
