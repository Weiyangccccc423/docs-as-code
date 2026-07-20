---
name: initializing-governance-repo
description: Use when creating project governance in an empty or near-empty repository before product design or implementation starts.
---

# Initializing Governance Repo

Create the minimum structure needed for reliable docs-as-code work.

## Steps

1. Read `references/repository-initialization-checklist.md`. For a target containing one product document and `docs-as-code-workflow-pack/`, run `./docs-as-code-workflow-pack/bin/governance-bootstrap --check --json` and then `./docs-as-code-workflow-pack/bin/governance-bootstrap --json`. The wrapper enables safe `--auto-repair-env`; check mode stays no-write and write mode applies only no-approval, non-manual repairs. Inspect `input_resolution`: the defaults are current-directory target selection, target-directory-name project naming, target-root-auto-discovery for exactly one product, and profile `unknown`. Stop on product ambiguity or when the target resolves to the workflow-pack root or its descendants; nesting the pack inside the target remains valid. Use explicit flags only from reviewed inputs.

   If reviewed local Git initialization is part of bootstrap, the existing target folder must be used. Run `./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --check --json` before `./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --json`; omit `--git-origin` when no remote is approved. Require `repository_git_check_ok: true`, then `repository_git_initialized: true`. Do not commit, authenticate, or push in this phase.

   For TXT, require built-in conversion evidence and `product_conversion_status: pending_review`. For DOCX/HTML, require the operation-scoped `--require-tool pandoc` preflight; for PDF, require `--require-tool pdftotext`. Both external paths use bounded no-shell conversion. Require `conversion-report.json` and the guarded `product-mark-ready` handoff; compare PDF layout-sensitive meaning against the archive, never treat conversion as source review, and never advance while `U-001` remains open.

2. From the workflow-pack checkout, run `python3 scripts/authority_skills.py --repair --check --json`. Stop on an invalid lock. Inspect `status_counts` and `repair_plan`; never guess a source for `source-unregistered` or `unmanaged` skills. After explicit approval, run `python3 scripts/authority_skills.py --repair --apply --approve-installs --strict-provenance --json`. Apply only installs locked `missing` skills, stops after the first command or digest failure, and never auto-replaces drifted or ambiguous installations. Inspect `repair_execution.partial_write_observed` and `manual_cleanup_required` before retrying. Use `--strict-provenance` before authority-dependent work when approved locked skills are required.

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

   Inspect generated root `AGENTS.md` and require its `Workflow Startup` section. It must route the next Agent through `make workflow-resume`, `assert_snapshot_command.argv`, `work_package.read_order`, and ordered `skill_loading_plan.steps[]`. Load local workflow skills from exact paths under `docs/agent-workflow/workflow-pack/skills/`; load authority-routing skills from the Agent environment and stop when `missing_policy` requires it. Run `refresh_command.argv` after exactly one selected action.

6. Ask for reviewed Git defaults, then initialize repository-local metadata without creating a commit or pushing:

   ```bash
   bin/governance repository init <target> --default-branch <branch> --author-name "<name>" --author-email "<email>" --reviewed --check --json
   bin/governance repository init <target> --default-branch <branch> --author-name "<name>" --author-email "<email>" --reviewed --json
   ```

   Add `--origin <url>` only when reviewed. Stop on parent-repository detection or metadata conflicts. Do not treat commit author name/email as proof of the credential or hosting account that a later push will use.

7. Verify:

   ```bash
   bin/governance verify <target>
   ```

8. Check the first downstream phase gate:

   ```bash
   bin/governance advance product-structuring <target> --check --json
   bin/governance advance product-structuring <target> --json
   ```

   Stop on `ok: false` and repair by `requirements[].code`.

9. When working inside the initialized target, switch to the copied target-local runtime:

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
   make implementation-run-check
   make check-env
   make repair-env-check
   make project-env-plan
   ```

10. If generated runtime or workflow-pack snapshot integrity fails, repair it from a trusted source workflow-pack checkout:

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
- Default branch, repository-local author, or optional origin has not been reviewed.
- The target resolves inside a parent Git repository, or existing local Git metadata conflicts with reviewed values.
- Authority skill lock validation fails, or required strict provenance is not current.
