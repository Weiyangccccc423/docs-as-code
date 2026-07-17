from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

try:
    from .state import STATE_REL
    from .workflow_plan import build_work_package, build_workflow_plan
except ImportError:  # pragma: no cover - direct script execution
    from state import STATE_REL
    from workflow_plan import build_work_package, build_workflow_plan


SCHEMA_VERSION = 1
SNAPSHOT_ALGORITHM = "sha256-canonical-json-v1"
DECISION_POLICY = "execute_exactly_one_selected_action_then_refresh"
INVARIANTS = (
    "refresh_after_action",
    "reject_stale_snapshot",
    "never_guess_missing_decisions",
)
BASELINE_INPUT_PATHS = (
    STATE_REL.as_posix(),
    ".governance/project-environment.json",
    ".governance/project-environment-repairs.json",
    "docs/product/core/PRD.md",
    "docs/product/core/source/source-manifest.json",
    "docs/unresolved.md",
    "docs/glossary.md",
)


def build_workflow_resume(
    root: Path,
    *,
    skill_roots: list[Path] | None = None,
    expect_snapshot: str = "",
) -> dict[str, object]:
    root = root.resolve()
    explicit_skill_roots = [path.expanduser().resolve() for path in (skill_roots or [])]
    if expect_snapshot and not _valid_snapshot_id(expect_snapshot):
        payload = _failed_payload(
            root,
            explicit_skill_roots,
            "Expected workflow snapshot must be a lowercase 64-character SHA-256 value.",
            expect_snapshot,
        )
        payload["stop_reasons"] = ["expected_snapshot_invalid"]
        return payload
    try:
        plan = build_workflow_plan(root)
        package = build_work_package(root, skill_roots=explicit_skill_roots)
        snapshot = _build_snapshot(root, plan, package)
    except (OSError, RuntimeError, ValueError) as error:
        return _failed_payload(root, explicit_skill_roots, str(error), expect_snapshot)

    actual_snapshot = str(snapshot["id"])
    stale = bool(expect_snapshot and expect_snapshot != actual_snapshot)
    phase = str(plan.get("phase") or package.get("phase") or "")
    refresh_command = _resume_command(root, explicit_skill_roots)
    assert_snapshot_command = _resume_command(
        root,
        explicit_skill_roots,
        expect_snapshot=actual_snapshot,
        command_id="assert-workflow-snapshot",
    )

    if stale:
        return {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "target": str(root),
            "workflow": "workflow-resume",
            "phase": phase,
            "status": "stale",
            "decision_policy": DECISION_POLICY,
            "can_continue": False,
            "stop_before_action": True,
            "stop_reasons": ["workflow_snapshot_changed"],
            "expected_snapshot": expect_snapshot,
            "stale": True,
            "snapshot": snapshot,
            "action_count": 0,
            "selected_action": {},
            "workflow_plan": plan,
            "work_package": package,
            "refresh_command": refresh_command,
            "assert_snapshot_command": assert_snapshot_command,
            "invariants": list(INVARIANTS),
            "errors": ["Workflow evidence changed after the expected snapshot was issued."],
        }

    route = _route(plan, package)
    selected_action = route["selected_action"]
    return {
        "ok": route["ok"],
        "schema_version": SCHEMA_VERSION,
        "target": str(root),
        "workflow": "workflow-resume",
        "phase": phase,
        "status": route["status"],
        "decision_policy": DECISION_POLICY,
        "can_continue": route["can_continue"],
        "stop_before_action": route["stop_before_action"],
        "stop_reasons": route["stop_reasons"],
        "expected_snapshot": expect_snapshot,
        "stale": False,
        "snapshot": snapshot,
        "action_count": 1 if selected_action else 0,
        "selected_action": selected_action,
        "workflow_plan": plan,
        "work_package": package,
        "refresh_command": refresh_command,
        "assert_snapshot_command": assert_snapshot_command,
        "invariants": list(INVARIANTS),
        "errors": route["errors"],
    }


