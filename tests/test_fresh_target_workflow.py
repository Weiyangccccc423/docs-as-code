import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "governance_cli.py"


def _agent_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    env.pop("MAKELEVEL", None)
    return env


def _run_json(testcase: unittest.TestCase, argv: list[str], cwd: Path | str) -> dict[str, object]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=_agent_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    testcase.assertEqual(0, result.returncode, result.stderr)
    testcase.assertEqual("", result.stderr)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        testcase.fail(f"command did not return JSON: {argv!r}: {error}: {result.stdout}")
    testcase.assertIsInstance(payload, dict)
    return payload


class FreshTargetWorkflowTest(unittest.TestCase):
    def test_fresh_folder_initializes_and_uses_target_local_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "fresh-target"
            product = base / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goal\n\n"
                "Ship a governed project from one product document.\n\n"
                "## Acceptance\n\n"
                "- The initialized repository exposes local governance checks.\n",
                encoding="utf-8",
            )

            env_check = _run_json(
                self,
                [
                    sys.executable,
                    str(CLI),
                    "env",
                    "--repair",
                    "--check",
                    "--target",
                    str(target),
                    "--json",
                ],
                cwd=ROOT,
            )
            self.assertTrue(env_check["ok"])
            self.assertTrue(env_check["check"])
            self.assertEqual([], env_check["missing_required"])
            self.assertIn("repair_commands", env_check)
            self.assertIn("would_repair", env_check)
            self.assertNotIn("local_commands", env_check)
            self.assertFalse(target.exists())

            init_check = _run_json(
                self,
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--check",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--profile",
                    "service",
                    "--project-name",
                    "Fresh Target Smoke",
                    "--json",
                ],
                cwd=ROOT,
            )
            self.assertTrue(init_check["ok"])
            self.assertEqual([], init_check["conflicts"])
            self.assertIn(".governance/state.json", init_check["would_write"])
            self.assertFalse(target.exists())

            init_payload = _run_json(
                self,
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
                    "Fresh Target Smoke",
                    "--json",
                ],
                cwd=ROOT,
            )
            self.assertTrue(init_payload["ok"])
            self.assertEqual("initialized", init_payload["state"]["phase"])
            self.assertEqual("ready_for_structuring", init_payload["state"]["product_import_status"])
            self.assertTrue((target / "bin/governance").is_file())
            self.assertTrue((target / "scripts/governance_cli.py").is_file())
            self.assertTrue((target / "docs/agent-workflow/runtime-manifest.json").is_file())
            self.assertTrue((target / "docs/agent-workflow/workflow-pack/manifest.json").is_file())
            self.assertTrue((target / "docs/product/core/PRD.md").is_file())
            self.assertTrue((target / "docs/product/core/source/source-manifest.json").is_file())

            verify_check = _run_json(
                self,
                [sys.executable, str(CLI), "verify", str(target), "--check", "--json"],
                cwd=ROOT,
            )
            self.assertTrue(verify_check["ok"])
            self.assertTrue(verify_check["check"])
            self.assertFalse(verify_check["state_updated"])
            self.assertEqual([], verify_check["findings"])

            status = _run_json(
                self,
                [sys.executable, str(CLI), "status", str(target), "--json"],
                cwd=ROOT,
            )
            self.assertTrue(status["ok"])
            self.assertEqual("service", status["state"]["profile"])
            self.assertEqual("Fresh Target Smoke", status["state"]["project_name"])

            next_actions = {action["id"]: action for action in status["next_actions"]}
            preflight_action = next_actions["advance-product-structuring-check"]
            preflight = _run_json(self, preflight_action["argv"], cwd=preflight_action["cwd"])
            self.assertTrue(preflight["ok"])
            self.assertTrue(preflight["check"])
            self.assertTrue(preflight["would_advance"])
            self.assertFalse(preflight["advanced"])

            local_commands = {command["make_target"]: command for command in status["local_commands"]}
            for make_target in ("verify-check", "governance-status", "repair-env-check"):
                command = local_commands[make_target]
                self.assertFalse(command["approval_required"])
                self.assertFalse(command["writes_state"])
                payload = _run_json(self, command["argv"], cwd=command["cwd"])
                self.assertTrue(payload["ok"])

            target_local_verify = _run_json(
                self,
                ["bin/governance", "verify", ".", "--check", "--json"],
                cwd=target,
            )
            self.assertTrue(target_local_verify["ok"])
            self.assertEqual(".", target_local_verify["target"])

            target_local_status = _run_json(
                self,
                ["bin/governance", "status", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(target_local_status["ok"])
            self.assertEqual(".", target_local_status["target"])
            self.assertEqual("initialized", target_local_status["state"]["phase"])
