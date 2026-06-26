# Phase 01: Empty Repository Initialization

## Input

- Empty or near-empty target folder
- Optional product document path
- This workflow pack

## Skills

Load:

- `using-governance-workflow`
- `initializing-governance-repo`
- `verifying-governance-docs`

## Procedure

1. Check environment:

   ```bash
   bin/governance env --repair --target <target>
   ```

2. Initialize the target folder:

   ```bash
   bin/governance init --target <target> --product <product-doc> --profile <profile> --project-name "<name>"
   ```

3. Inspect generated root files:

   - `README.md`
   - `AGENTS.md`
   - `SPEC.md`
   - `CONTRIBUTING.md`
   - `GOVERNANCE.md`
   - `SECURITY.md`
   - `Makefile`
   - `bin/governance`
   - `scripts/governance_cli.py`

4. Inspect generated docs domains:

   - `docs/product/`
   - `docs/architecture/`
   - `docs/ui/`
   - `docs/api/`
   - `docs/backend/`
   - `docs/frontend/`
   - `docs/tests/`
   - `docs/decisions/`
   - `docs/development/`
   - `docs/agent-workflow/`

5. Verify:

   ```bash
   bin/governance verify <target>
   bin/governance status <target>
   ```

## Output

A repository skeleton with governance entry points, product core files, unresolved item registry, glossary, and domain-level docs entrances.

The target receives a local governance runtime under `bin/` and `scripts/`. After initialization, use target-local commands when working inside the generated repository:

```bash
bin/governance verify .
make verify-governance
```

The target also receives `.governance/state.json`, which records phase, profile, product source, archive path, and last verification status.

## Stop Conditions

- Target folder has existing governance files and the user did not approve overwrite.
- Product document path is missing or unreadable.
- The target project type is unclear and would change the top-level code layout.
