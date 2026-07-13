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


THREAT_SCOPE_REL = Path("docs/architecture/threat-model/scope.json")
THREAT_MITIGATIONS_REL = Path("docs/architecture/threat-model/mitigations.json")
THREAT_REPORT_REL = Path("docs/architecture/threat-model/stride-report.json")
THREAT_REVIEW_EVIDENCE_REL = Path("docs/architecture/threat-model/review-evidence.json")
THREAT_REVIEW_SCHEMA_VERSION = 1
THREAT_REPORT_SCHEMA_VERSION = 1
THREAT_REVIEW_DECISION_POLICY = "run_stride_dread_review_before_architecture_authority_signoff"
THREAT_REVIEW_ALLOWED_PHASES = frozenset({"design-derivation", "implementation"})
THREAT_REVIEW_AUTHORITY_SKILL = "senior-security"
THREAT_REVIEW_TOOL_NAME = "threat_modeler"
THREAT_REVIEW_TOOL_FILE = "threat_modeler.py"
THREAT_REVIEW_DREAD_THRESHOLD = 7.0
THREAT_REVIEW_TOOL_TIMEOUT_SECONDS = 60
THREAT_REVIEW_MAX_JSON_BYTES = 10 * 1024 * 1024
THREAT_REVIEW_MAX_ELEMENTS = 128
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ELEMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER_RE = re.compile(r"\b(?:todo|tbd|unknown|placeholder)\b", re.IGNORECASE)
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"

STRIDE_CATEGORIES = (
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
)
STRIDE_BY_ELEMENT_TYPE = {
    "external-entity": ("Spoofing", "Repudiation"),
    "process": STRIDE_CATEGORIES,
    "data-store": (
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
    ),
    "data-flow": (
        "Tampering",
        "Information Disclosure",
        "Denial of Service",
    ),
}
DREAD_FACTORS = (
    "damage",
    "reproducibility",
    "exploitability",
    "affected_users",
    "discoverability",
)
ARCHITECTURE_SOURCE_PATHS = (
    "docs/architecture/01-system-context.md",
    "docs/architecture/02-containers.md",
    "docs/architecture/03-quality-attributes.md",
)


@dataclass
class ThreatReviewEvidenceResult:
    target: str
    ok: bool
    reviewed: bool
    check: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    tool_runs: list[dict[str, object]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("threat review result target must be a non-empty string")
        if not isinstance(self.ok, bool) or not isinstance(self.reviewed, bool) or not isinstance(self.check, bool):
            raise ValueError("threat review result boolean fields must be booleans")
        for name, values in (
            ("errors", self.errors),
            ("warnings", self.warnings),
            ("updated", self.updated),
            ("would_update", self.would_update),
        ):
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"threat review result {name} must contain strings")
        if self.ok and self.errors:
            raise ValueError("threat review success cannot contain errors")
        if not self.ok and not self.errors:
            raise ValueError("threat review failure requires errors")
        if self.check and self.updated:
            raise ValueError("threat review check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("threat review write mode cannot report would_update paths")
        self.evidence = copy.deepcopy(self.evidence)
        self.tool_runs = copy.deepcopy(self.tool_runs)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": "workflows/04-design-derivation.md",
            "decision_policy": THREAT_REVIEW_DECISION_POLICY,
            "scope_path": THREAT_SCOPE_REL.as_posix(),
            "mitigations_path": THREAT_MITIGATIONS_REL.as_posix(),
            "report_path": THREAT_REPORT_REL.as_posix(),
            "evidence_path": THREAT_REVIEW_EVIDENCE_REL.as_posix(),
            "dread_threshold": THREAT_REVIEW_DREAD_THRESHOLD,
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
            "state": copy.deepcopy(self.state),
        }


@dataclass
class _ThreatReviewPlan:
    target: str
    reviewed: bool
    errors: list[str]
    warnings: list[str]
    evidence: dict[str, Any]
    tool_runs: list[dict[str, object]]
    outputs: dict[str, bytes]
    would_update: list[str]
    state: dict[str, Any]


def check_threat_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> ThreatReviewEvidenceResult:
    plan = _build_threat_review_plan(
        root,
        reviewed=reviewed,
        skill_roots=list(skill_roots or []),
    )
    return ThreatReviewEvidenceResult(
        target=plan.target,
        ok=not plan.errors,
        reviewed=plan.reviewed,
        check=True,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        evidence=plan.evidence,
        tool_runs=plan.tool_runs,
        state=plan.state,
    )


