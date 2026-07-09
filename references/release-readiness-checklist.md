# Release Readiness Checklist

Use this checklist before tagging, exporting, or handing off this source workflow pack as a trusted baseline.

## Source Pack Verification

- Run `make verify-pack`.
- Run `python3 scripts/verify_pack.py --json` and require `ok: true` with no `findings`.
- Confirm source-pack verification covers required files, runtime Python syntax, command surfaces, workflow action schemas, phase-skill alignment, reference routing, template guardrails, local Markdown links, and workflow-pack snapshot coverage.

## Dry Run Validation

- Run `make dry-run`.
- Run `make dry-run-golden`.
- Run `python3 scripts/dry_run_workflow.py --json` and require `ok: true`.
- Run `python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json` and require `ok: true`.
- Confirm the payload reports `workflow: fresh-target-governance-dry-run`, reaches `final_phase: implementation`, produces architecture/API/backend/data-model/frontend/test/implementation-planning/ADR authoring queues, reports `target_local_make_coverage.missing_step_ids: []`, keeps the implementation gate blocked until source-backed design placeholders are replaced, claims one Ready task as `In Progress`, reports implementation closeout blocked without evidence, ready after passing local evidence is linked, applied through deterministic status updates, followed by complete implementation/workflow plans, and preserved after runtime refresh.
- Confirm the multi-acceptance fixture reports `acceptance_id_count: 4`, `api_candidate_count: 4`, and four authoring tasks per architecture/API/backend/data-model/frontend/test/planning/ADR queue.

## Export Artifact Integrity

- Run `make package`.
- Run `make artifact-smoke`.
- Run `python3 scripts/export_workflow_pack.py --check --json` before writing a package when inspecting changes.
- Run `python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json` for the release artifact.
- Run `python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json` for explicit manifest verification of the exported directory.
- Run `python3 scripts/smoke_workflow_pack_artifact.py --json` to unpack the tar.gz artifact and run manifest verification, `verify_pack`, plus dry-run checks from the unpacked artifact.
- Confirm the export writes `pack-manifest.json` with SHA-256 evidence, verifies the exported directory with `verify_pack`, and reports archive SHA-256 and size for transfer evidence.
- Confirm manifest verification reports `ok: true` with no `findings`, including no hash, size, executable-bit, duplicate-path, invalid-path, missing-file, or unmanifested-file drift.
- Confirm the unpacked artifact reports `ok: true`, has `pack-manifest.json`, reaches `final_phase: implementation` during its dry run, and reports `target_local_make_coverage.missing_step_ids: []`.

## Environment and Tooling

- Run `python3 scripts/check_env.py --json`.
- Require `ok: true` and `missing_required: []`.
- Require `repair_decision.decision: continue_workflow` and `repair_decision.stop_before_workflow: false`.
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
- Do not hand off an archive that has not passed artifact smoke validation from an unpacked artifact.
