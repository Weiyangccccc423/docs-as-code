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

1. Read `references/repository-initialization-checklist.md` and use it as the rubric for target safety, environment repair, generated entry points, runtime snapshot integrity, product seed, Git readiness, baseline security, tooling consistency, and handoff readiness. When the target root contains exactly one supported product document plus an unpacked `docs-as-code-workflow-pack/`, use the standard consumer entry:

   ```bash
   ./docs-as-code-workflow-pack/bin/governance-bootstrap --check --json
   ./docs-as-code-workflow-pack/bin/governance-bootstrap --json
   ```

   The wrapper enables safe `--auto-repair-env`, uses current-directory target selection, target-directory-name project naming, and target-root-auto-discovery for the product. Check mode stays no-write; write mode applies only no-approval, non-manual environment repairs. Inspect `input_resolution`; stop on ambiguous product selection, and pass `--profile`, `--project-name`, or `--product` only when reviewed explicit values are available. Never use the workflow-pack root or its descendants as targets; nesting the pack inside the target is valid.

   When branch, repository-local author, and optional origin have been reviewed, include local Git initialization in the same existing-folder check/apply sequence:

   ```bash
   ./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --check --json
   ./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --json
   ```

   Omit `--git-origin` when no remote is approved. The target directory must already exist. Require `repository_git_check_ok: true` with no `.git` write in check mode, then `repository_git_initialized: true` in apply mode. This creates no commit and never authenticates or pushes.

   TXT input is converted automatically with the Python standard library and stops at `product_conversion_status: pending_review`. DOCX/HTML first elevate only `pandoc` through `--require-tool pandoc`, then run bounded no-shell conversion. Require `product_conversion_applied: true`, `docs/product/core/source/conversion-report.json`, and a guarded `product-mark-ready` handoff. PDF remains a manual extraction stop. No non-Markdown path may advance product structuring before source review closes `U-001`.

2. From the trusted workflow-pack checkout, inventory authority skills and build the offline repair plan:

   ```bash
   python3 scripts/authority_skills.py --repair --check --json
   ```

   Stop on an invalid or routing-misaligned `manifest`. Inspect `status_counts`, `provenance_issue_skills`, and `repair_plan`. Source-unregistered or unmanaged skills require source and license review; do not guess install locations. After explicit approval, install all eligible locked missing skills with:

   ```bash
   python3 scripts/authority_skills.py --repair --apply --approve-installs --strict-provenance --json
   ```

   Apply mode refuses drifted, duplicated, unmanaged, source-unregistered, or unavailable-installer actions. It stops after the first installer or digest failure; inspect `repair_execution.partial_write_observed` and `manual_cleanup_required` before cleanup or retry. Base initialization may continue in non-strict mode, but run with `--strict-provenance` before authority-dependent design when approved locked skills are required.

