import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_env import PackageManager, ToolStatus, build_install_plan
from scripts.bootstrap_tree import InitPreflightError
from scripts.bootstrap_tree import bootstrap
from scripts.verify_governance import verify


def _append_index(readme: Path, filename: str) -> None:
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n- `{filename}` - generated for test\n", encoding="utf-8")


def _write_indexed_doc(root: Path, rel: str, text: str = "# Test\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _append_index(path.parent / "README.md", path.name)


def _append_product_meta_chapter(root: Path, filename: str) -> None:
    meta = root / "docs/product/core/product-meta.md"
    meta.write_text(meta.read_text(encoding="utf-8") + f"\n- [{filename}](../{filename})\n", encoding="utf-8")


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
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/workflows/00-overview.md").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/skills/using-governance-workflow/SKILL.md").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/references/architecture-methods.md").exists())
            workflow_manifest = json.loads((root / "docs/agent-workflow/workflow-pack/manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["path"] == "workflows/00-overview.md" for item in workflow_manifest["files"]))
            self.assertIn("Demo Product", (root / "docs/product/core/PRD.md").read_text(encoding="utf-8"))
            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("input-product.md", manifest["source"]["filename"])
            self.assertEqual("ready_for_structuring", manifest["import"]["status"])
            self.assertEqual("markdown-copy", manifest["import"]["conversion_method"])
            self.assertTrue(manifest["import"]["can_derive_design"])
            self.assertEqual(manifest["source"]["sha256"], manifest["archive"]["sha256"])

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_verify_rejects_tampered_archived_product_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            archived = root / "docs/product/core/source/product.md"
            archived.write_text("# Tampered\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("archived product source hash mismatch: docs/product/core/source/product.md", report.errors)

    def test_verify_rejects_tampered_workflow_pack_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            workflow = root / "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
            workflow.write_text(workflow.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("workflow pack file hash mismatch: docs/agent-workflow/workflow-pack/workflows/00-overview.md", report.errors)
            self.assertIn(
                {
                    "code": "workflow_pack_file_hash_mismatch",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                    "message": "workflow pack file hash mismatch: docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_non_markdown_product_requires_conversion_before_verification_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)

            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("conversion-required", manifest["import"]["conversion_method"])
            self.assertFalse(manifest["import"]["can_derive_design"])

            report = verify(root)
            self.assertIn("product source requires conversion before design derivation: docs/product/core/source/product.docx", report.errors)

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
            self.assertTrue((root / "scripts/phases.py").exists())
            self.assertTrue((root / "scripts/scaffold.py").exists())
            self.assertTrue((root / "scripts/verify_governance.py").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/manifest.json").exists())
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

    def test_verify_reports_blocking_unresolved_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | API | Need auth model | API and backend design | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)
            self.assertIn("blocking unresolved item U-001 affects API and backend design", report.errors)

    def test_verify_allows_non_blocking_unresolved_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-002 | Copy | Confirm button label | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_verify_reports_incomplete_unresolved_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "|  | API |  | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("docs/unresolved.md row (missing id) is missing required fields: ID, Description", report.errors)
            self.assertIn(
                {
                    "code": "unresolved_row_missing_fields",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "docs/unresolved.md row (missing id) is missing required fields: ID, Description",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_unresolved_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | API | Confirm auth model | none | TBD | 2026-06-26 |\n"
                "| U-001 | Backend | Confirm persistence model | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("duplicate unresolved item ID: U-001", report.errors)
            self.assertIn(
                {
                    "code": "unresolved_duplicate_id",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "duplicate unresolved item ID: U-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_unindexed_docs_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("docs/product/01-goals.md is not indexed in docs/product/README.md", report.errors)
            self.assertIn(
                {
                    "code": "docs_readme_unindexed_file",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md is not indexed in docs/product/README.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_indexed_docs_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            readme = root / "docs/product/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `01-goals.md` - goals\n", encoding="utf-8")
            _append_product_meta_chapter(root, "01-goals.md")

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_verify_reports_missing_local_markdown_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSee [API](../api/missing.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")

            report = verify(root)

            self.assertIn("docs/product/01-goals.md links to missing local Markdown target: docs/api/missing.md", report.errors)
            self.assertIn(
                {
                    "code": "docs_local_markdown_link_missing",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md links to missing local Markdown target: docs/api/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_existing_local_markdown_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            _write_indexed_doc(
                root,
                "docs/product/01-goals.md",
                "# Goals\n\n"
                "Source: [PRD](core/PRD.md).\n"
                "See [API](../api/00-conventions.md#http) and [external](https://example.com/spec.md).\n\n"
                "```md\n"
                "[Example](../api/missing-example.md)\n"
                "```\n",
            )
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _append_product_meta_chapter(root, "01-goals.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_product_chapter_missing_source_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nDerived goals.\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")

            report = verify(root)

            self.assertIn("docs/product/01-goals.md must link back to docs/product/core/PRD.md", report.errors)
            self.assertIn("docs/product/core/product-meta.md must link to product chapter: docs/product/01-goals.md", report.errors)
            self.assertIn(
                {
                    "code": "product_chapter_missing_prd_link",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md must link back to docs/product/core/PRD.md",
                },
                [finding.to_dict() for finding in report.findings],
            )
            self.assertIn(
                {
                    "code": "product_meta_missing_chapter_link",
                    "severity": "error",
                    "path": "docs/product/core/product-meta.md",
                    "message": "docs/product/core/product-meta.md must link to product chapter: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_product_chapter_source_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")
            meta = root / "docs/product/core/product-meta.md"
            meta.write_text(meta.read_text(encoding="utf-8") + "\n- [Goals](../01-goals.md)\n", encoding="utf-8")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_task_board_missing_trace_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | TBD | docs/tests/01-strategy.md | make test |\n",
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `02-task-board.md` - task board\n", encoding="utf-8")

            report = verify(root)

            self.assertIn("task board row TASK-001 is missing required fields: API", report.errors)
            self.assertIn(
                {
                    "code": "task_board_row_missing_fields",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 is missing required fields: API",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_task_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | [Goals](../product/01-goals.md) | docs/architecture/01-context.md#actors | `docs/api/00-conventions.md` | [Strategy](../tests/01-strategy.md) | make test |\n",
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `02-task-board.md` - task board\n", encoding="utf-8")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_task_board_missing_trace_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/missing.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/tests/01-strategy.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-001 references missing Product target: docs/product/missing.md", report.errors)
            self.assertIn(
                {
                    "code": "task_board_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 references missing Product target: docs/product/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

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
