# Release Readiness Checklist

Use this checklist before tagging, exporting, or handing off this source workflow pack as a trusted baseline.

## Source Pack Verification

- Run `make verify-pack`.
- Run `python3 scripts/verify_pack.py --json` and require `ok: true` with no `findings`.
- Confirm source-pack verification covers required files, runtime Python syntax, command surfaces, workflow action schemas, phase-skill alignment, reference routing, template guardrails, local Markdown links, and workflow-pack snapshot coverage.

## Dry Run Validation

- Run `make dry-run`.
- Run `python3 scripts/dry_run_workflow.py --json` and require `ok: true`.
- Confirm the payload reports `workflow: fresh-target-governance-dry-run`, reaches `final_phase: design-derivation`, produces API/backend/frontend/test/implementation-planning/ADR authoring queues, and keeps the implementation gate blocked until source-backed design placeholders are replaced.

## Export Artifact Integrity

- Run `make package`.
- Run `python3 scripts/export_workflow_pack.py --check --json` before writing a package when inspecting changes.
- Run `python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json` for the release artifact.
- Confirm the export writes `pack-manifest.json` with SHA-256 evidence, verifies the exported directory with `verify_pack`, and reports archive SHA-256 and size for transfer evidence.

## Environment and Tooling

- Run `python3 scripts/check_env.py --json`.
- Require `ok: true` and `missing_required: []`.
- Treat missing recommended tools as a release note or environment follow-up unless `--strict` is part of the target release policy.

## Release Evidence

- Run `python3 scripts/release_readiness.py --json`.
- Require `ok: true`, `release_ready: true`, and no skipped criteria.
- Record the command output or summarize the criteria results in the release notes, handoff, or commit message.

## Stop Conditions

- Do not tag or distribute a release artifact when `release_ready` is false.
- Do not treat `--skip-tests` output as release evidence.
- Do not ignore package export verification failures even when the source checkout itself verifies cleanly.
- Do not hand off an archive without its `pack-manifest.json`, archive SHA-256, and verification result.
