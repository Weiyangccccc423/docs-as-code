# Release Readiness Checklist

Use this checklist before tagging, exporting, or handing off this source workflow pack as a trusted baseline.

## Source Pack Verification

- Treat local `make ci` as the authoritative source-pack baseline. Confirm `.github/workflows/ci.yml` exposes only `workflow_dispatch` with no `push` or `pull_request` trigger, pins Python 3.10 and Node 22, then runs `make test`, `make stack-acceptance`, `python3 scripts/verify_pack.py --json`, and `python3 scripts/check_env.py --json` only when a reviewed remote-environment run is explicitly required.
- Run `make test` and `make verify-pack`, or run their combined local `make ci` gate. `make test` automatically bounds isolated module subprocesses by CPU count, Linux available memory at 768 MiB per worker, and an eight-worker ceiling; use an explicit `--workers` override only after reviewing local resource pressure. Use `make test-serial` only to diagnose ordering-sensitive failures, not as a second release gate.
- Confirm `make release-check` reuses `python3 scripts/run_tests.py` for its unit-test criterion instead of starting a second serial `unittest` discovery path.
- Run `make install-smoke-check` to probe `uv` without writes, then run `make install-smoke` to build exactly one wheel offline, install it in a disposable environment, and verify installed and generated-target `dac` commands. Require complete `init_check_read_only`, `status_from_nested`, `directory_after_command`, `target_help_status`, and `target_status_from_nested` evidence. Missing `uv`, unsafe output, timeout, malformed JSON, or incomplete CLI evidence blocks release readiness.
- Confirm release, dry-run, and artifact-smoke steps use `scripts/source_process.py`: release steps have a 60-minute outer timeout, nested dry-run/artifact-smoke steps have 15-minute timeouts, each output stream is limited to 16 MiB, sensitive output is redacted, and POSIX timeout terminates the full process group. Require structured command, duration, stdout/stderr, truncation, and redaction evidence. Successful parsed JSON step output above 64 KiB must set `stdout_compacted: true`, retain `stdout_size_bytes` and `stdout_sha256`, and omit the duplicated raw stdout; failed steps must retain their available raw output for diagnosis. Any `started: false`, `timed_out: true`, `output_safe: false`, or return-code mismatch blocks release readiness; never substitute an unbounded retry.
- Run `python3 scripts/verify_pack.py --json` and require `ok: true` with no `findings`.
- Confirm top-level `VERSION` is the reviewed strict SemVer release identity under `references/versioning-policy.md`; do not infer it from Git tags or generated manifests.
- Confirm `CHANGELOG.md` contains a dated current release entry that exactly matches `VERSION`, uses a recognized Keep a Changelog category with a concrete bullet, and states consumer-visible upgrade impact.
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
- Confirm the payload reports `workflow: fresh-target-governance-dry-run`, reaches `final_phase: implementation`, records reviewed source-bound optional chapter decisions with `product_dispositions.unresolved_decision_count: 0`, proves the product work package routes to the phase action, produces architecture/API/backend/data-model/frontend/test/implementation-planning/ADR authoring queues, and reports complete source/evidence/authority-bound `design_reviews` coverage with zero missing or stale records. Require `authority_report_count` and `decision_report_count` to equal the positive `expected_count`, so every active review has one structured authority report with exact decision coverage. Also require current `api_review`, `threat_review`, `reliability_review`, and `migration_review` evidence after runtime refresh, a matching check/apply `runtime_refresh.version_transition` with `classification: same`, `approval_required: false`, and `can_apply: true`, plus `target_local_make_coverage.missing_step_ids: []`. Require `implementation_run.ready_check`, `snapshot_guarded_start`, `start_applied`, `verification_ready`, `executed_all_required`, `review_required_after_execution`, `reviewed_closeout_ready`, `snapshot_guarded_closeout`, `closeout_applied`, and `complete` all true, with positive equal `required_count` and `passed_count`; also require closeout blocked without evidence, ready after passing local evidence, `implementation_review.evidence_current`, `code_review_evidence_current`, complete implementation/workflow plans, and completion preserved after runtime refresh.
- Require the explicit `implementation closeout blocked without evidence` branch before accepting runner completion.
- Confirm the multi-acceptance fixture reports `acceptance_id_count: 4`, `api_candidate_count: 4`, and four authoring tasks per architecture/API/backend/data-model/frontend/test/planning/ADR queue.

## Export Artifact Integrity

