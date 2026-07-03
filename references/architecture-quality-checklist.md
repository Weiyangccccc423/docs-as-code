# Architecture Quality Checklist

Use this checklist before architecture documents are used for API, backend, frontend, test, or implementation planning work.

Calibrate architecture quality against ISO/IEC/IEEE 42010 architecture-description structure, ISO/IEC 25010 product quality categories, arc42 quality scenarios, and lightweight ATAM-style tradeoff review. Keep the generated documents concise, but make quality expectations measurable enough for tests and task planning.

## Architecture Description

- Are stakeholders, concerns, system boundary, views, decisions, rationale, and known inconsistencies explicit?
- Do context, container, runtime, deployment, and quality views answer distinct stakeholder concerns?
- Are architecture claims linked to product scope, acceptance criteria, API contracts, backend/frontend design, ADRs, or unresolved questions?

Reference: `https://www.iso.org/standard/74393.html`

## Quality Model Coverage

- Are relevant quality characteristics named, such as availability, performance efficiency, compatibility, usability, reliability, security, maintainability, portability, safety, or operational suitability?
- Is each selected quality attribute tied to product value, stakeholder concern, or acceptance criteria?
- Are non-selected quality attributes either irrelevant for the product or registered as deferred/open decisions?

Reference: `https://www.iso.org/standard/78176.html`

## Quality Scenarios

- Does each important quality attribute have at least one measurable scenario with source, stimulus, environment, affected artifact, response, and response measure?
- Are usage, change, and failure scenarios covered when relevant?
- Are response measures concrete enough to become verification scope, such as latency, throughput, recovery time, error budget, manual effort, or migration duration?

Reference: `https://docs.arc42.org/section-10/`

## Runtime and Failure Flow

- Are critical success, degraded, retry, timeout, fallback, compensation, and cancellation paths documented?
- Are data ownership, consistency boundaries, and cross-container trust boundaries clear?
- Are observability signals named for important flows, including logs, metrics, traces, audit events, and alerts?

## Tradeoff Review

- Are sensitivity points, tradeoffs, risks, and non-risks recorded for high-cost architecture choices?
- Are alternatives documented when a choice materially affects quality attributes or implementation cost?
- Are decisions that are hard to reverse captured as ADRs with references to product, architecture, API, backend/frontend, and test sources?

Reference: `https://resources.sei.cmu.edu/asset_files/TechnicalReport/2000_005_001_13706.pdf`

## Implementation Readiness

- Can backend, frontend, API, data, and test design proceed without inventing architecture meaning?
- Are unresolved quality, deployment, external dependency, or operational questions registered in `docs/unresolved.md` before implementation handoff?
- Are verification hooks identified for every high-risk quality scenario?