def record_threat_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> ThreatReviewEvidenceResult:
    root = root.resolve()
    plan = _build_threat_review_plan(
        root,
        reviewed=reviewed,
        skill_roots=list(skill_roots or []),
    )
    if plan.errors:
        return ThreatReviewEvidenceResult(
            target=plan.target,
            ok=False,
            reviewed=plan.reviewed,
            errors=plan.errors,
            warnings=plan.warnings,
            evidence=plan.evidence,
            tool_runs=plan.tool_runs,
            state=plan.state,
        )
    updated: list[str] = []
    if plan.would_update:
        try:
            _write_outputs_atomically(root, plan.outputs)
        except OSError as error:
            return ThreatReviewEvidenceResult(
                target=plan.target,
                ok=False,
                reviewed=plan.reviewed,
                errors=[f"threat review evidence is not writable: {_os_error_reason(error)}"],
                warnings=plan.warnings,
                evidence=plan.evidence,
                tool_runs=plan.tool_runs,
                state=plan.state,
            )
        updated = list(plan.would_update)
    return ThreatReviewEvidenceResult(
        target=plan.target,
        ok=True,
        reviewed=plan.reviewed,
        warnings=plan.warnings,
        updated=updated,
        evidence=plan.evidence,
        tool_runs=plan.tool_runs,
        state=plan.state,
    )


