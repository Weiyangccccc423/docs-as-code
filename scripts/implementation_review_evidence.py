from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import fcntl

try:
    from .bounded_process import run_bounded_command
    from .state import load_state, utc_now
except ImportError:  # pragma: no cover - target runtime uses POSIX wrappers
    from bounded_process import run_bounded_command
    from state import load_state, utc_now


CODE_REVIEW_AUTHORITY_SKILL = "code-reviewer"
CODE_REVIEW_EVIDENCE_REL = Path("docs/development/05-code-review-evidence.json")
IMPLEMENTATION_BASELINES_REL = Path(".governance/implementation-change-baselines.json")
IMPLEMENTATION_REVIEW_LOCK_REL = Path(".governance/implementation-review.lock")
TASK_BOARD_REL = Path("docs/development/02-task-board.md")
VERIFICATION_LOG_REL = Path("docs/development/03-verification-log.md")
AUTHORITY_LOCK_REL = Path("references/authority-skills.lock.json")
TARGET_AUTHORITY_LOCK_REL = Path("docs/agent-workflow/workflow-pack/references/authority-skills.lock.json")
IMPLEMENTATION_PHASE = "implementation"
BASELINE_SCHEMA_VERSION = 1
CODE_REVIEW_SCHEMA_VERSION = 1
CODE_REVIEW_REPORT_SCHEMA_VERSION = 1
GIT_TIMEOUT_SECONDS = 30.0
GIT_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_INVENTORY_PATHS = 100_000
MAX_INVENTORY_BYTES = 2 * 1024 * 1024 * 1024
MAX_REPORT_BYTES = 262_144
MAX_BASELINE_DOCUMENT_BYTES = 64 * 1024 * 1024
MAX_EVIDENCE_DOCUMENT_BYTES = 64 * 1024 * 1024
MAX_FINDINGS = 200
TASK_ID_RE = re.compile(r"^TASK-[0-9]{3}$")
FINDING_ID_RE = re.compile(r"^CR-[0-9]{3}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVIEWER_KINDS = {"agent", "human", "pair"}
REVIEW_VERDICTS = {"approved", "approved-with-suggestions"}
FINDING_SEVERITIES = {"critical", "high", "medium", "low"}
FINDING_STATUSES = {"resolved", "false-positive", "accepted-risk", "open"}
CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".cshtml",
    ".csx",
    ".cxx",
    ".dart",
    ".go",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".mjs",
    ".php",
    ".phtml",
    ".py",
    ".rb",
    ".rake",
    ".razor",
    ".rs",
    ".ru",
    ".swift",
    ".ts",
    ".tsx",
}
CHANGE_SET_EXCLUDED_PATHS = {
    "docs/development/01-roadmap.md",
    "docs/development/02-task-board.md",
    "docs/development/03-verification-log.md",
    "docs/development/04-implementation-evidence.md",
    "docs/development/05-code-review-evidence.json",
    "docs/development/README.md",
}


class ImplementationReviewLockUnavailable(RuntimeError):
    pass


@contextmanager
def _implementation_review_lock(root: Path) -> Iterator[None]:
    path = root / IMPLEMENTATION_REVIEW_LOCK_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ImplementationReviewLockUnavailable(
                f"another implementation evidence writer holds {IMPLEMENTATION_REVIEW_LOCK_REL.as_posix()}"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def build_implementation_baseline_capture(root: Path, task_id: str) -> dict[str, object]:
    return _compact_baseline_capture(_build_implementation_baseline_capture(root, task_id))


def _build_implementation_baseline_capture(root: Path, task_id: str) -> dict[str, object]:
    root = root.resolve()
    task_id = task_id.strip()
    errors: list[str] = []
    phase = _phase(root, errors)
    task = _task_row(root, task_id, errors)
    status = _normalize(str(task.get("status", ""))) if task else ""
    document, document_errors = _load_baseline_document(root)
    errors.extend(document_errors)
    existing = _baseline_for_task(document, task_id)
    inventory: dict[str, object] = {}

    if not errors and not existing and status == "ready":
        inventory = _git_inventory(root)
        errors.extend(_strings(inventory.get("errors")))
    elif not errors and existing:
        inventory = _dict(existing.get("inventory"))
        errors.extend(_validate_inventory(inventory, "stored implementation baseline"))
    elif not errors and status == "in progress":
        errors.append(
            "implementation change baseline is missing for an In Progress task; do not recapture after edits"
        )

    baseline = existing or _new_baseline(task_id, inventory)
    capture_ready = not errors and bool(existing or inventory)
    return {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "task_id": task_id,
        "task_status": str(task.get("status", "")) if task else "",
        "path": IMPLEMENTATION_BASELINES_REL.as_posix(),
        "capture_ready": capture_ready,
        "existing": bool(existing),
        "baseline": baseline,
        "inventory_summary": _inventory_summary(inventory),
        "errors": errors,
    }


def capture_implementation_baseline(root: Path, task_id: str) -> dict[str, object]:
    root = root.resolve()
    try:
        with _implementation_review_lock(root):
            return _capture_implementation_baseline(root, task_id)
    except (OSError, ImplementationReviewLockUnavailable) as error:
        result = build_implementation_baseline_capture(root, task_id)
        result.update(
            {
                "ok": False,
                "captured": False,
                "already_current": False,
                "updated_paths": [],
                "errors": [f"implementation baseline lock is unavailable: {error}"],
            }
        )
        return result


def _capture_implementation_baseline(root: Path, task_id: str) -> dict[str, object]:
    root = root.resolve()
    plan = _build_implementation_baseline_capture(root, task_id)
    result = {
        **_compact_baseline_capture(plan),
        "captured": False,
        "already_current": False,
        "updated_paths": [],
    }
    if plan.get("capture_ready") is not True:
        result["ok"] = False
        return result
    if plan.get("existing") is True:
        result["already_current"] = True
        return result

    document, errors = _load_baseline_document(root)
    if errors:
        result["ok"] = False
        result["errors"] = errors
        return result
    if _baseline_for_task(document, task_id):
        result["already_current"] = True
        return result
    baselines = _dicts(document.get("baselines"))
    baselines.append(_dict(plan.get("baseline")))
    next_document = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "baselines": baselines,
    }
    try:
        _write_json_atomic(root / IMPLEMENTATION_BASELINES_REL, next_document)
    except OSError as error:
        result["ok"] = False
        result["errors"] = [
            f"implementation baseline is not writable: {IMPLEMENTATION_BASELINES_REL.as_posix()}: "
            f"{error.strerror or error}"
        ]
        return result
    result["captured"] = True
    result["updated_paths"] = [IMPLEMENTATION_BASELINES_REL.as_posix()]
    return result


