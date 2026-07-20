---
name: configuring-project-runtime
description: Use when a reviewed architecture or stack decision must be converted into project-runtime tool, version, probe, and repair contracts before project commands run.
---

# Configuring Project Runtime

Register and repair explicit runtime requirements without guessing a technology stack or installation command.

Read `references/project-environment-contract.md` before changing `docs/agent-workflow/project-environment.json`.

## Procedure

1. Inspect the current inventory:

   ```bash
   bin/governance project-env plan <target> --json
   ```

2. Inspect `coverage_status`, `configuration_complete`, `required_commands`, `command_coverage`, `missing_command_registrations`, `tool_readiness`, and the reported `read_order`. Read the accepted stack ADR or architecture source and every command that uses `project-runtime`.
3. Load `tech-stack-evaluator` when alternatives remain and `senior-architect` before accepting a cross-module runtime choice. Load the owning backend, frontend, data, or DevOps authority skill when its tool is in scope.
4. Record one tool only after the source proves its executable, safe version probe, numeric version range, official or repository source, local Markdown review evidence, and either manual repair policy or exact reviewed repair argv.
5. Run `project-env register --reviewed --check --json` with every explicit field. Inspect `errors`, `action`, `would_update`, `tool`, and `environment`.
6. Apply the same command without `--check` only after review. Use `--replace` only when an existing tool ID intentionally changes.
7. When a registered `reviewed-command` tool is unavailable, preview it before requesting approval:

   ```bash
   bin/governance project-env repair <target> --tool-id <tool-id> --check --json
   ```

   Inspect `repair_action`, `apply_command`, `readiness_before`, and `stop_before_workflow`. Run the approval-required apply argv only after explicit authorization. Require `action: repaired`, `environment_ready: true`, and completed evidence; command return code zero alone is insufficient.
8. Run:

   ```bash
   bin/governance project-env plan <target> --json
   bin/governance verify <target> --check --json
   ```

   Require `configuration_complete: true`. The design-phase `project-runtime` queue and `project-runtime-configuration` work package remain active otherwise, and implementation gate requirement `project_runtime_ready` must fail.

## Rules

- Keep governance commands in `core-governance`; register only project implementation tools in `project-runtime`.
- Use only the allowlisted read-only version probe styles returned by `project-env register --help`.
- Treat registration as repository configuration, not permission to install or upgrade software.
- Treat repair preview as planning, not permission to execute; every `reviewed-command` apply requires explicit approval.
- Never encode shell wrappers, privilege wrappers, inline interpreter code, placeholders, or secrets in repair argv.
- Investigate pending `.governance/project-environment-repairs.json` records before continuing.
- Do not infer package names, package-manager commands, version ranges, prefixes, or repair sources.
- Keep source review evidence repository-local and Markdown.
- Treat `command_contract_invalid`, `repair_evidence_pending`, `registration_required`, and `repair_required` as blocking `coverage_status` values. `not_required` is valid only when no command uses `project-runtime`; `ready` requires every declared command and registered tool probe to be ready.

## Stop Conditions

- No accepted local architecture or ADR evidence identifies the runtime choice.
- Required authority skills cannot be loaded.
- The executable, version requirement, probe prefix, or repair source is uncertain.
- The exact repair argv, cwd, write scope, or approval is uncertain.
- Registration conflicts with an existing tool and the replacement has not been explicitly reviewed.
- The source or review-evidence path is missing, external to the repository, or a symlink.
- `configuration_complete` is false or implementation gate requirement `project_runtime_ready` does not pass.
