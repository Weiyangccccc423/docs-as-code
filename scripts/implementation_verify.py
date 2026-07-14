from __future__ import annotations

import json
import os
import re
import signal
import stat
import subprocess
import tempfile
import threading
import time
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
    from .implementation_plan import (
        IMPLEMENTATION_PHASE,
        _is_empty_task_board_value,
        _markdown_line_cells,
        _read_task_rows,
        _render_markdown_table_line,
        _task_row_by_id,
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
        verify,
    )
except ImportError:  # pragma: no cover - direct script execution
    from implementation_plan import (
        IMPLEMENTATION_PHASE,
        _is_empty_task_board_value,
        _markdown_line_cells,
        _read_task_rows,
        _render_markdown_table_line,
        _task_row_by_id,
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
SENSITIVE_OUTPUT_PATTERNS = (
    re.compile(
        r"(?i)\b(?P<prefix>authorization\s*:\s*(?:bearer|basic)\s+)(?P<secret>[^\s]+)"
    ),
    re.compile(
        r"(?i)\b(?P<prefix>(?:api[_-]?(?:key|token)|access[_-]?token|refresh[_-]?token|"
        r"password|passwd|secret|private[_-]?key)\s*[=:]\s*)(?P<secret>[^\s,;]+)"
    ),
)
SENSITIVE_TOKEN_PATTERN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{16,})\b")


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
    path = root / COMMAND_CONTRACT_REL
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, [f"command contract is missing: {COMMAND_CONTRACT_REL.as_posix()}"]
    except UnicodeDecodeError:
        return {}, [f"command contract must be UTF-8: {COMMAND_CONTRACT_REL.as_posix()}"]
    except OSError as error:
        return {}, [f"command contract cannot be read: {error.strerror or error}"]

    sections = _markdown_sections(text, min_level=2)
    table = _markdown_table(sections.get("command table", ""))
    if not table:
        return {}, ["command contract Command Table is missing"]
    header = [_normalize_cell(cell) for cell in table[0]]
    missing = [column for column in COMMAND_CONTRACT_REQUIRED_COLUMNS if column not in header]
    if missing:
        return {}, [f"command contract is missing columns: {', '.join(missing)}"]
    matching: list[dict[str, str]] = []
    for data in table[1:]:
        if _is_separator_row(data):
            continue
        row = {
            column: _table_cell(data, header.index(column))
            for column in COMMAND_CONTRACT_REQUIRED_COLUMNS
        }
        if row["name"].strip() == command_name:
            matching.append(row)
    if not matching:
        return {}, [f"command contract command not found: {command_name}"]
    if len(matching) != 1:
        return {}, [f"command contract command must be unique: {command_name}"]

    row = matching[0]
    errors: list[str] = []
    try:
        argv = json.loads(row["argv"].strip().strip("`"))
    except json.JSONDecodeError:
        argv = None
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        errors.append(f"command contract Argv must be a non-empty JSON string array: {command_name}")
        argv = []
    cwd = row["cwd"].strip().strip("`").strip()
    if not _command_contract_cwd_valid(row["cwd"]):
        errors.append(f"command contract Cwd is invalid: {command_name}")
    writes_state = _parse_contract_boolean(row["writes state"])
    approval_required = _parse_contract_boolean(row["approval required"])
    if writes_state is None:
        errors.append(f"command contract Writes State must be true or false: {command_name}")
    if approval_required is None:
        errors.append(f"command contract Approval Required must be true or false: {command_name}")
    return {
        "name": row["name"].strip(),
        "purpose": row["purpose"].strip(),
        "cwd": cwd,
        "argv": argv,
        "writes_state": writes_state,
        "approval_required": approval_required,
        "evidence": row["evidence"].strip(),
        "environment": row["environment"].strip(),
    }, errors


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
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_dir() else None


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


def _run_bounded_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:
    started_at = datetime.now(timezone.utc)
    start = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=os.name == "posix",
        )
    except OSError as error:
        return {
            "started": False,
            "argv": argv,
            "cwd": str(cwd),
            "started_at": _utc_timestamp(started_at),
            "finished_at": _utc_timestamp(datetime.now(timezone.utc)),
            "duration_seconds": round(time.monotonic() - start, 6),
            "returncode": None,
            "result": "unavailable",
            "timed_out": False,
            "stdout": "",
            "stderr": error.strerror or str(error),
            "stdout_truncated": False,
            "stderr_truncated": False,
            "max_output_bytes_per_stream": max_output_bytes,
        }

    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}

    def drain(name: str, stream: Any) -> None:
        try:
            while True:
                chunk = stream.read(65_536)
                if not chunk:
                    return
                remaining = max_output_bytes - len(buffers[name])
                if remaining > 0:
                    buffers[name].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated[name] = True
        except (OSError, ValueError):
            return

    threads = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_group(process)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    finally:
        for thread in threads:
            thread.join(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    finished_at = datetime.now(timezone.utc)
    stdout, stdout_decode_truncated, stdout_redaction_count = _safe_output_text(
        bytes(buffers["stdout"]), max_output_bytes
    )
    stderr, stderr_decode_truncated, stderr_redaction_count = _safe_output_text(
        bytes(buffers["stderr"]), max_output_bytes
    )
    truncated["stdout"] = truncated["stdout"] or stdout_decode_truncated
    truncated["stderr"] = truncated["stderr"] or stderr_decode_truncated
    passed = process.returncode == 0 and not timed_out
    return {
        "started": True,
        "argv": argv,
        "cwd": str(cwd),
        "started_at": _utc_timestamp(started_at),
        "finished_at": _utc_timestamp(finished_at),
        "duration_seconds": round(time.monotonic() - start, 6),
        "returncode": process.returncode,
        "result": "pass" if passed else "fail",
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": truncated["stdout"],
        "stderr_truncated": truncated["stderr"],
        "output_redacted": stdout_redaction_count > 0 or stderr_redaction_count > 0,
        "stdout_redaction_count": stdout_redaction_count,
        "stderr_redaction_count": stderr_redaction_count,
        "max_output_bytes_per_stream": max_output_bytes,
    }


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:  # pragma: no cover - target runtime uses POSIX wrappers
            process.kill()
        return
    except OSError:
        try:
            process.kill()
        except OSError:
            pass


def _safe_output_text(value: bytes, max_output_bytes: int) -> tuple[str, bool, int]:
    text = value.decode("utf-8", errors="replace")
    text, redaction_count = _redact_sensitive_output(text)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_output_bytes:
        return text, False, redaction_count
    bounded = encoded[:max_output_bytes].decode("utf-8", errors="ignore")
    return bounded, True, redaction_count


def _redact_sensitive_output(value: str) -> tuple[str, int]:
    redaction_count = 0
    for pattern in SENSITIVE_OUTPUT_PATTERNS:
        value, count = pattern.subn(lambda match: f"{match.group('prefix')}[REDACTED]", value)
        redaction_count += count
    value, count = SENSITIVE_TOKEN_PATTERN.subn("[REDACTED]", value)
    return value, redaction_count + count


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
