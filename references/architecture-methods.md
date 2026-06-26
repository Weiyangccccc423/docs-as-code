# Architecture Methods Reference

Use this file when architecture or backend design needs a recognized external method.

## C4 Model

Use C4 to separate architecture views by abstraction level:

| View | Use |
| --- | --- |
| System Context | actors, external systems, and product boundary |
| Container | deployable/runtime units and data stores |
| Component | major components inside one container |
| Code | optional; only when implementation detail is useful |

Rules:

- Start with System Context before module design.
- Do not jump to classes before containers and data ownership are clear.
- Link every external system to API, plugin, or operations documentation.

Reference: `https://c4model.com/`

## arc42

Use arc42 as a completeness checklist for architecture documentation:

- introduction and goals
- constraints
- context and scope
- solution strategy
- building block view
- runtime view
- deployment view
- cross-cutting concepts
- architecture decisions
- quality requirements
- risks and technical debt
- glossary

Reference: `https://docs.arc42.org/home/`

## ADR

Use ADRs for decisions that are hard to reverse, cross-module, or repeatedly questioned.

Minimum ADR fields:

- Context
- Decision
- Consequences
- References

Reference: `https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions`

## OpenAPI

Use OpenAPI as the machine-readable HTTP API contract. Markdown endpoint files are human review layers.

Reference: `https://spec.openapis.org/oas/latest.html`
