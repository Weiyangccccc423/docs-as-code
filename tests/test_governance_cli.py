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


if __name__ == "__main__":
    unittest.main()
