from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - target runtime uses POSIX wrappers
    fcntl = None  # type: ignore[assignment]

try:
    from .bounded_process import run_bounded_command
    from .implementation_plan import (
        apply_implementation_closeout,
        apply_implementation_start,
        build_implementation_closeout,
        build_implementation_start,
    )
    from .implementation_verify import (
        DEFAULT_MAX_OUTPUT_BYTES,
        DEFAULT_TIMEOUT_SECONDS,
        build_implementation_verify,
        run_implementation_verify,
    )
    from .project_environment import (
        check_project_environment_tool_repair,
        repair_project_environment_tool,
    )
    from .workflow_resume import build_workflow_resume
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command
    from implementation_plan import (
        apply_implementation_closeout,
        apply_implementation_start,
        build_implementation_closeout,
        build_implementation_start,
    )
    from implementation_verify import (
        DEFAULT_MAX_OUTPUT_BYTES,
        DEFAULT_TIMEOUT_SECONDS,
        build_implementation_verify,
        run_implementation_verify,
    )
    from project_environment import (
        check_project_environment_tool_repair,
        repair_project_environment_tool,
    )
    from workflow_resume import build_workflow_resume


SCHEMA_VERSION = 1
DECISION_POLICY = "claim_then_edit_then_verify_all_bound_commands_then_closeout"
IMPLEMENTATION_RUN_LOCK_REL = Path(".governance/implementation-run.lock")
IMPLEMENTATION_RUN_LOCK_WAIT_SECONDS = 0.5


class ImplementationRunLockUnavailable(OSError):
    pass


