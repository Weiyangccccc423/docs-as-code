from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .bootstrap_tree import target_local_commands_payload
    from .gates import evaluate_gate
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from gates import evaluate_gate
    from workflow_actions import next_actions_payload


SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
STARTER_ENDPOINT_CONTRACT_PATH = "docs/api/endpoints/01-endpoint-contract.md"
SCAFFOLD_NAMES = ("product", "design")


@dataclass(frozen=True)
class ScaffoldSpec:
    path: str
    title: str
    purpose: str
    sections: tuple[str, ...]
    index_description: str
    placeholder: bool = True

    def __post_init__(self) -> None:
        _validate_scaffold_spec_path(self.path)
        if not isinstance(self.title, str) or not self.title:
            raise ValueError("scaffold spec title must be a non-empty string")
        if not isinstance(self.purpose, str) or not self.purpose:
            raise ValueError("scaffold spec purpose must be a non-empty string")
        if not isinstance(self.sections, tuple):
            raise ValueError("scaffold spec sections must be a tuple")
        if not self.sections:
            raise ValueError("scaffold spec sections must not be empty")
        if not all(isinstance(section, str) and section for section in self.sections):
            raise ValueError("scaffold spec sections must be non-empty strings")
        if not isinstance(self.index_description, str) or not self.index_description:
            raise ValueError("scaffold spec index_description must be a non-empty string")
        if not isinstance(self.placeholder, bool):
            raise ValueError("scaffold spec placeholder must be a boolean")


