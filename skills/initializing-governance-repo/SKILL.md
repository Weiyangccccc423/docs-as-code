---
name: initializing-governance-repo
description: Use when creating project governance in an empty or near-empty repository before product design or implementation starts.
---

# Initializing Governance Repo

Create the minimum structure needed for reliable docs-as-code work.

## Steps

1. Run environment check:

   ```bash
   python3 scripts/check_env.py
   ```

2. Bootstrap the target:

   ```bash
   python3 scripts/bootstrap_tree.py --target <target> --product <product-doc>
   ```

3. Verify:

   ```bash
   python3 scripts/verify_governance.py <target>
   ```

## Required Output

- root `README.md`, `AGENTS.md`, `SPEC.md`
- `docs/README.md`, `docs/AGENTS.md`
- `docs/product/core/PRD.md`
- `docs/unresolved.md`
- `docs/glossary.md`
- domain `README.md` and `AGENTS.md` for non-empty docs directories

## Stop Conditions

- Existing files would be overwritten without user approval.
- Product document cannot be read.
- Project type is unclear and affects code-directory choices.