def run_implementation_task(
    root: Path,
    *,
    task_id: str = "",
    check: bool = False,
    apply_start: bool = False,
    execute: bool = False,
    closeout: bool = False,
    auto_repair: bool = False,
    approve_repairs: bool = False,
    expect_snapshot: str = "",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, object]:
    root = root.resolve()
    task_id = task_id.strip()
    request_errors = _request_errors(
        apply_start=apply_start,
        execute=execute,
        closeout=closeout,
        auto_repair=auto_repair,
        approve_repairs=approve_repairs,
    )
    if request_errors:
        return _invalid_request_payload(root, task_id, check, request_errors)

    requested_writes = not check and (apply_start or execute or closeout or auto_repair)
    initial_resume = build_workflow_resume(root, expect_snapshot=expect_snapshot)
    initial_error = _resume_error_payload(root, task_id, check, requested_writes, initial_resume)
    if initial_error is not None:
        return initial_error

    if not requested_writes:
        return _run_from_resume(
            root,
            initial_resume,
            task_id=task_id,
            check=True,
            apply_start=False,
            execute=False,
            closeout=False,
            auto_repair=False,
            approve_repairs=False,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )

    snapshot_id = str(_mapping(initial_resume.get("snapshot")).get("id", ""))
    try:
        with _implementation_run_lock(root):
            locked_resume = build_workflow_resume(root, expect_snapshot=snapshot_id)
            locked_error = _resume_error_payload(
                root,
                task_id,
                check,
                requested_writes,
                locked_resume,
            )
            if locked_error is not None:
                return locked_error
            return _run_from_resume(
                root,
                locked_resume,
                task_id=task_id,
                check=False,
                apply_start=apply_start,
                execute=execute,
                closeout=closeout,
                auto_repair=auto_repair,
                approve_repairs=approve_repairs,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
    except ImplementationRunLockUnavailable as error:
        return _failed_payload(
            root,
            task_id,
            check,
            "lock_unavailable",
            [f"implementation run lock is unavailable: {error}"],
        )
    except OSError as error:
        return _failed_payload(
            root,
            task_id,
            check,
            "operation_failed",
            [f"implementation run operation failed: {error}"],
        )


def _run_from_resume(
    root: Path,
    resume: dict[str, object],
    *,
    task_id: str,
    check: bool,
    apply_start: bool,
    execute: bool,
    closeout: bool,
    auto_repair: bool,
    approve_repairs: bool,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:
    context, context_errors = _implementation_context(resume, task_id)
    if context_errors:
        return _blocked_context_payload(root, task_id, check, resume, context_errors)
    if context.get("complete") is True:
        return _base_payload(
            root,
            task_id,
            check,
            resume,
            status="complete",
            ok=True,
            run_ready=False,
        )

    package_payload = _mapping(context.get("package_payload"))
    package = _mapping(context.get("package"))
    selected_task_id = str(package.get("work_id", ""))
    status = str(package.get("status", ""))
    snapshot_id = str(_mapping(resume.get("snapshot")).get("id", ""))
    base = _base_payload(
        root,
        selected_task_id,
        check,
        resume,
        status=status or "blocked",
        ok=True,
        run_ready=package_payload.get("can_start") is True,
    )
    base["work_package"] = package
    base["skill_readiness"] = _mapping(package_payload.get("skill_readiness"))
    base["verification_command_names"] = _strings(package.get("verification_command_names"))
    base["writes_requested"] = not check and (apply_start or execute or closeout or auto_repair)

    if package_payload.get("can_start") is not True or package_payload.get("stop_before_work") is True:
        base.update(
            {
                "status": "blocked",
                "run_ready": False,
                "stop_reasons": _strings(package_payload.get("stop_reasons"))
                or ["implementation_work_package_not_startable"],
                "next_action": _mapping(package_payload.get("next_action")),
            }
        )
        return base

    if status == "ready":
        start_preview = build_implementation_start(root, selected_task_id)
        base["start_preview"] = start_preview
        if execute or closeout:
            base.update(
                {
                    "ok": False,
                    "status": "task_not_in_progress",
                    "run_ready": False,
                    "stop_reasons": ["claim_task_then_edit_implementation_before_verification"],
                    "errors": ["implementation run requires an In Progress task before verification or closeout"],
                    "next_action": _run_command(
                        root,
                        selected_task_id,
                        action="--apply-start",
                        expect_snapshot=snapshot_id,
                    ),
                }
            )
            return base
        if not apply_start:
            base.update(
                {
                    "status": "ready_to_start",
                    "run_ready": start_preview.get("start_ready") is True,
                    "next_action": _run_command(
                        root,
                        selected_task_id,
                        action="--apply-start",
                        expect_snapshot=snapshot_id,
                    ),
                }
            )
            return base
        start_apply = apply_implementation_start(root, selected_task_id)
        base["start_apply"] = start_apply
        base["start_applied"] = start_apply.get("applied") is True or start_apply.get("already_current") is True
        if start_apply.get("ok") is not True or base["start_applied"] is not True:
            base.update(
                {
                    "ok": False,
                    "status": "start_failed",
                    "run_ready": False,
                    "errors": _strings(start_apply.get("errors")) or ["implementation start did not apply"],
                }
            )
            return base
        refreshed = build_workflow_resume(root)
        base.update(
            {
                "status": "implementation_required",
                "snapshot_after": _mapping(refreshed.get("snapshot")),
                "next_action": {
                    "kind": "edit_selected_task",
                    "task_id": selected_task_id,
                    "read_order": _strings(package.get("read_order")),
                    "write_scope": _mapping(package.get("write_scope")),
                    "success_condition": "finish scoped code and test edits before requesting implementation run --execute",
                },
            }
        )
        return base

    if status != "in_progress":
        base.update(
            {
                "status": "blocked",
                "run_ready": False,
                "stop_reasons": [f"implementation_task_status_not_runnable:{status or 'missing'}"],
            }
        )
        return base

    commands = _dicts(package.get("verification_commands"))
    preflights = _verification_preflights(
        root,
        selected_task_id,
        commands,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    repair_runs: list[dict[str, object]] = []
    if execute and auto_repair and not _all_preflights_ready(preflights):
        repair_runs = _attempt_environment_repairs(
            root,
            preflights,
            approve_repairs=approve_repairs,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
        if any(run.get("applied") is True for run in repair_runs):
            preflights = _verification_preflights(
                root,
                selected_task_id,
                commands,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
            snapshot_id = str(
                _mapping(build_workflow_resume(root).get("snapshot")).get("id", "")
            )
    base["verification_preflights"] = preflights
    base["environment_repairs"] = repair_runs
    base["verification_summary"] = _verification_summary(preflights, [])

    if not _all_preflights_ready(preflights):
        base.update(
            {
                "ok": not execute and not closeout,
                "status": "repair_required",
                "run_ready": False,
                "stop_reasons": _preflight_stop_reasons(preflights),
                "repair_actions": _preflight_repair_actions(preflights),
                "next_action": _preflight_next_action(preflights),
            }
        )
        return base

    if not execute and not closeout:
        base.update(
            {
                "status": "verification_ready",
                "run_ready": True,
                "next_action": _run_command(
                    root,
                    selected_task_id,
                    action="--execute",
                    expect_snapshot=snapshot_id,
                ),
            }
        )
        return base

    runs: list[dict[str, object]] = []
    if execute:
        freshness = build_workflow_resume(root, expect_snapshot=snapshot_id)
        if freshness.get("ok") is not True:
            stale_payload = _resume_error_payload(root, selected_task_id, check, True, freshness)
            if stale_payload is not None:
                stale_payload["verification_preflights"] = preflights
                return stale_payload
        runs = _execute_verifications(
            root,
            selected_task_id,
            commands,
            preflights,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
        base["verification_runs"] = runs
        base["executed"] = bool(runs)
        base["verification_summary"] = _verification_summary(preflights, runs)
        if not runs or any(run.get("ok") is not True for run in runs):
            base.update(
                {
                    "ok": False,
                    "status": "verification_failed",
                    "run_ready": False,
                    "stop_reasons": ["required_verification_command_failed"],
                    "next_action": _run_command(root, selected_task_id, action="--execute"),
                }
            )
            return base

    closeout_preview = build_implementation_closeout(root, selected_task_id)
    base["closeout_preview"] = closeout_preview
    if closeout_preview.get("closeout_ready") is not True:
        base.update(
            {
                "ok": not closeout,
                "status": "closeout_blocked",
                "run_ready": False,
                "stop_reasons": [
                    str(item.get("code"))
                    for item in _dicts(closeout_preview.get("blocking_requirements"))
                ],
                "next_action": _mapping(closeout_preview.get("refresh_command")),
            }
        )
        return base

    if not closeout:
        refreshed = build_workflow_resume(root)
        base.update(
            {
                "status": "closeout_ready",
                "run_ready": True,
                "snapshot_after": _mapping(refreshed.get("snapshot")),
                "next_action": _run_command(
                    root,
                    selected_task_id,
                    action="--closeout",
                    expect_snapshot=str(_mapping(refreshed.get("snapshot")).get("id", "")),
                ),
            }
        )
        return base

    closeout_apply = apply_implementation_closeout(root, selected_task_id)
    base["closeout_apply"] = closeout_apply
    base["closeout_applied"] = closeout_apply.get("applied") is True or closeout_apply.get("already_current") is True
    if closeout_apply.get("ok") is not True or base["closeout_applied"] is not True:
        base.update(
            {
                "ok": False,
                "status": "closeout_failed",
                "run_ready": False,
                "errors": _strings(closeout_apply.get("errors")) or ["implementation closeout did not apply"],
            }
        )
        return base
    final_resume = build_workflow_resume(root)
    base.update(
        {
            "status": "complete",
            "run_ready": False,
            "snapshot_after": _mapping(final_resume.get("snapshot")),
            "next_action": _mapping(final_resume.get("selected_action")),
        }
    )
    return base


def _verification_preflights(
    root: Path,
    task_id: str,
    commands: list[dict[str, object]],
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> list[dict[str, object]]:
    preflights: list[dict[str, object]] = []
    for command in commands:
        name = str(command.get("name", ""))
        if command.get("ready") is not True:
            preflights.append(
                {
                    "ok": False,
                    "verification_ready": False,
                    "task_id": task_id,
                    "command_name": name,
                    "blocking_requirements": [
                        {
                            "code": str(command.get("blocker_code", "task_verification_command_invalid")),
                            "status": "missing",
                            "ok": False,
                            "message": "; ".join(_strings(command.get("errors"))),
                        }
                    ],
                    "environment_readiness": {},
                    "run_id": "",
                }
            )
            continue
        preflights.append(
            build_implementation_verify(
                root,
                task_id,
                name,
                allow_writes=command.get("writes_state") is True,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
                check=True,
            )
        )
    return preflights


def _execute_verifications(
    root: Path,
    task_id: str,
    commands: list[dict[str, object]],
    preflights: list[dict[str, object]],
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    command_by_name = {str(command.get("name", "")): command for command in commands}
    for preflight in preflights:
        name = str(preflight.get("command_name", ""))
        command = command_by_name.get(name, {})
        run = run_implementation_verify(
            root,
            task_id,
            name,
            run_id=str(preflight.get("run_id", "")),
            allow_writes=command.get("writes_state") is True,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
        runs.append(run)
        if run.get("ok") is not True:
            break
    return runs


def _attempt_environment_repairs(
    root: Path,
    preflights: list[dict[str, object]],
    *,
    approve_repairs: bool,
    timeout_seconds: float,
    max_output_bytes: int,
) -> list[dict[str, object]]:
    outcomes: list[dict[str, object]] = []
    seen: set[str] = set()
    for action in _preflight_repair_actions(preflights):
        action_id = str(action.get("id", ""))
        if not action_id or action_id in seen:
            continue
        seen.add(action_id)
        strategy = str(action.get("strategy", "manual"))
        if strategy == "reviewed-command":
            tool_id = str(action.get("tool_id", ""))
            preview = check_project_environment_tool_repair(
                root,
                tool_id,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            ).to_dict()
            outcome = {
                "id": action_id,
                "strategy": strategy,
                "tool_id": tool_id,
                "preview": preview,
                "approval_required": True,
                "applied": False,
            }
            if approve_repairs and preview.get("repair_ready") is True:
                applied = repair_project_environment_tool(
                    root,
                    tool_id,
                    approved=True,
                    timeout_seconds=timeout_seconds,
                    max_output_bytes=max_output_bytes,
                ).to_dict()
                outcome["apply"] = applied
                outcome["applied"] = applied.get("ok") is True and applied.get("environment_ready") is True
            outcomes.append(outcome)
            continue
        if strategy == "governance-env":
            preview_command = _mapping(action.get("repair_preflight_command"))
            preview = _run_embedded_json_command(
                root,
                preview_command,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
            decision = _mapping(_mapping(preview.get("payload")).get("repair_decision"))
            outcome = {
                "id": action_id,
                "strategy": strategy,
                "preview": preview,
                "approval_required": decision.get("requires_approval") is True,
                "applied": False,
            }
            if (
                decision.get("can_auto_apply") is True
                and decision.get("requires_approval") is not True
                and decision.get("manual_repair_required") is not True
            ):
                apply_command = _governance_repair_apply_command(preview_command)
                applied = _run_embedded_json_command(
                    root,
                    apply_command,
                    timeout_seconds=timeout_seconds,
                    max_output_bytes=max_output_bytes,
                )
                outcome["apply"] = applied
                outcome["applied"] = (
                    applied.get("ok") is True
                    and _mapping(applied.get("payload")).get("ok") is True
                )
            outcomes.append(outcome)
            continue
        outcomes.append(
            {
                "id": action_id,
                "strategy": strategy,
                "approval_required": action.get("approval_required") is True,
                "manual_repair_required": True,
                "applied": False,
                "instructions": str(action.get("instructions", "")),
            }
        )
    return outcomes


def _run_embedded_json_command(
    root: Path,
    command: dict[str, object],
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:
    argv = command.get("argv")
    cwd_value = command.get("cwd")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) for item in argv):
        return {"ok": False, "errors": ["embedded repair command argv is invalid"], "payload": {}}
    if not isinstance(cwd_value, str):
        return {"ok": False, "errors": ["embedded repair command cwd is invalid"], "payload": {}}
    cwd = root if cwd_value in {"", ".", str(root)} else Path(cwd_value)
    try:
        cwd = cwd.resolve()
        cwd.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return {"ok": False, "errors": ["embedded repair command cwd escapes repository"], "payload": {}}
    execution = run_bounded_command(
        list(argv),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    payload: dict[str, object] = {}
    try:
        decoded = json.loads(str(execution.get("stdout", "")))
        if isinstance(decoded, dict):
            payload = decoded
    except json.JSONDecodeError:
        pass
    return {
        "ok": execution.get("returncode") in {0, 1} and bool(payload),
        "execution": execution,
        "payload": payload,
        "errors": [] if payload else ["embedded repair command did not return a JSON object"],
    }


def _governance_repair_apply_command(command: dict[str, object]) -> dict[str, object]:
    argv = command.get("argv")
    if not isinstance(argv, list):
        return {}
    expected = ["bin/governance", "env", "--repair"]
    if argv[:3] != expected or "--check" not in argv or "--json" not in argv:
        return {}
    return {
        "id": "apply-command-environment-repair",
        "cwd": command.get("cwd", "."),
        "argv": [str(item) for item in argv if item != "--check"],
        "writes_state": True,
        "approval_required": False,
    }


def _implementation_context(
    resume: dict[str, object], task_id: str
) -> tuple[dict[str, object], list[str]]:
    if resume.get("phase") != "implementation":
        return {}, ["implementation run requires recorded phase implementation"]
    package_payload = _mapping(resume.get("work_package"))
    if package_payload.get("status") == "complete" and package_payload.get("package_available") is False:
        return {"complete": True}, []
    package = _mapping(package_payload.get("work_package"))
    if package.get("kind") != "implementation-task":
        return {}, ["workflow resume did not select an implementation-task work package"]
    selected = str(package.get("work_id", ""))
    if task_id and selected != task_id:
        return {}, [f"requested task {task_id} does not match selected implementation task {selected}"]
    return {"package_payload": package_payload, "package": package, "complete": False}, []


def _resume_error_payload(
    root: Path,
    task_id: str,
    check: bool,
    writes_requested: bool,
    resume: dict[str, object],
) -> dict[str, object] | None:
    if resume.get("ok") is True:
        return None
    status = "stale" if resume.get("stale") is True else "resume_failed"
    payload = _base_payload(
        root,
        task_id,
        check,
        resume,
        status=status,
        ok=False,
        run_ready=False,
    )
    payload["writes_requested"] = writes_requested
    payload["stale"] = resume.get("stale") is True
    payload["stop_reasons"] = _strings(resume.get("stop_reasons"))
    payload["errors"] = _strings(resume.get("errors"))
    return payload


def _blocked_context_payload(
    root: Path,
    task_id: str,
    check: bool,
    resume: dict[str, object],
    errors: list[str],
) -> dict[str, object]:
    payload = _base_payload(
        root,
        task_id,
        check,
        resume,
        status="blocked",
        ok=False,
        run_ready=False,
    )
    payload["stop_reasons"] = ["implementation_context_invalid"]
    payload["errors"] = errors
    return payload


def _base_payload(
    root: Path,
    task_id: str,
    check: bool,
    resume: dict[str, object],
    *,
    status: str,
    ok: bool,
    run_ready: bool,
) -> dict[str, object]:
    return {
        "ok": ok,
        "schema_version": SCHEMA_VERSION,
        "target": str(root),
        "workflow": "implementation-run",
        "decision_policy": DECISION_POLICY,
        "check": check,
        "status": status,
        "task_id": task_id,
        "run_ready": run_ready,
        "writes_requested": False,
        "start_applied": False,
        "executed": False,
        "closeout_applied": False,
        "stale": resume.get("stale") is True,
        "snapshot": _mapping(resume.get("snapshot")),
        "snapshot_after": {},
        "work_package": {},
        "skill_readiness": {},
        "verification_command_names": [],
        "verification_preflights": [],
        "verification_runs": [],
        "verification_summary": _verification_summary([], []),
        "environment_repairs": [],
        "repair_actions": [],
        "start_preview": {},
        "start_apply": {},
        "closeout_preview": {},
        "closeout_apply": {},
        "stop_reasons": [],
        "next_action": {},
        "refresh_command": _run_command(root, task_id),
        "errors": [],
    }


def _invalid_request_payload(
    root: Path, task_id: str, check: bool, errors: list[str]
) -> dict[str, object]:
    payload = _base_payload(
        root,
        task_id,
        check,
        {},
        status="invalid_request",
        ok=False,
        run_ready=False,
    )
    payload["stop_reasons"] = ["invalid_implementation_run_request"]
    payload["errors"] = errors
    return payload


def _failed_payload(
    root: Path,
    task_id: str,
    check: bool,
    status: str,
    errors: list[str],
) -> dict[str, object]:
    payload = _base_payload(
        root,
        task_id,
        check,
        {},
        status=status,
        ok=False,
        run_ready=False,
    )
    payload["stop_reasons"] = [f"implementation_run_{status}"]
    payload["errors"] = errors
    return payload


def _request_errors(
    *,
    apply_start: bool,
    execute: bool,
    closeout: bool,
    auto_repair: bool,
    approve_repairs: bool,
) -> list[str]:
    errors: list[str] = []
    if apply_start and (execute or closeout):
        errors.append(
            "--apply-start cannot be combined with --execute or --closeout; edit implementation between claim and verification"
        )
    if auto_repair and not execute:
        errors.append("--auto-repair requires --execute")
    if approve_repairs and not auto_repair:
        errors.append("--approve-repairs requires --auto-repair")
    return errors


def _verification_summary(
    preflights: list[dict[str, object]], runs: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "required_count": len(preflights),
        "ready_count": sum(1 for item in preflights if item.get("verification_ready") is True),
        "blocked_count": sum(1 for item in preflights if item.get("verification_ready") is not True),
        "executed_count": len(runs),
        "passed_count": sum(1 for item in runs if item.get("command_passed") is True),
        "failed_count": sum(1 for item in runs if item.get("command_passed") is not True),
        "all_ready": bool(preflights) and _all_preflights_ready(preflights),
        "all_passed": bool(runs) and all(item.get("command_passed") is True for item in runs),
    }


def _all_preflights_ready(preflights: list[dict[str, object]]) -> bool:
    return bool(preflights) and all(
        item.get("ok") is True and item.get("verification_ready") is True
        for item in preflights
    )


def _preflight_stop_reasons(preflights: list[dict[str, object]]) -> list[str]:
    reasons: list[str] = []
    for preflight in preflights:
        for requirement in _dicts(preflight.get("blocking_requirements")):
            code = str(requirement.get("code", ""))
            if code:
                reasons.append(code)
    return list(dict.fromkeys(reasons or ["verification_preflight_not_ready"]))


def _preflight_repair_actions(
    preflights: list[dict[str, object]],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    seen: set[str] = set()
    for preflight in preflights:
        readiness = _mapping(preflight.get("environment_readiness"))
        for action in _dicts(readiness.get("repair_actions")):
            action_id = str(action.get("id", ""))
            if action_id and action_id not in seen:
                seen.add(action_id)
                actions.append(action)
    return actions


def _preflight_next_action(preflights: list[dict[str, object]]) -> dict[str, object]:
    for preflight in preflights:
        readiness = _mapping(preflight.get("environment_readiness"))
        command = _mapping(readiness.get("repair_preflight_command"))
        if command:
            return command
        refresh = _mapping(preflight.get("refresh_command"))
        if refresh:
            return refresh
    return {}


def _run_command(
    root: Path,
    task_id: str,
    *,
    action: str = "",
    expect_snapshot: str = "",
) -> dict[str, object]:
    argv = ["bin/governance", "implementation", "run", "."]
    if task_id:
        argv.extend(["--task", task_id])
    if action:
        argv.append(action)
    if expect_snapshot:
        argv.extend(["--expect-snapshot", expect_snapshot])
    argv.append("--json")
    return {
        "id": "refresh-implementation-run" if not action else action.removeprefix("--"),
        "kind": "command",
        "cwd": str(root),
        "argv": argv,
        "writes_state": action in {"--apply-start", "--execute", "--closeout"},
        "approval_required": False,
    }


@contextmanager
def _implementation_run_lock(root: Path) -> Iterator[None]:
    if fcntl is None:
        raise ImplementationRunLockUnavailable("POSIX advisory file locking is unavailable")
    path = root / IMPLEMENTATION_RUN_LOCK_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + IMPLEMENTATION_RUN_LOCK_WAIT_SECONDS
    with path.open("a+b") as lock:
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise ImplementationRunLockUnavailable(
                        f"timed out after {IMPLEMENTATION_RUN_LOCK_WAIT_SECONDS} seconds waiting for {path}"
                    ) from error
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [str(item) for item in value if isinstance(item, str) and item] if isinstance(value, list) else []
