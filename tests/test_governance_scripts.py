import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_env import PackageManager, ToolStatus, build_install_plan
from scripts.bootstrap_tree import InitPreflightError
from scripts.bootstrap_tree import bootstrap
from scripts.verify_governance import verify


class GovernanceScriptsTest(unittest.TestCase):
    def test_bootstrap_archives_markdown_product_doc_and_passes_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "input-product.md"
            product.write_text(
                "# Demo Product\n\n"
                "## Goal\n\n"
                "Build a reliable workflow-driven project.\n",
                encoding="utf-8",
            )

            bootstrap(root, product)

            self.assertTrue((root / "README.md").exists())
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertTrue((root / "docs/product/core/PRD.md").exists())
            self.assertTrue((root / "docs/product/core/source/input-product.md").exists())
            self.assertIn("Demo Product", (root / "docs/product/core/PRD.md").read_text(encoding="utf-8"))

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_bootstrap_rejects_existing_governance_file_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            readme = root / "README.md"
            readme.write_text("# Existing\n", encoding="utf-8")

            with self.assertRaises(InitPreflightError) as caught:
                bootstrap(root, product)

            self.assertEqual(
                [{"path": "README.md", "reason": "generated file already exists"}],
                [conflict.to_dict() for conflict in caught.exception.result.conflicts],
            )
            self.assertEqual("# Existing\n", readme.read_text(encoding="utf-8"))
            self.assertFalse((root / "docs/README.md").exists())

    def test_bootstrap_installs_target_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")

            bootstrap(root, product)

            self.assertTrue((root / "bin/governance").exists())
            self.assertTrue((root / "scripts/governance_cli.py").exists())
            self.assertTrue((root / "scripts/verify_governance.py").exists())
            self.assertIn("bin/governance verify .", (root / "Makefile").read_text(encoding="utf-8"))

            verify_result = subprocess.run(
                ["make", "verify-governance"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            self.assertIn("Governance verification passed.", verify_result.stdout)

            cli_result = subprocess.run(
                [str(root / "bin/governance"), "status", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, cli_result.returncode, cli_result.stderr)
            self.assertIn("phase: initialized", cli_result.stdout)

    def test_verify_reports_unregistered_docs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            rogue = root / "docs/superpowers"
            rogue.mkdir()
            (rogue / "note.md").write_text("# Rogue\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("docs/superpowers is not registered in docs/AGENTS.md", report.errors)

    def test_verify_reports_stale_reserved_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            readme = root / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- docs/api: [预留]\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("reserved marker references non-empty docs/api", report.errors)

    def test_install_plan_respects_strict_scope(self) -> None:
        statuses = [
            ToolStatus(
                name="git",
                present=False,
                version="",
                note="Required",
                level="required",
                install_package="git",
            ),
            ToolStatus(
                name="pandoc",
                present=False,
                version="",
                note="Recommended",
                level="recommended",
                install_package="pandoc",
            ),
            ToolStatus(
                name="node",
                present=False,
                version="",
                note="Recommended",
                level="recommended",
                install_package=None,
            ),
        ]
        apt = PackageManager(name="apt", command="apt-get", supported=True)

        non_strict = build_install_plan(statuses, strict=False, package_manager=apt)
        strict = build_install_plan(statuses, strict=True, package_manager=apt)

        self.assertEqual(["git"], [item.tool for item in non_strict])
        self.assertEqual(["git", "pandoc"], [item.tool for item in strict])


if __name__ == "__main__":
    unittest.main()
