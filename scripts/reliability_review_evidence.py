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


RELIABILITY_SCOPE_REL = Path("docs/backend/reliability/slo-scope.json")
RELIABILITY_DEFINITIONS_REL = Path("docs/backend/reliability/slo-definitions.json")
RELIABILITY_BUDGETS_REL = Path("docs/backend/reliability/error-budgets.json")
RELIABILITY_REVIEW_REL = Path("docs/backend/reliability/slo-review.json")
RELIABILITY_EVIDENCE_REL = Path("docs/backend/reliability/review-evidence.json")
RELIABILITY_SCHEMA_VERSION = 1
RELIABILITY_DECISION_POLICY = "decide_slo_applicability_then_run_slo_architect_before_backend_signoff"
RELIABILITY_ALLOWED_PHASES = frozenset({"design-derivation", "implementation"})
RELIABILITY_AUTHORITY_SKILL = "slo-architect"
RELIABILITY_TOOL_FILES = {
    "slo_designer": "slo_designer.py",
    "error_budget_calculator": "error_budget_calculator.py",
    "slo_review": "slo_review.py",
}
RELIABILITY_REPORT_PATHS = {
    "definitions": RELIABILITY_DEFINITIONS_REL,
    "budgets": RELIABILITY_BUDGETS_REL,
    "review": RELIABILITY_REVIEW_REL,
}
RELIABILITY_REVIEW_ADAPTER = {
    "name": "target_percent_to_target_alias",
    "version": 1,
    "source_field": "target_percent",
    "reviewer_field": "target",
    "scope": "isolated_reviewer_input_only",
}
RELIABILITY_MODES = ("required", "not-applicable")
RELIABILITY_SLI_TYPES = (
    "request-success-rate",
    "request-latency",
    "availability-time",
    "data-freshness",
    "correctness",
)
RELIABILITY_TARGET_BASIS_KINDS = (
    "product-commitment",
    "architecture-scenario",
    "historical-baseline",
    "provisional-prelaunch",
)
RELIABILITY_REQUIRED_SOURCE_PATHS = (
    "docs/architecture/03-quality-attributes.md",
    "docs/backend/01-modules.md",
    "docs/backend/03-external-services.md",
)
RELIABILITY_POLICY_REQUIRED_SECTIONS = (
    "Scope",
    "Budget Actions",
    "Release Policy",
    "Incident Policy",
    "Review",
)
RELIABILITY_MAX_SLOS = 64
RELIABILITY_MAX_JSON_BYTES = 10 * 1024 * 1024
RELIABILITY_TOOL_TIMEOUT_SECONDS = 60
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SLO_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER_RE = re.compile(r"\b(?:todo|tbd|unknown|placeholder|must define)\b", re.IGNORECASE)
ACCEPTANCE_PATH_RE = re.compile(r"^docs/product/[0-9]{2}-[a-z0-9-]*acceptance[a-z0-9-]*\.md$")


