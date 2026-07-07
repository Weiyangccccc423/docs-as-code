# Phase 03: Product Structuring

## Input

- `docs/product/core/PRD.md`
- `docs/product/core/product-meta.md`
- `docs/unresolved.md`
- `docs/glossary.md`

## Skills

Load:

- `structuring-product-requirements`
- `archiving-product-document`
- `verifying-governance-docs`

## Procedure

1. Confirm the product is ready for structuring:

   ```bash
   bin/governance advance product-structuring <target> --check --json
   bin/governance advance product-structuring <target> --json
   ```

   The write command records the phase transition and returns `local_commands` plus `next_actions` for the next workflow transition. Do not follow those later actions until this phase's product chapters and verification requirements are complete.

2. Read `references/product-requirements-checklist.md` and use it as the rubric for source fidelity, requirement quality, acceptance IDs, glossary rows, unresolved questions, and design readiness.
3. Build the product structuring plan before creating chapter files:

   ```bash
   bin/governance product plan <target> --json
   ```

   The plan is read-only and returns `source_documents`, `available_chapters`, `prd_headings`, conservative `suggested_mappings`, `required_decisions`, `manual_authoring_tasks`, local workflow `skills`, `skill_requirements`, `authority_skill_requirements`, and ordered executable `steps`. Its `decision_policy` is `do_not_guess_product_meaning`. Use `suggested_mappings[].command_arg` only after source review confirms the PRD heading can be copied without interpretation. Resolve every `required_decisions[]` item by supplying an explicit `key=PRD Heading` mapping, authoring the chapter manually from the PRD, or omitting the unsupported chapter. Follow `manual_authoring_tasks[]` only after its `status: decision_required` is resolved; each task lists `execution`, `required_sections`, `required_links`, `required_evidence`, `open_decisions`, and read-only verify/refresh steps for PRD-backed manual authoring. Required evidence covers PRD source support, chapter file authoring, product README indexing, `product-meta.md` linking, unresolved-question review, glossary review, and chapter-specific checks such as stable `A-NNN` acceptance IDs.
4. Select only the product chapters that the source document supports. Use the deterministic scaffold to create selected files, update `docs/product/README.md`, and link them from `product-meta.md`:

   ```bash
   bin/governance scaffold product <target> \
     --chapter goals-and-requirements \
     --chapter acceptance-criteria \
     --check \
     --json
   bin/governance scaffold product <target> \
     --chapter goals-and-requirements \
     --chapter acceptance-criteria \
     --json
   ```

   `--check` reports `would_create`, `would_skip`, and `would_index` without writing placeholders. The write command returns `local_commands`, `next_actions`, and `scaffold_phase` when gate state is readable; when scaffold placeholders remain, it also returns `next_actions_blocked_by`. If `scaffold_phase.matches` is false, use returned `next_actions` to advance recorded phases in order before treating the scaffold as current phase work. Use the returned check commands, keep the next actions for later, and do not run downstream phase actions until every blocker listed in `next_actions_blocked_by` is resolved. Available chapter keys: `background-and-problems`, `change-log`, `goals-and-requirements`, `functional-spec`, `acceptance-criteria`, `success-metrics`.
5. When PRD headings are explicit enough to copy without interpretation, use the deterministic `product structure` command to replace scaffold placeholders from explicit `key=PRD Heading` mappings:

   ```bash
   bin/governance product structure <target> \
     --chapter "goals-and-requirements=Goals and Requirements" \
     --chapter "acceptance-criteria=Acceptance Criteria" \
     --check \
     --json
   bin/governance product structure <target> \
     --chapter "goals-and-requirements=Goals and Requirements" \
     --chapter "acceptance-criteria=Acceptance Criteria" \
     --json
   ```

   `--check` reports `would_update` without writing files. The write command copies only the named PRD sections, creates stable `A-NNN` acceptance IDs from acceptance bullets, removes product scaffold placeholders, cleans product README structured placeholders, and returns `local_commands` plus `next_actions`. If a required PRD heading is missing, stop and author the chapter manually from the source instead of guessing.
6. If PRD review reveals another supported chapter before placeholders are replaced, rerun `product plan` and then rerun `scaffold product` with the additional `--chapter`. The command may proceed while existing `docs/product/` scaffold placeholders remain, but any other verification error still blocks it.
7. Replace every remaining `governance:scaffold-placeholder` with PRD-derived content before leaving this phase.
8. Build or refine the product chapter map in `product-meta.md`.
9. Split stable sections into `docs/product/NN-<slug>.md`; use unique two-digit prefixes for ordering.
10. Extract acceptance criteria into a dedicated `NN-*acceptance*.md` product chapter before design derivation; give each criterion a stable unique `A-NNN` ID.
11. Extract success metrics into a dedicated product chapter when present.
12. Add cross-domain terms to `docs/glossary.md` with filled `Term`, `Meaning`, and `Source`; `Source` must link to the local Markdown document that defines the term.
13. Register unresolved product or interaction questions in `docs/unresolved.md` with unique `U-NNN` IDs.
14. Update `docs/product/README.md` so every product chapter file is indexed.

Use `none`, `-`, `n/a`, `non-blocking`, or `resolved` in `Blocking Scope` only when the item does not block downstream work. Any other value blocks governance verification.

## Output

```text
docs/product/
├── README.md
├── AGENTS.md
├── core/
│   ├── PRD.md
│   └── product-meta.md
├── 01-background-and-problems.md
├── 02-change-log.md
├── 03-goals-and-requirements.md
├── 07-functional-spec.md
├── 08-acceptance-criteria.md
└── 09-success-metrics.md
```

Use only chapters that the source document supports. Do not create empty decorative files. Scaffolded product chapters are temporary work surfaces and block verification until their placeholders are replaced with source-backed content.

## Verification

- Every product chapter links back to `core/PRD.md`.
- Product chapter, acceptance, glossary, unresolved-question, and design-readiness decisions satisfy `references/product-requirements-checklist.md`.
- Every product chapter filename uses `NN-<slug>.md`, and each `NN` prefix is unique.
- A dedicated acceptance criteria product chapter exists before design derivation and exposes stable unique `A-NNN` criteria IDs.
- `README.md` lists every product chapter.
- `product-meta.md` links to every product chapter.
- `docs/glossary.md` terms are unique, complete, and traceable to local Markdown sources.
- `docs/unresolved.md` contains every ambiguity with unique `U-NNN` IDs, filled `Domain` and `Description`, and no blocking rows before design derivation.

Run:

```bash
bin/governance verify <target> --check --json
bin/governance verify <target> --json
```

## Stop Conditions

- A derived chapter would require inventing missing product meaning.
- Acceptance criteria conflict with functional requirements.
- A term has different meanings across product, UI, API, or implementation text.
- `docs/unresolved.md` contains any row with a blocking scope.
