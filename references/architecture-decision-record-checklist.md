# Architecture Decision Record Checklist

Use this checklist before ADRs under `docs/decisions/` are treated as stable decision history or cited by implementation tasks.

Calibrate against Architecture Decision Records, MADR, ISO/IEC/IEEE 42010 architecture descriptions, and arc42 decision guidance. The local ADR template and governance verifier remain the executable rule source for filenames, required sections, and links.

## Decision Trigger

- Does the decision affect multiple modules, runtime topology, state machines, external dependencies, security posture, data ownership, API compatibility, or long-term operations?
- Is the decision hard to reverse, costly to revisit, repeatedly debated, or rich in credible alternatives?
- Would future implementation tasks need this decision to avoid re-litigating product or architecture meaning?
- Is a non-decision or local implementation detail kept out of ADRs and documented in the owning module instead?

Reference: `https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions`

## Context and Forces

- Does Context link to existing local Markdown sources such as product requirements, acceptance criteria, architecture views, API contracts, backend/frontend design, security concerns, or unresolved items?
- Are decision drivers or forces explicit enough to explain why this decision is architecturally significant?
- Are constraints, quality attributes, stakeholder concerns, and product boundaries preserved without inventing missing product meaning?

Reference: `https://www.iso.org/standard/74393.html`

## Options and Rationale

- Are credible considered options named, including rejected alternatives and the option selected?
- Does the Decision section explain why the selected option wins against the relevant drivers?
- Are rejected alternatives rejected for documented reasons instead of taste, habit, or framework preference?
- Are assumptions and unknowns registered in `docs/unresolved.md` when they could change the decision?

Reference: `https://adr.github.io/madr/`

## Consequences and Verification

- Are positive, negative, operational, security, performance, cost, migration, and maintenance consequences documented when relevant?
- Is the expected verification path named, such as design review, contract test, migration test, runbook check, or task-board evidence?
- Are follow-up tasks, constraints, or deferred risks linked to roadmap, task board, verification log, or unresolved items?

Reference: `https://docs.arc42.org/section-9/`

## Identity and Lifecycle

- Does the ADR filename use unique `NNN-<slug>.md` numbering under `docs/decisions/`?
- Is the ADR status clear enough for readers to distinguish proposed, accepted, rejected, deprecated, or superseded decisions?
- Are accepted ADR bodies kept stable, with material changes recorded by superseding ADRs rather than silent rewrites?
- Are superseded or related ADRs cross-linked through local Markdown references?

Reference: `https://adr.github.io/madr/`

## Traceability and Indexing

- Does the References section link only to existing local Markdown sources or explicitly justified external references?
- Do architecture, API, backend, frontend, test, or task documents that rely on the decision link back to the ADR?
- Is each non-template ADR indexed by the same-directory `docs/decisions/README.md`?
- Are ADR candidates from architecture, API, backend, security, or unresolved documents either recorded or intentionally deferred?
