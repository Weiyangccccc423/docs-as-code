from __future__ import annotations

import copy
import hashlib
import json
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from .state import StateFileError, load_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from state import StateFileError, load_state, utc_now


MIGRATION_SCOPE_REL = Path("docs/backend/migrations/review-scope.json")
MIGRATION_SCHEMA_BEFORE_REL = Path("docs/backend/migrations/schema-before.json")
MIGRATION_SCHEMA_AFTER_REL = Path("docs/backend/migrations/schema-after.json")
MIGRATION_SPEC_REL = Path("docs/backend/migrations/migration-spec.json")
MIGRATION_ACCEPTANCES_REL = Path("docs/backend/migrations/compatibility-acceptances.json")
MIGRATION_PLAN_REL = Path("docs/backend/migrations/migration-plan.json")
MIGRATION_COMPATIBILITY_REL = Path("docs/backend/migrations/compatibility-report.json")
MIGRATION_ROLLBACK_REL = Path("docs/backend/migrations/rollback-runbook.json")
MIGRATION_EVIDENCE_REL = Path("docs/backend/migrations/review-evidence.json")
MIGRATION_SCHEMA_VERSION = 1
MIGRATION_DECISION_POLICY = (
    "design_schema_with_database_schema_designer_then_run_migration_architect_before_data_model_signoff"
)
MIGRATION_ALLOWED_PHASES = frozenset({"design-derivation", "implementation"})
MIGRATION_MODES = ("required", "not-applicable")
MIGRATION_AUTHORITY_SKILLS = ("database-schema-designer", "migration-architect")
MIGRATION_TOOL_FILES = {
    "migration_planner": "migration_planner.py",
    "compatibility_checker": "compatibility_checker.py",
    "rollback_generator": "rollback_generator.py",
}
MIGRATION_INPUT_PATHS = {
    "schema_before": MIGRATION_SCHEMA_BEFORE_REL,
    "schema_after": MIGRATION_SCHEMA_AFTER_REL,
    "migration_spec": MIGRATION_SPEC_REL,
    "compatibility_acceptances": MIGRATION_ACCEPTANCES_REL,
}
MIGRATION_REPORT_PATHS = {
    "migration_plan": MIGRATION_PLAN_REL,
    "compatibility_report": MIGRATION_COMPATIBILITY_REL,
    "rollback_runbook": MIGRATION_ROLLBACK_REL,
}
MIGRATION_REQUIRED_SOURCE_PATHS = (
    "docs/architecture/03-quality-attributes.md",
    "docs/backend/01-modules.md",
    "docs/backend/02-data-model.md",
)
MIGRATION_COMPATIBILITY_LEVELS = (
    "fully_compatible",
    "backward_compatible",
    "accepted_with_mitigations",
)
MIGRATION_SERIOUS_SEVERITIES = frozenset({"breaking", "potentially_breaking"})
MIGRATION_MAX_JSON_BYTES = 20 * 1024 * 1024
MIGRATION_MAX_ACCEPTANCES = 256
MIGRATION_TOOL_TIMEOUT_SECONDS = 90
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
ISSUE_ID_RE = re.compile(r"^migration-compat-[0-9a-f]{12}$")
PLACEHOLDER_RE = re.compile(r"\b(?:todo|tbd|unknown|placeholder|must define)\b", re.IGNORECASE)
ACCEPTANCE_PATH_RE = re.compile(r"^docs/product/[0-9]{2}-[a-z0-9-]*acceptance[a-z0-9-]*\.md$")


@dataclass
class MigrationReviewEvidenceResult:
    target: str
    ok: bool
    reviewed: bool
    mode: str
    compatibility_status: str
    check: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    tool_runs: list[dict[str, object]] = field(default_factory=list)
    unaccepted_issues: list[dict[str, object]] = field(default_factory=list)
    report_summaries: dict[str, object] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("migration review target must be a non-empty string")
        if self.mode not in MIGRATION_MODES and self.mode != "unknown":
            raise ValueError("migration review mode is invalid")
        if not isinstance(self.ok, bool) or not isinstance(self.reviewed, bool) or not isinstance(self.check, bool):
            raise ValueError("migration review boolean fields must be booleans")
        for name in ("errors", "warnings", "updated", "would_update"):
            values = getattr(self, name)
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"migration review {name} must contain strings")
        if self.ok and self.errors:
            raise ValueError("migration review success cannot contain errors")
        if not self.ok and not self.errors:
            raise ValueError("migration review failure requires errors")
        if self.check and self.updated:
            raise ValueError("migration review check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("migration review write mode cannot report would_update paths")
        self.evidence = copy.deepcopy(self.evidence)
        self.tool_runs = copy.deepcopy(self.tool_runs)
        self.unaccepted_issues = copy.deepcopy(self.unaccepted_issues)
        self.report_summaries = copy.deepcopy(self.report_summaries)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": "workflows/04-design-derivation.md",
            "decision_policy": MIGRATION_DECISION_POLICY,
            "scope_path": MIGRATION_SCOPE_REL.as_posix(),
            "evidence_path": MIGRATION_EVIDENCE_REL.as_posix(),
            "mode": self.mode,
            "compatibility_status": self.compatibility_status,
            "reviewed": self.reviewed,
            "check": self.check,
            "apply_requested": not self.check,
            "applied": bool(self.updated),
            "writes_state": not self.check,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "updated": list(self.updated),
            "would_update": list(self.would_update),
            "evidence": copy.deepcopy(self.evidence),
            "tool_runs": copy.deepcopy(self.tool_runs),
            "unaccepted_issues": copy.deepcopy(self.unaccepted_issues),
            "report_summaries": copy.deepcopy(self.report_summaries),
            "state": copy.deepcopy(self.state),
        }


@dataclass
class _MigrationReviewPlan:
    target: str
    reviewed: bool
    mode: str
    compatibility_status: str
    errors: list[str]
    warnings: list[str]
    evidence: dict[str, Any]
    tool_runs: list[dict[str, object]]
    unaccepted_issues: list[dict[str, object]]
    report_summaries: dict[str, object]
    outputs: dict[str, bytes]
    would_update: list[str]
    state: dict[str, Any]


def check_migration_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> MigrationReviewEvidenceResult:
    plan = _build_migration_review_plan(root, reviewed=reviewed, skill_roots=list(skill_roots or []))
    return MigrationReviewEvidenceResult(
        target=plan.target,
        ok=not plan.errors,
        reviewed=plan.reviewed,
        mode=plan.mode,
        compatibility_status=plan.compatibility_status,
        check=True,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        evidence=plan.evidence,
        tool_runs=plan.tool_runs,
        unaccepted_issues=plan.unaccepted_issues,
        report_summaries=plan.report_summaries,
        state=plan.state,
    )


