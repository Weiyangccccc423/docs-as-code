import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.export_workflow_pack import run_export


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "scripts" / "export_workflow_pack.py"


class ExportWorkflowPackTest(unittest.TestCase):
    def test_export_creates_manifest_verified_pack_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            output = base / "docs-as-code-workflow-pack"
            archive = base / "docs-as-code-workflow-pack.tar.gz"

            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(output),
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
            self.assertFalse(payload["check"])
            self.assertEqual(str(output.resolve()), payload["output"])
            self.assertEqual(str(archive.resolve()), payload["archive"])
            self.assertTrue(output.is_dir())
            self.assertTrue(archive.is_file())
            self.assertGreater(payload["file_count"], 20)
            self.assertEqual(payload["file_count"], payload["manifest_file_count"])
            self.assertTrue(payload["manifest_verification"]["ok"])
            self.assertEqual([], payload["manifest_verification"]["findings"])
            self.assertEqual([], payload["verification"]["findings"])
            self.assertTrue((output / "pack-manifest.json").is_file())
            self.assertTrue((output / "scripts/export_workflow_pack.py").is_file())
            self.assertTrue((output / "scripts/dry_run_workflow.py").is_file())
            self.assertTrue((output / "tests/test_export_workflow_pack.py").is_file())
            self.assertTrue((output / ".github/workflows/ci.yml").is_file())

            manifest = json.loads((output / "pack-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(1, manifest["schema_version"])
            self.assertEqual("docs-as-code source workflow pack", manifest["source"])
            manifest_paths = {entry["path"] for entry in manifest["files"]}
            self.assertIn("README.md", manifest_paths)
            self.assertIn(".github/workflows/ci.yml", manifest_paths)
            self.assertIn("scripts/export_workflow_pack.py", manifest_paths)
            self.assertIn("tests/test_export_workflow_pack.py", manifest_paths)
            self.assertNotIn("pack-manifest.json", manifest_paths)

            with tarfile.open(archive, "r:gz") as tar:
                names = set(tar.getnames())
            self.assertIn("docs-as-code-workflow-pack/README.md", names)
            self.assertIn("docs-as-code-workflow-pack/pack-manifest.json", names)

    def test_export_is_reproducible_for_same_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            output_one = base / "one" / "first-pack"
            archive_one = base / "one" / "docs-as-code-workflow-pack.tar.gz"
            output_two = base / "two" / "second-pack"
            archive_two = base / "two" / "docs-as-code-workflow-pack.tar.gz"

            first = run_export(output=output_one, archive=archive_one)
            second = run_export(output=output_two, archive=archive_two)

            self.assertTrue(first["ok"], first)
            self.assertTrue(second["ok"], second)
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertEqual(first["archive_size_bytes"], second["archive_size_bytes"])
            self.assertEqual(
                (output_one / "pack-manifest.json").read_bytes(),
                (output_two / "pack-manifest.json").read_bytes(),
            )
            self.assertEqual(archive_one.read_bytes(), archive_two.read_bytes())

    def test_export_check_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preview-pack"
            result = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(output),
                    "--no-archive",
                    "--check",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertFalse(output.exists())
            self.assertIn("README.md", payload["files"])
            self.assertIn("pack-manifest.json", payload["would_write"])


if __name__ == "__main__":
    unittest.main()
