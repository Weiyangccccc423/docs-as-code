from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / "bin/governance"
VERSION = ROOT / "docs/agent-workflow/workflow-pack/VERSION"
OPERATIONAL_COMMANDS = ("status", "next", "verify", "doctor", "init", "upgrade")


class DacArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)
        self._dac_argument_tokens: tuple[str, ...] = ()

    def parse_args(
        self,
        args: Sequence[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> argparse.Namespace:
        self._dac_argument_tokens = tuple(sys.argv[1:] if args is None else args)
        return super().parse_args(args, namespace)

    def _help_command(self) -> str:
        if self.prog == "dac":
            for token in self._dac_argument_tokens:
                if token in OPERATIONAL_COMMANDS:
                    return f"dac {token} --help"
            return "dac help"
        if self.prog == "dac help":
            return "dac help"
        return f"{self.prog} --help"

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(
            2,
            f"{self.prog}: error: {message}\n"
            f"Try '{self._help_command()}' for more information.\n",
        )


def _version() -> str:
    try:
        value = VERSION.read_text(encoding="utf-8").strip()
    except OSError:
        return "target-runtime"
    return value or "target-runtime"


def build_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    parser = DacArgumentParser(
        prog="dac",
        description="Operate an initialized governed project with its generated runtime.",
        epilog=(
            "examples:\n"
            "  dac status\n"
            "  dac next\n"
            "  dac verify --check\n"
            "  dac doctor\n"
            "  dac help status\n"
            "  dac help <command>\n"
            "  dac COMMAND --help\n\n"
            "project binding:\n"
            "  This command always operates on the generated project that contains bin/dac,\n"
            "  including when invoked from one of that project's subdirectories.\n\n"
            "source-pack boundary:\n"
            "  dac init, dac upgrade, and dac next --apply require the source workflow pack\n"
            "  or an installed dac command. Use --json for machine-readable output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands: dict[str, argparse.ArgumentParser] = {}

    status = subparsers.add_parser(
        "status",
        help="Show the current workflow phase and verification state.",
        description="Show the current project, workflow phase, product, and verification state.",
        epilog="examples:\n  dac status\n  dac status --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["status"] = status

    next_command = subparsers.add_parser(
        "next",
        help="Show the next evidence-backed workflow action.",
        description="Show one snapshot-bound next action without executing it.",
        epilog="examples:\n  dac next\n  dac next --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    next_command.add_argument(
        "--apply",
        action="store_true",
        help="Requires the source workflow pack because generated targets omit the workflow executor.",
    )
    next_command.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["next"] = next_command

    verify = subparsers.add_parser(
        "verify",
        help="Verify governance documents and runtime integrity.",
        description="Verify governance documents and runtime integrity.",
        epilog="examples:\n  dac verify --check\n  dac verify --check --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    verify.add_argument("--check", action="store_true", help="Verify without updating state.")
    verify.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["verify"] = verify

    doctor = subparsers.add_parser(
        "doctor",
        help="Inspect the project environment and repair route.",
        description="Inspect required tools and the project environment repair route.",
        epilog="examples:\n  dac doctor\n  dac doctor --repair\n  dac doctor --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor.add_argument("--repair", action="store_true", help="Apply supported environment repairs.")
    doctor.add_argument("--strict", action="store_true", help="Also require recommended tools.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["doctor"] = doctor

    init = subparsers.add_parser(
        "init",
        help="Explain the trusted source-pack initialization boundary.",
        description=(
            "Initialization requires the source workflow pack or an installed dac command. "
            "Generated projects do not carry the initializer."
        ),
        epilog="examples:\n  dac init --help\n  dac init product.md --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init.add_argument("product", nargs="?", metavar="PRODUCT")
    init.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["init"] = init

    upgrade = subparsers.add_parser(
        "upgrade",
        help="Explain the trusted source-pack runtime refresh boundary.",
        description=(
            "Runtime refresh requires the source workflow pack or an installed dac command so "
            "source artifact integrity can be verified."
        ),
        epilog="examples:\n  dac upgrade --help\n  dac upgrade --check --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    upgrade.add_argument("--check", action="store_true", help="Request a read-only source-pack preview.")
    upgrade.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands["upgrade"] = upgrade

    help_command = subparsers.add_parser("help", help="Show this help or help for one command.")
    help_command.add_argument("topic", nargs="?", choices=tuple(commands), metavar="COMMAND")
    commands["help"] = help_command
    return parser, commands


def _failure(error_code: str, message: str, *, json_requested: bool) -> int:
    if json_requested:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_code": error_code,
                    "error": message,
                    "can_continue": False,
                    "writes_state": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(f"dac: {message}", file=sys.stderr)
        print('Run "dac help" for the generated-project command guide.', file=sys.stderr)
    return 2


def _exec_governance(argv: list[str], *, json_requested: bool) -> int:
    if not GOVERNANCE.is_file():
        return _failure(
            "dac_governance_runtime_missing",
            "generated project governance runtime is missing",
            json_requested=json_requested,
        )
    try:
        os.execv(str(GOVERNANCE), [str(GOVERNANCE), *argv])
    except OSError as error:
        return _failure(
            "dac_governance_runtime_unavailable",
            f"failed to start generated project governance runtime: {error}",
            json_requested=json_requested,
        )
    return 2


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

    json_requested = bool(getattr(args, "json", False))
    if args.command == "init":
        return _failure(
            "dac_target_init_unavailable",
            "generated-project dac init requires the source workflow pack or an installed dac command",
            json_requested=json_requested,
        )
    if args.command == "upgrade":
        return _failure(
            "dac_target_upgrade_requires_source_pack",
            "generated-project dac upgrade requires the source workflow pack or an installed dac command",
            json_requested=json_requested,
        )
    if args.command == "next" and args.apply:
        return _failure(
            "dac_target_apply_unavailable",
            "generated-project dac next --apply requires the source workflow pack; complete the selected work manually and run dac next again",
            json_requested=json_requested,
        )

    target = str(ROOT)
    if args.command == "status":
        command = ["status", target]
    elif args.command == "next":
        command = ["workflow", "resume", target]
    elif args.command == "verify":
        command = ["verify", target]
        if args.check:
            command.append("--check")
    else:
        command = ["env", "--repair"]
        if not args.repair:
            command.append("--check")
        if args.strict:
            command.append("--strict")
        command.extend(("--target", target))
    if json_requested:
        command.append("--json")
    return _exec_governance(command, json_requested=json_requested)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
