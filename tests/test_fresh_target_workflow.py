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


def _run_json(
    testcase: unittest.TestCase,
    argv: list[str],
    cwd: Path | str,
    expected_returncode: int = 0,
) -> dict[str, object]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=_agent_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    testcase.assertEqual(expected_returncode, result.returncode, result.stderr)
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
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n"
                "- Expose local governance checks after initialization.\n\n"
                "## Acceptance Criteria\n\n"
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

            apply_action = next_actions["advance-product-structuring"]
            advanced = _run_json(self, apply_action["argv"], cwd=apply_action["cwd"])
            self.assertTrue(advanced["ok"])
            self.assertTrue(advanced["advanced"])
            self.assertEqual("product-structuring", advanced["state"]["phase"])
            self.assertEqual("advance-design-derivation-check", advanced["next_actions"][0]["id"])

            scaffold_check = _run_json(
                self,
                [
                    "bin/governance",
                    "scaffold",
                    "product",
                    ".",
                    "--chapter",
                    "goals-and-requirements",
                    "--chapter",
                    "acceptance-criteria",
                    "--check",
                    "--json",
                ],
                cwd=target,
            )
            self.assertTrue(scaffold_check["ok"])
            self.assertTrue(scaffold_check["check"])
            self.assertEqual([], scaffold_check["created"])
            self.assertEqual([], scaffold_check["indexed"])
            self.assertIn("docs/product/03-goals-and-requirements.md", scaffold_check["would_create"])
            self.assertIn("docs/product/08-acceptance-criteria.md", scaffold_check["would_create"])
            self.assertIn("docs/product/03-goals-and-requirements.md", scaffold_check["would_index"])
            self.assertIn("docs/product/08-acceptance-criteria.md", scaffold_check["would_index"])
            self.assertIn("docs/product/core/product-meta.md", scaffold_check["would_index"])
            self.assertNotIn("local_commands", scaffold_check)
            self.assertNotIn("next_actions", scaffold_check)
            self.assertFalse((target / "docs/product/03-goals-and-requirements.md").exists())
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())

            scaffold = _run_json(
                self,
                [
                    "bin/governance",
                    "scaffold",
                    "product",
                    ".",
                    "--chapter",
                    "goals-and-requirements",
                    "--chapter",
                    "acceptance-criteria",
                    "--json",
                ],
                cwd=target,
            )
            self.assertTrue(scaffold["ok"])
            self.assertIn("docs/product/03-goals-and-requirements.md", scaffold["created"])
            self.assertIn("docs/product/08-acceptance-criteria.md", scaffold["created"])
            self.assertIn("docs/product/core/product-meta.md", scaffold["indexed"])
            self.assertEqual(
                {
                    "current": "product-structuring",
                    "expected": "product-structuring",
                    "matches": True,
                    "message": "recorded phase matches scaffold phase",
                },
                scaffold["scaffold_phase"],
            )
            self.assertEqual("advance-design-derivation-check", scaffold["next_actions"][0]["id"])
            blockers = {blocker["path"]: blocker for blocker in scaffold["next_actions_blocked_by"]}
            self.assertEqual(
                "governance_scaffold_placeholder",
                blockers["docs/product/03-goals-and-requirements.md"]["code"],
            )
            self.assertEqual(
                "governance_scaffold_placeholder",
                blockers["docs/product/08-acceptance-criteria.md"]["code"],
            )
            self.assertIn("before running next_actions", blockers["docs/product/03-goals-and-requirements.md"]["message"])

            goals = (target / "docs/product/03-goals-and-requirements.md").read_text(encoding="utf-8")
            acceptance = (target / "docs/product/08-acceptance-criteria.md").read_text(encoding="utf-8")
            product_meta = (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8")
            self.assertIn("governance:scaffold-placeholder", goals)
            self.assertIn("[PRD](core/PRD.md)", goals)
            self.assertIn("A-NNN", acceptance)
            self.assertIn("[Goals and Requirements](../03-goals-and-requirements.md)", product_meta)
            self.assertIn("[Acceptance Criteria](../08-acceptance-criteria.md)", product_meta)

            blocked_verify = _run_json(
                self,
                ["bin/governance", "verify", ".", "--check", "--json"],
                cwd=target,
                expected_returncode=1,
            )
            self.assertFalse(blocked_verify["ok"])
            self.assertTrue(blocked_verify["check"])
            self.assertFalse(blocked_verify["state_updated"])
            self.assertTrue(
                any(
                    finding["code"] == "governance_scaffold_placeholder"
                    and finding["path"] == "docs/product/03-goals-and-requirements.md"
                    for finding in blocked_verify["findings"]
                )
            )

            structure_check = _run_json(
                self,
                [
                    "bin/governance",
                    "product",
                    "structure",
                    ".",
                    "--chapter",
                    "goals-and-requirements=Goals and Requirements",
                    "--chapter",
                    "acceptance-criteria=Acceptance Criteria",
                    "--check",
                    "--json",
                ],
                cwd=target,
            )
            self.assertTrue(structure_check["ok"])
            self.assertTrue(structure_check["check"])
            self.assertEqual([], structure_check["updated"])
            self.assertIn("docs/product/03-goals-and-requirements.md", structure_check["would_update"])
            self.assertIn("docs/product/08-acceptance-criteria.md", structure_check["would_update"])

            structured = _run_json(
                self,
                [
                    "bin/governance",
                    "product",
                    "structure",
                    ".",
                    "--chapter",
                    "goals-and-requirements=Goals and Requirements",
                    "--chapter",
                    "acceptance-criteria=Acceptance Criteria",
                    "--json",
                ],
                cwd=target,
            )
            self.assertTrue(structured["ok"])
            self.assertIn("docs/product/03-goals-and-requirements.md", structured["updated"])
            self.assertIn("docs/product/08-acceptance-criteria.md", structured["updated"])
            self.assertEqual("advance-design-derivation-check", structured["next_actions"][0]["id"])

            goals = (target / "docs/product/03-goals-and-requirements.md").read_text(encoding="utf-8")
            acceptance = (target / "docs/product/08-acceptance-criteria.md").read_text(encoding="utf-8")
            self.assertNotIn("governance:scaffold-placeholder", goals)
            self.assertIn("Expose local governance checks after initialization.", goals)
            self.assertIn("## A-001 Initialized Repository Exposes Local Governance Checks", acceptance)

            clean_verify = _run_json(
                self,
                ["bin/governance", "verify", ".", "--check", "--json"],
                cwd=target,
            )
            self.assertTrue(clean_verify["ok"])
            self.assertEqual([], clean_verify["findings"])

            design_preflight = _run_json(
                self,
                ["bin/governance", "advance", "design-derivation", ".", "--check", "--json"],
                cwd=target,
            )
            self.assertTrue(design_preflight["ok"])
            self.assertTrue(design_preflight["would_advance"])