def _route(plan: dict[str, object], package: dict[str, object]) -> dict[str, object]:
    errors = _strings(plan.get("errors")) + _strings(package.get("errors"))
    if plan.get("ok") is not True or package.get("ok") is not True:
        return _route_result(
            ok=False,
            status="failed",
            stop_reasons=["workflow_plan_or_work_package_failed"],
            errors=errors or ["Workflow plan or work package could not be built."],
        )

    package_available = package.get("package_available") is True
    package_status = str(package.get("status", ""))
    selected_action = _dict(package.get("next_action"))
    if package_available:
        if package.get("stop_before_work") is True or package.get("can_start") is not True:
            return _route_result(
                status="blocked",
                stop_reasons=_strings(package.get("stop_reasons")) or ["work_package_not_startable"],
                selected_action=selected_action,
            )
        if _approval_required(selected_action):
            return _route_result(
                status="approval_required",
                stop_reasons=["selected_action_requires_approval"],
                selected_action=selected_action,
            )
        return _route_result(
            status="work_ready",
            can_continue=True,
            stop_before_action=False,
            selected_action=selected_action,
        )

    if package_status == "complete":
        return _route_result(
            status="complete",
            stop_reasons=[],
        )

    selected_action = _guarded_continuation(package) or selected_action
    if selected_action:
        if selected_action.get("valid") is False:
            return _route_result(
                status="blocked",
                stop_reasons=["continuation_preflight_apply_pair_invalid"],
                selected_action=selected_action,
            )
        if _approval_required(selected_action):
            return _route_result(
                status="approval_required",
                stop_reasons=["selected_action_requires_approval"],
                selected_action=selected_action,
            )
        return _route_result(
            status="action_ready",
            can_continue=True,
            stop_before_action=False,
            selected_action=selected_action,
        )

    return _route_result(
        status="blocked",
        stop_reasons=_strings(package.get("stop_reasons")) or ["no_resumable_action"],
    )


def _route_result(
    *,
    ok: bool = True,
    status: str,
    can_continue: bool = False,
    stop_before_action: bool = True,
    stop_reasons: list[str] | None = None,
    selected_action: dict[str, object] | None = None,
    errors: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ok": ok,
        "status": status,
        "can_continue": can_continue,
        "stop_before_action": stop_before_action,
        "stop_reasons": list(dict.fromkeys(stop_reasons or [])),
        "selected_action": dict(selected_action or {}),
        "errors": list(dict.fromkeys(errors or [])),
    }


def _guarded_continuation(package: dict[str, object]) -> dict[str, object]:
    actions = _dicts(package.get("next_actions"))
    preflight = next((action for action in actions if action.get("kind") == "preflight"), {})
    if not preflight:
        return {}
    preflight_id = str(preflight.get("id", ""))
    apply_id = str(preflight.get("preflight_for", ""))
    apply_action = next(
        (
            action
            for action in actions
            if action.get("kind") == "apply"
            and action.get("id") == apply_id
            and action.get("requires_action") == preflight_id
        ),
        {},
    )
    if not preflight_id or not apply_id or not apply_action:
        return {
            "id": apply_id or preflight_id or "invalid-continuation",
            "kind": "guarded-sequence",
            "valid": False,
            "steps": [preflight],
            "writes_state": False,
            "approval_required": True,
            "execution_policy": "stop_when_preflight_apply_pair_is_invalid",
        }
    steps = [preflight, apply_action]
    return {
        "id": apply_id,
        "kind": "guarded-sequence",
        "valid": True,
        "phase": str(apply_action.get("phase", preflight.get("phase", ""))),
        "cwd": str(preflight.get("cwd", apply_action.get("cwd", ""))),
        "steps": steps,
        "writes_state": any(step.get("writes_state") is True for step in steps),
        "approval_required": any(step.get("approval_required") is True for step in steps),
        "execution_policy": "run_preflight_then_apply_only_when_preflight_succeeds",
        "success_condition": str(apply_action.get("success_condition", "ok:true")),
        "description": str(apply_action.get("description", "Run the guarded continuation.")),
    }


