import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.release_readiness import _artifact_smoke_design_authoring_summary_ok


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "scripts" / "release_readiness.py"


class ReleaseReadinessTest(unittest.TestCase):
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
        self.assertGreater(criteria["source-pack-export-check"]["details"]["would_write_count"], 0)
        self.assertTrue(criteria["source-pack-export-check"]["details"]["would_archive"])
        self.assertEqual(
            [],
            criteria["fresh-target-dry-run"]["details"]["target_local_make_coverage"]["missing_step_ids"],
        )
        self.assertEqual(
            [],
            criteria["multi-acceptance-dry-run"]["details"]["target_local_make_coverage"]["missing_step_ids"],
        )
        self.assertTrue(criteria["release-artifact-smoke"]["details"]["fresh_target_init"]["ok"])
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["fresh_target_init"]["target_local_workflow_plan_ok"]
        )
        self.assertTrue(
            criteria["release-artifact-smoke"]["details"]["consumer_bootstrap_product_structure"]["ok"]
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
        self.assertTrue(implementation_routing["start_preview_skipped"])
        self.assertEqual("readiness_preview_not_ready", implementation_routing["start_preview_skip_code"])
        self.assertEqual("implementation_readiness_preview", implementation_routing["start_preview_blocked_by"])
        self.assertTrue(implementation_routing["start_apply_skipped"])
        self.assertEqual("start_preview_not_ready", implementation_routing["start_apply_skip_code"])
        self.assertEqual("implementation_start_preview", implementation_routing["start_apply_blocked_by"])
        self.assertTrue(implementation_routing["closeout_preview_skipped"])
        self.assertEqual("start_apply_not_applied", implementation_routing["closeout_preview_skip_code"])
        self.assertEqual("implementation_start_apply", implementation_routing["closeout_preview_blocked_by"])
        self.assertTrue(implementation_routing["closeout_apply_skipped"])
        self.assertEqual("closeout_preview_not_ready", implementation_routing["closeout_apply_skip_code"])
        self.assertEqual("implementation_closeout_preview", implementation_routing["closeout_apply_blocked_by"])
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