def build_threat_review_evidence_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    path = root / THREAT_REVIEW_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {
            "path": THREAT_REVIEW_EVIDENCE_REL.as_posix(),
            "exists": False,
            "ok": False,
            "status": "missing",
            "errors": [],
            "stale_reasons": [],
            "evidence": {},
        }
    evidence, errors = _load_json_object(root, THREAT_REVIEW_EVIDENCE_REL, "threat review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(evidence))
    stale_reasons: list[str] = []
    if not errors:
        stale_reasons.extend(_evidence_stale_reasons(root, evidence))
    return {
        "path": THREAT_REVIEW_EVIDENCE_REL.as_posix(),
        "exists": path.is_file() and not path.is_symlink(),
        "ok": not errors and not stale_reasons,
        "status": "invalid" if errors else "stale" if stale_reasons else "current",
        "errors": _dedupe_strings(errors),
        "stale_reasons": _dedupe_strings(stale_reasons),
        "evidence": copy.deepcopy(evidence),
    }


def threat_review_enforcement_ready(root: Path) -> bool:
    root = root.resolve()
    for rel in (
        THREAT_SCOPE_REL,
        THREAT_MITIGATIONS_REL,
        THREAT_REPORT_REL,
        THREAT_REVIEW_EVIDENCE_REL,
    ):
        path = root / rel
        if path.exists() or path.is_symlink():
            return True
    for rel_text in ARCHITECTURE_SOURCE_PATHS:
        path = root / rel_text
        if not path.is_file() or path.is_symlink():
            return False
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if SCAFFOLD_PLACEHOLDER in text:
            return False
    return True


def threat_review_required_evidence_paths() -> list[str]:
    return [
        THREAT_SCOPE_REL.as_posix(),
        THREAT_MITIGATIONS_REL.as_posix(),
        THREAT_REPORT_REL.as_posix(),
        THREAT_REVIEW_EVIDENCE_REL.as_posix(),
    ]


def _build_threat_review_plan(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path],
) -> _ThreatReviewPlan:
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
    elif phase not in THREAT_REVIEW_ALLOWED_PHASES:
        errors.append("threat review requires recorded phase design-derivation or implementation")
    if reviewed is not True:
        errors.append("--reviewed is required")

    scope, scope_bytes, scope_errors = _load_json_file(root, THREAT_SCOPE_REL, "threat review scope")
    mitigations, mitigation_bytes, mitigation_errors = _load_json_file(
        root,
        THREAT_MITIGATIONS_REL,
        "threat review mitigations",
    )
    errors.extend(scope_errors)
    errors.extend(mitigation_errors)
    elements: list[dict[str, Any]] = []
    source_paths: list[str] = []
    if not scope_errors:
        elements, source_paths, validation_errors = _validate_scope_document(root, scope)
        errors.extend(validation_errors)
    mitigation_items: list[dict[str, Any]] = []
    if not mitigation_errors:
        mitigation_items, validation_errors = _validate_mitigations_document(mitigations)
        errors.extend(validation_errors)

    authority, tool_path, authority_tool, authority_errors = _authority_tool_bundle(root, skill_roots)
    errors.extend(authority_errors)

    normalized_reports: list[dict[str, Any]] = []
    tool_runs: list[dict[str, object]] = []
    if not errors and elements and tool_path:
        normalized_reports, tool_runs, tool_errors = _run_authority_tool(tool_path, elements)
        errors.extend(tool_errors)

    report = {
        "schema_version": THREAT_REPORT_SCHEMA_VERSION,
        "authority_tool": THREAT_REVIEW_TOOL_FILE,
        "elements": normalized_reports,
    }
    high_threats: list[dict[str, Any]] = []
    mitigation_evidence_paths: list[str] = []
    if normalized_reports:
        high_threats = _high_dread_threats(normalized_reports)
        mitigation_evidence_paths, mitigation_mapping_errors = _validate_mitigation_mapping(
            root,
            elements,
            normalized_reports,
            high_threats,
            mitigation_items,
        )
        errors.extend(mitigation_mapping_errors)

    report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    source_snapshots, source_snapshot_errors = _snapshot_paths(
        root,
        _dedupe_strings([*source_paths, *mitigation_evidence_paths]),
        "threat review source",
    )
    errors.extend(source_snapshot_errors)

    summary = {
        "element_count": len(elements),
        "generated_threat_count": sum(
            len(item.get("threats", []))
            for item in normalized_reports
            if isinstance(item.get("threats"), list)
        ),
        "high_dread_threat_count": len(high_threats),
        "mitigated_high_dread_threat_count": len(high_threats) if not errors and high_threats else 0,
    }
    existing_evidence, existing_errors = _load_optional_evidence(root)
    recorded_at = utc_now()
    candidate_without_time = {
        "decision_policy": THREAT_REVIEW_DECISION_POLICY,
        "reviewed": reviewed is True,
        "dread_threshold": THREAT_REVIEW_DREAD_THRESHOLD,
        "scope_snapshot": _snapshot_bytes(THREAT_SCOPE_REL, scope_bytes) if scope_bytes else {},
        "mitigations_snapshot": _snapshot_bytes(THREAT_MITIGATIONS_REL, mitigation_bytes)
        if mitigation_bytes
        else {},
        "report_snapshot": _snapshot_bytes(THREAT_REPORT_REL, report_bytes) if normalized_reports else {},
        "source_snapshots": source_snapshots,
        "authority_skill": authority,
        "authority_tool": authority_tool,
        "summary": summary,
    }
    if (
        not existing_errors
        and all(existing_evidence.get(key) == value for key, value in candidate_without_time.items())
        and isinstance(existing_evidence.get("recorded_at"), str)
    ):
        recorded_at = str(existing_evidence["recorded_at"])
    evidence = {
        "schema_version": THREAT_REVIEW_SCHEMA_VERSION,
        **candidate_without_time,
        "recorded_at": recorded_at,
    }
    evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    outputs: dict[str, bytes] = {}
    if normalized_reports:
        outputs[THREAT_REPORT_REL.as_posix()] = report_bytes
    if normalized_reports and not errors:
        outputs[THREAT_REVIEW_EVIDENCE_REL.as_posix()] = evidence_bytes
    for rel in outputs:
        errors.extend(_output_path_errors(root, Path(rel)))
    would_update = (
        [rel for rel, content in sorted(outputs.items()) if _current_bytes(root / rel) != content]
        if not errors
        else []
    )
    return _ThreatReviewPlan(
        target=str(root),
        reviewed=reviewed is True,
        errors=_dedupe_strings(errors),
        warnings=_dedupe_strings(warnings),
        evidence=evidence,
        tool_runs=tool_runs,
        outputs=outputs,
        would_update=would_update,
        state=state,
    )


