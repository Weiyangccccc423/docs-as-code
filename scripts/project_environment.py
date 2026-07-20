from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from secrets import token_hex
from typing import Iterator
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover - target runtime uses POSIX wrappers
    fcntl = None  # type: ignore[assignment]

try:
    from .bounded_process import run_bounded_command
    from .state import StateFileError, load_state
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command
    from state import StateFileError, load_state


PROJECT_ENVIRONMENT_REL = Path("docs/agent-workflow/project-environment.json")
PROJECT_COMMAND_CONTRACT_REL = Path("docs/agent-workflow/command-contract.md")
PROJECT_ENVIRONMENT_SCHEMA_VERSION = 1
PROJECT_ENVIRONMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PROJECT_ENVIRONMENT_TOOL_ID_RE = PROJECT_ENVIRONMENT_ID_RE
PROJECT_ENVIRONMENT_EXECUTABLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
APPROVED_VERSION_PROBE_ARGS = {
    ("--version",),
    ("-V",),
    ("-version",),
    ("version",),
}
VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){0,3}$")
VERSION_REQUIREMENT_KEYS = {"exact", "minimum", "maximum_exclusive"}
REPAIR_STRATEGIES = {"governance-env", "manual", "reviewed-command"}
SOURCE_TYPES = {"official-url", "repository-doc", "workflow-pack"}
MAX_PROJECT_ENVIRONMENT_BYTES = 1_048_576
MAX_ENVIRONMENTS = 32
MAX_TOOLS_PER_ENVIRONMENT = 16
MAX_VERSION_PREFIX_LENGTH = 120
MAX_VERSION_COMPONENT_DIGITS = 9
MAX_ID_LENGTH = 64
MAX_EXECUTABLE_LENGTH = 128
MAX_DESCRIPTION_LENGTH = 1000
MAX_SOURCE_LOCATION_LENGTH = 2048
MAX_REVIEW_EVIDENCE_LENGTH = 512
MAX_REPAIR_INSTRUCTIONS_LENGTH = 4000
PROJECT_RUNTIME_ID = "project-runtime"
PROJECT_ENVIRONMENT_WORKFLOW = "workflows/04-design-derivation.md"
PROJECT_ENVIRONMENT_DECISION_POLICY = "register_only_reviewed_project_runtime_tools"
PROJECT_ENVIRONMENT_LOCAL_SKILLS = (
    "configuring-project-runtime",
    "capturing-architecture-decisions",
    "verifying-governance-docs",
)
PROJECT_ENVIRONMENT_SPECIALIST_SKILLS = (
    "tech-stack-evaluator",
    "senior-architect",
    "senior-devops",
)
PROJECT_ENVIRONMENT_ALLOWED_PHASES = {"design-derivation", "implementation"}
PROJECT_ENVIRONMENT_TEMP_REL = PROJECT_ENVIRONMENT_REL.with_name(f".{PROJECT_ENVIRONMENT_REL.name}.tmp")
PROJECT_ENVIRONMENT_LOCK_REL = Path(".governance/project-environment.lock")
PROJECT_ENVIRONMENT_LOCK_WAIT_SECONDS = 0.5
PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL = Path(".governance/project-environment-repairs.json")
PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_TEMP_REL = PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.with_name(
    f".{PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.name}.tmp"
)
PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_SCHEMA_VERSION = 1
PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_MAX_BYTES = 4_194_304
MAX_PROJECT_ENVIRONMENT_REPAIR_RECORDS = 1024
MAX_REPAIR_COMMAND_ARGS = 64
MAX_REPAIR_COMMAND_ARG_LENGTH = 2048
DEFAULT_REPAIR_TIMEOUT_SECONDS = 300.0
MAX_REPAIR_TIMEOUT_SECONDS = 3600.0
DEFAULT_REPAIR_MAX_OUTPUT_BYTES = 65_536
MAX_REPAIR_OUTPUT_BYTES = 1_048_576
PROJECT_ENVIRONMENT_PROBE_TIMEOUT_SECONDS = 5.0
PROJECT_ENVIRONMENT_PROBE_MAX_OUTPUT_BYTES = 4096
REPAIR_RECORD_ID_RE = re.compile(r"^PER-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_REPAIR_EXECUTABLES = {
    "bash",
    "cmd",
    "dash",
    "doas",
    "env",
    "fish",
    "ksh",
    "powershell",
    "pwsh",
    "sh",
    "su",
    "sudo",
    "zsh",
}
SENSITIVE_REPAIR_ARGUMENT_KEYS = {
    "api-key",
    "api-token",
    "authorization",
    "password",
    "passwd",
    "private-key",
    "secret",
    "token",
}
SENSITIVE_REPAIR_TOKEN_RE = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{16,})")


class ProjectEnvironmentLockUnavailable(RuntimeError):
    pass


def load_project_environment_contract(root: Path) -> tuple[dict[str, object], list[str]]:
    path = root / PROJECT_ENVIRONMENT_REL
    rel = PROJECT_ENVIRONMENT_REL.as_posix()
    if not path.exists():
        return {}, [f"missing required project environment contract: {rel}"]
    if not path.is_file() or path.is_symlink():
        return {}, [f"project environment contract must be a regular file: {rel}"]
    try:
        if path.stat().st_size > MAX_PROJECT_ENVIRONMENT_BYTES:
            return {}, [
                f"project environment contract must not exceed {MAX_PROJECT_ENVIRONMENT_BYTES} bytes: {rel}"
            ]
    except OSError as error:
        return {}, [f"project environment contract cannot be inspected: {error.strerror or error}"]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {}, [f"project environment contract must be UTF-8: {rel}"]
    except OSError as error:
        return {}, [f"project environment contract cannot be read: {error.strerror or error}"]
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError) as error:
        return {}, [f"project environment contract must be valid JSON: {error}"]
    if not isinstance(payload, dict):
        return {}, ["project environment contract root must be an object"]
    errors = validate_project_environment_contract(payload)
    return payload, errors


@dataclass
class ProjectEnvironmentRegistrationResult:
    target: str
    ok: bool
    tool_id: str
    check: bool
    reviewed: bool
    replace: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    action: str = "blocked"
    tool: dict[str, object] = field(default_factory=dict)
    environment: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
            "decision_policy": PROJECT_ENVIRONMENT_DECISION_POLICY,
            "operation": "register",
            "environment_id": PROJECT_RUNTIME_ID,
            "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
            "tool_id": self.tool_id,
            "check": self.check,
            "reviewed": self.reviewed,
            "replace_requested": self.replace,
            "apply_requested": not self.check,
            "applied": bool(self.updated),
            "writes_state": not self.check,
            "action": self.action,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "updated": list(self.updated),
            "would_update": list(self.would_update),
            "tool": copy.deepcopy(self.tool),
            "environment": copy.deepcopy(self.environment),
            "verify_command": {
                "argv": ["bin/governance", "verify", ".", "--check", "--json"],
                "cwd": ".",
                "writes_state": False,
            },
            "refresh_command": {
                "argv": ["bin/governance", "project-env", "plan", ".", "--json"],
                "cwd": ".",
                "writes_state": False,
            },
        }


@dataclass
class ProjectEnvironmentRepairResult:
    target: str
    ok: bool
    tool_id: str
    check: bool
    approved: bool
    action: str = "blocked"
    environment_ready: bool = False
    repair_ready: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tool: dict[str, object] = field(default_factory=dict)
    readiness_before: dict[str, object] = field(default_factory=dict)
    readiness_after: dict[str, object] = field(default_factory=dict)
    repair_action: dict[str, object] = field(default_factory=dict)
    apply_command: dict[str, object] = field(default_factory=dict)
    execution: dict[str, object] = field(default_factory=dict)
    evidence_id: str = ""
    updated: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
            "decision_policy": "execute_only_reviewed_project_runtime_repairs_after_approval",
            "operation": "repair",
            "environment_id": PROJECT_RUNTIME_ID,
            "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
            "evidence_path": PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.as_posix(),
            "tool_id": self.tool_id,
            "check": self.check,
            "approved": self.approved,
            "apply_requested": not self.check,
            "writes_state": not self.check,
            "action": self.action,
            "environment_ready": self.environment_ready,
            "repair_ready": self.repair_ready,
            "stop_before_workflow": not self.environment_ready,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "tool": copy.deepcopy(self.tool),
            "readiness_before": copy.deepcopy(self.readiness_before),
            "readiness_after": copy.deepcopy(self.readiness_after),
            "repair_action": copy.deepcopy(self.repair_action),
            "apply_command": copy.deepcopy(self.apply_command),
            "execution": copy.deepcopy(self.execution),
            "evidence_id": self.evidence_id,
            "updated": list(self.updated),
            "refresh_command": {
                "argv": ["bin/governance", "project-env", "repair", ".", "--tool-id", self.tool_id, "--check", "--json"],
                "cwd": ".",
                "writes_state": False,
                "approval_required": False,
            },
            "verify_command": {
                "argv": ["bin/governance", "verify", ".", "--check", "--json"],
                "cwd": ".",
                "writes_state": False,
                "approval_required": False,
            },
        }


