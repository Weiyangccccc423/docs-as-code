import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.export_workflow_pack import run_export
from scripts.verify_pack_manifest import MANIFEST_NAME, sha256_file, verify_pack_manifest


ROOT = Path(__file__).resolve().parents[1]
VERIFY_MANIFEST = ROOT / "scripts" / "verify_pack_manifest.py"


class PackManifestTest(unittest.TestCase):
    def test_exported_pack_manifest_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "docs-as-code-workflow-pack"

            export_payload = run_export(output=output, archive=None)
            self.assertTrue(export_payload["ok"], export_payload)

            report = verify_pack_manifest(output)

            self.assertTrue(report.ok, report.to_dict())
            self.assertEqual([], report.errors)
            self.assertGreater(report.file_count, 20)
            self.assertEqual(str((output / MANIFEST_NAME).resolve()), report.manifest)

    def test_cli_reports_json_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))

            result = subprocess.run(
                [sys.executable, str(VERIFY_MANIFEST), str(target), "--json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(1, payload["file_count"])
            self.assertEqual([], payload["findings"])

    def test_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))
            (target / "README.md").write_text("changed\n", encoding="utf-8")

            report = verify_pack_manifest(target)

            self.assertFalse(report.ok)
            self.assertTrue(_has_code(report, "pack_manifest_file_hash_mismatch"))

    def test_size_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))
            manifest = _read_manifest(target)
            manifest["files"][0]["size_bytes"] = manifest["files"][0]["size_bytes"] + 1
            _write_manifest(target, manifest)

            report = verify_pack_manifest(target)

            self.assertFalse(report.ok)
            self.assertTrue(_has_code(report, "pack_manifest_file_size_mismatch"))

    def test_executable_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp), rel="scripts/run", text="#!/bin/sh\nexit 0\n", executable=True)
            path = target / "scripts/run"
            path.chmod(path.stat().st_mode & ~stat.S_IXUSR & ~stat.S_IXGRP & ~stat.S_IXOTH)

            report = verify_pack_manifest(target)

            self.assertFalse(report.ok)
            self.assertTrue(_has_code(report, "pack_manifest_file_executable_mismatch"))

    def test_unmanifested_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))
            (target / "extra.txt").write_text("extra\n", encoding="utf-8")

            report = verify_pack_manifest(target)

            self.assertFalse(report.ok)
            self.assertTrue(_has_code(report, "pack_manifest_file_unmanifested"))

    def test_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))
            (target / "README.md").unlink()

            report = verify_pack_manifest(target)

            self.assertFalse(report.ok)
            self.assertTrue(_has_code(report, "pack_manifest_file_missing"))

    def test_duplicate_manifest_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))
            manifest = _read_manifest(target)
            manifest["files"].append(dict(manifest["files"][0]))
            _write_manifest(target, manifest)

            report = verify_pack_manifest(target)

            self.assertFalse(report.ok)
            self.assertTrue(_has_code(report, "pack_manifest_duplicate_path"))

    def test_invalid_manifest_paths_fail(self) -> None:
        cases = (
            ("/absolute.txt", "pack_manifest_invalid_path"),
            ("../escape.txt", "pack_manifest_invalid_path"),
            ("nested\\windows.txt", "pack_manifest_invalid_path"),
            (MANIFEST_NAME, "pack_manifest_reserved_path"),
        )
        for rel, code in cases:
            with self.subTest(rel=rel):
                with tempfile.TemporaryDirectory() as tmp:
                    target = _write_minimal_pack(Path(tmp))
                    manifest = _read_manifest(target)
                    manifest["files"][0]["path"] = rel
                    _write_manifest(target, manifest)

                    report = verify_pack_manifest(target)

                    self.assertFalse(report.ok)
                    self.assertTrue(_has_code(report, code), report.to_dict())

    def test_ignored_generated_files_do_not_fail_manifest_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _write_minimal_pack(Path(tmp))
            cache = target / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "tool.cpython-312.pyc").write_bytes(b"cache")
            (target / ".DS_Store").write_text("local\n", encoding="utf-8")

            report = verify_pack_manifest(target)

            self.assertTrue(report.ok, report.to_dict())


def _write_minimal_pack(
    base: Path,
    *,
    rel: str = "README.md",
    text: str = "ok\n",
    executable: bool = False,
) -> Path:
    target = base / "pack"
    target.mkdir()
    path = target / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    manifest = {
        "schema_version": 1,
        "created_at": "2026-07-07T00:00:00Z",
        "source": "docs-as-code source workflow pack",
        "source_root": str(ROOT),
        "files": [
            {
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "executable": bool(path.stat().st_mode & 0o111),
            }
        ],
    }
    _write_manifest(target, manifest)
    return target


def _read_manifest(target: Path) -> dict[str, object]:
    return json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))


def _write_manifest(target: Path, manifest: dict[str, object]) -> None:
    (target / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _has_code(report: object, code: str) -> bool:
    return any(finding.code == code for finding in report.findings)


if __name__ == "__main__":
    unittest.main()
