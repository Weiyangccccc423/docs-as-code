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
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render_spec(spec), encoding="utf-8")
            result.created.append(spec.path)
        if _ensure_index(root, spec):
            result.indexed.append(spec.path)
    return result


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


def _ensure_index(root: Path, spec: ScaffoldSpec) -> bool:
    path = root / spec.path
    if path.name == "README.md":
        return False
    readme = path.parent / "README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
    else:
        text = f"# {path.parent.relative_to(root).as_posix()}\n"
    filename = path.name
    if filename in text:
        return False
    if "## Index" not in text:
        text = text.rstrip() + "\n\n## Index\n"
    text = text.rstrip() + f"\n\n- `{filename}` - {spec.index_description}\n"
    readme.write_text(text, encoding="utf-8")
    return True