def build_implementation_review(
    root: Path,
    task_id: str,
    *,
    report_path: Path | None = None,
    reviewed: bool = False,
    check: bool = False,
    skill_roots: list[Path] | None = None,
) -> dict[str, object]:
    root = root.resolve()
    task_id = task_id.strip()
    errors: list[str] = []
    phase = _phase(root, errors)
    task = _task_row(root, task_id, errors)
    task_status = _normalize(str(task.get("status", ""))) if task else ""
    if task and task_status not in {"in progress", "done"}:
        errors.append("implementation review inspection requires an In Progress or Done task")
    if report_path is not None and task and task_status != "in progress":
        errors.append("recording implementation review evidence requires an In Progress task")

    baseline_document, baseline_errors = _load_baseline_document(root)
    errors.extend(baseline_errors)
    baseline = _baseline_for_task(baseline_document, task_id)
    if not baseline and not baseline_errors:
        errors.append("implementation review requires the immutable task-start change baseline")

    current_inventory: dict[str, object] = {}
    change_set: dict[str, object] = {}
    if not errors:
        current_inventory = _git_inventory(root)
        errors.extend(_strings(current_inventory.get("errors")))
    if not errors:
        change_set = _build_change_set(_dict(baseline.get("inventory")), current_inventory)
        errors.extend(_strings(change_set.get("errors")))
        if not _strings(change_set.get("changed_paths")):
            errors.append("implementation review requires at least one non-generated task change")

    authority = _code_reviewer_authority(root, skill_roots or [])
    if authority.get("provenance_ready") is not True:
        errors.extend(_strings(authority.get("errors")) or ["code-reviewer authority skill is unavailable"])

    evidence_document, evidence_errors = _load_review_evidence_document(root)
    errors.extend(evidence_errors)
    verification_evidence = _verification_evidence(root, task_id)
    errors.extend(_strings(verification_evidence.get("errors")))
    if not _strings(verification_evidence.get("errors")):
        verification_rows = _dicts(verification_evidence.get("rows"))
        if not verification_rows:
            errors.append("implementation review requires current verification evidence")
        elif any(_normalize(str(row.get("result", ""))) != "pass" for row in verification_rows):
            errors.append("implementation review requires every current verification result to pass")
    task_fingerprint = _task_fingerprint(task)
    active_review, stale_review, stale_reasons = _review_status(
        evidence_document,
        task_id=task_id,
        baseline=baseline,
        change_set=change_set,
        authority=authority,
        task_fingerprint=task_fingerprint,
        verification_evidence=verification_evidence,
    )

    report: dict[str, object] = {}
    report_errors: list[str] = []
    if report_path is not None:
        report, report_errors = _load_review_report(root, report_path, task_id)
        if report and not report_errors:
            report_errors.extend(_validate_report_change_set(report, change_set))
        if not reviewed:
            report_errors.append("implementation review apply requires --reviewed")
        errors.extend(report_errors)

    review = {}
    if report and not errors:
        review = _new_review(
            task_id=task_id,
            report=report,
            baseline=baseline,
            change_set=change_set,
            authority=authority,
            task_fingerprint=task_fingerprint,
            verification_evidence=verification_evidence,
        )
    already_current = bool(
        review
        and active_review
        and active_review.get("review_id") == review.get("review_id")
    )
    would_update = bool(review and not already_current)
    evidence_current = (
        bool(active_review) and not errors
        if report_path is None
        else bool(review and not errors)
    )
    status = _review_status_name(errors, evidence_current, stale_review, report_path)
    result = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": "workflows/06-implementation-execution.md",
        "decision_policy": "review_complete_task_change_set_before_closeout",
        "task_id": task_id,
        "task_status": str(task.get("status", "")) if task else "",
        "status": status,
        "check": check,
        "reviewed": reviewed,
        "apply_requested": report_path is not None and not check,
        "applied": False,
        "already_current": already_current,
        "review_ready": bool(review and not errors),
        "evidence_current": evidence_current,
        "evidence_path": CODE_REVIEW_EVIDENCE_REL.as_posix(),
        "baseline_path": IMPLEMENTATION_BASELINES_REL.as_posix(),
        "baseline": _baseline_summary(baseline),
        "change_set": change_set,
        "authority_skill": authority,
        "authority_review_context": _authority_review_context(authority, change_set),
        "report_contract": _report_contract(root, task_id),
        "report": report,
        "review": review or active_review or stale_review,
        "stale_reasons": stale_reasons,
        "verification_evidence": verification_evidence,
        "task_fingerprint": task_fingerprint,
        "would_update": [CODE_REVIEW_EVIDENCE_REL.as_posix()] if would_update else [],
        "updated": [],
        "errors": list(dict.fromkeys(errors)),
        "review_command": _review_command(root, task_id),
    }
    return result


