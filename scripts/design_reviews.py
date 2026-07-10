from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from .state import StateFileError, load_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from state import StateFileError, load_state, utc_now


DESIGN_REVIEWS_REL = Path("docs/decisions/design-reviews.json")
DESIGN_REVIEW_SCHEMA_VERSION = 1
DESIGN_REVIEW_PHASE = "design-derivation"
DESIGN_REVIEW_ALLOWED_PHASES = frozenset({DESIGN_REVIEW_PHASE, "implementation"})
DESIGN_REVIEW_WORKFLOW = "workflows/04-design-derivation.md"
DESIGN_REVIEW_DECISION_POLICY = "review_all_design_decisions_with_source_and_authority_evidence"
DESIGN_REVIEW_RESULTS = ("approved", "not-applicable")
DESIGN_REVIEW_SCOPE = (
    "open-decisions",
    "source-traceability",
    "required-links",
    "authority-skill",
)
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER_REASON_RE = re.compile(r"\b(?:todo|tbd|unknown|placeholder)\b", re.IGNORECASE)
ACCEPTANCE_HEADING_RE = re.compile(
    r"^##[ \t]+(?P<id>A-[0-9]{3})[ \t]+(?P<title>.+?)[ \t]*$",
    re.MULTILINE,
)
ADR_PATH_RE = re.compile(r"^docs/decisions/[0-9]{3}-[a-z0-9][a-z0-9-]*\.md$")


DESIGN_REVIEW_TRACK_SPECS: dict[str, dict[str, object]] = {
    "architecture": {
        "work_prefix": "ARCHITECTURE-AUTHOR",
        "primary_authority_skill": "senior-architect",
        "decisions": (
            "system_boundary",
            "actors",
            "external_systems",
            "trust_boundaries",
            "container_responsibilities",
            "runtime_flows",
            "quality_scenarios",
            "deployment_assumptions",
            "risk_tradeoffs",
            "verification_hooks",
            "adr_candidates",
        ),
        "results": ("approved",),
    },
    "ui-interaction": {
        "work_prefix": "UI-INTERACTION-AUTHOR",
        "primary_authority_skill": "senior-frontend",
        "decisions": (
            "primary_flows",
            "screens",
            "states",
            "error_actions",
            "accessibility",
            "copy_and_content",
        ),
        "results": ("approved",),
    },
    "api-contracts": {
        "work_prefix": "API-AUTHOR",
        "primary_authority_skill": "api-design-reviewer",
        "decisions": (
            "method_path",
            "auth",
            "idempotency",
            "request_fields",
            "response_fields",
            "error_codes",
            "upstream_links",
            "frontend_consumers",
        ),
        "results": ("approved",),
    },
    "backend-modules": {
        "work_prefix": "BACKEND-AUTHOR",
        "primary_authority_skill": "senior-backend",
        "decisions": (
            "module_boundaries",
            "runtime_flow",
            "api_ownership",
            "data_ownership",
            "external_dependencies",
            "retries_timeouts",
            "observability",
            "security_boundaries",
            "acceptance_tests",
        ),
        "results": ("approved",),
    },
    "data-model": {
        "work_prefix": "DATA-MODEL-AUTHOR",
        "primary_authority_skill": "database-designer",
        "decisions": (
            "entity_ownership",
            "table_and_field_names",
            "lifecycle_states",
            "idempotency_constraints",
            "transaction_boundaries",
            "consistency_model",
            "concurrency_conflicts",
            "indexes_and_query_paths",
            "migration_order",
            "rollback_strategy",
            "retention_and_audit",
        ),
        "results": ("approved",),
    },
    "frontend-modules": {
        "work_prefix": "FRONTEND-AUTHOR",
        "primary_authority_skill": "senior-frontend",
        "decisions": (
            "route_ownership",
            "state_ownership",
            "api_consumption",
            "loading_states",
            "error_actions",
            "performance",
            "cache_invalidation",
        ),
        "results": ("approved",),
    },
    "test-strategy": {
        "work_prefix": "TEST-AUTHOR",
        "primary_authority_skill": "senior-qa",
        "decisions": (
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
        ),
        "results": ("approved",),
    },
    "implementation-planning": {
        "work_prefix": "PLAN-AUTHOR",
        "primary_authority_skill": "senior-fullstack",
        "decisions": (
            "task_scope",
            "milestone_sequence",
            "task_boundaries",
            "task_status",
            "ready_criteria",
            "product_traceability",
            "design_traceability",
            "api_traceability",
            "acceptance_mapping",
            "verification_plan",
            "agent_handoff",
            "dependency_order",
            "done_evidence",
            "deferred_scope",
            "supply_chain_checks",
        ),
        "results": ("approved",),
    },
    "architecture-decisions": {
        "work_prefix": "ADR-AUTHOR",
        "primary_authority_skill": "senior-architect",
        "decisions": (
            "adr_trigger",
            "decision_scope",
            "decision_drivers",
            "affected_modules",
            "alternatives",
            "selected_option",
            "consequences",
            "status",
            "verification_path",
            "reverse_links",
            "supersession",
            "deferred_or_no_adr_reason",
        ),
        "results": DESIGN_REVIEW_RESULTS,
    },
}

