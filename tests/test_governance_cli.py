import json
import contextlib
import importlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "governance_cli.py"


def _append_index(readme: Path, filename: str) -> None:
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n- `{filename}` - generated for test\n", encoding="utf-8")


def _append_product_meta_chapter(root: Path, filename: str) -> None:
    meta = root / "docs/product/core/product-meta.md"
    meta.write_text(meta.read_text(encoding="utf-8") + f"\n- [{filename}](../{filename})\n", encoding="utf-8")


def _acceptance_doc() -> str:
    return (
        "# Acceptance Criteria\n\n"
        "Source: [PRD](core/PRD.md).\n\n"
        "## A-001 Goal Flow\n\n"
        "- The primary goal flow meets the documented product expectation.\n"
    )


def _api_conventions_doc() -> str:
    return (
        "# API Conventions\n\n"
        "## Product Links\n\n"
        "- [PRD](../product/core/PRD.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## HTTP Conventions\n\n"
        "- Use JSON request and response bodies for product workflow APIs.\n\n"
        "## Authentication\n\n"
        "- Mutating endpoints require an authenticated user boundary.\n\n"
        "## Idempotency\n\n"
        "- Client-provided idempotency keys protect retryable writes.\n\n"
        "## Compatibility\n\n"
        "- Breaking API changes require an API changelog entry before implementation.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _api_error_codes_doc() -> str:
    return (
        "# API Error Codes\n\n"
        "## Product Links\n\n"
        "- [Product goals](../product/01-goals.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Error Taxonomy\n\n"
        "- User-correctable errors use stable product-facing categories.\n\n"
        "## Error Codes\n\n"
        "- GOAL_VALIDATION_FAILED: the request conflicts with product validation rules.\n\n"
        "## Retry Semantics\n\n"
        "- Retry only idempotent requests with stable idempotency keys.\n\n"
        "## Frontend Handling\n\n"
        "- Frontend flows map known errors to visible recovery actions.\n"
    )


def _api_changelog_doc() -> str:
    return (
        "# API Changelog\n\n"
        "## Change Log\n\n"
        "- Initial contract baseline for the goal flow.\n\n"
        "## Compatibility Notes\n\n"
        "- Breaking changes require a new changelog entry before implementation.\n"
    )


def _api_endpoint_contract_doc() -> str:
    return (
        "# Goal Flow Endpoint\n\n"
        "## Method and Path\n\n"
        "POST /goals\n\n"
        "## Auth\n\n"
        "Authenticated user required.\n\n"
        "## Idempotency\n\n"
        "Client-provided idempotency keys protect retryable writes.\n\n"
        "## Request Fields\n\n"
        "- title: goal title.\n\n"
        "## Response Fields\n\n"
        "- id: created goal identifier.\n\n"
        "## Error Codes\n\n"
        "- [GOAL_VALIDATION_FAILED](../error-codes.md#goal_validation_failed)\n\n"
        "## Upstream Links\n\n"
        "- [Product goals](../../product/01-goals.md)\n\n"
        "## Frontend Consumers\n\n"
        "- [Frontend API consumption](../../frontend/02-api-consumption.md)\n"
    )


def _roadmap_doc() -> str:
    return (
        "# Roadmap\n\n"
        "## Product Links\n\n"
        "- [Product goals](../product/01-goals.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Milestones\n\n"
        "| ID | Status | Milestone |\n"
        "| --- | --- | --- |\n"
        "| TASK-001 | Ready | Goal flow |\n\n"
        "## Sequencing\n\n"
        "- Implement the product goal flow before deferred refinements.\n\n"
        "## Risks\n\n"
        "- API, backend, frontend, and tests must stay aligned to acceptance criteria.\n\n"
        "## Deferred Scope\n\n"
        "- none\n"
    )


def _task_board_doc(rows: str) -> str:
    rows = rows.replace(
        "docs/product/08-acceptance-criteria.md",
        "docs/product/08-acceptance-criteria.md#A-001",
    )
    return (
        "# Task Board\n\n"
        "## Task Table\n\n"
        "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"{rows}"
        "\n## Status Policy\n\n"
        "- Use Backlog, Ready, In Progress, Blocked, Done, or Deferred consistently with the implementation gate.\n\n"
        "## Traceability Rules\n\n"
        "- Product, Design, API, and Acceptance fields must link to existing local Markdown sources.\n"
        "- Done tasks must link to local Markdown verification evidence.\n"
    )


def _verification_log_doc(rows: str = "") -> str:
    return (
        "# Verification Log\n\n"
        "## Verification Runs\n\n"
        "| Task | Command | Result | Date | Notes |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"{rows}"
        "\n## Artifacts\n\n"
        "- none\n\n"
        "## Open Follow-ups\n\n"
        "- none\n"
    )


def _backend_external_services_doc() -> str:
    return (
        "# External Services\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Backend modules](01-modules.md)\n\n"
        "## Dependencies\n\n"
        "- No external runtime dependency is required for the first goal flow.\n\n"
        "## Contracts\n\n"
        "- Internal module contracts remain documented in backend modules and API docs.\n\n"
        "## Retries\n\n"
        "- Retry behavior must be idempotent for API writes.\n\n"
        "## Timeouts\n\n"
        "- Timeouts must fail fast enough to preserve the user workflow.\n\n"
        "## Authentication\n\n"
        "- Authenticated service calls must preserve user ownership boundaries.\n\n"
        "## Observability\n\n"
        "- Dependency failures must emit traceable error events.\n"
    )


def _backend_modules_doc() -> str:
    return (
        "# Backend Modules\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Architecture Links\n\n"
        "- [Architecture context](../architecture/01-system-context.md)\n\n"
        "## Modules\n\n"
        "- Workflow module owns the primary goal-flow runtime behavior.\n\n"
        "## API Ownership\n\n"
        "- Workflow API behavior follows [API conventions](../api/00-conventions.md).\n\n"
        "## Failure Modes\n\n"
        "- Persistence failures follow [Data model](02-data-model.md).\n"
        "- Dependency failures follow [External services](03-external-services.md).\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _test_strategy_doc() -> str:
    return (
        "# Test Strategy\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Architecture context](../architecture/01-system-context.md)\n\n"
        "## Acceptance Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Test Layers\n\n"
        "- Unit tests cover isolated validation rules and state transitions.\n"
        "- Integration tests cover API contract and persistence behavior.\n\n"
        "## Risk Coverage\n\n"
        "- Goal-flow risks are mapped back to acceptance and design sources before implementation.\n\n"
        "## Non-Functional Checks\n\n"
        "- Performance, security, and observability checks are planned for implementation handoff.\n"
    )


def _architecture_system_context_doc() -> str:
    return (
        "# System Context\n\n"
        "## Product Links\n\n"
        "- [Product goals](../product/01-goals.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Actors\n\n"
        "- Product users operate the primary goal flow.\n\n"
        "## External Systems\n\n"
        "- No mandatory external systems are required for the first implementation slice.\n\n"
        "## Trust Boundaries\n\n"
        "- Authenticated user data remains inside the application boundary.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _architecture_containers_doc() -> str:
    return (
        "# Containers\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [System context](01-system-context.md)\n\n"
        "## Containers\n\n"
        "- Web app, API, and persistence containers own the primary goal flow.\n\n"
        "## Runtime Responsibilities\n\n"
        "- API coordinates validation, persistence, and response contracts.\n\n"
        "## Data Ownership\n\n"
        "- Goal data is owned by the backend persistence boundary.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _architecture_quality_attributes_doc() -> str:
    return (
        "# Quality Attributes\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [Containers](02-containers.md)\n\n"
        "## Availability\n\n"
        "- The primary goal flow should fail visibly and recoverably.\n\n"
        "## Performance\n\n"
        "- Primary interactions should complete within documented product expectations.\n\n"
        "## Security\n\n"
        "- User-owned data must stay scoped to authenticated ownership boundaries.\n\n"
        "## Observability\n\n"
        "- Failures emit traceable events for implementation verification.\n\n"
        "## Tradeoffs\n\n"
        "- Keep runtime boundaries simple until acceptance evidence requires separation.\n"
    )


def _ui_interaction_model_doc() -> str:
    return (
        "# Interaction Model\n\n"
        "## Product Links\n\n"
        "- [Product goals](../product/01-goals.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Primary Flows\n\n"
        "- Users complete the documented goal flow through a visible, recoverable path.\n\n"
        "## Screens\n\n"
        "- Goal flow screens expose product state and correction actions.\n\n"
        "## States\n\n"
        "- Loading, empty, success, and error states are explicit for the primary flow.\n\n"
        "## Errors\n\n"
        "- User-correctable errors map to visible correction actions.\n\n"
        "## Accessibility\n\n"
        "- Controls have stable names and keyboard reachable states.\n"
    )


def _frontend_modules_doc() -> str:
    return (
        "# Frontend Modules\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## UI Links\n\n"
        "- [Interaction model](../ui/01-interaction-model.md)\n\n"
        "## Modules\n\n"
        "- Goal flow module owns the primary user interaction path.\n\n"
        "## State Ownership\n\n"
        "- API-backed state follows [API consumption](02-api-consumption.md).\n\n"
        "## Routes\n\n"
        "- Goal flow routes follow the interaction model and API conventions.\n\n"
        "## Open Decisions\n\n"
        "- API behavior follows [API conventions](../api/00-conventions.md).\n"
    )


def _frontend_api_consumption_doc() -> str:
    return (
        "# Frontend API Consumption\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## API Links\n\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Frontend modules](01-modules.md)\n\n"
        "## Consumption Map\n\n"
        "- Goal flow screens call the documented API contract.\n\n"
        "## Loading States\n\n"
        "- Loading states preserve user context while API calls complete.\n\n"
        "## Error Actions\n\n"
        "- API errors map to user-visible recovery actions.\n"
    )


def _acceptance_matrix_doc() -> str:
    return (
        "# Acceptance Matrix\n\n"
        "## Matrix\n\n"
        "| Acceptance | Design | API | Test |\n"
        "| --- | --- | --- | --- |\n"
        "| [A-001](../product/08-acceptance-criteria.md#a-001) | [Architecture context](../architecture/01-system-context.md) | [Goal endpoint](../api/endpoints/01-goal-flow.md) | [Test strategy](01-strategy.md) |\n\n"
        "## Uncovered Criteria\n\n"
        "- none\n"
    )


class GovernanceCliTest(unittest.TestCase):
    def test_env_tool_payload_reuses_status_output_contract(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        governance_cli = importlib.import_module("governance_cli")

        class CustomStatus:
            def to_dict(self) -> dict[str, object]:
                return {
                    "name": "custom",
                    "present": True,
                    "version": "custom 1.0",
                    "note": "Uses the status object contract.",
                    "level": "recommended",
                    "install_package": None,
                    "extra_contract_field": "preserved",
                }

        self.assertEqual(
            [
                {
                    "name": "custom",
                    "present": True,
                    "version": "custom 1.0",
                    "note": "Uses the status object contract.",
                    "level": "recommended",
                    "install_package": None,
                    "extra_contract_field": "preserved",
                }
            ],
            governance_cli._tool_status_payload([CustomStatus()]),
        )

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
            self.assertIn("install_commands", payload)
            self.assertIn("install_command", payload)
            self.assertIn("needs_escalation", payload)
            self.assertIn("missing_required", payload)
            self.assertIn("missing_recommended", payload)
            self.assertIn("repairs", payload)
            self.assertTrue(any(tool["name"] == "python3" for tool in payload["tools"]))
            self.assertEqual(str(target / ".governance/env-repair.md"), payload["repair_plan"])

    def test_env_repair_check_json_reports_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            repair_plan = target / ".governance/env-repair.md"

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "env",
                    "--target",
                    str(target),
                    "--repair",
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertIn(result.returncode, (0, 1), result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["ok"], result.returncode == 0)
            self.assertTrue(payload["check"])
            self.assertEqual([], payload["repairs"])
            self.assertIsNone(payload["repair_plan"])
            self.assertTrue(
                any(
                    item["kind"] == "repair_plan"
                    and item["path"] == str(repair_plan)
                    and item["status"] == "would_write"
                    for item in payload["would_repair"]
                )
            )
            self.assertFalse(repair_plan.exists())

    def test_env_repair_json_rejects_file_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.write_text("not a directory\n", encoding="utf-8")

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

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(
                [f"environment repair target is not a directory: {target}"],
                payload["errors"],
            )
            self.assertIsNone(payload["repair_plan"])
            self.assertEqual([], payload["repairs"])
            self.assertTrue(target.is_file())

    def test_env_repair_json_rejects_blocked_governance_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            governance = target / ".governance"
            governance.write_text("not a directory\n", encoding="utf-8")

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

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(
                [f"environment repair output parent is not a directory: {governance}"],
                payload["errors"],
            )
            self.assertIsNone(payload["repair_plan"])
            self.assertEqual([], payload["repairs"])
            self.assertTrue(governance.is_file())

    def test_env_repair_json_rejects_blocked_repair_plan_temp_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            repair_plan = target / ".governance/env-repair.md"
            repair_plan.parent.mkdir(parents=True)
            repair_plan.write_text("# Existing Plan\n", encoding="utf-8")
            temp_path = repair_plan.with_name(".env-repair.md.tmp")
            temp_path.mkdir()

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

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(
                [f"environment repair plan temp path is not a file: {temp_path}"],
                payload["errors"],
            )
            self.assertIsNone(payload["repair_plan"])
            self.assertEqual([], payload["repairs"])
            self.assertEqual("# Existing Plan\n", repair_plan.read_text(encoding="utf-8"))

    def test_env_repair_json_reports_repair_plan_write_failure_without_traceback(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        governance_cli = importlib.import_module("governance_cli")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            original_write_repair_plan = governance_cli.write_repair_plan

            def raise_os_error(*_args: object, **_kwargs: object) -> Path:
                raise OSError(28, "No space left on device")

            governance_cli.write_repair_plan = raise_os_error
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    returncode = governance_cli._cmd_env(
                        SimpleNamespace(target=str(target), repair=True, json=True, strict=False)
                    )
            finally:
                governance_cli.write_repair_plan = original_write_repair_plan

            self.assertEqual(1, returncode)
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(["environment repair failed: No space left on device"], payload["errors"])
            self.assertIsNone(payload["repair_plan"])
            self.assertEqual([], payload["repairs"])

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
            self.assertIn("docs/agent-workflow/runtime-manifest.json", payload["would_write"])
            self.assertIn("docs/agent-workflow/workflow-pack/manifest.json", payload["would_write"])
            self.assertIn("docs/agent-workflow/workflow-pack/skills/using-governance-workflow/SKILL.md", payload["would_write"])
            self.assertFalse(target.exists())

    def test_init_json_reports_bootstrap_write_failure_without_traceback(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        governance_cli = importlib.import_module("governance_cli")
        bootstrap_tree = importlib.import_module("bootstrap_tree")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            original_safe_write = bootstrap_tree._safe_write

            def fail_after_root_readme(path: Path, content: str, force: bool = False) -> None:
                original_safe_write(path, content, force)
                if path == target / "README.md":
                    raise OSError(28, "No space left on device")

            bootstrap_tree._safe_write = fail_after_root_readme
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    returncode = governance_cli._cmd_init(
                        SimpleNamespace(
                            target=str(target),
                            product=str(product),
                            force=False,
                            check=False,
                            json=True,
                            profile="unknown",
                            project_name=None,
                        )
                    )
            finally:
                bootstrap_tree._safe_write = original_safe_write

            self.assertEqual(1, returncode)
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual(["initialization failed: No space left on device"], payload["errors"])
            self.assertEqual([], payload["conflicts"])
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

    def test_init_rejects_invalid_utf8_markdown_product_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_bytes(b"\xff\xfe invalid markdown")

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
            self.assertIn(
                {"path": str(product), "reason": "markdown product document is not valid UTF-8"},
                payload["conflicts"],
            )
            self.assertFalse(target.exists())

    def test_init_rejects_product_directory_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.mkdir()

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
            self.assertIn(
                {"path": str(product), "reason": "product document is not a file"},
                payload["conflicts"],
            )
            self.assertFalse(target.exists())

    def test_init_json_rejects_file_target_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.write_text("not a directory\n", encoding="utf-8")
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
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {"path": str(target), "reason": "target path is not a directory"},
                payload["conflicts"],
            )
            self.assertEqual("not a directory\n", target.read_text(encoding="utf-8"))

    def test_init_json_rejects_file_target_parent_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            blocking_parent = base / "blocking-parent"
            blocking_parent.write_text("not a directory\n", encoding="utf-8")
            target = blocking_parent / "target"
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
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {"path": str(blocking_parent), "reason": "target parent path is not a directory"},
                payload["conflicts"],
            )
            self.assertEqual("not a directory\n", blocking_parent.read_text(encoding="utf-8"))

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
            self.assertEqual("docs/agent-workflow/runtime-manifest.json", payload["state"]["runtime_manifest"])
            self.assertEqual("docs/agent-workflow/workflow-pack/manifest.json", payload["state"]["workflow_pack_manifest"])
            self.assertIn("# Forced Demo", (target / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((target / "docs/README.md").exists())

    def test_init_force_json_rejects_generated_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            (target / "README.md").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--force",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {"path": "README.md", "reason": "generated file path is not a file"},
                payload["conflicts"],
            )
            self.assertFalse((target / "docs/README.md").exists())

    def test_init_force_json_rejects_generated_parent_file_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            (target / "docs").write_text("not a directory\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--force",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {"path": "docs", "reason": "generated parent path is not a directory"},
                payload["conflicts"],
            )
            self.assertEqual("not a directory\n", (target / "docs").read_text(encoding="utf-8"))

    def test_init_force_json_rejects_invalid_state_without_partial_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            readme = target / "README.md"
            readme.write_text("# Existing\n", encoding="utf-8")
            state_path = target / ".governance/state.json"
            state_path.parent.mkdir()
            state_path.write_text("{not json\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--force",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(
                any(
                    conflict["path"] == ".governance/state.json"
                    and conflict["reason"].startswith("existing governance state is invalid: invalid JSON:")
                    for conflict in payload["conflicts"]
                ),
                payload["conflicts"],
            )
            self.assertEqual("# Existing\n", readme.read_text(encoding="utf-8"))
            self.assertEqual("{not json\n", state_path.read_text(encoding="utf-8"))

    def test_init_json_rejects_blocked_state_temp_path_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            state_temp = target / ".governance/.state.json.tmp"
            state_temp.mkdir(parents=True)

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
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {"path": ".governance/.state.json.tmp", "reason": "state temp path is not a file"},
                payload["conflicts"],
            )
            self.assertFalse((target / "README.md").exists())
            self.assertFalse((target / ".governance/state.json").exists())

    def test_init_json_rejects_blocked_generated_temp_path_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            (target / ".README.md.tmp").mkdir()

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
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {"path": ".README.md.tmp", "reason": "generated file temp path is not a file"},
                payload["conflicts"],
            )
            self.assertFalse((target / "README.md").exists())
            self.assertFalse((target / "docs/README.md").exists())
            self.assertFalse((target / ".governance/state.json").exists())

    def test_init_json_rejects_product_archive_generated_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "source-manifest.json"
            product.write_text('{"product": true}\n', encoding="utf-8")

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
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {
                    "path": "docs/product/core/source/source-manifest.json",
                    "reason": "product archive path overlaps generated output",
                },
                payload["conflicts"],
            )
            self.assertFalse(target.exists())

    def test_init_json_rejects_product_archive_generated_temp_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / ".source-manifest.json.tmp"
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
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                {
                    "path": "docs/product/core/source/.source-manifest.json.tmp",
                    "reason": "product archive path overlaps generated file temp path",
                },
                payload["conflicts"],
            )
            self.assertFalse(target.exists())

    def test_runtime_refresh_repairs_target_runtime_and_workflow_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
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
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            prd = target / "docs/product/core/PRD.md"
            prd.write_text(
                prd.read_text(encoding="utf-8") + "\n## Local Product Detail\n\nKeep this content.\n",
                encoding="utf-8",
            )
            runtime = target / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            wrapper = target / "bin/governance"
            wrapper.chmod(0o644)
            workflow = target / "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
            workflow.write_text(workflow.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")
            stale_workflow = target / "docs/agent-workflow/workflow-pack/workflows/99-stale.md"
            stale_workflow.write_text("# Stale Workflow\n", encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, verify_result.returncode)
            self.assertIn("runtime file hash mismatch: scripts/scaffold.py", verify_result.stdout)
            self.assertIn("runtime file is not executable: bin/governance", verify_result.stdout)
            self.assertIn(
                "workflow pack file hash mismatch: "
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                verify_result.stdout,
            )
            self.assertIn(
                "workflow pack file is not listed in manifest: "
                "docs/agent-workflow/workflow-pack/workflows/99-stale.md",
                verify_result.stdout,
            )

            target_local_refresh = subprocess.run(
                [
                    sys.executable,
                    str(target / "scripts/governance_cli.py"),
                    "runtime",
                    "refresh",
                    str(target),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, target_local_refresh.returncode)
            self.assertIn(
                "runtime refresh must be run from a trusted source workflow-pack checkout",
                json.loads(target_local_refresh.stdout)["errors"][0],
            )

            refresh_result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, refresh_result.returncode, refresh_result.stderr)
            payload = json.loads(refresh_result.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("bin/governance", payload["refreshed"])
            self.assertIn("scripts/scaffold.py", payload["refreshed"])
            self.assertIn(
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                payload["refreshed"],
            )
            self.assertIn(
                "docs/agent-workflow/workflow-pack/workflows/99-stale.md",
                payload["removed"],
            )
            self.assertEqual(
                "docs/agent-workflow/runtime-manifest.json",
                payload["state"]["runtime_manifest"],
            )
            self.assertEqual(
                "docs/agent-workflow/workflow-pack/manifest.json",
                payload["state"]["workflow_pack_manifest"],
            )
            self.assertIn("runtime_refreshed_at", payload["state"])
            self.assertIn("Keep this content.", prd.read_text(encoding="utf-8"))
            self.assertTrue(wrapper.stat().st_mode & 0o100)
            self.assertFalse(stale_workflow.exists())

            verify_again = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_again.returncode, verify_again.stderr)

    def test_runtime_refresh_check_json_reports_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state_path = target / ".governance/state.json"
            state_before = state_path.read_text(encoding="utf-8")
            runtime = target / "scripts/scaffold.py"
            runtime_before = runtime.read_text(encoding="utf-8")
            runtime.write_text(runtime_before + "\n# tampered\n", encoding="utf-8")
            workflow = target / "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
            workflow_before = workflow.read_text(encoding="utf-8")
            workflow.write_text(workflow_before + "\nTampered.\n", encoding="utf-8")
            stale_workflow = target / "docs/agent-workflow/workflow-pack/workflows/99-stale.md"
            stale_workflow.write_text("# Stale Workflow\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--check", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual([], payload["refreshed"])
            self.assertEqual([], payload["removed"])
            self.assertIn("bin/governance", payload["would_refresh"])
            self.assertIn("scripts/scaffold.py", payload["would_refresh"])
            self.assertIn(
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                payload["would_refresh"],
            )
            self.assertIn(
                "docs/agent-workflow/workflow-pack/workflows/99-stale.md",
                payload["would_remove"],
            )
            self.assertEqual(state_before, state_path.read_text(encoding="utf-8"))
            self.assertIn("# tampered", runtime.read_text(encoding="utf-8"))
            self.assertIn("Tampered.", workflow.read_text(encoding="utf-8"))
            self.assertTrue(stale_workflow.exists())

    def test_runtime_refresh_rejects_uninitialized_target_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "target is not an initialized governance repository: .governance/state.json is missing",
                payload["errors"],
            )
            self.assertFalse((target / "docs/agent-workflow/runtime-manifest.json").exists())

    def test_runtime_refresh_rejects_invalid_state_without_partial_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            runtime = target / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            state_path = target / ".governance/state.json"
            state_path.write_text("{not json\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("target governance state is invalid", payload["errors"][0])
            self.assertIn("invalid JSON", payload["errors"][0])
            self.assertIn("# tampered", runtime.read_text(encoding="utf-8"))

    def test_runtime_refresh_rejects_blocked_workflow_pack_path_without_partial_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            runtime = target / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            snapshot_root = target / "docs/agent-workflow/workflow-pack"
            shutil.rmtree(snapshot_root)
            snapshot_root.write_text("not a directory\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("runtime refresh preflight failed", payload["errors"][0])
            self.assertIn("docs/agent-workflow/workflow-pack", payload["errors"][0])
            self.assertIn("parent path is not a directory", payload["errors"][0])
            self.assertIn("# tampered", runtime.read_text(encoding="utf-8"))

    def test_runtime_refresh_rejects_blocked_state_temp_path_without_partial_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            runtime = target / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            state_temp = target / ".governance/.state.json.tmp"
            state_temp.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("runtime refresh preflight failed", payload["errors"][0])
            self.assertIn(".governance/.state.json.tmp", payload["errors"][0])
            self.assertIn("state temp path is not a file", payload["errors"][0])
            self.assertIn("# tampered", runtime.read_text(encoding="utf-8"))

    def test_runtime_refresh_rejects_blocked_runtime_temp_path_without_partial_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            runtime = target / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            temp_path = runtime.with_name(".scaffold.py.tmp")
            temp_path.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("runtime refresh preflight failed", payload["errors"][0])
            self.assertIn(str(temp_path), payload["errors"][0])
            self.assertIn("runtime refresh temp path is not a file", payload["errors"][0])
            self.assertIn("# tampered", runtime.read_text(encoding="utf-8"))

    def test_runtime_refresh_reports_unwritable_runtime_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            shutil.rmtree(target / "scripts")
            (target / "scripts").write_text("not a directory\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI), "runtime", "refresh", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("runtime refresh preflight failed", payload["errors"][0])
            self.assertIn(str(target / "scripts"), payload["errors"][0])

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
            self.assertIsInstance(state["last_verification"]["checked_at"], str)
            self.assertIn("T", state["last_verification"]["checked_at"])

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_result.returncode, status_result.stderr)
            self.assertIn("phase: initialized", status_result.stdout)
            self.assertIn("profile: web-app", status_result.stdout)
            self.assertIn("product_import_status: ready_for_structuring", status_result.stdout)
            self.assertIn("product_can_derive_design: True", status_result.stdout)

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

    def test_verify_check_json_does_not_update_state(self) -> None:
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
            state_path = target / ".governance/state.json"
            state_before = state_path.read_text(encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--check", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            payload = json.loads(verify_result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertFalse(payload["state_updated"])
            self.assertEqual([], payload["errors"])
            self.assertEqual("initialized", payload["state"]["phase"])
            self.assertNotIn("last_verification", payload["state"])
            self.assertEqual(state_before, state_path.read_text(encoding="utf-8"))

    def test_status_json_reports_missing_state_with_status_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, status_result.returncode)
            self.assertEqual("", status_result.stderr)
            payload = json.loads(status_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual({}, payload["state"])
            self.assertEqual(["No governance state found."], payload["errors"])
            self.assertEqual("No governance state found.", payload["error"])

    def test_status_json_reports_invalid_state_without_traceback(self) -> None:
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
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state_path = target / ".governance/state.json"
            state_path.write_text("{not json\n", encoding="utf-8")

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, status_result.returncode)
            self.assertEqual("", status_result.stderr)
            payload = json.loads(status_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual({}, payload["state"])
            self.assertIn("invalid governance state file", payload["errors"][0])
            self.assertEqual(str(state_path), payload["path"])
            self.assertIn("invalid governance state file", payload["error"])
            self.assertIn("invalid JSON", payload["error"])

    def test_status_json_reports_state_directory_without_traceback(self) -> None:
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
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state_path = target / ".governance/state.json"
            state_path.unlink()
            state_path.mkdir()

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, status_result.returncode)
            self.assertEqual("", status_result.stderr)
            payload = json.loads(status_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(str(state_path), payload["path"])
            self.assertIn("invalid governance state file", payload["error"])
            self.assertIn("not a file", payload["error"])

    def test_verify_json_reports_invalid_state_without_traceback(self) -> None:
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
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state_path = target / ".governance/state.json"
            state_path.write_text("[]\n", encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            self.assertEqual("", verify_result.stderr)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(str(state_path), payload["path"])
            self.assertIn("root must be an object", payload["error"])

    def test_verify_json_reports_state_update_failure_with_findings_shape(self) -> None:
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
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            state_path = target / ".governance/state.json"
            original_state = json.loads(state_path.read_text(encoding="utf-8"))
            state_temp = target / ".governance/.state.json.tmp"
            state_temp.mkdir()

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            self.assertEqual("", verify_result.stderr)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertIn("findings", payload)
            self.assertIn("warnings", payload)
            self.assertIn("state", payload)
            self.assertIn("state_error", payload)
            self.assertIn("failed to update verification state", payload["errors"][0])
            self.assertIn("unwritable", payload["state_error"])
            self.assertEqual(original_state, json.loads(state_path.read_text(encoding="utf-8")))

    def test_verify_json_does_not_create_state_for_uninitialized_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            self.assertEqual("", verify_result.stderr)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual({}, payload["state"])
            self.assertFalse((target / ".governance/state.json").exists())

    def test_verify_json_reports_unwritable_state_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.write_text("not a directory\n", encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            self.assertEqual("", verify_result.stderr)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertEqual(str(target / ".governance/state.json"), payload["path"])
            self.assertIn("invalid governance state file", payload["error"])
            self.assertIn("unwritable", payload["error"])

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

    def test_gate_product_structuring_allows_ready_markdown_product(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, gate_result.returncode, gate_result.stderr)
            payload = json.loads(gate_result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual("product-structuring", payload["gate"])
            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertTrue(requirements["product_import_ready"]["ok"])

    def test_gate_json_reports_invalid_state_with_gate_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            state_path = target / ".governance/state.json"
            state_path.write_text("{not json\n", encoding="utf-8")

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, gate_result.returncode)
            self.assertEqual("", gate_result.stderr)
            payload = json.loads(gate_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual("product-structuring", payload["gate"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual({}, payload["state"])
            self.assertEqual({}, payload["verification"])
            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertFalse(requirements["state_readable"]["ok"])
            self.assertEqual(".governance/state.json", requirements["state_readable"]["path"])
            self.assertIn("invalid governance state file", requirements["state_readable"]["message"])

    def test_advance_product_structuring_updates_phase_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            advance = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, advance.returncode, advance.stderr)
            payload = json.loads(advance.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["advanced"])
            self.assertEqual("product-structuring", payload["state"]["phase"])
            self.assertEqual("initialized", payload["state"]["phase_history"][0]["from_phase"])
            self.assertEqual("product-structuring", payload["state"]["phase_history"][0]["gate"])

    def test_advance_rejects_duplicate_current_phase_without_writing_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            first = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)

            duplicate = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, duplicate.returncode)
            payload = json.loads(duplicate.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["advanced"])
            self.assertIn("already in phase: product-structuring", payload["errors"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("product-structuring", state["phase"])
            self.assertEqual(1, len(state["phase_history"]))

    def test_advance_check_json_reports_planned_state_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            state_path = target / ".governance/state.json"
            state_before = state_path.read_text(encoding="utf-8")

            advance = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "advance",
                    "product-structuring",
                    str(target),
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, advance.returncode, advance.stderr)
            payload = json.loads(advance.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertFalse(payload["advanced"])
            self.assertTrue(payload["would_advance"])
            self.assertEqual("initialized", payload["state"]["phase"])
            self.assertEqual("product-structuring", payload["would_state"]["phase"])
            self.assertEqual("initialized", payload["would_state"]["phase_history"][0]["from_phase"])
            self.assertEqual("product-structuring", payload["would_state"]["phase_history"][0]["gate"])
            self.assertEqual(state_before, state_path.read_text(encoding="utf-8"))

    def test_advance_check_json_rejects_blocked_state_temp_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            state_temp = target / ".governance/.state.json.tmp"
            state_temp.mkdir()

            advance = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "advance",
                    "product-structuring",
                    str(target),
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, advance.returncode)
            self.assertEqual("", advance.stderr)
            payload = json.loads(advance.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertFalse(payload["advanced"])
            self.assertFalse(payload["would_advance"])
            self.assertIn(".governance/.state.json.tmp is not a file", payload["errors"][0])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("initialized", state["phase"])
            self.assertNotIn("phase_history", state)

    def test_advance_failed_gate_does_not_update_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            advance = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, advance.returncode)
            payload = json.loads(advance.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["advanced"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("initialized", state["phase"])
            self.assertNotIn("phase_history", state)

    def test_advance_reports_state_write_failure_without_partial_phase_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            state_temp = target / ".governance/.state.json.tmp"
            state_temp.mkdir()

            advance = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, advance.returncode)
            self.assertEqual("", advance.stderr)
            payload = json.loads(advance.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["advanced"])
            self.assertIn("failed to advance phase: invalid governance state file", payload["errors"][0])
            self.assertIn("unwritable", payload["errors"][0])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("initialized", state["phase"])
            self.assertNotIn("phase_history", state)

    def test_gate_product_structuring_uses_manifest_after_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", state["product_import_status"])

            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            mark_ready = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "product",
                    "mark-ready",
                    str(target),
                    "--reviewed",
                    "--method",
                    "manual-reviewed-markdown",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, mark_ready.returncode, mark_ready.stderr)

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, gate_result.returncode, gate_result.stderr)
            payload = json.loads(gate_result.stdout)
            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertTrue(requirements["product_import_ready"]["ok"])

    def test_product_mark_ready_requires_review_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("manual review confirmation is required", payload["errors"])
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_conversion_placeholder_prd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("docs/product/core/PRD.md still contains the conversion placeholder", payload["errors"])
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_reports_prd_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            prd = target / "docs/product/core/PRD.md"
            prd.unlink()
            prd.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("reviewed PRD is not a file: docs/product/core/PRD.md", payload["errors"])
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_invalid_archive_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = target / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = str(target / "docs/product/core/source/product.docx")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_archive_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = target / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["size_bytes"] += 1
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "archived product source size mismatch: docs/product/core/source/product.docx",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_missing_archive_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = target / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["archive"]["size_bytes"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "invalid product source manifest: archive.size_bytes is missing or invalid",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_reports_manifest_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = target / "docs/product/core/source/source-manifest.json"
            manifest_path.unlink()
            manifest_path.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "product source manifest is not a file: docs/product/core/source/source-manifest.json",
                payload["errors"],
            )

    def test_product_mark_ready_reports_manifest_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = target / "docs/product/core/source/source-manifest.json"
            manifest_path.write_bytes(b"\xff")

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "invalid product source manifest encoding: expected UTF-8",
                payload["errors"],
            )

    def test_product_mark_ready_rejects_unresolved_directory_without_partial_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            unresolved = target / "docs/unresolved.md"
            unresolved.unlink()
            unresolved.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "docs/unresolved.md is not a file; cannot resolve conversion blocker",
                payload["errors"],
            )
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", state["product_import_status"])

    def test_product_mark_ready_rejects_product_meta_directory_without_partial_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            product_meta = target / "docs/product/core/product-meta.md"
            product_meta.unlink()
            product_meta.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "docs/product/core/product-meta.md is not a file; cannot update product metadata",
                payload["errors"],
            )
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", state["product_import_status"])

    def test_product_mark_ready_rejects_product_meta_temp_directory_without_partial_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            product_meta_temp = target / "docs/product/core/.product-meta.md.tmp"
            product_meta_temp.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "docs/product/core/.product-meta.md.tmp is not a file; cannot prepare product metadata",
                payload["errors"],
            )
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", state["product_import_status"])
            product_meta = (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8")
            self.assertNotIn("- Import status: `ready_for_structuring`", product_meta)

    def test_product_mark_ready_rejects_state_directory_without_partial_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            state_path = target / ".governance/state.json"
            state_path.unlink()
            state_path.mkdir()

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "mark-ready", str(target), "--reviewed", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                ".governance/state.json is not a file; cannot update product import state",
                payload["errors"],
            )
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            product_meta = (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8")
            self.assertNotIn("- Import status: `ready_for_structuring`", product_meta)

    def test_product_mark_ready_resolves_conversion_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text(
                "# Converted Product\n\n"
                "## Goal\n\n"
                "Ship governed projects from reviewed product input.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "product",
                    "mark-ready",
                    str(target),
                    "--reviewed",
                    "--method",
                    "manual-reviewed-markdown",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["conversion_blocker_resolved"])
            self.assertIn("docs/product/core/source/source-manifest.json", payload["updated"])
            self.assertIn("docs/product/core/product-meta.md", payload["updated"])
            self.assertIn("docs/unresolved.md", payload["updated"])
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("ready_for_structuring", manifest["import"]["status"])
            self.assertEqual("manual-reviewed-markdown", manifest["import"]["conversion_method"])
            self.assertTrue(manifest["import"]["can_derive_design"])
            self.assertIn("- Import status: `ready_for_structuring`", (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8"))
            self.assertIn("| U-001 | Product Archiving |", (target / "docs/unresolved.md").read_text(encoding="utf-8"))
            self.assertIn("| resolved |", (target / "docs/unresolved.md").read_text(encoding="utf-8"))

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, gate_result.returncode, gate_result.stderr)

    def test_product_mark_ready_check_json_reports_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/core/PRD.md").write_text(
                "# Converted Product\n\n"
                "## Goal\n\n"
                "Ship governed projects from reviewed product input.\n",
                encoding="utf-8",
            )

            manifest_path = target / "docs/product/core/source/source-manifest.json"
            unresolved_path = target / "docs/unresolved.md"
            state_path = target / ".governance/state.json"
            manifest_before = manifest_path.read_text(encoding="utf-8")
            unresolved_before = unresolved_path.read_text(encoding="utf-8")
            state_before = state_path.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "product",
                    "mark-ready",
                    str(target),
                    "--reviewed",
                    "--method",
                    "manual-reviewed-markdown",
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
            self.assertTrue(payload["check"])
            self.assertEqual([], payload["updated"])
            self.assertEqual("ready_for_structuring", payload["manifest"]["import"]["status"])
            self.assertTrue(payload["manifest"]["import"]["can_derive_design"])
            self.assertTrue(payload["would_resolve_conversion_blocker"])
            self.assertIn("docs/product/core/source/source-manifest.json", payload["would_update"])
            self.assertIn("docs/product/core/product-meta.md", payload["would_update"])
            self.assertIn("docs/unresolved.md", payload["would_update"])
            self.assertIn(".governance/state.json", payload["would_update"])
            self.assertEqual(manifest_before, manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(unresolved_before, unresolved_path.read_text(encoding="utf-8"))
            self.assertEqual(state_before, state_path.read_text(encoding="utf-8"))

    def test_gate_design_derivation_requires_product_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            blocked = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, blocked.returncode)
            blocked_payload = json.loads(blocked.stdout)
            blocked_requirements = {item["code"]: item for item in blocked_payload["requirements"]}
            self.assertFalse(blocked_requirements["product_chapters_present"]["ok"])

            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")

            missing_acceptance = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_acceptance.returncode)
            missing_acceptance_requirements = {item["code"]: item for item in json.loads(missing_acceptance.stdout)["requirements"]}
            self.assertFalse(missing_acceptance_requirements["product_acceptance_chapter_present"]["ok"])

            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            allowed = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)
            self.assertTrue(json.loads(allowed.stdout)["ok"])

    def test_scaffold_product_requires_selected_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "product", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("at least one product chapter must be selected", payload["errors"])
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())

    def test_scaffold_product_writes_selected_indexed_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "goals-and-requirements",
                    "--chapter",
                    "acceptance-criteria",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("docs/product/03-goals-and-requirements.md", payload["created"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["created"])
            self.assertIn("docs/product/03-goals-and-requirements.md", payload["indexed"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["indexed"])
            self.assertIn("docs/product/core/product-meta.md", payload["indexed"])
            goals = (target / "docs/product/03-goals-and-requirements.md").read_text(encoding="utf-8")
            acceptance = (target / "docs/product/08-acceptance-criteria.md").read_text(encoding="utf-8")
            product_readme = (target / "docs/product/README.md").read_text(encoding="utf-8")
            product_meta = (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8")
            self.assertIn("governance:scaffold-placeholder", goals)
            self.assertIn("[PRD](core/PRD.md)", goals)
            self.assertIn("A-NNN", acceptance)
            self.assertIn("03-goals-and-requirements.md", product_readme)
            self.assertIn("[Goals and Requirements](../03-goals-and-requirements.md)", product_meta)
            self.assertIn("[Acceptance Criteria](../08-acceptance-criteria.md)", product_meta)

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, verify_result.returncode)
            verify_payload = json.loads(verify_result.stdout)
            self.assertIn(
                "docs/product/03-goals-and-requirements.md still contains a governance scaffold placeholder",
                verify_payload["errors"],
            )

    def test_scaffold_product_check_json_reports_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            readme_path = target / "docs/product/README.md"
            meta_path = target / "docs/product/core/product-meta.md"
            readme_before = readme_path.read_text(encoding="utf-8")
            meta_before = meta_path.read_text(encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "goals-and-requirements",
                    "--chapter",
                    "acceptance-criteria",
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
            self.assertTrue(payload["check"])
            self.assertEqual([], payload["created"])
            self.assertEqual([], payload["indexed"])
            self.assertIn("docs/product/03-goals-and-requirements.md", payload["would_create"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["would_create"])
            self.assertIn("docs/product/03-goals-and-requirements.md", payload["would_index"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["would_index"])
            self.assertIn("docs/product/core/product-meta.md", payload["would_index"])
            self.assertFalse((target / "docs/product/03-goals-and-requirements.md").exists())
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())
            self.assertEqual(readme_before, readme_path.read_text(encoding="utf-8"))
            self.assertEqual(meta_before, meta_path.read_text(encoding="utf-8"))

    def test_scaffold_product_can_add_chapters_while_product_placeholders_remain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            first = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "goals-and-requirements",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)

            second = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "acceptance-criteria",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, second.returncode, second.stderr)
            payload = json.loads(second.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["created"])
            self.assertIn(
                "[Acceptance Criteria](../08-acceptance-criteria.md)",
                (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8"),
            )

    def test_scaffold_product_reports_invalid_readme_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/README.md").unlink()
            (target / "docs/product/README.md").mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "goals-and-requirements",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("product-structuring gate failed", payload["errors"])
            finding_codes = {
                finding["code"]
                for finding in payload["gate"]["verification"]["findings"]
                if finding["path"] == "docs/product/README.md"
            }
            self.assertIn("docs_directory_governance_file_not_file", finding_codes)
            self.assertIn("docs_readme_not_file", finding_codes)

    def test_scaffold_product_still_fails_on_non_placeholder_verification_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            first = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "goals-and-requirements",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            rogue = target / "docs/rogue"
            rogue.mkdir()
            (rogue / "note.md").write_text("# Rogue\n", encoding="utf-8")

            second = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "acceptance-criteria",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, second.returncode)
            payload = json.loads(second.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("product-structuring gate failed", payload["errors"])
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())

    def test_scaffold_design_rejects_product_chapter_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "design",
                    str(target),
                    "--chapter",
                    "acceptance-criteria",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("scaffold design does not accept --chapter", payload["errors"])

    def test_advance_design_derivation_records_previous_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            first = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            second = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, second.returncode, second.stderr)
            payload = json.loads(second.stdout)
            self.assertEqual("design-derivation", payload["state"]["phase"])
            history = payload["state"]["phase_history"]
            self.assertEqual(2, len(history))
            self.assertEqual("product-structuring", history[1]["from_phase"])
            self.assertEqual("design-derivation", history[1]["phase"])

    def test_advance_rejects_backward_phase_without_writing_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            first = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(_acceptance_doc(), encoding="utf-8")
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")
            second = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, second.returncode, second.stderr)

            backward = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, backward.returncode)
            payload = json.loads(backward.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["advanced"])
            self.assertIn("cannot advance from design-derivation back to product-structuring", payload["errors"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("design-derivation", state["phase"])
            self.assertEqual(2, len(state["phase_history"]))

    def test_gate_implementation_requires_design_and_delivery_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            blocked = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, blocked.returncode)
            blocked_requirements = {item["code"]: item for item in json.loads(blocked.stdout)["requirements"]}
            self.assertFalse(blocked_requirements["architecture_docs_present"]["ok"])

            for domain, filename in [
                ("architecture", "01-context.md"),
                ("api", "00-conventions.md"),
                ("backend", "01-modules.md"),
                ("tests", "01-strategy.md"),
                ("development", "01-roadmap.md"),
            ]:
                path = target / "docs" / domain / filename
                path.write_text(f"# {domain}\n", encoding="utf-8")
                _append_index(target / "docs" / domain / "README.md", filename)

            missing_standard_files = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_standard_files.returncode)
            missing_standard_requirements = {
                item["code"]: item for item in json.loads(missing_standard_files.stdout)["requirements"]
            }
            self.assertTrue(missing_standard_requirements["architecture_docs_present"]["ok"])
            self.assertFalse(missing_standard_requirements["architecture_system_context_present"]["ok"])
            self.assertFalse(missing_standard_requirements["architecture_containers_present"]["ok"])
            self.assertFalse(missing_standard_requirements["architecture_quality_attributes_present"]["ok"])
            self.assertFalse(missing_standard_requirements["api_error_codes_present"]["ok"])
            self.assertFalse(missing_standard_requirements["api_changelog_present"]["ok"])
            self.assertFalse(missing_standard_requirements["api_endpoints_index_present"]["ok"])
            self.assertFalse(missing_standard_requirements["api_endpoint_contract_present"]["ok"])
            self.assertFalse(missing_standard_requirements["verification_log_present"]["ok"])

            for filename, body in [
                ("01-system-context.md", _architecture_system_context_doc()),
                ("02-containers.md", _architecture_containers_doc()),
                ("03-quality-attributes.md", _architecture_quality_attributes_doc()),
            ]:
                path = target / "docs/architecture" / filename
                path.write_text(body, encoding="utf-8")
                _append_index(target / "docs/architecture/README.md", filename)
            (target / "docs/api/00-conventions.md").write_text(
                _api_conventions_doc(),
                encoding="utf-8",
            )
            (target / "docs/api/error-codes.md").write_text(
                _api_error_codes_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/api/README.md", "error-codes.md")
            (target / "docs/api/changelog.md").write_text(
                _api_changelog_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/api/README.md", "changelog.md")
            (target / "docs/tests/01-strategy.md").write_text(
                _test_strategy_doc(),
                encoding="utf-8",
            )
            (target / "docs/development/01-roadmap.md").write_text(
                _roadmap_doc(),
                encoding="utf-8",
            )
            (target / "docs/backend/01-modules.md").write_text(
                _backend_modules_doc(),
                encoding="utf-8",
            )
            for filename in ("02-data-model.md", "03-external-services.md"):
                path = target / "docs/backend" / filename
                path.write_text(f"# {filename}\n", encoding="utf-8")
                _append_index(target / "docs/backend/README.md", filename)
            (target / "docs/backend/02-data-model.md").write_text(
                "# Data Model\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n"
                "- [API conventions](../api/00-conventions.md)\n"
                "- [Backend modules](01-modules.md)\n\n"
                "## Owners\n\n"
                "- Goal state is owned by the workflow backend module.\n\n"
                "## Entities\n\n"
                "- Goal: user-owned workflow item with status and audit fields.\n\n"
                "## State Machines\n\n"
                "- Goal status moves from draft to active to archived.\n\n"
                "## Constraints\n\n"
                "- Goal identifiers are unique per owner and idempotency key.\n\n"
                "## Indexes\n\n"
                "- Owner and status indexes support primary goal list queries.\n\n"
                "## Migrations\n\n"
                "- Add owner-scoped goal tables before enabling API writes.\n",
                encoding="utf-8",
            )
            (target / "docs/backend/03-external-services.md").write_text(
                _backend_external_services_doc(),
                encoding="utf-8",
            )

            missing_ui_frontend = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_ui_frontend.returncode)
            missing_ui_frontend_requirements = {
                item["code"]: item for item in json.loads(missing_ui_frontend.stdout)["requirements"]
            }
            self.assertFalse(missing_ui_frontend_requirements["ui_docs_present"]["ok"])
            self.assertFalse(missing_ui_frontend_requirements["frontend_docs_present"]["ok"])

            (target / "docs/ui/01-interaction-model.md").write_text(
                _ui_interaction_model_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/ui/README.md", "01-interaction-model.md")
            (target / "docs/frontend/01-modules.md").write_text(
                _frontend_modules_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/frontend/README.md", "01-modules.md")
            (target / "docs/frontend/02-api-consumption.md").write_text(
                _frontend_api_consumption_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/frontend/README.md", "02-api-consumption.md")
            endpoint_root = target / "docs/api/endpoints"
            endpoint_root.mkdir(parents=True, exist_ok=True)
            (endpoint_root / "README.md").write_text(
                "# API Endpoints\n\n"
                "- `01-goal-flow.md` - goal flow endpoint\n",
                encoding="utf-8",
            )
            (endpoint_root / "01-goal-flow.md").write_text(
                _api_endpoint_contract_doc(),
                encoding="utf-8",
            )

            missing_matrix = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_matrix.returncode)
            missing_matrix_requirements = {item["code"]: item for item in json.loads(missing_matrix.stdout)["requirements"]}
            self.assertTrue(missing_matrix_requirements["ui_docs_present"]["ok"])
            self.assertTrue(missing_matrix_requirements["frontend_docs_present"]["ok"])
            self.assertTrue(missing_matrix_requirements["api_endpoints_index_present"]["ok"])
            self.assertTrue(missing_matrix_requirements["api_endpoint_contract_present"]["ok"])
            self.assertFalse(missing_matrix_requirements["acceptance_matrix_present"]["ok"])

            (target / "docs/tests/02-acceptance-matrix.md").write_text(
                _acceptance_matrix_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/tests/README.md", "02-acceptance-matrix.md")
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/development/README.md", "03-verification-log.md")

            missing_task = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_task.returncode)
            missing_task_requirements = {item["code"]: item for item in json.loads(missing_task.stdout)["requirements"]}
            self.assertTrue(missing_task_requirements["acceptance_matrix_present"]["ok"])
            self.assertFalse(missing_task_requirements["task_board_ready_task_present"]["ok"])

            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-system-context.md | docs/api/missing.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/development/README.md", "02-task-board.md")

            blocked_trace = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, blocked_trace.returncode)
            blocked_trace_payload = json.loads(blocked_trace.stdout)
            blocked_trace_requirements = {item["code"]: item for item in blocked_trace_payload["requirements"]}
            self.assertFalse(blocked_trace_requirements["verification_passed"]["ok"])
            self.assertFalse(blocked_trace_requirements["task_board_ready_task_present"]["ok"])
            self.assertIn(
                {
                    "code": "task_board_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 references missing API target: docs/api/missing.md",
                },
                blocked_trace_payload["verification"]["findings"],
            )

            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-system-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )

            allowed = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)
            self.assertTrue(json.loads(allowed.stdout)["ok"])

    def test_scaffold_design_requires_design_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, scaffold.returncode)
            payload = json.loads(scaffold.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("design-derivation gate failed", payload["errors"])
            self.assertFalse((target / "docs/architecture/01-system-context.md").exists())

    def test_scaffold_design_writes_indexed_placeholders_and_blocks_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, scaffold.returncode, scaffold.stderr)
            payload = json.loads(scaffold.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("docs/architecture/01-system-context.md", payload["created"])
            self.assertIn("docs/api/endpoints/README.md", payload["created"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", payload["created"])
            self.assertIn("docs/development/03-verification-log.md", payload["created"])
            self.assertTrue((target / "docs/backend/02-data-model.md").exists())
            self.assertIn("01-system-context.md", (target / "docs/architecture/README.md").read_text(encoding="utf-8"))
            self.assertIn("00-conventions.md", (target / "docs/api/README.md").read_text(encoding="utf-8"))
            self.assertIn("03-verification-log.md", (target / "docs/development/README.md").read_text(encoding="utf-8"))
            endpoints_index = (target / "docs/api/endpoints/README.md").read_text(encoding="utf-8")
            endpoint_contract = (target / "docs/api/endpoints/01-endpoint-contract.md").read_text(encoding="utf-8")
            acceptance_matrix = (target / "docs/tests/02-acceptance-matrix.md").read_text(encoding="utf-8")
            roadmap = (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8")
            task_board = (target / "docs/development/02-task-board.md").read_text(encoding="utf-8")
            verification_log = (target / "docs/development/03-verification-log.md").read_text(encoding="utf-8")
            self.assertNotIn("README.md", endpoints_index)
            self.assertIn("01-endpoint-contract.md", endpoints_index)
            self.assertIn("## Method and Path", endpoint_contract)
            self.assertIn("governance:scaffold-placeholder", endpoint_contract)
            self.assertIn("| Acceptance | Design | API | Test |", acceptance_matrix)
            self.assertIn("| ID | Status | Milestone |", roadmap)
            self.assertIn("| ID | Status | Task | Product | Design | API | Acceptance | Verification |", task_board)
            self.assertIn("Allowed statuses: Backlog, Ready, In Progress, Blocked, Done, Deferred.", task_board)
            self.assertIn("| Task | Command | Result | Date | Notes |", verification_log)
            self.assertIn("governance:scaffold-placeholder", verification_log)

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, verify_result.returncode)
            verify_payload = json.loads(verify_result.stdout)
            finding_codes = {item["code"] for item in verify_payload["findings"]}
            self.assertIn("governance_scaffold_placeholder", finding_codes)
            self.assertNotIn("docs_readme_unindexed_file", finding_codes)

            gate = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, gate.returncode)
            requirements = {item["code"]: item for item in json.loads(gate.stdout)["requirements"]}
            self.assertTrue(requirements["api_endpoint_contract_present"]["ok"])
            self.assertFalse(requirements["verification_passed"]["ok"])

    def test_scaffold_design_check_json_reports_plan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")
            architecture_readme = target / "docs/architecture/README.md"
            architecture_readme_before = architecture_readme.read_text(encoding="utf-8")

            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--check", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, scaffold.returncode, scaffold.stderr)
            payload = json.loads(scaffold.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertEqual([], payload["created"])
            self.assertEqual([], payload["indexed"])
            self.assertIn("docs/architecture/01-system-context.md", payload["would_create"])
            self.assertIn("docs/api/endpoints/README.md", payload["would_create"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", payload["would_create"])
            self.assertIn("docs/development/03-verification-log.md", payload["would_create"])
            self.assertIn("docs/architecture/01-system-context.md", payload["would_index"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", payload["would_index"])
            self.assertIn("docs/development/03-verification-log.md", payload["would_index"])
            self.assertFalse((target / "docs/architecture/01-system-context.md").exists())
            self.assertFalse((target / "docs/api/endpoints/01-endpoint-contract.md").exists())
            self.assertFalse((target / "docs/development/03-verification-log.md").exists())
            self.assertEqual(architecture_readme_before, architecture_readme.read_text(encoding="utf-8"))

    def test_scaffold_design_skips_starter_endpoint_when_contract_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")
            (target / "docs/api/error-codes.md").write_text(
                _api_error_codes_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/api/README.md", "error-codes.md")
            (target / "docs/ui/01-interaction-model.md").write_text(
                _ui_interaction_model_doc(),
                encoding="utf-8",
            )
            _append_index(target / "docs/ui/README.md", "01-interaction-model.md")
            endpoint_root = target / "docs/api/endpoints"
            endpoint_root.mkdir(parents=True, exist_ok=True)
            (endpoint_root / "README.md").write_text(
                "# API Endpoints\n\n"
                "## Index\n\n"
                "- `01-goal-flow.md` - goal flow endpoint\n",
                encoding="utf-8",
            )
            (endpoint_root / "01-goal-flow.md").write_text(
                _api_endpoint_contract_doc().replace(
                    "../../frontend/02-api-consumption.md",
                    "../../ui/01-interaction-model.md",
                ),
                encoding="utf-8",
            )

            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, scaffold.returncode, scaffold.stderr)
            payload = json.loads(scaffold.stdout)
            self.assertTrue(payload["ok"])
            self.assertNotIn("docs/api/endpoints/01-endpoint-contract.md", payload["created"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", payload["skipped"])
            self.assertFalse((endpoint_root / "01-endpoint-contract.md").exists())

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            verify_payload = json.loads(verify_result.stdout)
            finding_codes = {item["code"] for item in verify_payload["findings"]}
            self.assertNotIn("api_endpoint_duplicate_prefix", finding_codes)


if __name__ == "__main__":
    unittest.main()