def record_migration_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> MigrationReviewEvidenceResult:
    root = root.resolve()
    plan = _build_migration_review_plan(root, reviewed=reviewed, skill_roots=list(skill_roots or []))
    if plan.errors:
        return MigrationReviewEvidenceResult(
            target=plan.target,
            ok=False,
            reviewed=plan.reviewed,
            mode=plan.mode,
            compatibility_status=plan.compatibility_status,
            errors=plan.errors,
            warnings=plan.warnings,
            evidence=plan.evidence,
            tool_runs=plan.tool_runs,
            unaccepted_issues=plan.unaccepted_issues,
            report_summaries=plan.report_summaries,
            state=plan.state,
        )
    updated: list[str] = []
    if plan.would_update:
        try:
            _write_outputs_atomically(root, plan.outputs)
        except OSError as error:
            return MigrationReviewEvidenceResult(
                target=plan.target,
                ok=False,
                reviewed=plan.reviewed,
                mode=plan.mode,
                compatibility_status=plan.compatibility_status,
                errors=[f"migration review evidence is not writable: {_os_error_reason(error)}"],
                warnings=plan.warnings,
                evidence=plan.evidence,
                tool_runs=plan.tool_runs,
                unaccepted_issues=plan.unaccepted_issues,
                report_summaries=plan.report_summaries,
                state=plan.state,
            )
        updated = list(plan.would_update)
    return MigrationReviewEvidenceResult(
        target=plan.target,
        ok=True,
        reviewed=plan.reviewed,
        mode=plan.mode,
        compatibility_status=plan.compatibility_status,
        warnings=plan.warnings,
        updated=updated,
        evidence=plan.evidence,
        tool_runs=plan.tool_runs,
        unaccepted_issues=plan.unaccepted_issues,
        report_summaries=plan.report_summaries,
        state=plan.state,
    )


def build_migration_review_evidence_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    path = root / MIGRATION_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {
            "path": MIGRATION_EVIDENCE_REL.as_posix(),
            "exists": False,
            "ok": False,
            "status": "missing",
            "mode": "unknown",
            "errors": [],
            "stale_reasons": [],
            "evidence": {},
        }
    evidence, errors = _load_json_object(root, MIGRATION_EVIDENCE_REL, "migration review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(evidence))
    if not errors:
        errors.extend(_persisted_report_errors(root, evidence))
    stale_reasons: list[str] = []
    if not errors:
        stale_reasons.extend(_evidence_stale_reasons(root, evidence))
    return {
        "path": MIGRATION_EVIDENCE_REL.as_posix(),
        "exists": path.is_file() and not path.is_symlink(),
        "ok": not errors and not stale_reasons,
        "status": "invalid" if errors else "stale" if stale_reasons else "current",
        "mode": str(evidence.get("mode", "unknown")),
        "errors": _dedupe_strings(errors),
        "stale_reasons": _dedupe_strings(stale_reasons),
        "evidence": copy.deepcopy(evidence),
    }


def migration_review_enforcement_ready(root: Path) -> bool:
    root = root.resolve()
    for rel in (MIGRATION_SCOPE_REL, *MIGRATION_INPUT_PATHS.values(), *MIGRATION_REPORT_PATHS.values(), MIGRATION_EVIDENCE_REL):
        if (root / rel).exists() or (root / rel).is_symlink():
            return True
    path = root / "docs/backend/02-data-model.md"
    if not path.is_file() or path.is_symlink():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return SCAFFOLD_PLACEHOLDER not in text


def migration_review_required_evidence_paths(root: Path) -> list[str]:
    inventory = build_migration_review_evidence_inventory(root)
    evidence = inventory.get("evidence") if isinstance(inventory.get("evidence"), dict) else {}
    paths = [MIGRATION_SCOPE_REL.as_posix(), MIGRATION_EVIDENCE_REL.as_posix()]
    mode = str(inventory.get("mode", "unknown"))
    if mode == "unknown":
        scope, scope_errors = _load_json_object(root.resolve(), MIGRATION_SCOPE_REL, "migration review scope")
        applicability = scope.get("applicability") if not scope_errors else {}
        mode = str(applicability.get("decision", "unknown")) if isinstance(applicability, dict) else "unknown"
    if mode != "not-applicable":
        paths.extend(rel.as_posix() for rel in MIGRATION_INPUT_PATHS.values())
        paths.extend(rel.as_posix() for rel in MIGRATION_REPORT_PATHS.values())
    for key in ("source_snapshots",):
        snapshots = evidence.get(key) if isinstance(evidence, dict) else []
        if isinstance(snapshots, list):
            paths.extend(
                str(item.get("path", ""))
                for item in snapshots
                if isinstance(item, dict) and str(item.get("path", ""))
            )
    return _dedupe_strings(paths)


def _build_migration_review_plan(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path],
) -> _MigrationReviewPlan:
    root = root.resolve()
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
    elif phase not in MIGRATION_ALLOWED_PHASES:
        errors.append("migration review requires recorded phase design-derivation or implementation")
    if reviewed is not True:
        errors.append("--reviewed is required")

    scope, scope_bytes, scope_errors = _load_json_file(root, MIGRATION_SCOPE_REL, "migration review scope")
    errors.extend(scope_errors)
    mode = "unknown"
    source_paths: list[str] = []
    if not scope_errors:
        mode, source_paths, scope_validation_errors = _validate_scope_document(root, scope)
        errors.extend(scope_validation_errors)

    input_docs: dict[str, dict[str, Any]] = {}
    input_bytes: dict[str, bytes] = {}
    acceptances: list[dict[str, Any]] = []
    if mode == "required":
        for key, rel in MIGRATION_INPUT_PATHS.items():
            document, content, input_errors = _load_json_file(root, rel, f"migration {key}")
            input_docs[key] = document
            input_bytes[key] = content
            errors.extend(input_errors)
        if all(key in input_docs and input_docs[key] for key in MIGRATION_INPUT_PATHS):
            errors.extend(_validate_database_schema(input_docs["schema_before"], "schema-before", allow_empty=True))
            errors.extend(_validate_database_schema(input_docs["schema_after"], "schema-after", allow_empty=False))
            if _canonical_json(input_docs["schema_before"]) == _canonical_json(input_docs["schema_after"]):
                errors.append("migration schema-before and schema-after must differ")
            spec_sources, spec_errors = _validate_migration_spec(root, input_docs["migration_spec"])
            source_paths.extend(spec_sources)
            errors.extend(spec_errors)
            acceptances, acceptance_errors = _validate_acceptance_document(input_docs["compatibility_acceptances"])
            errors.extend(acceptance_errors)
    elif mode == "not-applicable":
        for rel in (*MIGRATION_INPUT_PATHS.values(), *MIGRATION_REPORT_PATHS.values()):
            if (root / rel).exists() or (root / rel).is_symlink():
                errors.append(
                    "not-applicable migration scope requires removing obsolete migration artifact: "
                    f"{rel.as_posix()}"
                )

    authority_skills, tool_paths, authority_tools, authority_errors = _authority_bundle(root, skill_roots)
    errors.extend(authority_errors)

    migration_plan: dict[str, Any] = {}
    compatibility_report: dict[str, Any] = {}
    rollback_runbook: dict[str, Any] = {}
    tool_runs: list[dict[str, object]] = []
    compatibility_status = "not-applicable" if mode == "not-applicable" else "unknown"
    unaccepted_issues: list[dict[str, object]] = []
    acceptance_source_paths: list[str] = []
    tool_blocking_errors = list(errors)
    if mode == "required" and not tool_blocking_errors and tool_paths:
        (
            migration_plan,
            compatibility_report,
            rollback_runbook,
            tool_runs,
            tool_errors,
        ) = _run_authority_tools(tool_paths, input_bytes)
        errors.extend(tool_errors)
        if not tool_errors:
            (
                compatibility_status,
                unaccepted_issues,
                acceptance_source_paths,
                acceptance_errors,
            ) = _apply_compatibility_acceptances(root, compatibility_report, acceptances)
            errors.extend(acceptance_errors)
    source_paths.extend(acceptance_source_paths)

    report_payloads = {
        "migration_plan": migration_plan,
        "compatibility_report": compatibility_report,
        "rollback_runbook": rollback_runbook,
    }
    report_bytes = {
        key: (_pretty_json(payload) if payload else b"")
        for key, payload in report_payloads.items()
    }
    source_snapshots, snapshot_errors = _snapshot_paths(root, source_paths, "migration review source")
    errors.extend(snapshot_errors)
    input_snapshots = {
        key: _snapshot_bytes(MIGRATION_INPUT_PATHS[key], input_bytes.get(key, b""))
        for key in MIGRATION_INPUT_PATHS
        if input_bytes.get(key)
    }
    report_snapshots = {
        key: _snapshot_bytes(MIGRATION_REPORT_PATHS[key], report_bytes[key])
        for key in MIGRATION_REPORT_PATHS
        if report_bytes.get(key)
    }
    serious_issue_count = len(_serious_issues(compatibility_report))
    summary = {
        "compatibility": compatibility_status,
        "compatibility_issue_count": serious_issue_count,
        "accepted_issue_count": serious_issue_count - len(unaccepted_issues),
        "migration_phase_count": len(_dict_items(migration_plan.get("phases"))),
        "rollback_phase_count": len(_dict_items(rollback_runbook.get("rollback_phases"))),
        "tool_run_count": len(tool_runs),
    } if mode == "required" else {
        "compatibility": "not-applicable",
        "compatibility_issue_count": 0,
        "accepted_issue_count": 0,
        "migration_phase_count": 0,
        "rollback_phase_count": 0,
        "tool_run_count": 0,
    }
    report_summaries = {
        "migration_id": str(migration_plan.get("migration_id", "")),
        "compatibility": compatibility_status,
        "compatibility_issue_count": serious_issue_count,
        "rollback_runbook_id": str(rollback_runbook.get("runbook_id", "")),
    }
    existing, existing_errors = _load_optional_evidence(root)
    candidate_without_time = {
        "decision_policy": MIGRATION_DECISION_POLICY,
        "mode": mode,
        "reviewed": reviewed is True,
        "scope_snapshot": _snapshot_bytes(MIGRATION_SCOPE_REL, scope_bytes) if scope_bytes else {},
        "input_snapshots": input_snapshots if mode == "required" else {},
        "source_snapshots": source_snapshots,
        "authority_skills": authority_skills,
        "authority_tools": authority_tools,
        "reports": report_snapshots if mode == "required" else {},
        "summary": summary,
    }
    recorded_at = utc_now()
    if (
        not existing_errors
        and all(existing.get(key) == value for key, value in candidate_without_time.items())
        and isinstance(existing.get("recorded_at"), str)
    ):
        recorded_at = str(existing["recorded_at"])
    evidence = {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        **candidate_without_time,
        "recorded_at": recorded_at,
    }
    evidence_bytes = _pretty_json(evidence)
    outputs: dict[str, bytes] = {}
    if mode == "required" and all(report_bytes.values()) and not errors:
        outputs.update(
            {MIGRATION_REPORT_PATHS[key].as_posix(): report_bytes[key] for key in MIGRATION_REPORT_PATHS}
        )
    if mode in MIGRATION_MODES and not errors:
        outputs[MIGRATION_EVIDENCE_REL.as_posix()] = evidence_bytes
    for rel in outputs:
        errors.extend(_output_path_errors(root, Path(rel)))
    would_update = (
        [rel for rel, content in sorted(outputs.items()) if _current_bytes(root / rel) != content]
        if not errors
        else []
    )
    return _MigrationReviewPlan(
        target=str(root),
        reviewed=reviewed is True,
        mode=mode,
        compatibility_status=compatibility_status,
        errors=_dedupe_strings(errors),
        warnings=_dedupe_strings(warnings),
        evidence=evidence,
        tool_runs=tool_runs,
        unaccepted_issues=unaccepted_issues,
        report_summaries=report_summaries,
        outputs=outputs,
        would_update=would_update,
        state=state,
    )


