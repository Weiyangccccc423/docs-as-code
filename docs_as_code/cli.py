from __future__ import annotations

import argparse
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


PRODUCT_SUFFIXES = ".md, .markdown, .txt, .docx, .pdf, .html, .htm"
PACK_MARKERS = (
    "VERSION",
    "scripts/bootstrap_consumer_project.py",
    "scripts/governance_cli.py",
    "workflows/00-overview.md",
)


def _version() -> str:
    try:
        return importlib.metadata.version("docs-as-code-workflow-pack")
    except importlib.metadata.PackageNotFoundError:
        version_file = Path(__file__).resolve().parents[1] / "VERSION"
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"


def build_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    parser = argparse.ArgumentParser(
        prog="dac",
        description="Initialize and operate a governed docs-as-code project from one product document.",
        epilog=(
            "examples:\n"
            "  dac init\n"
            "  dac init /path/to/product.pdf\n"
            "  dac status\n"
            "  dac next\n\n"
            'Run "dac help <command>" for details.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-C",
        "--directory",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help="Operate on DIR instead of the current project directory.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands: dict[str, argparse.ArgumentParser] = {}

    init = subparsers.add_parser(
        "init",
        help="Initialize the current project from one product document.",
        description=(
            "Initialize a governed project. When PRODUCT is omitted, dac discovers exactly one supported "
            f"product document in the project root ({PRODUCT_SUFFIXES})."
        ),
        epilog=(
            "examples:\n"
            "  dac init\n"
            "  dac init product.md\n"
            "  dac init /path/to/product.pdf\n"
            "  dac init --check --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init.add_argument(
        "product",
        nargs="?",
        metavar="PRODUCT",
        help="Product document path; defaults to unique project-root discovery.",
    )
    init.add_argument("--profile", help="Optional project profile recorded in governance state.")
    init.add_argument("--project-name", help="Optional project name; defaults to the directory name.")
    init.add_argument("--force", action="store_true", help="Replace existing generated governance files.")
    init.add_argument("--check", action="store_true", help="Preview initialization without writing files.")
    init.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["init"] = init

    doctor = subparsers.add_parser(
        "doctor",
        help="Inspect the workflow environment and repair route.",
        description="Inspect required tools and produce a safe environment repair plan.",
    )
    doctor.add_argument(
        "--repair",
        action="store_true",
        help="Apply only supported repairs that require no additional approval.",
    )
    doctor.add_argument("--strict", action="store_true", help="Also require recommended tools.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["doctor"] = doctor

    status = subparsers.add_parser("status", help="Show the current governance phase and state.")
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["status"] = status

    next_command = subparsers.add_parser(
        "next",
        help="Select the next evidence-backed workflow action.",
    )
    next_command.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["next"] = next_command

    verify = subparsers.add_parser("verify", help="Verify governance documents and runtime integrity.")
    verify.add_argument("--check", action="store_true", help="Verify without updating state.")
    verify.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["verify"] = verify

    upgrade = subparsers.add_parser("upgrade", help="Refresh the target-local workflow runtime.")
    upgrade.add_argument("--check", action="store_true", help="Preview the refresh without writing files.")
    upgrade.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["upgrade"] = upgrade

    help_command = subparsers.add_parser("help", help="Show help for dac or one command.")
    help_command.add_argument("topic", nargs="?", choices=tuple(commands), metavar="COMMAND")
    commands["help"] = help_command
    return parser, commands


def _pack_root() -> Path:
    override = os.environ.get("DOCS_AS_CODE_PACK_ROOT")
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.extend(
        (
            Path(__file__).resolve().parent / "pack",
            Path(__file__).resolve().parents[1],
        )
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if all((resolved / marker).is_file() for marker in PACK_MARKERS):
            return resolved
    raise RuntimeError("installed docs-as-code workflow resources are missing or incomplete")


def _run_python_script(script: Path, argv: Sequence[str], *, cwd: Path) -> int:
    environment = os.environ.copy()
    environment["DOCS_AS_CODE_PYTHON"] = sys.executable
    try:
        completed = subprocess.run(
            [sys.executable, str(script), *argv],
            cwd=cwd,
            env=environment,
            check=False,
        )
    except OSError as error:
        print(f"dac: failed to start {script.name}: {error}", file=sys.stderr)
        return 2
    return completed.returncode


def _run_pack_command(argv: Sequence[str]) -> int:
    try:
        root = _pack_root()
    except RuntimeError as error:
        print(f"dac: {error}", file=sys.stderr)
        return 2
    if not argv:
        print("dac: internal error: missing workflow script", file=sys.stderr)
        return 2
    script = root / argv[0]
    if not script.is_file():
        print(f"dac: installed workflow script is missing: {argv[0]}", file=sys.stderr)
        return 2
    return _run_python_script(script, argv[1:], cwd=root)


def _target_runtime(target: Path) -> Path | None:
    runtime = target / "scripts/governance_cli.py"
    if runtime.is_file():
        return runtime
    print(
        f"dac: project is not initialized: {target}\n"
        "Place one product document in the project root and run 'dac init'.",
        file=sys.stderr,
    )
    return None


def _append_flag(argv: list[str], enabled: bool, flag: str) -> None:
    if enabled:
        argv.append(flag)


def _run_init(args: argparse.Namespace, target: Path) -> int:
    argv = [
        "scripts/bootstrap_consumer_project.py",
        "--auto-repair-env",
        "--target",
        str(target),
    ]
    if args.product:
        product = Path(args.product).expanduser()
        if not product.is_absolute():
            product = target / product
        argv.extend(("--product", str(product.resolve())))
    if args.profile:
        argv.extend(("--profile", args.profile))
    if args.project_name:
        argv.extend(("--project-name", args.project_name))
    _append_flag(argv, args.force, "--force")
    _append_flag(argv, args.check, "--check")
    _append_flag(argv, args.json, "--json")
    return _run_pack_command(argv)


def _run_doctor(args: argparse.Namespace, target: Path) -> int:
    argv = ["scripts/governance_cli.py", "env", "--repair", "--target", str(target)]
    if not args.repair:
        argv.append("--check")
    _append_flag(argv, args.strict, "--strict")
    _append_flag(argv, args.json, "--json")
    return _run_pack_command(argv)


def _run_target_command(args: argparse.Namespace, target: Path) -> int:
    runtime = _target_runtime(target)
    if runtime is None:
        return 2
    commands = {
        "status": ["status", "."],
        "next": ["workflow", "resume", "."],
        "verify": ["verify", "."],
    }
    argv = list(commands[args.command])
    if args.command == "verify":
        _append_flag(argv, args.check, "--check")
    _append_flag(argv, args.json, "--json")
    return _run_python_script(runtime, argv, cwd=target)


def _run_upgrade(args: argparse.Namespace, target: Path) -> int:
    if _target_runtime(target) is None:
        return 2
    argv = ["scripts/governance_cli.py", "runtime", "refresh", str(target)]
    _append_flag(argv, args.check, "--check")
    _append_flag(argv, args.json, "--json")
    return _run_pack_command(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parser, commands = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "help":
        if args.topic:
            commands[args.topic].print_help()
        else:
            parser.print_help()
        return 0

    target = args.directory.expanduser().resolve()
    if args.command == "init":
        return _run_init(args, target)
    if args.command == "doctor":
        return _run_doctor(args, target)
    if args.command in {"status", "next", "verify"}:
        return _run_target_command(args, target)
    if args.command == "upgrade":
        return _run_upgrade(args, target)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
