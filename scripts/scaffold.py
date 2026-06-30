from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .gates import evaluate_gate
except ImportError:  # pragma: no cover - direct script execution
    from gates import evaluate_gate


SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
STARTER_ENDPOINT_CONTRACT_PATH = "docs/api/endpoints/01-endpoint-contract.md"


@dataclass(frozen=True)
class ScaffoldSpec:
    path: str
    title: str
    purpose: str
    sections: tuple[str, ...]
    index_description: str
    placeholder: bool = True


@dataclass
class ScaffoldResult:
    scaffold: str
    target: str
    ok: bool
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    indexed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    gate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "scaffold": self.scaffold,
            "target": self.target,
            "ok": self.ok,
            "created": self.created,
            "skipped": self.skipped,
            "indexed": self.indexed,
            "errors": self.errors,
            "gate": self.gate,
        }


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
    for spec in DESIGN_SCAFFOLD:
        if _should_skip_spec(root, spec):
            result.skipped.append(spec.path)
            continue
        path = root / spec.path
        if path.exists():
            result.skipped.append(spec.path)
        else:
            if not _write_scaffold_file(path, _render_spec(spec), result):
                continue
            result.created.append(spec.path)
        if _ensure_index(root, spec, result):
            result.indexed.append(spec.path)
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
    for chapter in chapters:
        if chapter in seen:
            continue
        seen.add(chapter)
        spec = PRODUCT_SCAFFOLD_BY_KEY[chapter]
        path = root / spec.path
        if path.exists():
            result.skipped.append(spec.path)
        else:
            if not _write_scaffold_file(path, _render_spec(spec), result):
                continue
            result.created.append(spec.path)
        if _ensure_index(root, spec, result):
            result.indexed.append(spec.path)
        if _ensure_product_meta_link(root, spec, result):
            product_meta = "docs/product/core/product-meta.md"
            if product_meta not in result.indexed:
                result.indexed.append(product_meta)
    return result


def _write_scaffold_file(path: Path, content: str, result: ScaffoldResult) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as error:
        _record_scaffold_write_error(result, path, error)
        return False
    return True


def _record_scaffold_write_error(result: ScaffoldResult, path: Path, error: OSError) -> None:
    reason = error.strerror or str(error)
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
    try:
        readme.write_text(text, encoding="utf-8")
    except OSError as error:
        _record_scaffold_write_error(result, readme, error)
        return False
    return True


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
    try:
        meta.write_text(text, encoding="utf-8")
    except OSError as error:
        _record_scaffold_write_error(result, meta, error)
        return False
    return True


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
