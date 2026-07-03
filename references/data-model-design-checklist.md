# Data Model Design Checklist

Use this checklist before `docs/backend/02-data-model.md` is used for backend implementation, API contracts, migrations, tests, or agent task planning.

Calibrate against relational constraint, index, and transaction practices plus evolutionary database design. If the target datastore is not relational, document the equivalent identity, constraint, consistency, query, and migration controls instead of omitting the decision.

## Product Traceability and Ownership

- Does every entity, table, collection, field group, or stored event link to a product, API, backend module, or acceptance source?
- Is the owning backend module explicit for every persistent concept?
- Are derived fields, denormalized fields, caches, and projections tied to their source of truth and refresh rules?
- Are unresolved ownership or source questions registered in `docs/unresolved.md` before implementation handoff?

## Identity and Relationships

- Does each persistent entity have a stable identity strategy, including primary key, external identifier, and tenant or user isolation boundary when relevant?
- Are relationship cardinality, optionality, referential actions, and deletion behavior explicit?
- Are natural keys, surrogate keys, and public IDs chosen deliberately and documented when they differ?

Reference: `https://www.postgresql.org/docs/current/ddl-constraints.html`

## Constraints and Invariants

- Are required fields, uniqueness rules, foreign-key relationships, value bounds, and cross-field invariants documented?
- Are idempotency keys, duplicate-submission behavior, and cross-user isolation enforced at the appropriate storage or transaction boundary?
- Are application-only invariants explicitly justified when the datastore cannot enforce them directly?

Reference: `https://www.postgresql.org/docs/current/ddl-constraints.html`

## State and Concurrency

- Are lifecycle states and allowed transitions defined before fields or tables are finalized?
- Does each state-changing operation document transaction boundaries, isolation expectations, lock or version strategy, and conflict outcomes?
- Are eventual-consistency windows, retry behavior, and compensation paths explicit for asynchronous or distributed flows?

Reference: `https://www.postgresql.org/docs/current/transaction-iso.html`

## Query Paths and Indexes

- Does every index map to a documented query path, filter, sort, uniqueness rule, or foreign-key access pattern?
- Are pagination order, cursor stability, tenant or user filters, and expensive-query limits documented?
- Are write overhead, index maintenance, composite ordering, partial coverage, and query-plan verification considered before adding indexes?

Reference: `https://www.postgresql.org/docs/current/indexes.html`

## Migration and Backfill

- Are schema changes versioned and ordered with forward migration, compatibility, backfill, validation, and rollback or roll-forward expectations?
- Can old and new application versions coexist during deployment when zero-downtime or staged rollout is required?
- Are destructive changes, data corrections, and historical data assumptions documented with verification evidence targets?

Reference: `https://martinfowler.com/articles/evodb.html`

## Retention, Deletion, and Audit

- Are retention, archival, soft-delete, restore, legal hold, and hard-delete rules explicit when product or policy requires them?
- Are audit fields or audit events defined for security-sensitive, financial, administrative, or cross-user changes?
- Are sensitive data, encryption, masking, logging, and export behavior linked to `references/security-design-checklist.md` when relevant?

## Verification

- Are constraint tests, migration tests, concurrency tests, query-performance checks, and fixture or seed-data expectations identifiable?
- Do acceptance criteria and API contracts cover lifecycle, idempotency, conflict, retention, and deletion behavior?
- Are any unverified data risks registered in `docs/unresolved.md` before task planning?
