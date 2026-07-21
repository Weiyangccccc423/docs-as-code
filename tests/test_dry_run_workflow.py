import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import dry_run_workflow


ROOT = Path(__file__).resolve().parents[1]
DRY_RUN = ROOT / "scripts" / "dry_run_workflow.py"


def _source_result(argv: list[str], **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "started": True,
        "argv": argv,
        "cwd": ".",
        "started_at": "2026-07-20T00:00:00.000000Z",
        "finished_at": "2026-07-20T00:00:00.010000Z",
        "duration_seconds": 0.01,
        "returncode": 0,
        "result": "pass",
        "timed_out": False,
        "timeout_seconds": 900.0,
        "stdout": "",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "output_redacted": False,
        "stdout_redaction_count": 0,
        "stderr_redaction_count": 0,
        "max_output_bytes_per_stream": 16 * 1024 * 1024,
        "output_safe": True,
    }
    result.update(overrides)
    return result


class DryRunWorkflowTest(unittest.TestCase):
    def test_run_json_compacts_large_successful_stdout_with_integrity_metadata(self) -> None:
        large_stdout = json.dumps(
            {
                "ok": True,
                "content": "x" * (dry_run_workflow.JSON_STEP_STDOUT_INLINE_BYTES + 1),
            },
            separators=(",", ":"),
        )
        steps: list[dict[str, object]] = []

        with mock.patch.object(
            dry_run_workflow,
            "run_source_command",
            return_value=_source_result(["large-command"], stdout=large_stdout),
        ):
            payload = dry_run_workflow._run_json(
                steps,
                "large_step",
                ["large-command"],
                Path("."),
            )

        self.assertTrue(payload["ok"])
        self.assertEqual("", steps[0]["stdout"])
        self.assertTrue(steps[0]["stdout_compacted"])
        self.assertEqual(len(large_stdout.encode("utf-8")), steps[0]["stdout_size_bytes"])
        self.assertEqual(
            hashlib.sha256(large_stdout.encode("utf-8")).hexdigest(),
            steps[0]["stdout_sha256"],
        )

    def test_run_json_preserves_large_stdout_when_json_parsing_fails(self) -> None:
        large_stdout = "x" * (dry_run_workflow.JSON_STEP_STDOUT_INLINE_BYTES + 1)
        steps: list[dict[str, object]] = []

        with mock.patch.object(
            dry_run_workflow,
            "run_source_command",
            return_value=_source_result(["invalid-command"], stdout=large_stdout),
        ):
            with self.assertRaises(dry_run_workflow.DryRunFailure):
                dry_run_workflow._run_json(
                    steps,
                    "invalid_step",
                    ["invalid-command"],
                    Path("."),
                )

        self.assertEqual(large_stdout, steps[0]["stdout"])
        self.assertNotIn("stdout_compacted", steps[0])

    def test_run_json_reports_timeout_as_a_structured_failure(self) -> None:
        steps: list[dict[str, object]] = []
        execution = _source_result(
            ["slow-command"],
            timed_out=True,
            returncode=-9,
            stdout='{"partial": true}',
            stderr="still running",
            timeout_seconds=0.05,
        )

        with mock.patch.object(dry_run_workflow, "run_source_command", return_value=execution):
            with self.assertRaises(dry_run_workflow.DryRunFailure) as raised:
                dry_run_workflow._run_json(
                    steps,
                    "slow_step",
                    ["slow-command"],
                    Path("."),
                    timeout_seconds=0.05,
                )

        self.assertTrue(raised.exception.step["timed_out"])
        self.assertEqual(0.05, raised.exception.step["timeout_seconds"])
        self.assertEqual('{"partial": true}', raised.exception.step["stdout"])
        self.assertEqual("still running", raised.exception.step["stderr"])

    def test_run_json_records_make_clock_skew_warnings_without_masking_other_stderr(self) -> None:
        clock_skew = (
            "make: Warning: File 'Makefile' has modification time 1.2 s in the future\n"
            "make: warning:  Clock skew detected.  Your build may be incomplete.\n"
        )
        result = _source_result(
            ["make", "check"],
            stdout='{"ok": true}\n',
            stderr=clock_skew,
        )
        steps: list[dict[str, object]] = []

        with mock.patch.object(dry_run_workflow, "run_source_command", return_value=result):
            payload = dry_run_workflow._run_json(steps, "make_check", ["make", "check"], Path("."))

        self.assertTrue(payload["ok"])
        self.assertEqual(clock_skew.splitlines(), steps[0]["warnings"])

        text_steps: list[dict[str, object]] = []
        with mock.patch.object(
            dry_run_workflow,
            "run_source_command",
            return_value=_source_result(
                ["make", "verify-governance"],
                stdout="Governance verification passed.\n",
                stderr=clock_skew,
            ),
        ):
            output = dry_run_workflow._run_text(
                text_steps,
                "make_verify_governance",
                ["make", "verify-governance"],
                Path("."),
            )

        self.assertEqual("Governance verification passed.\n", output)
        self.assertEqual(clock_skew.splitlines(), text_steps[0]["warnings"])

        for argv, stderr in (
            (["python3", "check.py"], clock_skew),
            (["make", "check"], clock_skew + "make: *** unrelated failure\n"),
        ):
            with self.subTest(argv=argv, stderr=stderr), mock.patch.object(
                dry_run_workflow,
                "run_source_command",
                return_value=_source_result(
                    argv,
                    stdout='{"ok": true}\n',
                    stderr=stderr,
                ),
            ):
                with self.assertRaises(dry_run_workflow.DryRunFailure):
                    dry_run_workflow._run_json([], "check", argv, Path("."))

    def test_run_text_blocks_unsafe_output(self) -> None:
        execution = _source_result(
            ["unsafe-command"],
            stdout="truncated output",
            stdout_truncated=True,
            output_safe=False,
        )

        with mock.patch.object(dry_run_workflow, "run_source_command", return_value=execution):
            with self.assertRaises(dry_run_workflow.DryRunFailure) as raised:
                dry_run_workflow._run_text([], "unsafe_step", ["unsafe-command"], Path("."))

        self.assertFalse(raised.exception.step["output_safe"])
        self.assertTrue(raised.exception.step["stdout_truncated"])

    def test_product_evidence_repair_schema_requires_safe_commands(self) -> None:
        task = {
            "required_evidence": [
                {"id": "chapter-file-authored", "target": "docs/product/01-background.md", "status": "placeholder_present"},
                {"id": "product-readme-indexed", "target": "docs/product/README.md", "status": "satisfied"},
            ],
            "evidence_repair_actions": [
                _repair_action(
                    kind="required-evidence-repair",
                    item_key="evidence_id",
                    item_value="chapter-file-authored",
                    target="docs/product/01-background.md",
                    status="placeholder_present",
                    refresh_argv=["bin/governance", "product", "plan", ".", "--json"],
                )
            ],
        }

        self.assertTrue(dry_run_workflow._task_evidence_repairs_cover_required_statuses(task))

        task["evidence_repair_actions"][0]["verify_command"]["writes_state"] = True
        self.assertFalse(dry_run_workflow._task_evidence_repairs_cover_required_statuses(task))

    def test_product_authoring_summary_must_match_tasks(self) -> None:
        payload = {
            "manual_authoring_tasks": [
                {
                    "open_decisions": ["chapter_in_scope", "source_evidence"],
                    "required_evidence": [
                        {"id": "chapter-file-authored", "target": "docs/product/01-background.md", "status": "missing"},
                        {"id": "product-readme-indexed", "target": "docs/product/README.md", "status": "satisfied"},
                    ],
                    "evidence_repair_actions": [
                        _repair_action(
                            kind="required-evidence-repair",
                            item_key="evidence_id",
                            item_value="chapter-file-authored",
                            target="docs/product/01-background.md",
                            status="missing",
                            refresh_argv=["bin/governance", "product", "plan", ".", "--json"],
                        )
                    ],
                }
            ],
            "manual_authoring_summary": {
                "task_count": 1,
                "open_decision_count": 2,
                "required_evidence_status_counts": {
                    "missing": 1,
                    "satisfied": 1,
                },
                "non_satisfied_required_evidence_count": 1,
                "evidence_repair_action_count": 1,
            },
        }

        self.assertTrue(dry_run_workflow._manual_authoring_summary_matches_tasks(payload))

        payload["manual_authoring_summary"]["task_count"] = 2
        self.assertFalse(dry_run_workflow._manual_authoring_summary_matches_tasks(payload))

    def test_design_link_repair_schema_requires_refresh_command(self) -> None:
        task = {
            "required_links": [
                {"kind": "api_contract", "target": "docs/api/endpoints/01-flow.md", "status": "missing"},
            ],
            "link_repair_actions": [
                _repair_action(
                    kind="required-link-repair",
                    item_key="link_kind",
                    item_value="api_contract",
                    target="docs/api/endpoints/01-flow.md",
                    status="missing",
                    refresh_argv=["bin/governance", "design", "backend-authoring", ".", "--json"],
                )
            ],
        }

        self.assertTrue(dry_run_workflow._task_link_repairs_cover_required_statuses(task))

        del task["link_repair_actions"][0]["refresh_command"]
        self.assertFalse(dry_run_workflow._task_link_repairs_cover_required_statuses(task))

    def test_design_authoring_summary_must_match_tasks(self) -> None:
        payload = {
            "authoring_tasks": [
                {
                    "open_decisions": ["api_contract", "frontend_consumers"],
                    "documents": [
                        {"path": "docs/backend/01-modules.md", "status": "placeholder_present"},
                        {"path": "docs/backend/03-external-services.md", "status": "authored"},
                    ],
                    "required_links": [
                        {"kind": "api_contract", "target": "docs/api/endpoints/01-flow.md", "status": "missing"},
                        {"kind": "product_acceptance", "target": "docs/product/08-acceptance.md", "status": "satisfied"},
                    ],
                    "link_repair_actions": [
                        _repair_action(
                            kind="required-link-repair",
                            item_key="link_kind",
                            item_value="api_contract",
                            target="docs/api/endpoints/01-flow.md",
                            status="missing",
                            refresh_argv=["bin/governance", "design", "backend-authoring", ".", "--json"],
                        )
                    ],
                }
            ],
            "authoring_summary": {
                "task_count": 1,
                "document_status_counts": {
                    "authored": 1,
                    "placeholder_present": 1,
                },
                "non_authored_document_count": 1,
                "open_decision_count": 2,
                "required_link_status_counts": {
                    "missing": 1,
                    "satisfied": 1,
                },
                "non_satisfied_required_link_count": 1,
                "link_repair_action_count": 1,
            },
        }

        self.assertTrue(dry_run_workflow._authoring_summary_matches_tasks(payload))

        payload["authoring_summary"]["required_link_status_counts"]["missing"] = 2
        self.assertFalse(dry_run_workflow._authoring_summary_matches_tasks(payload))

    def test_env_repair_decision_requires_explicit_continue_signal(self) -> None:
        payload = {
            "repair_decision": {
                "decision": "continue_workflow",
                "stop_before_workflow": False,
                "can_continue": True,
                "runnable_action_ids": [],
                "approval_action_ids": [],
                "manual_action_ids": [],
            }
        }

        self.assertTrue(dry_run_workflow._env_repair_decision_allows_workflow(payload))

        payload["repair_decision"]["approval_action_ids"] = ["env-repair-apt-install"]
        self.assertFalse(dry_run_workflow._env_repair_decision_allows_workflow(payload))

    def test_implementation_verification_preview_supports_registered_stack_contracts(self) -> None:
        payload = {
            "ok": True,
            "check": True,
            "verification_ready": True,
            "writes_state": False,
            "executed": False,
            "evidence_recorded": False,
            "command_contract": {"name": "node-stack-tests"},
            "environment_readiness": {
                "ok": True,
                "required_executable": "node",
                "environment_contract": {"environment_id": "project-runtime"},
                "environment_probe_executed": True,
                "required_tools": [{"version_satisfies": True}],
                "repair_decision": {"decision": "continue_execution"},
            },
            "would_write": [
                "docs/development/04-implementation-evidence.md",
                "docs/development/03-verification-log.md",
                "docs/development/02-task-board.md",
                "docs/development/README.md",
            ],
        }

        self.assertTrue(
            dry_run_workflow._implementation_verification_preview_ready(
                payload,
                command_name="node-stack-tests",
                executable="node",
                environment_id="project-runtime",
            )
        )
        self.assertFalse(
            dry_run_workflow._implementation_verification_preview_ready(
                payload,
                command_name="dry-run-task-tests",
                executable="python3",
                environment_id="core-governance",
            )
        )

    def test_dry_run_reaches_design_authoring_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "dry-target"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DRY_RUN),
                    "--target",
                    str(target),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["target_retained"])
            self.assertEqual("implementation", payload["final_phase"])
            self.assertEqual("fresh-target-governance-dry-run", payload["workflow"])
            self.assertEqual(["A-001"], payload["acceptance_ids"])
            self.assertEqual(1, payload["acceptance_id_count"])
            self.assertEqual(1, payload["api_candidate_count"])
            self.assertEqual(
                {
                    "architecture-authoring": 1,
                    "api-authoring": 1,
                    "backend-authoring": 1,
                    "data-model-authoring": 1,
                    "ui-interaction-authoring": 1,
                    "frontend-authoring": 1,
                    "test-strategy-authoring": 1,
                    "implementation-planning-authoring": 1,
                    "architecture-decisions-authoring": 1,
                },
                payload["authoring_task_counts"],
            )
            self.assertFalse(payload["implementation_gate"]["placeholder_blocked_ok"])
            self.assertTrue(payload["implementation_gate"]["placeholder_expected_blocked"])
            self.assertTrue(payload["implementation_gate"]["ready_ok"])
            self.assertEqual("TASK-001", payload["implementation_start"]["task_id"])
            self.assertTrue(payload["implementation_start"]["ready"])
            self.assertTrue(payload["implementation_start"]["applied_status_updates"])
            self.assertTrue(payload["implementation_start"]["baseline_captured"])
            self.assertTrue(payload["implementation_start"]["implementation_plan_in_progress"])
            self.assertTrue(payload["implementation_run"]["ready_check"])
            self.assertTrue(payload["implementation_run"]["snapshot_guarded_start"])
            self.assertTrue(payload["implementation_run"]["start_applied"])
            self.assertTrue(payload["implementation_run"]["verification_ready"])
            self.assertTrue(payload["implementation_run"]["executed_all_required"])
            self.assertTrue(payload["implementation_run"]["review_required_after_execution"])
            self.assertTrue(payload["implementation_run"]["reviewed_closeout_ready"])
            self.assertEqual(2, payload["implementation_run"]["required_count"])
            self.assertEqual(2, payload["implementation_run"]["passed_count"])
            self.assertTrue(payload["implementation_run"]["snapshot_guarded_closeout"])
            self.assertTrue(payload["implementation_run"]["closeout_applied"])
            self.assertTrue(payload["implementation_run"]["complete"])
            consumer_resume = payload["consumer_resume_implementation_handoff"]
            self.assertFalse(consumer_resume["exercised"])
            self.assertTrue(consumer_resume["ok"])
            self.assertFalse(consumer_resume["handoff_ready"])
            self.assertFalse(consumer_resume["reentry_exercised"])
            self.assertTrue(consumer_resume["reentry_ok"])
            self.assertTrue(payload["implementation_verification"]["preview_ready"])
            self.assertTrue(payload["implementation_verification"]["environment_ready"])
            self.assertTrue(payload["implementation_verification"]["environment_version_ready"])
            self.assertEqual(
                "core-governance",
                payload["implementation_verification"]["environment_id"],
            )
            self.assertTrue(payload["implementation_verification"]["executed"])
            self.assertTrue(payload["implementation_verification"]["evidence_recorded"])
            self.assertTrue(payload["implementation_verification"]["command_passed"])
            self.assertTrue(payload["implementation_verification"]["all_current_results_passing"])
            self.assertEqual("code-reviewer", payload["implementation_review"]["authority_skill"])
            self.assertTrue(payload["implementation_review"]["provenance_ready"])
            self.assertTrue(payload["implementation_review"]["change_set_bound"])
            self.assertTrue(payload["implementation_review"]["preview_ready"])
            self.assertTrue(payload["implementation_review"]["evidence_current"])
            stack_acceptance = payload["stack_acceptance"]
            self.assertTrue(stack_acceptance["all_required_passed"])
            self.assertTrue(stack_acceptance["all_available_passed"])
            self.assertEqual(["python", "node"], stack_acceptance["required_stacks"])
            self.assertEqual(["rust"], stack_acceptance["optional_stacks"])
            self.assertEqual("real_runtime_no_network_no_third_party_dependencies", stack_acceptance["policy"])
            for stack in ("python", "node"):
                self.assertEqual("passed", stack_acceptance["stacks"][stack]["status"])
                self.assertTrue(stack_acceptance["stacks"][stack]["runtime_available"])
                self.assertTrue(stack_acceptance["stacks"][stack]["executed"])
                self.assertTrue(stack_acceptance["stacks"][stack]["command_passed"])
                self.assertRegex(stack_acceptance["stacks"][stack]["observed_version"], r"\d")
            rust_acceptance = stack_acceptance["stacks"]["rust"]
            self.assertIn(rust_acceptance["status"], {"passed", "unavailable"})
            if rust_acceptance["status"] == "passed":
                self.assertTrue(rust_acceptance["runtime_available"])
                self.assertTrue(rust_acceptance["executed"])
                self.assertTrue(rust_acceptance["command_passed"])
            else:
                self.assertFalse(rust_acceptance["runtime_available"])
                self.assertFalse(rust_acceptance["executed"])
                self.assertEqual("manual", rust_acceptance["repair_strategy"])
            self.assertEqual(
                ["dry-run-task-tests", "node-stack-tests"],
                payload["implementation_task_package"]["verification_command_names"],
            )
            self.assertTrue(payload["implementation_task_package"]["verification_command_summary"]["all_ready"])
            self.assertEqual(
                [
                    "docs/development/04-implementation-evidence.md",
                    "docs/development/03-verification-log.md",
                    "docs/development/02-task-board.md",
                    "docs/development/README.md",
                ],
                payload["implementation_verification"]["updated_paths"],
            )
            self.assertEqual("TASK-001", payload["implementation_closeout"]["task_id"])
            self.assertTrue(payload["implementation_closeout"]["blocked_without_evidence"])
            self.assertTrue(payload["implementation_closeout"]["ready_with_evidence"])
            self.assertTrue(payload["implementation_closeout"]["applied_status_updates"])
            self.assertTrue(payload["implementation_closeout"]["implementation_plan_complete"])
            self.assertTrue(payload["implementation_closeout"]["workflow_plan_complete"])
            self.assertTrue(payload["runtime_refresh"]["check_ok"])
            self.assertTrue(payload["runtime_refresh"]["applied"])
            self.assertTrue(payload["runtime_refresh"]["runtime_refreshed_at"])
            self.assertTrue(payload["runtime_refresh"]["workflow_plan_complete_after_refresh"])
            self.assertTrue(payload["api_review"]["preflight_ok"])
            self.assertTrue(payload["api_review"]["applied"])
            self.assertTrue(payload["api_review"]["current_after_runtime_refresh"])
            self.assertTrue(payload["reliability_review"]["preflight_ok"])
            self.assertTrue(payload["reliability_review"]["applied"])
            self.assertTrue(payload["reliability_review"]["current_after_runtime_refresh"])
            self.assertEqual(1, payload["reliability_review"]["slo_count"])
            self.assertEqual("initial-baseline", payload["api_review"]["baseline_mode"])
            self.assertEqual("A", payload["api_review"]["scorecard_grade"])
            self.assertTrue(payload["threat_review"]["preflight_ok"])
            self.assertTrue(payload["threat_review"]["applied"])
            self.assertTrue(payload["threat_review"]["current_after_runtime_refresh"])
            self.assertEqual(1, payload["threat_review"]["element_count"])
            self.assertEqual(1, payload["threat_review"]["high_dread_threat_count"])
            self.assertTrue(payload["reliability_review"]["preflight_ok"])
            self.assertTrue(payload["reliability_review"]["applied"])
            self.assertTrue(payload["reliability_review"]["current_after_runtime_refresh"])
            self.assertEqual("required", payload["reliability_review"]["mode"])
            self.assertEqual(1, payload["reliability_review"]["slo_count"])
            self.assertTrue(payload["migration_review"]["preflight_ok"])
            self.assertTrue(payload["migration_review"]["applied"])
            self.assertTrue(payload["migration_review"]["current_after_runtime_refresh"])
            self.assertEqual("backward_compatible", payload["migration_review"]["compatibility_status"])
            self.assertEqual(
                [
                    "bin/governance",
                    "scripts/governance_cli.py",
                    "scripts/implementation_run.py",
                    "scripts/implementation_review_evidence.py",
                    "scripts/implementation_verify.py",
                    "scripts/project_environment.py",
                    "scripts/bounded_process.py",
                    "scripts/workflow_resume.py",
                    "scripts/api_review_evidence.py",
                    "scripts/threat_review_evidence.py",
                    "scripts/reliability_review_evidence.py",
                    "scripts/migration_review_evidence.py",
                    "scripts/design_reviews.py",
                    "docs/agent-workflow/runtime-manifest.json",
                    "docs/agent-workflow/workflow-pack/manifest.json",
                ],
                payload["runtime_refresh"]["refreshed_required_paths"],
            )
            self.assertEqual("action_ready", payload["workflow_resume"]["initialized_status"])
            self.assertEqual("work_ready", payload["workflow_resume"]["product_status"])
            self.assertEqual("work_ready", payload["workflow_resume"]["design_status"])
            self.assertEqual("work_ready", payload["workflow_resume"]["implementation_status"])
            self.assertEqual("complete", payload["workflow_resume"]["complete_status"])
            self.assertTrue(payload["workflow_resume"]["stale_guard"])
            self.assertEqual(
                [
                    "verification_log_row_present",
                    "verification_result_passing",
                    "required_verification_commands_passing",
                    "verification_results_all_passing",
                    "task_verification_links_local_evidence",
                    "code_review_evidence_current",
                ],
                payload["implementation_closeout"]["blocking_codes_without_evidence"],
            )
            self.assertEqual([], payload["target_local_make_coverage"]["missing_step_ids"])
            self.assertEqual("complete", payload["workflow_resume"]["complete_status"])
            self.assertTrue(payload["workflow_resume"]["stale_guard"])
            self.assertEqual(4, payload["product_dispositions"]["recorded_count"])
            self.assertEqual(4, payload["product_dispositions"]["omit_unsupported_count"])
            self.assertEqual(0, payload["product_dispositions"]["unresolved_decision_count"])
            self.assertTrue(payload["product_dispositions"]["work_package_routed_to_phase_action"])
            self.assertEqual(9, payload["design_reviews"]["recorded_count"])
            self.assertEqual(9, payload["design_reviews"]["expected_count"])
            self.assertEqual(9, payload["design_reviews"]["active_count"])
            self.assertEqual(9, payload["design_reviews"]["authority_report_count"])
            self.assertEqual(9, payload["design_reviews"]["decision_report_count"])
            self.assertEqual(0, payload["design_reviews"]["missing_count"])
            self.assertEqual(0, payload["design_reviews"]["stale_count"])
            self.assertTrue(payload["design_reviews"]["work_package_complete"])
            self.assertTrue(payload["project_environment_repair"]["registered"])
            self.assertTrue(payload["project_environment_repair"]["preview_approval_required"])
            self.assertTrue(payload["project_environment_repair"]["unapproved_blocked"])
            self.assertTrue(payload["project_environment_repair"]["applied"])
            self.assertTrue(payload["project_environment_repair"]["environment_ready"])
            self.assertEqual(0, payload["project_environment_repair"]["pending_count"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("make_verify_governance", step_ids)
            self.assertIn("make_verify_check", step_ids)
            self.assertIn("make_governance_status", step_ids)
            self.assertIn("make_workflow_plan_initialized", step_ids)
            self.assertIn("make_workflow_resume_initialized", step_ids)
            self.assertIn("make_work_package_initialized", step_ids)
            self.assertIn("product_plan", step_ids)
            self.assertIn("make_product_plan", step_ids)
            self.assertIn("workflow_plan_product_structuring", step_ids)
            self.assertIn("make_workflow_plan_product_structuring", step_ids)
            self.assertIn("make_workflow_resume_product_structuring", step_ids)
            self.assertIn("make_work_package_product_structuring", step_ids)
            self.assertIn("product_structure", step_ids)
            self.assertIn("product_disposition_background_and_problems_check", step_ids)
            self.assertIn("product_disposition_background_and_problems_apply", step_ids)
            self.assertIn("product_plan_after_dispositions", step_ids)
            self.assertIn("work_package_after_product_dispositions", step_ids)
            self.assertIn("product_dispositions_verify_check", step_ids)
            self.assertIn("api_review_check", step_ids)
            self.assertIn("api_review_apply", step_ids)
            self.assertIn("reliability_review_check", step_ids)
            self.assertIn("reliability_review_apply", step_ids)
            self.assertIn("migration_review_check", step_ids)
            self.assertIn("migration_review_apply", step_ids)
            self.assertIn("api_review_check_after_runtime_refresh", step_ids)
            self.assertIn("design_plan", step_ids)
            self.assertIn("make_design_plan", step_ids)
            self.assertIn("workflow_plan_design_derivation", step_ids)
            self.assertIn("make_workflow_plan_design_derivation", step_ids)
            self.assertIn("make_workflow_resume_design_derivation", step_ids)
            self.assertIn("make_work_package_design_derivation", step_ids)
            self.assertIn("design_review_architecture_a_001_check", step_ids)
            self.assertIn("design_review_architecture_a_001_apply", step_ids)
            self.assertIn("design_review_architecture_decisions_a_001_apply", step_ids)
            self.assertIn("design_plan_after_reviews", step_ids)
            self.assertIn("make_work_package_design_complete", step_ids)
            self.assertIn("implementation_advance_check", step_ids)
            self.assertIn("implementation_ready_verify_check", step_ids)
            self.assertIn("make_workflow_plan_implementation", step_ids)
            self.assertIn("make_workflow_resume_implementation", step_ids)
            self.assertIn("make_work_package_implementation", step_ids)
            self.assertIn("implementation_plan", step_ids)
            self.assertIn("make_implementation_plan", step_ids)
            self.assertIn("make_implementation_run_check", step_ids)
            self.assertIn("implementation_run_apply_start", step_ids)
            self.assertIn("implementation_run_check_in_progress", step_ids)
            self.assertIn("implementation_run_execute", step_ids)
            self.assertIn("implementation_review_plan", step_ids)
            self.assertIn("implementation_review_preview", step_ids)
            self.assertIn("implementation_review_record", step_ids)
            self.assertIn("implementation_run_reviewed_check", step_ids)
            self.assertIn("implementation_run_closeout", step_ids)
            self.assertIn("make_check_env", step_ids)
            self.assertIn("make_repair_env_check", step_ids)
            self.assertIn("make_project_env_plan", step_ids)
            self.assertIn("project_environment_reviewed_repair_register", step_ids)
            self.assertIn("project_environment_reviewed_repair_preview", step_ids)
            self.assertIn("project_environment_reviewed_repair_unapproved", step_ids)
            self.assertIn("project_environment_reviewed_repair_apply", step_ids)
            self.assertIn("project_environment_repaired_plan", step_ids)
            self.assertIn("implementation_start_preview", step_ids)
            self.assertIn("implementation_plan_after_start", step_ids)
            self.assertIn("implementation_closeout_without_evidence", step_ids)
            self.assertIn("implementation_verification_preview", step_ids)
            self.assertIn("implementation_verification_execute", step_ids)
            self.assertIn("implementation_closeout_with_evidence", step_ids)
            self.assertIn("implementation_plan_after_closeout_apply", step_ids)
            self.assertIn("workflow_plan_after_closeout_apply", step_ids)
            self.assertIn("runtime_refresh_check_after_complete", step_ids)
            self.assertIn("runtime_refresh_after_complete", step_ids)
            self.assertIn("make_workflow_plan_after_runtime_refresh", step_ids)
            self.assertIn("make_workflow_resume_complete_after_runtime_refresh", step_ids)
            self.assertIn("project_environment_node_register", step_ids)
            self.assertIn("implementation_node_verification_preview", step_ids)
            self.assertIn("implementation_node_verification_execute", step_ids)
            self.assertIn("project_environment_rust_register", step_ids)
            self.assertIn("implementation_rust_verification_preview", step_ids)
            self.assertIn("make_work_package_complete_after_runtime_refresh", step_ids)
            self.assertTrue((target / "bin/governance").is_file())
            self.assertTrue((target / "docs/product/core/chapter-dispositions.json").is_file())
            self.assertTrue((target / "docs/decisions/design-reviews.json").is_file())
            self.assertTrue((target / "docs/api/endpoints/01-endpoint-contract.md").is_file())
            self.assertTrue((target / "docs/development/04-implementation-evidence.md").is_file())
            self.assertTrue((target / "docs/development/05-code-review-evidence.json").is_file())
            self.assertTrue((target / ".governance/project-environment-repairs.json").is_file())

    def test_dry_run_handles_realistic_multi_acceptance_product_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "field-service-target"
            product = ROOT / "tests/fixtures/product-docs/field-service-ops.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DRY_RUN),
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["target_retained"])
            self.assertEqual("implementation", payload["final_phase"])
            self.assertEqual(["A-001", "A-002", "A-003", "A-004"], payload["acceptance_ids"])
            self.assertEqual(4, payload["acceptance_id_count"])
            self.assertEqual(4, payload["api_candidate_count"])
            self.assertEqual(
                {
                    "architecture-authoring": 4,
                    "api-authoring": 4,
                    "backend-authoring": 4,
                    "data-model-authoring": 4,
                    "ui-interaction-authoring": 4,
                    "frontend-authoring": 4,
                    "test-strategy-authoring": 4,
                    "implementation-planning-authoring": 4,
                    "architecture-decisions-authoring": 4,
                },
                payload["authoring_task_counts"],
            )
            acceptance = (target / "docs/product/08-acceptance-criteria.md").read_text(encoding="utf-8")
            self.assertIn("## A-004 Operations Manager Can View An Audit Timeline", acceptance)
            self.assertFalse(payload["implementation_gate"]["placeholder_blocked_ok"])
            self.assertTrue(payload["implementation_gate"]["placeholder_expected_blocked"])
            self.assertTrue(payload["implementation_gate"]["ready_ok"])
            self.assertTrue(payload["implementation_start"]["ready"])
            self.assertTrue(payload["implementation_start"]["applied_status_updates"])
            self.assertTrue(payload["implementation_start"]["implementation_plan_in_progress"])
            self.assertTrue(payload["implementation_closeout"]["blocked_without_evidence"])
            self.assertTrue(payload["implementation_closeout"]["ready_with_evidence"])
            self.assertTrue(payload["implementation_closeout"]["applied_status_updates"])
            self.assertTrue(payload["implementation_closeout"]["implementation_plan_complete"])
            self.assertTrue(payload["implementation_closeout"]["workflow_plan_complete"])
            self.assertTrue(payload["runtime_refresh"]["check_ok"])
            self.assertTrue(payload["runtime_refresh"]["applied"])
            self.assertTrue(payload["runtime_refresh"]["workflow_plan_complete_after_refresh"])
            self.assertTrue(payload["stack_acceptance"]["all_required_passed"])
            self.assertEqual("passed", payload["stack_acceptance"]["stacks"]["python"]["status"])
            self.assertEqual("passed", payload["stack_acceptance"]["stacks"]["node"]["status"])
            self.assertIn(payload["stack_acceptance"]["stacks"]["rust"]["status"], {"passed", "unavailable"})
            self.assertTrue(payload["api_review"]["preflight_ok"])
            self.assertTrue(payload["api_review"]["applied"])
            self.assertTrue(payload["api_review"]["current_after_runtime_refresh"])
            self.assertTrue(payload["migration_review"]["preflight_ok"])
            self.assertTrue(payload["migration_review"]["applied"])
            self.assertTrue(payload["migration_review"]["current_after_runtime_refresh"])
            self.assertEqual([], payload["target_local_make_coverage"]["missing_step_ids"])
            self.assertEqual(36, payload["design_reviews"]["recorded_count"])
            self.assertEqual(36, payload["design_reviews"]["expected_count"])
            self.assertEqual(36, payload["design_reviews"]["active_count"])
            self.assertEqual(36, payload["design_reviews"]["authority_report_count"])
            self.assertEqual(36, payload["design_reviews"]["decision_report_count"])
            self.assertEqual(0, payload["design_reviews"]["missing_count"])
            self.assertEqual(0, payload["design_reviews"]["stale_count"])
            self.assertTrue(payload["design_reviews"]["work_package_complete"])


def _repair_action(
    *,
    kind: str,
    item_key: str,
    item_value: str,
    target: str,
    status: str,
    refresh_argv: list[str],
) -> dict[str, object]:
    return {
        "id": f"repair-{item_value}",
        "sequence": 1,
        "kind": kind,
        item_key: item_value,
        "target": target,
        "status": status,
        "reason": "test repair",
        "repair_strategy": "repair_for_test",
        "can_auto_apply": False,
        "writes_state": True,
        "approval_required": False,
        "success_condition": "required item status becomes satisfied after verify and refresh",
        "verify_command": _embedded_command(
            "verify-repair",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        "refresh_command": _embedded_command("refresh-repair", refresh_argv),
    }


def _embedded_command(command_id: str, argv: list[str]) -> dict[str, object]:
    return {
        "id": command_id,
        "cwd": "/tmp/target",
        "command": " ".join(argv),
        "argv": argv,
        "writes_state": False,
        "approval_required": False,
        "description": "test command",
    }


if __name__ == "__main__":
    unittest.main()
