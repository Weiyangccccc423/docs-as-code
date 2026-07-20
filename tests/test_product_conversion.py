import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.product_conversion as product_conversion_module
from scripts.bootstrap_tree import bootstrap
from scripts.check_env import PackageManager, ToolStatus, build_install_plan, environment_ok
from scripts.product_conversion import check_product_conversion, convert_product_document
from scripts.product_import import check_product_import_ready, mark_product_import_ready
from scripts.state import load_state
from scripts.verify_governance import verify
from scripts.workflow_actions import next_actions_payload


class ProductConversionTest(unittest.TestCase):
    def test_operation_required_tool_is_planned_without_strict_mode(self) -> None:
        statuses = [
            ToolStatus("git", True, "git version 2.34.1", "Required.", "required", "git"),
            ToolStatus("pandoc", False, "", "Convert product documents.", "recommended", "pandoc"),
            ToolStatus("lychee", False, "", "Check links.", "recommended", None),
        ]
        package_manager = PackageManager("apt", "/usr/bin/apt-get", True)

        plan = build_install_plan(
            statuses,
            strict=False,
            package_manager=package_manager,
            required_tools=("pandoc",),
        )

        self.assertEqual(["pandoc"], [item.tool for item in plan])
        self.assertFalse(environment_ok(statuses, strict=False, required_tools=("pandoc",)))
        self.assertTrue(environment_ok(statuses, strict=False))

    def test_txt_conversion_check_is_no_write_and_apply_routes_to_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "product.txt"
            source.write_text("Field Service Console\n\nGoals\n- Dispatch work.\n", encoding="utf-8")
            target = base / "target"
            bootstrap(target, product_doc=source, project_name="Field Service Console")
            placeholder = (target / "docs/product/core/PRD.md").read_text(encoding="utf-8")
            initial_actions = next_actions_payload(load_state(target), cwd=str(target))
            self.assertEqual("product-convert-check", initial_actions[0]["id"])
            self.assertEqual("product-convert", initial_actions[1]["id"])

            check = check_product_conversion(target)

            self.assertTrue(check.ok, check.errors)
            self.assertTrue(check.check)
            self.assertEqual("utf8-text-to-markdown", check.method)
            self.assertEqual("builtin-utf8", check.converter)
            self.assertEqual(
                [
                    "docs/product/core/PRD.md",
                    "docs/product/core/source/conversion-report.json",
                    ".governance/state.json",
                ],
                check.would_update,
            )
            self.assertEqual(placeholder, (target / "docs/product/core/PRD.md").read_text(encoding="utf-8"))
            self.assertFalse((target / "docs/product/core/source/conversion-report.json").exists())

            result = convert_product_document(target)

            self.assertTrue(result.ok, result.errors)
            self.assertFalse(result.check)
            self.assertTrue(result.review_required)
            self.assertEqual("reviewed-utf8-text-to-markdown", result.review_method)
            self.assertEqual(
                "Field Service Console\n\nGoals\n- Dispatch work.\n",
                (target / "docs/product/core/PRD.md").read_text(encoding="utf-8"),
            )
            report = json.loads(
                (target / "docs/product/core/source/conversion-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(1, report["schema_version"])
            self.assertEqual("pending", report["review"]["status"])
            self.assertEqual("utf8-text-to-markdown", report["conversion"]["method"])
            self.assertEqual(report["output"]["sha256"], result.output_sha256)
            state = load_state(target)
            self.assertEqual("pending_review", state["product_conversion_status"])
            self.assertEqual(
                "docs/product/core/source/conversion-report.json",
                state["product_conversion_report"],
            )
            actions = next_actions_payload(state, cwd=str(target))
            self.assertEqual("product-mark-ready-check", actions[0]["id"])
            self.assertIn("reviewed-utf8-text-to-markdown", actions[0]["argv"])

    def test_docx_conversion_requires_pandoc_and_returns_targeted_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "product.docx"
            source.write_bytes(b"test-docx")
            target = base / "target"
            bootstrap(target, product_doc=source)
            placeholder = (target / "docs/product/core/PRD.md").read_text(encoding="utf-8")

            with mock.patch.object(product_conversion_module.shutil, "which", return_value=None):
                result = check_product_conversion(target)

            self.assertFalse(result.ok)
            self.assertEqual("pandoc", result.required_tool)
            self.assertTrue(result.repair_required)
            self.assertIn("required conversion tool is missing: pandoc", result.errors)
            self.assertEqual(
                [
                    "bin/governance",
                    "env",
                    "--repair",
                    "--require-tool",
                    "pandoc",
                    "--check",
                    "--target",
                    ".",
                    "--json",
                ],
                result.repair_check_command["argv"],
            )
            self.assertEqual(placeholder, (target / "docs/product/core/PRD.md").read_text(encoding="utf-8"))
            self.assertFalse((target / "docs/product/core/source/conversion-report.json").exists())

    def test_conversion_refuses_stale_converter_temporary_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "product.txt"
            source.write_text("Product\n", encoding="utf-8")
            target = base / "target"
            bootstrap(target, product_doc=source)
            stale = target / "docs/product/core/.PRD.md.conversion.tmp"
            stale.write_text("stale output\n", encoding="utf-8")

            result = check_product_conversion(target)

            self.assertFalse(result.ok)
            self.assertIn(
                "stale product conversion temporary output exists: docs/product/core/.PRD.md.conversion.tmp",
                result.errors,
            )
            self.assertEqual("stale output\n", stale.read_text(encoding="utf-8"))

    def test_conversion_rejects_oversized_output_before_target_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "product.txt"
            source.write_text("product content\n", encoding="utf-8")
            target = base / "target"
            bootstrap(target, product_doc=source)
            placeholder = (target / "docs/product/core/PRD.md").read_text(encoding="utf-8")

            with mock.patch.object(product_conversion_module, "MAX_CONVERTED_BYTES", 4):
                result = convert_product_document(target)

            self.assertFalse(result.ok)
            self.assertTrue(any("exceeds 4 bytes" in error for error in result.errors))
            self.assertEqual(placeholder, (target / "docs/product/core/PRD.md").read_text(encoding="utf-8"))
            self.assertFalse((target / "docs/product/core/source/conversion-report.json").exists())

    def test_docx_conversion_records_pandoc_evidence_and_review_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "product.docx"
            source.write_bytes(b"test-docx")
            target = base / "target"
            bootstrap(target, product_doc=source)
            fake_pandoc = base / "pandoc"
            fake_pandoc.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('pandoc 3.1.2')\n"
                "    raise SystemExit(0)\n"
                "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "output.write_text('# Converted Product\\n\\n- Preserve acceptance rules.\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            fake_pandoc.chmod(0o755)

            with mock.patch.object(product_conversion_module.shutil, "which", return_value=str(fake_pandoc)):
                check = check_product_conversion(target)
                result = convert_product_document(target)

            self.assertTrue(check.ok, check.errors)
            self.assertTrue(result.ok, result.errors)
            self.assertEqual("pandoc-docx-to-gfm", result.method)
            self.assertEqual("pandoc 3.1.2", result.converter_version)
            self.assertEqual("pass", result.execution["result"])
            self.assertNotIn("--extract-media", result.execution["argv"])
            report_path = target / "docs/product/core/source/conversion-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual("pending", report["review"]["status"])
            self.assertEqual("pandoc", report["conversion"]["tool"])
            self.assertEqual("pandoc 3.1.2", report["conversion"]["tool_version"])
            self.assertEqual(
                "# Converted Product\n\n- Preserve acceptance rules.\n",
                (target / "docs/product/core/PRD.md").read_text(encoding="utf-8"),
            )

            prd = target / "docs/product/core/PRD.md"
            prd.write_text(prd.read_text(encoding="utf-8") + "\nReviewed against source.\n", encoding="utf-8")
            ready = mark_product_import_ready(target, method=result.review_method, reviewed=True)

            self.assertTrue(ready.ok, ready.errors)
            reviewed_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual("reviewed", reviewed_report["review"]["status"])
            self.assertEqual(result.review_method, reviewed_report["review"]["method"])
            self.assertNotEqual(
                reviewed_report["output"]["sha256"],
                reviewed_report["review"]["reviewed_prd_sha256"],
            )
            manifest = json.loads(
                (target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                "docs/product/core/source/conversion-report.json",
                manifest["import"]["conversion_report"],
            )
            self.assertEqual(
                reviewed_report["review"]["reviewed_prd_sha256"],
                manifest["import"]["reviewed_prd_sha256"],
            )
            self.assertEqual("reviewed", load_state(target)["product_conversion_status"])
            self.assertTrue(verify(target).ok)

            reviewed_report_text = report_path.read_text(encoding="utf-8")
            report_path.unlink()
            missing_report = check_product_import_ready(
                target,
                method=result.review_method,
                reviewed=True,
            )
            self.assertFalse(missing_report.ok)
            self.assertIn(
                "referenced product conversion report is missing: docs/product/core/source/conversion-report.json",
                missing_report.errors,
            )
            report_path.write_text(reviewed_report_text, encoding="utf-8")

            prd.write_text(prd.read_text(encoding="utf-8") + "\nUnreviewed drift.\n", encoding="utf-8")
            drift_report = verify(target)
            self.assertTrue(
                any(
                    finding.code == "product_conversion_reviewed_prd_hash_mismatch"
                    for finding in drift_report.findings
                )
            )

    def test_pdf_conversion_stops_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "product.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            target = base / "target"
            bootstrap(target, product_doc=source)

            result = check_product_conversion(target)

            self.assertFalse(result.ok)
            self.assertFalse(result.repair_required)
            self.assertEqual("manual-reviewed-pdf-to-markdown", result.review_method)
            self.assertIn(
                "automatic PDF conversion is unsupported; extract and review Markdown manually",
                result.errors,
            )


if __name__ == "__main__":
    unittest.main()
