from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .source_process import run_source_command
except ImportError:  # pragma: no cover - direct script execution
    from source_process import run_source_command


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SMOKE_STEP_TIMEOUT_SECONDS = 900.0
INLINE_OUTPUT_BYTES = 8 << 10
PLANNED_STEPS = (
    ("build-wheel", "Build the installable wheel from the current source tree."),
    ("create-isolated-environment", "Create a disposable Python environment."),
    ("install-wheel", "Install the wheel without using the source checkout."),
    ("verify-entry-points", "Verify dac and docs-as-code entry points and help."),
    ("initialize-fresh-project", "Initialize a fresh folder containing one product document."),
    ("verify-generated-target", "Verify the generated target-local dac entry point."),
)
REQUIRED_EVIDENCE = (
    "version",
    "help",
    "no_args_help",
    "help_command",
    "help_init",
    "alias",
    "init_check",
    "init_check_read_only",
    "init",
    "status",
    "next",
    "verify",
    "target_help",
    "target_help_command",
    "target_status",
)


@dataclass(frozen=True)
class InstallSmokePaths:
    source: Path
    dist: Path
    venv: Path
    project: Path


@dataclass
class InstallSmokeContext:
    uv: Path
    uv_cache_dir: Path
    env: dict[str, str]
    steps: list[dict[str, object]]
    check: bool
    keep: bool
    allow_network: bool
    uv_version: str = ""
    workspace: Path | None = None


