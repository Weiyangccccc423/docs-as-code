import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "scripts" / "release_readiness.py"


class ReleaseReadinessTest(unittest.TestCase):
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
