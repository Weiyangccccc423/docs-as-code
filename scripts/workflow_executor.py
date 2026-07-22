"""Execute one snapshot-bound workflow action and refresh its routing evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable

try:
    from .bounded_process import run_bounded_command
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command


SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_TIMEOUT_SECONDS = 900.0
DEFAULT_MAX_OUTPUT_BYTES = 262_144
MAX_OUTPUT_BYTES = 1_048_576
SNAPSHOT_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_EXECUTABLES = {"bash", "cmd", "fish", "powershell", "pwsh", "sh", "zsh"}

Runner = Callable[..., dict[str, object]]


def execute_workflow_action(
    target: Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    runner: Runner | None = None,
) -> dict[str, object]:
    """Execute the selected target-local action, or return a guarded stop result."""

    target = target.expanduser().resolve()
    result = _base_payload(target)
    if not target.is_dir():
        return _failure(result, "blocked", "target_directory_missing", "Target directory does not exist.")
    if not _valid_limits(timeout_seconds, max_output_bytes):
        return _failure(
            result,
            "blocked",
            "execution_limits_invalid",
            "Workflow action execution limits are outside the supported bounds.",
        )

    command_runner = runner or run_bounded_command
    initial_command = _resume_command(target)
    initial_spec, errors = _validate_command(initial_command, target, "resume_command")
    if initial_spec is None:
        return _failure(result, "blocked", "resume_command_invalid", errors[0])
    initial_evidence = _run_command(
        initial_spec,
        target=target,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        runner=command_runner,
        label="resume",
    )
    result["initial_resume"] = initial_evidence
    initial_payload = _dict(initial_evidence.get("payload"))
    if not initial_evidence.get("passed") or initial_payload.get("ok") is not True:
        status = str(initial_payload.get("status") or "resume_failed")
        if status not in {"blocked", "approval_required", "stale", "complete"}:
            status = "resume_failed"
        return _failure(
            result,
            status,
            "workflow_resume_failed",
            _first_error(initial_payload, "Target workflow resume did not return a usable action."),
            recovery="Run dac next --json to inspect the current routing evidence.",
        )

    snapshot = _dict(initial_payload.get("snapshot"))
    snapshot_id = snapshot.get("id")
    result["snapshot_id"] = snapshot_id if isinstance(snapshot_id, str) else ""
    result["phase"] = str(initial_payload.get("phase") or "")
    action = _dict(initial_payload.get("selected_action"))
    result["selected_action"] = action

    if not isinstance(snapshot_id, str) or SNAPSHOT_RE.fullmatch(snapshot_id) is None:
        return _failure(result, "blocked", "snapshot_invalid", "Workflow resume did not return a valid snapshot id.")
    if initial_payload.get("stale") is True:
        return _failure(result, "stale", "workflow_snapshot_changed", "The selected workflow snapshot is stale.")
    if (
        initial_payload.get("status") == "complete"
        and initial_payload.get("action_count") == 0
        and not action
    ):
        result["ok"] = True
        result["status"] = "complete"
        result["recovery"] = "No executable workflow action is currently selected."
        return result
    if initial_payload.get("stop_before_action") is True or initial_payload.get("can_continue") is not True:
        status = str(initial_payload.get("status") or "blocked")
        if status not in {"blocked", "approval_required", "stale"}:
            status = "blocked"
        reason = "selected_action_requires_approval" if _approval_required(action) else "workflow_stop_before_action"
        return _failure(
            result,
            status,
            reason,
            _first_error(initial_payload, "Workflow routing requires a stop before action execution."),
            recovery="Resolve the reported decision or approval, then run dac next --json again.",
        )
    if not action or initial_payload.get("action_count") == 0:
        return _failure(
            result,
            "blocked",
            "selected_action_not_executable",
            _first_error(initial_payload, "Workflow routing did not select an executable action."),
            recovery="Run dac next --json and resolve the reported routing blockers before retrying.",
        )
    if action.get("valid") is False:
        return _failure(
            result,
            "blocked",
            "selected_action_invalid",
            "The selected workflow action is invalid and cannot be executed.",
        )
    if _approval_required(action):
        return _failure(
            result,
            "approval_required",
            "selected_action_requires_approval",
            "The selected workflow action requires explicit approval.",
            recovery="Review the action contract and approve it through its phase-specific command.",
        )

    steps, step_errors = _action_steps(action)
    if not steps:
        return _failure(
            result,
            "blocked",
            "selected_action_not_executable",
            step_errors[0] if step_errors else "The selected action has no executable argv steps.",
            recovery="Follow the selected action's manual decision or authoring instructions, then run dac next again.",
        )

    assert_command = _dict(initial_payload.get("assert_snapshot_command"))
    refresh_command = _dict(initial_payload.get("refresh_command"))
    assert_spec, assert_errors = _validate_command(assert_command, target, "assert_snapshot_command")
    refresh_spec, refresh_errors = _validate_command(refresh_command, target, "refresh_command")
    if assert_spec is None:
        return _failure(result, "blocked", "assert_snapshot_command_invalid", assert_errors[0])
    if refresh_spec is None:
        return _failure(result, "blocked", "refresh_command_invalid", refresh_errors[0])
    if assert_spec.get("writes_state") is True or assert_spec.get("approval_required") is True:
        return _failure(
            result,
            "blocked",
            "assert_snapshot_command_unsafe",
            "The snapshot assertion command must be a non-approval, read-only routing command.",
        )
    if not _contains_snapshot(assert_spec["argv"], snapshot_id):
        return _failure(
            result,
            "blocked",
            "assert_snapshot_command_mismatch",
            "The snapshot assertion command is not bound to the selected snapshot.",
        )
    if refresh_spec.get("writes_state") is True or refresh_spec.get("approval_required") is True:
        return _failure(
            result,
            "blocked",
            "refresh_command_unsafe",
            "The refresh command must be a non-approval, read-only routing command.",
        )

    normalized_steps: list[dict[str, object]] = []
    for index, step in enumerate(steps):
        normalized, validation_errors = _validate_command(step, target, f"step[{index}]")
        if normalized is None:
            return _failure(result, "blocked", _command_stop_reason(validation_errors[0]), validation_errors[0])
        normalized_steps.append(normalized)
    order_error = _validate_step_order(action, normalized_steps)
    if order_error:
        return _failure(result, "blocked", "action_steps_out_of_order", order_error)

    assertion = _run_command(
        assert_spec,
        target=target,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        runner=command_runner,
        label="assert_snapshot",
    )
    result["snapshot_assertion"] = assertion
    asserted_payload = _dict(assertion.get("payload"))
    if (
        not assertion.get("passed")
        or asserted_payload.get("ok") is not True
        or asserted_payload.get("stale") is True
        or _dict(asserted_payload.get("snapshot")).get("id") != snapshot_id
    ):
        return _failure(
            result,
            "stale",
            "workflow_snapshot_changed",
            "The repository changed after routing; no selected step was executed.",
            recovery="Discard this action and run dac next --json to obtain a fresh snapshot.",
        )

    for index, step in enumerate(normalized_steps):
        evidence = _run_command(
            step,
            target=target,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            runner=command_runner,
            label=f"step[{index}]",
        )
        result["step_results"].append(evidence)
        if step.get("writes_state") is True:
            result["writes_state"] = True
        if not evidence.get("passed"):
            return _failure(
                result,
                "step_failed",
                "selected_action_step_failed",
                _first_error(_dict(evidence.get("payload")), f"Workflow step {index} failed."),
                recovery="Inspect step_results, repair the reported issue, then run dac next --json before retrying.",
            )

    refresh = _run_command(
        refresh_spec,
        target=target,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        runner=command_runner,
        label="refresh",
    )
    result["refresh"] = refresh
    if not refresh.get("passed") or _dict(refresh.get("payload")).get("ok") is not True:
        return _failure(
            result,
            "refresh_failed",
            "workflow_refresh_failed",
            _first_error(_dict(refresh.get("payload")), "The selected action completed but workflow refresh failed."),
            recovery="Do not repeat the action from memory; run dac next --json and inspect the refresh failure first.",
        )

    result["ok"] = True
    result["status"] = "completed"
    result["writes_state"] = result["writes_state"] is True or action.get("writes_state") is True
    result["next"] = _dict(refresh.get("payload"))
    result["recovery"] = "Run dac next to inspect the refreshed workflow state."
    return result


def _base_payload(target: Path) -> dict[str, object]:
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "target": str(target),
        "workflow": "workflow-execute",
        "phase": "",
        "status": "starting",
        "writes_state": False,
        "snapshot_id": "",
        "selected_action": {},
        "initial_resume": {},
        "snapshot_assertion": {},
        "step_results": [],
        "refresh": {},
        "next": {},
        "stop_reasons": [],
        "errors": [],
        "recovery": "",
    }


def _failure(
    result: dict[str, object],
    status: str,
    reason: str,
    error: str,
    *,
    recovery: str = "",
) -> dict[str, object]:
    result["ok"] = False
    result["status"] = status
    result["stop_reasons"] = [reason]
    result["errors"] = [error]
    if recovery:
        result["recovery"] = recovery
    return result


def _resume_command(target: Path) -> dict[str, object]:
    return {
        "id": "workflow-resume",
        "cwd": str(target),
        "argv": ["bin/governance", "workflow", "resume", ".", "--json"],
        "writes_state": False,
        "approval_required": False,
        "allowed_returncodes": [0, 1],
        "success_condition": "ok:true",
    }


def _action_steps(action: dict[str, object]) -> tuple[list[dict[str, object]], list[str]]:
    raw_steps = action.get("steps")
    if isinstance(raw_steps, list) and raw_steps and all(isinstance(item, dict) for item in raw_steps):
        return [dict(item) for item in raw_steps], []
    if isinstance(action.get("argv"), list):
        return [action], []
    nested_command = action.get("command")
    if isinstance(nested_command, dict):
        command = dict(nested_command)
        for key in ("cwd", "writes_state", "approval_required", "success_condition"):
            if key not in command and key in action:
                command[key] = action[key]
        command.setdefault("id", str(action.get("id") or "selected-action"))
        return [command], []
    return [], ["The selected action exposes no argv, steps, or executable command object."]


def _validate_step_order(action: dict[str, object], steps: list[dict[str, object]]) -> str:
    if action.get("kind") != "guarded-sequence" and all("sequence" not in step for step in steps):
        return ""
    sequences: list[int] = []
    for step in steps:
        sequence = step.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            return "Every selected action step must declare an integer sequence."
        sequences.append(sequence)
    if sequences != list(range(1, len(sequences) + 1)):
        return "Selected action steps must be ordered with contiguous sequence values."
    if action.get("kind") == "guarded-sequence":
        if action.get("valid") is not True:
            return "Guarded sequence validity was not confirmed by workflow resume."
        if steps[0].get("kind") != "preflight":
            return "A guarded sequence must execute a preflight step first."
        if any(step.get("kind") != "apply" for step in steps[1:]):
            return "A guarded sequence may contain only apply steps after its preflight."
    return ""


def _command_stop_reason(error: str) -> str:
    if ".cwd must be an existing directory inside the target" in error:
        return "action_command_cwd_outside_target"
    if ".argv executable must remain inside the target" in error:
        return "action_command_executable_outside_target"
    if ".argv cannot invoke a shell interpreter" in error:
        return "action_command_shell_forbidden"
    return "action_command_invalid"


def _validate_command(
    command: dict[str, object], target: Path, label: str
) -> tuple[dict[str, object] | None, list[str]]:
    if not command:
        return None, [f"{label} is missing."]
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        return None, [f"{label}.argv must be a non-empty string array."]
    if any("\x00" in item for item in argv):
        return None, [f"{label}.argv contains a NUL byte."]
    cwd_value = command.get("cwd", ".")
    if not isinstance(cwd_value, str) or not cwd_value:
        return None, [f"{label}.cwd must be a non-empty path."]
    cwd = _inside_target(target, cwd_value)
    if cwd is None or not cwd.is_dir():
        return None, [f"{label}.cwd must be an existing directory inside the target repository."]
    executable = Path(argv[0])
    executable_name = executable.name.lower()
    if executable_name in FORBIDDEN_EXECUTABLES:
        return None, [f"{label}.argv cannot invoke a shell interpreter."]
    executable_path = executable.resolve() if executable.is_absolute() else (cwd / executable).resolve()
    try:
        executable_path.relative_to(target)
    except ValueError:
        return None, [f"{label}.argv executable must remain inside the target repository."]
    if not executable_path.is_file():
        return None, [f"{label}.argv executable does not exist: {argv[0]}"]
    if not os.access(executable_path, os.X_OK):
        return None, [f"{label}.argv executable is not executable: {argv[0]}"]
    normalized = dict(command)
    normalized["argv"] = list(argv)
    normalized["cwd"] = str(cwd)
    accepted, error = _accepted_returncodes(command, label)
    if error:
        return None, [error]
    normalized["allowed_returncodes"] = accepted
    condition = command.get("success_condition", "ok:true")
    if not isinstance(condition, str) or condition not in {"ok:true", "returncode:0"}:
        return None, [f"{label}.success_condition is unsupported: {condition!r}"]
    normalized["success_condition"] = condition
    return normalized, []


def _accepted_returncodes(command: dict[str, object], label: str) -> tuple[list[int], str | None]:
    raw = command.get("allowed_returncodes")
    if raw is None:
        raw = [command.get("expected_returncode", 0)]
    if not isinstance(raw, list) or not raw or any(isinstance(item, bool) or not isinstance(item, int) for item in raw):
        return [], f"{label}.allowed_returncodes must be a non-empty integer array."
    if any(item < 0 or item > 255 for item in raw):
        return [], f"{label}.allowed_returncodes contains an invalid process status."
    return list(dict.fromkeys(raw)), None


def _run_command(
    command: dict[str, object],
    *,
    target: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    runner: Runner,
    label: str,
) -> dict[str, object]:
    execution = runner(
        list(command["argv"]),
        cwd=Path(str(command["cwd"])),
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        env=_execution_environment(),
    )
    payload = _json_object(execution.get("stdout"))
    returncode = execution.get("returncode")
    accepted = command.get("allowed_returncodes", [0])
    returncode_ok = isinstance(returncode, int) and returncode in accepted
    condition = str(command.get("success_condition", "ok:true"))
    condition_ok = payload.get("ok") is True if condition == "ok:true" else returncode == 0
    passed = returncode_ok and condition_ok and execution.get("timed_out") is not True
    errors: list[str] = []
    if not returncode_ok:
        errors.append(f"{label} returned unexpected status {returncode!r}; expected {accepted}.")
    if payload == {}:
        errors.append(f"{label} did not return a JSON object.")
    elif not condition_ok:
        errors.append(f"{label} did not satisfy success condition {condition}.")
    if execution.get("timed_out") is True:
        errors.append(f"{label} exceeded the {timeout_seconds:g}-second timeout.")
    return {
        "id": str(command.get("id") or label),
        "label": label,
        "argv": list(command["argv"]),
        "cwd": str(command["cwd"]),
        "writes_state": command.get("writes_state") is True,
        "approval_required": command.get("approval_required") is True,
        "success_condition": condition,
        "allowed_returncodes": list(accepted),
        "execution": execution,
        "payload": payload,
        "passed": passed,
        "errors": errors,
    }


def _execution_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("DOCS_AS_CODE_PYTHON", sys.executable)
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _inside_target(target: Path, value: str) -> Path | None:
    candidate = target if value in {"", "."} else Path(value)
    if not candidate.is_absolute():
        candidate = target / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(target)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def _contains_snapshot(argv: list[str], snapshot_id: str) -> bool:
    return "--expect-snapshot" in argv and argv[argv.index("--expect-snapshot") + 1 :][:1] == [snapshot_id]


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return dict(decoded) if isinstance(decoded, dict) else {}


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _approval_required(value: object) -> bool:
    if isinstance(value, dict):
        if value.get("approval_required") is True:
            return True
        return any(_approval_required(item) for item in value.values())
    if isinstance(value, list):
        return any(_approval_required(item) for item in value)
    return False


def _first_error(payload: dict[str, object], fallback: str) -> str:
    error = payload.get("error")
    if isinstance(error, str) and error:
        return error
    errors = payload.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, str) and item:
                return item
    return fallback


def _valid_limits(timeout_seconds: float, max_output_bytes: int) -> bool:
    return (
        isinstance(timeout_seconds, (int, float))
        and not isinstance(timeout_seconds, bool)
        and 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS
        and isinstance(max_output_bytes, int)
        and not isinstance(max_output_bytes, bool)
        and 0 < max_output_bytes <= MAX_OUTPUT_BYTES
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute one snapshot-bound target-local workflow action.")
    parser.add_argument("--target", type=Path, required=True, help="Target project directory.")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-output-bytes", type=int, default=DEFAULT_MAX_OUTPUT_BYTES)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = execute_workflow_action(
        args.target,
        timeout_seconds=args.timeout_seconds,
        max_output_bytes=args.max_output_bytes,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Workflow action: {payload.get('status', 'unknown')}")
        for error in payload.get("errors", []):
            print(f"- {error}")
        recovery = payload.get("recovery")
        if isinstance(recovery, str) and recovery:
            print(f"Next: {recovery}")
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
