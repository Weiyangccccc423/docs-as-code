---
name: structuring-product-requirements
description: Use when splitting an archived PRD into product chapters, extracting glossary terms, acceptance criteria, success metrics, or unresolved questions.
---

# Structuring Product Requirements

Turn a preserved PRD into navigable product truth without changing its meaning.

## Output Layers

| Layer | Purpose |
| --- | --- |
| `core/PRD.md` | canonical product source |
| `core/product-meta.md` | summary and navigation |
| `NN-*.md` chapters | derived views |
| `docs/unresolved.md` | ambiguity registry |
| `docs/glossary.md` | cross-domain terms |

## Procedure

1. Run the product gate:

   ```bash
   bin/governance advance product-structuring <target> --check --json
   bin/governance advance product-structuring <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`. When the write command succeeds, keep the returned `next_actions`, `cwd`, and `argv` for later, but finish this phase's authored product chapters before running the next transition.

2. Read `references/product-requirements-checklist.md` before splitting or rewriting product content.
3. Read `core/source/source-manifest.json`.
4. Stop if `can_derive_design` is not true or the manifest hash does not verify.
5. Run `bin/governance product plan <target> --json` before creating chapter files. Use returned `source_documents`, `available_chapters`, `prd_headings`, `suggested_mappings`, `required_decisions`, `chapter_dispositions`, `stale_chapter_dispositions`, `disposition_summary`, `manual_authoring_tasks`, `manual_authoring_summary`, `skills`, `skill_requirements`, `authority_skill_requirements`, and ordered `steps` as the work queue. The `decision_policy` is `do_not_guess_product_meaning`; use `manual_authoring_summary` for `task_count`, `open_decision_count`, `required_evidence_status_counts`, `non_satisfied_required_evidence_count`, and `evidence_repair_action_count` before drilling into task details. Accept a `suggested_mappings[].command_arg` only after source review, and resolve every `required_decisions[]` item with an explicit `key=PRD Heading`, manual PRD-backed authoring, or a recorded omission of an unsupported optional chapter. Treat unresolved `manual_authoring_tasks[]` as `status: decision_required` work until a disposition or PRD evidence resolves the choice; `author-required` changes the status to `authoring_required` and keeps evidence work active. Each task lists `execution`, `required_sections`, `required_links`, `required_evidence`, `evidence_repair_actions`, `open_decisions`, and verify/refresh steps. Use each `required_evidence[].status` as the machine-readable repair signal; conservative values include `missing`, `not_indexed`, `not_linked`, `placeholder_present`, `pending_review`, and `satisfied`. Follow `evidence_repair_actions[]` by `sequence`; each action includes `repair_strategy`, `verify_command`, and `refresh_command` for the matching non-satisfied evidence item. Satisfy `required_evidence[]` for PRD source support, chapter file authoring, README indexing, `product-meta.md` linking, unresolved-question review, glossary review, and chapter-specific checks such as stable `A-NNN` acceptance IDs.
6. When a work package returns `next_action.kind: decide-product-chapter`, run `bin/governance product disposition <target> --chapter <chapter-key> --decision <author-required|omit-unsupported> --reason "<source-review explanation>" --reviewed --check --json`, inspect the no-write plan, then run it without `--check`. The decision is stored in `docs/product/core/chapter-dispositions.json` with the current PRD SHA-256 and explicit `review_scope` for chapter source, unresolved items, and glossary terms. This review receipt does not satisfy objective file, index, link, acceptance-ID, or chapter-specific evidence. Never omit `goals-and-requirements` or `acceptance-criteria`; stop on stale dispositions after the PRD changes.
7. Build the chapter map in `product-meta.md`.
8. Preview and create only PRD-supported chapter scaffolds with `bin/governance scaffold product <target> --chapter <chapter-key> --check --json`, inspect `would_create`, `would_skip`, and `would_index`, then run the same command without `--check` when the plan is correct; available chapter keys are `background-and-problems`, `change-log`, `goals-and-requirements`, `functional-spec`, `acceptance-criteria`, and `success-metrics`.
9. Use returned `local_commands` for checks and inspect `scaffold_phase`; if `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved. Keep `NN-<slug>.md` filenames with unique `NN` prefixes.
10. When the PRD has explicit headings that can be copied without interpretation, run `bin/governance product structure <target> --chapter "goals-and-requirements=Goals and Requirements" --chapter "acceptance-criteria=Acceptance Criteria" --check --json`, inspect `would_update`, then run it without `--check` when the heading mapping is correct. This command uses explicit `key=PRD Heading` mappings, removes product scaffold placeholders, cleans product README structured placeholders, creates stable `A-NNN` acceptance IDs from acceptance bullets, and returns `local_commands` plus `next_actions`.
11. If `product structure` reports a missing PRD heading, stop and author that chapter manually from the source instead of guessing.
12. Replace every remaining `governance:scaffold-placeholder` with PRD-derived content before leaving this phase.
13. Link every chapter back to `core/PRD.md`.
14. Link every `NN-*.md` chapter from `core/product-meta.md`.
15. Extract acceptance criteria into a stable `NN-*acceptance*.md` chapter before design derivation. Give each criterion a stable unique `A-NNN` ID.
16. Extract success metrics when present.
17. Add cross-domain terms to glossary with unique `Term`, filled `Meaning`, and a `Source` link to the local Markdown definition.
18. Register ambiguous requirements before deriving design. Use unique `U-NNN` IDs and fill `Domain` and `Description`; use `none`, `-`, `n/a`, `non-blocking`, or `resolved` only for items that do not block downstream work.

## Stop Conditions

- A chapter needs invented product scope.
- Two terms appear to refer to the same concept with different names.
- Acceptance criteria and functional text conflict.
- The archived source manifest reports `conversion_required`.
- `docs/unresolved.md` has any row with a blocking `Blocking Scope`.
