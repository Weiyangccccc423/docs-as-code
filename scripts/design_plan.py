from __future__ import annotations

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
    findings_by_path = _findings_by_path(report.findings)
    tracks = [_track_payload(root, track, findings_by_path) for track in DESIGN_TRACKS]
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "verification_ok": report.ok,
        "errors": errors,
        "tracks": tracks,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def _findings_by_path(findings: list[VerificationFinding]) -> dict[str, list[dict[str, str]]]:
    findings_by_path: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        if not finding.path:
            continue
        findings_by_path.setdefault(finding.path, []).append(finding.to_dict())
    return findings_by_path


def _track_payload(root: Path, track: DesignTrack, findings_by_path: dict[str, list[dict[str, str]]]) -> dict[str, object]:
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
    }


def _track_status(document_status: list[dict[str, Any]], blockers: list[dict[str, str]]) -> str:
    if blockers:
        return "authoring_blocked"
    if any(not item["exists"] for item in document_status):
        return "missing_documents"
    return "ready_for_review"