DESIGN_REVIEW_TRACK_ORDER = tuple(DESIGN_REVIEW_TRACK_SPECS)
DESIGN_REVIEW_BASELINE_DOCUMENTS = (
    "docs/architecture/01-system-context.md",
    "docs/architecture/02-containers.md",
    "docs/architecture/03-quality-attributes.md",
    "docs/ui/01-interaction-model.md",
    "docs/api/00-conventions.md",
    "docs/api/error-codes.md",
    "docs/api/changelog.md",
    "docs/backend/01-modules.md",
    "docs/backend/02-data-model.md",
    "docs/backend/03-external-services.md",
    "docs/frontend/01-modules.md",
    "docs/frontend/02-api-consumption.md",
    "docs/tests/01-strategy.md",
    "docs/tests/02-acceptance-matrix.md",
    "docs/development/01-roadmap.md",
    "docs/development/02-task-board.md",
    "docs/development/03-verification-log.md",
)
IMPLEMENTATION_MUTABLE_TABLE_COLUMNS = {
    "docs/development/01-roadmap.md": frozenset({"Status"}),
    "docs/development/02-task-board.md": frozenset({"Status", "Verification"}),
}
IMPLEMENTATION_TABLE_MUTABLE_REVIEW_EVIDENCE = frozenset(
    IMPLEMENTATION_MUTABLE_TABLE_COLUMNS
)
IMPLEMENTATION_EXECUTION_LOG_REVIEW_EVIDENCE = frozenset(
    {"docs/development/03-verification-log.md"}
)
MARKDOWN_TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


@dataclass
class DesignReviewResult:
    target: str
    ok: bool
    track: str
    work_id: str
    result: str
    reason: str
    reviewed: bool
    check: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)
    document: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("design review result target must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise ValueError("design review result ok must be a boolean")
        for field_name, value in (
            ("track", self.track),
            ("work_id", self.work_id),
            ("result", self.result),
            ("reason", self.reason),
        ):
            if not isinstance(value, str):
                raise ValueError(f"design review result {field_name} must be a string")
        if not isinstance(self.reviewed, bool) or not isinstance(self.check, bool):
            raise ValueError("design review result reviewed/check fields must be booleans")
        for field_name, values in (
            ("errors", self.errors),
            ("warnings", self.warnings),
            ("updated", self.updated),
            ("would_update", self.would_update),
        ):
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"design review result {field_name} must contain strings")
            if field_name in {"updated", "would_update"} and len(values) != len(set(values)):
                raise ValueError(f"design review result {field_name} paths must be unique")
        if self.check and self.updated:
            raise ValueError("design review check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("design review write mode cannot report would_update paths")
        if self.ok and self.errors:
            raise ValueError("design review success cannot contain errors")
        if not self.ok and not self.errors:
            raise ValueError("design review failure requires errors")
        self.errors = list(self.errors)
        self.warnings = list(self.warnings)
        self.updated = list(self.updated)
        self.would_update = list(self.would_update)
        self.review = copy.deepcopy(self.review)
        self.document = copy.deepcopy(self.document)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": DESIGN_REVIEW_WORKFLOW,
            "decision_policy": DESIGN_REVIEW_DECISION_POLICY,
            "review_path": DESIGN_REVIEWS_REL.as_posix(),
            "track": self.track,
            "work_id": self.work_id,
            "result": self.result,
            "reason": self.reason,
            "reviewed": self.reviewed,
            "check": self.check,
            "apply_requested": not self.check,
            "applied": bool(self.updated),
            "writes_state": not self.check,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "updated": list(self.updated),
            "would_update": list(self.would_update),
            "review": copy.deepcopy(self.review),
            "document": copy.deepcopy(self.document),
            "state": copy.deepcopy(self.state),
        }


@dataclass
class _DesignReviewPlan:
    target: str
    track: str
    work_id: str
    result: str
    reason: str
    reviewed: bool
    errors: list[str]
    warnings: list[str]
    review: dict[str, Any]
    document: dict[str, Any]
    rendered: bytes
    would_update: list[str]
    state: dict[str, Any]


def check_design_review(
    root: Path,
    *,
    track: str,
    work_id: str,
    result: str,
    reason: str,
    reviewed: bool,
    task: dict[str, object],
    evidence_paths: list[str] | None = None,
    skill_roots: list[Path] | None = None,
) -> DesignReviewResult:
    plan = _build_design_review_plan(
        root,
        track=track,
        work_id=work_id,
        result=result,
        reason=reason,
        reviewed=reviewed,
        task=task,
        evidence_paths=evidence_paths or [],
        skill_roots=skill_roots or [],
    )
    return DesignReviewResult(
        target=plan.target,
        ok=not plan.errors,
        track=plan.track,
        work_id=plan.work_id,
        result=plan.result,
        reason=plan.reason,
        reviewed=plan.reviewed,
        check=True,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        review=plan.review,
        document=plan.document,
        state=plan.state,
    )


