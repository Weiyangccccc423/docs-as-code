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
BACKEND_TRACK_ID = "backend-modules"
FRONTEND_TRACK_ID = "frontend-modules"
TEST_STRATEGY_TRACK_ID = "test-strategy"
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
OPEN_BACKEND_DECISIONS = (
    "module_boundaries",
    "runtime_flow",
    "api_ownership",
    "data_ownership",
    "entities",
    "state_machines",
    "transaction_boundaries",
    "consistency_model",
    "external_dependencies",
    "retries_timeouts",
    "observability",
    "security_boundaries",
    "acceptance_tests",
)
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
OPEN_FRONTEND_DECISIONS = (
    "primary_flows",
    "screens",
    "route_ownership",
    "state_ownership",
    "api_consumption",
    "loading_states",
    "error_actions",
    "accessibility",
    "performance",
    "copy_and_content",
    "cache_invalidation",
)
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
OPEN_TEST_STRATEGY_DECISIONS = (
    "acceptance_coverage",
    "test_layers",
    "contract_tests",
    "end_to_end_flows",
    "accessibility_checks",
    "security_checks",
    "non_functional_checks",
    "test_data",
    "environment_assumptions",
    "local_verification_commands",
    "evidence_targets",
    "uncovered_criteria",
)
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


def build_api_authoring(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase != DESIGN_PHASE:
        errors.append(f"API authoring requires recorded phase {DESIGN_PHASE}")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": API_TRACK_ID,
        "decision_policy": "do_not_guess_contract_details",
        "skills": ["designing-api-contracts"],
        "references": [
            "references/architecture-methods.md",
            "references/api-design-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "authoring_tasks": [
            _api_authoring_task(root, candidate, index)
            for index, candidate in enumerate(candidates, start=1)
        ],
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
    elif phase != DESIGN_PHASE:
        errors.append(f"backend authoring requires recorded phase {DESIGN_PHASE}")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": BACKEND_TRACK_ID,
        "decision_policy": "do_not_guess_backend_boundaries",
        "skills": ["designing-backend-modules", "designing-data-models"],
        "references": [
            "references/backend-design-checklist.md",
            "references/data-model-design-checklist.md",
            "references/backend-operability-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "authoring_tasks": [
            _backend_authoring_task(root, candidate, index)
            for index, candidate in enumerate(candidates, start=1)
        ],
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
    elif phase != DESIGN_PHASE:
        errors.append(f"frontend authoring requires recorded phase {DESIGN_PHASE}")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": FRONTEND_TRACK_ID,
        "decision_policy": "do_not_guess_frontend_behavior",
        "skills": ["designing-ui-interactions", "designing-frontend-modules"],
        "references": [
            "references/frontend-interaction-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "authoring_tasks": [
            _frontend_authoring_task(root, candidate, index)
            for index, candidate in enumerate(candidates, start=1)
        ],
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
    elif phase != DESIGN_PHASE:
        errors.append(f"test strategy authoring requires recorded phase {DESIGN_PHASE}")
    candidates = _api_candidates(root)
    if not candidates:
        errors.append("No product acceptance criteria with A-NNN headings found.")
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": DESIGN_WORKFLOW_PATH,
        "track": TEST_STRATEGY_TRACK_ID,
        "decision_policy": "do_not_guess_verification_scope",
        "skills": ["designing-test-strategy"],
        "references": [
            "references/test-strategy-checklist.md",
            "references/security-design-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "authoring_tasks": [
            _test_strategy_authoring_task(root, candidate, index)
            for index, candidate in enumerate(candidates, start=1)
        ],
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
        "candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "endpoint_file": endpoint_file,
        "endpoint_exists": candidate["endpoint_exists"],
        "replaceable_starter_endpoint": candidate["replaceable_starter_endpoint"],
        "documents": documents,
        "required_links": required_links,
        "open_decisions": list(candidate["open_decisions"]),
        "steps": _api_authoring_steps(root, source_reference, endpoint_file, documents, required_links),
    }