def _build_snapshot(
    root: Path,
    plan: dict[str, object],
    package: dict[str, object],
) -> dict[str, object]:
    input_paths = _snapshot_input_paths(root, package)
    inputs = [_path_evidence(root, rel) for rel in input_paths]
    material = {
        "schema_version": SCHEMA_VERSION,
        "workflow_plan": plan,
        "work_package": package,
        "inputs": inputs,
    }
    state_record = next((item for item in inputs if item.get("path") == STATE_REL.as_posix()), {})
    return {
        "algorithm": SNAPSHOT_ALGORITHM,
        "id": _canonical_sha256(material),
        "state_sha256": str(state_record.get("sha256", "")),
        "workflow_plan_sha256": _canonical_sha256(plan),
        "work_package_sha256": _canonical_sha256(package),
        "input_paths": input_paths,
        "inputs": inputs,
    }


def _snapshot_input_paths(root: Path, package_payload: dict[str, object]) -> list[str]:
    values = list(BASELINE_INPUT_PATHS)
    governance_root = root / ".governance"
    if governance_root.is_dir() and not governance_root.is_symlink():
        values.extend(
            path.relative_to(root).as_posix()
            for path in governance_root.rglob("*")
            if (path.is_symlink() or path.is_file()) and path.suffix != ".lock"
        )

    work_package = _dict(package_payload.get("work_package"))
    values.extend(_strings(work_package.get("read_order")))
    write_scope = _dict(work_package.get("write_scope"))
    values.extend(_strings(write_scope.get("primary_paths")))
    values.extend(_strings(write_scope.get("supporting_paths")))
    return sorted(set(_safe_relative_paths(values)))


def _safe_relative_paths(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        path = Path(value)
        if not value or path.is_absolute() or ".." in path.parts:
            continue
        normalized = path.as_posix()
        if normalized not in {"", "."}:
            result.append(normalized)
    return result


def _path_evidence(root: Path, rel: str) -> dict[str, object]:
    path = root / rel
    try:
        stat = path.lstat()
    except FileNotFoundError:
        return {"path": rel, "status": "missing", "sha256": ""}
    except OSError as error:
        return {"path": rel, "status": "unreadable", "sha256": "", "error": str(error)}

    if path.is_symlink():
        try:
            target = os.readlink(path)
        except OSError as error:
            return {"path": rel, "status": "unreadable-symlink", "sha256": "", "error": str(error)}
        return {
            "path": rel,
            "status": "symlink",
            "target": target,
            "sha256": hashlib.sha256(target.encode("utf-8", errors="surrogateescape")).hexdigest(),
        }
    if not path.is_file():
        return {"path": rel, "status": "not-file", "sha256": "", "size": stat.st_size}
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        return {"path": rel, "status": "unreadable", "sha256": "", "error": str(error)}
    return {
        "path": rel,
        "status": "file",
        "sha256": digest.hexdigest(),
        "size": stat.st_size,
    }


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_snapshot_id(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _resume_command(
    root: Path,
    skill_roots: list[Path],
    *,
    expect_snapshot: str = "",
    command_id: str = "refresh-workflow-resume",
) -> dict[str, object]:
    argv = ["bin/governance", "workflow", "resume", "."]
    for skill_root in skill_roots:
        argv.extend(["--skill-root", str(skill_root)])
    if expect_snapshot:
        argv.extend(["--expect-snapshot", expect_snapshot])
    argv.append("--json")
    return {
        "id": command_id,
        "cwd": str(root),
        "command": " ".join(argv),
        "argv": argv,
        "writes_state": False,
        "approval_required": False,
    }


def _failed_payload(
    root: Path,
    skill_roots: list[Path],
    error: str,
    expect_snapshot: str,
) -> dict[str, object]:
    refresh_command = _resume_command(root, skill_roots)
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "target": str(root),
        "workflow": "workflow-resume",
        "phase": "",
        "status": "failed",
        "decision_policy": DECISION_POLICY,
        "can_continue": False,
        "stop_before_action": True,
        "stop_reasons": ["workflow_resume_build_failed"],
        "expected_snapshot": expect_snapshot,
        "stale": False,
        "snapshot": {},
        "action_count": 0,
        "selected_action": {},
        "workflow_plan": {},
        "work_package": {},
        "refresh_command": refresh_command,
        "assert_snapshot_command": {},
        "invariants": list(INVARIANTS),
        "errors": [error],
    }


def _approval_required(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("approval_required") is True:
        return True
    return any(_approval_required(item) for item in value.values() if isinstance(item, dict))


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str) and item] if isinstance(value, list) else []