def record_design_review(
    root: Path,
    *,
    track: str,
    work_id: str,
    result: str,
    reason: str,
    reviewed: bool,
    task: dict[str, object],
    evidence_paths: list[str] | None = None,
    skill_roots: list[Path] | None = None,
) -> DesignReviewResult:
    root = root.resolve()
    plan = _build_design_review_plan(
        root,
        track=track,
        work_id=work_id,
        result=result,
        reason=reason,
        reviewed=reviewed,
        task=task,
        evidence_paths=evidence_paths or [],
        skill_roots=skill_roots or [],
    )
    if plan.errors:
        return DesignReviewResult(
            target=plan.target,
            ok=False,
            track=plan.track,
            work_id=plan.work_id,
            result=plan.result,
            reason=plan.reason,
            reviewed=plan.reviewed,
            errors=plan.errors,
            warnings=plan.warnings,
            review=plan.review,
            document=plan.document,
            state=plan.state,
        )

    updated: list[str] = []
    if plan.would_update:
        try:
            _write_atomic_bytes(root, root / DESIGN_REVIEWS_REL, plan.rendered)
        except OSError as error:
            return DesignReviewResult(
                target=plan.target,
                ok=False,
                track=plan.track,
                work_id=plan.work_id,
                result=plan.result,
                reason=plan.reason,
                reviewed=plan.reviewed,
                errors=[
                    f"design review document is not writable: {DESIGN_REVIEWS_REL.as_posix()}: "
                    f"{_os_error_reason(error)}"
                ],
                warnings=plan.warnings,
                review=plan.review,
                document=plan.document,
                state=plan.state,
            )
        updated = list(plan.would_update)

    return DesignReviewResult(
        target=plan.target,
        ok=True,
        track=plan.track,
        work_id=plan.work_id,
        result=plan.result,
        reason=plan.reason,
        reviewed=plan.reviewed,
        warnings=plan.warnings,
        updated=updated,
        review=plan.review,
        document=plan.document,
        state=plan.state,
    )


def apply_design_reviews(
    root: Path,
    *,
    track: str,
    tasks: list[dict[str, object]],
) -> dict[str, object]:
    inventory = build_design_review_inventory(root)
    active_by_key = {
        _review_key(item): item for item in _dict_items(inventory.get("active"))
    }
    stale_by_key = {
        _review_key(item): item for item in _dict_items(inventory.get("stale"))
    }
    updated_tasks: list[dict[str, object]] = []
    satisfied_count = 0
    stale_count = 0
    missing_count = 0
    spec = DESIGN_REVIEW_TRACK_SPECS.get(track, {})
    expected_decisions = list(_string_tuple(spec.get("decisions")))
    for original in tasks:
        task = copy.deepcopy(original)
        acceptance_id = str(task.get("acceptance_id", ""))
        key = (track, acceptance_id)
        active = active_by_key.get(key, {})
        stale = stale_by_key.get(key, {})
        task["required_decisions"] = list(expected_decisions)
        if active:
            task["open_decisions"] = []
            task["review_status"] = "satisfied"
            task["design_review"] = copy.deepcopy(active)
            satisfied_count += 1
        elif stale:
            task["open_decisions"] = list(expected_decisions)
            task["review_status"] = "stale"
            task["stale_design_review"] = copy.deepcopy(stale)
            stale_count += 1
        else:
            task["open_decisions"] = list(expected_decisions)
            task["review_status"] = "missing"
            missing_count += 1
        updated_tasks.append(task)
    return {
        "tasks": updated_tasks,
        "path": DESIGN_REVIEWS_REL.as_posix(),
        "exists": inventory.get("exists") is True,
        "active": [
            copy.deepcopy(item)
            for item in _dict_items(inventory.get("active"))
            if item.get("track") == track
        ],
        "stale": [
            copy.deepcopy(item)
            for item in _dict_items(inventory.get("stale"))
            if item.get("track") == track
        ],
        "summary": {
            "task_count": len(updated_tasks),
            "satisfied_count": satisfied_count,
            "stale_count": stale_count,
            "missing_count": missing_count,
        },
        "errors": list(_string_items(inventory.get("errors"))),
    }


def build_design_review_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    document, document_errors = load_design_review_document(root)
    expected = _expected_reviews(root)
    expected_by_key = {_review_key(item): item for item in expected}
    reviews = _dict_items(document.get("reviews")) if not document_errors else []
    try:
        implementation_phase = load_state(root).get("phase") == "implementation"
    except StateFileError:
        implementation_phase = False
    snapshot_cache: dict[str, tuple[str, str, str]] = {}
    active: list[dict[str, object]] = []
    stale: list[dict[str, object]] = []
    orphan: list[dict[str, object]] = []
    for review in reviews:
        key = _review_key(review)
        expected_review = expected_by_key.get(key)
        if expected_review is None:
            orphan_item = copy.deepcopy(review)
            orphan_item["stale_reasons"] = ["review no longer maps to a current acceptance criterion"]
            orphan.append(orphan_item)
            continue
        stale_reasons = _review_stale_reasons(
            root,
            review,
            expected_review,
            implementation_phase=implementation_phase,
            snapshot_cache=snapshot_cache,
        )
        item = copy.deepcopy(review)
        if stale_reasons:
            item["stale_reasons"] = stale_reasons
            stale.append(item)
        else:
            active.append(item)
    active_keys = {_review_key(item) for item in active}
    missing = [copy.deepcopy(item) for item in expected if _review_key(item) not in active_keys]
    return {
        "path": DESIGN_REVIEWS_REL.as_posix(),
        "exists": (root / DESIGN_REVIEWS_REL).is_file(),
        "schema_version": document.get("schema_version", DESIGN_REVIEW_SCHEMA_VERSION),
        "active": active,
        "stale": stale,
        "orphan": orphan,
        "missing": missing,
        "expected_count": len(expected),
        "summary": {
            "expected_count": len(expected),
            "active_count": len(active),
            "stale_count": len(stale),
            "orphan_count": len(orphan),
            "missing_count": len(missing),
        },
        "errors": document_errors,
    }