class InstallSmokeError(Exception):
    def __init__(
        self,
        message: str,
        *,
        step: dict[str, object] | None = None,
        error_code: str = "install_smoke_step_failed",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.step = step
        self.error_code = error_code


def _agent_env(*, uv_cache_dir: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    env.pop("MAKELEVEL", None)
    env["PYTHONIOENCODING"] = "utf-8"
    if uv_cache_dir is not None:
        env["UV_CACHE_DIR"] = str(uv_cache_dir)
    return env


def _compact_stream(step: dict[str, object], stream: str) -> None:
    value = step.get(stream)
    if not isinstance(value, str):
        return
    raw = value.encode("utf-8")
    if len(raw) <= INLINE_OUTPUT_BYTES:
        return
    step[stream] = ""
    step[f"{stream}_compacted"] = True
    step[f"{stream}_size_bytes"] = len(raw)
    step[f"{stream}_sha256"] = hashlib.sha256(raw).hexdigest()


def _compact_payloads(steps: list[dict[str, object]]) -> None:
    for step in steps:
        payload = step.get("payload")
        if not isinstance(payload, dict):
            continue
        stdout = step.get("stdout")
        if isinstance(stdout, str) and stdout:
            raw_stdout = stdout.encode("utf-8")
            step["stdout"] = ""
            step["stdout_compacted"] = True
            step["stdout_size_bytes"] = len(raw_stdout)
            step["stdout_sha256"] = hashlib.sha256(raw_stdout).hexdigest()
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        step.pop("payload", None)
        step["payload_summary"] = {
            key: payload[key]
            for key in ("ok", "check", "writes_state", "status", "phase", "target")
            if key in payload
        }
        step["payload_size_bytes"] = len(encoded)
        step["payload_sha256"] = hashlib.sha256(encoded).hexdigest()


def _run_step(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    *,
    cwd: Path,
    env: dict[str, str],
    parse_json: bool = False,
    expected_returncode: int = 0,
    timeout_seconds: float = INSTALL_SMOKE_STEP_TIMEOUT_SECONDS,
) -> dict[str, object]:
    command = [str(item) for item in argv]
    execution = run_source_command(
        command,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout_seconds,
    )
    step: dict[str, object] = {
        "id": step_id,
        **execution,
        "expected_returncode": expected_returncode,
    }
    steps.append(step)

    if execution.get("started") is not True:
        raise InstallSmokeError(f"step did not start: {step_id}", step=step)
    if execution.get("timed_out") is True:
        raise InstallSmokeError(f"step timed out: {step_id}", step=step)
    if execution.get("output_safe") is not True:
        raise InstallSmokeError(f"step output is incomplete or redacted: {step_id}", step=step)
    if execution.get("returncode") != expected_returncode:
        raise InstallSmokeError(f"step failed: {step_id}", step=step)

    stdout = execution.get("stdout")
    stdout_text = stdout if isinstance(stdout, str) else ""
    if parse_json:
        try:
            payload = json.loads(stdout_text)
        except json.JSONDecodeError as error:
            step["json_error"] = str(error)
            raise InstallSmokeError(f"step did not return JSON: {step_id}", step=step) from error
        if not isinstance(payload, dict):
            step["json_error"] = "top-level JSON payload must be an object"
            raise InstallSmokeError(f"step returned non-object JSON: {step_id}", step=step)
        step["payload"] = payload
        step["payload_ok"] = payload.get("ok")

    step["ok"] = True
    _compact_stream(step, "stdout")
    _compact_stream(step, "stderr")
    return step


def _payload(step: dict[str, object]) -> dict[str, object]:
    payload = step.get("payload")
    if not isinstance(payload, dict):
        raise InstallSmokeError(
            f"step has no JSON object payload: {step.get('id', 'unknown')}",
            step=step,
        )
    return payload


def _stdout(step: dict[str, object]) -> str:
    value = step.get("stdout")
    return value if isinstance(value, str) else ""


def _require(condition: bool, message: str, *, step: dict[str, object] | None = None) -> None:
    if not condition:
        raise InstallSmokeError(message, step=step)


def _evidence_ok(evidence: dict[str, object]) -> bool:
    return all(
        isinstance(evidence.get(field), str) and bool(evidence[field])
        if field == "version"
        else evidence.get(field) is True
        for field in REQUIRED_EVIDENCE
    )


def _version_matches_source(version: str, *, root: Path = ROOT) -> bool:
    try:
        source_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return False
    return bool(source_version) and version == source_version


def _planned_steps() -> list[dict[str, object]]:
    return [
        {
            "id": step_id,
            "description": description,
            "writes_state": True,
            "scope": "temporary-workspace",
        }
        for step_id, description in PLANNED_STEPS
    ]


def _resolve_uv(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit.expanduser()
    configured = os.environ.get("DOCS_AS_CODE_UV")
    if configured:
        return Path(configured).expanduser()
    discovered = shutil.which("uv")
    return Path(discovered) if discovered else None


def _resolve_uv_cache_dir(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser()
    configured = os.environ.get("UV_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(tempfile.gettempdir()) / "docs-as-code-uv-cache"


def _missing_uv_payload(*, check: bool) -> dict[str, object]:
    return {
        "ok": False,
        "check": check,
        "writes_state": False,
        "error_code": "install_smoke_uv_unavailable",
        "errors": ["uv is required to build and verify the installable CLI in an isolated environment"],
        "repair": {
            "kind": "manual-tool-install",
            "tool": "uv",
            "maintainer_action": "Install uv from the official Astral documentation, then rerun this command.",
            "consumer_alternatives": [
                "Consumers with uv can run: uv tool install git+https://github.com/Weiyangccccc423/docs-as-code.git",
                "Consumers may use Python 3.10+ pip or the exported offline workflow pack instead.",
            ],
        },
        "planned_steps": _planned_steps(),
        "steps": [],
    }


def _context_step(
    context: InstallSmokeContext,
    step_id: str,
    argv: list[str | Path],
    *,
    cwd: Path,
    parse_json: bool = False,
    timeout_seconds: float = INSTALL_SMOKE_STEP_TIMEOUT_SECONDS,
) -> dict[str, object]:
    return _run_step(
        context.steps,
        step_id,
        argv,
        cwd=cwd,
        env=context.env,
        parse_json=parse_json,
        timeout_seconds=timeout_seconds,
    )


def _base_payload(context: InstallSmokeContext) -> dict[str, object]:
    return {
        "ok": True,
        "check": context.check,
        "writes_state": False,
        "offline": not context.allow_network,
        "builder": {
            "executable": str(context.uv),
            "version": context.uv_version,
            "cache_dir": str(context.uv_cache_dir),
        },
        "planned_steps": _planned_steps(),
        "steps": context.steps,
    }


def _prepare_workspace(workspace: Path) -> InstallSmokePaths:
    paths = InstallSmokePaths(
        source=workspace / "source",
        dist=workspace / "dist",
        venv=workspace / "venv",
        project=workspace / "project",
    )
    shutil.copytree(
        ROOT,
        paths.source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            "__pycache__",
            "*.pyc",
            "*.egg-info",
            "build",
            "dist",
        ),
    )
    paths.project.mkdir()
    (paths.project / "product.md").write_text(
        "# Install Smoke Product\n\n"
        "## Goal\n\nVerify installation and initialization from one product document.\n\n"
        "## Acceptance Criteria\n\n- The generated repository exposes local governance commands.\n",
        encoding="utf-8",
    )
    return paths


def _build_wheel(context: InstallSmokeContext, paths: InstallSmokePaths) -> Path:
    offline = [] if context.allow_network else ["--offline"]
    _context_step(
        context,
        "build-wheel",
        [context.uv, "build", "--wheel", *offline, "--out-dir", paths.dist],
        cwd=paths.source,
    )
    wheels = sorted(paths.dist.glob("*.whl"))
    _require(len(wheels) == 1, f"expected exactly one wheel, found {len(wheels)}")
    return wheels[0]


def _install_wheel(
    context: InstallSmokeContext,
    paths: InstallSmokePaths,
    wheel: Path,
) -> tuple[Path, Path]:
    offline = [] if context.allow_network else ["--offline"]
    _context_step(
        context,
        "create-isolated-environment",
        [context.uv, "venv", "--python", sys.executable, *offline, paths.venv],
        cwd=paths.source,
    )
    python = paths.venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _require(python.is_file(), "isolated Python executable was not created")
    _context_step(
        context,
        "install-wheel",
        [context.uv, "pip", "install", "--python", python, *offline, wheel],
        cwd=paths.source,
    )
    script_dir = python.parent
    dac = script_dir / ("dac.exe" if os.name == "nt" else "dac")
    alias = script_dir / ("docs-as-code.exe" if os.name == "nt" else "docs-as-code")
    _require(dac.is_file(), "installed dac entry point is missing")
    _require(alias.is_file(), "installed docs-as-code compatibility entry point is missing")
    return dac, alias


def _verify_entry_points(
    context: InstallSmokeContext,
    project: Path,
    dac: Path,
    alias: Path,
) -> dict[str, object]:
    version_step = _context_step(context, "installed-dac-version", [dac, "--version"], cwd=project)
    help_step = _context_step(context, "installed-dac-help", [dac, "--help"], cwd=project)
    no_args_step = _context_step(context, "installed-dac-no-args-help", [dac], cwd=project)
    help_command_step = _context_step(context, "installed-dac-help-command", [dac, "help"], cwd=project)
    help_init_step = _context_step(context, "installed-dac-help-init", [dac, "help", "init"], cwd=project)
    alias_version = _context_step(context, "installed-alias-version", [alias, "--version"], cwd=project)
    alias_help = _context_step(context, "installed-alias-help", [alias, "--help"], cwd=project)
    version_output = _stdout(version_step).strip()
    version = version_output.removeprefix("dac ").strip()
    _require(
        _version_matches_source(version),
        "installed dac version does not match source VERSION",
        step=version_step,
    )
    help_output = _stdout(help_step)
    no_args_output = _stdout(no_args_step)
    help_command_output = _stdout(help_command_step)
    help_init_output = _stdout(help_init_step)
    alias_help_output = _stdout(alias_help)
    return {
        "version": version,
        "help": "usage: dac" in help_output and "dac help <command>" in help_output,
        "no_args_help": "usage: dac" in no_args_output and "getting started:" in no_args_output,
        "help_command": "usage: dac" in help_command_output and "dac COMMAND --help" in help_command_output,
        "help_init": (
            "usage: dac init" in help_init_output
            and "project root" in help_init_output
            and "dac init /path/to/product.pdf" in help_init_output
        ),
        "alias": (
            _stdout(alias_version).strip() == version_output
            and "usage: dac" in alias_help_output
            and "dac help <command>" in alias_help_output
        ),
    }


def _json_command(
    context: InstallSmokeContext,
    step_id: str,
    argv: list[str | Path],
    *,
    cwd: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    step = _context_step(context, step_id, argv, cwd=cwd, parse_json=True)
    return step, _payload(step)


def _verify_fresh_project(
    context: InstallSmokeContext,
    project: Path,
    dac: Path,
) -> tuple[dict[str, object], dict[str, bool], dict[str, bool]]:
    markers = (project / "README.md", project / "AGENTS.md", project / "docs")
    before_check = {str(path.relative_to(project)): path.exists() for path in markers}
    _init_check_step, init_check = _json_command(
        context,
        "installed-dac-init-check",
        [dac, "init", "--check", "--json"],
        cwd=project,
    )
    after_check = {str(path.relative_to(project)): path.exists() for path in markers}
    init_step, init = _json_command(
        context,
        "installed-dac-init",
        [dac, "init", "--json"],
        cwd=project,
    )
    _status_step, status = _json_command(
        context,
        "installed-dac-status",
        [dac, "status", "--json"],
        cwd=project,
    )
    _next_step, next_payload = _json_command(
        context,
        "installed-dac-next",
        [dac, "next", "--json"],
        cwd=project,
    )
    _verify_step, verify = _json_command(
        context,
        "installed-dac-verify",
        [dac, "verify", "--check", "--json"],
        cwd=project,
    )

    target_dac = project / "bin/dac"
    _require(target_dac.is_file(), "generated target-local bin/dac is missing", step=init_step)
    target_help = _context_step(context, "target-dac-help", [target_dac, "--help"], cwd=project)
    target_help_command = _context_step(
        context,
        "target-dac-help-command",
        [target_dac, "help"],
        cwd=project,
    )
    _target_status_step, target_status = _json_command(
        context,
        "target-dac-status",
        [target_dac, "status", "--json"],
        cwd=project,
    )
    evidence = {
        "init_check": init_check.get("ok") is True,
        "init_check_read_only": (
            init_check.get("check") is True
            and before_check == after_check
            and not any(after_check.values())
        ),
        "init": init.get("ok") is True,
        "status": status.get("ok") is True,
        "next": next_payload.get("ok") is True,
        "verify": verify.get("ok") is True,
        "target_help": "usage: dac" in _stdout(target_help),
        "target_help_command": (
            "usage: dac" in _stdout(target_help_command)
            and "dac help <command>" in _stdout(target_help_command)
        ),
        "target_status": target_status.get("ok") is True,
    }
    return evidence, before_check, after_check


def _run_full_smoke(context: InstallSmokeContext) -> dict[str, object]:
    if context.workspace is None:
        raise InstallSmokeError("temporary workspace was not created")
    paths = _prepare_workspace(context.workspace)
    wheel = _build_wheel(context, paths)
    dac, alias = _install_wheel(context, paths, wheel)
    entry_evidence = _verify_entry_points(context, paths.project, dac, alias)
    project_evidence, before_check, after_check = _verify_fresh_project(context, paths.project, dac)
    evidence = {**entry_evidence, **project_evidence}
    ok = _evidence_ok(evidence)
    _compact_payloads(context.steps)
    result = {
        **_base_payload(context),
        "ok": ok,
        "writes_state": True,
        "write_scope": "temporary-workspace",
        "wheel": {"name": wheel.name, "size_bytes": wheel.stat().st_size},
        "evidence": evidence,
        "generated_markers_before_check": before_check,
        "generated_markers_after_check": after_check,
        "workspace": str(context.workspace) if context.keep else "",
    }
    if not ok:
        result["error_code"] = "install_smoke_evidence_incomplete"
        result["errors"] = ["installed CLI evidence contract is incomplete"]
    return result


def _failure_payload(context: InstallSmokeContext, error: InstallSmokeError) -> dict[str, object]:
    _compact_payloads(context.steps)
    failure = {
        **_base_payload(context),
        "ok": False,
        "writes_state": context.workspace is not None,
        "write_scope": "temporary-workspace" if context.workspace is not None else "none",
        "error_code": error.error_code,
        "errors": [error.message],
        "failed_step": error.step or {},
        "workspace": str(context.workspace) if context.keep and context.workspace else "",
    }
    stderr = error.step.get("stderr") if isinstance(error.step, dict) else ""
    if (
        error.step
        and error.step.get("id") == "build-wheel"
        and isinstance(stderr, str)
        and "network was disabled" in stderr
    ):
        failure["error_code"] = "install_smoke_build_dependencies_unavailable"
        failure["repair"] = {
            "kind": "approved-cache-prime",
            "tool": "uv",
            "cache_dir": str(context.uv_cache_dir),
            "cwd": str(ROOT),
            "argv": [
                sys.executable,
                "scripts/smoke_installable_cli.py",
                "--allow-network",
                "--uv-cache-dir",
                str(context.uv_cache_dir),
                "--json",
            ],
            "writes_state": True,
            "approval_required": True,
        }
    return failure


def run_installable_cli_smoke(
    *,
    check: bool = False,
    keep: bool = False,
    uv_executable: Path | None = None,
    uv_cache_dir: Path | None = None,
    allow_network: bool = False,
) -> dict[str, object]:
    uv = _resolve_uv(uv_executable)
    if uv is None:
        return _missing_uv_payload(check=check)
    resolved_cache = _resolve_uv_cache_dir(uv_cache_dir)
    context = InstallSmokeContext(
        uv=uv,
        uv_cache_dir=resolved_cache,
        env=_agent_env(uv_cache_dir=resolved_cache),
        steps=[],
        check=check,
        keep=keep,
        allow_network=allow_network,
    )
    try:
        version_step = _context_step(
            context,
            "probe-uv",
            [uv, "--version"],
            cwd=ROOT,
            timeout_seconds=30.0,
        )
        context.uv_version = _stdout(version_step).strip()
        _require(bool(context.uv_version), "uv version probe returned empty output", step=version_step)
        if check:
            return _base_payload(context)
        context.workspace = Path(tempfile.mkdtemp(prefix="docs-as-code-install-smoke-")).resolve()
        return _run_full_smoke(context)
    except InstallSmokeError as error:
        return _failure_payload(context, error)
    finally:
        if context.workspace is not None and not keep:
            shutil.rmtree(context.workspace, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and install the dac wheel in isolation, then verify a fresh target project.",
    )
    parser.add_argument("--check", action="store_true", help="Probe uv and print the no-write execution plan.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--output", type=Path, help="Write the JSON result to this file.")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary workspace for inspection.")
    parser.add_argument("--uv", type=Path, help="Use this uv executable instead of auto-discovery.")
    parser.add_argument("--uv-cache-dir", type=Path, help="Use this uv cache directory.")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow uv to access package indexes; the default is offline verification.",
    )
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    print(f"Installable CLI smoke: {'PASS' if payload.get('ok') else 'FAIL'}")
    builder = payload.get("builder")
    if isinstance(builder, dict):
        print(f"Builder: {builder.get('version', 'unknown')} ({builder.get('executable', 'unknown')})")
    if payload.get("check") is True and payload.get("ok") is True:
        print("Plan: build and verify the wheel in a disposable workspace")
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        print(f"CLI version: {evidence.get('version', 'unknown')}")
    for error in payload.get("errors", []):
        print(f"ERROR: {error}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_installable_cli_smoke(
        check=args.check,
        keep=args.keep,
        uv_executable=args.uv,
        uv_cache_dir=args.uv_cache_dir,
        allow_network=args.allow_network,
    )
    rendered = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.json:
        print(rendered, end="")
    else:
        _print_human(payload)
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
