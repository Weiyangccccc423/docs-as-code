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

1. Build a product chapter map in `product-meta.md`.
2. Split stable sections into `docs/product/NN-<slug>.md`.
3. Extract acceptance criteria into a dedicated product chapter.
4. Extract success metrics into a dedicated product chapter when present.
5. Add cross-domain terms to `docs/glossary.md`.
6. Register unresolved product or interaction questions in `docs/unresolved.md`.
7. Update `docs/product/README.md`.

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
- `README.md` lists every product chapter.
- `product-meta.md` links to every product chapter.
- `docs/unresolved.md` contains every blocking ambiguity.

Run:

```bash
python3 scripts/verify_governance.py <target>
```

## Stop Conditions

- A derived chapter would require inventing missing product meaning.
- Acceptance criteria conflict with functional requirements.
- A term has different meanings across product, UI, API, or implementation text.
