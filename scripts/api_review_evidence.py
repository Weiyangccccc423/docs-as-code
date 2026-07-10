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
from pathlib import Path
from typing import Any

try:
    from .state import StateFileError, load_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from state import StateFileError, load_state, utc_now


API_OPENAPI_REL = Path("docs/api/openapi.json")
API_BASELINE_REL = Path("docs/api/baselines/openapi-baseline.json")
API_LINT_REPORT_REL = Path("docs/api/reviews/api-lint.json")
API_BREAKING_REPORT_REL = Path("docs/api/reviews/api-breaking-changes.json")
API_SCORECARD_REPORT_REL = Path("docs/api/reviews/api-scorecard.json")
API_REVIEW_EVIDENCE_REL = Path("docs/api/reviews/review-evidence.json")
API_REVIEW_SCHEMA_VERSION = 1
API_REVIEW_DECISION_POLICY = "run_api_design_reviewer_tools_before_authority_signoff"
API_REVIEW_ALLOWED_PHASES = frozenset({"design-derivation", "implementation"})
API_REVIEW_AUTHORITY_SKILL = "api-design-reviewer"
API_REVIEW_TOOL_FILES = {
    "api_linter": "api_linter.py",
    "breaking_change_detector": "breaking_change_detector.py",
    "api_scorecard": "api_scorecard.py",
}
API_REVIEW_REPORT_PATHS = {
    "lint": API_LINT_REPORT_REL,
    "breaking_changes": API_BREAKING_REPORT_REL,
    "scorecard": API_SCORECARD_REPORT_REL,
}
API_REVIEW_GRADE_ORDER = ("F", "D", "C", "B", "A")
API_REVIEW_DEFAULT_MIN_GRADE = "B"
API_REVIEW_TOOL_TIMEOUT_SECONDS = 60
API_REVIEW_MAX_JSON_BYTES = 10 * 1024 * 1024
OPENAPI_VERSION_RE = re.compile(r"^3\.(?:0|1)\.[0-9]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"


@dataclass
class ApiReviewEvidenceResult:
    target: str
    ok: bool
    reviewed: bool
    min_grade: str
    check: bool = False
    baseline_mode: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    openapi_snapshot: dict[str, str] = field(default_factory=dict)
    tool_runs: list[dict[str, object]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("API review result target must be a non-empty string")
        if not isinstance(self.ok, bool) or not isinstance(self.reviewed, bool) or not isinstance(self.check, bool):
            raise ValueError("API review result boolean fields must be booleans")
        if self.min_grade not in API_REVIEW_GRADE_ORDER:
            raise ValueError("API review result min_grade is invalid")
        for name, values in (
            ("errors", self.errors),
            ("warnings", self.warnings),
            ("updated", self.updated),
            ("would_update", self.would_update),
        ):
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"API review result {name} must contain strings")
        if self.ok and self.errors:
            raise ValueError("API review success cannot contain errors")
        if not self.ok and not self.errors:
            raise ValueError("API review failure requires errors")
        if self.check and self.updated:
            raise ValueError("API review check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("API review write mode cannot report would_update paths")
        self.errors = list(self.errors)
        self.warnings = list(self.warnings)
        self.updated = list(self.updated)
        self.would_update = list(self.would_update)
        self.evidence = copy.deepcopy(self.evidence)
        self.openapi_snapshot = dict(self.openapi_snapshot)
        self.tool_runs = copy.deepcopy(self.tool_runs)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": "workflows/04-design-derivation.md",
            "decision_policy": API_REVIEW_DECISION_POLICY,
            "openapi_path": API_OPENAPI_REL.as_posix(),
            "baseline_path": API_BASELINE_REL.as_posix(),
            "evidence_path": API_REVIEW_EVIDENCE_REL.as_posix(),
            "reviewed": self.reviewed,
            "min_grade": self.min_grade,
            "check": self.check,
            "apply_requested": not self.check,
            "applied": bool(self.updated),
            "writes_state": not self.check,
            "baseline_mode": self.baseline_mode,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "updated": list(self.updated),
            "would_update": list(self.would_update),
            "openapi_snapshot": dict(self.openapi_snapshot),
            "evidence": copy.deepcopy(self.evidence),
            "tool_runs": copy.deepcopy(self.tool_runs),
            "state": copy.deepcopy(self.state),
        }


@dataclass
class _ApiReviewPlan:
    target: str
    reviewed: bool
    min_grade: str
    baseline_mode: str
    errors: list[str]
    warnings: list[str]
    evidence: dict[str, Any]
    openapi_snapshot: dict[str, str]
    tool_runs: list[dict[str, object]]
    outputs: dict[str, bytes]
    would_update: list[str]
    state: dict[str, Any]


def check_api_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    min_grade: str = API_REVIEW_DEFAULT_MIN_GRADE,
    skill_roots: list[Path] | None = None,
) -> ApiReviewEvidenceResult:
    plan = _build_api_review_plan(
        root,
        reviewed=reviewed,
        min_grade=min_grade,
        skill_roots=list(skill_roots or []),
    )
    return ApiReviewEvidenceResult(
        target=plan.target,
        ok=not plan.errors,
        reviewed=plan.reviewed,
        min_grade=plan.min_grade,
        check=True,
        baseline_mode=plan.baseline_mode,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        evidence=plan.evidence,
        openapi_snapshot=plan.openapi_snapshot,
        tool_runs=plan.tool_runs,
        state=plan.state,
    )