def build_project_environment_plan(root: Path) -> dict[str, object]:
    root = root.resolve()
    payload, errors = load_project_environment_contract(root)
    if errors:
        return {
            "target": str(root),
            "ok": False,
            "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
            "decision_policy": PROJECT_ENVIRONMENT_DECISION_POLICY,
            "environment_id": PROJECT_RUNTIME_ID,
            "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
            "status": "blocked",
            "tool_count": 0,
            "tools": [],
            "errors": errors,
        }
    repair_evidence, evidence_errors = load_project_environment_repair_evidence(root)
    if evidence_errors:
        return {
            "target": str(root),
            "ok": False,
            "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
            "decision_policy": PROJECT_ENVIRONMENT_DECISION_POLICY,
            "environment_id": PROJECT_RUNTIME_ID,
            "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
            "repair_evidence_path": PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.as_posix(),
            "status": "repair_evidence_invalid",
            "tool_count": 0,
            "tools": [],
            "errors": evidence_errors,
        }

    environment = project_environment_by_id(payload, PROJECT_RUNTIME_ID)
    if environment is None:
        return {
            "target": str(root),
            "ok": False,
            "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
            "decision_policy": PROJECT_ENVIRONMENT_DECISION_POLICY,
            "environment_id": PROJECT_RUNTIME_ID,
            "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
            "status": "blocked",
            "tool_count": 0,
            "tools": [],
            "errors": [f"project environment contract must declare environment ID: {PROJECT_RUNTIME_ID}"],
        }

    tools = environment.get("tools")
    tool_items = [copy.deepcopy(tool) for tool in tools if isinstance(tool, dict)] if isinstance(tools, list) else []
    phase = "unknown"
    try:
        phase = str(load_state(root).get("phase", "unknown"))
    except StateFileError:
        pass
    repair_records = repair_evidence.get("repairs")
    repair_record_items = repair_records if isinstance(repair_records, list) else []
    pending_repair_ids = [
        str(record.get("id", ""))
        for record in repair_record_items
        if isinstance(record, dict) and record.get("status") == "pending"
    ]
    coverage = _project_runtime_command_coverage(
        root,
        environment,
        tool_items,
        pending_repair_ids=pending_repair_ids,
    )
    command_contract_errors = [
        str(error) for error in coverage.get("command_contract_errors", []) if isinstance(error, str)
    ]
    status = (
        "repair_evidence_pending"
        if pending_repair_ids
        else ("registration_required" if not tool_items else "registered_tools_present")
    )
    repair_routes = [
        {
            "tool_id": str(tool.get("id", "")),
            "strategy": str(tool.get("repair", {}).get("strategy", ""))
            if isinstance(tool.get("repair"), dict)
            else "",
            "preflight_command": {
                "argv": [
                    "bin/governance",
                    "project-env",
                    "repair",
                    ".",
                    "--tool-id",
                    str(tool.get("id", "")),
                    "--check",
                    "--json",
                ],
                "cwd": ".",
                "writes_state": False,
                "approval_required": False,
            },
        }
        for tool in tool_items
    ]
    return {
        "target": str(root),
        "ok": not command_contract_errors,
        "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
        "decision_policy": PROJECT_ENVIRONMENT_DECISION_POLICY,
        "environment_id": PROJECT_RUNTIME_ID,
        "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
        "workflow_phase": phase,
        "phase_allows_registration": phase in PROJECT_ENVIRONMENT_ALLOWED_PHASES,
        "status": status,
        "tool_count": len(tool_items),
        "tools": tool_items,
        **coverage,
        "repair_evidence_path": PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.as_posix(),
        "repair_evidence_summary": {
            "record_count": len(repair_record_items),
            "pending_count": len(pending_repair_ids),
            "pending_record_ids": pending_repair_ids,
        },
        "repair_routes": repair_routes,
        "specialist_skills": list(PROJECT_ENVIRONMENT_SPECIALIST_SKILLS),
        "skill_requirements": [
            {
                "type": "local-workflow",
                "name": name,
                "available_in_workflow_pack": True,
                "missing_policy": "stop_before_guessing",
            }
            for name in PROJECT_ENVIRONMENT_LOCAL_SKILLS
        ]
        + [
            {
                "type": "authority-routing",
                "name": name,
                "available_in_workflow_pack": False,
                "missing_policy": "load_from_agent_environment_or_stop_before_guessing",
            }
            for name in PROJECT_ENVIRONMENT_SPECIALIST_SKILLS
        ],
        "read_order": [
            PROJECT_ENVIRONMENT_REL.as_posix(),
            "docs/agent-workflow/command-contract.md",
            "docs/architecture/README.md",
            "docs/decisions/README.md",
        ],
        "active_work": {
            "status": coverage["coverage_status"],
            "next_action": (
                "investigate-pending-project-runtime-repair"
                if pending_repair_ids
                else (
                    "repair-command-contract"
                    if command_contract_errors
                    else (
                        "complete"
                        if coverage["configuration_complete"]
                        else (
                            "review-stack-decision-and-register-tool"
                            if coverage["missing_command_registrations"]
                            else "preflight-registered-project-runtime-tools"
                        )
                    )
                )
            ),
            "stop_condition": (
                "Do not continue while project environment repair evidence contains a pending record."
                if pending_repair_ids
                else "Do not register a project runtime tool without a local reviewed stack decision."
            ),
        },
        "register_command": {
            "argv_prefix": [
                "bin/governance",
                "project-env",
                "register",
                ".",
                "--tool-id",
                "<tool-id>",
                "--executable",
                "<executable>",
            ],
            "cwd": ".",
            "writes_state": True,
            "approval_required": False,
        },
        "errors": command_contract_errors,
    }


def _project_runtime_command_coverage(
    root: Path,
    environment: dict[str, object],
    tools: list[dict[str, object]],
    *,
    pending_repair_ids: list[str],
) -> dict[str, object]:
    try:
        from .verify_governance import load_command_contract_entries
    except ImportError:  # pragma: no cover - direct script execution
        from verify_governance import load_command_contract_entries

    entries, errors = load_command_contract_entries(root)
    required_commands = [
        copy.deepcopy(entry)
        for entry in entries
        if entry.get("environment") == PROJECT_RUNTIME_ID
    ]
    tool_ids = [str(tool.get("id", "")) for tool in tools]
    base: dict[str, object] = {
        "command_contract_path": PROJECT_COMMAND_CONTRACT_REL.as_posix(),
        "command_contract_errors": list(errors),
        "required_command_count": len(required_commands),
        "required_commands": required_commands,
        "command_coverage": [],
        "missing_command_registrations": [],
        "tool_readiness": [],
        "unready_tool_ids": [],
        "unused_tool_ids": tool_ids,
        "configuration_complete": False,
        "coverage_status": "command_contract_invalid" if errors else "registration_required",
    }
    if errors:
        return base
    if pending_repair_ids:
        base["coverage_status"] = "repair_evidence_pending"
        return base
    if not required_commands:
        base["configuration_complete"] = True
        base["coverage_status"] = "not_required"
        return base

    tools_by_executable = {
        str(tool.get("executable", "")): tool
        for tool in tools
        if str(tool.get("executable", ""))
    }
    command_requests: list[tuple[dict[str, object], Path | None, dict[str, object] | None, Path | None]] = []
    probe_requests: dict[tuple[str, str, str], tuple[Path, dict[str, object], Path | None]] = {}
    tool_command_keys: dict[str, list[tuple[str, str, str]]] = {}
    used_tool_ids: set[str] = set()
    missing_registrations: list[dict[str, object]] = []

    for command in required_commands:
        command_cwd = _project_runtime_command_cwd(root, str(command.get("cwd", "")))
        argv = command.get("argv")
        executable = argv[0] if isinstance(argv, list) and argv and isinstance(argv[0], str) else ""
        candidate = Path(executable) if executable else Path()
        repository_executable = bool(executable and "/" in executable and not candidate.is_absolute())
        declared_executable = candidate.name if candidate.is_absolute() else executable
        tool = None if repository_executable else tools_by_executable.get(declared_executable)
        resolved_override = candidate if candidate.is_absolute() else None
        command_requests.append((command, command_cwd, tool, resolved_override))
        if tool is None:
            if not repository_executable:
                missing_registrations.append(
                    {
                        "command_name": str(command.get("name", "")),
                        "executable": declared_executable,
                    }
                )
            continue
        tool_id = str(tool.get("id", ""))
        used_tool_ids.add(tool_id)
        if command_cwd is not None:
            key = (tool_id, str(command_cwd), str(resolved_override or ""))
            probe_requests[key] = (command_cwd, tool, resolved_override)
            tool_command_keys.setdefault(tool_id, []).append(key)

    for tool in tools:
        tool_id = str(tool.get("id", ""))
        if tool_command_keys.get(tool_id):
            continue
        key = (tool_id, str(root), "")
        probe_requests[key] = (root, tool, None)
        tool_command_keys.setdefault(tool_id, []).append(key)

    probe_results: dict[tuple[str, str, str], dict[str, object]] = {}
    requests = list(probe_requests.items())
    if requests:
        with ThreadPoolExecutor(max_workers=min(4, len(requests))) as executor:
            results = executor.map(
                lambda item: inspect_project_environment_tool(
                    item[1][0],
                    item[1][1],
                    resolved_override=item[1][2],
                ),
                requests,
            )
            for (key, _), result in zip(requests, results):
                probe_results[key] = result

    tool_readiness: list[dict[str, object]] = []
    for tool in tools:
        keys = tool_command_keys[str(tool.get("id", ""))]
        readiness_items = [probe_results[key] for key in keys]
        selected = next((item for item in readiness_items if item.get("ready") is not True), readiness_items[0])
        tool_readiness.append(copy.deepcopy(selected))
    command_coverage: list[dict[str, object]] = []
    for command, command_cwd, tool, resolved_override in command_requests:
        argv = command.get("argv")
        executable = argv[0] if isinstance(argv, list) and argv and isinstance(argv[0], str) else ""
        candidate = Path(executable) if executable else Path()
        repository_executable = bool(executable and "/" in executable and not candidate.is_absolute())
        coverage = {
            "command_name": str(command.get("name", "")),
            "cwd": str(command.get("cwd", "")),
            "argv": copy.deepcopy(argv) if isinstance(argv, list) else [],
            "executable": executable,
            "coverage_type": "repository-executable" if repository_executable else "registered-tool",
            "tool_id": str(tool.get("id", "")) if tool is not None else "",
            "ready": False,
            "blocker_code": "",
        }
        if command_cwd is None:
            coverage["blocker_code"] = "command_environment_cwd_unavailable"
        elif repository_executable:
            ready, blocker_code, resolved_path = _repository_command_executable_readiness(
                root,
                command_cwd,
                executable,
                allow_repository_executables=environment.get("allow_repository_executables") is True,
            )
            coverage["ready"] = ready
            coverage["blocker_code"] = blocker_code
            coverage["resolved_path"] = resolved_path
        elif tool is None:
            coverage["blocker_code"] = "command_environment_tool_undeclared"
        else:
            key = (str(tool.get("id", "")), str(command_cwd), str(resolved_override or ""))
            readiness = probe_results[key]
            coverage["ready"] = readiness.get("ready") is True
            coverage["blocker_code"] = str(readiness.get("blocker_code", ""))
            coverage["tool_readiness"] = copy.deepcopy(readiness)
        command_coverage.append(coverage)

    unready_tool_ids = [
        str(item.get("id", ""))
        for item in tool_readiness
        if item.get("ready") is not True
    ]
    unused_tool_ids = [tool_id for tool_id in tool_ids if tool_id not in used_tool_ids]
    missing_registrations = list(
        {
            (str(item["command_name"]), str(item["executable"])): item
            for item in missing_registrations
        }.values()
    )
    configuration_complete = (
        not missing_registrations
        and not unready_tool_ids
        and all(item.get("ready") is True for item in command_coverage)
    )
    coverage_status = (
        "registration_required"
        if missing_registrations
        else "ready"
        if configuration_complete
        else "repair_required"
    )
    base.update(
        {
            "command_coverage": command_coverage,
            "missing_command_registrations": missing_registrations,
            "tool_readiness": tool_readiness,
            "unready_tool_ids": unready_tool_ids,
            "unused_tool_ids": unused_tool_ids,
            "configuration_complete": configuration_complete,
            "coverage_status": coverage_status,
        }
    )
    return base


