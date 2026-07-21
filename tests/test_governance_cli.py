import json
import contextlib
import importlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "governance_cli.py"


def _agent_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    env.pop("MAKELEVEL", None)
    return env


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


def _requirements_by_name(requirements: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(requirement["name"]): requirement for requirement in requirements}


def _link_statuses(links: list[dict[str, object]]) -> dict[str, str]:
    return {str(link["kind"]): str(link["status"]) for link in links}


def _repair_actions_by_link_kind(actions: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(action["link_kind"]): action for action in actions}


def _repair_actions_by_evidence_id(actions: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(action["evidence_id"]): action for action in actions}


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


def _append_project_command(
    target: Path,
    *,
    name: str,
    argv: list[str],
    writes_state: bool = False,
    approval_required: bool = False,
    cwd: str = ".",
    environment: str = "core-governance",
) -> None:
    path = target / "docs/agent-workflow/command-contract.md"
    text = path.read_text(encoding="utf-8")
    row = (
        f"| {name} | Verify one implementation task. | `{cwd}` | `{json.dumps(argv)}` | "
        f"{str(writes_state).lower()} | {str(approval_required).lower()} | "
        f"`docs/development/04-implementation-evidence.md` | {environment} |\n"
    )
    lines = text.splitlines(keepends=True)
    prefix = f"| {name} |"
    text = "".join(line for line in lines if not line.startswith(prefix))
    path.write_text(text.replace("\n## Project Commands", f"\n{row}\n## Project Commands", 1), encoding="utf-8")


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


def _run_governance_json(
    case: unittest.TestCase,
    args: list[str],
    *,
    cwd: Path | None = None,
    expected_returncode: int = 0,
) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(CLI), *args, "--json"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    case.assertEqual(expected_returncode, result.returncode, f"{result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def _implementation_ready_target(
    case: unittest.TestCase,
    tmp: str,
    *,
    advance_implementation: bool = True,
) -> Path:
    root = Path(tmp)
    target = root / "target"
    product = root / "product.md"
    product.write_text("# Product\n", encoding="utf-8")
    _run_governance_json(case, ["init", "--target", str(target), "--product", str(product)])
    git_init = subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    case.assertEqual(0, git_init.returncode, git_init.stderr)

    (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
    _append_index(target / "docs/product/README.md", "01-goals.md")
    _append_product_meta_chapter(target, "01-goals.md")
    (target / "docs/product/08-acceptance-criteria.md").write_text(_acceptance_doc(), encoding="utf-8")
    _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
    _append_product_meta_chapter(target, "08-acceptance-criteria.md")
    _run_governance_json(case, ["advance", "product-structuring", str(target)])
    _run_governance_json(case, ["advance", "design-derivation", str(target)])

    for filename, body in [
        ("01-system-context.md", _architecture_system_context_doc()),
        ("02-containers.md", _architecture_containers_doc()),
        ("03-quality-attributes.md", _architecture_quality_attributes_doc()),
    ]:
        path = target / "docs/architecture" / filename
        path.write_text(body, encoding="utf-8")
        _append_index(target / "docs/architecture/README.md", filename)
    (target / "docs/api/00-conventions.md").write_text(_api_conventions_doc(), encoding="utf-8")
    _append_index(target / "docs/api/README.md", "00-conventions.md")
    (target / "docs/api/error-codes.md").write_text(_api_error_codes_doc(), encoding="utf-8")
    _append_index(target / "docs/api/README.md", "error-codes.md")
    (target / "docs/api/changelog.md").write_text(_api_changelog_doc(), encoding="utf-8")
    _append_index(target / "docs/api/README.md", "changelog.md")
    endpoint_root = target / "docs/api/endpoints"
    endpoint_root.mkdir(parents=True, exist_ok=True)
    (endpoint_root / "README.md").write_text(
        "# API Endpoints\n\n- `01-goal-flow.md` - goal flow endpoint\n",
        encoding="utf-8",
    )
    (endpoint_root / "01-goal-flow.md").write_text(_api_endpoint_contract_doc(), encoding="utf-8")
    (target / "docs/backend/01-modules.md").write_text(_backend_modules_doc(), encoding="utf-8")
    _append_index(target / "docs/backend/README.md", "01-modules.md")
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
    _append_index(target / "docs/backend/README.md", "02-data-model.md")
    (target / "docs/backend/03-external-services.md").write_text(_backend_external_services_doc(), encoding="utf-8")
    _append_index(target / "docs/backend/README.md", "03-external-services.md")
    (target / "docs/ui/01-interaction-model.md").write_text(_ui_interaction_model_doc(), encoding="utf-8")
    _append_index(target / "docs/ui/README.md", "01-interaction-model.md")
    (target / "docs/frontend/01-modules.md").write_text(_frontend_modules_doc(), encoding="utf-8")
    _append_index(target / "docs/frontend/README.md", "01-modules.md")
    (target / "docs/frontend/02-api-consumption.md").write_text(_frontend_api_consumption_doc(), encoding="utf-8")
    _append_index(target / "docs/frontend/README.md", "02-api-consumption.md")
    (target / "docs/tests/01-strategy.md").write_text(_test_strategy_doc(), encoding="utf-8")
    _append_index(target / "docs/tests/README.md", "01-strategy.md")
    (target / "docs/tests/02-acceptance-matrix.md").write_text(_acceptance_matrix_doc(), encoding="utf-8")
    _append_index(target / "docs/tests/README.md", "02-acceptance-matrix.md")
    (target / "docs/development/01-roadmap.md").write_text(_roadmap_doc(), encoding="utf-8")
    _append_index(target / "docs/development/README.md", "01-roadmap.md")
    (target / "docs/development/02-task-board.md").write_text(
        _task_board_doc(
            "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | "
            "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
            "docs/product/08-acceptance-criteria.md | command:task-tests |\n"
        ),
        encoding="utf-8",
    )
    _append_index(target / "docs/development/README.md", "02-task-board.md")
    (target / "docs/development/03-verification-log.md").write_text(_verification_log_doc(), encoding="utf-8")
    _append_index(target / "docs/development/README.md", "03-verification-log.md")
    command_contract = target / "docs/agent-workflow/command-contract.md"
    command_contract.write_text(
        command_contract.read_text(encoding="utf-8").replace(
            "\n## Project Commands",
            "\n| task-tests | Run task unit tests. | `.` | "
            "`[\"python3\", \"-m\", \"unittest\", \"discover\"]` | false | false | "
            "`docs/development/04-implementation-evidence.md` | core-governance |\n\n"
            "## Project Commands",
            1,
        ),
        encoding="utf-8",
    )
    _write_test_openapi(target)

    if advance_implementation:
        _record_all_test_design_reviews(case, target)
        _run_governance_json(case, ["advance", "implementation", str(target)])
    return target


def _write_test_implementation_change(target: Path) -> None:
    path = target / "src/reviewed_task.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def reviewed_task_ready():\n    return True\n", encoding="utf-8")


def _record_test_code_review(case: unittest.TestCase, target: Path) -> dict[str, object]:
    report = target / ".governance/code-review-reports/TASK-001.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": "TASK-001",
                "reviewer": {"kind": "agent", "id": "governance-cli-test-reviewer"},
                "verdict": "approved",
                "summary": "Reviewed the complete current task change set and passing verification evidence.",
                "findings": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return _run_governance_json(
        case,
        [
            "implementation",
            "review",
            str(target),
            "--task",
            "TASK-001",
            "--report",
            str(report),
            "--reviewed",
        ],
    )


def _prepare_reviewed_task_with_passing_log(
    case: unittest.TestCase,
    target: Path,
) -> None:
    started = _run_governance_json(
        case,
        ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
    )
    case.assertTrue(started["applied"] or started["already_current"])
    _write_test_implementation_change(target)
    (target / "docs/development/03-verification-log.md").write_text(
        _verification_log_doc(
            "| TASK-001 | task-tests | pass | 2026-07-08 | Local verification passed. |\n"
        ),
        encoding="utf-8",
    )
    reviewed = _record_test_code_review(case, target)
    case.assertTrue(reviewed["evidence_current"])


def _design_scaffold_target(case: unittest.TestCase, tmp: str) -> Path:
    root = Path(tmp)
    target = root / "target"
    product = root / "product.md"
    product.write_text("# Product\n", encoding="utf-8")
    _run_governance_json(case, ["init", "--target", str(target), "--product", str(product)])
    (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
    _append_index(target / "docs/product/README.md", "01-goals.md")
    _append_product_meta_chapter(target, "01-goals.md")
    (target / "docs/product/08-acceptance-criteria.md").write_text(_acceptance_doc(), encoding="utf-8")
    _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
    _append_product_meta_chapter(target, "08-acceptance-criteria.md")
    _run_governance_json(case, ["advance", "product-structuring", str(target)])
    _run_governance_json(case, ["advance", "design-derivation", str(target)])
    _run_governance_json(case, ["scaffold", "design", str(target)])
    return target


def _install_test_authority_skills(target: Path, names: tuple[str, ...]) -> None:
    for name in names:
        path = target / ".agents/skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\nname: {name}\ndescription: Test-only authority routing fixture.\n---\n\n# {name}\n",
            encoding="utf-8",
        )
        if name == "api-design-reviewer":
            _install_test_api_review_tools(target)
        if name == "senior-security":
            _install_test_threat_modeler(target)
        if name == "slo-architect":
            _install_test_slo_tools(target)
        if name == "migration-architect":
            _install_test_migration_tools(target)


