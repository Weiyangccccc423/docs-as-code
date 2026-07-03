# Test Strategy Checklist

Use this checklist before test strategy, acceptance matrix, or implementation verification plans are treated as ready for coding.

Calibrate test strategy against DORA test automation, the test pyramid, accessibility standards, and observability practices. Keep the strategy product-backed: tests should prove acceptance criteria and design risks, not just exercise code paths.

## Acceptance Traceability

- Does every product-defined `A-NNN` acceptance criterion map to design, API, and test evidence, or appear under Uncovered Criteria with a product-backed reason?
- Are acceptance IDs copied from product sources only, without inventing criteria in the matrix?
- Are manual-review criteria explicit about reviewer, evidence target, and follow-up path?

## Test Portfolio

- Are fast unit tests, integration tests, contract tests, and end-to-end tests assigned according to risk and feedback speed?
- Are high-value user journeys covered without making the slowest tests the only confidence source?
- Are backend, frontend, API, data, accessibility, security, observability, migration, and operational risks each assigned an appropriate verification layer when relevant?

Reference: `https://martinfowler.com/bliki/TestPyramid.html`

## Automation and Feedback

- Are verification commands local, deterministic, and suitable for agent execution before implementation handoff?
- Are CI expectations, failure triage, ownership, flaky-test handling, and skipped-test follow-ups documented?
- Are generated clients, schema checks, contract checks, linting, formatting, type checks, and migration checks included when the stack needs them?

Reference: `https://dora.dev/capabilities/test-automation/`

## Test Data and Environments

- Are test data sources, fixtures, seed data, cleanup, privacy constraints, and cross-user isolation rules documented?
- Are environment assumptions, external dependencies, fakes, mocks, sandboxes, and offline-mode behavior explicit?
- Are destructive, stateful, or production-adjacent checks separated from normal local verification commands?

Reference: `https://dora.dev/capabilities/test-data-management/`

## Non-Functional Verification

- Are performance, accessibility, security, reliability, observability, recovery, compatibility, and data-migration checks mapped from product/design risk?
- Are accessibility checks calibrated against WCAG when UI behavior is in scope?
- Are logs, metrics, traces, and audit-event expectations testable or explicitly assigned to manual review?

Reference: `https://www.w3.org/TR/WCAG22/`
Reference: `https://opentelemetry.io/docs/concepts/signals/`

## Evidence Maintenance

- Does each planned verification item identify the command, expected result, evidence file, and owner of follow-up failures?
- Are Done-task results recorded in `docs/development/03-verification-log.md` or another local Markdown evidence target?
- Are unresolved test gaps registered in `docs/unresolved.md` before implementation starts?
