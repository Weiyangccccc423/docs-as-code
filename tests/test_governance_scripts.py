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


def _write_product_chapter(root: Path, filename: str, title: str) -> None:
    _write_indexed_doc(root, f"docs/product/{filename}", f"# {title}\n\nSource: [PRD](core/PRD.md).\n")
    _append_product_meta_chapter(root, filename)


def _write_acceptance_chapter(root: Path) -> None:
    _write_product_chapter(root, "08-acceptance-criteria.md", "Acceptance Criteria")


def _write_api_error_codes_doc(root: Path) -> None:
    _write_indexed_doc(root, "docs/api/error-codes.md", "# API Error Codes\n\n## E_EXAMPLE\n\nExample error.\n")


def _write_frontend_consumer_doc(root: Path) -> None:
    _write_indexed_doc(
        root,
        "docs/frontend/02-api-consumption.md",
        "# API Consumption\n\n## Consumption Map\n\nWeb client goal flow consumes the example endpoint.\n",
    )


def _write_backend_trace_docs(root: Path) -> None:
    _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
    _write_indexed_doc(root, "docs/backend/02-data-model.md", "# Data Model\n")
    _write_indexed_doc(root, "docs/backend/03-external-services.md", "# External Services\n")
    _write_acceptance_chapter(root)


def _write_frontend_trace_docs(root: Path) -> None:
    _write_indexed_doc(root, "docs/ui/01-interaction-model.md", "# Interaction Model\n")
    _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
    _write_indexed_doc(root, "docs/frontend/02-api-consumption.md", "# API Consumption\n")
    _write_acceptance_chapter(root)


def _adr_doc(references: str = "- [System context](../architecture/01-system-context.md)") -> str:
    return (
        "# ADR-001: Choose Runtime Boundary\n\n"
        "- Status: accepted\n"
        "- Date: 2026-06-26\n\n"
        "## Context\n\n"
        "The runtime boundary affects API, backend, and frontend delivery.\n\n"
        "## Decision\n\n"
        "Use a modular monolith boundary for the first implementation slice.\n\n"
        "## Consequences\n\n"
        "Deployment stays simple while module boundaries remain documented.\n\n"
        "## References\n\n"
        f"{references.rstrip()}\n"
    )