def record_api_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    min_grade: str = API_REVIEW_DEFAULT_MIN_GRADE,
    skill_roots: list[Path] | None = None,
) -> ApiReviewEvidenceResult:
    root = root.resolve()
    plan = _build_api_review_plan(
        root,
        reviewed=reviewed,
        min_grade=min_grade,
        skill_roots=list(skill_roots or []),
    )
    if plan.errors:
        return ApiReviewEvidenceResult(
            target=plan.target,
            ok=False,
            reviewed=plan.reviewed,
            min_grade=plan.min_grade,
            baseline_mode=plan.baseline_mode,
            errors=plan.errors,
            warnings=plan.warnings,
            evidence=plan.evidence,
            openapi_snapshot=plan.openapi_snapshot,
            tool_runs=plan.tool_runs,
            state=plan.state,
        )
    updated: list[str] = []
    if plan.would_update:
        try:
            _write_outputs_atomically(root, plan.outputs)
        except OSError as error:
            return ApiReviewEvidenceResult(
                target=plan.target,
                ok=False,
                reviewed=plan.reviewed,
                min_grade=plan.min_grade,
                baseline_mode=plan.baseline_mode,
                errors=[f"API review evidence is not writable: {_os_error_reason(error)}"],
                warnings=plan.warnings,
                evidence=plan.evidence,
                openapi_snapshot=plan.openapi_snapshot,
                tool_runs=plan.tool_runs,
                state=plan.state,
            )
        updated = list(plan.would_update)
    return ApiReviewEvidenceResult(
        target=plan.target,
        ok=True,
        reviewed=plan.reviewed,
        min_grade=plan.min_grade,
        baseline_mode=plan.baseline_mode,
        warnings=plan.warnings,
        updated=updated,
        evidence=plan.evidence,
        openapi_snapshot=plan.openapi_snapshot,
        tool_runs=plan.tool_runs,
        state=plan.state,
    )


