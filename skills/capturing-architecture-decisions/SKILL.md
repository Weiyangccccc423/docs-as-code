---
name: capturing-architecture-decisions
description: Use when recording cross-module, hard-to-reverse, high-cost, repeatedly debated, or alternative-rich technical decisions.
---

# Capturing Architecture Decisions

Use ADRs for decision history, not general design notes.

Read `references/architecture-methods.md` and `references/architecture-decision-record-checklist.md` before creating ADRs. Use the methods reference for the baseline ADR pattern and the checklist for trigger, context, options, rationale, consequences, lifecycle, traceability, and indexing decisions.

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
- Name ADR files as `NNN-<slug>.md` under `docs/decisions/`, with unique numeric prefixes.
- Include rejected alternatives.
- Link `References` to existing local Markdown product, architecture, API, backend/frontend, or unresolved sources.
- For product-derived design decisions, run `bin/governance gate design-derivation <target> --json` first.
- Keep accepted ADR bodies stable; supersede with a new ADR when the decision changes.
- Add reverse links from module docs that cite the ADR.

## Procedure

1. Run `bin/governance design architecture-decisions-authoring <target> --json` and follow `authoring_tasks[]`. The payload's `decision_policy` is `do_not_guess_architecture_decisions`; each task lists ADR `documents`, required `sections`, `required_links`, unresolved `open_decisions` such as `adr_trigger`, `decision_scope`, and `alternatives`, `requires_adr: undetermined`, `specialist_skills` including `senior-architect`, `migration-architect`, and `tech-stack-evaluator`, and read-only command steps verify-architecture-decisions-authoring and refresh-architecture-decisions-authoring.
2. Read `references/architecture-methods.md` and `references/architecture-decision-record-checklist.md`.
3. Read the task's product, architecture, API, backend, frontend, test, task-board, and unresolved sources before deciding whether an ADR is required.
4. Create a numbered ADR only when the trigger is source-backed; otherwise register a deferred or no-ADR reason in the appropriate source or unresolved item.
5. Run the task's read-only verification and refresh steps before considering ADR authoring complete.