def _project_runtime_command_cwd(root: Path, value: str) -> Path | None:
    candidate = root if value == "." else root.joinpath(*PurePosixPath(value).parts)
    if candidate.is_symlink() or not candidate.is_dir():
        return None
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved


def _repository_command_executable_readiness(
    root: Path,
    command_cwd: Path,
    executable: str,
    *,
    allow_repository_executables: bool,
) -> tuple[bool, str, str]:
    if not allow_repository_executables:
        return False, "repository_executable_not_allowed_by_environment", ""
    candidate = command_cwd.joinpath(*PurePosixPath(executable).parts)
    if candidate.is_symlink():
        return False, "repository_executable_symlink", str(candidate)
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False, "command_executable_outside_repository", str(candidate)
    available, executable_ready = _project_environment_executable_status(resolved)
    if not available:
        return False, "command_executable_unavailable", str(resolved)
    if not executable_ready:
        return False, "command_executable_not_executable", str(resolved)
    return True, "", str(resolved)


def check_project_environment_tool_registration(
    root: Path,
    tool: dict[str, object],
    *,
    reviewed: bool,
    replace: bool = False,
) -> ProjectEnvironmentRegistrationResult:
    return _project_environment_tool_registration(
        root,
        tool,
        check=True,
        reviewed=reviewed,
        replace=replace,
    )


def register_project_environment_tool(
    root: Path,
    tool: dict[str, object],
    *,
    reviewed: bool,
    replace: bool = False,
) -> ProjectEnvironmentRegistrationResult:
    root = root.resolve()
    try:
        with _project_environment_lock(root):
            return _project_environment_tool_registration(
                root,
                tool,
                check=False,
                reviewed=reviewed,
                replace=replace,
            )
    except (OSError, ProjectEnvironmentLockUnavailable) as error:
        tool_id = str(tool.get("id", "")) if isinstance(tool, dict) else ""
        return ProjectEnvironmentRegistrationResult(
            target=str(root),
            ok=False,
            tool_id=tool_id,
            check=False,
            reviewed=reviewed,
            replace=replace,
            errors=[f"project environment registration lock is unavailable: {error}"],
            tool=tool,
        )


