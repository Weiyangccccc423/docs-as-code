from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .api_review_evidence import API_OPENAPI_REL, build_openapi_contract_inventory
    from .bootstrap_tree import target_local_commands_payload
    from .design_reviews import (
        DESIGN_REVIEWS_REL,
        DESIGN_REVIEW_TRACK_SPECS,
        apply_design_reviews,
        build_design_review_inventory,
        design_review_enforcement_ready,
    )
    from .state import load_state
    from .verify_governance import VerificationFinding, verify
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from api_review_evidence import API_OPENAPI_REL, build_openapi_contract_inventory
    from bootstrap_tree import target_local_commands_payload
    from design_reviews import (
        DESIGN_REVIEWS_REL,
        DESIGN_REVIEW_TRACK_SPECS,
        apply_design_reviews,
        build_design_review_inventory,
        design_review_enforcement_ready,
    )
    from state import load_state
    from verify_governance import VerificationFinding, verify
    from workflow_actions import next_actions_payload


DESIGN_WORKFLOW_PATH = "workflows/04-design-derivation.md"
DESIGN_PHASE = "design-derivation"
DESIGN_AUTHORING_PHASES = frozenset({DESIGN_PHASE, "implementation"})
TARGET_WORKFLOW_PACK_ROOT = "docs/agent-workflow/workflow-pack"
ARCHITECTURE_TRACK_ID = "architecture"
UI_INTERACTION_TRACK_ID = "ui-interaction"
API_TRACK_ID = "api-contracts"
BACKEND_TRACK_ID = "backend-modules"
DATA_MODEL_TRACK_ID = "data-model"
FRONTEND_TRACK_ID = "frontend-modules"
TEST_STRATEGY_TRACK_ID = "test-strategy"
IMPLEMENTATION_PLANNING_TRACK_ID = "implementation-planning"
ARCHITECTURE_DECISIONS_TRACK_ID = "architecture-decisions"
STARTER_ENDPOINT_CONTRACT = "docs/api/endpoints/01-endpoint-contract.md"
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
ACCEPTANCE_HEADING_RE = re.compile(r"^##[ \t]+(?P<id>A-[0-9]{3})[ \t]+(?P<title>.+?)[ \t]*$", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
TASK_ID_RE = re.compile(r"\bTASK-(?P<num>[0-9]{3})\b")
ADR_ID_RE = re.compile(r"^(?P<num>[0-9]{3})-[a-z0-9][a-z0-9-]*\.md$")
SLUG_TOKEN_RE = re.compile(r"[a-z0-9]+")
OPEN_API_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[API_TRACK_ID]["decisions"])
OPEN_ARCHITECTURE_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[ARCHITECTURE_TRACK_ID]["decisions"])
ARCHITECTURE_SYSTEM_CONTEXT_SECTIONS = (
    "Product Links",
    "Actors",
    "External Systems",
    "Trust Boundaries",
    "Open Decisions",
)
ARCHITECTURE_CONTAINERS_SECTIONS = (
    "Product Links",
    "Containers",
    "Runtime Responsibilities",
    "Data Ownership",
    "Open Decisions",
)
ARCHITECTURE_QUALITY_SECTIONS = (
    "Product Links",
    "Availability",
    "Performance",
    "Security",
    "Observability",
    "Tradeoffs",
)
API_CONVENTION_SECTIONS = (
    "Product Links",
    "HTTP Conventions",
    "Authentication",
    "Idempotency",
    "Compatibility",
    "Open Decisions",
)
API_ERROR_CODE_SECTIONS = (
    "Product Links",
    "Error Taxonomy",
    "Error Codes",
    "Retry Semantics",
    "Frontend Handling",
)
API_CHANGELOG_SECTIONS = (
    "Change Log",
    "Compatibility Notes",
)
API_ENDPOINT_SECTIONS = (
    "Method and Path",
    "Auth",
    "Idempotency",
    "Request Fields",
    "Response Fields",
    "Error Codes",
    "Upstream Links",
    "Frontend Consumers",
)
OPEN_BACKEND_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[BACKEND_TRACK_ID]["decisions"])
OPEN_DATA_MODEL_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[DATA_MODEL_TRACK_ID]["decisions"])
BACKEND_MODULE_SECTIONS = (
    "Product Links",
    "Architecture Links",
    "Modules",
    "API Ownership",
    "Failure Modes",
    "Open Decisions",
)
BACKEND_DATA_MODEL_SECTIONS = (
    "Product Links",
    "Owners",
    "Entities",
    "State Machines",
    "Constraints",
    "Indexes",
    "Migrations",
)
BACKEND_EXTERNAL_SERVICE_SECTIONS = (
    "Product Links",
    "Dependencies",
    "Contracts",
    "Retries",
    "Timeouts",
    "Authentication",
    "Observability",
)
OPEN_FRONTEND_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[FRONTEND_TRACK_ID]["decisions"])
OPEN_UI_INTERACTION_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[UI_INTERACTION_TRACK_ID]["decisions"])
UI_INTERACTION_SECTIONS = (
    "Product Links",
    "Primary Flows",
    "Screens",
    "States",
    "Errors",
    "Accessibility",
)
FRONTEND_MODULE_SECTIONS = (
    "Product Links",
    "UI Links",
    "Modules",
    "State Ownership",
    "Routes",
    "Open Decisions",
)
FRONTEND_API_CONSUMPTION_SECTIONS = (
    "Product Links",
    "API Links",
    "Consumption Map",
    "Loading States",
    "Error Actions",
)
OPEN_TEST_STRATEGY_DECISIONS = tuple(DESIGN_REVIEW_TRACK_SPECS[TEST_STRATEGY_TRACK_ID]["decisions"])
TEST_STRATEGY_SECTIONS = (
    "Product Links",
    "Acceptance Links",
    "Test Layers",
    "Risk Coverage",
    "Non-Functional Checks",
)
ACCEPTANCE_MATRIX_SECTIONS = (
    "Matrix",
    "Uncovered Criteria",
)
OPEN_IMPLEMENTATION_PLANNING_DECISIONS = tuple(
    DESIGN_REVIEW_TRACK_SPECS[IMPLEMENTATION_PLANNING_TRACK_ID]["decisions"]
)
ROADMAP_SECTIONS = (
    "Product Links",
    "Milestones",
    "Sequencing",
    "Risks",
    "Deferred Scope",
)
TASK_BOARD_SECTIONS = (
    "Task Table",
    "Status Policy",
    "Traceability Rules",
)
VERIFICATION_LOG_SECTIONS = (
    "Verification Runs",
    "Artifacts",
    "Open Follow-ups",
)
OPEN_ARCHITECTURE_DECISION_DECISIONS = tuple(
    DESIGN_REVIEW_TRACK_SPECS[ARCHITECTURE_DECISIONS_TRACK_ID]["decisions"]
)
ADR_SECTIONS = (
    "Context",
    "Decision",
    "Consequences",
    "References",
)
LOCAL_WORKFLOW_SKILL_MISSING_POLICY = "workflow_pack_integrity_error"
AUTHORITY_ROUTING_SKILL_MISSING_POLICY = "load_from_agent_environment_or_stop_before_guessing"
AUTHORITY_ROUTING_SPECIALIST_SKILLS = frozenset(
    {
        "a11y-audit",
        "api-design-reviewer",
        "ci-cd-pipeline-builder",
        "database-designer",
        "database-schema-designer",
        "migration-architect",
        "observability-designer",
        "performance-profiler",
        "playwright-pro",
        "security-pen-testing",
        "senior-architect",
        "senior-backend",
        "senior-frontend",
        "senior-fullstack",
        "senior-qa",
        "senior-security",
        "slo-architect",
        "tech-debt-tracker",
        "tech-stack-evaluator",
    }
)


@dataclass(frozen=True)
class DesignTrack:
    id: str
    title: str
    purpose: str
    skills: tuple[str, ...]
    specialist_skills: tuple[str, ...]
    references: tuple[str, ...]
    documents: tuple[str, ...]
    procedure: str


