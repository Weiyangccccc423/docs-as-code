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


def _run_bootstrap(
    testcase: unittest.TestCase,
    pack: Path,
    *,
    target: Path,
    product: Path,
    check: bool,
    advance_product_structuring: bool = False,
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
