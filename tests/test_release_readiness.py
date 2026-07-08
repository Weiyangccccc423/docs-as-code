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
        step_ids = {step["id"] for step in payload["steps"]}
        self.assertIn("pack_verification", step_ids)
        self.assertIn("environment_inventory", step_ids)
        self.assertIn("fresh_target_dry_run", step_ids)
        self.assertIn("multi_acceptance_dry_run", step_ids)
        self.assertIn("source_pack_export_check", step_ids)
        self.assertIn("source_pack_export", step_ids)
        self.assertIn("release_artifact_smoke", step_ids)


if __name__ == "__main__":
    unittest.main()
