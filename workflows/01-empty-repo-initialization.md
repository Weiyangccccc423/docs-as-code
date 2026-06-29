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
   bin/governance env --repair --target <target> --json
   ```

   Stop when `ok` is false. Missing required tools block initialization; rerun after repair.
   If `needs_escalation` is true, show `install_commands` or `install_command` to the user and get approval before running package-manager commands outside the CLI.

2. Run initialization preflight:

   ```bash
   bin/governance init --check --target <target> --product <product-doc> --profile <profile> --project-name "<name>" --json
   ```

   Stop when `ok` is false. Existing generated governance files must be reviewed before using `--force`.

3. Initialize the target folder:

   ```bash
   bin/governance init --target <target> --product <product-doc> --profile <profile> --project-name "<name>"
   ```

4. Inspect generated root files:

   - `README.md`
   - `AGENTS.md`
   - `SPEC.md`
   - `CONTRIBUTING.md`
   - `GOVERNANCE.md`
   - `SECURITY.md`
   - `Makefile`
   - `bin/governance`
   - `scripts/governance_cli.py`
   - `docs/agent-workflow/workflow-pack/manifest.json`

5. Inspect generated docs domains:

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

6. Verify:

   ```bash
   bin/governance verify <target>
   bin/governance status <target>
   ```

## Output

A repository skeleton with governance entry points, product core files, unresolved item registry, glossary, and domain-level docs entrances.

The target receives a local governance runtime under `bin/` and `scripts/`, a runtime hash manifest at `docs/agent-workflow/runtime-manifest.json`, plus a workflow-pack snapshot under `docs/agent-workflow/workflow-pack/`. After initialization, use target-local commands when working inside the generated repository:

```bash
bin/governance verify .
make verify-governance
```

The target also receives `.governance/state.json`, which records phase, profile, product source, archive path, and last verification status.

## Stop Conditions

- Target folder has existing governance files and the user did not approve overwrite.
- `init --check` returns conflicts.
- Product document path is missing or unreadable.
- The target project type is unclear and would change the top-level code layout.
