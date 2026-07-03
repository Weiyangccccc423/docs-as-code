---
name: initializing-governance-repo
description: Use when creating project governance in an empty or near-empty repository before product design or implementation starts.
---

# Initializing Governance Repo

Create the minimum structure needed for reliable docs-as-code work.

## Steps

1. Run environment check:

   ```bash
   bin/governance env --repair --check --target <target> --json
   ```

   Stop on `ok: false`. Inspect `would_repair`, `install_commands`, `manual_repairs`, and `needs_escalation` before running `bin/governance env --repair --target <target> --json`. If the target is already initialized and env JSON returns `local_commands` or `next_actions`, use them to resume instead of guessing.

2. Run preflight without writing files:

   ```bash
   bin/governance init --check --target <target> --product <product-doc> --json
   ```

   Stop when `ok` is false. Existing generated governance files require user approval before `--force`.

3. Bootstrap the target:

   ```bash
   bin/governance init --target <target> --product <product-doc>
   ```

   For automation, use `--json`. Use `local_commands[].argv` from `local_commands[].cwd` for routine checks; inspect `local_commands[].writes_state` before running a command that records state. Follow `next_actions`: run each action's `argv` from its reported `cwd`; run the reported `preflight` command first, then the matching state-writing `apply` command only after `ok: true`.

4. Verify:

   ```bash
   bin/governance verify <target>
   ```

5. Check the first downstream phase gate:

   ```bash
   bin/governance advance product-structuring <target> --check --json
   bin/governance advance product-structuring <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

6. When working inside the initialized target, switch to the copied target-local runtime:

   ```bash
   bin/governance verify .
   make verify-governance
   make verify-check
   make governance-status
   make check-env
   make repair-env-check
   ```

7. If generated runtime or workflow-pack snapshot integrity fails, repair it from a trusted source workflow-pack checkout:

   ```bash
   bin/governance runtime refresh <target> --check --json
   bin/governance runtime refresh <target> --json
   ```

## Required Output

- root `README.md`, `AGENTS.md`, `SPEC.md`
- root `bin/governance` and `scripts/governance_cli.py`
- `docs/agent-workflow/workflow-pack/manifest.json`
- local workflow-pack snapshot under `docs/agent-workflow/workflow-pack/`
- `docs/README.md`, `docs/AGENTS.md`
- `docs/product/core/PRD.md`
- `docs/unresolved.md`
- `docs/glossary.md`
- domain `README.md` and `AGENTS.md` for non-empty docs directories

## Stop Conditions

- Existing files would be overwritten without user approval.
- Product document cannot be read.
- Project type is unclear and affects code-directory choices.