def build_api_review_evidence_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    path = root / API_REVIEW_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {
            "path": API_REVIEW_EVIDENCE_REL.as_posix(),
            "exists": False,
            "ok": False,
            "status": "missing",
            "errors": [],
            "stale_reasons": [],
            "evidence": {},
        }
    evidence, errors = _load_json_object(root, API_REVIEW_EVIDENCE_REL, "API machine review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(evidence))
    stale_reasons: list[str] = []
    if not errors:
        stale_reasons.extend(_evidence_stale_reasons(root, evidence))
    return {
        "path": API_REVIEW_EVIDENCE_REL.as_posix(),
        "exists": path.is_file() and not path.is_symlink(),
        "ok": not errors and not stale_reasons,
        "status": "invalid" if errors else "stale" if stale_reasons else "current",
        "errors": _dedupe_strings(errors),
        "stale_reasons": _dedupe_strings(stale_reasons),
        "evidence": copy.deepcopy(evidence),
    }


def build_openapi_contract_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    document, content, errors = _load_openapi(root, API_OPENAPI_REL)
    return {
        "path": API_OPENAPI_REL.as_posix(),
        "exists": (root / API_OPENAPI_REL).is_file() and not (root / API_OPENAPI_REL).is_symlink(),
        "ok": not errors,
        "status": "current" if not errors else "invalid",
        "errors": _dedupe_strings(errors),
        "snapshot": _snapshot_bytes(API_OPENAPI_REL, content) if content else {},
        "document": copy.deepcopy(document),
    }


def api_review_enforcement_ready(root: Path) -> bool:
    root = root.resolve()
    for rel in (API_OPENAPI_REL, API_BASELINE_REL, API_REVIEW_EVIDENCE_REL):
        path = root / rel
        if path.exists() or path.is_symlink():
            return True
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


def api_review_required_evidence_paths() -> list[str]:
    return [
        API_OPENAPI_REL.as_posix(),
        API_BASELINE_REL.as_posix(),
        API_LINT_REPORT_REL.as_posix(),
        API_BREAKING_REPORT_REL.as_posix(),
        API_SCORECARD_REPORT_REL.as_posix(),
        API_REVIEW_EVIDENCE_REL.as_posix(),
    ]


def _build_api_review_plan(
    root: Path,
    *,
    reviewed: bool,
    min_grade: str,
    skill_roots: list[Path],
) -> _ApiReviewPlan:
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
    elif phase not in API_REVIEW_ALLOWED_PHASES:
        errors.append("API review requires recorded phase design-derivation or implementation")
    if reviewed is not True:
        errors.append("--reviewed is required")
    if min_grade not in API_REVIEW_GRADE_ORDER:
        errors.append(f"unsupported API scorecard minimum grade: {min_grade}")
        min_grade = API_REVIEW_DEFAULT_MIN_GRADE

    openapi, openapi_bytes, openapi_errors = _load_openapi(root, API_OPENAPI_REL)
    errors.extend(openapi_errors)
    openapi_snapshot = _snapshot_bytes(API_OPENAPI_REL, openapi_bytes) if openapi_bytes else {}

    existing_evidence, existing_evidence_errors = _load_optional_evidence(root)
    baseline_path = root / API_BASELINE_REL
    baseline_exists = baseline_path.exists() or baseline_path.is_symlink()
    if existing_evidence and not baseline_exists:
        errors.append("API baseline is missing; refusing to reinitialize an established API review")
    if baseline_exists:
        _baseline, baseline_bytes, baseline_errors = _load_openapi(root, API_BASELINE_REL)
        errors.extend(f"API baseline {error}" for error in baseline_errors)
    else:
        baseline_bytes = openapi_bytes
    baseline_mode = _baseline_mode(existing_evidence, openapi_bytes, baseline_bytes, baseline_exists)

    authority, tool_paths, authority_tools, authority_errors = _authority_tool_bundle(
        root,
        skill_roots,
    )
    errors.extend(authority_errors)

    report_bytes: dict[str, bytes] = {}
    report_payloads: dict[str, dict[str, Any]] = {}
    tool_runs: list[dict[str, object]] = []
    if not errors and openapi and openapi_bytes and baseline_bytes and tool_paths:
        report_bytes, report_payloads, tool_runs, tool_errors = _run_authority_tools(
            tool_paths=tool_paths,
            min_grade=min_grade,
            openapi_bytes=openapi_bytes,
            baseline_bytes=baseline_bytes,
        )
        errors.extend(tool_errors)

    report_evidence: dict[str, dict[str, object]] = {}
    if report_payloads and report_bytes:
        lint_summary, lint_errors = _lint_summary(report_payloads.get("lint", {}))
        breaking_summary, breaking_errors = _breaking_summary(report_payloads.get("breaking_changes", {}))
        scorecard_summary, scorecard_errors = _scorecard_summary(
            report_payloads.get("scorecard", {}),
            min_grade,
        )
        errors.extend(lint_errors)
        errors.extend(breaking_errors)
        errors.extend(scorecard_errors)
        summaries = {
            "lint": lint_summary,
            "breaking_changes": breaking_summary,
            "scorecard": scorecard_summary,
        }
        for key, rel in API_REVIEW_REPORT_PATHS.items():
            content = report_bytes.get(key, b"")
            if content:
                report_evidence[key] = {
                    **_snapshot_bytes(rel, content),
                    **summaries[key],
                }

    recorded_at = utc_now()
    candidate_without_time = {
        "decision_policy": API_REVIEW_DECISION_POLICY,
        "reviewed": reviewed is True,
        "min_grade": min_grade,
        "baseline_mode": baseline_mode,
        "openapi_snapshot": openapi_snapshot,
        "baseline_snapshot": _snapshot_bytes(API_BASELINE_REL, baseline_bytes) if baseline_bytes else {},
        "authority_skill": authority,
        "authority_tools": authority_tools,
        "reports": report_evidence,
    }
    if (
        not existing_evidence_errors
        and all(existing_evidence.get(key) == value for key, value in candidate_without_time.items())
        and isinstance(existing_evidence.get("recorded_at"), str)
    ):
        recorded_at = str(existing_evidence["recorded_at"])
    evidence = {
        "schema_version": API_REVIEW_SCHEMA_VERSION,
        **candidate_without_time,
        "recorded_at": recorded_at,
    }
    evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    outputs: dict[str, bytes] = {}
    if not baseline_exists and baseline_bytes:
        outputs[API_BASELINE_REL.as_posix()] = baseline_bytes
    for key, rel in API_REVIEW_REPORT_PATHS.items():
        if report_bytes.get(key):
            outputs[rel.as_posix()] = report_bytes[key]
    if report_evidence:
        outputs[API_REVIEW_EVIDENCE_REL.as_posix()] = evidence_bytes
    for rel in outputs:
        errors.extend(_output_path_errors(root, Path(rel)))
    would_update = [
        rel
        for rel, content in sorted(outputs.items())
        if _current_bytes(root / rel) != content
    ] if not errors else []
    return _ApiReviewPlan(
        target=str(root),
        reviewed=reviewed is True,
        min_grade=min_grade,
        baseline_mode=baseline_mode,
        errors=_dedupe_strings(errors),
        warnings=_dedupe_strings(warnings),
        evidence=evidence,
        openapi_snapshot=openapi_snapshot,
        tool_runs=tool_runs,
        outputs=outputs,
        would_update=would_update,
        state=state,
    )


def _authority_tool_bundle(
    root: Path,
    skill_roots: list[Path],
) -> tuple[dict[str, str], dict[str, Path], list[dict[str, str]], list[str]]:
    try:
        try:
            from .authority_skills import build_authority_skill_inventory
        except ImportError:  # pragma: no cover - direct script execution
            from authority_skills import build_authority_skill_inventory
        preferred_roots = [root / ".agents/skills", root / ".codex/skills", *skill_roots]
        inventory = build_authority_skill_inventory(
            skill_roots=preferred_roots,
            strict=False,
            include_default_skill_roots=False,
        )
        match = _authority_inventory_match(inventory)
        if not match:
            inventory = build_authority_skill_inventory(
                skill_roots=preferred_roots,
                strict=False,
                include_default_skill_roots=True,
            )
            match = _authority_inventory_match(inventory)
    except (OSError, RuntimeError) as error:
        return {}, {}, [], [f"authority skill inventory failed: {error}"]
    skill_path_text = str(match.get("skill_path", ""))
    if not skill_path_text:
        return {}, {}, [], [f"required authority skill is unavailable for API review: {API_REVIEW_AUTHORITY_SKILL}"]
    skill_path = Path(skill_path_text)
    skill_content, skill_error = _read_utf8_file(skill_path, "API authority SKILL.md")
    if skill_error:
        return {}, {}, [], [skill_error]
    authority = {
        "name": API_REVIEW_AUTHORITY_SKILL,
        "sha256": hashlib.sha256(skill_content).hexdigest(),
        "availability_scope": "agent-environment",
    }
    tool_paths: dict[str, Path] = {}
    authority_tools: list[dict[str, str]] = []
    errors: list[str] = []
    for name, filename in API_REVIEW_TOOL_FILES.items():
        path = skill_path.parent / "scripts" / filename
        if path.is_symlink() or not path.is_file():
            errors.append(f"API authority tool is missing or unsafe: {filename}")
            continue
        content, error = _read_utf8_file(path, f"API authority tool {filename}")
        if error:
            errors.append(error)
            continue
        tool_paths[name] = path
        authority_tools.append({"name": name, "sha256": hashlib.sha256(content).hexdigest()})
    authority_tools.sort(key=lambda item: item["name"])
    return authority, tool_paths, authority_tools, errors


def _authority_inventory_match(inventory: dict[str, object]) -> dict[str, object]:
    skills = inventory.get("skills")
    if not isinstance(skills, list):
        return {}
    return next(
        (
            item
            for item in skills
            if isinstance(item, dict)
            and item.get("name") == API_REVIEW_AUTHORITY_SKILL
            and item.get("available_in_agent_environment") is True
        ),
        {},
    )


def _run_authority_tools(
    *,
    tool_paths: dict[str, Path],
    min_grade: str,
    openapi_bytes: bytes,
    baseline_bytes: bytes,
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]], list[dict[str, object]], list[str]]:
    try:
        with tempfile.TemporaryDirectory(prefix="governance-api-review-") as tmp:
            return _run_authority_tools_in_workspace(
                Path(tmp),
                tool_paths=tool_paths,
                min_grade=min_grade,
                openapi_bytes=openapi_bytes,
                baseline_bytes=baseline_bytes,
            )
    except OSError as error:
        return {}, {}, [], [f"API authority tool workspace failed: {_os_error_reason(error)}"]