def _validate_scope_document(
    root: Path,
    document: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    if document.get("schema_version") != THREAT_REVIEW_SCHEMA_VERSION:
        errors.append(f"threat review scope schema_version must be {THREAT_REVIEW_SCHEMA_VERSION}")
    raw_elements = document.get("elements")
    if not isinstance(raw_elements, list) or not raw_elements:
        errors.append("threat review scope elements must be a non-empty list")
        raw_elements = []
    elif len(raw_elements) > THREAT_REVIEW_MAX_ELEMENTS:
        errors.append(f"threat review scope cannot exceed {THREAT_REVIEW_MAX_ELEMENTS} DFD elements")
    elements: list[dict[str, Any]] = []
    ids: set[str] = set()
    source_paths: list[str] = []
    for index, value in enumerate(raw_elements):
        label = f"threat review scope elements[{index}]"
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        element = copy.deepcopy(value)
        element_id = element.get("id")
        if not isinstance(element_id, str) or ELEMENT_ID_RE.fullmatch(element_id) is None:
            errors.append(f"{label}.id must use lowercase kebab-case")
            continue
        if element_id in ids:
            errors.append(f"threat review scope element ID is duplicated: {element_id}")
        ids.add(element_id)
        for field_name in ("name", "component"):
            if not _concrete_text(element.get(field_name)):
                errors.append(f"{label}.{field_name} must be concrete text")
        element_type = element.get("type")
        if element_type not in STRIDE_BY_ELEMENT_TYPE:
            errors.append(f"{label}.type must be one of {', '.join(STRIDE_BY_ELEMENT_TYPE)}")
        for field_name in ("assets", "trust_boundaries", "source_references"):
            values = element.get(field_name)
            if not isinstance(values, list) or not values or not all(_concrete_text(item) for item in values):
                errors.append(f"{label}.{field_name} must be a non-empty list of concrete strings")
        references = element.get("source_references")
        if isinstance(references, list):
            for reference in references:
                if not isinstance(reference, str):
                    continue
                normalized, path_error = _safe_relative_path(reference)
                if path_error:
                    errors.append(f"{label}.source_references path is invalid: {reference}: {path_error}")
                    continue
                if not normalized.startswith("docs/architecture/") or not normalized.endswith(".md"):
                    errors.append(f"{label}.source_references must point to architecture Markdown: {normalized}")
                    continue
                source_paths.append(normalized)
        elements.append(element)

    coverage = document.get("stride_coverage")
    if not isinstance(coverage, list):
        errors.append("threat review scope stride_coverage must be a list")
        coverage = []
    coverage_by_element: dict[str, set[str]] = {element_id: set() for element_id in ids}
    for index, value in enumerate(coverage):
        label = f"threat review scope stride_coverage[{index}]"
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        element_id = value.get("element_id")
        category = value.get("category")
        key = (str(element_id), str(category))
        if element_id not in ids:
            errors.append(f"{label}.element_id does not match a declared element: {element_id}")
            continue
        if category not in STRIDE_CATEGORIES:
            errors.append(f"{label}.category is not a STRIDE category: {category}")
            continue
        if category in coverage_by_element[str(element_id)]:
            errors.append(f"threat review STRIDE coverage is duplicated: {key[0]} / {key[1]}")
        coverage_by_element[str(element_id)].add(str(category))
        if value.get("status") != "considered":
            errors.append(f"{label}.status must be considered")
        if not _concrete_text(value.get("notes")):
            errors.append(f"{label}.notes must explain the review")
    for element in elements:
        element_id = str(element.get("id", ""))
        element_type = str(element.get("type", ""))
        expected = set(STRIDE_BY_ELEMENT_TYPE.get(element_type, ()))
        actual = coverage_by_element.get(element_id, set())
        for category in sorted(expected - actual):
            errors.append(f"threat review STRIDE coverage is missing: {element_id} / {category}")
        for category in sorted(actual - expected):
            errors.append(
                f"threat review STRIDE coverage is not applicable to {element_type}: {element_id} / {category}"
            )
    for rel in _dedupe_strings(source_paths):
        errors.extend(_repository_file_errors(root, rel, "threat review architecture source"))
    missing_core_sources = set(ARCHITECTURE_SOURCE_PATHS) - set(source_paths)
    for rel in sorted(missing_core_sources):
        errors.append(f"threat review scope must reference required architecture source: {rel}")
    return elements, _dedupe_strings(source_paths), _dedupe_strings(errors)


def _validate_mitigations_document(
    document: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if document.get("schema_version") != THREAT_REVIEW_SCHEMA_VERSION:
        errors.append(f"threat review mitigations schema_version must be {THREAT_REVIEW_SCHEMA_VERSION}")
    values = document.get("mitigations")
    if not isinstance(values, list):
        errors.append("threat review mitigations must be a list")
        values = []
    items: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str]] = set()
    for index, value in enumerate(values):
        label = f"threat review mitigations[{index}]"
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        item = copy.deepcopy(value)
        key = _mitigation_key(item)
        if not all(key):
            errors.append(f"{label} must identify element_id, category, and threat_name")
        elif key in keys:
            errors.append(f"threat review mitigation is duplicated: {' / '.join(key)}")
        keys.add(key)
        if item.get("category") not in STRIDE_CATEGORIES:
            errors.append(f"{label}.category is not a STRIDE category")
        if not _concrete_text(item.get("owner")):
            errors.append(f"{label} requires a named mitigation owner")
        if not _concrete_text(item.get("mitigation")):
            errors.append(f"{label}.mitigation must be concrete text")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(_concrete_text(path) for path in evidence):
            errors.append(f"{label}.evidence must be a non-empty list of repository paths")
        items.append(item)
    return items, _dedupe_strings(errors)