def record_implementation_review(
    root: Path,
    task_id: str,
    *,
    report_path: Path,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> dict[str, object]:
    root = root.resolve()
    try:
        with _implementation_review_lock(root):
            return _record_implementation_review(
                root,
                task_id,
                report_path=report_path,
                reviewed=reviewed,
                skill_roots=skill_roots,
            )
    except (OSError, ImplementationReviewLockUnavailable) as error:
        plan = build_implementation_review(root, task_id, skill_roots=skill_roots)
        plan.update(
            {
                "ok": False,
                "status": "blocked",
                "errors": [f"implementation review evidence lock is unavailable: {error}"],
            }
        )
        return plan


def _record_implementation_review(
    root: Path,
    task_id: str,
    *,
    report_path: Path,
    reviewed: bool,
    skill_roots: list[Path] | None = None,
) -> dict[str, object]:
    root = root.resolve()
    plan = build_implementation_review(
        root,
        task_id,
        report_path=report_path,
        reviewed=reviewed,
        check=False,
        skill_roots=skill_roots,
    )
    if plan.get("review_ready") is not True:
        return plan
    if plan.get("already_current") is True:
        plan["status"] = "current"
        plan["evidence_current"] = True
        return plan

    document, errors = _load_review_evidence_document(root)
    if errors:
        plan["ok"] = False
        plan["errors"] = errors
        return plan
    reviews = _dicts(document.get("reviews"))
    reviews.append(_dict(plan.get("review")))
    next_document = {
        "schema_version": CODE_REVIEW_SCHEMA_VERSION,
        "reviews": reviews,
    }
    try:
        _write_json_atomic(root / CODE_REVIEW_EVIDENCE_REL, next_document)
    except OSError as error:
        plan["ok"] = False
        plan["status"] = "blocked"
        plan["errors"] = [
            f"code review evidence is not writable: {CODE_REVIEW_EVIDENCE_REL.as_posix()}: "
            f"{error.strerror or error}"
        ]
        return plan

    refreshed = build_implementation_review(root, task_id, skill_roots=skill_roots)
    refreshed.update(
        {
            "check": False,
            "reviewed": reviewed,
            "apply_requested": True,
            "applied": True,
            "already_current": False,
            "updated": [CODE_REVIEW_EVIDENCE_REL.as_posix()],
            "would_update": [],
        }
    )
    return refreshed


def _phase(root: Path, errors: list[str]) -> str:
    try:
        state = load_state(root)
    except (OSError, ValueError) as error:
        errors.append(f"governance state is unavailable: {error}")
        return ""
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    if phase != IMPLEMENTATION_PHASE:
        errors.append(f"implementation review requires recorded phase {IMPLEMENTATION_PHASE}")
    return phase


def _task_row(root: Path, task_id: str, errors: list[str]) -> dict[str, str]:
    if TASK_ID_RE.fullmatch(task_id) is None:
        errors.append("implementation review requires --task TASK-NNN")
        return {}
    rows, row_errors = _markdown_rows(root / TASK_BOARD_REL)
    errors.extend(f"task board is invalid: {error}" for error in row_errors)
    row = next((item for item in rows if item.get("id", "").strip() == task_id), {})
    if not row and not row_errors:
        errors.append(f"implementation task not found: {task_id}")
    return row


def _markdown_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [], [error.strerror if isinstance(error, OSError) and error.strerror else str(error)]
    header: list[str] = []
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        cells = _markdown_cells(line)
        if cells is None:
            if header and rows:
                break
            continue
        normalized = [_normalize(cell) for cell in cells]
        if not header:
            if "id" in normalized or "task" in normalized:
                header = normalized
            continue
        if _separator_cells(cells):
            continue
        if len(cells) != len(header):
            return [], ["table row column count does not match header"]
        rows.append(dict(zip(header, cells)))
    if not header:
        return [], ["required Markdown table was not found"]
    return rows, []


def _markdown_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _separator_cells(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _git_inventory(root: Path) -> dict[str, object]:
    errors: list[str] = []
    repository = _run_git(root, ["rev-parse", "--is-inside-work-tree"], 4096)
    if repository.get("ok") is not True or str(repository.get("stdout", "")).strip() != "true":
        return {
            "schema_version": 1,
            "source": "git-ls-files",
            "files": [],
            "digest": "",
            "errors": [
                "implementation change evidence requires a Git work tree; initialize Git before claiming a task"
            ],
        }
    listed = _run_git(
        root,
        ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        GIT_MAX_OUTPUT_BYTES,
    )
    if listed.get("ok") is not True:
        return {
            "schema_version": 1,
            "source": "git-ls-files",
            "files": [],
            "digest": "",
            "errors": _strings(listed.get("errors")),
        }
    raw_paths = str(listed.get("stdout", "")).split("\0")
    paths = sorted({path for path in raw_paths if path and not _change_set_path_excluded(path)})
    if len(paths) > MAX_INVENTORY_PATHS:
        errors.append(
            f"Git change inventory exceeds {MAX_INVENTORY_PATHS} non-ignored files; refine .gitignore before retrying"
        )
    files: list[dict[str, object]] = []
    total_bytes = 0
    for rel in paths[: MAX_INVENTORY_PATHS + 1]:
        path_error = _safe_inventory_path(rel)
        if path_error:
            errors.append(path_error)
            continue
        try:
            candidate = (root / rel).lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            errors.append(
                f"Git inventory path is unavailable: {rel}: {error.strerror or error}"
            )
            continue
        if (
            not (root / rel).is_symlink()
            and (root / rel).is_file()
            and candidate.st_size > MAX_INVENTORY_BYTES - total_bytes
        ):
            errors.append(
                f"Git change inventory exceeds {MAX_INVENTORY_BYTES} bytes; refine .gitignore before retrying"
            )
            break
        evidence, evidence_errors = _path_evidence(
            root,
            rel,
            max_bytes=MAX_INVENTORY_BYTES - total_bytes,
        )
        errors.extend(evidence_errors)
        if evidence:
            total_bytes += int(evidence.get("size", 0))
            files.append(evidence)
        if total_bytes > MAX_INVENTORY_BYTES:
            errors.append(
                f"Git change inventory exceeds {MAX_INVENTORY_BYTES} bytes; refine .gitignore before retrying"
            )
            break
    material = {"schema_version": 1, "source": "git-ls-files", "files": files}
    return {
        **material,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "digest": _canonical_sha256(material) if not errors else "",
        "errors": list(dict.fromkeys(errors)),
    }


def _run_git(root: Path, args: list[str], max_output_bytes: int) -> dict[str, object]:
    run = run_bounded_command(
        ["git", "-C", str(root), *args],
        cwd=root,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        max_output_bytes=max_output_bytes,
    )
    errors: list[str] = []
    if run.get("result") != "pass":
        detail = str(run.get("stderr", "")).strip() or str(run.get("result", "git command failed"))
        errors.append(f"Git inventory command failed: {detail}")
    if run.get("stdout_truncated") is True or run.get("stderr_truncated") is True:
        errors.append("Git inventory command output exceeded its safety bound")
    if run.get("output_redacted") is True:
        errors.append("Git inventory output required redaction and cannot be used as machine data")
    return {
        "ok": not errors,
        "stdout": str(run.get("stdout", "")),
        "errors": errors,
    }


def _path_evidence(
    root: Path,
    rel: str,
    *,
    max_bytes: int,
) -> tuple[dict[str, object], list[str]]:
    path = root / rel
    try:
        before = path.lstat()
    except OSError as error:
        return {}, [f"Git inventory path is unavailable: {rel}: {error.strerror or error}"]
    if path.is_symlink():
        try:
            target = os.readlink(path)
            after = path.lstat()
        except OSError as error:
            return {}, [f"Git inventory symlink is unreadable: {rel}: {error.strerror or error}"]
        encoded_target = target.encode("utf-8", errors="surrogateescape")
        if len(encoded_target) > max_bytes:
            return {}, [
                f"Git change inventory exceeds {MAX_INVENTORY_BYTES} bytes; refine .gitignore before retrying"
            ]
        if (before.st_ino, before.st_mode, before.st_mtime_ns) != (
            after.st_ino,
            after.st_mode,
            after.st_mtime_ns,
        ):
            return {}, [f"Git inventory symlink changed while being hashed: {rel}"]
        return {
            "path": rel,
            "kind": "symlink",
            "mode": "120000",
            "size": len(encoded_target),
            "sha256": hashlib.sha256(encoded_target).hexdigest(),
        }, []
    if not stat.S_ISREG(before.st_mode):
        return {}, [f"Git inventory path must be a regular file or symlink: {rel}"]
    digest = hashlib.sha256()
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or (before.st_ino, before.st_mode) != (
                opened.st_ino,
                opened.st_mode,
            ):
                return {}, [f"Git inventory file changed before hashing: {rel}"]
            if opened.st_size > max_bytes:
                return {}, [
                    f"Git change inventory exceeds {MAX_INVENTORY_BYTES} bytes; refine .gitignore before retrying"
                ]
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
        final = path.lstat()
    except OSError as error:
        return {}, [f"Git inventory file is unreadable: {rel}: {error.strerror or error}"]
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if (opened.st_size, opened.st_mtime_ns, opened.st_ino, opened.st_mode) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
        after.st_mode,
    ) or (after.st_size, after.st_mtime_ns, after.st_ino, after.st_mode) != (
        final.st_size,
        final.st_mtime_ns,
        final.st_ino,
        final.st_mode,
    ):
        return {}, [f"Git inventory file changed while being hashed: {rel}"]
    return {
        "path": rel,
        "kind": "file",
        "mode": "100755" if opened.st_mode & 0o111 else "100644",
        "size": opened.st_size,
        "sha256": digest.hexdigest(),
    }, []


def _safe_inventory_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\0" in value:
        return f"Git inventory returned an unsafe path: {value!r}"
    return ""


def _change_set_path_excluded(value: str) -> bool:
    return value == ".governance" or value.startswith(".governance/") or value in CHANGE_SET_EXCLUDED_PATHS


def _new_baseline(task_id: str, inventory: dict[str, object]) -> dict[str, object]:
    if not inventory:
        return {}
    material = {
        "task_id": task_id,
        "inventory_digest": str(inventory.get("digest", "")),
        "inventory": inventory,
    }
    return {
        "baseline_id": _baseline_id(material),
        "captured_at": utc_now(),
        **material,
    }


def _baseline_id(material: dict[str, object]) -> str:
    return f"IB-{material.get('task_id', '')}-{_canonical_sha256(material)[:16]}"


def _build_change_set(
    baseline_inventory: dict[str, object],
    current_inventory: dict[str, object],
) -> dict[str, object]:
    errors = _validate_inventory(baseline_inventory, "implementation baseline")
    errors.extend(_validate_inventory(current_inventory, "current implementation inventory"))
    if errors:
        return {"changed_paths": [], "changes": [], "digest": "", "errors": errors}
    before = {str(item["path"]): item for item in _dicts(baseline_inventory.get("files"))}
    after = {str(item["path"]): item for item in _dicts(current_inventory.get("files"))}
    changes: list[dict[str, object]] = []
    for path in sorted(set(before) | set(after)):
        old = before.get(path)
        new = after.get(path)
        if old == new:
            continue
        status = "added" if old is None else "deleted" if new is None else "modified"
        changes.append(
            {
                "path": path,
                "status": status,
                "before_sha256": str(old.get("sha256", "")) if old else "",
                "after_sha256": str(new.get("sha256", "")) if new else "",
                "before_mode": str(old.get("mode", "")) if old else "",
                "after_mode": str(new.get("mode", "")) if new else "",
                "before_size": int(old.get("size", 0)) if old else 0,
                "after_size": int(new.get("size", 0)) if new else 0,
            }
        )
    material = {
        "schema_version": 1,
        "baseline_digest": str(baseline_inventory.get("digest", "")),
        "current_inventory_digest": str(current_inventory.get("digest", "")),
        "changes": changes,
    }
    return {
        **material,
        "changed_count": len(changes),
        "changed_paths": [str(item["path"]) for item in changes],
        "code_paths": [
            str(item["path"])
            for item in changes
            if Path(str(item["path"])).suffix.lower() in CODE_EXTENSIONS
        ],
        "digest": _canonical_sha256(material),
        "errors": [],
    }


def _validate_inventory(inventory: dict[str, object], label: str) -> list[str]:
    errors: list[str] = []
    if not inventory:
        return [f"{label} is missing"]
    if inventory.get("schema_version") != 1 or inventory.get("source") != "git-ls-files":
        errors.append(f"{label} schema is invalid")
    files = inventory.get("files")
    if not isinstance(files, list):
        errors.append(f"{label} files must be a list")
        return errors
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            errors.append(f"{label} contains a malformed file entry")
            continue
        path = item.get("path")
        if not isinstance(path, str) or _safe_inventory_path(path):
            errors.append(f"{label} contains an unsafe file path")
        elif path in seen:
            errors.append(f"{label} contains duplicate path: {path}")
        else:
            seen.add(path)
        kind = item.get("kind")
        if kind not in {"file", "symlink"}:
            errors.append(f"{label} contains an invalid file kind: {path}")
        expected_modes = {"100644", "100755"} if kind == "file" else {"120000"}
        if item.get("mode") not in expected_modes:
            errors.append(f"{label} contains an invalid file mode: {path}")
        if not isinstance(item.get("sha256"), str) or SHA256_RE.fullmatch(str(item.get("sha256"))) is None:
            errors.append(f"{label} contains an invalid file digest: {path}")
        if not isinstance(item.get("size"), int) or int(item.get("size", -1)) < 0:
            errors.append(f"{label} contains an invalid file size: {path}")
    material = {"schema_version": 1, "source": "git-ls-files", "files": files}
    if inventory.get("digest") != _canonical_sha256(material):
        errors.append(f"{label} digest does not match its file inventory")
    return list(dict.fromkeys(errors))


def _load_baseline_document(root: Path) -> tuple[dict[str, object], list[str]]:
    path = root / IMPLEMENTATION_BASELINES_REL
    if not path.exists():
        return {"schema_version": BASELINE_SCHEMA_VERSION, "baselines": []}, []
    document, errors = _load_json_object(
        path,
        "implementation baseline",
        MAX_BASELINE_DOCUMENT_BYTES,
    )
    if errors:
        return {}, errors
    if document.get("schema_version") != BASELINE_SCHEMA_VERSION:
        errors.append(f"implementation baseline schema_version must be {BASELINE_SCHEMA_VERSION}")
    baselines = document.get("baselines")
    if not isinstance(baselines, list):
        errors.append("implementation baseline baselines must be a list")
        return document, errors
    seen: set[str] = set()
    for baseline in baselines:
        if not isinstance(baseline, dict):
            errors.append("implementation baseline contains a malformed entry")
            continue
        task_id = baseline.get("task_id")
        if not isinstance(task_id, str) or TASK_ID_RE.fullmatch(task_id) is None:
            errors.append("implementation baseline entry has an invalid task_id")
        elif task_id in seen:
            errors.append(f"implementation baseline contains duplicate task: {task_id}")
        else:
            seen.add(task_id)
        errors.extend(_validate_inventory(_dict(baseline.get("inventory")), f"implementation baseline {task_id}"))
        if baseline.get("inventory_digest") != _dict(baseline.get("inventory")).get("digest"):
            errors.append(f"implementation baseline inventory digest mismatch: {task_id}")
        material = {
            "task_id": task_id,
            "inventory_digest": baseline.get("inventory_digest"),
            "inventory": baseline.get("inventory"),
        }
        if baseline.get("baseline_id") != _baseline_id(material):
            errors.append(f"implementation baseline content ID mismatch: {task_id}")
        if not _valid_utc_timestamp(baseline.get("captured_at")):
            errors.append(f"implementation baseline captured_at is invalid: {task_id}")
    return document, list(dict.fromkeys(errors))


def _baseline_for_task(document: dict[str, object], task_id: str) -> dict[str, object]:
    return next(
        (item for item in _dicts(document.get("baselines")) if item.get("task_id") == task_id),
        {},
    )


def _code_reviewer_authority(root: Path, skill_roots: list[Path]) -> dict[str, object]:
    try:
        from .authority_skills import build_authority_skill_inventory
    except ImportError:  # pragma: no cover - target runtime uses POSIX wrappers
        from authority_skills import build_authority_skill_inventory

    manifest_path = root / AUTHORITY_LOCK_REL
    if not manifest_path.is_file():
        manifest_path = root / TARGET_AUTHORITY_LOCK_REL
    try:
        inventory = build_authority_skill_inventory(
            skill_roots=skill_roots,
            strict=False,
            strict_provenance=False,
            manifest_path=manifest_path,
        )
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "name": CODE_REVIEW_AUTHORITY_SKILL,
            "provenance_ready": False,
            "errors": [f"code-reviewer authority inventory failed: {error}"],
        }
    skill = next(
        (
            item
            for item in _dicts(inventory.get("skills"))
            if item.get("name") == CODE_REVIEW_AUTHORITY_SKILL
        ),
        {},
    )
    ready = bool(
        skill
        and skill.get("status") == "current"
        and skill.get("source_registered") is True
        and skill.get("integrity_matches") is True
        and _dict(skill.get("trust")).get("status") == "approved"
    )
    errors = [] if ready else [
        "code-reviewer must be installed from the approved immutable source with matching tree integrity"
    ]
    return {
        "name": CODE_REVIEW_AUTHORITY_SKILL,
        "status": str(skill.get("status", "missing")),
        "provenance_ready": ready,
        "availability_scope": str(skill.get("availability_scope", "agent-environment")),
        "skill_path": str(skill.get("skill_path", "")),
        "sha256": str(skill.get("observed_sha256", "")),
        "source": _dict(skill.get("source")),
        "trust": _dict(skill.get("trust")),
        "errors": errors,
    }


