import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "smoke_workflow_pack_artifact.py"


class ArtifactSmokeTest(unittest.TestCase):
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
        self.assertTrue(payload["fresh_target_init"]["ok"])
        self.assertEqual("initialized", payload["fresh_target_init"]["phase"])
        self.assertTrue(payload["fresh_target_init"]["target_local_verify_ok"])
        self.assertTrue(payload["fresh_target_init"]["target_local_status_ok"])
        self.assertTrue(payload["fresh_target_init"]["target_local_workflow_plan_ok"])
        self.assertTrue(payload["fresh_target_init"]["runtime_manifest"])
        self.assertTrue(payload["fresh_target_init"]["workflow_pack_snapshot"])
        self.assertTrue(payload["fresh_target_init"]["product_source_manifest"])
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
        self.assertTrue(payload["consumer_bootstrap_product_structure"]["product_structure_apply_ok"])
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
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["start_preview_skipped"])
        self.assertEqual(
            "readiness_preview_not_ready",
            payload["consumer_bootstrap_implementation_routing"]["start_preview_skip_code"],
        )
        self.assertEqual(
            "implementation_readiness_preview",
            payload["consumer_bootstrap_implementation_routing"]["start_preview_blocked_by"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["start_apply_skipped"])
        self.assertEqual(
            "start_preview_not_ready",
            payload["consumer_bootstrap_implementation_routing"]["start_apply_skip_code"],
        )
        self.assertEqual(
            "implementation_start_preview",
            payload["consumer_bootstrap_implementation_routing"]["start_apply_blocked_by"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["closeout_preview_skipped"])
        self.assertEqual(
            "start_apply_not_applied",
            payload["consumer_bootstrap_implementation_routing"]["closeout_preview_skip_code"],
        )
        self.assertEqual(
            "implementation_start_apply",
            payload["consumer_bootstrap_implementation_routing"]["closeout_preview_blocked_by"],
        )
        self.assertTrue(payload["consumer_bootstrap_implementation_routing"]["closeout_apply_skipped"])
        self.assertEqual(
            "closeout_preview_not_ready",
            payload["consumer_bootstrap_implementation_routing"]["closeout_apply_skip_code"],
        )
        self.assertEqual(
            "implementation_closeout_preview",
            payload["consumer_bootstrap_implementation_routing"]["closeout_apply_blocked_by"],
        )
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
