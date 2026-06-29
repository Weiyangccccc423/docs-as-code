from __future__ import annotations

import argparse
import json
from pathlib import Path

from bootstrap_tree import InitPreflightError, bootstrap, preflight_init
from check_env import (
    ToolStatus,
    apply_install_plan,
    build_install_plan,
    collect_git_status,
    collect_status,
    collect_system_status,
    detect_package_manager,
    environment_ok,
    install_command_text,
    install_commands,
    missing_tools_by_level,
    write_repair_plan,
)
from gates import GATE_NAMES, evaluate_gate
from phases import PHASE_NAMES, advance_phase
from product_import import mark_product_import_ready
from scaffold import scaffold_design
from state import load_state, merge_state
from verify_governance import verify


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _tool_status_payload(statuses: list[ToolStatus]) -> list[dict[str, object]]:
    return [
        {
            "name": status.name,
            "present": status.present,
            "version": status.version,
            "note": status.note,
            "level": status.level,
            "install_package": status.install_package,
        }
        for status in statuses
    ]


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.target)
    product = Path(args.product) if args.product else None
    preflight = preflight_init(target, product, force=args.force)
    if args.check:
        if args.json:
            _print_json(preflight.to_dict())
        elif preflight.ok:
            print("Initialization preflight passed.")
        else:
            _print_init_conflicts(preflight.conflicts)
        return 0 if preflight.ok else 1
    if not preflight.ok:
        if args.json:
            _print_json(preflight.to_dict())
        else:
            _print_init_conflicts(preflight.conflicts)
        return 1
    try:
        bootstrap(
            target,
            product,
            force=args.force,
            profile=args.profile,
            project_name=args.project_name,
        )
    except InitPreflightError as error:
        if args.json:
            _print_json(error.result.to_dict())
        else:
            _print_init_conflicts(error.result.conflicts)
        return 1
    if args.json:
        payload = preflight_init(target, product, force=True).to_dict()
        payload["ok"] = True
        payload["conflicts"] = []
        payload["state"] = load_state(target)
        _print_json(payload)
        return 0
    print(f"Initialized governance repository at {target}")
    return 0


def _print_init_conflicts(conflicts: list) -> None:
    print("Initialization preflight failed:")
    for conflict in conflicts:
        print(f"- {conflict.path}: {conflict.reason}")


def _cmd_verify(args: argparse.Namespace) -> int:
    target = Path(args.target)
    report = verify(target)
    state = merge_state(
        target,
        last_verification={
            "ok": report.ok,
            "errors": report.errors,
            "warnings": report.warnings,
            "findings": [finding.to_dict() for finding in report.findings],
        },
    )
    if args.json:
        _print_json(
            {
                "ok": report.ok,
                "target": str(target),
                "errors": report.errors,
                "warnings": report.warnings,
                "findings": [finding.to_dict() for finding in report.findings],
                "state": state,
            }
        )
        return 0 if report.ok else 1
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
        if args.json:
            _print_json(
                {
                    "ok": False,
                    "target": str(target),
                    "error": "No governance state found.",
                }
            )
            return 1
        print("No governance state found.")
        return 1
    if args.json:
        _print_json(
            {
                "ok": True,
                "target": str(target),
                "state": state,
            }
        )
        return 0
    for key in ("phase", "profile", "project_name", "product_source", "updated_at"):
        if key in state:
            print(f"{key}: {state[key]}")
    last = state.get("last_verification")
    if isinstance(last, dict):
        print(f"last_verification.ok: {last.get('ok')}")
    return 0


def _cmd_env(args: argparse.Namespace) -> int:
    missing: list[str] = []
    statuses = collect_status()
    system = collect_system_status()
    package_manager = detect_package_manager(system)
    git = collect_git_status(Path(args.target))
    install_plan = build_install_plan(statuses, args.strict, package_manager)
    needs_escalation = bool(args.repair and install_plan and not system.is_root)
    install_results: list[dict[str, object]] = []
    for status in statuses:
        mark = "OK" if status.present else "MISSING"
        if not args.json:
            print(f"{mark:7} {status.name:10} {status.version or status.note}")
        if not status.present:
            missing.append(status.name)
    repair_plan = None
    repairs: list[dict[str, object]] = []
    if args.repair:
        install_results = apply_install_plan(install_plan, package_manager, system)
        if install_results and all(result["returncode"] == 0 for result in install_results):
            statuses = collect_status()
            missing = [status.name for status in statuses if not status.present]
        path = write_repair_plan(
            Path(args.target),
            statuses,
            system=system,
            package_manager=package_manager,
            install_plan=install_plan,
            needs_escalation=needs_escalation,
        )
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
            for result in install_results:
                print(f"Install command exited {result['returncode']}: {result['command']}")
    missing_required = missing_tools_by_level(statuses, "required")
    missing_recommended = missing_tools_by_level(statuses, "recommended")
    commands = install_commands(install_plan, package_manager)
    ok = environment_ok(statuses, args.strict)
    if args.json:
        _print_json(
            {
                "ok": ok,
                "target": str(Path(args.target)),
                "strict": args.strict,
                "missing": missing,
                "missing_required": missing_required,
                "missing_recommended": missing_recommended,
                "tools": _tool_status_payload(statuses),
                "system": system.to_dict(),
                "package_manager": package_manager.to_dict(),
                "git": git.to_dict(),
                "install_plan": [item.to_dict() for item in install_plan],
                "install_commands": commands,
                "install_command": install_command_text(commands),
                "needs_escalation": needs_escalation,
                "install_results": install_results,
                "repairs": repairs,
                "repair_plan": repair_plan,
            }
        )
    return 0 if ok else 1