def _validate_scope_document(root: Path, document: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    errors: list[str] = []
    if document.get("schema_version") != MIGRATION_SCHEMA_VERSION:
        errors.append(f"migration scope schema_version must be {MIGRATION_SCHEMA_VERSION}")
    applicability = document.get("applicability")
    if not isinstance(applicability, dict):
        errors.append("migration scope applicability must be an object")
        applicability = {}
    mode = str(applicability.get("decision", "unknown"))
    if mode not in MIGRATION_MODES:
        errors.append(f"migration applicability decision must be one of {', '.join(MIGRATION_MODES)}")
        mode = "unknown"
    for field_name in ("owner", "reason"):
        if not _concrete_text(applicability.get(field_name)):
            errors.append(f"migration applicability.{field_name} must be concrete text")
    if not _concrete_string_list(applicability.get("revisit_triggers")):
        errors.append("migration applicability.revisit_triggers must contain concrete review triggers")
    source_paths, source_errors = _validate_source_references(
        root, applicability.get("source_references"), "migration applicability"
    )
    errors.extend(source_errors)
    review = document.get("review")
    if not isinstance(review, dict):
        errors.append("migration scope review must be an object")
        review = {}
    for field_name in ("owner", "reason"):
        if not _concrete_text(review.get(field_name)):
            errors.append(f"migration review.{field_name} must be concrete text")
    review_sources, review_errors = _validate_source_references(root, review.get("source_references"), "migration review")
    source_paths.extend(review_sources)
    errors.extend(review_errors)
    missing = set(MIGRATION_REQUIRED_SOURCE_PATHS) - set(source_paths)
    for rel in sorted(missing):
        errors.append(f"migration scope must reference required data-model source: {rel}")
    if not any(ACCEPTANCE_PATH_RE.fullmatch(path) for path in source_paths):
        errors.append("migration scope must reference a product acceptance chapter")
    return mode, _dedupe_strings(source_paths), _dedupe_strings(errors)


def _validate_database_schema(document: dict[str, Any], label: str, *, allow_empty: bool) -> list[str]:
    errors: list[str] = []
    if not _concrete_text(str(document.get("schema_version", ""))):
        errors.append(f"migration {label}.schema_version must be concrete")
    if not _concrete_text(document.get("database")):
        errors.append(f"migration {label}.database must be concrete text")
    tables = document.get("tables")
    if not isinstance(tables, dict):
        return [*errors, f"migration {label}.tables must be an object"]
    if not allow_empty and not tables:
        errors.append(f"migration {label}.tables must define at least one table")
    for table_name, table in tables.items():
        prefix = f"migration {label}.tables.{table_name}"
        if not isinstance(table_name, str) or IDENTIFIER_RE.fullmatch(table_name) is None:
            errors.append(f"{prefix} uses an invalid table identifier")
        if not isinstance(table, dict):
            errors.append(f"{prefix} must be an object")
            continue
        columns = table.get("columns")
        if not isinstance(columns, dict) or not columns:
            errors.append(f"{prefix}.columns must be a non-empty object")
            continue
        for column_name, column in columns.items():
            column_prefix = f"{prefix}.columns.{column_name}"
            if not isinstance(column_name, str) or IDENTIFIER_RE.fullmatch(column_name) is None:
                errors.append(f"{column_prefix} uses an invalid column identifier")
            if not isinstance(column, dict):
                errors.append(f"{column_prefix} must be an object")
                continue
            if not _concrete_text(column.get("type")):
                errors.append(f"{column_prefix}.type must be concrete text")
            if not isinstance(column.get("nullable"), bool):
                errors.append(f"{column_prefix}.nullable must be a boolean")
    return _dedupe_strings(errors)


def _validate_migration_spec(root: Path, document: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if document.get("type") != "database":
        errors.append("migration specification type must be database")
    for field_name in ("pattern", "source", "target", "description"):
        if not _concrete_text(document.get(field_name)):
            errors.append(f"migration specification {field_name} must be concrete text")
    if not isinstance(document.get("constraints"), dict):
        errors.append("migration specification constraints must be an object")
    governance = document.get("governance")
    if not isinstance(governance, dict):
        errors.append("migration specification governance must be an object")
        governance = {}
    for field_name in ("owner", "strategy_rationale", "validation_plan"):
        if not _concrete_text(governance.get(field_name)):
            errors.append(f"migration specification governance.{field_name} must be concrete text")
    sources, source_errors = _validate_source_references(
        root, governance.get("source_references"), "migration specification governance"
    )
    errors.extend(source_errors)
    return sources, _dedupe_strings(errors)


def _validate_acceptance_document(document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if document.get("schema_version") != MIGRATION_SCHEMA_VERSION:
        errors.append(f"migration compatibility acceptances schema_version must be {MIGRATION_SCHEMA_VERSION}")
    decisions = document.get("decisions")
    if not isinstance(decisions, list):
        return [], [*errors, "migration compatibility acceptances decisions must be a list"]
    if len(decisions) > MIGRATION_MAX_ACCEPTANCES:
        errors.append(f"migration compatibility acceptances cannot exceed {MIGRATION_MAX_ACCEPTANCES} decisions")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(decisions):
        label = f"migration compatibility acceptances decisions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        issue_id = item.get("issue_id")
        if not isinstance(issue_id, str) or ISSUE_ID_RE.fullmatch(issue_id) is None:
            errors.append(f"{label}.issue_id is invalid")
        elif issue_id in seen:
            errors.append(f"migration compatibility acceptance is duplicated: {issue_id}")
        else:
            seen.add(issue_id)
        for field_name in ("owner", "reason", "mitigation"):
            if not _concrete_text(item.get(field_name)):
                errors.append(f"{label}.{field_name} must be concrete text")
        if not isinstance(item.get("evidence"), list) or not item.get("evidence"):
            errors.append(f"{label}.evidence must be a non-empty list")
        normalized.append(copy.deepcopy(item))
    return normalized, _dedupe_strings(errors)


def _apply_compatibility_acceptances(
    root: Path,
    report: dict[str, Any],
    acceptances: list[dict[str, Any]],
) -> tuple[str, list[dict[str, object]], list[str], list[str]]:
    serious = _serious_issues(report)
    by_id = {str(item.get("issue_id", "")): item for item in serious}
    decisions = {str(item.get("issue_id", "")): item for item in acceptances}
    errors: list[str] = []
    source_paths: list[str] = []
    for issue_id in sorted(set(decisions) - set(by_id)):
        errors.append(f"migration compatibility acceptance is orphaned: {issue_id}")
    unaccepted: list[dict[str, object]] = []
    for issue in serious:
        issue_id = str(issue.get("issue_id", ""))
        decision = decisions.get(issue_id)
        if decision is None:
            unaccepted.append(
                {
                    "issue_id": issue_id,
                    "severity": str(issue.get("severity", "")),
                    "field_path": str(issue.get("field_path", "")),
                    "description": str(issue.get("description", "")),
                }
            )
            errors.append(f"migration compatibility issue requires written acceptance: {issue_id}")
            issue["acceptance_status"] = "missing"
            continue
        evidence_paths, evidence_errors = _validate_source_references(
            root, decision.get("evidence"), f"migration compatibility acceptance {issue_id}"
        )
        errors.extend(evidence_errors)
        source_paths.extend(evidence_paths)
        issue["acceptance_status"] = "accepted"
        issue["acceptance"] = {
            "owner": str(decision.get("owner", "")),
            "reason": str(decision.get("reason", "")),
            "mitigation": str(decision.get("mitigation", "")),
            "evidence": evidence_paths,
        }
    if unaccepted or errors:
        status = str(report.get("overall_compatibility", "unknown"))
    elif serious:
        status = "accepted_with_mitigations"
    else:
        status = str(report.get("overall_compatibility", "unknown"))
        if status not in {"fully_compatible", "backward_compatible"}:
            errors.append(f"migration compatibility status is not acceptable: {status}")
    report["governance_compatibility_status"] = status
    return status, unaccepted, _dedupe_strings(source_paths), _dedupe_strings(errors)


def _authority_bundle(
    root: Path,
    skill_roots: list[Path],
) -> tuple[list[dict[str, str]], dict[str, Path], list[dict[str, str]], list[str]]:
    try:
        try:
            from .authority_skills import build_authority_skill_inventory
        except ImportError:  # pragma: no cover - direct script execution
            from authority_skills import build_authority_skill_inventory
        preferred = [root / ".agents/skills", root / ".codex/skills", *skill_roots]
        inventory = build_authority_skill_inventory(
            skill_roots=preferred,
            strict=False,
            include_default_skill_roots=False,
        )
        matches = _authority_inventory_matches(inventory)
        if set(matches) != set(MIGRATION_AUTHORITY_SKILLS):
            inventory = build_authority_skill_inventory(
                skill_roots=preferred,
                strict=False,
                include_default_skill_roots=True,
            )
            matches = _authority_inventory_matches(inventory)
    except (OSError, RuntimeError) as error:
        return [], {}, [], [f"authority skill inventory failed: {error}"]
    authorities: list[dict[str, str]] = []
    errors: list[str] = []
    migration_skill_path: Path | None = None
    for name in MIGRATION_AUTHORITY_SKILLS:
        match = matches.get(name, {})
        skill_path_text = str(match.get("skill_path", ""))
        if not skill_path_text:
            errors.append(f"required authority skill is unavailable for migration review: {name}")
            continue
        skill_path = Path(skill_path_text)
        content, error = _read_utf8_file(skill_path, f"migration authority skill {name}")
        if error:
            errors.append(error)
            continue
        authorities.append(
            {
                "name": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "availability_scope": "agent-environment",
            }
        )
        if name == "migration-architect":
            migration_skill_path = skill_path
    tool_paths: dict[str, Path] = {}
    tools: list[dict[str, str]] = []
    if migration_skill_path is not None:
        for name, filename in MIGRATION_TOOL_FILES.items():
            path = migration_skill_path.parent / "scripts" / filename
            if path.is_symlink() or not path.is_file():
                errors.append(f"migration authority tool is missing or unsafe: {filename}")
                continue
            content, error = _read_utf8_file(path, f"migration authority tool {filename}")
            if error:
                errors.append(error)
                continue
            tool_paths[name] = path
            tools.append({"name": name, "file": filename, "sha256": hashlib.sha256(content).hexdigest()})
    authorities.sort(key=lambda item: item["name"])
    tools.sort(key=lambda item: item["name"])
    return authorities, tool_paths, tools, _dedupe_strings(errors)


def _authority_inventory_matches(inventory: dict[str, object]) -> dict[str, dict[str, object]]:
    skills = inventory.get("skills")
    if not isinstance(skills, list):
        return {}
    return {
        str(item.get("name", "")): item
        for item in skills
        if isinstance(item, dict)
        and item.get("name") in MIGRATION_AUTHORITY_SKILLS
        and item.get("available_in_agent_environment") is True
    }


def _run_authority_tools(
    tool_paths: dict[str, Path],
    input_bytes: dict[str, bytes],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, object]],
    list[str],
]:
    try:
        workspace = tempfile.TemporaryDirectory(prefix="governance-migration-review-")
    except OSError as error:
        return {}, {}, {}, [], [f"migration review workspace could not be created: {_os_error_reason(error)}"]
    try:
        with workspace as temporary_text:
            return _run_authority_tools_in_workspace(Path(temporary_text), tool_paths, input_bytes)
    except OSError as error:
        return {}, {}, {}, [], [f"migration review workspace write failed: {_os_error_reason(error)}"]


def _run_authority_tools_in_workspace(
    temporary: Path,
    tool_paths: dict[str, Path],
    input_bytes: dict[str, bytes],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, object]],
    list[str],
]:
    runs: list[dict[str, object]] = []
    errors: list[str] = []
    input_paths: dict[str, Path] = {}
    for key, content in input_bytes.items():
        path = temporary / MIGRATION_INPUT_PATHS[key].name
        path.write_bytes(content)
        input_paths[key] = path
    raw_plan_path = temporary / "raw-migration-plan.json"
    run, run_errors = _run_file_tool(
        tool_paths["migration_planner"],
        ["--input", str(input_paths["migration_spec"]), "--format", "json", "--output", str(raw_plan_path)],
        temporary,
        "migration_planner",
        raw_plan_path,
        allowed_returncodes={0},
    )
    runs.append(run)
    errors.extend(run_errors)
    raw_plan, load_errors = _load_external_json(raw_plan_path, "migration planner output")
    errors.extend(load_errors)
    migration_plan, normalize_errors = _normalize_migration_plan(raw_plan)
    errors.extend(normalize_errors)

    compatibility_path = temporary / "raw-compatibility-report.json"
    run, run_errors = _run_file_tool(
        tool_paths["compatibility_checker"],
        [
            "--before", str(input_paths["schema_before"]),
            "--after", str(input_paths["schema_after"]),
            "--type", "database",
            "--format", "json",
            "--output", str(compatibility_path),
        ],
        temporary,
        "compatibility_checker",
        compatibility_path,
        allowed_returncodes={0, 1, 2},
    )
    runs.append(run)
    errors.extend(run_errors)
    raw_compatibility, load_errors = _load_external_json(compatibility_path, "compatibility checker output")
    errors.extend(load_errors)
    compatibility_report, normalize_errors = _normalize_compatibility_report(raw_compatibility)
    errors.extend(normalize_errors)
    errors.extend(_compatibility_returncode_errors(run, compatibility_report))

    rollback_runbook: dict[str, Any] = {}
    if migration_plan:
        normalized_plan_path = temporary / "normalized-migration-plan.json"
        normalized_plan_path.write_bytes(_pretty_json(migration_plan))
        rollback_path = temporary / "raw-rollback-runbook.json"
        run, run_errors = _run_file_tool(
            tool_paths["rollback_generator"],
            ["--input", str(normalized_plan_path), "--format", "json", "--output", str(rollback_path)],
            temporary,
            "rollback_generator",
            rollback_path,
            allowed_returncodes={0},
        )
        runs.append(run)
        errors.extend(run_errors)
        raw_rollback, load_errors = _load_external_json(rollback_path, "rollback generator output")
        errors.extend(load_errors)
        rollback_runbook, normalize_errors = _normalize_rollback_runbook(raw_rollback, migration_plan)
        errors.extend(normalize_errors)
    return migration_plan, compatibility_report, rollback_runbook, runs, _dedupe_strings(errors)


