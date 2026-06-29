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
   bin/governance advance product-structuring <target> --json
   ```

2. Build a product chapter map in `product-meta.md`.
3. Split stable sections into `docs/product/NN-<slug>.md`; use unique two-digit prefixes for ordering.
4. Extract acceptance criteria into a dedicated `NN-*acceptance*.md` product chapter before design derivation.
5. Extract success metrics into a dedicated product chapter when present.
6. Add cross-domain terms to `docs/glossary.md` with filled `Term`, `Meaning`, and `Source`; `Source` must link to the local Markdown document that defines the term.
7. Register unresolved product or interaction questions in `docs/unresolved.md` with unique `U-NNN` IDs.
8. Update `docs/product/README.md` so every product chapter file is indexed.

Use `none`, `-`, `n/a`, `non-blocking`, or `resolved` in `Blocking Scope` only when the item does not block downstream work. Any other value blocks governance verification.

## Output Pattern

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

Use only chapters that the source document supports. Do not create empty decorative files.

## Verification

- Every product chapter links back to `core/PRD.md`.
- Every product chapter filename uses `NN-<slug>.md`, and each `NN` prefix is unique.
- A dedicated acceptance criteria product chapter exists before design derivation.
- `README.md` lists every product chapter.
- `product-meta.md` links to every product chapter.
- `docs/glossary.md` terms are unique, complete, and traceable to local Markdown sources.
- `docs/unresolved.md` contains every ambiguity with unique `U-NNN` IDs, filled `Domain` and `Description`, and no blocking rows before design derivation.

Run:

```bash
bin/governance verify <target> --json
```

## Stop Conditions

- A derived chapter would require inventing missing product meaning.
- Acceptance criteria conflict with functional requirements.
- A term has different meanings across product, UI, API, or implementation text.
- `docs/unresolved.md` contains any row with a blocking scope.
