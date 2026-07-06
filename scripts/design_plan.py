from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .bootstrap_tree import target_local_commands_payload
    from .state import load_state
    from .verify_governance import VerificationFinding, verify
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from state import load_state
    from verify_governance import VerificationFinding, verify
    from workflow_actions import next_actions_payload


DESIGN_WORKFLOW_PATH = "workflows/04-design-derivation.md"
DESIGN_PHASE = "design-derivation"
API_TRACK_ID = "api-contracts"
STARTER_ENDPOINT_CONTRACT = "docs/api/endpoints/01-endpoint-contract.md"
ACCEPTANCE_HEADING_RE = re.compile(r"^##[ \t]+(?P<id>A-[0-9]{3})[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
SLUG_TOKEN_RE = re.compile(r"[a-z0-9]+")
OPEN_API_DECISIONS = (
    "method_path",
    "auth",
    "idempotency",
    "request_fields",
    "response_fields",
    "error_codes",
    "upstream_links",
    "frontend_consumers",
)


@dataclass(frozen=True)
class DesignTrack:
    id: str
    title: str
    purpose: str
    skills: tuple[str, ...]
    references: tuple[str, ...]
    documents: tuple[str, ...]
    procedure: str


DESIGN_TRACKS: tuple[DesignTrack, ...] = (
    DesignTrack(
        id="architecture",
        title="System Architecture",
        purpose="Replace architecture placeholders with product-derived boundaries, C4-style views, and quality scenarios.",
        skills=("designing-system-architecture",),
        references=("references/architecture-methods.md", "references/architecture-quality-checklist.md"),
        documents=(
            "docs/architecture/01-system-context.md",
            "docs/architecture/02-containers.md",
            "docs/architecture/03-quality-attributes.md",
        ),
        procedure="Read product scope and acceptance criteria before defining boundaries, containers, dependencies, risks, and measurable quality attributes.",
    ),
    DesignTrack(
        id="ui-interaction",
        title="UI Interaction",
        purpose="Replace UI placeholders with product-derived flows, screens, states, errors, and accessibility expectations.",
        skills=("designing-ui-interactions",),
        references=("references/frontend-interaction-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/ui/01-interaction-model.md",),
        procedure="Derive visible behavior from product sources and register unresolved interaction or accessibility gaps instead of guessing.",
    ),
    DesignTrack(
        id="api-contracts",
        title="API Contracts",
        purpose="Replace API placeholders with traceable conventions, endpoint contracts, error handling, auth, and compatibility notes.",
        skills=("designing-api-contracts",),
        references=(
            "references/architecture-methods.md",
            "references/api-design-checklist.md",
            "references/security-design-checklist.md",
        ),
        documents=(
            "docs/api/00-conventions.md",
            "docs/api/error-codes.md",
            "docs/api/changelog.md",
            "docs/api/endpoints/README.md",
            "docs/api/endpoints/01-endpoint-contract.md",
        ),
        procedure="Name concrete endpoint contracts only after method, path, auth, idempotency, errors, upstream links, and frontend consumers are source-backed.",
    ),
    DesignTrack(
        id="backend-modules",
        title="Backend Modules",
        purpose="Replace backend placeholders with module boundaries, API ownership, failure modes, operability, and dependency behavior.",
        skills=("designing-backend-modules",),
        references=(
            "references/backend-design-checklist.md",
            "references/backend-operability-checklist.md",
            "references/security-design-checklist.md",
        ),
        documents=("docs/backend/01-modules.md", "docs/backend/03-external-services.md"),
        procedure="Use architecture and API contracts before assigning module ownership, runtime flows, observability, retries, timeouts, or support expectations.",
    ),
    DesignTrack(
        id="data-model",
        title="Data Model",
        purpose="Replace data-model placeholders with entity ownership, states, constraints, indexes, migrations, retention, and audit decisions.",
        skills=("designing-data-models",),
        references=("references/backend-design-checklist.md", "references/data-model-design-checklist.md"),
        documents=("docs/backend/02-data-model.md",),
        procedure="Start from product nouns and backend ownership; define lifecycle and concurrency behavior before fields and indexes.",
    ),
    DesignTrack(
        id="frontend-modules",
        title="Frontend Modules",
        purpose="Replace frontend placeholders with module boundaries, state ownership, routes, API consumption, and error actions.",
        skills=("designing-frontend-modules",),
        references=("references/frontend-interaction-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/frontend/01-modules.md", "docs/frontend/02-api-consumption.md"),
        procedure="Use UI interaction design and API contracts before assigning route, state, loading, retry, and error handling behavior.",
    ),
    DesignTrack(
        id="test-strategy",
        title="Test Strategy",
        purpose="Replace test placeholders with acceptance traceability, risk coverage, verification layers, and non-functional checks.",
        skills=("designing-test-strategy",),
        references=("references/test-strategy-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/tests/01-strategy.md", "docs/tests/02-acceptance-matrix.md"),
        procedure="Map each product-defined A-NNN to design, concrete endpoint contracts, and test evidence, or list it under uncovered criteria with a source-backed reason.",
    ),
    DesignTrack(
        id="implementation-planning",
        title="Implementation Planning",
        purpose="Replace development placeholders with roadmap milestones, task board rows, Ready criteria, and verification evidence targets.",
        skills=("planning-implementation-work",),
        references=("references/implementation-readiness-checklist.md", "references/implementation-execution-checklist.md"),
        documents=(
            "docs/development/01-roadmap.md",
            "docs/development/02-task-board.md",
            "docs/development/03-verification-log.md",
        ),
        procedure="Create TASK-NNN work only from completed product, design, API, acceptance, and test sources; do not mark tasks Ready while blockers remain.",
    ),
    DesignTrack(
        id="architecture-decisions",
        title="Architecture Decisions",
        purpose="Capture cross-module, high-cost, or reversible-later decisions as ADRs with source-backed context.",
        skills=("capturing-architecture-decisions",),
        references=("references/architecture-decision-record-checklist.md",),
        documents=("docs/decisions/_template.md",),
        procedure="Create a numbered ADR only when the design work makes a consequential decision; keep references local and traceable.",
    ),
)


def build_design_plan(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    report = verify(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase != DESIGN_PHASE:
        errors.append(f"design plan requires recorded phase {DESIGN_PHASE}")
    source_documents = _source_documents(root)
    findings_by_path = _findings_by_path(report.findings)
    tracks = [_track_payload(root, track, source_documents, findings_by_path) for track in DESIGN_TRACKS]
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "verification_ok": report.ok,
        "errors": errors,
        "source_documents": source_documents,
        "tracks": tracks,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_api_candidates(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase != DESIGN_PHASE:
        errors.append(f"API candidates require recorded phase {DESIGN_PHASE}")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": API_TRACK_ID,
        "skills": ["designing-api-contracts"],
        "references": [
            "references/architecture-methods.md",
            "references/api-design-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "candidates": candidates,
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def _source_documents(root: Path) -> list[str]:
    candidates: list[str] = []
    for rel in ("docs/product/core/PRD.md", "docs/unresolved.md", "docs/glossary.md"):
        if (root / rel).is_file():
            candidates.append(rel)
    product_root = root / "docs/product"
    if product_root.is_dir():
        for path in sorted(product_root.glob("[0-9][0-9]-*.md")):
            if path.is_file():
                candidates.append(path.relative_to(root).as_posix())
    return sorted(dict.fromkeys(candidates))


def _api_candidates(root: Path) -> list[dict[str, object]]:
    acceptance_headings = _acceptance_headings(root)
    start_prefix = _next_endpoint_prefix(root)
    candidates: list[dict[str, object]] = []
    for index, item in enumerate(acceptance_headings, start=1):
        prefix = start_prefix + index - 1
        slug = _slugify(item["title"])
        suggested_endpoint_file = f"docs/api/endpoints/{prefix:02d}-{slug}.md"
        candidates.append(
            {
                "candidate_id": f"API-{index:03d}",
                "acceptance_id": item["acceptance_id"],
                "title": item["title"],
                "source": {
                    "path": item["path"],
                    "anchor": item["anchor"],
                    "reference": f"{item['path']}#{item['anchor']}",
                },
                "suggested_endpoint_file": suggested_endpoint_file,
                "endpoint_exists": (root / suggested_endpoint_file).is_file(),
                "replaceable_starter_endpoint": STARTER_ENDPOINT_CONTRACT
                if (root / STARTER_ENDPOINT_CONTRACT).is_file()
                else "",
                "open_decisions": list(OPEN_API_DECISIONS),
            }
        )
    return candidates


def _acceptance_headings(root: Path) -> list[dict[str, str]]:
    product_root = root / "docs/product"
    if not product_root.is_dir():
        return []
    headings: list[dict[str, str]] = []
    for path in sorted(product_root.glob("[0-9][0-9]-*acceptance*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in ACCEPTANCE_HEADING_RE.finditer(text):
            title = match.group("title").strip()
            acceptance_id = match.group("id")
            headings.append(
                {
                    "acceptance_id": acceptance_id,
                    "title": title,
                    "path": rel,
                    "anchor": _markdown_anchor(f"{acceptance_id} {title}"),
                }
            )
    return headings


def _next_endpoint_prefix(root: Path) -> int:
    endpoint_root = root / "docs/api/endpoints"
    prefixes: list[int] = []
    if endpoint_root.is_dir():
        for path in endpoint_root.glob("[0-9][0-9]-*.md"):
            rel = path.relative_to(root).as_posix()
            if rel == STARTER_ENDPOINT_CONTRACT:
                continue
            try:
                prefixes.append(int(path.name[:2]))
            except ValueError:
                continue
    return max(prefixes, default=0) + 1


def _slugify(value: str) -> str:
    slug = "-".join(SLUG_TOKEN_RE.findall(value.lower()))
    return slug or "endpoint"


def _markdown_anchor(value: str) -> str:
    return _slugify(value)


def _findings_by_path(findings: list[VerificationFinding]) -> dict[str, list[dict[str, str]]]:
    findings_by_path: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        if not finding.path:
            continue
        findings_by_path.setdefault(finding.path, []).append(finding.to_dict())
    return findings_by_path


def _track_payload(
    root: Path,
    track: DesignTrack,
    source_documents: list[str],
    findings_by_path: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    documents = list(track.documents)
    blockers: list[dict[str, str]] = []
    document_status: list[dict[str, object]] = []
    for document in documents:
        path = root / document
        document_blockers = list(findings_by_path.get(document, []))
        blockers.extend(document_blockers)
        document_status.append(
            {
                "path": document,
                "exists": path.is_file(),
                "blockers": document_blockers,
            }
        )
    return {
        "id": track.id,
        "title": track.title,
        "purpose": track.purpose,
        "status": _track_status(document_status, blockers),
        "skills": list(track.skills),
        "references": list(track.references),
        "documents": documents,
        "document_status": document_status,
        "blockers": blockers,
        "procedure": track.procedure,
        "steps": _track_steps(root, track, source_documents, documents, blockers),
    }


def _track_steps(
    root: Path,
    track: DesignTrack,
    source_documents: list[str],
    documents: list[str],
    blockers: list[dict[str, str]],
) -> list[dict[str, object]]:
    return [
        {
            "id": "load-track-skills",
            "kind": "skill-load",
            "skills": list(track.skills),
            "description": "Load the listed skills before interpreting or editing this design track.",
        },
        {
            "id": "read-product-sources",
            "kind": "read",
            "documents": list(source_documents),
            "description": "Read product truth, acceptance criteria, glossary, and unresolved items before authoring.",
        },
        {
            "id": "read-track-references",
            "kind": "read",
            "references": list(track.references),
            "description": "Read the authoritative checklists and method references for this track.",
        },
        {
            "id": "author-track-documents",
            "kind": "author",
            "documents": list(documents),
            "blockers": list(blockers),
            "description": "Replace placeholders with source-backed content and register unresolved gaps instead of guessing.",
        },
        _command_step(
            root,
            "verify-track",
            "Run read-only governance verification after authoring this track.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-design-plan",
            "Refresh the design authoring queue after verification.",
            ["bin/governance", "design", "plan", ".", "--json"],
        ),
    ]


def _command_step(root: Path, step_id: str, description: str, argv: list[str]) -> dict[str, object]:
    return {
        "id": step_id,
        "kind": "command",
        "cwd": str(root),
        "command": " ".join(argv),
        "argv": list(argv),
        "writes_state": False,
        "approval_required": False,
        "description": description,
    }


def _track_status(document_status: list[dict[str, Any]], blockers: list[dict[str, str]]) -> str:
    if blockers:
        return "authoring_blocked"
    if any(not item["exists"] for item in document_status):
        return "missing_documents"
    return "ready_for_review"
