# Phase 01: Empty Repository Initialization

## Input

- Empty or near-empty target folder
- Optional product document path. If omitted, `init` auto-discovers exactly one supported product document in the target folder root.
- This workflow pack

## Skills

Load:

- `using-governance-workflow`
- `initializing-governance-repo`
- `verifying-governance-docs`

## Procedure

1. Read `references/repository-initialization-checklist.md` and use it as the rubric for target safety, environment repair, generated entry points, runtime snapshot integrity, product seed, Git readiness, baseline security, tooling consistency, and handoff readiness.

2. Check environment:

   ```bash
   bin/governance env --repair --check --target <target> --json
   ```

   Stop when `ok` is false. Missing required tools block initialization; inspect `would_repair`, `install_commands`, `repair_commands`, `manual_repairs`, `needs_escalation`, and `repair_execution`, then rerun after repair.
   Use `repair_execution.status`, `repair_execution.can_auto_apply`, and `repair_execution.next_step` for branching. If any `repair_commands[].approval_required` value or `needs_escalation` is true, show the structured `repair_commands` or `install_command` to the user and get approval before running package-manager commands.
   Empty or uninitialized targets do not return workflow continuation commands. When the target is already initialized and governance state is readable, successful env JSON includes `local_commands` and `next_actions` for resuming from the current state.
   When a repair artifact or approved root package install is needed, run:

   ```bash
   bin/governance env --repair --target <target> --json
   ```

3. Run initialization preflight:

   ```bash
   bin/governance init --check --target <target> --profile <profile> --project-name "<name>" --json
   ```

   Stop when `ok` is false. Existing generated governance files must be reviewed before using `--force`. When `--product` is omitted, inspect `product.selection`: `auto-discovered` means exactly one root candidate was selected, `none` means the placeholder PRD path will be used, and `ambiguous` means multiple candidates were found and the agent must rerun with `--product <product-doc>` instead of guessing.

4. Initialize the target folder:

   ```bash
   bin/governance init --target <target> --profile <profile> --project-name "<name>"
   ```

   Use `--product <product-doc>` when the product document is outside the target root or when preflight reports multiple candidates.

   When `--json` is used, the success payload includes `local_commands` with target-local `make` entries plus `next_actions` with the next preflight/apply workflow commands. Both payloads include `cwd`, `argv`, `writes_state`, and `approval_required` for direct agent execution. `next_actions` also include `sequence`, `success_condition`, and either `preflight_for` or `requires_action`; run them by ascending `sequence` and run an apply action only after its `requires_action` reports `ok: true`. Follow `next_actions` instead of assuming product structuring is immediately available.

5. Inspect generated root files:

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

6. Inspect generated docs domains:

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

7. Verify:

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

Target safety, environment repair, generated entry points, runtime snapshot integrity, product seed, Git readiness, baseline security, tooling consistency, and handoff readiness must satisfy `references/repository-initialization-checklist.md`.

## Stop Conditions

- Target folder has existing governance files and the user did not approve overwrite.
- `init --check` returns conflicts.
- Product document path is missing or unreadable.
- Product document discovery returns multiple candidates and the user has not selected one with `--product`.
- The target project type is unclear and would change the top-level code layout.
