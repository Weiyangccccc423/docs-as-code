import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "governance_cli.py"


class GovernanceCliTest(unittest.TestCase):
    def test_env_repair_writes_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "env",
                    "--target",
                    str(target),
                    "--repair",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            repair_plan = target / ".governance/env-repair.md"
            self.assertTrue(repair_plan.exists())
            self.assertIn("Environment Repair Plan", repair_plan.read_text(encoding="utf-8"))

    def test_env_json_reports_tools_and_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "env",
                    "--target",
                    str(target),
                    "--repair",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertIn("tools", payload)
            self.assertIn("system", payload)
            self.assertIn("package_manager", payload)
            self.assertIn("git", payload)
            self.assertIn("install_plan", payload)
            self.assertIn("needs_escalation", payload)
            self.assertIn("repairs", payload)
            self.assertTrue(any(tool["name"] == "python3" for tool in payload["tools"]))
            self.assertEqual(str(target / ".governance/env-repair.md"), payload["repair_plan"])

    def test_init_check_json_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual([], payload["conflicts"])
            self.assertIn("README.md", payload["would_write"])
            self.assertFalse(target.exists())

    def test_init_json_reports_conflicts_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            readme = target / "README.md"
            readme.write_text("# Existing\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn({"path": "README.md", "reason": "generated file already exists"}, payload["conflicts"])
            self.assertEqual("# Existing\n", readme.read_text(encoding="utf-8"))
            self.assertFalse((target / "docs/README.md").exists())

    def test_init_force_json_allows_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            (target / "README.md").write_text("# Existing\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--project-name",
                    "Forced Demo",
                    "--force",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual("initialized", payload["state"]["phase"])
            self.assertIn("# Forced Demo", (target / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((target / "docs/README.md").exists())

    def test_init_verify_and_status_update_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--profile",
                    "web-app",
                    "--project-name",
                    "Governed Demo",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state_path = target / ".governance/state.json"
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("initialized", state["phase"])
            self.assertEqual("web-app", state["profile"])
            self.assertEqual("Governed Demo", state["project_name"])
            self.assertEqual("product.md", Path(state["product_source"]).name)

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(state["last_verification"]["ok"])

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_result.returncode, status_result.stderr)
            self.assertIn("phase: initialized", status_result.stdout)
            self.assertIn("profile: web-app", status_result.stdout)

    def test_init_verify_and_status_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--profile",
                    "service",
                    "--project-name",
                    "JSON Demo",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            init_payload = json.loads(init_result.stdout)
            self.assertTrue(init_payload["ok"])
            self.assertEqual(str(target), init_payload["target"])
            self.assertEqual("initialized", init_payload["state"]["phase"])

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            verify_payload = json.loads(verify_result.stdout)
            self.assertTrue(verify_payload["ok"])
            self.assertEqual([], verify_payload["errors"])
            self.assertEqual(str(target), verify_payload["target"])

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_result.returncode, status_result.stderr)
            status_payload = json.loads(status_result.stdout)
            self.assertTrue(status_payload["ok"])
            self.assertEqual("service", status_payload["state"]["profile"])

    def test_verify_json_reports_structured_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n", encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("findings", payload)
            self.assertIn(
                {
                    "code": "docs_readme_unindexed_file",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md is not indexed in docs/product/README.md",
                },
                payload["findings"],
            )


if __name__ == "__main__":
    unittest.main()
