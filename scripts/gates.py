from __future__ import annotations

import argparse
import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .bootstrap_tree import target_local_commands_payload
    from .state import STATE_REL, StateFileError, load_state
    from .verify_governance import product_acceptance_ids, task_board_executable_tasks, verify
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from state import STATE_REL, StateFileError, load_state
    from verify_governance import product_acceptance_ids, task_board_executable_tasks, verify
    from workflow_actions import next_actions_payload


GATE_NAMES = ("product-structuring", "design-derivation", "implementation")
REQUIREMENT_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PRODUCT_CHAPTER_TRACE_FINDING_CODES = {
    "product_chapter_invalid_filename",
    "product_chapter_duplicate_prefix",
    "product_chapter_missing_prd_link",
    "product_meta_missing_chapter_link",
}
PRODUCT_ACCEPTANCE_ID_UNIQUENESS_FINDING_CODES = {
    "product_acceptance_duplicate_id",
}
PRODUCT_GLOSSARY_FINDING_CODES = {
    "glossary_table_missing_columns",
    "glossary_row_missing_fields",
    "glossary_duplicate_term",
    "glossary_source_reference_missing",
}
PRODUCT_UNRESOLVED_FINDING_CODES = {
    "unresolved_table_missing_columns",
    "unresolved_row_missing_fields",
    "unresolved_invalid_id",
    "unresolved_duplicate_id",
    "unresolved_blocking_item",
}
DOMAIN_DOCUMENT_FINDING_CODES = {
    "docs_local_markdown_link_missing",
    "docs_readme_not_file",
    "docs_readme_unindexed_file",
    "governance_scaffold_placeholder",
    "governance_structured_placeholder",
    "markdown_invalid_encoding",
    "markdown_not_file",
    "required_directory_not_directory",
    "required_file_not_file",
}
ARCHITECTURE_DESIGN_FINDING_CODES = {
    "architecture_system_context_missing_sections",
    "architecture_system_context_empty_sections",
    "architecture_system_context_trace_reference_missing",
    "architecture_containers_missing_sections",
    "architecture_containers_empty_sections",
    "architecture_containers_trace_reference_missing",
    "architecture_quality_attributes_missing_sections",
    "architecture_quality_attributes_empty_sections",
    "architecture_quality_attributes_trace_reference_missing",
}
API_CONTRACT_FINDING_CODES = {
    "api_conventions_missing_sections",
    "api_conventions_empty_sections",
    "api_conventions_trace_reference_missing",
    "api_error_codes_missing_sections",
    "api_error_codes_empty_sections",
    "api_error_codes_trace_reference_missing",
    "api_changelog_missing_sections",
    "api_changelog_empty_sections",
    "api_endpoint_invalid_filename",
    "api_endpoint_duplicate_prefix",
    "api_endpoint_missing_sections",
    "api_endpoint_empty_sections",
    "api_endpoint_method_path_invalid",
    "api_endpoint_error_codes_reference_missing",
    "api_endpoint_upstream_reference_missing",
    "api_endpoint_frontend_consumer_reference_missing",
}
BACKEND_DESIGN_FINDING_CODES = {
    "backend_module_missing_sections",
    "backend_module_empty_sections",
    "backend_module_trace_reference_missing",
    "backend_data_model_missing_sections",
    "backend_data_model_empty_sections",
    "backend_data_model_trace_reference_missing",
    "backend_external_services_missing_sections",
    "backend_external_services_empty_sections",
    "backend_external_services_trace_reference_missing",
}
FRONTEND_DESIGN_FINDING_CODES = {
    "ui_interaction_model_missing_sections",
    "ui_interaction_model_empty_sections",
    "ui_interaction_model_trace_reference_missing",
    "frontend_module_missing_sections",
    "frontend_module_empty_sections",
    "frontend_module_trace_reference_missing",
    "frontend_api_consumption_missing_sections",
    "frontend_api_consumption_empty_sections",
    "frontend_api_consumption_trace_reference_missing",
}
VERIFICATION_STRATEGY_FINDING_CODES = {
    "test_strategy_missing_sections",
    "test_strategy_empty_sections",
    "test_strategy_trace_reference_missing",
    "acceptance_matrix_missing_sections",
    "acceptance_matrix_empty_sections",
    "acceptance_matrix_missing_columns",
    "acceptance_matrix_no_rows",
    "acceptance_matrix_row_missing_fields",
    "acceptance_matrix_invalid_acceptance_id",
    "acceptance_matrix_duplicate_acceptance_id",
    "acceptance_matrix_acceptance_anchor_mismatch",
    "acceptance_matrix_acceptance_id_unknown",
    "acceptance_matrix_trace_reference_missing",
    "acceptance_matrix_api_endpoint_reference_missing",
    "acceptance_matrix_uncovered_id_unknown",
    "acceptance_matrix_product_coverage_missing",
}
DELIVERY_PLAN_FINDING_CODES = {
    "roadmap_missing_sections",
    "roadmap_empty_sections",
    "roadmap_milestone_missing_columns",
    "roadmap_milestone_no_rows",
    "roadmap_milestone_row_missing_fields",
    "roadmap_milestone_invalid_id",
    "roadmap_milestone_invalid_status",
    "roadmap_milestone_duplicate_id",
    "roadmap_trace_reference_missing",
    "roadmap_task_missing",
    "roadmap_task_status_conflict",
    "task_board_missing_sections",
    "task_board_empty_sections",
    "task_board_missing_columns",
    "task_board_no_tasks",
    "task_board_row_missing_fields",
    "task_board_invalid_id",
    "task_board_invalid_status",
    "task_board_duplicate_id",
    "task_board_trace_reference_missing",
    "task_board_trace_reference_mismatch",
    "task_board_acceptance_reference_missing",
    "task_board_acceptance_id_missing",
    "task_board_acceptance_id_unknown",
    "task_board_acceptance_anchor_mismatch",
    "task_board_blocked_unresolved_missing",
    "task_board_blocked_unresolved_link_missing",
    "task_board_done_evidence_missing",
    "task_board_ready_task_missing",
    "task_board_roadmap_missing",
    "task_board_acceptance_matrix_missing",
    "verification_log_missing_sections",
    "verification_log_empty_sections",
    "verification_log_missing_columns",
    "verification_log_invalid_task_id",
    "verification_log_duplicate_task_id",
}
IMPLEMENTATION_REQUIRED_FILES = (
    ("architecture_system_context_present", "docs/architecture/01-system-context.md", "system context architecture doc exists"),
    ("architecture_containers_present", "docs/architecture/02-containers.md", "containers architecture doc exists"),
    (
        "architecture_quality_attributes_present",
        "docs/architecture/03-quality-attributes.md",
        "quality attributes architecture doc exists",
    ),
    ("ui_interaction_model_present", "docs/ui/01-interaction-model.md", "UI interaction model exists"),
    ("api_conventions_present", "docs/api/00-conventions.md", "API conventions doc exists"),
    ("api_error_codes_present", "docs/api/error-codes.md", "API error codes registry exists"),
    ("api_changelog_present", "docs/api/changelog.md", "API changelog exists"),
    ("api_endpoints_index_present", "docs/api/endpoints/README.md", "API endpoints index exists"),
    ("backend_modules_present", "docs/backend/01-modules.md", "backend modules doc exists"),
    ("backend_data_model_present", "docs/backend/02-data-model.md", "backend data model doc exists"),
    ("backend_external_services_present", "docs/backend/03-external-services.md", "backend external services doc exists"),
    ("frontend_modules_present", "docs/frontend/01-modules.md", "frontend modules doc exists"),
    ("frontend_api_consumption_present", "docs/frontend/02-api-consumption.md", "frontend API consumption doc exists"),
    ("test_strategy_present", "docs/tests/01-strategy.md", "test strategy exists"),
    ("acceptance_matrix_present", "docs/tests/02-acceptance-matrix.md", "acceptance matrix exists"),
    ("roadmap_present", "docs/development/01-roadmap.md", "roadmap exists"),
    ("task_board_present", "docs/development/02-task-board.md", "task board exists"),
    ("verification_log_present", "docs/development/03-verification-log.md", "verification log exists"),
)


