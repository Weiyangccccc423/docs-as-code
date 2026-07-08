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
            target.mkdir()
            product = target / "product.md"
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
            self.assertIn("repair_actions", env_check)
            self.assertIn("repair_execution", env_check)
            self.assertIn("can_auto_apply", env_check["repair_execution"])
            self.assertIn("next_step", env_check["repair_execution"])
            self.assertIn("would_repair", env_check)
            self.assertNotIn("local_commands", env_check)
            self.assertTrue(target.exists())

            init_check = _run_json(
                self,
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--check",
                    "--target",
                    str(target),
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
            self.assertEqual("auto-discovered", init_check["product"]["selection"])
            self.assertEqual(str(product.resolve()), init_check["product"]["path"])
            self.assertIn(".governance/state.json", init_check["would_write"])
            self.assertTrue(target.exists())

            init_payload = _run_json(
                self,
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--profile",
                    "service",
                    "--project-name",
                    "Fresh Target Smoke",
                    "--json",
                ],
                cwd=ROOT,
            )
            self.assertTrue(init_payload["ok"])
            self.assertEqual("auto-discovered", init_payload["product"]["selection"])
            self.assertEqual([str(product.resolve())], init_payload["product"]["candidates"])
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
            self.assertEqual(1, preflight_action["sequence"])
            self.assertEqual("advance-product-structuring", preflight_action["preflight_for"])
            self.assertEqual("ok:true", preflight_action["success_condition"])
            preflight = _run_json(self, preflight_action["argv"], cwd=preflight_action["cwd"])
            self.assertTrue(preflight["ok"])
            self.assertTrue(preflight["check"])
            self.assertTrue(preflight["would_advance"])
            self.assertFalse(preflight["advanced"])

            local_commands = {command["make_target"]: command for command in status["local_commands"]}
            self.assertEqual(
                ["make", "product-plan"],
                local_commands["product-plan"]["argv"],
            )
            self.assertEqual(
                ["make", "design-plan"],
                local_commands["design-plan"]["argv"],
            )
            self.assertEqual(
                ["make", "implementation-plan"],
                local_commands["implementation-plan"]["argv"],
            )
            for make_target in ("verify-check", "governance-status", "check-env", "repair-env-check"):
                command = local_commands[make_target]
                self.assertFalse(command["approval_required"])
                self.assertFalse(command["writes_state"])
                payload = _run_json(self, command["argv"], cwd=command["cwd"])
                self.assertTrue(payload["ok"])
                if make_target == "check-env":
                    self.assertIn("tools", payload)
                    self.assertEqual(".", payload["target"])

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
            self.assertEqual(2, apply_action["sequence"])
            self.assertEqual("advance-product-structuring-check", apply_action["requires_action"])
            self.assertEqual("ok:true", apply_action["success_condition"])
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
            self.assertFalse(design_preflight["advanced"])

            design_advanced = _run_json(
                self,
                ["bin/governance", "advance", "design-derivation", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(design_advanced["ok"])
            self.assertTrue(design_advanced["advanced"])
            self.assertEqual("design-derivation", design_advanced["state"]["phase"])
            self.assertEqual("advance-implementation-check", design_advanced["next_actions"][0]["id"])

            design_scaffold_check = _run_json(
                self,
                ["bin/governance", "scaffold", "design", ".", "--check", "--json"],
                cwd=target,
            )
            self.assertTrue(design_scaffold_check["ok"])
            self.assertTrue(design_scaffold_check["check"])
            self.assertEqual([], design_scaffold_check["created"])
            self.assertEqual([], design_scaffold_check["indexed"])
            for path in (
                "docs/architecture/01-system-context.md",
                "docs/api/endpoints/README.md",
                "docs/api/endpoints/01-endpoint-contract.md",
                "docs/development/03-verification-log.md",
            ):
                self.assertIn(path, design_scaffold_check["would_create"])
            for path in (
                "docs/architecture/01-system-context.md",
                "docs/api/endpoints/01-endpoint-contract.md",
                "docs/development/03-verification-log.md",
            ):
                self.assertIn(path, design_scaffold_check["would_index"])
            self.assertNotIn("local_commands", design_scaffold_check)
            self.assertNotIn("next_actions", design_scaffold_check)
            self.assertFalse((target / "docs/architecture/01-system-context.md").exists())
            self.assertFalse((target / "docs/api/endpoints/01-endpoint-contract.md").exists())

            design_scaffold = _run_json(
                self,
                ["bin/governance", "scaffold", "design", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(design_scaffold["ok"])
            for path in (
                "docs/architecture/01-system-context.md",
                "docs/api/endpoints/README.md",
                "docs/api/endpoints/01-endpoint-contract.md",
                "docs/backend/02-data-model.md",
                "docs/development/03-verification-log.md",
            ):
                self.assertIn(path, design_scaffold["created"])
            self.assertEqual(
                {
                    "current": "design-derivation",
                    "expected": "design-derivation",
                    "matches": True,
                    "message": "recorded phase matches scaffold phase",
                },
                design_scaffold["scaffold_phase"],
            )
            self.assertEqual("advance-implementation-check", design_scaffold["next_actions"][0]["id"])
            design_blockers = {
                blocker["path"]: blocker
                for blocker in design_scaffold["next_actions_blocked_by"]
            }
            self.assertEqual(
                "governance_scaffold_placeholder",
                design_blockers["docs/architecture/01-system-context.md"]["code"],
            )
            self.assertEqual(
                "governance_scaffold_placeholder",
                design_blockers["docs/api/endpoints/01-endpoint-contract.md"]["code"],
            )
            self.assertEqual(
                "governance_scaffold_placeholder",
                design_blockers["docs/development/03-verification-log.md"]["code"],
            )

            endpoint_contract = (target / "docs/api/endpoints/01-endpoint-contract.md").read_text(encoding="utf-8")
            acceptance_matrix = (target / "docs/tests/02-acceptance-matrix.md").read_text(encoding="utf-8")
            roadmap = (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8")
            task_board = (target / "docs/development/02-task-board.md").read_text(encoding="utf-8")
            self.assertIn("METHOD /product-derived-path", endpoint_contract)
            self.assertIn("| Acceptance | Design | API | Test |", acceptance_matrix)
            self.assertIn("| ID | Status | Milestone |", roadmap)
            self.assertIn("| ID | Status | Task | Product | Design | API | Acceptance | Verification |", task_board)

            design_blocked_verify = _run_json(
                self,
                ["bin/governance", "verify", ".", "--check", "--json"],
                cwd=target,
                expected_returncode=1,
            )
            self.assertFalse(design_blocked_verify["ok"])
            self.assertTrue(
                any(
                    finding["code"] == "governance_scaffold_placeholder"
                    and finding["path"] == "docs/api/endpoints/01-endpoint-contract.md"
                    for finding in design_blocked_verify["findings"]
                )
            )

            design_plan = _run_json(
                self,
                ["bin/governance", "design", "plan", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(design_plan["ok"])
            self.assertEqual("design-derivation", design_plan["phase"])
            self.assertIn("docs/product/core/PRD.md", design_plan["source_documents"])
            self.assertIn("docs/product/08-acceptance-criteria.md", design_plan["source_documents"])
            self.assertEqual(
                [
                    "architecture",
                    "ui-interaction",
                    "api-contracts",
                    "backend-modules",
                    "data-model",
                    "frontend-modules",
                    "test-strategy",
                    "implementation-planning",
                    "architecture-decisions",
                ],
                [track["id"] for track in design_plan["tracks"]],
            )
            tracks = {track["id"]: track for track in design_plan["tracks"]}
            self.assertIn("designing-system-architecture", tracks["architecture"]["skills"])
            self.assertEqual(1, tracks["architecture"]["sequence"])
            self.assertEqual("senior-architect", tracks["architecture"]["primary_specialist_skill"])
            self.assertIn("references/architecture-methods.md", tracks["architecture"]["references"])
            self.assertIn("docs/architecture/01-system-context.md", tracks["architecture"]["documents"])
            self.assertIn("designing-api-contracts", tracks["api-contracts"]["skills"])
            self.assertEqual(3, tracks["api-contracts"]["sequence"])
            self.assertEqual("api-design-reviewer", tracks["api-contracts"]["primary_specialist_skill"])
            self.assertIn("references/api-design-checklist.md", tracks["api-contracts"]["references"])
            self.assertIn("references/security-design-checklist.md", tracks["api-contracts"]["references"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", tracks["api-contracts"]["documents"])
            api_steps = tracks["api-contracts"]["steps"]
            self.assertEqual("load-track-skills", api_steps[0]["id"])
            self.assertEqual(1, api_steps[0]["sequence"])
            self.assertIn("designing-api-contracts", api_steps[0]["skills"])
            self.assertEqual("read-product-sources", api_steps[1]["id"])
            self.assertEqual(2, api_steps[1]["sequence"])
            self.assertIn("docs/product/core/PRD.md", api_steps[1]["documents"])
            self.assertEqual("verify-track", api_steps[4]["id"])
            self.assertEqual(5, api_steps[4]["sequence"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], api_steps[4]["argv"])
            self.assertIn("designing-backend-modules", tracks["backend-modules"]["skills"])
            self.assertIn("references/backend-design-checklist.md", tracks["backend-modules"]["references"])
            self.assertIn("designing-data-models", tracks["data-model"]["skills"])
            self.assertIn("references/data-model-design-checklist.md", tracks["data-model"]["references"])
            self.assertTrue(
                any(
                    blocker["path"] == "docs/api/endpoints/01-endpoint-contract.md"
                    and blocker["code"] == "governance_scaffold_placeholder"
                    for blocker in tracks["api-contracts"]["blockers"]
                )
            )
            self.assertEqual("advance-implementation-check", design_plan["next_actions"][0]["id"])

            api_candidates = _run_json(
                self,
                ["bin/governance", "design", "api-candidates", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(api_candidates["ok"])
            self.assertEqual("api-contracts", api_candidates["track"])
            self.assertEqual(1, len(api_candidates["candidates"]))
            candidate = api_candidates["candidates"][0]
            self.assertEqual("A-001", candidate["acceptance_id"])
            self.assertEqual("Initialized Repository Exposes Local Governance Checks", candidate["title"])
            self.assertEqual(
                "docs/api/endpoints/01-initialized-repository-exposes-local-governance-checks.md",
                candidate["suggested_endpoint_file"],
            )
            self.assertIn("method_path", candidate["open_decisions"])
            self.assertIn("frontend_consumers", candidate["open_decisions"])

            api_authoring = _run_json(
                self,
                ["bin/governance", "design", "api-authoring", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(api_authoring["ok"])
            self.assertEqual("api-contracts", api_authoring["track"])
            self.assertEqual("do_not_guess_contract_details", api_authoring["decision_policy"])
            self.assertEqual(1, len(api_authoring["authoring_tasks"]))
            authoring_task = api_authoring["authoring_tasks"][0]
            self.assertEqual("API-AUTHOR-001", authoring_task["task_id"])
            self.assertEqual(1, authoring_task["sequence"])
            self.assertEqual("api-contract-authoring", authoring_task["execution"]["stage"])
            self.assertEqual("api-design-reviewer", authoring_task["execution"]["primary_specialist_skill"])
            self.assertEqual("verify-api-authoring", authoring_task["execution"]["verify_step"])
            self.assertEqual("refresh-api-authoring", authoring_task["execution"]["refresh_step"])
            self.assertEqual("API-001", authoring_task["candidate_id"])
            self.assertEqual("A-001", authoring_task["acceptance_id"])
            self.assertEqual(
                "docs/api/endpoints/01-initialized-repository-exposes-local-governance-checks.md",
                authoring_task["endpoint_file"],
            )
            self.assertIn("docs/api/error-codes.md", [link["target"] for link in authoring_task["required_links"]])
            self.assertIn("docs/frontend/02-api-consumption.md", [link["target"] for link in authoring_task["required_links"]])
            self.assertIn("docs/backend/01-modules.md", [link["target"] for link in authoring_task["required_links"]])
            self.assertIn("request_fields", authoring_task["open_decisions"])
            self.assertIn("response_fields", authoring_task["open_decisions"])
            self.assertEqual(
                ["bin/governance", "design", "api-authoring", ".", "--json"],
                authoring_task["steps"][-1]["argv"],
            )

            backend_authoring = _run_json(
                self,
                ["bin/governance", "design", "backend-authoring", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(backend_authoring["ok"])
            self.assertEqual("backend-modules", backend_authoring["track"])
            self.assertEqual("do_not_guess_backend_boundaries", backend_authoring["decision_policy"])
            self.assertEqual(1, len(backend_authoring["authoring_tasks"]))
            backend_task = backend_authoring["authoring_tasks"][0]
            self.assertEqual("BACKEND-AUTHOR-001", backend_task["task_id"])
            self.assertEqual("backend-design-authoring", backend_task["execution"]["stage"])
            self.assertEqual("senior-backend", backend_task["execution"]["primary_specialist_skill"])
            self.assertEqual("A-001", backend_task["acceptance_id"])
            self.assertIn("designing-backend-modules", backend_authoring["skills"])
            self.assertIn("designing-data-models", backend_authoring["skills"])
            self.assertIn("docs/backend/01-modules.md", [document["path"] for document in backend_task["documents"]])
            self.assertIn("docs/backend/02-data-model.md", [document["path"] for document in backend_task["documents"]])
            self.assertIn("docs/backend/03-external-services.md", [document["path"] for document in backend_task["documents"]])
            self.assertIn("module_boundaries", backend_task["open_decisions"])
            self.assertIn("transaction_boundaries", backend_task["open_decisions"])
            self.assertIn("docs/api/endpoints/01-initialized-repository-exposes-local-governance-checks.md", [link["target"] for link in backend_task["required_links"]])
            self.assertEqual(
                ["bin/governance", "design", "backend-authoring", ".", "--json"],
                backend_task["steps"][-1]["argv"],
            )

            frontend_authoring = _run_json(
                self,
                ["bin/governance", "design", "frontend-authoring", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(frontend_authoring["ok"])
            self.assertEqual("frontend-modules", frontend_authoring["track"])
            self.assertEqual("do_not_guess_frontend_behavior", frontend_authoring["decision_policy"])
            self.assertEqual(1, len(frontend_authoring["authoring_tasks"]))
            frontend_task = frontend_authoring["authoring_tasks"][0]
            self.assertEqual("FRONTEND-AUTHOR-001", frontend_task["task_id"])
            self.assertEqual("frontend-design-authoring", frontend_task["execution"]["stage"])
            self.assertEqual("senior-frontend", frontend_task["execution"]["primary_specialist_skill"])
            self.assertEqual("A-001", frontend_task["acceptance_id"])
            self.assertIn("designing-ui-interactions", frontend_authoring["skills"])
            self.assertIn("designing-frontend-modules", frontend_authoring["skills"])
            self.assertIn("docs/ui/01-interaction-model.md", [document["path"] for document in frontend_task["documents"]])
            self.assertIn("docs/frontend/01-modules.md", [document["path"] for document in frontend_task["documents"]])
            self.assertIn("docs/frontend/02-api-consumption.md", [document["path"] for document in frontend_task["documents"]])
            self.assertIn("state_ownership", frontend_task["open_decisions"])
            self.assertIn("error_actions", frontend_task["open_decisions"])
            self.assertIn("docs/api/endpoints/01-initialized-repository-exposes-local-governance-checks.md", [link["target"] for link in frontend_task["required_links"]])
            self.assertEqual(
                ["bin/governance", "design", "frontend-authoring", ".", "--json"],
                frontend_task["steps"][-1]["argv"],
            )

            test_strategy_authoring = _run_json(
                self,
                ["bin/governance", "design", "test-strategy-authoring", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(test_strategy_authoring["ok"])
            self.assertEqual("test-strategy", test_strategy_authoring["track"])
            self.assertEqual("do_not_guess_verification_scope", test_strategy_authoring["decision_policy"])
            self.assertEqual(1, len(test_strategy_authoring["authoring_tasks"]))
            test_task = test_strategy_authoring["authoring_tasks"][0]
            self.assertEqual("TEST-AUTHOR-001", test_task["task_id"])
            self.assertEqual("test-strategy-authoring", test_task["execution"]["stage"])
            self.assertEqual("senior-qa", test_task["execution"]["primary_specialist_skill"])
            self.assertEqual("A-001", test_task["acceptance_id"])
            self.assertIn("designing-test-strategy", test_strategy_authoring["skills"])
            self.assertIn("docs/tests/01-strategy.md", [document["path"] for document in test_task["documents"]])
            self.assertIn("docs/tests/02-acceptance-matrix.md", [document["path"] for document in test_task["documents"]])
            self.assertIn("acceptance_coverage", test_task["open_decisions"])
            self.assertIn("evidence_targets", test_task["open_decisions"])
            self.assertIn("docs/api/endpoints/01-initialized-repository-exposes-local-governance-checks.md", [link["target"] for link in test_task["required_links"]])
            self.assertEqual(
                ["bin/governance", "design", "test-strategy-authoring", ".", "--json"],
                test_task["steps"][-1]["argv"],
            )

            implementation_planning_authoring = _run_json(
                self,
                ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(implementation_planning_authoring["ok"])
            self.assertEqual("implementation-planning", implementation_planning_authoring["track"])
            self.assertEqual("do_not_guess_task_scope", implementation_planning_authoring["decision_policy"])
            self.assertEqual(1, len(implementation_planning_authoring["authoring_tasks"]))
            planning_task = implementation_planning_authoring["authoring_tasks"][0]
            self.assertEqual("PLAN-AUTHOR-001", planning_task["task_id"])
            self.assertEqual("implementation-planning-authoring", planning_task["execution"]["stage"])
            self.assertEqual("senior-fullstack", planning_task["execution"]["primary_specialist_skill"])
            self.assertEqual("A-001", planning_task["acceptance_id"])
            self.assertEqual("TASK-001", planning_task["suggested_task_id"])
            self.assertIn("planning-implementation-work", implementation_planning_authoring["skills"])
            self.assertIn("docs/development/01-roadmap.md", [document["path"] for document in planning_task["documents"]])
            self.assertIn("docs/development/02-task-board.md", [document["path"] for document in planning_task["documents"]])
            self.assertIn("docs/development/03-verification-log.md", [document["path"] for document in planning_task["documents"]])
            self.assertIn("task_scope", planning_task["open_decisions"])
            self.assertIn("ready_criteria", planning_task["open_decisions"])
            self.assertIn("verification_plan", planning_task["open_decisions"])
            self.assertIn("agent_handoff", planning_task["open_decisions"])
            self.assertIn("docs/tests/02-acceptance-matrix.md", [link["target"] for link in planning_task["required_links"]])
            self.assertEqual(
                ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
                planning_task["steps"][-1]["argv"],
            )

            architecture_decisions_authoring = _run_json(
                self,
                ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
                cwd=target,
            )
            self.assertTrue(architecture_decisions_authoring["ok"])
            self.assertEqual("architecture-decisions", architecture_decisions_authoring["track"])
            self.assertEqual(
                "do_not_guess_architecture_decisions",
                architecture_decisions_authoring["decision_policy"],
            )
            self.assertEqual(1, len(architecture_decisions_authoring["authoring_tasks"]))
            adr_task = architecture_decisions_authoring["authoring_tasks"][0]
            self.assertEqual("ADR-AUTHOR-001", adr_task["task_id"])
            self.assertEqual("architecture-decision-authoring", adr_task["execution"]["stage"])
            self.assertEqual("senior-architect", adr_task["execution"]["primary_specialist_skill"])
            self.assertEqual("A-001", adr_task["acceptance_id"])
            self.assertEqual("undetermined", adr_task["requires_adr"])
            self.assertEqual("001", adr_task["next_adr_prefix"])
            self.assertIn("capturing-architecture-decisions", architecture_decisions_authoring["skills"])
            self.assertIn("docs/decisions/_template.md", [document["path"] for document in adr_task["documents"]])
            self.assertIn("adr_trigger", adr_task["open_decisions"])
            self.assertIn("decision_scope", adr_task["open_decisions"])
            self.assertIn("alternatives", adr_task["open_decisions"])
            self.assertIn("docs/architecture/03-quality-attributes.md", [link["target"] for link in adr_task["required_links"]])
            self.assertEqual(
                ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
                adr_task["steps"][-1]["argv"],
            )