def _authority_tool_bundle(
    root: Path,
    skill_roots: list[Path],
) -> tuple[dict[str, str], Path | None, dict[str, str], list[str]]:
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
        return {}, None, {}, [f"authority skill inventory failed: {error}"]
    skill_path_text = str(match.get("skill_path", ""))
    if not skill_path_text:
        return {}, None, {}, [
            f"required authority skill is unavailable for threat review: {THREAT_REVIEW_AUTHORITY_SKILL}"
        ]
    skill_path = Path(skill_path_text)
    skill_content, skill_error = _read_utf8_file(skill_path, "threat review authority SKILL.md")
    if skill_error:
        return {}, None, {}, [skill_error]
    tool_path = skill_path.parent / "scripts" / THREAT_REVIEW_TOOL_FILE
    if tool_path.is_symlink() or not tool_path.is_file():
        return {}, None, {}, [f"threat review authority tool is missing or unsafe: {THREAT_REVIEW_TOOL_FILE}"]
    tool_content, tool_error = _read_utf8_file(tool_path, f"threat review authority tool {THREAT_REVIEW_TOOL_FILE}")
    if tool_error:
        return {}, None, {}, [tool_error]
    return (
        {
            "name": THREAT_REVIEW_AUTHORITY_SKILL,
            "sha256": hashlib.sha256(skill_content).hexdigest(),
            "availability_scope": "agent-environment",
        },
        tool_path,
        {
            "name": THREAT_REVIEW_TOOL_NAME,
            "file": THREAT_REVIEW_TOOL_FILE,
            "sha256": hashlib.sha256(tool_content).hexdigest(),
        },
        [],
    )


def _authority_inventory_match(inventory: dict[str, object]) -> dict[str, object]:
    skills = inventory.get("skills")
    if not isinstance(skills, list):
        return {}
    return next(
        (
            item
            for item in skills
            if isinstance(item, dict)
            and item.get("name") == THREAT_REVIEW_AUTHORITY_SKILL
            and item.get("available_in_agent_environment") is True
        ),
        {},
    )


