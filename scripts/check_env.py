from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolSpec:
    name: str
    note: str
    level: str
    apt_package: str | None = None


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


@dataclass
class SystemStatus:
    platform: str
    os_id: str
    os_like: str
    pretty_name: str
    is_root: bool

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

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "package": self.package,
            "manager": self.manager,
        }


@dataclass
class GitStatus:
    installed: bool
    is_repo: bool
    branch: str
    user_name: str
    user_email: str

    def to_dict(self) -> dict[str, object]:
        return {
            "installed": self.installed,
            "is_repo": self.is_repo,
            "branch": self.branch,
            "user_name": self.user_name,
            "user_email": self.user_email,
        }


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
        result = subprocess.run(command, check=False, text=True, capture_output=True, timeout=300)
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


def repair_target_error(target: Path) -> str | None:
    if target.exists():
        if target.is_dir():
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
    needs_escalation: bool = False,
) -> Path:
    error = repair_target_error(target)
    if error:
        raise ValueError(error)
    missing = [status for status in statuses if not status.present]
    system = system or collect_system_status()
    package_manager = package_manager or detect_package_manager(system)
    install_plan = install_plan or []
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
            "- Install system tools with your OS package manager when required.",
            "- Install `node` and `corepack` with the target project's selected JavaScript runtime policy.",
            "- Install `lychee` before enforcing strict link checks.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    parser.add_argument("--target", default=".", help="Target directory for repair artifacts.")
    args = parser.parse_args()

    target = Path(args.target)
    missing: list[str] = []
    statuses = collect_status()
    system = collect_system_status()
    package_manager = detect_package_manager(system)
    install_plan = build_install_plan(statuses, args.strict, package_manager)
    needs_escalation = bool(args.repair and install_plan and not system.is_root)

    for status in statuses:
        mark = "OK" if status.present else "MISSING"
        print(f"{mark:7} {status.name:10} {status.version or status.note}")
        if not status.present:
            missing.append(status.name)

    if missing:
        print("\nRepair guidance:")
        print("- Install missing system tools with your OS package manager.")
        print("- `pandoc` and `lychee` are optional during early product archiving but required for strict docs CI.")
        print("- Re-run `python3 scripts/check_env.py --strict` before declaring the workflow environment ready.")
    if args.repair:
        target_error = repair_target_error(target)
        if target_error:
            print(f"ERROR: {target_error}")
            return 1
        install_results = apply_install_plan(install_plan, package_manager, system)
        if install_results and all(result["returncode"] == 0 for result in install_results):
            statuses = collect_status()
            missing = [status.name for status in statuses if not status.present]
        path = write_repair_plan(
            target,
            statuses,
            system=system,
            package_manager=package_manager,
            install_plan=install_plan,
            needs_escalation=needs_escalation,
        )
        print(f"\nWrote repair plan: {path}")
        if needs_escalation:
            print(
                "Installation requires root approval: "
                f"{install_command_text(install_commands(install_plan, package_manager))}"
            )
        for result in install_results:
            print(f"Install command exited {result['returncode']}: {result['command']}")
    return 0 if environment_ok(statuses, args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
