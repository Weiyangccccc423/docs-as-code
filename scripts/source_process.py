from __future__ import annotations

from pathlib import Path

try:
    from .bounded_process import run_bounded_command
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command


SOURCE_PROCESS_MAX_OUTPUT_BYTES = 16 * 1024 * 1024


def run_source_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    max_output_bytes: int = SOURCE_PROCESS_MAX_OUTPUT_BYTES,
) -> dict[str, object]:
    execution = run_bounded_command(
        argv,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        env=env,
    )
    output_safe = not any(
        execution.get(field) is True
        for field in ("stdout_truncated", "stderr_truncated", "output_redacted")
    )
    return {
        **execution,
        "timeout_seconds": timeout_seconds,
        "output_safe": output_safe,
    }