def check_project_environment_tool_repair(
    root: Path,
    tool_id: str,
    *,
    timeout_seconds: float = DEFAULT_REPAIR_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_REPAIR_MAX_OUTPUT_BYTES,
) -> ProjectEnvironmentRepairResult:
    return _project_environment_tool_repair(
        root,
        tool_id,
        check=True,
        approved=False,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def repair_project_environment_tool(
    root: Path,
    tool_id: str,
    *,
    approved: bool,
    timeout_seconds: float = DEFAULT_REPAIR_TIMEOUT_SECONDS,
    max_output_bytes: int = DEFAULT_REPAIR_MAX_OUTPUT_BYTES,
) -> ProjectEnvironmentRepairResult:
    root = root.resolve()
    if not approved:
        return _project_environment_tool_repair(
            root,
            tool_id,
            check=False,
            approved=False,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
    try:
        with _project_environment_lock(root):
            return _project_environment_tool_repair(
                root,
                tool_id,
                check=False,
                approved=True,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )
    except (OSError, ProjectEnvironmentLockUnavailable) as error:
        return ProjectEnvironmentRepairResult(
            target=str(root),
            ok=False,
            tool_id=tool_id,
            check=False,
            approved=True,
            errors=[f"project environment repair lock is unavailable: {error}"],
        )


def _project_environment_tool_repair(
    root: Path,
    tool_id: str,
    *,
    check: bool,
    approved: bool,
    timeout_seconds: float,
    max_output_bytes: int,
) -> ProjectEnvironmentRepairResult:
    root = root.resolve()
    tool_id = tool_id.strip()
    base = {
        "target": str(root),
        "tool_id": tool_id,
        "check": check,
        "approved": approved,
    }
    parameter_errors: list[str] = []
    if not PROJECT_ENVIRONMENT_TOOL_ID_RE.fullmatch(tool_id):
        parameter_errors.append("project environment repair tool ID must be a lowercase slug")
    if not 0 < timeout_seconds <= MAX_REPAIR_TIMEOUT_SECONDS:
        parameter_errors.append(
            f"project environment repair timeout must be greater than 0 and at most {MAX_REPAIR_TIMEOUT_SECONDS} seconds"
        )
    if not 0 < max_output_bytes <= MAX_REPAIR_OUTPUT_BYTES:
        parameter_errors.append(
            f"project environment repair output limit must be greater than 0 and at most {MAX_REPAIR_OUTPUT_BYTES} bytes"
        )
    if parameter_errors:
        return ProjectEnvironmentRepairResult(**base, ok=False, errors=parameter_errors)

    payload, errors = load_project_environment_contract(root)
    if errors:
        return ProjectEnvironmentRepairResult(**base, ok=False, errors=errors)
    existing_evidence, evidence_errors = load_project_environment_repair_evidence(root)
    if evidence_errors:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-invalid",
            errors=evidence_errors,
        )
    existing_repairs = existing_evidence.get("repairs")
    pending_evidence_ids = [
        str(record.get("id", ""))
        for record in existing_repairs
        if isinstance(record, dict) and record.get("status") == "pending"
    ] if isinstance(existing_repairs, list) else []
    if pending_evidence_ids:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-pending",
            errors=[
                "project environment repair evidence contains pending record(s): "
                + ", ".join(pending_evidence_ids)
            ],
        )
    environment = project_environment_by_id(payload, PROJECT_RUNTIME_ID)
    if environment is None:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            errors=[f"project environment contract must declare environment ID: {PROJECT_RUNTIME_ID}"],
        )
    tools = environment.get("tools")
    tool = next(
        (
            item
            for item in tools
            if isinstance(tools, list) and isinstance(item, dict) and item.get("id") == tool_id
        ),
        None,
    ) if isinstance(tools, list) else None
    if tool is None:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="registration-required",
            errors=[f"project runtime tool is not registered: {tool_id}"],
        )
    phase_errors: list[str] = []
    try:
        phase = str(load_state(root).get("phase", "unknown"))
    except StateFileError as error:
        phase = "unknown"
        phase_errors.append(str(error))
    if phase not in PROJECT_ENVIRONMENT_ALLOWED_PHASES:
        phase_errors.append(
            "project runtime repair requires workflow phase design-derivation or implementation"
        )
    phase_errors.extend(_project_environment_source_errors(root, tool))
    if phase_errors:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="blocked",
            errors=phase_errors,
            tool=tool,
        )

    readiness_before = inspect_project_environment_tool(root, tool)
    if readiness_before.get("ready") is True:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=True,
            action="already-ready",
            environment_ready=True,
            repair_ready=False,
            tool=tool,
            readiness_before=readiness_before,
            readiness_after=readiness_before,
        )

    repair = tool.get("repair")
    repair_payload = repair if isinstance(repair, dict) else {}
    strategy = str(repair_payload.get("strategy", "manual"))
    repair_action = {
        "id": f"repair-project-environment-tool-{tool_id}",
        "strategy": strategy,
        "tool_id": tool_id,
        "source": copy.deepcopy(repair_payload.get("source", {})),
        "instructions": str(repair_payload.get("instructions", "")),
        "writes_state": strategy != "governance-env",
        "approval_required": strategy != "governance-env",
    }
    if strategy == "manual":
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="manual-repair-required",
            environment_ready=False,
            repair_ready=False,
            errors=["project runtime tool requires the reviewed manual repair instructions"],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
        )
    if strategy == "governance-env":
        repair_action["repair_preflight_command"] = _governance_environment_repair_preflight(root)
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="governance-repair-preflight-required",
            environment_ready=False,
            repair_ready=False,
            errors=["project runtime tool delegates repair to the governance environment workflow"],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
        )

    command = repair_payload.get("command")
    command_cwd, resolved_executable, command_errors = _resolve_project_environment_repair_command(
        root,
        command,
    )
    if command_errors or command_cwd is None or resolved_executable is None:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-command-unavailable",
            environment_ready=False,
            repair_ready=False,
            errors=command_errors or ["project environment repair command is unavailable"],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
        )
    command_payload = command if isinstance(command, dict) else {}
    argv = command_payload.get("argv")
    exact_argv = [str(argument) for argument in argv] if isinstance(argv, list) else []
    repair_action["command"] = {
        "argv": exact_argv,
        "cwd": str(command_payload.get("cwd", ".")),
        "resolved_executable": str(resolved_executable),
    }
    apply_command = _project_environment_repair_apply_command(
        root,
        tool_id,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    if check:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=True,
            action="approval-required",
            environment_ready=False,
            repair_ready=True,
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
            apply_command=apply_command,
        )
    if not approved:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="approval-required",
            environment_ready=False,
            repair_ready=True,
            errors=["project environment reviewed repair command requires explicit --approved confirmation"],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
            apply_command=apply_command,
        )

    ledger, evidence_errors = load_project_environment_repair_evidence(root)
    if evidence_errors:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-invalid",
            environment_ready=False,
            repair_ready=False,
            errors=evidence_errors,
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
        )
    evidence_id = _new_project_environment_repair_id()
    try:
        record = _pending_project_environment_repair_record(
            root,
            tool,
            exact_argv,
            command_payload,
            resolved_executable,
            readiness_before,
            evidence_id,
        )
    except OSError as error:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-source-unreadable",
            errors=[
                f"project environment repair evidence source cannot be hashed: {error.strerror or error}"
            ],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
            evidence_id=evidence_id,
        )
    repairs = ledger.get("repairs")
    if not isinstance(repairs, list):
        repairs = []
        ledger["repairs"] = repairs
    if len(repairs) >= MAX_PROJECT_ENVIRONMENT_REPAIR_RECORDS:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-full",
            errors=[
                f"project environment repair evidence must contain fewer than {MAX_PROJECT_ENVIRONMENT_REPAIR_RECORDS} records"
            ],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
        )
    repairs.append(record)
    try:
        _write_project_environment_repair_evidence(root, ledger)
    except OSError as error:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-unwritable",
            errors=[f"project environment repair evidence is not writable: {error.strerror or error}"],
            tool=tool,
            readiness_before=readiness_before,
            repair_action=repair_action,
            evidence_id=evidence_id,
        )

    execution = run_bounded_command(
        [str(resolved_executable), *exact_argv[1:]],
        cwd=command_cwd,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )
    readiness_after = inspect_project_environment_tool(root, tool)
    execution_passed = execution.get("result") == "pass"
    environment_ready = readiness_after.get("ready") is True
    integrity_inputs_unchanged, integrity_errors = _project_environment_repair_integrity(
        root,
        record,
    )
    repair_succeeded = execution_passed and environment_ready and integrity_inputs_unchanged
    record["status"] = "completed" if repair_succeeded else "failed"
    execution_evidence = _project_environment_repair_execution_evidence(execution)
    execution_evidence["integrity_inputs_unchanged"] = integrity_inputs_unchanged
    execution_evidence["integrity_errors"] = integrity_errors
    record["execution"] = execution_evidence
    record["readiness_after"] = _project_environment_readiness_evidence(readiness_after)
    try:
        _write_project_environment_repair_evidence(root, ledger)
    except OSError as error:
        return ProjectEnvironmentRepairResult(
            **base,
            ok=False,
            action="repair-evidence-finalization-failed",
            environment_ready=environment_ready,
            repair_ready=True,
            errors=[
                "project environment repair command executed but evidence finalization failed: "
                f"{error.strerror or error}"
            ],
            tool=tool,
            readiness_before=readiness_before,
            readiness_after=readiness_after,
            repair_action=repair_action,
            execution=execution,
            evidence_id=evidence_id,
            updated=[PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.as_posix()],
        )

    action = (
        "repaired"
        if repair_succeeded
        else (
            "repair-integrity-failed"
            if not integrity_inputs_unchanged
            else ("applied-but-unresolved" if execution_passed else "repair-failed")
        )
    )
    result_errors: list[str] = []
    if not integrity_inputs_unchanged:
        result_errors.append(
            "project environment repair integrity input changed during execution: "
            + "; ".join(integrity_errors)
        )
    elif not execution_passed:
        result_errors.append("project environment reviewed repair command failed")
    elif not environment_ready:
        result_errors.append("project environment repair command passed but the required version remains unavailable")
    return ProjectEnvironmentRepairResult(
        **base,
        ok=repair_succeeded,
        action=action,
        environment_ready=environment_ready,
        repair_ready=True,
        errors=result_errors,
        tool=tool,
        readiness_before=readiness_before,
        readiness_after=readiness_after,
        repair_action=repair_action,
        execution=execution,
        evidence_id=evidence_id,
        updated=[PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.as_posix()],
    )


def _project_environment_tool_registration(
    root: Path,
    tool: dict[str, object],
    *,
    check: bool,
    reviewed: bool,
    replace: bool,
) -> ProjectEnvironmentRegistrationResult:
    root = root.resolve()
    tool_id = str(tool.get("id", "")) if isinstance(tool, dict) else ""
    base = {
        "target": str(root),
        "tool_id": tool_id,
        "check": check,
        "reviewed": reviewed,
        "replace": replace,
    }
    payload, errors = load_project_environment_contract(root)
    if errors:
        return ProjectEnvironmentRegistrationResult(**base, ok=False, errors=errors)
    environment = project_environment_by_id(payload, PROJECT_RUNTIME_ID)
    if environment is None:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=[f"project environment contract must declare environment ID: {PROJECT_RUNTIME_ID}"],
        )
    registration_errors: list[str] = []
    try:
        phase = str(load_state(root).get("phase", "unknown"))
    except StateFileError as error:
        phase = "unknown"
        registration_errors.append(str(error))
    if phase not in PROJECT_ENVIRONMENT_ALLOWED_PHASES:
        registration_errors.append(
            "project runtime registration requires workflow phase design-derivation or implementation"
        )
    if not reviewed:
        registration_errors.append("project runtime registration requires explicit --reviewed confirmation")
    if registration_errors:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=registration_errors,
            tool=tool,
            environment=environment,
        )
    if not isinstance(tool, dict):
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=["project environment registration tool must be an object"],
            environment=environment,
        )
    tool, integrity_errors = _bind_project_environment_repair_integrity(root, tool)
    if integrity_errors:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=integrity_errors,
            tool=tool,
            environment=environment,
        )

    tools = environment.get("tools")
    if not isinstance(tools, list):
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=["project runtime environment tools must be an array"],
            environment=environment,
        )
    existing_index = next(
        (index for index, item in enumerate(tools) if isinstance(item, dict) and item.get("id") == tool_id),
        None,
    )
    action = "register"
    prospective = copy.deepcopy(payload)
    prospective_environment = project_environment_by_id(prospective, PROJECT_RUNTIME_ID)
    if prospective_environment is None:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=[f"project environment contract must declare environment ID: {PROJECT_RUNTIME_ID}"],
            tool=tool,
            environment=environment,
        )
    prospective_tools = prospective_environment.get("tools")
    if not isinstance(prospective_tools, list):
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=["project runtime environment tools must be an array"],
            tool=tool,
            environment=environment,
        )
    if existing_index is not None:
        existing = tools[existing_index]
        if existing == tool:
            action = "already-registered"
        elif not replace:
            return ProjectEnvironmentRegistrationResult(
                **base,
                ok=False,
                errors=[
                    f"project environment tool {tool_id} already exists with a different definition; "
                    "rerun with --replace after reviewing the change"
                ],
                action="conflict",
                tool=tool,
                environment=environment,
            )
        else:
            action = "replace"
            prospective_tools[existing_index] = copy.deepcopy(tool)
    else:
        prospective_tools.append(copy.deepcopy(tool))

    errors = validate_project_environment_contract(prospective)
    errors.extend(_project_environment_source_errors(root, tool))
    if errors:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=errors,
            action=action,
            tool=tool,
            environment=environment,
        )
    if action == "already-registered":
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=True,
            action=action,
            tool=tool,
            environment=environment,
        )

    would_update = [PROJECT_ENVIRONMENT_REL.as_posix()]
    if check:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=True,
            action=action,
            would_update=would_update,
            tool=tool,
            environment=prospective_environment,
        )
    try:
        _write_project_environment_contract(root, prospective)
    except OSError as error:
        return ProjectEnvironmentRegistrationResult(
            **base,
            ok=False,
            errors=[f"project environment contract is not writable: {error.strerror or error}"],
            action=action,
            tool=tool,
            environment=environment,
        )
    return ProjectEnvironmentRegistrationResult(
        **base,
        ok=True,
        action=action,
        updated=would_update,
        tool=tool,
        environment=prospective_environment,
    )


