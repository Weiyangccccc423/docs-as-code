---
name: capturing-architecture-decisions
description: Use when recording cross-module, hard-to-reverse, high-cost, repeatedly debated, or alternative-rich technical decisions.
---

# Capturing Architecture Decisions

Use ADRs for decision history, not general design notes.

## ADR Trigger

Create an ADR when a decision:

- affects two or more modules
- changes runtime topology or state machines
- selects or rejects infrastructure such as queues, caches, storage, auth, or API strategy
- has credible alternatives
- will be cited by future implementation tasks

## Required Fields

- Context
- Decision
- Consequences
- References

## Rules

- Keep ADRs short.
- Include rejected alternatives.
- For product-derived design decisions, run `bin/governance gate design-derivation <target> --json` first.
- Keep accepted ADR bodies stable; supersede with a new ADR when the decision changes.
- Add reverse links from module docs that cite the ADR.
