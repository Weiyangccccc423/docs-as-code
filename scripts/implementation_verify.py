from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from secrets import token_hex
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - target runtime uses POSIX wrappers
    fcntl = None  # type: ignore[assignment]

try:
    from .bounded_process import run_bounded_command as _run_bounded_command
    from .check_env import TOOLS
    from .implementation_plan import (
        IMPLEMENTATION_PHASE,
        _is_empty_task_board_value,
        _markdown_line_cells,
        _read_task_rows,
        _render_markdown_table_line,
        _task_row_by_id,
    )
    from .project_environment import (
        PROJECT_ENVIRONMENT_REL,
        inspect_project_environment_tool as _project_environment_tool_readiness,
        load_project_environment_contract,
        project_environment_by_id,
    )
    from .state import load_state
    from .verify_governance import (
        COMMAND_CONTRACT_REL,
        COMMAND_CONTRACT_REQUIRED_COLUMNS,
        TASK_BOARD_REL,
        TASK_BOARD_REQUIRED_COLUMNS,
        TASK_ID_RE,
        VERIFICATION_LOG_REL,
        VERIFICATION_LOG_REQUIRED_COLUMNS,
        _command_contract_cwd_valid,
        _is_separator_row,
        _markdown_sections,
        _markdown_table,
        _normalize_cell,
        _table_cell,
        load_command_contract_entry,
        verify,
    )
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command as _run_bounded_command
    from check_env import TOOLS
    from implementation_plan import (
        IMPLEMENTATION_PHASE,
        _is_empty_task_board_value,
        _markdown_line_cells,
        _read_task_rows,
        _render_markdown_table_line,
        _task_row_by_id,
    )
    from project_environment import (
        PROJECT_ENVIRONMENT_REL,
        inspect_project_environment_tool as _project_environment_tool_readiness,
        load_project_environment_contract,
        project_environment_by_id,
    )
    from state import load_state
    from verify_governance import (
        COMMAND_CONTRACT_REL,
        COMMAND_CONTRACT_REQUIRED_COLUMNS,
        TASK_BOARD_REL,
        TASK_BOARD_REQUIRED_COLUMNS,
        TASK_ID_RE,
        VERIFICATION_LOG_REL,
        VERIFICATION_LOG_REQUIRED_COLUMNS,
        _command_contract_cwd_valid,
        _is_separator_row,
        _markdown_sections,
        _markdown_table,
        _normalize_cell,
        _table_cell,
        load_command_contract_entry,
        verify,
    )


IMPLEMENTATION_EVIDENCE_REL = Path("docs/development/04-implementation-evidence.md")
DEVELOPMENT_README_REL = Path("docs/development/README.md")
EVIDENCE_OUTPUT_PATHS = (
    IMPLEMENTATION_EVIDENCE_REL,
    VERIFICATION_LOG_REL,
    TASK_BOARD_REL,
    DEVELOPMENT_README_REL,
)
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_MAX_OUTPUT_BYTES = 65_536
MAX_CONFIGURED_OUTPUT_BYTES = 1_048_576
RUN_ID_RE = re.compile(r"^VR-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}$")
IMPLEMENTATION_VERIFY_LOCK_REL = Path(".governance/implementation-verify.lock")
IMPLEMENTATION_VERIFY_LOCK_WAIT_SECONDS = 0.5
class ImplementationVerifyLockUnavailable(OSError):
    pass


