# Product Requirements Checklist

Use this checklist before product chapters, acceptance criteria, glossary terms, or unresolved questions drive design derivation.

Calibrate against ISO/IEC/IEEE 29148 requirements engineering, INVEST story quality, and Gherkin-style scenario phrasing without making any one format mandatory. Markdown product documents remain the human review layer.

## Chapter Dispositions

- Is every unsupported optional chapter resolved with a reviewed `author-required` or `omit-unsupported` decision rather than silently skipped?
- Was `product disposition --check` run before writing `docs/product/core/chapter-dispositions.json`?
- Does each disposition bind to the current canonical PRD SHA-256 with a concrete source-review reason?
- Does `review_scope` cover chapter source, unresolved items, and glossary implications without replacing objective file or traceability evidence?
- Are stale dispositions rejected after the PRD changes?
- Are `goals-and-requirements` and `acceptance-criteria` protected from omission?

## Source Fidelity

- Does every derived product chapter link back to `docs/product/core/PRD.md` or a specific local source section?
- Do summaries preserve product meaning without invented actors, workflows, constraints, or success targets?
- Are assumptions either directly supported by the PRD or registered in `docs/unresolved.md`?

Reference: `https://www.iso.org/standard/72089.html`

## Requirement Quality

- Are requirements clear, necessary, feasible, unambiguous, verifiable, and traceable?
- Is each requirement written as product behavior, constraint, policy, or measurable outcome rather than implementation detail?
- Can downstream architecture, API, UI, backend, frontend, and tests cite the requirement without guessing intent?

Reference: `https://www.iso.org/standard/72089.html`

## Scope and Story Slicing

- Are user or job statements small enough to design and verify independently without losing product value?
- Do story-like requirements satisfy INVEST checks: independent, negotiable, valuable, estimable, small, and testable?
- Are oversized, ambiguous, or cross-cutting requirements split or marked as unresolved before design derivation?

Reference: `https://xp123.com/articles/invest-in-good-stories-and-smart-tasks/`

## Acceptance Criteria

- Does each product acceptance criterion use a stable product-defined `A-NNN` ID?
- Is each criterion outcome-based and measurable enough to verify by test, review, or explicit manual evidence?
- When scenario structure helps, can it be expressed as Given/When/Then without adding unstated behavior?
- Are acceptance criteria separated from implementation tasks and UI/API design decisions?

Reference: `https://cucumber.io/docs/gherkin/reference/`

## Functional, Quality, and Constraint Separation

- Are functional behavior, quality expectations, constraints, success metrics, and out-of-scope items separated?
- Are non-functional claims tied to measurable response, reliability, security, privacy, usability, or operations expectations?
- Are success metrics preserved in a dedicated product chapter when present in the PRD?

## Glossary and Domain Language

- Does each cross-domain glossary row have a unique `Term`, filled `Meaning`, and local Markdown `Source`?
- Are synonyms, aliases, and near-duplicates reconciled before they become API, data, or UI names?
- Are terms with conflicting meanings registered in `docs/unresolved.md` before design derivation?

## Unresolved Questions

- Does every ambiguity use a unique `U-NNN` ID with filled `Domain`, `Description`, and `Blocking Scope`?
- Is `Blocking Scope` explicit enough to show which design or implementation work is blocked?
- Are non-blocking values limited to the workflow-approved values: `none`, `-`, `n/a`, `non-blocking`, or `resolved`?

## Design Readiness

- Is every product chapter indexed by `docs/product/README.md` and `docs/product/core/product-meta.md`?
- Does a dedicated acceptance criteria chapter exist before design derivation?
- Are there no blocking unresolved rows in `docs/unresolved.md` before the design-derivation phase transition?
