# Release Readiness Checklist

Use this checklist before tagging, exporting, or handing off this source workflow pack as a trusted baseline.

## Source Pack Verification

- Confirm `.github/workflows/ci.yml` pins Python 3.10 and Node 22, then runs the source-pack CI baseline: `make test`, `make stack-acceptance`, `python3 scripts/verify_pack.py --json`, and `python3 scripts/check_env.py --json`.
- Run `make test` and `make verify-pack`, or run their combined `make ci` gate.
- Run `python3 scripts/verify_pack.py --json` and require `ok: true` with no `findings`.
- Run `make authority-skills` or `python3 scripts/authority_skills.py --json` and confirm the inventory lists the authority-routing specialist skills required by design and implementation routing.
- Run `python3 scripts/authority_skills.py --repair --check --json`; require a valid, routing-aligned `references/authority-skills.lock.json`, `writes_state: false`, and no guessed argv for source-unregistered skills.
- Run `python3 scripts/authority_skills.py --strict --json` only when the current release environment is expected to provide all agent-environment specialist skills; otherwise record missing skills as environment readiness notes, not source-pack failures.
- Run `python3 scripts/authority_skills.py --strict-provenance --json` only when release policy requires every specialist skill to have approved immutable source and matching integrity evidence; acknowledged unregistered entries remain visible provenance debt in the portable baseline.
- Confirm source-pack verification covers required files, runtime Python syntax, command surfaces, workflow action schemas, phase-skill alignment, reference routing, template guardrails, local Markdown links, and workflow-pack snapshot coverage.

## Dry Run Validation

- Run `make dry-run`.
- Run `make dry-run-golden`.
- Run `python3 scripts/dry_run_workflow.py --json` and require `ok: true`.
- Run `python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json` and require `ok: true`.
- Run `make stack-acceptance` or `python3 scripts/stack_acceptance.py --json`; require real dependency-free Python and Node stack status `passed`.
- Run `python3 scripts/stack_acceptance.py --strict-rust --json` only when Cargo is required in the release environment. Otherwise require missing Rust to report reviewed manual repair routing instead of a silent skip.
- Confirm the payload reports `workflow: fresh-target-governance-dry-run`, reaches `final_phase: implementation`, records reviewed source-bound optional chapter decisions with `product_dispositions.unresolved_decision_count: 0`, proves the product work package routes to the phase action, produces architecture/API/backend/data-model/frontend/test/implementation-planning/ADR authoring queues, reports complete source/evidence/authority-bound `design_reviews` coverage with zero missing or stale records, reports current `api_review`, `threat_review`, `reliability_review`, and `migration_review` evidence after runtime refresh, reports `target_local_make_coverage.missing_step_ids: []`, keeps the implementation gate blocked until source-backed design placeholders and reviews are complete, claims one Ready task as `In Progress`, reports implementation closeout blocked without evidence, ready after passing local evidence is linked, applied through deterministic status updates, followed by complete implementation/workflow plans, and preserved after runtime refresh.
- Confirm the multi-acceptance fixture reports `acceptance_id_count: 4`, `api_candidate_count: 4`, and four authoring tasks per architecture/API/backend/data-model/frontend/test/planning/ADR queue.

## Export Artifact Integrity

- Run `make package`.
- Run `make artifact-smoke`.
- Run `python3 scripts/export_workflow_pack.py --check --json` before writing a package when inspecting changes.
- Run `python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json` for the release artifact.
- Run `python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json` for explicit manifest verification of the exported directory.
- Run `python3 scripts/smoke_workflow_pack_artifact.py --json` for a self-contained temporary export smoke test.
- Run `python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json` to unpack the exact release tar.gz artifact and run manifest verification, `verify_pack`, fresh-target initialization, target-local command checks, consumer bootstrap with `--auto-repair-env --workflow-preset product-structure`, `--auto-repair-env --workflow-preset design-scaffold`, `--auto-repair-env --workflow-preset design-routing`, and `--auto-repair-env --workflow-preset implementation-routing`, plus dry-run checks from the unpacked artifact.
- Confirm the export writes `pack-manifest.json` with SHA-256 evidence, verifies the exported directory with `verify_pack`, and reports archive SHA-256 and size for transfer evidence.
- Confirm repeated exports from the same source checkout produce identical `manifest_sha256`, `archive_sha256`, and archive size.
- Confirm manifest verification reports `ok: true` with no `findings`, including no hash, size, executable-bit, duplicate-path, invalid-path, missing-file, or unmanifested-file drift.
- Confirm the unpacked artifact reports `ok: true`, `archive_source: provided-archive`, has `pack-manifest.json`, reports `fresh_target_init.ok: true`, proves target-local verify/status/workflow-plan commands, reports `stack_acceptance.ok: true` with Python and Node status `passed`, reports `product_dispositions.ok: true` with no unresolved decision, reports `design_reviews.ok: true` with full active coverage and no stale review, reports `api_review.ok: true`, `threat_review.ok: true`, `reliability_review.ok: true`, and `migration_review.ok: true`, reports `consumer_bootstrap_product_structure.ok: true` for `product-structure`, reports `consumer_bootstrap_design_scaffold.ok: true` for `design-scaffold`, reports `consumer_bootstrap_design_routing.ok: true` for `design-routing`, reports `consumer_bootstrap_implementation_routing.ok: true` for `implementation-routing` with scaffold-placeholder blockers preserved, non-empty `readiness_blocker_codes` and `readiness_next_repair_action`, and implementation skip codes such as `advance_preview_not_ready`, `readiness_preview_not_ready`, `start_preview_not_ready`, `start_apply_not_applied`, and `closeout_preview_not_ready`, includes `authority_skill_inventory.ok: true` and `env_auto_repair.ok: true` in each consumer bootstrap summary, reaches `final_phase: implementation` during its dry run, and reports `target_local_make_coverage.missing_step_ids: []`.

## Environment and Tooling

- Run `python3 scripts/check_env.py --json`.
- Require `ok: true` and `missing_required: []`.
- Require `repair_decision.decision: continue_workflow` and `repair_decision.stop_before_workflow: false`.
- Treat missing recommended tools as a release note or environment follow-up unless `--strict` is part of the target release policy.

## Release Evidence

- Run `python3 scripts/release_readiness.py --json`.
- Require `ok: true`, `release_ready: true`, and no skipped criteria.
- Confirm the `authority-skill-inventory` criterion passes in non-strict mode and records lock validation, status counts, `required_skill_count`, `available_skill_count`, `missing_skill_count`, and `missing_policy`.
- Record the command output or summarize the criteria results in the release notes, handoff, or commit message.

## Stop Conditions

- Do not tag or distribute a release artifact when `release_ready` is false.
- Do not treat `--skip-tests` output as release evidence.
- Do not ignore package export verification failures even when the source checkout itself verifies cleanly.
- Do not hand off an archive without its `pack-manifest.json`, archive SHA-256, and verification result.
- Do not hand off an archive that has not passed artifact smoke validation from an unpacked artifact.