@dataclass
class ReliabilityReviewEvidenceResult:
    target: str
    ok: bool
    reviewed: bool
    mode: str
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
            raise ValueError("reliability review target must be a non-empty string")
        if self.mode not in RELIABILITY_MODES and self.mode != "unknown":
            raise ValueError("reliability review mode is invalid")
        if not isinstance(self.ok, bool) or not isinstance(self.reviewed, bool) or not isinstance(self.check, bool):
            raise ValueError("reliability review boolean fields must be booleans")
        for name, values in (
            ("errors", self.errors),
            ("warnings", self.warnings),
            ("updated", self.updated),
            ("would_update", self.would_update),
        ):
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise ValueError(f"reliability review {name} must contain strings")
        if self.ok and self.errors:
            raise ValueError("reliability review success cannot contain errors")
        if not self.ok and not self.errors:
            raise ValueError("reliability review failure requires errors")
        if self.check and self.updated:
            raise ValueError("reliability review check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("reliability review write mode cannot report would_update paths")
        self.evidence = copy.deepcopy(self.evidence)
        self.tool_runs = copy.deepcopy(self.tool_runs)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": "workflows/04-design-derivation.md",
            "decision_policy": RELIABILITY_DECISION_POLICY,
            "scope_path": RELIABILITY_SCOPE_REL.as_posix(),
            "evidence_path": RELIABILITY_EVIDENCE_REL.as_posix(),
            "mode": self.mode,
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
class _ReliabilityReviewPlan:
    target: str
    reviewed: bool
    mode: str
    errors: list[str]
    warnings: list[str]
    evidence: dict[str, Any]
    tool_runs: list[dict[str, object]]
    outputs: dict[str, bytes]
    would_update: list[str]
    state: dict[str, Any]


def check_reliability_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> ReliabilityReviewEvidenceResult:
    plan = _build_reliability_review_plan(root, reviewed=reviewed, skill_roots=list(skill_roots or []))
    return ReliabilityReviewEvidenceResult(
        target=plan.target,
        ok=not plan.errors,
        reviewed=plan.reviewed,
        mode=plan.mode,
        check=True,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        evidence=plan.evidence,
        tool_runs=plan.tool_runs,
        state=plan.state,
    )


def record_reliability_review_evidence(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> ReliabilityReviewEvidenceResult:
    root = root.resolve()
    plan = _build_reliability_review_plan(root, reviewed=reviewed, skill_roots=list(skill_roots or []))
    if plan.errors:
        return ReliabilityReviewEvidenceResult(
            target=plan.target,
            ok=False,
            reviewed=plan.reviewed,
            mode=plan.mode,
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
            return ReliabilityReviewEvidenceResult(
                target=plan.target,
                ok=False,
                reviewed=plan.reviewed,
                mode=plan.mode,
                errors=[f"reliability review evidence is not writable: {_os_error_reason(error)}"],
                warnings=plan.warnings,
                evidence=plan.evidence,
                tool_runs=plan.tool_runs,
                state=plan.state,
            )
        updated = list(plan.would_update)
    return ReliabilityReviewEvidenceResult(
        target=plan.target,
        ok=True,
        reviewed=plan.reviewed,
        mode=plan.mode,
        warnings=plan.warnings,
        updated=updated,
        evidence=plan.evidence,
        tool_runs=plan.tool_runs,
        state=plan.state,
    )


def build_reliability_review_evidence_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    path = root / RELIABILITY_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {
            "path": RELIABILITY_EVIDENCE_REL.as_posix(),
            "exists": False,
            "ok": False,
            "status": "missing",
            "mode": "unknown",
            "errors": [],
            "stale_reasons": [],
            "evidence": {},
        }
    evidence, errors = _load_json_object(root, RELIABILITY_EVIDENCE_REL, "reliability review evidence")
    if not errors:
        errors.extend(_validate_evidence_document(evidence))
    stale_reasons: list[str] = []
    if not errors:
        stale_reasons.extend(_evidence_stale_reasons(root, evidence))
    return {
        "path": RELIABILITY_EVIDENCE_REL.as_posix(),
        "exists": path.is_file() and not path.is_symlink(),
        "ok": not errors and not stale_reasons,
        "status": "invalid" if errors else "stale" if stale_reasons else "current",
        "mode": str(evidence.get("mode", "unknown")),
        "errors": _dedupe_strings(errors),
        "stale_reasons": _dedupe_strings(stale_reasons),
        "evidence": copy.deepcopy(evidence),
    }


def reliability_review_enforcement_ready(root: Path) -> bool:
    root = root.resolve()
    for rel in (
        RELIABILITY_SCOPE_REL,
        RELIABILITY_DEFINITIONS_REL,
        RELIABILITY_BUDGETS_REL,
        RELIABILITY_REVIEW_REL,
        RELIABILITY_EVIDENCE_REL,
    ):
        if (root / rel).exists() or (root / rel).is_symlink():
            return True
    for rel in ("docs/backend/01-modules.md", "docs/backend/03-external-services.md"):
        path = root / rel
        if not path.is_file() or path.is_symlink():
            return False
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if SCAFFOLD_PLACEHOLDER in text:
            return False
    return True


def reliability_review_required_evidence_paths(root: Path) -> list[str]:
    inventory = build_reliability_review_evidence_inventory(root)
    evidence = inventory.get("evidence") if isinstance(inventory.get("evidence"), dict) else {}
    paths = [RELIABILITY_SCOPE_REL.as_posix(), RELIABILITY_EVIDENCE_REL.as_posix()]
    if inventory.get("mode") == "required":
        paths.extend(rel.as_posix() for rel in RELIABILITY_REPORT_PATHS.values())
    source_snapshots = evidence.get("source_snapshots") if isinstance(evidence, dict) else []
    if isinstance(source_snapshots, list):
        paths.extend(
            str(item.get("path", ""))
            for item in source_snapshots
            if isinstance(item, dict) and str(item.get("path", ""))
        )
    return _dedupe_strings(paths)


def _build_reliability_review_plan(
    root: Path,
    *,
    reviewed: bool,
    skill_roots: list[Path],
) -> _ReliabilityReviewPlan:
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
    elif phase not in RELIABILITY_ALLOWED_PHASES:
        errors.append("reliability review requires recorded phase design-derivation or implementation")
    if reviewed is not True:
        errors.append("--reviewed is required")

    scope, scope_bytes, scope_errors = _load_json_file(root, RELIABILITY_SCOPE_REL, "reliability review scope")
    errors.extend(scope_errors)
    mode = "unknown"
    slos: list[dict[str, Any]] = []
    source_paths: list[str] = []
    if not scope_errors:
        mode, slos, source_paths, validation_errors = _validate_scope_document(root, scope)
        errors.extend(validation_errors)
        if mode == "not-applicable":
            for rel in RELIABILITY_REPORT_PATHS.values():
                path = root / rel
                if path.exists() or path.is_symlink():
                    errors.append(
                        "not-applicable reliability scope requires removing obsolete generated report: "
                        f"{rel.as_posix()}"
                    )

    authority, tool_paths, authority_tools, authority_errors = _authority_tool_bundle(root, skill_roots)
    errors.extend(authority_errors)

    definitions: list[dict[str, Any]] = []
    budgets: list[dict[str, Any]] = []
    review_findings: list[dict[str, Any]] = []
    tool_runs: list[dict[str, object]] = []
    if mode == "required" and not errors and slos and tool_paths:
        definitions, budgets, review_findings, tool_runs, tool_errors = _run_authority_tools(
            tool_paths,
            slos,
        )
        errors.extend(tool_errors)
        if review_findings:
            errors.append(
                f"SLO authority review reported {sum(len(item['findings']) for item in review_findings)} finding(s)"
            )

    report_payloads = {
        "definitions": {
            "schema_version": RELIABILITY_SCHEMA_VERSION,
            "slos": definitions,
        },
        "budgets": {
            "schema_version": RELIABILITY_SCHEMA_VERSION,
            "budgets": budgets,
        },
        "review": {
            "schema_version": RELIABILITY_SCHEMA_VERSION,
            "adapter": copy.deepcopy(RELIABILITY_REVIEW_ADAPTER),
            "findings": review_findings,
        },
    }
    report_bytes = {
        key: (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        for key, payload in report_payloads.items()
    }
    source_snapshots, snapshot_errors = _snapshot_paths(root, source_paths, "reliability review source")
    errors.extend(snapshot_errors)
    report_evidence = {
        key: _snapshot_bytes(RELIABILITY_REPORT_PATHS[key], report_bytes[key])
        for key in RELIABILITY_REPORT_PATHS
    } if mode == "required" and definitions and budgets else {}
    summary = {
        "slo_count": len(slos) if mode == "required" else 0,
        "review_finding_count": sum(len(item["findings"]) for item in review_findings),
        "tool_run_count": len(tool_runs),
    }
    existing, existing_errors = _load_optional_evidence(root)
    candidate_without_time = {
        "decision_policy": RELIABILITY_DECISION_POLICY,
        "mode": mode,
        "reviewed": reviewed is True,
        "scope_snapshot": _snapshot_bytes(RELIABILITY_SCOPE_REL, scope_bytes) if scope_bytes else {},
        "source_snapshots": source_snapshots,
        "authority_skill": authority,
        "authority_tools": authority_tools,
        "review_adapter": copy.deepcopy(RELIABILITY_REVIEW_ADAPTER),
        "reports": report_evidence,
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
        "schema_version": RELIABILITY_SCHEMA_VERSION,
        **candidate_without_time,
        "recorded_at": recorded_at,
    }
    evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
    outputs: dict[str, bytes] = {}
    if mode == "required" and definitions and budgets and not errors:
        outputs.update(
            {
                RELIABILITY_REPORT_PATHS[key].as_posix(): report_bytes[key]
                for key in RELIABILITY_REPORT_PATHS
            }
        )
    if mode in RELIABILITY_MODES and not errors:
        outputs[RELIABILITY_EVIDENCE_REL.as_posix()] = evidence_bytes
    for rel in outputs:
        errors.extend(_output_path_errors(root, Path(rel)))
    would_update = (
        [rel for rel, content in sorted(outputs.items()) if _current_bytes(root / rel) != content]
        if not errors
        else []
    )
    return _ReliabilityReviewPlan(
        target=str(root),
        reviewed=reviewed is True,
        mode=mode,
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
) -> tuple[str, list[dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    if document.get("schema_version") != RELIABILITY_SCHEMA_VERSION:
        errors.append(f"reliability scope schema_version must be {RELIABILITY_SCHEMA_VERSION}")
    applicability = document.get("applicability")
    if not isinstance(applicability, dict):
        errors.append("reliability scope applicability must be an object")
        applicability = {}
    mode = str(applicability.get("decision", "unknown"))
    if mode not in RELIABILITY_MODES:
        errors.append(f"reliability applicability decision must be one of {', '.join(RELIABILITY_MODES)}")
        mode = "unknown"
    for field_name in ("owner", "reason"):
        if not _concrete_text(applicability.get(field_name)):
            errors.append(f"reliability applicability.{field_name} must be concrete text")
    triggers = applicability.get("revisit_triggers")
    if not _concrete_string_list(triggers):
        errors.append("reliability applicability.revisit_triggers must contain concrete review triggers")
    source_paths, source_errors = _validate_source_references(
        root,
        applicability.get("source_references"),
        "reliability applicability",
    )
    errors.extend(source_errors)
    missing_required = set(RELIABILITY_REQUIRED_SOURCE_PATHS) - set(source_paths)
    for rel in sorted(missing_required):
        errors.append(f"reliability scope must reference required backend source: {rel}")
    if not any(ACCEPTANCE_PATH_RE.fullmatch(path) for path in source_paths):
        errors.append("reliability scope must reference a product acceptance chapter")

    raw_slos = document.get("slos")
    if not isinstance(raw_slos, list):
        errors.append("reliability scope slos must be a list")
        raw_slos = []
    if len(raw_slos) > RELIABILITY_MAX_SLOS:
        errors.append(f"reliability scope cannot exceed {RELIABILITY_MAX_SLOS} SLO definitions")
    if mode == "required" and not raw_slos:
        errors.append("required reliability scope must define at least one SLO")
    if mode == "not-applicable" and raw_slos:
        errors.append("not-applicable reliability scope must not define SLOs")

    slos: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(raw_slos):
        label = f"reliability scope slos[{index}]"
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        item = copy.deepcopy(value)
        slo_id = item.get("id")
        if not isinstance(slo_id, str) or SLO_ID_RE.fullmatch(slo_id) is None:
            errors.append(f"{label}.id must use lowercase kebab-case")
        elif slo_id in seen_ids:
            errors.append(f"reliability SLO ID is duplicated: {slo_id}")
        else:
            seen_ids.add(slo_id)
        for field_name in (
            "service",
            "owner",
            "user_journey",
            "sli_numerator",
            "sli_denominator",
            "policy_doc",
            "review_cadence",
        ):
            if not _concrete_text(item.get(field_name)):
                errors.append(f"{label}.{field_name} must be concrete text")
        if item.get("sli_type") not in RELIABILITY_SLI_TYPES:
            errors.append(f"{label}.sli_type is unsupported")
        target = item.get("target_percent")
        if not _number_in_range(target, 50, 100):
            errors.append(f"{label}.target_percent must be between 50 and 100")
        window = item.get("window_days")
        if not isinstance(window, int) or isinstance(window, bool) or not 1 <= window <= 365:
            errors.append(f"{label}.window_days must be an integer between 1 and 365")
        labels = item.get("sli_labels")
        if not isinstance(labels, list) or not all(_concrete_text(entry) for entry in labels):
            errors.append(f"{label}.sli_labels must be a list of concrete strings")
        item_sources, item_source_errors = _validate_source_references(
            root,
            item.get("source_references"),
            f"{label} source",
        )
        errors.extend(item_source_errors)
        source_paths.extend(item_sources)
        basis = item.get("target_basis")
        if not isinstance(basis, dict):
            errors.append(f"{label}.target_basis must be an object")
            basis = {}
        if basis.get("kind") not in RELIABILITY_TARGET_BASIS_KINDS:
            errors.append(f"{label}.target_basis.kind is unsupported")
        if not _concrete_text(basis.get("rationale")):
            errors.append(f"{label}.target_basis.rationale must be concrete text")
        basis_sources, basis_errors = _validate_source_references(
            root,
            basis.get("source_references"),
            f"{label} target basis",
        )
        errors.extend(basis_errors)
        source_paths.extend(basis_sources)
        if basis.get("kind") == "provisional-prelaunch" and not _concrete_text(basis.get("validation_plan")):
            errors.append(f"{label}.target_basis.validation_plan is required for provisional targets")
        policy_path = item.get("policy_doc")
        if isinstance(policy_path, str):
            normalized, path_error = _safe_relative_path(policy_path)
            if path_error:
                errors.append(f"{label}.policy_doc path is invalid: {path_error}")
            else:
                source_paths.append(normalized)
                errors.extend(_validate_policy_document(root, normalized))
        slos.append(item)
    return mode, slos, _dedupe_strings(source_paths), _dedupe_strings(errors)


def _validate_source_references(
    root: Path,
    value: object,
    label: str,
) -> tuple[list[str], list[str]]:
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


def _validate_policy_document(root: Path, rel: str) -> list[str]:
    errors = _repository_file_errors(root, rel, "error budget policy")
    if errors:
        return errors
    if not rel.startswith("docs/backend/") or not rel.endswith(".md"):
        errors.append(f"error budget policy must be backend Markdown: {rel}")
        return errors
    try:
        text = (root / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [f"error budget policy must be readable UTF-8 Markdown: {rel}"]
    if SCAFFOLD_PLACEHOLDER in text or PLACEHOLDER_RE.search(text):
        errors.append(f"error budget policy contains placeholder content: {rel}")
    headings = set(re.findall(r"^##[ \t]+(.+?)[ \t]*$", text, re.MULTILINE))
    for section in RELIABILITY_POLICY_REQUIRED_SECTIONS:
        if section not in headings:
            errors.append(f"error budget policy is missing section {section}: {rel}")
    readme = root / "docs/backend/README.md"
    try:
        indexed = Path(rel).name in readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        indexed = False
    if not indexed:
        errors.append(f"error budget policy is not indexed by docs/backend/README.md: {rel}")
    return errors


def _authority_tool_bundle(
    root: Path,
    skill_roots: list[Path],
) -> tuple[dict[str, str], dict[str, Path], list[dict[str, str]], list[str]]:
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
        match = _authority_inventory_match(inventory)
        if not match:
            inventory = build_authority_skill_inventory(
                skill_roots=preferred,
                strict=False,
                include_default_skill_roots=True,
            )
            match = _authority_inventory_match(inventory)
    except (OSError, RuntimeError) as error:
        return {}, {}, [], [f"authority skill inventory failed: {error}"]
    skill_path_text = str(match.get("skill_path", ""))
    if not skill_path_text:
        return {}, {}, [], [
            f"required authority skill is unavailable for reliability review: {RELIABILITY_AUTHORITY_SKILL}"
        ]
    skill_path = Path(skill_path_text)
    skill_content, skill_error = _read_utf8_file(skill_path, "reliability authority SKILL.md")
    if skill_error:
        return {}, {}, [], [skill_error]
    authority = {
        "name": RELIABILITY_AUTHORITY_SKILL,
        "sha256": hashlib.sha256(skill_content).hexdigest(),
        "availability_scope": "agent-environment",
    }
    paths: dict[str, Path] = {}
    tools: list[dict[str, str]] = []
    errors: list[str] = []
    for name, filename in RELIABILITY_TOOL_FILES.items():
        path = skill_path.parent / "scripts" / filename
        if path.is_symlink() or not path.is_file():
            errors.append(f"reliability authority tool is missing or unsafe: {filename}")
            continue
        content, error = _read_utf8_file(path, f"reliability authority tool {filename}")
        if error:
            errors.append(error)
            continue
        paths[name] = path
        tools.append({"name": name, "file": filename, "sha256": hashlib.sha256(content).hexdigest()})
    tools.sort(key=lambda item: item["name"])
    return authority, paths, tools, errors


def _authority_inventory_match(inventory: dict[str, object]) -> dict[str, object]:
    skills = inventory.get("skills")
    if not isinstance(skills, list):
        return {}
    return next(
        (
            item
            for item in skills
            if isinstance(item, dict)
            and item.get("name") == RELIABILITY_AUTHORITY_SKILL
            and item.get("available_in_agent_environment") is True
        ),
        {},
    )


def _run_authority_tools(
    tool_paths: dict[str, Path],
    slos: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, object]],
    list[str],
]:
    definitions: list[dict[str, Any]] = []
    budgets: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    runs: list[dict[str, object]] = []
    errors: list[str] = []
    try:
        workspace = tempfile.TemporaryDirectory(prefix="governance-reliability-review-")
    except OSError as error:
        return [], [], [], [], [f"reliability review workspace could not be created: {_os_error_reason(error)}"]
    with workspace as temporary_text:
        temporary = Path(temporary_text)
        reviewer_root = temporary / "review-inputs"
        reviewer_root.mkdir()
        for item in slos:
            slo_id = str(item.get("id", ""))
            designer_args = [
                "--service", str(item.get("service", "")),
                "--sli-type", str(item.get("sli_type", "")),
                "--target", str(item.get("target_percent", "")),
                "--window-days", str(item.get("window_days", "")),
                "--user-journey", str(item.get("user_journey", "")),
                "--sli-numerator", str(item.get("sli_numerator", "")),
                "--sli-denominator", str(item.get("sli_denominator", "")),
                "--owner", str(item.get("owner", "")),
                "--policy-doc", str(item.get("policy_doc", "")),
                "--review-cadence", str(item.get("review_cadence", "")),
                "--format", "json",
            ]
            labels = item.get("sli_labels")
            if isinstance(labels, list) and labels:
                designer_args.extend(["--sli-labels", ",".join(str(label) for label in labels)])
            designer, run, run_errors = _run_json_tool(
                tool_paths["slo_designer"], designer_args, temporary, "slo_designer", slo_id
            )
            runs.append(run)
            errors.extend(run_errors)
            normalized, normalize_errors = _normalize_slo_definition(item, designer)
            errors.extend(normalize_errors)
            if normalized:
                definitions.append(normalized)
                reviewer_doc = copy.deepcopy(normalized)
                reviewer_doc["target"] = normalized["target_percent"]
                (reviewer_root / f"{slo_id}.json").write_text(
                    json.dumps(reviewer_doc, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

            budget, run, run_errors = _run_json_tool(
                tool_paths["error_budget_calculator"],
                [
                    "--target", str(item.get("target_percent", "")),
                    "--window-days", str(item.get("window_days", "")),
                    "--format", "json",
                ],
                temporary,
                "error_budget_calculator",
                slo_id,
            )
            runs.append(run)
            errors.extend(run_errors)
            normalized_budget, budget_errors = _normalize_budget(item, budget)
            errors.extend(budget_errors)
            if normalized_budget:
                budgets.append(normalized_budget)
        definitions.sort(key=lambda item: str(item.get("id", "")))
        budgets.sort(key=lambda item: str(item.get("slo_id", "")))
        if not errors and definitions:
            review_payload, run, review_errors = _run_json_tool(
                tool_paths["slo_review"],
                ["--slo-doc", str(reviewer_root), "--format", "json"],
                temporary,
                "slo_review",
                "all",
                allow_nonzero=True,
            )
            runs.append(run)
            errors.extend(review_errors)
            findings, finding_errors = _normalize_review_findings(review_payload, reviewer_root)
            errors.extend(finding_errors)
            if run.get("returncode") not in {0, 1}:
                errors.append(f"reliability authority tool slo_review returned {run.get('returncode')}")
            elif run.get("returncode") == 1 and not findings:
                errors.append("reliability authority tool slo_review failed without findings")
    return definitions, budgets, findings, runs, _dedupe_strings(errors)


def _run_json_tool(
    path: Path,
    arguments: list[str],
    cwd: Path,
    name: str,
    subject: str,
    *,
    allow_nonzero: bool = False,
) -> tuple[object, dict[str, object], list[str]]:
    try:
        completed = subprocess.run(
            [sys.executable, str(path), *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=RELIABILITY_TOOL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {}, {"tool": name, "subject": subject, "returncode": -1, "stderr": str(error)[:1000]}, [
            f"reliability authority tool {name} failed for {subject}: {error}"
        ]
    run = {
        "tool": name,
        "subject": subject,
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip()[:1000],
    }
    errors: list[str] = []
    content = completed.stdout.encode("utf-8", errors="replace")
    if len(content) > RELIABILITY_MAX_JSON_BYTES:
        errors.append(f"reliability authority tool {name} output exceeds size limit for {subject}")
        return {}, run, errors
    try:
        payload = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        errors.append(f"reliability authority tool {name} output must be JSON for {subject}")
        payload = {}
    if completed.returncode != 0 and not allow_nonzero:
        errors.append(f"reliability authority tool {name} returned {completed.returncode} for {subject}")
    return copy.deepcopy(payload), run, errors


def _normalize_slo_definition(
    source: dict[str, Any],
    payload: object,
) -> tuple[dict[str, Any], list[str]]:
    slo_id = str(source.get("id", ""))
    if not isinstance(payload, dict):
        return {}, [f"slo_designer output root must be an object for {slo_id}"]
    errors: list[str] = []
    for field_name in ("service", "owner", "user_journey", "target_percent", "window_days", "review_cadence"):
        expected = source.get(field_name)
        if payload.get(field_name) != expected:
            errors.append(f"slo_designer output {field_name} mismatch for {slo_id}")
    sli = payload.get("sli") if isinstance(payload.get("sli"), dict) else {}
    expected_sli = {
        "type": source.get("sli_type"),
        "numerator": source.get("sli_numerator"),
        "denominator": source.get("sli_denominator"),
        "labels": source.get("sli_labels"),
    }
    if sli != expected_sli:
        errors.append(f"slo_designer output SLI mismatch for {slo_id}")
    error_budget = payload.get("error_budget") if isinstance(payload.get("error_budget"), dict) else {}
    if error_budget.get("policy_doc") != source.get("policy_doc"):
        errors.append(f"slo_designer output policy_doc mismatch for {slo_id}")
    minutes = error_budget.get("minutes_per_window")
    if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
        errors.append(f"slo_designer output error budget is invalid for {slo_id}")
    normalized = {
        "id": slo_id,
        "service": str(payload.get("service", "")),
        "owner": str(payload.get("owner", "")),
        "user_journey": str(payload.get("user_journey", "")),
        "sli": copy.deepcopy(sli),
        "target_percent": payload.get("target_percent"),
        "window_days": payload.get("window_days"),
        "error_budget": copy.deepcopy(error_budget),
        "alerts": copy.deepcopy(payload.get("alerts")) if isinstance(payload.get("alerts"), dict) else {},
        "review_cadence": str(payload.get("review_cadence", "")),
        "target_basis": copy.deepcopy(source.get("target_basis")),
        "source_references": copy.deepcopy(source.get("source_references")),
    }
    return normalized, _dedupe_strings(errors)


def _normalize_budget(
    source: dict[str, Any],
    payload: object,
) -> tuple[dict[str, Any], list[str]]:
    slo_id = str(source.get("id", ""))
    if not isinstance(payload, dict):
        return {}, [f"error budget output root must be an object for {slo_id}"]
    errors: list[str] = []
    if payload.get("target_percent") != source.get("target_percent"):
        errors.append(f"error budget target mismatch for {slo_id}")
    if payload.get("window_days") != source.get("window_days"):
        errors.append(f"error budget window mismatch for {slo_id}")
    for field_name in ("bad_fraction", "budget_minutes", "budget_hours"):
        value = payload.get(field_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            errors.append(f"error budget {field_name} is invalid for {slo_id}")
    rules = payload.get("alert_rules")
    if not isinstance(rules, list) or {str(item.get("name", "")) for item in rules if isinstance(item, dict)} != {
        "fast_burn", "slow_burn", "ticket_burn"
    }:
        errors.append(f"error budget must contain fast, slow, and ticket burn rules for {slo_id}")
    normalized = {"slo_id": slo_id, **copy.deepcopy(payload)}
    return normalized, _dedupe_strings(errors)


def _normalize_review_findings(
    payload: object,
    reviewer_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(payload, list):
        return [], ["slo_review output root must be a list"]
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            errors.append(f"slo_review result[{index}] must be an object")
            continue
        path = Path(str(item.get("path", "")))
        try:
            path.resolve().relative_to(reviewer_root.resolve())
        except (OSError, ValueError):
            errors.append(f"slo_review result path is outside isolated input: {path}")
            continue
        raw_findings = item.get("findings")
        if not isinstance(raw_findings, list):
            errors.append(f"slo_review findings must be a list for {path.name}")
            continue
        finding_items: list[dict[str, str]] = []
        for finding in raw_findings:
            if not isinstance(finding, list) or len(finding) != 3 or not all(isinstance(value, str) for value in finding):
                errors.append(f"slo_review finding has invalid shape for {path.name}")
                continue
            finding_items.append({"level": finding[0], "code": finding[1], "message": finding[2]})
        if finding_items:
            normalized.append({"slo_id": path.stem, "findings": finding_items})
    normalized.sort(key=lambda item: item["slo_id"])
    return normalized, _dedupe_strings(errors)


def _validate_evidence_document(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != RELIABILITY_SCHEMA_VERSION:
        errors.append(f"reliability evidence schema_version must be {RELIABILITY_SCHEMA_VERSION}")
    if document.get("decision_policy") != RELIABILITY_DECISION_POLICY:
        errors.append("reliability evidence decision_policy is invalid")
    mode = document.get("mode")
    if mode not in RELIABILITY_MODES:
        errors.append("reliability evidence mode is invalid")
    if document.get("reviewed") is not True:
        errors.append("reliability evidence reviewed must be true")
    errors.extend(_validate_snapshot(document.get("scope_snapshot"), RELIABILITY_SCOPE_REL, "scope_snapshot"))
    snapshots = document.get("source_snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        errors.append("reliability evidence source_snapshots must be a non-empty list")
    else:
        for index, snapshot in enumerate(snapshots):
            if not isinstance(snapshot, dict):
                errors.append(f"reliability evidence source_snapshots[{index}] must be an object")
                continue
            path = snapshot.get("path")
            _, path_error = _safe_relative_path(path if isinstance(path, str) else "")
            if path_error:
                errors.append(f"reliability source snapshot path is invalid: {path or '<missing>'}")
            _validate_digest(snapshot.get("sha256"), "reliability source snapshot", errors)
    authority = document.get("authority_skill")
    if not isinstance(authority, dict):
        errors.append("reliability evidence authority_skill must be an object")
    else:
        if authority.get("name") != RELIABILITY_AUTHORITY_SKILL:
            errors.append(f"reliability authority skill must be {RELIABILITY_AUTHORITY_SKILL}")
        _validate_digest(authority.get("sha256"), "reliability authority skill", errors)
    tools = document.get("authority_tools")
    if not isinstance(tools, list):
        errors.append("reliability evidence authority_tools must be a list")
    else:
        by_name = {str(item.get("name", "")): item for item in tools if isinstance(item, dict)}
        if set(by_name) != set(RELIABILITY_TOOL_FILES):
            errors.append("reliability evidence must bind all slo-architect tools")
        for name, item in by_name.items():
            _validate_digest(item.get("sha256"), f"reliability authority tool {name}", errors)
    if document.get("review_adapter") != RELIABILITY_REVIEW_ADAPTER:
        errors.append("reliability evidence review_adapter is invalid")
    reports = document.get("reports")
    if not isinstance(reports, dict):
        errors.append("reliability evidence reports must be an object")
        reports = {}
    if mode == "required":
        for key, rel in RELIABILITY_REPORT_PATHS.items():
            errors.extend(_validate_snapshot(reports.get(key), rel, f"reports.{key}"))
    elif reports:
        errors.append("not-applicable reliability evidence must not contain reports")
    summary = document.get("summary")
    if not isinstance(summary, dict):
        errors.append("reliability evidence summary must be an object")
    else:
        slo_count = summary.get("slo_count")
        finding_count = summary.get("review_finding_count")
        tool_run_count = summary.get("tool_run_count")
        if not _non_negative_int(slo_count) or (mode == "required" and slo_count == 0):
            errors.append("reliability evidence summary.slo_count is invalid")
        if finding_count != 0:
            errors.append("reliability evidence must have zero authority review findings")
        if not _non_negative_int(tool_run_count):
            errors.append("reliability evidence summary.tool_run_count is invalid")
        if mode == "not-applicable" and (slo_count != 0 or tool_run_count != 0):
            errors.append("not-applicable reliability evidence must not report SLO or tool runs")
    recorded_at = document.get("recorded_at")
    if not isinstance(recorded_at, str) or not _valid_timestamp(recorded_at):
        errors.append("reliability evidence recorded_at must be an ISO-8601 timestamp")
    return _dedupe_strings(errors)


def _evidence_stale_reasons(root: Path, evidence: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    snapshots: list[object] = [evidence.get("scope_snapshot")]
    sources = evidence.get("source_snapshots")
    if isinstance(sources, list):
        snapshots.extend(sources)
    reports = evidence.get("reports")
    if isinstance(reports, dict):
        snapshots.extend(reports.values())
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        rel = str(snapshot.get("path", ""))
        path = root / rel
        if path.is_symlink() or not path.is_file():
            reasons.append(f"reliability evidence source is missing or unsafe: {rel or '<missing>'}")
            continue
        try:
            content = path.read_bytes()
        except OSError:
            reasons.append(f"reliability evidence source is unreadable: {rel}")
            continue
        if hashlib.sha256(content).hexdigest() != snapshot.get("sha256"):
            reasons.append(f"reliability evidence source changed after review: {rel}")
    current_authority, _paths, current_tools, authority_errors = _authority_tool_bundle(root, [])
    recorded_authority = evidence.get("authority_skill")
    if current_authority and isinstance(recorded_authority, dict):
        if current_authority.get("sha256") != recorded_authority.get("sha256"):
            reasons.append("reliability authority skill changed after review: slo-architect")
    recorded_tools = {
        str(item.get("name", "")): str(item.get("sha256", ""))
        for item in evidence.get("authority_tools", [])
        if isinstance(item, dict)
    } if isinstance(evidence.get("authority_tools"), list) else {}
    current_hashes = {item["name"]: item["sha256"] for item in current_tools}
    for name in sorted(set(recorded_tools) | set(current_hashes)):
        if recorded_tools.get(name) != current_hashes.get(name):
            reasons.append(f"reliability authority tool changed after review: {name}")
    reasons.extend(f"reliability authority tool is no longer usable: {error}" for error in authority_errors)
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
    if len(content) > RELIABILITY_MAX_JSON_BYTES:
        return {}, content, [f"{label} exceeds {RELIABILITY_MAX_JSON_BYTES} bytes"]
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
    path = root / RELIABILITY_EVIDENCE_REL
    if not path.exists() and not path.is_symlink():
        return {}, []
    document, errors = _load_json_object(root, RELIABILITY_EVIDENCE_REL, "reliability review evidence")
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
        return [f"reliability evidence {label} must be an object"]
    errors: list[str] = []
    if value.get("path") != rel.as_posix():
        errors.append(f"reliability evidence {label} path must be {rel.as_posix()}")
    _validate_digest(value.get("sha256"), f"reliability evidence {label}", errors)
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
            return [f"reliability output parent must not contain symbolic links: {current.relative_to(root)}"]
        if current.exists() and not current.is_dir():
            return [f"reliability output parent is not a directory: {current.relative_to(root)}"]
    errors: list[str] = []
    if path.is_symlink() or (path.exists() and not path.is_file()):
        errors.append(f"reliability output path is unsafe: {rel.as_posix()}")
    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        errors.append(f"reliability temporary path already exists: {temp.relative_to(root)}")
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


def _concrete_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value.strip()) >= 3
        and PLACEHOLDER_RE.search(value) is None
        and SCAFFOLD_PLACEHOLDER not in value
    )


def _concrete_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_concrete_text(item) for item in value)


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
