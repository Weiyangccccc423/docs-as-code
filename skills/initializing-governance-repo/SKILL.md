---
name: initializing-governance-repo
description: Use when creating project governance in an empty or near-empty repository before product design or implementation starts.
---

# Initializing Governance Repo

Create the minimum structure needed for reliable docs-as-code work.

## Steps

1. Read `references/repository-initialization-checklist.md`.

2. From the workflow-pack checkout, run `python3 scripts/authority_skills.py --repair --check --json`. Stop on an invalid lock. Inspect `status_counts` and `repair_plan`; never guess a source for `source-unregistered` or `unmanaged` skills. Use `--strict-provenance` before authority-dependent work when approved locked skills are required.

3. Run environment check:

   ```bash
   bin/governance env --repair --check --target <target> --json
   ```

   Stop on `ok: false`. Inspect `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, `repair_execution`, and `repair_decision` before running `bin/governance env --repair --target <target> --json`. Use `repair_decision.decision`, `repair_decision.stop_before_workflow`, `repair_decision.runnable_action_ids`, `repair_decision.approval_action_ids`, and `repair_decision.manual_action_ids` for the first branch, then use `repair_execution.status`, `repair_execution.can_auto_apply`, `repair_execution.install_attempted`, `repair_execution.install_failed`, `repair_execution.post_repair_missing_required`, `repair_execution.post_repair_missing_recommended`, and `repair_execution.next_step` for detail. Sort `repair_actions` by `sequence`; run actions with `argv` only when `approval_required` is false or approval is explicit, and present `manual-repair` actions to the user. Treat `applied_but_unresolved` as a stop state before retrying repairs. If the target is already initialized and env JSON returns `local_commands` or `next_actions`, use them to resume instead of guessing.

4. Run preflight without writing files:

   ```bash
   bin/governance init --check --target <target> --json
   ```

   If the product document is outside the target root, or `product.selection` returns `ambiguous`, rerun with `--product <product-doc>`. Stop when `ok` is false. Existing generated governance files require user approval before `--force`.

5. Bootstrap the target:

   ```bash
   bin/governance init --target <target>
   ```

   For automation, use `--json` and inspect `product.selection`; `auto-discovered` means exactly one root product document was imported. Use `local_commands[].argv` from `local_commands[].cwd` for routine checks; inspect `writes_state` and `approval_required` before running returned commands. Follow `next_actions`: sort by `sequence`, run each action's `argv` from its reported `cwd`, use `preflight_for` and `requires_action` to pair commands, and run the matching state-writing `apply` command only after the referenced preflight reports the declared `success_condition` of `ok:true`.

6. Verify:

   ```bash
   bin/governance verify <target>
   ```

7. Check the first downstream phase gate:

   ```bash
   bin/governance advance product-structuring <target> --check --json
   bin/governance advance product-structuring <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

8. When working inside the initialized target, switch to the copied target-local runtime:

   ```bash
   bin/governance verify .
   make verify-governance
   make verify-check
   make governance-status
   make workflow-plan
   make work-package
   make workflow-resume
   make product-plan
   make design-plan
   make implementation-plan
   make check-env
   make repair-env-check
   make project-env-plan
   ```

9. If generated runtime or workflow-pack snapshot integrity fails, repair it from a trusted source workflow-pack checkout:

   ```bash
   bin/governance runtime refresh <target> --check --json
   bin/governance runtime refresh <target> --json
   ```

## Required Output

- root `README.md`, `AGENTS.md`, `SPEC.md`
- root `bin/governance` and `scripts/governance_cli.py`
- `docs/agent-workflow/project-environment.json` with `core-governance` and an unconfigured `project-runtime`
- `docs/agent-workflow/workflow-pack/manifest.json`
- `docs/agent-workflow/workflow-pack/references/authority-skills.lock.json`
- local workflow-pack snapshot under `docs/agent-workflow/workflow-pack/`
- `docs/README.md`, `docs/AGENTS.md`
- `docs/product/core/PRD.md`
- `docs/unresolved.md`
- `docs/glossary.md`
- domain `README.md` and `AGENTS.md` for non-empty docs directories

## Stop Conditions

- Existing files would be overwritten without user approval.
- Product document cannot be read.
- Product document discovery is ambiguous and no explicit `--product` was selected.
- Project type is unclear and affects code-directory choices.
- Authority skill lock validation fails, or required strict provenance is not current.