@dataclass
class GateRequirement:
    code: str
    ok: bool
    message: str
    path: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not REQUIREMENT_CODE_RE.match(self.code):
            raise ValueError("gate requirement code must use lowercase snake_case")
        if not isinstance(self.ok, bool):
            raise ValueError("gate requirement ok must be a boolean")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("gate requirement message must be a non-empty string")
        if not isinstance(self.path, str):
            raise ValueError("gate requirement path must be a string")
        if self.path:
            posix_path = PurePosixPath(self.path)
            windows_path = PureWindowsPath(self.path)
            normalized_path = posix_path.as_posix()
            if (
                posix_path.is_absolute()
                or windows_path.is_absolute()
                or ".." in posix_path.parts
                or ".." in windows_path.parts
            ):
                raise ValueError("gate requirement path must be repository-relative")
            if "\\" in self.path or self.path != normalized_path:
                raise ValueError("gate requirement path must use normalized POSIX form")

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "ok": self.ok,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class GateResult:
    gate: str
    target: str
    ok: bool
    requirements: list[GateRequirement] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.gate not in GATE_NAMES:
            raise ValueError("gate result gate must be a known gate")
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("gate result target must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise ValueError("gate result ok must be a boolean")
        if not isinstance(self.requirements, list):
            raise ValueError("gate result requirements must be a list")
        if not all(isinstance(item, GateRequirement) for item in self.requirements):
            raise ValueError("gate result requirements must contain GateRequirement entries")
        if not isinstance(self.verification, dict):
            raise ValueError("gate result verification must be an object")
        if not isinstance(self.state, dict):
            raise ValueError("gate result state must be an object")
        self.requirements = list(self.requirements)
        self.verification = copy.deepcopy(self.verification)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "target": self.target,
            "ok": self.ok,
            "requirements": [item.to_dict() for item in self.requirements],
            "verification": copy.deepcopy(self.verification),
            "state": copy.deepcopy(self.state),
        }