def _project_environment_source_errors(root: Path, tool: dict[str, object]) -> list[str]:
    repair = tool.get("repair")
    if not isinstance(repair, dict):
        return []
    source = repair.get("source")
    if not isinstance(source, dict):
        return []
    errors: list[str] = []
    review_evidence = source.get("review_evidence")
    if isinstance(review_evidence, str) and not _project_environment_local_file(root, review_evidence):
        errors.append(f"project environment repair source review evidence is missing: {review_evidence}")
    source_type = source.get("type")
    location = source.get("location")
    if source_type in {"repository-doc", "workflow-pack"} and isinstance(location, str):
        if not _project_environment_local_file(root, location):
            errors.append(f"project environment repair source is missing: {location}")
    if repair.get("strategy") == "reviewed-command":
        errors.extend(project_environment_repair_command_errors(root, repair.get("command")))
    return errors


def project_environment_repair_command_errors(root: Path, command: object) -> list[str]:
    if not isinstance(command, dict):
        return []
    cwd_value = command.get("cwd")
    if not isinstance(cwd_value, str):
        return []
    cwd = root if cwd_value == "." else root.joinpath(*PurePosixPath(cwd_value).parts)
    if cwd.is_symlink() or not cwd.is_dir():
        return [f"project environment repair command cwd is missing or unsafe: {cwd_value}"]
    try:
        resolved_cwd = cwd.resolve()
        resolved_cwd.relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return [f"project environment repair command cwd escapes the repository: {cwd_value}"]
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not isinstance(argv[0], str) or "/" not in argv[0]:
        return []
    candidate = resolved_cwd.joinpath(*PurePosixPath(argv[0]).parts)
    if candidate.is_symlink() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        return [f"project environment repair executable is missing or unsafe: {argv[0]}"]
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return [f"project environment repair executable escapes the repository: {argv[0]}"]
    expected_sha256 = command.get("executable_sha256")
    try:
        observed_sha256 = _sha256_file(candidate)
    except OSError as error:
        return [
            "project environment repair executable cannot be hashed: "
            f"{error.strerror or error}"
        ]
    if observed_sha256 != expected_sha256:
        return [
            f"project environment repair executable SHA-256 does not match the reviewed contract: {argv[0]}"
        ]
    return []


