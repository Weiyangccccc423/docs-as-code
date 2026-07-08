import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import dry_run_workflow


ROOT = Path(__file__).resolve().parents[1]
DRY_RUN = ROOT / "scripts" / "dry_run_workflow.py"


class DryRunWorkflowTest(unittest.TestCase):
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
                    "api-authoring": 1,
                    "backend-authoring": 1,
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
            self.assertEqual("TASK-001", payload["implementation_closeout"]["task_id"])
            self.assertTrue(payload["implementation_closeout"]["blocked_without_evidence"])
            self.assertTrue(payload["implementation_closeout"]["ready_with_evidence"])
            self.assertEqual(
                [
                    "verification_log_row_present",
                    "verification_result_passing",
                    "task_verification_links_local_evidence",
                ],
                payload["implementation_closeout"]["blocking_codes_without_evidence"],
            )
            self.assertEqual([], payload["target_local_make_coverage"]["missing_step_ids"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("make_verify_governance", step_ids)
            self.assertIn("make_verify_check", step_ids)
            self.assertIn("make_governance_status", step_ids)
            self.assertIn("make_workflow_plan_initialized", step_ids)
            self.assertIn("product_plan", step_ids)
            self.assertIn("make_product_plan", step_ids)
            self.assertIn("workflow_plan_product_structuring", step_ids)
            self.assertIn("make_workflow_plan_product_structuring", step_ids)
            self.assertIn("product_structure", step_ids)
            self.assertIn("design_plan", step_ids)
            self.assertIn("make_design_plan", step_ids)
            self.assertIn("workflow_plan_design_derivation", step_ids)
            self.assertIn("make_workflow_plan_design_derivation", step_ids)
            self.assertIn("implementation_advance_check", step_ids)
            self.assertIn("implementation_ready_verify_check", step_ids)
            self.assertIn("make_workflow_plan_implementation", step_ids)
            self.assertIn("implementation_plan", step_ids)
            self.assertIn("make_implementation_plan", step_ids)
            self.assertIn("make_check_env", step_ids)
            self.assertIn("make_repair_env_check", step_ids)
            self.assertIn("implementation_closeout_without_evidence", step_ids)
            self.assertIn("implementation_closeout_with_evidence", step_ids)
            self.assertTrue((target / "bin/governance").is_file())
            self.assertTrue((target / "docs/api/endpoints/01-endpoint-contract.md").is_file())

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
                    "api-authoring": 4,
                    "backend-authoring": 4,
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
            self.assertTrue(payload["implementation_closeout"]["blocked_without_evidence"])
            self.assertTrue(payload["implementation_closeout"]["ready_with_evidence"])
            self.assertEqual([], payload["target_local_make_coverage"]["missing_step_ids"])


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
