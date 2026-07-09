import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "scripts" / "export_workflow_pack.py"


class ConsumerBootstrapTest(unittest.TestCase):
    def test_exported_pack_bootstraps_consumer_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Bootstrap Product\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize a governed repository from an exported workflow pack.\n"
                "- Keep the product document archived before design derivation.\n\n"
                "## Acceptance Criteria\n\n"
                "- The initialized target exposes local governance checks.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            export_payload = json.loads(export.stdout)
            self.assertTrue(export_payload["ok"])

            check_payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=True,
            )

            self.assertTrue(check_payload["ok"])
            self.assertTrue(check_payload["check"])
            self.assertFalse(check_payload["initialized"])
            self.assertFalse(target.exists())
            self.assertTrue(check_payload["pack_manifest_verification"]["ok"])
            self.assertTrue(check_payload["pack_verification"]["ok"])
            self.assertTrue(check_payload["env_check"]["ok"])
            self.assertTrue(check_payload["init_check"]["ok"])
            self.assertEqual("explicit", check_payload["init_check"]["product"]["selection"])
            self.assertEqual(
                {"pack_manifest_verify", "pack_verify", "env_repair_check", "init_check"},
                {step["id"] for step in check_payload["steps"]},
            )

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
            )

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["check"])
            self.assertTrue(payload["initialized"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual(str(product.resolve()), payload["product"])
            self.assertTrue(payload["pack_manifest_verification"]["ok"])
            self.assertTrue(payload["pack_verification"]["ok"])
            self.assertTrue(payload["env_check"]["ok"])
            self.assertTrue(payload["init_check"]["ok"])
            self.assertTrue(payload["init"]["ok"])
            self.assertEqual("initialized", payload["init"]["state"]["phase"])
            self.assertEqual("service", payload["init"]["state"]["profile"])
            self.assertEqual("Consumer Bootstrap Smoke", payload["init"]["state"]["project_name"])
            self.assertTrue(payload["target_local"]["ok"])
            self.assertTrue(payload["target_local"]["verify_ok"])
            self.assertTrue(payload["target_local"]["status_ok"])
            self.assertTrue(payload["target_local"]["workflow_plan_ok"])
            self.assertEqual("initialized", payload["target_local"]["phase"])
            self.assertEqual("explicit", payload["target_local"]["product_selection"])
            self.assertTrue((target / "bin/governance").is_file())
            self.assertTrue((target / "scripts/governance_cli.py").is_file())
            self.assertTrue((target / "docs/agent-workflow/runtime-manifest.json").is_file())
            self.assertTrue((target / "docs/agent-workflow/workflow-pack/manifest.json").is_file())
            self.assertTrue((target / "docs/product/core/source/source-manifest.json").is_file())
            self.assertIn("local_commands", payload)
            self.assertIn("next_actions", payload)
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("init", step_ids)
            self.assertIn("target_local_verify_check", step_ids)
            self.assertIn("target_local_governance_status", step_ids)
            self.assertIn("target_local_workflow_plan", step_ids)

    def test_exported_pack_can_advance_to_product_structuring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Product Structuring\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and prepare product structuring in one bootstrap run.\n\n"
                "## Acceptance Criteria\n\n"
                "- A-001: The bootstrap output exposes the product authoring plan.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
                advance_product_structuring=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["initialized"])
            self.assertTrue(payload["advanced_product_structuring"])
            self.assertTrue(payload["product_structuring"]["ok"])
            self.assertTrue(payload["product_structuring"]["advance_check_ok"])
            self.assertTrue(payload["product_structuring"]["advance_ok"])
            self.assertTrue(payload["product_structuring"]["product_plan_ok"])
            self.assertEqual("product-structuring", payload["product_structuring"]["phase"])
            self.assertEqual("product-structuring", payload["target_local"]["phase"])
            self.assertEqual("do_not_guess_product_meaning", payload["product_plan"]["decision_policy"])
            self.assertIn("manual_authoring_summary", payload["product_plan"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("advance_product_structuring_check", step_ids)
            self.assertIn("advance_product_structuring", step_ids)
            self.assertIn("target_local_product_plan", step_ids)

    def test_exported_pack_previews_product_scaffold_from_product_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Product Scaffold\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and identify source-backed product chapters.\n\n"
                "## Acceptance Criteria\n\n"
                "- A-001: The bootstrap output previews supported product chapter scaffolds.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
                advance_product_structuring=True,
                product_scaffold_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["initialized"])
            self.assertTrue(payload["advanced_product_structuring"])
            self.assertTrue(payload["product_scaffold_preview_requested"])
            self.assertTrue(payload["product_scaffold_previewed"])
            self.assertTrue(payload["product_scaffold_preview_ok"])
            preview = payload["product_scaffold_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("do_not_guess_product_meaning", preview["decision_policy"])
            self.assertEqual(
                ["goals-and-requirements", "acceptance-criteria"],
                preview["selected_chapters"],
            )
            self.assertEqual(
                [
                    "goals-and-requirements=Goals and Requirements",
                    "acceptance-criteria=Acceptance Criteria",
                ],
                preview["command_args"],
            )
            scaffold_check = preview["scaffold_check"]
            self.assertTrue(scaffold_check["ok"])
            self.assertTrue(scaffold_check["check"])
            self.assertIn("docs/product/03-goals-and-requirements.md", scaffold_check["would_create"])
            self.assertIn("docs/product/08-acceptance-criteria.md", scaffold_check["would_create"])
            self.assertIn("docs/product/core/product-meta.md", scaffold_check["would_index"])
            self.assertFalse((target / "docs/product/03-goals-and-requirements.md").exists())
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_product_scaffold_preview", step_ids)

    def test_exported_pack_previews_product_structure_from_product_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Product Structure\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and identify source-backed product sections.\n"
                "- Preview deterministic product structuring without writing chapters.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output previews source-backed product structure updates.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
                advance_product_structuring=True,
                product_scaffold_preview=True,
                product_structure_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["product_scaffold_preview_ok"])
            self.assertTrue(payload["product_structure_preview_requested"])
            self.assertTrue(payload["product_structure_previewed"])
            self.assertTrue(payload["product_structure_preview_ok"])
            preview = payload["product_structure_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("do_not_guess_product_meaning", preview["decision_policy"])
            self.assertEqual("product_plan.suggested_mappings[].command_arg", preview["source"])
            self.assertEqual(
                [
                    "goals-and-requirements=Goals and Requirements",
                    "acceptance-criteria=Acceptance Criteria",
                ],
                preview["command_args"],
            )
            structure_check = preview["structure_check"]
            self.assertTrue(structure_check["ok"])
            self.assertTrue(structure_check["check"])
            self.assertIn("docs/product/03-goals-and-requirements.md", structure_check["would_update"])
            self.assertIn("docs/product/08-acceptance-criteria.md", structure_check["would_update"])
            self.assertFalse((target / "docs/product/03-goals-and-requirements.md").exists())
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_product_structure_preview", step_ids)

    def test_exported_pack_can_apply_product_structure_from_product_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Product Apply\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and write source-backed product chapters.\n"
                "- Keep deterministic structure apply limited to explicit PRD headings.\n\n"
                "## Acceptance Criteria\n\n"
                "- The target contains structured product chapters without scaffold placeholders.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
                advance_product_structuring=True,
                product_scaffold_preview=True,
                product_structure_preview=True,
                product_structure_apply=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["product_structure_apply_requested"])
            self.assertTrue(payload["product_structure_applied"])
            self.assertTrue(payload["product_structure_apply_ok"])
            apply_payload = payload["product_structure_apply"]
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["writes_state"])
            self.assertEqual("do_not_guess_product_meaning", apply_payload["decision_policy"])
            self.assertEqual("product_plan.suggested_mappings[].command_arg", apply_payload["source"])
            self.assertEqual(
                [
                    "goals-and-requirements=Goals and Requirements",
                    "acceptance-criteria=Acceptance Criteria",
                ],
                apply_payload["command_args"],
            )
            self.assertTrue(apply_payload["scaffold"]["ok"])
            self.assertTrue(apply_payload["structure_check"]["ok"])
            self.assertTrue(apply_payload["structure"]["ok"])
            self.assertIn("docs/product/03-goals-and-requirements.md", apply_payload["structure"]["updated"])
            self.assertIn("docs/product/08-acceptance-criteria.md", apply_payload["structure"]["updated"])
            self.assertTrue(apply_payload["post_status"]["ok"])
            self.assertEqual("product-structuring", apply_payload["post_workflow_plan"]["phase"])

            goals = target / "docs/product/03-goals-and-requirements.md"
            acceptance = target / "docs/product/08-acceptance-criteria.md"
            self.assertTrue(goals.is_file())
            self.assertTrue(acceptance.is_file())
            goals_text = goals.read_text(encoding="utf-8")
            acceptance_text = acceptance.read_text(encoding="utf-8")
            self.assertIn("Initialize governance and write source-backed product chapters.", goals_text)
            self.assertIn("A-001", acceptance_text)
            self.assertNotIn("governance:scaffold-placeholder", goals_text)
            self.assertNotIn("governance:scaffold-placeholder", acceptance_text)
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_product_scaffold_apply", step_ids)
            self.assertIn("target_local_product_structure_apply_check", step_ids)
            self.assertIn("target_local_product_structure_apply", step_ids)

    def test_exported_pack_can_advance_to_design_derivation_after_product_structure_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Design Derivation\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and write source-backed product chapters.\n"
                "- Advance to design derivation only after product verification is clean.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output exposes the design authoring plan.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
                advance_product_structuring=True,
                product_scaffold_preview=True,
                product_structure_preview=True,
                product_structure_apply=True,
                advance_design_derivation=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["advance_design_derivation_requested"])
            self.assertTrue(payload["advanced_design_derivation"])
            self.assertTrue(payload["product_structure_apply_ok"])
            design_derivation = payload["design_derivation"]
            self.assertTrue(design_derivation["ok"])
            self.assertTrue(design_derivation["product_verify_check_ok"])
            self.assertTrue(design_derivation["advance_check_ok"])
            self.assertTrue(design_derivation["advance_ok"])
            self.assertTrue(design_derivation["status_ok"])
            self.assertTrue(design_derivation["workflow_plan_ok"])
            self.assertTrue(design_derivation["design_plan_ok"])
            self.assertEqual("design-derivation", design_derivation["phase"])
            self.assertEqual("design-derivation", payload["target_local"]["phase"])
            self.assertEqual("design-derivation", payload["design_plan"]["phase"])
            self.assertIn("tracks", payload["design_plan"])
            self.assertTrue(payload["design_plan"]["tracks"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("product_clean_verify_check_before_design_derivation", step_ids)
            self.assertIn("advance_design_derivation_check", step_ids)
            self.assertIn("advance_design_derivation", step_ids)
            self.assertIn("target_local_design_plan", step_ids)

    def test_exported_pack_previews_design_scaffold_after_design_derivation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Design Scaffold Preview\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and prepare a design scaffold preflight.\n"
                "- Keep design preview read-only until authoring is explicitly approved.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output previews standard design scaffold files.\n",
                encoding="utf-8",
            )

            export = subprocess.run(
                [
                    sys.executable,
                    str(EXPORT),
                    "--output",
                    str(pack),
                    "--no-archive",
                    "--force",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, export.returncode, export.stdout + export.stderr)
            self.assertEqual("", export.stderr)
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=False,
                advance_product_structuring=True,
                product_scaffold_preview=True,
                product_structure_preview=True,
                product_structure_apply=True,
                advance_design_derivation=True,
                design_scaffold_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["advanced_design_derivation"])
            self.assertTrue(payload["design_scaffold_preview_requested"])
            self.assertTrue(payload["design_scaffold_previewed"])
            self.assertTrue(payload["design_scaffold_preview_ok"])
            preview = payload["design_scaffold_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("design-derivation", preview["phase"])
            scaffold_check = preview["scaffold_check"]
            self.assertTrue(scaffold_check["ok"])
            self.assertTrue(scaffold_check["check"])
            self.assertIn("docs/architecture/01-system-context.md", scaffold_check["would_create"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", scaffold_check["would_create"])
            self.assertIn("docs/development/03-verification-log.md", scaffold_check["would_create"])
            self.assertIn("docs/architecture/01-system-context.md", scaffold_check["would_index"])
            self.assertFalse((target / "docs/architecture/01-system-context.md").exists())
            self.assertFalse((target / "docs/api/endpoints/01-endpoint-contract.md").exists())
            self.assertFalse((target / "docs/development/03-verification-log.md").exists())
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_design_scaffold_preview", step_ids)


def _run_bootstrap(
    testcase: unittest.TestCase,
    pack: Path,
    *,
    target: Path,
    product: Path,
    check: bool,
    advance_product_structuring: bool = False,
    product_scaffold_preview: bool = False,
    product_structure_preview: bool = False,
    product_structure_apply: bool = False,
    advance_design_derivation: bool = False,
    design_scaffold_preview: bool = False,
) -> dict[str, object]:
    argv = [
        sys.executable,
        str(pack / "scripts/bootstrap_consumer_project.py"),
        "--target",
        str(target),
        "--product",
        str(product),
        "--profile",
        "service",
        "--project-name",
        "Consumer Bootstrap Smoke",
        "--json",
    ]
    if check:
        argv.insert(-1, "--check")
    if advance_product_structuring:
        argv.insert(-1, "--advance-product-structuring")
    if product_scaffold_preview:
        argv.insert(-1, "--product-scaffold-preview")
    if product_structure_preview:
        argv.insert(-1, "--product-structure-preview")
    if product_structure_apply:
        argv.insert(-1, "--product-structure-apply")
    if advance_design_derivation:
        argv.insert(-1, "--advance-design-derivation")
    if design_scaffold_preview:
        argv.insert(-1, "--design-scaffold-preview")
    result = subprocess.run(
        argv,
        cwd=pack,
        text=True,
        capture_output=True,
        check=False,
    )
    testcase.assertEqual(0, result.returncode, result.stdout + result.stderr)
    testcase.assertEqual("", result.stderr)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        testcase.fail(f"bootstrap did not return JSON: {error}: {result.stdout}")
    testcase.assertIsInstance(payload, dict)
    return payload


if __name__ == "__main__":
    unittest.main()
