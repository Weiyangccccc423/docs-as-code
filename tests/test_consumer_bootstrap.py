import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_consumer_project import (
    _apply_implementation_closeout,
    _maybe_auto_repair_env,
    _preview_implementation_closeout,
)


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
            self.assertTrue(check_payload["authority_skill_inventory"]["ok"])
            self.assertFalse(check_payload["authority_skill_inventory"]["strict"])
            self.assertGreaterEqual(check_payload["authority_skill_inventory"]["required_skill_count"], 19)
            self.assertEqual(
                {
                    "pack_manifest_verify",
                    "pack_verify",
                    "authority_skill_inventory",
                    "env_repair_check",
                    "init_check",
                },
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
            self.assertTrue(payload["authority_skill_inventory"]["ok"])
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
            self.assertIn("authority_skill_inventory", step_ids)
            self.assertIn("init", step_ids)
            self.assertIn("target_local_verify_check", step_ids)
            self.assertIn("target_local_governance_status", step_ids)
            self.assertIn("target_local_workflow_plan", step_ids)

    def test_strict_authority_skills_blocks_bootstrap_when_agent_skills_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            codex_home = base / "empty-codex-home"
            home = base / "empty-home"
            (codex_home / "skills").mkdir(parents=True)
            (home / ".codex" / "skills").mkdir(parents=True)
            product.write_text(
                "# Consumer Bootstrap Product\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap reports missing authority skills before target writes.\n",
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
            self.assertTrue(json.loads(export.stdout)["ok"])

            payload = _run_bootstrap(
                self,
                pack,
                target=target,
                product=product,
                check=True,
                strict_authority_skills=True,
                expected_returncode=1,
                env={"CODEX_HOME": str(codex_home), "HOME": str(home)},
            )

            self.assertFalse(payload["ok"])
            self.assertFalse(payload["initialized"])
            self.assertTrue(payload["strict_authority_skills"])
            self.assertEqual("authority skill inventory failed", payload["error"])
            self.assertEqual("authority_skill_inventory", payload["steps"][-1]["id"])
            self.assertEqual("authority_skill_inventory", payload["failed_step"]["id"])
            self.assertFalse(payload["failed_payload"]["ok"])
            self.assertTrue(payload["failed_payload"]["strict"])
            self.assertIn("senior-architect", payload["failed_payload"]["missing_skills"])
            self.assertFalse(target.exists())

    def test_auto_repair_env_runs_write_mode_repair_then_rechecks_when_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "pack"
            target = base / "target"
            scripts = pack / "scripts"
            scripts.mkdir(parents=True)
            target.mkdir()
            (scripts / "governance_cli.py").write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "from pathlib import Path\n"
                "target = Path(sys.argv[sys.argv.index('--target') + 1])\n"
                "log = target / 'env-calls.jsonl'\n"
                "log.write_text(log.read_text(encoding='utf-8') + json.dumps(sys.argv[1:]) + '\\n' if log.exists() else json.dumps(sys.argv[1:]) + '\\n', encoding='utf-8')\n"
                "if '--check' in sys.argv:\n"
                "    print(json.dumps({'ok': True, 'check': True, 'missing_required': [], 'repair_decision': {'decision': 'continue_workflow'}}))\n"
                "else:\n"
                "    print(json.dumps({'ok': True, 'check': False, 'repair_execution': {'status': 'applied'}, 'repairs': [{'kind': 'repair_plan'}]}))\n",
                encoding="utf-8",
            )
            initial_check = {
                "ok": False,
                "check": True,
                "missing_required": ["git"],
                "repair_execution": {"can_auto_apply": True, "status": "ready_to_apply"},
                "repair_decision": {
                    "decision": "run_repair_actions",
                    "requires_approval": False,
                    "manual_repair_required": False,
                    "runnable_action_ids": ["env-repair-apt-update", "env-repair-apt-install"],
                    "approval_action_ids": [],
                    "manual_action_ids": [],
                },
            }
            steps: list[dict[str, object]] = []

            payload = _maybe_auto_repair_env(
                steps,
                pack,
                target,
                initial_check,
                auto_repair_env=True,
                check=False,
            )

            self.assertTrue(payload["requested"])
            self.assertTrue(payload["applied"])
            self.assertFalse(payload["skipped"])
            self.assertEqual("", payload["skip_reason"])
            self.assertEqual(initial_check, payload["initial_check"])
            self.assertTrue(payload["ok"])
            self.assertEqual("continue_workflow", payload["decision"])
            self.assertEqual("continue", payload["status"])
            self.assertFalse(payload["stop_before_workflow"])
            self.assertTrue(payload["can_continue"])
            self.assertFalse(payload["can_auto_apply"])
            self.assertFalse(payload["requires_approval"])
            self.assertFalse(payload["manual_repair_required"])
            self.assertEqual([], payload["runnable_action_ids"])
            self.assertEqual([], payload["approval_action_ids"])
            self.assertEqual([], payload["manual_action_ids"])
            self.assertEqual("continue workflow", payload["next_step"])
            self.assertTrue(payload["final_env_check_ok"])
            self.assertEqual([], payload["final_missing_required"])
            self.assertTrue(payload["repair"]["ok"])
            self.assertFalse(payload["repair"]["check"])
            self.assertTrue(payload["post_check"]["ok"])
            self.assertTrue(payload["final_env_check"]["ok"])
            self.assertEqual(
                ["env_repair_auto_apply", "env_repair_check_after_auto_repair"],
                [step["id"] for step in steps],
            )
            calls = [
                json.loads(line)
                for line in (target / "env-calls.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [
                    ["env", "--repair", "--target", str(target), "--json"],
                    ["env", "--repair", "--check", "--target", str(target), "--json"],
                ],
                calls,
            )

    def test_auto_repair_env_skips_when_repair_requires_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "pack"
            target = base / "target"
            pack.mkdir()
            target.mkdir()
            initial_check = {
                "ok": False,
                "check": True,
                "missing_required": ["git"],
                "repair_execution": {"can_auto_apply": False, "status": "approval_required"},
                "repair_decision": {
                    "decision": "request_approval",
                    "requires_approval": True,
                    "approval_action_ids": ["env-repair-apt-install"],
                },
            }
            steps: list[dict[str, object]] = []

            payload = _maybe_auto_repair_env(
                steps,
                pack,
                target,
                initial_check,
                auto_repair_env=True,
                check=False,
            )

            self.assertTrue(payload["requested"])
            self.assertFalse(payload["applied"])
            self.assertTrue(payload["skipped"])
            self.assertEqual("environment repair requires approval", payload["skip_reason"])
            self.assertFalse(payload["ok"])
            self.assertEqual("request_approval", payload["decision"])
            self.assertEqual("approval_required", payload["status"])
            self.assertTrue(payload["stop_before_workflow"])
            self.assertFalse(payload["can_continue"])
            self.assertFalse(payload["can_auto_apply"])
            self.assertTrue(payload["requires_approval"])
            self.assertFalse(payload["manual_repair_required"])
            self.assertEqual([], payload["runnable_action_ids"])
            self.assertEqual(["env-repair-apt-install"], payload["approval_action_ids"])
            self.assertEqual([], payload["manual_action_ids"])
            self.assertEqual("request approval before running repair_commands", payload["next_step"])
            self.assertEqual(initial_check, payload["final_env_check"])
            self.assertEqual([], steps)

    def test_auto_repair_env_skips_when_manual_repair_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "pack"
            target = base / "target"
            pack.mkdir()
            target.mkdir()
            initial_check = {
                "ok": False,
                "check": True,
                "missing_required": ["node"],
                "repair_execution": {
                    "can_auto_apply": False,
                    "manual_repair_required": True,
                    "status": "manual_repair_required",
                    "next_step": "complete manual_repairs before continuing",
                },
                "repair_decision": {
                    "decision": "complete_manual_repairs",
                    "manual_repair_required": True,
                    "manual_action_ids": ["env-manual-repair-node"],
                },
            }
            steps: list[dict[str, object]] = []

            payload = _maybe_auto_repair_env(
                steps,
                pack,
                target,
                initial_check,
                auto_repair_env=True,
                check=False,
            )

            self.assertTrue(payload["requested"])
            self.assertFalse(payload["applied"])
            self.assertTrue(payload["skipped"])
            self.assertEqual("environment repair requires manual action", payload["skip_reason"])
            self.assertFalse(payload["ok"])
            self.assertEqual("complete_manual_repairs", payload["decision"])
            self.assertEqual("manual_repair_required", payload["status"])
            self.assertTrue(payload["stop_before_workflow"])
            self.assertFalse(payload["can_continue"])
            self.assertFalse(payload["can_auto_apply"])
            self.assertFalse(payload["requires_approval"])
            self.assertTrue(payload["manual_repair_required"])
            self.assertEqual([], payload["runnable_action_ids"])
            self.assertEqual([], payload["approval_action_ids"])
            self.assertEqual(["env-manual-repair-node"], payload["manual_action_ids"])
            self.assertEqual("complete manual_repairs before continuing", payload["next_step"])
            self.assertEqual(initial_check, payload["final_env_check"])
            self.assertEqual([], steps)

    def test_auto_repair_env_reports_not_requested_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "pack"
            target = base / "target"
            pack.mkdir()
            target.mkdir()
            initial_check = {
                "ok": False,
                "check": True,
                "missing_required": ["git"],
                "repair_execution": {
                    "can_auto_apply": True,
                    "status": "ready_to_apply",
                    "next_step": "run repair_commands[].argv from repair_commands[].cwd",
                },
                "repair_decision": {
                    "decision": "run_repair_actions",
                    "runnable_action_ids": ["env-repair-apt-install"],
                    "approval_action_ids": [],
                    "manual_action_ids": [],
                },
            }
            steps: list[dict[str, object]] = []

            payload = _maybe_auto_repair_env(
                steps,
                pack,
                target,
                initial_check,
                auto_repair_env=False,
                check=False,
            )

            self.assertFalse(payload["requested"])
            self.assertFalse(payload["applied"])
            self.assertTrue(payload["skipped"])
            self.assertEqual("automatic environment repair was not requested", payload["skip_reason"])
            self.assertFalse(payload["ok"])
            self.assertEqual("auto_repair_not_requested", payload["decision"])
            self.assertEqual("not_requested", payload["status"])
            self.assertTrue(payload["stop_before_workflow"])
            self.assertFalse(payload["can_continue"])
            self.assertFalse(payload["can_auto_apply"])
            self.assertFalse(payload["requires_approval"])
            self.assertFalse(payload["manual_repair_required"])
            self.assertEqual(["env-repair-apt-install"], payload["runnable_action_ids"])
            self.assertEqual([], payload["approval_action_ids"])
            self.assertEqual([], payload["manual_action_ids"])
            self.assertEqual("rerun with --auto-repair-env or repair environment manually", payload["next_step"])
            self.assertEqual(initial_check, payload["final_env_check"])
            self.assertEqual([], steps)

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

    def test_workflow_preset_expands_to_product_structure_apply_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Product Preset\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and write source-backed product chapters via preset routing.\n"
                "- Keep preset behavior equivalent to the explicit product structure flag chain.\n\n"
                "## Acceptance Criteria\n\n"
                "- A-001: The bootstrap output exposes expanded preset flags and writes product chapters.\n",
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
                workflow_preset="product-structure",
            )

            self.assertTrue(payload["ok"])
            self.assertEqual("product-structure", payload["workflow_preset"])
            self.assertEqual(
                [
                    "advance_product_structuring",
                    "product_scaffold_preview",
                    "product_structure_preview",
                    "product_structure_apply",
                ],
                payload["workflow_preset_expanded_flags"],
            )
            self.assertTrue(payload["advanced_product_structuring"])
            self.assertTrue(payload["product_scaffold_preview_requested"])
            self.assertTrue(payload["product_structure_preview_requested"])
            self.assertTrue(payload["product_structure_apply_requested"])
            self.assertTrue(payload["product_structure_apply_ok"])
            self.assertEqual("product-structuring", payload["target_local"]["phase"])
            self.assertTrue((target / "docs/product/03-goals-and-requirements.md").is_file())
            self.assertTrue((target / "docs/product/08-acceptance-criteria.md").is_file())
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_product_scaffold_apply", step_ids)
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

    def test_exported_pack_can_apply_design_scaffold_after_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Design Scaffold Apply\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and write the standard design scaffold.\n"
                "- Keep scaffold placeholders visible as blockers after writing.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output exposes placeholder blockers after design scaffold apply.\n",
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
                design_scaffold_apply=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["design_scaffold_apply_requested"])
            self.assertTrue(payload["design_scaffold_applied"])
            self.assertTrue(payload["design_scaffold_apply_ok"])
            apply_payload = payload["design_scaffold_apply"]
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["writes_state"])
            self.assertEqual("design-derivation", apply_payload["phase"])
            scaffold = apply_payload["scaffold"]
            self.assertTrue(scaffold["ok"])
            self.assertIn("next_actions_blocked_by", scaffold)
            blocker_paths = {
                blocker["path"]
                for blocker in scaffold["next_actions_blocked_by"]
                if isinstance(blocker, dict)
            }
            self.assertIn("docs/architecture/01-system-context.md", blocker_paths)
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", blocker_paths)
            self.assertIn("docs/development/03-verification-log.md", blocker_paths)
            self.assertTrue(apply_payload["post_status"]["ok"])
            self.assertEqual("design-derivation", apply_payload["post_workflow_plan"]["phase"])
            self.assertFalse(apply_payload["post_verify_check"]["ok"])
            self.assertTrue(apply_payload["post_verify_blocked_by_placeholders"])

            system_context = target / "docs/architecture/01-system-context.md"
            endpoint_contract = target / "docs/api/endpoints/01-endpoint-contract.md"
            verification_log = target / "docs/development/03-verification-log.md"
            self.assertTrue(system_context.is_file())
            self.assertTrue(endpoint_contract.is_file())
            self.assertTrue(verification_log.is_file())
            self.assertIn("governance:scaffold-placeholder", system_context.read_text(encoding="utf-8"))
            self.assertIn("METHOD /product-derived-path", endpoint_contract.read_text(encoding="utf-8"))
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_design_scaffold_apply", step_ids)
            self.assertIn("target_local_verify_check_after_design_scaffold_apply", step_ids)

    def test_exported_pack_previews_design_authoring_after_scaffold_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Design Authoring Preview\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose every design authoring queue.\n"
                "- Keep authoring preview read-only after design scaffold is written.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output includes all design authoring payloads for agent routing.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["design_authoring_preview_requested"])
            self.assertTrue(payload["design_authoring_previewed"])
            self.assertTrue(payload["design_authoring_preview_ok"])
            preview = payload["design_authoring_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("design-derivation", preview["phase"])
            expected_queues = [
                "architecture-authoring",
                "api-authoring",
                "backend-authoring",
                "data-model-authoring",
                "ui-interaction-authoring",
                "frontend-authoring",
                "test-strategy-authoring",
                "implementation-planning-authoring",
                "architecture-decisions-authoring",
            ]
            self.assertEqual(expected_queues, preview["queue_order"])
            self.assertEqual(set(expected_queues), set(preview["queues"].keys()))
            architecture = preview["queues"]["architecture-authoring"]
            self.assertTrue(architecture["ok"])
            self.assertEqual("do_not_guess_architecture_boundaries", architecture["decision_policy"])
            self.assertIn("authoring_summary", architecture)
            self.assertIn("active_work", architecture)
            self.assertIn("authoring_tasks", architecture)
            api = preview["queues"]["api-authoring"]
            self.assertTrue(api["ok"])
            self.assertEqual("do_not_guess_contract_details", api["decision_policy"])
            self.assertIn("authoring_tasks", api)
            step_ids = {step["id"] for step in payload["steps"]}
            for queue_id in expected_queues:
                self.assertIn(f"target_local_design_{queue_id.replace('-', '_')}_preview", step_ids)

    def test_exported_pack_previews_implementation_readiness_after_design_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Implementation Readiness Preview\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose implementation readiness routing.\n"
                "- Keep implementation readiness preview read-only until design docs are source-backed.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output includes implementation gate and plan blockers for agent routing.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
                implementation_readiness_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["implementation_readiness_preview_requested"])
            self.assertTrue(payload["implementation_readiness_previewed"])
            self.assertTrue(payload["implementation_readiness_preview_ok"])
            preview = payload["implementation_readiness_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("design-derivation", preview["phase"])
            self.assertFalse(preview["implementation_ready"])
            self.assertFalse(preview["readiness_ok"])
            self.assertFalse(preview["verify_ok"])
            self.assertFalse(preview["gate_ok"])
            self.assertFalse(preview["implementation_plan_ok"])
            self.assertFalse(preview["verify_check"]["ok"])
            self.assertFalse(preview["gate"]["ok"])
            self.assertFalse(preview["implementation_plan"]["ok"])
            self.assertIn(
                "implementation plan requires recorded phase implementation",
                preview["implementation_plan"]["errors"],
            )
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_verify_check_implementation_readiness_preview", step_ids)
            self.assertIn("target_local_implementation_gate_preview", step_ids)
            self.assertIn("target_local_implementation_plan_preview", step_ids)

    def test_exported_pack_previews_implementation_advance_without_writing_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Implementation Advance Preview\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose implementation phase advance blockers.\n"
                "- Keep implementation phase preview read-only while design placeholders remain.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output includes implementation advance preflight blockers.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
                implementation_readiness_preview=True,
                implementation_advance_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["implementation_readiness_preview_ok"])
            self.assertTrue(payload["implementation_advance_preview_requested"])
            self.assertTrue(payload["implementation_advance_previewed"])
            self.assertTrue(payload["implementation_advance_preview_ok"])
            preview = payload["implementation_advance_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("implementation", preview["phase"])
            self.assertFalse(preview["advance_ready"])
            self.assertFalse(preview["advance_check_ok"])
            self.assertFalse(preview["would_advance"])
            self.assertFalse(preview["advanced"])
            advance_check = preview["advance_check"]
            self.assertFalse(advance_check["ok"])
            self.assertTrue(advance_check["check"])
            self.assertFalse(advance_check["advanced"])
            self.assertEqual("design-derivation", advance_check["state"]["phase"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_implementation_advance_preview", step_ids)

    def test_exported_pack_skips_implementation_advance_apply_until_preview_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Implementation Advance Apply\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose implementation advance apply routing.\n"
                "- Skip implementation phase writes while design placeholders remain.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output reports skipped implementation advance apply without changing phase.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
                implementation_readiness_preview=True,
                implementation_advance_preview=True,
                implementation_advance_apply=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["implementation_advance_preview_ok"])
            self.assertTrue(payload["implementation_advance_apply_requested"])
            self.assertFalse(payload["implementation_advance_applied"])
            self.assertTrue(payload["implementation_advance_apply_ok"])
            apply_payload = payload["implementation_advance_apply"]
            self.assertTrue(apply_payload["ok"])
            self.assertFalse(apply_payload["check"])
            self.assertTrue(apply_payload["writes_state"])
            self.assertFalse(apply_payload["advance_ready"])
            self.assertTrue(apply_payload["apply_skipped"])
            self.assertEqual("implementation advance preview did not pass", apply_payload["skip_reason"])
            self.assertEqual({}, apply_payload["advance"])
            self.assertEqual("design-derivation", payload["target_local"]["phase"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("target_local_implementation_advance_preview", step_ids)
            self.assertNotIn("target_local_implementation_advance_apply", step_ids)

    def test_exported_pack_skips_implementation_start_preview_until_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Implementation Start Preview\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose implementation start routing.\n"
                "- Keep implementation start preview read-only while readiness is blocked.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output skips task start checks until implementation readiness passes.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
                implementation_readiness_preview=True,
                implementation_start_preview=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["implementation_readiness_preview_ok"])
            self.assertTrue(payload["implementation_start_preview_requested"])
            self.assertTrue(payload["implementation_start_previewed"])
            self.assertTrue(payload["implementation_start_preview_ok"])
            preview = payload["implementation_start_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("design-derivation", preview["phase"])
            self.assertEqual(
                "implementation_readiness_preview.implementation_plan.active_work.task_id",
                preview["source"],
            )
            self.assertEqual("", preview["task_id"])
            self.assertFalse(preview["start_ready"])
            self.assertTrue(preview["preview_skipped"])
            self.assertEqual("implementation readiness preview did not pass", preview["skip_reason"])
            self.assertEqual({}, preview["implementation_start"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertNotIn("target_local_implementation_start_preview", step_ids)

    def test_exported_pack_skips_implementation_start_apply_until_preview_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Implementation Start Apply\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose implementation start apply routing.\n"
                "- Skip task status writes while implementation readiness is blocked.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output reports skipped implementation start apply without changing task status.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
                implementation_readiness_preview=True,
                implementation_start_preview=True,
                implementation_start_apply=True,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["implementation_start_preview_ok"])
            self.assertTrue(payload["implementation_start_apply_requested"])
            self.assertFalse(payload["implementation_start_applied"])
            self.assertTrue(payload["implementation_start_apply_ok"])
            apply_payload = payload["implementation_start_apply"]
            self.assertTrue(apply_payload["ok"])
            self.assertFalse(apply_payload["check"])
            self.assertTrue(apply_payload["writes_state"])
            self.assertFalse(apply_payload["start_ready"])
            self.assertTrue(apply_payload["apply_skipped"])
            self.assertEqual("implementation start preview did not pass", apply_payload["skip_reason"])
            self.assertEqual({}, apply_payload["implementation_start_apply"])
            self.assertEqual("design-derivation", payload["target_local"]["phase"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertNotIn("target_local_implementation_start_apply", step_ids)

    def test_exported_pack_skips_implementation_closeout_until_start_apply_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pack = base / "docs-as-code-workflow-pack"
            product = base / "product.md"
            target = base / "consumer-target"
            product.write_text(
                "# Consumer Implementation Closeout Apply\n\n"
                "## Goals and Requirements\n\n"
                "- Initialize governance and expose implementation closeout apply routing.\n"
                "- Skip Done status writes until local verification evidence passes.\n\n"
                "## Acceptance Criteria\n\n"
                "- The bootstrap output reports skipped closeout apply while verification evidence is missing.\n",
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
                design_scaffold_apply=True,
                design_authoring_preview=True,
                implementation_readiness_preview=True,
                implementation_advance_preview=True,
                implementation_advance_apply=True,
                implementation_start_preview=True,
                implementation_start_apply=True,
                implementation_closeout_preview=True,
                implementation_closeout_apply=True,
            )

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["implementation_start_applied"])
            self.assertTrue(payload["implementation_start_apply_ok"])
            self.assertTrue(payload["implementation_closeout_preview_requested"])
            self.assertTrue(payload["implementation_closeout_previewed"])
            self.assertTrue(payload["implementation_closeout_preview_ok"])
            preview = payload["implementation_closeout_preview"]
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["writes_state"])
            self.assertEqual("design-derivation", preview["phase"])
            self.assertEqual("", preview["task_id"])
            self.assertFalse(preview["closeout_ready"])
            self.assertTrue(preview["preview_skipped"])
            self.assertEqual("implementation start apply did not pass", preview["skip_reason"])
            self.assertEqual({}, preview["implementation_closeout"])
            self.assertTrue(payload["implementation_closeout_apply_requested"])
            self.assertFalse(payload["implementation_closeout_applied"])
            self.assertTrue(payload["implementation_closeout_apply_ok"])
            apply_payload = payload["implementation_closeout_apply"]
            self.assertTrue(apply_payload["ok"])
            self.assertFalse(apply_payload["check"])
            self.assertTrue(apply_payload["writes_state"])
            self.assertFalse(apply_payload["closeout_ready"])
            self.assertTrue(apply_payload["apply_skipped"])
            self.assertEqual("implementation closeout preview did not pass", apply_payload["skip_reason"])
            self.assertEqual({}, apply_payload["implementation_closeout_apply"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertNotIn("target_local_implementation_closeout_preview", step_ids)
            self.assertNotIn("target_local_implementation_closeout_apply", step_ids)

    def test_implementation_closeout_apply_skips_when_preview_reports_evidence_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            bin_dir = target / "bin"
            bin_dir.mkdir(parents=True)
            governance = bin_dir / "governance"
            governance.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import sys\n"
                "if sys.argv[1:] == ['implementation', 'closeout', '.', '--task', 'TASK-001', '--json']:\n"
                "    print(json.dumps({\n"
                "        'ok': True,\n"
                "        'closeout_ready': False,\n"
                "        'blocking_requirements': [\n"
                "            {'code': 'verification_log_row_present'},\n"
                "            {'code': 'verification_result_passing'},\n"
                "            {'code': 'task_verification_links_local_evidence'},\n"
                "        ],\n"
                "    }))\n"
                "    raise SystemExit(0)\n"
                "print(json.dumps({'ok': False, 'argv': sys.argv[1:]}))\n"
                "raise SystemExit(97)\n",
                encoding="utf-8",
            )
            governance.chmod(0o755)
            steps: list[dict[str, object]] = []
            start_apply = {
                "ok": True,
                "apply_skipped": False,
                "post_status": {"state": {"phase": "implementation"}},
                "post_implementation_plan": {"active_work": {"task_id": "TASK-001"}},
            }

            preview = _preview_implementation_closeout(steps, target, start_apply)
            apply_payload = _apply_implementation_closeout(steps, target, preview)

            self.assertTrue(preview["ok"])
            self.assertEqual("implementation", preview["phase"])
            self.assertEqual("TASK-001", preview["task_id"])
            self.assertFalse(preview["closeout_ready"])
            closeout = preview["implementation_closeout"]
            self.assertTrue(closeout["ok"])
            self.assertFalse(closeout["closeout_ready"])
            blocking_codes = {
                requirement["code"]
                for requirement in closeout["blocking_requirements"]
                if isinstance(requirement, dict)
            }
            self.assertEqual(
                {
                    "verification_log_row_present",
                    "verification_result_passing",
                    "task_verification_links_local_evidence",
                },
                blocking_codes,
            )
            self.assertTrue(apply_payload["ok"])
            self.assertTrue(apply_payload["apply_skipped"])
            self.assertEqual("implementation closeout preview did not pass", apply_payload["skip_reason"])
            self.assertEqual({}, apply_payload["implementation_closeout_apply"])
            step_ids = {step["id"] for step in steps}
            self.assertEqual({"target_local_implementation_closeout_preview"}, step_ids)


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
    design_scaffold_apply: bool = False,
    design_authoring_preview: bool = False,
    implementation_readiness_preview: bool = False,
    implementation_advance_preview: bool = False,
    implementation_advance_apply: bool = False,
    implementation_start_preview: bool = False,
    implementation_start_apply: bool = False,
    implementation_closeout_preview: bool = False,
    implementation_closeout_apply: bool = False,
    workflow_preset: str = "",
    auto_repair_env: bool = False,
    strict_authority_skills: bool = False,
    expected_returncode: int = 0,
    env: dict[str, str] | None = None,
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
    if design_scaffold_apply:
        argv.insert(-1, "--design-scaffold-apply")
    if design_authoring_preview:
        argv.insert(-1, "--design-authoring-preview")
    if implementation_readiness_preview:
        argv.insert(-1, "--implementation-readiness-preview")
    if implementation_advance_preview:
        argv.insert(-1, "--implementation-advance-preview")
    if implementation_advance_apply:
        argv.insert(-1, "--implementation-advance-apply")
    if implementation_start_preview:
        argv.insert(-1, "--implementation-start-preview")
    if implementation_start_apply:
        argv.insert(-1, "--implementation-start-apply")
    if implementation_closeout_preview:
        argv.insert(-1, "--implementation-closeout-preview")
    if implementation_closeout_apply:
        argv.insert(-1, "--implementation-closeout-apply")
    if workflow_preset:
        argv.insert(-1, "--workflow-preset")
        argv.insert(-1, workflow_preset)
    if auto_repair_env:
        argv.insert(-1, "--auto-repair-env")
    if strict_authority_skills:
        argv.insert(-1, "--strict-authority-skills")
    run_env = None
    if env is not None:
        run_env = {**os.environ, **env}
    result = subprocess.run(
        argv,
        cwd=pack,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )
    testcase.assertEqual(expected_returncode, result.returncode, result.stdout + result.stderr)
    testcase.assertEqual("", result.stderr)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        testcase.fail(f"bootstrap did not return JSON: {error}: {result.stdout}")
    testcase.assertIsInstance(payload, dict)
    return payload


if __name__ == "__main__":
    unittest.main()
