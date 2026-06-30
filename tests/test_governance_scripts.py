import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import scripts.bootstrap_tree as bootstrap_module
import scripts.check_env as check_env_module
import scripts.product_import as product_import_module
import scripts.scaffold as scaffold_module
from scripts.check_env import (
    PackageManager,
    ToolStatus,
    build_install_plan,
    environment_ok,
    install_command_text,
    install_commands,
    missing_tools_by_level,
    repair_target_error,
    write_repair_plan,
)
from scripts.bootstrap_tree import InitPreflightError
from scripts.bootstrap_tree import bootstrap
from scripts.bootstrap_tree import preflight_init
from scripts.gates import evaluate_gate
from scripts.state import StateFileError, load_state, merge_state
from scripts.verify_governance import task_board_ready_tasks, verify


def _append_index(readme: Path, filename: str) -> None:
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n- `{filename}` - generated for test\n", encoding="utf-8")


def _write_indexed_doc(root: Path, rel: str, text: str = "# Test\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _append_index(path.parent / "README.md", path.name)


def _append_product_meta_chapter(root: Path, filename: str) -> None:
    meta = root / "docs/product/core/product-meta.md"
    meta.write_text(meta.read_text(encoding="utf-8") + f"\n- [{filename}](../{filename})\n", encoding="utf-8")


def _write_product_chapter(root: Path, filename: str, title: str) -> None:
    _write_indexed_doc(root, f"docs/product/{filename}", f"# {title}\n\nSource: [PRD](core/PRD.md).\n")
    _append_product_meta_chapter(root, filename)


def _write_acceptance_chapter(root: Path) -> None:
    _write_indexed_doc(
        root,
        "docs/product/08-acceptance-criteria.md",
        "# Acceptance Criteria\n\n"
        "Source: [PRD](core/PRD.md).\n\n"
        "## A-001 Goal Flow\n\n"
        "- The primary goal flow meets the documented product expectation.\n",
    )
    _append_product_meta_chapter(root, "08-acceptance-criteria.md")


def _append_acceptance_criterion(root: Path, acceptance_id: str, title: str) -> None:
    path = root / "docs/product/08-acceptance-criteria.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"\n## {acceptance_id} {title}\n\n"
        "- The additional acceptance criterion is traceable or explicitly uncovered.\n",
        encoding="utf-8",
    )


def _write_api_error_codes_doc(root: Path) -> None:
    _write_indexed_doc(root, "docs/api/error-codes.md", _api_error_codes_doc())


def _api_error_codes_doc(
    product_links: str = "[PRD](../product/core/PRD.md), [Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# API Error Codes\n\n"
        "## Product Links\n\n"
        f"- {product_links}\n\n"
        "## Error Taxonomy\n\n"
        "- Validation errors use stable client-actionable codes.\n"
        "- System errors hide internal implementation details.\n\n"
        "## Error Codes\n\n"
        "- E_EXAMPLE: example error for endpoint contract tests.\n\n"
        "## Retry Semantics\n\n"
        "- Retry only idempotent requests or writes protected by an idempotency key.\n\n"
        "## Frontend Handling\n\n"
        "- Frontend flows map stable codes to user-visible recovery actions.\n"
    )


def _api_conventions_doc(
    product_links: str = "[PRD](../product/core/PRD.md), [Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# API Conventions\n\n"
        "## Product Links\n\n"
        f"- {product_links}\n\n"
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


def _api_changelog_doc() -> str:
    return (
        "# API Changelog\n\n"
        "## Change Log\n\n"
        "- Initial API contract baseline records conventions, error codes, and endpoint files.\n\n"
        "## Compatibility Notes\n\n"
        "- Breaking changes require downstream frontend, backend, and test updates in the same delivery slice.\n"
    )


def _write_frontend_consumer_doc(root: Path) -> None:
    _write_acceptance_chapter(root)
    _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
    _write_indexed_doc(root, "docs/ui/01-interaction-model.md", _ui_interaction_model_doc())
    _write_indexed_doc(root, "docs/frontend/01-modules.md", _frontend_modules_doc())
    _write_indexed_doc(
        root,
        "docs/frontend/02-api-consumption.md",
        _frontend_api_consumption_doc(),
    )


def _write_backend_trace_docs(root: Path) -> None:
    _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
    _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
    _write_indexed_doc(root, "docs/backend/02-data-model.md", _backend_data_model_doc())
    _write_indexed_doc(root, "docs/backend/03-external-services.md", _backend_external_services_doc())
    _write_acceptance_chapter(root)


def _write_frontend_trace_docs(root: Path) -> None:
    _write_indexed_doc(root, "docs/ui/01-interaction-model.md", _ui_interaction_model_doc())
    _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
    _write_indexed_doc(root, "docs/frontend/02-api-consumption.md", _frontend_api_consumption_doc())
    _write_acceptance_chapter(root)


def _write_test_strategy_trace_docs(root: Path) -> None:
    _write_acceptance_chapter(root)
    _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
    _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())


def _write_traceable_test_strategy(root: Path) -> None:
    _write_test_strategy_trace_docs(root)
    _write_indexed_doc(
        root,
        "docs/tests/01-strategy.md",
        _test_strategy_doc(),
    )


def _write_acceptance_matrix_trace_docs(root: Path) -> None:
    _write_traceable_test_strategy(root)
    _write_api_error_codes_doc(root)
    _write_indexed_doc(root, "docs/ui/01-interaction-model.md", _ui_interaction_model_doc())
    endpoints_readme = root / "docs/api/endpoints/README.md"
    endpoints_readme.parent.mkdir(parents=True, exist_ok=True)
    if not endpoints_readme.exists():
        endpoints_readme.write_text("# API Endpoints\n", encoding="utf-8")
    _write_indexed_doc(
        root,
        "docs/api/endpoints/01-goal-flow.md",
        _endpoint_contract_doc(
            "Goal Flow Endpoint",
            upstream_links="- [Acceptance](../../product/08-acceptance-criteria.md)",
            frontend_consumers="- [Interaction model](../../ui/01-interaction-model.md)",
        ),
    )


def _architecture_system_context_doc(
    product_links: str = "[PRD](../product/core/PRD.md), [Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# System Context\n\n"
        "## Product Links\n\n"
        f"- {product_links}\n\n"
        "## Actors\n\n"
        "- Primary user\n\n"
        "## External Systems\n\n"
        "- none\n\n"
        "## Trust Boundaries\n\n"
        "- User browser to application boundary\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _architecture_containers_doc(
    system_context: str = "[System context](01-system-context.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# Containers\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n\n"
        "## System Context\n\n"
        f"- {system_context}\n\n"
        "## Containers\n\n"
        "- Web application: owns user interaction runtime.\n"
        "- API service: owns product workflow operations.\n\n"
        "## Runtime Responsibilities\n\n"
        "- The API service validates and persists goal flow changes.\n\n"
        "## Data Ownership\n\n"
        "- The API service owns workflow state.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _architecture_quality_attributes_doc(
    containers: str = "[Containers](02-containers.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# Quality Attributes\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n"
        f"- {containers}\n\n"
        "## Availability\n\n"
        "- The API service should preserve the goal flow during planned dependency outages.\n\n"
        "## Performance\n\n"
        "- Primary goal-flow reads should complete within documented product expectations.\n\n"
        "## Security\n\n"
        "- User-owned goal data must stay within authenticated boundaries.\n\n"
        "## Observability\n\n"
        "- Goal-flow failures should emit traceable error and audit events.\n\n"
        "## Tradeoffs\n\n"
        "- Simpler runtime boundaries are preferred until acceptance evidence requires separation.\n"
    )


def _backend_data_model_doc(
    backend_modules: str = "[Backend modules](01-modules.md)",
    api: str = "[API conventions](../api/00-conventions.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# Data Model\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n"
        f"- {api}\n"
        f"- {backend_modules}\n\n"
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
        "- Add owner-scoped goal tables before enabling API writes.\n"
    )