def _run_authority_tools_in_workspace(
    temporary: Path,
    *,
    tool_paths: dict[str, Path],
    min_grade: str,
    openapi_bytes: bytes,
    baseline_bytes: bytes,
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]], list[dict[str, object]], list[str]]:
    report_bytes: dict[str, bytes] = {}
    report_payloads: dict[str, dict[str, Any]] = {}
    tool_runs: list[dict[str, object]] = []
    errors: list[str] = []
    baseline = temporary / "openapi-baseline.json"
    current = temporary / "openapi-current.json"
    baseline.write_bytes(baseline_bytes)
    current.write_bytes(openapi_bytes)
    command_specs = (
        (
            "lint",
            "api_linter",
            [str(current), "--format", "json"],
        ),
        (
            "breaking_changes",
            "breaking_change_detector",
            [str(baseline), str(current), "--format", "json", "--exit-on-breaking"],
        ),
        (
            "scorecard",
            "api_scorecard",
            [str(current), "--format", "json", "--min-grade", min_grade],
        ),
    )
    for report_key, tool_name, arguments in command_specs:
        output = temporary / f"{report_key}.json"
        argv = [sys.executable, str(tool_paths[tool_name]), *arguments, "--output", str(output)]
        try:
            completed = subprocess.run(
                argv,
                cwd=temporary,
                text=True,
                capture_output=True,
                check=False,
                timeout=API_REVIEW_TOOL_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            errors.append(f"API authority tool {tool_name} failed to run: {error}")
            continue
        tool_runs.append(
            {
                "tool": tool_name,
                "returncode": completed.returncode,
                "stderr": completed.stderr.strip()[:1000],
            }
        )
        payload, content, report_errors = _load_external_report(output, tool_name)
        errors.extend(report_errors)
        if payload and content:
            report_payloads[report_key] = payload
            report_bytes[report_key] = content
        if completed.returncode != 0:
            errors.append(f"API authority tool {tool_name} returned {completed.returncode}")
    return report_bytes, report_payloads, tool_runs, errors


def _lint_summary(payload: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    errors: list[str] = []
    endpoint_count = _non_negative_int(summary.get("total_endpoints"))
    error_count = _non_negative_int(summary.get("errors"))
    warning_count = _non_negative_int(summary.get("warnings"))
    score = summary.get("score")
    if endpoint_count <= 0:
        errors.append("API lint report must cover at least one endpoint")
    if error_count != 0 or warning_count != 0:
        errors.append(f"API lint report is not clean: {error_count} error(s), {warning_count} warning(s)")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        errors.append("API lint report score must be numeric")
        score = 0
    return {
        "total_endpoints": endpoint_count,
        "errors": error_count,
        "warnings": warning_count,
        "score": score,
    }, errors


def _breaking_summary(payload: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    breaking_count = _non_negative_int(summary.get("breaking_changes"))
    potential_count = _non_negative_int(summary.get("potentially_breaking_changes"))
    has_breaking = payload.get("hasBreakingChanges")
    errors: list[str] = []
    if has_breaking is not False or breaking_count != 0 or potential_count != 0:
        errors.append(
            "API breaking changes or potentially breaking changes require versioned migration review"
        )
    return {
        "breaking_changes": breaking_count,
        "potentially_breaking_changes": potential_count,
        "has_breaking_changes": has_breaking is True,
    }, errors


def _scorecard_summary(
    payload: dict[str, object],
    min_grade: str,
) -> tuple[dict[str, object], list[str]]:
    overall = payload.get("overall") if isinstance(payload.get("overall"), dict) else {}
    grade = str(overall.get("grade", ""))
    score = overall.get("score")
    endpoint_count = _non_negative_int(overall.get("totalEndpoints"))
    errors: list[str] = []
    if grade not in API_REVIEW_GRADE_ORDER:
        errors.append("API scorecard grade is missing or invalid")
    elif API_REVIEW_GRADE_ORDER.index(grade) < API_REVIEW_GRADE_ORDER.index(min_grade):
        errors.append(f"API scorecard grade {grade} is below required grade {min_grade}")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        errors.append("API scorecard score must be numeric")
        score = 0
    if endpoint_count <= 0:
        errors.append("API scorecard must cover at least one endpoint")
    return {
        "grade": grade,
        "score": score,
        "total_endpoints": endpoint_count,
        "min_grade": min_grade,
    }, errors


def _validate_evidence_document(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != API_REVIEW_SCHEMA_VERSION:
        errors.append(f"API machine review schema_version must be {API_REVIEW_SCHEMA_VERSION}")
    if document.get("decision_policy") != API_REVIEW_DECISION_POLICY:
        errors.append("API machine review decision_policy is invalid")
    if document.get("reviewed") is not True:
        errors.append("API machine review evidence reviewed must be true")
    min_grade = document.get("min_grade")
    if min_grade not in API_REVIEW_GRADE_ORDER:
        errors.append("API machine review min_grade is invalid")
        min_grade = API_REVIEW_DEFAULT_MIN_GRADE
    if document.get("baseline_mode") not in {"initial-baseline", "comparison"}:
        errors.append("API machine review baseline_mode is invalid")
    errors.extend(_validate_snapshot(document.get("openapi_snapshot"), API_OPENAPI_REL, "openapi_snapshot"))
    errors.extend(_validate_snapshot(document.get("baseline_snapshot"), API_BASELINE_REL, "baseline_snapshot"))
    authority = document.get("authority_skill")
    if not isinstance(authority, dict):
        errors.append("API machine review authority_skill must be an object")
    else:
        if authority.get("name") != API_REVIEW_AUTHORITY_SKILL:
            errors.append(f"API machine review authority skill must be {API_REVIEW_AUTHORITY_SKILL}")
        _validate_digest(authority.get("sha256"), "API machine review authority skill", errors)
        if authority.get("availability_scope") != "agent-environment":
            errors.append("API machine review authority skill availability_scope must be agent-environment")
    tools = document.get("authority_tools")
    if not isinstance(tools, list):
        errors.append("API machine review authority_tools must be a list")
    else:
        by_name = {str(item.get("name", "")): item for item in tools if isinstance(item, dict)}
        if set(by_name) != set(API_REVIEW_TOOL_FILES):
            errors.append("API machine review authority_tools must include linter, detector, and scorecard")
        for name, item in by_name.items():
            _validate_digest(item.get("sha256"), f"API authority tool {name}", errors)
    reports = document.get("reports")
    if not isinstance(reports, dict):
        errors.append("API machine review reports must be an object")
    else:
        for key, rel in API_REVIEW_REPORT_PATHS.items():
            report = reports.get(key)
            errors.extend(_validate_snapshot(report, rel, f"reports.{key}"))
        if isinstance(reports.get("lint"), dict):
            normalized = {
                "summary": {
                    "total_endpoints": reports["lint"].get("total_endpoints"),
                    "errors": reports["lint"].get("errors"),
                    "warnings": reports["lint"].get("warnings"),
                    "score": reports["lint"].get("score"),
                }
            }
            _summary, report_errors = _lint_summary(normalized)
            errors.extend(report_errors)
        if isinstance(reports.get("breaking_changes"), dict):
            normalized = {
                "summary": {
                    "breaking_changes": reports["breaking_changes"].get("breaking_changes"),
                    "potentially_breaking_changes": reports["breaking_changes"].get(
                        "potentially_breaking_changes"
                    ),
                },
                "hasBreakingChanges": reports["breaking_changes"].get("has_breaking_changes"),
            }
            _summary, report_errors = _breaking_summary(normalized)
            errors.extend(report_errors)
        if isinstance(reports.get("scorecard"), dict):
            normalized = {
                "overall": {
                    "grade": reports["scorecard"].get("grade"),
                    "score": reports["scorecard"].get("score"),
                    "totalEndpoints": reports["scorecard"].get("total_endpoints"),
                }
            }
            _summary, report_errors = _scorecard_summary(normalized, str(min_grade))
            errors.extend(report_errors)
    recorded_at = document.get("recorded_at")
    if not isinstance(recorded_at, str) or not _valid_timestamp(recorded_at):
        errors.append("API machine review recorded_at must be an ISO-8601 timestamp")
    return _dedupe_strings(errors)


def _evidence_stale_reasons(root: Path, evidence: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    snapshots = [
        evidence.get("openapi_snapshot"),
        evidence.get("baseline_snapshot"),
    ]
    reports = evidence.get("reports")
    if isinstance(reports, dict):
        snapshots.extend(reports.get(key) for key in API_REVIEW_REPORT_PATHS)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        rel = str(snapshot.get("path", ""))
        path = root / rel
        if path.is_symlink() or not path.is_file():
            reasons.append(f"API review evidence source is missing or unsafe: {rel or '<missing>'}")
            continue
        try:
            content = path.read_bytes()
        except OSError:
            reasons.append(f"API review evidence source is unreadable: {rel}")
            continue
        if hashlib.sha256(content).hexdigest() != snapshot.get("sha256"):
            reasons.append(f"API review evidence source changed after tool review: {rel}")
    current_authority, _tool_paths, current_tools, authority_errors = _authority_tool_bundle(root, [])
    if current_authority:
        recorded_authority = evidence.get("authority_skill")
        recorded_authority_sha = (
            recorded_authority.get("sha256")
            if isinstance(recorded_authority, dict)
            else ""
        )
        if current_authority.get("sha256") != recorded_authority_sha:
            reasons.append("API review authority skill changed after tool review: api-design-reviewer")
        recorded_tools = {
            str(item.get("name", "")): str(item.get("sha256", ""))
            for item in evidence.get("authority_tools", [])
            if isinstance(item, dict)
        } if isinstance(evidence.get("authority_tools"), list) else {}
        current_tool_hashes = {
            str(item.get("name", "")): str(item.get("sha256", ""))
            for item in current_tools
        }
        for name in sorted(set(recorded_tools) | set(current_tool_hashes)):
            if recorded_tools.get(name) != current_tool_hashes.get(name):
                reasons.append(f"API review authority tool changed after tool review: {name}")
        reasons.extend(
            f"API review authority tool is no longer usable: {error}"
            for error in authority_errors
        )
    return reasons


def _load_openapi(
    root: Path,
    rel: Path,
) -> tuple[dict[str, Any], bytes, list[str]]:
    document, content, errors = _load_json_file(root, rel, "OpenAPI contract")
    if errors:
        return {}, content, errors
    if SCAFFOLD_PLACEHOLDER.encode("utf-8") in content:
        errors.append(f"OpenAPI contract still contains {SCAFFOLD_PLACEHOLDER}: {rel.as_posix()}")
    version = document.get("openapi")
    if not isinstance(version, str) or OPENAPI_VERSION_RE.fullmatch(version) is None:
        errors.append("OpenAPI contract must declare OpenAPI 3.0.x or 3.1.x")
    info = document.get("info")
    if not isinstance(info, dict):
        errors.append("OpenAPI contract info must be an object")
    else:
        for key in ("title", "version", "description"):
            if not isinstance(info.get(key), str) or not str(info[key]).strip():
                errors.append(f"OpenAPI contract info.{key} must be a non-empty string")
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("OpenAPI contract paths must contain at least one endpoint")
    return document, content, errors


def _load_json_file(
    root: Path,
    rel: Path,
    label: str,
) -> tuple[dict[str, Any], bytes, list[str]]:
    path = root / rel
    if path.is_symlink():
        return {}, b"", [f"{label} must not be a symbolic link: {rel.as_posix()}"]
    if not path.is_file():
        return {}, b"", [f"{label} is missing: {rel.as_posix()}"]
    try:
        content = path.read_bytes()
    except OSError as error:
        return {}, b"", [f"{label} is unreadable: {_os_error_reason(error)}"]
    if len(content) > API_REVIEW_MAX_JSON_BYTES:
        return {}, content, [f"{label} exceeds {API_REVIEW_MAX_JSON_BYTES} bytes"]
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


def _load_optional_evidence(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = root / API_REVIEW_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {}, []
    document, errors = _load_json_object(root, API_REVIEW_EVIDENCE_REL, "API machine review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(document))
    return document, errors


def _load_external_report(
    path: Path,
    tool_name: str,
) -> tuple[dict[str, Any], bytes, list[str]]:
    if not path.is_file() or path.is_symlink():
        return {}, b"", [f"API authority tool {tool_name} did not produce a safe JSON report"]
    try:
        content = path.read_bytes()
    except OSError as error:
        return {}, b"", [f"API authority tool {tool_name} report is unreadable: {_os_error_reason(error)}"]
    if len(content) > API_REVIEW_MAX_JSON_BYTES:
        return {}, content, [f"API authority tool {tool_name} report exceeds size limit"]
    try:
        loaded = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, content, [f"API authority tool {tool_name} report must be UTF-8 JSON"]
    if not isinstance(loaded, dict):
        return {}, content, [f"API authority tool {tool_name} report root must be an object"]
    canonical = (json.dumps(loaded, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return copy.deepcopy(loaded), canonical, []


def _baseline_mode(
    existing_evidence: dict[str, Any],
    openapi_bytes: bytes,
    baseline_bytes: bytes,
    baseline_exists: bool,
) -> str:
    if not baseline_exists:
        return "initial-baseline"
    if (
        existing_evidence.get("baseline_mode") == "initial-baseline"
        and openapi_bytes == baseline_bytes
    ):
        return "initial-baseline"
    return "comparison"


def _snapshot_bytes(rel: Path, content: bytes) -> dict[str, str]:
    return {"path": rel.as_posix(), "sha256": hashlib.sha256(content).hexdigest()}


def _validate_snapshot(value: object, rel: Path, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"API machine review {label} must be an object"]
    errors: list[str] = []
    if value.get("path") != rel.as_posix():
        errors.append(f"API machine review {label} path must be {rel.as_posix()}")
    _validate_digest(value.get("sha256"), f"API machine review {label}", errors)
    return errors


def _validate_digest(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        errors.append(f"{label} sha256 must be a lowercase SHA-256 digest")


def _output_path_errors(root: Path, rel: Path) -> list[str]:
    path = root / rel
    errors: list[str] = []
    current = root
    for part in rel.parts[:-1]:
        current /= part
        if current.is_symlink():
            return [f"API review output parent must not contain symbolic links: {current.relative_to(root)}"]
        if current.exists() and not current.is_dir():
            return [f"API review output parent is not a directory: {current.relative_to(root)}"]
    if path.is_symlink() or (path.exists() and not path.is_file()):
        errors.append(f"API review output path is unsafe: {rel.as_posix()}")
    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        errors.append(f"API review temporary path already exists: {temp.relative_to(root)}")
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


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else -1


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