def _run_authority_tool(
    tool_path: Path,
    elements: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, object]], list[str]]:
    reports: list[dict[str, Any]] = []
    runs: list[dict[str, object]] = []
    errors: list[str] = []
    try:
        workspace = tempfile.TemporaryDirectory(prefix="governance-threat-review-")
    except OSError as error:
        return [], [], [f"threat review temporary workspace could not be created: {_os_error_reason(error)}"]
    with workspace as temporary_text:
        temporary = Path(temporary_text)
        for index, element in enumerate(elements, start=1):
            element_id = str(element.get("id", ""))
            output = temporary / f"{index:04d}-{element_id}.json"
            argv = [
                sys.executable,
                str(tool_path),
                "--component",
                str(element.get("component", "")),
                "--assets",
                ",".join(str(item) for item in element.get("assets", []) if isinstance(item, str)),
                "--json",
                "--output",
                str(output),
            ]
            try:
                completed = subprocess.run(
                    argv,
                    cwd=temporary,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=THREAT_REVIEW_TOOL_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                errors.append(f"threat review authority tool failed for {element_id}: {error}")
                continue
            runs.append(
                {
                    "tool": THREAT_REVIEW_TOOL_NAME,
                    "element_id": element_id,
                    "returncode": completed.returncode,
                    "stderr": completed.stderr.strip()[:1000],
                }
            )
            payload, report_errors = _load_external_report(output, element_id)
            errors.extend(report_errors)
            if completed.returncode != 0:
                errors.append(
                    f"threat review authority tool returned {completed.returncode} for element {element_id}"
                )
            if payload:
                normalized, normalization_errors = _normalize_tool_report(element, payload)
                errors.extend(normalization_errors)
                if normalized:
                    reports.append(normalized)
    reports.sort(key=lambda item: str(item.get("element_id", "")))
    return reports, runs, _dedupe_strings(errors)


def _load_external_report(path: Path, element_id: str) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file() or path.is_symlink():
        return {}, [f"threat review authority tool did not produce a safe JSON report for {element_id}"]
    try:
        content = path.read_bytes()
    except OSError as error:
        return {}, [f"threat review authority report is unreadable for {element_id}: {_os_error_reason(error)}"]
    if len(content) > THREAT_REVIEW_MAX_JSON_BYTES:
        return {}, [f"threat review authority report exceeds size limit for {element_id}"]
    try:
        loaded = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, [f"threat review authority report must be UTF-8 JSON for {element_id}"]
    if not isinstance(loaded, dict):
        return {}, [f"threat review authority report root must be an object for {element_id}"]
    return copy.deepcopy(loaded), []


def _normalize_tool_report(
    element: dict[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    element_id = str(element.get("id", ""))
    errors: list[str] = []
    if payload.get("component") != element.get("component"):
        errors.append(f"threat review authority report component mismatch for {element_id}")
    threats = payload.get("threats")
    if not isinstance(threats, list) or not threats:
        errors.append(f"threat review authority report must contain threats for {element_id}")
        threats = []
    normalized_threats: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, value in enumerate(threats):
        label = f"threat review authority report {element_id} threats[{index}]"
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        threat = copy.deepcopy(value)
        category = threat.get("category")
        name = threat.get("name")
        if category not in STRIDE_CATEGORIES:
            errors.append(f"{label}.category is not a STRIDE category")
        if not _concrete_text(name):
            errors.append(f"{label}.name must be concrete text")
        key = (str(category), str(name))
        if key in seen_keys:
            errors.append(f"threat review authority report contains a duplicate threat: {element_id} / {' / '.join(key)}")
        seen_keys.add(key)
        for field_name in ("description", "attack_vector", "impact", "risk_level"):
            if not _concrete_text(threat.get(field_name)):
                errors.append(f"{label}.{field_name} must be concrete text")
        for field_name in ("likelihood", "severity", "risk_score"):
            if not _number_in_range(threat.get(field_name), 1, 25):
                errors.append(f"{label}.{field_name} must be numeric")
        dread = threat.get("dread")
        if not isinstance(dread, dict):
            errors.append(f"{label}.dread must be an object")
        else:
            factor_values: list[float] = []
            for factor in DREAD_FACTORS:
                value = dread.get(factor)
                if not _number_in_range(value, 1, 10):
                    errors.append(f"{label}.dread.{factor} must be between 1 and 10")
                else:
                    factor_values.append(float(value))
            total = dread.get("total")
            if not _number_in_range(total, 1, 10):
                errors.append(f"{label}.dread.total must be between 1 and 10")
            elif len(factor_values) == len(DREAD_FACTORS):
                calculated = sum(factor_values) / len(factor_values)
                if abs(float(total) - calculated) > 0.05:
                    errors.append(f"{label}.dread.total does not match the five DREAD factors")
        suggested = threat.get("mitigations")
        if not isinstance(suggested, list) or not suggested or not all(_concrete_text(item) for item in suggested):
            errors.append(f"{label}.mitigations must contain authority-tool suggestions")
        normalized_threats.append(threat)
    normalized_threats.sort(key=lambda item: (str(item.get("category", "")), str(item.get("name", ""))))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("total_threats") != len(normalized_threats):
        errors.append(f"threat review authority report summary count mismatch for {element_id}")
    return (
        {
            "element_id": element_id,
            "element_name": str(element.get("name", "")),
            "element_type": str(element.get("type", "")),
            "component": str(element.get("component", "")),
            "assets": list(element.get("assets", [])),
            "summary": copy.deepcopy(summary),
            "threats": normalized_threats,
        },
        _dedupe_strings(errors),
    )


def _high_dread_threats(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    high: list[dict[str, Any]] = []
    for report in reports:
        element_id = str(report.get("element_id", ""))
        for threat in report.get("threats", []):
            if not isinstance(threat, dict):
                continue
            dread = threat.get("dread")
            total = dread.get("total") if isinstance(dread, dict) else None
            if isinstance(total, (int, float)) and not isinstance(total, bool) and float(total) >= THREAT_REVIEW_DREAD_THRESHOLD:
                high.append(
                    {
                        "element_id": element_id,
                        "category": str(threat.get("category", "")),
                        "threat_name": str(threat.get("name", "")),
                        "dread_total": float(total),
                    }
                )
    high.sort(key=lambda item: (item["element_id"], item["category"], item["threat_name"]))
    return high


def _validate_mitigation_mapping(
    root: Path,
    elements: list[dict[str, Any]],
    reports: list[dict[str, Any]],
    high_threats: list[dict[str, Any]],
    mitigations: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    evidence_paths: list[str] = []
    element_ids = {str(item.get("id", "")) for item in elements}
    generated_keys = {
        (
            str(report.get("element_id", "")),
            str(threat.get("category", "")),
            str(threat.get("name", "")),
        )
        for report in reports
        for threat in report.get("threats", [])
        if isinstance(threat, dict)
    }
    high_by_key = {_mitigation_key(item): item for item in high_threats}
    mitigation_by_key = {_mitigation_key(item): item for item in mitigations}
    for key in sorted(high_by_key):
        mitigation = mitigation_by_key.get(key)
        if mitigation is None:
            errors.append(
                f"high-DREAD threat requires a named mitigation owner and repository evidence: {' / '.join(key)}"
            )
            continue
        if not _concrete_text(mitigation.get("owner")):
            errors.append(f"high-DREAD threat requires a named mitigation owner: {' / '.join(key)}")
        if not _concrete_text(mitigation.get("mitigation")):
            errors.append(f"high-DREAD threat requires a concrete mitigation: {' / '.join(key)}")
    for key, mitigation in sorted(mitigation_by_key.items()):
        if key[0] not in element_ids:
            errors.append(f"threat mitigation references an unknown element: {key[0]}")
        if key not in generated_keys:
            errors.append(f"threat mitigation does not match a generated threat: {' / '.join(key)}")
        evidence = mitigation.get("evidence")
        if isinstance(evidence, list):
            for path in evidence:
                if not isinstance(path, str):
                    continue
                normalized, path_error = _safe_relative_path(path)
                if path_error:
                    errors.append(f"threat mitigation evidence path is invalid: {path}: {path_error}")
                    continue
                evidence_paths.append(normalized)
                errors.extend(_repository_file_errors(root, normalized, "threat mitigation evidence"))
    return _dedupe_strings(evidence_paths), _dedupe_strings(errors)


def _validate_evidence_document(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != THREAT_REVIEW_SCHEMA_VERSION:
        errors.append(f"threat review evidence schema_version must be {THREAT_REVIEW_SCHEMA_VERSION}")
    if document.get("decision_policy") != THREAT_REVIEW_DECISION_POLICY:
        errors.append("threat review evidence decision_policy is invalid")
    if document.get("reviewed") is not True:
        errors.append("threat review evidence reviewed must be true")
    if document.get("dread_threshold") != THREAT_REVIEW_DREAD_THRESHOLD:
        errors.append(f"threat review evidence DREAD threshold must be {THREAT_REVIEW_DREAD_THRESHOLD}")
    errors.extend(_validate_snapshot(document.get("scope_snapshot"), THREAT_SCOPE_REL, "scope_snapshot"))
    errors.extend(
        _validate_snapshot(document.get("mitigations_snapshot"), THREAT_MITIGATIONS_REL, "mitigations_snapshot")
    )
    errors.extend(_validate_snapshot(document.get("report_snapshot"), THREAT_REPORT_REL, "report_snapshot"))
    source_snapshots = document.get("source_snapshots")
    if not isinstance(source_snapshots, list) or not source_snapshots:
        errors.append("threat review evidence source_snapshots must be a non-empty list")
    else:
        seen: set[str] = set()
        for index, snapshot in enumerate(source_snapshots):
            if not isinstance(snapshot, dict):
                errors.append(f"threat review evidence source_snapshots[{index}] must be an object")
                continue
            path = snapshot.get("path")
            normalized, path_error = _safe_relative_path(path if isinstance(path, str) else "")
            if path_error:
                errors.append(f"threat review source snapshot path is invalid: {path or '<missing>'}")
            elif normalized in seen:
                errors.append(f"threat review source snapshot is duplicated: {normalized}")
            else:
                seen.add(normalized)
            _validate_digest(snapshot.get("sha256"), "threat review source snapshot", errors)
    authority = document.get("authority_skill")
    if not isinstance(authority, dict):
        errors.append("threat review evidence authority_skill must be an object")
    else:
        if authority.get("name") != THREAT_REVIEW_AUTHORITY_SKILL:
            errors.append(f"threat review authority skill must be {THREAT_REVIEW_AUTHORITY_SKILL}")
        _validate_digest(authority.get("sha256"), "threat review authority skill", errors)
        if authority.get("availability_scope") != "agent-environment":
            errors.append("threat review authority skill availability_scope must be agent-environment")
    tool = document.get("authority_tool")
    if not isinstance(tool, dict):
        errors.append("threat review evidence authority_tool must be an object")
    else:
        if tool.get("name") != THREAT_REVIEW_TOOL_NAME or tool.get("file") != THREAT_REVIEW_TOOL_FILE:
            errors.append("threat review authority tool identity is invalid")
        _validate_digest(tool.get("sha256"), "threat review authority tool", errors)
    summary = document.get("summary")
    if not isinstance(summary, dict):
        errors.append("threat review evidence summary must be an object")
    else:
        for field_name in ("element_count", "generated_threat_count"):
            value = summary.get(field_name)
            if not _non_negative_int(value) or value == 0:
                errors.append(f"threat review evidence summary.{field_name} must be a positive integer")
        for field_name in ("high_dread_threat_count", "mitigated_high_dread_threat_count"):
            if not _non_negative_int(summary.get(field_name)):
                errors.append(f"threat review evidence summary.{field_name} must be a non-negative integer")
        if summary.get("high_dread_threat_count") != summary.get("mitigated_high_dread_threat_count"):
            errors.append("threat review evidence must mitigate every high-DREAD threat")
    recorded_at = document.get("recorded_at")
    if not isinstance(recorded_at, str) or not _valid_timestamp(recorded_at):
        errors.append("threat review evidence recorded_at must be an ISO-8601 timestamp")
    return _dedupe_strings(errors)


def _evidence_stale_reasons(root: Path, evidence: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    snapshots: list[object] = [
        evidence.get("scope_snapshot"),
        evidence.get("mitigations_snapshot"),
        evidence.get("report_snapshot"),
    ]
    source_snapshots = evidence.get("source_snapshots")
    if isinstance(source_snapshots, list):
        snapshots.extend(source_snapshots)
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        rel = str(snapshot.get("path", ""))
        path = root / rel
        if path.is_symlink() or not path.is_file():
            reasons.append(f"threat review evidence source is missing or unsafe: {rel or '<missing>'}")
            continue
        try:
            content = path.read_bytes()
        except OSError:
            reasons.append(f"threat review evidence source is unreadable: {rel}")
            continue
        if hashlib.sha256(content).hexdigest() != snapshot.get("sha256"):
            reasons.append(f"threat review evidence source changed after review: {rel}")
    current_authority, _tool_path, current_tool, authority_errors = _authority_tool_bundle(root, [])
    recorded_authority = evidence.get("authority_skill")
    if current_authority and isinstance(recorded_authority, dict):
        if current_authority.get("sha256") != recorded_authority.get("sha256"):
            reasons.append("threat review authority skill changed after review: senior-security")
    recorded_tool = evidence.get("authority_tool")
    if current_tool and isinstance(recorded_tool, dict):
        if current_tool.get("sha256") != recorded_tool.get("sha256"):
            reasons.append("threat review authority tool changed after review: threat_modeler")
    reasons.extend(f"threat review authority tool is no longer usable: {error}" for error in authority_errors)
    return _dedupe_strings(reasons)


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
    if len(content) > THREAT_REVIEW_MAX_JSON_BYTES:
        return {}, content, [f"{label} exceeds {THREAT_REVIEW_MAX_JSON_BYTES} bytes"]
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
    path = root / THREAT_REVIEW_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {}, []
    document, errors = _load_json_object(root, THREAT_REVIEW_EVIDENCE_REL, "threat review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(document))
    return document, errors


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
        file_errors = _repository_file_errors(root, normalized, label)
        if file_errors:
            errors.extend(file_errors)
            continue
        try:
            content = (root / normalized).read_bytes()
            content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{label} path must be UTF-8: {normalized}")
            continue
        except OSError as error:
            errors.append(f"{label} path is unreadable: {normalized}: {_os_error_reason(error)}")
            continue
        snapshots.append({"path": normalized, "sha256": hashlib.sha256(content).hexdigest()})
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
        return normalized, "path must be normalized POSIX syntax"
    return normalized, ""


def _snapshot_bytes(rel: Path, content: bytes) -> dict[str, str]:
    return {"path": rel.as_posix(), "sha256": hashlib.sha256(content).hexdigest()}


def _validate_snapshot(value: object, rel: Path, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"threat review evidence {label} must be an object"]
    errors: list[str] = []
    if value.get("path") != rel.as_posix():
        errors.append(f"threat review evidence {label} path must be {rel.as_posix()}")
    _validate_digest(value.get("sha256"), f"threat review evidence {label}", errors)
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
            return [f"threat review output parent must not contain symbolic links: {current.relative_to(root)}"]
        if current.exists() and not current.is_dir():
            return [f"threat review output parent is not a directory: {current.relative_to(root)}"]
    errors: list[str] = []
    if path.is_symlink() or (path.exists() and not path.is_file()):
        errors.append(f"threat review output path is unsafe: {rel.as_posix()}")
    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        errors.append(f"threat review temporary path already exists: {temp.relative_to(root)}")
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


def _mitigation_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value.get("element_id", "")),
        str(value.get("category", "")),
        str(value.get("threat_name", "")),
    )


def _concrete_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value.strip()) >= 3
        and PLACEHOLDER_RE.search(value) is None
        and SCAFFOLD_PLACEHOLDER not in value
    )


def _number_in_range(value: object, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum <= float(value) <= maximum
    )


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
