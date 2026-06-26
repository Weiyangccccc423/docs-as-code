---
name: initializing-governance-repo
description: Use when creating project governance in an empty or near-empty repository before product design or implementation starts.
---

# Initializing Governance Repo

Create the minimum structure needed for reliable docs-as-code work.

## Steps

1. Run environment check:

   ```bash
   bin/governance env --repair --target <target> --json
   ```

2. Run preflight without writing files:

   ```bash
   bin/governance init --check --target <target> --product <product-doc> --json
   ```

   Stop when `ok` is false. Existing generated governance files require user approval before `--force`.

3. Bootstrap the target:

   ```bash
   bin/governance init --target <target> --product <product-doc>
   ```

4. Verify:

   ```bash
   bin/governance verify <target>
   ```

5. Check the first downstream phase gate:

   ```bash
   bin/governance gate product-structuring <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

6. When working inside the initialized target, switch to the copied target-local runtime:

   ```bash
   bin/governance verify .
   make verify-governance
   ```

## Required Output

- root `README.md`, `AGENTS.md`, `SPEC.md`
- root `bin/governance` and `scripts/governance_cli.py`
- `docs/README.md`, `docs/AGENTS.md`
- `docs/product/core/PRD.md`
- `docs/unresolved.md`
- `docs/glossary.md`
- domain `README.md` and `AGENTS.md` for non-empty docs directories

## Stop Conditions

- Existing files would be overwritten without user approval.
- Product document cannot be read.
- Project type is unclear and affects code-directory choices.