def _endpoint_contract_doc(
    title: str,
    upstream_links: str = "- [Product goals](../../product/01-goals.md)",
    error_codes: str = "- [E_EXAMPLE](../error-codes.md#e-example)",
    frontend_consumers: str = "- [API consumption map](../../frontend/02-api-consumption.md)",
) -> str:
    return (
        f"# {title}\n\n"
        "## Method and Path\n\n"
        "GET /example\n\n"
        "## Auth\n\n"
        "Required.\n\n"
        "## Idempotency\n\n"
        "Safe retry.\n\n"
        "## Request Fields\n\n"
        "- none\n\n"
        "## Response Fields\n\n"
        "- id\n\n"
        "## Error Codes\n\n"
        f"{error_codes.rstrip()}\n\n"
        "## Upstream Links\n\n"
        f"{upstream_links.rstrip()}\n\n"
        "## Frontend Consumers\n\n"
        f"{frontend_consumers.rstrip()}\n"
    )


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

    def test_verify_reports_incomplete_glossary_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "|  |  |  |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("docs/glossary.md row (missing term) is missing required fields: Term, Meaning, Source", report.errors)
            self.assertIn(
                {
                    "code": "glossary_row_missing_fields",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "docs/glossary.md row (missing term) is missing required fields: Term, Meaning, Source",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning |\n"
                "| --- | --- |\n"
                "| Account | User account |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("docs/glossary.md table is missing required columns: source", report.errors)
            self.assertIn(
                {
                    "code": "glossary_table_missing_columns",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "docs/glossary.md table is missing required columns: source",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_glossary_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | docs/product/core/PRD.md |\n"
                "| account | Duplicate spelling | docs/product/core/PRD.md |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("duplicate glossary term: account", report.errors)
            self.assertIn(
                {
                    "code": "glossary_duplicate_term",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "duplicate glossary term: account",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_source_without_local_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | PRD |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("glossary row Account Source field has no local Markdown reference", report.errors)
            self.assertIn(
                {
                    "code": "glossary_source_reference_missing",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "glossary row Account Source field has no local Markdown reference",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_missing_source_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | docs/product/missing.md |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("glossary row Account references missing Source target: docs/product/missing.md", report.errors)
            self.assertIn(
                {
                    "code": "glossary_source_reference_missing",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "glossary row Account references missing Source target: docs/product/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_glossary_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | [PRD](product/core/PRD.md) |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertEqual([], report.errors)

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

    def test_verify_reports_invalid_product_chapter_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "goals.md")
            meta = root / "docs/product/core/product-meta.md"
            meta.write_text(meta.read_text(encoding="utf-8") + "\n- [Goals](../goals.md)\n", encoding="utf-8")

            report = verify(root)

            self.assertIn("docs/product/goals.md must use NN-<slug>.md product chapter naming", report.errors)
            self.assertIn(
                {
                    "code": "product_chapter_invalid_filename",
                    "severity": "error",
                    "path": "docs/product/goals.md",
                    "message": "docs/product/goals.md must use NN-<slug>.md product chapter naming",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_product_chapter_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            for filename in ("01-goals.md", "01-scope.md"):
                chapter = root / "docs/product" / filename
                chapter.write_text("# Chapter\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
                _append_index(root / "docs/product/README.md", filename)
                _append_product_meta_chapter(root, filename)

            report = verify(root)

            self.assertIn("duplicate product chapter prefix 01: docs/product/01-goals.md, docs/product/01-scope.md", report.errors)
            self.assertIn(
                {
                    "code": "product_chapter_duplicate_prefix",
                    "severity": "error",
                    "path": "docs/product/01-scope.md",
                    "message": "duplicate product chapter prefix 01: docs/product/01-goals.md, docs/product/01-scope.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_api_endpoint_contract_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text(
                "# API Endpoints\n\n"
                "- `01-create-user.md` - create user endpoint\n"
                "- `02-list-users.md` - list users endpoint\n",
                encoding="utf-8",
            )
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User"),
                encoding="utf-8",
            )
            (endpoint_readme.parent / "02-list-users.md").write_text(
                _endpoint_contract_doc("List Users"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_api_endpoint_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                "# Create User\n\n"
                "## Method and Path\n\n"
                "POST /users\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md is missing endpoint contract sections: "
                "Auth, Idempotency, Request Fields, Response Fields, Error Codes, Upstream Links, Frontend Consumers",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_missing_sections",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md is missing endpoint contract sections: "
                    "Auth, Idempotency, Request Fields, Response Fields, Error Codes, Upstream Links, Frontend Consumers",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                "# Create User\n\n"
                "## Method and Path\n\n"
                "POST /users\n\n"
                "## Auth\n\n"
                "- TBD\n\n"
                "## Idempotency\n\n"
                "Use Idempotency-Key.\n\n"
                "## Request Fields\n\n"
                "- email\n\n"
                "## Response Fields\n\n"
                "- id\n\n"
                "## Error Codes\n\n"
                "TODO\n\n"
                "## Upstream Links\n\n"
                "- [Product goals](../../product/01-goals.md)\n\n"
                "## Frontend Consumers\n\n"
                "- [API consumption map](../../frontend/02-api-consumption.md)\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md has empty endpoint contract sections: Auth, Error Codes",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_empty_sections",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md has empty endpoint contract sections: Auth, Error Codes",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_invalid_method_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User").replace("GET /example", "Create a user endpoint"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Method and Path section must include an HTTP method and absolute path",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_method_path_invalid",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Method and Path section must include an HTTP method and absolute path",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_error_codes_registry_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", error_codes="- E_EXAMPLE"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Error Codes section must reference docs/api/error-codes.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_error_codes_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Error Codes section must reference docs/api/error-codes.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_error_codes_registry_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md references missing Error Codes registry target: docs/api/error-codes.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_error_codes_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md references missing Error Codes registry target: docs/api/error-codes.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_upstream_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", "- Product goals and architecture context"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Upstream Links section must reference existing local Markdown source",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_upstream_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Upstream Links section must reference existing local Markdown source",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_upstream_reference_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", "- [Missing product source](../../product/missing.md)"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md references missing Upstream Links target: docs/product/missing.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_upstream_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md references missing Upstream Links target: docs/product/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_frontend_consumer_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", frontend_consumers="- Web client goal flow"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Frontend Consumers section must reference existing local Markdown consumer docs",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_frontend_consumer_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Frontend Consumers section must reference existing local Markdown consumer docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_frontend_consumer_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc(
                    "Create User",
                    frontend_consumers="- [Missing consumer](../../frontend/missing.md)",
                ),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md references missing Frontend Consumers target: docs/frontend/missing.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_frontend_consumer_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md references missing Frontend Consumers target: docs/frontend/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_api_endpoint_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "create-user.md").write_text("# Create User\n", encoding="utf-8")

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/create-user.md must use NN-<slug>.md endpoint contract naming",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_invalid_filename",
                    "severity": "error",
                    "path": "docs/api/endpoints/create-user.md",
                    "message": "docs/api/endpoints/create-user.md must use NN-<slug>.md endpoint contract naming",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_api_endpoint_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text(
                "# API Endpoints\n\n"
                "- `01-create-user.md` - create user endpoint\n"
                "- `01-list-users.md` - list users endpoint\n",
                encoding="utf-8",
            )
            for filename in ("01-create-user.md", "01-list-users.md"):
                (endpoint_readme.parent / filename).write_text(
                    _endpoint_contract_doc("Endpoint"),
                    encoding="utf-8",
                )

            report = verify(root)

            self.assertIn(
                "duplicate API endpoint contract prefix 01: "
                "docs/api/endpoints/01-create-user.md, docs/api/endpoints/01-list-users.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_duplicate_prefix",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-list-users.md",
                    "message": "duplicate API endpoint contract prefix 01: "
                    "docs/api/endpoints/01-create-user.md, docs/api/endpoints/01-list-users.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_backend_module_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_backend_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                "# Backend Modules\n\n"
                "API: [API conventions](../api/00-conventions.md).\n"
                "Data: [Data model](02-data-model.md).\n"
                "External services: [External services](03-external-services.md).\n"
                "Acceptance: [Acceptance](../product/08-acceptance-criteria.md).\n",
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_backend_module_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                "# Backend Modules\n\n"
                "The service module owns the goal flow runtime behavior.\n",
            )

            report = verify(root)

            expected = [
                "docs/backend/01-modules.md must reference existing API docs",
                "docs/backend/01-modules.md must reference docs/backend/02-data-model.md",
                "docs/backend/01-modules.md must reference docs/backend/03-external-services.md",
                "docs/backend/01-modules.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "docs/backend/01-modules.md must reference existing API docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_module_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                "# Backend Modules\n\n"
                "API: [Missing API](../api/missing.md).\n"
                "Data: [Data model](02-data-model.md).\n"
                "External services: [External services](03-external-services.md).\n"
                "Acceptance: [Acceptance](../product/08-acceptance-criteria.md).\n",
            )

            report = verify(root)

            expected = [
                "docs/backend/01-modules.md references missing API target: docs/api/missing.md",
                "docs/backend/01-modules.md references missing Data Model target: docs/backend/02-data-model.md",
                "docs/backend/01-modules.md references missing External Services target: docs/backend/03-external-services.md",
                "docs/backend/01-modules.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "docs/backend/01-modules.md references missing API target: docs/api/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_frontend_module_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_frontend_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                "# Frontend Modules\n\n"
                "UI: [Interaction model](../ui/01-interaction-model.md).\n"
                "API: [API conventions](../api/00-conventions.md).\n"
                "State and API consumption: [API consumption](02-api-consumption.md).\n"
                "Acceptance: [Acceptance](../product/08-acceptance-criteria.md).\n",
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_frontend_module_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                "# Frontend Modules\n\n"
                "The web module owns the primary goal flow screens.\n",
            )

            report = verify(root)

            expected = [
                "docs/frontend/01-modules.md must reference existing UI docs",
                "docs/frontend/01-modules.md must reference existing API docs",
                "docs/frontend/01-modules.md must reference docs/frontend/02-api-consumption.md",
                "docs/frontend/01-modules.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "frontend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/frontend/01-modules.md",
                    "message": "docs/frontend/01-modules.md must reference existing UI docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_module_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                "# Frontend Modules\n\n"
                "UI: [Missing UI](../ui/missing.md).\n"
                "API: [Missing API](../api/missing.md).\n"
                "State and API consumption: [API consumption](02-api-consumption.md).\n"
                "Acceptance: [Acceptance](../product/08-acceptance-criteria.md).\n",
            )

            report = verify(root)

            expected = [
                "docs/frontend/01-modules.md references missing UI target: docs/ui/missing.md",
                "docs/frontend/01-modules.md references missing API target: docs/api/missing.md",
                "docs/frontend/01-modules.md references missing API Consumption target: docs/frontend/02-api-consumption.md",
                "docs/frontend/01-modules.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "frontend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/frontend/01-modules.md",
                    "message": "docs/frontend/01-modules.md references missing UI target: docs/ui/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_adr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", "# System Context\n")
            _write_indexed_doc(root, "docs/decisions/001-runtime-boundary.md", _adr_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_adr_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                "# ADR-001: Choose Runtime Boundary\n\n"
                "## Context\n\n"
                "Runtime boundary context.\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md is missing ADR sections: Decision, Consequences, References",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_missing_sections",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md is missing ADR sections: Decision, Consequences, References",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                "# ADR-001: Choose Runtime Boundary\n\n"
                "## Context\n\n"
                "TBD\n\n"
                "## Decision\n\n"
                "Use a modular monolith boundary.\n\n"
                "## Consequences\n\n"
                "Deployment remains simple.\n\n"
                "## References\n\n"
                "- [System context](../architecture/01-system-context.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md has empty ADR sections: Context",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_empty_sections",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md has empty ADR sections: Context",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_missing_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                _adr_doc("- System context and module tradeoffs"),
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md References section must reference existing local Markdown sources",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_reference_missing",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md References section must reference existing local Markdown sources",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_missing_reference_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                _adr_doc("- [Missing source](../architecture/missing.md)"),
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md references missing ADR References target: docs/architecture/missing.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_reference_missing",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md references missing ADR References target: docs/architecture/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

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
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | TBD | docs/product/08-acceptance-criteria.md | make test |\n",
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
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | [Goals](../product/01-goals.md) | docs/architecture/01-context.md#actors | `docs/api/00-conventions.md` | [Acceptance](../product/08-acceptance-criteria.md) | make test |\n",
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `02-task-board.md` - task board\n", encoding="utf-8")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_task_board_acceptance_without_product_acceptance_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/tests/01-strategy.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-001 Acceptance field must reference a product acceptance chapter",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_acceptance_reference_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 Acceptance field must reference a product acceptance chapter",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_missing_trace_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/missing.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
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

    def test_verify_reports_duplicate_task_board_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-001 | Ready | Implement goal audit | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("duplicate task board ID: TASK-001", report.errors)
            self.assertIn(
                {
                    "code": "task_board_duplicate_id",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "duplicate task board ID: TASK-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_task_board_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Raedy | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-001 has invalid Status: Raedy", report.errors)
            self.assertIn(
                {
                    "code": "task_board_invalid_status",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 has invalid Status: Raedy",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_standard_task_board_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            _write_indexed_doc(root, "docs/development/03-verification-log.md", "# Verification Log\n")
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Backlog | Scope goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-003 | In Progress | Wire goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-004 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Blocked by [U-001](../unresolved.md) |\n"
                "| TASK-005 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | docs/development/03-verification-log.md |\n"
                "| TASK-006 | Deferred | Later goal audit | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_blocked_task_without_unresolved_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Waiting for decision |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-002 is Blocked but does not cite an existing unresolved item ID",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_blocked_unresolved_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 is Blocked but does not cite an existing unresolved item ID",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_blocked_task_without_unresolved_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Blocked by U-001 |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-002 is Blocked but does not link to docs/unresolved.md", report.errors)
            self.assertIn(
                {
                    "code": "task_board_blocked_unresolved_link_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 is Blocked but does not link to docs/unresolved.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_blocked_task_with_unresolved_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Blocked by [U-001](../unresolved.md) |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_done_task_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-002 is Done but Verification has no local Markdown evidence", report.errors)
            self.assertIn(
                {
                    "code": "task_board_done_evidence_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 is Done but Verification has no local Markdown evidence",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_done_task_with_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            _write_indexed_doc(root, "docs/development/03-verification-log.md", "# Verification Log\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | [verification log](03-verification-log.md) |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_done_task_with_missing_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | docs/development/missing-log.md |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-002 references missing Verification evidence: docs/development/missing-log.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_done_evidence_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 references missing Verification evidence: docs/development/missing-log.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_task_status_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                "# Roadmap\n\n"
                "| ID | Status | Milestone |\n"
                "| --- | --- | --- |\n"
                "| TASK-001 | Done | Goal flow |\n",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("roadmap status for TASK-001 is Done but task board status is Ready", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_task_status_conflict",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "roadmap status for TASK-001 is Done but task board status is Ready",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_matching_roadmap_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", "# API Conventions\n")
            _write_indexed_doc(root, "docs/tests/01-strategy.md", "# Test Strategy\n")
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                "# Roadmap\n\n"
                "| ID | Status | Milestone |\n"
                "| --- | --- | --- |\n"
                "| TASK-001 | Ready | Goal flow |\n",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

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