def _authority_review_context(
    authority: dict[str, object], change_set: dict[str, object]
) -> dict[str, object]:
    skill_path = Path(str(authority.get("skill_path", ""))) if authority.get("skill_path") else None
    required_reads: list[str] = []
    if skill_path is not None:
        skill_root = skill_path.parent
        required_reads.append(str(skill_path))
        universal = skill_root / "rules/universal.md"
        if universal.is_file():
            required_reads.append(str(universal))
        language_names = sorted(
            {
                _language_name(Path(path).suffix.lower())
                for path in _strings(change_set.get("code_paths"))
                if _language_name(Path(path).suffix.lower())
            }
        )
        for language in language_names:
            language_path = skill_root / "languages" / f"{language}.md"
            if language_path.is_file():
                required_reads.append(str(language_path))
    return {
        "required_reads": required_reads,
        "review_paths": _strings(change_set.get("changed_paths")),
        "code_paths": _strings(change_set.get("code_paths")),
        "method": "code-reviewer-guided-task-change-review",
        "stop_condition": "record_no_approved_verdict_while_blocking_findings_remain",
    }


def _language_name(extension: str) -> str:
    mapping = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "typescript",
        ".jsx": "typescript",
        ".mjs": "typescript",
        ".go": "go",
        ".swift": "swift",
        ".kt": "kotlin",
        ".kts": "kotlin",
        ".cs": "csharp",
        ".csx": "csharp",
        ".razor": "csharp",
        ".cshtml": "csharp",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".rs": "rust",
        ".rb": "ruby",
        ".rake": "ruby",
        ".ru": "ruby",
        ".php": "php",
        ".phtml": "php",
        ".dart": "dart",
    }
    return mapping.get(extension, "")


