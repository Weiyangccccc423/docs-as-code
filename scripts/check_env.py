from __future__ import annotations

import argparse
import copy
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    from .bootstrap_tree import target_local_commands_payload
    from .state import StateFileError, load_state
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from state import StateFileError, load_state
    from workflow_actions import next_actions_payload


@dataclass(frozen=True)
class ToolSpec:
    name: str
    note: str
    level: str
    apt_package: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("tool spec name must be a non-empty string")
        if not isinstance(self.note, str) or not self.note:
            raise ValueError("tool spec note must be a non-empty string")
        if self.level not in TOOL_LEVELS:
            raise ValueError("tool spec level must be required or recommended")
        if self.apt_package is not None and (not isinstance(self.apt_package, str) or not self.apt_package):
            raise ValueError("tool spec apt_package must be a non-empty string or null")


TOOL_LEVELS = {"required", "recommended"}
TOOLS = [
    ToolSpec("git", "Required for version control and change evidence.", "required", "git"),
    ToolSpec("rg", "Recommended for fast repository search.", "recommended", "ripgrep"),
    ToolSpec("python3", "Required for workflow-pack scripts.", "required", "python3"),
    ToolSpec("node", "Recommended for frontend projects and markdown tooling.", "recommended", None),
    ToolSpec("corepack", "Recommended for pnpm-managed frontend projects.", "recommended", None),
    ToolSpec("pandoc", "Recommended for converting docx/html product documents to Markdown.", "recommended", "pandoc"),
    ToolSpec("lychee", "Recommended for link verification.", "recommended", None),
]


@dataclass
class ToolStatus:
    name: str
    present: bool
    version: str
    note: str
    level: str
    install_package: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.name, "tool status name")
        _require_bool(self.present, "tool status present")
        _require_string(self.version, "tool status version")
        _require_non_empty_string(self.note, "tool status note")
        if self.level not in TOOL_LEVELS:
            raise ValueError("tool status level must be required or recommended")
        _require_nullable_non_empty_string(self.install_package, "tool status install_package")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "present": self.present,
            "version": self.version,
            "note": self.note,
            "level": self.level,
            "install_package": self.install_package,
        }


@dataclass
class SystemStatus:
    platform: str
    os_id: str
    os_like: str
    pretty_name: str
    is_root: bool

    def __post_init__(self) -> None:
        _require_string(self.platform, "system status platform")
        _require_string(self.os_id, "system status os_id")
        _require_string(self.os_like, "system status os_like")
        _require_non_empty_string(self.pretty_name, "system status pretty_name")
        _require_bool(self.is_root, "system status is_root")

    def to_dict(self) -> dict[str, object]:
        return {
            "platform": self.platform,
            "os_id": self.os_id,
            "os_like": self.os_like,
            "pretty_name": self.pretty_name,
            "is_root": self.is_root,
        }


@dataclass
class PackageManager:
    name: str
    command: str | None
    supported: bool

    def __post_init__(self) -> None:
        _require_non_empty_string(self.name, "package manager name")
        _require_nullable_non_empty_string(self.command, "package manager command")
        _require_bool(self.supported, "package manager supported")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "supported": self.supported,
        }


@dataclass
class InstallPlanItem:
    tool: str
    package: str
    manager: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.tool, "install plan item tool")
        _require_non_empty_string(self.package, "install plan item package")
        _require_non_empty_string(self.manager, "install plan item manager")

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "package": self.package,
            "manager": self.manager,
        }


@dataclass
class ManualRepairItem:
    tool: str
    level: str
    note: str
    reason: str
    package_manager: str
    install_package: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.tool, "manual repair item tool")
        if self.level not in TOOL_LEVELS:
            raise ValueError("manual repair item level must be required or recommended")
        _require_non_empty_string(self.note, "manual repair item note")
        _require_non_empty_string(self.reason, "manual repair item reason")
        _require_non_empty_string(self.package_manager, "manual repair item package_manager")
        _require_nullable_non_empty_string(self.install_package, "manual repair item install_package")

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "level": self.level,
            "note": self.note,
            "reason": self.reason,
            "package_manager": self.package_manager,
            "install_package": self.install_package,
        }