def _cmd_gate(args: argparse.Namespace) -> int:
    target = Path(args.target)
    result = evaluate_gate(target, args.gate)
    if args.json:
        _print_json(result.to_dict())
        return 0 if result.ok else 1
    if result.ok:
        print(f"Gate passed: {args.gate}")
        return 0
    print(f"Gate failed: {args.gate}")
    for requirement in result.requirements:
        if not requirement.ok:
            suffix = f" ({requirement.path})" if requirement.path else ""
            print(f"- {requirement.code}: {requirement.message}{suffix}")
    return 1


def _cmd_scaffold(args: argparse.Namespace) -> int:
    target = Path(args.target)
    if args.scaffold == "design":
        result = scaffold_design(target)
    else:  # pragma: no cover - argparse choices prevent this
        raise ValueError(f"unknown scaffold: {args.scaffold}")
    payload = result.to_dict()
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if not result.ok:
        print(f"Scaffold failed: {args.scaffold}")
        for error in result.errors:
            print(f"- ERROR: {error}")
        return 1
    print(f"Scaffold created: {args.scaffold}")
    for path in result.created:
        print(f"- CREATED: {path}")
    for path in result.skipped:
        print(f"- SKIPPED: {path}")
    return 0


def _cmd_advance(args: argparse.Namespace) -> int:
    target = Path(args.target)
    result = advance_phase(target, args.phase)
    if args.json:
        _print_json(result.to_dict())
        return 0 if result.ok else 1
    if result.ok:
        print(f"Advanced phase: {args.phase}")
        return 0
    print(f"Advance failed: {args.phase}")
    for error in result.errors:
        print(f"- ERROR: {error}")
    for requirement in result.gate.get("requirements", []):
        if isinstance(requirement, dict) and not requirement.get("ok"):
            path = requirement.get("path")
            suffix = f" ({path})" if path else ""
            print(f"- {requirement.get('code')}: {requirement.get('message')}{suffix}")
    return 1


def _cmd_product_mark_ready(args: argparse.Namespace) -> int:
    target = Path(args.target)
    result = mark_product_import_ready(target, method=args.method, reviewed=args.reviewed)
    payload = result.to_dict()
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if not result.ok:
        print("Product import is not ready:")
        for error in result.errors:
            print(f"- ERROR: {error}")
        for warning in result.warnings:
            print(f"- WARN: {warning}")
        return 1
    print("Product import marked ready for structuring.")
    for path in result.updated:
        print(f"- UPDATED: {path}")
    for warning in result.warnings:
        print(f"- WARN: {warning}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="docs-as-code governance workflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize a target governance repository.")
    init.add_argument("--target", default=".")
    init.add_argument("--product")
    init.add_argument("--profile", default="unknown")
    init.add_argument("--project-name", default="Project Workspace")
    init.add_argument("--force", action="store_true")
    init.add_argument("--check", action="store_true", help="Run initialization preflight without writing files.")
    init.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    init.set_defaults(func=_cmd_init)

    verify_parser = sub.add_parser("verify", help="Verify governance consistency.")
    verify_parser.add_argument("target", nargs="?", default=".")
    verify_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    verify_parser.set_defaults(func=_cmd_verify)

    status = sub.add_parser("status", help="Show target governance workflow state.")
    status.add_argument("target", nargs="?", default=".")
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    status.set_defaults(func=_cmd_status)

    env = sub.add_parser("env", help="Check local workflow environment.")
    env.add_argument(
        "--strict",
        action="store_true",
        help="Also fail when recommended tools are missing; required tools always fail.",
    )
    env.add_argument("--repair", action="store_true")
    env.add_argument("--target", default=".")
    env.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    env.set_defaults(func=_cmd_env)

    gate = sub.add_parser("gate", help="Check whether a workflow phase gate can be entered.")
    gate.add_argument("gate", choices=GATE_NAMES)
    gate.add_argument("target", nargs="?", default=".")
    gate.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    gate.set_defaults(func=_cmd_gate)

    scaffold = sub.add_parser("scaffold", help="Create standard governance document scaffolds.")
    scaffold.add_argument("scaffold", choices=("design",))
    scaffold.add_argument("target", nargs="?", default=".")
    scaffold.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    scaffold.set_defaults(func=_cmd_scaffold)

    advance = sub.add_parser("advance", help="Advance workflow phase after the matching gate passes.")
    advance.add_argument("phase", choices=PHASE_NAMES)
    advance.add_argument("target", nargs="?", default=".")
    advance.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    advance.set_defaults(func=_cmd_advance)

    product = sub.add_parser("product", help="Manage product document import state.")
    product_sub = product.add_subparsers(dest="product_command", required=True)
    mark_ready = product_sub.add_parser("mark-ready", help="Mark a reviewed converted PRD ready for structuring.")
    mark_ready.add_argument("target", nargs="?", default=".")
    mark_ready.add_argument("--method", default="manual-reviewed-markdown")
    mark_ready.add_argument(
        "--reviewed",
        action="store_true",
        help="Confirm docs/product/core/PRD.md has reviewed Markdown content preserving source meaning.",
    )
    mark_ready.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    mark_ready.set_defaults(func=_cmd_product_mark_ready)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