def _load_review_report(
    root: Path, report_path: Path, task_id: str
) -> tuple[dict[str, object], list[str]]:
    path = report_path if report_path.is_absolute() else root / report_path
    try:
        resolved = path.resolve(strict=True)
        rel = resolved.relative_to(root)
    except (FileNotFoundError, OSError, ValueError):
        return {}, ["implementation review report must be an existing repository-local file"]
    if not rel.as_posix().startswith(".governance/code-review-reports/"):
        return {}, ["implementation review report must be under .governance/code-review-reports/"]
    if path.is_symlink() or not resolved.is_file():
        return {}, ["implementation review report must be a regular non-symlink file"]
    report, errors = _load_json_object(resolved, "implementation review report", MAX_REPORT_BYTES)
    if errors:
        return {}, errors
    errors.extend(_validate_review_report_value(root, report, task_id))
    return report, list(dict.fromkeys(errors))


def _validate_review_report_value(
    root: Path,
    report: dict[str, object],
    task_id: str,
) -> list[str]:
    errors: list[str] = []
    expected_keys = {"schema_version", "task_id", "reviewer", "verdict", "summary", "findings"}
    if set(report) != expected_keys:
        errors.append("implementation review report must contain exactly the documented top-level fields")
    if report.get("schema_version") != CODE_REVIEW_REPORT_SCHEMA_VERSION:
        errors.append(f"implementation review report schema_version must be {CODE_REVIEW_REPORT_SCHEMA_VERSION}")
    if report.get("task_id") != task_id:
        errors.append(f"implementation review report task_id must be {task_id}")
    reviewer = report.get("reviewer")
    if not isinstance(reviewer, dict) or set(reviewer) != {"kind", "id"}:
        errors.append("implementation review report reviewer must contain exactly kind and id")
    else:
        if reviewer.get("kind") not in REVIEWER_KINDS:
            errors.append("implementation review report reviewer.kind is invalid")
        reviewer_id = reviewer.get("id")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id) > 128:
            errors.append("implementation review report reviewer.id must be 1-128 characters")
    if report.get("verdict") not in REVIEW_VERDICTS:
        errors.append("implementation review report verdict must be approved or approved-with-suggestions")
    summary = report.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
        errors.append("implementation review report summary must be 1-4000 characters")
    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append("implementation review report findings must be a list")
    elif len(findings) > MAX_FINDINGS:
        errors.append(f"implementation review report findings exceed {MAX_FINDINGS}")
    else:
        errors.extend(_validate_findings(root, findings))
        if report.get("verdict") == "approved" and findings:
            unresolved_suggestions = [
                item for item in findings if isinstance(item, dict) and item.get("status") == "accepted-risk"
            ]
            if unresolved_suggestions:
                errors.append("approved verdict cannot retain accepted-risk findings; use approved-with-suggestions")
    return list(dict.fromkeys(errors))


