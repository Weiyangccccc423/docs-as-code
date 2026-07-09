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
        step_ids = {step["id"] for step in payload["steps"]}
        self.assertIn("export_artifact", step_ids)
        self.assertIn("unpacked_verify_pack_manifest", step_ids)
        self.assertIn("unpacked_verify_pack", step_ids)
        self.assertIn("unpacked_init_fresh_target_check", step_ids)
        self.assertIn("unpacked_init_fresh_target", step_ids)
        self.assertIn("fresh_target_verify_check", step_ids)
        self.assertIn("fresh_target_governance_status", step_ids)
        self.assertIn("fresh_target_workflow_plan", step_ids)
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
            self.assertIn("unpacked_dry_run", step_ids)


if __name__ == "__main__":
    unittest.main()
