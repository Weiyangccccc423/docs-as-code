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

2. Read `core/source/source-manifest.json`.
3. Stop if `can_derive_design` is not true or the manifest hash does not verify.
4. Build the chapter map in `product-meta.md`.
5. Preview and create only PRD-supported chapter scaffolds with `bin/governance scaffold product <target> --chapter <chapter-key> --check --json`, inspect `would_create`, `would_skip`, and `would_index`, then run the same command without `--check` when the plan is correct; available chapter keys are `background-and-problems`, `change-log`, `goals-and-requirements`, `functional-spec`, `acceptance-criteria`, and `success-metrics`.
6. Use returned `local_commands` for checks and inspect `scaffold_phase`; if `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work. If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved. Keep `NN-<slug>.md` filenames with unique `NN` prefixes.
7. Replace every `governance:scaffold-placeholder` with PRD-derived content before leaving this phase.
8. Link every chapter back to `core/PRD.md`.
9. Link every `NN-*.md` chapter from `core/product-meta.md`.
10. Extract acceptance criteria into a stable `NN-*acceptance*.md` chapter before design derivation. Give each criterion a stable unique `A-NNN` ID.
11. Extract success metrics when present.
12. Add cross-domain terms to glossary with unique `Term`, filled `Meaning`, and a `Source` link to the local Markdown definition.
13. Register ambiguous requirements before deriving design. Use unique `U-NNN` IDs and fill `Domain` and `Description`; use `none`, `-`, `n/a`, `non-blocking`, or `resolved` only for items that do not block downstream work.

## Stop Conditions

- A chapter needs invented product scope.
- Two terms appear to refer to the same concept with different names.
- Acceptance criteria and functional text conflict.
- The archived source manifest reports `conversion_required`.
- `docs/unresolved.md` has any row with a blocking `Blocking Scope`.