@dataclass
class GitStatus:
    installed: bool
    is_repo: bool
    branch: str
    user_name: str
    user_email: str

    def __post_init__(self) -> None:
        _require_bool(self.installed, "git status installed")
        _require_bool(self.is_repo, "git status is_repo")
        _require_string(self.branch, "git status branch")
        _require_string(self.user_name, "git status user_name")
        _require_string(self.user_email, "git status user_email")

    def to_dict(self) -> dict[str, object]:
        return {
            "installed": self.installed,
            "is_repo": self.is_repo,
            "branch": self.branch,
            "user_name": self.user_name,
            "user_email": self.user_email,
        }


def _require_string(value: object, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")


def _require_non_empty_string(value: object, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _require_nullable_non_empty_string(value: object, label: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"{label} must be a non-empty string or null")


def _require_bool(value: object, label: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")


def _validate_tool_specs(specs: object) -> None:
    if not isinstance(specs, list):
        raise ValueError("tool specs must be a list")
    if not all(isinstance(spec, ToolSpec) for spec in specs):
        raise ValueError("tool specs must contain ToolSpec entries")
    names = [spec.name for spec in specs]
    if len(names) != len(set(names)):
        raise ValueError("tool specs must use unique tool names")


_validate_tool_specs(TOOLS)


def collect_status() -> list[ToolStatus]:
    statuses: list[ToolStatus] = []
    for spec in TOOLS:
        path = shutil.which(spec.name)
        version = _version(spec.name) if path else ""
        statuses.append(ToolStatus(spec.name, bool(path), version, spec.note, spec.level, spec.apt_package))
    return statuses


def collect_system_status() -> SystemStatus:
    os_release = _read_os_release()
    is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    return SystemStatus(
        platform=platform.system().lower(),
        os_id=os_release.get("ID", ""),
        os_like=os_release.get("ID_LIKE", ""),
        pretty_name=os_release.get("PRETTY_NAME", platform.platform()),
        is_root=is_root,
    )


def detect_package_manager(system: SystemStatus | None = None) -> PackageManager:
    system = system or collect_system_status()
    apt = shutil.which("apt-get")
    if apt and (system.os_id in {"ubuntu", "debian"} or "debian" in system.os_like):
        return PackageManager("apt", apt, True)
    for name in ("brew", "dnf", "yum", "pacman"):
        command = shutil.which(name)
        if command:
            return PackageManager(name, command, False)
    return PackageManager("unknown", None, False)


def collect_git_status(target: Path) -> GitStatus:
    installed = shutil.which("git") is not None
    if not installed:
        return GitStatus(False, False, "", "", "")
    is_repo = _git(target, "rev-parse", "--is-inside-work-tree") == "true"
    branch = _git(target, "branch", "--show-current") if is_repo else ""
    user_name = _git(target, "config", "--get", "user.name") if is_repo else ""
    user_email = _git(target, "config", "--get", "user.email") if is_repo else ""
    return GitStatus(installed, is_repo, branch, user_name, user_email)


def build_install_plan(
    statuses: list[ToolStatus],
    strict: bool,
    package_manager: PackageManager,
) -> list[InstallPlanItem]:
    if package_manager.name != "apt" or not package_manager.supported:
        return []
    items: list[InstallPlanItem] = []
    for status in statuses:
        if status.present or not status.install_package:
            continue
        if status.level == "required" or strict:
            items.append(InstallPlanItem(status.name, status.install_package, package_manager.name))
    return items


def missing_tools_by_level(statuses: list[ToolStatus], level: str) -> list[str]:
    return [status.name for status in statuses if not status.present and status.level == level]


def environment_ok(statuses: list[ToolStatus], strict: bool) -> bool:
    if missing_tools_by_level(statuses, "required"):
        return False
    return not (strict and missing_tools_by_level(statuses, "recommended"))


def install_commands(plan: list[InstallPlanItem], package_manager: PackageManager) -> list[list[str]]:
    if not plan or package_manager.name != "apt" or not package_manager.command:
        return []
    packages = sorted({item.package for item in plan})
    return [
        [package_manager.command, "update"],
        [package_manager.command, "install", "-y", *packages],
    ]


def install_command_text(commands: list[list[str]]) -> str:
    return " && ".join(" ".join(command) for command in commands)


def repair_commands(
    target: Path,
    install_plan: list[InstallPlanItem],
    package_manager: PackageManager,
    *,
    needs_escalation: bool,
) -> list[dict[str, object]]:
    commands = install_commands(install_plan, package_manager)
    if not commands:
        return []
    cwd = str(target.resolve())
    items: list[dict[str, object]] = []
    for command in commands:
        command_id = "env-repair-package-manager"
        description = "run governance environment package-manager repair command"
        if package_manager.name == "apt" and command[1:] == ["update"]:
            command_id = "env-repair-apt-update"
            description = "refresh apt package indexes for governance environment repair"
        elif package_manager.name == "apt" and len(command) >= 4 and command[1:3] == ["install", "-y"]:
            packages = " ".join(command[3:])
            command_id = "env-repair-apt-install"
            description = f"install supported governance environment packages: {packages}"
        items.append(
            {
                "id": command_id,
                "kind": "package-manager",
                "cwd": cwd,
                "command": " ".join(command),
                "argv": list(command),
                "writes_state": True,
                "approval_required": needs_escalation,
                "description": description,
            }
        )
    return items


def repair_execution_summary(
    statuses: list[ToolStatus],
    strict: bool,
    repair_command_items: list[dict[str, object]],
    manual_repairs: list[ManualRepairItem],
    *,
    needs_escalation: bool,
    install_results: list[dict[str, object]],
    errors: list[str] | None = None,
) -> dict[str, object]:
    command_ids = [str(item.get("id", "")) for item in repair_command_items if item.get("id")]
    manual_tools = [item.tool for item in manual_repairs]
    approval_required = needs_escalation or any(
        item.get("approval_required") is True for item in repair_command_items
    )
    install_attempted = bool(install_results)
    install_failed = any(result.get("returncode") != 0 for result in install_results)
    env_ok = environment_ok(statuses, strict)
    error_list = list(errors or [])
    status = "continue"
    can_continue = True
    can_auto_apply = False
    next_step = "continue workflow"
    if error_list:
        status = "blocked_by_error"
        can_continue = False
        next_step = "fix reported environment repair error"
    elif install_failed:
        status = "install_failed"
        can_continue = False
        next_step = "inspect install_results and repair package-manager failure"
    elif install_attempted and env_ok:
        status = "applied"
        next_step = "rerun governance env or continue workflow"
    elif manual_repairs:
        status = "manual_repair_required"
        can_continue = False
        next_step = "complete manual_repairs before continuing"
    elif approval_required and repair_command_items:
        status = "approval_required"
        can_continue = False
        next_step = "request approval before running repair_commands"
    elif repair_command_items:
        status = "ready_to_apply"
        can_continue = False
        can_auto_apply = True
        next_step = "run repair_commands[].argv from repair_commands[].cwd"
    elif not env_ok:
        status = "unresolved"
        can_continue = False
        next_step = "inspect missing tools and manual repair policy"
    return {
        "status": status,
        "can_continue": can_continue,
        "can_auto_apply": can_auto_apply,
        "approval_required": approval_required,
        "manual_repair_required": bool(manual_repairs),
        "command_ids": command_ids,
        "manual_tools": manual_tools,
        "next_step": next_step,
    }


def repair_actions_payload(
    repair_command_items: list[dict[str, object]],
    manual_repairs: list[ManualRepairItem],
    *,
    install_results: list[dict[str, object]],
    errors: list[str],
) -> list[dict[str, object]]:
    if errors or any(result.get("returncode") != 0 for result in install_results):
        return []

    actions: list[dict[str, object]] = []
    sequence = 1
    for item in repair_command_items:
        action = copy.deepcopy(item)
        action["sequence"] = sequence
        action["source"] = "repair_commands"
        action["success_condition"] = "returncode:0"
        actions.append(action)
        sequence += 1

    for item in manual_repairs:
        actions.append(
            {
                "id": f"env-manual-repair-{item.tool}",
                "kind": "manual-repair",
                "sequence": sequence,
                "tool": item.tool,
                "level": item.level,
                "note": item.note,
                "reason": item.reason,
                "package_manager": item.package_manager,
                "install_package": item.install_package,
                "writes_state": True,
                "approval_required": True,
                "source": "manual_repairs",
                "success_condition": f"tool_present:{item.tool}",
                "description": f"manually install or enable governance environment tool: {item.tool}",
            }
        )
        sequence += 1

    return actions


def manual_repair_items(
    statuses: list[ToolStatus],
    strict: bool,
    package_manager: PackageManager,
    install_plan: list[InstallPlanItem],
) -> list[ManualRepairItem]:
    planned_tools = {item.tool for item in install_plan}
    items: list[ManualRepairItem] = []
    for status in statuses:
        if status.present or status.name in planned_tools:
            continue
        if status.level == "recommended" and not strict:
            continue
        items.append(
            ManualRepairItem(
                status.name,
                status.level,
                status.note,
                _manual_repair_reason(status, package_manager),
                package_manager.name,
                status.install_package,
            )
        )
    return items


def _manual_repair_reason(status: ToolStatus, package_manager: PackageManager) -> str:
    if not status.install_package:
        return "no supported package mapping"
    if not package_manager.supported:
        return f"unsupported package manager: {package_manager.name}"
    if package_manager.name != "apt":
        return f"unsupported package manager: {package_manager.name}"
    return "not included in automatic install plan"


def manual_repair_lines(items: list[ManualRepairItem]) -> list[str]:
    return [
        f"- `{item.tool}` ({item.level}): {item.reason}"
        + (f"; package `{item.install_package}`" if item.install_package else "")
        + f". {item.note}"
        for item in items
    ]


def apply_install_plan(
    plan: list[InstallPlanItem],
    package_manager: PackageManager,
    system: SystemStatus,
) -> list[dict[str, object]]:
    commands = install_commands(plan, package_manager)
    if not commands or not system.is_root:
        return []
    results: list[dict[str, object]] = []
    for command in commands:
        try:
            result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=300)
        except subprocess.TimeoutExpired as error:
            results.append(_failed_install_result(command, 124, f"timed out after {error.timeout} seconds"))
            break
        except OSError as error:
            reason = error.strerror or str(error)
            results.append(_failed_install_result(command, 127, reason))
            break
        results.append(
            {
                "command": " ".join(command),
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }
        )
        if result.returncode != 0:
            break
    return results


def _failed_install_result(command: list[str], returncode: int, stderr: str) -> dict[str, object]:
    return {
        "command": " ".join(command),
        "returncode": returncode,
        "stdout": "",
        "stderr": stderr[-2000:],
    }


def _tool_status_payload(statuses: list[ToolStatus]) -> list[dict[str, object]]:
    return [status.to_dict() for status in statuses]


def _env_payload(
    target: Path,
    *,
    strict: bool,
    check: bool = False,
    statuses: list[ToolStatus],
    system: SystemStatus,
    package_manager: PackageManager,
    git: GitStatus,
    install_plan: list[InstallPlanItem],
    needs_escalation: bool,
    install_results: list[dict[str, object]],
    repairs: list[dict[str, object]],
    repair_plan: str | None,
    would_repair: list[dict[str, object]] | None = None,
    errors: list[str] | None = None,
) -> dict[str, object]:
    commands = install_commands(install_plan, package_manager)
    manual_repairs = manual_repair_items(statuses, strict, package_manager, install_plan)
    repair_command_items = repair_commands(
        target,
        install_plan,
        package_manager,
        needs_escalation=needs_escalation,
    )
    error_list = list(errors or [])
    payload: dict[str, object] = {
        "ok": environment_ok(statuses, strict) and not error_list,
        "target": str(target),
        "strict": strict,
        "check": check,
        "missing": [status.name for status in statuses if not status.present],
        "missing_required": missing_tools_by_level(statuses, "required"),
        "missing_recommended": missing_tools_by_level(statuses, "recommended"),
        "tools": _tool_status_payload(statuses),
        "system": system.to_dict(),
        "package_manager": package_manager.to_dict(),
        "git": git.to_dict(),
        "install_plan": [item.to_dict() for item in install_plan],
        "install_commands": commands,
        "install_command": install_command_text(commands),
        "repair_commands": repair_command_items,
        "manual_repairs": [item.to_dict() for item in manual_repairs],
        "repair_actions": repair_actions_payload(
            repair_command_items,
            manual_repairs,
            install_results=install_results,
            errors=error_list,
        ),
        "repair_execution": repair_execution_summary(
            statuses,
            strict,
            repair_command_items,
            manual_repairs,
            needs_escalation=needs_escalation,
            install_results=install_results,
            errors=error_list,
        ),
        "needs_escalation": needs_escalation,
        "install_results": copy.deepcopy(install_results),
        "repairs": copy.deepcopy(repairs),
        "repair_plan": repair_plan,
        "would_repair": copy.deepcopy(would_repair or []),
        "errors": error_list,
    }
    payload.update(env_continuation_payload(target, payload))
    return payload


def env_continuation_payload(target: Path, payload: dict[str, object]) -> dict[str, object]:
    if payload.get("ok") is not True:
        return {}
    try:
        state = load_state(target)
    except (OSError, StateFileError):
        return {}
    if not state:
        return {}
    cwd = str(target.resolve())
    return {
        "local_commands": target_local_commands_payload(cwd=cwd),
        "next_actions": next_actions_payload(state, cwd=cwd),
    }


def planned_repair_actions(target: Path) -> list[dict[str, object]]:
    repair_plan = target / ".governance/env-repair.md"
    return [
        {"kind": "directory", "path": str(repair_plan.parent), "status": "would_ensure"},
        {"kind": "repair_plan", "path": str(repair_plan), "status": "would_write"},
    ]


def repair_target_error(target: Path) -> str | None:
    if target.exists():
        if target.is_dir():
            governance_dir = target / ".governance"
            if governance_dir.exists() and not governance_dir.is_dir():
                return f"environment repair output parent is not a directory: {governance_dir}"
            repair_plan = governance_dir / "env-repair.md"
            if repair_plan.exists() and not repair_plan.is_file():
                return f"environment repair plan path is not a file: {repair_plan}"
            repair_plan_temp = _atomic_temp_path(repair_plan)
            if repair_plan_temp.exists() and not repair_plan_temp.is_file():
                return f"environment repair plan temp path is not a file: {repair_plan_temp}"
            return None
        return f"environment repair target is not a directory: {target}"
    for ancestor in target.parents:
        if not ancestor.exists():
            continue
        if not ancestor.is_dir():
            return f"environment repair target parent is not a directory: {ancestor}"
        return None
    return None


def write_repair_plan(
    target: Path,
    statuses: list[ToolStatus],
    *,
    system: SystemStatus | None = None,
    package_manager: PackageManager | None = None,
    install_plan: list[InstallPlanItem] | None = None,
    strict: bool = False,
    needs_escalation: bool = False,
) -> Path:
    error = repair_target_error(target)
    if error:
        raise ValueError(error)
    missing = [status for status in statuses if not status.present]
    system = system or collect_system_status()
    package_manager = package_manager or detect_package_manager(system)
    install_plan = install_plan or []
    manual_repairs = manual_repair_items(statuses, strict, package_manager, install_plan)
    path = target / ".governance/env-repair.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Environment Repair Plan",
        "",
        "This file is generated by `scripts/check_env.py --repair`.",
        "",
        "## Missing Tools",
        "",
    ]
    if missing:
        for status in missing:
            lines.append(f"- `{status.name}` ({status.level}): {status.note}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## System",
            "",
            f"- OS: {system.pretty_name}",
            f"- Package manager: {package_manager.name}",
            f"- Running as root: {system.is_root}",
            "",
            "## Safe Local Repairs",
            "",
            "- `.governance/` directory exists.",
            "- No global configuration was changed.",
            "",
            "## Install Plan",
            "",
        ]
    )
    if install_plan:
        packages = " ".join(sorted({item.package for item in install_plan}))
        commands = install_commands(install_plan, package_manager)
        lines.append(f"- Supported packages: `{packages}`")
        if needs_escalation:
            lines.append(
                f"- Requires approval/root execution: `{install_command_text(commands)}`"
            )
        else:
            lines.append("- Installation can be attempted because this process is running as root.")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Manual Repairs",
            "",
        ]
    )
    if manual_repairs:
        lines.extend(manual_repair_lines(manual_repairs))
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Manual Guidance",
            "",
            "- Install system tools with your OS package manager when required.",
            "- Install `node` and `corepack` with the target project's selected JavaScript runtime policy.",
            "- Install `lychee` before enforcing strict link checks.",
        ]
    )
    _write_atomic_text(path, "\n".join(lines) + "\n")
    return path


