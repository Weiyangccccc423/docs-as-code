import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from scripts import release_readiness
from scripts.release_readiness import (
    _artifact_smoke_design_authoring_summary_ok,
    _artifact_smoke_work_package_ok,
    _dry_run_implementation_task_package_ok,
    _dry_run_implementation_runner_ok,
    _run_local_unit_test_gate,
)


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "scripts" / "release_readiness.py"


def _source_result(argv: list[str], **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "started": True,
        "argv": argv,
        "cwd": str(ROOT),
        "started_at": "2026-07-20T00:00:00.000000Z",
        "finished_at": "2026-07-20T00:00:00.010000Z",
        "duration_seconds": 0.01,
        "returncode": 0,
        "result": "pass",
        "timed_out": False,
        "timeout_seconds": 3600.0,
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


class ReleaseReadinessTest(unittest.TestCase):
    def test_release_step_records_timeout_as_structured_failure(self) -> None:
        steps: list[dict[str, object]] = []
        execution = _source_result(
            ["slow-command"],
            timed_out=True,
            returncode=-9,
            stdout="partial stdout",
            stderr="partial stderr",
            timeout_seconds=0.05,
        )

        with mock.patch.object(release_readiness, "run_source_command", return_value=execution):
            payload = release_readiness._run_step(
                steps,
                "slow_step",
                ["slow-command"],
                timeout_seconds=0.05,
            )

        self.assertIsNone(payload)
        self.assertFalse(steps[0]["ok"])
        self.assertTrue(steps[0]["timed_out"])
        self.assertEqual(0.05, steps[0]["timeout_seconds"])
        self.assertEqual("partial stdout", steps[0]["stdout"])
        self.assertEqual("partial stderr", steps[0]["stderr"])

    def test_release_step_blocks_unsafe_output(self) -> None:
        steps: list[dict[str, object]] = []
        execution = _source_result(
            ["unsafe-command"],
            stdout="truncated output",
            stdout_truncated=True,
            output_safe=False,
        )

        with mock.patch.object(release_readiness, "run_source_command", return_value=execution):
            payload = release_readiness._run_step(steps, "unsafe_step", ["unsafe-command"])

        self.assertIsNone(payload)
        self.assertFalse(steps[0]["ok"])
        self.assertFalse(steps[0]["output_safe"])
        self.assertTrue(steps[0]["stdout_truncated"])

    def test_local_unit_test_gate_uses_parallel_runner(self) -> None:
        steps: list[dict[str, object]] = []
        criteria: list[dict[str, object]] = []

        def record_step(
            target_steps: list[dict[str, object]],
            step_id: str,
            argv: list[str | Path],
            **_kwargs: object,
        ) -> None:
            target_steps.append(
                {
                    "id": step_id,
                    "argv": [str(item) for item in argv],
                    "ok": True,
                }
            )

        with mock.patch("scripts.release_readiness._run_step", side_effect=record_step) as run_step:
            _run_local_unit_test_gate(steps, criteria, skip_tests=False)

        run_step.assert_called_once_with(
            steps,
            "unit_tests",
            [sys.executable, "scripts/run_tests.py"],
        )
        self.assertEqual("pass", criteria[0]["status"])
        self.assertEqual("python3 scripts/run_tests.py", criteria[0]["evidence"])

    def test_local_unit_test_gate_preserves_skip_evidence(self) -> None:
        steps: list[dict[str, object]] = []
        criteria: list[dict[str, object]] = []

        with mock.patch("scripts.release_readiness._run_step") as run_step:
            _run_local_unit_test_gate(steps, criteria, skip_tests=True)

        run_step.assert_not_called()
        self.assertEqual([], steps)
        self.assertEqual("skipped", criteria[0]["status"])
        self.assertEqual("python3 scripts/run_tests.py", criteria[0]["evidence"])

    def test_dry_run_implementation_runner_check_requires_guarded_complete_execution(self) -> None:
        payload = {
            "implementation_run": {
                "ready_check": True,
                "snapshot_guarded_start": True,
                "start_applied": True,
                "verification_ready": True,
                "required_count": 2,
                "passed_count": 2,
                "executed_all_required": True,
                "snapshot_guarded_closeout": True,
                "closeout_applied": True,
                "complete": True,
            }
        }

        self.assertTrue(_dry_run_implementation_runner_ok(payload))
        payload["implementation_run"]["snapshot_guarded_closeout"] = False
        self.assertFalse(_dry_run_implementation_runner_ok(payload))

    def test_dry_run_implementation_task_package_check_requires_bound_commands(self) -> None:
        command_names = ["task-tests", "node-tests"]
        payload = {
            "implementation_task_package": {
                "verification_command_names": command_names,
                "verification_commands": [
                    {
                        "name": name,
                        "ready": True,
                        "preflight_command": {"argv": ["bin/governance", "implementation", "verify"]},
                        "execute_command": {"argv": ["bin/governance", "implementation", "verify"]},
                    }
                    for name in command_names
                ],
                "verification_command_summary": {
                    "required_count": 2,
                    "ready_count": 2,
                    "blocked_count": 0,
                    "all_ready": True,
                },
                "execution_contract": {
                    "decision_policy": "claim_then_execute_all_required_verification_commands_then_closeout",
                    "verification_commands": [
                        {
                            "name": name,
                            "ready": True,
                            "preflight_command": {"argv": ["bin/governance", "implementation", "verify"]},
                            "execute_command": {"argv": ["bin/governance", "implementation", "verify"]},
                        }
                        for name in command_names
                    ],
                },
            }
        }

        self.assertTrue(_dry_run_implementation_task_package_ok(payload))
        payload["implementation_task_package"]["verification_command_summary"]["all_ready"] = False
        self.assertFalse(_dry_run_implementation_task_package_ok(payload))

    def test_artifact_smoke_work_package_check_requires_expected_identity(self) -> None:
        summary = {
            "work_package": {
                "ok": True,
                "phase": "design-derivation",
                "status": "blocked",
                "kind": "design-authoring",
                "queue_id": "architecture-authoring",
                "work_id": "DESIGN-AUTHOR-001",
                "can_start": True,
                "stop_before_work": False,
                "skill_ready": True,
                "missing_local_workflow_skills": [],
                "missing_authority_routing_skills": [],
                "next_action_kind": "repair",
            }
        }

        self.assertTrue(
            _artifact_smoke_work_package_ok(
                summary,
                expected_phase="design-derivation",
                expected_kind="design-authoring",
                expected_queue_id="architecture-authoring",
            )
        )
        self.assertFalse(
            _artifact_smoke_work_package_ok(
                {},
                expected_phase="design-derivation",
                expected_kind="design-authoring",
                expected_queue_id="architecture-authoring",
            )
        )
        self.assertFalse(
            _artifact_smoke_work_package_ok(
                summary,
                expected_phase="design-derivation",
                expected_kind="design-authoring",
                expected_queue_id="api-authoring",
            )
        )

    def test_design_authoring_summary_check_rejects_non_numeric_category_counts(self) -> None:
        queue_ids = [
            "architecture-authoring",
            "api-authoring",
            "backend-authoring",
            "data-model-authoring",
            "ui-interaction-authoring",
            "frontend-authoring",
            "test-strategy-authoring",
            "implementation-planning-authoring",
            "architecture-decisions-authoring",
        ]
        queue_summaries = [
            {
                "sequence": sequence,
                "queue_id": queue_id,
                "status": "blocked",
                "task_count": 1,
                "open_decision_count": 0,
                "non_satisfied_required_link_count": 1,
                "link_repair_action_count": 1,
            }
            for sequence, queue_id in enumerate(queue_ids, start=1)
        ]
        active_work = {
            "status": "blocked",
            "queue_id": queue_ids[0],
            "queue_sequence": 1,
        }
        design_routing = {
            "authoring_summary_ok": True,
            "queue_summaries": queue_summaries,
            "active_work": active_work,
            "authoring_summary": {
                "queue_count": 9,
                "blocked_queue_count": "9",
                "decision_required_queue_count": 0,
                "ready_queue_count": 0,
                "queue_status_counts": {"blocked": 9},
                "total_task_count": 9,
                "total_open_decision_count": 0,
                "total_non_satisfied_required_link_count": 9,
                "total_link_repair_action_count": 9,
                "next_queue_id": queue_ids[0],
                "next_active_work": active_work,
            },
        }

        self.assertFalse(_artifact_smoke_design_authoring_summary_ok(design_routing))

    def test_release_readiness_fast_mode_runs_hard_checks_without_claiming_release_ready(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RELEASE),
                "--skip-tests",
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
        self.assertFalse(payload["release_ready"])
        self.assertTrue(payload["tests_skipped"])
        criteria = {item["id"]: item for item in payload["criteria"]}
        self.assertEqual("skipped", criteria["unit-tests"]["status"])
        for criterion_id in (
            "diff-whitespace",
            "cached-diff-whitespace",
            "pack-verification",
            "environment-inventory",
            "authority-skill-inventory",
            "fresh-target-dry-run",
            "multi-acceptance-dry-run",
            "source-pack-export-check",
            "source-pack-export",
            "source-pack-reproducible-export",
            "release-artifact-smoke",
        ):
            self.assertEqual("pass", criteria[criterion_id]["status"])
        self.assertEqual(
            "continue_workflow",
            criteria["environment-inventory"]["details"]["repair_decision"]["decision"],
        )
        self.assertFalse(
            criteria["environment-inventory"]["details"]["repair_decision"]["stop_before_workflow"],
        )
        self.assertGreaterEqual(criteria["authority-skill-inventory"]["details"]["required_skill_count"], 19)
        self.assertEqual(
            "load_from_agent_environment_or_stop_before_guessing",
            criteria["authority-skill-inventory"]["details"]["missing_policy"],
        )
        self.assertTrue(criteria["authority-skill-inventory"]["details"]["manifest_ok"])
        self.assertTrue(criteria["authority-skill-inventory"]["details"]["manifest_aligned_with_routing"])
        self.assertEqual(24, sum(criteria["authority-skill-inventory"]["details"]["status_counts"].values()))
        self.assertTrue(criteria["authority-skill-inventory"]["details"]["repair_plan"]["requested"])
        self.assertTrue(criteria["authority-skill-inventory"]["details"]["repair_plan"]["check"])
        self.assertFalse(criteria["authority-skill-inventory"]["details"]["repair_plan"]["writes_state"])
        self.assertGreater(criteria["source-pack-export-check"]["details"]["would_write_count"], 0)
        self.assertTrue(criteria["source-pack-export-check"]["details"]["would_archive"])
        self.assertEqual(
            [],
            criteria["fresh-target-dry-run"]["details"]["target_local_make_coverage"]["missing_step_ids"],
        )
        self.assertEqual(
            4,
            criteria["fresh-target-dry-run"]["details"]["product_dispositions"]["recorded_count"],
        )
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["product_dispositions"][
                "work_package_routed_to_phase_action"
            ]
        )
        self.assertEqual(
            9,
            criteria["fresh-target-dry-run"]["details"]["design_reviews"]["active_count"],
        )
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["design_reviews"]["work_package_complete"]
        )
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["implementation_verification"]["command_passed"]
        )
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["implementation_verification"][
                "all_current_results_passing"
            ]
        )
        self.assertTrue(criteria["fresh-target-dry-run"]["details"]["implementation_run"]["complete"])
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["implementation_run"]["executed_all_required"]
        )
        self.assertEqual(
            ["dry-run-task-tests", "node-stack-tests"],
            criteria["fresh-target-dry-run"]["details"]["implementation_task_package"][
                "verification_command_names"
            ],
        )
        self.assertTrue(criteria["fresh-target-dry-run"]["details"]["stack_acceptance"]["all_required_passed"])
        self.assertEqual(
            "passed",
            criteria["fresh-target-dry-run"]["details"]["stack_acceptance"]["stacks"]["node"]["status"],
        )
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["api_review"]["current_after_runtime_refresh"]
        )
        self.assertTrue(
            criteria["fresh-target-dry-run"]["details"]["threat_review"]["current_after_runtime_refresh"]
        )
        self.assertEqual(
            [],
            criteria["multi-acceptance-dry-run"]["details"]["target_local_make_coverage"]["missing_step_ids"],
        )
        self.assertEqual(
            0,
            criteria["multi-acceptance-dry-run"]["details"]["product_dispositions"][
                "unresolved_decision_count"
            ],
        )
        self.assertEqual(
            36,
            criteria["multi-acceptance-dry-run"]["details"]["design_reviews"]["active_count"],
        )
        self.assertTrue(
            criteria["multi-acceptance-dry-run"]["details"]["api_review"]["current_after_runtime_refresh"]
        )
        self.assertTrue(
            criteria["multi-acceptance-dry-run"]["details"]["threat_review"]["current_after_runtime_refresh"]
        )
        self.assertTrue(
            criteria["multi-acceptance-dry-run"]["details"]["implementation_verification"]["evidence_recorded"]
        )
        self.assertTrue(criteria["multi-acceptance-dry-run"]["details"]["implementation_run"]["complete"])
        self.assertTrue(
            criteria["multi-acceptance-dry-run"]["details"]["implementation_task_package"][
                "verification_command_summary"
            ]["all_ready"]
        )
        self.assertTrue(
            criteria["multi-acceptance-dry-run"]["details"]["stack_acceptance"]["all_required_passed"]
        )
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["fresh_target_init"]["ok"])
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["fresh_target_init"]["target_local_workflow_plan_ok"]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["fresh_target_init"]["target_local_work_package_ok"]
        )
        self.assertEqual(
            0,
            criteria["release-artifact-smoke"]["details"]["product_dispositions"][
                "unresolved_decision_count"
            ],
        )
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["design_reviews"]["ok"])
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["api_review"]["ok"])
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["threat_review"]["ok"])
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["implementation_verification"]["ok"]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["implementation_task_package"]["ok"]
        )
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["implementation_run"]["complete"])
        consumer_resume = criteria["release-artifact-smoke"]["details"][
            "consumer_resume_implementation_handoff"
        ]
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
        self.assertTrue(consumer_resume["snapshot_guarded"])
        self.assertTrue(consumer_resume["reentry_exercised"])
        self.assertTrue(consumer_resume["reentry_ok"])
        self.assertTrue(consumer_resume["reentry_transition_already_current"])
        self.assertTrue(consumer_resume["reentry_snapshot_stable"])
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["stack_acceptance"]["ok"])
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["stack_acceptance"]["all_required_passed"]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["api_review"][
                "current_after_runtime_refresh"
            ]
        )
        self.assertEqual(
            9,
            criteria["release-artifact-smoke"]["details"]["design_reviews"]["active_count"],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["ok"]
        )
        self.assertEqual(
            "product-plan",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["work_package"][
                "queue_id"
            ],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "ok"
            ]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "requested"
            ]
        )
        self.assertEqual(
            "continue_workflow",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "decision"
            ],
        )
        self.assertEqual(
            "continue",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "status"
            ],
        )
        self.assertFalse(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "stop_before_workflow"
            ],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "can_continue"
            ],
        )
        self.assertFalse(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "can_auto_apply"
            ],
        )
        self.assertFalse(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "requires_approval"
            ],
        )
        self.assertFalse(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "manual_repair_required"
            ],
        )
        self.assertEqual(
            [],
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "runnable_action_ids"
            ],
        )
        self.assertEqual(
            [],
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "approval_action_ids"
            ],
        )
        self.assertEqual(
            [],
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "manual_action_ids"
            ],
        )
        self.assertEqual(
            "continue workflow",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "next_step"
            ],
        )
        self.assertEqual(
            [],
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["env_auto_repair"][
                "final_missing_required"
            ],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"][
                "authority_skill_inventory"
            ]["ok"]
        )
        self.assertFalse(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"][
                "authority_skill_inventory"
            ]["strict"]
        )
        self.assertEqual(
            "product-structuring",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["phase"],
        )
        self.assertEqual(
            "product-structure",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["workflow_preset"],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"][
                "product_structure_apply_ok"
            ]
        )
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"]["ok"])
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"]["env_auto_repair"][
                "ok"
            ]
        )
        self.assertEqual(
            "continue_workflow",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"]["env_auto_repair"][
                "decision"
            ],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"][
                "authority_skill_inventory"
            ]["ok"]
        )
        self.assertEqual(
            "design-derivation",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"]["phase"],
        )
        self.assertEqual(
            "design-scaffold",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"]["workflow_preset"],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"][
                "design_scaffold_apply_ok"
            ]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"][
                "post_verify_blocked_by_placeholders"
            ]
        )
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["ok"])
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["env_auto_repair"][
                "ok"
            ]
        )
        self.assertEqual(
            "continue_workflow",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["env_auto_repair"][
                "decision"
            ],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"][
                "authority_skill_inventory"
            ]["ok"]
        )
        self.assertEqual(
            "design-derivation",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["phase"],
        )
        self.assertEqual(
            "design-routing",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["workflow_preset"],
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"][
                "design_authoring_preview_ok"
            ]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["work_package"]["ok"]
        )
        self.assertEqual(
            "architecture-authoring",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["work_package"][
                "queue_id"
            ],
        )
        self.assertEqual(
            "architecture-authoring",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_scaffold"]["work_package"][
                "queue_id"
            ],
        )
        self.assertEqual(
            "architecture-authoring",
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_implementation_routing"][
                "work_package"
            ]["queue_id"],
        )
        self.assertEqual(9, criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["queue_count"])
        self.assertEqual([], criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]["missing_queue_ids"])
        design_routing = criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_design_routing"]
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
        self.assertEqual(design_routing["authoring_summary"]["next_active_work"], design_routing["active_work"])
        implementation_routing = criteria["release-artifact-smoke"]["details"][
            "consumer_bootstrap_implementation_routing"
        ]
        self.assertTrue(implementation_routing["ok"])
        self.assertTrue(implementation_routing["env_auto_repair"]["ok"])
        self.assertEqual("continue_workflow", implementation_routing["env_auto_repair"]["decision"])
        self.assertFalse(implementation_routing["env_auto_repair"]["stop_before_workflow"])
        self.assertTrue(implementation_routing["authority_skill_inventory"]["ok"])
        self.assertEqual("design-derivation", implementation_routing["phase"])
        self.assertEqual("implementation-routing", implementation_routing["workflow_preset"])
        self.assertTrue(implementation_routing["implementation_readiness_preview_ok"])
        self.assertTrue(implementation_routing["readiness_previewed"])
        self.assertFalse(implementation_routing["readiness_ok"])
        self.assertFalse(implementation_routing["implementation_ready"])
        self.assertGreater(implementation_routing["readiness_blocker_count"], 0)
        self.assertIn("governance_scaffold_placeholder", implementation_routing["readiness_blocker_codes"])
        self.assertIn(
            implementation_routing["readiness_next_blocker"]["code"],
            implementation_routing["readiness_blocker_codes"],
        )
        self.assertTrue(implementation_routing["readiness_next_repair_action"])
        self.assertTrue(implementation_routing["advance_previewed"])
        self.assertFalse(implementation_routing["advance_ready"])
        self.assertTrue(implementation_routing["advance_apply_skipped"])
        self.assertEqual("advance_preview_not_ready", implementation_routing["advance_apply_skip_code"])
        self.assertEqual("implementation_advance_preview", implementation_routing["advance_apply_blocked_by"])
        self.assertTrue(implementation_routing["implementation_run_preview_ok"])
        self.assertTrue(implementation_routing["run_previewed"])
        self.assertTrue(implementation_routing["run_preview_skipped"])
        self.assertEqual("advance_apply_not_applied", implementation_routing["run_preview_skip_code"])
        self.assertEqual("implementation_advance_apply", implementation_routing["run_preview_blocked_by"])
        self.assertFalse(implementation_routing["run_required_advance_applied"])
        self.assertFalse(implementation_routing["run_handoff_ready"])
        self.assertEqual("", implementation_routing["run_status"])
        self.assertEqual("", implementation_routing["run_task_id"])
        self.assertEqual({}, implementation_routing["run_snapshot"])
        self.assertEqual({}, implementation_routing["run_next_action"])
        self.assertTrue(implementation_routing["blocked_by_placeholders"])
        self.assertEqual("provided-archive", criteria["release-artifact-smoke"]["details"]["archive_source"])
        self.assertEqual(
            criteria["source-pack-export"]["details"]["archive_sha256"],
            criteria["release-artifact-smoke"]["details"]["archive_sha256"],
        )
        self.assertEqual(
            criteria["source-pack-export"]["details"]["manifest_sha256"],
            criteria["release-artifact-smoke"]["details"]["manifest_sha256"],
        )
        step_ids = {step["id"] for step in payload["steps"]}
        self.assertIn("pack_verification", step_ids)
        self.assertIn("environment_inventory", step_ids)
        self.assertIn("authority_skill_inventory", step_ids)
        self.assertIn("fresh_target_dry_run", step_ids)
        self.assertIn("multi_acceptance_dry_run", step_ids)
        self.assertIn("source_pack_export_check", step_ids)
        self.assertIn("source_pack_export", step_ids)
        self.assertIn("source_pack_export_repeat", step_ids)
        self.assertIn("release_artifact_smoke", step_ids)
        artifact_smoke_step = next(step for step in payload["steps"] if step["id"] == "release_artifact_smoke")
        self.assertIn("--archive", artifact_smoke_step["argv"])


if __name__ == "__main__":
    unittest.main()
