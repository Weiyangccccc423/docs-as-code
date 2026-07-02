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

2. Select only the product chapters that the source document supports. Use the deterministic scaffold to create selected files, update `docs/product/README.md`, and link them from `product-meta.md`:

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

   `--check` reports `would_create`, `would_skip`, and `would_index` without writing placeholders. Available chapter keys: `background-and-problems`, `change-log`, `goals-and-requirements`, `functional-spec`, `acceptance-criteria`, `success-metrics`.
3. If PRD review reveals another supported chapter before placeholders are replaced, rerun `scaffold product` with the additional `--chapter`. The command may proceed while existing `docs/product/` scaffold placeholders remain, but any other verification error still blocks it.
4. Replace every `governance:scaffold-placeholder` with PRD-derived content before leaving this phase.
5. Build or refine the product chapter map in `product-meta.md`.
6. Split stable sections into `docs/product/NN-<slug>.md`; use unique two-digit prefixes for ordering.
7. Extract acceptance criteria into a dedicated `NN-*acceptance*.md` product chapter before design derivation; give each criterion a stable unique `A-NNN` ID.
8. Extract success metrics into a dedicated product chapter when present.
9. Add cross-domain terms to `docs/glossary.md` with filled `Term`, `Meaning`, and `Source`; `Source` must link to the local Markdown document that defines the term.
10. Register unresolved product or interaction questions in `docs/unresolved.md` with unique `U-NNN` IDs.
11. Update `docs/product/README.md` so every product chapter file is indexed.

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
