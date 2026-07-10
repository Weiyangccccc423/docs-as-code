from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .state import StateFileError, load_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from state import StateFileError, load_state, utc_now


PRODUCT_DISPOSITIONS_REL = Path("docs/product/core/chapter-dispositions.json")
PRODUCT_PRD_REL = Path("docs/product/core/PRD.md")
PRODUCT_DISPOSITION_SCHEMA_VERSION = 1
PRODUCT_DISPOSITION_PHASE = "product-structuring"
PRODUCT_DISPOSITION_WORKFLOW = "workflows/03-product-structuring.md"
PRODUCT_DISPOSITION_DECISION_POLICY = "record_only_reviewed_source_backed_chapter_dispositions"
PRODUCT_CHAPTER_KEYS = (
    "background-and-problems",
    "change-log",
    "goals-and-requirements",
    "functional-spec",
    "acceptance-criteria",
    "success-metrics",
)
PRODUCT_DISPOSITION_DECISIONS = ("author-required", "omit-unsupported")
PRODUCT_DISPOSITION_REVIEW_SCOPE = ("chapter-source", "unresolved-items", "glossary-terms")
NON_OMITTABLE_PRODUCT_CHAPTERS = frozenset({"goals-and-requirements", "acceptance-criteria"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER_REASON_RE = re.compile(r"\b(?:todo|tbd|unknown|placeholder)\b", re.IGNORECASE)


@dataclass
class ProductDispositionResult:
    target: str
    ok: bool
    chapter: str
    decision: str
    reason: str
    reviewed: bool
    check: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    disposition: dict[str, Any] = field(default_factory=dict)
    document: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("product disposition result target must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise ValueError("product disposition result ok must be a boolean")
        if not isinstance(self.chapter, str):
            raise ValueError("product disposition result chapter must be a string")
        if not isinstance(self.decision, str):
            raise ValueError("product disposition result decision must be a string")
        if not isinstance(self.reason, str):
            raise ValueError("product disposition result reason must be a string")
        if not isinstance(self.reviewed, bool):
            raise ValueError("product disposition result reviewed must be a boolean")
        if not isinstance(self.check, bool):
            raise ValueError("product disposition result check must be a boolean")
        if not isinstance(self.errors, list) or not all(isinstance(item, str) for item in self.errors):
            raise ValueError("product disposition result errors must be strings")
        if not isinstance(self.warnings, list) or not all(isinstance(item, str) for item in self.warnings):
            raise ValueError("product disposition result warnings must be strings")
        for field_name, paths in (("updated", self.updated), ("would_update", self.would_update)):
            if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                raise ValueError(f"product disposition result {field_name} must contain string paths")
            if len(paths) != len(set(paths)):
                raise ValueError(f"product disposition result {field_name} paths must be unique")
        if not isinstance(self.disposition, dict):
            raise ValueError("product disposition result disposition must be an object")
        if not isinstance(self.document, dict):
            raise ValueError("product disposition result document must be an object")
        if not isinstance(self.state, dict):
            raise ValueError("product disposition result state must be an object")
        if self.check and self.updated:
            raise ValueError("product disposition check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("product disposition write mode cannot report would_update paths")
        if self.ok and self.errors:
            raise ValueError("product disposition success cannot contain errors")
        if not self.ok and not self.errors:
            raise ValueError("product disposition failure requires errors")
        self.errors = list(self.errors)
        self.warnings = list(self.warnings)
        self.updated = list(self.updated)
        self.would_update = list(self.would_update)
        self.disposition = copy.deepcopy(self.disposition)
        self.document = copy.deepcopy(self.document)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": PRODUCT_DISPOSITION_WORKFLOW,
            "decision_policy": PRODUCT_DISPOSITION_DECISION_POLICY,
            "disposition_path": PRODUCT_DISPOSITIONS_REL.as_posix(),
            "chapter": self.chapter,
            "decision": self.decision,
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
            "disposition": copy.deepcopy(self.disposition),
            "document": copy.deepcopy(self.document),
            "state": copy.deepcopy(self.state),
        }


@dataclass
class _ProductDispositionPlan:
    target: str
    chapter: str
    decision: str
    reason: str
    reviewed: bool
    errors: list[str]
    warnings: list[str]
    disposition: dict[str, Any]
    document: dict[str, Any]
    rendered: bytes
    would_update: list[str]
    state: dict[str, Any]


def check_product_disposition(
    root: Path,
    *,
    chapter: str,
    decision: str,
    reason: str,
    reviewed: bool,
) -> ProductDispositionResult:
    plan = _build_product_disposition_plan(
        root,
        chapter=chapter,
        decision=decision,
        reason=reason,
        reviewed=reviewed,
    )
    return ProductDispositionResult(
        target=plan.target,
        ok=not plan.errors,
        chapter=plan.chapter,
        decision=plan.decision,
        reason=plan.reason,
        reviewed=plan.reviewed,
        check=True,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        disposition=plan.disposition,
        document=plan.document,
        state=plan.state,
    )


def record_product_disposition(
    root: Path,
    *,
    chapter: str,
    decision: str,
    reason: str,
    reviewed: bool,
) -> ProductDispositionResult:
    root = root.resolve()
    plan = _build_product_disposition_plan(
        root,
        chapter=chapter,
        decision=decision,
        reason=reason,
        reviewed=reviewed,
    )
    if plan.errors:
        return ProductDispositionResult(
            target=plan.target,
            ok=False,
            chapter=plan.chapter,
            decision=plan.decision,
            reason=plan.reason,
            reviewed=plan.reviewed,
            errors=plan.errors,
            warnings=plan.warnings,
            disposition=plan.disposition,
            document=plan.document,
            state=plan.state,
        )

    updated: list[str] = []
    if plan.would_update:
        try:
            _write_atomic_bytes(root, root / PRODUCT_DISPOSITIONS_REL, plan.rendered)
        except OSError as error:
            return ProductDispositionResult(
                target=plan.target,
                ok=False,
                chapter=plan.chapter,
                decision=plan.decision,
                reason=plan.reason,
                reviewed=plan.reviewed,
                errors=[
                    f"product chapter disposition document is not writable: "
                    f"{PRODUCT_DISPOSITIONS_REL.as_posix()}: {_os_error_reason(error)}"
                ],
                warnings=plan.warnings,
                disposition=plan.disposition,
                document=plan.document,
                state=plan.state,
            )
        updated = list(plan.would_update)

    return ProductDispositionResult(
        target=plan.target,
        ok=True,
        chapter=plan.chapter,
        decision=plan.decision,
        reason=plan.reason,
        reviewed=plan.reviewed,
        warnings=plan.warnings,
        updated=updated,
        disposition=plan.disposition,
        document=plan.document,
        state=plan.state,
    )


def build_product_disposition_inventory(root: Path) -> dict[str, object]:
    root = root.resolve()
    document, document_errors = load_product_disposition_document(root)
    prd_sha256, source_errors = _product_prd_sha256(root)
    dispositions = _dict_items(document.get("dispositions")) if not document_errors else []
    active = [item for item in dispositions if item.get("prd_sha256") == prd_sha256] if prd_sha256 else []
    stale = [item for item in dispositions if item.get("prd_sha256") != prd_sha256] if prd_sha256 else dispositions
    return {
        "path": PRODUCT_DISPOSITIONS_REL.as_posix(),
        "exists": (root / PRODUCT_DISPOSITIONS_REL).is_file(),
        "schema_version": document.get("schema_version", PRODUCT_DISPOSITION_SCHEMA_VERSION),
        "current_prd_sha256": prd_sha256,
        "active": copy.deepcopy(active),
        "stale": copy.deepcopy(stale),
        "errors": [*document_errors, *source_errors],
    }


def load_product_disposition_document(root: Path) -> tuple[dict[str, Any], list[str]]:
    root = root.resolve()
    path = root / PRODUCT_DISPOSITIONS_REL
    if path.is_symlink():
        return _empty_document(), [
            f"product chapter disposition document must not be a symbolic link: {PRODUCT_DISPOSITIONS_REL.as_posix()}"
        ]
    if not path.exists():
        return _empty_document(), []
    if not path.is_file():
        return _empty_document(), [
            f"product chapter disposition document is not a file: {PRODUCT_DISPOSITIONS_REL.as_posix()}"
        ]
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return _empty_document(), ["product chapter disposition document must be UTF-8 JSON"]
    except json.JSONDecodeError as error:
        return _empty_document(), [f"product chapter disposition document is invalid JSON: {error.msg}"]
    except OSError as error:
        return _empty_document(), [
            f"product chapter disposition document is unreadable: {_os_error_reason(error)}"
        ]
    if not isinstance(loaded, dict):
        return _empty_document(), ["product chapter disposition document root must be an object"]
    errors = _validate_document(loaded)
    return copy.deepcopy(loaded), errors


def _build_product_disposition_plan(
    root: Path,
    *,
    chapter: str,
    decision: str,
    reason: str,
    reviewed: bool,
) -> _ProductDispositionPlan:
    root = root.resolve()
    normalized_chapter = chapter.strip() if isinstance(chapter, str) else ""
    normalized_decision = decision.strip() if isinstance(decision, str) else ""
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
    elif phase != PRODUCT_DISPOSITION_PHASE:
        errors.append(f"product disposition requires recorded phase {PRODUCT_DISPOSITION_PHASE}")
    if normalized_chapter not in PRODUCT_CHAPTER_KEYS:
        errors.append(f"unknown product chapter: {normalized_chapter or '<missing>'}")
    if normalized_decision not in PRODUCT_DISPOSITION_DECISIONS:
        errors.append(f"unsupported product chapter disposition: {normalized_decision or '<missing>'}")
    if normalized_decision == "omit-unsupported" and normalized_chapter in NON_OMITTABLE_PRODUCT_CHAPTERS:
        errors.append(f"required product chapter cannot be omitted: {normalized_chapter}")
    if reviewed is not True:
        errors.append("--reviewed is required")
    if not _concrete_reason(normalized_reason):
        errors.append("reason must be a concrete source-review explanation")

    prd_sha256, source_errors = _product_prd_sha256(root)
    errors.extend(source_errors)
    document, document_errors = load_product_disposition_document(root)
    errors.extend(document_errors)
    dispositions = _dict_items(document.get("dispositions")) if not document_errors else []
    existing = next((item for item in dispositions if item.get("chapter") == normalized_chapter), {})
    recorded_at = utc_now()
    if (
        existing.get("decision") == normalized_decision
        and existing.get("reason") == normalized_reason
        and existing.get("reviewed") is True
        and existing.get("review_scope") == list(PRODUCT_DISPOSITION_REVIEW_SCOPE)
        and existing.get("source_path") == PRODUCT_PRD_REL.as_posix()
        and existing.get("prd_sha256") == prd_sha256
        and isinstance(existing.get("recorded_at"), str)
    ):
        recorded_at = str(existing["recorded_at"])
    disposition = {
        "chapter": normalized_chapter,
        "decision": normalized_decision,
        "reason": normalized_reason,
        "reviewed": reviewed is True,
        "review_scope": list(PRODUCT_DISPOSITION_REVIEW_SCOPE),
        "source_path": PRODUCT_PRD_REL.as_posix(),
        "prd_sha256": prd_sha256,
        "recorded_at": recorded_at,
    }
    updated_dispositions = [item for item in dispositions if item.get("chapter") != normalized_chapter]
    if normalized_chapter:
        updated_dispositions.append(disposition)
    updated_dispositions.sort(key=_disposition_sort_key)
    updated_document = {
        "schema_version": PRODUCT_DISPOSITION_SCHEMA_VERSION,
        "dispositions": updated_dispositions,
    }
    rendered = (json.dumps(updated_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path = root / PRODUCT_DISPOSITIONS_REL
    errors.extend(_product_disposition_output_errors(root, path))
    current = b""
    if path.is_file():
        try:
            current = path.read_bytes()
        except OSError as error:
            errors.append(f"product chapter disposition document is unreadable: {_os_error_reason(error)}")
    would_update = [PRODUCT_DISPOSITIONS_REL.as_posix()] if not errors and current != rendered else []
    return _ProductDispositionPlan(
        target=str(root),
        chapter=normalized_chapter,
        decision=normalized_decision,
        reason=normalized_reason,
        reviewed=reviewed is True,
        errors=_dedupe_strings(errors),
        warnings=warnings,
        disposition=disposition,
        document=updated_document,
        rendered=rendered,
        would_update=would_update,
        state=state,
    )


def _validate_document(document: dict[str, object]) -> list[str]:
    errors: list[str] = []
    schema_version = document.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != PRODUCT_DISPOSITION_SCHEMA_VERSION
    ):
        errors.append(
            f"product chapter disposition document schema_version must be {PRODUCT_DISPOSITION_SCHEMA_VERSION}"
        )
    dispositions = document.get("dispositions")
    if not isinstance(dispositions, list):
        errors.append("product chapter disposition document dispositions must be a list")
        return errors
    seen: set[str] = set()
    for index, item in enumerate(dispositions):
        prefix = f"product chapter disposition entry {index + 1}"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        chapter = item.get("chapter")
        decision = item.get("decision")
        reason = item.get("reason")
        reviewed = item.get("reviewed")
        review_scope = item.get("review_scope")
        source_path = item.get("source_path")
        prd_sha256 = item.get("prd_sha256")
        recorded_at = item.get("recorded_at")
        if chapter not in PRODUCT_CHAPTER_KEYS:
            errors.append(f"{prefix} has unknown chapter: {chapter}")
        elif chapter in seen:
            errors.append(f"duplicate product chapter disposition: {chapter}")
        else:
            seen.add(str(chapter))
        if decision not in PRODUCT_DISPOSITION_DECISIONS:
            errors.append(f"{prefix} has unsupported decision: {decision}")
        if decision == "omit-unsupported" and chapter in NON_OMITTABLE_PRODUCT_CHAPTERS:
            errors.append(f"required product chapter cannot be omitted: {chapter}")
        if not isinstance(reason, str) or not _concrete_reason(reason):
            errors.append(f"{prefix} reason must be a concrete source-review explanation")
        if reviewed is not True:
            errors.append(f"{prefix} reviewed must be true")
        if review_scope != list(PRODUCT_DISPOSITION_REVIEW_SCOPE):
            errors.append(
                f"{prefix} review_scope must be {', '.join(PRODUCT_DISPOSITION_REVIEW_SCOPE)}"
            )
        if source_path != PRODUCT_PRD_REL.as_posix():
            errors.append(f"{prefix} source_path must be {PRODUCT_PRD_REL.as_posix()}")
        if not isinstance(prd_sha256, str) or SHA256_RE.fullmatch(prd_sha256) is None:
            errors.append(f"{prefix} prd_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(recorded_at, str) or not _valid_timestamp(recorded_at):
            errors.append(f"{prefix} recorded_at must be an ISO-8601 timestamp")
    return _dedupe_strings(errors)


def _product_prd_sha256(root: Path) -> tuple[str, list[str]]:
    path = root / PRODUCT_PRD_REL
    if not path.exists():
        return "", [f"required product disposition source is missing: {PRODUCT_PRD_REL.as_posix()}"]
    if not path.is_file():
        return "", [f"required product disposition source is not a file: {PRODUCT_PRD_REL.as_posix()}"]
    try:
        content = path.read_bytes()
        content.decode("utf-8")
    except UnicodeDecodeError:
        return "", [f"required product disposition source must be UTF-8 Markdown: {PRODUCT_PRD_REL.as_posix()}"]
    except OSError as error:
        return "", [f"required product disposition source is unreadable: {_os_error_reason(error)}"]
    return hashlib.sha256(content).hexdigest(), []


def _empty_document() -> dict[str, Any]:
    return {"schema_version": PRODUCT_DISPOSITION_SCHEMA_VERSION, "dispositions": []}


def _dict_items(value: object) -> list[dict[str, Any]]:
    return (
        [copy.deepcopy(item) for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _concrete_reason(reason: str) -> bool:
    normalized = reason.strip()
    return (
        len(normalized) >= 16
        and normalized not in {"-", "none", "n/a"}
        and PLACEHOLDER_REASON_RE.search(normalized) is None
    )


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _disposition_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    chapter = str(item.get("chapter", ""))
    try:
        sequence = PRODUCT_CHAPTER_KEYS.index(chapter)
    except ValueError:
        sequence = len(PRODUCT_CHAPTER_KEYS)
    return sequence, chapter


def _product_disposition_output_errors(root: Path, path: Path) -> list[str]:
    errors: list[str] = []
    try:
        relative = path.relative_to(root)
        resolved_parent = path.parent.resolve()
        resolved_parent.relative_to(root)
    except ValueError:
        return [
            "product chapter disposition output parent resolves outside target: "
            f"{PRODUCT_DISPOSITIONS_REL.parent.as_posix()}"
        ]
    except OSError as error:
        return [f"product chapter disposition output parent is invalid: {_os_error_reason(error)}"]

    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink() and not current.exists():
            errors.append(
                "product chapter disposition output parent contains a broken symbolic link: "
                f"{current.relative_to(root).as_posix()}"
            )
            break
        if current.exists() and not current.is_dir():
            errors.append(
                "product chapter disposition output parent is not a directory: "
                f"{current.relative_to(root).as_posix()}"
            )
            break

    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        errors.append(
            "product chapter disposition temporary path already exists: "
            f"{temp.relative_to(root).as_posix()}"
        )
    return errors


def _write_atomic_bytes(root: Path, path: Path, content: bytes) -> None:
    output_errors = _product_disposition_output_errors(root, path)
    if output_errors:
        raise OSError(output_errors[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _atomic_temp_path(path)
    if temp.exists() or temp.is_symlink():
        raise OSError(f"temporary path already exists: {temp}")
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


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)