def gate_continuation_payload(result: GateResult) -> dict[str, object]:
    if not result.state:
        return {}
    payload: dict[str, object] = {
        "local_commands": target_local_commands_payload(cwd=result.target),
    }
    if result.ok:
        payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
    return payload


def evaluate_gate(root: Path, gate: str) -> GateResult:
    if gate not in GATE_NAMES:
        raise ValueError(f"unknown gate: {gate}")
    root = root.resolve()
    try:
        state = load_state(root)
    except StateFileError as error:
        return GateResult(
            gate=gate,
            target=str(root),
            ok=False,
            requirements=[
                GateRequirement(
                    code="state_readable",
                    ok=False,
                    path=STATE_REL.as_posix(),
                    message=str(error),
                )
            ],
        )
    report = verify(root)
    requirements: list[GateRequirement] = []

    _add(requirements, "state_readable", True, STATE_REL.as_posix(), "governance state is readable")
    _add(requirements, "state_present", bool(state), ".governance/state.json", "governance state exists")
    _add(requirements, "verification_passed", report.ok, "", "governance verification passes")

    _add_product_import_requirements(requirements, root)
    if gate in {"design-derivation", "implementation"}:
        _add(requirements, "product_chapters_present", _has_product_chapter(root), "docs/product", "product chapters exist")
        _add(
            requirements,
            "product_acceptance_chapter_present",
            _has_acceptance_chapter(root),
            "docs/product",
            "product acceptance criteria chapter exists",
        )
        _add(
            requirements,
            "product_acceptance_ids_present",
            bool(product_acceptance_ids(root)),
            "docs/product",
            "product acceptance criteria expose stable A-NNN IDs",
        )
        _add(
            requirements,
            "product_chapters_traceable",
            _product_chapter_trace_ok(report),
            "docs/product",
            "product chapters are indexed, named, and linked to source",
        )
        _add(
            requirements,
            "product_acceptance_ids_unique",
            _report_has_no_error_finding_codes(report, PRODUCT_ACCEPTANCE_ID_UNIQUENESS_FINDING_CODES),
            "docs/product",
            "product acceptance IDs are unique",
        )
        _add(
            requirements,
            "product_glossary_traceable",
            _report_has_no_error_finding_codes(report, PRODUCT_GLOSSARY_FINDING_CODES),
            "docs/glossary.md",
            "glossary terms are complete, unique, and source-linked",
        )
        _add(
            requirements,
            "product_unresolved_clear",
            _report_has_no_error_finding_codes(report, PRODUCT_UNRESOLVED_FINDING_CODES),
            "docs/unresolved.md",
            "unresolved items are complete and non-blocking",
        )
    if gate == "implementation":
        _add_implementation_requirements(requirements, root)
        _add_design_derivation_readiness_requirements(requirements, report)

    return GateResult(
        gate=gate,
        target=str(root),
        ok=all(item.ok for item in requirements),
        requirements=requirements,
        verification=report.to_dict(),
        state=state,
    )