3. Check environment:

   ```bash
   bin/governance env --repair --check --target <target> --json
   ```

   Stop when `ok` is false. Missing required tools block initialization; inspect `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, `repair_execution`, and `repair_decision`, then rerun after repair.
   Use `repair_decision.decision`, `repair_decision.stop_before_workflow`, `repair_decision.runnable_action_ids`, `repair_decision.approval_action_ids`, and `repair_decision.manual_action_ids` as the first branching signal, with `repair_execution.status`, `repair_execution.can_auto_apply`, `repair_execution.install_attempted`, `repair_execution.install_failed`, `repair_execution.post_repair_missing_required`, `repair_execution.post_repair_missing_recommended`, and `repair_execution.next_step` as supporting detail. Sort `repair_actions` by `sequence`; run actions with `argv` only when `approval_required` is false or approval is explicit, and present `manual-repair` actions to the user. If any `repair_commands[].approval_required` value or `needs_escalation` is true, show the structured `repair_commands` or `install_command` to the user and get approval before running package-manager commands. Treat `applied_but_unresolved` as a stop state before retrying repairs.
   Empty or uninitialized targets do not return workflow continuation commands. When the target is already initialized and governance state is readable, successful env JSON includes `local_commands` and `next_actions` for resuming from the current state.
   When a repair artifact or approved root package install is needed, run:

   ```bash
   bin/governance env --repair --target <target> --json
   ```

4. Run initialization preflight:

   ```bash
   bin/governance init --check --target <target> --profile <profile> --project-name "<name>" --json
   ```

   Stop when `ok` is false. Existing generated governance files must be reviewed before using `--force`. When `--product` is omitted, inspect `product.selection`: `auto-discovered` means exactly one root candidate was selected, `none` means the placeholder PRD path will be used, and `ambiguous` means multiple candidates were found and the agent must rerun with `--product <product-doc>` instead of guessing.

5. Initialize the target folder:

   ```bash
   bin/governance init --target <target> --profile <profile> --project-name "<name>"
   ```

   Use `--product <product-doc>` when the product document is outside the target root or when preflight reports multiple candidates.

   When `--json` is used, the success payload includes `local_commands` with target-local `make` entries plus `next_actions` with the next preflight/apply workflow commands. Both payloads include `cwd`, `argv`, `writes_state`, and `approval_required` for direct agent execution. `next_actions` also include `sequence`, `success_condition`, and either `preflight_for` or `requires_action`; run them by ascending `sequence` and run an apply action only after its `requires_action` reports `ok: true`. Follow `next_actions` instead of assuming product structuring is immediately available.

6. After governance files exist, initialize reviewed local Git metadata. Ask for the default branch, commit author name, commit author email, and optional origin URL; do not inherit or guess them from global Git configuration:

   ```bash
   bin/governance repository init <target> --default-branch <branch> --author-name "<name>" --author-email "<email>" --reviewed --check --json
   bin/governance repository init <target> --default-branch <branch> --author-name "<name>" --author-email "<email>" --reviewed --json
   ```

   Add `--origin <url>` only after the URL is reviewed. The command uses repository-local `user.name` and `user.email`, refuses a parent repository or conflicting existing metadata, and never creates a commit, authenticates, or pushes. The Git credential used for a later push determines the hosting account independently of commit authorship; verify that identity before the first explicit push.

7. Inspect generated root files:

   - `README.md`
   - `AGENTS.md`
   - `SPEC.md`
   - `CONTRIBUTING.md`
   - `GOVERNANCE.md`
   - `SECURITY.md`
   - `Makefile`
   - `bin/governance`
   - `scripts/governance_cli.py`
   - `docs/agent-workflow/project-environment.json`
   - `docs/agent-workflow/workflow-pack/manifest.json`
   - `docs/agent-workflow/workflow-pack/references/authority-skills.lock.json`

   In root `AGENTS.md`, require the `Workflow Startup` contract: read the target-local workflow overview, run `make workflow-resume`, enforce `assert_snapshot_command.argv`, read `work_package.read_order`, and follow `skill_loading_plan.steps[]`. Local workflow skills must be read from their exact path under `docs/agent-workflow/workflow-pack/skills/`; authority-routing skills must be loaded from the Agent environment or stop under `missing_policy`. Execute one selected action, run `refresh_command.argv`, then resume.

8. Inspect generated docs domains:

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

9. Verify:

   ```bash
   bin/governance verify <target>
   bin/governance status <target>
   ```

## Output

A repository skeleton with governance entry points, product core files, unresolved item registry, glossary, and domain-level docs entrances.

The target receives a local governance runtime under `bin/` and `scripts/`, a runtime hash manifest at `docs/agent-workflow/runtime-manifest.json`, a structured runtime/version/repair contract at `docs/agent-workflow/project-environment.json`, plus a workflow-pack snapshot under `docs/agent-workflow/workflow-pack/`. `core-governance` is ready immediately; keep `project-runtime` empty until stack selection supplies reviewed tools and sources. After initialization, use target-local commands when working inside the generated repository:

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
- Default branch, repository-local author, or optional origin has not been reviewed.
- The target resolves inside a parent Git repository, or existing local Git metadata conflicts with reviewed values.
- Authority skill lock validation fails, or strict provenance is required and any skill is missing, drifted, unmanaged, or source-unregistered.
