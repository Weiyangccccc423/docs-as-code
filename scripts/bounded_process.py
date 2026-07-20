from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def run_bounded_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    max_output_bytes: int,
    env: dict[str, str] | None = None,
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
            env=env,
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
            "output_redacted": False,
            "stdout_redaction_count": 0,
            "stderr_redaction_count": 0,
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


def _utc_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