def design_review_enforcement_ready(root: Path) -> bool:
    root = root.resolve()
    if (root / DESIGN_REVIEWS_REL).exists() or (root / DESIGN_REVIEWS_REL).is_symlink():
        return True
    for rel in DESIGN_REVIEW_BASELINE_DOCUMENTS:
        path = root / rel
        if not path.is_file() or path.is_symlink():
            return False
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if SCAFFOLD_PLACEHOLDER in text:
            return False
    endpoint_root = root / "docs/api/endpoints"
    if not endpoint_root.is_dir():
        return False
    for path in endpoint_root.glob("[0-9][0-9]-*.md"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if SCAFFOLD_PLACEHOLDER not in text:
            return True
    return False


def load_design_review_document(root: Path) -> tuple[dict[str, Any], list[str]]:
    root = root.resolve()
    path = root / DESIGN_REVIEWS_REL
    if path.is_symlink():
        return _empty_document(), [
            f"design review document must not be a symbolic link: {DESIGN_REVIEWS_REL.as_posix()}"
        ]
    if not path.exists():
        return _empty_document(), []
    if not path.is_file():
        return _empty_document(), [
            f"design review document is not a file: {DESIGN_REVIEWS_REL.as_posix()}"
        ]
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return _empty_document(), ["design review document must be UTF-8 JSON"]
    except json.JSONDecodeError as error:
        return _empty_document(), [f"design review document is invalid JSON: {error.msg}"]
    except OSError as error:
        return _empty_document(), [f"design review document is unreadable: {_os_error_reason(error)}"]
    if not isinstance(loaded, dict):
        return _empty_document(), ["design review document root must be an object"]
    return copy.deepcopy(loaded), _validate_document(loaded)


def _build_design_review_plan(
    root: Path,
    *,
    track: str,
    work_id: str,
    result: str,
    reason: str,
    reviewed: bool,
    task: dict[str, object],
    evidence_paths: list[str],
    skill_roots: list[Path],
) -> _DesignReviewPlan:
    root = root.resolve()
    normalized_track = track.strip() if isinstance(track, str) else ""
    normalized_work_id = work_id.strip() if isinstance(work_id, str) else ""
    normalized_result = result.strip() if isinstance(result, str) else ""
    normalized_reason = reason.strip() if isinstance(reason, str) else ""
    errors: list[str] = []
    warnings: list[str] = []
    state: dict[str, Any] = {}
    try:
        state = load_state(root)
    except StateFileError as error:
        errors.append(str(error))
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    if not state:
        errors.append("No governance state found.")
    elif phase not in DESIGN_REVIEW_ALLOWED_PHASES:
        errors.append("design review requires recorded phase design-derivation or implementation")

    spec = DESIGN_REVIEW_TRACK_SPECS.get(normalized_track)
    if spec is None:
        errors.append(f"unknown design review track: {normalized_track or '<missing>'}")
        spec = {}
    expected_decisions = list(_string_tuple(spec.get("decisions")))
    allowed_results = _string_tuple(spec.get("results"))
    primary_authority_skill = str(spec.get("primary_authority_skill", ""))
    task_id = str(task.get("task_id", ""))
    acceptance_id = str(task.get("acceptance_id", ""))
    if not task_id or task_id != normalized_work_id:
        errors.append(f"design review work item does not exist in the current track: {normalized_work_id or '<missing>'}")
    if not acceptance_id:
        errors.append("design review work item has no acceptance ID")
    if normalized_result not in allowed_results:
        errors.append(
            f"unsupported design review result for {normalized_track or '<missing>'}: "
            f"{normalized_result or '<missing>'}"
        )
    if reviewed is not True:
        errors.append("--reviewed is required")
    if not _concrete_reason(normalized_reason):
        errors.append("reason must be a concrete authority-review explanation")

    document_errors = _task_document_errors(task)
    errors.extend(document_errors)
    link_errors = _task_link_errors(task)
    errors.extend(link_errors)

    explicit_evidence = _dedupe_strings(
        [path.strip() for path in evidence_paths if isinstance(path, str) and path.strip()]
    )
    if normalized_track == "architecture-decisions" and normalized_result == "approved":
        if not any(ADR_PATH_RE.fullmatch(path) for path in explicit_evidence):
            errors.append("approved architecture-decision review requires --evidence docs/decisions/NNN-<slug>.md")

    authority_skill, authority_errors = _authority_skill_evidence(
        root,
        primary_authority_skill,
        skill_roots,
    )
    errors.extend(authority_errors)

    source_paths = ["docs/product/core/PRD.md"]
    source = task.get("source") if isinstance(task.get("source"), dict) else {}
    source_path = str(source.get("path", ""))
    if source_path:
        source_paths.append(source_path)
    source_snapshots, source_errors = _snapshot_paths(root, source_paths, "design review source")
    errors.extend(source_errors)

    task_documents = [
        str(item.get("path", ""))
        for item in _dict_items(task.get("documents"))
        if str(item.get("path", "")) and not Path(str(item.get("path", ""))).name.startswith("_")
    ]
    link_paths = [
        str(item.get("target", "")).split("#", 1)[0]
        for item in _dict_items(task.get("required_links"))
        if str(item.get("target", "")).split("#", 1)[0]
    ]
    evidence_candidates = [
        path
        for path in _dedupe_strings([*task_documents, *link_paths, *explicit_evidence])
        if path not in source_paths
    ]
    evidence_snapshots, evidence_errors = _snapshot_paths(
        root,
        evidence_candidates,
        "design review evidence",
    )
    errors.extend(evidence_errors)
    if not evidence_snapshots:
        errors.append("design review requires at least one repository evidence document")

    document, stored_errors = load_design_review_document(root)
    errors.extend(stored_errors)
    expected_keys = {_review_key(item) for item in _expected_reviews(root)}
    reviews = [
        item
        for item in _dict_items(document.get("reviews"))
        if _review_key(item) in expected_keys
    ] if not stored_errors else []
    existing = next(
        (
            item
            for item in reviews
            if item.get("track") == normalized_track and item.get("acceptance_id") == acceptance_id
        ),
        {},
    )
    recorded_at = utc_now()
    candidate_without_time = {
        "track": normalized_track,
        "work_id": normalized_work_id,
        "acceptance_id": acceptance_id,
        "result": normalized_result,
        "reason": normalized_reason,
        "reviewed": reviewed is True,
        "review_scope": list(DESIGN_REVIEW_SCOPE),
        "reviewed_decisions": expected_decisions,
        "source_snapshots": source_snapshots,
        "evidence_snapshots": evidence_snapshots,
        "authority_skill": authority_skill,
    }
    if (
        all(existing.get(key) == value for key, value in candidate_without_time.items())
        and isinstance(existing.get("recorded_at"), str)
    ):
        recorded_at = str(existing["recorded_at"])
    review = {**candidate_without_time, "recorded_at": recorded_at}
    updated_reviews = [
        item
        for item in reviews
        if not (
            item.get("track") == normalized_track
            and item.get("acceptance_id") == acceptance_id
        )
    ]
    if normalized_track and acceptance_id:
        updated_reviews.append(review)
    updated_reviews.sort(key=_review_sort_key)
    updated_document = {
        "schema_version": DESIGN_REVIEW_SCHEMA_VERSION,
        "reviews": updated_reviews,
    }
    rendered = (json.dumps(updated_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path = root / DESIGN_REVIEWS_REL
    errors.extend(_design_review_output_errors(root, path))
    current = b""
    if path.is_file() and not path.is_symlink():
        try:
            current = path.read_bytes()
        except OSError as error:
            errors.append(f"design review document is unreadable: {_os_error_reason(error)}")
    would_update = [DESIGN_REVIEWS_REL.as_posix()] if not errors and current != rendered else []
    return _DesignReviewPlan(
        target=str(root),
        track=normalized_track,
        work_id=normalized_work_id,
        result=normalized_result,
        reason=normalized_reason,
        reviewed=reviewed is True,
        errors=_dedupe_strings(errors),
        warnings=warnings,
        review=review,
        document=updated_document,
        rendered=rendered,
        would_update=would_update,
        state=state,
    )


def _authority_skill_evidence(
    root: Path,
    skill_name: str,
    skill_roots: list[Path],
) -> tuple[dict[str, str], list[str]]:
    if not skill_name:
        return {}, ["design review track has no primary authority skill"]
    try:
        try:
            from .authority_skills import build_authority_skill_inventory
        except ImportError:  # pragma: no cover - direct script execution
            from authority_skills import build_authority_skill_inventory
        inventory = build_authority_skill_inventory(
            skill_roots=[root / ".agents/skills", root / ".codex/skills", *skill_roots],
            strict=False,
        )
    except (OSError, RuntimeError) as error:
        return {}, [f"authority skill inventory failed: {error}"]
    match = next(
        (
            item
            for item in _dict_items(inventory.get("skills"))
            if item.get("name") == skill_name and item.get("available_in_agent_environment") is True
        ),
        {},
    )
    path_text = str(match.get("skill_path", ""))
    if not path_text:
        return {}, [
            f"required authority skill is unavailable for design review: {skill_name}"
        ]
    path = Path(path_text)
    try:
        content = path.read_bytes()
        content.decode("utf-8")
    except UnicodeDecodeError:
        return {}, [f"authority skill must be UTF-8: {skill_name}"]
    except OSError as error:
        return {}, [f"authority skill is unreadable: {skill_name}: {_os_error_reason(error)}"]
    return {
        "name": skill_name,
        "sha256": hashlib.sha256(content).hexdigest(),
        "availability_scope": "agent-environment",
    }, []


def _task_document_errors(task: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for document in _dict_items(task.get("documents")):
        status = str(document.get("status", ""))
        path = str(document.get("path", "<missing>"))
        if status not in {"authored", "reference_template"}:
            errors.append(f"design review document is not authoring-complete: {path}: {status or 'unknown'}")
    return errors


def _task_link_errors(task: dict[str, object]) -> list[str]:
    return [
        f"design review required link is not satisfied: {item.get('target', '<missing>')}: "
        f"{item.get('status', 'unknown')}"
        for item in _dict_items(task.get("required_links"))
        if item.get("status") != "satisfied"
    ]


def _expected_reviews(root: Path) -> list[dict[str, object]]:
    acceptances = _acceptance_items(root)
    expected: list[dict[str, object]] = []
    for track, spec in DESIGN_REVIEW_TRACK_SPECS.items():
        prefix = str(spec.get("work_prefix", ""))
        for index, acceptance in enumerate(acceptances, start=1):
            expected.append(
                {
                    "track": track,
                    "work_id": f"{prefix}-{index:03d}",
                    "acceptance_id": acceptance["acceptance_id"],
                    "acceptance_path": acceptance["path"],
                    "reviewed_decisions": list(_string_tuple(spec.get("decisions"))),
                    "primary_authority_skill": str(spec.get("primary_authority_skill", "")),
                    "result_options": list(_string_tuple(spec.get("results"))),
                }
            )
    return expected


def _acceptance_items(root: Path) -> list[dict[str, str]]:
    product_root = root / "docs/product"
    if not product_root.is_dir():
        return []
    items: list[dict[str, str]] = []
    for path in sorted(product_root.glob("[0-9][0-9]-*acceptance*.md")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        for match in ACCEPTANCE_HEADING_RE.finditer(text):
            items.append(
                {
                    "acceptance_id": match.group("id"),
                    "title": match.group("title").strip(),
                    "path": rel,
                }
            )
    return items


def _review_stale_reasons(
    root: Path,
    review: dict[str, object],
    expected: dict[str, object],
    *,
    implementation_phase: bool,
    snapshot_cache: dict[str, tuple[str, str, str]],
) -> list[str]:
    reasons: list[str] = []
    if review.get("work_id") != expected.get("work_id"):
        reasons.append("work ID changed for the current acceptance ordering")
    if review.get("reviewed_decisions") != expected.get("reviewed_decisions"):
        reasons.append("required design decision registry changed")
    authority_skill = review.get("authority_skill") if isinstance(review.get("authority_skill"), dict) else {}
    if authority_skill.get("name") != expected.get("primary_authority_skill"):
        reasons.append("primary authority skill requirement changed")
    source_paths = {
        str(item.get("path", ""))
        for item in _dict_items(review.get("source_snapshots"))
    }
    for required_path in ("docs/product/core/PRD.md", str(expected.get("acceptance_path", ""))):
        if required_path and required_path not in source_paths:
            reasons.append(f"required source snapshot is missing: {required_path}")
    for field_name in ("source_snapshots", "evidence_snapshots"):
        for snapshot in _dict_items(review.get(field_name)):
            reason = _snapshot_stale_reason(
                root,
                snapshot,
                allow_implementation_mutation=implementation_phase,
                snapshot_cache=snapshot_cache,
            )
            if reason:
                reasons.append(reason)
    return _dedupe_strings(reasons)


def _snapshot_paths(
    root: Path,
    paths: list[str],
    label: str,
) -> tuple[list[dict[str, str]], list[str]]:
    snapshots: list[dict[str, str]] = []
    errors: list[str] = []
    for rel in _dedupe_strings(paths):
        normalized, path_error = _safe_relative_path(rel)
        if path_error:
            errors.append(f"{label} path is invalid: {rel or '<missing>'}: {path_error}")
            continue
        path = root / normalized
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            errors.append(f"{label} path resolves outside target: {normalized}")
            continue
        if path.is_symlink():
            errors.append(f"{label} path must not be a symbolic link: {normalized}")
            continue
        if not path.is_file():
            errors.append(f"{label} path is not a file: {normalized}")
            continue
        try:
            content = path.read_bytes()
            content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{label} path must be UTF-8: {normalized}")
            continue
        except OSError as error:
            errors.append(f"{label} path is unreadable: {normalized}: {_os_error_reason(error)}")
            continue
        snapshot = {
            "path": normalized,
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        semantic_digest = _implementation_semantic_sha256(normalized, content)
        if semantic_digest:
            snapshot["semantic_sha256"] = semantic_digest
        snapshots.append(snapshot)
    snapshots.sort(key=lambda item: item["path"])
    return snapshots, errors


def _snapshot_stale_reason(
    root: Path,
    snapshot: dict[str, object],
    *,
    allow_implementation_mutation: bool,
    snapshot_cache: dict[str, tuple[str, str, str]],
) -> str:
    rel = str(snapshot.get("path", ""))
    normalized, path_error = _safe_relative_path(rel)
    if path_error:
        return f"review snapshot path is invalid: {rel or '<missing>'}"
    cached = snapshot_cache.get(normalized)
    if cached is None:
        path = root / normalized
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            cached = (f"review snapshot path resolves outside target: {normalized}", "", "")
        else:
            if path.is_symlink() or not path.is_file():
                cached = (f"review snapshot source is missing or unsafe: {normalized}", "", "")
            else:
                try:
                    content = path.read_bytes()
                except OSError:
                    cached = (f"review snapshot source is unreadable: {normalized}", "", "")
                else:
                    cached = (
                        "",
                        hashlib.sha256(content).hexdigest(),
                        _implementation_semantic_sha256(normalized, content),
                    )
        snapshot_cache[normalized] = cached
    snapshot_error, digest, current_semantic_digest = cached
    if snapshot_error:
        return snapshot_error
    if allow_implementation_mutation and normalized in IMPLEMENTATION_EXECUTION_LOG_REVIEW_EVIDENCE:
        return ""
    if allow_implementation_mutation and normalized in IMPLEMENTATION_TABLE_MUTABLE_REVIEW_EVIDENCE:
        expected_semantic_digest = snapshot.get("semantic_sha256")
        if isinstance(expected_semantic_digest, str) and SHA256_RE.fullmatch(expected_semantic_digest):
            if current_semantic_digest != expected_semantic_digest:
                return f"reviewed planning meaning changed after authority review: {normalized}"
            return ""
    if digest != snapshot.get("sha256"):
        return f"review snapshot changed after authority review: {normalized}"
    return ""


def _implementation_semantic_sha256(rel: str, content: bytes) -> str:
    mutable_columns = IMPLEMENTATION_MUTABLE_TABLE_COLUMNS.get(rel)
    if not mutable_columns:
        return ""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return ""
    normalized_lines: list[str] = []
    mutable_indexes: tuple[int, ...] = ()
    for line in text.splitlines():
        cells = _markdown_table_cells(line)
        if cells is None:
            mutable_indexes = ()
            normalized_lines.append(line)
            continue
        normalized_cells = [cell.strip() for cell in cells]
        if "ID" in normalized_cells and mutable_columns.issubset(normalized_cells):
            mutable_indexes = tuple(
                normalized_cells.index(column)
                for column in mutable_columns
            )
        elif mutable_indexes and max(mutable_indexes) < len(normalized_cells):
            is_separator = all(
                MARKDOWN_TABLE_SEPARATOR_CELL_RE.fullmatch(cell) is not None
                for cell in normalized_cells
            )
            if not is_separator:
                for index in mutable_indexes:
                    normalized_cells[index] = "<implementation-mutable>"
        normalized_lines.append("| " + " | ".join(normalized_cells) + " |")
    normalized = "\n".join(normalized_lines) + ("\n" if text.endswith(("\n", "\r")) else "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _markdown_table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return stripped[1:-1].split("|")


def _validate_document(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    schema_version = document.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != DESIGN_REVIEW_SCHEMA_VERSION
    ):
        errors.append(f"design review document schema_version must be {DESIGN_REVIEW_SCHEMA_VERSION}")
    reviews = document.get("reviews")
    if not isinstance(reviews, list):
        errors.append("design review document reviews must be a list")
        return errors
    seen: set[tuple[str, str]] = set()
    for index, review in enumerate(reviews):
        prefix = f"design review entry {index + 1}"
        if not isinstance(review, dict):
            errors.append(f"{prefix} must be an object")
            continue
        track = review.get("track")
        spec = DESIGN_REVIEW_TRACK_SPECS.get(str(track), {})
        if not spec:
            errors.append(f"{prefix} has unknown track: {track}")
        acceptance_id = review.get("acceptance_id")
        if not isinstance(acceptance_id, str) or re.fullmatch(r"A-[0-9]{3}", acceptance_id) is None:
            errors.append(f"{prefix} acceptance_id must use A-NNN")
        key = (str(track), str(acceptance_id))
        if key in seen:
            errors.append(f"duplicate design review: {key[0]} {key[1]}")
        seen.add(key)
        work_prefix = str(spec.get("work_prefix", ""))
        work_id = review.get("work_id")
        if not isinstance(work_id, str) or not work_id.startswith(f"{work_prefix}-"):
            errors.append(f"{prefix} work_id does not match track {track}")
        result = review.get("result")
        if result not in _string_tuple(spec.get("results")):
            errors.append(f"{prefix} has unsupported result: {result}")
        reason = review.get("reason")
        if not isinstance(reason, str) or not _concrete_reason(reason):
            errors.append(f"{prefix} reason must be a concrete authority-review explanation")
        if review.get("reviewed") is not True:
            errors.append(f"{prefix} reviewed must be true")
        if review.get("review_scope") != list(DESIGN_REVIEW_SCOPE):
            errors.append(f"{prefix} review_scope must match the design review contract")
        if review.get("reviewed_decisions") != list(_string_tuple(spec.get("decisions"))):
            errors.append(f"{prefix} reviewed_decisions must match the track decision registry")
        source_snapshots = review.get("source_snapshots")
        evidence_snapshots = review.get("evidence_snapshots")
        errors.extend(_validate_snapshots(source_snapshots, f"{prefix} source_snapshots", require_non_empty=True))
        errors.extend(_validate_snapshots(evidence_snapshots, f"{prefix} evidence_snapshots", require_non_empty=True))
        authority = review.get("authority_skill")
        if not isinstance(authority, dict):
            errors.append(f"{prefix} authority_skill must be an object")
        else:
            if authority.get("name") != spec.get("primary_authority_skill"):
                errors.append(f"{prefix} authority_skill name must be {spec.get('primary_authority_skill', '')}")
            digest = authority.get("sha256")
            if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
                errors.append(f"{prefix} authority_skill sha256 must be a lowercase SHA-256 digest")
            if authority.get("availability_scope") != "agent-environment":
                errors.append(f"{prefix} authority_skill availability_scope must be agent-environment")
        recorded_at = review.get("recorded_at")
        if not isinstance(recorded_at, str) or not _valid_timestamp(recorded_at):
            errors.append(f"{prefix} recorded_at must be an ISO-8601 timestamp")
    return _dedupe_strings(errors)


def _validate_snapshots(value: object, label: str, *, require_non_empty: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    if require_non_empty and not value:
        errors.append(f"{label} must not be empty")
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{label} entry {index + 1} must be an object")
            continue
        path = item.get("path")
        digest = item.get("sha256")
        normalized, path_error = _safe_relative_path(str(path) if isinstance(path, str) else "")
        if path_error:
            errors.append(f"{label} entry {index + 1} path is invalid")
        elif normalized in seen:
            errors.append(f"{label} contains duplicate path: {normalized}")
        else:
            seen.add(normalized)
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            errors.append(f"{label} entry {index + 1} sha256 must be a lowercase SHA-256 digest")
        semantic_digest = item.get("semantic_sha256")
        if semantic_digest is not None and (
            not isinstance(semantic_digest, str)
            or SHA256_RE.fullmatch(semantic_digest) is None
        ):
            errors.append(
                f"{label} entry {index + 1} semantic_sha256 must be a lowercase SHA-256 digest"
            )
    return errors


def _safe_relative_path(value: str) -> tuple[str, str]:
    if not value or "\\" in value:
        return "", "path must be a non-empty POSIX relative path"
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return "", "path traversal and absolute paths are forbidden"
    normalized = pure.as_posix()
    if normalized != value:
        return "", "path must be normalized"
    return normalized, ""


def _design_review_output_errors(root: Path, path: Path) -> list[str]:
    errors: list[str] = []
    try:
        relative = path.relative_to(root)
        path.parent.resolve().relative_to(root)
    except ValueError:
        return [
            "design review output parent resolves outside target: "
            f"{DESIGN_REVIEWS_REL.parent.as_posix()}"
        ]
    except OSError as error:
        return [f"design review output parent is invalid: {_os_error_reason(error)}"]
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            errors.append(
                "design review output parent must not contain symbolic links: "
                f"{current.relative_to(root).as_posix()}"
            )
            break
        if current.exists() and not current.is_dir():
            errors.append(
                "design review output parent is not a directory: "
                f"{current.relative_to(root).as_posix()}"
            )
            break
    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        errors.append(
            "design review temporary path already exists: "
            f"{temp.relative_to(root).as_posix()}"
        )
    return errors


def _write_atomic_bytes(root: Path, path: Path, content: bytes) -> None:
    output_errors = _design_review_output_errors(root, path)
    if output_errors:
        raise OSError(output_errors[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _atomic_temp_path(path)
    try:
        temp.write_bytes(content)
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


def _empty_document() -> dict[str, Any]:
    return {"schema_version": DESIGN_REVIEW_SCHEMA_VERSION, "reviews": []}


def _review_key(item: dict[str, object]) -> tuple[str, str]:
    return str(item.get("track", "")), str(item.get("acceptance_id", ""))


def _review_sort_key(item: dict[str, object]) -> tuple[int, str]:
    track = str(item.get("track", ""))
    try:
        track_index = DESIGN_REVIEW_TRACK_ORDER.index(track)
    except ValueError:
        track_index = len(DESIGN_REVIEW_TRACK_ORDER)
    return track_index, str(item.get("acceptance_id", ""))


def _dict_items(value: object) -> list[dict[str, Any]]:
    return [copy.deepcopy(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_items(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str) and item] if isinstance(value, list) else []


def _string_tuple(value: object) -> tuple[str, ...]:
    return tuple(str(item) for item in value if isinstance(item, str) and item) if isinstance(value, (list, tuple)) else ()


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _concrete_reason(reason: str) -> bool:
    normalized = reason.strip()
    return (
        len(normalized) >= 24
        and normalized.casefold() not in {"none", "n/a", "not applicable"}
        and PLACEHOLDER_REASON_RE.search(normalized) is None
    )


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)