def _validate_findings(root: Path, findings: list[object]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    expected = {"id", "severity", "status", "path", "message", "resolution"}
    for item in findings:
        if not isinstance(item, dict) or set(item) != expected:
            errors.append("each code review finding must contain exactly id, severity, status, path, message, resolution")
            continue
        finding_id = item.get("id")
        if not isinstance(finding_id, str) or FINDING_ID_RE.fullmatch(finding_id) is None:
            errors.append("code review finding id must match CR-NNN")
        elif finding_id in seen:
            errors.append(f"duplicate code review finding id: {finding_id}")
        else:
            seen.add(finding_id)
        severity = item.get("severity")
        status = item.get("status")
        if severity not in FINDING_SEVERITIES:
            errors.append(f"code review finding severity is invalid: {finding_id}")
        if status not in FINDING_STATUSES:
            errors.append(f"code review finding status is invalid: {finding_id}")
        if status == "open":
            errors.append(f"code review finding remains open: {finding_id}")
        if status == "accepted-risk" and severity in {"critical", "high"}:
            errors.append(f"critical or high code review finding cannot be accepted as residual risk: {finding_id}")
        path = item.get("path")
        if not isinstance(path, str) or _safe_inventory_path(path):
            errors.append(f"code review finding path is invalid: {finding_id}")
        message = item.get("message")
        resolution = item.get("resolution")
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            errors.append(f"code review finding message must be 1-2000 characters: {finding_id}")
        if not isinstance(resolution, str) or not resolution.strip() or len(resolution) > 2000:
            errors.append(f"code review finding resolution must be 1-2000 characters: {finding_id}")
    return errors


def _validate_report_change_set(
    report: dict[str, object], change_set: dict[str, object]
) -> list[str]:
    changed_paths = set(_strings(change_set.get("changed_paths")))
    out_of_scope = sorted(
        {
            str(item.get("path", ""))
            for item in _dicts(report.get("findings"))
            if str(item.get("path", "")) not in changed_paths
        }
    )
    return [
        f"code review finding path is outside the current task change set: {path}"
        for path in out_of_scope
    ]


def _new_review(
    *,
    task_id: str,
    report: dict[str, object],
    baseline: dict[str, object],
    change_set: dict[str, object],
    authority: dict[str, object],
    task_fingerprint: dict[str, object],
    verification_evidence: dict[str, object],
) -> dict[str, object]:
    material = {
        "task_id": task_id,
        "baseline_id": str(baseline.get("baseline_id", "")),
        "baseline_digest": str(baseline.get("inventory_digest", "")),
        "change_set_digest": str(change_set.get("digest", "")),
        "changed_paths": _strings(change_set.get("changed_paths")),
        "task_fingerprint": task_fingerprint,
        "verification_evidence": verification_evidence,
        "authority_skill": {
            "name": CODE_REVIEW_AUTHORITY_SKILL,
            "sha256": str(authority.get("sha256", "")),
            "source": _dict(authority.get("source")),
            "trust": _dict(authority.get("trust")),
        },
        "report": report,
    }
    digest = _canonical_sha256(material)
    return {
        "review_id": f"IR-{task_id}-{digest[:16]}",
        "reviewed_at": utc_now(),
        **material,
    }


def _load_review_evidence_document(root: Path) -> tuple[dict[str, object], list[str]]:
    path = root / CODE_REVIEW_EVIDENCE_REL
    if not path.exists():
        return {"schema_version": CODE_REVIEW_SCHEMA_VERSION, "reviews": []}, []
    document, errors = _load_json_object(
        path,
        "code review evidence",
        MAX_EVIDENCE_DOCUMENT_BYTES,
    )
    if errors:
        return {}, errors
    if document.get("schema_version") != CODE_REVIEW_SCHEMA_VERSION:
        errors.append(f"code review evidence schema_version must be {CODE_REVIEW_SCHEMA_VERSION}")
    reviews = document.get("reviews")
    if not isinstance(reviews, list):
        errors.append("code review evidence reviews must be a list")
        return document, errors
    seen: set[str] = set()
    expected_keys = {
        "review_id",
        "reviewed_at",
        "task_id",
        "baseline_id",
        "baseline_digest",
        "change_set_digest",
        "changed_paths",
        "task_fingerprint",
        "verification_evidence",
        "authority_skill",
        "report",
    }
    for review in reviews:
        if not isinstance(review, dict):
            errors.append("code review evidence contains a malformed review")
            continue
        if set(review) != expected_keys:
            errors.append("code review evidence entry contains unexpected or missing fields")
        review_id = review.get("review_id")
        if not isinstance(review_id, str) or not review_id:
            errors.append("code review evidence review_id must be non-empty")
        elif review_id in seen:
            errors.append(f"duplicate code review evidence review_id: {review_id}")
        else:
            seen.add(review_id)
        if not isinstance(review.get("task_id"), str) or TASK_ID_RE.fullmatch(str(review.get("task_id"))) is None:
            errors.append(f"code review evidence has invalid task_id: {review_id}")
        if not isinstance(review.get("change_set_digest"), str) or SHA256_RE.fullmatch(str(review.get("change_set_digest"))) is None:
            errors.append(f"code review evidence has invalid change_set_digest: {review_id}")
        changed_paths = review.get("changed_paths")
        if not isinstance(changed_paths, list) or any(
            not isinstance(path, str) or _safe_inventory_path(path) for path in changed_paths
        ):
            errors.append(f"code review evidence has invalid changed_paths: {review_id}")
        elif len(changed_paths) != len(set(changed_paths)):
            errors.append(f"code review evidence has duplicate changed_paths: {review_id}")
        authority = _dict(review.get("authority_skill"))
        if authority.get("name") != CODE_REVIEW_AUTHORITY_SKILL or SHA256_RE.fullmatch(str(authority.get("sha256", ""))) is None:
            errors.append(f"code review evidence has invalid authority skill: {review_id}")
        task_id = str(review.get("task_id", ""))
        report = _dict(review.get("report"))
        errors.extend(_validate_review_report_value(root, report, task_id))
        errors.extend(_validate_report_change_set(report, {"changed_paths": changed_paths}))
        if not _valid_utc_timestamp(review.get("reviewed_at")):
            errors.append(f"code review evidence reviewed_at is invalid: {review_id}")
        material = {
            key: review.get(key)
            for key in expected_keys
            if key not in {"review_id", "reviewed_at"}
        }
        expected_review_id = f"IR-{task_id}-{_canonical_sha256(material)[:16]}"
        if review_id != expected_review_id:
            errors.append(f"code review evidence content ID mismatch: {review_id}")
    return document, list(dict.fromkeys(errors))


def _review_status(
    document: dict[str, object],
    *,
    task_id: str,
    baseline: dict[str, object],
    change_set: dict[str, object],
    authority: dict[str, object],
    task_fingerprint: dict[str, object],
    verification_evidence: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], list[str]]:
    reviews = [item for item in _dicts(document.get("reviews")) if item.get("task_id") == task_id]
    if not reviews:
        return {}, {}, []
    latest = reviews[-1]
    reasons: list[str] = []
    if latest.get("baseline_id") != baseline.get("baseline_id") or latest.get("baseline_digest") != baseline.get("inventory_digest"):
        reasons.append("implementation task baseline changed after code review")
    if latest.get("change_set_digest") != change_set.get("digest"):
        reasons.append("implementation change set changed after code review")
    if latest.get("task_fingerprint") != task_fingerprint:
        reasons.append("implementation task traceability changed after code review")
    if latest.get("verification_evidence") != verification_evidence:
        reasons.append("implementation verification evidence changed after code review")
    recorded_authority = _dict(latest.get("authority_skill"))
    if authority.get("provenance_ready") is not True:
        reasons.append("code-reviewer authority skill is no longer provenance-ready")
    elif recorded_authority.get("sha256") != authority.get("sha256"):
        reasons.append("code-reviewer authority skill changed after review")
    return (latest, {}, []) if not reasons else ({}, latest, reasons)