def _run_file_tool(
    path: Path,
    arguments: list[str],
    cwd: Path,
    name: str,
    output: Path,
    *,
    allowed_returncodes: set[int],
) -> tuple[dict[str, object], list[str]]:
    try:
        completed = subprocess.run(
            [sys.executable, str(path), *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=MIGRATION_TOOL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"tool": name, "returncode": -1, "stderr": str(error)[:1000]}, [
            f"migration authority tool {name} failed: {error}"
        ]
    run = {
        "tool": name,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip()[:1000],
        "stderr": completed.stderr.strip()[:1000],
    }
    errors: list[str] = []
    if completed.returncode not in allowed_returncodes:
        errors.append(f"migration authority tool {name} returned {completed.returncode}")
    if output.is_symlink() or not output.is_file():
        errors.append(f"migration authority tool {name} did not create a safe JSON output")
    elif output.stat().st_size > MIGRATION_MAX_JSON_BYTES:
        errors.append(f"migration authority tool {name} output exceeds size limit")
    return run, errors


def _normalize_migration_plan(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(payload)
    normalized.pop("created_at", None)
    errors: list[str] = []
    for field_name in ("migration_id", "source_system", "target_system", "migration_type", "complexity"):
        if not _concrete_text(normalized.get(field_name)):
            errors.append(f"migration planner output {field_name} must be concrete text")
    if normalized.get("migration_type") != "database":
        errors.append("migration planner output migration_type must be database")
    duration = normalized.get("estimated_duration_hours")
    if not _non_negative_number(duration):
        errors.append("migration planner output estimated_duration_hours is invalid")
    phases = normalized.get("phases")
    if not isinstance(phases, list) or not phases or not all(isinstance(item, dict) for item in phases):
        errors.append("migration planner output phases must be a non-empty object list")
    for field_name in ("risks", "success_criteria", "stakeholders"):
        if not isinstance(normalized.get(field_name), list) or not normalized.get(field_name):
            errors.append(f"migration planner output {field_name} must be a non-empty list")
    if not isinstance(normalized.get("rollback_plan"), dict):
        errors.append("migration planner output rollback_plan must be an object")
    return normalized, _dedupe_strings(errors)


def _normalize_compatibility_report(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(payload)
    for field_name in ("analysis_date", "schema_before", "schema_after"):
        normalized.pop(field_name, None)
    errors: list[str] = []
    overall = normalized.get("overall_compatibility")
    if overall not in {
        "fully_compatible", "backward_compatible", "potentially_incompatible", "breaking_changes"
    }:
        errors.append("compatibility checker output overall_compatibility is invalid")
    issues = normalized.get("issues")
    if not isinstance(issues, list) or not all(isinstance(item, dict) for item in issues):
        errors.append("compatibility checker output issues must be an object list")
        issues = []
    issue_ids: set[str] = set()
    for issue in issues:
        issue["issue_id"] = _compatibility_issue_id(issue)
        issue_id = str(issue["issue_id"])
        if issue_id in issue_ids:
            errors.append(f"compatibility checker output contains duplicate issue: {issue_id}")
        issue_ids.add(issue_id)
        for field_name in ("type", "severity", "description", "field_path", "impact", "suggested_migration"):
            if not _concrete_text(issue.get(field_name)):
                errors.append(f"compatibility issue {issue['issue_id']} {field_name} must be concrete text")
        if issue.get("severity") not in {"breaking", "potentially_breaking", "non_breaking"}:
            errors.append(f"compatibility issue {issue['issue_id']} severity is invalid")
    expected_breaking = sum(1 for item in issues if item.get("severity") == "breaking")
    expected_potential = sum(1 for item in issues if item.get("severity") == "potentially_breaking")
    if normalized.get("breaking_changes_count") != expected_breaking:
        errors.append("compatibility checker breaking_changes_count does not match issues")
    if normalized.get("potentially_breaking_count") != expected_potential:
        errors.append("compatibility checker potentially_breaking_count does not match issues")
    for field_name in ("non_breaking_changes_count", "additive_changes_count"):
        if not _non_negative_int(normalized.get(field_name)):
            errors.append(f"compatibility checker output {field_name} is invalid")
    for field_name in ("migration_scripts", "recommendations"):
        if not isinstance(normalized.get(field_name), list):
            errors.append(f"compatibility checker output {field_name} must be a list")
    if not isinstance(normalized.get("risk_assessment"), dict):
        errors.append("compatibility checker output risk_assessment must be an object")
    return normalized, _dedupe_strings(errors)


def _compatibility_returncode_errors(
    run: dict[str, object],
    report: dict[str, Any],
) -> list[str]:
    breaking = report.get("breaking_changes_count")
    potentially_breaking = report.get("potentially_breaking_count")
    if not _non_negative_int(breaking) or not _non_negative_int(potentially_breaking):
        return []
    expected = 2 if breaking > 0 else 1 if potentially_breaking > 0 else 0
    if run.get("returncode") == expected:
        return []
    return [
        "compatibility checker return code does not match compatibility report: "
        f"expected {expected}, got {run.get('returncode')}"
    ]


def _normalize_rollback_runbook(
    payload: dict[str, Any],
    migration_plan: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(payload)
    normalized.pop("created_at", None)
    errors: list[str] = []
    if not _concrete_text(normalized.get("runbook_id")):
        errors.append("rollback generator output runbook_id must be concrete text")
    if normalized.get("migration_id") != migration_plan.get("migration_id"):
        errors.append("rollback generator migration_id does not match migration plan")
    phases = normalized.get("rollback_phases")
    if not isinstance(phases, list) or not phases or not all(isinstance(item, dict) for item in phases):
        errors.append("rollback generator output rollback_phases must be a non-empty object list")
    if isinstance(phases, list) and len(phases) < len(_dict_items(migration_plan.get("phases"))):
        errors.append("rollback generator must cover every migration phase")
    for field_name in ("trigger_conditions", "communication_templates", "emergency_contacts"):
        values = normalized.get(field_name)
        if not isinstance(values, list) or not values or not all(isinstance(item, dict) for item in values):
            errors.append(f"rollback generator output {field_name} must be a non-empty object list")
    for field_name in ("validation_checklist", "post_rollback_procedures"):
        values = normalized.get(field_name)
        if not isinstance(values, list) or not values or not all(_concrete_text(item) for item in values):
            errors.append(f"rollback generator output {field_name} must be a non-empty concrete text list")
    for field_name in ("data_recovery_plan", "escalation_matrix"):
        if not isinstance(normalized.get(field_name), dict):
            errors.append(f"rollback generator output {field_name} must be an object")
    return normalized, _dedupe_strings(errors)


def _compatibility_issue_id(issue: dict[str, Any]) -> str:
    identity = {
        key: copy.deepcopy(issue.get(key))
        for key in (
            "type", "severity", "description", "field_path", "old_value", "new_value", "impact",
            "suggested_migration", "affected_operations",
        )
    }
    digest = hashlib.sha256(_canonical_json(identity)).hexdigest()[:12]
    return f"migration-compat-{digest}"


def _serious_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    issues = report.get("issues")
    if not isinstance(issues, list):
        return []
    return [
        item
        for item in issues
        if isinstance(item, dict) and item.get("severity") in MIGRATION_SERIOUS_SEVERITIES
    ]


def _validate_evidence_document(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != MIGRATION_SCHEMA_VERSION:
        errors.append(f"migration evidence schema_version must be {MIGRATION_SCHEMA_VERSION}")
    if document.get("decision_policy") != MIGRATION_DECISION_POLICY:
        errors.append("migration evidence decision_policy is invalid")
    mode = document.get("mode")
    if mode not in MIGRATION_MODES:
        errors.append("migration evidence mode is invalid")
    if document.get("reviewed") is not True:
        errors.append("migration evidence reviewed must be true")
    errors.extend(_validate_snapshot(document.get("scope_snapshot"), MIGRATION_SCOPE_REL, "scope_snapshot"))
    sources = document.get("source_snapshots")
    if not isinstance(sources, list) or not sources:
        errors.append("migration evidence source_snapshots must be a non-empty list")
    else:
        for index, snapshot in enumerate(sources):
            if not isinstance(snapshot, dict):
                errors.append(f"migration evidence source_snapshots[{index}] must be an object")
                continue
            _, path_error = _safe_relative_path(str(snapshot.get("path", "")))
            if path_error:
                errors.append(f"migration source snapshot path is invalid: {snapshot.get('path', '<missing>')}")
            _validate_digest(snapshot.get("sha256"), "migration source snapshot", errors)
    authorities = document.get("authority_skills")
    if not isinstance(authorities, list):
        errors.append("migration evidence authority_skills must be a list")
    else:
        by_name = {str(item.get("name", "")): item for item in authorities if isinstance(item, dict)}
        if set(by_name) != set(MIGRATION_AUTHORITY_SKILLS):
            errors.append("migration evidence must bind database-schema-designer and migration-architect")
        for name, item in by_name.items():
            if item.get("availability_scope") != "agent-environment":
                errors.append(f"migration authority skill availability_scope is invalid: {name}")
            _validate_digest(item.get("sha256"), f"migration authority skill {name}", errors)
    tools = document.get("authority_tools")
    if not isinstance(tools, list):
        errors.append("migration evidence authority_tools must be a list")
    else:
        by_name = {str(item.get("name", "")): item for item in tools if isinstance(item, dict)}
        if set(by_name) != set(MIGRATION_TOOL_FILES):
            errors.append("migration evidence must bind all migration-architect tools")
        for name, item in by_name.items():
            if item.get("file") != MIGRATION_TOOL_FILES.get(name):
                errors.append(f"migration authority tool file is invalid: {name}")
            _validate_digest(item.get("sha256"), f"migration authority tool {name}", errors)
    inputs = document.get("input_snapshots")
    reports = document.get("reports")
    if mode == "required":
        if not isinstance(inputs, dict):
            errors.append("required migration evidence input_snapshots must be an object")
            inputs = {}
        if not isinstance(reports, dict):
            errors.append("required migration evidence reports must be an object")
            reports = {}
        for key, rel in MIGRATION_INPUT_PATHS.items():
            errors.extend(_validate_snapshot(inputs.get(key), rel, f"input_snapshots.{key}"))
        for key, rel in MIGRATION_REPORT_PATHS.items():
            errors.extend(_validate_snapshot(reports.get(key), rel, f"reports.{key}"))
    else:
        if inputs:
            errors.append("not-applicable migration evidence must not contain input snapshots")
        if reports:
            errors.append("not-applicable migration evidence must not contain reports")
    summary = document.get("summary")
    if not isinstance(summary, dict):
        errors.append("migration evidence summary must be an object")
    else:
        for field_name in (
            "compatibility_issue_count", "accepted_issue_count", "migration_phase_count",
            "rollback_phase_count", "tool_run_count",
        ):
            if not _non_negative_int(summary.get(field_name)):
                errors.append(f"migration evidence summary.{field_name} is invalid")
        if mode == "required":
            if summary.get("compatibility") not in MIGRATION_COMPATIBILITY_LEVELS:
                errors.append("migration evidence summary.compatibility is not approved")
            if summary.get("accepted_issue_count") != summary.get("compatibility_issue_count"):
                errors.append("migration evidence must accept every serious compatibility issue")
            if summary.get("migration_phase_count", 0) <= 0 or summary.get("rollback_phase_count", 0) <= 0:
                errors.append("migration evidence must include migration and rollback phases")
            if summary.get("tool_run_count") != len(MIGRATION_TOOL_FILES):
                errors.append("migration evidence must record all authority tool runs")
        elif any(summary.get(name) != 0 for name in (
            "compatibility_issue_count", "accepted_issue_count", "migration_phase_count",
            "rollback_phase_count", "tool_run_count",
        )) or summary.get("compatibility") != "not-applicable":
            errors.append("not-applicable migration evidence summary must be empty")
    recorded_at = document.get("recorded_at")
    if not isinstance(recorded_at, str) or not _valid_timestamp(recorded_at):
        errors.append("migration evidence recorded_at must be an ISO-8601 timestamp")
    return _dedupe_strings(errors)


def _persisted_report_errors(root: Path, evidence: dict[str, object]) -> list[str]:
    if evidence.get("mode") != "required":
        return []
    migration_plan, plan_errors = _load_json_object(root, MIGRATION_PLAN_REL, "migration plan report")
    compatibility_report, compatibility_errors = _load_json_object(
        root, MIGRATION_COMPATIBILITY_REL, "migration compatibility report"
    )
    rollback_runbook, rollback_errors = _load_json_object(root, MIGRATION_ROLLBACK_REL, "migration rollback runbook")
    errors = [*plan_errors, *compatibility_errors, *rollback_errors]
    if not plan_errors:
        migration_plan, normalize_errors = _normalize_migration_plan(migration_plan)
        errors.extend(normalize_errors)
    if not compatibility_errors:
        compatibility_report, normalize_errors = _normalize_compatibility_report(compatibility_report)
        errors.extend(normalize_errors)
    if not rollback_errors and migration_plan:
        rollback_runbook, normalize_errors = _normalize_rollback_runbook(rollback_runbook, migration_plan)
        errors.extend(normalize_errors)
    if errors:
        return _dedupe_strings(errors)

    summary = evidence.get("summary")
    if not isinstance(summary, dict):
        return []
    serious = _serious_issues(compatibility_report)
    accepted_count = 0
    for issue in serious:
        issue_id = str(issue.get("issue_id", ""))
        acceptance = issue.get("acceptance")
        if issue.get("acceptance_status") != "accepted" or not isinstance(acceptance, dict):
            errors.append(f"persisted compatibility issue is not explicitly accepted: {issue_id}")
            continue
        for field_name in ("owner", "reason", "mitigation"):
            if not _concrete_text(acceptance.get(field_name)):
                errors.append(f"persisted compatibility issue {issue_id} acceptance.{field_name} is invalid")
        evidence_paths, evidence_errors = _validate_source_references(
            root, acceptance.get("evidence"), f"persisted compatibility issue {issue_id} acceptance"
        )
        errors.extend(evidence_errors)
        if not evidence_errors and evidence_paths:
            accepted_count += 1
    comparisons = (
        ("compatibility_issue_count", len(serious)),
        ("accepted_issue_count", accepted_count),
        ("migration_phase_count", len(_dict_items(migration_plan.get("phases")))),
        ("rollback_phase_count", len(_dict_items(rollback_runbook.get("rollback_phases")))),
    )
    for field_name, expected in comparisons:
        if summary.get(field_name) != expected:
            errors.append(
                f"migration evidence summary.{field_name} does not match generated reports: "
                f"expected {expected}, got {summary.get(field_name)}"
            )
    report_status = compatibility_report.get("governance_compatibility_status")
    if report_status != summary.get("compatibility"):
        errors.append(
            "migration evidence summary.compatibility does not match compatibility report: "
            f"expected {report_status}, got {summary.get('compatibility')}"
        )
    return _dedupe_strings(errors)


def _evidence_stale_reasons(root: Path, evidence: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    snapshots: list[object] = [evidence.get("scope_snapshot")]
    for key in ("input_snapshots", "reports"):
        values = evidence.get(key)
        if isinstance(values, dict):
            snapshots.extend(values.values())
    sources = evidence.get("source_snapshots")
    if isinstance(sources, list):
        snapshots.extend(sources)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        rel = str(snapshot.get("path", ""))
        path = root / rel
        if path.is_symlink() or not path.is_file():
            reasons.append(f"migration evidence source is missing or unsafe: {rel or '<missing>'}")
            continue
        try:
            content = path.read_bytes()
        except OSError:
            reasons.append(f"migration evidence source is unreadable: {rel}")
            continue
        if hashlib.sha256(content).hexdigest() != snapshot.get("sha256"):
            reasons.append(f"migration evidence source changed after review: {rel}")
    current_authorities, _paths, current_tools, authority_errors = _authority_bundle(root, [])
    recorded_authorities = {
        str(item.get("name", "")): str(item.get("sha256", ""))
        for item in evidence.get("authority_skills", [])
        if isinstance(item, dict)
    } if isinstance(evidence.get("authority_skills"), list) else {}
    current_authority_hashes = {item["name"]: item["sha256"] for item in current_authorities}
    for name in sorted(set(recorded_authorities) | set(current_authority_hashes)):
        if recorded_authorities.get(name) != current_authority_hashes.get(name):
            reasons.append(f"migration authority skill changed after review: {name}")
    recorded_tools = {
        str(item.get("name", "")): str(item.get("sha256", ""))
        for item in evidence.get("authority_tools", [])
        if isinstance(item, dict)
    } if isinstance(evidence.get("authority_tools"), list) else {}
    current_tool_hashes = {item["name"]: item["sha256"] for item in current_tools}
    for name in sorted(set(recorded_tools) | set(current_tool_hashes)):
        if recorded_tools.get(name) != current_tool_hashes.get(name):
            reasons.append(f"migration authority tool changed after review: {name}")
    reasons.extend(f"migration authority dependency is no longer usable: {error}" for error in authority_errors)
    return _dedupe_strings(reasons)


def _validate_source_references(root: Path, value: object, label: str) -> tuple[list[str], list[str]]:
    if not isinstance(value, list) or not value:
        return [], [f"{label}.source_references must be a non-empty list"]
    paths: list[str] = []
    errors: list[str] = []
    for item in value:
        if not isinstance(item, str):
            errors.append(f"{label}.source_references must contain strings")
            continue
        normalized, path_error = _safe_relative_path(item)
        if path_error:
            errors.append(f"{label} source path is invalid: {item}: {path_error}")
            continue
        paths.append(normalized)
        errors.extend(_repository_file_errors(root, normalized, f"{label} source"))
    return _dedupe_strings(paths), _dedupe_strings(errors)


def _load_json_file(root: Path, rel: Path, label: str) -> tuple[dict[str, Any], bytes, list[str]]:
    path = root / rel
    if path.is_symlink():
        return {}, b"", [f"{label} must not be a symbolic link: {rel.as_posix()}"]
    if not path.is_file():
        return {}, b"", [f"{label} is missing: {rel.as_posix()}"]
    try:
        content = path.read_bytes()
    except OSError as error:
        return {}, b"", [f"{label} is unreadable: {_os_error_reason(error)}"]
    if len(content) > MIGRATION_MAX_JSON_BYTES:
        return {}, content, [f"{label} exceeds {MIGRATION_MAX_JSON_BYTES} bytes"]
    try:
        loaded = json.loads(content.decode("utf-8"))
    except UnicodeDecodeError:
        return {}, content, [f"{label} must be UTF-8 JSON"]
    except json.JSONDecodeError as error:
        return {}, content, [f"{label} is invalid JSON: {error.msg}"]
    if not isinstance(loaded, dict):
        return {}, content, [f"{label} root must be an object"]
    return copy.deepcopy(loaded), content, []


def _load_json_object(root: Path, rel: Path, label: str) -> tuple[dict[str, Any], list[str]]:
    document, _content, errors = _load_json_file(root, rel, label)
    return document, errors


def _load_external_json(path: Path, label: str) -> tuple[dict[str, Any], list[str]]:
    if path.is_symlink() or not path.is_file():
        return {}, [f"{label} is missing or unsafe"]
    try:
        content = path.read_bytes()
    except OSError as error:
        return {}, [f"{label} is unreadable: {_os_error_reason(error)}"]
    if len(content) > MIGRATION_MAX_JSON_BYTES:
        return {}, [f"{label} exceeds {MIGRATION_MAX_JSON_BYTES} bytes"]
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, [f"{label} must be UTF-8 JSON"]
    if not isinstance(payload, dict):
        return {}, [f"{label} root must be an object"]
    return copy.deepcopy(payload), []


def _load_optional_evidence(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = root / MIGRATION_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {}, []
    document, errors = _load_json_object(root, MIGRATION_EVIDENCE_REL, "migration review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(document))
    return document, errors


def _snapshot_paths(root: Path, paths: list[str], label: str) -> tuple[list[dict[str, str]], list[str]]:
    snapshots: list[dict[str, str]] = []
    errors: list[str] = []
    for rel in _dedupe_strings(paths):
        file_errors = _repository_file_errors(root, rel, label)
        if file_errors:
            errors.extend(file_errors)
            continue
        try:
            content = (root / rel).read_bytes()
            content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{label} must be UTF-8: {rel}")
            continue
        except OSError as error:
            errors.append(f"{label} is unreadable: {rel}: {_os_error_reason(error)}")
            continue
        snapshots.append({"path": rel, "sha256": hashlib.sha256(content).hexdigest()})
    snapshots.sort(key=lambda item: item["path"])
    return snapshots, _dedupe_strings(errors)


def _repository_file_errors(root: Path, rel: str, label: str) -> list[str]:
    normalized, path_error = _safe_relative_path(rel)
    if path_error:
        return [f"{label} path is invalid: {rel or '<missing>'}: {path_error}"]
    path = root / normalized
    current = root
    for part in Path(normalized).parts:
        current /= part
        if current.is_symlink():
            return [f"{label} path must not contain symbolic links: {normalized}"]
    try:
        path.resolve().relative_to(root)
    except (OSError, ValueError):
        return [f"{label} path resolves outside target: {normalized}"]
    if not path.is_file():
        return [f"{label} path is not a file: {normalized}"]
    return []


def _safe_relative_path(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        return "", "path is empty"
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return normalized, "path must be repository-relative and must not contain '..'"
    if normalized != path.as_posix() or normalized.startswith("./"):
        return normalized, "path must use normalized POSIX syntax"
    return normalized, ""


def _snapshot_bytes(rel: Path, content: bytes) -> dict[str, str]:
    return {"path": rel.as_posix(), "sha256": hashlib.sha256(content).hexdigest()}


def _validate_snapshot(value: object, rel: Path, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"migration evidence {label} must be an object"]
    errors: list[str] = []
    if value.get("path") != rel.as_posix():
        errors.append(f"migration evidence {label} path must be {rel.as_posix()}")
    _validate_digest(value.get("sha256"), f"migration evidence {label}", errors)
    return errors


def _validate_digest(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        errors.append(f"{label} sha256 must be a lowercase SHA-256 digest")


def _output_path_errors(root: Path, rel: Path) -> list[str]:
    path = root / rel
    current = root
    for part in rel.parts[:-1]:
        current /= part
        if current.is_symlink():
            return [f"migration output parent must not contain symbolic links: {current.relative_to(root)}"]
        if current.exists() and not current.is_dir():
            return [f"migration output parent is not a directory: {current.relative_to(root)}"]
    errors: list[str] = []
    if path.is_symlink() or (path.exists() and not path.is_file()):
        errors.append(f"migration output path is unsafe: {rel.as_posix()}")
    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        errors.append(f"migration temporary path already exists: {temp.relative_to(root)}")
    return errors


def _write_outputs_atomically(root: Path, outputs: dict[str, bytes]) -> None:
    snapshots: dict[Path, tuple[bool, bytes, int | None]] = {}
    temp_paths: list[Path] = []
    replaced: list[Path] = []
    try:
        for rel, content in outputs.items():
            path = root / rel
            errors = _output_path_errors(root, Path(rel))
            if errors:
                raise OSError(errors[0])
            if path.is_file():
                snapshots[path] = (True, path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            else:
                snapshots[path] = (False, b"", None)
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = _atomic_temp_path(path)
            temp_paths.append(temp)
            temp.write_bytes(content)
            mode = snapshots[path][2]
            if mode is not None:
                temp.chmod(mode)
        for rel in outputs:
            path = root / rel
            _atomic_temp_path(path).replace(path)
            replaced.append(path)
    except OSError as error:
        rollback_errors: list[str] = []
        for path in reversed(replaced):
            existed, content, mode = snapshots[path]
            try:
                if existed:
                    restore = _atomic_temp_path(path)
                    restore.write_bytes(content)
                    if mode is not None:
                        restore.chmod(mode)
                    restore.replace(path)
                elif path.exists() and path.is_file():
                    path.unlink()
            except OSError as rollback_error:
                rollback_errors.append(_os_error_reason(rollback_error))
        detail = f"; rollback failed: {', '.join(rollback_errors)}" if rollback_errors else ""
        raise OSError(f"{_os_error_reason(error)}{detail}") from error
    finally:
        for temp in temp_paths:
            if temp.exists() and temp.is_file():
                try:
                    temp.unlink()
                except OSError:
                    pass


def _atomic_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def _current_bytes(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        return b""
    try:
        return path.read_bytes()
    except OSError:
        return b""


def _read_utf8_file(path: Path, label: str) -> tuple[bytes, str]:
    try:
        content = path.read_bytes()
        content.decode("utf-8")
    except UnicodeDecodeError:
        return b"", f"{label} must be UTF-8"
    except OSError as error:
        return b"", f"{label} is unreadable: {_os_error_reason(error)}"
    return content, ""


def _pretty_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _dict_items(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _concrete_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value.strip()) >= 3
        and PLACEHOLDER_RE.search(value) is None
        and SCAFFOLD_PLACEHOLDER not in value
    )


def _concrete_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_concrete_text(item) for item in value)


def _non_negative_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)