def _install_test_threat_modeler(target: Path) -> None:
    script = target / ".agents/skills/senior-security/scripts/threat_modeler.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "component = sys.argv[sys.argv.index('--component') + 1]\n"
        "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "report = {\n"
        "    'component': component,\n"
        "    'analysis_date': '2026-01-01T00:00:00+00:00',\n"
        "    'summary': {\n"
        "        'total_threats': 2,\n"
        "        'by_risk_level': {'critical': 0, 'high': 1, 'medium': 1, 'low': 0},\n"
        "    },\n"
        "    'threats': [{\n"
        "        'category': 'Spoofing',\n"
        "        'name': 'API Key Impersonation',\n"
        "        'description': 'An attacker uses a stolen API credential.',\n"
        "        'attack_vector': 'Credential exposure',\n"
        "        'impact': 'Unauthorized access',\n"
        "        'likelihood': 4,\n"
        "        'severity': 4,\n"
        "        'risk_score': 16,\n"
        "        'risk_level': 'High',\n"
        "        'dread': {\n"
        "            'damage': 8,\n"
        "            'reproducibility': 8,\n"
        "            'exploitability': 8,\n"
        "            'affected_users': 8,\n"
        "            'discoverability': 8,\n"
        "            'total': 8.0,\n"
        "        },\n"
        "        'mitigations': ['Use short-lived credentials.'],\n"
        "    }, {\n"
        "        'category': 'Denial of Service',\n"
        "        'name': 'Burst Exhaustion',\n"
        "        'description': 'A client exhausts request capacity.',\n"
        "        'attack_vector': 'Request bursts',\n"
        "        'impact': 'Temporary degradation',\n"
        "        'likelihood': 2,\n"
        "        'severity': 2,\n"
        "        'risk_score': 4,\n"
        "        'risk_level': 'Medium',\n"
        "        'dread': {\n"
        "            'damage': 4,\n"
        "            'reproducibility': 5,\n"
        "            'exploitability': 4,\n"
        "            'affected_users': 5,\n"
        "            'discoverability': 7,\n"
        "            'total': 5.0,\n"
        "        },\n"
        "        'mitigations': ['Apply layered rate limits.'],\n"
        "    }],\n"
        "}\n"
        "output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )


def _write_test_threat_review_inputs(target: Path, *, include_owner: bool = True) -> None:
    root = target / "docs/architecture/threat-model"
    root.mkdir(parents=True, exist_ok=True)
    categories = [
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
        "Elevation of Privilege",
    ]
    scope = {
        "schema_version": 1,
        "elements": [
            {
                "id": "goal-api",
                "name": "Goal API",
                "type": "process",
                "component": "REST API",
                "assets": ["goal_data", "access_tokens"],
                "trust_boundaries": ["public-client-to-api"],
                "source_references": [
                    "docs/architecture/01-system-context.md",
                    "docs/architecture/02-containers.md",
                    "docs/architecture/03-quality-attributes.md",
                ],
            }
        ],
        "stride_coverage": [
            {
                "element_id": "goal-api",
                "category": category,
                "status": "considered",
                "notes": f"Reviewed {category} against the Goal API boundary.",
            }
            for category in categories
        ],
    }
    mitigation = {
        "element_id": "goal-api",
        "category": "Spoofing",
        "threat_name": "API Key Impersonation",
        "owner": "backend-security" if include_owner else "",
        "mitigation": "Use short-lived credentials and rotate exposed keys.",
        "evidence": ["docs/architecture/03-quality-attributes.md"],
    }
    mitigations = {"schema_version": 1, "mitigations": [mitigation]}
    (root / "scope.json").write_text(
        json.dumps(scope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "mitigations.json").write_text(
        json.dumps(mitigations, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _install_test_slo_tools(target: Path) -> None:
    root = target / ".agents/skills/slo-architect/scripts"
    root.mkdir(parents=True, exist_ok=True)
    (root / "slo_designer.py").write_text(
        "import json\n"
        "import sys\n"
        "from datetime import datetime, timezone\n\n"
        "def arg(name, default=''):\n"
        "    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default\n\n"
        "target = float(arg('--target'))\n"
        "window = int(arg('--window-days'))\n"
        "payload = {\n"
        "    'slo_id': 'nondeterministic-' + str(datetime.now(timezone.utc).timestamp()),\n"
        "    'created': datetime.now(timezone.utc).isoformat(),\n"
        "    'service': arg('--service'),\n"
        "    'owner': arg('--owner'),\n"
        "    'user_journey': arg('--user-journey'),\n"
        "    'sli': {\n"
        "        'type': arg('--sli-type'),\n"
        "        'numerator': arg('--sli-numerator', 'count(good_events)'),\n"
        "        'denominator': arg('--sli-denominator', 'count(total_events)'),\n"
        "        'labels': arg('--sli-labels').split(',') if arg('--sli-labels') else [],\n"
        "    },\n"
        "    'target_percent': target,\n"
        "    'window_days': window,\n"
        "    'error_budget': {\n"
        "        'minutes_per_window': round((100 - target) / 100 * window * 24 * 60, 2),\n"
        "        'policy_doc': arg('--policy-doc'),\n"
        "    },\n"
        "    'alerts': {\n"
        "        'fast_burn_threshold': 'see error_budget_calculator.py',\n"
        "        'slow_burn_threshold': 'see error_budget_calculator.py',\n"
        "    },\n"
        "    'review_cadence': arg('--review-cadence', 'quarterly'),\n"
        "}\n"
        "print(json.dumps(payload, indent=2, sort_keys=True))\n",
        encoding="utf-8",
    )
    (root / "error_budget_calculator.py").write_text(
        "import json\n"
        "import sys\n\n"
        "target = float(sys.argv[sys.argv.index('--target') + 1])\n"
        "window = int(sys.argv[sys.argv.index('--window-days') + 1])\n"
        "budget = round((100 - target) / 100 * window * 24 * 60, 4)\n"
        "payload = {\n"
        "    'target_percent': target,\n"
        "    'window_days': window,\n"
        "    'bad_fraction': round((100 - target) / 100, 6),\n"
        "    'budget_minutes': budget,\n"
        "    'budget_hours': round(budget / 60, 4),\n"
        "    'alert_rules': [\n"
        "        {'name': 'fast_burn', 'severity': 'page', 'long_window': '1h', 'short_window': '5m', 'budget_pct_consumed': 2.0, 'burn_rate_threshold': 14.4, 'rationale': 'fast', 'promql': 'fast'},\n"
        "        {'name': 'slow_burn', 'severity': 'page', 'long_window': '6h', 'short_window': '30m', 'budget_pct_consumed': 5.0, 'burn_rate_threshold': 6.0, 'rationale': 'slow', 'promql': 'slow'},\n"
        "        {'name': 'ticket_burn', 'severity': 'ticket', 'long_window': '3d', 'short_window': '6h', 'budget_pct_consumed': 10.0, 'burn_rate_threshold': 1.0, 'rationale': 'ticket', 'promql': 'ticket'},\n"
        "    ],\n"
        "}\n"
        "print(json.dumps(payload, indent=2, sort_keys=True))\n",
        encoding="utf-8",
    )
    (root / "slo_review.py").write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "review_root = Path(sys.argv[sys.argv.index('--slo-doc') + 1])\n"
        "results = []\n"
        "for path in sorted(review_root.glob('*.json')):\n"
        "    doc = json.loads(path.read_text(encoding='utf-8'))\n"
        "    findings = []\n"
        "    target = doc.get('target')\n"
        "    window = doc.get('window_days')\n"
        "    if target is None:\n"
        "        findings.append(['FAIL', 'no_target', 'no target'])\n"
        "    elif target >= 99.99:\n"
        "        findings.append(['FAIL', 'target_too_high', 'target too high'])\n"
        "    elif target <= 99.0:\n"
        "        findings.append(['WARN', 'target_too_low', 'target too low'])\n"
        "    if window is None or window < 7:\n"
        "        findings.append(['FAIL', 'window_too_short', 'window too short'])\n"
        "    if findings:\n"
        "        results.append({'path': str(path), 'findings': findings})\n"
        "print(json.dumps(results, indent=2, sort_keys=True))\n"
        "raise SystemExit(1 if any(f[0] == 'FAIL' for r in results for f in r['findings']) else 0)\n",
        encoding="utf-8",
    )


def _write_test_reliability_review_inputs(
    target: Path,
    *,
    decision: str = "required",
    target_percent: float = 99.9,
) -> None:
    root = target / "docs/backend/reliability"
    root.mkdir(parents=True, exist_ok=True)
    source_references = [
        "docs/product/08-acceptance-criteria.md",
        "docs/architecture/03-quality-attributes.md",
        "docs/backend/01-modules.md",
        "docs/backend/03-external-services.md",
    ]
    applicability = {
        "decision": decision,
        "owner": "backend-platform",
        "reason": (
            "The user-facing goal API requires a measurable reliability objective."
            if decision == "required"
            else "This repository does not operate a production service or user-facing reliability commitment."
        ),
        "source_references": source_references,
        "revisit_triggers": [
            "A production service or user-facing reliability commitment is introduced."
        ],
    }
    slos: list[dict[str, object]] = []
    if decision == "required":
        policy = target / "docs/backend/04-error-budget-policy.md"
        policy.write_text(
            "# Error Budget Policy\n\n"
            "## Scope\n\n- Protect the goal creation journey.\n\n"
            "## Budget Actions\n\n- Pause risky releases when the budget is exhausted.\n\n"
            "## Release Policy\n\n- Use multi-window burn-rate evidence before rollback.\n\n"
            "## Incident Policy\n\n- Page the backend owner on fast or slow burn.\n\n"
            "## Review\n\n- Review quarterly with product and backend owners.\n",
            encoding="utf-8",
        )
        readme = target / "docs/backend/README.md"
        if "04-error-budget-policy.md" not in readme.read_text(encoding="utf-8"):
            _append_index(readme, "04-error-budget-policy.md")
        slos.append(
            {
                "id": "goal-api-success",
                "service": "goal-api",
                "sli_type": "request-success-rate",
                "target_percent": target_percent,
                "window_days": 28,
                "owner": "backend-platform",
                "user_journey": "An authenticated user creates a goal and receives a stable identifier.",
                "sli_numerator": "count(goal_create_requests_total{outcome=\"success\"})",
                "sli_denominator": "count(goal_create_requests_total)",
                "sli_labels": ["environment=production"],
                "policy_doc": "docs/backend/04-error-budget-policy.md",
                "review_cadence": "quarterly",
                "source_references": source_references,
                "target_basis": {
                    "kind": "provisional-prelaunch",
                    "rationale": "Use a provisional target until production measurements establish a sustainable baseline.",
                    "source_references": [
                        "docs/architecture/03-quality-attributes.md",
                        "docs/product/08-acceptance-criteria.md",
                    ],
                    "validation_plan": "Measure the SLI for 28 days after launch and review the target before the next release.",
                },
            }
        )
    document = {
        "schema_version": 1,
        "applicability": applicability,
        "slos": slos,
    }
    (root / "slo-scope.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _install_test_migration_tools(target: Path, *, issue_severity: str = "") -> None:
    root = target / ".agents/skills/migration-architect/scripts"
    root.mkdir(parents=True, exist_ok=True)
    (root / "migration_planner.py").write_text(
        "import json\n"
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "source = json.loads(Path(sys.argv[sys.argv.index('--input') + 1]).read_text(encoding='utf-8'))\n"
        "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "plan = {\n"
        "    'migration_id': 'fixture-migration',\n"
        "    'source_system': source['source'],\n"
        "    'target_system': source['target'],\n"
        "    'migration_type': source['type'],\n"
        "    'complexity': 'low',\n"
        "    'estimated_duration_hours': 4,\n"
        "    'phases': [{'name': 'migration', 'description': 'Apply initial schema', 'duration_hours': 4, 'dependencies': [], 'validation_criteria': ['Schema validation passes'], 'rollback_triggers': ['Validation fails'], 'tasks': ['Apply schema'], 'risk_level': 'low', 'resources_required': ['database owner']}],\n"
        "    'risks': [{'category': 'technical', 'description': 'Schema application fails', 'probability': 'low', 'impact': 'medium', 'severity': 'medium', 'mitigation': 'Run validation before cutover', 'owner': 'database-platform'}],\n"
        "    'success_criteria': ['Schema validation passes'],\n"
        "    'rollback_plan': {'rollback_phases': [{'phase': 'migration', 'rollback_actions': ['Drop initial schema'], 'validation_criteria': ['Empty schema restored'], 'estimated_time_minutes': 15}], 'rollback_triggers': ['Validation fails'], 'rollback_decision_matrix': {'medium_severity': 'rollback'}, 'rollback_contacts': ['database-platform']},\n"
        "    'stakeholders': ['database-platform'],\n"
        "    'created_at': datetime.now(timezone.utc).isoformat(),\n"
        "}\n"
        "output.write_text(json.dumps(plan, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    issue = (
        {
            "type": "column_removed",
            "severity": issue_severity,
            "description": "Column legacy_title is removed from goals",
            "field_path": "tables.goals.columns.legacy_title",
            "old_value": {"type": "varchar", "nullable": True},
            "new_value": None,
            "impact": "Existing readers can fail",
            "suggested_migration": "Use expand-contract before removal",
            "affected_operations": ["SELECT", "UPDATE"],
        }
        if issue_severity
        else None
    )
    issue_count = 1 if issue_severity else 0
    compatibility = (
        "breaking_changes"
        if issue_severity == "breaking"
        else "potentially_incompatible"
        if issue_severity
        else "backward_compatible"
    )
    return_code = 2 if issue_severity == "breaking" else 1 if issue_severity else 0
    (root / "compatibility_checker.py").write_text(
        "import json\n"
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "before = Path(sys.argv[sys.argv.index('--before') + 1]).read_text(encoding='utf-8')\n"
        "after = Path(sys.argv[sys.argv.index('--after') + 1]).read_text(encoding='utf-8')\n"
        "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
        f"issue = {issue!r}\n"
        "issues = [issue] if issue else []\n"
        "report = {\n"
        "    'schema_before': before[:500],\n"
        "    'schema_after': after[:500],\n"
        "    'analysis_date': datetime.now(timezone.utc).isoformat(),\n"
        f"    'overall_compatibility': {compatibility!r},\n"
        f"    'breaking_changes_count': {issue_count if issue_severity == 'breaking' else 0},\n"
        f"    'potentially_breaking_count': {issue_count if issue_severity and issue_severity != 'breaking' else 0},\n"
        "    'non_breaking_changes_count': 0,\n"
        "    'additive_changes_count': 1,\n"
        "    'issues': issues,\n"
        "    'migration_scripts': [{'script_type': 'sql', 'description': 'Create goals table', 'script_content': 'CREATE TABLE goals (id text primary key);', 'rollback_script': 'DROP TABLE goals;', 'dependencies': [], 'validation_query': \"SELECT 1 FROM goals LIMIT 1;\"}],\n"
        "    'risk_assessment': {'overall_risk': 'low', 'deployment_risk': 'safe_independent_deployment', 'rollback_complexity': 'low', 'testing_requirements': ['migration_testing']},\n"
        "    'recommendations': ['Run migration tests'],\n"
        "}\n"
        "output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
        f"raise SystemExit({return_code})\n",
        encoding="utf-8",
    )
    (root / "rollback_generator.py").write_text(
        "import json\n"
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "plan = json.loads(Path(sys.argv[sys.argv.index('--input') + 1]).read_text(encoding='utf-8'))\n"
        "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "runbook = {\n"
        "    'runbook_id': 'fixture-runbook',\n"
        "    'migration_id': plan['migration_id'],\n"
        "    'created_at': datetime.now(timezone.utc).isoformat(),\n"
        "    'rollback_phases': [{'phase_name': 'rollback_migration', 'description': 'Undo migration', 'urgency_level': 'medium', 'estimated_duration_minutes': 15, 'prerequisites': ['Database owner available'], 'steps': [{'step_id': 'rollback-1', 'name': 'Drop goals table', 'description': 'Restore empty schema', 'script_type': 'sql', 'script_content': 'DROP TABLE goals;', 'estimated_duration_minutes': 5, 'dependencies': [], 'validation_commands': [\"SELECT 1;\"], 'success_criteria': ['Empty schema restored'], 'failure_escalation': 'Escalate to database owner', 'rollback_order': 1}], 'validation_checkpoints': ['Empty schema restored'], 'communication_requirements': ['Notify database owner'], 'risk_level': 'low'}],\n"
        "    'trigger_conditions': [{'trigger_id': 'validation_failure', 'name': 'Validation Failure', 'condition': 'migration_validation_failures > 0', 'metric_threshold': {'metric': 'migration_validation_failures', 'operator': 'greater_than', 'value': 0, 'duration_minutes': 1}, 'evaluation_window_minutes': 1, 'auto_execute': False, 'escalation_contacts': ['database-platform']}],\n"
        "    'data_recovery_plan': {'recovery_method': 'backup_restore', 'backup_location': 'controlled-backup', 'recovery_scripts': ['restore-schema'], 'data_validation_queries': ['SELECT 1;'], 'estimated_recovery_time_minutes': 15, 'recovery_dependencies': ['database-platform']},\n"
        "    'communication_templates': [{'template_type': 'start', 'audience': 'technical', 'subject': 'Rollback started', 'body': 'Notify the database owner.', 'urgency': 'high', 'delivery_methods': ['incident-channel']}],\n"
        "    'escalation_matrix': {'high': {'trigger': 'rollback failure', 'contacts': ['database-platform']}},\n"
        "    'validation_checklist': ['Schema validation passes'],\n"
        "    'post_rollback_procedures': ['Monitor schema health'],\n"
        "    'emergency_contacts': [{'role': 'Database owner', 'name': 'database-platform'}],\n"
        "}\n"
        "output.write_text(json.dumps(runbook, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )


def _write_test_migration_review_inputs(
    target: Path,
    *,
    decision: str = "required",
    accepted_issue_id: str = "",
) -> None:
    root = target / "docs/backend/migrations"
    root.mkdir(parents=True, exist_ok=True)
    source_references = [
        "docs/product/08-acceptance-criteria.md",
        "docs/architecture/03-quality-attributes.md",
        "docs/backend/01-modules.md",
        "docs/backend/02-data-model.md",
    ]
    scope = {
        "schema_version": 1,
        "applicability": {
            "decision": decision,
            "owner": "database-platform",
            "reason": (
                "The goal data model must be deployed from an empty schema."
                if decision == "required"
                else "The project has no persistent data store or schema lifecycle."
            ),
            "source_references": source_references,
            "revisit_triggers": ["A persistent data store or schema lifecycle is introduced."],
        },
        "review": {
            "owner": "database-platform",
            "reason": "Schema ownership, compatibility, validation, and rollback evidence were reviewed.",
            "source_references": source_references,
        },
    }
    (root / "review-scope.json").write_text(
        json.dumps(scope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if decision != "required":
        return
    before = {
        "schema_version": "0.0",
        "database": "goal_store",
        "tables": {},
        "views": {},
        "procedures": [],
    }
    after = {
        "schema_version": "1.0",
        "database": "goal_store",
        "tables": {
            "goals": {
                "columns": {
                    "id": {"type": "varchar", "length": 64, "nullable": False, "primary_key": True},
                    "title": {"type": "varchar", "length": 255, "nullable": False},
                },
                "constraints": {"primary_key": ["id"], "unique": [], "foreign_key": [], "check": []},
                "indexes": [{"name": "idx_goals_title", "columns": ["title"]}],
            }
        },
        "views": {},
        "procedures": [],
    }
    migration_spec = {
        "type": "database",
        "pattern": "schema_change",
        "source": "Empty goal_store schema",
        "target": "goal_store schema version 1.0",
        "description": "Deploy the source-backed initial goal persistence schema.",
        "constraints": {
            "max_downtime_minutes": 30,
            "data_volume_gb": 0,
            "dependencies": ["goal-api"],
            "compliance_requirements": [],
            "special_requirements": ["referential_integrity"],
        },
        "tables_to_migrate": [{"name": "goals", "row_count": 0, "size_mb": 0, "critical": True}],
        "schema_changes": [{"table": "goals", "changes": [{"type": "create_table"}]}],
        "governance": {
            "owner": "database-platform",
            "strategy_rationale": "Use an explicit initial schema migration so deployment and rollback remain auditable.",
            "validation_plan": "Apply and roll back the schema in an isolated database before implementation release.",
            "source_references": source_references,
        },
    }
    decisions = []
    if accepted_issue_id:
        decisions.append(
            {
                "issue_id": accepted_issue_id,
                "owner": "database-platform",
                "reason": "The legacy reader is removed in the same controlled release.",
                "mitigation": "Use expand-contract deployment and verify no legacy readers before contraction.",
                "evidence": ["docs/backend/02-data-model.md"],
            }
        )
    acceptances = {"schema_version": 1, "decisions": decisions}
    for name, payload in (
        ("schema-before.json", before),
        ("schema-after.json", after),
        ("migration-spec.json", migration_spec),
        ("compatibility-acceptances.json", acceptances),
    ):
        (root / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _install_test_api_review_tools(
    target: Path,
    *,
    breaking: bool = False,
    lint_warnings: int = 0,
    scorecard_grade: str = "A",
    mutate_input: bool = False,
) -> None:
    skill_root = target / ".agents/skills/api-design-reviewer"
    reports = {
        "api_linter.py": {
            "summary": {
                "total_endpoints": 1,
                "endpoints_with_issues": 0,
                "total_issues": lint_warnings,
                "errors": 0,
                "warnings": lint_warnings,
                "info": 0,
                "score": 100.0,
            },
            "issues": [
                {
                    "severity": "warning",
                    "category": "test-only",
                    "message": "Deterministic warning fixture.",
                }
            ] if lint_warnings else [],
        },
        "breaking_change_detector.py": {
            "summary": {
                "total_changes": 1 if breaking else 0,
                "breaking_changes": 1 if breaking else 0,
                "potentially_breaking_changes": 0,
                "non_breaking_changes": 0,
                "enhancements": 0,
                "critical_severity": 1 if breaking else 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0,
                "info_severity": 0,
            },
            "hasBreakingChanges": breaking,
            "changes": [
                {
                    "type": "endpoint_removed",
                    "severity": "critical",
                    "path": "/goals",
                }
            ] if breaking else [],
        },
        "api_scorecard.py": {
            "overall": {
                "score": 95.0 if scorecard_grade == "A" else 75.0,
                "grade": scorecard_grade,
                "totalEndpoints": 1,
            },
            "api_info": {
                "title": "Goal API",
                "version": "1.0.0",
                "description": "Goal workflow API",
                "total_paths": 1,
                "openapi_version": "3.1.0",
            },
            "categories": {},
            "topRecommendations": [],
        },
    }
    for script_name, report in reports.items():
        script = skill_root / "scripts" / script_name
        script.parent.mkdir(parents=True, exist_ok=True)
        input_mutation = (
            "Path(sys.argv[1]).write_text('{\\\"openapi\\\": \\\"0.0.0\\\"}\\n', encoding='utf-8')\n"
            if mutate_input and script_name == "api_linter.py"
            else ""
        )
        script.write_text(
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            f"REPORT = {report!r}\n"
            f"{input_mutation}"
            "output_index = sys.argv.index('--output') + 1\n"
            "Path(sys.argv[output_index]).write_text(json.dumps(REPORT, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n"
            f"raise SystemExit({1 if script_name == 'breaking_change_detector.py' and breaking else 0})\n",
            encoding="utf-8",
        )


def _write_test_openapi(target: Path) -> None:
    path = target / "docs/api/openapi.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "info": {
                    "title": "Goal API",
                    "version": "1.0.0",
                    "description": "Source-backed goal workflow API.",
                    "contact": {"name": "Goal API owners"},
                },
                "servers": [{"url": "https://api.example.test"}],
                "paths": {
                    "/goals": {
                        "post": {
                            "operationId": "createGoal",
                            "summary": "Create a goal",
                            "description": "Creates one source-backed goal for the authenticated owner.",
                            "security": [{"bearerAuth": []}],
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/CreateGoal"}
                                    }
                                },
                            },
                            "responses": {
                                "201": {"description": "Goal created."},
                                "400": {"description": "Invalid request."},
                                "401": {"description": "Authentication required."},
                                "409": {"description": "Duplicate idempotency key."},
                                "500": {"description": "Unexpected failure."},
                            },
                        }
                    }
                },
                "components": {
                    "securitySchemes": {
                        "bearerAuth": {"type": "http", "scheme": "bearer"}
                    },
                    "schemas": {
                        "CreateGoal": {
                            "type": "object",
                            "required": ["title"],
                            "properties": {"title": {"type": "string", "minLength": 1}},
                        }
                    },
                },
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


def _record_all_test_design_reviews(case: unittest.TestCase, target: Path) -> None:
    reviews = (
        ("architecture", "ARCHITECTURE-AUTHOR-001", "approved", "senior-architect"),
        ("ui-interaction", "UI-INTERACTION-AUTHOR-001", "approved", "senior-frontend"),
        ("api-contracts", "API-AUTHOR-001", "approved", "api-design-reviewer"),
        ("backend-modules", "BACKEND-AUTHOR-001", "approved", "senior-backend"),
        ("data-model", "DATA-MODEL-AUTHOR-001", "approved", "database-designer"),
        ("frontend-modules", "FRONTEND-AUTHOR-001", "approved", "senior-frontend"),
        ("test-strategy", "TEST-AUTHOR-001", "approved", "senior-qa"),
        ("implementation-planning", "PLAN-AUTHOR-001", "approved", "senior-fullstack"),
        ("architecture-decisions", "ADR-AUTHOR-001", "not-applicable", "senior-architect"),
    )
    _install_test_authority_skills(
        target,
        tuple(
            dict.fromkeys(
                [
                    *(item[3] for item in reviews),
                    "senior-security",
                    "slo-architect",
                    "database-schema-designer",
                    "migration-architect",
                ]
            )
        ),
    )
    _write_test_threat_review_inputs(target)
    _run_governance_json(
        case,
        ["design", "threat-review", str(target), "--reviewed"],
    )
    _write_test_reliability_review_inputs(target)
    _run_governance_json(
        case,
        ["design", "reliability-review", str(target), "--reviewed"],
    )
    _run_governance_json(
        case,
        ["design", "api-review", str(target), "--reviewed"],
    )
    _write_test_migration_review_inputs(target)
    _run_governance_json(
        case,
        ["design", "migration-review", str(target), "--reviewed"],
    )
    for track, work_id, result, authority_skill in reviews:
        _run_governance_json(
            case,
            [
                "design",
                "review",
                str(target),
                "--track",
                track,
                "--work",
                work_id,
                "--result",
                result,
                "--reason",
                f"Test fixture review with {authority_skill} confirms all declared decisions are addressed.",
                "--reviewed",
            ],
        )


class GovernanceCliTest(unittest.TestCase):
    def test_workflow_resume_returns_one_snapshot_guarded_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Build a governed workspace.\n\n"
                "## Acceptance Criteria\n\n"
                "- The workflow exposes one resumable next action.\n",
                encoding="utf-8",
            )
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])

            payload = _run_governance_json(self, ["workflow", "resume", str(target)])

            self.assertTrue(payload["ok"])
            self.assertEqual(1, payload["schema_version"])
            self.assertEqual("workflow-resume", payload["workflow"])
            self.assertEqual("initialized", payload["phase"])
            self.assertEqual("action_ready", payload["status"])
            self.assertTrue(payload["can_continue"])
            self.assertFalse(payload["stop_before_action"])
            self.assertFalse(payload["stale"])
            self.assertEqual("advance-product-structuring", payload["selected_action"]["id"])
            self.assertEqual("guarded-sequence", payload["selected_action"]["kind"])
            self.assertTrue(payload["selected_action"]["writes_state"])
            self.assertEqual(
                ["advance-product-structuring-check", "advance-product-structuring"],
                [step["id"] for step in payload["selected_action"]["steps"]],
            )
            self.assertEqual(
                "run_preflight_then_apply_only_when_preflight_succeeds",
                payload["selected_action"]["execution_policy"],
            )
            self.assertRegex(payload["snapshot"]["id"], r"^[0-9a-f]{64}$")
            self.assertEqual("sha256-canonical-json-v1", payload["snapshot"]["algorithm"])
            self.assertRegex(payload["snapshot"]["state_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(payload["snapshot"]["inputs"])
            self.assertEqual(
                [
                    "bin/governance",
                    "workflow",
                    "resume",
                    ".",
                    "--expect-snapshot",
                    payload["snapshot"]["id"],
                    "--json",
                ],
                payload["assert_snapshot_command"]["argv"],
            )
            self.assertEqual(
                "execute_exactly_one_selected_action_then_refresh",
                payload["decision_policy"],
            )

            repeated = _run_governance_json(
                self,
                [
                    "workflow",
                    "resume",
                    str(target),
                    "--expect-snapshot",
                    payload["snapshot"]["id"],
                ],
            )
            self.assertTrue(repeated["ok"])
            self.assertFalse(repeated["stale"])
            self.assertEqual(payload["snapshot"]["id"], repeated["snapshot"]["id"])

            for step in payload["selected_action"]["steps"]:
                result = subprocess.run(
                    step["argv"],
                    cwd=step["cwd"],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, f"{result.stderr}\n{result.stdout}")
                self.assertTrue(json.loads(result.stdout)["ok"])

            advanced = _run_governance_json(self, ["workflow", "resume", str(target)])
            self.assertEqual("product-structuring", advanced["phase"])
            self.assertEqual("work_ready", advanced["status"])
            self.assertEqual("decide-product-chapter", advanced["selected_action"]["kind"])

    def test_workflow_resume_rejects_stale_snapshot_after_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goals\n\n- Govern changes.\n", encoding="utf-8")
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])
            initial = _run_governance_json(self, ["workflow", "resume", str(target)])

            prd = target / "docs/product/core/PRD.md"
            prd.write_text(prd.read_text(encoding="utf-8") + "\nChanged after routing.\n", encoding="utf-8")
            stale = _run_governance_json(
                self,
                [
                    "workflow",
                    "resume",
                    str(target),
                    "--expect-snapshot",
                    initial["snapshot"]["id"],
                ],
                expected_returncode=1,
            )

            self.assertFalse(stale["ok"])
            self.assertTrue(stale["stale"])
            self.assertEqual("stale", stale["status"])
            self.assertFalse(stale["can_continue"])
            self.assertTrue(stale["stop_before_action"])
            self.assertEqual({}, stale["selected_action"])
            self.assertEqual(initial["snapshot"]["id"], stale["expected_snapshot"])
            self.assertNotEqual(initial["snapshot"]["id"], stale["snapshot"]["id"])
            self.assertIn("workflow_snapshot_changed", stale["stop_reasons"])

    def test_workflow_resume_rejects_malformed_expected_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])

            payload = _run_governance_json(
                self,
                ["workflow", "resume", str(target), "--expect-snapshot", "not-a-sha256"],
                expected_returncode=1,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual("failed", payload["status"])
            self.assertFalse(payload["stale"])
            self.assertEqual({}, payload["selected_action"])
            self.assertIn("expected_snapshot_invalid", payload["stop_reasons"])

    def test_workflow_resume_routes_one_startable_work_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Build governed output.\n\n"
                "## Acceptance Criteria\n\n"
                "- Product evidence is traceable.\n",
                encoding="utf-8",
            )
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])
            _run_governance_json(self, ["advance", "product-structuring", str(target)])

            payload = _run_governance_json(self, ["workflow", "resume", str(target)])

            self.assertTrue(payload["ok"])
            self.assertEqual("work_ready", payload["status"])
            self.assertTrue(payload["can_continue"])
            self.assertEqual("PRODUCT-AUTHOR-001", payload["work_package"]["work_package"]["work_id"])
            self.assertEqual("decide-product-chapter", payload["selected_action"]["kind"])
            self.assertEqual(1, payload["action_count"])
            self.assertIn("docs/product/core/PRD.md", payload["snapshot"]["input_paths"])
            self.assertEqual(
                ["refresh_after_action", "reject_stale_snapshot", "never_guess_missing_decisions"],
                payload["invariants"],
            )

    def test_workflow_resume_reports_snapshot_build_failure_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])
            module = importlib.import_module("scripts.workflow_resume")

            with mock.patch.object(module, "_build_snapshot", side_effect=OSError("snapshot unreadable")):
                payload = module.build_workflow_resume(target)

            self.assertFalse(payload["ok"])
            self.assertEqual("failed", payload["status"])
            self.assertEqual(["workflow_resume_build_failed"], payload["stop_reasons"])
            self.assertEqual(["snapshot unreadable"], payload["errors"])

    def test_workflow_resume_blocks_malformed_preflight_apply_pair(self) -> None:
        module = importlib.import_module("scripts.workflow_resume")
        preflight = {
            "id": "advance-product-structuring-check",
            "kind": "preflight",
            "preflight_for": "advance-product-structuring",
            "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
            "cwd": "/tmp/target",
            "writes_state": False,
            "approval_required": False,
        }

        route = module._route(
            {"ok": True, "errors": []},
            {
                "ok": True,
                "package_available": False,
                "status": "phase_action_required",
                "next_action": preflight,
                "next_actions": [preflight],
                "errors": [],
            },
        )

        self.assertEqual("blocked", route["status"])
        self.assertFalse(route["can_continue"])
        self.assertTrue(route["stop_before_action"])
        self.assertEqual(["continuation_preflight_apply_pair_invalid"], route["stop_reasons"])
        self.assertFalse(route["selected_action"]["valid"])

    def test_project_environment_plan_and_register_cli_are_previewable_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _design_scaffold_target(self, tmp)
            evidence = target / "docs/decisions/001-stack.md"
            evidence.write_text("# Stack Decision\n\nReviewed Node.js runtime selection.\n", encoding="utf-8")
            command = [
                sys.executable,
                str(CLI),
                "project-env",
                "register",
                str(target),
                "--tool-id",
                "node-runtime",
                "--executable",
                "node",
                "--version-probe",
                "double-dash-version",
                "--probe-output",
                "stdout",
                "--version-prefix",
                "v",
                "--minimum-version",
                "20.0.0",
                "--maximum-exclusive-version",
                "26.0.0",
                "--repair-source-type",
                "official-url",
                "--repair-source",
                "https://nodejs.org/en/download",
                "--review-evidence",
                "docs/decisions/001-stack.md",
                "--repair-instructions",
                "Install the reviewed Node.js runtime from the official source.",
                "--reviewed",
                "--check",
                "--json",
            ]
            plan = subprocess.run(
                [sys.executable, str(CLI), "project-env", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            preview = subprocess.run(command, text=True, capture_output=True, check=False)
            self.assertEqual(0, plan.returncode, plan.stderr)
            self.assertEqual(0, preview.returncode, preview.stderr)
            self.assertEqual("registration_required", json.loads(plan.stdout)["status"])
            self.assertEqual(
                ["docs/agent-workflow/project-environment.json"],
                json.loads(preview.stdout)["would_update"],
            )
            self.assertEqual([], json.loads(preview.stdout)["updated"])
            self.assertEqual([], json.loads((target / "docs/agent-workflow/project-environment.json").read_text())["environments"][1]["tools"])

            applied = subprocess.run(
                command[:-2] + ["--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, applied.returncode, f"{applied.stderr}\n{applied.stdout}")
            applied_payload = json.loads(applied.stdout)
            self.assertTrue(applied_payload["applied"])
            self.assertEqual(
                ["docs/agent-workflow/project-environment.json"],
                applied_payload["updated"],
            )
            registered_plan = subprocess.run(
                [sys.executable, str(CLI), "project-env", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, registered_plan.returncode, registered_plan.stderr)
            registered_payload = json.loads(registered_plan.stdout)
            self.assertEqual("registered_tools_present", registered_payload["status"])
            self.assertEqual(1, registered_payload["tool_count"])
            self.assertEqual("node-runtime", registered_payload["repair_routes"][0]["tool_id"])
            self.assertEqual(
                [
                    "bin/governance",
                    "project-env",
                    "repair",
                    ".",
                    "--tool-id",
                    "node-runtime",
                    "--check",
                    "--json",
                ],
                registered_payload["repair_routes"][0]["preflight_command"]["argv"],
            )

            conflict_command = command[:-2]
            prefix_index = conflict_command.index("--version-prefix")
            conflict_command[prefix_index + 1] = "Node "
            conflict = subprocess.run(
                conflict_command + ["--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, conflict.returncode)
            self.assertIn("--replace", json.loads(conflict.stdout)["errors"][0])

    def test_project_environment_reviewed_repair_cli_requires_approval_and_rechecks_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _design_scaffold_target(self, tmp)
            evidence = target / "docs/decisions/001-stack.md"
            evidence.write_text("# Stack Decision\n\nReviewed demo runtime repair command.\n", encoding="utf-8")
            installer = target / "tools/install-demo-runtime"
            installer.parent.mkdir()
            installer.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                "mkdir -p tools-bin\n"
                "printf '%s\\n' '#!/bin/sh' 'printf \"Demo 2.1.0\\n\"' > tools-bin/demo-runtime\n"
                "chmod +x tools-bin/demo-runtime\n",
                encoding="utf-8",
            )
            installer.chmod(0o755)
            env = _agent_env()
            env["PATH"] = os.pathsep.join([str(target / "tools-bin"), env.get("PATH", "")])
            register = [
                sys.executable,
                str(CLI),
                "project-env",
                "register",
                str(target),
                "--tool-id",
                "demo-runtime",
                "--executable",
                "demo-runtime",
                "--version-prefix",
                "Demo ",
                "--minimum-version",
                "2.0.0",
                "--maximum-exclusive-version",
                "3.0.0",
                "--repair-strategy",
                "reviewed-command",
                "--repair-source-type",
                "official-url",
                "--repair-source",
                "https://example.com/demo-runtime",
                "--review-evidence",
                "docs/decisions/001-stack.md",
                "--repair-instructions",
                "Run the reviewed repository installer.",
                "--repair-command-cwd",
                ".",
                "--repair-command-arg",
                "tools/install-demo-runtime",
                "--reviewed",
                "--json",
            ]
            registered = subprocess.run(register, env=env, text=True, capture_output=True, check=False)
            self.assertEqual(0, registered.returncode, registered.stderr)

            preview = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "project-env",
                    "repair",
                    str(target),
                    "--tool-id",
                    "demo-runtime",
                    "--check",
                    "--json",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            blocked = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "project-env",
                    "repair",
                    str(target),
                    "--tool-id",
                    "demo-runtime",
                    "--json",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, preview.returncode, preview.stderr)
            self.assertEqual(1, blocked.returncode)
            preview_payload = json.loads(preview.stdout)
            self.assertEqual("approval-required", preview_payload["action"])
            self.assertTrue(preview_payload["apply_command"]["approval_required"])
            self.assertFalse((target / "tools-bin/demo-runtime").exists())

            applied = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "project-env",
                    "repair",
                    str(target),
                    "--tool-id",
                    "demo-runtime",
                    "--approved",
                    "--json",
                ],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, applied.returncode, f"{applied.stderr}\n{applied.stdout}")
            applied_payload = json.loads(applied.stdout)
            self.assertTrue(applied_payload["ok"])
            self.assertEqual("repaired", applied_payload["action"])
            self.assertTrue(applied_payload["environment_ready"])
            self.assertEqual("pass", applied_payload["execution"]["result"])
            self.assertTrue(
                (target / ".governance/project-environment-repairs.json").is_file()
            )

    def test_env_json_uses_shared_payload_builder(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        governance_cli = importlib.import_module("governance_cli")
        check_env = importlib.import_module("check_env")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            statuses = [
                check_env.ToolStatus(
                    name="python3",
                    present=True,
                    version="Python 3",
                    note="Required",
                    level="required",
                    install_package="python3",
                )
            ]
            system = check_env.SystemStatus(
                platform="linux",
                os_id="ubuntu",
                os_like="debian",
                pretty_name="Ubuntu",
                is_root=False,
            )
            package_manager = check_env.PackageManager("none", None, False)
            git = check_env.GitStatus(False, False, "", "", "")
            calls: list[dict[str, object]] = []
            original_collect_status = governance_cli.collect_status
            original_collect_system_status = governance_cli.collect_system_status
            original_detect_package_manager = governance_cli.detect_package_manager
            original_collect_git_status = governance_cli.collect_git_status
            original_build_install_plan = governance_cli.build_install_plan
            original_build_env_payload = governance_cli.build_env_payload

            def fake_payload(target_arg: Path, **kwargs: object) -> dict[str, object]:
                calls.append(kwargs)
                return {
                    "ok": True,
                    "target": str(target_arg),
                    "check": kwargs["check"],
                    "from_shared_payload": True,
                }

            governance_cli.collect_status = lambda: statuses
            governance_cli.collect_system_status = lambda: system
            governance_cli.detect_package_manager = lambda _system=None: package_manager
            governance_cli.collect_git_status = lambda _target: git
            governance_cli.build_install_plan = lambda _statuses, _strict, _package_manager: []
            governance_cli.build_env_payload = fake_payload
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    returncode = governance_cli._cmd_env(
                        SimpleNamespace(target=str(target), repair=False, json=True, strict=False)
                    )
            finally:
                governance_cli.collect_status = original_collect_status
                governance_cli.collect_system_status = original_collect_system_status
                governance_cli.detect_package_manager = original_detect_package_manager
                governance_cli.collect_git_status = original_collect_git_status
                governance_cli.build_install_plan = original_build_install_plan
                governance_cli.build_env_payload = original_build_env_payload

            payload = json.loads(stdout.getvalue())
            self.assertEqual(0, returncode)
            self.assertTrue(payload["from_shared_payload"])
            self.assertEqual([statuses], [call["statuses"] for call in calls])
            self.assertEqual([False], [call["check"] for call in calls])

    def test_env_repair_check_text_reports_manual_repairs(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        governance_cli = importlib.import_module("governance_cli")
        check_env = importlib.import_module("check_env")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            statuses = [
                check_env.ToolStatus(
                    name="node",
                    present=False,
                    version="",
                    note="Recommended for frontend projects.",
                    level="recommended",
                    install_package=None,
                )
            ]
            system = check_env.SystemStatus("linux", "ubuntu", "debian", "Ubuntu", False)
            package_manager = check_env.PackageManager("apt", "/usr/bin/apt-get", True)
            git = check_env.GitStatus(False, False, "", "", "")
            original_collect_status = governance_cli.collect_status
            original_collect_system_status = governance_cli.collect_system_status
            original_detect_package_manager = governance_cli.detect_package_manager
            original_collect_git_status = governance_cli.collect_git_status

            governance_cli.collect_status = lambda: statuses
            governance_cli.collect_system_status = lambda: system
            governance_cli.detect_package_manager = lambda _system=None: package_manager
            governance_cli.collect_git_status = lambda _target: git
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    returncode = governance_cli._cmd_env(
                        SimpleNamespace(target=str(target), repair=True, json=False, strict=True, check=True)
                    )
            finally:
                governance_cli.collect_status = original_collect_status
                governance_cli.collect_system_status = original_collect_system_status
                governance_cli.detect_package_manager = original_detect_package_manager
                governance_cli.collect_git_status = original_collect_git_status

            output = stdout.getvalue()
            self.assertEqual(1, returncode)
            self.assertIn("Manual repairs required:", output)
            self.assertIn("- `node` (recommended): no supported package mapping. Recommended for frontend projects.", output)
            self.assertFalse((target / ".governance/env-repair.md").exists())

    def test_env_payload_reports_approval_required_repair_execution(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        check_env = importlib.import_module("check_env")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            statuses = [
                check_env.ToolStatus(
                    name="git",
                    present=False,
                    version="",
                    note="Required for version control.",
                    level="required",
                    install_package="git",
                )
            ]
            system = check_env.SystemStatus("linux", "ubuntu", "debian", "Ubuntu", False)
            package_manager = check_env.PackageManager("apt", "/usr/bin/apt-get", True)
            install_plan = check_env.build_install_plan(statuses, False, package_manager)

            payload = check_env._env_payload(
                target,
                strict=False,
                check=True,
                statuses=statuses,
                system=system,
                package_manager=package_manager,
                git=check_env.GitStatus(False, False, "", "", ""),
                install_plan=install_plan,
                needs_escalation=True,
                install_results=[],
                repairs=[],
                repair_plan=None,
                would_repair=check_env.planned_repair_actions(target),
            )

            self.assertFalse(payload["ok"])
            execution = payload["repair_execution"]
            self.assertEqual("approval_required", execution["status"])
            self.assertFalse(execution["can_continue"])
            self.assertFalse(execution["can_auto_apply"])
            self.assertTrue(execution["approval_required"])
            self.assertFalse(execution["manual_repair_required"])
            self.assertEqual(["env-repair-apt-update", "env-repair-apt-install"], execution["command_ids"])

    def test_env_payload_reports_manual_repair_execution_blocker(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        check_env = importlib.import_module("check_env")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            statuses = [
                check_env.ToolStatus(
                    name="node",
                    present=False,
                    version="",
                    note="Recommended for frontend projects.",
                    level="recommended",
                    install_package=None,
                )
            ]
            system = check_env.SystemStatus("linux", "ubuntu", "debian", "Ubuntu", False)
            package_manager = check_env.PackageManager("apt", "/usr/bin/apt-get", True)

            payload = check_env._env_payload(
                target,
                strict=True,
                check=True,
                statuses=statuses,
                system=system,
                package_manager=package_manager,
                git=check_env.GitStatus(False, False, "", "", ""),
                install_plan=[],
                needs_escalation=False,
                install_results=[],
                repairs=[],
                repair_plan=None,
                would_repair=check_env.planned_repair_actions(target),
            )

            self.assertFalse(payload["ok"])
            execution = payload["repair_execution"]
            self.assertEqual("manual_repair_required", execution["status"])
            self.assertFalse(execution["can_continue"])
            self.assertFalse(execution["can_auto_apply"])
            self.assertFalse(execution["approval_required"])
            self.assertTrue(execution["manual_repair_required"])
            self.assertEqual(["node"], execution["manual_tools"])

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
            self.assertIn("repair_execution", payload)
            self.assertIn("next_step", payload["repair_execution"])
            self.assertIn("missing_required", payload)
            self.assertIn("missing_recommended", payload)
            self.assertIn("repairs", payload)
            self.assertEqual([], payload["errors"])
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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
            self.assertIn("repair_execution", payload)
            self.assertIn("can_auto_apply", payload["repair_execution"])
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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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

    def test_init_json_auto_discovers_single_product_doc_in_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            product = target / "product.md"
            product.write_text("# Auto Product\n\nInitialize from the only product document.\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual("auto-discovered", payload["product"]["selection"])
            self.assertEqual(str(product.resolve()), payload["product"]["path"])
            self.assertEqual([str(product.resolve())], payload["product"]["candidates"])
            self.assertIn("Auto Product", (target / "docs/product/core/PRD.md").read_text(encoding="utf-8"))
            manifest = json.loads((target / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("product.md", manifest["source"]["filename"])
            self.assertEqual(str(product.resolve()), payload["state"]["product_source"])

    def test_init_check_json_rejects_multiple_auto_discovery_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            product = target / "product.md"
            requirements = target / "requirements.md"
            product.write_text("# Product\n", encoding="utf-8")
            requirements.write_text("# Requirements\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual("ambiguous", payload["product"]["selection"])
            self.assertEqual([str(product.resolve()), str(requirements.resolve())], payload["product"]["candidates"])
            self.assertIn(
                {
                    "path": str(target.resolve()),
                    "reason": "multiple product document candidates found; pass --product",
                },
                payload["conflicts"],
            )
            self.assertFalse((target / "README.md").exists())

            explicit = subprocess.run(
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

            self.assertEqual(0, explicit.returncode, explicit.stderr)
            explicit_payload = json.loads(explicit.stdout)
            self.assertTrue(explicit_payload["ok"])
            self.assertEqual("explicit", explicit_payload["product"]["selection"])
            self.assertEqual(str(product), explicit_payload["product"]["path"])

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
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                payload["local_commands"],
            )
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
            self.assertIn("scripts/workflow_resume.py", payload["refreshed"])
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
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                payload["next_actions"],
            )
            runtime_local_commands = {command["make_target"]: command for command in payload["local_commands"]}
            for make_target in ("verify-check", "workflow-plan", "work-package", "workflow-resume"):
                command = runtime_local_commands[make_target]
                self.assertFalse(command["writes_state"])
                self.assertFalse(command["approval_required"])
                command_result = subprocess.run(
                    command["argv"],
                    cwd=command["cwd"],
                    env=_agent_env(),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, command_result.returncode, command_result.stderr)
                command_payload = json.loads(command_result.stdout)
                self.assertTrue(command_payload["ok"])
                if make_target == "verify-check":
                    self.assertTrue(command_payload["check"])
                    self.assertEqual([], command_payload["findings"])
                if make_target == "workflow-plan":
                    self.assertEqual("initialized", command_payload["phase"])
                    self.assertEqual("advance-product-structuring-check", command_payload["next_actions"][0]["id"])
                if make_target == "work-package":
                    self.assertEqual("workflow-work-package", command_payload["workflow"])
                    self.assertEqual("initialized", command_payload["phase"])
                    self.assertFalse(command_payload["package_available"])
                    self.assertEqual("phase_action_required", command_payload["status"])
                    self.assertEqual("advance-product-structuring-check", command_payload["next_action"]["id"])
                if make_target == "workflow-resume":
                    self.assertEqual("workflow-resume", command_payload["workflow"])
                    self.assertEqual("initialized", command_payload["phase"])
                    self.assertEqual("action_ready", command_payload["status"])
                    self.assertEqual("advance-product-structuring", command_payload["selected_action"]["id"])
                    self.assertEqual("guarded-sequence", command_payload["selected_action"]["kind"])

            self.assertTrue((target / "scripts/authority_skills.py").is_file())

            runtime_preflight = next(
                action for action in payload["next_actions"] if action["id"] == "advance-product-structuring-check"
            )
            preflight_result = subprocess.run(
                runtime_preflight["argv"],
                cwd=runtime_preflight["cwd"],
                env=_agent_env(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, preflight_result.returncode, preflight_result.stderr)
            preflight_payload = json.loads(preflight_result.stdout)
            self.assertTrue(preflight_payload["ok"])
            self.assertTrue(preflight_payload["check"])
            self.assertTrue(preflight_payload["would_advance"])
            self.assertFalse(preflight_payload["advanced"])
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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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

    def test_verify_uses_one_timestamp_for_state_update_when_clock_moves_backward(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        governance_cli = importlib.import_module("governance_cli")
        state_module = importlib.import_module("state")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            governance_cli.bootstrap(target, product, profile="service", project_name="Clock Test")

            checked_at = "2099-07-14T06:36:25+00:00"
            earlier_cli_time = "2099-07-14T06:36:24+00:00"
            earlier_state_time = "2099-07-14T06:36:23+00:00"
            state_path = target / ".governance/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["updated_at"] = checked_at
            state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            original_cli_utc_now = governance_cli.utc_now
            original_state_utc_now = state_module.utc_now
            governance_cli.utc_now = lambda: earlier_cli_time
            state_module.utc_now = lambda: earlier_state_time
            stdout = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout):
                    returncode = governance_cli._cmd_verify(
                        SimpleNamespace(target=str(target), check=False, json=True)
                    )
            finally:
                governance_cli.utc_now = original_cli_utc_now
                state_module.utc_now = original_state_utc_now

            self.assertEqual(0, returncode)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["state_updated"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(checked_at, state["last_verification"]["checked_at"])
            self.assertEqual(checked_at, state["updated_at"])

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
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                init_payload["next_actions"],
            )

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
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                verify_payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                verify_payload["next_actions"],
            )

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
            self.assertIn(
                {
                    "make_target": "verify-governance",
                    "cwd": str(target.resolve()),
                    "command": "make verify-governance",
                    "argv": ["make", "verify-governance"],
                    "recipe": "bin/governance verify .",
                    "writes_state": True,
                    "approval_required": False,
                    "description": "run governance verification and update verification state",
                },
                status_payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                status_payload["next_actions"],
            )

    def test_initialized_target_local_governance_wrapper_verifies_and_reports_status(self) -> None:
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
                    "Target Local Demo",
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
                ["bin/governance", "verify", ".", "--check", "--json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            verify_payload = json.loads(verify_result.stdout)
            self.assertTrue(verify_payload["ok"])
            self.assertTrue(verify_payload["check"])
            self.assertFalse(verify_payload["state_updated"])
            self.assertEqual([], verify_payload["errors"])
            self.assertEqual(".", verify_payload["target"])
            self.assertEqual("initialized", verify_payload["state"]["phase"])
            self.assertIn(
                {
                    "make_target": "governance-status",
                    "cwd": str(target.resolve()),
                    "command": "make governance-status",
                    "argv": ["make", "governance-status"],
                    "recipe": "bin/governance status . --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "print workflow state as JSON",
                },
                verify_payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                verify_payload["next_actions"],
            )
            self.assertEqual(state_before, state_path.read_text(encoding="utf-8"))

            status_result = subprocess.run(
                ["bin/governance", "status", ".", "--json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_result.returncode, status_result.stderr)
            status_payload = json.loads(status_result.stdout)
            self.assertTrue(status_payload["ok"])
            self.assertEqual(".", status_payload["target"])
            self.assertEqual("service", status_payload["state"]["profile"])
            self.assertEqual("Target Local Demo", status_payload["state"]["project_name"])
            self.assertEqual(
                "docs/agent-workflow/workflow-pack/manifest.json",
                status_payload["state"]["workflow_pack_manifest"],
            )
            self.assertIn(
                {
                    "make_target": "governance-status",
                    "cwd": str(target.resolve()),
                    "command": "make governance-status",
                    "argv": ["make", "governance-status"],
                    "recipe": "bin/governance status . --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "print workflow state as JSON",
                },
                status_payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring",
                    "kind": "apply",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--json"],
                    "writes_state": True,
                    "approval_required": False,
                    "requires": "advance-product-structuring-check ok:true",
                    "sequence": 2,
                    "requires_action": "advance-product-structuring-check",
                    "success_condition": "ok:true",
                    "description": "record advance from initialization into product structuring",
                },
                status_payload["next_actions"],
            )

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
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                payload["next_actions"],
            )
            self.assertNotIn("last_verification", payload["state"])
            self.assertEqual(state_before, state_path.read_text(encoding="utf-8"))

    def test_verify_check_json_reports_state_read_failure_without_update_wording(self) -> None:
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
            state_path.write_text("{not json\n", encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--check", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            self.assertEqual("", verify_result.stderr)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertFalse(payload["state_updated"])
            self.assertIn("failed to read verification state", payload["errors"][-1])
            self.assertNotIn("failed to update verification state", payload["errors"][-1])
            self.assertEqual(str(state_path), payload["path"])
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
            self.assertEqual("{not json\n", state_path.read_text(encoding="utf-8"))

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

    def test_target_local_workflow_plan_reports_product_authoring_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n\n"
                "## Acceptance Criteria\n\n"
                "- The initialized repository exposes local governance checks.\n",
                encoding="utf-8",
            )
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            advance_result = subprocess.run(
                ["bin/governance", "advance", "product-structuring", ".", "--json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_result.returncode, advance_result.stderr)

            result = subprocess.run(
                ["bin/governance", "workflow", "plan", ".", "--json"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["blocked"])
            self.assertEqual("workflow-plan", payload["workflow"])
            self.assertEqual("product-structuring", payload["phase"])
            commands = {command["id"]: command for command in payload["commands"]}
            self.assertEqual(
                ["bin/governance", "product", "plan", ".", "--json"],
                commands["product-plan"]["argv"],
            )
            self.assertFalse(commands["product-plan"]["writes_state"])
            local_commands = {command["make_target"]: command for command in payload["local_commands"]}
            self.assertIn("workflow-plan", local_commands)
            self.assertEqual(["make", "workflow-plan"], local_commands["workflow-plan"]["argv"])
            self.assertEqual("advance-design-derivation-check", payload["next_actions"][0]["id"])
            queues = {queue["id"]: queue for queue in payload["queues"]}
            self.assertEqual(["product-plan"], list(queues))
            product_queue = queues["product-plan"]
            self.assertTrue(product_queue["ok"])
            self.assertEqual("blocked", product_queue["status"])
            self.assertEqual("product-structuring", product_queue["phase"])
            self.assertEqual(2, product_queue["summary"]["suggested_mapping_count"])
            self.assertEqual(4, product_queue["summary"]["required_decision_count"])
            self.assertEqual(4, product_queue["summary"]["manual_authoring_summary"]["task_count"])
            self.assertEqual(
                [
                    "structuring-product-requirements",
                    "archiving-product-document",
                    "verifying-governance-docs",
                ],
                product_queue["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertEqual([], product_queue["summary"]["skill_summary"]["authority_routing_skills"])
            self.assertEqual(
                ["structuring-product-requirements", "archiving-product-document", "verifying-governance-docs"],
                [step["name"] for step in product_queue["summary"]["skill_loading_plan"]["steps"]],
            )
            self.assertIn(
                "structuring-product-requirements",
                payload["skill_summary"]["local_workflow_skills"],
            )
            self.assertGreater(
                product_queue["summary"]["manual_authoring_summary"]["non_satisfied_required_evidence_count"],
                0,
            )
            self.assertEqual("product-plan", payload["active_work"]["queue_id"])
            self.assertEqual("PRODUCT-AUTHOR-001", payload["active_work"]["task_id"])
            self.assertEqual("background-and-problems", payload["active_work"]["chapter"])
            self.assertEqual("decision_required", payload["active_work"]["status"])
            self.assertGreater(payload["active_work"]["blocker_count"], 0)
            self.assertEqual("chapter_in_scope", payload["active_work"]["next_open_decision"])
            self.assertEqual(
                ["bin/governance", "product", "plan", ".", "--json"],
                payload["active_work"]["inspect_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "verify", ".", "--check", "--json"],
                product_queue["summary"]["active_work"]["verify_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "product", "plan", ".", "--json"],
                product_queue["summary"]["active_work"]["refresh_command"]["argv"],
            )

            work_package_result = subprocess.run(
                ["bin/governance", "workflow", "work-package", ".", "--json"],
                cwd=target,
                env=_agent_env(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, work_package_result.returncode, work_package_result.stderr)
            work_package_payload = json.loads(work_package_result.stdout)
            self.assertTrue(work_package_payload["ok"])
            self.assertTrue(work_package_payload["package_available"])
            self.assertEqual("product-structuring", work_package_payload["phase"])
            self.assertEqual("decision_required", work_package_payload["status"])
            self.assertTrue(work_package_payload["can_start"])
            package = work_package_payload["work_package"]
            self.assertEqual("product-authoring", package["kind"])
            self.assertEqual("product-plan", package["queue_id"])
            self.assertEqual("PRODUCT-AUTHOR-001", package["work_id"])
            self.assertEqual("do_not_guess_product_meaning", package["decision_policy"])
            self.assertEqual(
                ["docs/product/01-background-and-problems.md"],
                package["write_scope"]["primary_paths"],
            )
            self.assertIn("docs/product/core/PRD.md", package["read_order"])
            self.assertIn(
                "docs/agent-workflow/workflow-pack/references/product-requirements-checklist.md",
                package["read_order"],
            )
            self.assertTrue(all((target / path).is_file() for path in package["read_order"]))
            self.assertEqual([], work_package_payload["skill_readiness"]["missing_authority_routing_skills"])
            local_requirements = [
                requirement
                for requirement in work_package_payload["skill_readiness"]["resolved_requirements"]
                if requirement["type"] == "local-workflow"
            ]
            self.assertTrue(local_requirements)
            self.assertTrue(
                all(
                    requirement["resolved_path"].startswith(
                        "docs/agent-workflow/workflow-pack/skills/"
                    )
                    and (target / requirement["resolved_path"]).is_file()
                    for requirement in local_requirements
                )
            )
            self.assertEqual("decide-product-chapter", work_package_payload["next_action"]["kind"])
            self.assertEqual("background-and-problems", work_package_payload["next_action"]["chapter"])
            self.assertEqual(
                ["author-required", "omit-unsupported"],
                work_package_payload["next_action"]["options"],
            )
            self.assertEqual(
                [
                    "bin/governance",
                    "product",
                    "disposition",
                    ".",
                    "--chapter",
                    "background-and-problems",
                ],
                work_package_payload["next_action"]["command_contract"]["argv_prefix"],
            )

            missing_skill = target / local_requirements[0]["resolved_path"]
            missing_skill.unlink()
            missing_skill_result = subprocess.run(
                ["bin/governance", "workflow", "work-package", ".", "--json"],
                cwd=target,
                env=_agent_env(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, missing_skill_result.returncode, missing_skill_result.stderr)
            missing_skill_payload = json.loads(missing_skill_result.stdout)
            self.assertFalse(missing_skill_payload["can_start"])
            self.assertTrue(missing_skill_payload["stop_before_work"])
            self.assertIn(
                local_requirements[0]["name"],
                missing_skill_payload["skill_readiness"]["missing_local_workflow_skills"],
            )
            self.assertEqual("repair-workflow-pack", missing_skill_payload["next_action"]["kind"])

    def test_workflow_plan_reports_design_authoring_summaries(self) -> None:
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
            (target / "docs/product/08-acceptance-criteria.md").write_text(_acceptance_doc(), encoding="utf-8")
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold_design = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_design.returncode, scaffold_design.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "workflow", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["blocked"])
            self.assertEqual("workflow-plan", payload["workflow"])
            self.assertEqual("design-derivation", payload["phase"])
            queues = {queue["id"]: queue for queue in payload["queues"]}
            self.assertEqual(
                [
                    "design-plan",
                    "architecture-authoring",
                    "api-candidates",
                    "api-authoring",
                    "backend-authoring",
                    "data-model-authoring",
                    "ui-interaction-authoring",
                    "frontend-authoring",
                    "test-strategy-authoring",
                    "implementation-planning-authoring",
                    "architecture-decisions-authoring",
                    "project-runtime",
                ],
                list(queues),
            )
            self.assertEqual(9, queues["design-plan"]["summary"]["track_count"])
            self.assertGreater(queues["design-plan"]["summary"]["blocker_count"], 0)
            self.assertEqual(1, queues["architecture-authoring"]["summary"]["authoring_summary"]["task_count"])
            self.assertIn(
                "designing-system-architecture",
                queues["architecture-authoring"]["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertIn(
                "senior-architect",
                queues["architecture-authoring"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn(
                "designing-system-architecture",
                queues["design-plan"]["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertIn(
                "senior-architect",
                queues["design-plan"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn(
                "api-design-reviewer",
                queues["design-plan"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn(
                "senior-architect",
                [step["name"] for step in queues["design-plan"]["summary"]["skill_loading_plan"]["steps"]],
            )
            self.assertEqual(1, queues["api-candidates"]["summary"]["candidate_count"])
            self.assertEqual(1, queues["api-authoring"]["summary"]["authoring_summary"]["task_count"])
            self.assertIn(
                "api-design-reviewer",
                queues["api-authoring"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                queues["api-authoring"]["summary"]["skill_loading_plan"]["steps"][1]["missing_policy"],
            )
            self.assertGreater(
                queues["backend-authoring"]["summary"]["authoring_summary"]["non_satisfied_required_link_count"],
                0,
            )
            self.assertIn(
                "designing-backend-modules",
                queues["backend-authoring"]["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertIn(
                "designing-data-models",
                queues["data-model-authoring"]["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertIn(
                "designing-ui-interactions",
                queues["ui-interaction-authoring"]["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertIn(
                "senior-backend",
                queues["backend-authoring"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn(
                "database-schema-designer",
                queues["data-model-authoring"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn(
                "migration-architect",
                queues["data-model-authoring"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn(
                "a11y-audit",
                queues["ui-interaction-authoring"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertIn("senior-architect", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("api-design-reviewer", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("senior-backend", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("database-schema-designer", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("senior-security", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("tech-stack-evaluator", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("senior-architect", [step["name"] for step in payload["skill_loading_plan"]["steps"]])
            self.assertIn("database-schema-designer", [step["name"] for step in payload["skill_loading_plan"]["steps"]])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                payload["skill_summary"]["authority_missing_policy"],
            )
            self.assertEqual("design-plan", payload["active_work"]["queue_id"])
            self.assertEqual("architecture", payload["active_work"]["track_id"])
            self.assertEqual("authoring_blocked", payload["active_work"]["status"])
            self.assertGreater(payload["active_work"]["blocker_count"], 0)
            self.assertEqual(
                ["bin/governance", "design", "plan", ".", "--json"],
                payload["active_work"]["inspect_command"]["argv"],
            )
            self.assertEqual("architecture", queues["design-plan"]["summary"]["active_work"]["track_id"])
            self.assertEqual(
                "ARCHITECTURE-AUTHOR-001",
                queues["architecture-authoring"]["summary"]["active_work"]["task_id"],
            )
            self.assertEqual("API-AUTHOR-001", queues["api-authoring"]["summary"]["active_work"]["task_id"])
            self.assertEqual(
                "error_registry",
                queues["api-authoring"]["summary"]["active_work"]["next_required_link"]["kind"],
            )
            self.assertEqual(
                ["bin/governance", "design", "api-authoring", ".", "--json"],
                queues["api-authoring"]["summary"]["active_work"]["refresh_command"]["argv"],
            )
            self.assertEqual(
                "api-design-reviewer",
                queues["api-candidates"]["summary"]["active_work"]["primary_specialist_skill"],
            )
            commands = {command["id"]: command for command in payload["commands"]}
            self.assertEqual(
                ["bin/governance", "design", "architecture-authoring", ".", "--json"],
                commands["architecture-authoring"]["argv"],
            )
            self.assertFalse(commands["architecture-authoring"]["writes_state"])
            self.assertEqual(
                ["bin/governance", "design", "backend-authoring", ".", "--json"],
                commands["backend-authoring"]["argv"],
            )
            self.assertFalse(commands["backend-authoring"]["writes_state"])
            self.assertEqual(
                ["bin/governance", "design", "data-model-authoring", ".", "--json"],
                commands["data-model-authoring"]["argv"],
            )
            self.assertFalse(commands["data-model-authoring"]["writes_state"])
            self.assertEqual(
                ["bin/governance", "design", "ui-interaction-authoring", ".", "--json"],
                commands["ui-interaction-authoring"]["argv"],
            )
            self.assertFalse(commands["ui-interaction-authoring"]["writes_state"])
            self.assertEqual("complete", queues["project-runtime"]["status"])
            self.assertEqual("not_required", queues["project-runtime"]["summary"]["coverage_status"])
            self.assertTrue(queues["project-runtime"]["summary"]["configuration_complete"])
            self.assertIn(
                "configuring-project-runtime",
                queues["project-runtime"]["summary"]["skill_summary"]["local_workflow_skills"],
            )
            self.assertIn(
                "tech-stack-evaluator",
                queues["project-runtime"]["summary"]["skill_summary"]["authority_routing_skills"],
            )
            self.assertEqual(
                ["bin/governance", "project-env", "plan", ".", "--json"],
                commands["project-runtime"]["argv"],
            )

            isolated_env = _agent_env()
            isolated_env["HOME"] = str(Path(tmp) / "isolated-home")
            isolated_env["CODEX_HOME"] = str(Path(tmp) / "isolated-codex")
            work_package_result = subprocess.run(
                [sys.executable, str(CLI), "workflow", "work-package", str(target), "--json"],
                env=isolated_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, work_package_result.returncode, work_package_result.stderr)
            work_package_payload = json.loads(work_package_result.stdout)
            self.assertTrue(work_package_payload["ok"])
            self.assertTrue(work_package_payload["package_available"])
            self.assertEqual("design-derivation", work_package_payload["phase"])
            self.assertEqual("authoring_required", work_package_payload["status"])
            self.assertFalse(work_package_payload["can_start"])
            self.assertTrue(work_package_payload["stop_before_work"])
            package = work_package_payload["work_package"]
            self.assertEqual("design-authoring", package["kind"])
            self.assertEqual("architecture-authoring", package["queue_id"])
            self.assertEqual("architecture", package["track_id"])
            self.assertEqual("ARCHITECTURE-AUTHOR-001", package["work_id"])
            self.assertEqual(
                [
                    "docs/architecture/01-system-context.md",
                    "docs/architecture/02-containers.md",
                    "docs/architecture/03-quality-attributes.md",
                ],
                package["write_scope"]["primary_paths"],
            )
            self.assertIn(
                "docs/agent-workflow/workflow-pack/references/architecture-methods.md",
                package["read_order"],
            )
            self.assertTrue(all((target / path).is_file() for path in package["read_order"]))
            self.assertIn("senior-architect", work_package_payload["skill_readiness"]["missing_authority_routing_skills"])
            self.assertEqual("load-authority-skills", work_package_payload["next_action"]["kind"])
            self.assertIn("senior-architect", work_package_payload["next_action"]["skills"])

            for requirement in package["authority_skill_requirements"]:
                skill = str(requirement["name"])
                skill_file = target / ".agents/skills" / skill / "SKILL.md"
                skill_file.parent.mkdir(parents=True, exist_ok=True)
                skill_file.write_text(f"---\nname: {skill}\n---\n\n# {skill}\n", encoding="utf-8")
            local_skill_result = subprocess.run(
                [sys.executable, str(CLI), "workflow", "work-package", str(target), "--json"],
                env=isolated_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, local_skill_result.returncode, local_skill_result.stderr)
            local_skill_payload = json.loads(local_skill_result.stdout)
            self.assertTrue(local_skill_payload["can_start"])
            self.assertFalse(local_skill_payload["stop_before_work"])
            self.assertEqual([], local_skill_payload["skill_readiness"]["missing_authority_routing_skills"])
            self.assertEqual("author-design-documents", local_skill_payload["next_action"]["kind"])
            resolved_requirements = _requirements_by_name(
                local_skill_payload["skill_readiness"]["resolved_requirements"]
            )
            self.assertIn(".agents/skills/senior-architect/SKILL.md", resolved_requirements["senior-architect"]["resolved_path"])

    def test_project_runtime_work_package_blocks_implementation_until_registered_and_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            architecture = target / "docs/architecture/02-containers.md"
            architecture.write_text(
                architecture.read_text(encoding="utf-8")
                + "\n## Runtime Toolchain\n\n- The reviewed implementation runtime is Node.js 20 or newer.\n",
                encoding="utf-8",
            )
            _append_project_command(
                target,
                name="node-stack-tests",
                argv=["node", "--test"],
                environment="project-runtime",
            )
            _record_all_test_design_reviews(self, target)
            _install_test_authority_skills(target, ("tech-stack-evaluator", "senior-devops"))

            workflow_plan = _run_governance_json(self, ["workflow", "plan", str(target)])
            runtime_queue = next(queue for queue in workflow_plan["queues"] if queue["id"] == "project-runtime")
            self.assertEqual("blocked", runtime_queue["status"])
            self.assertEqual("registration_required", runtime_queue["summary"]["coverage_status"])
            self.assertEqual("project-runtime", workflow_plan["active_work"]["queue_id"])

            work_package = _run_governance_json(self, ["workflow", "work-package", str(target)])
            self.assertTrue(work_package["package_available"])
            self.assertEqual("registration_required", work_package["status"])
            self.assertTrue(work_package["can_start"], work_package)
            self.assertFalse(work_package["stop_before_work"])
            package = work_package["work_package"]
            self.assertEqual("project-runtime-configuration", package["kind"])
            self.assertEqual("project-runtime", package["queue_id"])
            self.assertEqual("node", package["missing_command_registrations"][0]["executable"])
            self.assertIn("docs/agent-workflow/command-contract.md", package["read_order"])
            self.assertIn("docs/agent-workflow/project-environment.json", package["write_scope"]["primary_paths"])
            self.assertEqual("register-project-runtime-tool", work_package["next_action"]["kind"])

            failed_gate = _run_governance_json(
                self,
                ["gate", "implementation", str(target)],
                expected_returncode=1,
            )
            requirements = {item["code"]: item for item in failed_gate["requirements"]}
            self.assertFalse(requirements["project_runtime_ready"]["ok"])
            self.assertEqual(
                "docs/agent-workflow/project-environment.json",
                requirements["project_runtime_ready"]["path"],
            )

            registered = _run_governance_json(
                self,
                [
                    "project-env",
                    "register",
                    str(target),
                    "--tool-id",
                    "node-runtime",
                    "--executable",
                    "node",
                    "--version-probe",
                    "double-dash-version",
                    "--probe-output",
                    "stdout",
                    "--version-prefix",
                    "v",
                    "--minimum-version",
                    "20.0.0",
                    "--maximum-exclusive-version",
                    "26.0.0",
                    "--repair-source-type",
                    "official-url",
                    "--repair-source",
                    "https://nodejs.org/en/download",
                    "--review-evidence",
                    "docs/architecture/02-containers.md",
                    "--repair-instructions",
                    "Install the reviewed Node.js runtime from the official source.",
                    "--reviewed",
                ],
            )
            self.assertTrue(registered["applied"])

            completed_package = _run_governance_json(self, ["workflow", "work-package", str(target)])
            self.assertFalse(completed_package["package_available"])
            self.assertEqual("complete", completed_package["status"])
            self.assertFalse(completed_package["blocked"])

            passed_gate = _run_governance_json(self, ["gate", "implementation", str(target)])
            passed_requirements = {item["code"]: item for item in passed_gate["requirements"]}
            self.assertTrue(passed_gate["ok"], passed_gate)
            self.assertTrue(passed_requirements["project_runtime_ready"]["ok"])

    def test_design_work_package_authors_own_track_before_downstream_link_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _design_scaffold_target(self, tmp)
            _install_test_authority_skills(
                target,
                (
                    "senior-architect",
                    "senior-security",
                    "observability-designer",
                    "slo-architect",
                    "senior-frontend",
                    "a11y-audit",
                    "api-design-reviewer",
                    "senior-backend",
                ),
            )

            architecture_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("architecture-authoring", architecture_package["work_package"]["queue_id"])
            self.assertEqual("authoring_required", architecture_package["status"])
            self.assertEqual("author-design-documents", architecture_package["next_action"]["kind"])
            self.assertIn(
                "docs/architecture/01-system-context.md",
                architecture_package["next_action"]["paths"],
            )

            for filename, body in (
                ("01-system-context.md", _architecture_system_context_doc()),
                ("02-containers.md", _architecture_containers_doc()),
                ("03-quality-attributes.md", _architecture_quality_attributes_doc()),
            ):
                (target / "docs/architecture" / filename).write_text(body, encoding="utf-8")
            (target / "docs/ui/01-interaction-model.md").write_text(
                _ui_interaction_model_doc(),
                encoding="utf-8",
            )

            api_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("api-authoring", api_package["work_package"]["queue_id"])
            self.assertEqual("authoring_required", api_package["status"])
            self.assertEqual("author-design-documents", api_package["next_action"]["kind"])
            self.assertIn("docs/api/00-conventions.md", api_package["next_action"]["paths"])
            self.assertNotEqual("repair", api_package["next_action"]["kind"])

    def test_api_review_runs_authority_tools_and_records_hash_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))
            args = ["design", "api-review", str(target), "--reviewed"]

            preview = _run_governance_json(self, [*args, "--check"])
            expected_paths = {
                "docs/api/baselines/openapi-baseline.json",
                "docs/api/reviews/api-lint.json",
                "docs/api/reviews/api-breaking-changes.json",
                "docs/api/reviews/api-scorecard.json",
                "docs/api/reviews/review-evidence.json",
            }
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertEqual(expected_paths, set(preview["would_update"]))
            self.assertEqual("initial-baseline", preview["baseline_mode"])
            self.assertEqual("A", preview["evidence"]["reports"]["scorecard"]["grade"])
            self.assertFalse(any((target / path).exists() for path in expected_paths))

            applied = _run_governance_json(self, args)
            self.assertTrue(applied["ok"])
            self.assertTrue(applied["applied"])
            self.assertEqual(expected_paths, set(applied["updated"]))
            self.assertTrue(all((target / path).is_file() for path in expected_paths))
            evidence = json.loads(
                (target / "docs/api/reviews/review-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual("api-design-reviewer", evidence["authority_skill"]["name"])
            self.assertRegex(evidence["authority_skill"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                {"api_linter", "api_scorecard", "breaking_change_detector"},
                {tool["name"] for tool in evidence["authority_tools"]},
            )
            self.assertTrue(
                all(re.fullmatch(r"[0-9a-f]{64}", tool["sha256"]) for tool in evidence["authority_tools"])
            )

            idempotent = _run_governance_json(self, [*args, "--check"])
            self.assertTrue(idempotent["ok"])
            self.assertEqual([], idempotent["would_update"])
            self.assertEqual(evidence["recorded_at"], idempotent["evidence"]["recorded_at"])

    def test_api_work_package_routes_machine_review_before_authority_signoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                (
                    "api-design-reviewer",
                    "senior-backend",
                    "senior-security",
                    "slo-architect",
                    "migration-architect",
                    "database-schema-designer",
                ),
            )
            _write_test_threat_review_inputs(target)
            _run_governance_json(
                self,
                ["design", "threat-review", str(target), "--reviewed"],
            )

            machine_review = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )

            self.assertEqual("api-authoring", machine_review["work_package"]["queue_id"])
            self.assertEqual("api-contracts", machine_review["work_package"]["track_id"])
            self.assertEqual("machine-review", machine_review["work_package"]["work_stage"])
            self.assertEqual("machine_review_required", machine_review["status"])
            self.assertEqual("run-api-review", machine_review["next_action"]["kind"])
            self.assertEqual(
                ["bin/governance", "design", "api-review", "."],
                machine_review["next_action"]["command_contract"]["argv_prefix"],
            )
            self.assertEqual(
                ["--reviewed"],
                machine_review["next_action"]["command_contract"]["required_arguments"],
            )

            _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed"],
            )
            _write_test_reliability_review_inputs(target)
            _run_governance_json(
                self,
                ["design", "reliability-review", str(target), "--reviewed"],
            )
            _write_test_migration_review_inputs(target)
            _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed"],
            )
            authority_review = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("review", authority_review["work_package"]["work_stage"])
            self.assertNotEqual("run-api-review", authority_review["next_action"]["kind"])

    def test_threat_review_runs_authority_tool_and_gates_architecture_signoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("senior-architect", "senior-security"))
            _write_test_threat_review_inputs(target)

            blocked_review = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "architecture",
                    "--work",
                    "ARCHITECTURE-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Architecture boundaries and security risks were reviewed.",
                    "--reviewed",
                ],
                expected_returncode=1,
            )
            self.assertTrue(any("design threat-review" in error for error in blocked_review["errors"]))

            work_package = _run_governance_json(self, ["workflow", "work-package", str(target)])
            self.assertEqual("architecture", work_package["work_package"]["track_id"])
            self.assertEqual("threat-review", work_package["work_package"]["work_stage"])
            self.assertEqual("run-threat-review", work_package["next_action"]["kind"])
            self.assertEqual(
                ["bin/governance", "design", "threat-review", "."],
                work_package["next_action"]["command_contract"]["argv_prefix"],
            )
            input_contract = work_package["next_action"]["input_contract"]
            self.assertTrue((target / input_contract["scope_template"]).is_file())
            self.assertTrue((target / input_contract["mitigations_template"]).is_file())

            args = ["design", "threat-review", str(target), "--reviewed"]
            preview = _run_governance_json(self, [*args, "--check"])
            expected_paths = {
                "docs/architecture/threat-model/stride-report.json",
                "docs/architecture/threat-model/review-evidence.json",
            }
            self.assertTrue(preview["ok"])
            self.assertEqual(expected_paths, set(preview["would_update"]))
            self.assertEqual(1, preview["evidence"]["summary"]["high_dread_threat_count"])
            self.assertEqual(1, preview["evidence"]["summary"]["mitigated_high_dread_threat_count"])

            applied = _run_governance_json(self, args)
            self.assertTrue(applied["ok"])
            self.assertEqual(expected_paths, set(applied["updated"]))
            evidence = json.loads(
                (target / "docs/architecture/threat-model/review-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual("senior-security", evidence["authority_skill"]["name"])
            self.assertRegex(evidence["authority_tool"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(7.0, evidence["dread_threshold"])
            report = json.loads(
                (target / "docs/architecture/threat-model/stride-report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                ["Burst Exhaustion", "API Key Impersonation"],
                [item["name"] for item in report["elements"][0]["threats"]],
            )

            approved_review = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "architecture",
                    "--work",
                    "ARCHITECTURE-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Architecture boundaries and threat mitigations are complete.",
                    "--reviewed",
                ],
            )
            evidence_paths = {item["path"] for item in approved_review["review"]["evidence_snapshots"]}
            self.assertIn("docs/architecture/threat-model/review-evidence.json", evidence_paths)

    def test_threat_review_fails_closed_for_unowned_high_dread_threat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("senior-security",))
            _write_test_threat_review_inputs(target, include_owner=False)

            payload = _run_governance_json(
                self,
                ["design", "threat-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertFalse(payload["ok"])
            self.assertTrue(any("named mitigation owner" in error for error in payload["errors"]))
            self.assertFalse((target / "docs/architecture/threat-model/review-evidence.json").exists())

    def test_threat_review_requires_all_core_architecture_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("senior-security",))
            _write_test_threat_review_inputs(target)
            scope_path = target / "docs/architecture/threat-model/scope.json"
            scope = json.loads(scope_path.read_text(encoding="utf-8"))
            scope["elements"][0]["source_references"].remove(
                "docs/architecture/03-quality-attributes.md"
            )
            scope_path.write_text(json.dumps(scope, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            payload = _run_governance_json(
                self,
                ["design", "threat-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertTrue(
                any("required architecture source" in error for error in payload["errors"])
            )

    def test_threat_review_allows_owned_mitigation_below_required_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("senior-security",))
            _write_test_threat_review_inputs(target)
            path = target / "docs/architecture/threat-model/mitigations.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["mitigations"].append(
                {
                    "element_id": "goal-api",
                    "category": "Denial of Service",
                    "threat_name": "Burst Exhaustion",
                    "owner": "backend-platform",
                    "mitigation": "Apply layered request rate limits.",
                    "evidence": ["docs/architecture/03-quality-attributes.md"],
                }
            )
            path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            payload = _run_governance_json(
                self,
                ["design", "threat-review", str(target), "--reviewed", "--check"],
            )
            self.assertTrue(payload["ok"])

    def test_threat_review_evidence_becomes_stale_when_authority_tool_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("senior-security",))
            _write_test_threat_review_inputs(target)
            _run_governance_json(self, ["design", "threat-review", str(target), "--reviewed"])

            tool = target / ".agents/skills/senior-security/scripts/threat_modeler.py"
            tool.write_text(tool.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
            verification = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn("threat_review_evidence_stale", {item["code"] for item in verification["findings"]})

    def test_reliability_review_runs_slo_authority_tools_before_backend_signoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                (
                    "api-design-reviewer",
                    "senior-security",
                    "slo-architect",
                    "senior-backend",
                ),
            )
            _write_test_threat_review_inputs(target)
            _run_governance_json(self, ["design", "threat-review", str(target), "--reviewed"])
            _run_governance_json(self, ["design", "api-review", str(target), "--reviewed"])
            _write_test_reliability_review_inputs(target)

            blocked = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "backend-modules",
                    "--work",
                    "BACKEND-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Backend module and operability decisions were reviewed.",
                    "--reviewed",
                ],
                expected_returncode=1,
            )
            self.assertTrue(any("design reliability-review" in error for error in blocked["errors"]))

            package = _run_governance_json(self, ["workflow", "work-package", str(target)])
            self.assertEqual("backend-modules", package["work_package"]["track_id"])
            self.assertEqual("reliability-review", package["work_package"]["work_stage"])
            self.assertEqual("run-reliability-review", package["next_action"]["kind"])
            input_contract = package["next_action"]["input_contract"]
            self.assertTrue((target / input_contract["scope_template"]).is_file())
            self.assertTrue((target / input_contract["policy_template"]).is_file())

            args = ["design", "reliability-review", str(target), "--reviewed"]
            preview = _run_governance_json(self, [*args, "--check"])
            expected_paths = {
                "docs/backend/reliability/slo-definitions.json",
                "docs/backend/reliability/error-budgets.json",
                "docs/backend/reliability/slo-review.json",
                "docs/backend/reliability/review-evidence.json",
            }
            self.assertTrue(preview["ok"])
            self.assertEqual("required", preview["mode"])
            self.assertEqual(expected_paths, set(preview["would_update"]))
            self.assertEqual(1, preview["evidence"]["summary"]["slo_count"])
            self.assertEqual(0, preview["evidence"]["summary"]["review_finding_count"])
            self.assertEqual(
                "target_percent_to_target_alias",
                preview["evidence"]["review_adapter"]["name"],
            )

            applied = _run_governance_json(self, args)
            self.assertTrue(applied["ok"])
            self.assertEqual(expected_paths, set(applied["updated"]))
            evidence = json.loads(
                (target / "docs/backend/reliability/review-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual("slo-architect", evidence["authority_skill"]["name"])
            self.assertEqual(
                {"slo_designer", "error_budget_calculator", "slo_review"},
                {item["name"] for item in evidence["authority_tools"]},
            )

            approved = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "backend-modules",
                    "--work",
                    "BACKEND-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Backend boundaries and reliability evidence are implementation-ready.",
                    "--reviewed",
                ],
            )
            paths = {item["path"] for item in approved["review"]["evidence_snapshots"]}
            self.assertIn("docs/backend/reliability/review-evidence.json", paths)
            self.assertIn("docs/backend/04-error-budget-policy.md", paths)

    def test_reliability_review_records_reviewed_not_applicable_decision_without_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("slo-architect",))
            _write_test_reliability_review_inputs(target, decision="not-applicable")

            payload = _run_governance_json(
                self,
                ["design", "reliability-review", str(target), "--reviewed"],
            )
            self.assertTrue(payload["ok"])
            self.assertEqual("not-applicable", payload["mode"])
            self.assertEqual(
                ["docs/backend/reliability/review-evidence.json"],
                payload["updated"],
            )
            self.assertEqual([], payload["tool_runs"])
            self.assertEqual(0, payload["evidence"]["summary"]["slo_count"])

    def test_reliability_review_rejects_not_applicable_with_obsolete_generated_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("slo-architect",))
            _write_test_reliability_review_inputs(target)
            _run_governance_json(self, ["design", "reliability-review", str(target), "--reviewed"])

            _write_test_reliability_review_inputs(target, decision="not-applicable")
            blocked = _run_governance_json(
                self,
                ["design", "reliability-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )

            self.assertTrue(
                any("not-applicable reliability scope requires removing obsolete generated report" in error for error in blocked["errors"])
            )

    def test_reliability_review_fails_closed_on_authority_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("slo-architect",))
            _write_test_reliability_review_inputs(target, target_percent=99.0)

            payload = _run_governance_json(
                self,
                ["design", "reliability-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertFalse(payload["ok"])
            self.assertTrue(any("authority review reported" in error for error in payload["errors"]))
            self.assertFalse((target / "docs/backend/reliability/review-evidence.json").exists())

    def test_reliability_review_evidence_stales_when_slo_tool_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("slo-architect",))
            _write_test_reliability_review_inputs(target)
            _run_governance_json(self, ["design", "reliability-review", str(target), "--reviewed"])

            tool = target / ".agents/skills/slo-architect/scripts/slo_review.py"
            tool.write_text(tool.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
            verification = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "reliability_review_evidence_stale",
                {item["code"] for item in verification["findings"]},
            )

    def test_migration_review_runs_authority_tools_before_data_model_signoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                (
                    "api-design-reviewer",
                    "senior-security",
                    "slo-architect",
                    "migration-architect",
                    "database-schema-designer",
                    "database-designer",
                ),
            )
            _write_test_threat_review_inputs(target)
            _run_governance_json(self, ["design", "threat-review", str(target), "--reviewed"])
            _run_governance_json(self, ["design", "api-review", str(target), "--reviewed"])
            _write_test_reliability_review_inputs(target)
            _run_governance_json(self, ["design", "reliability-review", str(target), "--reviewed"])
            _write_test_migration_review_inputs(target)

            blocked = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "data-model",
                    "--work",
                    "DATA-MODEL-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Data ownership and migration decisions were reviewed.",
                    "--reviewed",
                ],
                expected_returncode=1,
            )
            self.assertTrue(any("design migration-review" in error for error in blocked["errors"]))

            package = _run_governance_json(self, ["workflow", "work-package", str(target)])
            self.assertEqual("data-model", package["work_package"]["track_id"])
            self.assertEqual("migration-review", package["work_package"]["work_stage"])
            self.assertEqual("run-migration-review", package["next_action"]["kind"])
            self.assertEqual(
                ["database-schema-designer", "migration-architect"],
                package["next_action"]["authority_skills"],
            )
            supporting_paths = set(package["work_package"]["write_scope"]["supporting_paths"])
            self.assertTrue(
                {
                    "docs/backend/migrations/review-scope.json",
                    "docs/backend/migrations/schema-before.json",
                    "docs/backend/migrations/schema-after.json",
                    "docs/backend/migrations/migration-spec.json",
                    "docs/backend/migrations/compatibility-acceptances.json",
                    "docs/backend/migrations/migration-plan.json",
                    "docs/backend/migrations/compatibility-report.json",
                    "docs/backend/migrations/rollback-runbook.json",
                    "docs/backend/migrations/review-evidence.json",
                }.issubset(supporting_paths)
            )
            for template in package["next_action"]["input_contract"]["templates"].values():
                self.assertTrue((target / template).is_file())

            args = ["design", "migration-review", str(target), "--reviewed"]
            preview = _run_governance_json(self, [*args, "--check"])
            expected_paths = {
                "docs/backend/migrations/migration-plan.json",
                "docs/backend/migrations/compatibility-report.json",
                "docs/backend/migrations/rollback-runbook.json",
                "docs/backend/migrations/review-evidence.json",
            }
            self.assertTrue(preview["ok"])
            self.assertEqual("required", preview["mode"])
            self.assertEqual(expected_paths, set(preview["would_update"]))
            self.assertEqual("backward_compatible", preview["evidence"]["summary"]["compatibility"])
            self.assertEqual(3, preview["evidence"]["summary"]["tool_run_count"])

            applied = _run_governance_json(self, args)
            self.assertEqual(expected_paths, set(applied["updated"]))
            evidence = json.loads(
                (target / "docs/backend/migrations/review-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                {"database-schema-designer", "migration-architect"},
                {item["name"] for item in evidence["authority_skills"]},
            )
            rollback = json.loads(
                (target / "docs/backend/migrations/rollback-runbook.json").read_text(encoding="utf-8")
            )
            self.assertTrue(rollback["data_recovery_plan"])
            self.assertTrue(rollback["communication_templates"])
            self.assertTrue(rollback["validation_checklist"])
            self.assertTrue(rollback["post_rollback_procedures"])

            approved = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "data-model",
                    "--work",
                    "DATA-MODEL-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Data schema, compatibility, migration, and rollback evidence are implementation-ready.",
                    "--reviewed",
                ],
            )
            paths = {item["path"] for item in approved["review"]["evidence_snapshots"]}
            self.assertIn("docs/backend/migrations/review-evidence.json", paths)
            self.assertIn("docs/backend/migrations/rollback-runbook.json", paths)

    def test_migration_review_requires_written_acceptance_for_compatibility_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            _install_test_migration_tools(target, issue_severity="potentially_breaking")
            _write_test_migration_review_inputs(target)

            blocked = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertEqual(1, len(blocked["unaccepted_issues"]))
            issue_id = blocked["unaccepted_issues"][0]["issue_id"]
            self.assertRegex(issue_id, r"^migration-compat-[0-9a-f]{12}$")
            self.assertTrue(any(issue_id in error for error in blocked["errors"]))

            _write_test_migration_review_inputs(target, accepted_issue_id=issue_id)
            accepted = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed"],
            )
            self.assertTrue(accepted["ok"])
            self.assertEqual("accepted_with_mitigations", accepted["compatibility_status"])
            self.assertEqual(1, accepted["evidence"]["summary"]["accepted_issue_count"])

    def test_migration_review_records_not_applicable_without_running_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            _write_test_migration_review_inputs(target, decision="not-applicable")

            payload = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed"],
            )
            self.assertTrue(payload["ok"])
            self.assertEqual("not-applicable", payload["mode"])
            self.assertEqual(
                ["docs/backend/migrations/review-evidence.json"],
                payload["updated"],
            )
            self.assertEqual([], payload["tool_runs"])

    def test_migration_review_evidence_stales_when_authority_tool_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            _write_test_migration_review_inputs(target)
            _run_governance_json(self, ["design", "migration-review", str(target), "--reviewed"])

            tool = target / ".agents/skills/migration-architect/scripts/compatibility_checker.py"
            tool.write_text(tool.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
            verification = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "migration_review_evidence_stale",
                {item["code"] for item in verification["findings"]},
            )

    def test_migration_review_rejects_tool_exit_code_that_disagrees_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            _install_test_migration_tools(target, issue_severity="potentially_breaking")
            tool = target / ".agents/skills/migration-architect/scripts/compatibility_checker.py"
            tool.write_text(
                tool.read_text(encoding="utf-8").replace("raise SystemExit(1)", "raise SystemExit(0)"),
                encoding="utf-8",
            )
            _write_test_migration_review_inputs(target)

            blocked = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )

            self.assertTrue(
                any("return code does not match compatibility report" in error for error in blocked["errors"])
            )

    def test_migration_review_evidence_summary_must_match_generated_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            _write_test_migration_review_inputs(target)
            _run_governance_json(self, ["design", "migration-review", str(target), "--reviewed"])
            evidence_path = target / "docs/backend/migrations/review-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["summary"]["compatibility_issue_count"] = 1
            evidence["summary"]["accepted_issue_count"] = 1
            evidence_path.write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            verification = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )

            self.assertTrue(
                any(
                    item["code"] == "migration_review_evidence_invalid"
                    and "compatibility_issue_count does not match" in item["message"]
                    for item in verification["findings"]
                )
            )

    def test_migration_review_rejects_orphan_acceptance_and_obsolete_not_applicable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            orphan_id = "migration-compat-0123456789ab"
            _write_test_migration_review_inputs(target, accepted_issue_id=orphan_id)
            orphaned = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertTrue(any(orphan_id in error and "orphaned" in error for error in orphaned["errors"]))

            _write_test_migration_review_inputs(target)
            _run_governance_json(self, ["design", "migration-review", str(target), "--reviewed"])
            _write_test_migration_review_inputs(target, decision="not-applicable")
            obsolete = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertTrue(
                any("requires removing obsolete migration artifact" in error for error in obsolete["errors"])
            )

    def test_migration_review_rejects_symlinked_schema_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                ("migration-architect", "database-schema-designer"),
            )
            _write_test_migration_review_inputs(target)
            schema = target / "docs/backend/migrations/schema-before.json"
            external = Path(tmp) / "external-schema.json"
            external.write_text(schema.read_text(encoding="utf-8"), encoding="utf-8")
            schema.unlink()
            schema.symlink_to(external)

            blocked = _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )

            self.assertTrue(any("must not be a symbolic link" in error for error in blocked["errors"]))

    def test_migration_review_reports_temporary_workspace_write_failure(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        migration_review = importlib.import_module("migration_review_evidence")
        tool_paths = {
            name: ROOT / "scripts/migration_review_evidence.py"
            for name in migration_review.MIGRATION_TOOL_FILES
        }
        input_bytes = {
            key: b"{}\n"
            for key in migration_review.MIGRATION_INPUT_PATHS
        }

        with mock.patch.object(migration_review.Path, "write_bytes", side_effect=OSError("disk full")):
            plan, compatibility, rollback, runs, errors = migration_review._run_authority_tools(
                tool_paths,
                input_bytes,
            )

        self.assertEqual({}, plan)
        self.assertEqual({}, compatibility)
        self.assertEqual({}, rollback)
        self.assertEqual([], runs)
        self.assertTrue(any("workspace write failed" in error and "disk full" in error for error in errors))

    def test_api_design_review_requires_current_machine_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))
            review_args = [
                "design",
                "review",
                str(target),
                "--track",
                "api-contracts",
                "--work",
                "API-AUTHOR-001",
                "--result",
                "approved",
                "--reason",
                "API authority review confirms the OpenAPI contract and machine reports satisfy the declared decisions.",
                "--reviewed",
            ]
            missing = _run_governance_json(self, review_args, expected_returncode=1)
            self.assertIn("API machine review evidence is missing", "\n".join(missing["errors"]))

            _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed"],
            )
            reviewed = _run_governance_json(self, review_args)
            evidence_paths = {
                snapshot["path"]
                for snapshot in reviewed["review"]["evidence_snapshots"]
            }
            self.assertIn("docs/api/openapi.json", evidence_paths)
            self.assertIn("docs/api/reviews/review-evidence.json", evidence_paths)
            self.assertIn("docs/api/reviews/api-lint.json", evidence_paths)
            self.assertIn("docs/api/reviews/api-scorecard.json", evidence_paths)
            self.assertIn("docs/api/reviews/api-breaking-changes.json", evidence_paths)

            openapi = target / "docs/api/openapi.json"
            specification = json.loads(openapi.read_text(encoding="utf-8"))
            specification["info"]["description"] = "Changed API meaning after machine and authority review."
            openapi.write_text(
                json.dumps(specification, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            stale_verify = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            finding_codes = {
                finding["code"]
                for finding in stale_verify["findings"]
                if isinstance(finding, dict) and "code" in finding
            }
            self.assertIn("api_review_evidence_stale", finding_codes)
            self.assertIn("design_review_stale", finding_codes)

    def test_api_review_rejects_breaking_change_without_writing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))
            _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed"],
            )
            openapi = target / "docs/api/openapi.json"
            specification = json.loads(openapi.read_text(encoding="utf-8"))
            specification["paths"] = {"/replacement": specification["paths"]["/goals"]}
            openapi.write_text(
                json.dumps(specification, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _install_test_api_review_tools(target, breaking=True)

            rejected = _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )

            self.assertIn("breaking changes", "\n".join(rejected["errors"]))
            evidence = json.loads(
                (target / "docs/api/reviews/review-evidence.json").read_text(encoding="utf-8")
            )
            self.assertNotEqual(
                rejected["openapi_snapshot"]["sha256"],
                evidence["openapi_snapshot"]["sha256"],
            )

    def test_api_review_fails_closed_on_lint_warnings_and_low_scorecard_grade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))
            _install_test_api_review_tools(target, lint_warnings=1)

            warned = _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertIn("1 warning(s)", "\n".join(warned["errors"]))
            self.assertFalse((target / "docs/api/reviews/review-evidence.json").exists())

            _install_test_api_review_tools(target, scorecard_grade="C")
            low_grade = _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed", "--check"],
                expected_returncode=1,
            )
            self.assertIn("grade C is below required grade B", "\n".join(low_grade["errors"]))
            self.assertFalse((target / "docs/api/reviews/review-evidence.json").exists())

    def test_api_review_evidence_becomes_stale_when_authority_tool_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))
            _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed"],
            )
            linter = target / ".agents/skills/api-design-reviewer/scripts/api_linter.py"
            linter.write_text(
                linter.read_text(encoding="utf-8") + "# Authority tool changed after review.\n",
                encoding="utf-8",
            )

            stale = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            findings = [
                finding
                for finding in stale["findings"]
                if finding.get("code") == "api_review_evidence_stale"
            ]
            self.assertTrue(findings)
            self.assertIn("authority tool changed", "\n".join(finding["message"] for finding in findings))

    def test_api_review_tools_run_against_an_isolated_openapi_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))
            _install_test_api_review_tools(target, mutate_input=True)
            openapi = target / "docs/api/openapi.json"
            original = openapi.read_bytes()

            result = _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed", "--check"],
            )

            self.assertTrue(result["ok"])
            self.assertEqual(original, openapi.read_bytes())
            self.assertFalse((target / "docs/api/reviews/review-evidence.json").exists())

    def test_api_review_public_check_returns_error_for_unsupported_grade(self) -> None:
        from scripts.api_review_evidence import check_api_review_evidence

        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            result = check_api_review_evidence(target, reviewed=True, min_grade="Z")

            self.assertFalse(result.ok)
            self.assertIn("unsupported API scorecard minimum grade: Z", result.errors)

    def test_api_review_atomic_write_cleans_staged_files_after_staging_failure(self) -> None:
        from scripts import api_review_evidence

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_write_bytes = Path.write_bytes

            def staged_write(path: Path, content: bytes) -> int:
                if path.name == ".second.json.tmp":
                    raise OSError("planned staging failure")
                return original_write_bytes(path, content)

            with mock.patch.object(Path, "write_bytes", new=staged_write):
                with self.assertRaises(OSError):
                    api_review_evidence._write_outputs_atomically(
                        root,
                        {"first.json": b"first\n", "second.json": b"second\n"},
                    )

            self.assertFalse((root / ".first.json.tmp").exists())
            self.assertFalse((root / ".second.json.tmp").exists())
            self.assertFalse((root / "first.json").exists())
            self.assertFalse((root / "second.json").exists())

    def test_api_review_reports_temporary_workspace_failure_without_crashing(self) -> None:
        from scripts.api_review_evidence import check_api_review_evidence

        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(target, ("api-design-reviewer",))

            with mock.patch(
                "scripts.api_review_evidence.tempfile.TemporaryDirectory",
                side_effect=OSError("temporary storage unavailable"),
            ):
                result = check_api_review_evidence(target, reviewed=True)

            self.assertFalse(result.ok)
            self.assertIn(
                "API authority tool workspace failed: temporary storage unavailable",
                result.errors,
            )

    def test_design_review_records_authority_bound_decisions_and_detects_stale_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _install_test_authority_skills(
                target,
                (
                    "senior-architect",
                    "senior-security",
                    "observability-designer",
                    "slo-architect",
                    "api-design-reviewer",
                    "migration-architect",
                    "database-schema-designer",
                ),
            )

            missing_review = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "design_review_missing",
                {finding["code"] for finding in missing_review["findings"]},
            )
            _write_test_threat_review_inputs(target)
            _run_governance_json(
                self,
                ["design", "threat-review", str(target), "--reviewed"],
            )
            _run_governance_json(
                self,
                ["design", "api-review", str(target), "--reviewed"],
            )
            _write_test_reliability_review_inputs(target)
            _run_governance_json(
                self,
                ["design", "reliability-review", str(target), "--reviewed"],
            )
            _write_test_migration_review_inputs(target)
            _run_governance_json(
                self,
                ["design", "migration-review", str(target), "--reviewed"],
            )
            review_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("architecture-authoring", review_package["work_package"]["queue_id"])
            self.assertEqual("review_required", review_package["status"])
            self.assertEqual("record-design-review", review_package["next_action"]["kind"])
            self.assertEqual("senior-architect", review_package["next_action"]["authority_skill"])

            reason = "Senior architecture review confirms every listed boundary decision is addressed in linked evidence."
            review_args = [
                "design",
                "review",
                str(target),
                "--track",
                "architecture",
                "--work",
                "ARCHITECTURE-AUTHOR-001",
                "--result",
                "approved",
                "--reason",
                reason,
                "--reviewed",
            ]
            review_rel = "docs/decisions/design-reviews.json"
            preview = _run_governance_json(self, [*review_args, "--check"])
            self.assertTrue(preview["ok"])
            self.assertEqual([review_rel], preview["would_update"])
            self.assertFalse((target / review_rel).exists())

            applied = _run_governance_json(self, review_args)
            self.assertTrue(applied["applied"])
            self.assertEqual([review_rel], applied["updated"])
            review = applied["review"]
            self.assertEqual("architecture", review["track"])
            self.assertEqual("A-001", review["acceptance_id"])
            self.assertEqual("senior-architect", review["authority_skill"]["name"])
            self.assertRegex(review["authority_skill"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(len(review["reviewed_decisions"]), 5)
            self.assertTrue(review["source_snapshots"])
            self.assertTrue(review["evidence_snapshots"])

            architecture_plan = _run_governance_json(
                self,
                ["design", "architecture-authoring", str(target)],
            )
            architecture_task = architecture_plan["authoring_tasks"][0]
            self.assertEqual([], architecture_task["open_decisions"])
            self.assertEqual("satisfied", architecture_task["review_status"])
            repeated = _run_governance_json(self, review_args)
            self.assertFalse(repeated["applied"])
            self.assertEqual([], repeated["updated"])

            context_path = target / "docs/architecture/01-system-context.md"
            context_path.write_text(
                context_path.read_text(encoding="utf-8")
                + "\n## Review-sensitive change\n\n- Architecture evidence changed after review.\n",
                encoding="utf-8",
            )
            stale_verify = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "design_review_stale",
                {finding["code"] for finding in stale_verify["findings"]},
            )
            stale_plan = _run_governance_json(
                self,
                ["design", "architecture-authoring", str(target)],
            )
            self.assertGreater(len(stale_plan["authoring_tasks"][0]["open_decisions"]), 5)
            self.assertEqual("stale", stale_plan["authoring_tasks"][0]["review_status"])

    def test_design_review_rejects_missing_authority_unreviewed_and_unsafe_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            review_args = [
                "design",
                "review",
                str(target),
                "--track",
                "architecture",
                "--work",
                "ARCHITECTURE-AUTHOR-001",
                "--result",
                "approved",
                "--reason",
                "Senior architecture review confirms the declared decisions are covered by repository evidence.",
                "--reviewed",
                "--check",
                "--json",
            ]
            isolated_env = _agent_env()
            isolated_env["HOME"] = str(Path(tmp) / "isolated-home")
            isolated_env["CODEX_HOME"] = str(Path(tmp) / "isolated-codex")
            missing_skill = subprocess.run(
                [sys.executable, str(CLI), *review_args],
                env=isolated_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_skill.returncode, missing_skill.stderr)
            self.assertIn(
                "required authority skill is unavailable",
                "\n".join(json.loads(missing_skill.stdout)["errors"]),
            )

            _install_test_authority_skills(target, ("senior-architect",))
            unreviewed = _run_governance_json(
                self,
                [item for item in review_args[:-1] if item != "--reviewed"],
                expected_returncode=1,
            )
            self.assertIn("--reviewed is required", unreviewed["errors"])
            unsupported = _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "architecture",
                    "--work",
                    "ARCHITECTURE-AUTHOR-001",
                    "--result",
                    "not-applicable",
                    "--reason",
                    "Architecture review found all decisions applicable and documented in evidence.",
                    "--reviewed",
                    "--check",
                ],
                expected_returncode=1,
            )
            self.assertIn("unsupported design review result for architecture", "\n".join(unsupported["errors"]))

            outside = Path(tmp) / "outside.txt"
            outside.write_text("do not overwrite\n", encoding="utf-8")
            temp_path = target / "docs/decisions/.design-reviews.json.tmp"
            temp_path.symlink_to(outside)
            unsafe_temp = _run_governance_json(
                self,
                review_args[:-1],
                expected_returncode=1,
            )
            self.assertIn("temporary path already exists", "\n".join(unsafe_temp["errors"]))
            self.assertEqual("do not overwrite\n", outside.read_text(encoding="utf-8"))
            temp_path.unlink()

            decisions_dir = target / "docs/decisions"
            internal_decisions = target / "docs/review-storage"
            decisions_dir.rename(internal_decisions)
            decisions_dir.symlink_to(internal_decisions, target_is_directory=True)
            unsafe_internal_parent = _run_governance_json(
                self,
                review_args[:-1],
                expected_returncode=1,
            )
            self.assertIn(
                "output parent must not contain symbolic links",
                "\n".join(unsafe_internal_parent["errors"]),
            )
            self.assertFalse((internal_decisions / "design-reviews.json").exists())
            decisions_dir.unlink()
            internal_decisions.rename(decisions_dir)

            outside_decisions = Path(tmp) / "outside-decisions"
            decisions_dir.rename(outside_decisions)
            decisions_dir.symlink_to(outside_decisions, target_is_directory=True)
            unsafe_parent = _run_governance_json(
                self,
                review_args[:-1],
                expected_returncode=1,
            )
            self.assertIn("output parent resolves outside target", "\n".join(unsafe_parent["errors"]))
            self.assertFalse((outside_decisions / "design-reviews.json").exists())

    def test_design_review_invalid_document_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            review_path = target / "docs/decisions/design-reviews.json"
            review_path.write_text('{"schema_version": 1, "reviews": "invalid"}\n', encoding="utf-8")
            verify_payload = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "design_review_invalid",
                {finding["code"] for finding in verify_payload["findings"]},
            )
            authoring_payload = _run_governance_json(
                self,
                ["design", "architecture-authoring", str(target)],
                expected_returncode=1,
            )
            self.assertIn("design review document reviews must be a list", authoring_payload["errors"])

    def test_authored_starter_endpoint_still_requires_design_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            endpoint_root = target / "docs/api/endpoints"
            product_endpoint = endpoint_root / "01-goal-flow.md"
            starter_endpoint = endpoint_root / "01-endpoint-contract.md"
            product_endpoint.rename(starter_endpoint)
            for path in target.rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                if "01-goal-flow.md" in text:
                    path.write_text(
                        text.replace("01-goal-flow.md", "01-endpoint-contract.md"),
                        encoding="utf-8",
                    )

            verify_payload = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )

            findings = verify_payload["findings"]
            self.assertIsInstance(findings, list)
            self.assertIn(
                "design_review_missing",
                {
                    finding["code"]
                    for finding in findings
                    if isinstance(finding, dict) and "code" in finding
                },
            )

    def test_implementation_phase_can_refresh_stale_design_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            architecture = target / "docs/architecture/01-system-context.md"
            architecture.write_text(
                architecture.read_text(encoding="utf-8")
                + "\nImplementation-discovered constraint: preserve the documented service boundary.\n",
                encoding="utf-8",
            )
            stale_verify = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "design_review_stale",
                {
                    finding["code"]
                    for finding in stale_verify["findings"]
                    if isinstance(finding, dict) and "code" in finding
                },
            )
            _run_governance_json(
                self,
                ["design", "threat-review", str(target), "--reviewed"],
            )

            review_args = [
                "design",
                "review",
                str(target),
                "--track",
                "architecture",
                "--work",
                "ARCHITECTURE-AUTHOR-001",
                "--result",
                "approved",
                "--reason",
                "Senior architecture re-review confirms the implementation-discovered constraint preserves the approved boundary.",
                "--reviewed",
            ]
            preview = _run_governance_json(self, [*review_args, "--check"])
            self.assertTrue(preview["ok"])
            self.assertEqual(["docs/decisions/design-reviews.json"], preview["would_update"])
            applied = _run_governance_json(self, review_args)
            self.assertTrue(applied["applied"])

            authoring = _run_governance_json(
                self,
                ["design", "architecture-authoring", str(target)],
            )
            self.assertEqual("satisfied", authoring["authoring_tasks"][0]["review_status"])

    def test_implementation_phase_task_scope_change_stales_design_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                task_board.read_text(encoding="utf-8").replace(
                    "Implement goal flow",
                    "Implement unrelated administrator flow",
                ),
                encoding="utf-8",
            )

            verify_payload = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )

            stale_messages = [
                finding["message"]
                for finding in verify_payload["findings"]
                if isinstance(finding, dict) and finding.get("code") == "design_review_stale"
            ]
            self.assertTrue(stale_messages)
            self.assertTrue(
                any("docs/development/02-task-board.md" in message for message in stale_messages)
            )

    def test_design_work_package_routes_orphan_review_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp, advance_implementation=False)
            _record_all_test_design_reviews(self, target)
            review_path = target / "docs/decisions/design-reviews.json"
            review_document = json.loads(review_path.read_text(encoding="utf-8"))
            orphan = dict(review_document["reviews"][0])
            orphan["acceptance_id"] = "A-999"
            orphan["work_id"] = "ARCHITECTURE-AUTHOR-999"
            review_document["reviews"].append(orphan)
            review_path.write_text(
                json.dumps(review_document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            work_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertTrue(work_package["package_available"])
            self.assertEqual("review", work_package["work_package"]["work_stage"])
            self.assertEqual("architecture", work_package["work_package"]["track_id"])
            self.assertEqual("record-design-review", work_package["next_action"]["kind"])
            self.assertIn(
                "design_review_orphan",
                {blocker["code"] for blocker in work_package["work_package"]["blockers"]},
            )

            _run_governance_json(
                self,
                [
                    "design",
                    "review",
                    str(target),
                    "--track",
                    "architecture",
                    "--work",
                    "ARCHITECTURE-AUTHOR-001",
                    "--result",
                    "approved",
                    "--reason",
                    "Senior architecture review reconfirms current evidence while removing orphaned review state.",
                    "--reviewed",
                ],
            )
            repaired = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertFalse(repaired["package_available"])
            self.assertEqual("complete", repaired["status"])

    def test_implementation_plan_reports_ready_task_execution_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            result = subprocess.run(
                [sys.executable, str(CLI), "implementation", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["blocked"])
            self.assertTrue(payload["gate_ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("implementation", payload["phase"])
            self.assertEqual("workflows/06-implementation-execution.md", payload["workflow"])
            self.assertEqual("execute_exactly_one_ready_task", payload["decision_policy"])
            self.assertIn("executing-implementation-task", payload["skills"])
            self.assertIn("verifying-governance-docs", payload["skills"])
            self.assertIn("senior-fullstack", payload["specialist_skills"])
            self.assertIn("senior-architect", payload["specialist_skills"])
            self.assertIn("senior-backend", payload["specialist_skills"])
            self.assertIn("api-design-reviewer", payload["specialist_skills"])
            requirements = _requirements_by_name(payload["skill_requirements"])
            self.assertEqual("local-workflow", requirements["executing-implementation-task"]["type"])
            self.assertEqual("authority-routing", requirements["senior-architect"]["type"])
            self.assertEqual("authority-routing", requirements["senior-backend"]["type"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                requirements["senior-backend"]["missing_policy"],
            )
            self.assertEqual(
                {
                    "task_count": 1,
                    "ready_task_count": 1,
                    "in_progress_task_count": 0,
                    "actionable_task_count": 1,
                    "actionable_ready_task_count": 1,
                    "actionable_in_progress_task_count": 0,
                    "blocked_task_count": 0,
                    "done_task_count": 0,
                    "done_task_with_passing_evidence_count": 0,
                    "all_tasks_done": False,
                    "execution_complete": False,
                    "remaining_task_count": 1,
                    "invalid_task_count": 0,
                    "task_status_counts": {"ready": 1},
                    "verification_evidence_task_count": 0,
                    "gate_ok": True,
                },
                payload["implementation_summary"],
            )
            self.assertEqual("implementation-task", payload["active_work"]["kind"])
            self.assertEqual("TASK-001", payload["active_work"]["task_id"])
            self.assertEqual("ready", payload["active_work"]["status"])
            self.assertEqual("A-001", payload["active_work"]["acceptance_id"])
            self.assertEqual(
                ["bin/governance", "gate", "implementation", ".", "--json"],
                payload["active_work"]["gate_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "implementation", "start", ".", "--task", "TASK-001", "--json"],
                payload["active_work"]["start_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "verify", ".", "--check", "--json"],
                payload["active_work"]["verify_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "implementation", "plan", ".", "--json"],
                payload["active_work"]["refresh_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "implementation", "closeout", ".", "--task", "TASK-001", "--json"],
                payload["active_work"]["closeout_command"]["argv"],
            )
            self.assertEqual(1, len(payload["tasks"]))
            task = payload["tasks"][0]
            self.assertTrue(task["actionable"])
            self.assertEqual("TASK-001", task["task_id"])
            self.assertEqual("Ready", task["status"])
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual([], task["blockers"])
            self.assertEqual("implementation-execution", task["execution"]["stage"])
            self.assertEqual("executing-implementation-task", task["execution"]["primary_skill"])
            self.assertEqual(["task-tests"], task["verification_command_names"])
            self.assertEqual(
                {
                    "required_count": 1,
                    "ready_count": 1,
                    "blocked_count": 0,
                    "approval_required_count": 0,
                    "writes_state_count": 0,
                    "all_ready": True,
                },
                task["verification_command_summary"],
            )
            verification_command = task["verification_commands"][0]
            self.assertTrue(verification_command["ready"])
            self.assertEqual("task-tests", verification_command["name"])
            self.assertEqual(["python3", "-m", "unittest", "discover"], verification_command["argv"])
            self.assertEqual("core-governance", verification_command["environment"])
            self.assertEqual(
                [
                    "bin/governance",
                    "implementation",
                    "verify",
                    ".",
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--check",
                    "--json",
                ],
                verification_command["preflight_command"]["argv"],
            )
            self.assertEqual(
                [
                    "bin/governance",
                    "implementation",
                    "verify",
                    ".",
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--json",
                ],
                verification_command["execute_command"]["argv"],
            )
            self.assertIn("docs/development/02-task-board.md", task["read_order"])
            self.assertIn("docs/product/01-goals.md", task["read_order"])
            self.assertIn("docs/api/00-conventions.md", task["read_order"])
            self.assertIn("docs/tests/02-acceptance-matrix.md", task["read_order"])
            self.assertIn("docs/agent-workflow/command-contract.md", task["read_order"])
            self.assertEqual(
                "docs/product/01-goals.md",
                task["source_references"]["product"]["references"][0]["path"],
            )
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md",
                task["source_references"]["acceptance"]["references"][0]["path"],
            )
            self.assertEqual(
                [
                    "load-implementation-skill",
                    "read-implementation-checklist",
                    "implementation-gate",
                    "implementation-start",
                    "verify-implementation-execution",
                    "read-task-sources",
                    "inspect-code-surface",
                    "implement-one-task",
                    "run-task-verification",
                    "update-task-evidence",
                    "implementation-closeout",
                    "refresh-implementation-plan",
                ],
                [step["id"] for step in task["steps"]],
            )

            isolated_home = Path(tmp) / "agent-home"
            for requirement in payload["authority_skill_requirements"]:
                skill = str(requirement["name"])
                skill_file = isolated_home / ".codex/skills" / skill / "SKILL.md"
                skill_file.parent.mkdir(parents=True, exist_ok=True)
                skill_file.write_text(f"---\nname: {skill}\n---\n\n# {skill}\n", encoding="utf-8")
            isolated_env = _agent_env()
            isolated_env["HOME"] = str(isolated_home)
            isolated_env["CODEX_HOME"] = str(isolated_home / ".codex")
            work_package_result = subprocess.run(
                [sys.executable, str(CLI), "workflow", "work-package", str(target), "--json"],
                env=isolated_env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, work_package_result.returncode, work_package_result.stderr)
            work_package_payload = json.loads(work_package_result.stdout)
            self.assertTrue(work_package_payload["ok"])
            self.assertTrue(work_package_payload["package_available"])
            self.assertEqual("implementation", work_package_payload["phase"])
            self.assertEqual("ready", work_package_payload["status"])
            self.assertTrue(work_package_payload["can_start"])
            self.assertFalse(work_package_payload["stop_before_work"])
            package = work_package_payload["work_package"]
            self.assertEqual("implementation-task", package["kind"])
            self.assertEqual("implementation-plan", package["queue_id"])
            self.assertEqual("TASK-001", package["work_id"])
            self.assertTrue(package["write_scope"]["requires_codebase_mapping"])
            self.assertEqual(["task-tests"], package["verification_command_names"])
            self.assertTrue(package["verification_command_summary"]["all_ready"])
            self.assertEqual("task-tests", package["verification_commands"][0]["name"])
            self.assertEqual(
                "claim_then_execute_all_required_verification_commands_then_closeout",
                package["execution_contract"]["decision_policy"],
            )
            self.assertEqual(
                package["verification_commands"],
                package["execution_contract"]["verification_commands"],
            )
            self.assertIn(
                "docs/agent-workflow/workflow-pack/references/implementation-execution-checklist.md",
                package["read_order"],
            )
            self.assertTrue(all((target / path).is_file() for path in package["read_order"]))
            self.assertEqual([], work_package_payload["skill_readiness"]["missing_authority_routing_skills"])
            self.assertEqual("claim-implementation-task", work_package_payload["next_action"]["kind"])
            self.assertEqual(
                ["bin/governance", "implementation", "start", ".", "--task", "TASK-001", "--json"],
                work_package_payload["next_action"]["command"]["argv"],
            )

    def test_implementation_plan_blocks_ready_task_without_registered_command_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                task_board.read_text(encoding="utf-8").replace("command:task-tests", "make test"),
                encoding="utf-8",
            )

            payload = _run_governance_json(self, ["implementation", "plan", str(target)])

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["blocked"])
            self.assertFalse(payload["tasks"][0]["actionable"])
            self.assertEqual([], payload["tasks"][0]["verification_command_names"])
            self.assertIn(
                "task_verification_command_binding_missing",
                {item["code"] for item in payload["tasks"][0]["blockers"]},
            )

    def test_implementation_plan_blocks_unknown_command_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                task_board.read_text(encoding="utf-8").replace("command:task-tests", "command:missing-tests"),
                encoding="utf-8",
            )

            payload = _run_governance_json(self, ["implementation", "plan", str(target)])

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["blocked"])
            command = payload["tasks"][0]["verification_commands"][0]
            self.assertFalse(command["ready"])
            self.assertEqual("missing-tests", command["name"])
            self.assertIn("command contract command not found", command["errors"][0])
            self.assertIn(
                "task_verification_command_invalid",
                {item["code"] for item in payload["tasks"][0]["blockers"]},
            )

    def test_implementation_plan_blocks_malformed_command_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                task_board.read_text(encoding="utf-8").replace(
                    "command:task-tests",
                    "command:task-tests/extra",
                ),
                encoding="utf-8",
            )

            payload = _run_governance_json(self, ["implementation", "plan", str(target)])

            self.assertTrue(payload["blocked"])
            command = payload["tasks"][0]["verification_commands"][0]
            self.assertEqual("malformed", command["status"])
            self.assertEqual("task-tests/extra", command["name"])
            self.assertIn("must match command:<registered-name>", command["errors"][0])
            self.assertIn(
                "task_verification_command_binding_malformed",
                {item["code"] for item in payload["tasks"][0]["blockers"]},
            )

    def test_implementation_plan_blocks_approval_required_command_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "print('approval')"],
                approval_required=True,
            )

            payload = _run_governance_json(self, ["implementation", "plan", str(target)])

            self.assertTrue(payload["blocked"])
            command = payload["tasks"][0]["verification_commands"][0]
            self.assertEqual("approval_required", command["status"])
            self.assertTrue(command["approval_required"])
            self.assertIn(
                "task_verification_command_requires_approval",
                {item["code"] for item in payload["tasks"][0]["blockers"]},
            )

    def test_implementation_plan_adds_allow_writes_to_state_writing_verification_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "print('writes')"],
                writes_state=True,
            )

            payload = _run_governance_json(self, ["implementation", "plan", str(target)])

            command = payload["tasks"][0]["verification_commands"][0]
            self.assertTrue(command["ready"])
            self.assertIn("--allow-writes", command["preflight_command"]["argv"])
            self.assertIn("--allow-writes", command["execute_command"]["argv"])

    def test_implementation_start_reports_in_progress_status_sync_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "start",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["start_ready"])
            self.assertEqual("claim_exactly_one_ready_task_before_editing_code", payload["decision_policy"])
            self.assertEqual("In Progress", payload["target_status"])
            requirements = {requirement["code"]: requirement for requirement in payload["requirements"]}
            self.assertEqual("satisfied", requirements["implementation_gate_passed"]["status"])
            self.assertEqual("satisfied", requirements["task_status_startable"]["status"])
            self.assertEqual("satisfied", requirements["single_in_progress_task"]["status"])
            self.assertEqual("In Progress", payload["status_update_plan"]["target_status"])
            self.assertTrue(payload["status_update_plan"]["can_auto_apply"])
            self.assertEqual(
                ["bin/governance", "implementation", "start", ".", "--task", "TASK-001", "--apply", "--json"],
                payload["status_update_plan"]["apply_command"]["argv"],
            )
            self.assertEqual(
                [
                    {
                        "path": "docs/development/02-task-board.md",
                        "task_id": "TASK-001",
                        "field": "Status",
                        "from": "Ready",
                        "to": "In Progress",
                    },
                    {
                        "path": "docs/development/01-roadmap.md",
                        "task_id": "TASK-001",
                        "field": "Status",
                        "from": "Ready",
                        "to": "In Progress",
                    },
                ],
                payload["status_update_plan"]["updates"],
            )
            self.assertIn("| TASK-001 | Ready | Implement goal flow |", (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"))
            self.assertIn("| TASK-001 | Ready | Goal flow |", (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8"))

    def test_implementation_start_apply_marks_task_and_roadmap_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "start",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--apply",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["apply_requested"])
            self.assertTrue(payload["applied"])
            self.assertFalse(payload["already_current"])
            self.assertEqual(
                [
                    ".governance/implementation-change-baselines.json",
                    "docs/development/02-task-board.md",
                    "docs/development/01-roadmap.md",
                ],
                payload["updated_paths"],
            )
            self.assertEqual("In Progress", payload["task"]["status"])
            self.assertFalse(payload["status_update_plan"]["updates_required"])
            self.assertIn("| TASK-001 | In Progress | Implement goal flow |", (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"))
            self.assertIn("| TASK-001 | In Progress | Goal flow |", (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8"))

            plan = _run_governance_json(self, ["implementation", "plan", str(target)])
            self.assertFalse(plan["blocked"])
            self.assertTrue(plan["gate_ok"])
            self.assertEqual(1, plan["implementation_summary"]["in_progress_task_count"])
            self.assertEqual(1, plan["implementation_summary"]["actionable_in_progress_task_count"])
            self.assertEqual("in_progress", plan["active_work"]["status"])
            self.assertEqual("TASK-001", plan["active_work"]["task_id"])

    def test_implementation_closeout_blocks_done_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["closeout_ready"])
            self.assertEqual("do_not_mark_done_without_passing_evidence", payload["decision_policy"])
            requirements = {requirement["code"]: requirement for requirement in payload["requirements"]}
            self.assertEqual("satisfied", requirements["implementation_gate_passed"]["status"])
            self.assertEqual("satisfied", requirements["governance_verify_passed"]["status"])
            self.assertEqual("missing", requirements["verification_log_row_present"]["status"])
            self.assertEqual("missing", requirements["verification_result_passing"]["status"])
            self.assertEqual("missing", requirements["required_verification_commands_passing"]["status"])
            self.assertEqual("missing", requirements["task_verification_links_local_evidence"]["status"])
            self.assertFalse(payload["evidence_summary"]["verification_logged"])
            self.assertEqual(["task-tests"], payload["evidence_summary"]["required_verification_commands"])
            self.assertEqual(["task-tests"], payload["evidence_summary"]["missing_verification_commands"])
            self.assertFalse(payload["evidence_summary"]["verification_links_local_evidence"])
            self.assertEqual(
                ["bin/governance", "implementation", "closeout", ".", "--task", "TASK-001", "--json"],
                payload["refresh_command"]["argv"],
            )

    def test_implementation_closeout_blocks_unknown_required_verification_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                task_board.read_text(encoding="utf-8").replace(
                    "command:task-tests",
                    "command:missing-tests docs/development/03-verification-log.md",
                ),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | missing-tests | pass | 2026-07-08 | Unregistered evidence. |\n"
                ),
                encoding="utf-8",
            )

            payload = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )

            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertFalse(payload["closeout_ready"])
            self.assertEqual(
                "missing",
                requirements["required_verification_commands_registered"]["status"],
            )
            self.assertEqual(
                "satisfied",
                requirements["required_verification_commands_passing"]["status"],
            )
            self.assertEqual(
                ["missing-tests"],
                payload["evidence_summary"]["required_verification_commands"],
            )
            self.assertEqual([], payload["evidence_summary"]["missing_verification_commands"])
            self.assertEqual([], payload["evidence_summary"]["failing_verification_commands"])
            self.assertFalse(payload["evidence_summary"]["verification_commands_registered"])

    def test_implementation_verify_check_previews_registered_command_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            marker = target / "command-ran"
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--run-id",
                    "VR-20260713T120000000000Z-01234567",
                    "--check",
                ],
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertTrue(payload["verification_ready"])
            self.assertFalse(payload["writes_state"])
            self.assertFalse(payload["executed"])
            self.assertFalse(marker.exists())
            self.assertEqual("task-tests", payload["command_contract"]["name"])
            self.assertTrue(payload["environment_readiness"]["ok"])
            self.assertEqual("python3", payload["environment_readiness"]["required_executable"])
            self.assertEqual("path_lookup", payload["environment_readiness"]["resolution_strategy"])
            self.assertEqual(
                "argv0_and_declared_environment_tools",
                payload["environment_readiness"]["validation_scope"],
            )
            self.assertTrue(payload["environment_readiness"]["version_constraints_enforced"])
            self.assertFalse(payload["environment_readiness"]["package_source_inferred"])
            self.assertEqual(
                "core-governance",
                payload["environment_readiness"]["environment_contract"]["environment_id"],
            )
            self.assertTrue(payload["environment_readiness"]["environment_probe_executed"])
            self.assertTrue(payload["environment_readiness"]["available"])
            self.assertTrue(payload["environment_readiness"]["executable"])
            self.assertEqual(
                "continue_execution",
                payload["environment_readiness"]["repair_decision"]["decision"],
            )
            self.assertEqual(
                ["docs/development/04-implementation-evidence.md", "docs/development/03-verification-log.md", "docs/development/02-task-board.md", "docs/development/README.md"],
                payload["would_write"],
            )
            self.assertIn("--run-id", payload["execute_command"]["argv"])

    def test_implementation_verify_blocks_unsatisfied_declared_runtime_version_with_manual_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            environment_path = target / "docs/agent-workflow/project-environment.json"
            environment_contract = json.loads(environment_path.read_text(encoding="utf-8"))
            project_runtime = next(
                item for item in environment_contract["environments"] if item["id"] == "project-runtime"
            )
            project_runtime["tools"] = [
                {
                    "id": "python-tests",
                    "executable": "python3",
                    "version_probe": {
                        "args": ["--version"],
                        "output": "stdout",
                        "prefix": "Python ",
                    },
                    "version_requirement": {"minimum": "99.0.0"},
                    "repair": {
                        "strategy": "manual",
                        "source": {
                            "type": "official-url",
                            "location": "https://www.python.org/downloads/",
                            "review_evidence": "docs/agent-workflow/workflow-pack/references/project-environment-contract.md",
                        },
                        "instructions": "Install an approved Python runtime that satisfies the declared version.",
                    },
                }
            ]
            environment_path.write_text(
                json.dumps(environment_contract, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _append_project_command(
                target,
                name="future-python-tests",
                argv=["python3", "-c", "print('must not run')"],
                environment="project-runtime",
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "future-python-tests",
                    "--run-id",
                    "VR-20260714T130000000000Z-50607080",
                    "--check",
                ],
                expected_returncode=1,
            )

            readiness = payload["environment_readiness"]
            self.assertFalse(readiness["ok"])
            self.assertEqual("project-runtime", readiness["environment_contract"]["environment_id"])
            self.assertTrue(readiness["environment_probe_executed"])
            self.assertEqual(1, len(readiness["required_tools"]))
            tool = readiness["required_tools"][0]
            self.assertEqual("python-tests", tool["id"])
            self.assertTrue(tool["available"])
            self.assertTrue(tool["probe_passed"])
            self.assertFalse(tool["version_satisfies"])
            self.assertEqual("environment_tool_version_unsatisfied", tool["blocker_code"])
            self.assertEqual(
                "complete_manual_environment_repairs",
                readiness["repair_decision"]["decision"],
            )
            self.assertEqual("https://www.python.org/downloads/", readiness["repair_actions"][0]["source"]["location"])
            self.assertEqual({}, readiness["repair_preflight_command"])

    def test_implementation_verify_blocks_unknown_missing_executable_without_guessing_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="missing-project-tool",
                argv=["docs-as-code-missing-project-tool", "test"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "missing-project-tool",
                    "--run-id",
                    "VR-20260713T120000000000Z-10203040",
                    "--check",
                ],
                expected_returncode=1,
            )

            self.assertFalse(payload["verification_ready"])
            self.assertFalse(payload["executed"])
            readiness = payload["environment_readiness"]
            self.assertFalse(readiness["ok"])
            self.assertEqual("command_environment_tool_undeclared", readiness["blocker_code"])
            self.assertEqual(
                "complete_manual_environment_repairs",
                readiness["repair_decision"]["decision"],
            )
            self.assertTrue(readiness["repair_decision"]["manual_repair_required"])
            self.assertEqual({}, readiness["repair_preflight_command"])
            self.assertEqual("register", readiness["repair_actions"][0]["strategy"])
            self.assertIn("--check", readiness["refresh_command"]["argv"])
            blocker_codes = {item["code"] for item in payload["blocking_requirements"]}
            self.assertIn("command_environment_ready", blocker_codes)

    def test_implementation_verify_resolves_repository_relative_executable_from_contract_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            project = target / "services/api"
            project.mkdir(parents=True)
            executable = project / "tools/check"
            executable.parent.mkdir()
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
            _append_project_command(
                target,
                name="api-check",
                argv=["tools/check"],
                cwd="services/api",
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "api-check",
                    "--run-id",
                    "VR-20260713T120000000000Z-20304050",
                    "--check",
                ],
            )

            readiness = payload["environment_readiness"]
            self.assertTrue(readiness["ok"])
            self.assertEqual("cwd_relative", readiness["resolution_strategy"])
            self.assertEqual(str(executable.resolve()), readiness["resolved_path"])

    def test_implementation_verify_rejects_relative_executable_that_escapes_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            project = target / "services/api"
            project.mkdir(parents=True)
            outside = target.parent / "outside-check"
            outside.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            outside.chmod(0o755)
            _append_project_command(
                target,
                name="outside-check",
                argv=["../../../outside-check"],
                cwd="services/api",
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "outside-check",
                    "--run-id",
                    "VR-20260713T120000000000Z-30405060",
                    "--check",
                ],
                expected_returncode=1,
            )

            readiness = payload["environment_readiness"]
            self.assertFalse(readiness["ok"])
            self.assertEqual("command_executable_outside_repository", readiness["blocker_code"])
            self.assertEqual(
                "repair_repository_executable",
                readiness["repair_decision"]["decision"],
            )

    def test_implementation_verify_rejects_non_executable_repository_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            executable = target / "tools/check"
            executable.parent.mkdir()
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o644)
            _append_project_command(target, name="non-executable-check", argv=["tools/check"])
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "non-executable-check",
                    "--run-id",
                    "VR-20260713T120000000000Z-40506070",
                    "--check",
                ],
                expected_returncode=1,
            )

            readiness = payload["environment_readiness"]
            self.assertFalse(readiness["ok"])
            self.assertTrue(readiness["available"])
            self.assertFalse(readiness["executable"])
            self.assertEqual("command_executable_not_executable", readiness["blocker_code"])

    def test_implementation_verify_executes_and_records_passing_evidence_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "print('verification passed')"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            _write_test_implementation_change(target)

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--run-id",
                    "VR-20260713T120000000000Z-01234567",
                ],
            )

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["executed"])
            self.assertTrue(payload["evidence_recorded"])
            self.assertTrue(payload["command_passed"])
            self.assertEqual(0, payload["execution_result"]["returncode"])
            self.assertEqual("pass", payload["execution_result"]["result"])
            self.assertEqual(
                [
                    "docs/development/04-implementation-evidence.md",
                    "docs/development/03-verification-log.md",
                    "docs/development/02-task-board.md",
                    "docs/development/README.md",
                ],
                payload["updated_paths"],
            )
            evidence = (target / "docs/development/04-implementation-evidence.md").read_text(encoding="utf-8")
            verification_log = (target / "docs/development/03-verification-log.md").read_text(encoding="utf-8")
            task_board = (target / "docs/development/02-task-board.md").read_text(encoding="utf-8")
            self.assertIn("## VR-20260713T120000000000Z-01234567", evidence)
            self.assertIn("verification passed", evidence)
            execution_date = str(payload["execution_result"]["started_at"])[:10]
            self.assertIn(f"| TASK-001 | task-tests | pass | {execution_date} |", verification_log)
            self.assertIn("[task-tests evidence](04-implementation-evidence.md#vr-20260713t120000000000z-01234567)", task_board)
            self.assertTrue(_run_governance_json(self, ["verify", str(target), "--check"])["ok"])
            self.assertTrue(_record_test_code_review(self, target)["evidence_current"])
            closeout = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )
            self.assertTrue(closeout["closeout_ready"])
            self.assertTrue(closeout["evidence_summary"]["all_verification_results_passing"])

    def test_implementation_verify_records_failure_and_closeout_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "print('verification failed'); raise SystemExit(3)"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--run-id",
                    "VR-20260713T120000000000Z-89abcdef",
                ],
                expected_returncode=1,
            )

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["evidence_recorded"])
            self.assertFalse(payload["command_passed"])
            self.assertEqual(3, payload["execution_result"]["returncode"])
            self.assertIn("verification failed", (target / "docs/development/04-implementation-evidence.md").read_text(encoding="utf-8"))
            closeout = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )
            requirements = {item["code"]: item for item in closeout["requirements"]}
            self.assertFalse(closeout["closeout_ready"])
            self.assertEqual("missing", requirements["verification_results_all_passing"]["status"])

    def test_implementation_verify_rerun_replaces_current_summary_but_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=[
                    "python3",
                    "-c",
                    "from pathlib import Path; raise SystemExit(0 if Path('verification-ready').is_file() else 2)",
                ],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            _write_test_implementation_change(target)
            _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--run-id",
                    "VR-20260713T120000000000Z-11111111",
                ],
                expected_returncode=1,
            )
            (target / "verification-ready").write_text("ready\n", encoding="utf-8")

            second = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                    "--run-id",
                    "VR-20260713T120100000000Z-22222222",
                ],
            )

            self.assertTrue(second["command_passed"])
            log = (target / "docs/development/03-verification-log.md").read_text(encoding="utf-8")
            evidence = (target / "docs/development/04-implementation-evidence.md").read_text(encoding="utf-8")
            self.assertEqual(1, len(re.findall(r"^\| TASK-001 \| task-tests \|", log, flags=re.MULTILINE)))
            self.assertIn("| TASK-001 | task-tests | pass |", log)
            self.assertIn("## VR-20260713T120000000000Z-11111111", evidence)
            self.assertIn("## VR-20260713T120100000000Z-22222222", evidence)
            self.assertTrue(_record_test_code_review(self, target)["evidence_current"])
            closeout = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )
            self.assertTrue(closeout["closeout_ready"])

    def test_implementation_verify_refuses_approval_required_contract_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            marker = target / "approval-command-ran"
            _append_project_command(
                target,
                name="external-check",
                argv=["python3", "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"],
                approval_required=True,
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "external-check",
                    "--run-id",
                    "VR-20260713T120000000000Z-aabbccdd",
                ],
                expected_returncode=1,
            )

            self.assertFalse(payload["ok"])
            self.assertFalse(payload["executed"])
            self.assertFalse(marker.exists())
            blocker_codes = {item["code"] for item in payload["blocking_requirements"]}
            self.assertIn("command_approval_not_allowed", blocker_codes)

    def test_implementation_verify_requires_write_opt_in_for_state_writing_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            marker = target / "state-writing-command-ran"
            _append_project_command(
                target,
                name="generate-artifact",
                argv=["python3", "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"],
                writes_state=True,
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            blocked = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "generate-artifact",
                    "--run-id",
                    "VR-20260713T120000000000Z-bbccddee",
                ],
                expected_returncode=1,
            )

            self.assertFalse(blocked["executed"])
            self.assertFalse(marker.exists())
            blocker_codes = {item["code"] for item in blocked["blocking_requirements"]}
            self.assertIn("command_writes_state_requires_opt_in", blocker_codes)

            allowed = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "generate-artifact",
                    "--run-id",
                    "VR-20260713T120100000000Z-ccddeeff",
                    "--allow-writes",
                ],
            )

            self.assertTrue(allowed["command_passed"])
            self.assertTrue(marker.is_file())

    def test_implementation_verify_times_out_and_records_bounded_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="slow-tests",
                argv=[
                    "python3",
                    "-c",
                    "import time; print('before timeout', flush=True); time.sleep(5)",
                ],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "slow-tests",
                    "--run-id",
                    "VR-20260713T120000000000Z-ddeeff00",
                    "--timeout-seconds",
                    "0.1",
                ],
                expected_returncode=1,
            )

            self.assertTrue(payload["executed"])
            self.assertTrue(payload["evidence_recorded"])
            self.assertFalse(payload["command_passed"])
            self.assertTrue(payload["execution_result"]["timed_out"])
            self.assertIn(
                "before timeout",
                (target / "docs/development/04-implementation-evidence.md").read_text(encoding="utf-8"),
            )

    def test_implementation_verify_truncates_captured_output_at_configured_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="verbose-tests",
                argv=["python3", "-c", "print('x' * 4096)"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "verbose-tests",
                    "--run-id",
                    "VR-20260713T120000000000Z-eeff0011",
                    "--max-output-bytes",
                    "128",
                ],
            )

            self.assertTrue(payload["command_passed"])
            self.assertTrue(payload["execution_result"]["stdout_truncated"])
            self.assertLessEqual(len(payload["execution_result"]["stdout"].encode("utf-8")), 128)

    def test_implementation_verify_keeps_replacement_text_within_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="binary-output-tests",
                argv=["python3", "-c", "import os; os.write(1, b'\\xff' * 256)"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "binary-output-tests",
                    "--run-id",
                    "VR-20260714T120000000000Z-ff001122",
                    "--max-output-bytes",
                    "32",
                ],
            )

            self.assertTrue(payload["execution_result"]["stdout_truncated"])
            self.assertLessEqual(len(payload["execution_result"]["stdout"].encode("utf-8")), 32)

    def test_implementation_verify_redacts_common_secret_output_before_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="secret-safe-tests",
                argv=[
                    "python3",
                    "-c",
                    "import os; print('API_TOKEN=' + os.environ['IMPLEMENTATION_VERIFY_TEST_TOKEN'])",
                ],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            with mock.patch.dict(os.environ, {"IMPLEMENTATION_VERIFY_TEST_TOKEN": "super-secret-value"}):
                payload = _run_governance_json(
                    self,
                    [
                        "implementation",
                        "verify",
                        str(target),
                        "--task",
                        "TASK-001",
                        "--command",
                        "secret-safe-tests",
                        "--run-id",
                        "VR-20260714T120000000000Z-00112233",
                    ],
                )

            evidence = (target / "docs/development/04-implementation-evidence.md").read_text(encoding="utf-8")
            self.assertNotIn("super-secret-value", payload["execution_result"]["stdout"])
            self.assertNotIn("super-secret-value", evidence)
            self.assertIn("[REDACTED]", evidence)
            self.assertTrue(payload["execution_result"]["output_redacted"])
            self.assertGreater(payload["execution_result"]["stdout_redaction_count"], 0)

    @unittest.skipUnless(os.name == "posix", "implementation verification lock uses POSIX advisory locking")
    def test_implementation_verify_refuses_execution_while_evidence_lock_is_held(self) -> None:
        import fcntl

        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            marker = target / "locked-command-ran"
            _append_project_command(
                target,
                name="locked-tests",
                argv=["python3", "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            lock_path = target / ".governance/implementation-verify.lock"
            with lock_path.open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                payload = _run_governance_json(
                    self,
                    [
                        "implementation",
                        "verify",
                        str(target),
                        "--task",
                        "TASK-001",
                        "--command",
                        "locked-tests",
                        "--run-id",
                        "VR-20260714T120000000000Z-11223344",
                    ],
                    expected_returncode=1,
                )

            self.assertFalse(payload["executed"])
            self.assertFalse(marker.exists())
            blocker_codes = {item["code"] for item in payload["blocking_requirements"]}
            self.assertIn("implementation_verify_lock_unavailable", blocker_codes)

    def test_implementation_closeout_requires_every_current_verification_command_to_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            (target / "docs/development/02-task-board.md").write_text(
                _task_board_doc(
                    "| TASK-001 | In Progress | Implement goal flow | docs/product/01-goals.md | "
                    "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
                    "docs/product/08-acceptance-criteria.md | command:task-tests docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            (target / "docs/development/01-roadmap.md").write_text(
                _roadmap_doc().replace("| TASK-001 | Ready |", "| TASK-001 | In Progress |"),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | task-tests | pass | 2026-07-13 | unit evidence |\n"
                    "| TASK-001 | integration-tests | fail | 2026-07-13 | integration evidence |\n"
                ),
                encoding="utf-8",
            )

            payload = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )

            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertFalse(payload["closeout_ready"])
            self.assertEqual("missing", requirements["verification_results_all_passing"]["status"])
            self.assertFalse(payload["evidence_summary"]["all_verification_results_passing"])
            plan = _run_governance_json(self, ["implementation", "plan", str(target)])
            task = next(item for item in plan["tasks"] if item["task_id"] == "TASK-001")
            self.assertTrue(task["passing_verification_logged"])
            self.assertFalse(task["all_verification_results_passing"])

    def test_implementation_closeout_reports_done_status_sync_plan_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            (target / "docs/development/02-task-board.md").write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | "
                    "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
                    "docs/product/08-acceptance-criteria.md | command:task-tests docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | task-tests | pass | 2026-07-08 | Local verification passed. |\n"
                ),
                encoding="utf-8",
            )
            _prepare_reviewed_task_with_passing_log(self, target)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["closeout_ready"])
            self.assertTrue(payload["gate_ok"])
            self.assertTrue(payload["verification_ok"])
            self.assertEqual("TASK-001", payload["task_id"])
            self.assertEqual("Done", payload["target_status"])
            self.assertEqual([], payload["blocking_requirements"])
            self.assertTrue(payload["evidence_summary"]["verification_logged"])
            self.assertTrue(payload["evidence_summary"]["passing_verification_logged"])
            self.assertEqual([], payload["evidence_summary"]["missing_verification_commands"])
            self.assertEqual([], payload["evidence_summary"]["failing_verification_commands"])
            self.assertTrue(payload["evidence_summary"]["verification_links_local_evidence"])
            self.assertEqual("pass", payload["evidence_summary"]["verification_results"][0]["result"])
            self.assertEqual("docs/development/03-verification-log.md", payload["evidence_summary"]["verification_references"][0]["path"])
            self.assertEqual("docs/product/01-goals.md", payload["task"]["source_references"]["product"]["references"][0]["path"])
            self.assertEqual("Done", payload["status_update_plan"]["target_status"])
            self.assertTrue(payload["status_update_plan"]["can_auto_apply"])
            self.assertTrue(payload["status_update_plan"]["updates_required"])
            self.assertEqual(
                ["bin/governance", "implementation", "closeout", ".", "--task", "TASK-001", "--apply", "--json"],
                payload["status_update_plan"]["apply_command"]["argv"],
            )
            self.assertEqual(
                [
                    {
                        "path": "docs/development/02-task-board.md",
                        "task_id": "TASK-001",
                        "field": "Status",
                        "from": "In Progress",
                        "to": "Done",
                    },
                    {
                        "path": "docs/development/01-roadmap.md",
                        "task_id": "TASK-001",
                        "field": "Status",
                        "from": "In Progress",
                        "to": "Done",
                    },
                ],
                payload["status_update_plan"]["updates"],
            )
            self.assertIn("| TASK-001 | In Progress | Implement goal flow |", (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"))
            self.assertIn("| TASK-001 | In Progress | Goal flow |", (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8"))

    def test_implementation_closeout_apply_refuses_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--apply",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["closeout_ready"])
            self.assertTrue(payload["apply_requested"])
            self.assertFalse(payload["applied"])
            self.assertIn("implementation closeout is not ready", payload["apply_errors"][0])
            self.assertIn("| TASK-001 | Ready | Implement goal flow |", (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"))
            self.assertIn("| TASK-001 | Ready | Goal flow |", (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8"))

    def test_implementation_closeout_apply_marks_task_and_roadmap_done_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            (target / "docs/development/02-task-board.md").write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | "
                    "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
                    "docs/product/08-acceptance-criteria.md | command:task-tests docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | task-tests | pass | 2026-07-08 | Local verification passed. |\n"
                ),
                encoding="utf-8",
            )
            _prepare_reviewed_task_with_passing_log(self, target)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--apply",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["apply_requested"])
            self.assertTrue(payload["applied"])
            self.assertFalse(payload["already_current"])
            self.assertEqual(
                ["docs/development/02-task-board.md", "docs/development/01-roadmap.md"],
                payload["updated_paths"],
            )
            self.assertTrue(payload["pre_apply_status_update_plan"]["can_auto_apply"])
            self.assertFalse(payload["status_update_plan"]["updates_required"])
            self.assertFalse(payload["status_update_plan"]["can_auto_apply"])
            self.assertEqual("Done", payload["task"]["status"])
            self.assertEqual("Done", payload["evidence_summary"]["task_status"])
            self.assertEqual("Done", payload["evidence_summary"]["roadmap_status"])
            self.assertIn("| TASK-001 | Done | Implement goal flow |", (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"))
            self.assertIn("| TASK-001 | Done | Goal flow |", (target / "docs/development/01-roadmap.md").read_text(encoding="utf-8"))

    def test_implementation_closeout_apply_marks_in_progress_task_done_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            (target / "docs/development/02-task-board.md").write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | "
                    "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
                    "docs/product/08-acceptance-criteria.md | command:task-tests docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | task-tests | pass | 2026-07-08 | Local verification passed. |\n"
                ),
                encoding="utf-8",
            )
            _prepare_reviewed_task_with_passing_log(self, target)

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--apply",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["closeout_ready"])
            self.assertTrue(payload["applied"])
            self.assertEqual("Done", payload["task"]["status"])
            self.assertEqual("Done", payload["evidence_summary"]["task_status"])
            self.assertEqual("Done", payload["evidence_summary"]["roadmap_status"])
            self.assertEqual(
                [
                    {
                        "path": "docs/development/02-task-board.md",
                        "task_id": "TASK-001",
                        "field": "Status",
                        "from": "In Progress",
                        "to": "Done",
                    },
                    {
                        "path": "docs/development/01-roadmap.md",
                        "task_id": "TASK-001",
                        "field": "Status",
                        "from": "In Progress",
                        "to": "Done",
                    },
                ],
                payload["pre_apply_status_update_plan"]["updates"],
            )

    def test_implementation_plan_reports_complete_after_all_tasks_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            (target / "docs/development/02-task-board.md").write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | "
                    "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
                    "docs/product/08-acceptance-criteria.md | command:task-tests docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | task-tests | pass | 2026-07-08 | Local verification passed. |\n"
                ),
                encoding="utf-8",
            )
            _prepare_reviewed_task_with_passing_log(self, target)
            apply_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--apply",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, apply_result.returncode, apply_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "implementation", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["blocked"])
            self.assertFalse(payload["gate_ok"])
            self.assertTrue(payload["implementation_summary"]["execution_complete"])
            self.assertTrue(payload["implementation_summary"]["all_tasks_done"])
            self.assertEqual(1, payload["implementation_summary"]["done_task_with_passing_evidence_count"])
            self.assertEqual("implementation-complete", payload["active_work"]["kind"])
            self.assertEqual("complete", payload["active_work"]["status"])
            self.assertEqual(1, payload["active_work"]["completed_task_count"])
            self.assertEqual([], payload["active_work"]["next_actions"])

    def test_workflow_plan_reports_complete_after_all_implementation_tasks_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            (target / "docs/development/02-task-board.md").write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | "
                    "docs/architecture/01-system-context.md | docs/api/00-conventions.md | "
                    "docs/product/08-acceptance-criteria.md | command:task-tests docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            (target / "docs/development/03-verification-log.md").write_text(
                _verification_log_doc(
                    "| TASK-001 | task-tests | pass | 2026-07-08 | Local verification passed. |\n"
                ),
                encoding="utf-8",
            )
            _prepare_reviewed_task_with_passing_log(self, target)
            apply_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "implementation",
                    "closeout",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--apply",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, apply_result.returncode, apply_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "workflow", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["blocked"])
            self.assertEqual("implementation", payload["phase"])
            queue = payload["queues"][0]
            self.assertEqual("implementation-plan", queue["id"])
            self.assertEqual("complete", queue["status"])
            self.assertTrue(queue["summary"]["implementation_summary"]["execution_complete"])
            self.assertEqual("implementation-complete", queue["summary"]["active_work"]["kind"])
            self.assertEqual("complete", payload["active_work"]["status"])
            self.assertEqual("complete", payload["active_work"]["queue_status"])

    def test_workflow_plan_reports_implementation_task_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            result = subprocess.run(
                [sys.executable, str(CLI), "workflow", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["blocked"])
            self.assertEqual("implementation", payload["phase"])
            queues = {queue["id"]: queue for queue in payload["queues"]}
            self.assertEqual(["implementation-plan"], list(queues))
            queue = queues["implementation-plan"]
            self.assertEqual("ready", queue["status"])
            self.assertEqual("implementation-task-plan", queue["kind"])
            self.assertEqual(
                ["bin/governance", "implementation", "plan", ".", "--json"],
                queue["command"]["argv"],
            )
            self.assertEqual(1, queue["summary"]["implementation_summary"]["actionable_ready_task_count"])
            self.assertEqual("TASK-001", queue["summary"]["active_work"]["task_id"])
            self.assertIn("executing-implementation-task", payload["skill_summary"]["local_workflow_skills"])
            self.assertIn("senior-backend", payload["skill_summary"]["authority_routing_skills"])
            self.assertIn("api-design-reviewer", payload["skill_summary"]["authority_routing_skills"])
            self.assertEqual("implementation-plan", payload["active_work"]["queue_id"])
            self.assertEqual("ready", payload["active_work"]["queue_status"])
            self.assertEqual("TASK-001", payload["active_work"]["task_id"])
            self.assertEqual(
                ["bin/governance", "implementation", "plan", ".", "--json"],
                payload["active_work"]["inspect_command"]["argv"],
            )
            local_commands = {command["make_target"]: command for command in payload["local_commands"]}
            self.assertEqual(["make", "implementation-plan"], local_commands["implementation-plan"]["argv"])

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
            self.assertFalse(payload["check"])
            self.assertFalse(payload["state_updated"])
            self.assertEqual({}, payload["state"])
            self.assertIn("warnings", payload)
            self.assertIn("findings", payload)
            self.assertIn("state_error", payload)
            self.assertEqual(str(target / ".governance/state.json"), payload["path"])
            self.assertIn("invalid governance state file", payload["error"])
            self.assertIn("unwritable", payload["error"])
            self.assertIn("failed to update verification state", payload["errors"][-1])

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
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                payload["next_actions"],
            )

    def test_init_next_actions_execute_from_reported_cwd(self) -> None:
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
            init_payload = json.loads(init_result.stdout)
            preflight_action, apply_action = init_payload["next_actions"]

            preflight = subprocess.run(
                preflight_action["argv"],
                cwd=preflight_action["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, preflight.returncode, preflight.stderr)
            preflight_payload = json.loads(preflight.stdout)
            self.assertTrue(preflight_payload["ok"])
            self.assertTrue(preflight_payload["check"])
            self.assertTrue(preflight_payload["would_advance"])
            self.assertFalse(preflight_payload["advanced"])
            self.assertEqual("product-structuring", preflight_payload["phase"])

            applied = subprocess.run(
                apply_action["argv"],
                cwd=apply_action["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, applied.returncode, applied.stderr)
            applied_payload = json.loads(applied.stdout)
            self.assertTrue(applied_payload["ok"])
            self.assertFalse(applied_payload["check"])
            self.assertTrue(applied_payload["advanced"])
            self.assertEqual("product-structuring", applied_payload["state"]["phase"])

            status_action = next(
                action for action in applied_payload["local_commands"] if action["make_target"] == "governance-status"
            )
            status = subprocess.run(
                status_action["argv"],
                cwd=status_action["cwd"],
                env=_agent_env(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status.returncode, status.stderr)
            status_payload = json.loads(status.stdout)
            self.assertTrue(status_payload["ok"])
            self.assertEqual("product-structuring", status_payload["state"]["phase"])

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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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
            self.assertIn(
                {
                    "make_target": "governance-status",
                    "cwd": str(target.resolve()),
                    "command": "make governance-status",
                    "argv": ["make", "governance-status"],
                    "recipe": "bin/governance status . --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "print workflow state as JSON",
                },
                payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-design-derivation-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "design-derivation",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/04-design-derivation.md",
                    "skills": [
                        "designing-system-architecture",
                        "designing-ui-interactions",
                        "designing-api-contracts",
                        "designing-backend-modules",
                        "designing-data-models",
                        "capturing-architecture-decisions",
                        "configuring-project-runtime",
                        "designing-frontend-modules",
                        "designing-test-strategy",
                        "planning-implementation-work",
                        "verifying-governance-docs",
                    ],
                    "command": "bin/governance advance design-derivation . --check --json",
                    "argv": ["bin/governance", "advance", "design-derivation", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-design-derivation",
                    "success_condition": "ok:true",
                    "description": "preflight advance from product structuring into design derivation",
                },
                payload["next_actions"],
            )

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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)

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

    def test_product_mark_ready_rejects_backslash_archive_path(self) -> None:
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
            manifest["archive"]["path"] = "docs/product/core/source/product\\name.docx"
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
            self.assertNotIn("Traceback", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("docs/product/core/source/product\\name.docx", manifest["archive"]["path"])

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

    def test_product_mark_ready_reports_missing_source_object_without_traceback(self) -> None:
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
            del manifest["source"]
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
            self.assertIn("invalid product source manifest: missing source object", payload["errors"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_source_hash_mismatch_without_ready_state(self) -> None:
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
            manifest["source"]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: source.sha256 does not match archive.sha256",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_invalid_archive_hash_without_ready_state(self) -> None:
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
            manifest["archive"]["sha256"] = "not-a-sha256"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: archive.sha256 must be a lowercase SHA-256 hex digest",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("not-a-sha256", manifest["archive"]["sha256"])

    def test_product_mark_ready_rejects_source_not_provided_without_ready_state(self) -> None:
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
            manifest["source"]["provided"] = False
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: source.provided must be true when product source is archived",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_invalid_import_status_without_ready_state(self) -> None:
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
            manifest["import"]["status"] = "reviewed"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product import status: reviewed; expected one of conversion_required, no_source, ready_for_structuring",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("reviewed", manifest["import"]["status"])

    def test_product_mark_ready_rejects_invalid_manifest_created_at_without_ready_state(self) -> None:
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
            manifest["created_at"] = "2026-01-01T00:00:00"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: created_at must be an ISO timestamp with timezone",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("2026-01-01T00:00:00", manifest["created_at"])

    def test_product_mark_ready_rejects_invalid_reviewed_at_without_ready_state(self) -> None:
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
            manifest["import"]["reviewed_at"] = "2026-01-01T00:00:00"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: import.reviewed_at must be an ISO timestamp with timezone",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("2026-01-01T00:00:00", manifest["import"]["reviewed_at"])

    def test_product_mark_ready_rejects_ready_reviewed_import_without_reviewed_at(self) -> None:
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
            manifest["import"]["conversion_method"] = "manual-reviewed-markdown"
            manifest["import"]["status"] = "ready_for_structuring"
            manifest["import"]["can_derive_design"] = True
            manifest["import"].pop("reviewed_at", None)
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "product import status ready_for_structuring with reviewed conversion requires import.reviewed_at",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("ready_for_structuring", manifest["import"]["status"])
            self.assertNotIn("reviewed_at", manifest["import"])

    def test_product_mark_ready_rejects_inconsistent_conversion_required_without_ready_state(self) -> None:
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
            manifest["import"]["status"] = "conversion_required"
            manifest["import"]["can_derive_design"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "product import status conversion_required requires can_derive_design: false",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertTrue(manifest["import"]["can_derive_design"])

    def test_product_mark_ready_rejects_inconsistent_ready_without_ready_state(self) -> None:
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
            manifest["import"]["status"] = "ready_for_structuring"
            manifest["import"]["can_derive_design"] = False
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "product import status ready_for_structuring requires can_derive_design: true",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("ready_for_structuring", manifest["import"]["status"])
            self.assertFalse(manifest["import"]["can_derive_design"])

    def test_product_mark_ready_rejects_non_boolean_can_derive_design_without_ready_state(self) -> None:
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
            manifest["import"]["can_derive_design"] = "false"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: import.can_derive_design must be a boolean",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("false", manifest["import"]["can_derive_design"])

    def test_product_mark_ready_rejects_prd_path_drift_without_ready_state(self) -> None:
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
            manifest["import"]["prd_path"] = "docs/product/core/other.md"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: import.prd_path must be docs/product/core/PRD.md",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("docs/product/core/other.md", manifest["import"]["prd_path"])

    def test_product_mark_ready_rejects_missing_conversion_method_without_ready_state(self) -> None:
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
            manifest["import"]["conversion_method"] = ""
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: import.conversion_method must be a non-empty string",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("", manifest["import"]["conversion_method"])

    def test_product_mark_ready_rejects_missing_source_original_path_without_ready_state(self) -> None:
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
            manifest["source"]["original_path"] = ""
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: source.original_path must be a non-empty string",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("", manifest["source"]["original_path"])

    def test_product_mark_ready_rejects_source_original_path_filename_mismatch_without_ready_state(self) -> None:
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
            manifest["source"]["original_path"] = str(Path(tmp) / "other.docx")
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
                "invalid product source manifest: source.original_path filename must match source.filename",
                payload["errors"],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual(str(Path(tmp) / "other.docx"), manifest["source"]["original_path"])

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
            self.assertIn("reviewed_at", manifest["import"])
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                payload["local_commands"],
            )
            self.assertIn(
                {
                    "id": "advance-product-structuring-check",
                    "kind": "preflight",
                    "cwd": str(target.resolve()),
                    "phase": "product-structuring",
                    "workflow": "docs/agent-workflow/workflow-pack/workflows/03-product-structuring.md",
                    "skills": ["structuring-product-requirements", "verifying-governance-docs"],
                    "command": "bin/governance advance product-structuring . --check --json",
                    "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                    "writes_state": False,
                    "approval_required": False,
                    "requires": "current phase is the previous workflow phase and the gate can pass",
                    "sequence": 1,
                    "preflight_for": "advance-product-structuring",
                    "success_condition": "ok:true",
                    "description": "preflight advance from initialization into product structuring",
                },
                payload["next_actions"],
            )
            product_meta = (target / "docs/product/core/product-meta.md").read_text(encoding="utf-8")
            self.assertIn("- Import status: `ready_for_structuring`", product_meta)
            self.assertIn(f"- Reviewed at: `{manifest['import']['reviewed_at']}`", product_meta)
            self.assertIn("| U-001 | Product Archiving |", (target / "docs/unresolved.md").read_text(encoding="utf-8"))
            self.assertIn("| resolved |", (target / "docs/unresolved.md").read_text(encoding="utf-8"))

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, gate_result.returncode, gate_result.stderr)

    def test_product_mark_ready_next_actions_execute_from_reported_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.txt"
            product.write_text(
                "Converted Product\n\nGoal\nShip governed projects from reviewed product input.\n",
                encoding="utf-8",
            )

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            init_payload = json.loads(init_result.stdout)
            convert_check, convert_apply = init_payload["next_actions"]
            self.assertEqual("product-convert-check", convert_check["id"])
            self.assertEqual("product-convert", convert_apply["id"])

            conversion_preflight = subprocess.run(
                convert_check["argv"],
                cwd=convert_check["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, conversion_preflight.returncode, conversion_preflight.stderr)
            self.assertTrue(json.loads(conversion_preflight.stdout)["ok"])

            conversion_applied = subprocess.run(
                convert_apply["argv"],
                cwd=convert_apply["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, conversion_applied.returncode, conversion_applied.stderr)
            conversion_payload = json.loads(conversion_applied.stdout)
            self.assertTrue(conversion_payload["ok"])
            self.assertEqual("pending_review", conversion_payload["state"]["product_conversion_status"])

            mark_ready_check, mark_ready_apply = conversion_payload["next_actions"]
            self.assertEqual("product-mark-ready-check", mark_ready_check["id"])
            self.assertEqual("product-mark-ready", mark_ready_apply["id"])
            self.assertIn("reviewed-utf8-text-to-markdown", mark_ready_check["argv"])
            self.assertEqual(1, mark_ready_check["sequence"])
            self.assertEqual("product-mark-ready", mark_ready_check["preflight_for"])
            self.assertEqual("ok:true", mark_ready_check["success_condition"])
            self.assertEqual(2, mark_ready_apply["sequence"])
            self.assertEqual("product-mark-ready-check", mark_ready_apply["requires_action"])
            self.assertEqual("ok:true", mark_ready_apply["success_condition"])

            preflight = subprocess.run(
                mark_ready_check["argv"],
                cwd=mark_ready_check["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, preflight.returncode, preflight.stderr)
            preflight_payload = json.loads(preflight.stdout)
            self.assertTrue(preflight_payload["ok"])
            self.assertTrue(preflight_payload["check"])
            self.assertIn("docs/product/core/source/source-manifest.json", preflight_payload["would_update"])
            self.assertTrue(preflight_payload["would_resolve_conversion_blocker"])

            applied = subprocess.run(
                mark_ready_apply["argv"],
                cwd=mark_ready_apply["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, applied.returncode, applied.stderr)
            applied_payload = json.loads(applied.stdout)
            self.assertTrue(applied_payload["ok"])
            self.assertFalse(applied_payload["check"])
            self.assertTrue(applied_payload["conversion_blocker_resolved"])
            self.assertEqual("ready_for_structuring", applied_payload["state"]["product_import_status"])

            advance_check, advance_apply = applied_payload["next_actions"]
            self.assertEqual("advance-product-structuring-check", advance_check["id"])
            self.assertEqual("advance-product-structuring", advance_apply["id"])

            advance_preflight = subprocess.run(
                advance_check["argv"],
                cwd=advance_check["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_preflight.returncode, advance_preflight.stderr)
            advance_preflight_payload = json.loads(advance_preflight.stdout)
            self.assertTrue(advance_preflight_payload["ok"])
            self.assertTrue(advance_preflight_payload["check"])
            self.assertTrue(advance_preflight_payload["would_advance"])

            advanced = subprocess.run(
                advance_apply["argv"],
                cwd=advance_apply["cwd"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advanced.returncode, advanced.stderr)
            advanced_payload = json.loads(advanced.stdout)
            self.assertTrue(advanced_payload["ok"])
            self.assertTrue(advanced_payload["advanced"])
            self.assertEqual("product-structuring", advanced_payload["state"]["phase"])

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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)

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
            self.assertTrue(blocked_requirements["product_chapters_traceable"]["ok"])
            self.assertIn(
                {
                    "make_target": "governance-status",
                    "cwd": str(target.resolve()),
                    "command": "make governance-status",
                    "argv": ["make", "governance-status"],
                    "recipe": "bin/governance status . --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "print workflow state as JSON",
                },
                blocked_payload["local_commands"],
            )
            self.assertNotIn("next_actions", blocked_payload)

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
            self.assertTrue(missing_acceptance_requirements["product_chapters_traceable"]["ok"])
            self.assertFalse(missing_acceptance_requirements["product_acceptance_chapter_present"]["ok"])
            self.assertFalse(missing_acceptance_requirements["product_acceptance_ids_present"]["ok"])

            (target / "docs/product/08-acceptance-criteria.md").write_text(
                "# Acceptance Criteria\n\nSource: [PRD](core/PRD.md).\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            missing_acceptance_ids = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_acceptance_ids.returncode)
            missing_acceptance_ids_payload = json.loads(missing_acceptance_ids.stdout)
            missing_acceptance_ids_requirements = {
                item["code"]: item for item in missing_acceptance_ids_payload["requirements"]
            }
            self.assertTrue(missing_acceptance_ids_requirements["product_acceptance_chapter_present"]["ok"])
            self.assertFalse(missing_acceptance_ids_requirements["product_acceptance_ids_present"]["ok"])
            self.assertTrue(missing_acceptance_ids_requirements["product_acceptance_ids_unique"]["ok"])

            (target / "docs/product/08-acceptance-criteria.md").write_text(
                _acceptance_doc(),
                encoding="utf-8",
            )

            allowed = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)
            allowed_payload = json.loads(allowed.stdout)
            allowed_requirements = {item["code"]: item for item in allowed_payload["requirements"]}
            self.assertTrue(allowed_payload["ok"])
            self.assertTrue(allowed_requirements["product_acceptance_ids_present"]["ok"])
            self.assertTrue(allowed_requirements["product_acceptance_ids_unique"]["ok"])
            self.assertTrue(allowed_requirements["product_chapters_traceable"]["ok"])
            self.assertTrue(allowed_requirements["product_glossary_traceable"]["ok"])
            self.assertTrue(allowed_requirements["product_unresolved_clear"]["ok"])

    def test_gate_design_derivation_routes_untraceable_product_chapter(self) -> None:
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
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nDerived goals.\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(_acceptance_doc(), encoding="utf-8")
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            result = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertTrue(requirements["product_chapters_present"]["ok"])
            self.assertFalse(requirements["product_chapters_traceable"]["ok"])
            self.assertTrue(requirements["product_acceptance_ids_present"]["ok"])
            self.assertIn(
                {
                    "code": "product_chapter_missing_prd_link",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md must link back to docs/product/core/PRD.md",
                },
                payload["verification"]["findings"],
            )

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
            self.assertIn(
                {
                    "make_target": "verify-check",
                    "cwd": str(target.resolve()),
                    "command": "make verify-check",
                    "argv": ["make", "verify-check"],
                    "recipe": "bin/governance verify . --check --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "run read-only JSON verification without updating state",
                },
                payload["local_commands"],
            )
            self.assertEqual("advance-product-structuring-check", payload["next_actions"][0]["id"])
            self.assertEqual(str(target.resolve()), payload["next_actions"][0]["cwd"])
            self.assertEqual(
                {
                    "current": "initialized",
                    "expected": "product-structuring",
                    "matches": False,
                    "message": (
                        "recorded phase is not product-structuring; "
                        "use returned next_actions to advance phases in order"
                    ),
                },
                payload["scaffold_phase"],
            )
            blockers = {
                blocker["path"]: blocker
                for blocker in payload["next_actions_blocked_by"]
            }
            self.assertIn("docs/product/03-goals-and-requirements.md", blockers)
            self.assertIn("docs/product/08-acceptance-criteria.md", blockers)
            self.assertEqual("governance_scaffold_placeholder", blockers["docs/product/03-goals-and-requirements.md"]["code"])
            self.assertIn("before running next_actions", blockers["docs/product/03-goals-and-requirements.md"]["message"])
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

    def test_product_plan_maps_prd_headings_to_structuring_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n\n"
                "## Acceptance Criteria\n\n"
                "- The initialized repository exposes local governance checks.\n",
                encoding="utf-8",
            )
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            advance_result = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_result.returncode, advance_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("product-structuring", payload["phase"])
            self.assertEqual("workflows/03-product-structuring.md", payload["workflow"])
            self.assertEqual("do_not_guess_product_meaning", payload["decision_policy"])
            self.assertEqual("structuring-product-requirements", payload["primary_skill"])
            self.assertIn("docs/product/core/PRD.md", payload["source_documents"])
            self.assertIn("docs/product/core/product-meta.md", payload["source_documents"])
            self.assertIn("docs/unresolved.md", payload["source_documents"])
            self.assertIn("docs/glossary.md", payload["source_documents"])
            available = {chapter["key"]: chapter for chapter in payload["available_chapters"]}
            self.assertIn("goals-and-requirements", available)
            self.assertEqual("docs/product/03-goals-and-requirements.md", available["goals-and-requirements"]["path"])
            self.assertIn("acceptance-criteria", available)
            heading_titles = [heading["title"] for heading in payload["prd_headings"]]
            self.assertIn("Goals and Requirements", heading_titles)
            self.assertIn("Acceptance Criteria", heading_titles)
            suggestions = {mapping["chapter"]: mapping for mapping in payload["suggested_mappings"]}
            self.assertEqual("goals-and-requirements=Goals and Requirements", suggestions["goals-and-requirements"]["command_arg"])
            self.assertEqual("acceptance-criteria=Acceptance Criteria", suggestions["acceptance-criteria"]["command_arg"])
            self.assertEqual("exact-title", suggestions["acceptance-criteria"]["confidence"])
            required_decisions = {decision["chapter"]: decision for decision in payload["required_decisions"]}
            self.assertIn("background-and-problems", required_decisions)
            self.assertNotIn("acceptance-criteria", required_decisions)
            manual_tasks = {task["chapter"]: task for task in payload["manual_authoring_tasks"]}
            self.assertEqual(
                {
                    "task_count": 4,
                    "open_decision_count": 21,
                    "required_evidence_status_counts": {
                        "missing": 5,
                        "not_indexed": 4,
                        "not_linked": 4,
                        "pending_review": 12,
                    },
                    "non_satisfied_required_evidence_count": 25,
                    "evidence_repair_action_count": 25,
                },
                payload["manual_authoring_summary"],
            )
            self.assertIn("background-and-problems", manual_tasks)
            self.assertNotIn("acceptance-criteria", manual_tasks)
            self.assertEqual("PRODUCT-AUTHOR-001", payload["active_work"]["task_id"])
            self.assertEqual("product-manual-authoring-task", payload["active_work"]["kind"])
            self.assertEqual("background-and-problems", payload["active_work"]["chapter"])
            self.assertEqual("decision_required", payload["active_work"]["status"])
            self.assertEqual(6, payload["active_work"]["blocker_count"])
            self.assertEqual(5, payload["active_work"]["open_decision_count"])
            self.assertEqual("chapter_in_scope", payload["active_work"]["next_open_decision"])
            self.assertEqual("prd-source-evidence", payload["active_work"]["next_repair_action"]["evidence_id"])
            self.assertEqual(
                ["bin/governance", "verify", ".", "--check", "--json"],
                payload["active_work"]["verify_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "product", "plan", ".", "--json"],
                payload["active_work"]["refresh_command"]["argv"],
            )
            background_task = manual_tasks["background-and-problems"]
            self.assertEqual("PRODUCT-AUTHOR-001", background_task["task_id"])
            self.assertEqual("decision_required", background_task["status"])
            self.assertEqual("do_not_guess_product_meaning", background_task["decision_policy"])
            self.assertEqual("structuring-product-requirements", background_task["execution"]["primary_skill"])
            self.assertEqual("verify-product-authoring", background_task["execution"]["verify_step"])
            self.assertEqual("refresh-product-plan", background_task["execution"]["refresh_step"])
            self.assertIn("Source Links", background_task["required_sections"])
            self.assertIn("Open Questions", background_task["required_sections"])
            required_links = {link["kind"]: link for link in background_task["required_links"]}
            self.assertTrue(required_links["canonical_prd"]["exists"])
            self.assertTrue(required_links["product_index"]["exists"])
            self.assertTrue(required_links["product_meta"]["exists"])
            self.assertTrue(required_links["unresolved_registry"]["exists"])
            required_evidence = {item["id"]: item for item in background_task["required_evidence"]}
            self.assertEqual("docs/product/core/PRD.md", required_evidence["prd-source-evidence"]["target"])
            self.assertTrue(required_evidence["prd-source-evidence"]["exists"])
            self.assertEqual("pending_review", required_evidence["prd-source-evidence"]["status"])
            self.assertEqual("docs/product/01-background-and-problems.md", required_evidence["chapter-file-authored"]["target"])
            self.assertFalse(required_evidence["chapter-file-authored"]["exists"])
            self.assertEqual("missing", required_evidence["chapter-file-authored"]["status"])
            self.assertEqual("docs/product/README.md", required_evidence["product-readme-indexed"]["target"])
            self.assertEqual("not_indexed", required_evidence["product-readme-indexed"]["status"])
            self.assertEqual("docs/product/core/product-meta.md", required_evidence["product-meta-linked"]["target"])
            self.assertEqual("not_linked", required_evidence["product-meta-linked"]["status"])
            self.assertEqual("docs/unresolved.md", required_evidence["unresolved-reviewed"]["target"])
            self.assertEqual("pending_review", required_evidence["unresolved-reviewed"]["status"])
            self.assertEqual("docs/glossary.md", required_evidence["glossary-reviewed"]["target"])
            self.assertEqual("pending_review", required_evidence["glossary-reviewed"]["status"])
            self.assertEqual(
                "bin/governance verify . --check --json",
                required_evidence["chapter-file-authored"]["verification"],
            )
            self.assertIn("chapter_in_scope", background_task["open_decisions"])
            self.assertIn("source_evidence", background_task["open_decisions"])
            self.assertIn("provide_explicit_key_heading_mapping", background_task["action_options"])
            task_steps = background_task["steps"]
            self.assertEqual(list(range(1, 12)), [step["sequence"] for step in task_steps])
            self.assertEqual("load-product-structuring-skills", task_steps[0]["id"])
            self.assertEqual("author-product-chapter", task_steps[6]["id"])
            self.assertEqual("docs/product/01-background-and-problems.md", task_steps[6]["document"])
            self.assertEqual("collect-authoring-evidence", task_steps[8]["id"])
            self.assertEqual("evidence", task_steps[8]["kind"])
            self.assertEqual(
                [
                    "bin/governance",
                    "scaffold",
                    "product",
                    ".",
                    "--chapter",
                    "background-and-problems",
                    "--check",
                    "--json",
                ],
                task_steps[4]["argv"],
            )
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task_steps[9]["argv"])
            self.assertEqual(["bin/governance", "product", "plan", ".", "--json"], task_steps[10]["argv"])
            skill_requirements = _requirements_by_name(payload["skill_requirements"])
            self.assertEqual("local-workflow", skill_requirements["structuring-product-requirements"]["type"])
            self.assertTrue(skill_requirements["structuring-product-requirements"]["available_in_workflow_pack"])
            self.assertEqual(
                "docs/agent-workflow/workflow-pack/skills/structuring-product-requirements/SKILL.md",
                skill_requirements["structuring-product-requirements"]["path"],
            )
            self.assertEqual([], payload["authority_skill_requirements"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-design-derivation-check", payload["next_actions"][0]["id"])
            self.assertEqual(str(target.resolve()), payload["next_actions"][0]["cwd"])
            steps = payload["steps"]
            self.assertEqual(
                [
                    "load-product-structuring-skills",
                    "read-product-sources",
                    "read-product-rubric",
                    "select-source-supported-chapters",
                    "scaffold-product-check",
                    "scaffold-product",
                    "structure-product-check",
                    "structure-product",
                    "verify-product-structuring",
                    "refresh-product-plan",
                ],
                [step["id"] for step in steps],
            )
            self.assertEqual(list(range(1, 11)), [step["sequence"] for step in steps])
            self.assertEqual("skill-load", steps[0]["kind"])
            self.assertIn("structuring-product-requirements", steps[0]["skills"])
            self.assertEqual(
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
                steps[4]["argv"],
            )
            self.assertFalse(steps[4]["writes_state"])
            self.assertTrue(steps[5]["writes_state"])
            self.assertEqual(
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
                steps[6]["argv"],
            )
            self.assertFalse(steps[6]["writes_state"])
            self.assertTrue(steps[7]["writes_state"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], steps[8]["argv"])
            self.assertEqual(["bin/governance", "product", "plan", ".", "--json"], steps[9]["argv"])

    def test_product_plan_reports_required_decision_when_heading_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n",
                encoding="utf-8",
            )
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            advance_result = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_result.returncode, advance_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            suggestions = {mapping["chapter"]: mapping for mapping in payload["suggested_mappings"]}
            self.assertIn("goals-and-requirements", suggestions)
            self.assertNotIn("acceptance-criteria", suggestions)
            required_decisions = {decision["chapter"]: decision for decision in payload["required_decisions"]}
            self.assertIn("acceptance-criteria", required_decisions)
            self.assertEqual("no conservative PRD heading match found", required_decisions["acceptance-criteria"]["reason"])
            self.assertIn("key=PRD Heading", required_decisions["acceptance-criteria"]["decision"])
            self.assertEqual(
                {
                    "task_count": 5,
                    "open_decision_count": 27,
                    "required_evidence_status_counts": {
                        "missing": 7,
                        "not_indexed": 5,
                        "not_linked": 5,
                        "pending_review": 15,
                    },
                    "non_satisfied_required_evidence_count": 32,
                    "evidence_repair_action_count": 32,
                },
                payload["manual_authoring_summary"],
            )
            manual_tasks = {task["chapter"]: task for task in payload["manual_authoring_tasks"]}
            self.assertIn("acceptance-criteria", manual_tasks)
            acceptance_task = manual_tasks["acceptance-criteria"]
            self.assertEqual("decision_required", acceptance_task["status"])
            self.assertIn("acceptance_id_strategy", acceptance_task["open_decisions"])
            self.assertIn("Acceptance Criteria", acceptance_task["required_sections"])
            self.assertEqual("docs/product/08-acceptance-criteria.md", acceptance_task["path"])
            acceptance_evidence = {item["id"]: item for item in acceptance_task["required_evidence"]}
            self.assertIn("acceptance-ids-stable", acceptance_evidence)
            self.assertEqual("docs/product/08-acceptance-criteria.md", acceptance_evidence["acceptance-ids-stable"]["target"])
            self.assertEqual("missing", acceptance_evidence["acceptance-ids-stable"]["status"])
            evidence_repairs = _repair_actions_by_evidence_id(acceptance_task["evidence_repair_actions"])
            self.assertIn("acceptance-ids-stable", evidence_repairs)
            self.assertEqual("missing", evidence_repairs["acceptance-ids-stable"]["status"])
            self.assertEqual(
                "create_or_restore_required_product_markdown_source_before_phase_verification",
                evidence_repairs["acceptance-ids-stable"]["repair_strategy"],
            )
            self.assertFalse(evidence_repairs["acceptance-ids-stable"]["can_auto_apply"])
            self.assertEqual(
                ["bin/governance", "verify", ".", "--check", "--json"],
                evidence_repairs["acceptance-ids-stable"]["verify_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "product", "plan", ".", "--json"],
                evidence_repairs["acceptance-ids-stable"]["refresh_command"]["argv"],
            )
            self.assertEqual(
                [
                    "bin/governance",
                    "scaffold",
                    "product",
                    ".",
                    "--chapter",
                    "acceptance-criteria",
                    "--check",
                    "--json",
                ],
                acceptance_task["steps"][4]["argv"],
            )
            structure_check = {step["id"]: step for step in payload["steps"]}["structure-product-check"]
            self.assertEqual(
                [
                    "bin/governance",
                    "product",
                    "structure",
                    ".",
                    "--chapter",
                    "goals-and-requirements=Goals and Requirements",
                    "--check",
                    "--json",
                ],
                structure_check["argv"],
            )

    def test_product_disposition_records_reviewed_decisions_and_advances_work_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n\n"
                "## Acceptance Criteria\n\n"
                "- The initialized repository exposes local governance checks.\n",
                encoding="utf-8",
            )
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])
            _run_governance_json(self, ["advance", "product-structuring", str(target)])

            initial_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("PRODUCT-AUTHOR-001", initial_package["work_package"]["work_id"])
            self.assertEqual("background-and-problems", initial_package["work_package"]["chapter"])
            self.assertEqual("decide-product-chapter", initial_package["next_action"]["kind"])

            disposition_rel = "docs/product/core/chapter-dispositions.json"
            disposition_path = target / disposition_rel
            reason = "Source review confirms the PRD contains no background or problem statement."
            preview = _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "omit-unsupported",
                    "--reason",
                    reason,
                    "--reviewed",
                    "--check",
                ],
            )
            self.assertTrue(preview["ok"])
            self.assertTrue(preview["check"])
            self.assertFalse(preview["apply_requested"])
            self.assertFalse(preview["applied"])
            self.assertEqual([disposition_rel], preview["would_update"])
            self.assertEqual([], preview["updated"])
            self.assertFalse(disposition_path.exists())
            self.assertEqual("omit-unsupported", preview["disposition"]["decision"])
            self.assertEqual(reason, preview["disposition"]["reason"])
            self.assertTrue(preview["disposition"]["reviewed"])
            self.assertEqual(
                ["chapter-source", "unresolved-items", "glossary-terms"],
                preview["disposition"]["review_scope"],
            )
            self.assertEqual("docs/product/core/PRD.md", preview["disposition"]["source_path"])
            self.assertRegex(preview["disposition"]["prd_sha256"], r"^[0-9a-f]{64}$")

            applied = _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "omit-unsupported",
                    "--reason",
                    reason,
                    "--reviewed",
                ],
            )
            self.assertTrue(applied["apply_requested"])
            self.assertTrue(applied["applied"])
            self.assertEqual([disposition_rel], applied["updated"])
            self.assertEqual([], applied["would_update"])
            self.assertTrue(disposition_path.is_file())
            disposition_document = json.loads(disposition_path.read_text(encoding="utf-8"))
            self.assertEqual(1, disposition_document["schema_version"])
            self.assertEqual(1, len(disposition_document["dispositions"]))
            self.assertEqual("background-and-problems", disposition_document["dispositions"][0]["chapter"])
            disposition_bytes = disposition_path.read_bytes()
            repeated = _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "omit-unsupported",
                    "--reason",
                    reason,
                    "--reviewed",
                ],
            )
            self.assertFalse(repeated["applied"])
            self.assertEqual([], repeated["updated"])
            self.assertEqual(disposition_bytes, disposition_path.read_bytes())

            plan = _run_governance_json(self, ["product", "plan", str(target)])
            self.assertIn(disposition_rel, plan["source_documents"])
            self.assertNotIn(
                "background-and-problems",
                {decision["chapter"] for decision in plan["required_decisions"]},
            )
            self.assertNotIn(
                "background-and-problems",
                {task["chapter"] for task in plan["manual_authoring_tasks"]},
            )
            self.assertEqual(
                {
                    "active_count": 1,
                    "author_required_count": 0,
                    "omit_unsupported_count": 1,
                    "stale_count": 0,
                    "undecided_count": 3,
                },
                plan["disposition_summary"],
            )
            next_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("PRODUCT-AUTHOR-002", next_package["work_package"]["work_id"])
            self.assertEqual("change-log", next_package["work_package"]["chapter"])

            author_reason = "The chapter must be authored manually from source evidence after review."
            _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "author-required",
                    "--reason",
                    author_reason,
                    "--reviewed",
                ],
            )
            author_plan = _run_governance_json(self, ["product", "plan", str(target)])
            author_tasks = {task["chapter"]: task for task in author_plan["manual_authoring_tasks"]}
            self.assertEqual("authoring_required", author_tasks["background-and-problems"]["status"])
            self.assertEqual("author-required", author_tasks["background-and-problems"]["disposition"]["decision"])
            author_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("PRODUCT-AUTHOR-001", author_package["work_package"]["work_id"])
            self.assertEqual("repair", author_package["next_action"]["kind"])

            background_path = target / "docs/product/01-background-and-problems.md"
            background_path.write_text(
                "# Background and Problems\n\n"
                "Source: [PRD](core/PRD.md).\n\n"
                "## Background\n\n"
                "- The reviewed source establishes the governed workspace context.\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", background_path.name)
            _append_product_meta_chapter(target, background_path.name)
            authored_plan = _run_governance_json(self, ["product", "plan", str(target)])
            authored_tasks = {task["chapter"]: task for task in authored_plan["manual_authoring_tasks"]}
            self.assertTrue(
                all(item["status"] == "satisfied" for item in authored_tasks["background-and-problems"]["required_evidence"])
            )
            self.assertEqual("change-log", authored_plan["active_work"]["chapter"])
            authored_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertEqual("PRODUCT-AUTHOR-002", authored_package["work_package"]["work_id"])
            self.assertEqual("change-log", authored_package["work_package"]["chapter"])

            omissions = {
                "background-and-problems": reason,
                "change-log": "Source review confirms the PRD contains no document revision history.",
                "functional-spec": "Source review confirms the PRD contains no separate functional specification.",
                "success-metrics": "Source review confirms the PRD contains no measurable success metrics.",
            }
            for chapter, omission_reason in omissions.items():
                _run_governance_json(
                    self,
                    [
                        "product",
                        "disposition",
                        str(target),
                        "--chapter",
                        chapter,
                        "--decision",
                        "omit-unsupported",
                        "--reason",
                        omission_reason,
                        "--reviewed",
                    ],
                )

            complete_plan = _run_governance_json(self, ["product", "plan", str(target)])
            self.assertEqual([], complete_plan["required_decisions"])
            self.assertEqual([], complete_plan["manual_authoring_tasks"])
            self.assertEqual("ready", complete_plan["active_work"]["status"])
            self.assertEqual(4, complete_plan["disposition_summary"]["omit_unsupported_count"])
            complete_package = _run_governance_json(
                self,
                ["workflow", "work-package", str(target)],
            )
            self.assertFalse(complete_package["package_available"])
            self.assertEqual("phase_action_required", complete_package["status"])
            self.assertEqual("advance-design-derivation-check", complete_package["next_action"]["id"])

    def test_product_disposition_rejects_unreviewed_unsafe_or_required_omissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n## Goals and Requirements\n\n- Build the governed workspace.\n",
                encoding="utf-8",
            )
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])
            _run_governance_json(self, ["advance", "product-structuring", str(target)])

            unreviewed = _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "omit-unsupported",
                    "--reason",
                    "The source was checked and has no background section.",
                    "--check",
                ],
                expected_returncode=1,
            )
            self.assertIn("--reviewed is required", unreviewed["errors"])

            placeholder_reason = _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "omit-unsupported",
                    "--reason",
                    "TODO",
                    "--reviewed",
                    "--check",
                ],
                expected_returncode=1,
            )
            self.assertIn("reason must be a concrete source-review explanation", placeholder_reason["errors"])

            for chapter in ("goals-and-requirements", "acceptance-criteria"):
                protected = _run_governance_json(
                    self,
                    [
                        "product",
                        "disposition",
                        str(target),
                        "--chapter",
                        chapter,
                        "--decision",
                        "omit-unsupported",
                        "--reason",
                        "The source review did not find a dedicated section for this chapter.",
                        "--reviewed",
                        "--check",
                    ],
                    expected_returncode=1,
                )
                self.assertIn(f"required product chapter cannot be omitted: {chapter}", protected["errors"])

            self.assertFalse((target / "docs/product/core/chapter-dispositions.json").exists())
            outside = Path(tmp) / "outside.txt"
            outside.write_text("do not overwrite\n", encoding="utf-8")
            disposition_temp = target / "docs/product/core/.chapter-dispositions.json.tmp"
            disposition_temp.symlink_to(outside)
            disposition_args = [
                "product",
                "disposition",
                str(target),
                "--chapter",
                "background-and-problems",
                "--decision",
                "omit-unsupported",
                "--reason",
                "Source review confirms the PRD contains no background section.",
                "--reviewed",
            ]
            unsafe_temp_check = _run_governance_json(
                self,
                [*disposition_args, "--check"],
                expected_returncode=1,
            )
            self.assertIn("temporary path already exists", "\n".join(unsafe_temp_check["errors"]))
            unsafe_temp = _run_governance_json(self, disposition_args, expected_returncode=1)
            self.assertIn("temporary path already exists", "\n".join(unsafe_temp["errors"]))
            self.assertEqual("do not overwrite\n", outside.read_text(encoding="utf-8"))
            self.assertTrue(disposition_temp.is_symlink())
            self.assertFalse((target / "docs/product/core/chapter-dispositions.json").exists())

            disposition_temp.unlink()
            product_core = target / "docs/product/core"
            outside_core = Path(tmp) / "outside-core"
            product_core.rename(outside_core)
            product_core.symlink_to(outside_core, target_is_directory=True)
            unsafe_parent = _run_governance_json(
                self,
                [*disposition_args, "--check"],
                expected_returncode=1,
            )
            self.assertIn("output parent resolves outside target", "\n".join(unsafe_parent["errors"]))
            self.assertFalse((outside_core / "chapter-dispositions.json").exists())

    def test_product_disposition_becomes_stale_when_prd_changes_and_invalid_documents_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n- Build the governed workspace.\n\n"
                "## Acceptance Criteria\n\n- The workspace verifies locally.\n",
                encoding="utf-8",
            )
            _run_governance_json(self, ["init", "--target", str(target), "--product", str(product)])
            _run_governance_json(self, ["advance", "product-structuring", str(target)])
            _run_governance_json(
                self,
                [
                    "product",
                    "disposition",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--decision",
                    "omit-unsupported",
                    "--reason",
                    "Source review confirms the PRD contains no background or problem statement.",
                    "--reviewed",
                ],
            )

            prd_path = target / "docs/product/core/PRD.md"
            prd_path.write_text(
                prd_path.read_text(encoding="utf-8") + "\n## New Product Context\n\n- A new source-backed context.\n",
                encoding="utf-8",
            )
            stale_plan = _run_governance_json(self, ["product", "plan", str(target)])
            self.assertEqual(0, stale_plan["disposition_summary"]["active_count"])
            self.assertEqual(1, stale_plan["disposition_summary"]["stale_count"])
            self.assertIn(
                "background-and-problems",
                {decision["chapter"] for decision in stale_plan["required_decisions"]},
            )
            self.assertEqual(
                "background-and-problems",
                stale_plan["stale_chapter_dispositions"][0]["chapter"],
            )
            verify_stale = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "product_chapter_disposition_stale",
                {finding["code"] for finding in verify_stale["findings"]},
            )

            disposition_path = target / "docs/product/core/chapter-dispositions.json"
            disposition_path.write_text('{"schema_version": 1, "dispositions": "invalid"}\n', encoding="utf-8")
            invalid_plan = _run_governance_json(
                self,
                ["product", "plan", str(target)],
                expected_returncode=1,
            )
            self.assertIn("product chapter disposition document dispositions must be a list", invalid_plan["errors"])
            verify_invalid = _run_governance_json(
                self,
                ["verify", str(target), "--check"],
                expected_returncode=1,
            )
            self.assertIn(
                "product_chapter_disposition_invalid",
                {finding["code"] for finding in verify_invalid["findings"]},
            )

    def test_product_plan_evidence_status_tracks_scaffolded_manual_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n",
                encoding="utf-8",
            )
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            advance_result = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_result.returncode, advance_result.stderr)
            scaffold_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "scaffold",
                    "product",
                    str(target),
                    "--chapter",
                    "background-and-problems",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_result.returncode, scaffold_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            manual_tasks = {task["chapter"]: task for task in payload["manual_authoring_tasks"]}
            background_task = manual_tasks["background-and-problems"]
            required_evidence = {item["id"]: item for item in background_task["required_evidence"]}
            self.assertTrue(required_evidence["chapter-file-authored"]["exists"])
            self.assertEqual("placeholder_present", required_evidence["chapter-file-authored"]["status"])
            self.assertEqual("satisfied", required_evidence["product-readme-indexed"]["status"])
            self.assertEqual("satisfied", required_evidence["product-meta-linked"]["status"])
            evidence_repairs = _repair_actions_by_evidence_id(background_task["evidence_repair_actions"])
            self.assertIn("chapter-file-authored", evidence_repairs)
            self.assertNotIn("product-readme-indexed", evidence_repairs)
            self.assertNotIn("product-meta-linked", evidence_repairs)
            self.assertEqual("placeholder_present", evidence_repairs["chapter-file-authored"]["status"])
            self.assertEqual(
                "replace_product_scaffold_placeholder_with_prd_backed_content",
                evidence_repairs["chapter-file-authored"]["repair_strategy"],
            )
            self.assertEqual(
                ["bin/governance", "product", "plan", ".", "--json"],
                evidence_repairs["chapter-file-authored"]["refresh_command"]["argv"],
            )

    def test_product_plan_requires_product_structuring_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n",
                encoding="utf-8",
            )
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "product", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual("initialized", payload["phase"])
            self.assertIn("product plan requires recorded phase product-structuring", payload["errors"])
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)

    def test_product_structure_fills_scaffolded_chapters_from_prd_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text(
                "# Product\n\n"
                "## Goals and Requirements\n\n"
                "- Ship a governed project from one product document.\n"
                "- Expose local governance checks after initialization.\n\n"
                "## Acceptance Criteria\n\n"
                "- The initialized repository exposes local governance checks.\n"
                "- Product chapters remain traceable to the archived PRD.\n",
                encoding="utf-8",
            )
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            advance_result = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_result.returncode, advance_result.stderr)
            scaffold_result = subprocess.run(
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
            self.assertEqual(0, scaffold_result.returncode, scaffold_result.stderr)

            check_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "product",
                    "structure",
                    str(target),
                    "--chapter",
                    "goals-and-requirements=Goals and Requirements",
                    "--chapter",
                    "acceptance-criteria=Acceptance Criteria",
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, check_result.returncode, check_result.stderr)
            check_payload = json.loads(check_result.stdout)
            self.assertTrue(check_payload["ok"])
            self.assertTrue(check_payload["check"])
            self.assertEqual([], check_payload["updated"])
            self.assertIn("docs/product/03-goals-and-requirements.md", check_payload["would_update"])
            self.assertIn("docs/product/08-acceptance-criteria.md", check_payload["would_update"])
            self.assertNotIn("local_commands", check_payload)
            self.assertIn(
                "governance:scaffold-placeholder",
                (target / "docs/product/03-goals-and-requirements.md").read_text(encoding="utf-8"),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "product",
                    "structure",
                    str(target),
                    "--chapter",
                    "goals-and-requirements=Goals and Requirements",
                    "--chapter",
                    "acceptance-criteria=Acceptance Criteria",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["check"])
            self.assertIn("docs/product/03-goals-and-requirements.md", payload["updated"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["updated"])
            self.assertIn("local_commands", payload)
            self.assertIn("next_actions", payload)

            goals = (target / "docs/product/03-goals-and-requirements.md").read_text(encoding="utf-8")
            acceptance = (target / "docs/product/08-acceptance-criteria.md").read_text(encoding="utf-8")
            self.assertNotIn("governance:scaffold-placeholder", goals)
            self.assertIn("Source: [PRD](core/PRD.md).", goals)
            self.assertIn("Ship a governed project from one product document.", goals)
            self.assertIn("## A-001 Initialized Repository Exposes Local Governance Checks", acceptance)
            self.assertIn("## A-002 Product Chapters Remain Traceable To The Archived PRD", acceptance)

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--check", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            verify_payload = json.loads(verify_result.stdout)
            self.assertTrue(verify_payload["ok"])

            design_check = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--check", "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, design_check.returncode, design_check.stderr)
            design_payload = json.loads(design_check.stdout)
            self.assertTrue(design_payload["ok"])
            self.assertTrue(design_payload["would_advance"])

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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
            self.assertFalse((target / "docs/product/03-goals-and-requirements.md").exists())
            self.assertFalse((target / "docs/product/08-acceptance-criteria.md").exists())
            self.assertEqual(readme_before, readme_path.read_text(encoding="utf-8"))
            self.assertEqual(meta_before, meta_path.read_text(encoding="utf-8"))

    def test_scaffold_product_reports_matching_phase_after_advance(self) -> None:
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
            advance = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance.returncode, advance.stderr)

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

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                {
                    "current": "product-structuring",
                    "expected": "product-structuring",
                    "matches": True,
                    "message": "recorded phase matches scaffold phase",
                },
                payload["scaffold_phase"],
            )

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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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
            self.assertEqual("design", payload["scaffold"])
            self.assertEqual(str(target), payload["target"])
            self.assertFalse(payload["check"])
            self.assertIn("scaffold design does not accept --chapter", payload["errors"])
            self.assertEqual([], payload["created"])
            self.assertEqual([], payload["skipped"])
            self.assertEqual([], payload["indexed"])
            self.assertEqual([], payload["would_create"])
            self.assertEqual([], payload["would_skip"])
            self.assertEqual([], payload["would_index"])
            self.assertEqual({}, payload["gate"])

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
            _run_governance_json(self, ["advance", "product-structuring", str(target)])
            _run_governance_json(self, ["advance", "design-derivation", str(target)])

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
            self.assertFalse(blocked_trace_requirements["delivery_plan_ready"]["ok"])
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
            _write_test_openapi(target)
            _record_all_test_design_reviews(self, target)

            allowed = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)
            allowed_payload = json.loads(allowed.stdout)
            allowed_requirements = {item["code"]: item for item in allowed_payload["requirements"]}
            self.assertTrue(allowed_payload["ok"])
            self.assertTrue(allowed_requirements["architecture_design_ready"]["ok"])
            self.assertTrue(allowed_requirements["api_contracts_ready"]["ok"])
            self.assertTrue(allowed_requirements["backend_design_ready"]["ok"])
            self.assertTrue(allowed_requirements["frontend_design_ready"]["ok"])
            self.assertTrue(allowed_requirements["verification_strategy_ready"]["ok"])
            self.assertTrue(allowed_requirements["delivery_plan_ready"]["ok"])

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
            self.assertIn(
                {
                    "make_target": "governance-status",
                    "cwd": str(target.resolve()),
                    "command": "make governance-status",
                    "argv": ["make", "governance-status"],
                    "recipe": "bin/governance status . --json",
                    "writes_state": False,
                    "approval_required": False,
                    "description": "print workflow state as JSON",
                },
                payload["local_commands"],
            )
            self.assertEqual("advance-product-structuring-check", payload["next_actions"][0]["id"])
            self.assertEqual(str(target.resolve()), payload["next_actions"][0]["cwd"])
            self.assertEqual(
                {
                    "current": "initialized",
                    "expected": "design-derivation",
                    "matches": False,
                    "message": (
                        "recorded phase is not design-derivation; "
                        "use returned next_actions to advance phases in order"
                    ),
                },
                payload["scaffold_phase"],
            )
            blockers = {
                blocker["path"]: blocker
                for blocker in payload["next_actions_blocked_by"]
            }
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", blockers)
            self.assertIn("docs/development/03-verification-log.md", blockers)
            self.assertEqual(
                "governance_scaffold_placeholder",
                blockers["docs/api/endpoints/01-endpoint-contract.md"]["code"],
            )
            self.assertIn("before running next_actions", blockers["docs/api/endpoints/01-endpoint-contract.md"]["message"])
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
            self.assertIn("METHOD /product-derived-path", endpoint_contract)
            self.assertIn("| Field | Type | Required | Source | Notes |", endpoint_contract)
            self.assertIn("[Error registry](../error-codes.md)", endpoint_contract)
            self.assertIn("[Acceptance](../../product/NN-acceptance.md#a-nnn)", endpoint_contract)
            self.assertIn("[API consumption](../../frontend/02-api-consumption.md)", endpoint_contract)
            self.assertIn("governance:scaffold-placeholder", endpoint_contract)
            self.assertIn("| Acceptance | Design | API | Test |", acceptance_matrix)
            self.assertIn("[A-NNN](../product/NN-acceptance.md#a-nnn)", acceptance_matrix)
            self.assertIn("[Endpoint](../api/endpoints/NN-endpoint.md)", acceptance_matrix)
            self.assertIn("| ID | Status | Milestone |", roadmap)
            self.assertIn("Product-derived milestone linked to acceptance/design scope", roadmap)
            self.assertIn("| ID | Status | Task | Product | Design | API | Acceptance | Verification |", task_board)
            self.assertIn("[Product](../product/NN-scope.md)", task_board)
            self.assertIn("[Verification plan](03-verification-log.md#task-nnn)", task_board)
            self.assertIn("Allowed statuses: Backlog, Ready, In Progress, Blocked, Done, Deferred.", task_board)
            self.assertIn("| Task | Command | Result | Date | Notes |", verification_log)
            self.assertIn("evidence notes and artifact links", verification_log)
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
            self.assertFalse(requirements["api_contracts_ready"]["ok"])
            self.assertFalse(requirements["delivery_plan_ready"]["ok"])

    def test_design_plan_routes_scaffold_blockers_to_authoritative_skills(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold.returncode, scaffold.stderr)

            plan = subprocess.run(
                [sys.executable, str(CLI), "design", "plan", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, plan.returncode, plan.stderr)
            payload = json.loads(plan.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("workflows/04-design-derivation.md", payload["workflow"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertIn("docs/product/core/PRD.md", payload["source_documents"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["source_documents"])
            self.assertIn("docs/unresolved.md", payload["source_documents"])
            self.assertIn("docs/glossary.md", payload["source_documents"])
            track_ids = [track["id"] for track in payload["tracks"]]
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
                track_ids,
            )
            tracks = {track["id"]: track for track in payload["tracks"]}
            self.assertEqual(1, tracks["architecture"]["sequence"])
            self.assertEqual("designing-system-architecture", tracks["architecture"]["primary_skill"])
            self.assertEqual("senior-architect", tracks["architecture"]["primary_specialist_skill"])
            self.assertIn("senior-architect", tracks["architecture"]["specialist_skills"])
            self.assertIn("senior-security", tracks["architecture"]["specialist_skills"])
            self.assertEqual(3, tracks["api-contracts"]["sequence"])
            self.assertEqual("designing-api-contracts", tracks["api-contracts"]["primary_skill"])
            self.assertEqual("api-design-reviewer", tracks["api-contracts"]["primary_specialist_skill"])
            self.assertEqual("authoring_blocked", tracks["api-contracts"]["status"])
            self.assertIn("designing-api-contracts", tracks["api-contracts"]["skills"])
            self.assertIn("api-design-reviewer", tracks["api-contracts"]["specialist_skills"])
            self.assertIn("senior-security", tracks["api-contracts"]["specialist_skills"])
            api_requirements = _requirements_by_name(tracks["api-contracts"]["skill_requirements"])
            self.assertEqual("local-workflow", api_requirements["designing-api-contracts"]["type"])
            self.assertTrue(api_requirements["designing-api-contracts"]["available_in_workflow_pack"])
            self.assertEqual("workflow-pack", api_requirements["designing-api-contracts"]["availability_scope"])
            self.assertEqual(
                "docs/agent-workflow/workflow-pack/skills/designing-api-contracts/SKILL.md",
                api_requirements["designing-api-contracts"]["path"],
            )
            self.assertEqual(
                "workflow_pack_integrity_error",
                api_requirements["designing-api-contracts"]["missing_policy"],
            )
            self.assertEqual("authority-routing", api_requirements["api-design-reviewer"]["type"])
            self.assertFalse(api_requirements["api-design-reviewer"]["available_in_workflow_pack"])
            self.assertEqual("agent-environment", api_requirements["api-design-reviewer"]["availability_scope"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                api_requirements["api-design-reviewer"]["missing_policy"],
            )
            api_authority_requirements = _requirements_by_name(
                tracks["api-contracts"]["authority_skill_requirements"]
            )
            self.assertIn("api-design-reviewer", api_authority_requirements)
            self.assertNotIn("designing-api-contracts", api_authority_requirements)
            api_loading_plan = tracks["api-contracts"]["skill_loading_plan"]
            self.assertEqual("local_workflow_then_authority_routing", api_loading_plan["load_order"])
            self.assertEqual(
                "missing_required_local_workflow_skill_or_unavailable_authority_routing_skill",
                api_loading_plan["stop_condition"],
            )
            self.assertEqual(
                ["designing-api-contracts", "api-design-reviewer", "senior-backend", "senior-security"],
                [step["name"] for step in api_loading_plan["steps"]],
            )
            self.assertEqual("load_local_workflow_skill", api_loading_plan["steps"][0]["action"])
            self.assertEqual("workflow-pack", api_loading_plan["steps"][0]["load_from"])
            self.assertTrue(api_loading_plan["steps"][0]["available_in_workflow_pack"])
            self.assertEqual("load_authority_routing_skill", api_loading_plan["steps"][1]["action"])
            self.assertEqual("agent-environment", api_loading_plan["steps"][1]["load_from"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                api_loading_plan["steps"][1]["missing_policy"],
            )
            self.assertTrue(api_loading_plan["local_workflow_all_available"])
            self.assertTrue(api_loading_plan["authority_routing_requires_agent_environment"])
            self.assertIn("references/api-design-checklist.md", tracks["api-contracts"]["references"])
            self.assertIn("references/security-design-checklist.md", tracks["api-contracts"]["references"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", tracks["api-contracts"]["documents"])
            api_steps = tracks["api-contracts"]["steps"]
            self.assertEqual(
                [
                    "load-track-skills",
                    "read-product-sources",
                    "read-track-references",
                    "author-track-documents",
                    "verify-track",
                    "refresh-design-plan",
                ],
                [step["id"] for step in api_steps],
            )
            self.assertEqual(list(range(1, 7)), [step["sequence"] for step in api_steps])
            self.assertEqual("skill-load", api_steps[0]["kind"])
            self.assertIn("designing-api-contracts", api_steps[0]["skills"])
            self.assertIn("api-design-reviewer", api_steps[0]["specialist_skills"])
            api_step_requirements = _requirements_by_name(api_steps[0]["skill_requirements"])
            self.assertEqual("local-workflow", api_step_requirements["designing-api-contracts"]["type"])
            self.assertEqual("authority-routing", api_step_requirements["api-design-reviewer"]["type"])
            self.assertEqual(
                ["designing-api-contracts", "api-design-reviewer", "senior-backend", "senior-security"],
                [step["name"] for step in api_steps[0]["skill_loading_plan"]["steps"]],
            )
            self.assertEqual("read", api_steps[1]["kind"])
            self.assertIn("docs/product/core/PRD.md", api_steps[1]["documents"])
            self.assertIn("docs/product/08-acceptance-criteria.md", api_steps[1]["documents"])
            self.assertEqual("read", api_steps[2]["kind"])
            self.assertIn("references/api-design-checklist.md", api_steps[2]["references"])
            self.assertEqual("author", api_steps[3]["kind"])
            self.assertIn("docs/api/endpoints/01-endpoint-contract.md", api_steps[3]["documents"])
            self.assertEqual("command", api_steps[4]["kind"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], api_steps[4]["argv"])
            self.assertFalse(api_steps[4]["writes_state"])
            self.assertFalse(api_steps[4]["approval_required"])
            self.assertEqual("command", api_steps[5]["kind"])
            self.assertEqual(["bin/governance", "design", "plan", ".", "--json"], api_steps[5]["argv"])
            self.assertTrue(
                any(
                    blocker["path"] == "docs/api/endpoints/01-endpoint-contract.md"
                    and blocker["code"] == "governance_scaffold_placeholder"
                    for blocker in tracks["api-contracts"]["blockers"]
                )
            )
            self.assertIn("designing-backend-modules", tracks["backend-modules"]["skills"])
            self.assertIn("senior-backend", tracks["backend-modules"]["specialist_skills"])
            self.assertIn("observability-designer", tracks["backend-modules"]["specialist_skills"])
            self.assertIn("slo-architect", tracks["backend-modules"]["specialist_skills"])
            self.assertIn("references/backend-operability-checklist.md", tracks["backend-modules"]["references"])
            self.assertEqual("senior-backend", tracks["backend-modules"]["primary_specialist_skill"])
            self.assertIn("designing-data-models", tracks["data-model"]["skills"])
            self.assertEqual("database-designer", tracks["data-model"]["primary_specialist_skill"])
            self.assertIn("database-schema-designer", tracks["data-model"]["specialist_skills"])
            self.assertIn("references/data-model-design-checklist.md", tracks["data-model"]["references"])
            self.assertEqual(
                [
                    "designing-data-models",
                    "database-designer",
                    "database-schema-designer",
                    "migration-architect",
                    "senior-backend",
                    "senior-security",
                ],
                [step["name"] for step in tracks["data-model"]["skill_loading_plan"]["steps"]],
            )

    def test_design_api_candidates_extracts_acceptance_inputs_without_guessing_contracts(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "api-candidates", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("api-contracts", payload["track"])
            self.assertIn("designing-api-contracts", payload["skills"])
            self.assertIn("api-design-reviewer", payload["specialist_skills"])
            self.assertIn("senior-security", payload["specialist_skills"])
            self.assertIn("references/api-design-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["candidates"]))
            candidate = payload["candidates"][0]
            self.assertEqual("API-001", candidate["candidate_id"])
            self.assertEqual("A-001", candidate["acceptance_id"])
            self.assertEqual("Goal Flow", candidate["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md", candidate["source"]["path"])
            self.assertEqual("a-001-goal-flow", candidate["source"]["anchor"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", candidate["source"]["reference"])
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", candidate["suggested_endpoint_file"])
            self.assertFalse(candidate["endpoint_exists"])
            self.assertIn("method_path", candidate["open_decisions"])
            self.assertIn("request_fields", candidate["open_decisions"])
            self.assertIn("response_fields", candidate["open_decisions"])
            self.assertIn("frontend_consumers", candidate["open_decisions"])

    def test_design_architecture_authoring_builds_system_design_task_queue_without_guessing_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _design_scaffold_target(self, tmp)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "architecture-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("architecture", payload["track"])
            self.assertEqual("do_not_guess_architecture_boundaries", payload["decision_policy"])
            self.assertEqual(["designing-system-architecture"], payload["skills"])
            self.assertIn("senior-architect", payload["specialist_skills"])
            self.assertIn("senior-security", payload["specialist_skills"])
            self.assertIn("observability-designer", payload["specialist_skills"])
            self.assertIn("slo-architect", payload["specialist_skills"])
            payload_requirements = _requirements_by_name(payload["skill_requirements"])
            self.assertEqual("local-workflow", payload_requirements["designing-system-architecture"]["type"])
            self.assertEqual("authority-routing", payload_requirements["senior-architect"]["type"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                payload_requirements["senior-architect"]["missing_policy"],
            )
            self.assertEqual(
                [
                    "designing-system-architecture",
                    "senior-architect",
                    "senior-security",
                    "observability-designer",
                    "slo-architect",
                ],
                [step["name"] for step in payload["skill_loading_plan"]["steps"]],
            )
            self.assertIn("references/architecture-methods.md", payload["references"])
            self.assertIn("references/architecture-quality-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(
                {
                    "task_count": 1,
                    "document_status_counts": {
                        "placeholder_present": 3,
                    },
                    "non_authored_document_count": 3,
                    "open_decision_count": 11,
                    "required_link_status_counts": {
                        "satisfied": 4,
                    },
                    "non_satisfied_required_link_count": 0,
                    "link_repair_action_count": 0,
                },
                payload["authoring_summary"],
            )
            self.assertEqual("ARCHITECTURE-AUTHOR-001", payload["active_work"]["task_id"])
            self.assertEqual("authoring_required", payload["active_work"]["status"])
            self.assertEqual("senior-architect", payload["active_work"]["primary_specialist_skill"])
            self.assertEqual("system_boundary", payload["active_work"]["next_open_decision"])
            self.assertEqual(
                ["bin/governance", "design", "architecture-authoring", ".", "--json"],
                payload["active_work"]["refresh_command"]["argv"],
            )
            task = payload["authoring_tasks"][0]
            self.assertEqual("ARCHITECTURE-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("architecture-design-authoring", task["execution"]["stage"])
            self.assertEqual("designing-system-architecture", task["execution"]["primary_skill"])
            self.assertEqual("senior-architect", task["execution"]["primary_specialist_skill"])
            self.assertEqual("verify-architecture-authoring", task["execution"]["verify_step"])
            self.assertEqual("refresh-architecture-authoring", task["execution"]["refresh_step"])
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(
                [
                    "docs/architecture/01-system-context.md",
                    "docs/architecture/02-containers.md",
                    "docs/architecture/03-quality-attributes.md",
                ],
                document_paths,
            )
            self.assertIn("Actors", task["documents"][0]["sections"])
            self.assertIn("Runtime Responsibilities", task["documents"][1]["sections"])
            self.assertIn("Tradeoffs", task["documents"][2]["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual("docs/product/core/PRD.md", required_links["product_prd"])
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/glossary.md", required_links["glossary"])
            self.assertEqual("docs/unresolved.md", required_links["unresolved_decisions"])
            self.assertEqual(
                {
                    "product_prd": "satisfied",
                    "product_acceptance": "satisfied",
                    "glossary": "satisfied",
                    "unresolved_decisions": "satisfied",
                },
                _link_statuses(task["required_links"]),
            )
            self.assertEqual([], task["link_repair_actions"])
            self.assertIn("system_boundary", task["open_decisions"])
            self.assertIn("container_responsibilities", task["open_decisions"])
            self.assertIn("quality_scenarios", task["open_decisions"])
            self.assertIn("deployment_assumptions", task["open_decisions"])
            self.assertIn("adr_candidates", task["open_decisions"])
            self.assertEqual(
                [
                    "load-architecture-design-skills",
                    "read-architecture-references",
                    "read-product-sources",
                    "author-system-context",
                    "author-containers",
                    "author-quality-attributes",
                    "link-acceptance-and-decisions",
                    "verify-architecture-authoring",
                    "refresh-architecture-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 10)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["designing-system-architecture"], task["steps"][0]["skills"])
            self.assertIn("senior-architect", task["steps"][0]["specialist_skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][7]["argv"])
            self.assertFalse(task["steps"][7]["writes_state"])
            self.assertEqual(
                ["bin/governance", "design", "architecture-authoring", ".", "--json"],
                task["steps"][8]["argv"],
            )
            self.assertNotIn("containers", task)
            self.assertNotIn("database", task)
            self.assertNotIn("deployment_topology", task)

    def test_design_api_authoring_builds_contract_task_queue_without_guessing_contracts(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold_design = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_design.returncode, scaffold_design.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "api-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("api-contracts", payload["track"])
            self.assertEqual("do_not_guess_contract_details", payload["decision_policy"])
            self.assertIn("designing-api-contracts", payload["skills"])
            self.assertIn("api-design-reviewer", payload["specialist_skills"])
            payload_requirements = _requirements_by_name(payload["skill_requirements"])
            self.assertEqual("local-workflow", payload_requirements["designing-api-contracts"]["type"])
            self.assertTrue(payload_requirements["designing-api-contracts"]["available_in_workflow_pack"])
            self.assertEqual("authority-routing", payload_requirements["api-design-reviewer"]["type"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                payload_requirements["api-design-reviewer"]["missing_policy"],
            )
            self.assertEqual(
                ["designing-api-contracts", "api-design-reviewer", "senior-backend", "senior-security"],
                [step["name"] for step in payload["skill_loading_plan"]["steps"]],
            )
            self.assertIn("references/api-design-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(
                {
                    "task_count": 1,
                    "document_status_counts": {
                        "missing": 2,
                        "placeholder_present": 3,
                    },
                    "non_authored_document_count": 5,
                    "open_decision_count": 8,
                    "required_link_status_counts": {
                        "placeholder_present": 4,
                        "satisfied": 2,
                    },
                    "non_satisfied_required_link_count": 4,
                    "link_repair_action_count": 4,
                },
                payload["authoring_summary"],
            )
            self.assertEqual("API-AUTHOR-001", payload["active_work"]["task_id"])
            self.assertEqual("design-authoring-task", payload["active_work"]["kind"])
            self.assertEqual("authoring_required", payload["active_work"]["status"])
            self.assertEqual("api-design-reviewer", payload["active_work"]["primary_specialist_skill"])
            self.assertEqual("error_registry", payload["active_work"]["next_required_link"]["kind"])
            self.assertEqual("method_path", payload["active_work"]["next_open_decision"])
            self.assertEqual(
                "docs/api/00-conventions.md",
                payload["active_work"]["next_repair_action"]["target"],
            )
            self.assertEqual(
                ["bin/governance", "verify", ".", "--check", "--json"],
                payload["active_work"]["verify_command"]["argv"],
            )
            self.assertEqual(
                ["bin/governance", "design", "api-authoring", ".", "--json"],
                payload["active_work"]["refresh_command"]["argv"],
            )
            self.assertEqual(1, len(payload["authoring_tasks"]))
            task = payload["authoring_tasks"][0]
            self.assertEqual("API-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual(
                {
                    "stage": "api-contract-authoring",
                    "primary_skill": "designing-api-contracts",
                    "primary_specialist_skill": "api-design-reviewer",
                    "verify_step": "verify-api-authoring",
                    "refresh_step": "refresh-api-authoring",
                    "stop_condition": "open_decisions_unresolved_or_required_links_missing",
                },
                task["execution"],
            )
            self.assertEqual("API-001", task["candidate_id"])
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", task["endpoint_file"])
            self.assertEqual("docs/api/endpoints/01-endpoint-contract.md", task["replaceable_starter_endpoint"])
            self.assertIn("api-design-reviewer", task["specialist_skills"])
            task_requirements = _requirements_by_name(task["skill_requirements"])
            self.assertEqual("local-workflow", task_requirements["designing-api-contracts"]["type"])
            self.assertEqual("authority-routing", task_requirements["api-design-reviewer"]["type"])
            self.assertEqual(
                ["designing-api-contracts", "api-design-reviewer", "senior-backend", "senior-security"],
                [step["name"] for step in task["skill_loading_plan"]["steps"]],
            )
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(
                [
                    "docs/api/00-conventions.md",
                    "docs/api/error-codes.md",
                    "docs/api/changelog.md",
                    "docs/api/endpoints/01-goal-flow.md",
                    "docs/api/openapi.json",
                ],
                document_paths,
            )
            endpoint_doc = task["documents"][3]
            self.assertIn("Method and Path", endpoint_doc["sections"])
            self.assertIn("Frontend Consumers", endpoint_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/api/error-codes.md", required_links["error_registry"])
            self.assertEqual("docs/backend/01-modules.md", required_links["backend_owner"])
            self.assertEqual("docs/frontend/02-api-consumption.md", required_links["frontend_consumers"])
            self.assertEqual("docs/tests/02-acceptance-matrix.md", required_links["acceptance_matrix"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("placeholder_present", required_link_statuses["error_registry"])
            self.assertEqual("placeholder_present", required_link_statuses["backend_owner"])
            self.assertEqual("placeholder_present", required_link_statuses["frontend_consumers"])
            self.assertEqual("placeholder_present", required_link_statuses["acceptance_matrix"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            repair_actions = _repair_actions_by_link_kind(task["link_repair_actions"])
            self.assertNotIn("product_acceptance", repair_actions)
            self.assertEqual("placeholder_present", repair_actions["backend_owner"]["status"])
            self.assertEqual(
                "replace_scaffold_placeholder_with_source_backed_content",
                repair_actions["backend_owner"]["repair_strategy"],
            )
            self.assertFalse(repair_actions["backend_owner"]["can_auto_apply"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], repair_actions["backend_owner"]["verify_command"]["argv"])
            self.assertEqual(
                ["bin/governance", "design", "api-authoring", ".", "--json"],
                repair_actions["backend_owner"]["refresh_command"]["argv"],
            )
            self.assertIn("method_path", task["open_decisions"])
            self.assertIn("auth", task["open_decisions"])
            self.assertIn("request_fields", task["open_decisions"])
            self.assertIn("response_fields", task["open_decisions"])
            self.assertIn("frontend_consumers", task["open_decisions"])
            self.assertEqual(
                [
                    "load-api-contract-skill",
                    "read-api-references",
                    "read-source-acceptance",
                    "fill-shared-api-documents",
                    "author-endpoint-contract",
                    "author-openapi-contract",
                    "link-consumers-and-owners",
                    "update-acceptance-matrix",
                    "verify-api-authoring",
                    "refresh-api-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 11)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["designing-api-contracts"], task["steps"][0]["skills"])
            self.assertIn("api-design-reviewer", task["steps"][0]["specialist_skills"])
            step_requirements = _requirements_by_name(task["steps"][0]["skill_requirements"])
            self.assertEqual("local-workflow", step_requirements["designing-api-contracts"]["type"])
            self.assertEqual("authority-routing", step_requirements["api-design-reviewer"]["type"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][8]["argv"])
            self.assertFalse(task["steps"][8]["writes_state"])
            self.assertEqual(["bin/governance", "design", "api-authoring", ".", "--json"], task["steps"][9]["argv"])
            self.assertNotIn("method", task)
            self.assertNotIn("path", task)
            self.assertNotIn("request_schema", task)
            self.assertNotIn("response_schema", task)

    def test_design_backend_authoring_builds_module_task_queue_without_guessing_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _design_scaffold_target(self, tmp)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "backend-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("backend-modules", payload["track"])
            self.assertEqual("do_not_guess_backend_boundaries", payload["decision_policy"])
            self.assertIn("designing-backend-modules", payload["skills"])
            self.assertNotIn("designing-data-models", payload["skills"])
            self.assertIn("senior-backend", payload["specialist_skills"])
            self.assertIn("observability-designer", payload["specialist_skills"])
            self.assertIn("slo-architect", payload["specialist_skills"])
            self.assertNotIn("database-schema-designer", payload["specialist_skills"])
            payload_requirements = _requirements_by_name(payload["skill_requirements"])
            self.assertEqual("local-workflow", payload_requirements["designing-backend-modules"]["type"])
            self.assertNotIn("designing-data-models", payload_requirements)
            self.assertEqual("authority-routing", payload_requirements["senior-backend"]["type"])
            self.assertEqual("authority-routing", payload_requirements["observability-designer"]["type"])
            self.assertIn("references/backend-design-checklist.md", payload["references"])
            self.assertIn("references/backend-operability-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["authoring_tasks"]))
            self.assertEqual("BACKEND-AUTHOR-001", payload["active_work"]["task_id"])
            self.assertEqual("authoring_required", payload["active_work"]["status"])
            self.assertEqual("senior-backend", payload["active_work"]["primary_specialist_skill"])
            self.assertEqual("architecture_context", payload["active_work"]["next_required_link"]["kind"])
            self.assertEqual("module_boundaries", payload["active_work"]["next_open_decision"])
            self.assertEqual(
                ["bin/governance", "design", "backend-authoring", ".", "--json"],
                payload["active_work"]["refresh_command"]["argv"],
            )
            task = payload["authoring_tasks"][0]
            self.assertEqual("BACKEND-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("backend-design-authoring", task["execution"]["stage"])
            self.assertEqual("designing-backend-modules", task["execution"]["primary_skill"])
            self.assertEqual("senior-backend", task["execution"]["primary_specialist_skill"])
            self.assertEqual("verify-backend-authoring", task["execution"]["verify_step"])
            self.assertEqual("refresh-backend-authoring", task["execution"]["refresh_step"])
            self.assertEqual(
                "open_decisions_unresolved_or_required_links_missing",
                task["execution"]["stop_condition"],
            )
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            self.assertIn("senior-backend", task["specialist_skills"])
            self.assertIn("observability-designer", task["specialist_skills"])
            self.assertIn("slo-architect", task["specialist_skills"])
            self.assertNotIn("database-schema-designer", task["specialist_skills"])
            task_requirements = _requirements_by_name(task["skill_requirements"])
            self.assertEqual("local-workflow", task_requirements["designing-backend-modules"]["type"])
            self.assertNotIn("designing-data-models", task_requirements)
            self.assertEqual("authority-routing", task_requirements["senior-backend"]["type"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                task_requirements["senior-backend"]["missing_policy"],
            )
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(
                [
                    "docs/backend/01-modules.md",
                    "docs/backend/03-external-services.md",
                ],
                document_paths,
            )
            module_doc = task["documents"][0]
            self.assertIn("Modules", module_doc["sections"])
            self.assertIn("API Ownership", module_doc["sections"])
            dependency_doc = task["documents"][1]
            self.assertIn("Retries", dependency_doc["sections"])
            self.assertIn("Observability", dependency_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/architecture/02-containers.md", required_links["architecture_containers"])
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", required_links["api_contract"])
            self.assertEqual("docs/backend/02-data-model.md", required_links["data_model"])
            self.assertEqual("docs/tests/01-strategy.md", required_links["test_strategy"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("placeholder_present", required_link_statuses["architecture_containers"])
            self.assertEqual("missing", required_link_statuses["api_contract"])
            self.assertEqual("placeholder_present", required_link_statuses["data_model"])
            self.assertEqual("placeholder_present", required_link_statuses["test_strategy"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            repair_actions = _repair_actions_by_link_kind(task["link_repair_actions"])
            self.assertEqual("missing", repair_actions["api_contract"]["status"])
            self.assertEqual(
                "create_or_restore_required_local_markdown_source_before_authoring_downstream_content",
                repair_actions["api_contract"]["repair_strategy"],
            )
            self.assertEqual(
                ["bin/governance", "design", "backend-authoring", ".", "--json"],
                repair_actions["api_contract"]["refresh_command"]["argv"],
            )
            self.assertIn("module_boundaries", task["open_decisions"])
            self.assertIn("api_ownership", task["open_decisions"])
            self.assertIn("data_ownership", task["open_decisions"])
            self.assertNotIn("transaction_boundaries", task["open_decisions"])
            self.assertIn("observability", task["open_decisions"])
            self.assertEqual(
                [
                    "load-backend-design-skills",
                    "read-backend-references",
                    "read-source-acceptance",
                    "read-architecture-and-api-sources",
                    "author-backend-modules",
                    "author-external-services",
                    "link-tests-and-acceptance",
                    "verify-backend-authoring",
                    "refresh-backend-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 10)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["designing-backend-modules"], task["steps"][0]["skills"])
            self.assertIn("senior-backend", task["steps"][0]["specialist_skills"])
            self.assertIn("slo-architect", task["steps"][0]["specialist_skills"])
            self.assertNotIn("database-schema-designer", task["steps"][0]["specialist_skills"])
            step_requirements = _requirements_by_name(task["steps"][0]["skill_requirements"])
            self.assertEqual("authority-routing", step_requirements["senior-backend"]["type"])
            self.assertEqual(
                [
                    "designing-backend-modules",
                    "senior-backend",
                    "observability-designer",
                    "slo-architect",
                    "senior-security",
                ],
                [step["name"] for step in task["skill_loading_plan"]["steps"]],
            )
            self.assertEqual(
                "missing_required_local_workflow_skill_or_unavailable_authority_routing_skill",
                task["skill_loading_plan"]["stop_condition"],
            )
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][7]["argv"])
            self.assertFalse(task["steps"][7]["writes_state"])
            self.assertEqual(["bin/governance", "design", "backend-authoring", ".", "--json"], task["steps"][8]["argv"])
            self.assertNotIn("module_name", task)
            self.assertNotIn("table_name", task)
            self.assertNotIn("fields", task)

    def test_design_data_model_authoring_builds_persistence_task_queue_without_guessing_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _design_scaffold_target(self, tmp)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "data-model-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("data-model", payload["track"])
            self.assertEqual("do_not_guess_data_model", payload["decision_policy"])
            self.assertEqual(["designing-data-models"], payload["skills"])
            self.assertIn("database-designer", payload["specialist_skills"])
            self.assertIn("database-schema-designer", payload["specialist_skills"])
            self.assertIn("migration-architect", payload["specialist_skills"])
            self.assertIn("senior-backend", payload["specialist_skills"])
            self.assertIn("senior-security", payload["specialist_skills"])
            payload_requirements = _requirements_by_name(payload["skill_requirements"])
            self.assertEqual("local-workflow", payload_requirements["designing-data-models"]["type"])
            self.assertEqual("authority-routing", payload_requirements["database-designer"]["type"])
            self.assertEqual("authority-routing", payload_requirements["database-schema-designer"]["type"])
            self.assertEqual("authority-routing", payload_requirements["migration-architect"]["type"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                payload_requirements["database-designer"]["missing_policy"],
            )
            self.assertIn("references/backend-design-checklist.md", payload["references"])
            self.assertIn("references/data-model-design-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["authoring_tasks"]))
            self.assertEqual("DATA-MODEL-AUTHOR-001", payload["active_work"]["task_id"])
            self.assertEqual("authoring_required", payload["active_work"]["status"])
            self.assertEqual("database-designer", payload["active_work"]["primary_specialist_skill"])
            self.assertEqual("architecture_containers", payload["active_work"]["next_required_link"]["kind"])
            self.assertEqual("entity_ownership", payload["active_work"]["next_open_decision"])
            self.assertEqual(
                ["bin/governance", "design", "data-model-authoring", ".", "--json"],
                payload["active_work"]["refresh_command"]["argv"],
            )
            task = payload["authoring_tasks"][0]
            self.assertEqual("DATA-MODEL-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("data-model-authoring", task["execution"]["stage"])
            self.assertEqual("designing-data-models", task["execution"]["primary_skill"])
            self.assertEqual("database-designer", task["execution"]["primary_specialist_skill"])
            self.assertEqual("verify-data-model-authoring", task["execution"]["verify_step"])
            self.assertEqual("refresh-data-model-authoring", task["execution"]["refresh_step"])
            self.assertEqual(
                "open_decisions_unresolved_or_required_links_missing",
                task["execution"]["stop_condition"],
            )
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(["docs/backend/02-data-model.md"], document_paths)
            data_doc = task["documents"][0]
            self.assertIn("Entities", data_doc["sections"])
            self.assertIn("State Machines", data_doc["sections"])
            self.assertIn("Indexes", data_doc["sections"])
            self.assertIn("Migrations", data_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/architecture/02-containers.md", required_links["architecture_containers"])
            self.assertEqual("docs/backend/01-modules.md", required_links["backend_modules"])
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", required_links["api_contract"])
            self.assertEqual("docs/tests/01-strategy.md", required_links["test_strategy"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("placeholder_present", required_link_statuses["architecture_containers"])
            self.assertEqual("placeholder_present", required_link_statuses["backend_modules"])
            self.assertEqual("missing", required_link_statuses["api_contract"])
            self.assertEqual("placeholder_present", required_link_statuses["test_strategy"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            repair_actions = _repair_actions_by_link_kind(task["link_repair_actions"])
            self.assertEqual("missing", repair_actions["api_contract"]["status"])
            self.assertEqual(
                ["bin/governance", "design", "data-model-authoring", ".", "--json"],
                repair_actions["api_contract"]["refresh_command"]["argv"],
            )
            self.assertIn("entity_ownership", task["open_decisions"])
            self.assertIn("idempotency_constraints", task["open_decisions"])
            self.assertIn("transaction_boundaries", task["open_decisions"])
            self.assertIn("migration_order", task["open_decisions"])
            self.assertIn("rollback_strategy", task["open_decisions"])
            self.assertEqual(
                [
                    "load-data-model-design-skills",
                    "read-data-model-references",
                    "read-source-acceptance",
                    "read-backend-and-api-sources",
                    "author-data-model",
                    "link-tests-and-acceptance",
                    "verify-data-model-authoring",
                    "refresh-data-model-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 9)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["designing-data-models"], task["steps"][0]["skills"])
            self.assertIn("database-schema-designer", task["steps"][0]["specialist_skills"])
            self.assertIn("migration-architect", task["steps"][0]["specialist_skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][6]["argv"])
            self.assertFalse(task["steps"][6]["writes_state"])
            self.assertEqual(["bin/governance", "design", "data-model-authoring", ".", "--json"], task["steps"][7]["argv"])
            self.assertNotIn("table_name", task)
            self.assertNotIn("fields", task)
            self.assertNotIn("migration_sql", task)

    def test_design_ui_and_frontend_authoring_queues_split_interaction_from_modules(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold_design = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_design.returncode, scaffold_design.stderr)

            ui_result = subprocess.run(
                [sys.executable, str(CLI), "design", "ui-interaction-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, ui_result.returncode, ui_result.stderr)
            payload = json.loads(ui_result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("ui-interaction", payload["track"])
            self.assertEqual("do_not_guess_ui_behavior", payload["decision_policy"])
            self.assertIn("designing-ui-interactions", payload["skills"])
            self.assertNotIn("designing-frontend-modules", payload["skills"])
            self.assertIn("senior-frontend", payload["specialist_skills"])
            self.assertIn("a11y-audit", payload["specialist_skills"])
            self.assertNotIn("performance-profiler", payload["specialist_skills"])
            self.assertIn("references/frontend-interaction-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["authoring_tasks"]))
            task = payload["authoring_tasks"][0]
            self.assertEqual("UI-INTERACTION-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("ui-interaction-authoring", task["execution"]["stage"])
            self.assertEqual("designing-ui-interactions", task["execution"]["primary_skill"])
            self.assertEqual("senior-frontend", task["execution"]["primary_specialist_skill"])
            self.assertEqual("verify-ui-interaction-authoring", task["execution"]["verify_step"])
            self.assertEqual("refresh-ui-interaction-authoring", task["execution"]["refresh_step"])
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            self.assertIn("senior-frontend", task["specialist_skills"])
            self.assertIn("a11y-audit", task["specialist_skills"])
            self.assertNotIn("performance-profiler", task["specialist_skills"])
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(
                ["docs/ui/01-interaction-model.md"],
                document_paths,
            )
            ui_doc = task["documents"][0]
            self.assertIn("Primary Flows", ui_doc["sections"])
            self.assertIn("Screens", ui_doc["sections"])
            self.assertIn("States", ui_doc["sections"])
            self.assertIn("Errors", ui_doc["sections"])
            self.assertIn("Accessibility", ui_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual("docs/product/core/PRD.md", required_links["product_prd"])
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/glossary.md", required_links["glossary"])
            self.assertEqual("docs/unresolved.md", required_links["unresolved_decisions"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_prd"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("satisfied", required_link_statuses["glossary"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            self.assertIn("primary_flows", task["open_decisions"])
            self.assertIn("screens", task["open_decisions"])
            self.assertIn("states", task["open_decisions"])
            self.assertIn("error_actions", task["open_decisions"])
            self.assertIn("accessibility", task["open_decisions"])
            self.assertIn("copy_and_content", task["open_decisions"])
            self.assertEqual(
                [
                    "load-ui-interaction-design-skills",
                    "read-ui-interaction-references",
                    "read-product-sources",
                    "author-ui-interaction-model",
                    "link-acceptance-and-decisions",
                    "verify-ui-interaction-authoring",
                    "refresh-ui-interaction-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 8)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["designing-ui-interactions"], task["steps"][0]["skills"])
            self.assertIn("senior-frontend", task["steps"][0]["specialist_skills"])
            self.assertIn("a11y-audit", task["steps"][0]["specialist_skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][5]["argv"])
            self.assertFalse(task["steps"][5]["writes_state"])
            self.assertEqual(["bin/governance", "design", "ui-interaction-authoring", ".", "--json"], task["steps"][6]["argv"])

            frontend_result = subprocess.run(
                [sys.executable, str(CLI), "design", "frontend-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, frontend_result.returncode, frontend_result.stderr)
            frontend_payload = json.loads(frontend_result.stdout)
            self.assertTrue(frontend_payload["ok"])
            self.assertEqual("frontend-modules", frontend_payload["track"])
            self.assertEqual("do_not_guess_frontend_behavior", frontend_payload["decision_policy"])
            self.assertNotIn("designing-ui-interactions", frontend_payload["skills"])
            self.assertIn("designing-frontend-modules", frontend_payload["skills"])
            self.assertIn("performance-profiler", frontend_payload["specialist_skills"])
            frontend_task = frontend_payload["authoring_tasks"][0]
            self.assertEqual("FRONTEND-AUTHOR-001", frontend_task["task_id"])
            self.assertEqual("designing-frontend-modules", frontend_task["execution"]["primary_skill"])
            self.assertEqual("verify-frontend-authoring", frontend_task["execution"]["verify_step"])
            frontend_document_paths = [document["path"] for document in frontend_task["documents"]]
            self.assertEqual(
                ["docs/frontend/01-modules.md", "docs/frontend/02-api-consumption.md"],
                frontend_document_paths,
            )
            self.assertIn("docs/ui/01-interaction-model.md", [link["target"] for link in frontend_task["required_links"]])
            self.assertIn("route_ownership", frontend_task["open_decisions"])
            self.assertIn("state_ownership", frontend_task["open_decisions"])
            self.assertIn("api_consumption", frontend_task["open_decisions"])
            self.assertIn("loading_states", frontend_task["open_decisions"])
            self.assertIn("error_actions", frontend_task["open_decisions"])
            self.assertNotIn("primary_flows", frontend_task["open_decisions"])
            self.assertNotIn("screens", frontend_task["open_decisions"])
            self.assertNotIn("accessibility", frontend_task["open_decisions"])
            self.assertEqual(
                [
                    "load-frontend-design-skills",
                    "read-frontend-references",
                    "read-source-acceptance",
                    "read-ui-and-api-sources",
                    "author-frontend-modules",
                    "author-api-consumption",
                    "link-tests-and-acceptance",
                    "verify-frontend-authoring",
                    "refresh-frontend-authoring",
                ],
                [step["id"] for step in frontend_task["steps"]],
            )
            self.assertEqual(list(range(1, 10)), [step["sequence"] for step in frontend_task["steps"]])
            self.assertEqual(["designing-frontend-modules"], frontend_task["steps"][0]["skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], frontend_task["steps"][7]["argv"])
            self.assertFalse(frontend_task["steps"][7]["writes_state"])
            self.assertEqual(["bin/governance", "design", "frontend-authoring", ".", "--json"], frontend_task["steps"][8]["argv"])
            self.assertNotIn("route_names", task)
            self.assertNotIn("component_names", task)
            self.assertNotIn("state_shape", task)

    def test_design_test_strategy_authoring_builds_verification_task_queue_without_guessing_tests(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold_design = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_design.returncode, scaffold_design.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "test-strategy-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("test-strategy", payload["track"])
            self.assertEqual("do_not_guess_verification_scope", payload["decision_policy"])
            self.assertIn("designing-test-strategy", payload["skills"])
            self.assertIn("senior-qa", payload["specialist_skills"])
            self.assertIn("playwright-pro", payload["specialist_skills"])
            self.assertIn("security-pen-testing", payload["specialist_skills"])
            self.assertIn("references/test-strategy-checklist.md", payload["references"])
            self.assertIn("references/security-design-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["authoring_tasks"]))
            task = payload["authoring_tasks"][0]
            self.assertEqual("TEST-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("test-strategy-authoring", task["execution"]["stage"])
            self.assertEqual("designing-test-strategy", task["execution"]["primary_skill"])
            self.assertEqual("senior-qa", task["execution"]["primary_specialist_skill"])
            self.assertEqual("verify-test-strategy-authoring", task["execution"]["verify_step"])
            self.assertEqual("refresh-test-strategy-authoring", task["execution"]["refresh_step"])
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            self.assertIn("senior-qa", task["specialist_skills"])
            self.assertIn("playwright-pro", task["specialist_skills"])
            self.assertIn("security-pen-testing", task["specialist_skills"])
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(
                [
                    "docs/tests/01-strategy.md",
                    "docs/tests/02-acceptance-matrix.md",
                ],
                document_paths,
            )
            strategy_doc = task["documents"][0]
            self.assertIn("Test Layers", strategy_doc["sections"])
            self.assertIn("Non-Functional Checks", strategy_doc["sections"])
            matrix_doc = task["documents"][1]
            self.assertIn("Matrix", matrix_doc["sections"])
            self.assertIn("Uncovered Criteria", matrix_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", required_links["api_contract"])
            self.assertEqual("docs/architecture/03-quality-attributes.md", required_links["architecture_quality"])
            self.assertEqual("docs/backend/01-modules.md", required_links["backend_modules"])
            self.assertEqual("docs/frontend/01-modules.md", required_links["frontend_modules"])
            self.assertEqual("docs/development/03-verification-log.md", required_links["verification_log"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("missing", required_link_statuses["api_contract"])
            self.assertEqual("placeholder_present", required_link_statuses["architecture_quality"])
            self.assertEqual("placeholder_present", required_link_statuses["backend_modules"])
            self.assertEqual("placeholder_present", required_link_statuses["verification_log"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            self.assertIn("acceptance_coverage", task["open_decisions"])
            self.assertIn("test_layers", task["open_decisions"])
            self.assertIn("security_checks", task["open_decisions"])
            self.assertIn("non_functional_checks", task["open_decisions"])
            self.assertIn("evidence_targets", task["open_decisions"])
            self.assertEqual(
                [
                    "load-test-strategy-skill",
                    "read-test-references",
                    "read-source-acceptance",
                    "read-design-risk-sources",
                    "author-test-strategy",
                    "author-acceptance-matrix",
                    "link-evidence-and-readiness",
                    "verify-test-strategy-authoring",
                    "refresh-test-strategy-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 10)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["designing-test-strategy"], task["steps"][0]["skills"])
            self.assertIn("senior-qa", task["steps"][0]["specialist_skills"])
            self.assertIn("playwright-pro", task["steps"][0]["specialist_skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][7]["argv"])
            self.assertFalse(task["steps"][7]["writes_state"])
            self.assertEqual(["bin/governance", "design", "test-strategy-authoring", ".", "--json"], task["steps"][8]["argv"])
            self.assertNotIn("test_names", task)
            self.assertNotIn("commands", task)
            self.assertNotIn("fixtures", task)

    def test_design_implementation_planning_authoring_builds_task_queue_without_guessing_scope(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold_design = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_design.returncode, scaffold_design.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "implementation-planning-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("implementation-planning", payload["track"])
            self.assertEqual("do_not_guess_task_scope", payload["decision_policy"])
            self.assertIn("planning-implementation-work", payload["skills"])
            self.assertIn("senior-fullstack", payload["specialist_skills"])
            self.assertIn("ci-cd-pipeline-builder", payload["specialist_skills"])
            self.assertIn("tech-debt-tracker", payload["specialist_skills"])
            self.assertIn("references/implementation-readiness-checklist.md", payload["references"])
            self.assertIn("references/implementation-execution-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["authoring_tasks"]))
            task = payload["authoring_tasks"][0]
            self.assertEqual("PLAN-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("implementation-planning-authoring", task["execution"]["stage"])
            self.assertEqual("planning-implementation-work", task["execution"]["primary_skill"])
            self.assertEqual("senior-fullstack", task["execution"]["primary_specialist_skill"])
            self.assertEqual(
                "verify-implementation-planning-authoring",
                task["execution"]["verify_step"],
            )
            self.assertEqual(
                "refresh-implementation-planning-authoring",
                task["execution"]["refresh_step"],
            )
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("TASK-001", task["suggested_task_id"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            self.assertIn("senior-fullstack", task["specialist_skills"])
            self.assertIn("ci-cd-pipeline-builder", task["specialist_skills"])
            self.assertIn("tech-debt-tracker", task["specialist_skills"])
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(
                [
                    "docs/development/01-roadmap.md",
                    "docs/development/02-task-board.md",
                    "docs/development/03-verification-log.md",
                ],
                document_paths,
            )
            roadmap_doc = task["documents"][0]
            self.assertIn("Milestones", roadmap_doc["sections"])
            self.assertIn("Deferred Scope", roadmap_doc["sections"])
            task_board_doc = task["documents"][1]
            self.assertIn("Task Table", task_board_doc["sections"])
            self.assertIn("Traceability Rules", task_board_doc["sections"])
            verification_log_doc = task["documents"][2]
            self.assertIn("Verification Runs", verification_log_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", required_links["api_contract"])
            self.assertEqual("docs/tests/02-acceptance-matrix.md", required_links["acceptance_matrix"])
            self.assertEqual("docs/development/03-verification-log.md", required_links["verification_log"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("placeholder_present", required_link_statuses["architecture_context"])
            self.assertEqual("missing", required_link_statuses["api_contract"])
            self.assertEqual("placeholder_present", required_link_statuses["acceptance_matrix"])
            self.assertEqual("placeholder_present", required_link_statuses["verification_log"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            self.assertIn("task_scope", task["open_decisions"])
            self.assertIn("ready_criteria", task["open_decisions"])
            self.assertIn("verification_plan", task["open_decisions"])
            self.assertIn("agent_handoff", task["open_decisions"])
            self.assertIn("done_evidence", task["open_decisions"])
            self.assertEqual(
                [
                    "load-implementation-planning-skill",
                    "read-implementation-references",
                    "read-source-acceptance",
                    "read-design-and-test-sources",
                    "author-roadmap",
                    "author-task-board",
                    "initialize-verification-log",
                    "link-ready-contract",
                    "verify-implementation-planning-authoring",
                    "refresh-implementation-planning-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 11)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["planning-implementation-work"], task["steps"][0]["skills"])
            self.assertIn("senior-fullstack", task["steps"][0]["specialist_skills"])
            self.assertIn("ci-cd-pipeline-builder", task["steps"][0]["specialist_skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][8]["argv"])
            self.assertFalse(task["steps"][8]["writes_state"])
            self.assertEqual(
                ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
                task["steps"][9]["argv"],
            )
            self.assertNotIn("implementation_files", task)
            self.assertNotIn("code_commands", task)
            self.assertNotIn("estimates", task)

    def test_design_architecture_decisions_authoring_builds_adr_review_queue_without_guessing_decisions(self) -> None:
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
            advance_product = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_product.returncode, advance_product.stderr)
            advance_design = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, advance_design.returncode, advance_design.stderr)
            scaffold_design = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, scaffold_design.returncode, scaffold_design.stderr)

            result = subprocess.run(
                [sys.executable, str(CLI), "design", "architecture-decisions-authoring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertEqual("design-derivation", payload["phase"])
            self.assertEqual("architecture-decisions", payload["track"])
            self.assertEqual("do_not_guess_architecture_decisions", payload["decision_policy"])
            self.assertIn("capturing-architecture-decisions", payload["skills"])
            self.assertIn("senior-architect", payload["specialist_skills"])
            self.assertIn("migration-architect", payload["specialist_skills"])
            self.assertIn("tech-stack-evaluator", payload["specialist_skills"])
            self.assertIn("references/architecture-methods.md", payload["references"])
            self.assertIn("references/architecture-decision-record-checklist.md", payload["references"])
            self.assertIn("local_commands", payload)
            self.assertEqual("advance-implementation-check", payload["next_actions"][0]["id"])
            self.assertEqual(1, len(payload["authoring_tasks"]))
            task = payload["authoring_tasks"][0]
            self.assertEqual("ADR-AUTHOR-001", task["task_id"])
            self.assertEqual(1, task["sequence"])
            self.assertEqual("architecture-decision-authoring", task["execution"]["stage"])
            self.assertEqual("capturing-architecture-decisions", task["execution"]["primary_skill"])
            self.assertEqual("senior-architect", task["execution"]["primary_specialist_skill"])
            self.assertEqual(
                "verify-architecture-decisions-authoring",
                task["execution"]["verify_step"],
            )
            self.assertEqual(
                "refresh-architecture-decisions-authoring",
                task["execution"]["refresh_step"],
            )
            self.assertEqual("A-001", task["acceptance_id"])
            self.assertEqual("Goal Flow", task["title"])
            self.assertEqual("undetermined", task["requires_adr"])
            self.assertEqual("001", task["next_adr_prefix"])
            self.assertEqual("docs/product/08-acceptance-criteria.md#a-001-goal-flow", task["source"]["reference"])
            self.assertIn("senior-architect", task["specialist_skills"])
            self.assertIn("migration-architect", task["specialist_skills"])
            self.assertIn("tech-stack-evaluator", task["specialist_skills"])
            document_paths = [document["path"] for document in task["documents"]]
            self.assertEqual(["docs/decisions/_template.md"], document_paths)
            template_doc = task["documents"][0]
            self.assertIn("Context", template_doc["sections"])
            self.assertIn("Decision", template_doc["sections"])
            self.assertIn("Consequences", template_doc["sections"])
            self.assertIn("References", template_doc["sections"])
            required_links = {link["kind"]: link["target"] for link in task["required_links"]}
            self.assertEqual(
                "docs/product/08-acceptance-criteria.md#a-001-goal-flow",
                required_links["product_acceptance"],
            )
            self.assertEqual("docs/architecture/01-system-context.md", required_links["architecture_context"])
            self.assertEqual("docs/architecture/03-quality-attributes.md", required_links["architecture_quality"])
            self.assertEqual("docs/api/endpoints/01-goal-flow.md", required_links["api_contract"])
            self.assertEqual("docs/backend/01-modules.md", required_links["backend_modules"])
            self.assertEqual("docs/frontend/01-modules.md", required_links["frontend_modules"])
            required_link_statuses = _link_statuses(task["required_links"])
            self.assertEqual("satisfied", required_link_statuses["product_acceptance"])
            self.assertEqual("placeholder_present", required_link_statuses["architecture_context"])
            self.assertEqual("placeholder_present", required_link_statuses["architecture_quality"])
            self.assertEqual("missing", required_link_statuses["api_contract"])
            self.assertEqual("placeholder_present", required_link_statuses["backend_modules"])
            self.assertEqual("satisfied", required_link_statuses["unresolved_decisions"])
            repair_actions = _repair_actions_by_link_kind(task["link_repair_actions"])
            self.assertEqual("placeholder_present", repair_actions["architecture_context"]["status"])
            self.assertEqual("missing", repair_actions["api_contract"]["status"])
            self.assertEqual(
                ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
                repair_actions["api_contract"]["refresh_command"]["argv"],
            )
            self.assertIn("adr_trigger", task["open_decisions"])
            self.assertIn("decision_scope", task["open_decisions"])
            self.assertIn("alternatives", task["open_decisions"])
            self.assertIn("consequences", task["open_decisions"])
            self.assertIn("verification_path", task["open_decisions"])
            self.assertEqual(
                [
                    "load-adr-skill",
                    "read-adr-references",
                    "read-source-acceptance",
                    "read-design-decision-sources",
                    "evaluate-adr-trigger",
                    "author-adr-if-triggered",
                    "link-decision-references",
                    "verify-architecture-decisions-authoring",
                    "refresh-architecture-decisions-authoring",
                ],
                [step["id"] for step in task["steps"]],
            )
            self.assertEqual(list(range(1, 10)), [step["sequence"] for step in task["steps"]])
            self.assertEqual(["capturing-architecture-decisions"], task["steps"][0]["skills"])
            self.assertIn("senior-architect", task["steps"][0]["specialist_skills"])
            self.assertIn("migration-architect", task["steps"][0]["specialist_skills"])
            self.assertEqual(["bin/governance", "verify", ".", "--check", "--json"], task["steps"][7]["argv"])
            self.assertFalse(task["steps"][7]["writes_state"])
            self.assertEqual(
                ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
                task["steps"][8]["argv"],
            )
            self.assertNotIn("adr_file", task)
            self.assertNotIn("decision", task)
            self.assertNotIn("selected_option", task)

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
            self.assertNotIn("local_commands", payload)
            self.assertNotIn("next_actions", payload)
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