@dataclass
class ScaffoldResult:
    scaffold: str
    target: str
    ok: bool
    check: bool = False
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    indexed: list[str] = field(default_factory=list)
    would_create: list[str] = field(default_factory=list)
    would_skip: list[str] = field(default_factory=list)
    would_index: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    gate: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scaffold not in SCAFFOLD_NAMES:
            raise ValueError("scaffold result scaffold must be product or design")
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("scaffold result target must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise ValueError("scaffold result ok must be a boolean")
        if not isinstance(self.check, bool):
            raise ValueError("scaffold result check must be a boolean")
        for field_name in (
            "created",
            "skipped",
            "indexed",
            "would_create",
            "would_skip",
            "would_index",
        ):
            _validate_scaffold_path_list(field_name, getattr(self, field_name))
        if not isinstance(self.errors, list) or not all(isinstance(item, str) for item in self.errors):
            raise ValueError("scaffold result errors must be strings")
        if not isinstance(self.gate, dict):
            raise ValueError("scaffold result gate must be an object")
        if self.check and (self.created or self.skipped or self.indexed):
            raise ValueError("scaffold result check mode cannot contain write outputs")
        if not self.check and (self.would_create or self.would_skip or self.would_index):
            raise ValueError("scaffold result write mode cannot contain would outputs")
        if self.ok and self.errors:
            raise ValueError("scaffold result ok cannot include errors")
        if not self.ok and not self.errors:
            raise ValueError("scaffold result failure requires errors")
        self.created = list(self.created)
        self.skipped = list(self.skipped)
        self.indexed = list(self.indexed)
        self.would_create = list(self.would_create)
        self.would_skip = list(self.would_skip)
        self.would_index = list(self.would_index)
        self.errors = list(self.errors)
        self.gate = copy.deepcopy(self.gate)

    def to_dict(self) -> dict[str, object]:
        return {
            "scaffold": self.scaffold,
            "target": self.target,
            "ok": self.ok,
            "check": self.check,
            "created": list(self.created),
            "skipped": list(self.skipped),
            "indexed": list(self.indexed),
            "would_create": list(self.would_create),
            "would_skip": list(self.would_skip),
            "would_index": list(self.would_index),
            "errors": list(self.errors),
            "gate": copy.deepcopy(self.gate),
        }


def scaffold_continuation_payload(result: ScaffoldResult) -> dict[str, object]:
    if not result.ok or result.check:
        return {}
    state = result.gate.get("state")
    if not isinstance(state, dict) or not state:
        return {}
    payload: dict[str, object] = {
        "local_commands": target_local_commands_payload(cwd=result.target),
        "next_actions": next_actions_payload(state, cwd=result.target),
    }
    blockers = _scaffold_next_action_blockers(result)
    if blockers:
        payload["next_actions_blocked_by"] = blockers
    return payload


def _scaffold_next_action_blockers(result: ScaffoldResult) -> list[dict[str, str]]:
    root = Path(result.target)
    blockers: list[dict[str, str]] = []
    for rel in sorted(set(result.created) | set(result.skipped)):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if SCAFFOLD_PLACEHOLDER not in text:
            continue
        blockers.append(
            {
                "code": "governance_scaffold_placeholder",
                "path": rel,
                "message": (
                    f"{rel} still contains a governance scaffold placeholder; "
                    "replace it with source-backed content before running next_actions."
                ),
            }
        )
    return blockers


def _validate_scaffold_path_list(field_name: str, paths: object) -> None:
    if not isinstance(paths, list):
        raise ValueError(f"scaffold result {field_name} must be a list")
    if not all(isinstance(path, str) for path in paths):
        raise ValueError(f"scaffold result {field_name} paths must be strings")
    if len(paths) != len(set(paths)):
        raise ValueError(f"scaffold result {field_name} paths must be unique")
    for path in paths:
        posix_path = PurePosixPath(path)
        windows_path = PureWindowsPath(path)
        normalized_path = posix_path.as_posix()
        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError(f"scaffold result {field_name} paths must be repository-relative")
        if "\\" in path or path != normalized_path:
            raise ValueError(f"scaffold result {field_name} paths must use normalized POSIX form")


def _validate_scaffold_spec_path(path: object) -> None:
    if not isinstance(path, str) or not path:
        raise ValueError("scaffold spec path must be a non-empty string")
    posix_path = PurePosixPath(path)
    windows_path = PureWindowsPath(path)
    normalized_path = posix_path.as_posix()
    if (
        path == "."
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise ValueError("scaffold spec path must be repository-relative")
    if "\\" in path or path != normalized_path:
        raise ValueError("scaffold spec path must use normalized POSIX form")


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: bytes = b""
    mode: int | None = None


DESIGN_SCAFFOLD: tuple[ScaffoldSpec, ...] = (
    ScaffoldSpec(
        "docs/architecture/01-system-context.md",
        "System Context",
        "Define actors, external systems, trust boundaries, and product-scope links.",
        ("Product Links", "Actors", "External Systems", "Trust Boundaries", "Open Decisions"),
        "C4-style system context, actors, external systems, and boundaries",
    ),
    ScaffoldSpec(
        "docs/architecture/02-containers.md",
        "Containers",
        "Define deployable/runtime containers and their responsibilities.",
        ("Product Links", "Containers", "Runtime Responsibilities", "Data Ownership", "Open Decisions"),
        "C4-style containers and runtime responsibilities",
    ),
    ScaffoldSpec(
        "docs/architecture/03-quality-attributes.md",
        "Quality Attributes",
        "Make non-functional requirements measurable before implementation.",
        ("Product Links", "Availability", "Performance", "Security", "Observability", "Tradeoffs"),
        "quality attributes, measurable constraints, and tradeoffs",
    ),
    ScaffoldSpec(
        "docs/api/00-conventions.md",
        "API Conventions",
        "Define shared HTTP, auth, idempotency, pagination, and compatibility rules.",
        ("Product Links", "HTTP Conventions", "Authentication", "Idempotency", "Compatibility", "Open Decisions"),
        "shared API conventions",
    ),
    ScaffoldSpec(
        "docs/api/error-codes.md",
        "API Error Codes",
        "Define stable error codes and user-visible handling expectations.",
        ("Product Links", "Error Taxonomy", "Error Codes", "Retry Semantics", "Frontend Handling"),
        "API error code registry",
    ),
    ScaffoldSpec(
        "docs/api/changelog.md",
        "API Changelog",
        "Track API contract changes that affect frontend, backend, tests, or clients.",
        ("Change Log", "Compatibility Notes"),
        "API contract change log",
    ),
    ScaffoldSpec(
        "docs/api/endpoints/README.md",
        "API Endpoints",
        "Index endpoint contract files.",
        ("Index",),
        "endpoint contract index",
        placeholder=False,
    ),
    ScaffoldSpec(
        "docs/api/endpoints/01-endpoint-contract.md",
        "Endpoint Contract",
        "Replace this starter endpoint contract with the first product-derived API endpoint.",
        (
            "Method and Path",
            "Auth",
            "Idempotency",
            "Request Fields",
            "Response Fields",
            "Error Codes",
            "Upstream Links",
            "Frontend Consumers",
        ),
        "starter endpoint contract placeholder",
    ),
    ScaffoldSpec(
        "docs/ui/01-interaction-model.md",
        "Interaction Model",
        "Derive screens, flows, states, and user-visible errors from product requirements.",
        ("Product Links", "Primary Flows", "Screens", "States", "Errors", "Accessibility"),
        "UI flows, states, and interaction requirements",
    ),
    ScaffoldSpec(
        "docs/backend/01-modules.md",
        "Backend Modules",
        "Define backend module boundaries, responsibilities, and API ownership.",
        ("Product Links", "Architecture Links", "Modules", "API Ownership", "Failure Modes", "Open Decisions"),
        "backend module boundaries and responsibilities",
    ),
    ScaffoldSpec(
        "docs/backend/02-data-model.md",
        "Data Model",
        "Define entity ownership, lifecycle states, constraints, indexes, and migration order.",
        ("Product Links", "Owners", "Entities", "State Machines", "Constraints", "Indexes", "Migrations"),
        "data model, lifecycle, constraints, and migrations",
    ),
    ScaffoldSpec(
        "docs/backend/03-external-services.md",
        "External Services",
        "Define external service contracts, retries, timeouts, auth, and operational failure modes.",
        ("Product Links", "Dependencies", "Contracts", "Retries", "Timeouts", "Authentication", "Observability"),
        "external service contracts and failure modes",
    ),
    ScaffoldSpec(
        "docs/frontend/01-modules.md",
        "Frontend Modules",
        "Define frontend module boundaries, state ownership, and route/screen responsibilities.",
        ("Product Links", "UI Links", "Modules", "State Ownership", "Routes", "Open Decisions"),
        "frontend module boundaries and state ownership",
    ),
    ScaffoldSpec(
        "docs/frontend/02-api-consumption.md",
        "API Consumption",
        "Map frontend flows to API endpoints, loading states, errors, and retries.",
        ("Product Links", "API Links", "Consumption Map", "Loading States", "Error Actions"),
        "frontend API consumption and error handling map",
    ),
    ScaffoldSpec(
        "docs/tests/01-strategy.md",
        "Test Strategy",
        "Define test layers, acceptance evidence, and non-functional verification.",
        ("Product Links", "Acceptance Links", "Test Layers", "Risk Coverage", "Non-Functional Checks"),
        "test strategy and quality baseline",
    ),
    ScaffoldSpec(
        "docs/tests/02-acceptance-matrix.md",
        "Acceptance Matrix",
        "Map product acceptance criteria to design, API, implementation, and test evidence.",
        ("Matrix", "Uncovered Criteria"),
        "acceptance criteria traceability matrix",
    ),
    ScaffoldSpec(
        "docs/development/01-roadmap.md",
        "Roadmap",
        "Plan implementation slices without losing traceability to product and design.",
        ("Product Links", "Milestones", "Sequencing", "Risks", "Deferred Scope"),
        "implementation roadmap",
    ),
    ScaffoldSpec(
        "docs/development/02-task-board.md",
        "Task Board",
        "Track tasks with required columns: ID, Status, Task, Product, Design, API, Acceptance, Verification.",
        ("Task Table", "Status Policy", "Traceability Rules"),
        "traceable implementation task board",
    ),
    ScaffoldSpec(
        "docs/development/03-verification-log.md",
        "Verification Log",
        "Record verification commands, results, dates, notes, and evidence artifacts for completed tasks.",
        ("Verification Runs", "Artifacts", "Open Follow-ups"),
        "verification evidence log",
    ),
)

PRODUCT_SCAFFOLD_BY_KEY: dict[str, ScaffoldSpec] = {
    "background-and-problems": ScaffoldSpec(
        "docs/product/01-background-and-problems.md",
        "Background and Problems",
        "Structure the product background, motivating problems, constraints, and source references.",
        ("Source Links", "Background", "Problems", "Constraints", "Open Questions"),
        "product background, problems, constraints, and open questions",
    ),
    "change-log": ScaffoldSpec(
        "docs/product/02-change-log.md",
        "Change Log",
        "Record product-document changes that alter downstream interpretation.",
        ("Source Links", "Changes", "Impact", "Open Questions"),
        "product document change log and interpretation notes",
    ),
    "goals-and-requirements": ScaffoldSpec(
        "docs/product/03-goals-and-requirements.md",
        "Goals and Requirements",
        "Structure product goals, requirements, exclusions, and ambiguity notes.",
        ("Source Links", "Goals", "Requirements", "Out of Scope", "Open Questions"),
        "product goals, requirements, exclusions, and open questions",
    ),
    "functional-spec": ScaffoldSpec(
        "docs/product/07-functional-spec.md",
        "Functional Spec",
        "Structure user-visible functional behavior without inventing implementation details.",
        ("Source Links", "Functional Behavior", "Inputs", "Outputs", "Edge Cases", "Open Questions"),
        "functional behavior, inputs, outputs, and edge cases",
    ),
    "acceptance-criteria": ScaffoldSpec(
        "docs/product/08-acceptance-criteria.md",
        "Acceptance Criteria",
        "Extract stable product-defined acceptance criteria with A-NNN IDs.",
        ("Source Links", "Acceptance Criteria", "Deferred or Uncovered Criteria", "Open Questions"),
        "product acceptance criteria with stable A-NNN IDs",
    ),
    "success-metrics": ScaffoldSpec(
        "docs/product/09-success-metrics.md",
        "Success Metrics",
        "Structure product success metrics and measurement assumptions.",
        ("Source Links", "Metrics", "Measurement", "Targets", "Open Questions"),
        "success metrics, measurement assumptions, and targets",
    ),
}
PRODUCT_CHAPTER_CHOICES = tuple(PRODUCT_SCAFFOLD_BY_KEY)


def check_scaffold_design(root: Path) -> ScaffoldResult:
    root = root.resolve()
    gate = evaluate_gate(root, "design-derivation")
    if not gate.ok:
        return ScaffoldResult(
            scaffold="design",
            target=str(root),
            ok=False,
            check=True,
            errors=["design-derivation gate failed"],
            gate=gate.to_dict(),
        )

    result = ScaffoldResult(scaffold="design", target=str(root), ok=True, check=True, gate=gate.to_dict())
    specs: list[ScaffoldSpec] = []
    for spec in DESIGN_SCAFFOLD:
        if _should_skip_spec(root, spec):
            result.would_skip.append(spec.path)
            continue
        specs.append(spec)
    if not _preflight_design_scaffold(root, specs, result):
        return result
    _plan_scaffold(root, specs, include_product_meta=False, result=result)
    return result


def scaffold_design(root: Path) -> ScaffoldResult:
    root = root.resolve()
    gate = evaluate_gate(root, "design-derivation")
    if not gate.ok:
        return ScaffoldResult(
            scaffold="design",
            target=str(root),
            ok=False,
            errors=["design-derivation gate failed"],
            gate=gate.to_dict(),
        )

    result = ScaffoldResult(scaffold="design", target=str(root), ok=True, gate=gate.to_dict())
    specs: list[ScaffoldSpec] = []
    for spec in DESIGN_SCAFFOLD:
        if _should_skip_spec(root, spec):
            result.skipped.append(spec.path)
            continue
        specs.append(spec)
    if not _preflight_design_scaffold(root, specs, result):
        return result

    output_paths = _scaffold_output_paths(specs, include_product_meta=False)
    snapshots = _snapshot_files(root, output_paths)
    existing_dirs = _snapshot_output_dirs(root, output_paths)
    for spec in specs:
        if not result.ok:
            break
        path = root / spec.path
        if path.exists():
            result.skipped.append(spec.path)
        else:
            if not _write_scaffold_file(path, _render_spec(spec), result):
                break
            result.created.append(spec.path)
        if _ensure_index(root, spec, result):
            result.indexed.append(spec.path)
        if not result.ok:
            break
    if not result.ok:
        _rollback_scaffold_outputs(root, snapshots, output_paths, existing_dirs, result)
    return result


def _preflight_design_scaffold(root: Path, specs: list[ScaffoldSpec], result: ScaffoldResult) -> bool:
    support_paths: set[tuple[str, Path]] = set()
    for spec in specs:
        path = root / spec.path
        _preflight_scaffold_output_file(result, path)
        if path.name != "README.md":
            support_paths.add(("scaffold index", path.parent / "README.md"))
    for label, path in sorted(support_paths, key=lambda item: (item[0], item[1].as_posix())):
        _preflight_scaffold_text_file(result, label, path)
    return result.ok


def check_scaffold_product(root: Path, chapters: list[str] | tuple[str, ...]) -> ScaffoldResult:
    root = root.resolve()
    gate = evaluate_gate(root, "product-structuring")
    if not _product_scaffold_gate_allows(gate):
        return ScaffoldResult(
            scaffold="product",
            target=str(root),
            ok=False,
            check=True,
            errors=["product-structuring gate failed"],
            gate=gate.to_dict(),
        )
    if not chapters:
        return ScaffoldResult(
            scaffold="product",
            target=str(root),
            ok=False,
            check=True,
            errors=["at least one product chapter must be selected"],
            gate=gate.to_dict(),
        )

    unknown = [chapter for chapter in chapters if chapter not in PRODUCT_SCAFFOLD_BY_KEY]
    if unknown:
        return ScaffoldResult(
            scaffold="product",
            target=str(root),
            ok=False,
            check=True,
            errors=[f"unknown product chapter: {chapter}" for chapter in unknown],
            gate=gate.to_dict(),
        )

    result = ScaffoldResult(scaffold="product", target=str(root), ok=True, check=True, gate=gate.to_dict())
    seen: set[str] = set()
    specs: list[ScaffoldSpec] = []
    for chapter in chapters:
        if chapter in seen:
            continue
        seen.add(chapter)
        specs.append(PRODUCT_SCAFFOLD_BY_KEY[chapter])
    if not _preflight_product_scaffold(root, specs, result):
        return result
    _plan_scaffold(root, specs, include_product_meta=True, result=result)
    return result


def scaffold_product(root: Path, chapters: list[str] | tuple[str, ...]) -> ScaffoldResult:
    root = root.resolve()
    gate = evaluate_gate(root, "product-structuring")
    if not _product_scaffold_gate_allows(gate):
        return ScaffoldResult(
            scaffold="product",
            target=str(root),
            ok=False,
            errors=["product-structuring gate failed"],
            gate=gate.to_dict(),
        )
    if not chapters:
        return ScaffoldResult(
            scaffold="product",
            target=str(root),
            ok=False,
            errors=["at least one product chapter must be selected"],
            gate=gate.to_dict(),
        )

    unknown = [chapter for chapter in chapters if chapter not in PRODUCT_SCAFFOLD_BY_KEY]
    if unknown:
        return ScaffoldResult(
            scaffold="product",
            target=str(root),
            ok=False,
            errors=[f"unknown product chapter: {chapter}" for chapter in unknown],
            gate=gate.to_dict(),
        )

    result = ScaffoldResult(scaffold="product", target=str(root), ok=True, gate=gate.to_dict())
    seen: set[str] = set()
    specs: list[ScaffoldSpec] = []
    for chapter in chapters:
        if chapter in seen:
            continue
        seen.add(chapter)
        specs.append(PRODUCT_SCAFFOLD_BY_KEY[chapter])
    if not _preflight_product_scaffold(root, specs, result):
        return result

    output_paths = _scaffold_output_paths(specs, include_product_meta=True)
    snapshots = _snapshot_files(root, output_paths)
    existing_dirs = _snapshot_output_dirs(root, output_paths)
    for spec in specs:
        if not result.ok:
            break
        path = root / spec.path
        if path.exists():
            result.skipped.append(spec.path)
        else:
            if not _write_scaffold_file(path, _render_spec(spec), result):
                break
            result.created.append(spec.path)
        if _ensure_index(root, spec, result):
            result.indexed.append(spec.path)
        if not result.ok:
            break
        if _ensure_product_meta_link(root, spec, result):
            product_meta = "docs/product/core/product-meta.md"
            if product_meta not in result.indexed:
                result.indexed.append(product_meta)
        if not result.ok:
            break
    if not result.ok:
        _rollback_scaffold_outputs(root, snapshots, output_paths, existing_dirs, result)
    return result


def _preflight_product_scaffold(root: Path, specs: list[ScaffoldSpec], result: ScaffoldResult) -> bool:
    support_paths: set[tuple[str, Path]] = set()
    for spec in specs:
        path = root / spec.path
        _preflight_scaffold_output_file(result, path)
        support_paths.add(("scaffold index", path.parent / "README.md"))
        support_paths.add(("scaffold product meta", root / "docs/product/core/product-meta.md"))
    for label, path in sorted(support_paths, key=lambda item: (item[0], item[1].as_posix())):
        _preflight_scaffold_text_file(result, label, path)
    return result.ok


def _scaffold_output_paths(specs: list[ScaffoldSpec], include_product_meta: bool) -> list[Path]:
    paths: set[Path] = set()
    for spec in specs:
        path = Path(spec.path)
        paths.add(path)
        if path.name != "README.md":
            paths.add(path.parent / "README.md")
    if include_product_meta:
        paths.add(Path("docs/product/core/product-meta.md"))
    return sorted(paths, key=lambda path: path.as_posix())


def _plan_scaffold(
    root: Path,
    specs: list[ScaffoldSpec],
    include_product_meta: bool,
    result: ScaffoldResult,
) -> None:
    for spec in specs:
        path = root / spec.path
        if path.exists():
            result.would_skip.append(spec.path)
        else:
            result.would_create.append(spec.path)
        if _would_index(root, spec, result):
            result.would_index.append(spec.path)
        if include_product_meta and _would_product_meta_link(root, spec, result):
            product_meta = "docs/product/core/product-meta.md"
            if product_meta not in result.would_index:
                result.would_index.append(product_meta)


def _would_index(root: Path, spec: ScaffoldSpec, result: ScaffoldResult) -> bool:
    path = root / spec.path
    if path.name == "README.md":
        return False
    readme = path.parent / "README.md"
    text = _read_scaffold_text(
        result,
        readme,
        "scaffold index",
        f"# {path.parent.relative_to(root).as_posix()}\n",
    )
    if text is None:
        return False
    return path.name not in text


def _would_product_meta_link(root: Path, spec: ScaffoldSpec, result: ScaffoldResult) -> bool:
    path = root / spec.path
    if not path.as_posix().startswith(str(root / "docs/product")):
        return False
    meta = root / "docs/product/core/product-meta.md"
    text = _read_scaffold_text(result, meta, "scaffold product meta", "# Product Meta\n\n## Chapter Map\n")
    if text is None:
        return False
    return f"../{path.name}" not in text


def _snapshot_files(root: Path, rels: list[Path]) -> dict[str, _FileSnapshot]:
    snapshots: dict[str, _FileSnapshot] = {}
    for rel in rels:
        path = root / rel
        rel_key = rel.as_posix()
        if path.exists():
            stat = path.stat()
            snapshots[rel_key] = _FileSnapshot(exists=True, content=path.read_bytes(), mode=stat.st_mode)
        else:
            snapshots[rel_key] = _FileSnapshot(exists=False)
    return snapshots


def _snapshot_output_dirs(root: Path, rels: list[Path]) -> set[str]:
    dirs: set[str] = set()
    for rel in rels:
        current = root / rel.parent
        while current != root and current.is_relative_to(root):
            if current.exists() and current.is_dir():
                dirs.add(current.relative_to(root).as_posix())
            current = current.parent
    return dirs


def _rollback_scaffold_outputs(
    root: Path,
    snapshots: dict[str, _FileSnapshot],
    output_paths: list[Path],
    existing_dirs: set[str],
    result: ScaffoldResult,
) -> None:
    rollback_errors: list[str] = []
    for rel_key, snapshot in sorted(snapshots.items(), reverse=True):
        try:
            _restore_snapshot(root / rel_key, snapshot)
        except OSError as error:
            rollback_errors.append(f"failed to rollback scaffold output {rel_key}: {_os_error_reason(error)}")
    rollback_errors.extend(_cleanup_scaffold_dirs(root, output_paths, existing_dirs))
    result.created.clear()
    result.indexed.clear()
    result.errors.extend(rollback_errors)


def _restore_snapshot(path: Path, snapshot: _FileSnapshot) -> None:
    if snapshot.exists:
        _write_atomic_bytes(path, snapshot.content, snapshot.mode)
        return
    if path.exists():
        path.unlink()


def _cleanup_scaffold_dirs(root: Path, output_paths: list[Path], existing_dirs: set[str]) -> list[str]:
    errors: list[str] = []
    dirs = {root / rel.parent for rel in output_paths if rel.parent != Path(".")}
    for directory in sorted(dirs, key=lambda path: len(path.parts), reverse=True):
        try:
            if not directory.exists() or not directory.is_dir() or any(directory.iterdir()):
                continue
            rel = directory.relative_to(root).as_posix()
            if rel in existing_dirs:
                continue
            directory.rmdir()
        except OSError as error:
            rel = directory.relative_to(root).as_posix()
            errors.append(f"failed to remove empty scaffold directory {rel}: {_os_error_reason(error)}")
    return errors


def _preflight_scaffold_output_file(result: ScaffoldResult, path: Path) -> None:
    if not _preflight_scaffold_parent(result, "scaffold file", path):
        return
    if path.exists() and not path.is_file():
        _record_scaffold_read_error(result, "scaffold file", path, "is not a file")
        return
    if not path.exists():
        _preflight_scaffold_temp_file(result, "scaffold file", path)


def _preflight_scaffold_text_file(result: ScaffoldResult, label: str, path: Path) -> None:
    if not _preflight_scaffold_parent(result, label, path):
        return
    if not path.exists():
        _preflight_scaffold_temp_file(result, label, path)
        return
    if not path.is_file():
        _record_scaffold_read_error(result, label, path, "is not a file")
        return
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _record_scaffold_read_error(result, label, path, "must be UTF-8 Markdown")
        return
    except OSError as error:
        reason = error.strerror or str(error)
        _record_scaffold_read_error(result, label, path, f"is unreadable: {reason}")
        return
    _preflight_scaffold_temp_file(result, label, path)


def _preflight_scaffold_temp_file(result: ScaffoldResult, label: str, path: Path) -> None:
    temp = _atomic_temp_path(path)
    if not _preflight_scaffold_parent(result, f"{label} temp path", temp):
        return
    if temp.exists() and not temp.is_file():
        _record_scaffold_read_error(result, f"{label} temp path", temp, "is not a file")


def _preflight_scaffold_parent(result: ScaffoldResult, label: str, path: Path) -> bool:
    root = Path(result.target).resolve()
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        _record_scaffold_read_error(result, label, path.parent, "parent is outside target")
        return False
    current = root
    for part in rel.parts[:-1]:
        current = current / part
        if current.exists() and not current.is_dir():
            _record_scaffold_read_error(result, label, current, "parent is not a directory")
            return False
    return True


def _write_scaffold_file(path: Path, content: str, result: ScaffoldResult) -> bool:
    temp = _atomic_temp_path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(content, encoding="utf-8")
        temp.replace(path)
    except OSError as error:
        if temp.exists() and temp.is_file():
            try:
                temp.unlink()
            except OSError:
                pass
        _record_scaffold_write_error(result, path, error)
        return False
    return True


def _write_atomic_bytes(path: Path, content: bytes, mode: int | None = None) -> None:
    temp = _atomic_temp_path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(content)
        if mode is not None:
            temp.chmod(mode)
        temp.replace(path)
    except OSError:
        if temp.exists() and temp.is_file():
            try:
                temp.unlink()
            except OSError:
                pass
        raise


def _atomic_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def _record_scaffold_write_error(result: ScaffoldResult, path: Path, error: OSError) -> None:
    reason = _os_error_reason(error)
    rel = _result_relative_path(result, path)
    result.ok = False
    result.errors.append(f"failed to write scaffold file {rel}: {reason}")


def _record_scaffold_read_error(result: ScaffoldResult, label: str, path: Path, message: str) -> None:
    rel = _result_relative_path(result, path)
    result.ok = False
    result.errors.append(f"{label} {message}: {rel}")


def _result_relative_path(result: ScaffoldResult, path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(result.target).resolve()).as_posix()
    except ValueError:
        return str(path)


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)


def _product_scaffold_gate_allows(gate: Any) -> bool:
    if gate.ok:
        return True
    failed_requirements = {requirement.code for requirement in gate.requirements if not requirement.ok}
    if failed_requirements != {"verification_passed"}:
        return False
    findings = gate.verification.get("findings")
    if not isinstance(findings, list):
        return False
    error_findings = [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("severity") == "error"
    ]
    if not error_findings:
        return False
    return all(
        finding.get("code") == "governance_scaffold_placeholder"
        and isinstance(finding.get("path"), str)
        and finding["path"].startswith("docs/product/")
        for finding in error_findings
    )


def _should_skip_spec(root: Path, spec: ScaffoldSpec) -> bool:
    if spec.path != STARTER_ENDPOINT_CONTRACT_PATH:
        return False
    if (root / spec.path).exists():
        return False
    return _has_endpoint_contract(root)


def _has_endpoint_contract(root: Path) -> bool:
    endpoint_root = root / "docs/api/endpoints"
    if not endpoint_root.exists():
        return False
    for path in endpoint_root.glob("*.md"):
        if path.name in {"README.md", "AGENTS.md"} or path.name.startswith("_"):
            continue
        return True
    return False


def _render_spec(spec: ScaffoldSpec) -> str:
    lines = [f"# {spec.title}", ""]
    if spec.placeholder:
        lines.extend(
            [
                f"<!-- {SCAFFOLD_PLACEHOLDER} -->",
                "",
                "> Replace this scaffold with product-derived content and remove the placeholder marker before implementation.",
                "",
            ]
        )
    lines.extend([spec.purpose, ""])
    for section in spec.sections:
        lines.extend([f"## {section}", "", *_section_lines(spec.path, section), ""])
    return "\n".join(lines).rstrip() + "\n"


def _section_lines(path: str, section: str) -> list[str]:
    key = (path, section)
    if path.startswith("docs/product/") and section == "Source Links":
        return ["- [PRD](core/PRD.md)"]
    if key == ("docs/product/08-acceptance-criteria.md", "Acceptance Criteria"):
        return [
            "Document only source-backed acceptance criteria.",
            "",
            "### A-NNN Criterion Title",
            "",
            "- Replace with a product-defined, testable criterion.",
        ]
    if path.startswith("docs/product/") and section == "Open Questions":
        return ["- Register blocking ambiguity in [unresolved](../unresolved.md) instead of guessing."]
    if key == ("docs/tests/02-acceptance-matrix.md", "Matrix"):
        return [
            "| Acceptance | Design | API | Test |",
            "| --- | --- | --- | --- |",
            "| A-NNN acceptance source | design source | endpoint contract source | test evidence source |",
        ]
    if key == ("docs/tests/02-acceptance-matrix.md", "Uncovered Criteria"):
        return ["- A-NNN deferred or uncovered reason"]
    if key == ("docs/development/01-roadmap.md", "Milestones"):
        return [
            "| ID | Status | Milestone |",
            "| --- | --- | --- |",
            "| TASK-NNN | Backlog | Product-derived milestone |",
        ]
    if key == ("docs/development/02-task-board.md", "Task Table"):
        return [
            "| ID | Status | Task | Product | Design | API | Acceptance | Verification |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
            "| TASK-NNN | Backlog | Product-derived task | product source | design source | endpoint contract source | A-NNN acceptance source | verification plan |",
        ]
    if key == ("docs/development/02-task-board.md", "Status Policy"):
        return ["- Allowed statuses: Backlog, Ready, In Progress, Blocked, Done, Deferred."]
    if key == ("docs/development/02-task-board.md", "Traceability Rules"):
        return [
            "- Product, Design, API, and Acceptance cells must reference existing local Markdown sources.",
            "- Done tasks must link Verification to local Markdown evidence.",
        ]
    if key == ("docs/development/03-verification-log.md", "Verification Runs"):
        return [
            "| Task | Command | Result | Date | Notes |",
            "| --- | --- | --- | --- | --- |",
            "| TASK-NNN | verification command | pending | YYYY-MM-DD | evidence notes |",
        ]
    if key == ("docs/development/03-verification-log.md", "Artifacts"):
        return ["- Link local evidence artifacts or summarize relevant command output here."]
    if key == ("docs/development/03-verification-log.md", "Open Follow-ups"):
        return ["- none"]
    return ["- TBD"]


def _ensure_index(root: Path, spec: ScaffoldSpec, result: ScaffoldResult) -> bool:
    path = root / spec.path
    if path.name == "README.md":
        return False
    readme = path.parent / "README.md"
    try:
        readme.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        _record_scaffold_write_error(result, readme, error)
        return False
    text = _read_scaffold_text(
        result,
        readme,
        "scaffold index",
        f"# {path.parent.relative_to(root).as_posix()}\n",
    )
    if text is None:
        return False
    filename = path.name
    if filename in text:
        return False
    if "## Index" not in text:
        text = text.rstrip() + "\n\n## Index\n"
    text = text.rstrip() + f"\n\n- `{filename}` - {spec.index_description}\n"
    return _write_scaffold_file(readme, text, result)


def _ensure_product_meta_link(root: Path, spec: ScaffoldSpec, result: ScaffoldResult) -> bool:
    path = root / spec.path
    if not path.as_posix().startswith(str(root / "docs/product")):
        return False
    meta = root / "docs/product/core/product-meta.md"
    try:
        meta.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        _record_scaffold_write_error(result, meta, error)
        return False
    text = _read_scaffold_text(result, meta, "scaffold product meta", "# Product Meta\n\n## Chapter Map\n")
    if text is None:
        return False
    rel_link = f"../{path.name}"
    if rel_link in text:
        return False
    if "## Chapter Map" not in text:
        text = text.rstrip() + "\n\n## Chapter Map\n"
    text = text.rstrip() + f"\n\n- [{spec.title}]({rel_link})\n"
    return _write_scaffold_file(meta, text, result)


def _read_scaffold_text(result: ScaffoldResult, path: Path, label: str, default: str) -> str | None:
    if not path.exists():
        return default
    if not path.is_file():
        _record_scaffold_read_error(result, label, path, "is not a file")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _record_scaffold_read_error(result, label, path, "must be UTF-8 Markdown")
    except OSError as error:
        reason = error.strerror or str(error)
        _record_scaffold_read_error(result, label, path, f"is unreadable: {reason}")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Create standard docs-as-code governance scaffolds.")
    parser.add_argument("scaffold", choices=("product", "design"), help="Scaffold kind to create.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to update.")
    parser.add_argument(
        "--chapter",
        action="append",
        choices=PRODUCT_CHAPTER_CHOICES,
        default=[],
        help="Product chapter to scaffold. Repeat for multiple chapters.",
    )
    parser.add_argument("--check", action="store_true", help="Run scaffold preflight without writing files.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable scaffold result.")
    args = parser.parse_args()
    target = Path(args.target)
    if args.scaffold != "product" and args.chapter:
        result = ScaffoldResult(
            scaffold=args.scaffold,
            target=str(target),
            ok=False,
            check=args.check,
            errors=[f"scaffold {args.scaffold} does not accept --chapter"],
            gate={},
        )
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
            return 1
        print(f"Scaffold failed: {args.scaffold}")
        for error in result.errors:
            print(f"- ERROR: {error}")
        return 1
    if args.scaffold == "design":
        result = check_scaffold_design(target) if args.check else scaffold_design(target)
    elif args.scaffold == "product":
        result = check_scaffold_product(target, args.chapter) if args.check else scaffold_product(target, args.chapter)
    else:  # pragma: no cover - argparse choices prevent this
        raise ValueError(f"unknown scaffold: {args.scaffold}")
    payload = result.to_dict()
    payload.update(scaffold_continuation_payload(result))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.ok else 1
    if not result.ok:
        print(f"Scaffold failed: {args.scaffold}")
        for error in result.errors:
            print(f"- ERROR: {error}")
        return 1
    if args.check:
        print(f"Scaffold preflight passed: {args.scaffold}")
        for path in result.would_create:
            print(f"- WOULD CREATE: {path}")
        for path in result.would_skip:
            print(f"- WOULD SKIP: {path}")
        for path in result.would_index:
            print(f"- WOULD INDEX: {path}")
        return 0
    print(f"Scaffold created: {args.scaffold}")
    for path in result.created:
        print(f"- CREATED: {path}")
    for path in result.skipped:
        print(f"- SKIPPED: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