def build_implementation_verify(
    root: Path,
    task_id: str,
    command_name: str,
    *,
    run_id: str = "",
    allow_writes: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    check: bool = True,
) -> dict[str, object]:
    root = root.resolve()
    task_id = task_id.strip()
    command_name = command_name.strip()
    run_id = run_id.strip() or _new_run_id()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""

    rows, row_errors = _read_task_rows(root)
    task_row = _task_row_by_id(rows, task_id)
    command_contract, contract_errors = _load_command_contract(root, command_name)
    prior_run_ids, evidence_errors = _evidence_run_ids(root)
    governance_report = verify(root)
    command_cwd = _command_cwd(root, command_contract)
    refresh_command = _verification_preflight_command_payload(
        root,
        task_id,
        command_name,
        run_id,
        allow_writes=allow_writes,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    environment_readiness = _command_environment_readiness(
        root,
        command_cwd,
        command_contract,
        refresh_command=refresh_command,
        allow_probes=governance_report.ok and not contract_errors,
    )

    requirements = [
        _requirement(
            "implementation_phase_active",
            bool(state) and phase == IMPLEMENTATION_PHASE,
            f"recorded workflow phase must be {IMPLEMENTATION_PHASE}",
            detail=phase or "missing phase",
        ),
        _requirement(
            "task_id_valid",
            TASK_ID_RE.fullmatch(task_id) is not None,
            "implementation verification requires --task TASK-NNN",
            detail=task_id,
        ),
        _requirement(
            "task_board_row_present",
            task_row is not None,
            f"task must exist in {TASK_BOARD_REL.as_posix()}",
            path=TASK_BOARD_REL.as_posix(),
            detail=task_id,
        ),
        _requirement(
            "task_status_in_progress",
            task_row is not None and _normalize_cell(task_row.get("status", "")) == "in progress",
            "task status must be In Progress before a verification command can run",
            path=TASK_BOARD_REL.as_posix(),
            detail=task_row.get("status", "").strip() if task_row is not None else "",
        ),
        _requirement(
            "governance_verify_passed",
            governance_report.ok,
            "read-only governance verification must pass before command execution",
            detail=", ".join(sorted({finding.code for finding in governance_report.findings})),
        ),
        _requirement(
            "command_contract_row_present",
            bool(command_contract),
            "command must be registered exactly once in the command contract",
            path=COMMAND_CONTRACT_REL.as_posix(),
            detail=command_name,
        ),
        _requirement(
            "command_contract_row_valid",
            not contract_errors and bool(command_contract),
            "registered command contract row must have valid structured fields",
            path=COMMAND_CONTRACT_REL.as_posix(),
            detail="; ".join(contract_errors),
        ),
        _requirement(
            "command_approval_not_allowed",
            bool(command_contract) and command_contract.get("approval_required") is False,
            "implementation verify refuses commands that require approval",
            path=COMMAND_CONTRACT_REL.as_posix(),
            detail=command_name,
        ),
        _requirement(
            "command_writes_state_requires_opt_in",
            bool(command_contract)
            and (command_contract.get("writes_state") is False or allow_writes),
            "state-writing commands require explicit --allow-writes opt-in",
            path=COMMAND_CONTRACT_REL.as_posix(),
            detail=command_name,
        ),
        _requirement(
            "command_cwd_ready",
            command_cwd is not None,
            "command Cwd must resolve to an existing directory inside the repository",
            path=COMMAND_CONTRACT_REL.as_posix(),
            detail=str(command_contract.get("cwd", "")) if command_contract else "",
        ),
        _requirement(
            "command_environment_ready",
            environment_readiness.get("ok") is True,
            "the exact registered command executable must be available before execution",
            path=COMMAND_CONTRACT_REL.as_posix(),
            detail=str(
                environment_readiness.get("blocker_code")
                or environment_readiness.get("resolved_path")
                or environment_readiness.get("required_executable")
                or ""
            ),
        ),
        _requirement(
            "verification_run_id_valid",
            RUN_ID_RE.fullmatch(run_id) is not None,
            "verification run ID must use VR-YYYYMMDDTHHMMSSffffffZ-xxxxxxxx format",
            detail=run_id,
        ),
        _requirement(
            "verification_run_id_unique",
            not evidence_errors and run_id not in prior_run_ids,
            "verification run ID must not already exist in the append-only evidence ledger",
            path=IMPLEMENTATION_EVIDENCE_REL.as_posix(),
            detail="; ".join(evidence_errors) or run_id,
        ),
        _requirement(
            "verification_timeout_valid",
            isinstance(timeout_seconds, (int, float)) and 0 < float(timeout_seconds) <= 86_400,
            "timeout seconds must be greater than zero and no more than 86400",
            detail=str(timeout_seconds),
        ),
        _requirement(
            "verification_output_limit_valid",
            isinstance(max_output_bytes, int) and 0 < max_output_bytes <= MAX_CONFIGURED_OUTPUT_BYTES,
            f"max output bytes must be between 1 and {MAX_CONFIGURED_OUTPUT_BYTES}",
            detail=str(max_output_bytes),
        ),
    ]
    blockers = [item for item in requirements if item["status"] != "satisfied"]
    errors = [*row_errors, *contract_errors, *evidence_errors]
    ready = not errors and not blockers
    execute_command = _execute_command_payload(
        root,
        task_id,
        command_name,
        run_id,
        allow_writes=allow_writes,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    return {
        "ok": ready,
        "target": str(root),
        "phase": phase,
        "decision_policy": "execute_only_registered_structured_command_and_record_actual_result",
        "task_id": task_id,
        "command_name": command_name,
        "run_id": run_id,
        "check": check,
        "verification_ready": ready,
        "writes_state": False,
        "allow_writes": allow_writes,
        "executed": False,
        "evidence_recorded": False,
        "command_passed": False,
        "command_contract": command_contract,
        "command_cwd": str(command_cwd) if command_cwd is not None else "",
        "environment_readiness": environment_readiness,
        "timeout_seconds": timeout_seconds,
        "max_output_bytes": max_output_bytes,
        "requirements": requirements,
        "blocking_requirements": blockers,
        "would_write": [path.as_posix() for path in EVIDENCE_OUTPUT_PATHS],
        "updated_paths": [],
        "execution_result": {},
        "execute_command": execute_command,
        "errors": errors,
    }


def run_implementation_verify(
    root: Path,
    task_id: str,
    command_name: str,
    *,
    run_id: str = "",
    allow_writes: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, object]:
    root = root.resolve()
    payload = build_implementation_verify(
        root,
        task_id,
        command_name,
        run_id=run_id,
        allow_writes=allow_writes,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        check=False,
    )
    if payload["verification_ready"] is not True:
        return payload

    selected_run_id = str(payload.get("run_id", ""))
    try:
        with _implementation_verify_lock(root):
            payload = build_implementation_verify(
                root,
                task_id,
                command_name,
                run_id=selected_run_id,
                allow_writes=allow_writes,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
                check=False,
            )
            if payload["verification_ready"] is not True:
                return payload
            return _run_implementation_verify_locked(
                root,
                payload,
                timeout_seconds=float(timeout_seconds),
                max_output_bytes=max_output_bytes,
            )
    except ImplementationVerifyLockUnavailable as error:
        requirement = _requirement(
            "implementation_verify_lock_unavailable",
            False,
            "another implementation verification execution currently owns the evidence lock",
            path=IMPLEMENTATION_VERIFY_LOCK_REL.as_posix(),
            detail=str(error),
        )
        payload["ok"] = False
        payload["verification_ready"] = False
        payload["requirements"] = [*list(payload.get("requirements", [])), requirement]
        payload["blocking_requirements"] = [*list(payload.get("blocking_requirements", [])), requirement]
        payload["errors"] = [*list(payload.get("errors", [])), str(error)]
        return payload


def _run_implementation_verify_locked(
    root: Path,
    payload: dict[str, object],
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:

    contract = payload["command_contract"]
    argv = contract.get("argv") if isinstance(contract, dict) else None
    command_cwd_text = payload.get("command_cwd")
    if not isinstance(argv, list) or not argv or not isinstance(command_cwd_text, str):
        return _execution_failed(payload, "verified command contract is unavailable")

    execution_result = _run_bounded_command(
        [str(item) for item in argv],
        cwd=Path(command_cwd_text),
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    payload["executed"] = execution_result.get("started") is True
    execution_result.pop("started", None)
    payload["execution_result"] = execution_result
    payload["command_passed"] = execution_result.get("result") == "pass"
    payload["writes_state"] = True

    try:
        outputs = _build_evidence_outputs(root, payload)
        _write_outputs_atomically(root, outputs)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
        return _execution_failed(payload, f"implementation verification evidence write failed: {reason}")

    payload["evidence_recorded"] = True
    payload["updated_paths"] = [path.as_posix() for path in EVIDENCE_OUTPUT_PATHS]
    if payload["command_passed"] is not True:
        return _execution_failed(payload, "verification command did not pass", preserve_evidence=True)
    payload["ok"] = True
    payload["errors"] = []
    return payload


def _load_command_contract(root: Path, command_name: str) -> tuple[dict[str, object], list[str]]:
    return load_command_contract_entry(root, command_name)


def _parse_contract_boolean(value: str) -> bool | None:
    normalized = _normalize_cell(value)
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _command_cwd(root: Path, contract: dict[str, object]) -> Path | None:
    value = contract.get("cwd")
    if not isinstance(value, str) or not value:
        return None
    candidate = root if value == "." else root.joinpath(*PurePosixPath(value).parts)
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved if resolved.is_dir() else None


def _command_environment_readiness(
    root: Path,
    command_cwd: Path | None,
    contract: dict[str, object],
    *,
    refresh_command: dict[str, object],
    allow_probes: bool = True,
) -> dict[str, object]:
    readiness = _command_executable_readiness(
        root,
        command_cwd,
        contract,
        refresh_command=refresh_command,
    )
    readiness.update(
        {
            "environment_contract": {
                "path": PROJECT_ENVIRONMENT_REL.as_posix(),
                "schema_version": None,
                "environment_id": str(contract.get("environment", "")),
                "description": "",
                "allow_repository_executables": False,
            },
            "environment_probe_executed": False,
            "required_tools": [],
            "repair_actions": [],
        }
    )
    payload, errors = load_project_environment_contract(root)
    if errors:
        readiness["ok"] = False
        readiness["blocker_code"] = "project_environment_contract_invalid"
        readiness["environment_contract"]["errors"] = list(errors)
        readiness["repair_decision"] = _environment_repair_decision(
            "repair_project_environment_contract",
            status="environment_contract_invalid",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="repair project-environment.json, run governance verification, then refresh this preflight",
        )
        readiness["repair_preflight_command"] = {}
        return readiness

    environment_id = str(contract.get("environment", "")).strip()
    environment = project_environment_by_id(payload, environment_id)
    readiness["environment_contract"]["schema_version"] = payload.get("schema_version")
    if environment is None:
        readiness["ok"] = False
        readiness["blocker_code"] = "command_environment_id_unknown"
        readiness["repair_decision"] = _environment_repair_decision(
            "register_project_environment",
            status="environment_registration_required",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="register the command Environment ID in project-environment.json, then refresh this preflight",
        )
        readiness["repair_preflight_command"] = {}
        return readiness

    readiness["environment_contract"].update(
        {
            "description": environment.get("description", ""),
            "allow_repository_executables": environment.get("allow_repository_executables") is True,
        }
    )
    tools = environment.get("tools") if isinstance(environment.get("tools"), list) else []
    if not allow_probes:
        readiness["ok"] = False
        readiness["blocker_code"] = "environment_probe_blocked_by_governance"
        readiness["required_tools"] = [
            {
                "id": str(tool.get("id", "")),
                "executable": str(tool.get("executable", "")),
                "probe_executed": False,
                "ready": False,
                "blocker_code": "environment_probe_blocked_by_governance",
            }
            for tool in tools
            if isinstance(tool, dict)
        ]
        readiness["repair_decision"] = _environment_repair_decision(
            "repair_governance_before_environment_probe",
            status="governance_verification_required",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="repair governance verification blockers before executing environment version probes",
        )
        readiness["repair_preflight_command"] = {}
        return readiness
    readiness["version_constraints_enforced"] = True
    required_executable = str(readiness.get("required_executable", ""))
    candidate = Path(required_executable) if required_executable else Path()
    repository_executable = bool(required_executable and "/" in required_executable and not candidate.is_absolute())
    declared_executable = candidate.name if candidate.is_absolute() else required_executable
    resolved_direct = Path(str(readiness.get("resolved_path", ""))) if readiness.get("resolved_path") else None
    tool_requests = [
        (
            tool,
            (
                resolved_direct
                if candidate.is_absolute() and tool.get("executable") == declared_executable
                else None
            ),
        )
        for tool in tools
        if isinstance(tool, dict)
    ]
    if len(tool_requests) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(tool_requests))) as executor:
            required_tools = list(
                executor.map(
                    lambda request: _project_environment_tool_readiness(
                        command_cwd,
                        request[0],
                        resolved_override=request[1],
                    ),
                    tool_requests,
                )
            )
    else:
        required_tools = [
            _project_environment_tool_readiness(
                command_cwd,
                tool,
                resolved_override=resolved_override,
            )
            for tool, resolved_override in tool_requests
        ]
    readiness["required_tools"] = required_tools
    readiness["environment_probe_executed"] = any(
        tool.get("probe_executed") is True for tool in required_tools
    )

    declared_tool = next(
        (tool for tool in required_tools if tool.get("executable") == declared_executable),
        None,
    )
    registration_action: dict[str, object] | None = None
    if repository_executable:
        if environment.get("allow_repository_executables") is not True:
            readiness["ok"] = False
            readiness["blocker_code"] = "repository_executable_not_allowed_by_environment"
            registration_action = _environment_registration_action(
                environment_id,
                required_executable,
                "enable reviewed repository executables for this environment or select another environment",
            )
    elif required_executable and declared_tool is None:
        readiness["ok"] = False
        readiness["blocker_code"] = "command_environment_tool_undeclared"
        registration_action = _environment_registration_action(
            environment_id,
            declared_executable,
            "register the command executable, version requirement, probe, and reviewed repair source",
        )

    failed_tools = [tool for tool in required_tools if tool.get("ready") is not True]
    repair_actions = [_environment_tool_repair_action(root, tool) for tool in failed_tools]
    if registration_action is not None:
        repair_actions.insert(0, registration_action)
    readiness["repair_actions"] = repair_actions
    if declared_tool is not None and declared_tool.get("ready") is not True:
        readiness["blocker_code"] = str(declared_tool.get("blocker_code", "environment_tool_unready"))
    elif failed_tools and not readiness.get("blocker_code"):
        readiness["blocker_code"] = str(
            failed_tools[0].get("blocker_code", "environment_tool_unready")
        )

    readiness["ok"] = readiness.get("ok") is True and registration_action is None and not failed_tools
    if readiness["ok"] is True:
        readiness["repair_decision"] = _environment_repair_decision(
            "continue_execution",
            status="ready",
            stop_before_execution=False,
            requires_approval=False,
            manual_repair_required=False,
            next_step="execute the exact registered command",
        )
        readiness["repair_preflight_command"] = {}
        return readiness

    governance_actions = [
        action for action in repair_actions if action.get("strategy") == "governance-env"
    ]
    manual_actions = [
        action for action in repair_actions if action.get("strategy") in {"manual", "register"}
    ]
    reviewed_command_actions = [
        action for action in repair_actions if action.get("strategy") == "reviewed-command"
    ]
    if manual_actions:
        readiness["repair_decision"] = _environment_repair_decision(
            "complete_manual_environment_repairs",
            status="manual_environment_repair_required",
            stop_before_execution=True,
            requires_approval=True,
            manual_repair_required=True,
            next_step="complete the reviewed manual repair_actions, then refresh this preflight",
        )
        readiness["repair_preflight_command"] = {}
    elif reviewed_command_actions:
        readiness["repair_decision"] = _environment_repair_decision(
            "run_reviewed_project_environment_repair_preflight",
            status="reviewed_repair_preflight_required",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=False,
            next_step="run repair_preflight_command, request approval for its apply action, then refresh this preflight",
        )
        first_tool_id = str(reviewed_command_actions[0].get("tool_id", ""))
        readiness["repair_preflight_command"] = _project_environment_repair_preflight_command(
            root,
            first_tool_id,
        )
    elif governance_actions:
        readiness["repair_decision"] = _environment_repair_decision(
            "run_governance_environment_repair_preflight",
            status="repair_preflight_required",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=False,
            next_step="run repair_preflight_command, inspect its repair_decision, then refresh this preflight",
        )
        readiness["repair_preflight_command"] = _environment_repair_preflight_command(root)
    return readiness


def _command_executable_readiness(
    root: Path,
    command_cwd: Path | None,
    contract: dict[str, object],
    *,
    refresh_command: dict[str, object],
) -> dict[str, object]:
    argv = contract.get("argv")
    environment_label = contract.get("environment")
    required_executable = argv[0] if isinstance(argv, list) and argv and isinstance(argv[0], str) else ""
    environment = environment_label if isinstance(environment_label, str) else ""
    base: dict[str, object] = {
        "ok": False,
        "environment": environment,
        "validation_scope": "argv0_and_declared_environment_tools",
        "version_constraints_enforced": False,
        "package_source_inferred": False,
        "required_executable": required_executable,
        "resolution_strategy": "unavailable",
        "resolved_path": "",
        "available": False,
        "executable": False,
        "known_governance_tool": False,
        "blocker_code": "command_contract_executable_invalid",
        "repair_decision": _environment_repair_decision(
            "register_project_environment_tool",
            status="contract_invalid",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="fix the command contract Argv executable before retrying preflight",
        ),
        "repair_preflight_command": {},
        "refresh_command": dict(refresh_command),
    }
    if not required_executable or "\x00" in required_executable:
        return base
    if command_cwd is None:
        base["blocker_code"] = "command_environment_cwd_unavailable"
        base["repair_decision"] = _environment_repair_decision(
            "repair_command_cwd",
            status="cwd_unavailable",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="restore or correct the repository-local command Cwd before retrying preflight",
        )
        return base

    if "/" not in required_executable:
        base["resolution_strategy"] = "path_lookup"
        known_tool = required_executable in {spec.name for spec in TOOLS}
        base["known_governance_tool"] = known_tool
        try:
            found = shutil.which(required_executable, path=_command_search_path(command_cwd))
        except (OSError, RuntimeError, ValueError):
            found = None
        if found:
            try:
                resolved = Path(found).resolve()
            except (OSError, RuntimeError, ValueError):
                resolved = Path(found)
            available, executable = _executable_path_status(resolved)
            base.update(
                {
                    "ok": available and executable,
                    "resolved_path": str(resolved),
                    "available": available,
                    "executable": executable,
                    "blocker_code": "" if available and executable else "command_executable_not_executable",
                }
            )
            if available and executable:
                base["repair_decision"] = _environment_repair_decision(
                    "continue_execution",
                    status="ready",
                    stop_before_execution=False,
                    requires_approval=False,
                    manual_repair_required=False,
                    next_step="execute the exact registered command",
                )
                return base
        base["blocker_code"] = "command_executable_unavailable"
        if known_tool:
            base["repair_decision"] = _environment_repair_decision(
                "run_governance_environment_repair_preflight",
                status="repair_preflight_required",
                stop_before_execution=True,
                requires_approval=False,
                manual_repair_required=False,
                next_step="run repair_preflight_command, inspect its repair_decision, then refresh this preflight",
            )
            base["repair_preflight_command"] = _environment_repair_preflight_command(root)
        else:
            base["repair_decision"] = _environment_repair_decision(
                "register_project_environment_tool",
                status="tool_registration_required",
                stop_before_execution=True,
                requires_approval=True,
                manual_repair_required=True,
                next_step=(
                    "document the project's approved tool source and install policy; "
                    "do not infer a package name or installation command"
                ),
            )
        return base

    candidate = Path(required_executable)
    if candidate.is_absolute():
        base["resolution_strategy"] = "absolute_path"
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError, ValueError):
            resolved = candidate
        base["resolved_path"] = str(resolved)
        available, executable = _executable_path_status(resolved)
        base["available"] = available
        base["executable"] = executable
        if available and executable:
            base["ok"] = True
            base["blocker_code"] = ""
            base["repair_decision"] = _environment_repair_decision(
                "continue_execution",
                status="ready",
                stop_before_execution=False,
                requires_approval=False,
                manual_repair_required=False,
                next_step="execute the exact registered command",
            )
            return base
        base["blocker_code"] = (
            "command_executable_not_executable" if available else "command_executable_unavailable"
        )
        base["repair_decision"] = _environment_repair_decision(
            "repair_external_executable",
            status="external_executable_unavailable",
            stop_before_execution=True,
            requires_approval=True,
            manual_repair_required=True,
            next_step="repair the explicitly pinned external executable path, then refresh this preflight",
        )
        return base

    base["resolution_strategy"] = "cwd_relative"
    try:
        resolved = (command_cwd / candidate).resolve()
    except (OSError, RuntimeError, ValueError):
        base["blocker_code"] = "command_executable_path_invalid"
        base["repair_decision"] = _environment_repair_decision(
            "repair_repository_executable",
            status="repository_path_invalid",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="repair the invalid repository executable path, then refresh this preflight",
        )
        return base
    try:
        resolved.relative_to(root)
    except ValueError:
        base["blocker_code"] = "command_executable_outside_repository"
        base["repair_decision"] = _environment_repair_decision(
            "repair_repository_executable",
            status="repository_path_invalid",
            stop_before_execution=True,
            requires_approval=False,
            manual_repair_required=True,
            next_step="use an executable path that resolves inside the repository, then refresh this preflight",
        )
        return base

    base["resolved_path"] = str(resolved)
    available, executable = _executable_path_status(resolved)
    base["available"] = available
    base["executable"] = executable
    if available and executable:
        base["ok"] = True
        base["blocker_code"] = ""
        base["repair_decision"] = _environment_repair_decision(
            "continue_execution",
            status="ready",
            stop_before_execution=False,
            requires_approval=False,
            manual_repair_required=False,
            next_step="execute the exact registered command",
        )
        return base
    base["blocker_code"] = "command_executable_not_executable" if available else "command_executable_unavailable"
    base["repair_decision"] = _environment_repair_decision(
        "repair_repository_executable",
        status="repository_executable_unavailable",
        stop_before_execution=True,
        requires_approval=False,
        manual_repair_required=True,
        next_step="restore the repository-local executable and mode, then refresh this preflight",
    )
    return base


def _environment_tool_repair_action(root: Path, tool: dict[str, object]) -> dict[str, object]:
    repair = tool.get("repair")
    repair_payload = repair if isinstance(repair, dict) else {}
    strategy = str(repair_payload.get("strategy", "manual"))
    action: dict[str, object] = {
        "id": f"repair-environment-tool-{tool.get('id', 'unknown')}",
        "strategy": strategy,
        "tool_id": str(tool.get("id", "")),
        "executable": str(tool.get("executable", "")),
        "blocker_code": str(tool.get("blocker_code", "")),
        "source": dict(repair_payload.get("source", {}))
        if isinstance(repair_payload.get("source"), dict)
        else {},
        "writes_state": strategy != "governance-env",
        "approval_required": strategy != "governance-env",
    }
    if strategy == "governance-env":
        action["repair_preflight_command"] = _environment_repair_preflight_command(root)
    elif strategy == "reviewed-command":
        action["command"] = (
            dict(repair_payload.get("command", {}))
            if isinstance(repair_payload.get("command"), dict)
            else {}
        )
        action["instructions"] = str(repair_payload.get("instructions", ""))
        action["repair_preflight_command"] = _project_environment_repair_preflight_command(
            root,
            str(tool.get("id", "")),
        )
    else:
        action["instructions"] = str(repair_payload.get("instructions", ""))
    return action


def _environment_registration_action(
    environment_id: str, executable: str, instructions: str
) -> dict[str, object]:
    return {
        "id": f"register-environment-tool-{environment_id}-{executable or 'unknown'}",
        "strategy": "register",
        "environment_id": environment_id,
        "executable": executable,
        "source": {},
        "instructions": instructions,
        "writes_state": True,
        "approval_required": False,
    }


def _command_search_path(command_cwd: Path) -> str:
    entries: list[str] = []
    for entry in os.get_exec_path():
        path = Path(entry) if entry else Path(".")
        entries.append(str(path if path.is_absolute() else (command_cwd / path).resolve()))
    return os.pathsep.join(entries)


def _executable_path_status(path: Path) -> tuple[bool, bool]:
    try:
        available = path.is_file()
        return available, available and os.access(path, os.X_OK)
    except (OSError, RuntimeError, ValueError):
        return False, False


def _environment_repair_decision(
    decision: str,
    *,
    status: str,
    stop_before_execution: bool,
    requires_approval: bool,
    manual_repair_required: bool,
    next_step: str,
) -> dict[str, object]:
    return {
        "decision": decision,
        "status": status,
        "stop_before_execution": stop_before_execution,
        "can_auto_apply": False,
        "requires_approval": requires_approval,
        "manual_repair_required": manual_repair_required,
        "next_step": next_step,
    }


def _environment_repair_preflight_command(root: Path) -> dict[str, object]:
    return {
        "id": "preflight-command-environment-repair",
        "description": "Preview registered governance environment repairs without writing or installing.",
        "cwd": str(root),
        "argv": [
            "bin/governance",
            "env",
            "--repair",
            "--check",
            "--strict",
            "--target",
            ".",
            "--json",
        ],
        "writes_state": False,
        "approval_required": False,
    }


def _project_environment_repair_preflight_command(
    root: Path,
    tool_id: str,
) -> dict[str, object]:
    return {
        "id": f"preflight-project-environment-repair-{tool_id}",
        "description": "Preview one exact reviewed project runtime repair without writing or installing.",
        "cwd": str(root),
        "argv": [
            "bin/governance",
            "project-env",
            "repair",
            ".",
            "--tool-id",
            tool_id,
            "--check",
            "--json",
        ],
        "writes_state": False,
        "approval_required": False,
    }


def _evidence_run_ids(root: Path) -> tuple[set[str], list[str]]:
    path = root / IMPLEMENTATION_EVIDENCE_REL
    if not path.exists():
        return set(), []
    if not path.is_file() or path.is_symlink():
        return set(), [f"implementation evidence path is not a regular file: {IMPLEMENTATION_EVIDENCE_REL}"]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return set(), [f"implementation evidence must be UTF-8: {IMPLEMENTATION_EVIDENCE_REL}"]
    except OSError as error:
        return set(), [f"implementation evidence cannot be read: {error.strerror or error}"]
    run_ids = re.findall(r"^## (VR-[^\s]+)\s*$", text, flags=re.MULTILINE)
    duplicates = sorted({run_id for run_id in run_ids if run_ids.count(run_id) > 1})
    errors = [f"implementation evidence contains duplicate run ID: {run_id}" for run_id in duplicates]
    return set(run_ids), errors


def _requirement(
    code: str,
    satisfied: bool,
    message: str,
    *,
    path: str = "",
    detail: str = "",
) -> dict[str, object]:
    return {
        "code": code,
        "status": "satisfied" if satisfied else "missing",
        "ok": satisfied,
        "path": path,
        "message": message,
        "detail": detail,
    }


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"VR-{timestamp}-{token_hex(4)}"


def _execute_command_payload(
    root: Path,
    task_id: str,
    command_name: str,
    run_id: str,
    *,
    allow_writes: bool,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:
    argv = [
        "bin/governance",
        "implementation",
        "verify",
        ".",
        "--task",
        task_id,
        "--command",
        command_name,
        "--run-id",
        run_id,
        "--timeout-seconds",
        str(timeout_seconds),
        "--max-output-bytes",
        str(max_output_bytes),
    ]
    if allow_writes:
        argv.append("--allow-writes")
    argv.append("--json")
    return {
        "id": "execute-implementation-verification",
        "description": "Execute the exact registered command and atomically record its actual result.",
        "cwd": str(root),
        "argv": argv,
        "writes_state": True,
        "approval_required": False,
    }


def _verification_preflight_command_payload(
    root: Path,
    task_id: str,
    command_name: str,
    run_id: str,
    *,
    allow_writes: bool,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:
    command = _execute_command_payload(
        root,
        task_id,
        command_name,
        run_id,
        allow_writes=allow_writes,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    argv = list(command["argv"])
    argv.insert(-1, "--check")
    return {
        "id": "refresh-implementation-verification-preflight",
        "description": "Refresh command and environment readiness without execution or evidence writes.",
        "cwd": str(root),
        "argv": argv,
        "writes_state": False,
        "approval_required": False,
    }


@contextmanager
def _implementation_verify_lock(root: Path) -> Any:
    if fcntl is None:
        raise ImplementationVerifyLockUnavailable("POSIX advisory file locking is unavailable")
    path = root / IMPLEMENTATION_VERIFY_LOCK_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + IMPLEMENTATION_VERIFY_LOCK_WAIT_SECONDS
    with path.open("a+b") as lock:
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise ImplementationVerifyLockUnavailable(
                        f"timed out after {IMPLEMENTATION_VERIFY_LOCK_WAIT_SECONDS} seconds waiting for {path}"
                    ) from error
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _utc_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _build_evidence_outputs(root: Path, payload: dict[str, object]) -> dict[str, bytes]:
    execution = payload.get("execution_result")
    contract = payload.get("command_contract")
    if not isinstance(execution, dict) or not isinstance(contract, dict):
        raise ValueError("implementation verification result is incomplete")
    run_id = str(payload.get("run_id", ""))
    task_id = str(payload.get("task_id", ""))
    command_name = str(payload.get("command_name", ""))
    result = str(execution.get("result", "fail"))
    log_result = "pass" if result == "pass" else "fail"
    executed_at = str(execution.get("started_at", ""))
    date = executed_at[:10]
    anchor = run_id.lower()
    evidence_link = f"04-implementation-evidence.md#{anchor}"

    evidence_path = root / IMPLEMENTATION_EVIDENCE_REL
    evidence_text = _read_optional_utf8(evidence_path)
    next_evidence = _append_evidence_run(
        evidence_text,
        run_id=run_id,
        task_id=task_id,
        command_name=command_name,
        contract=contract,
        execution=execution,
    )
    verification_text = (root / VERIFICATION_LOG_REL).read_text(encoding="utf-8")
    next_verification = _upsert_verification_log(
        verification_text,
        task_id=task_id,
        command_name=command_name,
        result=log_result,
        date=date,
        evidence_link=evidence_link,
        run_id=run_id,
    )
    task_board_text = (root / TASK_BOARD_REL).read_text(encoding="utf-8")
    next_task_board = _update_task_evidence_link(
        task_board_text,
        task_id=task_id,
        command_name=command_name,
        evidence_link=evidence_link,
    )
    readme_text = (root / DEVELOPMENT_README_REL).read_text(encoding="utf-8")
    next_readme = _index_evidence_ledger(readme_text)
    return {
        IMPLEMENTATION_EVIDENCE_REL.as_posix(): next_evidence.encode("utf-8"),
        VERIFICATION_LOG_REL.as_posix(): next_verification.encode("utf-8"),
        TASK_BOARD_REL.as_posix(): next_task_board.encode("utf-8"),
        DEVELOPMENT_README_REL.as_posix(): next_readme.encode("utf-8"),
    }


def _read_optional_utf8(path: Path) -> str:
    if not path.exists():
        return ""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"output path is not a regular file: {path}")
    return path.read_text(encoding="utf-8")


def _append_evidence_run(
    text: str,
    *,
    run_id: str,
    task_id: str,
    command_name: str,
    contract: dict[str, object],
    execution: dict[str, object],
) -> str:
    if re.search(rf"^## {re.escape(run_id)}\s*$", text, flags=re.MULTILINE):
        raise ValueError(f"implementation evidence run ID already exists: {run_id}")
    if not text.strip():
        text = (
            "# Implementation Verification Evidence\n\n"
            "> Append-only ledger. Current command status is summarized in `03-verification-log.md`.\n"
        )
    stdout = str(execution.get("stdout", ""))
    stderr = str(execution.get("stderr", ""))
    section = (
        f"\n## {run_id}\n\n"
        f"- Task: `{task_id}`\n"
        f"- Command: `{command_name}`\n"
        f"- Started at: `{execution.get('started_at', '')}`\n"
        f"- Finished at: `{execution.get('finished_at', '')}`\n"
        f"- Cwd: `{contract.get('cwd', '')}`\n"
        f"- Argv: `{json.dumps(contract.get('argv', []), ensure_ascii=True)}`\n"
        f"- Return code: `{execution.get('returncode')}`\n"
        f"- Result: `{execution.get('result', '')}`\n"
        f"- Timed out: `{str(execution.get('timed_out') is True).lower()}`\n"
        f"- Duration seconds: `{execution.get('duration_seconds', 0)}`\n"
        f"- Stdout truncated: `{str(execution.get('stdout_truncated') is True).lower()}`\n"
        f"- Stderr truncated: `{str(execution.get('stderr_truncated') is True).lower()}`\n\n"
        f"- Output redacted: `{str(execution.get('output_redacted') is True).lower()}`\n"
        f"- Stdout redactions: `{execution.get('stdout_redaction_count', 0)}`\n"
        f"- Stderr redactions: `{execution.get('stderr_redaction_count', 0)}`\n\n"
        "### Standard Output\n\n"
        f"{_markdown_output_block(stdout)}\n\n"
        "### Standard Error\n\n"
        f"{_markdown_output_block(stderr)}\n"
    )
    return text.rstrip() + "\n" + section


def _markdown_output_block(value: str) -> str:
    if not value:
        return "```text\n(empty)\n```"
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{value.rstrip()}\n{fence}"


def _upsert_verification_log(
    text: str,
    *,
    task_id: str,
    command_name: str,
    result: str,
    date: str,
    evidence_link: str,
    run_id: str,
) -> str:
    lines = text.splitlines(keepends=True)
    header_index, header = _find_table_header(lines, tuple(VERIFICATION_LOG_REQUIRED_COLUMNS))
    task_index = header.index("task")
    command_index = header.index("command")
    row = (
        f"| {task_id} | {command_name} | {result} | {date} | "
        f"[{command_name} evidence]({evidence_link}) `{run_id}` |\n"
    )
    insert_index = header_index + 1
    for index in range(header_index + 1, len(lines)):
        cells = _markdown_line_cells(lines[index])
        if cells is None:
            break
        insert_index = index + 1
        if _is_separator_row(cells):
            continue
        if task_index >= len(cells) or command_index >= len(cells):
            raise ValueError("verification log row is missing required columns")
        if (
            _normalize_cell(cells[task_index]) == _normalize_cell(task_id)
            and _normalize_cell(cells[command_index]) == _normalize_cell(command_name)
        ):
            lines[index] = row
            return "".join(lines)
    lines.insert(insert_index, row)
    return "".join(lines)


def _update_task_evidence_link(
    text: str,
    *,
    task_id: str,
    command_name: str,
    evidence_link: str,
) -> str:
    lines = text.splitlines(keepends=True)
    header_index, header = _find_table_header(lines, tuple(TASK_BOARD_REQUIRED_COLUMNS))
    task_index = header.index("id")
    verification_index = header.index("verification")
    label = f"{command_name} evidence"
    link = f"[{label}]({evidence_link})"
    link_pattern = re.compile(rf"\[{re.escape(label)}\]\([^)]*\)")
    for index in range(header_index + 1, len(lines)):
        cells = _markdown_line_cells(lines[index])
        if cells is None:
            break
        if _is_separator_row(cells):
            continue
        if task_index >= len(cells) or verification_index >= len(cells):
            raise ValueError("task board row is missing required columns")
        if cells[task_index].strip() != task_id:
            continue
        current = cells[verification_index].strip()
        if link_pattern.search(current):
            cells[verification_index] = link_pattern.sub(link, current, count=1)
        elif _is_empty_task_board_value(current):
            cells[verification_index] = link
        else:
            cells[verification_index] = f"{current}; {link}"
        lines[index] = _render_markdown_table_line(cells, lines[index])
        return "".join(lines)
    raise ValueError(f"task board row not found for {task_id}")


def _find_table_header(lines: list[str], required_columns: tuple[str, ...]) -> tuple[int, list[str]]:
    for index, line in enumerate(lines):
        cells = _markdown_line_cells(line)
        if cells is None:
            continue
        header = [_normalize_cell(cell) for cell in cells]
        if all(column in header for column in required_columns):
            return index, header
    raise ValueError(f"Markdown table is missing required columns: {', '.join(required_columns)}")


def _index_evidence_ledger(text: str) -> str:
    if IMPLEMENTATION_EVIDENCE_REL.name in text:
        return text
    return (
        text.rstrip()
        + "\n\n## Implementation Evidence\n\n"
        + "- `04-implementation-evidence.md` - append-only output ledger written by `implementation verify`.\n"
    )


def _write_outputs_atomically(root: Path, outputs: dict[str, bytes]) -> None:
    snapshots: dict[Path, tuple[bool, bytes, int | None]] = {}
    temporary: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for rel, content in outputs.items():
            path = _safe_output_path(root, Path(rel))
            if path.is_file():
                snapshots[path] = (True, path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            else:
                snapshots[path] = (False, b"", None)
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            temp = Path(temp_name)
            temporary[path] = temp
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            mode = snapshots[path][2]
            if mode is not None:
                temp.chmod(mode)
        for rel in outputs:
            path = root / rel
            temporary[path].replace(path)
            replaced.append(path)
        report = verify(root)
        if not report.ok:
            findings = ", ".join(sorted({finding.code for finding in report.findings}))
            raise OSError(f"post-write governance verification failed: {findings}")
    except OSError as error:
        rollback_errors = _rollback_outputs(snapshots, replaced)
        detail = f"; rollback failed: {', '.join(rollback_errors)}" if rollback_errors else ""
        raise OSError(f"{error.strerror or error}{detail}") from error
    finally:
        for temp in temporary.values():
            if temp.exists() and temp.is_file():
                try:
                    temp.unlink()
                except OSError:
                    pass


def _safe_output_path(root: Path, rel: Path) -> Path:
    path = root / rel
    current = root
    for part in rel.parts[:-1]:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise OSError(f"implementation evidence output parent is unsafe: {current}")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise OSError(f"implementation evidence output path is unsafe: {rel.as_posix()}")
    return path


def _rollback_outputs(
    snapshots: dict[Path, tuple[bool, bytes, int | None]],
    replaced: list[Path],
) -> list[str]:
    errors: list[str] = []
    for path in reversed(replaced):
        existed, content, mode = snapshots[path]
        try:
            if existed:
                descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".rollback", dir=path.parent)
                restore = Path(temp_name)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                if mode is not None:
                    restore.chmod(mode)
                restore.replace(path)
            elif path.exists() and path.is_file():
                path.unlink()
        except OSError as error:
            errors.append(error.strerror or str(error))
    return errors


def _execution_failed(
    payload: dict[str, object],
    message: str,
    *,
    preserve_evidence: bool = False,
) -> dict[str, object]:
    payload["ok"] = False
    if not preserve_evidence:
        payload["evidence_recorded"] = False
        payload["updated_paths"] = []
    payload["errors"] = [*list(payload.get("errors", [])), message]
    return payload