def _add(requirements: list[GateRequirement], code: str, ok: bool, path: str, message: str) -> None:
    requirements.append(GateRequirement(code=code, ok=ok, path=path, message=message))


def _add_product_import_requirements(requirements: list[GateRequirement], root: Path) -> None:
    manifest = _load_product_source_manifest(root)
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    archive = manifest.get("archive") if isinstance(manifest.get("archive"), dict) else {}
    imported = manifest.get("import") if isinstance(manifest.get("import"), dict) else {}
    _add(
        requirements,
        "product_source_present",
        source.get("provided") is True and bool(archive.get("path")),
        "docs/product/core/source/source-manifest.json",
        "product source is archived",
    )
    _add(
        requirements,
        "product_import_ready",
        imported.get("status") == "ready_for_structuring" and imported.get("can_derive_design") is True,
        "docs/product/core/source/source-manifest.json",
        "product import is ready for downstream derivation",
    )


def _report_has_no_error_finding_codes(report: Any, codes: set[str]) -> bool:
    for finding in getattr(report, "findings", []):
        if getattr(finding, "severity", "") != "error":
            continue
        if getattr(finding, "code", "") in codes:
            return False
    return True


def _add_design_derivation_readiness_requirements(requirements: list[GateRequirement], report: Any) -> None:
    _add(
        requirements,
        "architecture_design_ready",
        _report_has_no_domain_errors(report, ARCHITECTURE_DESIGN_FINDING_CODES, ("docs/architecture",)),
        "docs/architecture",
        "architecture design docs are complete and traceable",
    )
    _add(
        requirements,
        "api_contracts_ready",
        _report_has_no_domain_errors(report, API_CONTRACT_FINDING_CODES, ("docs/api",)),
        "docs/api",
        "API conventions, registry, changelog, and endpoint contracts are complete and traceable",
    )
    _add(
        requirements,
        "backend_design_ready",
        _report_has_no_domain_errors(report, BACKEND_DESIGN_FINDING_CODES, ("docs/backend",)),
        "docs/backend",
        "backend modules, data model, and external service docs are complete and traceable",
    )
    _add(
        requirements,
        "frontend_design_ready",
        _report_has_no_domain_errors(report, FRONTEND_DESIGN_FINDING_CODES, ("docs/ui", "docs/frontend")),
        "docs/frontend",
        "UI and frontend design docs are complete and traceable",
    )
    _add(
        requirements,
        "verification_strategy_ready",
        _report_has_no_domain_errors(report, VERIFICATION_STRATEGY_FINDING_CODES, ("docs/tests",)),
        "docs/tests",
        "test strategy and acceptance matrix are complete and traceable",
    )
    _add(
        requirements,
        "delivery_plan_ready",
        _report_has_no_domain_errors(report, DELIVERY_PLAN_FINDING_CODES, ("docs/development",)),
        "docs/development",
        "roadmap, task board, and verification log are complete and traceable",
    )


def _report_has_no_domain_errors(report: Any, codes: set[str], path_prefixes: tuple[str, ...]) -> bool:
    for finding in getattr(report, "findings", []):
        if getattr(finding, "severity", "") != "error":
            continue
        code = getattr(finding, "code", "")
        path = getattr(finding, "path", "")
        if code in codes:
            return False
        if code in DOMAIN_DOCUMENT_FINDING_CODES and _path_is_under_any(path, path_prefixes):
            return False
    return True