def _bind_project_environment_repair_integrity(
    root: Path,
    tool: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    bound_tool = copy.deepcopy(tool)
    repair = bound_tool.get("repair")
    if not isinstance(repair, dict) or repair.get("strategy") != "reviewed-command":
        return bound_tool, []
    command = repair.get("command")
    if not isinstance(command, dict):
        return bound_tool, []
    argv = command.get("argv")
    cwd_value = command.get("cwd")
    if (
        not isinstance(argv, list)
        or not argv
        or not isinstance(argv[0], str)
        or "/" not in argv[0]
        or not isinstance(cwd_value, str)
    ):
        return bound_tool, []
    if cwd_value != "." and not _normalized_repository_path(cwd_value):
        return bound_tool, []
    if not _normalized_repository_path(argv[0]):
        return bound_tool, []
    cwd = root if cwd_value == "." else root.joinpath(*PurePosixPath(cwd_value).parts)
    if cwd.is_symlink() or not cwd.is_dir():
        return bound_tool, [f"project environment repair command cwd is missing or unsafe: {cwd_value}"]
    candidate = cwd.joinpath(*PurePosixPath(argv[0]).parts)
    if candidate.is_symlink() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        return bound_tool, [f"project environment repair executable is missing or unsafe: {argv[0]}"]
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return bound_tool, [f"project environment repair executable escapes the repository: {argv[0]}"]
    try:
        observed_sha256 = _sha256_file(candidate)
    except OSError as error:
        return bound_tool, [
            "project environment repair executable cannot be hashed during registration: "
            f"{error.strerror or error}"
        ]
    expected_sha256 = command.get("executable_sha256")
    if isinstance(expected_sha256, str) and expected_sha256 != observed_sha256:
        return bound_tool, [
            f"project environment repair executable SHA-256 does not match registration input: {argv[0]}"
        ]
    command["executable_sha256"] = observed_sha256
    return bound_tool, []


def _project_environment_local_file(root: Path, rel: str) -> bool:
    candidate = root / rel
    if candidate.is_symlink() or not candidate.is_file():
        return False
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _write_project_environment_contract(root: Path, payload: dict[str, object]) -> None:
    path = root / PROJECT_ENVIRONMENT_REL
    temp_path = root / PROJECT_ENVIRONMENT_TEMP_REL
    if temp_path.is_symlink() or (temp_path.exists() and not temp_path.is_file()):
        raise OSError(f"temporary path is not a regular file: {PROJECT_ENVIRONMENT_TEMP_REL.as_posix()}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        if temp_path.is_file() and not temp_path.is_symlink():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


@contextmanager
def _project_environment_lock(root: Path) -> Iterator[None]:
    if fcntl is None:
        raise ProjectEnvironmentLockUnavailable("POSIX advisory file locking is unavailable")
    path = root / PROJECT_ENVIRONMENT_LOCK_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + PROJECT_ENVIRONMENT_LOCK_WAIT_SECONDS
    with path.open("a+b") as lock:
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise ProjectEnvironmentLockUnavailable(
                        f"timed out after {PROJECT_ENVIRONMENT_LOCK_WAIT_SECONDS} seconds waiting for {path}"
                    ) from error
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def inspect_project_environment_tool(
    command_cwd: Path | None,
    tool: dict[str, object],
    *,
    resolved_override: Path | None = None,
) -> dict[str, object]:
    executable = str(tool.get("executable", ""))
    result: dict[str, object] = {
        "id": str(tool.get("id", "")),
        "executable": executable,
        "resolved_path": "",
        "available": False,
        "executable_ready": False,
        "probe_executed": False,
        "probe_passed": False,
        "observed_version": "",
        "version_requirement": dict(tool.get("version_requirement", {}))
        if isinstance(tool.get("version_requirement"), dict)
        else {},
        "version_satisfies": False,
        "ready": False,
        "blocker_code": "environment_tool_unavailable",
        "repair": dict(tool.get("repair", {})) if isinstance(tool.get("repair"), dict) else {},
    }
    if command_cwd is None:
        result["blocker_code"] = "environment_tool_cwd_unavailable"
        return result
    if resolved_override is not None:
        found = str(resolved_override)
    else:
        try:
            found = shutil.which(executable, path=_project_environment_command_search_path(command_cwd))
        except (OSError, RuntimeError, ValueError):
            found = None
    if not found:
        return result
    try:
        resolved = Path(found).resolve()
    except (OSError, RuntimeError, ValueError):
        resolved = Path(found)
    available, executable_ready = _project_environment_executable_status(resolved)
    result["resolved_path"] = str(resolved)
    result["available"] = available
    result["executable_ready"] = executable_ready
    if not available or not executable_ready:
        result["blocker_code"] = "environment_tool_not_executable"
        return result
    probe = tool.get("version_probe")
    if not isinstance(probe, dict):
        result["blocker_code"] = "environment_tool_probe_invalid"
        return result
    args = probe.get("args")
    if not isinstance(args, list) or any(not isinstance(argument, str) for argument in args):
        result["blocker_code"] = "environment_tool_probe_invalid"
        return result
    execution = run_bounded_command(
        [str(resolved), *args],
        cwd=command_cwd,
        timeout_seconds=PROJECT_ENVIRONMENT_PROBE_TIMEOUT_SECONDS,
        max_output_bytes=PROJECT_ENVIRONMENT_PROBE_MAX_OUTPUT_BYTES,
    )
    result["probe_executed"] = execution.get("started") is True
    output_name = str(probe.get("output", ""))
    stdout = str(execution.get("stdout", ""))
    stderr = str(execution.get("stderr", ""))
    output = stdout if output_name == "stdout" else stderr
    if output_name == "combined":
        output = "\n".join(item for item in (stdout, stderr) if item)
    observed_version = extract_probed_version(output, str(probe.get("prefix", "")))
    probe_passed = execution.get("result") == "pass" and bool(observed_version)
    requirement = tool.get("version_requirement")
    version_satisfies = (
        probe_passed
        and isinstance(requirement, dict)
        and version_satisfies_requirement(observed_version, requirement)
    )
    result["probe_passed"] = probe_passed
    result["observed_version"] = observed_version
    result["version_satisfies"] = version_satisfies
    result["probe_result"] = {
        "returncode": execution.get("returncode"),
        "timed_out": execution.get("timed_out") is True,
        "output_redacted": execution.get("output_redacted") is True,
    }
    if not probe_passed:
        result["blocker_code"] = "environment_tool_version_probe_failed"
        return result
    if not version_satisfies:
        result["blocker_code"] = "environment_tool_version_unsatisfied"
        return result
    result["ready"] = True
    result["blocker_code"] = ""
    return result


def _resolve_project_environment_repair_command(
    root: Path,
    command: object,
) -> tuple[Path | None, Path | None, list[str]]:
    if not isinstance(command, dict):
        return None, None, ["project environment reviewed repair command is missing"]
    cwd_value = command.get("cwd")
    argv = command.get("argv")
    if not isinstance(cwd_value, str) or not isinstance(argv, list) or not argv:
        return None, None, ["project environment reviewed repair command is invalid"]
    cwd = root if cwd_value == "." else root.joinpath(*PurePosixPath(cwd_value).parts)
    if cwd.is_symlink() or not cwd.is_dir():
        return None, None, [f"project environment repair command cwd is missing or unsafe: {cwd_value}"]
    try:
        resolved_cwd = cwd.resolve()
        resolved_cwd.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None, None, [f"project environment repair command cwd escapes the repository: {cwd_value}"]
    executable = str(argv[0])
    if "/" in executable:
        candidate = resolved_cwd.joinpath(*PurePosixPath(executable).parts)
        if candidate.is_symlink():
            return None, None, [f"project environment repair executable must not be a symlink: {executable}"]
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError):
            return None, None, [f"project environment repair executable escapes the repository: {executable}"]
    else:
        try:
            found = shutil.which(executable, path=_project_environment_command_search_path(resolved_cwd))
        except (OSError, RuntimeError, ValueError):
            found = None
        if not found:
            return None, None, [f"project environment repair command executable is unavailable: {executable}"]
        try:
            resolved = Path(found).resolve()
        except (OSError, RuntimeError, ValueError):
            resolved = Path(found)
    available, executable_ready = _project_environment_executable_status(resolved)
    if not available or not executable_ready:
        return None, None, [f"project environment repair command executable is not executable: {executable}"]
    return resolved_cwd, resolved, []


def _project_environment_command_search_path(command_cwd: Path) -> str:
    entries: list[str] = []
    for entry in os.get_exec_path():
        path = Path(entry) if entry else Path(".")
        entries.append(str(path if path.is_absolute() else (command_cwd / path).resolve()))
    return os.pathsep.join(entries)


def _project_environment_executable_status(path: Path) -> tuple[bool, bool]:
    try:
        available = path.is_file()
        return available, available and os.access(path, os.X_OK)
    except (OSError, RuntimeError, ValueError):
        return False, False


def _project_environment_repair_apply_command(
    root: Path,
    tool_id: str,
    *,
    timeout_seconds: float,
    max_output_bytes: int,
) -> dict[str, object]:
    return {
        "id": f"apply-project-environment-repair-{tool_id}",
        "description": "Execute the exact reviewed repair command and atomically record repair evidence.",
        "cwd": str(root),
        "argv": [
            "bin/governance",
            "project-env",
            "repair",
            ".",
            "--tool-id",
            tool_id,
            "--approved",
            "--timeout-seconds",
            str(timeout_seconds),
            "--max-output-bytes",
            str(max_output_bytes),
            "--json",
        ],
        "writes_state": True,
        "approval_required": True,
    }


def _governance_environment_repair_preflight(root: Path) -> dict[str, object]:
    return {
        "id": "preflight-governance-environment-repair",
        "description": "Preview governance environment repair without writing or installing.",
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


def load_project_environment_repair_evidence(
    root: Path,
) -> tuple[dict[str, object], list[str]]:
    path = root / PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL
    if not path.exists():
        return {
            "schema_version": PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_SCHEMA_VERSION,
            "repairs": [],
        }, []
    rel = PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL.as_posix()
    if path.is_symlink() or not path.is_file():
        return {}, [f"project environment repair evidence must be a regular file: {rel}"]
    try:
        if path.stat().st_size > PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_MAX_BYTES:
            return {}, [
                f"project environment repair evidence must not exceed {PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_MAX_BYTES} bytes: {rel}"
            ]
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {}, [f"project environment repair evidence must be UTF-8: {rel}"]
    except OSError as error:
        return {}, [f"project environment repair evidence cannot be read: {error.strerror or error}"]
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError) as error:
        return {}, [f"project environment repair evidence must be valid JSON: {error}"]
    if not isinstance(payload, dict):
        return {}, ["project environment repair evidence root must be an object"]
    errors = validate_project_environment_repair_evidence(payload)
    return payload, errors


def validate_project_environment_repair_evidence(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    _check_keys(payload, {"schema_version", "repairs"}, "project environment repair evidence", errors)
    if payload.get("schema_version") != PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_SCHEMA_VERSION:
        errors.append(
            "project environment repair evidence schema_version must be "
            f"{PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_SCHEMA_VERSION}"
        )
    repairs = payload.get("repairs")
    if not isinstance(repairs, list):
        errors.append("project environment repair evidence repairs must be an array")
        return errors
    if len(repairs) > MAX_PROJECT_ENVIRONMENT_REPAIR_RECORDS:
        errors.append(
            f"project environment repair evidence must contain no more than {MAX_PROJECT_ENVIRONMENT_REPAIR_RECORDS} records"
        )
    seen_ids: set[str] = set()
    for index, record in enumerate(repairs):
        _validate_project_environment_repair_record(
            record,
            f"project environment repair evidence repairs[{index}]",
            seen_ids,
            errors,
        )
    return errors


def _validate_project_environment_repair_record(
    record: object,
    label: str,
    seen_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(record, dict):
        errors.append(f"{label} must be an object")
        return
    _check_keys(
        record,
        {
            "id",
            "status",
            "tool_id",
            "contract_sha256",
            "source",
            "review_evidence",
            "repair_command",
            "readiness_before",
            "readiness_after",
            "execution",
        },
        label,
        errors,
    )
    record_id = record.get("id")
    if not isinstance(record_id, str) or REPAIR_RECORD_ID_RE.fullmatch(record_id) is None:
        errors.append(f"{label}.id must be a project environment repair record ID")
    elif record_id in seen_ids:
        errors.append(f"project environment repair evidence record ID must be unique: {record_id}")
    else:
        seen_ids.add(record_id)
    if record.get("status") not in {"pending", "completed", "failed"}:
        errors.append(f"{label}.status must be pending, completed, or failed")
    tool_id = record.get("tool_id")
    if not isinstance(tool_id, str) or PROJECT_ENVIRONMENT_TOOL_ID_RE.fullmatch(tool_id) is None:
        errors.append(f"{label}.tool_id must be a lowercase slug")
    if not isinstance(record.get("contract_sha256"), str) or SHA256_RE.fullmatch(
        str(record.get("contract_sha256", ""))
    ) is None:
        errors.append(f"{label}.contract_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(record.get("source"), dict):
        errors.append(f"{label}.source must be an object")
    review_evidence = record.get("review_evidence")
    if (
        not isinstance(review_evidence, dict)
        or not isinstance(review_evidence.get("path"), str)
        or SHA256_RE.fullmatch(str(review_evidence.get("sha256", ""))) is None
    ):
        errors.append(f"{label}.review_evidence must contain path and SHA-256 evidence")
    for key in ("repair_command", "readiness_before", "readiness_after", "execution"):
        if not isinstance(record.get(key), dict):
            errors.append(f"{label}.{key} must be an object")
    repair_command = record.get("repair_command")
    if isinstance(repair_command, dict):
        if not isinstance(repair_command.get("argv"), list) or not repair_command.get("argv"):
            errors.append(f"{label}.repair_command.argv must be a non-empty array")
        if not isinstance(repair_command.get("cwd"), str):
            errors.append(f"{label}.repair_command.cwd must be a string")
        if not isinstance(repair_command.get("resolved_executable"), str):
            errors.append(f"{label}.repair_command.resolved_executable must be a string")
        if SHA256_RE.fullmatch(str(repair_command.get("executable_sha256", ""))) is None:
            errors.append(f"{label}.repair_command.executable_sha256 must be a SHA-256 digest")
    readiness_after = record.get("readiness_after")
    execution = record.get("execution")
    status = record.get("status")
    if isinstance(execution, dict) and any(key in execution for key in ("stdout", "stderr")):
        errors.append(f"{label}.execution must not store stdout or stderr")
    if status == "pending" and (execution or readiness_after):
        errors.append(f"{label} pending record must not contain execution or readiness_after evidence")
    if status == "completed" and isinstance(execution, dict) and isinstance(readiness_after, dict):
        if execution.get("result") != "pass":
            errors.append(f"{label} completed record execution result must be pass")
        if execution.get("integrity_inputs_unchanged") is not True:
            errors.append(f"{label} completed record integrity inputs must be unchanged")
        if readiness_after.get("ready") is not True:
            errors.append(f"{label} completed record readiness_after.ready must be true")


def _pending_project_environment_repair_record(
    root: Path,
    tool: dict[str, object],
    exact_argv: list[str],
    command: dict[str, object],
    resolved_executable: Path,
    readiness_before: dict[str, object],
    evidence_id: str,
) -> dict[str, object]:
    repair = tool.get("repair")
    repair_payload = repair if isinstance(repair, dict) else {}
    source = repair_payload.get("source")
    source_payload = copy.deepcopy(source) if isinstance(source, dict) else {}
    location = source_payload.get("location")
    if source_payload.get("type") in {"repository-doc", "workflow-pack"} and isinstance(location, str):
        source_payload["sha256"] = _sha256_file(root / location)
    review_path = str(source_payload.get("review_evidence", ""))
    command_evidence: dict[str, object] = {
        "argv": exact_argv,
        "cwd": str(command.get("cwd", ".")),
        "resolved_executable": str(resolved_executable),
    }
    command_evidence["executable_sha256"] = _sha256_file(resolved_executable)
    return {
        "id": evidence_id,
        "status": "pending",
        "tool_id": str(tool.get("id", "")),
        "contract_sha256": _sha256_file(root / PROJECT_ENVIRONMENT_REL),
        "source": source_payload,
        "review_evidence": {
            "path": review_path,
            "sha256": _sha256_file(root / review_path),
        },
        "repair_command": command_evidence,
        "readiness_before": _project_environment_readiness_evidence(readiness_before),
        "readiness_after": {},
        "execution": {},
    }


def _project_environment_readiness_evidence(readiness: dict[str, object]) -> dict[str, object]:
    return {
        "ready": readiness.get("ready") is True,
        "blocker_code": str(readiness.get("blocker_code", "")),
        "resolved_path": str(readiness.get("resolved_path", "")),
        "observed_version": str(readiness.get("observed_version", "")),
        "version_satisfies": readiness.get("version_satisfies") is True,
        "probe_executed": readiness.get("probe_executed") is True,
    }


def _project_environment_repair_execution_evidence(execution: dict[str, object]) -> dict[str, object]:
    return {
        key: copy.deepcopy(value)
        for key, value in execution.items()
        if key not in {"argv", "cwd", "stdout", "stderr", "started"}
    }


def _project_environment_repair_integrity(
    root: Path,
    record: dict[str, object],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    def compare(path: Path, expected: object, label: str) -> None:
        try:
            observed = _sha256_file(path)
        except OSError as error:
            errors.append(f"{label} cannot be re-read: {error.strerror or error}")
            return
        if observed != expected:
            errors.append(f"{label} SHA-256 changed")

    compare(
        root / PROJECT_ENVIRONMENT_REL,
        record.get("contract_sha256"),
        "project environment contract",
    )
    review_evidence = record.get("review_evidence")
    if isinstance(review_evidence, dict):
        review_path = review_evidence.get("path")
        if isinstance(review_path, str):
            compare(root / review_path, review_evidence.get("sha256"), "repair review evidence")
    source = record.get("source")
    if isinstance(source, dict) and isinstance(source.get("sha256"), str):
        source_location = source.get("location")
        if isinstance(source_location, str):
            compare(root / source_location, source.get("sha256"), "repair source")
    repair_command = record.get("repair_command")
    if isinstance(repair_command, dict):
        resolved_executable = repair_command.get("resolved_executable")
        if isinstance(resolved_executable, str):
            compare(
                Path(resolved_executable),
                repair_command.get("executable_sha256"),
                "repair executable",
            )
    return not errors, errors


def _write_project_environment_repair_evidence(root: Path, payload: dict[str, object]) -> None:
    path = root / PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL
    temp_path = root / PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_TEMP_REL
    if temp_path.is_symlink() or (temp_path.exists() and not temp_path.is_file()):
        raise OSError(
            f"temporary path is not a regular file: {PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_TEMP_REL.as_posix()}"
        )
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if len(content.encode("utf-8")) > PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_MAX_BYTES:
        raise OSError("project environment repair evidence exceeds its maximum size")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        if temp_path.is_file() and not temp_path.is_symlink():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def _new_project_environment_repair_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"PER-{timestamp}-{token_hex(4)}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_project_environment_contract(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    _check_keys(payload, {"schema_version", "environments"}, "project environment contract", errors)
    if payload.get("schema_version") != PROJECT_ENVIRONMENT_SCHEMA_VERSION:
        errors.append(
            f"project environment contract schema_version must be {PROJECT_ENVIRONMENT_SCHEMA_VERSION}"
        )
    environments = payload.get("environments")
    if not isinstance(environments, list) or not environments:
        errors.append("project environment contract environments must be a non-empty array")
        return errors
    if len(environments) > MAX_ENVIRONMENTS:
        errors.append(
            f"project environment contract environments must contain no more than {MAX_ENVIRONMENTS} entries"
        )

    seen_environment_ids: set[str] = set()
    for index, environment in enumerate(environments):
        _validate_environment(
            environment,
            f"project environment contract environments[{index}]",
            seen_environment_ids,
            errors,
        )
    return errors


def project_environment_by_id(
    payload: dict[str, object], environment_id: str
) -> dict[str, object] | None:
    environments = payload.get("environments")
    if not isinstance(environments, list):
        return None
    for environment in environments:
        if isinstance(environment, dict) and environment.get("id") == environment_id:
            return environment
    return None


def parse_numeric_version(value: str) -> tuple[int, int, int, int] | None:
    value = value.strip()
    if not VERSION_RE.fullmatch(value):
        return None
    raw_parts = value.split(".")
    if any(len(part) > MAX_VERSION_COMPONENT_DIGITS for part in raw_parts):
        return None
    parts = [int(part) for part in raw_parts]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


def version_satisfies_requirement(version: str, requirement: dict[str, object]) -> bool:
    parsed = parse_numeric_version(version)
    if parsed is None:
        return False
    exact = requirement.get("exact")
    minimum = requirement.get("minimum")
    maximum_exclusive = requirement.get("maximum_exclusive")
    if isinstance(exact, str):
        return parsed == parse_numeric_version(exact)
    if isinstance(minimum, str):
        parsed_minimum = parse_numeric_version(minimum)
        if parsed_minimum is None or parsed < parsed_minimum:
            return False
    if isinstance(maximum_exclusive, str):
        parsed_maximum = parse_numeric_version(maximum_exclusive)
        if parsed_maximum is None or parsed >= parsed_maximum:
            return False
    return True


def extract_probed_version(output: str, prefix: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        candidates = stripped[len(prefix) :].strip().split(maxsplit=1)
        if not candidates:
            return ""
        candidate = candidates[0]
        return candidate if parse_numeric_version(candidate) is not None else ""
    return ""


def _validate_environment(
    environment: object,
    label: str,
    seen_environment_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(environment, dict):
        errors.append(f"{label} must be an object")
        return
    _check_keys(
        environment,
        {"id", "description", "allow_repository_executables", "tools"},
        label,
        errors,
    )
    environment_id = environment.get("id")
    if (
        not isinstance(environment_id, str)
        or len(environment_id) > MAX_ID_LENGTH
        or not PROJECT_ENVIRONMENT_ID_RE.fullmatch(environment_id)
    ):
        errors.append(f"{label}.id must be a lowercase slug")
    elif environment_id in seen_environment_ids:
        errors.append(f"project environment contract environment id must be unique: {environment_id}")
    else:
        seen_environment_ids.add(environment_id)
    description = environment.get("description")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > MAX_DESCRIPTION_LENGTH
    ):
        errors.append(f"{label}.description must be a non-empty string")
    if not isinstance(environment.get("allow_repository_executables"), bool):
        errors.append(f"{label}.allow_repository_executables must be a boolean")
    tools = environment.get("tools")
    if not isinstance(tools, list):
        errors.append(f"{label}.tools must be an array")
        return
    if len(tools) > MAX_TOOLS_PER_ENVIRONMENT:
        errors.append(f"{label}.tools must contain no more than {MAX_TOOLS_PER_ENVIRONMENT} entries")
    seen_tool_ids: set[str] = set()
    seen_executables: set[str] = set()
    for tool_index, tool in enumerate(tools):
        _validate_tool(
            tool,
            f"{label}.tools[{tool_index}]",
            seen_tool_ids,
            seen_executables,
            errors,
        )


def _validate_tool(
    tool: object,
    label: str,
    seen_tool_ids: set[str],
    seen_executables: set[str],
    errors: list[str],
) -> None:
    if not isinstance(tool, dict):
        errors.append(f"{label} must be an object")
        return
    _check_keys(
        tool,
        {"id", "executable", "version_probe", "version_requirement", "repair"},
        label,
        errors,
    )
    tool_id = tool.get("id")
    if (
        not isinstance(tool_id, str)
        or len(tool_id) > MAX_ID_LENGTH
        or not PROJECT_ENVIRONMENT_TOOL_ID_RE.fullmatch(tool_id)
    ):
        errors.append(f"{label}.id must be a lowercase slug")
    elif tool_id in seen_tool_ids:
        errors.append(f"project environment tool id must be unique within its environment: {tool_id}")
    else:
        seen_tool_ids.add(tool_id)
    executable = tool.get("executable")
    if (
        not isinstance(executable, str)
        or len(executable) > MAX_EXECUTABLE_LENGTH
        or not PROJECT_ENVIRONMENT_EXECUTABLE_RE.fullmatch(executable)
    ):
        errors.append(f"{label}.executable must be a bare executable name")
        executable = ""
    elif executable in seen_executables:
        errors.append(f"project environment executable must be unique within its environment: {executable}")
    else:
        seen_executables.add(executable)
    _validate_version_probe(tool.get("version_probe"), f"{label}.version_probe", errors)
    _validate_version_requirement(tool.get("version_requirement"), f"{label}.version_requirement", errors)
    _validate_repair(tool.get("repair"), executable, f"{label}.repair", errors)


def _validate_version_probe(probe: object, label: str, errors: list[str]) -> None:
    if not isinstance(probe, dict):
        errors.append(f"{label} must be an object")
        return
    _check_keys(probe, {"args", "output", "prefix"}, label, errors)
    args = probe.get("args")
    if not isinstance(args, list) or tuple(args) not in APPROVED_VERSION_PROBE_ARGS:
        errors.append(f"{label}.args must be an approved read-only version argument")
    if probe.get("output") not in {"stdout", "stderr", "combined"}:
        errors.append(f"{label}.output must be stdout, stderr, or combined")
    prefix = probe.get("prefix")
    if (
        not isinstance(prefix, str)
        or not prefix
        or len(prefix) > MAX_VERSION_PREFIX_LENGTH
        or any(character in prefix for character in "\r\n\x00")
    ):
        errors.append(
            f"{label}.prefix must be a non-empty single-line string no longer than "
            f"{MAX_VERSION_PREFIX_LENGTH} characters"
        )


def _validate_version_requirement(requirement: object, label: str, errors: list[str]) -> None:
    if not isinstance(requirement, dict) or not requirement:
        errors.append(f"{label} must be a non-empty object")
        return
    _check_unknown_keys(requirement, VERSION_REQUIREMENT_KEYS, label, errors)
    for key, value in requirement.items():
        if key in VERSION_REQUIREMENT_KEYS and (
            not isinstance(value, str) or parse_numeric_version(value) is None
        ):
            errors.append(f"{label}.{key} must be a numeric dotted version")
    if "exact" in requirement and len(requirement) != 1:
        errors.append(f"{label}.exact cannot be combined with version range fields")
    minimum = requirement.get("minimum")
    maximum = requirement.get("maximum_exclusive")
    if isinstance(minimum, str) and isinstance(maximum, str):
        parsed_minimum = parse_numeric_version(minimum)
        parsed_maximum = parse_numeric_version(maximum)
        if parsed_minimum is not None and parsed_maximum is not None and parsed_minimum >= parsed_maximum:
            errors.append(f"{label}.minimum must be lower than maximum_exclusive")


def _validate_repair(repair: object, executable: str, label: str, errors: list[str]) -> None:
    if not isinstance(repair, dict):
        errors.append(f"{label} must be an object")
        return
    strategy = repair.get("strategy")
    if strategy not in REPAIR_STRATEGIES:
        errors.append(f"{label}.strategy must be governance-env, manual, or reviewed-command")
        return
    if strategy == "governance-env":
        expected_keys = {"strategy", "source", "tool"}
    elif strategy == "reviewed-command":
        expected_keys = {"strategy", "source", "instructions", "command"}
    else:
        expected_keys = {"strategy", "source", "instructions"}
    _check_keys(repair, expected_keys, label, errors)
    _validate_source(repair.get("source"), f"{label}.source", errors)
    if strategy == "governance-env":
        _validate_governance_repair(repair, executable, label, errors)
    else:
        _validate_manual_repair(repair, label, errors)
        if strategy == "reviewed-command":
            _validate_reviewed_repair_command(repair.get("command"), f"{label}.command", errors)


def _validate_governance_repair(
    repair: dict[str, object], executable: str, label: str, errors: list[str]
) -> None:
    if repair.get("tool") != executable:
        errors.append(f"{label}.tool must match the declared executable")
    source = repair.get("source")
    if (
        not isinstance(source, dict)
        or source.get("type") != "workflow-pack"
        or source.get("location") != "scripts/check_env.py"
    ):
        errors.append(f"{label}.source must reference workflow-pack scripts/check_env.py")


def _validate_manual_repair(
    repair: dict[str, object], label: str, errors: list[str]
) -> None:
    instructions = repair.get("instructions")
    if (
        not isinstance(instructions, str)
        or not instructions.strip()
        or len(instructions) > MAX_REPAIR_INSTRUCTIONS_LENGTH
        or "REPLACE" in instructions.upper()
    ):
        errors.append(f"{label}.instructions must contain reviewed manual repair guidance")


def _validate_reviewed_repair_command(command: object, label: str, errors: list[str]) -> None:
    if not isinstance(command, dict):
        errors.append(f"{label} must be an object")
        return
    missing = sorted({"argv", "cwd"} - set(command))
    if missing:
        errors.append(f"{label} is missing field(s): {', '.join(missing)}")
    _check_unknown_keys(command, {"argv", "cwd", "executable_sha256"}, label, errors)
    cwd = command.get("cwd")
    if not isinstance(cwd, str) or (cwd != "." and not _normalized_repository_path(cwd)):
        errors.append(f"{label}.cwd must be . or a normalized repository-relative path")
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or len(argv) > MAX_REPAIR_COMMAND_ARGS:
        errors.append(
            f"{label}.argv must contain between 1 and {MAX_REPAIR_COMMAND_ARGS} explicit arguments"
        )
        return
    if any(
        not isinstance(argument, str)
        or not argument
        or len(argument) > MAX_REPAIR_COMMAND_ARG_LENGTH
        or any(character in argument for character in "\x00\r\n")
        or "REPLACE" in argument.upper()
        or (argument.startswith("<") and argument.endswith(">"))
        for argument in argv
    ):
        errors.append(f"{label}.argv must contain bounded single-line arguments without placeholders")
        return
    executable = argv[0]
    executable_name = PurePosixPath(executable).name.lower()
    if executable_name in FORBIDDEN_REPAIR_EXECUTABLES:
        errors.append(f"{label}.argv[0] must not invoke a shell or privilege wrapper")
    if "/" not in executable:
        if not PROJECT_ENVIRONMENT_EXECUTABLE_RE.fullmatch(executable):
            errors.append(f"{label}.argv[0] must be a bare executable or repository-relative path")
    elif not _normalized_repository_path(executable):
        errors.append(f"{label}.argv[0] must be a normalized repository-relative executable path")
    executable_sha256 = command.get("executable_sha256")
    if "/" in executable:
        if not isinstance(executable_sha256, str) or SHA256_RE.fullmatch(executable_sha256) is None:
            errors.append(f"{label}.executable_sha256 must bind the repository repair executable")
    elif executable_sha256 is not None:
        errors.append(f"{label}.executable_sha256 is only valid for repository repair executables")
    if _repair_command_uses_inline_code(executable_name, argv[1:]):
        errors.append(f"{label}.argv must not execute inline interpreter code")
    if any(_sensitive_repair_argument(argument) for argument in argv):
        errors.append(f"{label}.argv must not contain a sensitive command argument")


def _repair_command_uses_inline_code(executable_name: str, arguments: list[object]) -> bool:
    string_arguments = {str(argument) for argument in arguments}
    if executable_name.startswith("python"):
        return "-c" in string_arguments
    if executable_name in {"node", "nodejs"}:
        return bool(string_arguments & {"-e", "--eval", "-p", "--print"})
    if executable_name in {"perl", "ruby"}:
        return "-e" in string_arguments
    return False


def _sensitive_repair_argument(argument: str) -> bool:
    if SENSITIVE_REPAIR_TOKEN_RE.search(argument):
        return True
    parsed = urlsplit(argument) if "://" in argument else None
    if parsed is not None and (parsed.username is not None or parsed.password is not None):
        return True
    key = argument.lstrip("-").split("=", 1)[0].lower().replace("_", "-")
    return key in SENSITIVE_REPAIR_ARGUMENT_KEYS or any(
        key.endswith(f"-{suffix}") for suffix in SENSITIVE_REPAIR_ARGUMENT_KEYS
    )


def _validate_source(source: object, label: str, errors: list[str]) -> None:
    if not isinstance(source, dict):
        errors.append(f"{label} must be an object")
        return
    _check_keys(source, {"type", "location", "review_evidence"}, label, errors)
    source_type = source.get("type")
    location = source.get("location")
    if source_type not in SOURCE_TYPES:
        errors.append(f"{label}.type must be official-url, repository-doc, or workflow-pack")
    if (
        not isinstance(location, str)
        or not location
        or len(location) > MAX_SOURCE_LOCATION_LENGTH
        or "REPLACE" in location.upper()
    ):
        errors.append(f"{label}.location must identify a reviewed source")
        return
    if source_type == "official-url":
        parsed = urlsplit(location)
        if parsed.scheme != "https" or not parsed.hostname:
            errors.append(f"{label}.location must identify an HTTPS host for an official URL")
    if source_type in {"repository-doc", "workflow-pack"} and not _normalized_repository_path(location):
        errors.append(f"{label}.location must be a normalized repository-relative path")
    review_evidence = source.get("review_evidence")
    if (
        not isinstance(review_evidence, str)
        or len(review_evidence) > MAX_REVIEW_EVIDENCE_LENGTH
        or not _normalized_repository_path(review_evidence)
        or not review_evidence.endswith(".md")
    ):
        errors.append(f"{label}.review_evidence must be a normalized local Markdown path")


def _normalized_repository_path(value: str) -> bool:
    if not value or "\\" in value or value.startswith(("/", "~")):
        return False
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    return (
        not windows.is_absolute()
        and not windows.drive
        and not posix.is_absolute()
        and posix.as_posix() == value
        and bool(posix.parts)
        and all(part not in {"", ".", ".."} for part in posix.parts)
    )


def _check_keys(
    payload: dict[str, object], expected: set[str], label: str, errors: list[str]
) -> None:
    missing = sorted(expected - set(payload))
    unknown = sorted(set(payload) - expected)
    if missing:
        errors.append(f"{label} is missing field(s): {', '.join(missing)}")
    if unknown:
        errors.append(f"{label} has unknown field(s): {', '.join(unknown)}")


def _check_unknown_keys(
    payload: dict[str, object], allowed: set[str], label: str, errors: list[str]
) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        errors.append(f"{label} has unknown field(s): {', '.join(unknown)}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result
