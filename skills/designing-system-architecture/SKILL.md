---
name: designing-system-architecture
description: Use when deriving system architecture, boundaries, C4-style views, quality attributes, deployment assumptions, or cross-module decisions from structured product docs.
---

# Designing System Architecture

Use product truth to define system boundaries before implementation design.

Read `references/architecture-methods.md` before producing architecture documents.

## Required Views

- system context
- containers
- external dependencies
- runtime flow for critical user paths
- quality attributes
- deployment assumptions
- major risks
 - ADR candidates

## Procedure

1. Read product scope and acceptance criteria.
2. Identify actors, systems, and external services.
3. Define containers without committing to unnecessary internal classes.
4. Record cross-module decisions as ADRs.
5. Link every architecture claim to product, API, or decision sources.

## Stop Conditions

- A boundary decision changes product scope.
- A dependency is assumed without ownership or contract.
- A quality attribute is implied but not measurable.
