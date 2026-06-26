# AGENTS.md

> Scope: this workflow-pack repository.

## Purpose

This repository is a reusable package for creating governed docs-as-code project workspaces. Do not treat it as a generated target project.

## Editing Rules

- Keep `skills/` concise and trigger-focused.
- Put deterministic behavior in `scripts/`.
- Put generated repository examples in `templates/`.
- Put phase procedures in `workflows/`.
- Add or update tests before changing script behavior.

## Required Reading

For workflow changes:

1. `workflows/00-overview.md`
2. The target phase file under `workflows/`
3. Any affected skill under `skills/`
4. Relevant script tests under `tests/`

## Verification

Run:

```bash
make test
make verify-pack
```

Before claiming completion, report the verification commands and results.

## Baseline Rule

This workflow pack should be kept in Git. Commit after each coherent change to scripts, skills, workflows, or templates so future workflow behavior is traceable.
