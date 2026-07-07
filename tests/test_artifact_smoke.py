import json
import subprocess
import sys
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
        self.assertFalse(payload["target_retained"])
        self.assertGreater(payload["archive_member_count"], 20)
        self.assertIsInstance(payload["archive_sha256"], str)
        self.assertIsInstance(payload["manifest_sha256"], str)
        step_ids = {step["id"] for step in payload["steps"]}
        self.assertIn("export_artifact", step_ids)
        self.assertIn("unpacked_verify_pack_manifest", step_ids)
        self.assertIn("unpacked_verify_pack", step_ids)
        self.assertIn("unpacked_dry_run", step_ids)


if __name__ == "__main__":
    unittest.main()
