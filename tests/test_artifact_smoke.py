import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import smoke_workflow_pack_artifact


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "smoke_workflow_pack_artifact.py"


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


class ArtifactSmokeTest(unittest.TestCase):
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

        with mock.patch.object(smoke_workflow_pack_artifact, "run_source_command", return_value=execution):
            with self.assertRaises(smoke_workflow_pack_artifact.ArtifactSmokeError) as raised:
                smoke_workflow_pack_artifact._run_json(
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

    def test_run_json_blocks_unsafe_output(self) -> None:
        execution = _source_result(
            ["unsafe-command"],
            stdout='{"ok": true}',
            output_redacted=True,
            output_safe=False,
        )

        with mock.patch.object(smoke_workflow_pack_artifact, "run_source_command", return_value=execution):
            with self.assertRaises(smoke_workflow_pack_artifact.ArtifactSmokeError) as raised:
                smoke_workflow_pack_artifact._run_json([], "unsafe_step", ["unsafe-command"], Path("."))

        self.assertFalse(raised.exception.step["output_safe"])
        self.assertTrue(raised.exception.step["output_redacted"])

    def test_artifact_smoke_unpacks_and_runs_checks_from_exported_pack(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SMOKE),
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
        self.assertEqual("temporary-export", payload["archive_source"])
        self.assertFalse(payload["target_retained"])
        self.assertGreater(payload["archive_member_count"], 20)
        self.assertIsInstance(payload["archive_sha256"], str)
        self.assertIsInstance(payload["manifest_sha256"], str)
        self.assertEqual([], payload["target_local_make_coverage"]["missing_step_ids"])
        self.assertEqual(4, payload["product_dispositions"]["recorded_count"])
        self.assertEqual(0, payload["product_dispositions"]["unresolved_decision_count"])
        self.assertTrue(payload["product_dispositions"]["work_package_routed_to_phase_action"])
        self.assertTrue(payload["design_reviews"]["ok"])
        self.assertEqual(9, payload["design_reviews"]["expected_count"])
        self.assertEqual(9, payload["design_reviews"]["recorded_count"])
        self.assertEqual(9, payload["design_reviews"]["active_count"])
        self.assertEqual(0, payload["design_reviews"]["missing_count"])
        self.assertEqual(0, payload["design_reviews"]["stale_count"])
        self.assertTrue(payload["design_reviews"]["work_package_complete"])
        self.assertTrue(payload["implementation_verification"]["ok"])
        self.assertTrue(payload["implementation_verification"]["preview_ready"])
        self.assertTrue(payload["implementation_verification"]["executed"])
        self.assertTrue(payload["implementation_verification"]["evidence_recorded"])
        self.assertTrue(payload["implementation_verification"]["command_passed"])
        self.assertTrue(payload["implementation_verification"]["all_current_results_passing"])
        self.assertTrue(payload["implementation_run"]["ready_check"])
        self.assertTrue(payload["implementation_run"]["snapshot_guarded_start"])
        self.assertTrue(payload["implementation_run"]["executed_all_required"])
        self.assertTrue(payload["implementation_run"]["snapshot_guarded_closeout"])
        self.assertTrue(payload["implementation_run"]["complete"])
        consumer_resume = payload["consumer_resume_implementation_handoff"]
        self.assertTrue(consumer_resume["exercised"])
        self.assertTrue(consumer_resume["ok"])
        self.assertEqual("design-derivation", consumer_resume["phase_before"])
        self.assertEqual("implementation", consumer_resume["phase_after"])
        self.assertTrue(consumer_resume["transition_applied"])
        self.assertTrue(consumer_resume["state_write_observed"])
        self.assertTrue(consumer_resume["routing_ok"])
        self.assertTrue(consumer_resume["route_ready"])
        self.assertTrue(consumer_resume["runner_contract_valid"])
        self.assertTrue(consumer_resume["handoff_ready"])
        self.assertEqual("ready_to_start", consumer_resume["status"])
        self.assertEqual("TASK-001", consumer_resume["task_id"])
        self.assertTrue(consumer_resume["snapshot_guarded"])
        self.assertTrue(consumer_resume["reentry_exercised"])
        self.assertTrue(consumer_resume["reentry_ok"])
        self.assertTrue(consumer_resume["reentry_transition_already_current"])
        self.assertTrue(consumer_resume["reentry_snapshot_stable"])
        self.assertTrue(payload["implementation_task_package"]["ok"])
        self.assertEqual(
            ["dry-run-task-tests", "node-stack-tests"],
            payload["implementation_task_package"]["verification_command_names"],
        )
        self.assertEqual(
            "claim_then_execute_all_required_verification_commands_then_closeout",
            payload["implementation_task_package"]["decision_policy"],
        )
        self.assertTrue(payload["stack_acceptance"]["ok"])
        self.assertTrue(payload["stack_acceptance"]["all_required_passed"])
        self.assertEqual("passed", payload["stack_acceptance"]["stacks"]["python"]["status"])
        self.assertEqual("passed", payload["stack_acceptance"]["stacks"]["node"]["status"])
        self.assertIn(payload["stack_acceptance"]["stacks"]["rust"]["status"], {"passed", "unavailable"})
        self.assertTrue(payload["api_review"]["ok"])
        self.assertTrue(payload["api_review"]["preflight_ok"])
        self.assertTrue(payload["api_review"]["applied"])
        self.assertTrue(payload["api_review"]["current_after_runtime_refresh"])
        self.assertEqual("A", payload["api_review"]["scorecard_grade"])
        self.assertTrue(payload["threat_review"]["ok"])
        self.assertTrue(payload["threat_review"]["preflight_ok"])
        self.assertTrue(payload["threat_review"]["applied"])
        self.assertTrue(payload["threat_review"]["current_after_runtime_refresh"])
        self.assertEqual(1, payload["threat_review"]["element_count"])
        self.assertEqual(1, payload["threat_review"]["high_dread_threat_count"])
        self.assertTrue(payload["fresh_target_init"]["ok"])
        self.assertEqual("initialized", payload["fresh_target_init"]["phase"])
        self.assertTrue(payload["fresh_target_init"]["target_local_verify_ok"])
        self.assertTrue(payload["fresh_target_init"]["target_local_status_ok"])
        self.assertTrue(payload["fresh_target_init"]["target_local_workflow_plan_ok"])
        self.assertTrue(payload["fresh_target_init"]["target_local_work_package_ok"])
        self.assertTrue(payload["fresh_target_init"]["target_local_workflow_resume_ok"])
        self.assertTrue(payload["fresh_target_init"]["runtime_manifest"])
        self.assertTrue(payload["fresh_target_init"]["workflow_pack_snapshot"])
        self.assertTrue(payload["fresh_target_init"]["product_source_manifest"])
        one_command = payload["consumer_bootstrap_one_command"]
        self.assertTrue(one_command["ok"])
        self.assertTrue(one_command["check_ok"])
        self.assertTrue(one_command["check_left_target_uninitialized"])
        self.assertTrue(one_command["apply_ok"])
        self.assertTrue(one_command["initialized"])
        self.assertTrue(one_command["auto_repair_env"])
        self.assertEqual("current-directory", one_command["target_selection"])
        self.assertEqual("target-directory-name", one_command["project_name_selection"])
        self.assertEqual("auto-discovered", one_command["product_selection"])
        self.assertTrue(one_command["workflow_resume_ok"])
        self.assertTrue(one_command["repository_git_check_ok"])
        self.assertTrue(one_command["repository_git_initialized"])
        self.assertTrue(one_command["repository_git_apply_ok"])
        self.assertEqual("main", one_command["repository_git_branch"])
        self.assertEqual("Artifact Consumer", one_command["repository_git_author_name"])
        self.assertEqual("artifact-consumer@example.com", one_command["repository_git_author_email"])
        self.assertFalse(one_command["repository_git_has_commits"])
        conversion = payload["consumer_bootstrap_product_conversion"]
        self.assertTrue(conversion["ok"])
        self.assertTrue(conversion["check_ok"])
        self.assertTrue(conversion["check_left_target_uninitialized"])
        self.assertTrue(conversion["apply_ok"])
        self.assertTrue(conversion["conversion_requested"])
        self.assertTrue(conversion["conversion_applied"])
        self.assertTrue(conversion["pending_product_review"])
        self.assertTrue(conversion["conversion_report"])
        self.assertEqual("product-mark-ready", conversion["selected_action_id"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["ok"])
        self.assertEqual("product-structuring", payload["consumer_bootstrap_product_structure"]["phase"])
        self.assertEqual(
            "product-structure",
            payload["consumer_bootstrap_product_structure"]["workflow_preset"],
        )
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["auto_repair_env"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["requested"])
        self.assertEqual(
            "continue_workflow",
            payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["decision"],
        )
        self.assertEqual("continue", payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["status"])
        self.assertFalse(
            payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["stop_before_workflow"]
        )
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["can_continue"])
        self.assertFalse(payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["can_auto_apply"])
        self.assertFalse(payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["requires_approval"])
        self.assertFalse(
            payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["manual_repair_required"]
        )
        self.assertEqual([], payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["runnable_action_ids"])
        self.assertEqual([], payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["approval_action_ids"])
        self.assertEqual([], payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["manual_action_ids"])
        self.assertEqual(
            "continue workflow",
            payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["next_step"],
        )
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["final_env_check_ok"])
        self.assertEqual([], payload["consumer_bootstrap_product_structure"]["env_auto_repair"]["final_missing_required"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["ok"])
        self.assertFalse(payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["strict"])
        self.assertGreaterEqual(
            payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["required_skill_count"],
            19,
        )
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["manifest_ok"])
        self.assertTrue(
            payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"][
                "manifest_aligned_with_routing"
            ]
        )
        self.assertTrue(
            payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["repair_requested"]
        )
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["repair_check"])
        self.assertFalse(
            payload["consumer_bootstrap_product_structure"]["authority_skill_inventory"]["repair_writes_state"]
        )
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["product_structure_apply_ok"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["work_package"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["workflow_resume"]["ok"])
        self.assertEqual(
            "product-structuring",
            payload["consumer_bootstrap_product_structure"]["workflow_resume"]["phase"],
        )
        self.assertEqual("product-structuring", payload["consumer_bootstrap_product_structure"]["work_package"]["phase"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["goals_chapter"])
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["acceptance_chapter"])
        self.assertIn(
            "product_structure_apply",
            payload["consumer_bootstrap_product_structure"]["workflow_preset_expanded_flags"],
        )
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["ok"])
        self.assertEqual("design-derivation", payload["consumer_bootstrap_design_scaffold"]["phase"])
        self.assertEqual(
            "design-scaffold",
            payload["consumer_bootstrap_design_scaffold"]["workflow_preset"],
        )
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["auto_repair_env"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["env_auto_repair"]["ok"])
        self.assertEqual("continue_workflow", payload["consumer_bootstrap_design_scaffold"]["env_auto_repair"]["decision"])
        self.assertFalse(payload["consumer_bootstrap_design_scaffold"]["env_auto_repair"]["stop_before_workflow"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["authority_skill_inventory"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["design_scaffold_apply_ok"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["post_verify_blocked_by_placeholders"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["system_context_doc"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["endpoint_contract_doc"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["work_package"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_design_scaffold"]["workflow_resume"]["ok"])
        self.assertEqual(
            "architecture-authoring",
            payload["consumer_bootstrap_design_scaffold"]["work_package"]["queue_id"],
        )
        self.assertIn(
            "design_scaffold_apply",
            payload["consumer_bootstrap_design_scaffold"]["workflow_preset_expanded_flags"],
        )
        self.assertTrue(payload["consumer_bootstrap_design_routing"]["ok"])
        self.assertEqual("design-derivation", payload["consumer_bootstrap_design_routing"]["phase"])
        self.assertEqual(
            "design-routing",
            payload["consumer_bootstrap_design_routing"]["workflow_preset"],
        )
        self.assertTrue(payload["consumer_bootstrap_design_routing"]["design_authoring_preview_ok"])
        self.assertTrue(payload["consumer_bootstrap_design_routing"]["env_auto_repair"]["ok"])
        self.assertEqual("continue_workflow", payload["consumer_bootstrap_design_routing"]["env_auto_repair"]["decision"])
        self.assertFalse(payload["consumer_bootstrap_design_routing"]["env_auto_repair"]["stop_before_workflow"])
        self.assertTrue(payload["consumer_bootstrap_design_routing"]["authority_skill_inventory"]["ok"])
        self.assertEqual(9, payload["consumer_bootstrap_design_routing"]["queue_count"])
        self.assertEqual([], payload["consumer_bootstrap_design_routing"]["missing_queue_ids"])
        self.assertTrue(payload["consumer_bootstrap_design_routing"]["work_package"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_design_routing"]["workflow_resume"]["ok"])
        self.assertEqual(
            "architecture-authoring",
            payload["consumer_bootstrap_design_routing"]["work_package"]["queue_id"],
        )
        design_routing = payload["consumer_bootstrap_design_routing"]
        self.assertEqual(9, len(design_routing["queue_summaries"]))
        self.assertEqual(9, design_routing["authoring_summary"]["queue_count"])
        self.assertGreater(design_routing["authoring_summary"]["blocked_queue_count"], 0)
        self.assertGreater(design_routing["authoring_summary"]["total_task_count"], 0)
        self.assertGreater(
            design_routing["authoring_summary"]["total_non_satisfied_required_link_count"],
            0,
        )
        self.assertEqual(
            design_routing["authoring_summary"]["next_queue_id"],
            design_routing["active_work"]["queue_id"],
        )
        self.assertEqual(
            design_routing["authoring_summary"]["next_active_work"],
            design_routing["active_work"],
        )
        self.assertIn(
            "design_authoring_preview",
            payload["consumer_bootstrap_design_routing"]["workflow_preset_expanded_flags"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["ok"])
        self.assertEqual("design-derivation", payload["consumer_bootstrap_implementation_routing"]["phase"])
        self.assertEqual(
            "implementation-routing",
            payload["consumer_bootstrap_implementation_routing"]["workflow_preset"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["implementation_readiness_preview_ok"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["env_auto_repair"]["ok"])
        self.assertEqual(
            "continue_workflow",
            payload["consumer_bootstrap_implementation_routing"]["env_auto_repair"]["decision"],
        )
        self.assertFalse(payload["consumer_bootstrap_implementation_routing"]["env_auto_repair"]["stop_before_workflow"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["authority_skill_inventory"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["work_package"]["ok"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["workflow_resume"]["ok"])
        self.assertEqual(
            "architecture-authoring",
            payload["consumer_bootstrap_implementation_routing"]["work_package"]["queue_id"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["readiness_previewed"])
        self.assertFalse(payload["consumer_bootstrap_implementation_routing"]["readiness_ok"])
        self.assertFalse(payload["consumer_bootstrap_implementation_routing"]["implementation_ready"])
        self.assertGreater(payload["consumer_bootstrap_implementation_routing"]["readiness_blocker_count"], 0)
        self.assertIn(
            "governance_scaffold_placeholder",
            payload["consumer_bootstrap_implementation_routing"]["readiness_blocker_codes"],
        )
        self.assertIn(
            payload["consumer_bootstrap_implementation_routing"]["readiness_next_blocker"]["code"],
            payload["consumer_bootstrap_implementation_routing"]["readiness_blocker_codes"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["readiness_next_repair_action"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["advance_previewed"])
        self.assertFalse(payload["consumer_bootstrap_implementation_routing"]["advance_ready"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["advance_apply_skipped"])
        self.assertEqual(
            "advance_preview_not_ready",
            payload["consumer_bootstrap_implementation_routing"]["advance_apply_skip_code"],
        )
        self.assertEqual(
            "implementation_advance_preview",
            payload["consumer_bootstrap_implementation_routing"]["advance_apply_blocked_by"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["implementation_run_preview_ok"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["run_previewed"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["run_preview_skipped"])
        self.assertEqual(
            "advance_apply_not_applied",
            payload["consumer_bootstrap_implementation_routing"]["run_preview_skip_code"],
        )
        self.assertEqual(
            "implementation_advance_apply",
            payload["consumer_bootstrap_implementation_routing"]["run_preview_blocked_by"],
        )
        self.assertFalse(payload["consumer_bootstrap_implementation_routing"]["run_required_advance_applied"])
        self.assertFalse(payload["consumer_bootstrap_implementation_routing"]["run_handoff_ready"])
        self.assertEqual("", payload["consumer_bootstrap_implementation_routing"]["run_status"])
        self.assertEqual("", payload["consumer_bootstrap_implementation_routing"]["run_task_id"])
        self.assertEqual({}, payload["consumer_bootstrap_implementation_routing"]["run_snapshot"])
        self.assertEqual({}, payload["consumer_bootstrap_implementation_routing"]["run_next_action"])
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["blocked_by_placeholders"])
        self.assertIn(
            "implementation_readiness_preview",
            payload["consumer_bootstrap_implementation_routing"]["workflow_preset_expanded_flags"],
        )
        self.assertIn(
            "implementation_advance_preview",
            payload["consumer_bootstrap_implementation_routing"]["workflow_preset_expanded_flags"],
        )
        self.assertIn(
            "implementation_run_preview",
            payload["consumer_bootstrap_implementation_routing"]["workflow_preset_expanded_flags"],
        )
        self.assertNotIn(
            "implementation_start_apply",
            payload["consumer_bootstrap_implementation_routing"]["workflow_preset_expanded_flags"],
        )
        self.assertNotIn(
            "implementation_closeout_apply",
            payload["consumer_bootstrap_implementation_routing"]["workflow_preset_expanded_flags"],
        )
        step_ids = {step["id"] for step in payload["steps"]}
        self.assertIn("export_artifact", step_ids)
        self.assertIn("unpacked_verify_pack_manifest", step_ids)
        self.assertIn("unpacked_verify_pack", step_ids)
        self.assertIn("unpacked_init_fresh_target_check", step_ids)
        self.assertIn("unpacked_init_fresh_target", step_ids)
        self.assertIn("fresh_target_verify_check", step_ids)
        self.assertIn("fresh_target_governance_status", step_ids)
        self.assertIn("fresh_target_workflow_plan", step_ids)
        self.assertIn("fresh_target_workflow_resume", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_one_command_check", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_one_command_apply", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_product_conversion_check", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_product_conversion_apply", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_product_structure", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_design_scaffold", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_design_routing", step_ids)
        self.assertIn("unpacked_consumer_bootstrap_implementation_routing", step_ids)
        self.assertIn("unpacked_dry_run", step_ids)

    def test_artifact_smoke_can_validate_existing_archive_without_reexporting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = base / "docs-as-code-workflow-pack.tar.gz"
            output = base / "docs-as-code-workflow-pack"
            export_result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/export_workflow_pack.py"),
                    "--output",
                    str(output),
                    "--archive",
                    str(archive),
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export_result.returncode, export_result.stdout + export_result.stderr)
            export_payload = json.loads(export_result.stdout)
            self.assertTrue(export_payload["ok"])

            result = subprocess.run(
                [
                    sys.executable,
                    str(SMOKE),
                    "--archive",
                    str(archive),
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
            self.assertEqual("provided-archive", payload["archive_source"])
            self.assertEqual(str(archive.resolve()), payload["archive"])
            self.assertEqual(export_payload["archive_sha256"], payload["archive_sha256"])
            self.assertEqual(export_payload["manifest_sha256"], payload["manifest_sha256"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertNotIn("export_artifact", step_ids)
            self.assertIn("unpacked_verify_pack_manifest", step_ids)
            self.assertIn("unpacked_init_fresh_target", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_one_command_check", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_one_command_apply", step_ids)
            self.assertTrue(payload["consumer_bootstrap_one_command"]["ok"])
            self.assertTrue(payload["consumer_bootstrap_product_conversion"]["ok"])
            self.assertIn("unpacked_consumer_bootstrap_product_conversion_check", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_product_conversion_apply", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_product_structure", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_design_scaffold", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_design_routing", step_ids)
            self.assertIn("unpacked_consumer_bootstrap_implementation_routing", step_ids)
            self.assertIn("unpacked_dry_run", step_ids)

    def test_artifact_smoke_reports_missing_provided_archive(self) -> None:
        missing_archive = Path(tempfile.gettempdir()) / "docs-as-code-missing-pack.tar.gz"
        if missing_archive.exists():
            missing_archive.unlink()

        result = subprocess.run(
            [
                sys.executable,
                str(SMOKE),
                "--archive",
                str(missing_archive),
                "--json",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("artifact archive is not a file", payload["error"])
        self.assertEqual(str(missing_archive.resolve()), payload["archive"])
        self.assertEqual("provided-archive", payload["archive_source"])
        self.assertEqual([], payload["steps"])

    def test_artifact_smoke_reports_unreadable_provided_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "broken.tar.gz"
            archive.write_text("not a gzip archive\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SMOKE),
                    "--archive",
                    str(archive),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("artifact archive could not be read", payload["error"])
            self.assertEqual(str(archive.resolve()), payload["archive"])
            self.assertEqual("provided-archive", payload["archive_source"])
            self.assertEqual([], payload["steps"])


if __name__ == "__main__":
    unittest.main()