def _verification_evidence(root: Path, task_id: str) -> dict[str, object]:
    rows, errors = _markdown_rows(root / VERIFICATION_LOG_REL)
    if errors:
        return {"rows": [], "digest": "", "errors": errors}
    task_rows = [row for row in rows if row.get("task", "").strip() == task_id]
    material = [
        {
            "task": row.get("task", "").strip(),
            "command": row.get("command", "").strip(),
            "result": row.get("result", "").strip(),
            "date": row.get("date", "").strip(),
            "notes": row.get("notes", "").strip(),
        }
        for row in task_rows
    ]
    return {
        "rows": material,
        "row_count": len(material),
        "digest": _canonical_sha256(material),
        "errors": [],
    }


def _task_fingerprint(task: dict[str, str]) -> dict[str, object]:
    material = {
        key: value.strip()
        for key, value in task.items()
        if key != "status"
    }
    return {"sha256": _canonical_sha256(material), "fields": material}


def _review_status_name(
    errors: list[str],
    evidence_current: bool,
    stale_review: dict[str, object],
    report_path: Path | None,
) -> str:
    if errors:
        return "blocked"
    if evidence_current:
        return "current"
    if stale_review:
        return "stale"
    if report_path is not None:
        return "ready_to_record"
    return "review_required"