- Run `make package`.
- Run `make artifact-smoke`.
- Run `python3 scripts/export_workflow_pack.py --check --json` before writing a package when inspecting changes.
- Run `python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json` for the release artifact.
- Run `python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json` for explicit manifest verification of the exported directory.
- Run `python3 scripts/smoke_workflow_pack_artifact.py --json` for a self-contained temporary export smoke test.
- Run `python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json` to unpack the exact release tar.gz artifact and run manifest verification, `verify_pack`, one-command Markdown initialization, TXT product conversion with `consumer_bootstrap_product_conversion.ok: true`, fresh-target initialization, target-local command checks, consumer bootstrap with `--auto-repair-env --workflow-preset product-structure`, `--auto-repair-env --workflow-preset design-scaffold`, `--auto-repair-env --workflow-preset design-routing`, and `--auto-repair-env --workflow-preset implementation-routing`, plus dry-run checks that invoke `--resume --workflow-preset implementation-routing` from the unpacked artifact after design completion.
- Confirm the export writes `pack-manifest.json` with SHA-256 evidence, verifies the exported directory with `verify_pack`, and reports archive SHA-256 and size for transfer evidence.
- Require export and manifest-verification payload `pack_version` to equal exported `VERSION`; require every smoke target's snapshot, runtime manifest, snapshot manifest, and governance state to retain that exact value.
- Confirm repeated exports from the same source checkout produce identical `manifest_sha256`, `archive_sha256`, and archive size.
- Confirm manifest verification reports `ok: true` with no `findings`, including no hash, size, executable-bit, duplicate-path, invalid-path, missing-file, or unmanifested-file drift.
- Confirm the unpacked artifact reports `ok: true`, `archive_source: provided-archive`, has `pack-manifest.json`, reports `consumer_bootstrap_one_command.ok: true`, `consumer_bootstrap_one_command.repository_git_initialized: true`, `consumer_bootstrap_product_conversion.ok: true`, and `fresh_target_init.ok: true`. Require the one-command Git result to prove the reviewed branch and repository-local author, `repository_git_has_commits: false`, and no commit or push action. Prove target-local verify/status/workflow-plan commands, and require `consumer_resume_implementation_handoff.ok: true` with `state_write_observed`, `routing_ok`, `route_ready`, and `runner_contract_valid` all true for a design-to-implementation transition and snapshot-guarded Ready task. Require `stack_acceptance.ok: true` with Python and Node status `passed`, and preserve a complete `implementation_run` summary with snapshot-guarded start/closeout and all required commands passed. Also require current product dispositions, design reviews whose `authority_report_count` and `decision_report_count` equal `expected_count`, API/threat/reliability/migration evidence, all fresh consumer bootstrap preset summaries and their blocker/skip routing, authority/environment checks, `final_phase: implementation`, and `target_local_make_coverage.missing_step_ids: []`.
- Preserve explicit artifact fields `design_reviews.ok: true` and `consumer_bootstrap_implementation_routing.ok: true` in release evidence.
- Preserve consumer summaries `consumer_bootstrap_product_structure.ok: true`, `consumer_bootstrap_design_scaffold.ok: true`, `consumer_bootstrap_design_routing.ok: true`, and `consumer_bootstrap_implementation_routing.ok: true`; each must expose `authority_skill_inventory` and `env_auto_repair` evidence.
- For blocked implementation routing, require `readiness_blocker_codes`, `readiness_next_repair_action`, `advance_preview_not_ready`, `readiness_preview_not_ready`, `start_preview_not_ready`, `start_apply_not_applied`, and `closeout_preview_not_ready` instead of treating skipped writes as success.
- For an implementation target waiting on review, require `implementation_review_ready: true`, preview `review_ready: true`, top-level propagation of the exact read-only `implementation review` action, and `implementation_continuation_ready: false`; reject any malformed task, cwd, argv, write, or approval field.

## Environment and Tooling

- Run `python3 scripts/check_env.py --json`.
- Require `ok: true` and `missing_required: []`.
- Require `repair_decision.decision: continue_workflow` and `repair_decision.stop_before_workflow: false`.
- Treat missing recommended tools as a release note or environment follow-up unless `--strict` is part of the target release policy.

## Release Evidence

- Run `python3 scripts/release_readiness.py --json`.
- Require `ok: true`, `release_ready: true`, and no skipped criteria.
- Confirm the `installable-cli-smoke` criterion passes with offline wheel build/install evidence and the installed version matches the reviewed release.
- Confirm the `authority-skill-inventory` criterion passes in non-strict mode and records lock validation, status counts, `required_skill_count`, `available_skill_count`, `missing_skill_count`, and `missing_policy`.
- Record the command output or summarize the criteria results in the release notes, handoff, or commit message.

## Stop Conditions

- Do not tag or distribute a release artifact when `release_ready` is false.
- Do not treat `--skip-tests` output as release evidence.
- Do not ignore package export verification failures even when the source checkout itself verifies cleanly.
- Do not hand off an archive without its `pack-manifest.json`, archive SHA-256, and verification result.
- Do not hand off an archive that has not passed artifact smoke validation from an unpacked artifact.
- Do not accept source workflow evidence with `output_safe: false`; truncated or redacted output is incomplete evidence even when the command return code matches.
