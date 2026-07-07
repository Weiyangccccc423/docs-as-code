import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_tree import TARGET_LOCAL_COMMANDS, _iter_workflow_pack_files
from scripts.verify_pack import (
    TARGET_MAKEFILE_REQUIRED_COMMANDS,
    PackFinding,
    PackReport,
    verify_pack,
)
from scripts.verify_governance import (
    TARGET_ENTRY_DOC_GUARDRAILS,
    TARGET_MAKEFILE_REQUIRED_TARGETS,
    TARGET_MAKEFILE_REQUIRED_TARGET_RECIPES,
    WORKFLOW_PACK_REQUIRED_PATHS,
)


ROOT = Path(__file__).resolve().parents[1]


class PackStructureTest(unittest.TestCase):
    def test_target_local_command_contracts_stay_aligned(self) -> None:
        expected_targets = tuple(target for target, _recipe, _description, _writes_state in TARGET_LOCAL_COMMANDS)
        expected_recipes = {
            target: (recipe,)
            for target, recipe, _description, _writes_state in TARGET_LOCAL_COMMANDS
        }
        expected_make_commands = tuple(f"make {target}" for target in expected_targets)

        self.assertEqual(expected_targets, TARGET_MAKEFILE_REQUIRED_TARGETS)
        self.assertEqual(expected_recipes, TARGET_MAKEFILE_REQUIRED_TARGET_RECIPES)
        self.assertEqual(expected_make_commands, TARGET_MAKEFILE_REQUIRED_COMMANDS)
        for command in expected_make_commands:
            self.assertIn(command, TARGET_ENTRY_DOC_GUARDRAILS["README.md"])

    def test_verify_pack_report_objects_reject_unstable_output_shape(self) -> None:
        finding = PackFinding(
            code="pack_required_file_missing",
            message="missing required pack file: README.md",
            path="README.md",
        )
        warning = PackFinding(
            code="pack_reference_warning",
            message="reference should be reviewed",
            path="references/community-practices.md",
            severity="warning",
        )
        source_findings = [finding, warning]
        report = PackReport("/tmp/pack", source_findings)
        source_findings.clear()

        self.assertEqual(
            {
                "code": "pack_required_file_missing",
                "severity": "error",
                "path": "README.md",
                "message": "missing required pack file: README.md",
            },
            finding.to_dict(),
        )
        self.assertEqual(["missing required pack file: README.md"], report.errors)
        self.assertEqual(["reference should be reviewed"], report.warnings)
        self.assertFalse(report.ok)
        self.assertEqual(
            {
                "ok": False,
                "target": "/tmp/pack",
                "errors": ["missing required pack file: README.md"],
                "warnings": ["reference should be reviewed"],
                "findings": [finding.to_dict(), warning.to_dict()],
            },
            report.to_dict(),
        )
        payload = report.to_dict()
        payload_errors = payload["errors"]
        payload_warnings = payload["warnings"]
        payload_findings = payload["findings"]
        self.assertIsInstance(payload_errors, list)
        self.assertIsInstance(payload_warnings, list)
        self.assertIsInstance(payload_findings, list)
        payload_errors.append("mutated error")
        payload_warnings.append("mutated warning")
        self.assertIsInstance(payload_findings[0], dict)
        payload_findings[0]["message"] = "mutated finding"
        self.assertEqual(["missing required pack file: README.md"], report.errors)
        self.assertEqual(["reference should be reviewed"], report.warnings)
        self.assertEqual("missing required pack file: README.md", report.findings[0].message)

        cases = [
            (
                lambda: PackFinding("PackRequiredFileMissing", "message", "README.md"),
                "pack finding code must use lowercase snake_case",
            ),
            (
                lambda: PackFinding("pack_required_file_missing", "", "README.md"),
                "pack finding message must be a non-empty string",
            ),
            (
                lambda: PackFinding("pack_required_file_missing", "message", ""),
                "pack finding path must be a non-empty string",
            ),
            (
                lambda: PackFinding("pack_required_file_missing", "message", "README.md", "info"),
                "pack finding severity must be error or warning",
            ),
            (
                lambda: PackReport("", []),
                "pack report target must be a non-empty string",
            ),
            (
                lambda: PackReport("/tmp/pack", (finding,)),
                "pack report findings must be a list",
            ),
            (
                lambda: PackReport("/tmp/pack", [finding.to_dict()]),
                "pack report findings must contain PackFinding entries",
            ),
        ]
        for factory, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    factory()

    def test_verify_pack_script_json_reports_ok(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_pack.py"), "--json"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(str(ROOT.resolve()), payload["target"])
        self.assertEqual([], payload["errors"])
        self.assertEqual([], payload["findings"])

    def test_verify_pack_script_json_reports_missing_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            target.mkdir()

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/verify_pack.py"), str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("missing required pack file: README.md", payload["errors"])
            self.assertTrue(
                any(
                    finding["code"] == "pack_required_file_missing"
                    and finding["path"] == "README.md"
                    for finding in payload["findings"]
                )
            )

    def test_verify_pack_reports_missing_fresh_target_workflow_smoke_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            smoke_test = target / "tests/test_fresh_target_workflow.py"
            if smoke_test.exists():
                smoke_test.unlink()

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_fresh_target_smoke_test_missing"
                    and finding.path == "tests/test_fresh_target_workflow.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_incomplete_fresh_target_workflow_smoke_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            smoke_test = target / "tests/test_fresh_target_workflow.py"
            smoke_test.write_text(
                smoke_test.read_text(encoding="utf-8").replace(
                    "repair-env-check",
                    "repair-env-preview",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_fresh_target_smoke_test_incomplete"
                    and finding.path == "tests/test_fresh_target_workflow.py"
                    and "repair-env-check" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_fresh_target_smoke_missing_product_structuring_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            smoke_test = target / "tests/test_fresh_target_workflow.py"
            smoke_test.write_text(
                smoke_test.read_text(encoding="utf-8").replace(
                    "advance-product-structuring-check",
                    "advance-product-structure-check",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_fresh_target_smoke_test_incomplete"
                    and finding.path == "tests/test_fresh_target_workflow.py"
                    and "advance-product-structuring-check" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_fresh_target_smoke_missing_design_scaffold_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            smoke_test = target / "tests/test_fresh_target_workflow.py"
            smoke_test.write_text(
                smoke_test.read_text(encoding="utf-8").replace(
                    "docs/architecture/01-system-context.md",
                    "docs/architecture/01-context-preview.md",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_fresh_target_smoke_test_incomplete"
                    and finding.path == "tests/test_fresh_target_workflow.py"
                    and "docs/architecture/01-system-context.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_dry_run_workflow_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/dry_run_workflow.py"
            if script.exists():
                script.unlink()

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_dry_run_workflow_missing"
                    and finding.path == "scripts/dry_run_workflow.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_incomplete_dry_run_workflow_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/dry_run_workflow.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    "implementation_advance_check",
                    "implementation_gate_preview",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_dry_run_workflow_incomplete"
                    and finding.path == "scripts/dry_run_workflow.py"
                    and "implementation_advance_check" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_source_pack_export_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/export_workflow_pack.py"
            if script.exists():
                script.unlink()

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_source_pack_export_missing"
                    and finding.path == "scripts/export_workflow_pack.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_incomplete_source_pack_export_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/export_workflow_pack.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    "pack-manifest.json",
                    "source-manifest.json",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_source_pack_export_incomplete"
                    and finding.path == "scripts/export_workflow_pack.py"
                    and "pack-manifest.json" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_pack_manifest_verify_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/verify_pack_manifest.py"
            if script.exists():
                script.unlink()

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_required_file_missing"
                    and finding.path == "scripts/verify_pack_manifest.py"
                    for finding in report.findings
                )
            )
            self.assertTrue(
                any(
                    finding.code == "pack_manifest_verify_missing"
                    and finding.path == "scripts/verify_pack_manifest.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_incomplete_pack_manifest_verify_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/verify_pack_manifest.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    "pack_manifest_file_unmanifested",
                    "pack_manifest_file_not_listed",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_manifest_verify_incomplete"
                    and finding.path == "scripts/verify_pack_manifest.py"
                    and "pack_manifest_file_unmanifested" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_artifact_smoke_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/smoke_workflow_pack_artifact.py"
            if script.exists():
                script.unlink()

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_artifact_smoke_missing"
                    and finding.path == "scripts/smoke_workflow_pack_artifact.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_incomplete_artifact_smoke_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/smoke_workflow_pack_artifact.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    "unpacked_dry_run",
                    "unpacked_preview",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_artifact_smoke_incomplete"
                    and finding.path == "scripts/smoke_workflow_pack_artifact.py"
                    and "unpacked_dry_run" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_artifact_smoke_missing_manifest_verifier_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/smoke_workflow_pack_artifact.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    "unpacked_verify_pack_manifest",
                    "unpacked_manifest_preview",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_artifact_smoke_incomplete"
                    and finding.path == "scripts/smoke_workflow_pack_artifact.py"
                    and "unpacked_verify_pack_manifest" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_release_readiness_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/release_readiness.py"
            if script.exists():
                script.unlink()

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_release_readiness_missing"
                    and finding.path == "scripts/release_readiness.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_incomplete_release_readiness_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/release_readiness.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    "release_ready",
                    "handoff_ready",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_release_readiness_incomplete"
                    and finding.path == "scripts/release_readiness.py"
                    and "release_ready" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\nverify-pack: test\n\tpython3 scripts/verify_pack.py\n\tpython3 scripts/check_env.py\n",
                    "\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_missing"
                    and finding.path == "Makefile"
                    and "verify-pack" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_dry_run_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\ndry-run:\n\tpython3 scripts/dry_run_workflow.py --json\n",
                    "\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_missing"
                    and finding.path == "Makefile"
                    and "dry-run" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_package_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\npackage:\n\tpython3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json\n",
                    "\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_missing"
                    and finding.path == "Makefile"
                    and "package" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_artifact_smoke_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\nartifact-smoke:\n\tpython3 scripts/smoke_workflow_pack_artifact.py --json\n",
                    "\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_missing"
                    and finding.path == "Makefile"
                    and "artifact-smoke" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_release_check_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\nrelease-check:\n\tpython3 scripts/release_readiness.py --json\n",
                    "\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_missing"
                    and finding.path == "Makefile"
                    and "release-check" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_makefile_target_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\tpython3 scripts/check_env.py\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_recipe_missing"
                    and finding.path == "Makefile"
                    and "verify-pack" in finding.message
                    and "python3 scripts/check_env.py" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_dry_run_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "temporary target",
                    "throwaway target",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_dry_run_doc_missing"
                    and finding.path == "README.md"
                    and "temporary target" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_source_pack_export_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "pack-manifest.json",
                    "export-manifest.json",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_source_pack_export_doc_missing"
                    and finding.path == "README.md"
                    and "pack-manifest.json" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_artifact_smoke_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "unpacks the tar.gz artifact",
                    "checks the archive",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_artifact_smoke_doc_missing"
                    and finding.path == "README.md"
                    and "unpacks the tar.gz artifact" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_release_readiness_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "references/release-readiness-checklist.md",
                    "references/release-checklist.md",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_release_readiness_doc_missing"
                    and finding.path == "README.md"
                    and "references/release-readiness-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_pack_manifest_verify_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json",
                    "python3 scripts/check_export_manifest.py dist/docs-as-code-workflow-pack --json",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_manifest_verify_doc_missing"
                    and finding.path == "README.md"
                    and "python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json"
                    in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_readme_quick_start_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "bin/governance status /path/to/new-project\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_readme_quick_start_command_missing"
                    and finding.path == "README.md"
                    and "bin/governance status" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_readme_agent_automation_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "bin/governance verify /path/to/new-project --check --json\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_readme_agent_automation_command_missing"
                    and finding.path == "README.md"
                    and "verify /path/to/new-project --check --json" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_runtime_local_commands_payload_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            gates = target / "scripts/gates.py"
            gates.write_text(
                gates.read_text(encoding="utf-8").replace(
                    '"local_commands": target_local_commands_payload(cwd=result.target),',
                    '"local_commands": [],',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_continuation_call_missing"
                    and finding.path == "scripts/gates.py"
                    and "target_local_commands_payload" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_runtime_next_actions_payload_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            gates = target / "scripts/gates.py"
            gates.write_text(
                gates.read_text(encoding="utf-8").replace(
                    'payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)',
                    'payload["next_actions"] = []',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_continuation_call_missing"
                    and finding.path == "scripts/gates.py"
                    and "next_actions_payload" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_import_action_schema_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '        "skills": ("archiving-product-document", "verifying-governance-docs"),\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_schema_missing"
                    and finding.path == "scripts/workflow_actions.py"
                    and "PRODUCT_IMPORT_ACTIONS action 0" in finding.message
                    and "skills" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_import_action_approval_schema_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '        "approval_required": False,\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_schema_missing"
                    and finding.path == "scripts/workflow_actions.py"
                    and "PRODUCT_IMPORT_ACTIONS action 0" in finding.message
                    and "approval_required" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_advance_action_schema_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '            "cwd": cwd,\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_schema_missing"
                    and finding.path == "scripts/workflow_actions.py"
                    and "_advance_actions() return action 0" in finding.message
                    and "cwd" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_workflow_action_missing_primary_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '            "designing-api-contracts",\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_skill_mismatch"
                    and finding.path == "scripts/workflow_actions.py"
                    and "design-derivation" in finding.message
                    and "designing-api-contracts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_workflow_action_path_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    'f"{TARGET_WORKFLOW_ROOT}/workflows/04-design-derivation.md"',
                    'f"{TARGET_WORKFLOW_ROOT}/workflows/05-verification-and-drift-control.md"',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_workflow_mismatch"
                    and finding.path == "scripts/workflow_actions.py"
                    and "design-derivation" in finding.message
                    and "workflows/04-design-derivation.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_product_import_action_command_argv_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '"command": "bin/governance product mark-ready . --reviewed --method manual-reviewed-markdown --check --json",',
                    '"command": "bin/governance status . --json",',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_command_mismatch"
                    and finding.path == "scripts/workflow_actions.py"
                    and "PRODUCT_IMPORT_ACTIONS action 0" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_advance_action_command_argv_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/workflow_actions.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '"command": _command_text(preflight_argv),',
                    '"command": "bin/governance status . --json",',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_action_command_mismatch"
                    and finding.path == "scripts/workflow_actions.py"
                    and "_advance_actions() return action 0" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_target_local_command_schema_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/bootstrap_tree.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '            "writes_state": writes_state,\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_local_command_schema_missing"
                    and finding.path == "scripts/bootstrap_tree.py"
                    and "writes_state" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_target_local_command_approval_schema_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/bootstrap_tree.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '            "approval_required": False,\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_local_command_schema_missing"
                    and finding.path == "scripts/bootstrap_tree.py"
                    and "approval_required" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_target_local_command_make_argv_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/bootstrap_tree.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '            "command": f"make {target}",\n',
                    '            "command": "make verify-governance",\n',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_local_command_command_mismatch"
                    and finding.path == "scripts/bootstrap_tree.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_target_local_command_source_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/bootstrap_tree.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '    (\n        "check-env",\n        "bin/governance env --target .",\n'
                    '        "inventory local governance tools",\n        False,\n    ),\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_local_command_source_missing"
                    and finding.path == "scripts/bootstrap_tree.py"
                    and "check-env" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_invalid_target_local_command_source_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/bootstrap_tree.py"
            script.write_text(
                script.read_text(encoding="utf-8").replace(
                    '        True,\n    ),\n    (\n        "verify-check",',
                    '        "yes",\n    ),\n    (\n        "verify-check",',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_local_command_source_invalid"
                    and finding.path == "scripts/bootstrap_tree.py"
                    and "writes_state" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_target_makefile_command_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "templates/root/README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `make governance-status` - print workflow state as JSON.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_makefile_command_doc_missing"
                    and finding.path == "templates/root/README.md"
                    and "make governance-status" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_runtime_strategy_makefile_command_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            strategy = target / "references/runtime-strategy.md"
            strategy.write_text(
                strategy.read_text(encoding="utf-8").replace(
                    "make repair-env-check\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_target_makefile_command_doc_missing"
                    and finding.path == "references/runtime-strategy.md"
                    and "make repair-env-check" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_environment_repair_doc_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            router = target / "skills/using-governance-workflow/SKILL.md"
            router.write_text(
                router.read_text(encoding="utf-8").replace("repair_commands", "package_repair_actions"),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_env_repair_doc_field_missing"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "repair_commands" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_runtime_refresh_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            strategy = target / "references/runtime-strategy.md"
            strategy.write_text(
                strategy.read_text(encoding="utf-8").replace(
                    " and `would_remove`",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_refresh_doc_missing"
                    and finding.path == "references/runtime-strategy.md"
                    and "would_remove" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_archive_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/archiving-product-document/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    ", inspect `would_update`,",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_product_archive_doc_missing"
                    and finding.path == "skills/archiving-product-document/SKILL.md"
                    and "would_update" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_archive_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/archiving-product-document/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/product-archive-checklist.md`",
                    "the product archive checklist",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_product_reference_doc_missing"
                    and finding.path == "skills/archiving-product-document/SKILL.md"
                    and "references/product-archive-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_archive_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/product-archive-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "source path, archived path, byte size, SHA-256, conversion method, import status, and `can_derive_design`",
                    "source path and archive path",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/product-archive-checklist.md"
                    and "Manifest Evidence" in finding.message
                    and "SHA-256" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_structure_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/structuring-product-requirements/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`would_create`, `would_skip`, and `would_index`",
                    "`would_create` and `would_skip`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_product_structure_doc_missing"
                    and finding.path == "skills/structuring-product-requirements/SKILL.md"
                    and "would_index" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_structure_command_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "product structure",
                    "product fill",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_product_structure_doc_missing"
                    and finding.path == "workflows/03-product-structuring.md"
                    and "product structure" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_design_scaffold_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/using-governance-workflow/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`would_create`, `would_skip`, and `would_index`",
                    "`would_create` and `would_skip`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_scaffold_doc_missing"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "would_index" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_design_plan_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/using-governance-workflow/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "run `bin/governance design plan <target> --json`",
                    "inspect design authoring manually",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_plan_doc_missing"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "design plan" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_api_candidates_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design api-candidates <target> --json`",
                    "`bin/governance design plan <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_api_candidates_doc_missing"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    and "design api-candidates" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_api_authoring_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design api-authoring <target> --json`",
                    "`bin/governance design api-candidates <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_api_authoring_doc_missing"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    and "design api-authoring" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_backend_authoring_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-backend-modules/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design backend-authoring <target> --json`",
                    "`bin/governance design plan <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_backend_authoring_doc_missing"
                    and finding.path == "skills/designing-backend-modules/SKILL.md"
                    and "design backend-authoring" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_frontend_authoring_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-frontend-modules/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design frontend-authoring <target> --json`",
                    "`bin/governance design plan <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_frontend_authoring_doc_missing"
                    and finding.path == "skills/designing-frontend-modules/SKILL.md"
                    and "design frontend-authoring" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_test_strategy_authoring_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-test-strategy/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design test-strategy-authoring <target> --json`",
                    "`bin/governance design plan <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_test_strategy_authoring_doc_missing"
                    and finding.path == "skills/designing-test-strategy/SKILL.md"
                    and "design test-strategy-authoring" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_planning_authoring_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/planning-implementation-work/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design implementation-planning-authoring <target> --json`",
                    "`bin/governance design plan <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_implementation_planning_authoring_doc_missing"
                    and finding.path == "skills/planning-implementation-work/SKILL.md"
                    and "design implementation-planning-authoring" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_architecture_decisions_authoring_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/capturing-architecture-decisions/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`bin/governance design architecture-decisions-authoring <target> --json`",
                    "`bin/governance design plan <target> --json`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_architecture_decisions_authoring_doc_missing"
                    and finding.path == "skills/capturing-architecture-decisions/SKILL.md"
                    and "design architecture-decisions-authoring" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_scaffold_continuation_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/structuring-product-requirements/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    " If `next_actions_blocked_by` is present, keep `next_actions` for later and do not run downstream state-writing actions until blockers are resolved.",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_scaffold_continuation_doc_missing"
                    and finding.path == "skills/structuring-product-requirements/SKILL.md"
                    and "next_actions_blocked_by" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_design_scaffold_continuation_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    " If `scaffold_phase.matches` is false, follow returned `next_actions` to advance recorded phases in order before treating the scaffold as current-phase work.",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_scaffold_continuation_doc_missing"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    and "scaffold_phase.matches" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_handoff_doc_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/planning-implementation-work/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "its `A-NNN` ID is mapped in `docs/tests/02-acceptance-matrix.md`, and ",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_implementation_handoff_doc_missing"
                    and finding.path == "skills/planning-implementation-work/SKILL.md"
                    and "docs/tests/02-acceptance-matrix.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_design_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "3. Read `references/architecture-methods.md` and `references/architecture-quality-checklist.md`, then create or complete `docs/architecture/` views:",
                    "3. Read `references/architecture-quality-checklist.md`, then create or complete `docs/architecture/` views:",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "references/architecture-methods.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_api_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/architecture-methods.md`",
                    "the architecture methods reference",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    and "references/architecture-methods.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_api_design_checklist_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/api-design-checklist.md`",
                    "the API design checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    and "references/api-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_architecture_quality_checklist_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-system-architecture/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/architecture-quality-checklist.md`",
                    "the architecture quality checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-system-architecture/SKILL.md"
                    and "references/architecture-quality-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_adr_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/capturing-architecture-decisions/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/architecture-methods.md`",
                    "the architecture methods reference",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/capturing-architecture-decisions/SKILL.md"
                    and "references/architecture-methods.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_adr_checklist_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/capturing-architecture-decisions/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/architecture-decision-record-checklist.md`",
                    "the architecture decision record checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/capturing-architecture-decisions/SKILL.md"
                    and "references/architecture-decision-record-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_adr_checklist_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/architecture-decision-record-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "credible considered options",
                    "options",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/architecture-decision-record-checklist.md"
                    and "Options and Rationale" in finding.message
                    and "credible considered options" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_method_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/architecture-methods.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "Reference: `https://spec.openapis.org/oas/latest.html`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/architecture-methods.md"
                    and "OpenAPI" in finding.message
                    and "https://spec.openapis.org/oas/latest.html" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_api_design_checklist_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/api-design-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "https://www.rfc-editor.org/rfc/rfc9457.html",
                    "https://example.invalid/problem-details",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/api-design-checklist.md"
                    and "Error Responses" in finding.message
                    and "https://www.rfc-editor.org/rfc/rfc9457.html" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_architecture_quality_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/architecture-quality-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "source, stimulus, environment, affected artifact, response, and response measure",
                    "source and response",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/architecture-quality-checklist.md"
                    and "Quality Scenarios" in finding.message
                    and "affected artifact" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_backend_checklist_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/backend-design-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "## Runtime Flow\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/backend-design-checklist.md"
                    and "Runtime Flow" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_backend_consistency_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/backend-design-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "- Are transaction boundaries, consistency expectations, and concurrency conflicts documented for state-changing operations?\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/backend-design-checklist.md"
                    and "transaction boundaries, consistency expectations, and concurrency conflicts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_data_model_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-data-models/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/backend-design-checklist.md`",
                    "the backend design checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-data-models/SKILL.md"
                    and "references/backend-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_data_model_design_checklist_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-data-models/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/data-model-design-checklist.md`",
                    "the data model design checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-data-models/SKILL.md"
                    and "references/data-model-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_backend_data_model_checklist_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-backend-modules/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/data-model-design-checklist.md`",
                    "the data model design checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-backend-modules/SKILL.md"
                    and "references/data-model-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_data_model_design_checklist_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/data-model-design-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "transaction boundaries, isolation expectations, lock or version strategy, and conflict outcomes",
                    "transaction boundaries and conflict outcomes",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/data-model-design-checklist.md"
                    and "State and Concurrency" in finding.message
                    and "isolation expectations" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_backend_operability_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-backend-modules/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/backend-operability-checklist.md`",
                    "the backend operability checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-backend-modules/SKILL.md"
                    and "references/backend-operability-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_readiness_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/planning-implementation-work/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/implementation-readiness-checklist.md`",
                    "the implementation readiness checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/planning-implementation-work/SKILL.md"
                    and "references/implementation-readiness-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_security_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/security-design-checklist.md`",
                    "the security design checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    and "references/security-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_test_strategy_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-test-strategy/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/test-strategy-checklist.md`",
                    "the test strategy checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-test-strategy/SKILL.md"
                    and "references/test-strategy-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_frontend_interaction_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-frontend-modules/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/frontend-interaction-checklist.md`",
                    "the frontend interaction checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_design_reference_doc_missing"
                    and finding.path == "skills/designing-frontend-modules/SKILL.md"
                    and "references/frontend-interaction-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_requirements_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/structuring-product-requirements/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/product-requirements-checklist.md`",
                    "the product requirements checklist",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_product_reference_doc_missing"
                    and finding.path == "skills/structuring-product-requirements/SKILL.md"
                    and "references/product-requirements-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_requirements_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/product-requirements-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "clear, necessary, feasible, unambiguous, verifiable, and traceable",
                    "clear and traceable",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/product-requirements-checklist.md"
                    and "Requirement Quality" in finding.message
                    and "necessary" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_backend_operability_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/backend-operability-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "logs, metrics, traces, and audit events",
                    "logs and metrics",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/backend-operability-checklist.md"
                    and "Observability Signals" in finding.message
                    and "traces" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_frontend_interaction_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/frontend-interaction-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "role, state, property, keyboard interaction, and focus-management behavior",
                    "role and state",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/frontend-interaction-checklist.md"
                    and "Component Behavior" in finding.message
                    and "focus-management" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_readiness_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/implementation-readiness-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "working code, synchronized docs, passing verification commands",
                    "working code",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/implementation-readiness-checklist.md"
                    and "Definition of Done" in finding.message
                    and "synchronized docs" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_execution_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/planning-implementation-work/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/implementation-execution-checklist.md`",
                    "the implementation execution checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_implementation_reference_doc_missing"
                    and finding.path == "skills/planning-implementation-work/SKILL.md"
                    and "references/implementation-execution-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_execution_skill_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/executing-implementation-task/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/implementation-execution-checklist.md`",
                    "the implementation execution checklist",
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_implementation_reference_doc_missing"
                    and finding.path == "skills/executing-implementation-task/SKILL.md"
                    and "references/implementation-execution-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_implementation_execution_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/implementation-execution-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "preferring target-local `local_commands[].argv`",
                    "preferring local commands",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/implementation-execution-checklist.md"
                    and "Verification Execution" in finding.message
                    and "local_commands[].argv" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_test_strategy_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/test-strategy-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "unit tests, integration tests, contract tests, and end-to-end tests",
                    "unit tests and end-to-end tests",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/test-strategy-checklist.md"
                    and "Test Portfolio" in finding.message
                    and "contract tests" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_security_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/security-design-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "object-level authorization, function-level authorization, and mass-assignment risks",
                    "function-level authorization risks",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/security-design-checklist.md"
                    and "object-level authorization" in finding.message
                    and "mass-assignment" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_documented_verification_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "make verify-pack\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_verification_command_missing"
                    and finding.path == "AGENTS.md"
                    and "make verify-pack" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_governance_verification_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/verifying-governance-docs/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/governance-verification-checklist.md`",
                    "the governance verification checklist",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_verification_reference_doc_missing"
                    and finding.path == "skills/verifying-governance-docs/SKILL.md"
                    and "references/governance-verification-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_governance_verification_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/governance-verification-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "matching `--check --json` preflight",
                    "matching preflight",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/governance-verification-checklist.md"
                    and "Command Discipline" in finding.message
                    and "--check --json" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_purpose_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    " Do not treat it as a generated target project.",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_purpose_guardrail_missing"
                    and finding.path == "AGENTS.md"
                    and "generated target project" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_baseline_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    " Commit after each coherent change to scripts, skills, workflows, or templates so future workflow behavior is traceable.",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_baseline_guardrail_missing"
                    and finding.path == "AGENTS.md"
                    and "commit after each coherent change" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_editing_rule_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "- Put deterministic behavior in `scripts/`.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_editing_rule_missing"
                    and finding.path == "AGENTS.md"
                    and "deterministic behavior" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_required_reading_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "1. `workflows/00-overview.md`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_required_reading_missing"
                    and finding.path == "AGENTS.md"
                    and "workflows/00-overview.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_verification_report_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "Before claiming completion, report the verification commands and results.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_verification_guardrail_missing"
                    and finding.path == "AGENTS.md"
                    and "verification commands and results" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_phase_workflow_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/01-empty-repo-initialization.md"
            text = workflow.read_text(encoding="utf-8")
            self.assertIn("## Verification", text)
            workflow.write_text(
                re.sub(r"\n## Verification\n.*?(?=\n## Stop Conditions\n)", "\n", text, flags=re.S),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_section_missing"
                    and finding.path == "workflows/01-empty-repo-initialization.md"
                    and "Verification" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_repository_initialization_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/initializing-governance-repo/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "`references/repository-initialization-checklist.md`",
                    "the repository initialization checklist",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_initialization_reference_doc_missing"
                    and finding.path == "skills/initializing-governance-repo/SKILL.md"
                    and "references/repository-initialization-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_repository_initialization_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/repository-initialization-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "bin/governance init --check --target <target> --product <product-doc> --json",
                    "bin/governance init --check",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/repository-initialization-checklist.md"
                    and "Target Safety" in finding.message
                    and "--product <product-doc>" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_workflow_heading_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "# Phase 03: Product Structuring",
                    "# Phase 04: Product Structuring",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_phase_heading_mismatch"
                    and finding.path == "workflows/03-product-structuring.md"
                    and "Phase 03" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_workflow_title_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "# Phase 04: Design Derivation",
                    "# Phase 04: Backend Design",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_phase_title_mismatch"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "Design Derivation" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_workflow_section_order_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                "\n".join(
                    [
                        "# Phase 03: Product Structuring",
                        "",
                        "## Input",
                        "",
                        "## Skills",
                        "",
                        "- `structuring-product-requirements`",
                        "",
                        "## Procedure",
                        "",
                        "## Verification",
                        "",
                        "## Output",
                        "",
                        "## Stop Conditions",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_section_order_mismatch"
                    and finding.path == "workflows/03-product-structuring.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_empty_phase_workflow_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                "\n".join(
                    [
                        "# Phase 03: Product Structuring",
                        "",
                        "## Input",
                        "",
                        "- `docs/product/core/PRD.md`",
                        "",
                        "## Skills",
                        "",
                        "- `structuring-product-requirements`",
                        "",
                        "## Procedure",
                        "",
                        "1. Structure product requirements.",
                        "",
                        "## Output",
                        "",
                        "## Verification",
                        "",
                        "- Run governance verification.",
                        "",
                        "## Stop Conditions",
                        "",
                        "- Stop on product ambiguity.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_section_empty"
                    and finding.path == "workflows/03-product-structuring.md"
                    and "Output" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_local_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/00-overview.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8")
                + "\nBroken source-pack link: [Missing](missing-reference.md)\n",
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_local_markdown_link_missing"
                    and finding.path == "workflows/00-overview.md"
                    and "workflows/missing-reference.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_unknown_skill_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "`designing-api-contracts`",
                    "`missing-api-skill`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_skill_reference_missing"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "missing-api-skill" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_non_executable_runtime_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance"
            wrapper.chmod(0o644)

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_file_not_executable"
                    and finding.path == "bin/governance"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_wrapper_command_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance-verify"
            wrapper.write_text(
                wrapper.read_text(encoding="utf-8").replace(
                    'python3 "$ROOT_DIR/scripts/governance_cli.py" verify "$@"',
                    'python3 "$ROOT_DIR/scripts/governance_cli.py" status "$@"',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_wrapper_command_mismatch"
                    and finding.path == "bin/governance-verify"
                    and "governance_cli.py\" verify" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_wrapper_missing_shell_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance"
            wrapper.write_text(
                wrapper.read_text(encoding="utf-8").replace("set -euo pipefail\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_wrapper_guard_missing"
                    and finding.path == "bin/governance"
                    and "set -euo pipefail" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_wrapper_missing_root_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance"
            wrapper.write_text(
                wrapper.read_text(encoding="utf-8").replace(
                    'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_wrapper_root_missing"
                    and finding.path == "bin/governance"
                    and "ROOT_DIR" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_invalid_workflow_pack_file_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/product/core/PRD.md"
            template.write_bytes(b"\xff")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_file_invalid_encoding"
                    and finding.path == "templates/docs/product/core/PRD.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_python_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            script.write_text("def broken(:\n    pass\n", encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_python_syntax_invalid"
                    and finding.path == "scripts/governance_cli.py"
                    and "invalid Python syntax" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_bootstrap_runtime_script_list_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/bootstrap_tree.py"
            text = script.read_text(encoding="utf-8")
            self.assertIn('    "workflow_actions.py",\n', text)
            script.write_text(text.replace('    "workflow_actions.py",\n', "", 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_file_list_mismatch"
                    and finding.path == "scripts/bootstrap_tree.py"
                    and "RUNTIME_SCRIPT_FILES" in finding.message
                    and "workflow_actions.py" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_verifier_runtime_script_list_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/verify_governance.py"
            text = script.read_text(encoding="utf-8")
            self.assertIn('    "workflow_actions.py",\n', text)
            script.write_text(text.replace('    "workflow_actions.py",\n', "", 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_file_list_mismatch"
                    and finding.path == "scripts/verify_governance.py"
                    and "RUNTIME_REQUIRED_SCRIPT_FILES" in finding.message
                    and "workflow_actions.py" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_verifier_workflow_pack_required_path_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/verify_governance.py"
            text = script.read_text(encoding="utf-8")
            self.assertIn('    "references/runtime-strategy.md",\n', text)
            script.write_text(text.replace('    "references/runtime-strategy.md",\n', "", 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_snapshot_unverified_file"
                    and finding.path == "references/runtime-strategy.md"
                    and "references/runtime-strategy.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_non_literal_workflow_pack_required_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/verify_governance.py"
            text = script.read_text(encoding="utf-8")
            original = "WORKFLOW_PACK_REQUIRED_PATHS = (\n"
            self.assertIn(original, text)
            script.write_text(text.replace(original, "WORKFLOW_PACK_REQUIRED_PATHS = tuple(\n", 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_pack_required_paths_not_literal"
                    and finding.path == "scripts/verify_governance.py"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_governance_cli_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            original = 'status = sub.add_parser("status", help="Show target governance workflow state.")'
            replacement = 'status = sub.add_parser("state", help="Show target governance workflow state.")'
            text = script.read_text(encoding="utf-8")
            self.assertIn(original, text)
            script.write_text(text.replace(original, replacement, 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_governance_cli_command_missing"
                    and finding.path == "scripts/governance_cli.py"
                    and "status" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_governance_cli_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            original = 'runtime_refresh = runtime_sub.add_parser(\n        "refresh",'
            replacement = 'runtime_refresh = runtime_sub.add_parser(\n        "repair",'
            text = script.read_text(encoding="utf-8")
            self.assertIn(original, text)
            script.write_text(text.replace(original, replacement, 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_governance_cli_subcommand_missing"
                    and finding.path == "scripts/governance_cli.py"
                    and "runtime" in finding.message
                    and "refresh" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_product_structure_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            original = 'structure = product_sub.add_parser("structure", help="Fill scaffolded product chapters from explicit PRD sections.")'
            replacement = 'structure = product_sub.add_parser("fill", help="Fill scaffolded product chapters from explicit PRD sections.")'
            text = script.read_text(encoding="utf-8")
            self.assertIn(original, text)
            script.write_text(text.replace(original, replacement, 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_governance_cli_subcommand_missing"
                    and finding.path == "scripts/governance_cli.py"
                    and "product" in finding.message
                    and "structure" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_design_plan_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            original = 'design_plan = design_sub.add_parser(\n        "plan",'
            replacement = 'design_plan = design_sub.add_parser(\n        "queue",'
            text = script.read_text(encoding="utf-8")
            self.assertIn(original, text)
            script.write_text(text.replace(original, replacement, 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_governance_cli_subcommand_missing"
                    and finding.path == "scripts/governance_cli.py"
                    and "design" in finding.message
                    and "plan" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_workflow_order_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "3. `workflows/03-product-structuring.md`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_order_mismatch"
                    and finding.path == "README.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_package_layout_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "├── references/   # supporting methods and practice references\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_package_layout_missing_directory"
                    and finding.path == "README.md"
                    and "references/" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_package_layout_stale_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "├── skills/       # agent skills used by the workflow\n",
                    "├── skills/       # agent skills used by the workflow\n├── plugins/      # stale plugin experiments\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_package_layout_stale_directory"
                    and finding.path == "README.md"
                    and "plugins/" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_sequential_advance_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "`advance` records adjacent transitions one phase at a time and cannot skip phases; "
                    "use `gate --json` for repeated checks or earlier-phase audits instead of moving the "
                    "recorded phase backward.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_advance_doc_missing"
                    and finding.path == "README.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_forward_only_phase_advance_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "one phase at a time",
                    "forward-only",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_advance_doc_ambiguous"
                    and finding.path == "workflows/00-overview.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_overview_phase_map_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "| 03 | Product structuring | `structuring-product-requirements` |\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_map_mismatch"
                    and finding.path == "workflows/00-overview.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_overview_phase_map_title_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "| 04 | Design derivation |",
                    "| 04 | Backend design |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_map_title_mismatch"
                    and finding.path == "workflows/00-overview.md"
                    and "04" in finding.message
                    and "Design Derivation" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_primary_skill_missing_from_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "- API contract: `designing-api-contracts`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_primary_skill_missing"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "designing-api-contracts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_primary_skill_order_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "`designing-api-contracts`, `designing-backend-modules`",
                    "`designing-backend-modules`, `designing-api-contracts`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_primary_skill_order_mismatch"
                    and finding.path == "workflows/00-overview.md"
                    and "04" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_map_missing_primary_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "| 03 | Product structuring | `structuring-product-requirements` |\n",
                    "| 03 | Product structuring | |\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_map_primary_skill_missing"
                    and finding.path == "workflows/00-overview.md"
                    and "03" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_router_missing_phase_primary_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            router = target / "skills/using-governance-workflow/SKILL.md"
            router.write_text(
                router.read_text(encoding="utf-8").replace(
                    "`designing-api-contracts`, then ",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_router_primary_skill_missing"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "designing-api-contracts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_router_primary_skill_order_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            router = target / "skills/using-governance-workflow/SKILL.md"
            router.write_text(
                router.read_text(encoding="utf-8").replace(
                    "`designing-api-contracts`, then `designing-backend-modules`",
                    "`designing-backend-modules`, then `designing-api-contracts`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_router_primary_skill_order_mismatch"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "04" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_workflow_routing_reference_doc_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            router = target / "skills/using-governance-workflow/SKILL.md"
            router.write_text(
                router.read_text(encoding="utf-8").replace(
                    "`references/workflow-routing-checklist.md`",
                    "the workflow routing checklist",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_routing_reference_doc_missing"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "references/workflow-routing-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_workflow_routing_reference_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            reference = target / "references/workflow-routing-checklist.md"
            reference.write_text(
                reference.read_text(encoding="utf-8").replace(
                    "`local_commands[].argv` and `next_actions[].argv` executed from their reported `cwd`",
                    "`local_commands` and `next_actions` are useful",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_method_reference_baseline_missing"
                    and finding.path == "references/workflow-routing-checklist.md"
                    and "Machine-Readable Continuation" in finding.message
                    and "next_actions[].argv" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_unrouted_reference_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "Use `references/community-practices.md` to calibrate this workflow against recognized docs-as-code, architecture, API, ADR, quality, and security practices without treating any single framework as a rigid template. ",
                    "",
                    1,
                ),
                encoding="utf-8",
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `references/community-practices.md`: external practice calibration.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_reference_unrouted"
                    and finding.path == "references/community-practices.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_reference_index_missing_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `references/backend-design-checklist.md`: backend and data-design completion checklist.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_reference_index_missing"
                    and finding.path == "README.md"
                    and "references/backend-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_skill_index_missing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `skills/designing-data-models/SKILL.md`: persistence and lifecycle design.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_skill_index_missing"
                    and finding.path == "README.md"
                    and "skills/designing-data-models/SKILL.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_index_entry_missing_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `skills/designing-data-models/SKILL.md`: persistence and lifecycle design.\n",
                    "- `skills/designing-data-models/SKILL.md`:   \n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_index_entry_description_missing"
                    and finding.path == "README.md"
                    and "Skill Files" in finding.message
                    and "skills/designing-data-models/SKILL.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_unrouted_template_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `templates/docs/decisions/ADR-template.md`: ADR shape for architecture decisions.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_unrouted"
                    and finding.path == "templates/docs/decisions/ADR-template.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_template_index_missing_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `templates/root/README.md`: generated target root README shape.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_index_missing"
                    and finding.path == "README.md"
                    and "templates/root/README.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/decisions/ADR-template.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace("- Related modules: TBD\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/decisions/ADR-template.md"
                    and "- Related modules: TBD" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_template_section_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/decisions/ADR-template.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace("## References\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_section_missing"
                    and finding.path == "templates/docs/decisions/ADR-template.md"
                    and "References" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_task_handoff_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/task-handoff.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Verification commands pass and output is recorded.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/agent-workflow/task-handoff.md"
                    and "Verification commands pass" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_command_contract_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/command-contract.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| Name | Purpose | Cwd | Argv | Writes State | Approval Required | Evidence | Environment |\n",
                    "| Name | Purpose | Cwd | Command | Writes State | Approval Required | Evidence | Environment |\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/agent-workflow/command-contract.md"
                    and "Argv" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_command_contract_template_missing_default_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/command-contract.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| governance-status | Print workflow state as JSON. | `.` | `"
                    '["bin/governance", "status", ".", "--json"]'
                    "` | false | false | `docs/development/03-verification-log.md` | Core governance runtime |\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_command_contract_template_command_drift"
                    and finding.path == "templates/docs/agent-workflow/command-contract.md"
                    and "governance-status" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_command_contract_template_default_argv_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/command-contract.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    '| check-env | Inventory local governance tools. | `.` | `["bin/governance", "env", "--target", "."]`',
                    '| check-env | Inventory local governance tools. | `.` | `["bin/governance", "env", "--repair", "--check", "--target", ".", "--json"]`',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_command_contract_template_command_drift"
                    and finding.path == "templates/docs/agent-workflow/command-contract.md"
                    and "check-env" in finding.message
                    and "Argv" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_task_handoff_execution_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/task-handoff.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Task execution satisfies `docs/agent-workflow/workflow-pack/references/implementation-execution-checklist.md`.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/agent-workflow/task-handoff.md"
                    and "implementation-execution-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_task_handoff_template_verification_record_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/task-handoff.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| Command | Result | Evidence |\n",
                    "| Command | Result |\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/agent-workflow/task-handoff.md"
                    and "Evidence" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_verification_log_template_section_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/development/03-verification-log.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace("## Verification Runs\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_section_missing"
                    and finding.path == "templates/docs/development/03-verification-log.md"
                    and "Verification Runs" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_task_board_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/development/02-task-board.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "Done tasks must link Verification to local Markdown evidence.",
                    "Done tasks can use any verification note.",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/development/02-task-board.md"
                    and "Done tasks must link Verification" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_acceptance_matrix_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/tests/02-acceptance-matrix.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| Acceptance | Design | API | Test |",
                    "| Acceptance | Design | Test |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/tests/02-acceptance-matrix.md"
                    and "| Acceptance | Design | API | Test |" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_roadmap_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/development/01-roadmap.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| ID | Status | Milestone |",
                    "| ID | Status |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/development/01-roadmap.md"
                    and "| ID | Status | Milestone |" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_test_strategy_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/tests/01-strategy.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Integration tests cover API contract and persistence behavior.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/tests/01-strategy.md"
                    and "Integration tests cover API contract" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_system_context_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/architecture/01-system-context.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- External system, service, or explicit `none`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/architecture/01-system-context.md"
                    and "External system" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_containers_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/architecture/02-containers.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "Map each container to owned data, shared data, and integration boundaries.",
                    "List data notes.",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/architecture/02-containers.md"
                    and "Map each container" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_quality_attributes_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/architecture/03-quality-attributes.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Logs, metrics, traces, audit events, and alerting expectations\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/architecture/03-quality-attributes.md"
                    and "Logs, metrics, traces" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_api_conventions_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/api/00-conventions.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Idempotency key policy for retryable writes and duplicate submission handling.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/api/00-conventions.md"
                    and "Idempotency key policy" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_api_error_codes_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/api/error-codes.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| Code | HTTP Status | Product Meaning | Retryable | User Action |",
                    "| Code | HTTP Status | Retryable |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/api/error-codes.md"
                    and "| Code | HTTP Status | Product Meaning | Retryable | User Action |" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_api_changelog_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/api/changelog.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| Date | Change | Source | Compatibility Impact |",
                    "| Date | Change |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/api/changelog.md"
                    and "| Date | Change | Source | Compatibility Impact |" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_endpoint_contract_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/api/endpoints/01-endpoint-contract.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Reference `docs/api/error-codes.md` and list only registered endpoint errors.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/api/endpoints/01-endpoint-contract.md"
                    and "docs/api/error-codes.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_endpoint_index_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/api/endpoints/README.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Endpoint files must use `NN-<slug>.md` with unique `NN` prefixes.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/api/endpoints/README.md"
                    and "NN-<slug>.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_backend_modules_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/backend/01-modules.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Link owned API endpoints under `docs/api/endpoints/`.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/backend/01-modules.md"
                    and "docs/api/endpoints" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_backend_modules_consistency_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/backend/01-modules.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Document success path, failure path, retry, timeout, compensation, transaction boundaries, consistency expectations, concurrency conflicts, duplicate-submission handling, observability, and security behavior.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/backend/01-modules.md"
                    and "transaction boundaries, consistency expectations, concurrency conflicts" in finding.message
                    and "duplicate-submission" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_backend_data_model_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/backend/02-data-model.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Document uniqueness, idempotency keys, cross-user isolation, transaction boundaries, consistency expectations, concurrency conflicts, retention, soft-delete, and audit constraints.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/backend/02-data-model.md"
                    and "idempotency keys" in finding.message
                    and "transaction boundaries, consistency expectations, concurrency conflicts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_backend_external_services_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/backend/03-external-services.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Document retryable failures, backoff policy, idempotency behavior, compensation, and duplicate-submission handling.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/backend/03-external-services.md"
                    and "retryable failures" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_backend_external_services_security_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/backend/03-external-services.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Document credential owner, auth mechanism, secret storage, rotation, least-privilege access, and access boundary.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/backend/03-external-services.md"
                    and "least-privilege access" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_ui_interaction_model_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/ui/01-interaction-model.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Map user-visible errors to API error codes, recovery actions, and acceptance criteria.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/ui/01-interaction-model.md"
                    and "API error codes" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_frontend_modules_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/frontend/01-modules.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Link each server-derived state to the API endpoint contract that owns it.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/frontend/01-modules.md"
                    and "server-derived state" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_frontend_api_consumption_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/frontend/02-api-consumption.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Map API error codes to user-visible copy, recovery action, retry behavior, telemetry, and acceptance criteria.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/frontend/02-api-consumption.md"
                    and "API error codes" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_skill_heading_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "# Designing API Contracts",
                    "# Designing Backend Modules",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_skill_heading_mismatch"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    for finding in report.findings
                )
            )

    def test_makefile_verify_pack_runs_pack_verifier(self) -> None:
        text = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\tpython3 scripts/verify_pack\.py$")

    def test_required_workflow_pack_files_exist(self) -> None:
        required = [
            "README.md",
            "AGENTS.md",
            "Makefile",
            "workflows/00-overview.md",
            "workflows/01-empty-repo-initialization.md",
            "workflows/02-product-document-archiving.md",
            "workflows/03-product-structuring.md",
            "workflows/04-design-derivation.md",
            "workflows/05-verification-and-drift-control.md",
            "workflows/06-implementation-execution.md",
            "references/architecture-methods.md",
            "references/backend-design-checklist.md",
            "references/runtime-strategy.md",
            "skills/executing-implementation-task/SKILL.md",
            "templates/root/README.md",
            "templates/docs/product/core/PRD.md",
            "templates/docs/agent-workflow/command-contract.md",
            "templates/docs/agent-workflow/task-handoff.md",
            "templates/docs/api/00-conventions.md",
            "templates/docs/api/changelog.md",
            "templates/docs/api/endpoints/README.md",
            "templates/docs/api/endpoints/01-endpoint-contract.md",
            "templates/docs/api/error-codes.md",
            "templates/docs/architecture/01-system-context.md",
            "templates/docs/architecture/02-containers.md",
            "templates/docs/architecture/03-quality-attributes.md",
            "templates/docs/backend/01-modules.md",
            "templates/docs/backend/02-data-model.md",
            "templates/docs/backend/03-external-services.md",
            "templates/docs/decisions/ADR-template.md",
            "templates/docs/development/01-roadmap.md",
            "templates/docs/development/02-task-board.md",
            "templates/docs/development/03-verification-log.md",
            "templates/docs/frontend/01-modules.md",
            "templates/docs/frontend/02-api-consumption.md",
            "templates/docs/tests/01-strategy.md",
            "templates/docs/tests/02-acceptance-matrix.md",
            "templates/docs/ui/01-interaction-model.md",
        ]
        missing = [path for path in required if not (ROOT / path).exists()]
        self.assertEqual([], missing)

    def test_skills_have_valid_frontmatter(self) -> None:
        skill_dirs = [
            "using-governance-workflow",
            "initializing-governance-repo",
            "archiving-product-document",
            "structuring-product-requirements",
            "designing-system-architecture",
            "designing-ui-interactions",
            "designing-api-contracts",
            "designing-backend-modules",
            "designing-data-models",
            "designing-frontend-modules",
            "designing-test-strategy",
            "capturing-architecture-decisions",
            "planning-implementation-work",
            "verifying-governance-docs",
            "executing-implementation-task",
        ]
        for skill in skill_dirs:
            skill_file = ROOT / "skills" / skill / "SKILL.md"
            self.assertTrue(skill_file.exists(), skill)
            text = skill_file.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), skill)
            frontmatter = text.split("---", 2)[1].strip()
            self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(skill)}$", skill)
            self.assertRegex(frontmatter, r"(?m)^description:\s*Use when .+", skill)

    def test_verifying_skill_prioritizes_structural_markdown_repairs(self) -> None:
        text = (ROOT / "skills/verifying-governance-docs/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Repair Order", text)
        self.assertIn("Fix document-integrity findings first", text)
        self.assertIn("markdown_not_file", text)
        self.assertIn("markdown_invalid_encoding", text)
        self.assertIn("rerun verification before interpreting downstream traceability findings", text)

    def test_verifier_workflow_pack_required_paths_match_bootstrap_snapshot(self) -> None:
        copied = [path.as_posix() for path in _iter_workflow_pack_files()]
        self.assertEqual(copied, list(WORKFLOW_PACK_REQUIRED_PATHS))


if __name__ == "__main__":
    unittest.main()
