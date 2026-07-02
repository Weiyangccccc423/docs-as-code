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
   bin/governance env --repair --check --target <target> --json
   ```

   Stop when `ok` is false. Missing required tools block initialization; inspect `would_repair`, then rerun after repair.
   If `needs_escalation` is true, show `install_commands` or `install_command` to the user and get approval before running package-manager commands.
   When a repair artifact or approved root package install is needed, run:

   ```bash
   bin/governance env --repair --target <target> --json
   ```

2. Run initialization preflight:

   ```bash
   bin/governance init --check --target <target> --product <product-doc> --profile <profile> --project-name "<name>" --json
   ```

   Stop when `ok` is false. Existing generated governance files must be reviewed before using `--force`.

3. Initialize the target folder:

   ```bash
   bin/governance init --target <target> --product <product-doc> --profile <profile> --project-name "<name>"
   ```

   When `--json` is used, the success payload includes `local_commands` with target-local `make` entries plus `next_actions` with the next preflight/apply workflow commands. Both payloads include `cwd` and `argv` for direct agent execution. Follow `next_actions` instead of assuming product structuring is immediately available.

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
make verify-check
make governance-status
make check-env
make repair-env-check
```

If runtime or workflow-pack snapshot verification fails, run the refresh command from a trusted source workflow-pack checkout:

```bash
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

The target also receives `.governance/state.json`, which records phase, profile, product source, archive path, and last verification status.

## Verification

Initialization is complete only when the generated target passes:

```bash
bin/governance verify <target>
bin/governance status <target>
```

Use `bin/governance verify <target> --check --json` first when automation needs findings without updating `.governance/state.json`.

## Stop Conditions

- Target folder has existing governance files and the user did not approve overwrite.
- `init --check` returns conflicts.
- Product document path is missing or unreadable.
- The target project type is unclear and would change the top-level code layout.