def _report_contract(root: Path, task_id: str) -> dict[str, object]:
    example_path = f".governance/code-review-reports/{task_id}.json"
    return {
        "schema_version": CODE_REVIEW_REPORT_SCHEMA_VERSION,
        "path_policy": ".governance/code-review-reports/*.json",
        "example_path": example_path,
        "required_fields": ["schema_version", "task_id", "reviewer", "verdict", "summary", "findings"],
        "finding_fields": ["id", "severity", "status", "path", "message", "resolution"],
        "allowed_verdicts": sorted(REVIEW_VERDICTS),
        "allowed_finding_severities": sorted(FINDING_SEVERITIES),
        "allowed_finding_statuses": sorted(FINDING_STATUSES),
        "check_argv": [
            "bin/governance",
            "implementation",
            "review",
            ".",
            "--task",
            task_id,
            "--report",
            example_path,
            "--reviewed",
            "--check",
            "--json",
        ],
        "cwd": str(root),
    }


def _review_command(root: Path, task_id: str) -> dict[str, object]:
    return {
        "id": "inspect-implementation-code-review",
        "kind": "command",
        "cwd": str(root),
        "argv": ["bin/governance", "implementation", "review", ".", "--task", task_id, "--json"],
        "writes_state": False,
        "approval_required": False,
    }


def _compact_baseline_capture(payload: dict[str, object]) -> dict[str, object]:
    compact = {key: value for key, value in payload.items() if key != "inventory_summary"}
    compact["baseline"] = _baseline_summary(_dict(payload.get("baseline")))
    return compact


def _baseline_summary(baseline: dict[str, object]) -> dict[str, object]:
    inventory = _dict(baseline.get("inventory"))
    summary = _inventory_summary(inventory)
    return {
        "baseline_id": str(baseline.get("baseline_id", "")),
        "digest": str(baseline.get("inventory_digest", "")),
        "file_count": summary["file_count"],
        "total_bytes": summary["total_bytes"],
    }


def _inventory_summary(inventory: dict[str, object]) -> dict[str, object]:
    files = _dicts(inventory.get("files"))
    return {
        "file_count": len(files),
        "total_bytes": sum(int(item.get("size", 0)) for item in files),
        "digest": str(inventory.get("digest", "")),
    }


def _load_json_object(path: Path, label: str, max_bytes: int) -> tuple[dict[str, object], list[str]]:
    try:
        stat = path.lstat()
        if path.is_symlink() or not path.is_file():
            return {}, [f"{label} must be a regular non-symlink file"]
        if stat.st_size > max_bytes:
            return {}, [f"{label} exceeds {max_bytes} bytes"]
        value = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return {}, [f"{label} must be UTF-8"]
    except json.JSONDecodeError as error:
        return {}, [f"{label} must be valid JSON: {error.msg}"]
    except OSError as error:
        return {}, [f"{label} is unreadable: {error.strerror or error}"]
    if not isinstance(value, dict):
        return {}, [f"{label} root must be an object"]
    return value, []


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o644)
        temp_path.replace(path)
    except OSError:
        if temp_path is not None and temp_path.exists() and temp_path.is_file():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str) and item] if isinstance(value, list) else []
