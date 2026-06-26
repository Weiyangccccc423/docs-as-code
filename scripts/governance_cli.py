from __future__ import annotations

import argparse
from pathlib import Path

from bootstrap_tree import bootstrap
from check_env import collect_status, write_repair_plan
from state import load_state, merge_state
from verify_governance import verify


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.target)
    product = Path(args.product) if args.product else None
    bootstrap(
        target,
        product,
        force=args.force,
        profile=args.profile,
        project_name=args.project_name,
    )
    print(f"Initialized governance repository at {target}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    target = Path(args.target)
    report = verify(target)
    merge_state(
        target,
        last_verification={
            "ok": report.ok,
            "errors": report.errors,
            "warnings": report.warnings,
        },
    )
    if report.ok:
        print("Governance verification passed.")
        return 0
    print("Governance verification failed:")
    for error in report.errors:
        print(f"- ERROR: {error}")
    for warning in report.warnings:
        print(f"- WARN: {warning}")
    return 1


def _cmd_status(args: argparse.Namespace) -> int:
    target = Path(args.target)
    state = load_state(target)
    if not state:
        print("No governance state found.")
        return 1
    for key in ("phase", "profile", "project_name", "product_source", "updated_at"):
        if key in state:
            print(f"{key}: {state[key]}")
    last = state.get("last_verification")
    if isinstance(last, dict):
        print(f"last_verification.ok: {last.get('ok')}")
    return 0


def _cmd_env(args: argparse.Namespace) -> int:
    missing: list[str] = []
    for status in collect_status():
        mark = "OK" if status.present else "MISSING"
        print(f"{mark:7} {status.name:10} {status.version or status.note}")
        if not status.present:
            missing.append(status.name)
    if args.repair:
        path = write_repair_plan(Path(args.target), collect_status())
        print(f"\nWrote repair plan: {path}")
    return 1 if args.strict and missing else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="docs-as-code governance workflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize a target governance repository.")
    init.add_argument("--target", default=".")
    init.add_argument("--product")
    init.add_argument("--profile", default="unknown")
    init.add_argument("--project-name", default="Project Workspace")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=_cmd_init)

    verify_parser = sub.add_parser("verify", help="Verify governance consistency.")
    verify_parser.add_argument("target", nargs="?", default=".")
    verify_parser.set_defaults(func=_cmd_verify)

    status = sub.add_parser("status", help="Show target governance workflow state.")
    status.add_argument("target", nargs="?", default=".")
    status.set_defaults(func=_cmd_status)

    env = sub.add_parser("env", help="Check local workflow environment.")
    env.add_argument("--strict", action="store_true")
    env.add_argument("--repair", action="store_true")
    env.add_argument("--target", default=".")
    env.set_defaults(func=_cmd_env)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
