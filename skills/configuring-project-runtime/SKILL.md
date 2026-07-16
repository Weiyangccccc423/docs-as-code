---
name: configuring-project-runtime
description: Use when a reviewed architecture or stack decision must be converted into project-runtime tool, version, probe, and repair contracts before project commands run.
---

# Configuring Project Runtime

Register explicit runtime requirements without guessing a technology stack or installation command.

Read `references/project-environment-contract.md` before changing `docs/agent-workflow/project-environment.json`.

## Procedure

1. Inspect the current inventory:

   ```bash
   bin/governance project-env plan <target> --json
   ```

2. Read the reported `read_order`, the accepted stack ADR or architecture source, and the commands that will use `project-runtime`.
3. Load `tech-stack-evaluator` when alternatives remain and `senior-architect` before accepting a cross-module runtime choice. Load the owning backend, frontend, data, or DevOps authority skill when its tool is in scope.
4. Record one tool only after the source proves its executable, safe version probe, numeric version range, official or repository source, and local Markdown review evidence.
5. Run `project-env register --reviewed --check --json` with every explicit field. Inspect `errors`, `action`, `would_update`, `tool`, and `environment`.
6. Apply the same command without `--check` only after review. Use `--replace` only when an existing tool ID intentionally changes.
7. Run:

   ```bash
   bin/governance project-env plan <target> --json
   bin/governance verify <target> --check --json
   ```

## Rules

- Keep governance commands in `core-governance`; register only project implementation tools in `project-runtime`.
- Use only the allowlisted read-only version probe styles returned by `project-env register --help`.
- Treat registration as repository configuration, not permission to install or upgrade software.
- Do not infer package names, package-manager commands, version ranges, prefixes, or repair sources.
- Keep source review evidence repository-local and Markdown.

## Stop Conditions

- No accepted local architecture or ADR evidence identifies the runtime choice.
- Required authority skills cannot be loaded.
- The executable, version requirement, probe prefix, or repair source is uncertain.
- Registration conflicts with an existing tool and the replacement has not been explicitly reviewed.
- The source or review-evidence path is missing, external to the repository, or a symlink.