def _write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _atomic_temp_path(path)
    try:
        temp.write_text(content, encoding="utf-8")
        temp.replace(path)
    except OSError:
        if temp.exists() and temp.is_file():
            try:
                temp.unlink()
            except OSError:
                pass
        raise


def _atomic_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def _version(tool: str) -> str:
    candidates = ([tool, "--version"], [tool, "-V"])
    for cmd in candidates:
        try:
            result = subprocess.run(cmd, check=False, text=True, capture_output=True, timeout=5)
        except Exception:
            continue
        output = (result.stdout or result.stderr).strip().splitlines()
        if output:
            return output[0][:120]
    return "installed"


def _read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _git(target: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(target), *args],
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local tools used by the governance workflow pack.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also return non-zero when recommended tools are missing; required tools always block.",
    )
    parser.add_argument("--repair", action="store_true", help="Write a local environment repair plan.")
    parser.add_argument("--check", action="store_true", help="Preview repair actions without writing files or installing packages.")
    parser.add_argument("--target", default=".", help="Target directory for repair artifacts.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable environment report.")
    args = parser.parse_args()

    target = Path(args.target)
    missing: list[str] = []
    statuses = collect_status()
    system = collect_system_status()
    package_manager = detect_package_manager(system)
    git = collect_git_status(target)
    install_plan = build_install_plan(statuses, args.strict, package_manager)
    manual_repairs = manual_repair_items(statuses, args.strict, package_manager, install_plan)
    needs_escalation = bool(args.repair and install_plan and not system.is_root)
    install_results: list[dict[str, object]] = []
    repair_plan = None
    repairs: list[dict[str, object]] = []

    for status in statuses:
        mark = "OK" if status.present else "MISSING"
        if not args.json:
            print(f"{mark:7} {status.name:10} {status.version or status.note}")
        if not status.present:
            missing.append(status.name)

    if missing and not args.json:
        print("\nRepair guidance:")
        print("- Install missing system tools with your OS package manager.")
        print("- `pandoc` and `lychee` are optional during early product archiving but required for strict docs CI.")
        print("- Re-run `python3 scripts/check_env.py --strict` before declaring the workflow environment ready.")
    if args.repair:
        target_error = repair_target_error(target)
        if target_error:
            if args.json:
                print(
                    json.dumps(
                        _env_payload(
                            target,
                            strict=args.strict,
                            check=args.check,
                            statuses=statuses,
                            system=system,
                            package_manager=package_manager,
                            git=git,
                            install_plan=install_plan,
                            needs_escalation=needs_escalation,
                            install_results=install_results,
                            repairs=repairs,
                            repair_plan=repair_plan,
                            errors=[target_error],
                        ),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(f"ERROR: {target_error}")
            return 1
        if args.check:
            would_repair = planned_repair_actions(target)
            if args.json:
                print(
                    json.dumps(
                        _env_payload(
                            target,
                            strict=args.strict,
                            check=True,
                            statuses=statuses,
                            system=system,
                            package_manager=package_manager,
                            git=git,
                            install_plan=install_plan,
                            needs_escalation=needs_escalation,
                            install_results=install_results,
                            repairs=repairs,
                            repair_plan=repair_plan,
                            would_repair=would_repair,
                        ),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print("\nEnvironment repair preflight:")
                for item in would_repair:
                    print(f"- {item['status']}: {item['path']}")
                if needs_escalation:
                    print(
                        "Installation requires root approval: "
                        f"{install_command_text(install_commands(install_plan, package_manager))}"
                    )
                if manual_repairs:
                    print("Manual repairs required:")
                    for line in manual_repair_lines(manual_repairs):
                        print(line)
            return 0 if environment_ok(statuses, args.strict) else 1
        install_results = apply_install_plan(install_plan, package_manager, system)
        if install_results and all(result["returncode"] == 0 for result in install_results):
            statuses = collect_status()
            missing = [status.name for status in statuses if not status.present]
            manual_repairs = manual_repair_items(statuses, args.strict, package_manager, install_plan)
        try:
            path = write_repair_plan(
                target,
                statuses,
                system=system,
                package_manager=package_manager,
                install_plan=install_plan,
                strict=args.strict,
                needs_escalation=needs_escalation,
            )
        except (OSError, ValueError) as error:
            reason = error.strerror if isinstance(error, OSError) and error.strerror else str(error)
            repair_error = f"environment repair failed: {reason}"
            if args.json:
                print(
                    json.dumps(
                        _env_payload(
                            target,
                            strict=args.strict,
                            check=args.check,
                            statuses=statuses,
                            system=system,
                            package_manager=package_manager,
                            git=git,
                            install_plan=install_plan,
                            needs_escalation=needs_escalation,
                            install_results=install_results,
                            repairs=repairs,
                            repair_plan=repair_plan,
                            errors=[repair_error],
                        ),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(f"ERROR: {repair_error}")
            return 1
        repair_plan = str(path)
        repairs.append({"kind": "directory", "path": str(path.parent), "status": "ensured"})
        repairs.append({"kind": "repair_plan", "path": repair_plan, "status": "written"})
        if not args.json:
            print(f"\nWrote repair plan: {path}")
            if needs_escalation:
                print(
                    "Installation requires root approval: "
                    f"{install_command_text(install_commands(install_plan, package_manager))}"
                )
            if manual_repairs:
                print("Manual repairs required:")
                for line in manual_repair_lines(manual_repairs):
                    print(line)
            for result in install_results:
                print(f"Install command exited {result['returncode']}: {result['command']}")
    if args.json:
        print(
            json.dumps(
                _env_payload(
                    target,
                    strict=args.strict,
                    check=args.check,
                    statuses=statuses,
                    system=system,
                    package_manager=package_manager,
                    git=git,
                    install_plan=install_plan,
                    needs_escalation=needs_escalation,
                    install_results=install_results,
                    repairs=repairs,
                    repair_plan=repair_plan,
                ),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    return 0 if environment_ok(statuses, args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
