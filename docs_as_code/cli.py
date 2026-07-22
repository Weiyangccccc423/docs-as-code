from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator, Sequence

from .packaging import MANIFEST_NAME, build_embedded_pack


PRODUCT_SUFFIXES = ".md, .markdown, .txt, .docx, .pdf, .html, .htm"
PACK_MARKERS = (
    "VERSION",
    "scripts/bootstrap_consumer_project.py",
    "scripts/governance_cli.py",
    "workflows/00-overview.md",
)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    payload: dict[str, Any] | None
    stdout: str
    stderr: str


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
            "getting started:\n"
            "  1. Create or enter a project directory.\n"
            "  2. Put exactly one product document in the project root.\n"
            "  3. Run dac init --check, then run dac init.\n"
            "  4. Run dac next to inspect the next workflow action.\n\n"
            "safe operation:\n"
            "  Commands using --check are read-only previews.\n"
            "  Commands using --json return the complete agent contract.\n\n"
            "examples:\n"
            "  dac init\n"
            "  dac init /path/to/product.pdf\n"
            "  dac status\n"
            "  dac next\n"
            "  dac -C /path/to/project verify --check\n\n"
            "help:\n"
            "  dac help\n"
            "  dac help init\n"
            "  dac help <command>\n"
            "  dac COMMAND --help"
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
        epilog=(
            "examples:\n"
            "  dac doctor\n"
            "  dac doctor --strict\n"
            "  dac doctor --repair\n"
            "  dac doctor --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor.add_argument(
        "--repair",
        action="store_true",
        help="Apply only supported repairs that require no additional approval.",
    )
    doctor.add_argument("--strict", action="store_true", help="Also require recommended tools.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["doctor"] = doctor

    status = subparsers.add_parser(
        "status",
        help="Show the current governance phase and state.",
        description="Show a concise project, phase, product, and verification summary.",
        epilog="examples:\n  dac status\n  dac status --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["status"] = status

    next_command = subparsers.add_parser(
        "next",
        help="Describe the next evidence-backed workflow action.",
        description="Select and summarize one snapshot-bound next action without executing it.",
        epilog="examples:\n  dac next\n  dac next --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    next_command.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["next"] = next_command

    verify = subparsers.add_parser(
        "verify",
        help="Verify governance documents and runtime integrity.",
        description="Verify generated governance structure, evidence, and runtime integrity.",
        epilog=(
            "examples:\n"
            "  dac verify --check\n"
            "  dac verify\n"
            "  dac verify --check --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    verify.add_argument("--check", action="store_true", help="Verify without updating state.")
    verify.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["verify"] = verify

    upgrade = subparsers.add_parser(
        "upgrade",
        help="Refresh the target-local workflow runtime.",
        description="Preview or apply a manifest-checked refresh of managed target-local runtime files.",
        epilog=(
            "examples:\n"
            "  dac upgrade --check\n"
            "  dac upgrade\n"
            "  dac upgrade --check --json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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


@contextmanager
def _prepared_pack_root() -> Iterator[Path]:
    root = _pack_root()
    if (root / MANIFEST_NAME).is_file():
        yield root
        return

    source_root = Path(__file__).resolve().parents[1]
    if root != source_root:
        raise RuntimeError("installed docs-as-code workflow manifest is missing")

    with tempfile.TemporaryDirectory(prefix="docs-as-code-source-pack-") as tmp:
        prepared = Path(tmp) / "pack"
        build_embedded_pack(source_root, prepared)
        yield prepared


def _script_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["DOCS_AS_CODE_PYTHON"] = sys.executable
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _run_python_script(script: Path, argv: Sequence[str], *, cwd: Path) -> int:
    try:
        completed = subprocess.run(
            [sys.executable, str(script), *argv],
            cwd=cwd,
            env=_script_environment(),
            check=False,
        )
    except OSError as error:
        print(f"dac: failed to start {script.name}: {error}", file=sys.stderr)
        return 2
    return completed.returncode


def _run_python_json(script: Path, argv: Sequence[str], *, cwd: Path) -> CommandResult:
    command = list(argv)
    if "--json" not in command:
        command.append("--json")
    try:
        completed = subprocess.run(
            [sys.executable, str(script), *command],
            cwd=cwd,
            env=_script_environment(),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return CommandResult(2, None, "", f"failed to start {script.name}: {error}")

    payload: dict[str, Any] | None = None
    try:
        decoded = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        decoded = None
    if isinstance(decoded, dict):
        payload = decoded
    return CommandResult(completed.returncode, payload, completed.stdout, completed.stderr)


def _run_pack_command(argv: Sequence[str]) -> int:
    try:
        pack_context = _prepared_pack_root()
    except RuntimeError as error:
        print(f"dac: {error}", file=sys.stderr)
        return 2
    if not argv:
        print("dac: internal error: missing workflow script", file=sys.stderr)
        return 2
    try:
        with pack_context as root:
            script = root / argv[0]
            if not script.is_file():
                print(f"dac: installed workflow script is missing: {argv[0]}", file=sys.stderr)
                return 2
            return _run_python_script(script, argv[1:], cwd=root)
    except RuntimeError as error:
        print(f"dac: {error}", file=sys.stderr)
        return 2


def _run_pack_json(argv: Sequence[str]) -> CommandResult:
    if not argv:
        return CommandResult(2, None, "", "internal error: missing workflow script")
    try:
        with _prepared_pack_root() as root:
            script = root / argv[0]
            if not script.is_file():
                return CommandResult(2, None, "", f"installed workflow script is missing: {argv[0]}")
            return _run_python_json(script, argv[1:], cwd=root)
    except RuntimeError as error:
        return CommandResult(2, None, "", str(error))


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


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _display_path(value: object, target: Path) -> str:
    if not isinstance(value, str) or not value:
        return "not selected"
    path = Path(value)
    try:
        return path.resolve().relative_to(target.resolve()).as_posix()
    except (OSError, ValueError):
        return value


def _error_messages(payload: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    error = payload.get("error")
    if isinstance(error, str) and error:
        messages.append(error)
    for value in _items(payload.get("errors")):
        if isinstance(value, str) and value and value not in messages:
            messages.append(value)
    for source in (payload, _dict(payload.get("failed_payload"))):
        nested_error = source.get("error")
        if isinstance(nested_error, str) and nested_error and nested_error not in messages:
            messages.append(nested_error)
        for value in _items(source.get("errors")):
            if isinstance(value, str) and value and value not in messages:
                messages.append(value)
        init_check = _dict(source.get("init_check")) or source
        for conflict in _items(init_check.get("conflicts")):
            conflict_data = _dict(conflict)
            path = conflict_data.get("path")
            reason = conflict_data.get("reason")
            if isinstance(reason, str) and reason:
                message = f"{path}: {reason}" if isinstance(path, str) and path else reason
                if message not in messages:
                    messages.append(message)
    return messages


def _render_failure(label: str, result: CommandResult, *, help_command: str) -> int:
    payload = result.payload
    if payload is None:
        print(f"dac: {label} returned invalid machine output.", file=sys.stderr)
        detail = result.stderr.strip() or result.stdout.strip()
        if detail:
            print(f"dac: {detail.splitlines()[0]}", file=sys.stderr)
        print(f"dac: details: {help_command}", file=sys.stderr)
        return result.returncode or 2

    print(f"{label} failed:", file=sys.stderr)
    messages = _error_messages(payload)
    if not messages:
        messages = [f"command exited with status {result.returncode}"]
    for message in messages[:8]:
        print(f"- {message}", file=sys.stderr)
    print(f"Details: {help_command}", file=sys.stderr)
    return result.returncode or 1


def _result_ok(result: CommandResult) -> bool:
    return result.returncode == 0 and result.payload is not None and result.payload.get("ok") is True


def _emit_json_result(result: CommandResult) -> int:
    if result.payload is not None:
        print(json.dumps(result.payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    return result.returncode


def _require_cli_product(result: CommandResult) -> CommandResult:
    payload = result.payload
    if payload is None or payload.get("ok") is not True:
        return result
    init_check = _dict(payload.get("init_check"))
    product = _dict(init_check.get("product"))
    selection = product.get("selection")
    path = product.get("path")
    if selection in {"explicit", "auto-discovered"} and isinstance(path, str) and path:
        return result
    if selection != "none":
        return result
    failed = dict(payload)
    failed.update(
        {
            "ok": False,
            "error": (
                "dac requires exactly one product document in the project root; "
                "add one or run dac init PRODUCT"
            ),
            "errors": [
                "dac requires exactly one product document in the project root; "
                "add one or run dac init PRODUCT"
            ],
            "failed_step": "cli_product_selection",
            "writes_state": False,
        }
    )
    return CommandResult(1, failed, "", result.stderr)


def _bind_cli_preflight(result: CommandResult, preflight: CommandResult) -> CommandResult:
    if result.payload is None or preflight.payload is None:
        return result
    product = _dict(_dict(preflight.payload.get("init_check")).get("product"))
    payload = dict(result.payload)
    payload["cli_preflight"] = {
        "product": dict(product),
        "writes_state": False,
    }
    return CommandResult(result.returncode, payload, result.stdout, result.stderr)


def _render_init(payload: dict[str, Any], *, target: Path, check: bool) -> None:
    stage = _dict(payload.get("init_check" if check else "init"))
    product = _dict(_dict(payload.get("cli_preflight")).get("product")) or _dict(stage.get("product"))
    selection = product.get("selection") if isinstance(product.get("selection"), str) else "unknown"
    product_path = _display_path(product.get("path"), target)
    if check:
        print(f"Ready to initialize: {target}")
        print(f"Product: {product_path} ({selection})")
        print(f"Files to create: {len(_items(stage.get('would_write')))}")
        print("Run without --check to initialize.")
        return

    state = _dict(stage.get("state"))
    phase = state.get("phase") if isinstance(state.get("phase"), str) else "initialized"
    archived = state.get("archived_product")
    print(f"Initialized: {target}")
    print(f"Product: {product_path} ({selection})")
    if isinstance(archived, str) and archived:
        print(f"Archived as: {archived}")
    print(f"Phase: {phase}")
    print("Next: dac next")


def _render_status(payload: dict[str, Any], *, target: Path) -> None:
    state = _dict(payload.get("state"))
    project = state.get("project_name")
    phase = state.get("phase")
    product = _display_path(state.get("product_source"), target)
    product_status = state.get("product_import_status")
    if isinstance(project, str) and project:
        print(f"Project: {project}")
    if isinstance(phase, str) and phase:
        print(f"Phase: {phase}")
    print(f"Product: {product}")
    if isinstance(product_status, str) and product_status:
        print(f"Product status: {product_status}")
    last_verification = _dict(state.get("last_verification"))
    if last_verification:
        print(f"Last verification: {'passed' if last_verification.get('ok') is True else 'failed'}")
    print("Next: dac next")


def _action_skills(action: dict[str, Any]) -> list[str]:
    skills: list[str] = []
    sources = [action, *(_dict(step) for step in _items(action.get("steps")))]
    for source in sources:
        for skill in _items(source.get("skills")):
            if isinstance(skill, str) and skill and skill not in skills:
                skills.append(skill)
    return skills


def _render_next(payload: dict[str, Any]) -> None:
    phase = payload.get("phase")
    status = payload.get("status")
    action = _dict(payload.get("selected_action"))
    if isinstance(phase, str) and phase:
        print(f"Phase: {phase}")
    if isinstance(status, str) and status:
        print(f"Workflow status: {status}")
    if not action:
        print("Next action: none")
        return
    action_id = action.get("id") or action.get("kind") or "unknown"
    print(f"Next action: {action_id}")
    description = action.get("description")
    if isinstance(description, str) and description:
        summary = description[0].upper() + description[1:]
        print(f"Summary: {summary}")
    skills = _action_skills(action)
    if skills:
        print(f"Skills: {', '.join(skills)}")
    print(f"Writes state: {'yes' if action.get('writes_state') is True else 'no'}")
    print("Agent details: dac next --json")


def _render_verify(payload: dict[str, Any], *, check: bool) -> None:
    print("Governance verification passed.")
    print(f"Mode: {'read-only' if check else 'state updated'}")
    state = _dict(payload.get("state"))
    phase = state.get("phase")
    if isinstance(phase, str) and phase:
        print(f"Phase: {phase}")
    print("Next: dac next")


def _render_doctor(payload: dict[str, Any]) -> None:
    tools = [_dict(tool) for tool in _items(payload.get("tools"))]
    required = [tool for tool in tools if tool.get("level") == "required"]
    required_present = sum(tool.get("present") is True for tool in required)
    missing_recommended = [
        str(tool.get("name"))
        for tool in tools
        if tool.get("level") == "recommended" and tool.get("present") is not True and tool.get("name")
    ]
    print("Environment ready.")
    print(f"Required tools: {required_present}/{len(required)} available")
    if missing_recommended:
        print(f"Optional tools missing: {', '.join(missing_recommended)}")
    else:
        print("Optional tools: all available")
    decision = _dict(payload.get("repair_decision"))
    if decision.get("decision") == "run_repair_actions":
        print("Repair available: dac doctor --repair")
    print("Details: dac doctor --json")


def _render_upgrade(payload: dict[str, Any], *, check: bool) -> None:
    transition = _dict(payload.get("version_transition"))
    from_version = transition.get("from_version") or "not recorded"
    to_version = transition.get("to_version") or "unknown"
    classification = transition.get("classification") or "unknown"
    if check:
        print("Runtime upgrade check passed.")
        print(f"Version: {from_version} -> {to_version} ({classification})")
        print(f"Files to refresh: {len(_items(payload.get('would_refresh')))}")
        print(f"Files to remove: {len(_items(payload.get('would_remove')))}")
        print("Run: dac upgrade")
        return
    print("Runtime upgraded.")
    print(f"Version: {from_version} -> {to_version} ({classification})")
    print(f"Files refreshed: {len(_items(payload.get('refreshed')))}")
    print(f"Files removed: {len(_items(payload.get('removed')))}")
    print("Next: dac verify --check")


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
    if args.check:
        argv.append("--check")
        if args.json:
            argv.append("--json")
        result = _require_cli_product(_run_pack_json(argv))
        if args.json:
            return _emit_json_result(result)
        if not _result_ok(result):
            return _render_failure("Initialization", result, help_command="dac init --check --json")
        assert result.payload is not None
        _render_init(result.payload, target=target, check=True)
        return 0

    preflight = _require_cli_product(_run_pack_json([*argv, "--check"]))
    if not _result_ok(preflight):
        if args.json:
            return _emit_json_result(preflight)
        return _render_failure("Initialization", preflight, help_command="dac init --check --json")

    apply_argv = list(argv)
    if not args.product:
        init_check = _dict(_dict(preflight.payload).get("init_check"))
        selected = _dict(init_check.get("product")).get("path")
        if isinstance(selected, str) and selected:
            apply_argv.extend(("--product", selected))
    if args.json:
        apply_argv.append("--json")

    result = _bind_cli_preflight(_run_pack_json(apply_argv), preflight)
    if args.json:
        return _emit_json_result(result)
    if not _result_ok(result):
        return _render_failure("Initialization", result, help_command="dac init --check --json")
    assert result.payload is not None
    _render_init(result.payload, target=target, check=False)
    return 0


def _run_doctor(args: argparse.Namespace, target: Path) -> int:
    argv = ["scripts/governance_cli.py", "env", "--repair", "--target", str(target)]
    if not args.repair:
        argv.append("--check")
    _append_flag(argv, args.strict, "--strict")
    if args.json:
        argv.append("--json")
        return _run_pack_command(argv)
    result = _run_pack_json(argv)
    if not _result_ok(result):
        return _render_failure("Environment check", result, help_command="dac doctor --json")
    assert result.payload is not None
    _render_doctor(result.payload)
    return 0


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
    if args.json:
        argv.append("--json")
        return _run_python_script(runtime, argv, cwd=target)
    result = _run_python_json(runtime, argv, cwd=target)
    if not _result_ok(result):
        detail_commands = {
            "status": "dac status --json",
            "next": "dac next --json",
            "verify": "dac verify --check --json",
        }
        return _render_failure(args.command.capitalize(), result, help_command=detail_commands[args.command])
    assert result.payload is not None
    if args.command == "status":
        _render_status(result.payload, target=target)
    elif args.command == "next":
        _render_next(result.payload)
    else:
        _render_verify(result.payload, check=args.check)
    return 0


def _run_upgrade(args: argparse.Namespace, target: Path) -> int:
    if _target_runtime(target) is None:
        return 2
    argv = ["scripts/governance_cli.py", "runtime", "refresh", str(target)]
    _append_flag(argv, args.check, "--check")
    if args.json:
        argv.append("--json")
        return _run_pack_command(argv)
    result = _run_pack_json(argv)
    if not _result_ok(result):
        return _render_failure("Runtime upgrade", result, help_command="dac upgrade --check --json")
    assert result.payload is not None
    _render_upgrade(result.payload, check=args.check)
    return 0


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