def _authoring_document(path: str, sections: tuple[str, ...], purpose: str) -> dict[str, object]:
    return {
        "path": path,
        "sections": list(sections),
        "purpose": purpose,
    }


def _required_link(root: Path, kind: str, target: str) -> dict[str, object]:
    path = target.split("#", 1)[0]
    return {
        "kind": kind,
        "target": target,
        "exists": bool(path) and (root / path).is_file(),
    }


def _api_authoring_steps(
    root: Path,
    source_reference: str,
    endpoint_file: str,
    documents: list[dict[str, object]],
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "id": "load-api-contract-skill",
            "kind": "skill-load",
            "skills": ["designing-api-contracts"],
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
            "documents": [document for document in documents if document["path"] != endpoint_file],
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
    ]


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
            "docs/backend/02-data-model.md",
            BACKEND_DATA_MODEL_SECTIONS,
            "Define data ownership, entities, lifecycle states, constraints, indexes, and migration order.",
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
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "documents": documents,
        "required_links": required_links,
        "open_decisions": list(OPEN_BACKEND_DECISIONS),
        "steps": _backend_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _backend_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "id": "load-backend-design-skills",
            "kind": "skill-load",
            "skills": ["designing-backend-modules", "designing-data-models"],
            "description": "Load backend and data-model skills before assigning modules, persistence, or operability responsibilities.",
        },
        {
            "id": "read-backend-references",
            "kind": "read",
            "references": [
                "references/backend-design-checklist.md",
                "references/data-model-design-checklist.md",
                "references/backend-operability-checklist.md",
                "references/security-design-checklist.md",
            ],
            "description": "Read backend, data-model, operability, and security checklists before resolving backend decisions.",
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
            "id": "author-data-model",
            "kind": "author",
            "document": "docs/backend/02-data-model.md",
            "sections": list(BACKEND_DATA_MODEL_SECTIONS),
            "description": "Define ownership, entities, state machines, constraints, indexes, migrations, retention, and audit decisions.",
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
    ]


def _frontend_authoring_task(root: Path, candidate: dict[str, object], index: int) -> dict[str, object]:
    source = candidate["source"]
    if not isinstance(source, dict):  # pragma: no cover - internal invariant
        source = {}
    source_reference = str(source.get("reference", ""))
    api_contract = str(candidate["suggested_endpoint_file"])
    documents = [
        _authoring_document(
            "docs/ui/01-interaction-model.md",
            UI_INTERACTION_SECTIONS,
            "Define product-derived flows, screens, states, errors, and accessibility expectations.",
        ),
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
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "documents": documents,
        "required_links": required_links,
        "open_decisions": list(OPEN_FRONTEND_DECISIONS),
        "steps": _frontend_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _frontend_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "id": "load-frontend-design-skills",
            "kind": "skill-load",
            "skills": ["designing-ui-interactions", "designing-frontend-modules"],
            "description": "Load UI and frontend module skills before assigning flows, routes, state, or API consumption.",
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
            "id": "author-ui-interaction-model",
            "kind": "author",
            "document": "docs/ui/01-interaction-model.md",
            "sections": list(UI_INTERACTION_SECTIONS),
            "description": "Define product-derived flows, screens, states, user-visible errors, and accessibility expectations.",
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
    ]


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
        "api_candidate_id": candidate["candidate_id"],
        "acceptance_id": candidate["acceptance_id"],
        "title": candidate["title"],
        "source": source,
        "documents": documents,
        "required_links": required_links,
        "open_decisions": list(OPEN_TEST_STRATEGY_DECISIONS),
        "steps": _test_strategy_authoring_steps(root, source_reference, api_contract, required_links),
    }


def _test_strategy_authoring_steps(
    root: Path,
    source_reference: str,
    api_contract: str,
    required_links: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "id": "load-test-strategy-skill",
            "kind": "skill-load",
            "skills": ["designing-test-strategy"],
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
    ]


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
