from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .state import STATE_REL, StateFileError, load_state
    from .verify_governance import task_board_ready_tasks, verify
except ImportError:  # pragma: no cover - direct script execution
    from state import STATE_REL, StateFileError, load_state
    from verify_governance import task_board_ready_tasks, verify


GATE_NAMES = ("product-structuring", "design-derivation", "implementation")
REQUIREMENT_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
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

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "target": self.target,
            "ok": self.ok,
            "requirements": [item.to_dict() for item in self.requirements],
            "verification": self.verification,
            "state": self.state,
        }


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
    if gate == "implementation":
        _add_implementation_requirements(requirements, root)

    return GateResult(
        gate=gate,
        target=str(root),
        ok=all(item.ok for item in requirements),
        requirements=requirements,
        verification={
            "ok": report.ok,
            "errors": report.errors,
            "warnings": report.warnings,
            "findings": [finding.to_dict() for finding in report.findings],
        },
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
        bool(task_board_ready_tasks(root)),
        "docs/development/02-task-board.md",
        "task board has at least one Ready task with product/design/API/acceptance/verification links",
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
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
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