DESIGN_TRACKS: tuple[DesignTrack, ...] = (
    DesignTrack(
        id=ARCHITECTURE_TRACK_ID,
        title="System Architecture",
        purpose="Replace architecture placeholders with product-derived boundaries, C4-style views, and quality scenarios.",
        skills=("designing-system-architecture",),
        specialist_skills=("senior-architect", "senior-security", "observability-designer", "slo-architect"),
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
        specialist_skills=("senior-frontend", "a11y-audit"),
        references=("references/frontend-interaction-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/ui/01-interaction-model.md",),
        procedure="Derive visible behavior from product sources and register unresolved interaction or accessibility gaps instead of guessing.",
    ),
    DesignTrack(
        id="api-contracts",
        title="API Contracts",
        purpose="Replace API placeholders with traceable conventions, endpoint contracts, error handling, auth, and compatibility notes.",
        skills=("designing-api-contracts",),
        specialist_skills=("api-design-reviewer", "senior-backend", "senior-security"),
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
        specialist_skills=("senior-backend", "observability-designer", "slo-architect", "senior-security"),
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
        specialist_skills=("database-designer", "database-schema-designer", "migration-architect", "senior-backend", "senior-security"),
        references=("references/backend-design-checklist.md", "references/data-model-design-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/backend/02-data-model.md",),
        procedure="Start from product nouns and backend ownership; define lifecycle and concurrency behavior before fields and indexes.",
    ),
    DesignTrack(
        id="frontend-modules",
        title="Frontend Modules",
        purpose="Replace frontend placeholders with module boundaries, state ownership, routes, API consumption, and error actions.",
        skills=("designing-frontend-modules",),
        specialist_skills=("senior-frontend", "a11y-audit", "performance-profiler"),
        references=("references/frontend-interaction-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/frontend/01-modules.md", "docs/frontend/02-api-consumption.md"),
        procedure="Use UI interaction design and API contracts before assigning route, state, loading, retry, and error handling behavior.",
    ),
    DesignTrack(
        id="test-strategy",
        title="Test Strategy",
        purpose="Replace test placeholders with acceptance traceability, risk coverage, verification layers, and non-functional checks.",
        skills=("designing-test-strategy",),
        specialist_skills=("senior-qa", "playwright-pro", "a11y-audit", "security-pen-testing"),
        references=("references/test-strategy-checklist.md", "references/security-design-checklist.md"),
        documents=("docs/tests/01-strategy.md", "docs/tests/02-acceptance-matrix.md"),
        procedure="Map each product-defined A-NNN to design, concrete endpoint contracts, and test evidence, or list it under uncovered criteria with a source-backed reason.",
    ),
    DesignTrack(
        id="implementation-planning",
        title="Implementation Planning",
        purpose="Replace development placeholders with roadmap milestones, task board rows, Ready criteria, and verification evidence targets.",
        skills=("planning-implementation-work",),
        specialist_skills=("senior-fullstack", "ci-cd-pipeline-builder", "tech-debt-tracker"),
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
        specialist_skills=("senior-architect", "migration-architect", "tech-stack-evaluator"),
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
    tracks = [
        _track_payload(root, track, sequence, source_documents, findings_by_path)
        for sequence, track in enumerate(DESIGN_TRACKS, start=1)
    ]
    review_inventory = build_design_review_inventory(root)
    errors.extend(_string_items(review_inventory.get("errors")))
    tracks = _apply_design_review_track_status(
        tracks,
        review_inventory,
        enforce_missing=design_review_enforcement_ready(root),
    )
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "verification_ok": report.ok,
        "errors": errors,
        "source_documents": source_documents,
        "design_review_path": DESIGN_REVIEWS_REL.as_posix(),
        "design_review_summary": review_inventory.get("summary", {}),
        "active_design_reviews": review_inventory.get("active", []),
        "stale_design_reviews": review_inventory.get("stale", []),
        "missing_design_reviews": review_inventory.get("missing", []),
        "tracks": tracks,
        "active_work": _active_design_track_work(root, tracks),
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def _apply_design_review_track_status(
    tracks: list[dict[str, object]],
    inventory: dict[str, object],
    *,
    enforce_missing: bool,
) -> list[dict[str, object]]:
    active = _dict_items(inventory.get("active"))
    stale = _dict_items(inventory.get("stale"))
    missing = _dict_items(inventory.get("missing")) if enforce_missing else []
    orphan = _dict_items(inventory.get("orphan"))
    updated: list[dict[str, object]] = []
    for original in tracks:
        track = dict(original)
        track_id = str(track.get("id", ""))
        active_items = [item for item in active if item.get("track") == track_id]
        stale_items = [item for item in stale if item.get("track") == track_id]
        missing_items = [item for item in missing if item.get("track") == track_id]
        orphan_items = [item for item in orphan if item.get("track") == track_id]
        review_blockers: list[dict[str, str]] = []
        for item in stale_items:
            review_blockers.append(
                {
                    "code": "design_review_stale",
                    "path": DESIGN_REVIEWS_REL.as_posix(),
                    "message": (
                        f"{track_id} review for {item.get('acceptance_id', '<unknown>')} "
                        "is stale against current source or evidence"
                    ),
                }
            )
        for item in missing_items:
            review_blockers.append(
                {
                    "code": "design_review_missing",
                    "path": DESIGN_REVIEWS_REL.as_posix(),
                    "message": (
                        f"{track_id} review for {item.get('acceptance_id', '<unknown>')} "
                        "has not been recorded"
                    ),
                }
            )
        for item in orphan_items:
            review_blockers.append(
                {
                    "code": "design_review_orphan",
                    "path": DESIGN_REVIEWS_REL.as_posix(),
                    "message": (
                        f"{track_id} review for {item.get('acceptance_id', '<unknown>')} "
                        "no longer maps to current acceptance evidence"
                    ),
                }
            )
        blockers = _dict_items(track.get("blockers"))
        if review_blockers:
            blockers.extend(review_blockers)
            if track.get("status") == "ready_for_review":
                track["status"] = "review_required"
        track["blockers"] = blockers
        track["review_summary"] = {
            "active_count": len(active_items),
            "stale_count": len(stale_items),
            "missing_count": len(missing_items),
            "orphan_count": len(orphan_items),
        }
        updated.append(track)
    return updated


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
    skills = ["designing-api-contracts"]
    specialist_skills = _specialist_skills(API_TRACK_ID)
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": API_TRACK_ID,
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/architecture-methods.md",
            "references/api-design-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "candidates": candidates,
        "active_work": _active_api_candidate_work(root, candidates),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_architecture_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("architecture authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-system-architecture"]
    specialist_skills = _specialist_skills(ARCHITECTURE_TRACK_ID)
    authoring_tasks = [
        _architecture_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        ARCHITECTURE_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": ARCHITECTURE_TRACK_ID,
        "decision_policy": "do_not_guess_architecture_boundaries",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/architecture-methods.md",
            "references/architecture-quality-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "architecture-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_api_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("API authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-api-contracts"]
    specialist_skills = _specialist_skills(API_TRACK_ID)
    authoring_tasks = [
        _api_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        API_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": API_TRACK_ID,
        "decision_policy": "do_not_guess_contract_details",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/architecture-methods.md",
            "references/api-design-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "api-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_backend_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("backend authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-backend-modules"]
    specialist_skills = _specialist_skills(BACKEND_TRACK_ID)
    authoring_tasks = [
        _backend_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        BACKEND_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": BACKEND_TRACK_ID,
        "decision_policy": "do_not_guess_backend_boundaries",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/backend-design-checklist.md",
            "references/backend-operability-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "backend-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_data_model_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("data model authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-data-models"]
    specialist_skills = _specialist_skills(DATA_MODEL_TRACK_ID)
    authoring_tasks = [
        _data_model_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        DATA_MODEL_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": DATA_MODEL_TRACK_ID,
        "decision_policy": "do_not_guess_data_model",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/backend-design-checklist.md",
            "references/data-model-design-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "data-model-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_ui_interaction_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("UI interaction authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-ui-interactions"]
    specialist_skills = _specialist_skills(UI_INTERACTION_TRACK_ID)
    authoring_tasks = [
        _ui_interaction_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        UI_INTERACTION_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": UI_INTERACTION_TRACK_ID,
        "decision_policy": "do_not_guess_ui_behavior",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/frontend-interaction-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "ui-interaction-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_frontend_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("frontend authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-frontend-modules"]
    specialist_skills = _specialist_skills(FRONTEND_TRACK_ID)
    authoring_tasks = [
        _frontend_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        FRONTEND_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": FRONTEND_TRACK_ID,
        "decision_policy": "do_not_guess_frontend_behavior",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/frontend-interaction-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "frontend-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_test_strategy_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("test strategy authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    skills = ["designing-test-strategy"]
    specialist_skills = _specialist_skills(TEST_STRATEGY_TRACK_ID)
    authoring_tasks = [
        _test_strategy_authoring_task(root, candidate, index)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        TEST_STRATEGY_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": TEST_STRATEGY_TRACK_ID,
        "decision_policy": "do_not_guess_verification_scope",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/test-strategy-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "test-strategy-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_implementation_planning_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("implementation planning authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    start_task_prefix = _next_task_prefix(root)
    skills = ["planning-implementation-work"]
    specialist_skills = _specialist_skills(IMPLEMENTATION_PLANNING_TRACK_ID)
    authoring_tasks = [
        _implementation_planning_authoring_task(
            root,
            candidate,
            index,
            f"TASK-{start_task_prefix + index - 1:03d}",
        )
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        IMPLEMENTATION_PLANNING_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": IMPLEMENTATION_PLANNING_TRACK_ID,
        "decision_policy": "do_not_guess_task_scope",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/implementation-readiness-checklist.md",
            "references/implementation-execution-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_architecture_decisions_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_AUTHORING_PHASES:
        errors.append("architecture decisions authoring requires recorded phase design-derivation or implementation")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    next_adr_prefix = f"{_next_adr_prefix(root):03d}"
    skills = ["capturing-architecture-decisions"]
    specialist_skills = _specialist_skills(ARCHITECTURE_DECISIONS_TRACK_ID)
    authoring_tasks = [
        _architecture_decision_authoring_task(root, candidate, index, next_adr_prefix)
        for index, candidate in enumerate(candidates, start=1)
    ]
    authoring_tasks, review_state = _prepare_design_authoring_tasks(
        root,
        ARCHITECTURE_DECISIONS_TRACK_ID,
        authoring_tasks,
    )
    errors.extend(_string_items(review_state.get("errors")))
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": ARCHITECTURE_DECISIONS_TRACK_ID,
        "decision_policy": "do_not_guess_architecture_decisions",
        "skills": skills,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, skills, specialist_skills),
        "references": [
            "references/architecture-methods.md",
            "references/architecture-decision-record-checklist.md",
        ],
        "source_documents": _source_documents(root),
        **_design_review_payload_fields(review_state),
        "authoring_tasks": authoring_tasks,
        "authoring_summary": _authoring_summary(authoring_tasks),
        "active_work": _active_design_authoring_work(
            root,
            authoring_tasks,
            ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def _authoring_summary(tasks: list[dict[str, object]]) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    document_status_counts: dict[str, int] = {}
    non_authored_document_count = 0
    non_satisfied_count = 0
    open_decision_count = 0
    repair_action_count = 0
    for task in tasks:
        documents = task.get("documents")
        if isinstance(documents, list):
            for document in documents:
                if not isinstance(document, dict):
                    continue
                document_status = str(document.get("status", "unknown") or "unknown")
                document_status_counts[document_status] = document_status_counts.get(document_status, 0) + 1
                if document_status not in {"authored", "reference_template"}:
                    non_authored_document_count += 1
        open_decisions = task.get("open_decisions")
        if isinstance(open_decisions, list):
            open_decision_count += len(open_decisions)
        repair_actions = task.get("link_repair_actions")
        if isinstance(repair_actions, list):
            repair_action_count += len(repair_actions)
        required_links = task.get("required_links")
        if not isinstance(required_links, list):
            continue
        for link in required_links:
            if not isinstance(link, dict):
                continue
            status = str(link.get("status", "unknown") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            if status != "satisfied":
                non_satisfied_count += 1
    return {
        "task_count": len(tasks),
        "document_status_counts": dict(sorted(document_status_counts.items())),
        "non_authored_document_count": non_authored_document_count,
        "open_decision_count": open_decision_count,
        "required_link_status_counts": dict(sorted(status_counts.items())),
        "non_satisfied_required_link_count": non_satisfied_count,
        "link_repair_action_count": repair_action_count,
    }


def _prepare_design_authoring_tasks(
    root: Path,
    track: str,
    tasks: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    for task in tasks:
        document_blockers: list[dict[str, object]] = []
        document_repair_actions: list[dict[str, object]] = []
        documents = task.get("documents") if isinstance(task.get("documents"), list) else []
        for document in documents:
            if not isinstance(document, dict):
                continue
            path = str(document.get("path", ""))
            sections = [
                str(section)
                for section in document.get("sections", [])
                if isinstance(section, str) and section
            ] if isinstance(document.get("sections"), list) else []
            status, details = _design_document_status(root, path, sections)
            document["status"] = status
            if details:
                document["details"] = details
            if status in {"authored", "reference_template"}:
                continue
            blocker = {
                "kind": "design_document",
                "target": path,
                "status": status,
                "details": details,
            }
            document_blockers.append(blocker)
            document_repair_actions.append(
                {
                    "id": f"author-design-document-{_slugify(path)}",
                    "sequence": len(document_repair_actions) + 1,
                    "kind": "design-document-authoring",
                    "target": path,
                    "status": status,
                    "reason": details,
                    "repair_strategy": "author_declared_sections_from_source_and_authority_review",
                    "can_auto_apply": False,
                    "writes_state": True,
                    "approval_required": False,
                    "success_condition": "design document status becomes authored after verify and refresh",
                }
            )
        task["document_blockers"] = document_blockers
        task["document_repair_actions"] = document_repair_actions
    review_state = apply_design_reviews(root, track=track, tasks=tasks)
    return list(review_state.get("tasks", [])), review_state


def _design_review_payload_fields(review_state: dict[str, object]) -> dict[str, object]:
    return {
        "design_review_path": str(review_state.get("path", DESIGN_REVIEWS_REL.as_posix())),
        "design_reviews": list(review_state.get("active", []))
        if isinstance(review_state.get("active"), list)
        else [],
        "stale_design_reviews": list(review_state.get("stale", []))
        if isinstance(review_state.get("stale"), list)
        else [],
        "review_summary": dict(review_state.get("summary", {}))
        if isinstance(review_state.get("summary"), dict)
        else {},
    }


def _design_document_status(root: Path, rel: str, sections: list[str]) -> tuple[str, str]:
    path = root / rel
    if not rel:
        return "missing", "design document path is missing"
    if path.is_symlink():
        return "unsafe_path", "design document must not be a symbolic link"
    if not path.exists():
        return "missing", "design document does not exist"
    if not path.is_file():
        return "not_file", "design document path is not a file"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "unreadable", "design document must be UTF-8 Markdown"
    except OSError as error:
        return "unreadable", f"design document is unreadable: {_os_error_reason(error)}"
    if path.name.startswith("_"):
        return "reference_template", "underscore-prefixed template is reference-only"
    if SCAFFOLD_PLACEHOLDER in text:
        return "placeholder_present", "design document still contains a governance scaffold placeholder"
    if rel == API_OPENAPI_REL.as_posix():
        inventory = build_openapi_contract_inventory(root)
        if inventory.get("ok") is not True:
            errors = inventory.get("errors")
            details = "; ".join(
                str(error) for error in errors if isinstance(error, str) and error
            ) if isinstance(errors, list) else "OpenAPI contract is invalid"
            return "invalid_structured_document", details
        return "authored", "OpenAPI contract is valid JSON with a supported version, info, and endpoint paths"
    heading_names = {
        match.group("title").strip().casefold()
        for match in MARKDOWN_HEADING_RE.finditer(text)
    }
    missing_sections = [section for section in sections if section.casefold() not in heading_names]
    if missing_sections:
        return "missing_sections", f"missing required sections: {', '.join(missing_sections)}"
    return "authored", "design document exists with declared sections and no scaffold placeholder"


def _active_design_track_work(root: Path, tracks: list[dict[str, object]]) -> dict[str, object]:
    if not tracks:
        return {
            "kind": "design-track",
            "status": "ready",
            "blocker_count": 0,
            "open_decision_count": 0,
            "next_repair_action": {},
        }

    track = next((item for item in tracks if item.get("status") != "ready_for_review"), tracks[0])
    blockers = track.get("blockers") if isinstance(track.get("blockers"), list) else []
    steps = track.get("steps") if isinstance(track.get("steps"), list) else []
    verify_step = "verify-track"
    refresh_step = "refresh-design-plan"
    return {
        "kind": "design-track",
        "track_id": str(track.get("id", "")),
        "sequence": int(track.get("sequence", 0)) if isinstance(track.get("sequence"), int) else 0,
        "status": str(track.get("status", "unknown")),
        "title": str(track.get("title", "")),
        "primary_skill": str(track.get("primary_skill", "")),
        "primary_specialist_skill": str(track.get("primary_specialist_skill", "")),
        "documents": list(track.get("documents")) if isinstance(track.get("documents"), list) else [],
        "blocker_count": len(blockers),
        "open_decision_count": 0,
        "next_blocker": dict(blockers[0]) if blockers and isinstance(blockers[0], dict) else {},
        "next_repair_action": {},
        "verify_step": verify_step,
        "refresh_step": refresh_step,
        "stop_condition": "track_blockers_unresolved",
        "skill_loading_plan": track.get("skill_loading_plan", {}),
        "verify_command": _command_from_steps_or_default(
            root,
            steps,
            verify_step,
            "Run read-only governance verification after authoring this track.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        "refresh_command": _command_from_steps_or_default(
            root,
            steps,
            refresh_step,
            "Refresh the design track plan after active work changes.",
            ["bin/governance", "design", "plan", ".", "--json"],
        ),
    }


def _active_api_candidate_work(root: Path, candidates: list[dict[str, object]]) -> dict[str, object]:
    if not candidates:
        return {
            "kind": "api-candidate",
            "status": "ready",
            "blocker_count": 0,
            "open_decision_count": 0,
            "next_repair_action": {},
        }

    candidate = next(
        (item for item in candidates if isinstance(item.get("open_decisions"), list) and item["open_decisions"]),
        candidates[0],
    )
    open_decisions = candidate.get("open_decisions") if isinstance(candidate.get("open_decisions"), list) else []
    refresh_step = "refresh-api-candidates"
    return {
        "kind": "api-candidate",
        "candidate_id": str(candidate.get("candidate_id", "")),
        "sequence": int(str(candidate.get("candidate_id", "0")).rsplit("-", 1)[-1])
        if str(candidate.get("candidate_id", "")).rsplit("-", 1)[-1].isdigit()
        else 0,
        "status": "decision_required" if open_decisions else "ready",
        "acceptance_id": str(candidate.get("acceptance_id", "")),
        "title": str(candidate.get("title", "")),
        "source": candidate.get("source", {}),
        "suggested_endpoint_file": str(candidate.get("suggested_endpoint_file", "")),
        "replaceable_starter_endpoint": str(candidate.get("replaceable_starter_endpoint", "")),
        "primary_skill": "designing-api-contracts",
        "primary_specialist_skill": "api-design-reviewer",
        "blocker_count": len(open_decisions),
        "open_decision_count": len(open_decisions),
        "next_open_decision": str(open_decisions[0]) if open_decisions else "",
        "next_repair_action": {},
        "refresh_step": refresh_step,
        "stop_condition": "api_candidate_open_decisions_unresolved",
        "refresh_command": _embedded_command(
            root,
            refresh_step,
            "Refresh API candidates after product acceptance changes.",
            ["bin/governance", "design", "api-candidates", ".", "--json"],
        ),
    }


def _active_design_authoring_work(
    root: Path,
    tasks: list[dict[str, object]],
    refresh_argv: list[str],
) -> dict[str, object]:
    if not tasks:
        return {
            "kind": "design-authoring-task",
            "status": "ready",
            "blocker_count": 0,
            "open_decision_count": 0,
            "next_repair_action": {},
        }

    task = _first_design_authoring_task(tasks)
    if not task:
        return {
            "kind": "design-authoring-task",
            "status": "complete",
            "blocker_count": 0,
            "document_blocker_count": 0,
            "link_blocker_count": 0,
            "open_decision_count": 0,
            "next_repair_action": {},
        }
    links = task.get("required_links")
    document_blockers = task.get("document_blockers")
    open_decisions = task.get("open_decisions") if isinstance(task.get("open_decisions"), list) else []
    execution = task.get("execution") if isinstance(task.get("execution"), dict) else {}
    verify_step = str(execution.get("verify_step", "verify-design-authoring"))
    refresh_step = str(execution.get("refresh_step", "refresh-design-authoring"))
    document_blocker_count = _list_count(document_blockers)
    link_blocker_count = _non_satisfied_item_count(links)
    blocker_count = document_blocker_count + link_blocker_count
    return {
        "kind": "design-authoring-task",
        "task_id": str(task.get("task_id", "")),
        "sequence": int(task.get("sequence", 0)) if isinstance(task.get("sequence"), int) else 0,
        "status": _authoring_work_status(
            document_blocker_count,
            link_blocker_count,
            len(open_decisions),
        ),
        "acceptance_id": str(task.get("acceptance_id", "")),
        "title": str(task.get("title", "")),
        "documents": [
            str(document.get("path", ""))
            for document in task.get("documents", [])
            if isinstance(document, dict)
        ]
        if isinstance(task.get("documents"), list)
        else [],
        "primary_skill": str(execution.get("primary_skill", "")),
        "primary_specialist_skill": str(execution.get("primary_specialist_skill", "")),
        "verify_step": verify_step,
        "refresh_step": refresh_step,
        "stop_condition": str(execution.get("stop_condition", "")),
        "blocker_count": blocker_count,
        "document_blocker_count": document_blocker_count,
        "link_blocker_count": link_blocker_count,
        "open_decision_count": len(open_decisions),
        "next_document_blocker": _first_dict(document_blockers),
        "next_required_link": _first_non_satisfied_item(links),
        "next_open_decision": str(open_decisions[0]) if open_decisions else "",
        "next_repair_action": (
            _first_dict(task.get("document_repair_actions"))
            or _first_dict(task.get("link_repair_actions"))
        ),
        "review_status": str(task.get("review_status", "missing")),
        "required_authority_skill": str(execution.get("primary_specialist_skill", "")),
        "skill_loading_plan": task.get("skill_loading_plan", {}),
        "verify_command": _embedded_command(
            root,
            verify_step,
            "Run read-only governance verification after repairing design authoring links.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        "refresh_command": _embedded_command(
            root,
            refresh_step,
            "Refresh this design authoring queue after active work changes.",
            refresh_argv,
        ),
    }


def _authoring_work_status(
    document_blocker_count: int,
    link_blocker_count: int,
    open_decision_count: int,
) -> str:
    if document_blocker_count > 0:
        return "authoring_required"
    if link_blocker_count > 0:
        return "integration_required"
    if open_decision_count > 0:
        return "review_required"
    return "complete"


def _first_design_authoring_task(tasks: list[dict[str, object]]) -> dict[str, object]:
    for item_key in ("document_blockers", "required_links", "open_decisions"):
        for task in tasks:
            if item_key == "required_links":
                blocked = _non_satisfied_item_count(task.get(item_key)) > 0
            else:
                blocked = _list_count(task.get(item_key)) > 0
            if blocked:
                return task
    return {}


def _first_blocked_task(tasks: list[dict[str, object]], *, item_key: str) -> dict[str, object]:
    for task in tasks:
        if _non_satisfied_item_count(task.get(item_key)) > 0 or _list_count(task.get("open_decisions")) > 0:
            return task
    return tasks[0]


def _first_non_satisfied_item(items: object) -> dict[str, object]:
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and item.get("status") != "satisfied":
            return dict(item)
    return {}


def _first_dict(items: object) -> dict[str, object]:
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict):
            return dict(item)
    return {}


def _non_satisfied_item_count(items: object) -> int:
    if not isinstance(items, list):
        return 0
    return sum(1 for item in items if isinstance(item, dict) and item.get("status") != "satisfied")


def _list_count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _string_items(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def _dict_items(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _command_from_steps_or_default(
    root: Path,
    steps: list[object],
    step_id: str,
    description: str,
    argv: list[str],
) -> dict[str, object]:
    for step in steps:
        if isinstance(step, dict) and step.get("id") == step_id:
            return dict(step)
    return _embedded_command(root, step_id, description, argv)


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
    if (root / DESIGN_REVIEWS_REL).is_file():
        candidates.append(DESIGN_REVIEWS_REL.as_posix())
    return sorted(dict.fromkeys(candidates))


def _specialist_skills(track_id: str) -> list[str]:
    for track in DESIGN_TRACKS:
        if track.id == track_id:
            return list(track.specialist_skills)
    return []


def _skill_requirement_fields(
    root: Path,
    skills: list[str] | tuple[str, ...],
    specialist_skills: list[str] | tuple[str, ...],
) -> dict[str, object]:
    skill_requirements = _skill_requirements(root, skills, specialist_skills)
    authority_requirements = _authority_skill_requirements(specialist_skills)
    return {
        "skill_requirements": skill_requirements,
        "authority_skill_requirements": authority_requirements,
        "skill_loading_plan": _skill_loading_plan(skill_requirements),
    }


def _skill_requirements(
    root: Path,
    skills: list[str] | tuple[str, ...],
    specialist_skills: list[str] | tuple[str, ...],
) -> list[dict[str, object]]:
    requirements: list[dict[str, object]] = []
    seen: set[str] = set()
    for skill in skills:
        if skill in seen:
            continue
        seen.add(skill)
        requirements.append(_local_workflow_skill_requirement(root, skill))
    for skill in specialist_skills:
        if skill in seen:
            continue
        seen.add(skill)
        requirements.append(_authority_skill_requirement(skill))
    return requirements


def _authority_skill_requirements(
    specialist_skills: list[str] | tuple[str, ...],
) -> list[dict[str, object]]:
    requirements: list[dict[str, object]] = []
    seen: set[str] = set()
    for skill in specialist_skills:
        if skill in seen:
            continue
        seen.add(skill)
        requirements.append(_authority_skill_requirement(skill))
    return requirements


def _local_workflow_skill_requirement(root: Path, skill: str) -> dict[str, object]:
    path, available = _local_workflow_skill_path(root, skill)
    return {
        "name": skill,
        "type": "local-workflow",
        "required": True,
        "available_in_workflow_pack": available,
        "availability_scope": "workflow-pack",
        "path": path,
        "missing_policy": LOCAL_WORKFLOW_SKILL_MISSING_POLICY,
    }


def _authority_skill_requirement(skill: str) -> dict[str, object]:
    return {
        "name": skill,
        "type": "authority-routing"
        if skill in AUTHORITY_ROUTING_SPECIALIST_SKILLS
        else "specialist-routing",
        "required": True,
        "available_in_workflow_pack": False,
        "availability_scope": "agent-environment",
        "missing_policy": AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
    }


def _skill_loading_plan(requirements: list[dict[str, object]]) -> dict[str, object]:
    steps = [
        _skill_loading_step(sequence, requirement)
        for sequence, requirement in enumerate(requirements, start=1)
    ]
    local_steps = [
        step
        for step in steps
        if step.get("type") == "local-workflow"
    ]
    authority_steps = [
        step
        for step in steps
        if step.get("type") == "authority-routing"
    ]
    missing_local_steps = [
        step
        for step in local_steps
        if step.get("available_in_workflow_pack") is not True
    ]
    return {
        "load_order": "local_workflow_then_authority_routing",
        "stop_condition": "missing_required_local_workflow_skill_or_unavailable_authority_routing_skill",
        "local_workflow_all_available": not missing_local_steps,
        "authority_routing_requires_agent_environment": bool(authority_steps),
        "local_workflow_skill_count": len(local_steps),
        "authority_routing_skill_count": len(authority_steps),
        "missing_local_workflow_skills": [
            step["name"]
            for step in missing_local_steps
            if isinstance(step.get("name"), str)
        ],
        "steps": steps,
    }


def _skill_loading_step(sequence: int, requirement: dict[str, object]) -> dict[str, object]:
    kind = str(requirement.get("type", ""))
    return {
        "sequence": sequence,
        "name": str(requirement.get("name", "")),
        "type": kind,
        "required": requirement.get("required") is True,
        "action": _skill_loading_action(kind),
        "load_from": str(requirement.get("availability_scope", "")),
        "available_in_workflow_pack": requirement.get("available_in_workflow_pack") is True,
        "path": str(requirement.get("path", "")),
        "missing_policy": str(requirement.get("missing_policy", "")),
    }


def _skill_loading_action(kind: str) -> str:
    if kind == "local-workflow":
        return "load_local_workflow_skill"
    if kind == "authority-routing":
        return "load_authority_routing_skill"
    return "load_specialist_routing_skill"


def _local_workflow_skill_path(root: Path, skill: str) -> tuple[str, bool]:
    snapshot_rel = Path(TARGET_WORKFLOW_PACK_ROOT) / "skills" / skill / "SKILL.md"
    source_rel = Path("skills") / skill / "SKILL.md"
    for rel in (snapshot_rel, source_rel):
        if (root / rel).is_file():
            return rel.as_posix(), True
    return snapshot_rel.as_posix(), False


def _api_candidates(root: Path) -> list[dict[str, object]]:
    acceptance_headings = _acceptance_headings(root)
    existing_by_slug = _existing_endpoint_paths_by_slug(root)
    authored_starter = _authored_starter_endpoint(root)
    next_prefix = _next_endpoint_prefix(root)
    candidates: list[dict[str, object]] = []
    for index, item in enumerate(acceptance_headings, start=1):
        slug = _slugify(item["title"])
        suggested_endpoint_file = existing_by_slug.get(slug, "")
        if not suggested_endpoint_file and authored_starter:
            suggested_endpoint_file = authored_starter
        if not suggested_endpoint_file:
            suggested_endpoint_file = f"docs/api/endpoints/{next_prefix:02d}-{slug}.md"
            next_prefix += 1
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


def _existing_endpoint_paths_by_slug(root: Path) -> dict[str, str]:
    endpoint_root = root / "docs/api/endpoints"
    existing: dict[str, str] = {}
    if not endpoint_root.is_dir():
        return existing
    for path in sorted(endpoint_root.glob("[0-9][0-9]-*.md")):
        rel = path.relative_to(root).as_posix()
        if rel == STARTER_ENDPOINT_CONTRACT or not path.is_file():
            continue
        slug = path.stem[3:]
        if slug:
            existing.setdefault(slug, rel)
    return existing


def _authored_starter_endpoint(root: Path) -> str:
    path = root / STARTER_ENDPOINT_CONTRACT
    if not path.is_file() or path.is_symlink():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return STARTER_ENDPOINT_CONTRACT if SCAFFOLD_PLACEHOLDER not in text else ""


def _api_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    endpoint_file = str(candidate["suggested_endpoint_file"])
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    documents = [
        _authoring_document(
            "docs/api/00-conventions.md",
            API_CONVENTION_SECTIONS,
            "Fill shared API conventions before writing endpoint-specific contracts.",
        ),
        _authoring_document(
            "docs/api/error-codes.md",
            API_ERROR_CODE_SECTIONS,
            "Register reusable error taxonomy, retry behavior, and frontend handling.",
        ),
        _authoring_document(
            "docs/api/changelog.md",
            API_CHANGELOG_SECTIONS,
            "Record the initial compatibility baseline for the contract set.",
        ),
        _authoring_document(
            endpoint_file,
            API_ENDPOINT_SECTIONS,
            "Author the concrete endpoint contract only after every open decision has a source.",
        ),
        _authoring_document(
            API_OPENAPI_REL.as_posix(),
            (),
            "Encode the reviewed HTTP contract as OpenAPI 3.0.x or 3.1.x JSON for deterministic validation.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "error_registry", "docs/api/error-codes.md"),
        _required_link(root, "backend_owner", "docs/backend/01-modules.md"),
        _required_link(root, "frontend_consumers", "docs/frontend/02-api-consumption.md"),
        _required_link(root, "acceptance_matrix", "docs/tests/02-acceptance-matrix.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"API-AUTHOR-{index:03d}",
        "sequence": index,
        "candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "endpoint_file": endpoint_file,
        "endpoint_exists": candidate["endpoint_exists"],
        "replaceable_starter_endpoint": candidate["replaceable_starter_endpoint"],
        "specialist_skills": _specialist_skills(API_TRACK_ID),
        **_skill_requirement_fields(root, ["designing-api-contracts"], _specialist_skills(API_TRACK_ID)),
        "execution": _authoring_execution(
            "api-contract-authoring",
            "designing-api-contracts",
            "api-design-reviewer",
            "verify-api-authoring",
            "refresh-api-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-api-authoring",
            ["bin/governance", "design", "api-authoring", ".", "--json"],
        ),
        "open_decisions": list(candidate["open_decisions"]),
        "steps": _api_authoring_steps(root, source_reference, endpoint_file, documents, required_links),
    }


def _architecture_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    documents = [
        _authoring_document(
            "docs/architecture/01-system-context.md",
            ARCHITECTURE_SYSTEM_CONTEXT_SECTIONS,
            "Define system boundary, actors, external systems, trust boundaries, and unresolved architecture gaps.",
        ),
        _authoring_document(
            "docs/architecture/02-containers.md",
            ARCHITECTURE_CONTAINERS_SECTIONS,
            "Define containers, runtime responsibilities, data ownership, and unresolved container gaps.",
        ),
        _authoring_document(
            "docs/architecture/03-quality-attributes.md",
            ARCHITECTURE_QUALITY_SECTIONS,
            "Define measurable quality scenarios, tradeoffs, and implementation-readiness implications.",
        ),
    ]
    required_links = [
        _required_link(root, "product_prd", "docs/product/core/PRD.md"),
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "glossary", "docs/glossary.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"ARCHITECTURE-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "specialist_skills": _specialist_skills(ARCHITECTURE_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["designing-system-architecture"],
            _specialist_skills(ARCHITECTURE_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "architecture-design-authoring",
            "designing-system-architecture",
            "senior-architect",
            "verify-architecture-authoring",
            "refresh-architecture-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-architecture-authoring",
            ["bin/governance", "design", "architecture-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_ARCHITECTURE_DECISIONS),
        "steps": _architecture_authoring_steps(root, source_reference, required_links),
    }


def _authoring_document(path: str, sections: tuple[str, ...], purpose: str) -> dict[str, object]:
    return {
        "path": path,
        "sections": list(sections),
        "purpose": purpose,
    }


def _required_link(root: Path, kind: str, target: str) -> dict[str, object]:
    path = target.split("#", 1)[0]
    status, details = _required_link_status(root, target)
    payload: dict[str, object] = {
        "kind": kind,
        "target": target,
        "exists": bool(path) and (root / path).is_file(),
        "status": status,
    }
    if details:
        payload["details"] = details
    return payload


def _required_link_status(root: Path, target: str) -> tuple[str, str]:
    path_part, anchor = _split_markdown_reference(target)
    if not path_part:
        return "missing", "required link target has no file path"
    path = root / path_part
    if not path.exists():
        return "missing", f"{path_part} does not exist"
    if not path.is_file():
        return "missing", f"{path_part} is not a file"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "unreadable", f"{path_part} is not UTF-8 Markdown"
    except OSError as error:
        return "unreadable", f"{path_part} is unreadable: {error.strerror or str(error)}"
    if SCAFFOLD_PLACEHOLDER in text:
        return "placeholder_present", f"{path_part} still contains a governance scaffold placeholder"
    if anchor and not _markdown_anchor_exists(text, anchor):
        return "anchor_missing", f"{path_part} does not define anchor #{anchor}"
    return "satisfied", f"{target} resolves to a local Markdown source"


def _link_repair_actions(
    root: Path,
    required_links: list[dict[str, object]],
    refresh_step: str,
    refresh_argv: list[str],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for link in required_links:
        status = str(link.get("status", ""))
        if status == "satisfied":
            continue
        kind = str(link.get("kind", "required_link"))
        target = str(link.get("target", ""))
        actions.append(
            {
                "id": f"repair-required-link-{_slugify(kind)}",
                "sequence": len(actions) + 1,
                "kind": "required-link-repair",
                "link_kind": kind,
                "target": target,
                "status": status or "unknown",
                "reason": str(link.get("details", "")),
                "repair_strategy": _required_link_repair_strategy(status),
                "can_auto_apply": False,
                "writes_state": True,
                "approval_required": False,
                "success_condition": "required link status becomes satisfied after verify and refresh",
                "verify_command": _embedded_command(
                    root,
                    "verify-design-authoring-repair",
                    "Run read-only governance verification after repairing the linked source.",
                    ["bin/governance", "verify", ".", "--check", "--json"],
                ),
                "refresh_command": _embedded_command(
                    root,
                    refresh_step,
                    "Refresh this design authoring queue after repairing the linked source.",
                    refresh_argv,
                ),
            }
        )
    return actions


def _required_link_repair_strategy(status: str) -> str:
    strategies = {
        "missing": "create_or_restore_required_local_markdown_source_before_authoring_downstream_content",
        "anchor_missing": "add_or_correct_the_referenced_heading_anchor_without_changing_product_meaning",
        "placeholder_present": "replace_scaffold_placeholder_with_source_backed_content",
        "unreadable": "restore_target_as_utf8_markdown_file",
    }
    return strategies.get(status, "inspect_required_link_and_repair_before_continuing")


def _embedded_command(root: Path, command_id: str, description: str, argv: list[str]) -> dict[str, object]:
    return {
        "id": command_id,
        "cwd": str(root),
        "command": " ".join(argv),
        "argv": list(argv),
        "writes_state": False,
        "approval_required": False,
        "description": description,
    }


def _split_markdown_reference(target: str) -> tuple[str, str]:
    path_part, separator, anchor = target.partition("#")
    return path_part, anchor if separator else ""


def _markdown_anchor_exists(text: str, expected_anchor: str) -> bool:
    normalized_expected = expected_anchor.strip().casefold()
    if not normalized_expected:
        return True
    for match in MARKDOWN_HEADING_RE.finditer(text):
        if _markdown_anchor(match.group("title").strip()).casefold() == normalized_expected:
            return True
    return False


def _api_authoring_steps(
    root: Path,
    source_reference: str,
    endpoint_file: str,
    documents: list[dict[str, object]],
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-api-contract-skill",
            "kind": "skill-load",
            "skills": ["designing-api-contracts"],
            "specialist_skills": _specialist_skills(API_TRACK_ID),
            **_skill_requirement_fields(root, ["designing-api-contracts"], _specialist_skills(API_TRACK_ID)),
            "description": "Load the API contract skill before authoring shared conventions or endpoint files.",
        },
        {
            "id": "read-api-references",
            "kind": "read",
            "references": [
                "references/architecture-methods.md",
                "references/api-design-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read API, architecture, and security guidance before resolving contract decisions.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the acceptance criterion that created this endpoint candidate.",
        },
        {
            "id": "fill-shared-api-documents",
            "kind": "author",
            "documents": [
                document
                for document in documents
                if document["path"] not in {endpoint_file, API_OPENAPI_REL.as_posix()}
            ],
            "description": "Complete conventions, error registry, and changelog sections with source-backed content.",
        },
        {
            "id": "author-endpoint-contract",
            "kind": "author",
            "document": endpoint_file,
            "sections": list(API_ENDPOINT_SECTIONS),
            "description": "Write method/path, auth, idempotency, fields, errors, upstream links, and consumers only after sources are known.",
        },
        {
            "id": "author-openapi-contract",
            "kind": "author",
            "document": API_OPENAPI_REL.as_posix(),
            "format": "openapi-3-json",
            "description": "Encode the complete reviewed endpoint set as OpenAPI JSON without inventing behavior absent from Markdown and source evidence.",
        },
        {
            "id": "link-consumers-and-owners",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"backend_owner", "frontend_consumers", "unresolved_decisions"}
            ],
            "description": "Connect endpoint ownership and frontend consumption to existing design documents or unresolved decisions.",
        },
        {
            "id": "update-acceptance-matrix",
            "kind": "author",
            "documents": ["docs/tests/02-acceptance-matrix.md"],
            "description": "Map the acceptance criterion to the concrete endpoint contract and test source, or list it as uncovered.",
        },
        _command_step(
            root,
            "verify-api-authoring",
            "Run read-only governance verification after API contract authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-api-authoring",
            "Refresh the API authoring queue after verification.",
            ["bin/governance", "design", "api-authoring", ".", "--json"],
        ),
    ])


def _architecture_authoring_steps(
    root: Path,
    source_reference: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-architecture-design-skills",
            "kind": "skill-load",
            "skills": ["designing-system-architecture"],
            "specialist_skills": _specialist_skills(ARCHITECTURE_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["designing-system-architecture"],
                _specialist_skills(ARCHITECTURE_TRACK_ID),
            ),
            "description": "Load architecture and authority-routing skills before defining boundaries, containers, quality scenarios, or ADR candidates.",
        },
        {
            "id": "read-architecture-references",
            "kind": "read",
            "references": [
                "references/architecture-methods.md",
                "references/architecture-quality-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read architecture methods, quality coverage, and security guidance before resolving architecture decisions.",
        },
        {
            "id": "read-product-sources",
            "kind": "read",
            "documents": [
                "docs/product/core/PRD.md",
                source_reference,
                "docs/glossary.md",
                "docs/unresolved.md",
            ],
            "description": "Read product truth, acceptance criteria, glossary, and unresolved decisions before authoring architecture.",
        },
        {
            "id": "author-system-context",
            "kind": "author",
            "document": "docs/architecture/01-system-context.md",
            "sections": list(ARCHITECTURE_SYSTEM_CONTEXT_SECTIONS),
            "description": "Define actors, external systems, system boundary, trust boundaries, and open architecture gaps.",
        },
        {
            "id": "author-containers",
            "kind": "author",
            "document": "docs/architecture/02-containers.md",
            "sections": list(ARCHITECTURE_CONTAINERS_SECTIONS),
            "description": "Define containers, runtime responsibilities, data ownership, and unresolved container-level decisions.",
        },
        {
            "id": "author-quality-attributes",
            "kind": "author",
            "document": "docs/architecture/03-quality-attributes.md",
            "sections": list(ARCHITECTURE_QUALITY_SECTIONS),
            "description": "Define measurable availability, performance, security, observability, tradeoff, and verification expectations.",
        },
        {
            "id": "link-acceptance-and-decisions",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"product_acceptance", "unresolved_decisions"}
            ],
            "description": "Connect architecture claims to acceptance criteria and unresolved architecture decisions before downstream design.",
        },
        _command_step(
            root,
            "verify-architecture-authoring",
            "Run read-only governance verification after architecture authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-architecture-authoring",
            "Refresh the architecture authoring queue after verification.",
            ["bin/governance", "design", "architecture-authoring", ".", "--json"],
        ),
    ])


def _backend_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/backend/01-modules.md",
            BACKEND_MODULE_SECTIONS,
            "Define module boundaries, API ownership, runtime flow, failure modes, and open decisions.",
        ),
        _authoring_document(
            "docs/backend/03-external-services.md",
            BACKEND_EXTERNAL_SERVICE_SECTIONS,
            "Document dependencies, contracts, retries, timeouts, authentication, and observability expectations.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "architecture_context", "docs/architecture/01-system-context.md"),
        _required_link(root, "architecture_containers", "docs/architecture/02-containers.md"),
        _required_link(root, "api_contract", api_contract),
        _required_link(root, "data_model", "docs/backend/02-data-model.md"),
        _required_link(root, "external_services", "docs/backend/03-external-services.md"),
        _required_link(root, "test_strategy", "docs/tests/01-strategy.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"BACKEND-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "specialist_skills": _specialist_skills(BACKEND_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["designing-backend-modules"],
            _specialist_skills(BACKEND_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "backend-design-authoring",
            "designing-backend-modules",
            "senior-backend",
            "verify-backend-authoring",
            "refresh-backend-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-backend-authoring",
            ["bin/governance", "design", "backend-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_BACKEND_DECISIONS),
        "steps": _backend_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _backend_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-backend-design-skills",
            "kind": "skill-load",
            "skills": ["designing-backend-modules"],
            "specialist_skills": _specialist_skills(BACKEND_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["designing-backend-modules"],
                _specialist_skills(BACKEND_TRACK_ID),
            ),
            "description": "Load backend skills before assigning modules, runtime flows, operability, or external dependency responsibilities.",
        },
        {
            "id": "read-backend-references",
            "kind": "read",
            "references": [
                "references/backend-design-checklist.md",
                "references/backend-operability-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read backend, operability, and security checklists before resolving backend module decisions.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the product acceptance criterion that drives this backend design task.",
        },
        {
            "id": "read-architecture-and-api-sources",
            "kind": "read",
            "documents": [
                "docs/architecture/01-system-context.md",
                "docs/architecture/02-containers.md",
                api_contract,
            ],
            "description": "Read architecture and API contract sources before assigning backend ownership.",
        },
        {
            "id": "author-backend-modules",
            "kind": "author",
            "document": "docs/backend/01-modules.md",
            "sections": list(BACKEND_MODULE_SECTIONS),
            "description": "Define module boundaries, API ownership, runtime flow, failure modes, and unresolved backend gaps.",
        },
        {
            "id": "author-external-services",
            "kind": "author",
            "document": "docs/backend/03-external-services.md",
            "sections": list(BACKEND_EXTERNAL_SERVICE_SECTIONS),
            "description": "Document dependencies, contracts, retries, timeouts, authentication, observability, or explicitly state none.",
        },
        {
            "id": "link-tests-and-acceptance",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"product_acceptance", "test_strategy", "unresolved_decisions"}
            ],
            "description": "Connect backend decisions to acceptance criteria, test strategy, and unresolved items.",
        },
        _command_step(
            root,
            "verify-backend-authoring",
            "Run read-only governance verification after backend design authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-backend-authoring",
            "Refresh the backend authoring queue after verification.",
            ["bin/governance", "design", "backend-authoring", ".", "--json"],
        ),
    ])


def _data_model_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/backend/02-data-model.md",
            BACKEND_DATA_MODEL_SECTIONS,
            "Define entity ownership, lifecycle states, constraints, indexes, migration order, rollback, retention, and audit behavior.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "architecture_containers", "docs/architecture/02-containers.md"),
        _required_link(root, "backend_modules", "docs/backend/01-modules.md"),
        _required_link(root, "api_contract", api_contract),
        _required_link(root, "test_strategy", "docs/tests/01-strategy.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"DATA-MODEL-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "specialist_skills": _specialist_skills(DATA_MODEL_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["designing-data-models"],
            _specialist_skills(DATA_MODEL_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "data-model-authoring",
            "designing-data-models",
            "database-designer",
            "verify-data-model-authoring",
            "refresh-data-model-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-data-model-authoring",
            ["bin/governance", "design", "data-model-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_DATA_MODEL_DECISIONS),
        "steps": _data_model_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _data_model_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-data-model-design-skills",
            "kind": "skill-load",
            "skills": ["designing-data-models"],
            "specialist_skills": _specialist_skills(DATA_MODEL_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["designing-data-models"],
                _specialist_skills(DATA_MODEL_TRACK_ID),
            ),
            "description": "Load data-model and authority-routing database skills before naming entities, constraints, indexes, migrations, or rollback paths.",
        },
        {
            "id": "read-data-model-references",
            "kind": "read",
            "references": [
                "references/backend-design-checklist.md",
                "references/data-model-design-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read backend, data-model, and security checklists before resolving persistence decisions.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the product acceptance criterion that drives this persistence design task.",
        },
        {
            "id": "read-backend-and-api-sources",
            "kind": "read",
            "documents": [
                "docs/architecture/02-containers.md",
                "docs/backend/01-modules.md",
                api_contract,
            ],
            "description": "Read architecture, backend ownership, and API contract sources before defining persistence behavior.",
        },
        {
            "id": "author-data-model",
            "kind": "author",
            "document": "docs/backend/02-data-model.md",
            "sections": list(BACKEND_DATA_MODEL_SECTIONS),
            "description": "Define ownership, entities, state machines, constraints, indexes, migrations, rollback, retention, and audit decisions.",
        },
        {
            "id": "link-tests-and-acceptance",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"product_acceptance", "test_strategy", "unresolved_decisions"}
            ],
            "description": "Connect persistence decisions to acceptance criteria, verification strategy, and unresolved items.",
        },
        _command_step(
            root,
            "verify-data-model-authoring",
            "Run read-only governance verification after data-model authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-data-model-authoring",
            "Refresh the data-model authoring queue after verification.",
            ["bin/governance", "design", "data-model-authoring", ".", "--json"],
        ),
    ])


def _frontend_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/frontend/01-modules.md",
            FRONTEND_MODULE_SECTIONS,
            "Define frontend module boundaries, route ownership, state ownership, and open decisions.",
        ),
        _authoring_document(
            "docs/frontend/02-api-consumption.md",
            FRONTEND_API_CONSUMPTION_SECTIONS,
            "Map API contracts to frontend loading, retry, stale, success, and error handling behavior.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "ui_interaction", "docs/ui/01-interaction-model.md"),
        _required_link(root, "api_contract", api_contract),
        _required_link(root, "api_error_registry", "docs/api/error-codes.md"),
        _required_link(root, "frontend_modules", "docs/frontend/01-modules.md"),
        _required_link(root, "test_strategy", "docs/tests/01-strategy.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"FRONTEND-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "specialist_skills": _specialist_skills(FRONTEND_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["designing-frontend-modules"],
            _specialist_skills(FRONTEND_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "frontend-design-authoring",
            "designing-frontend-modules",
            "senior-frontend",
            "verify-frontend-authoring",
            "refresh-frontend-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-frontend-authoring",
            ["bin/governance", "design", "frontend-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_FRONTEND_DECISIONS),
        "steps": _frontend_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _frontend_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-frontend-design-skills",
            "kind": "skill-load",
            "skills": ["designing-frontend-modules"],
            "specialist_skills": _specialist_skills(FRONTEND_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["designing-frontend-modules"],
                _specialist_skills(FRONTEND_TRACK_ID),
            ),
            "description": "Load frontend module skills before assigning routes, state ownership, or API consumption.",
        },
        {
            "id": "read-frontend-references",
            "kind": "read",
            "references": [
                "references/frontend-interaction-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read frontend interaction and security guidance before resolving user-visible behavior.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the product acceptance criterion that drives this frontend design task.",
        },
        {
            "id": "read-ui-and-api-sources",
            "kind": "read",
            "documents": [
                "docs/ui/01-interaction-model.md",
                api_contract,
                "docs/api/error-codes.md",
            ],
            "description": "Read UI and API sources before assigning frontend state, routes, loading, and errors.",
        },
        {
            "id": "author-frontend-modules",
            "kind": "author",
            "document": "docs/frontend/01-modules.md",
            "sections": list(FRONTEND_MODULE_SECTIONS),
            "description": "Define frontend modules, state ownership, route ownership, and unresolved frontend gaps.",
        },
        {
            "id": "author-api-consumption",
            "kind": "author",
            "document": "docs/frontend/02-api-consumption.md",
            "sections": list(FRONTEND_API_CONSUMPTION_SECTIONS),
            "description": "Map API links to loading states, stale states, retries, success handling, and user-visible error actions.",
        },
        {
            "id": "link-tests-and-acceptance",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"product_acceptance", "test_strategy", "unresolved_decisions"}
            ],
            "description": "Connect frontend behavior to acceptance criteria, test strategy, and unresolved items.",
        },
        _command_step(
            root,
            "verify-frontend-authoring",
            "Run read-only governance verification after frontend design authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-frontend-authoring",
            "Refresh the frontend authoring queue after verification.",
            ["bin/governance", "design", "frontend-authoring", ".", "--json"],
        ),
    ])


def _ui_interaction_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    documents = [
        _authoring_document(
            "docs/ui/01-interaction-model.md",
            UI_INTERACTION_SECTIONS,
            "Define product-derived flows, screens, states, user-visible errors, accessibility expectations, and copy gaps.",
        ),
    ]
    required_links = [
        _required_link(root, "product_prd", "docs/product/core/PRD.md"),
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "glossary", "docs/glossary.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"UI-INTERACTION-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "specialist_skills": _specialist_skills(UI_INTERACTION_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["designing-ui-interactions"],
            _specialist_skills(UI_INTERACTION_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "ui-interaction-authoring",
            "designing-ui-interactions",
            "senior-frontend",
            "verify-ui-interaction-authoring",
            "refresh-ui-interaction-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-ui-interaction-authoring",
            ["bin/governance", "design", "ui-interaction-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_UI_INTERACTION_DECISIONS),
        "steps": _ui_interaction_authoring_steps(root, source_reference, required_links),
    }


def _ui_interaction_authoring_steps(
    root: Path,
    source_reference: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-ui-interaction-design-skills",
            "kind": "skill-load",
            "skills": ["designing-ui-interactions"],
            "specialist_skills": _specialist_skills(UI_INTERACTION_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["designing-ui-interactions"],
                _specialist_skills(UI_INTERACTION_TRACK_ID),
            ),
            "description": "Load UI interaction and accessibility authority-routing skills before defining visible behavior.",
        },
        {
            "id": "read-ui-interaction-references",
            "kind": "read",
            "references": [
                "references/frontend-interaction-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read interaction, accessibility, and security guidance before resolving user-visible behavior.",
        },
        {
            "id": "read-product-sources",
            "kind": "read",
            "documents": [
                "docs/product/core/PRD.md",
                source_reference,
                "docs/glossary.md",
                "docs/unresolved.md",
            ],
            "description": "Read product truth, acceptance criteria, glossary, and unresolved decisions before authoring UI interaction behavior.",
        },
        {
            "id": "author-ui-interaction-model",
            "kind": "author",
            "document": "docs/ui/01-interaction-model.md",
            "sections": list(UI_INTERACTION_SECTIONS),
            "description": "Define product-derived flows, screens, states, user-visible errors, accessibility expectations, and unresolved copy gaps.",
        },
        {
            "id": "link-acceptance-and-decisions",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"product_acceptance", "unresolved_decisions"}
            ],
            "description": "Connect UI behavior to acceptance criteria and unresolved interaction or accessibility decisions.",
        },
        _command_step(
            root,
            "verify-ui-interaction-authoring",
            "Run read-only governance verification after UI interaction authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-ui-interaction-authoring",
            "Refresh the UI interaction authoring queue after verification.",
            ["bin/governance", "design", "ui-interaction-authoring", ".", "--json"],
        ),
    ])


def _test_strategy_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/tests/01-strategy.md",
            TEST_STRATEGY_SECTIONS,
            "Define test layers, risk coverage, non-functional checks, commands, test data, and evidence targets.",
        ),
        _authoring_document(
            "docs/tests/02-acceptance-matrix.md",
            ACCEPTANCE_MATRIX_SECTIONS,
            "Map product-defined acceptance criteria to design, API, and test evidence or list uncovered criteria.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "api_contract", api_contract),
        _required_link(root, "architecture_quality", "docs/architecture/03-quality-attributes.md"),
        _required_link(root, "backend_modules", "docs/backend/01-modules.md"),
        _required_link(root, "frontend_modules", "docs/frontend/01-modules.md"),
        _required_link(root, "ui_interaction", "docs/ui/01-interaction-model.md"),
        _required_link(root, "verification_log", "docs/development/03-verification-log.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"TEST-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "specialist_skills": _specialist_skills(TEST_STRATEGY_TRACK_ID),
        **_skill_requirement_fields(root, ["designing-test-strategy"], _specialist_skills(TEST_STRATEGY_TRACK_ID)),
        "execution": _authoring_execution(
            "test-strategy-authoring",
            "designing-test-strategy",
            "senior-qa",
            "verify-test-strategy-authoring",
            "refresh-test-strategy-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-test-strategy-authoring",
            ["bin/governance", "design", "test-strategy-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_TEST_STRATEGY_DECISIONS),
        "steps": _test_strategy_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _test_strategy_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-test-strategy-skill",
            "kind": "skill-load",
            "skills": ["designing-test-strategy"],
            "specialist_skills": _specialist_skills(TEST_STRATEGY_TRACK_ID),
            **_skill_requirement_fields(root, ["designing-test-strategy"], _specialist_skills(TEST_STRATEGY_TRACK_ID)),
            "description": "Load the test strategy skill before assigning verification layers, commands, or evidence targets.",
        },
        {
            "id": "read-test-references",
            "kind": "read",
            "references": [
                "references/test-strategy-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read test strategy and security guidance before resolving verification scope.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the product acceptance criterion that drives this verification task.",
        },
        {
            "id": "read-design-risk-sources",
            "kind": "read",
            "documents": [
                api_contract,
                "docs/architecture/03-quality-attributes.md",
                "docs/backend/01-modules.md",
                "docs/frontend/01-modules.md",
                "docs/ui/01-interaction-model.md",
            ],
            "description": "Read design and implementation-risk sources before assigning test layers or matrix coverage.",
        },
        {
            "id": "author-test-strategy",
            "kind": "author",
            "document": "docs/tests/01-strategy.md",
            "sections": list(TEST_STRATEGY_SECTIONS),
            "description": "Define acceptance traceability, test layers, risk coverage, non-functional checks, commands, data, and evidence targets.",
        },
        {
            "id": "author-acceptance-matrix",
            "kind": "author",
            "document": "docs/tests/02-acceptance-matrix.md",
            "sections": list(ACCEPTANCE_MATRIX_SECTIONS),
            "description": "Map each product-defined acceptance ID to design, API, and test evidence, or list it under uncovered criteria.",
        },
        {
            "id": "link-evidence-and-readiness",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"] in {"product_acceptance", "verification_log", "unresolved_decisions"}
            ],
            "description": "Connect verification scope to acceptance criteria, evidence logs, and unresolved coverage gaps.",
        },
        _command_step(
            root,
            "verify-test-strategy-authoring",
            "Run read-only governance verification after test strategy authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-test-strategy-authoring",
            "Refresh the test strategy authoring queue after verification.",
            ["bin/governance", "design", "test-strategy-authoring", ".", "--json"],
        ),
    ])


def _implementation_planning_authoring_task(
    root: Path,
    candidate: dict[str, object],
    index: int,
    suggested_task_id: str,
) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/development/01-roadmap.md",
            ROADMAP_SECTIONS,
            "Define product-linked milestones, sequencing, risks, and explicitly deferred scope.",
        ),
        _authoring_document(
            "docs/development/02-task-board.md",
            TASK_BOARD_SECTIONS,
            "Create traceable TASK-NNN rows only when Product, Design, API, Acceptance, and Verification sources exist.",
        ),
        _authoring_document(
            "docs/development/03-verification-log.md",
            VERIFICATION_LOG_SECTIONS,
            "Initialize the stable local Markdown evidence target for Done task verification.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "architecture_context", "docs/architecture/01-system-context.md"),
        _required_link(root, "architecture_quality", "docs/architecture/03-quality-attributes.md"),
        _required_link(root, "ui_interaction", "docs/ui/01-interaction-model.md"),
        _required_link(root, "api_contract", api_contract),
        _required_link(root, "backend_modules", "docs/backend/01-modules.md"),
        _required_link(root, "frontend_modules", "docs/frontend/01-modules.md"),
        _required_link(root, "test_strategy", "docs/tests/01-strategy.md"),
        _required_link(root, "acceptance_matrix", "docs/tests/02-acceptance-matrix.md"),
        _required_link(root, "roadmap", "docs/development/01-roadmap.md"),
        _required_link(root, "task_board", "docs/development/02-task-board.md"),
        _required_link(root, "verification_log", "docs/development/03-verification-log.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"PLAN-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "suggested_task_id": suggested_task_id,
        "source": source,
        "specialist_skills": _specialist_skills(IMPLEMENTATION_PLANNING_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["planning-implementation-work"],
            _specialist_skills(IMPLEMENTATION_PLANNING_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "implementation-planning-authoring",
            "planning-implementation-work",
            "senior-fullstack",
            "verify-implementation-planning-authoring",
            "refresh-implementation-planning-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-implementation-planning-authoring",
            ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_IMPLEMENTATION_PLANNING_DECISIONS),
        "steps": _implementation_planning_authoring_steps(
            root,
            source_reference,
            api_contract,
            required_links,
        ),
    }


def _implementation_planning_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-implementation-planning-skill",
            "kind": "skill-load",
            "skills": ["planning-implementation-work"],
            "specialist_skills": _specialist_skills(IMPLEMENTATION_PLANNING_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["planning-implementation-work"],
                _specialist_skills(IMPLEMENTATION_PLANNING_TRACK_ID),
            ),
            "description": "Load the implementation planning skill before assigning TASK-NNN scope, status, readiness, or evidence targets.",
        },
        {
            "id": "read-implementation-references",
            "kind": "read",
            "references": [
                "references/implementation-readiness-checklist.md",
                "references/implementation-execution-checklist.md",
            ],
            "description": "Read readiness and execution guidance before resolving task scope or Ready/Done contracts.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the product acceptance criterion that drives this implementation planning task.",
        },
        {
            "id": "read-design-and-test-sources",
            "kind": "read",
            "documents": [
                "docs/architecture/01-system-context.md",
                "docs/architecture/03-quality-attributes.md",
                "docs/ui/01-interaction-model.md",
                api_contract,
                "docs/backend/01-modules.md",
                "docs/frontend/01-modules.md",
                "docs/tests/01-strategy.md",
                "docs/tests/02-acceptance-matrix.md",
            ],
            "description": "Read design, API, and verification sources before deciding task boundaries, dependencies, or readiness.",
        },
        {
            "id": "author-roadmap",
            "kind": "author",
            "document": "docs/development/01-roadmap.md",
            "sections": list(ROADMAP_SECTIONS),
            "description": "Create milestone rows with TASK-NNN IDs, sequencing, risks, and deferred scope backed by product and design sources.",
        },
        {
            "id": "author-task-board",
            "kind": "author",
            "document": "docs/development/02-task-board.md",
            "sections": list(TASK_BOARD_SECTIONS),
            "description": "Create task rows with Product, Design, API, Acceptance, and Verification links; mark Ready only when every gate input exists.",
        },
        {
            "id": "initialize-verification-log",
            "kind": "author",
            "document": "docs/development/03-verification-log.md",
            "sections": list(VERIFICATION_LOG_SECTIONS),
            "description": "Initialize the local Markdown evidence target for completed task verification without claiming Done evidence.",
        },
        {
            "id": "link-ready-contract",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"]
                in {
                    "product_acceptance",
                    "api_contract",
                    "test_strategy",
                    "acceptance_matrix",
                    "verification_log",
                    "unresolved_decisions",
                }
            ],
            "description": "Connect each planned task to acceptance, API, test, evidence, and unresolved-decision sources before marking it Ready.",
        },
        _command_step(
            root,
            "verify-implementation-planning-authoring",
            "Run read-only governance verification after implementation planning authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-implementation-planning-authoring",
            "Refresh the implementation planning authoring queue after verification.",
            ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
        ),
    ])


def _architecture_decision_authoring_task(
    root: Path,
    candidate: dict[str, object],
    index: int,
    next_adr_prefix: str,
) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/decisions/_template.md",
            ADR_SECTIONS,
            "Use the ADR template only when the decision trigger is source-backed; otherwise record a deferral or no-ADR reason.",
        ),
    ]
    required_links = [
        _required_link(root, "product_acceptance", source_reference),
        _required_link(root, "architecture_context", "docs/architecture/01-system-context.md"),
        _required_link(root, "architecture_containers", "docs/architecture/02-containers.md"),
        _required_link(root, "architecture_quality", "docs/architecture/03-quality-attributes.md"),
        _required_link(root, "api_contract", api_contract),
        _required_link(root, "backend_modules", "docs/backend/01-modules.md"),
        _required_link(root, "data_model", "docs/backend/02-data-model.md"),
        _required_link(root, "frontend_modules", "docs/frontend/01-modules.md"),
        _required_link(root, "test_strategy", "docs/tests/01-strategy.md"),
        _required_link(root, "task_board", "docs/development/02-task-board.md"),
        _required_link(root, "unresolved_decisions", "docs/unresolved.md"),
    ]
    return {
        "task_id": f"ADR-AUTHOR-{index:03d}",
        "sequence": index,
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "requires_adr": "undetermined",
        "next_adr_prefix": next_adr_prefix,
        "source": source,
        "specialist_skills": _specialist_skills(ARCHITECTURE_DECISIONS_TRACK_ID),
        **_skill_requirement_fields(
            root,
            ["capturing-architecture-decisions"],
            _specialist_skills(ARCHITECTURE_DECISIONS_TRACK_ID),
        ),
        "execution": _authoring_execution(
            "architecture-decision-authoring",
            "capturing-architecture-decisions",
            "senior-architect",
            "verify-architecture-decisions-authoring",
            "refresh-architecture-decisions-authoring",
        ),
        "documents": documents,
        "required_links": required_links,
        "link_repair_actions": _link_repair_actions(
            root,
            required_links,
            "refresh-architecture-decisions-authoring",
            ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
        ),
        "open_decisions": list(OPEN_ARCHITECTURE_DECISION_DECISIONS),
        "steps": _architecture_decision_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _architecture_decision_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return _sequence_steps([
        {
            "id": "load-adr-skill",
            "kind": "skill-load",
            "skills": ["capturing-architecture-decisions"],
            "specialist_skills": _specialist_skills(ARCHITECTURE_DECISIONS_TRACK_ID),
            **_skill_requirement_fields(
                root,
                ["capturing-architecture-decisions"],
                _specialist_skills(ARCHITECTURE_DECISIONS_TRACK_ID),
            ),
            "description": "Load the ADR skill before deciding whether a source-backed architecture decision record is required.",
        },
        {
            "id": "read-adr-references",
            "kind": "read",
            "references": [
                "references/architecture-methods.md",
                "references/architecture-decision-record-checklist.md",
            ],
            "description": "Read ADR method and checklist guidance before evaluating trigger, options, consequences, or lifecycle.",
        },
        {
            "id": "read-source-acceptance",
            "kind": "read",
            "documents": [source_reference],
            "description": "Read the product acceptance criterion that may drive an architecture decision.",
        },
        {
            "id": "read-design-decision-sources",
            "kind": "read",
            "documents": [
                "docs/architecture/01-system-context.md",
                "docs/architecture/02-containers.md",
                "docs/architecture/03-quality-attributes.md",
                api_contract,
                "docs/backend/01-modules.md",
                "docs/backend/02-data-model.md",
                "docs/frontend/01-modules.md",
                "docs/tests/01-strategy.md",
            ],
            "description": "Read design sources before judging whether a decision is cross-module, costly, reversible-later, or alternative-rich.",
        },
        {
            "id": "evaluate-adr-trigger",
            "kind": "review",
            "open_decisions": [
                "adr_trigger",
                "decision_scope",
                "decision_drivers",
                "affected_modules",
                "deferred_or_no_adr_reason",
            ],
            "description": "Decide from sources whether an ADR is required, should be deferred, or should be omitted as a local design note.",
        },
        {
            "id": "author-adr-if-triggered",
            "kind": "author",
            "template": "docs/decisions/_template.md",
            "sections": list(ADR_SECTIONS),
            "description": "Create a numbered NNN-<slug>.md ADR only after trigger, options, decision, consequences, status, and references are source-backed.",
        },
        {
            "id": "link-decision-references",
            "kind": "link",
            "required_links": [
                link
                for link in required_links
                if link["kind"]
                in {
                    "product_acceptance",
                    "architecture_context",
                    "architecture_quality",
                    "api_contract",
                    "backend_modules",
                    "frontend_modules",
                    "unresolved_decisions",
                }
            ],
            "description": "Connect ADR references and reverse links to existing local Markdown sources, or register blockers.",
        },
        _command_step(
            root,
            "verify-architecture-decisions-authoring",
            "Run read-only governance verification after ADR authoring.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        _command_step(
            root,
            "refresh-architecture-decisions-authoring",
            "Refresh the architecture decisions authoring queue after verification.",
            ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
        ),
    ])


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


def _next_task_prefix(root: Path) -> int:
    prefixes: list[int] = []
    for rel in ("docs/development/01-roadmap.md", "docs/development/02-task-board.md"):
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        prefixes.extend(int(match.group("num")) for match in TASK_ID_RE.finditer(text))
    return max(prefixes, default=0) + 1


def _next_adr_prefix(root: Path) -> int:
    decisions_root = root / "docs/decisions"
    prefixes: list[int] = []
    if decisions_root.is_dir():
        for path in decisions_root.glob("[0-9][0-9][0-9]-*.md"):
            match = ADR_ID_RE.fullmatch(path.name)
            if match:
                prefixes.append(int(match.group("num")))
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
    sequence: int,
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
        "sequence": sequence,
        "title": track.title,
        "purpose": track.purpose,
        "status": _track_status(document_status, blockers),
        "skills": list(track.skills),
        "specialist_skills": list(track.specialist_skills),
        **_skill_requirement_fields(root, track.skills, track.specialist_skills),
        "primary_skill": track.skills[0] if track.skills else "",
        "primary_specialist_skill": track.specialist_skills[0] if track.specialist_skills else "",
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
    return _sequence_steps([
        {
            "id": "load-track-skills",
            "kind": "skill-load",
            "skills": list(track.skills),
            "specialist_skills": list(track.specialist_skills),
            **_skill_requirement_fields(root, track.skills, track.specialist_skills),
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
    ])


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


def _sequence_steps(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "sequence": index,
            **step,
        }
        for index, step in enumerate(steps, start=1)
    ]


def _authoring_execution(
    stage: str,
    primary_skill: str,
    primary_specialist_skill: str,
    verify_step: str,
    refresh_step: str,
) -> dict[str, str]:
    return {
        "stage": stage,
        "primary_skill": primary_skill,
        "primary_specialist_skill": primary_specialist_skill,
        "verify_step": verify_step,
        "refresh_step": refresh_step,
        "stop_condition": "open_decisions_unresolved_or_required_links_missing",
    }


def _track_status(document_status: list[dict[str, Any]], blockers: list[dict[str, str]]) -> str:
    if blockers:
        return "authoring_blocked"
    if any(not item["exists"] for item in document_status):
        return "missing_documents"
    return "ready_for_review"