def _backend_external_services_doc(
    backend_modules: str = "[Backend modules](01-modules.md)",
    api: str = "[API conventions](../api/00-conventions.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# External Services\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n"
        f"- {api}\n"
        f"- {backend_modules}\n\n"
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


def _backend_modules_doc(
    architecture: str = "[System context](../architecture/01-system-context.md)",
    api: str = "[API conventions](../api/00-conventions.md)",
    data_model: str = "[Data model](02-data-model.md)",
    external_services: str = "[External services](03-external-services.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# Backend Modules\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n\n"
        "## Architecture Links\n\n"
        f"- {architecture}\n\n"
        "## Modules\n\n"
        "- Workflow module owns the primary goal-flow runtime behavior.\n\n"
        "## API Ownership\n\n"
        f"- Workflow API behavior follows {api}.\n\n"
        "## Failure Modes\n\n"
        f"- Persistence failures follow {data_model}.\n"
        f"- Dependency failures follow {external_services}.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _frontend_modules_doc(
    ui: str = "[Interaction model](../ui/01-interaction-model.md)",
    api: str = "[API conventions](../api/00-conventions.md)",
    api_consumption: str = "[API consumption](02-api-consumption.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# Frontend Modules\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n\n"
        "## UI Links\n\n"
        f"- {ui}\n\n"
        "## Modules\n\n"
        "- Goal flow module owns the primary interaction screens.\n\n"
        "## State Ownership\n\n"
        f"- API-backed state follows {api_consumption}.\n\n"
        "## Routes\n\n"
        f"- Goal flow routes call APIs defined by {api}.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _ui_interaction_model_doc(
    product_links: str = "[PRD](../product/core/PRD.md), [Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# Interaction Model\n\n"
        "## Product Links\n\n"
        f"- {product_links}\n\n"
        "## Primary Flows\n\n"
        "- The primary goal flow lets an authenticated user create and review workflow items.\n\n"
        "## Screens\n\n"
        "- Goal list screen shows current workflow items and entry points.\n"
        "- Goal detail screen shows the selected item and available actions.\n\n"
        "## States\n\n"
        "- Empty, loading, success, validation error, and retryable failure states are explicit.\n\n"
        "## Errors\n\n"
        "- User-correctable errors map to visible correction actions.\n\n"
        "## Accessibility\n\n"
        "- Primary actions remain keyboard reachable and screen-reader labelled.\n"
    )


def _frontend_api_consumption_doc(
    frontend_modules: str = "[Frontend modules](01-modules.md)",
    api: str = "[API conventions](../api/00-conventions.md)",
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
) -> str:
    return (
        "# API Consumption\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n"
        f"- {frontend_modules}\n\n"
        "## API Links\n\n"
        f"- {api}\n\n"
        "## Consumption Map\n\n"
        "- Goal flow screens consume the documented API contract through the frontend module boundary.\n\n"
        "## Loading States\n\n"
        "- Loading states keep the primary goal flow responsive while API requests are in flight.\n\n"
        "## Error Actions\n\n"
        "- Recoverable API errors show user-visible retry or correction actions.\n"
    )


def _acceptance_matrix_doc(
    acceptance: str = "[A-001](../product/08-acceptance-criteria.md#a-001)",
    design: str = "[System context](../architecture/01-system-context.md)",
    api: str = "[Goal endpoint](../api/endpoints/01-goal-flow.md)",
    test: str = "[Test strategy](01-strategy.md)",
) -> str:
    return (
        "# Acceptance Matrix\n\n"
        "## Matrix\n\n"
        "| Acceptance | Design | API | Test |\n"
        "| --- | --- | --- | --- |\n"
        f"| {acceptance} | {design} | {api} | {test} |\n\n"
        "## Uncovered Criteria\n\n"
        "- none\n"
    )


def _roadmap_doc(
    status: str = "Ready",
    product_links: str = "[PRD](../product/core/PRD.md), [Acceptance](../product/08-acceptance-criteria.md)",
    milestone_table: str | None = None,
) -> str:
    if milestone_table is None:
        milestone_table = (
            "| ID | Status | Milestone |\n"
            "| --- | --- | --- |\n"
            f"| TASK-001 | {status} | Goal flow |\n"
        )
    return (
        "# Roadmap\n\n"
        "## Product Links\n\n"
        f"- {product_links}\n\n"
        "## Milestones\n\n"
        f"{milestone_table}\n"
        "## Sequencing\n\n"
        "- Implement product goal flow foundations before deferred refinements.\n\n"
        "## Risks\n\n"
        "- API, backend, frontend, and test work must stay aligned to acceptance criteria.\n\n"
        "## Deferred Scope\n\n"
        "- none\n"
    )


def _task_board_doc(rows: str) -> str:
    rows = rows.replace(
        "[Acceptance](../product/08-acceptance-criteria.md)",
        "[A-001](../product/08-acceptance-criteria.md#a-001)",
    )
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


def _test_strategy_doc(
    acceptance: str = "[Acceptance](../product/08-acceptance-criteria.md)",
    api: str = "[API conventions](../api/00-conventions.md)",
    design: str = "[System context](../architecture/01-system-context.md)",
) -> str:
    return (
        "# Test Strategy\n\n"
        "## Product Links\n\n"
        f"- {acceptance}\n"
        f"- {api}\n"
        f"- {design}\n\n"
        "## Acceptance Links\n\n"
        f"- {acceptance}\n\n"
        "## Test Layers\n\n"
        "- Unit tests cover isolated validation rules and state transitions.\n"
        "- Integration tests cover API contract and persistence behavior.\n\n"
        "## Risk Coverage\n\n"
        "- Goal-flow risks are mapped back to acceptance and design sources before implementation.\n\n"
        "## Non-Functional Checks\n\n"
        "- Performance, security, and observability checks are planned for implementation handoff.\n"
    )


def _adr_doc(references: str = "- [System context](../architecture/01-system-context.md)") -> str:
    return (
        "# ADR-001: Choose Runtime Boundary\n\n"
        "- Status: accepted\n"
        "- Date: 2026-06-26\n\n"
        "## Context\n\n"
        "The runtime boundary affects API, backend, and frontend delivery.\n\n"
        "## Decision\n\n"
        "Use a modular monolith boundary for the first implementation slice.\n\n"
        "## Consequences\n\n"
        "Deployment stays simple while module boundaries remain documented.\n\n"
        "## References\n\n"
        f"{references.rstrip()}\n"
    )


def _endpoint_contract_doc(
    title: str,
    upstream_links: str = "- [Product goals](../../product/01-goals.md)",
    error_codes: str = "- [E_EXAMPLE](../error-codes.md#e-example)",
    frontend_consumers: str = "- [API consumption map](../../frontend/02-api-consumption.md)",
) -> str:
    return (
        f"# {title}\n\n"
        "## Method and Path\n\n"
        "GET /example\n\n"
        "## Auth\n\n"
        "Required.\n\n"
        "## Idempotency\n\n"
        "Safe retry.\n\n"
        "## Request Fields\n\n"
        "- none\n\n"
        "## Response Fields\n\n"
        "- id\n\n"
        "## Error Codes\n\n"
        f"{error_codes.rstrip()}\n\n"
        "## Upstream Links\n\n"
        f"{upstream_links.rstrip()}\n\n"
        "## Frontend Consumers\n\n"
        f"{frontend_consumers.rstrip()}\n"
    )


class GovernanceScriptsTest(unittest.TestCase):
    def test_bootstrap_archives_markdown_product_doc_and_passes_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "input-product.md"
            product.write_text(
                "# Demo Product\n\n"
                "## Goal\n\n"
                "Build a reliable workflow-driven project.\n",
                encoding="utf-8",
            )

            bootstrap(root, product)

            self.assertTrue((root / "README.md").exists())
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertTrue((root / "docs/product/core/PRD.md").exists())
            self.assertTrue((root / "docs/product/core/source/input-product.md").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/workflows/00-overview.md").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/skills/using-governance-workflow/SKILL.md").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/references/architecture-methods.md").exists())
            workflow_manifest = json.loads((root / "docs/agent-workflow/workflow-pack/manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["path"] == "workflows/00-overview.md" for item in workflow_manifest["files"]))
            runtime_manifest = json.loads((root / "docs/agent-workflow/runtime-manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(any(item["path"] == "bin/governance" for item in runtime_manifest["files"]))
            self.assertTrue(any(item["path"] == "scripts/verify_governance.py" for item in runtime_manifest["files"]))
            self.assertIn("Demo Product", (root / "docs/product/core/PRD.md").read_text(encoding="utf-8"))
            self.assertIn("`U-NNN`", (root / "docs/unresolved.md").read_text(encoding="utf-8"))
            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("input-product.md", manifest["source"]["filename"])
            self.assertEqual("ready_for_structuring", manifest["import"]["status"])
            self.assertEqual("markdown-copy", manifest["import"]["conversion_method"])
            self.assertTrue(manifest["import"]["can_derive_design"])
            self.assertEqual(manifest["source"]["sha256"], manifest["archive"]["sha256"])

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_copy_source_preserves_existing_archive_when_copy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "input-product.md"
            product.write_text("# Updated Product\n", encoding="utf-8")
            source_dir = root / "docs/product/core/source"
            existing_archive = source_dir / product.name
            existing_archive.parent.mkdir(parents=True)
            existing_archive.write_text("# Existing Archive\n", encoding="utf-8")
            original_copy2 = bootstrap_module.shutil.copy2

            def fail_after_partial_copy(_source: Path, target: Path) -> None:
                target.write_text("# Partial Archive\n", encoding="utf-8")
                raise OSError("simulated copy failure")

            bootstrap_module.shutil.copy2 = fail_after_partial_copy
            try:
                with self.assertRaises(OSError):
                    bootstrap_module._copy_source(product, source_dir, force=True)
            finally:
                bootstrap_module.shutil.copy2 = original_copy2

            self.assertEqual("# Existing Archive\n", existing_archive.read_text(encoding="utf-8"))
            self.assertFalse((source_dir / f".{product.name}.tmp").exists())

    def test_runtime_refresh_rejects_missing_source_runtime_without_partial_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            wrapper = root / "bin/governance"
            wrapper.write_text(wrapper.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            original_runtime_scripts = bootstrap_module.RUNTIME_SCRIPT_FILES
            bootstrap_module.RUNTIME_SCRIPT_FILES = [*original_runtime_scripts, "missing_runtime_source.py"]
            try:
                result = bootstrap_module.refresh_runtime(root)
            finally:
                bootstrap_module.RUNTIME_SCRIPT_FILES = original_runtime_scripts

            self.assertFalse(result.ok)
            self.assertEqual([], result.refreshed)
            self.assertIn(
                "runtime refresh preflight failed: scripts/missing_runtime_source.py: source file is missing",
                result.errors,
            )
            self.assertIn("# tampered", wrapper.read_text(encoding="utf-8"))

    def test_runtime_refresh_rolls_back_runtime_files_when_copy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            wrapper = root / "bin/governance"
            init_wrapper = root / "bin/governance-init"
            wrapper.write_text(wrapper.read_text(encoding="utf-8") + "\n# stale governance\n", encoding="utf-8")
            init_wrapper.write_text(
                init_wrapper.read_text(encoding="utf-8") + "\n# stale governance init\n",
                encoding="utf-8",
            )
            original_wrapper = wrapper.read_text(encoding="utf-8")
            original_init_wrapper = init_wrapper.read_text(encoding="utf-8")
            original_copy_runtime_file = bootstrap_module._copy_runtime_file

            def fail_after_copy(source: Path, target: Path, force: bool = False) -> None:
                original_copy_runtime_file(source, target, force)
                if target == init_wrapper:
                    raise OSError("simulated runtime copy failure")

            bootstrap_module._copy_runtime_file = fail_after_copy
            try:
                result = bootstrap_module.refresh_runtime(root)
            finally:
                bootstrap_module._copy_runtime_file = original_copy_runtime_file

            self.assertFalse(result.ok)
            self.assertEqual([], result.refreshed)
            self.assertIn("runtime refresh failed: simulated runtime copy failure", result.errors)
            self.assertEqual(original_wrapper, wrapper.read_text(encoding="utf-8"))
            self.assertEqual(original_init_wrapper, init_wrapper.read_text(encoding="utf-8"))
            self.assertFalse((wrapper.parent / ".governance.tmp").exists())
            self.assertFalse((init_wrapper.parent / ".governance-init.tmp").exists())

    def test_runtime_refresh_rolls_back_snapshot_and_runtime_when_state_update_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            runtime = root / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# stale runtime\n", encoding="utf-8")
            stale_snapshot = root / "docs/agent-workflow/workflow-pack/obsolete.md"
            stale_snapshot.write_text("# Obsolete local snapshot\n", encoding="utf-8")
            workflow_manifest = root / "docs/agent-workflow/workflow-pack/manifest.json"
            runtime_manifest = root / "docs/agent-workflow/runtime-manifest.json"
            state_path = root / ".governance/state.json"
            original_runtime = runtime.read_text(encoding="utf-8")
            original_workflow_manifest = workflow_manifest.read_text(encoding="utf-8")
            original_runtime_manifest = runtime_manifest.read_text(encoding="utf-8")
            original_state = state_path.read_text(encoding="utf-8")
            original_merge_state = bootstrap_module.merge_state

            def raise_state_error(root_arg: Path, **_updates: object) -> dict[str, object]:
                raise StateFileError(root_arg / ".governance/state.json", "unwritable: No space left on device")

            bootstrap_module.merge_state = raise_state_error
            try:
                result = bootstrap_module.refresh_runtime(root)
            finally:
                bootstrap_module.merge_state = original_merge_state

            self.assertFalse(result.ok)
            self.assertEqual([], result.refreshed)
            self.assertEqual([], result.removed)
            self.assertTrue(
                any(error.startswith("runtime refresh failed: invalid governance state file: ") for error in result.errors),
                result.errors,
            )
            self.assertEqual(original_runtime, runtime.read_text(encoding="utf-8"))
            self.assertEqual("# Obsolete local snapshot\n", stale_snapshot.read_text(encoding="utf-8"))
            self.assertEqual(original_workflow_manifest, workflow_manifest.read_text(encoding="utf-8"))
            self.assertEqual(original_runtime_manifest, runtime_manifest.read_text(encoding="utf-8"))
            self.assertEqual(original_state, state_path.read_text(encoding="utf-8"))

    def test_init_preflight_rejects_missing_source_runtime_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            original_runtime_scripts = bootstrap_module.RUNTIME_SCRIPT_FILES
            bootstrap_module.RUNTIME_SCRIPT_FILES = [*original_runtime_scripts, "missing_runtime_source.py"]
            try:
                result = preflight_init(root, product)
                with self.assertRaises(InitPreflightError) as context:
                    bootstrap(root, product)
            finally:
                bootstrap_module.RUNTIME_SCRIPT_FILES = original_runtime_scripts

            self.assertFalse(result.ok)
            self.assertIn(
                {"path": "scripts/missing_runtime_source.py", "reason": "source file is missing"},
                [conflict.to_dict() for conflict in result.conflicts],
            )
            self.assertIn(
                {"path": "scripts/missing_runtime_source.py", "reason": "source file is missing"},
                [conflict.to_dict() for conflict in context.exception.result.conflicts],
            )
            self.assertFalse(root.exists())

    def test_verify_reports_root_required_file_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            readme = root / "README.md"
            readme.unlink()
            readme.mkdir()

            report = verify(root)

            self.assertIn("required file is not a file: README.md", report.errors)
            self.assertIn(
                {
                    "code": "required_file_not_file",
                    "severity": "error",
                    "path": "README.md",
                    "message": "required file is not a file: README.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_docs_agents_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            docs_agents = root / "docs/AGENTS.md"
            docs_agents.unlink()
            docs_agents.mkdir()

            report = verify(root)

            self.assertIn("required file is not a file: docs/AGENTS.md", report.errors)
            self.assertIn(
                {
                    "code": "required_file_not_file",
                    "severity": "error",
                    "path": "docs/AGENTS.md",
                    "message": "required file is not a file: docs/AGENTS.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_root_readme_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            (root / "README.md").write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: README.md must be UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "README.md",
                    "message": "invalid Markdown encoding: README.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_docs_readme_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            (root / "docs/README.md").write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/README.md must be UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "docs/README.md",
                    "message": "invalid Markdown encoding: docs/README.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_docs_agents_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            (root / "docs/AGENTS.md").write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/AGENTS.md must be UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "docs/AGENTS.md",
                    "message": "invalid Markdown encoding: docs/AGENTS.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_unresolved_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            (root / "docs/unresolved.md").write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/unresolved.md must be UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "invalid Markdown encoding: docs/unresolved.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            (root / "docs/glossary.md").write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/glossary.md must be UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "invalid Markdown encoding: docs/glossary.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_product_chapter_invalid_encoding_without_silent_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_bytes(b"\xff")
            _append_index(root / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(root, "01-goals.md")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/product/01-goals.md must be UTF-8", report.errors)
            self.assertNotIn("docs/product/01-goals.md must link back to docs/product/core/PRD.md", report.errors)
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "invalid Markdown encoding: docs/product/01-goals.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_product_meta_invalid_encoding_without_false_missing_chapter_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")
            (root / "docs/product/core/product-meta.md").write_bytes(b"\xff")

            report = verify(root)

            self.assertIn(
                "invalid Markdown encoding: docs/product/core/product-meta.md must be UTF-8",
                report.errors,
            )
            self.assertNotIn(
                "docs/product/core/product-meta.md must link to product chapter: docs/product/01-goals.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "markdown_invalid_encoding",
                    "severity": "error",
                    "path": "docs/product/core/product-meta.md",
                    "message": "invalid Markdown encoding: docs/product/core/product-meta.md must be UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_conventions_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            api_conventions = root / "docs/api/00-conventions.md"
            api_conventions.mkdir()

            report = verify(root)

            self.assertIn("Markdown path is not a file: docs/api/00-conventions.md", report.errors)
            self.assertIn(
                {
                    "code": "markdown_not_file",
                    "severity": "error",
                    "path": "docs/api/00-conventions.md",
                    "message": "Markdown path is not a file: docs/api/00-conventions.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_contract_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            endpoint = root / "docs/api/endpoints/01-goal.md"
            endpoint.parent.mkdir(parents=True, exist_ok=True)
            endpoint.mkdir()

            report = verify(root)

            self.assertIn("Markdown path is not a file: docs/api/endpoints/01-goal.md", report.errors)
            self.assertIn(
                {
                    "code": "markdown_not_file",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-goal.md",
                    "message": "Markdown path is not a file: docs/api/endpoints/01-goal.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_system_context_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            system_context = root / "docs/architecture/01-system-context.md"
            system_context.mkdir()

            report = verify(root)

            self.assertIn("Markdown path is not a file: docs/architecture/01-system-context.md", report.errors)
            self.assertIn(
                {
                    "code": "markdown_not_file",
                    "severity": "error",
                    "path": "docs/architecture/01-system-context.md",
                    "message": "Markdown path is not a file: docs/architecture/01-system-context.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_modules_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            backend_modules = root / "docs/backend/01-modules.md"
            backend_modules.mkdir()

            report = verify(root)

            self.assertIn("Markdown path is not a file: docs/backend/01-modules.md", report.errors)
            self.assertIn(
                {
                    "code": "markdown_not_file",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "Markdown path is not a file: docs/backend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_standard_doc_directories_without_traceback(self) -> None:
        for rel in [
            "docs/ui/01-interaction-model.md",
            "docs/frontend/01-modules.md",
            "docs/frontend/02-api-consumption.md",
        ]:
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                product = root / "product.md"
                product.write_text("# Demo\n", encoding="utf-8")
                bootstrap(root, product)

                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir()

                report = verify(root)

                message = f"Markdown path is not a file: {rel}"
                self.assertIn(message, report.errors)
                self.assertIn(
                    {
                        "code": "markdown_not_file",
                        "severity": "error",
                        "path": rel,
                        "message": message,
                    },
                    [finding.to_dict() for finding in report.findings],
                )

    def test_verify_reports_test_standard_doc_directories_without_traceback(self) -> None:
        for rel in [
            "docs/tests/01-strategy.md",
            "docs/tests/02-acceptance-matrix.md",
        ]:
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                product = root / "product.md"
                product.write_text("# Demo\n", encoding="utf-8")
                bootstrap(root, product)

                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir()

                report = verify(root)

                message = f"Markdown path is not a file: {rel}"
                self.assertIn(message, report.errors)
                self.assertIn(
                    {
                        "code": "markdown_not_file",
                        "severity": "error",
                        "path": rel,
                        "message": message,
                    },
                    [finding.to_dict() for finding in report.findings],
                )

    def test_verify_reports_product_acceptance_directory_during_matrix_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            acceptance_chapter = root / "docs/product/08-acceptance-criteria.md"
            acceptance_chapter.mkdir()
            _write_indexed_doc(root, "docs/tests/02-acceptance-matrix.md", _acceptance_matrix_doc())

            report = verify(root)

            self.assertIn("Markdown path is not a file: docs/product/08-acceptance-criteria.md", report.errors)
            self.assertIn(
                {
                    "code": "markdown_not_file",
                    "severity": "error",
                    "path": "docs/product/08-acceptance-criteria.md",
                    "message": "Markdown path is not a file: docs/product/08-acceptance-criteria.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_governance_closure_doc_directories_without_traceback(self) -> None:
        for rel in [
            "docs/decisions/001-runtime-boundary.md",
            "docs/development/01-roadmap.md",
            "docs/development/02-task-board.md",
        ]:
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                product = root / "product.md"
                product.write_text("# Demo\n", encoding="utf-8")
                bootstrap(root, product)

                if rel == "docs/development/01-roadmap.md":
                    _write_indexed_doc(
                        root,
                        "docs/development/02-task-board.md",
                        _task_board_doc(
                            "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                        ),
                    )
                if rel == "docs/development/02-task-board.md":
                    _write_acceptance_matrix_trace_docs(root)
                    _write_indexed_doc(root, "docs/tests/02-acceptance-matrix.md", _acceptance_matrix_doc())

                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir()

                report = verify(root)

                message = f"Markdown path is not a file: {rel}"
                self.assertIn(message, report.errors)
                self.assertIn(
                    {
                        "code": "markdown_not_file",
                        "severity": "error",
                        "path": rel,
                        "message": message,
                    },
                    [finding.to_dict() for finding in report.findings],
                )

    def test_task_board_ready_tasks_returns_empty_for_task_board_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            task_board = root / "docs/development/02-task-board.md"
            task_board.mkdir()

            self.assertEqual([], task_board_ready_tasks(root))

    def test_task_board_ready_tasks_returns_empty_for_task_board_invalid_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_bytes(b"\xff")

            self.assertEqual([], task_board_ready_tasks(root))

    def test_task_board_ready_tasks_returns_empty_for_acceptance_matrix_invalid_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(
                root,
                "docs/development/02-task-board.md",
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
            )
            matrix = root / "docs/tests/02-acceptance-matrix.md"
            matrix.write_bytes(b"\xff")

            self.assertEqual([], task_board_ready_tasks(root))

    def test_verify_reports_product_source_manifest_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest_path.unlink()
            manifest_path.mkdir()

            report = verify(root)

            self.assertIn(
                "required file is not a file: docs/product/core/source/source-manifest.json",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "required_file_not_file",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "required file is not a file: docs/product/core/source/source-manifest.json",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_product_source_manifest_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest_path.write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid product source manifest encoding: expected UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "product_source_manifest_invalid_encoding",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "invalid product source manifest encoding: expected UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_product_structuring_gate_handles_product_source_manifest_invalid_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest_path.write_bytes(b"\xff")

            result = evaluate_gate(root, "product-structuring")

            self.assertFalse(result.ok)
            requirement_by_code = {requirement.code: requirement for requirement in result.requirements}
            self.assertFalse(requirement_by_code["product_source_present"].ok)
            self.assertFalse(requirement_by_code["product_import_ready"].ok)
            self.assertIn("invalid product source manifest encoding: expected UTF-8", result.verification["errors"])

    def test_verify_reports_docs_root_file_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
            (root / "SPEC.md").write_text("# Spec\n", encoding="utf-8")
            (root / "docs").write_text("not a directory\n", encoding="utf-8")

            report = verify(root)

            self.assertIn("required directory is not a directory: docs", report.errors)
            self.assertIn(
                {
                    "code": "required_directory_not_directory",
                    "severity": "error",
                    "path": "docs",
                    "message": "required directory is not a directory: docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_tampered_archived_product_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            archived = root / "docs/product/core/source/product.md"
            archived.write_text("# Tampered\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("archived product source hash mismatch: docs/product/core/source/product.md", report.errors)

    def test_verify_rejects_archived_product_source_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["size_bytes"] += 1
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("archived product source size mismatch: docs/product/core/source/product.md", report.errors)
            self.assertIn(
                {
                    "code": "product_source_size_mismatch",
                    "severity": "error",
                    "path": "docs/product/core/source/product.md",
                    "message": "archived product source size mismatch: docs/product/core/source/product.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_archived_product_source_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["archive"]["size_bytes"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("invalid product source manifest: archive.size_bytes is missing or invalid", report.errors)
            self.assertIn(
                {
                    "code": "product_source_manifest_archive_size_missing",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "invalid product source manifest: archive.size_bytes is missing or invalid",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_source_archive_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source"]["size_bytes"] += 1
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "invalid product source manifest: source.size_bytes does not match archive.size_bytes",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_source_manifest_source_size_mismatch",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "invalid product source manifest: source.size_bytes does not match archive.size_bytes",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_source_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["source"]["size_bytes"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("invalid product source manifest: source.size_bytes is missing or invalid", report.errors)
            self.assertIn(
                {
                    "code": "product_source_manifest_source_size_missing",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "invalid product source manifest: source.size_bytes is missing or invalid",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_source_archive_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source"]["sha256"] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("invalid product source manifest: source.sha256 does not match archive.sha256", report.errors)
            self.assertIn(
                {
                    "code": "product_source_manifest_source_hash_mismatch",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "invalid product source manifest: source.sha256 does not match archive.sha256",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["source"]["sha256"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("invalid product source manifest: source.sha256 is missing", report.errors)
            self.assertIn(
                {
                    "code": "product_source_manifest_source_hash_missing",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": "invalid product source manifest: source.sha256 is missing",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_absolute_archived_product_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = str(root / "docs/product/core/source/product.md")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_source_manifest_archive_path_invalid",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": (
                        "invalid product source manifest: "
                        "archive.path must be a relative path under docs/product/core/source"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_traversing_archived_product_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = "docs/product/core/source/../source/product.md"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_source_manifest_archive_path_invalid",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": (
                        "invalid product source manifest: "
                        "archive.path must be a relative path under docs/product/core/source"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_manifest_as_archived_product_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = "docs/product/core/source/source-manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_source_manifest_archive_path_invalid",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": (
                        "invalid product source manifest: "
                        "archive.path must be a relative path under docs/product/core/source"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_manifest_temp_as_archived_product_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            temp_archive = root / "docs/product/core/source/.source-manifest.json.tmp"
            temp_archive.write_text("# Not a product archive\n", encoding="utf-8")
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = "docs/product/core/source/.source-manifest.json.tmp"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_source_manifest_archive_path_invalid",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": (
                        "invalid product source manifest: "
                        "archive.path must be a relative path under docs/product/core/source"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_archived_product_source_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            directory = root / "docs/product/core/source/nested"
            directory.mkdir()
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = "docs/product/core/source/nested"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "invalid product source manifest: archive.path does not point to a file: "
                "docs/product/core/source/nested",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_source_manifest_archive_path_not_file",
                    "severity": "error",
                    "path": "docs/product/core/source/source-manifest.json",
                    "message": (
                        "invalid product source manifest: archive.path does not point to a file: "
                        "docs/product/core/source/nested"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_tampered_workflow_pack_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            workflow = root / "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
            workflow.write_text(workflow.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("workflow pack file hash mismatch: docs/agent-workflow/workflow-pack/workflows/00-overview.md", report.errors)
            self.assertIn(
                {
                    "code": "workflow_pack_file_hash_mismatch",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                    "message": "workflow pack file hash mismatch: docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_workflow_pack_manifest_file_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            workflow = root / "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
            workflow.unlink()
            workflow.mkdir()

            report = verify(root)

            self.assertIn(
                "workflow pack file is not a file: "
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "workflow_pack_file_not_file",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                    "message": (
                        "workflow pack file is not a file: "
                        "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_workflow_pack_manifest_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/workflow-pack/manifest.json"
            manifest_path.unlink()
            manifest_path.mkdir()

            report = verify(root)

            self.assertIn(
                "workflow pack manifest is not a file: docs/agent-workflow/workflow-pack/manifest.json",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "workflow_pack_manifest_not_file",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/manifest.json",
                    "message": (
                        "workflow pack manifest is not a file: "
                        "docs/agent-workflow/workflow-pack/manifest.json"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_workflow_pack_manifest_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/workflow-pack/manifest.json"
            manifest_path.write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid workflow pack manifest encoding: expected UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "workflow_pack_manifest_invalid_encoding",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/manifest.json",
                    "message": "invalid workflow pack manifest encoding: expected UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_required_workflow_pack_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/workflow-pack/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"] = [
                item
                for item in manifest["files"]
                if item["path"] != "workflows/00-overview.md"
            ]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "workflow pack manifest is missing required file entry: "
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "workflow_pack_manifest_required_file_missing",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/manifest.json",
                    "message": (
                        "workflow pack manifest is missing required file entry: "
                        "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_duplicate_workflow_pack_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/workflow-pack/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            duplicate = next(item for item in manifest["files"] if item["path"] == "workflows/00-overview.md")
            manifest["files"].append(dict(duplicate))
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("duplicate workflow pack manifest path: workflows/00-overview.md", report.errors)
            self.assertIn(
                {
                    "code": "workflow_pack_manifest_duplicate_path",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/manifest.json",
                    "message": "duplicate workflow pack manifest path: workflows/00-overview.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_workflow_pack_manifest_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/workflow-pack/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = next(item for item in manifest["files"] if item["path"] == "workflows/00-overview.md")
            entry["size_bytes"] += 1
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "workflow pack file size mismatch: "
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "workflow_pack_file_size_mismatch",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                    "message": (
                        "workflow pack file size mismatch: "
                        "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_workflow_pack_manifest_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/workflow-pack/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = next(item for item in manifest["files"] if item["path"] == "workflows/00-overview.md")
            del entry["size_bytes"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "workflow pack file size is missing or invalid: "
                "docs/agent-workflow/workflow-pack/workflows/00-overview.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "workflow_pack_manifest_size_missing",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/manifest.json",
                    "message": (
                        "workflow pack file size is missing or invalid: "
                        "docs/agent-workflow/workflow-pack/workflows/00-overview.md"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_unmanifested_workflow_pack_snapshot_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            stale = root / "docs/agent-workflow/workflow-pack/workflows/99-stale.md"
            stale.write_text("# Stale Workflow\n", encoding="utf-8")

            report = verify(root)

            self.assertIn(
                "workflow pack file is not listed in manifest: "
                "docs/agent-workflow/workflow-pack/workflows/99-stale.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "workflow_pack_file_unmanifested",
                    "severity": "error",
                    "path": "docs/agent-workflow/workflow-pack/workflows/99-stale.md",
                    "message": (
                        "workflow pack file is not listed in manifest: "
                        "docs/agent-workflow/workflow-pack/workflows/99-stale.md"
                    ),
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_non_markdown_product_requires_conversion_before_verification_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)

            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])
            self.assertEqual("conversion-required", manifest["import"]["conversion_method"])
            self.assertFalse(manifest["import"]["can_derive_design"])
            unresolved = (root / "docs/unresolved.md").read_text(encoding="utf-8")
            self.assertIn("U-001", unresolved)
            self.assertIn("Convert archived source docs/product/core/source/product.docx", unresolved)
            self.assertIn("product structuring/design derivation", unresolved)

            report = verify(root)
            self.assertIn("product source requires conversion before design derivation: docs/product/core/source/product.docx", report.errors)
            self.assertIn("blocking unresolved item U-001 affects product structuring/design derivation", report.errors)

    def test_verify_rejects_tampered_target_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            runtime = root / "scripts/scaffold.py"
            runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")

            report = verify(root)

            self.assertIn("runtime file hash mismatch: scripts/scaffold.py", report.errors)
            self.assertIn(
                {
                    "code": "runtime_file_hash_mismatch",
                    "severity": "error",
                    "path": "scripts/scaffold.py",
                    "message": "runtime file hash mismatch: scripts/scaffold.py",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_runtime_manifest_file_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            runtime = root / "scripts/scaffold.py"
            runtime.unlink()
            runtime.mkdir()

            report = verify(root)

            self.assertIn("runtime file is not a file: scripts/scaffold.py", report.errors)
            self.assertIn(
                {
                    "code": "runtime_file_not_file",
                    "severity": "error",
                    "path": "scripts/scaffold.py",
                    "message": "runtime file is not a file: scripts/scaffold.py",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_runtime_manifest_directory_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/runtime-manifest.json"
            manifest_path.unlink()
            manifest_path.mkdir()

            report = verify(root)

            self.assertIn("runtime manifest is not a file: docs/agent-workflow/runtime-manifest.json", report.errors)
            self.assertIn(
                {
                    "code": "runtime_manifest_not_file",
                    "severity": "error",
                    "path": "docs/agent-workflow/runtime-manifest.json",
                    "message": "runtime manifest is not a file: docs/agent-workflow/runtime-manifest.json",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_runtime_manifest_invalid_encoding_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/runtime-manifest.json"
            manifest_path.write_bytes(b"\xff")

            report = verify(root)

            self.assertIn("invalid runtime manifest encoding: expected UTF-8", report.errors)
            self.assertIn(
                {
                    "code": "runtime_manifest_invalid_encoding",
                    "severity": "error",
                    "path": "docs/agent-workflow/runtime-manifest.json",
                    "message": "invalid runtime manifest encoding: expected UTF-8",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_non_executable_target_runtime_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            wrapper = root / "bin/governance"
            wrapper.chmod(0o644)

            report = verify(root)

            self.assertIn("runtime file is not executable: bin/governance", report.errors)
            self.assertIn(
                {
                    "code": "runtime_file_not_executable",
                    "severity": "error",
                    "path": "bin/governance",
                    "message": "runtime file is not executable: bin/governance",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_duplicate_runtime_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/runtime-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            duplicate = next(item for item in manifest["files"] if item["path"] == "scripts/scaffold.py")
            manifest["files"].append(dict(duplicate))
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("duplicate runtime manifest path: scripts/scaffold.py", report.errors)
            self.assertIn(
                {
                    "code": "runtime_manifest_duplicate_path",
                    "severity": "error",
                    "path": "docs/agent-workflow/runtime-manifest.json",
                    "message": "duplicate runtime manifest path: scripts/scaffold.py",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_runtime_manifest_size_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/runtime-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = next(item for item in manifest["files"] if item["path"] == "scripts/scaffold.py")
            entry["size_bytes"] += 1
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("runtime file size mismatch: scripts/scaffold.py", report.errors)
            self.assertIn(
                {
                    "code": "runtime_file_size_mismatch",
                    "severity": "error",
                    "path": "scripts/scaffold.py",
                    "message": "runtime file size mismatch: scripts/scaffold.py",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_runtime_manifest_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/runtime-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = next(item for item in manifest["files"] if item["path"] == "scripts/scaffold.py")
            del entry["size_bytes"]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("runtime file size is missing or invalid: scripts/scaffold.py", report.errors)
            self.assertIn(
                {
                    "code": "runtime_manifest_size_missing",
                    "severity": "error",
                    "path": "docs/agent-workflow/runtime-manifest.json",
                    "message": "runtime file size is missing or invalid: scripts/scaffold.py",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_missing_required_runtime_manifest_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/agent-workflow/runtime-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"] = [
                item
                for item in manifest["files"]
                if item["path"] != "scripts/scaffold.py"
            ]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "runtime manifest is missing required file entry: scripts/scaffold.py",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "runtime_manifest_required_file_missing",
                    "severity": "error",
                    "path": "docs/agent-workflow/runtime-manifest.json",
                    "message": "runtime manifest is missing required file entry: scripts/scaffold.py",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_rejects_invalid_product_import_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["import"]["status"] = "reviewed"
            manifest["import"]["can_derive_design"] = True
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report = verify(root)

            self.assertIn(
                "invalid product import status: reviewed; expected one of conversion_required, no_source, ready_for_structuring",
                report.errors,
            )

    def test_verify_rejects_inconsistent_product_import_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["import"]["status"] = "conversion_required"
            manifest["import"]["can_derive_design"] = True
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            report = verify(root)

            self.assertIn(
                "product import status conversion_required requires can_derive_design: false",
                report.errors,
            )
            self.assertIn("product source requires conversion before design derivation: docs/product/core/source/product.md", report.errors)

    def test_bootstrap_rejects_existing_governance_file_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            readme = root / "README.md"
            readme.write_text("# Existing\n", encoding="utf-8")

            with self.assertRaises(InitPreflightError) as caught:
                bootstrap(root, product)

            self.assertEqual(
                [{"path": "README.md", "reason": "generated file already exists"}],
                [conflict.to_dict() for conflict in caught.exception.result.conflicts],
            )
            self.assertEqual("# Existing\n", readme.read_text(encoding="utf-8"))
            self.assertFalse((root / "docs/README.md").exists())

    def test_preflight_rejects_generated_directory_even_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            (root / "README.md").mkdir()

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {"path": "README.md", "reason": "generated file path is not a file"},
                [conflict.to_dict() for conflict in result.conflicts],
            )

    def test_preflight_rejects_generated_parent_file_even_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            (root / "scripts").write_text("not a directory\n", encoding="utf-8")

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {"path": "scripts", "reason": "generated parent path is not a directory"},
                [conflict.to_dict() for conflict in result.conflicts],
            )

    def test_preflight_rejects_generated_temp_path_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            temp_path = root / ".README.md.tmp"
            temp_path.mkdir()

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {"path": ".README.md.tmp", "reason": "generated file temp path is not a file"},
                [conflict.to_dict() for conflict in result.conflicts],
            )
            with self.assertRaises(InitPreflightError) as context:
                bootstrap(root, product, force=True)
            self.assertIn(
                {"path": ".README.md.tmp", "reason": "generated file temp path is not a file"},
                [conflict.to_dict() for conflict in context.exception.result.conflicts],
            )
            self.assertFalse((root / "README.md").exists())
            self.assertFalse((root / "docs/README.md").exists())

    def test_preflight_rejects_invalid_state_even_with_force_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            readme = root / "README.md"
            readme.write_text("# Existing\n", encoding="utf-8")
            state_path = root / ".governance/state.json"
            state_path.parent.mkdir()
            state_path.write_text("{not json\n", encoding="utf-8")

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    conflict.path == ".governance/state.json"
                    and conflict.reason.startswith("existing governance state is invalid: invalid JSON:")
                    for conflict in result.conflicts
                ),
                [conflict.to_dict() for conflict in result.conflicts],
            )
            with self.assertRaises(InitPreflightError) as context:
                bootstrap(root, product, force=True)
            self.assertTrue(
                any(
                    conflict.path == ".governance/state.json"
                    and conflict.reason.startswith("existing governance state is invalid: invalid JSON:")
                    for conflict in context.exception.result.conflicts
                ),
                [conflict.to_dict() for conflict in context.exception.result.conflicts],
            )
            self.assertEqual("# Existing\n", readme.read_text(encoding="utf-8"))
            self.assertEqual("{not json\n", state_path.read_text(encoding="utf-8"))

    def test_preflight_rejects_product_archive_generated_output_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            product = Path(tmp) / "source-manifest.json"
            product.write_text('{"product": true}\n', encoding="utf-8")

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {
                    "path": "docs/product/core/source/source-manifest.json",
                    "reason": "product archive path overlaps generated output",
                },
                [conflict.to_dict() for conflict in result.conflicts],
            )
            with self.assertRaises(InitPreflightError) as context:
                bootstrap(root, product, force=True)
            self.assertIn(
                {
                    "path": "docs/product/core/source/source-manifest.json",
                    "reason": "product archive path overlaps generated output",
                },
                [conflict.to_dict() for conflict in context.exception.result.conflicts],
            )
            self.assertFalse(root.exists())

    def test_preflight_rejects_product_archive_generated_temp_collision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            product = Path(tmp) / ".source-manifest.json.tmp"
            product.write_text("# Product\n", encoding="utf-8")

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {
                    "path": "docs/product/core/source/.source-manifest.json.tmp",
                    "reason": "product archive path overlaps generated file temp path",
                },
                [conflict.to_dict() for conflict in result.conflicts],
            )
            with self.assertRaises(InitPreflightError) as context:
                bootstrap(root, product, force=True)
            self.assertIn(
                {
                    "path": "docs/product/core/source/.source-manifest.json.tmp",
                    "reason": "product archive path overlaps generated file temp path",
                },
                [conflict.to_dict() for conflict in context.exception.result.conflicts],
            )
            self.assertFalse(root.exists())

    def test_preflight_rejects_file_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            root.write_text("not a directory\n", encoding="utf-8")
            product = Path(tmp) / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {"path": str(root), "reason": "target path is not a directory"},
                [conflict.to_dict() for conflict in result.conflicts],
            )

    def test_preflight_rejects_file_target_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocking_parent = Path(tmp) / "blocking-parent"
            blocking_parent.write_text("not a directory\n", encoding="utf-8")
            root = blocking_parent / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")

            result = preflight_init(root, product, force=True)

            self.assertFalse(result.ok)
            self.assertIn(
                {"path": str(blocking_parent), "reason": "target parent path is not a directory"},
                [conflict.to_dict() for conflict in result.conflicts],
            )

    def test_bootstrap_installs_target_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")

            bootstrap(root, product)

            self.assertTrue((root / "bin/governance").exists())
            self.assertTrue((root / "scripts/governance_cli.py").exists())
            self.assertTrue((root / "scripts/phases.py").exists())
            self.assertTrue((root / "scripts/product_import.py").exists())
            self.assertTrue((root / "scripts/scaffold.py").exists())
            self.assertTrue((root / "scripts/verify_governance.py").exists())
            self.assertTrue((root / "docs/agent-workflow/workflow-pack/manifest.json").exists())
            self.assertIn("bin/governance verify .", (root / "Makefile").read_text(encoding="utf-8"))

            verify_result = subprocess.run(
                ["make", "verify-governance"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            self.assertIn("Governance verification passed.", verify_result.stdout)

            cli_result = subprocess.run(
                [str(root / "bin/governance"), "status", str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, cli_result.returncode, cli_result.stderr)
            self.assertIn("phase: initialized", cli_result.stdout)

    def test_product_mark_ready_reports_archived_source_hash_read_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")

            original_sha256 = product_import_module._sha256

            def raise_os_error(_path: Path) -> str:
                raise OSError(13, "Permission denied")

            product_import_module._sha256 = raise_os_error
            try:
                result = product_import_module.mark_product_import_ready(root, reviewed=True)
            finally:
                product_import_module._sha256 = original_sha256

            self.assertFalse(result.ok)
            self.assertIn(
                "archived product source is unreadable: docs/product/core/source/product.docx: Permission denied",
                result.errors,
            )
            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_manifest_as_archive_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = "docs/product/core/source/source-manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            result = product_import_module.mark_product_import_ready(root, reviewed=True)

            self.assertFalse(result.ok)
            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                result.errors,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_rejects_manifest_temp_as_archive_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            temp_archive = root / "docs/product/core/source/.source-manifest.json.tmp"
            temp_archive.write_text("not product source\n", encoding="utf-8")
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["archive"]["path"] = "docs/product/core/source/.source-manifest.json.tmp"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            result = product_import_module.mark_product_import_ready(root, reviewed=True)

            self.assertFalse(result.ok)
            self.assertIn(
                "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
                result.errors,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_reports_manifest_write_failure_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")

            original_write_json = product_import_module._write_json

            def raise_os_error(_path: Path, _payload: dict[str, object]) -> None:
                raise OSError(28, "No space left on device")

            product_import_module._write_json = raise_os_error
            try:
                result = product_import_module.mark_product_import_ready(root, reviewed=True)
            finally:
                product_import_module._write_json = original_write_json

            self.assertFalse(result.ok)
            self.assertEqual([], result.updated)
            self.assertIn("failed to update product import readiness: No space left on device", result.errors)
            self.assertEqual("conversion_required", result.manifest["import"]["status"])
            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", manifest["import"]["status"])

    def test_product_mark_ready_reports_product_meta_write_failure_without_partial_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            product_meta_path = root / "docs/product/core/product-meta.md"
            unresolved_path = root / "docs/unresolved.md"
            state_path = root / ".governance/state.json"
            original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            original_product_meta = product_meta_path.read_text(encoding="utf-8")
            original_unresolved = unresolved_path.read_text(encoding="utf-8")
            original_state = json.loads(state_path.read_text(encoding="utf-8"))
            original_write_text = product_import_module._write_text

            def raise_os_error(path: Path, content: str) -> None:
                if path == product_meta_path:
                    raise OSError(28, "No space left on device")
                original_write_text(path, content)

            product_import_module._write_text = raise_os_error
            try:
                result = product_import_module.mark_product_import_ready(root, reviewed=True)
            finally:
                product_import_module._write_text = original_write_text

            self.assertFalse(result.ok)
            self.assertEqual([], result.updated)
            self.assertIn("failed to update product import readiness: No space left on device", result.errors)
            self.assertEqual(original_manifest, json.loads(manifest_path.read_text(encoding="utf-8")))
            self.assertEqual("conversion_required", result.manifest["import"]["status"])
            self.assertEqual(original_product_meta, product_meta_path.read_text(encoding="utf-8"))
            self.assertEqual(original_unresolved, unresolved_path.read_text(encoding="utf-8"))
            self.assertEqual(original_state, json.loads(state_path.read_text(encoding="utf-8")))

    def test_product_mark_ready_rolls_back_document_updates_when_state_update_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            product_meta_path = root / "docs/product/core/product-meta.md"
            unresolved_path = root / "docs/unresolved.md"
            state_path = root / ".governance/state.json"
            original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            original_product_meta = product_meta_path.read_text(encoding="utf-8")
            original_unresolved = unresolved_path.read_text(encoding="utf-8")
            original_state = json.loads(state_path.read_text(encoding="utf-8"))
            original_merge_state = product_import_module.merge_state

            def raise_state_error(root_arg: Path, **_updates: object) -> dict[str, object]:
                raise StateFileError(root_arg / ".governance/state.json", "unwritable: No space left on device")

            product_import_module.merge_state = raise_state_error
            try:
                result = product_import_module.mark_product_import_ready(root, reviewed=True)
            finally:
                product_import_module.merge_state = original_merge_state

            self.assertFalse(result.ok)
            self.assertEqual([], result.updated)
            self.assertTrue(
                any(
                    error.startswith("failed to update product import readiness: invalid governance state file: ")
                    for error in result.errors
                ),
                result.errors,
            )
            self.assertFalse(result.conversion_blocker_resolved)
            self.assertEqual(original_manifest, json.loads(manifest_path.read_text(encoding="utf-8")))
            self.assertEqual("conversion_required", result.manifest["import"]["status"])
            self.assertEqual(original_product_meta, product_meta_path.read_text(encoding="utf-8"))
            self.assertEqual(original_unresolved, unresolved_path.read_text(encoding="utf-8"))
            self.assertEqual(original_state, json.loads(state_path.read_text(encoding="utf-8")))

    def test_product_mark_ready_rejects_invalid_state_without_partial_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = root / "docs/product/core/source/source-manifest.json"
            product_meta_path = root / "docs/product/core/product-meta.md"
            unresolved_path = root / "docs/unresolved.md"
            state_path = root / ".governance/state.json"
            original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            original_product_meta = product_meta_path.read_text(encoding="utf-8")
            original_unresolved = unresolved_path.read_text(encoding="utf-8")
            state_path.write_text("{not json\n", encoding="utf-8")

            result = product_import_module.mark_product_import_ready(root, reviewed=True)

            self.assertFalse(result.ok)
            self.assertEqual([], result.updated)
            self.assertTrue(
                any(
                    error.startswith("product import state is invalid: invalid governance state file: ")
                    for error in result.errors
                ),
                result.errors,
            )
            self.assertEqual(original_manifest, json.loads(manifest_path.read_text(encoding="utf-8")))
            self.assertEqual("conversion_required", result.manifest["import"]["status"])
            self.assertEqual(original_product_meta, product_meta_path.read_text(encoding="utf-8"))
            self.assertEqual(original_unresolved, unresolved_path.read_text(encoding="utf-8"))
            self.assertEqual("{not json\n", state_path.read_text(encoding="utf-8"))

    def test_product_import_atomic_write_cleans_temp_after_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "source-manifest.json"
            path.write_text("# Existing\n", encoding="utf-8")
            temp_path = path.with_name(".source-manifest.json.tmp")
            original_replace = product_import_module.Path.replace

            def fail_replace(self: Path, target: Path) -> Path:
                if self == temp_path and target == path:
                    raise OSError("simulated replace failure")
                return original_replace(self, target)

            product_import_module.Path.replace = fail_replace
            try:
                with self.assertRaises(OSError):
                    product_import_module._write_text(path, "# Updated\n")
            finally:
                product_import_module.Path.replace = original_replace

            self.assertEqual("# Existing\n", path.read_text(encoding="utf-8"))
            self.assertFalse(temp_path.exists())

    def test_target_runtime_marks_converted_product_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.docx"
            product.write_bytes(b"fake docx bytes")
            bootstrap(root, product)
            (root / "docs/product/core/PRD.md").write_text(
                "# Converted Product\n\n"
                "## Goal\n\n"
                "Use reviewed product input for downstream structuring.\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(root / "bin/governance"), "product", "mark-ready", ".", "--reviewed", "--json"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["conversion_blocker_resolved"])
            manifest = json.loads((root / "docs/product/core/source/source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("ready_for_structuring", manifest["import"]["status"])

            gate_result = subprocess.run(
                [str(root / "bin/governance"), "gate", "product-structuring", ".", "--json"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, gate_result.returncode, gate_result.stderr)

    def test_target_runtime_scaffolds_selected_product_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")
            bootstrap(root, product)

            result = subprocess.run(
                [
                    str(root / "bin/governance"),
                    "scaffold",
                    "product",
                    ".",
                    "--chapter",
                    "goals-and-requirements",
                    "--chapter",
                    "acceptance-criteria",
                    "--json",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("docs/product/03-goals-and-requirements.md", payload["created"])
            self.assertIn("docs/product/08-acceptance-criteria.md", payload["created"])
            self.assertIn(
                "[Acceptance Criteria](../08-acceptance-criteria.md)",
                (root / "docs/product/core/product-meta.md").read_text(encoding="utf-8"),
            )

    def test_verify_reports_unregistered_docs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            rogue = root / "docs/superpowers"
            rogue.mkdir()
            (rogue / "note.md").write_text("# Rogue\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("docs/superpowers is not registered in docs/AGENTS.md", report.errors)

    def test_verify_reports_stale_reserved_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            readme = root / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- docs/api: [预留]\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("reserved marker references non-empty docs/api", report.errors)

    def test_verify_reports_blocking_unresolved_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | API | Need auth model | API and backend design | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)
            self.assertIn("blocking unresolved item U-001 affects API and backend design", report.errors)

    def test_verify_allows_non_blocking_unresolved_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-002 | Copy | Confirm button label | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_verify_reports_incomplete_unresolved_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "|  | API |  | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("docs/unresolved.md row (missing id) is missing required fields: ID, Description", report.errors)
            self.assertIn(
                {
                    "code": "unresolved_row_missing_fields",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "docs/unresolved.md row (missing id) is missing required fields: ID, Description",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_unresolved_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | API | Confirm auth model | none | TBD | 2026-06-26 |\n"
                "| U-001 | Backend | Confirm persistence model | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("duplicate unresolved item ID: U-001", report.errors)
            self.assertIn(
                {
                    "code": "unresolved_duplicate_id",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "duplicate unresolved item ID: U-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_unresolved_id_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            unresolved = root / "docs/unresolved.md"
            unresolved.write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| TODO-1 | API | Confirm auth model | none | TBD | 2026-06-26 |\n"
                "| u-001 | Backend | Confirm persistence model | none | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/unresolved.md row TODO-1 must use U-NNN unresolved item ID format",
                report.errors,
            )
            self.assertIn(
                "docs/unresolved.md row u-001 must use U-NNN unresolved item ID format",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "unresolved_invalid_id",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "docs/unresolved.md row TODO-1 must use U-NNN unresolved item ID format",
                },
                [finding.to_dict() for finding in report.findings],
            )
            self.assertIn(
                {
                    "code": "unresolved_invalid_id",
                    "severity": "error",
                    "path": "docs/unresolved.md",
                    "message": "docs/unresolved.md row u-001 must use U-NNN unresolved item ID format",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_incomplete_glossary_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "|  |  |  |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("docs/glossary.md row (missing term) is missing required fields: Term, Meaning, Source", report.errors)
            self.assertIn(
                {
                    "code": "glossary_row_missing_fields",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "docs/glossary.md row (missing term) is missing required fields: Term, Meaning, Source",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning |\n"
                "| --- | --- |\n"
                "| Account | User account |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("docs/glossary.md table is missing required columns: source", report.errors)
            self.assertIn(
                {
                    "code": "glossary_table_missing_columns",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "docs/glossary.md table is missing required columns: source",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_glossary_term(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | docs/product/core/PRD.md |\n"
                "| account | Duplicate spelling | docs/product/core/PRD.md |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("duplicate glossary term: account", report.errors)
            self.assertIn(
                {
                    "code": "glossary_duplicate_term",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "duplicate glossary term: account",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_source_without_local_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | PRD |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("glossary row Account Source field has no local Markdown reference", report.errors)
            self.assertIn(
                {
                    "code": "glossary_source_reference_missing",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "glossary row Account Source field has no local Markdown reference",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_glossary_missing_source_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | docs/product/missing.md |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn("glossary row Account references missing Source target: docs/product/missing.md", report.errors)
            self.assertIn(
                {
                    "code": "glossary_source_reference_missing",
                    "severity": "error",
                    "path": "docs/glossary.md",
                    "message": "glossary row Account references missing Source target: docs/product/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_glossary_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            glossary = root / "docs/glossary.md"
            glossary.write_text(
                "# Glossary\n\n"
                "| Term | Meaning | Source |\n"
                "| --- | --- | --- |\n"
                "| Account | User account | [PRD](product/core/PRD.md) |\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_unindexed_docs_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n", encoding="utf-8")

            report = verify(root)
            self.assertIn("docs/product/01-goals.md is not indexed in docs/product/README.md", report.errors)
            self.assertIn(
                {
                    "code": "docs_readme_unindexed_file",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md is not indexed in docs/product/README.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_indexed_docs_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            readme = root / "docs/product/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `01-goals.md` - goals\n", encoding="utf-8")
            _append_product_meta_chapter(root, "01-goals.md")

            report = verify(root)
            self.assertEqual([], report.errors)

    def test_verify_reports_missing_local_markdown_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSee [API](../api/missing.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")

            report = verify(root)

            self.assertIn("docs/product/01-goals.md links to missing local Markdown target: docs/api/missing.md", report.errors)
            self.assertIn(
                {
                    "code": "docs_local_markdown_link_missing",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md links to missing local Markdown target: docs/api/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_existing_local_markdown_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            _write_indexed_doc(
                root,
                "docs/product/01-goals.md",
                "# Goals\n\n"
                "Source: [PRD](core/PRD.md).\n"
                "See [API](../api/00-conventions.md#http) and [external](https://example.com/spec.md).\n\n"
                "```md\n"
                "[Example](../api/missing-example.md)\n"
                "```\n",
            )
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _append_product_meta_chapter(root, "01-goals.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_product_chapter_missing_source_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nDerived goals.\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")

            report = verify(root)

            self.assertIn("docs/product/01-goals.md must link back to docs/product/core/PRD.md", report.errors)
            self.assertIn("docs/product/core/product-meta.md must link to product chapter: docs/product/01-goals.md", report.errors)
            self.assertIn(
                {
                    "code": "product_chapter_missing_prd_link",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md must link back to docs/product/core/PRD.md",
                },
                [finding.to_dict() for finding in report.findings],
            )
            self.assertIn(
                {
                    "code": "product_meta_missing_chapter_link",
                    "severity": "error",
                    "path": "docs/product/core/product-meta.md",
                    "message": "docs/product/core/product-meta.md must link to product chapter: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_chapter_missing_acceptance_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "08-acceptance-criteria.md", "Acceptance Criteria")

            report = verify(root)

            self.assertIn(
                "docs/product/08-acceptance-criteria.md must define at least one A-NNN acceptance ID",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_acceptance_missing_ids",
                    "severity": "error",
                    "path": "docs/product/08-acceptance-criteria.md",
                    "message": "docs/product/08-acceptance-criteria.md must define at least one A-NNN acceptance ID",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_product_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/product/09-secondary-acceptance.md",
                "# Secondary Acceptance\n\n"
                "Source: [PRD](core/PRD.md).\n\n"
                "## A-001 Secondary Flow\n\n"
                "- This repeats an existing acceptance ID.\n",
            )
            _append_product_meta_chapter(root, "09-secondary-acceptance.md")

            report = verify(root)

            self.assertIn(
                "duplicate product acceptance ID A-001: docs/product/09-secondary-acceptance.md also defined in docs/product/08-acceptance-criteria.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "product_acceptance_duplicate_id",
                    "severity": "error",
                    "path": "docs/product/09-secondary-acceptance.md",
                    "message": "duplicate product acceptance ID A-001: docs/product/09-secondary-acceptance.md also defined in docs/product/08-acceptance-criteria.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_product_chapter_source_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/01-goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "01-goals.md")
            meta = root / "docs/product/core/product-meta.md"
            meta.write_text(meta.read_text(encoding="utf-8") + "\n- [Goals](../01-goals.md)\n", encoding="utf-8")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_invalid_product_chapter_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            chapter = root / "docs/product/goals.md"
            chapter.write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(root / "docs/product/README.md", "goals.md")
            meta = root / "docs/product/core/product-meta.md"
            meta.write_text(meta.read_text(encoding="utf-8") + "\n- [Goals](../goals.md)\n", encoding="utf-8")

            report = verify(root)

            self.assertIn("docs/product/goals.md must use NN-<slug>.md product chapter naming", report.errors)
            self.assertIn(
                {
                    "code": "product_chapter_invalid_filename",
                    "severity": "error",
                    "path": "docs/product/goals.md",
                    "message": "docs/product/goals.md must use NN-<slug>.md product chapter naming",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_product_chapter_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            for filename in ("01-goals.md", "01-scope.md"):
                chapter = root / "docs/product" / filename
                chapter.write_text("# Chapter\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
                _append_index(root / "docs/product/README.md", filename)
                _append_product_meta_chapter(root, filename)

            report = verify(root)

            self.assertIn("duplicate product chapter prefix 01: docs/product/01-goals.md, docs/product/01-scope.md", report.errors)
            self.assertIn(
                {
                    "code": "product_chapter_duplicate_prefix",
                    "severity": "error",
                    "path": "docs/product/01-scope.md",
                    "message": "duplicate product chapter prefix 01: docs/product/01-goals.md, docs/product/01-scope.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_api_conventions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_api_conventions_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/00-conventions.md",
                "# API Conventions\n\n"
                "## Product Links\n\n"
                "- [PRD](../product/core/PRD.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/00-conventions.md is missing API convention sections: "
                "HTTP Conventions, Authentication, Idempotency, Compatibility, Open Decisions",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_conventions_missing_sections",
                    "severity": "error",
                    "path": "docs/api/00-conventions.md",
                    "message": "docs/api/00-conventions.md is missing API convention sections: "
                    "HTTP Conventions, Authentication, Idempotency, Compatibility, Open Decisions",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_conventions_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/api/00-conventions.md",
                _api_conventions_doc().replace(
                    "## Authentication\n\n"
                    "- Mutating endpoints require an authenticated user boundary.\n\n",
                    "## Authentication\n\n- TODO\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/api/00-conventions.md has empty API convention sections: Authentication",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_conventions_empty_sections",
                    "severity": "error",
                    "path": "docs/api/00-conventions.md",
                    "message": "docs/api/00-conventions.md has empty API convention sections: Authentication",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_conventions_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/00-conventions.md",
                _api_conventions_doc("Product scope and acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/api/00-conventions.md must reference existing Product docs",
                "docs/api/00-conventions.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "api_conventions_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/api/00-conventions.md",
                    "message": "docs/api/00-conventions.md must reference existing Product docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_conventions_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/00-conventions.md",
                _api_conventions_doc(
                    "[Missing scope](../product/01-goals.md), "
                    "[Acceptance](../product/08-acceptance-criteria.md)"
                ),
            )

            report = verify(root)

            expected = [
                "docs/api/00-conventions.md references missing Product target: docs/product/01-goals.md",
                "docs/api/00-conventions.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "api_conventions_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/api/00-conventions.md",
                    "message": "docs/api/00-conventions.md references missing Product target: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_api_error_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/error-codes.md", _api_error_codes_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_api_error_codes_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/error-codes.md",
                "# API Error Codes\n\n"
                "## Product Links\n\n"
                "- [PRD](../product/core/PRD.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/error-codes.md is missing API error code sections: "
                "Error Taxonomy, Error Codes, Retry Semantics, Frontend Handling",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_error_codes_missing_sections",
                    "severity": "error",
                    "path": "docs/api/error-codes.md",
                    "message": "docs/api/error-codes.md is missing API error code sections: "
                    "Error Taxonomy, Error Codes, Retry Semantics, Frontend Handling",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_error_codes_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/api/error-codes.md",
                _api_error_codes_doc().replace(
                    "## Retry Semantics\n\n"
                    "- Retry only idempotent requests or writes protected by an idempotency key.\n\n",
                    "## Retry Semantics\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/api/error-codes.md has empty API error code sections: Retry Semantics",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_error_codes_empty_sections",
                    "severity": "error",
                    "path": "docs/api/error-codes.md",
                    "message": "docs/api/error-codes.md has empty API error code sections: Retry Semantics",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_error_codes_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/error-codes.md",
                _api_error_codes_doc("Product scope and acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/api/error-codes.md must reference existing Product docs",
                "docs/api/error-codes.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "api_error_codes_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/api/error-codes.md",
                    "message": "docs/api/error-codes.md must reference existing Product docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_error_codes_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/error-codes.md",
                _api_error_codes_doc(
                    "[Missing scope](../product/01-goals.md), "
                    "[Acceptance](../product/08-acceptance-criteria.md)"
                ),
            )

            report = verify(root)

            expected = [
                "docs/api/error-codes.md references missing Product target: docs/product/01-goals.md",
                "docs/api/error-codes.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "api_error_codes_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/api/error-codes.md",
                    "message": "docs/api/error-codes.md references missing Product target: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_api_changelog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/api/changelog.md", _api_changelog_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_api_changelog_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/changelog.md",
                "# API Changelog\n\n"
                "## Change Log\n\n"
                "- Initial API contract baseline.\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/changelog.md is missing API changelog sections: Compatibility Notes",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_changelog_missing_sections",
                    "severity": "error",
                    "path": "docs/api/changelog.md",
                    "message": "docs/api/changelog.md is missing API changelog sections: Compatibility Notes",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_changelog_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/api/changelog.md",
                _api_changelog_doc().replace(
                    "## Compatibility Notes\n\n"
                    "- Breaking changes require downstream frontend, backend, and test updates in the same delivery slice.\n",
                    "## Compatibility Notes\n\n- TODO\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/api/changelog.md has empty API changelog sections: Compatibility Notes",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_changelog_empty_sections",
                    "severity": "error",
                    "path": "docs/api/changelog.md",
                    "message": "docs/api/changelog.md has empty API changelog sections: Compatibility Notes",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_api_endpoint_contract_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text(
                "# API Endpoints\n\n"
                "- `01-create-user.md` - create user endpoint\n"
                "- `02-list-users.md` - list users endpoint\n",
                encoding="utf-8",
            )
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User"),
                encoding="utf-8",
            )
            (endpoint_readme.parent / "02-list-users.md").write_text(
                _endpoint_contract_doc("List Users"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_api_endpoint_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                "# Create User\n\n"
                "## Method and Path\n\n"
                "POST /users\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md is missing endpoint contract sections: "
                "Auth, Idempotency, Request Fields, Response Fields, Error Codes, Upstream Links, Frontend Consumers",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_missing_sections",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md is missing endpoint contract sections: "
                    "Auth, Idempotency, Request Fields, Response Fields, Error Codes, Upstream Links, Frontend Consumers",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                "# Create User\n\n"
                "## Method and Path\n\n"
                "POST /users\n\n"
                "## Auth\n\n"
                "- TBD\n\n"
                "## Idempotency\n\n"
                "Use Idempotency-Key.\n\n"
                "## Request Fields\n\n"
                "- email\n\n"
                "## Response Fields\n\n"
                "- id\n\n"
                "## Error Codes\n\n"
                "TODO\n\n"
                "## Upstream Links\n\n"
                "- [Product goals](../../product/01-goals.md)\n\n"
                "## Frontend Consumers\n\n"
                "- [API consumption map](../../frontend/02-api-consumption.md)\n",
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md has empty endpoint contract sections: Auth, Error Codes",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_empty_sections",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md has empty endpoint contract sections: Auth, Error Codes",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_invalid_method_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User").replace("GET /example", "Create a user endpoint"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Method and Path section must include an HTTP method and absolute path",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_method_path_invalid",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Method and Path section must include an HTTP method and absolute path",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_error_codes_registry_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", error_codes="- E_EXAMPLE"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Error Codes section must reference docs/api/error-codes.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_error_codes_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Error Codes section must reference docs/api/error-codes.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_error_codes_registry_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md references missing Error Codes registry target: docs/api/error-codes.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_error_codes_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md references missing Error Codes registry target: docs/api/error-codes.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_upstream_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", "- Product goals and architecture context"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Upstream Links section must reference existing local Markdown source",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_upstream_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Upstream Links section must reference existing local Markdown source",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_upstream_reference_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", "- [Missing product source](../../product/missing.md)"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md references missing Upstream Links target: docs/product/missing.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_upstream_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md references missing Upstream Links target: docs/product/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_frontend_consumer_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc("Create User", frontend_consumers="- Web client goal flow"),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md Frontend Consumers section must reference existing local Markdown consumer docs",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_frontend_consumer_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md Frontend Consumers section must reference existing local Markdown consumer docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_api_endpoint_missing_frontend_consumer_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `01-create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "01-create-user.md").write_text(
                _endpoint_contract_doc(
                    "Create User",
                    frontend_consumers="- [Missing consumer](../../frontend/missing.md)",
                ),
                encoding="utf-8",
            )

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/01-create-user.md references missing Frontend Consumers target: docs/frontend/missing.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_frontend_consumer_reference_missing",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-create-user.md",
                    "message": "docs/api/endpoints/01-create-user.md references missing Frontend Consumers target: docs/frontend/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_api_endpoint_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text("# API Endpoints\n\n- `create-user.md` - create user endpoint\n", encoding="utf-8")
            (endpoint_readme.parent / "create-user.md").write_text("# Create User\n", encoding="utf-8")

            report = verify(root)

            self.assertIn(
                "docs/api/endpoints/create-user.md must use NN-<slug>.md endpoint contract naming",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_invalid_filename",
                    "severity": "error",
                    "path": "docs/api/endpoints/create-user.md",
                    "message": "docs/api/endpoints/create-user.md must use NN-<slug>.md endpoint contract naming",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_api_endpoint_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_api_error_codes_doc(root)
            _write_frontend_consumer_doc(root)

            endpoint_readme = root / "docs/api/endpoints/README.md"
            endpoint_readme.parent.mkdir(parents=True, exist_ok=True)
            endpoint_readme.write_text(
                "# API Endpoints\n\n"
                "- `01-create-user.md` - create user endpoint\n"
                "- `01-list-users.md` - list users endpoint\n",
                encoding="utf-8",
            )
            for filename in ("01-create-user.md", "01-list-users.md"):
                (endpoint_readme.parent / filename).write_text(
                    _endpoint_contract_doc("Endpoint"),
                    encoding="utf-8",
                )

            report = verify(root)

            self.assertIn(
                "duplicate API endpoint contract prefix 01: "
                "docs/api/endpoints/01-create-user.md, docs/api/endpoints/01-list-users.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "api_endpoint_duplicate_prefix",
                    "severity": "error",
                    "path": "docs/api/endpoints/01-list-users.md",
                    "message": "duplicate API endpoint contract prefix 01: "
                    "docs/api/endpoints/01-create-user.md, docs/api/endpoints/01-list-users.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_backend_module_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_backend_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                _backend_modules_doc(),
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_backend_module_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                "# Backend Modules\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/backend/01-modules.md is missing backend module sections: "
                "Architecture Links, Modules, API Ownership, Failure Modes, Open Decisions",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "backend_module_missing_sections",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "docs/backend/01-modules.md is missing backend module sections: "
                    "Architecture Links, Modules, API Ownership, Failure Modes, Open Decisions",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_module_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_backend_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                _backend_modules_doc().replace(
                    "## Failure Modes\n\n"
                    "- Persistence failures follow [Data model](02-data-model.md).\n"
                    "- Dependency failures follow [External services](03-external-services.md).\n\n",
                    "## Failure Modes\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/backend/01-modules.md has empty backend module sections: Failure Modes",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "backend_module_empty_sections",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "docs/backend/01-modules.md has empty backend module sections: Failure Modes",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_module_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                _backend_modules_doc(
                    architecture="System context",
                    api="API conventions",
                    data_model="Data model",
                    external_services="External services",
                    acceptance="Acceptance criteria",
                ),
            )

            report = verify(root)

            expected = [
                "docs/backend/01-modules.md must reference existing Architecture docs",
                "docs/backend/01-modules.md must reference existing API docs",
                "docs/backend/01-modules.md must reference docs/backend/02-data-model.md",
                "docs/backend/01-modules.md must reference docs/backend/03-external-services.md",
                "docs/backend/01-modules.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "docs/backend/01-modules.md must reference existing Architecture docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_module_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/backend/01-modules.md",
                _backend_modules_doc(
                    architecture="[Missing architecture](../architecture/missing.md)",
                    api="[Missing API](../api/missing.md)",
                ),
            )

            report = verify(root)

            expected = [
                "docs/backend/01-modules.md references missing Architecture target: docs/architecture/missing.md",
                "docs/backend/01-modules.md references missing API target: docs/api/missing.md",
                "docs/backend/01-modules.md references missing Data Model target: docs/backend/02-data-model.md",
                "docs/backend/01-modules.md references missing External Services target: docs/backend/03-external-services.md",
                "docs/backend/01-modules.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/01-modules.md",
                    "message": "docs/backend/01-modules.md references missing Architecture target: docs/architecture/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_backend_data_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/backend/01-modules.md", _backend_modules_doc())
            _write_indexed_doc(root, "docs/backend/02-data-model.md", _backend_data_model_doc())
            _write_indexed_doc(root, "docs/backend/03-external-services.md", _backend_external_services_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_backend_data_model_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/backend/02-data-model.md",
                "# Data Model\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/backend/02-data-model.md is missing data model sections: "
                "Owners, Entities, State Machines, Constraints, Indexes, Migrations",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "backend_data_model_missing_sections",
                    "severity": "error",
                    "path": "docs/backend/02-data-model.md",
                    "message": "docs/backend/02-data-model.md is missing data model sections: "
                    "Owners, Entities, State Machines, Constraints, Indexes, Migrations",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_data_model_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/backend/01-modules.md", _backend_modules_doc())
            _write_indexed_doc(root, "docs/backend/03-external-services.md", _backend_external_services_doc())
            _write_indexed_doc(
                root,
                "docs/backend/02-data-model.md",
                _backend_data_model_doc().replace(
                    "## Entities\n\n"
                    "- Goal: user-owned workflow item with status and audit fields.\n\n",
                    "## Entities\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/backend/02-data-model.md has empty data model sections: Entities",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "backend_data_model_empty_sections",
                    "severity": "error",
                    "path": "docs/backend/02-data-model.md",
                    "message": "docs/backend/02-data-model.md has empty data model sections: Entities",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_data_model_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/backend/02-data-model.md",
                _backend_data_model_doc(
                    backend_modules="Backend modules",
                    api="API conventions",
                    acceptance="Acceptance criteria",
                ),
            )

            report = verify(root)

            expected = [
                "docs/backend/02-data-model.md must reference docs/backend/01-modules.md",
                "docs/backend/02-data-model.md must reference existing API docs",
                "docs/backend/02-data-model.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_data_model_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/02-data-model.md",
                    "message": "docs/backend/02-data-model.md must reference docs/backend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_data_model_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/backend/02-data-model.md", _backend_data_model_doc())

            report = verify(root)

            expected = [
                "docs/backend/02-data-model.md references missing Backend Modules target: docs/backend/01-modules.md",
                "docs/backend/02-data-model.md references missing API target: docs/api/00-conventions.md",
                "docs/backend/02-data-model.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_data_model_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/02-data-model.md",
                    "message": "docs/backend/02-data-model.md references missing Backend Modules target: docs/backend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_backend_external_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/backend/01-modules.md", _backend_modules_doc())
            _write_indexed_doc(root, "docs/backend/02-data-model.md", _backend_data_model_doc())
            _write_indexed_doc(root, "docs/backend/03-external-services.md", _backend_external_services_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_backend_external_services_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/backend/03-external-services.md",
                "# External Services\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/backend/03-external-services.md is missing external services sections: "
                "Dependencies, Contracts, Retries, Timeouts, Authentication, Observability",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "backend_external_services_missing_sections",
                    "severity": "error",
                    "path": "docs/backend/03-external-services.md",
                    "message": "docs/backend/03-external-services.md is missing external services sections: "
                    "Dependencies, Contracts, Retries, Timeouts, Authentication, Observability",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_external_services_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/backend/01-modules.md", _backend_modules_doc())
            _write_indexed_doc(root, "docs/backend/02-data-model.md", _backend_data_model_doc())
            _write_indexed_doc(
                root,
                "docs/backend/03-external-services.md",
                _backend_external_services_doc().replace(
                    "## Contracts\n\n"
                    "- Internal module contracts remain documented in backend modules and API docs.\n\n",
                    "## Contracts\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/backend/03-external-services.md has empty external services sections: Contracts",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "backend_external_services_empty_sections",
                    "severity": "error",
                    "path": "docs/backend/03-external-services.md",
                    "message": "docs/backend/03-external-services.md has empty external services sections: Contracts",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_external_services_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/backend/03-external-services.md",
                _backend_external_services_doc(
                    backend_modules="Backend modules",
                    api="API conventions",
                    acceptance="Acceptance criteria",
                ),
            )

            report = verify(root)

            expected = [
                "docs/backend/03-external-services.md must reference docs/backend/01-modules.md",
                "docs/backend/03-external-services.md must reference existing API docs",
                "docs/backend/03-external-services.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_external_services_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/03-external-services.md",
                    "message": "docs/backend/03-external-services.md must reference docs/backend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_backend_external_services_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/backend/03-external-services.md", _backend_external_services_doc())

            report = verify(root)

            expected = [
                "docs/backend/03-external-services.md references missing Backend Modules target: docs/backend/01-modules.md",
                "docs/backend/03-external-services.md references missing API target: docs/api/00-conventions.md",
                "docs/backend/03-external-services.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "backend_external_services_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/backend/03-external-services.md",
                    "message": "docs/backend/03-external-services.md references missing Backend Modules target: docs/backend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_ui_interaction_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/ui/01-interaction-model.md", _ui_interaction_model_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_ui_interaction_model_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/ui/01-interaction-model.md",
                "# Interaction Model\n\n"
                "## Product Links\n\n"
                "- [PRD](../product/core/PRD.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/ui/01-interaction-model.md is missing UI interaction sections: "
                "Primary Flows, Screens, States, Errors, Accessibility",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "ui_interaction_model_missing_sections",
                    "severity": "error",
                    "path": "docs/ui/01-interaction-model.md",
                    "message": "docs/ui/01-interaction-model.md is missing UI interaction sections: "
                    "Primary Flows, Screens, States, Errors, Accessibility",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_ui_interaction_model_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/ui/01-interaction-model.md",
                _ui_interaction_model_doc().replace(
                    "## Errors\n\n"
                    "- User-correctable errors map to visible correction actions.\n\n",
                    "## Errors\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/ui/01-interaction-model.md has empty UI interaction sections: Errors",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "ui_interaction_model_empty_sections",
                    "severity": "error",
                    "path": "docs/ui/01-interaction-model.md",
                    "message": "docs/ui/01-interaction-model.md has empty UI interaction sections: Errors",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_ui_interaction_model_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/ui/01-interaction-model.md",
                _ui_interaction_model_doc("Product scope and acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/ui/01-interaction-model.md must reference existing Product docs",
                "docs/ui/01-interaction-model.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "ui_interaction_model_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/ui/01-interaction-model.md",
                    "message": "docs/ui/01-interaction-model.md must reference existing Product docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_ui_interaction_model_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/ui/01-interaction-model.md",
                _ui_interaction_model_doc(
                    "[Missing scope](../product/01-goals.md), "
                    "[Acceptance](../product/08-acceptance-criteria.md)"
                ),
            )

            report = verify(root)

            expected = [
                "docs/ui/01-interaction-model.md references missing Product target: docs/product/01-goals.md",
                "docs/ui/01-interaction-model.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "ui_interaction_model_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/ui/01-interaction-model.md",
                    "message": "docs/ui/01-interaction-model.md references missing Product target: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_frontend_module_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_frontend_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                _frontend_modules_doc(),
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_frontend_module_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                "# Frontend Modules\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/frontend/01-modules.md is missing frontend module sections: "
                "UI Links, Modules, State Ownership, Routes, Open Decisions",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "frontend_module_missing_sections",
                    "severity": "error",
                    "path": "docs/frontend/01-modules.md",
                    "message": "docs/frontend/01-modules.md is missing frontend module sections: "
                    "UI Links, Modules, State Ownership, Routes, Open Decisions",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_module_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_frontend_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                _frontend_modules_doc().replace(
                    "## State Ownership\n\n"
                    "- API-backed state follows [API consumption](02-api-consumption.md).\n\n",
                    "## State Ownership\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/frontend/01-modules.md has empty frontend module sections: State Ownership",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "frontend_module_empty_sections",
                    "severity": "error",
                    "path": "docs/frontend/01-modules.md",
                    "message": "docs/frontend/01-modules.md has empty frontend module sections: State Ownership",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_module_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                _frontend_modules_doc(
                    ui="Interaction model",
                    api="API conventions",
                    api_consumption="API consumption",
                    acceptance="Acceptance criteria",
                ),
            )

            report = verify(root)

            expected = [
                "docs/frontend/01-modules.md must reference existing UI docs",
                "docs/frontend/01-modules.md must reference existing API docs",
                "docs/frontend/01-modules.md must reference docs/frontend/02-api-consumption.md",
                "docs/frontend/01-modules.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "frontend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/frontend/01-modules.md",
                    "message": "docs/frontend/01-modules.md must reference existing UI docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_module_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/frontend/01-modules.md",
                _frontend_modules_doc(
                    ui="[Missing UI](../ui/missing.md)",
                    api="[Missing API](../api/missing.md)",
                ),
            )

            report = verify(root)

            expected = [
                "docs/frontend/01-modules.md references missing UI target: docs/ui/missing.md",
                "docs/frontend/01-modules.md references missing API target: docs/api/missing.md",
                "docs/frontend/01-modules.md references missing API Consumption target: docs/frontend/02-api-consumption.md",
                "docs/frontend/01-modules.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "frontend_module_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/frontend/01-modules.md",
                    "message": "docs/frontend/01-modules.md references missing UI target: docs/ui/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_frontend_api_consumption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_indexed_doc(root, "docs/ui/01-interaction-model.md", _ui_interaction_model_doc())
            _write_indexed_doc(root, "docs/frontend/01-modules.md", _frontend_modules_doc())
            _write_indexed_doc(root, "docs/frontend/02-api-consumption.md", _frontend_api_consumption_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_frontend_api_consumption_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/frontend/02-api-consumption.md",
                "# API Consumption\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/frontend/02-api-consumption.md is missing API consumption sections: "
                "API Links, Consumption Map, Loading States, Error Actions",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "frontend_api_consumption_missing_sections",
                    "severity": "error",
                    "path": "docs/frontend/02-api-consumption.md",
                    "message": "docs/frontend/02-api-consumption.md is missing API consumption sections: "
                    "API Links, Consumption Map, Loading States, Error Actions",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_api_consumption_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_indexed_doc(root, "docs/ui/01-interaction-model.md", _ui_interaction_model_doc())
            _write_indexed_doc(root, "docs/frontend/01-modules.md", _frontend_modules_doc())
            _write_indexed_doc(
                root,
                "docs/frontend/02-api-consumption.md",
                _frontend_api_consumption_doc().replace(
                    "## Loading States\n\n"
                    "- Loading states keep the primary goal flow responsive while API requests are in flight.\n\n",
                    "## Loading States\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/frontend/02-api-consumption.md has empty API consumption sections: Loading States",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "frontend_api_consumption_empty_sections",
                    "severity": "error",
                    "path": "docs/frontend/02-api-consumption.md",
                    "message": "docs/frontend/02-api-consumption.md has empty API consumption sections: Loading States",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_api_consumption_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/frontend/02-api-consumption.md",
                _frontend_api_consumption_doc(
                    frontend_modules="Frontend modules",
                    api="API conventions",
                    acceptance="Acceptance criteria",
                ),
            )

            report = verify(root)

            expected = [
                "docs/frontend/02-api-consumption.md must reference docs/frontend/01-modules.md",
                "docs/frontend/02-api-consumption.md must reference existing API docs",
                "docs/frontend/02-api-consumption.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "frontend_api_consumption_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/frontend/02-api-consumption.md",
                    "message": "docs/frontend/02-api-consumption.md must reference docs/frontend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_frontend_api_consumption_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/frontend/02-api-consumption.md", _frontend_api_consumption_doc())

            report = verify(root)

            expected = [
                "docs/frontend/02-api-consumption.md references missing Frontend Modules target: docs/frontend/01-modules.md",
                "docs/frontend/02-api-consumption.md references missing API target: docs/api/00-conventions.md",
                "docs/frontend/02-api-consumption.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "frontend_api_consumption_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/frontend/02-api-consumption.md",
                    "message": "docs/frontend/02-api-consumption.md references missing Frontend Modules target: docs/frontend/01-modules.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_architecture_system_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_architecture_system_context_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/01-system-context.md",
                "# System Context\n\n"
                "## Product Links\n\n"
                "- [PRD](../product/core/PRD.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/architecture/01-system-context.md is missing system context sections: "
                "Actors, External Systems, Trust Boundaries, Open Decisions",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "architecture_system_context_missing_sections",
                    "severity": "error",
                    "path": "docs/architecture/01-system-context.md",
                    "message": "docs/architecture/01-system-context.md is missing system context sections: "
                    "Actors, External Systems, Trust Boundaries, Open Decisions",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_system_context_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/architecture/01-system-context.md",
                _architecture_system_context_doc().replace(
                    "## Actors\n\n"
                    "- Primary user\n\n",
                    "## Actors\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/architecture/01-system-context.md has empty system context sections: Actors",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "architecture_system_context_empty_sections",
                    "severity": "error",
                    "path": "docs/architecture/01-system-context.md",
                    "message": "docs/architecture/01-system-context.md has empty system context sections: Actors",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_system_context_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/01-system-context.md",
                _architecture_system_context_doc("Product scope and acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/architecture/01-system-context.md must reference existing Product docs",
                "docs/architecture/01-system-context.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "architecture_system_context_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/architecture/01-system-context.md",
                    "message": "docs/architecture/01-system-context.md must reference existing Product docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_system_context_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/01-system-context.md",
                _architecture_system_context_doc(
                    "[Missing scope](../product/01-goals.md), "
                    "[Acceptance](../product/08-acceptance-criteria.md)"
                ),
            )

            report = verify(root)

            expected = [
                "docs/architecture/01-system-context.md references missing Product target: docs/product/01-goals.md",
                "docs/architecture/01-system-context.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "architecture_system_context_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/architecture/01-system-context.md",
                    "message": "docs/architecture/01-system-context.md references missing Product target: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_architecture_containers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/architecture/02-containers.md", _architecture_containers_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_architecture_containers_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/02-containers.md",
                "# Containers\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/architecture/02-containers.md is missing container sections: "
                "Containers, Runtime Responsibilities, Data Ownership, Open Decisions",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "architecture_containers_missing_sections",
                    "severity": "error",
                    "path": "docs/architecture/02-containers.md",
                    "message": "docs/architecture/02-containers.md is missing container sections: "
                    "Containers, Runtime Responsibilities, Data Ownership, Open Decisions",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_containers_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(
                root,
                "docs/architecture/02-containers.md",
                _architecture_containers_doc().replace(
                    "## Runtime Responsibilities\n\n"
                    "- The API service validates and persists goal flow changes.\n\n",
                    "## Runtime Responsibilities\n\n- TODO\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/architecture/02-containers.md has empty container sections: Runtime Responsibilities",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "architecture_containers_empty_sections",
                    "severity": "error",
                    "path": "docs/architecture/02-containers.md",
                    "message": "docs/architecture/02-containers.md has empty container sections: Runtime Responsibilities",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_containers_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/02-containers.md",
                _architecture_containers_doc(system_context="System context", acceptance="Acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/architecture/02-containers.md must reference docs/architecture/01-system-context.md",
                "docs/architecture/02-containers.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "architecture_containers_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/architecture/02-containers.md",
                    "message": "docs/architecture/02-containers.md must reference docs/architecture/01-system-context.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_containers_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/architecture/02-containers.md", _architecture_containers_doc())

            report = verify(root)

            expected = [
                "docs/architecture/02-containers.md references missing System Context target: docs/architecture/01-system-context.md",
                "docs/architecture/02-containers.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "architecture_containers_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/architecture/02-containers.md",
                    "message": "docs/architecture/02-containers.md references missing System Context target: docs/architecture/01-system-context.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_complete_architecture_quality_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/architecture/02-containers.md", _architecture_containers_doc())
            _write_indexed_doc(root, "docs/architecture/03-quality-attributes.md", _architecture_quality_attributes_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_architecture_quality_attributes_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/03-quality-attributes.md",
                "# Quality Attributes\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/architecture/03-quality-attributes.md is missing quality attribute sections: "
                "Availability, Performance, Security, Observability, Tradeoffs",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "architecture_quality_attributes_missing_sections",
                    "severity": "error",
                    "path": "docs/architecture/03-quality-attributes.md",
                    "message": "docs/architecture/03-quality-attributes.md is missing quality attribute sections: "
                    "Availability, Performance, Security, Observability, Tradeoffs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_quality_attributes_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/architecture/02-containers.md", _architecture_containers_doc())
            _write_indexed_doc(
                root,
                "docs/architecture/03-quality-attributes.md",
                _architecture_quality_attributes_doc().replace(
                    "## Performance\n\n"
                    "- Primary goal-flow reads should complete within documented product expectations.\n\n",
                    "## Performance\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/architecture/03-quality-attributes.md has empty quality attribute sections: Performance",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "architecture_quality_attributes_empty_sections",
                    "severity": "error",
                    "path": "docs/architecture/03-quality-attributes.md",
                    "message": "docs/architecture/03-quality-attributes.md has empty quality attribute sections: Performance",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_quality_attributes_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/architecture/03-quality-attributes.md",
                _architecture_quality_attributes_doc(containers="Containers", acceptance="Acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/architecture/03-quality-attributes.md must reference docs/architecture/02-containers.md",
                "docs/architecture/03-quality-attributes.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "architecture_quality_attributes_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/architecture/03-quality-attributes.md",
                    "message": "docs/architecture/03-quality-attributes.md must reference docs/architecture/02-containers.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_architecture_quality_attributes_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/architecture/03-quality-attributes.md", _architecture_quality_attributes_doc())

            report = verify(root)

            expected = [
                "docs/architecture/03-quality-attributes.md references missing Containers target: docs/architecture/02-containers.md",
                "docs/architecture/03-quality-attributes.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "architecture_quality_attributes_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/architecture/03-quality-attributes.md",
                    "message": "docs/architecture/03-quality-attributes.md references missing Containers target: docs/architecture/02-containers.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_test_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_test_strategy_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/01-strategy.md",
                _test_strategy_doc(),
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_test_strategy_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/tests/01-strategy.md",
                "# Test Strategy\n\n"
                "## Product Links\n\n"
                "- [Acceptance](../product/08-acceptance-criteria.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/tests/01-strategy.md is missing test strategy sections: "
                "Acceptance Links, Test Layers, Risk Coverage, Non-Functional Checks",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "test_strategy_missing_sections",
                    "severity": "error",
                    "path": "docs/tests/01-strategy.md",
                    "message": "docs/tests/01-strategy.md is missing test strategy sections: "
                    "Acceptance Links, Test Layers, Risk Coverage, Non-Functional Checks",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_test_strategy_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_test_strategy_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/01-strategy.md",
                _test_strategy_doc().replace(
                    "## Risk Coverage\n\n"
                    "- Goal-flow risks are mapped back to acceptance and design sources before implementation.\n\n",
                    "## Risk Coverage\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/tests/01-strategy.md has empty test strategy sections: Risk Coverage",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "test_strategy_empty_sections",
                    "severity": "error",
                    "path": "docs/tests/01-strategy.md",
                    "message": "docs/tests/01-strategy.md has empty test strategy sections: Risk Coverage",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_test_strategy_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/tests/01-strategy.md",
                _test_strategy_doc(
                    acceptance="Acceptance criteria",
                    api="API conventions",
                    design="System context",
                ),
            )

            report = verify(root)

            expected = [
                "docs/tests/01-strategy.md must reference a product acceptance chapter",
                "docs/tests/01-strategy.md must reference existing API docs",
                "docs/tests/01-strategy.md must reference existing Design docs",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "test_strategy_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/tests/01-strategy.md",
                    "message": "docs/tests/01-strategy.md must reference a product acceptance chapter",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_test_strategy_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/tests/01-strategy.md",
                _test_strategy_doc(),
            )

            report = verify(root)

            expected = [
                "docs/tests/01-strategy.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
                "docs/tests/01-strategy.md references missing API target: docs/api/00-conventions.md",
                "docs/tests/01-strategy.md references missing Design target: docs/architecture/01-system-context.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "test_strategy_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/tests/01-strategy.md",
                    "message": "docs/tests/01-strategy.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_acceptance_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(root, "docs/tests/02-acceptance-matrix.md", _acceptance_matrix_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_allows_uncovered_acceptance_matrix_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _append_acceptance_criterion(root, "A-002", "Deferred Flow")
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc().replace("- none\n", "- A-002 deferred until follow-up scope.\n"),
            )

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_acceptance_matrix_unknown_uncovered_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc().replace("- none\n", "- A-999 deferred until follow-up scope.\n"),
            )

            report = verify(root)

            self.assertIn(
                "acceptance matrix Uncovered Criteria references unknown product acceptance IDs: A-999",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_uncovered_id_unknown",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix Uncovered Criteria references unknown product acceptance IDs: A-999",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_missing_product_acceptance_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _append_acceptance_criterion(root, "A-002", "Deferred Flow")
            _write_indexed_doc(root, "docs/tests/02-acceptance-matrix.md", _acceptance_matrix_doc())

            report = verify(root)

            self.assertIn(
                "acceptance matrix must map or list uncovered product acceptance IDs: A-002",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_product_coverage_missing",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix must map or list uncovered product acceptance IDs: A-002",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                "# Acceptance Matrix\n\n"
                "| Acceptance | Design | API | Test |\n"
                "| --- | --- | --- | --- |\n"
                "| [A-001](../product/08-acceptance-criteria.md#a-001) | [System context](../architecture/01-system-context.md) | [Goal endpoint](../api/endpoints/01-goal-flow.md) | [Test strategy](01-strategy.md) |\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/tests/02-acceptance-matrix.md is missing acceptance matrix sections: Matrix, Uncovered Criteria",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_missing_sections",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "docs/tests/02-acceptance-matrix.md is missing acceptance matrix sections: Matrix, Uncovered Criteria",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc().replace(
                    "## Uncovered Criteria\n\n"
                    "- none\n",
                    "## Uncovered Criteria\n\n"
                    "- TBD\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/tests/02-acceptance-matrix.md has empty acceptance matrix sections: Uncovered Criteria",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_empty_sections",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "docs/tests/02-acceptance-matrix.md has empty acceptance matrix sections: Uncovered Criteria",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                "# Acceptance Matrix\n\n"
                "| Acceptance | Design |\n"
                "| --- | --- |\n"
                "| [A-001](../product/08-acceptance-criteria.md#a-001) | [System context](../architecture/01-system-context.md) |\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/tests/02-acceptance-matrix.md table is missing required columns: API, Test",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_missing_columns",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "docs/tests/02-acceptance-matrix.md table is missing required columns: API, Test",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc(
                    acceptance="A-001 acceptance criterion",
                    design="System context",
                    api="API conventions",
                    test="Test strategy",
                ),
            )

            report = verify(root)

            expected = [
                "acceptance matrix row A-001 acceptance criterion Acceptance field has no local Markdown reference",
                "acceptance matrix row A-001 acceptance criterion Design field has no local Markdown reference",
                "acceptance matrix row A-001 acceptance criterion API field has no local Markdown reference",
                "acceptance matrix row A-001 acceptance criterion Test field has no local Markdown reference",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "acceptance_matrix_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix row A-001 acceptance criterion Acceptance field has no local Markdown reference",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_invalid_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc(
                    acceptance="[Acceptance](../product/08-acceptance-criteria.md)",
                ),
            )

            report = verify(root)

            self.assertIn(
                "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance field must include A-NNN acceptance ID",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_invalid_acceptance_id",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance field must include A-NNN acceptance ID",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_api_without_endpoint_contract_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc(api="[API conventions](../api/00-conventions.md)"),
            )

            report = verify(root)

            self.assertIn(
                "acceptance matrix row docs/product/08-acceptance-criteria.md API field must reference an API endpoint contract under docs/api/endpoints/NN-<slug>.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_api_endpoint_reference_missing",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix row docs/product/08-acceptance-criteria.md API field must reference an API endpoint contract under docs/api/endpoints/NN-<slug>.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_lowercase_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc(
                    acceptance="[a-001](../product/08-acceptance-criteria.md#a-001)",
                ),
            )

            report = verify(root)

            self.assertIn(
                "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance field must include A-NNN acceptance ID",
                report.errors,
            )

    def test_verify_reports_duplicate_acceptance_matrix_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                "# Acceptance Matrix\n\n"
                "## Matrix\n\n"
                "| Acceptance | Design | API | Test |\n"
                "| --- | --- | --- | --- |\n"
                "| [A-001](../product/08-acceptance-criteria.md#a-001) | [System context](../architecture/01-system-context.md) | [Goal endpoint](../api/endpoints/01-goal-flow.md) | [Test strategy](01-strategy.md) |\n"
                "| [A-001 retry](../product/08-acceptance-criteria.md#a-001-retry) | [System context](../architecture/01-system-context.md) | [Goal endpoint](../api/endpoints/01-goal-flow.md) | [Test strategy](01-strategy.md) |\n\n"
                "## Uncovered Criteria\n\n"
                "- none\n",
            )

            report = verify(root)

            self.assertIn("duplicate acceptance matrix Acceptance ID: A-001", report.errors)
            self.assertIn(
                {
                    "code": "acceptance_matrix_duplicate_acceptance_id",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "duplicate acceptance matrix Acceptance ID: A-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_unknown_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc(
                    acceptance="[A-999](../product/08-acceptance-criteria.md#a-999)",
                ),
            )

            report = verify(root)

            self.assertIn(
                "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance ID A-999 is not defined in referenced product acceptance chapter",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_acceptance_id_unknown",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance ID A-999 is not defined in referenced product acceptance chapter",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_does_not_report_acceptance_matrix_unknown_id_for_unreadable_acceptance_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            (root / "docs/product/08-acceptance-criteria.md").write_bytes(b"\xff")
            _write_indexed_doc(root, "docs/tests/02-acceptance-matrix.md", _acceptance_matrix_doc())

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/product/08-acceptance-criteria.md must be UTF-8", report.errors)
            self.assertNotIn(
                "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance ID A-001 is not defined in referenced product acceptance chapter",
                report.errors,
            )

    def test_verify_reports_acceptance_matrix_acceptance_anchor_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc(
                    acceptance="[A-001](../product/08-acceptance-criteria.md#a-999)",
                ),
            )

            report = verify(root)

            self.assertIn(
                "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance link fragment A-999 does not match Acceptance ID A-001",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "acceptance_matrix_acceptance_anchor_mismatch",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance link fragment A-999 does not match Acceptance ID A-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_acceptance_matrix_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/tests/02-acceptance-matrix.md", _acceptance_matrix_doc())

            report = verify(root)

            expected = [
                "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance references missing target: docs/product/08-acceptance-criteria.md",
                "acceptance matrix row docs/product/08-acceptance-criteria.md Design references missing target: docs/architecture/01-system-context.md",
                "acceptance matrix row docs/product/08-acceptance-criteria.md API references missing target: docs/api/endpoints/01-goal-flow.md",
                "acceptance matrix row docs/product/08-acceptance-criteria.md Test references missing target: docs/tests/01-strategy.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "acceptance_matrix_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/tests/02-acceptance-matrix.md",
                    "message": "acceptance matrix row docs/product/08-acceptance-criteria.md Acceptance references missing target: docs/product/08-acceptance-criteria.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_adr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/decisions/001-runtime-boundary.md", _adr_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_allows_adr_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/decisions/001-runtime-boundary.md", _adr_doc())
            _write_indexed_doc(root, "docs/decisions/002-data-boundary.md", _adr_doc())

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_invalid_adr_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/decisions/runtime-boundary.md", _adr_doc())

            report = verify(root)

            self.assertIn("docs/decisions/runtime-boundary.md must use NNN-<slug>.md ADR naming", report.errors)
            self.assertIn(
                {
                    "code": "adr_invalid_filename",
                    "severity": "error",
                    "path": "docs/decisions/runtime-boundary.md",
                    "message": "docs/decisions/runtime-boundary.md must use NNN-<slug>.md ADR naming",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_adr_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-system-context.md", _architecture_system_context_doc())
            _write_indexed_doc(root, "docs/decisions/001-runtime-boundary.md", _adr_doc())
            _write_indexed_doc(root, "docs/decisions/001-data-boundary.md", _adr_doc())

            report = verify(root)

            self.assertIn(
                "duplicate ADR prefix 001: docs/decisions/001-data-boundary.md, docs/decisions/001-runtime-boundary.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_duplicate_prefix",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "duplicate ADR prefix 001: "
                    "docs/decisions/001-data-boundary.md, docs/decisions/001-runtime-boundary.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                "# ADR-001: Choose Runtime Boundary\n\n"
                "## Context\n\n"
                "Runtime boundary context.\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md is missing ADR sections: Decision, Consequences, References",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_missing_sections",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md is missing ADR sections: Decision, Consequences, References",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                "# ADR-001: Choose Runtime Boundary\n\n"
                "## Context\n\n"
                "TBD\n\n"
                "## Decision\n\n"
                "Use a modular monolith boundary.\n\n"
                "## Consequences\n\n"
                "Deployment remains simple.\n\n"
                "## References\n\n"
                "- [System context](../architecture/01-system-context.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md has empty ADR sections: Context",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_empty_sections",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md has empty ADR sections: Context",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_missing_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                _adr_doc("- System context and module tradeoffs"),
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md References section must reference existing local Markdown sources",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_reference_missing",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md References section must reference existing local Markdown sources",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_adr_missing_reference_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/decisions/001-runtime-boundary.md",
                _adr_doc("- [Missing source](../architecture/missing.md)"),
            )

            report = verify(root)

            self.assertIn(
                "docs/decisions/001-runtime-boundary.md references missing ADR References target: docs/architecture/missing.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "adr_reference_missing",
                    "severity": "error",
                    "path": "docs/decisions/001-runtime-boundary.md",
                    "message": "docs/decisions/001-runtime-boundary.md references missing ADR References target: docs/architecture/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "docs/development/02-task-board.md is missing task board sections: "
                "Task Table, Status Policy, Traceability Rules",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_missing_sections",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "docs/development/02-task-board.md is missing task board sections: "
                    "Task Table, Status Policy, Traceability Rules",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            _write_indexed_doc(
                root,
                "docs/development/02-task-board.md",
                "# Task Board\n\n"
                "## Task Table\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n\n"
                "## Status Policy\n\n"
                "- TBD\n\n"
                "## Traceability Rules\n\n"
                "- TODO\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/development/02-task-board.md has empty task board sections: Status Policy, Traceability Rules",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_empty_sections",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "docs/development/02-task-board.md has empty task board sections: "
                    "Status Policy, Traceability Rules",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_missing_trace_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | TBD | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `02-task-board.md` - task board\n", encoding="utf-8")

            report = verify(root)

            self.assertIn("task board row TASK-001 is missing required fields: API", report.errors)
            self.assertIn(
                {
                    "code": "task_board_row_missing_fields",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 is missing required fields: API",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_traceable_task_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | [Goals](../product/01-goals.md) | docs/architecture/01-context.md#actors | `docs/api/00-conventions.md` | [Acceptance](../product/08-acceptance-criteria.md) | make test |\n"
                ),
                encoding="utf-8",
            )
            readme = root / "docs/development/README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n- `02-task-board.md` - task board\n", encoding="utf-8")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_task_board_acceptance_without_product_acceptance_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/tests/01-strategy.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-001 Acceptance field must reference a product acceptance chapter",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_acceptance_reference_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 Acceptance field must reference a product acceptance chapter",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_acceptance_without_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "## Task Table\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | [Acceptance](../product/08-acceptance-criteria.md) | make test |\n\n"
                "## Status Policy\n\n"
                "- Use Backlog, Ready, In Progress, Blocked, Done, or Deferred consistently with the implementation gate.\n\n"
                "## Traceability Rules\n\n"
                "- Product, Design, API, and Acceptance fields must link to existing local Markdown sources.\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-001 Acceptance field must include A-NNN acceptance ID", report.errors)
            self.assertIn(
                {
                    "code": "task_board_acceptance_id_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 Acceptance field must include A-NNN acceptance ID",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_unknown_acceptance_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | [A-999](../product/08-acceptance-criteria.md#a-999) | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-001 Acceptance ID A-999 is not defined in referenced product acceptance chapter",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_acceptance_id_unknown",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 Acceptance ID A-999 is not defined in referenced product acceptance chapter",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_does_not_report_task_board_unknown_id_for_unreadable_acceptance_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            (root / "docs/product/08-acceptance-criteria.md").write_bytes(b"\xff")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | [A-001](../product/08-acceptance-criteria.md#a-001) | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/product/08-acceptance-criteria.md must be UTF-8", report.errors)
            self.assertNotIn(
                "task board row TASK-001 Acceptance ID A-001 is not defined in referenced product acceptance chapter",
                report.errors,
            )

    def test_verify_reports_task_board_acceptance_missing_from_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _append_acceptance_criterion(root, "A-002", "Deferred Flow")
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_acceptance_matrix_trace_docs(root)
            _write_indexed_doc(
                root,
                "docs/tests/02-acceptance-matrix.md",
                _acceptance_matrix_doc().replace("- none\n", "- A-002 deferred until follow-up scope.\n"),
            )
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status | Milestone |\n"
                        "| --- | --- | --- |\n"
                        "| TASK-001 | Ready | Goal flow |\n"
                        "| TASK-002 | Backlog | Deferred flow |\n"
                    )
                ),
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Backlog | Implement deferred flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | [A-002](../product/08-acceptance-criteria.md#a-002) | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-002 Acceptance ID A-002 is not mapped in docs/tests/02-acceptance-matrix.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_acceptance_matrix_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 Acceptance ID A-002 is not mapped in docs/tests/02-acceptance-matrix.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_acceptance_anchor_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | [A-001](../product/08-acceptance-criteria.md#a-999) | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-001 Acceptance link fragment A-999 does not match Acceptance ID A-001",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_acceptance_anchor_mismatch",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 Acceptance link fragment A-999 does not match Acceptance ID A-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_missing_trace_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/missing.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-001 references missing Product target: docs/product/missing.md", report.errors)
            self.assertIn(
                {
                    "code": "task_board_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 references missing Product target: docs/product/missing.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_trace_reference_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Backlog | Miswired goal flow | docs/api/00-conventions.md | docs/product/01-goals.md | docs/architecture/01-context.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            expected = [
                "task board row TASK-001 Product field must reference product scope docs",
                "task board row TASK-001 Design field must reference design docs",
                "task board row TASK-001 API field must reference API docs",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "task_board_trace_reference_mismatch",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 Product field must reference product scope docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_task_board_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                "| TASK-001 | Ready | Implement goal audit | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("duplicate task board ID: TASK-001", report.errors)
            self.assertIn(
                {
                    "code": "task_board_duplicate_id",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "duplicate task board ID: TASK-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_task_board_id_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-1 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-1 must use TASK-NNN task ID format", report.errors)
            self.assertIn(
                {
                    "code": "task_board_invalid_id",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-1 must use TASK-NNN task ID format",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_task_board_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Raedy | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-001 has invalid Status: Raedy", report.errors)
            self.assertIn(
                {
                    "code": "task_board_invalid_status",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 has invalid Status: Raedy",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_standard_task_board_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(root, "docs/development/03-verification-log.md", "# Verification Log\n")
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Backlog | Scope goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-003 | In Progress | Wire goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-004 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Blocked by [U-001](../unresolved.md) |\n"
                    "| TASK-005 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | docs/development/03-verification-log.md |\n"
                    "| TASK-006 | Deferred | Later goal audit | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_blocked_task_without_unresolved_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Waiting for decision |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-002 is Blocked but does not cite an existing unresolved item ID",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_blocked_unresolved_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 is Blocked but does not cite an existing unresolved item ID",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_does_not_report_blocked_task_missing_id_when_unresolved_registry_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            (root / "docs/unresolved.md").write_bytes(b"\xff")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Waiting for decision |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("invalid Markdown encoding: docs/unresolved.md must be UTF-8", report.errors)
            self.assertNotIn(
                "task board row TASK-002 is Blocked but does not cite an existing unresolved item ID",
                report.errors,
            )

    def test_verify_reports_blocked_task_without_unresolved_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Blocked by U-001 |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-002 is Blocked but does not link to docs/unresolved.md", report.errors)
            self.assertIn(
                {
                    "code": "task_board_blocked_unresolved_link_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 is Blocked but does not link to docs/unresolved.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_blocked_task_with_unresolved_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            (root / "docs/unresolved.md").write_text(
                "# Unresolved Items\n\n"
                "| ID | Domain | Description | Blocking Scope | Owner | Date |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| U-001 | Backend | Confirm edge-case owner | non-blocking | TBD | 2026-06-26 |\n",
                encoding="utf-8",
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Blocked | Resolve goal edge case | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | Blocked by [U-001](../unresolved.md) |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_done_task_without_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-002 is Done but Verification has no local Markdown evidence", report.errors)
            self.assertIn(
                {
                    "code": "task_board_done_evidence_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 is Done but Verification has no local Markdown evidence",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_done_task_with_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(root, "docs/development/03-verification-log.md", "# Verification Log\n")

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | [verification log](03-verification-log.md) |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_verify_reports_done_task_with_missing_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | docs/development/missing-log.md |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn(
                "task board row TASK-002 references missing Verification evidence: docs/development/missing-log.md",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "task_board_done_evidence_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 references missing Verification evidence: docs/development/missing-log.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_done_task_verification_evidence_directory_without_false_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            evidence = root / "docs/development/03-verification-log.md"
            evidence.mkdir()

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Done | Verify goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | docs/development/03-verification-log.md |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("Markdown path is not a file: docs/development/03-verification-log.md", report.errors)
            self.assertNotIn(
                "task board row TASK-002 references missing Verification evidence: docs/development/03-verification-log.md",
                report.errors,
            )

    def test_verify_reports_roadmap_task_missing_from_task_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status | Milestone |\n"
                        "| --- | --- | --- |\n"
                        "| TASK-999 | Ready | Missing task board row |\n"
                    )
                ),
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("roadmap milestone TASK-999 has no matching task board row", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_task_missing",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "roadmap milestone TASK-999 has no matching task board row",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_task_status_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(status="Done"),
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("roadmap status for TASK-001 is Done but task board status is Ready", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_task_status_conflict",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "roadmap status for TASK-001 is Done but task board status is Ready",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_task_board_missing_roadmap_milestone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(root, "docs/development/01-roadmap.md", _roadmap_doc(status="Ready"))

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                    "| TASK-002 | Backlog | Extra unplanned task | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertIn("task board row TASK-002 has no matching roadmap milestone", report.errors)
            self.assertIn(
                {
                    "code": "task_board_roadmap_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-002 has no matching roadmap milestone",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_missing_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                "# Roadmap\n\n"
                "## Product Links\n\n"
                "- [PRD](../product/core/PRD.md)\n",
            )

            report = verify(root)

            self.assertIn(
                "docs/development/01-roadmap.md is missing roadmap sections: "
                "Milestones, Sequencing, Risks, Deferred Scope",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "roadmap_missing_sections",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "docs/development/01-roadmap.md is missing roadmap sections: "
                    "Milestones, Sequencing, Risks, Deferred Scope",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_empty_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc().replace(
                    "## Risks\n\n"
                    "- API, backend, frontend, and test work must stay aligned to acceptance criteria.\n\n",
                    "## Risks\n\n- TBD\n\n",
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/development/01-roadmap.md has empty roadmap sections: Risks",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "roadmap_empty_sections",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "docs/development/01-roadmap.md has empty roadmap sections: Risks",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_milestone_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status |\n"
                        "| --- | --- |\n"
                        "| TASK-001 | Ready |\n"
                    )
                ),
            )

            report = verify(root)

            self.assertIn(
                "docs/development/01-roadmap.md Milestones table is missing required columns: Milestone",
                report.errors,
            )
            self.assertIn(
                {
                    "code": "roadmap_milestone_missing_columns",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "docs/development/01-roadmap.md Milestones table is missing required columns: Milestone",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_milestone_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status | Milestone |\n"
                        "| --- | --- | --- |\n"
                    )
                ),
            )

            report = verify(root)

            self.assertIn("docs/development/01-roadmap.md must contain at least one milestone row", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_milestone_no_rows",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "docs/development/01-roadmap.md must contain at least one milestone row",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_milestone_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status | Milestone |\n"
                        "| --- | --- | --- |\n"
                        "| TASK-001 | Ready | TBD |\n"
                    )
                ),
            )

            report = verify(root)

            self.assertIn("roadmap milestone row TASK-001 is missing required fields: Milestone", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_milestone_row_missing_fields",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "roadmap milestone row TASK-001 is missing required fields: Milestone",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_milestone_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/development/01-roadmap.md", _roadmap_doc(status="Planning"))

            report = verify(root)

            self.assertIn("roadmap milestone row TASK-001 has invalid Status: Planning", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_milestone_invalid_status",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "roadmap milestone row TASK-001 has invalid Status: Planning",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_duplicate_roadmap_milestone_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_acceptance_chapter(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status | Milestone |\n"
                        "| --- | --- | --- |\n"
                        "| TASK-001 | Ready | Goal flow |\n"
                        "| TASK-001 | Backlog | Follow-up flow |\n"
                    )
                ),
            )

            report = verify(root)

            self.assertIn("duplicate roadmap milestone ID: TASK-001", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_milestone_duplicate_id",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "duplicate roadmap milestone ID: TASK-001",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_invalid_roadmap_milestone_id_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_product_chapter(root, "01-goals.md", "Goals")
            _write_acceptance_chapter(root)

            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    milestone_table=(
                        "| ID | Status | Milestone |\n"
                        "| --- | --- | --- |\n"
                        "| M-001 | Ready | Goal flow |\n"
                    )
                ),
            )

            report = verify(root)

            self.assertIn("roadmap milestone row M-001 must use TASK-NNN task ID format", report.errors)
            self.assertIn(
                {
                    "code": "roadmap_milestone_invalid_id",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "roadmap milestone row M-001 must use TASK-NNN task ID format",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_missing_trace_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(product_links="Product scope and acceptance criteria"),
            )

            report = verify(root)

            expected = [
                "docs/development/01-roadmap.md must reference existing Product docs",
                "docs/development/01-roadmap.md must reference a product acceptance chapter",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "roadmap_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "docs/development/01-roadmap.md must reference existing Product docs",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_reports_roadmap_missing_trace_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(
                    product_links="[Missing scope](../product/01-goals.md), "
                    "[Acceptance](../product/08-acceptance-criteria.md)"
                ),
            )

            report = verify(root)

            expected = [
                "docs/development/01-roadmap.md references missing Product target: docs/product/01-goals.md",
                "docs/development/01-roadmap.md references missing Acceptance target: docs/product/08-acceptance-criteria.md",
            ]
            for message in expected:
                self.assertIn(message, report.errors)
            self.assertIn(
                {
                    "code": "roadmap_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/development/01-roadmap.md",
                    "message": "docs/development/01-roadmap.md references missing Product target: docs/product/01-goals.md",
                },
                [finding.to_dict() for finding in report.findings],
            )

    def test_verify_allows_matching_roadmap_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product = root / "product.md"
            product.write_text("# Demo\n", encoding="utf-8")
            bootstrap(root, product)
            _write_indexed_doc(root, "docs/product/01-goals.md", "# Goals\n\nSource: [PRD](core/PRD.md).\n")
            _append_product_meta_chapter(root, "01-goals.md")
            _write_acceptance_chapter(root)
            _write_indexed_doc(root, "docs/architecture/01-context.md", "# Context\n")
            _write_indexed_doc(root, "docs/api/00-conventions.md", _api_conventions_doc())
            _write_traceable_test_strategy(root)
            _write_indexed_doc(
                root,
                "docs/development/01-roadmap.md",
                _roadmap_doc(status="Ready"),
            )

            task_board = root / "docs/development/02-task-board.md"
            task_board.write_text(
                _task_board_doc(
                    "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/product/08-acceptance-criteria.md | make test |\n"
                ),
                encoding="utf-8",
            )
            _append_index(root / "docs/development/README.md", "02-task-board.md")

            report = verify(root)

            self.assertEqual([], report.errors)

    def test_install_plan_respects_strict_scope(self) -> None:
        statuses = [
            ToolStatus(
                name="git",
                present=False,
                version="",
                note="Required",
                level="required",
                install_package="git",
            ),
            ToolStatus(
                name="pandoc",
                present=False,
                version="",
                note="Recommended",
                level="recommended",
                install_package="pandoc",
            ),
            ToolStatus(
                name="node",
                present=False,
                version="",
                note="Recommended",
                level="recommended",
                install_package=None,
            ),
        ]
        apt = PackageManager(name="apt", command="apt-get", supported=True)

        non_strict = build_install_plan(statuses, strict=False, package_manager=apt)
        strict = build_install_plan(statuses, strict=True, package_manager=apt)

        self.assertEqual(["git"], [item.tool for item in non_strict])
        self.assertEqual(["git", "pandoc"], [item.tool for item in strict])
        commands = install_commands(strict, apt)
        self.assertEqual(
            [["apt-get", "update"], ["apt-get", "install", "-y", "git", "pandoc"]],
            commands,
        )
        self.assertEqual("apt-get update && apt-get install -y git pandoc", install_command_text(commands))

    def test_environment_ok_requires_required_tools_and_strict_recommended_tools(self) -> None:
        statuses = [
            ToolStatus(
                name="git",
                present=False,
                version="",
                note="Required",
                level="required",
                install_package="git",
            ),
            ToolStatus(
                name="pandoc",
                present=False,
                version="",
                note="Recommended",
                level="recommended",
                install_package="pandoc",
            ),
        ]

        self.assertFalse(environment_ok(statuses, strict=False))
        self.assertFalse(environment_ok(statuses, strict=True))
        self.assertEqual(["git"], missing_tools_by_level(statuses, "required"))
        self.assertEqual(["pandoc"], missing_tools_by_level(statuses, "recommended"))

        required_present = [
            ToolStatus(
                name="git",
                present=True,
                version="git version 2",
                note="Required",
                level="required",
                install_package="git",
            ),
            statuses[1],
        ]

        self.assertTrue(environment_ok(required_present, strict=False))
        self.assertFalse(environment_ok(required_present, strict=True))

    def test_repair_target_error_rejects_file_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_text("not a directory\n", encoding="utf-8")

            self.assertEqual(
                f"environment repair target is not a directory: {target}",
                repair_target_error(target),
            )
            self.assertEqual(
                f"environment repair target parent is not a directory: {target}",
                repair_target_error(target / "child"),
            )

    def test_repair_target_error_rejects_blocked_repair_plan_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            governance = target / ".governance"
            governance.write_text("not a directory\n", encoding="utf-8")

            self.assertEqual(
                f"environment repair output parent is not a directory: {governance}",
                repair_target_error(target),
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            repair_plan = target / ".governance/env-repair.md"
            repair_plan.mkdir(parents=True)

            self.assertEqual(
                f"environment repair plan path is not a file: {repair_plan}",
                repair_target_error(target),
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            repair_plan = target / ".governance/env-repair.md"
            repair_plan.parent.mkdir(parents=True)
            repair_plan.write_text("# Existing Plan\n", encoding="utf-8")
            temp_path = repair_plan.with_name(".env-repair.md.tmp")
            temp_path.mkdir()

            self.assertEqual(
                f"environment repair plan temp path is not a file: {temp_path}",
                repair_target_error(target),
            )
            with self.assertRaises(ValueError) as context:
                write_repair_plan(target, [])
            self.assertEqual(
                f"environment repair plan temp path is not a file: {temp_path}",
                str(context.exception),
            )
            self.assertEqual("# Existing Plan\n", repair_plan.read_text(encoding="utf-8"))

    def test_write_repair_plan_cleans_temp_after_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            repair_plan = target / ".governance/env-repair.md"
            repair_plan.parent.mkdir(parents=True)
            repair_plan.write_text("# Existing Plan\n", encoding="utf-8")
            temp_path = repair_plan.with_name(".env-repair.md.tmp")
            original_replace = check_env_module.Path.replace

            def fail_replace(self: Path, destination: Path) -> Path:
                if self == temp_path and destination == repair_plan:
                    raise OSError("simulated replace failure")
                return original_replace(self, destination)

            check_env_module.Path.replace = fail_replace
            try:
                with self.assertRaises(OSError):
                    write_repair_plan(target, [])
            finally:
                check_env_module.Path.replace = original_replace

            self.assertEqual("# Existing Plan\n", repair_plan.read_text(encoding="utf-8"))
            self.assertFalse(temp_path.exists())

    def test_merge_state_reports_unwritable_state_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.write_text("not a directory\n", encoding="utf-8")

            with self.assertRaises(StateFileError) as context:
                merge_state(target, phase="initialized")

            self.assertEqual(target / ".governance/state.json", context.exception.path)
            self.assertIn("unwritable", context.exception.reason)

    def test_merge_state_preserves_existing_state_when_atomic_temp_path_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            state_path = target / ".governance/state.json"
            state_path.parent.mkdir()
            original = {"phase": "initialized", "profile": "service"}
            state_path.write_text(json.dumps(original, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            (state_path.parent / ".state.json.tmp").mkdir()

            with self.assertRaises(StateFileError) as context:
                merge_state(target, phase="product-structuring")

            self.assertEqual(state_path, context.exception.path)
            self.assertIn("unwritable", context.exception.reason)
            self.assertEqual(original, json.loads(state_path.read_text(encoding="utf-8")))

    def test_load_state_reports_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            state_path = target / ".governance/state.json"
            state_path.mkdir(parents=True)

            with self.assertRaises(StateFileError) as context:
                load_state(target)

            self.assertEqual(state_path, context.exception.path)
            self.assertEqual("not a file", context.exception.reason)

    def test_scaffold_design_preflight_blocks_index_directory_without_partial_files(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend_root = root / "docs/backend"
            backend_root.mkdir(parents=True)
            (backend_root / "README.md").mkdir()
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_design(root)
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((root / "docs/architecture/01-system-context.md").exists())
            self.assertFalse((root / "docs/api/00-conventions.md").exists())
            self.assertIn("scaffold index is not a file: docs/backend/README.md", result.errors)

    def test_scaffold_product_preflight_blocks_index_directory_without_partial_chapter(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_root = root / "docs/product"
            product_root.mkdir(parents=True)
            (product_root / "README.md").mkdir()
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((product_root / "03-goals-and-requirements.md").exists())
            self.assertTrue(any("docs/product/README.md" in error for error in result.errors))

    def test_scaffold_product_preflight_blocks_index_temp_path_without_partial_chapter(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_root = root / "docs/product"
            product_root.mkdir(parents=True)
            readme = product_root / "README.md"
            readme.write_text("# Product\n\n## Index\n", encoding="utf-8")
            meta = product_root / "core/product-meta.md"
            meta.parent.mkdir(parents=True)
            meta.write_text("# Product Meta\n\n## Chapter Map\n", encoding="utf-8")
            original_readme = readme.read_text(encoding="utf-8")
            original_meta = meta.read_text(encoding="utf-8")
            (product_root / ".README.md.tmp").mkdir()
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((product_root / "03-goals-and-requirements.md").exists())
            self.assertEqual(original_readme, readme.read_text(encoding="utf-8"))
            self.assertEqual(original_meta, meta.read_text(encoding="utf-8"))
            self.assertIn(
                "scaffold index temp path is not a file: docs/product/.README.md.tmp",
                result.errors,
            )

    def test_scaffold_product_cleans_temp_after_replace_failure(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = root / "docs/product/03-goals-and-requirements.md"
            temp_path = chapter.with_name(".03-goals-and-requirements.md.tmp")
            original_evaluate_gate = scaffold_module.evaluate_gate
            original_replace = scaffold_module.Path.replace

            def fail_replace(self: Path, target: Path) -> Path:
                if self == temp_path and target == chapter:
                    raise OSError("simulated replace failure")
                return original_replace(self, target)

            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            scaffold_module.Path.replace = fail_replace
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate
                scaffold_module.Path.replace = original_replace

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse(chapter.exists())
            self.assertFalse(temp_path.exists())
            self.assertTrue(
                any(
                    "failed to write scaffold file docs/product/03-goals-and-requirements.md" in error
                    for error in result.errors
                )
            )

    def test_scaffold_product_stops_after_write_failure_without_later_chapters(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_chapter = root / "docs/product/03-goals-and-requirements.md"
            later_chapter = root / "docs/product/08-acceptance-criteria.md"
            temp_path = first_chapter.with_name(".03-goals-and-requirements.md.tmp")
            original_evaluate_gate = scaffold_module.evaluate_gate
            original_replace = scaffold_module.Path.replace

            def fail_replace(self: Path, target: Path) -> Path:
                if self == temp_path and target == first_chapter:
                    raise OSError("simulated replace failure")
                return original_replace(self, target)

            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            scaffold_module.Path.replace = fail_replace
            try:
                result = scaffold_module.scaffold_product(
                    root,
                    ["goals-and-requirements", "acceptance-criteria"],
                )
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate
                scaffold_module.Path.replace = original_replace

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse(first_chapter.exists())
            self.assertFalse(later_chapter.exists())
            self.assertFalse((root / "docs/product/README.md").exists())
            self.assertFalse((root / "docs/product/core/product-meta.md").exists())

    def test_scaffold_design_stops_after_write_failure_without_later_files(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_file = root / "docs/architecture/01-system-context.md"
            later_file = root / "docs/api/00-conventions.md"
            temp_path = first_file.with_name(".01-system-context.md.tmp")
            original_evaluate_gate = scaffold_module.evaluate_gate
            original_replace = scaffold_module.Path.replace

            def fail_replace(self: Path, target: Path) -> Path:
                if self == temp_path and target == first_file:
                    raise OSError("simulated replace failure")
                return original_replace(self, target)

            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            scaffold_module.Path.replace = fail_replace
            try:
                result = scaffold_module.scaffold_design(root)
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate
                scaffold_module.Path.replace = original_replace

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse(first_file.exists())
            self.assertFalse(later_file.exists())
            self.assertFalse((root / "docs/architecture/README.md").exists())

    def test_scaffold_product_reports_index_directory(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_root = root / "docs/product"
            product_root.mkdir(parents=True)
            (product_root / "README.md").mkdir()
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((product_root / "03-goals-and-requirements.md").exists())
            self.assertIn("scaffold index is not a file: docs/product/README.md", result.errors)

    def test_scaffold_product_reports_index_invalid_encoding(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_root = root / "docs/product"
            product_root.mkdir(parents=True)
            (product_root / "README.md").write_bytes(b"\xff")
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((product_root / "03-goals-and-requirements.md").exists())
            self.assertIn("scaffold index must be UTF-8 Markdown: docs/product/README.md", result.errors)

    def test_scaffold_product_reports_product_meta_directory(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_root = root / "docs/product"
            product_root.mkdir(parents=True)
            (product_root / "README.md").write_text("# Product\n", encoding="utf-8")
            meta = product_root / "core/product-meta.md"
            meta.mkdir(parents=True)
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((product_root / "03-goals-and-requirements.md").exists())
            self.assertIn("scaffold product meta is not a file: docs/product/core/product-meta.md", result.errors)

    def test_scaffold_product_reports_product_meta_invalid_encoding(self) -> None:
        class PassingGate:
            ok = True
            requirements: list[object] = []
            verification: dict[str, object] = {"findings": []}

            def to_dict(self) -> dict[str, object]:
                return {"ok": True, "requirements": [], "verification": self.verification}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            product_root = root / "docs/product"
            product_root.mkdir(parents=True)
            (product_root / "README.md").write_text("# Product\n", encoding="utf-8")
            meta = product_root / "core/product-meta.md"
            meta.parent.mkdir(parents=True)
            meta.write_bytes(b"\xff")
            original_evaluate_gate = scaffold_module.evaluate_gate
            scaffold_module.evaluate_gate = lambda _root, _gate: PassingGate()
            try:
                result = scaffold_module.scaffold_product(root, ["goals-and-requirements"])
            finally:
                scaffold_module.evaluate_gate = original_evaluate_gate

            self.assertFalse(result.ok)
            self.assertEqual([], result.created)
            self.assertFalse((product_root / "03-goals-and-requirements.md").exists())
            self.assertIn(
                "scaffold product meta must be UTF-8 Markdown: docs/product/core/product-meta.md",
                result.errors,
            )


if __name__ == "__main__":
    unittest.main()