def _product_chapter_trace_ok(report: Any) -> bool:
    for finding in getattr(report, "findings", []):
        if getattr(finding, "severity", "") != "error":
            continue
        code = getattr(finding, "code", "")
        path = getattr(finding, "path", "")
        if code in PRODUCT_CHAPTER_TRACE_FINDING_CODES:
            return False
        if code == "docs_readme_unindexed_file" and _is_product_chapter_path(path):
            return False
        if code == "docs_local_markdown_link_missing" and path.startswith("docs/product/"):
            return False
    return True


def _path_is_under_any(path: object, prefixes: tuple[str, ...]) -> bool:
    return any(_path_is_under(path, prefix) for prefix in prefixes)


def _path_is_under(path: object, prefix: str) -> bool:
    if not isinstance(path, str):
        return False
    posix_path = PurePosixPath(path)
    prefix_path = PurePosixPath(prefix)
    return len(posix_path.parts) >= len(prefix_path.parts) and posix_path.parts[: len(prefix_path.parts)] == prefix_path.parts


def _is_product_chapter_path(path: object) -> bool:
    if not isinstance(path, str):
        return False
    posix_path = PurePosixPath(path)
    return len(posix_path.parts) == 3 and posix_path.parts[:2] == ("docs", "product")


def _load_product_source_manifest(root: Path) -> dict[str, Any]:
    path = root / "docs/product/core/source/source-manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _add_implementation_requirements(requirements: list[GateRequirement], root: Path) -> None:
    for domain, message in [
        ("architecture", "architecture docs exist"),
        ("ui", "UI interaction docs exist"),
        ("api", "API contract docs exist"),
        ("backend", "backend design docs exist"),
        ("frontend", "frontend design docs exist"),
        ("tests", "test strategy docs exist"),
        ("development", "development plan docs exist"),
    ]:
        _add(requirements, f"{domain}_docs_present", _has_authored_markdown(root / "docs" / domain), f"docs/{domain}", message)
    for code, rel, message in IMPLEMENTATION_REQUIRED_FILES:
        _add(requirements, code, _is_authored_markdown_file(root / rel), rel, message)
    _add(
        requirements,
        "api_endpoint_contract_present",
        _has_api_endpoint_contract(root),
        "docs/api/endpoints",
        "at least one API endpoint contract exists",
    )
    _add(
        requirements,
        "task_board_ready_task_present",
        bool(task_board_executable_tasks(root)),
        "docs/development/02-task-board.md",
        "task board has at least one Ready or In Progress task with product/design/API/acceptance/verification links",
    )


def _has_product_chapter(root: Path) -> bool:
    product_root = root / "docs/product"
    return any(path.is_file() for path in product_root.glob("[0-9][0-9]-*.md"))


def _has_acceptance_chapter(root: Path) -> bool:
    product_root = root / "docs/product"
    return any(path.is_file() and "acceptance" in path.stem.lower() for path in product_root.glob("[0-9][0-9]-*.md"))


def _has_authored_markdown(directory: Path) -> bool:
    if not directory.exists():
        return False
    for path in directory.rglob("*.md"):
        if path.name in {"README.md", "AGENTS.md"} or path.name.startswith("_"):
            continue
        return True
    return False


def _is_authored_markdown_file(path: Path) -> bool:
    return path.is_file() and not path.name.startswith("_")


def _has_api_endpoint_contract(root: Path) -> bool:
    endpoint_root = root / "docs/api/endpoints"
    if not endpoint_root.exists():
        return False
    return any(
        path.is_file() and path.name not in {"README.md", "AGENTS.md"} and not path.name.startswith("_")
        for path in endpoint_root.glob("*.md")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs-as-code workflow phase gates.")
    parser.add_argument("gate", choices=GATE_NAMES, help="Gate to evaluate.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to check.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable gate result.")
    args = parser.parse_args()
    result = evaluate_gate(Path(args.target), args.gate)
    if args.json:
        payload = result.to_dict()
        payload.update(gate_continuation_payload(result))
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.ok else 1
    if result.ok:
        print(f"Gate passed: {args.gate}")
        return 0
    print(f"Gate failed: {args.gate}")
    for requirement in result.requirements:
        if not requirement.ok:
            suffix = f" ({requirement.path})" if requirement.path else ""
            print(f"- {requirement.code}: {requirement.message}{suffix}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
