from __future__ import annotations

import copy
import json
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover - target runtime uses POSIX wrappers
    fcntl = None  # type: ignore[assignment]

try:
    from .state import StateFileError, load_state
except ImportError:  # pragma: no cover - direct script execution
    from state import StateFileError, load_state


PROJECT_ENVIRONMENT_REL = Path("docs/agent-workflow/project-environment.json")
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
REPAIR_STRATEGIES = {"governance-env", "manual"}
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
PROJECT_ENVIRONMENT_SPECIALIST_SKILLS = ("tech-stack-evaluator", "senior-architect")
PROJECT_ENVIRONMENT_ALLOWED_PHASES = {"design-derivation", "implementation"}
PROJECT_ENVIRONMENT_TEMP_REL = PROJECT_ENVIRONMENT_REL.with_name(f".{PROJECT_ENVIRONMENT_REL.name}.tmp")
PROJECT_ENVIRONMENT_LOCK_REL = Path(".governance/project-environment.lock")
PROJECT_ENVIRONMENT_LOCK_WAIT_SECONDS = 0.5


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
    status = "registration_required" if not tool_items else "registered_tools_present"
    return {
        "target": str(root),
        "ok": True,
        "workflow": PROJECT_ENVIRONMENT_WORKFLOW,
        "decision_policy": PROJECT_ENVIRONMENT_DECISION_POLICY,
        "environment_id": PROJECT_RUNTIME_ID,
        "contract_path": PROJECT_ENVIRONMENT_REL.as_posix(),
        "workflow_phase": phase,
        "phase_allows_registration": phase in PROJECT_ENVIRONMENT_ALLOWED_PHASES,
        "status": status,
        "tool_count": len(tool_items),
        "tools": tool_items,
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
            "status": status,
            "next_action": "review-stack-decision-and-register-tool",
            "stop_condition": "Do not register a project runtime tool without a local reviewed stack decision.",
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
        "errors": [],
    }


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
    return errors


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
        errors.append(f"{label}.strategy must be governance-env or manual")
        return
    expected_keys = {"strategy", "source", "tool"} if strategy == "governance-env" else {
        "strategy",
        "source",
        "instructions",
    }
    _check_keys(repair, expected_keys, label, errors)
    _validate_source(repair.get("source"), f"{label}.source", errors)
    if strategy == "governance-env":
        _validate_governance_repair(repair, executable, label, errors)
    else:
        _validate_manual_repair(repair, label, errors)


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
