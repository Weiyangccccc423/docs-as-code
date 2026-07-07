from __future__ import annotations

import argparse
import json
from pathlib import Path

from bootstrap_tree import (
    InitPreflightError,
    bootstrap,
    check_runtime_refresh,
    preflight_init,
    refresh_runtime,
    target_local_commands_payload,
)
from check_env import (
    _env_payload as build_env_payload,
    apply_install_plan,
    build_install_plan,
    collect_git_status,
    collect_status,
    collect_system_status,
    detect_package_manager,
    environment_ok,
    install_command_text,
    install_commands,
    manual_repair_items,
    manual_repair_lines,
    planned_repair_actions,
    repair_target_error,
    write_repair_plan,
)
from design_plan import (
    build_api_authoring,
    build_api_candidates,
    build_architecture_decisions_authoring,
    build_backend_authoring,
    build_design_plan,
    build_frontend_authoring,
    build_implementation_planning_authoring,
    build_test_strategy_authoring,
)
from gates import GATE_NAMES, evaluate_gate
from phases import PHASE_NAMES, advance_phase, check_advance_phase
from product_import import check_product_import_ready, mark_product_import_ready
from product_structure import check_structure_product, structure_product
from scaffold import (
    PRODUCT_CHAPTER_CHOICES,
    ScaffoldResult,
    check_scaffold_design,
    check_scaffold_product,
    scaffold_design,
    scaffold_continuation_payload,
    scaffold_product,
)
from state import STATE_REL, StateFileError, load_state, merge_state, utc_now
from verify_governance import verify
from workflow_actions import next_actions_payload


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


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
    except (OSError, StateFileError) as error:
        message = _init_error_message(error)
        if args.json:
            payload = preflight.to_dict()
            payload["ok"] = False
            payload["errors"] = [message]
            _print_json(payload)
        else:
            print("Initialization failed:")
            print(f"- {message}")
        return 1
    if args.json:
        payload = preflight_init(target, product, force=True).to_dict()
        payload["ok"] = True
        payload["conflicts"] = []
        payload["state"] = load_state(target)
        payload["local_commands"] = target_local_commands_payload(cwd=str(target.resolve()))
        payload["next_actions"] = next_actions_payload(payload["state"], cwd=str(target.resolve()))
        _print_json(payload)
        return 0
    print(f"Initialized governance repository at {target}")
    return 0


def _print_init_conflicts(conflicts: list) -> None:
    print("Initialization preflight failed:")
    for conflict in conflicts:
        print(f"- {conflict.path}: {conflict.reason}")


def _init_error_message(error: OSError | StateFileError) -> str:
    if isinstance(error, OSError):
        reason = error.strerror or str(error)
    else:
        reason = str(error)
    return f"initialization failed: {reason}"


def _cmd_verify(args: argparse.Namespace) -> int:
    target = Path(args.target)
    report = verify(target)
    report_payload = report.to_dict()
    state = {}
    state_error = ""
    state_error_action = ""
    state_error_path = ""
    state_updated = False
    if target.exists() and not target.is_dir() and not args.check:
        error = StateFileError(target / STATE_REL, "unwritable: target path is not a directory")
        state_error = str(error)
        state_error_action = "update"
        state_error_path = str(error.path)
    elif (target / STATE_REL).exists() and args.check:
        try:
            state = load_state(target)
        except StateFileError as error:
            state_error = str(error)
            state_error_action = "read"
            state_error_path = str(error.path)
    elif (target / STATE_REL).exists():
        try:
            checked_at = utc_now()
            state = merge_state(
                target,
                last_verification={
                    "checked_at": checked_at,
                    **report_payload,
                },
            )
            state_updated = True
        except StateFileError as error:
            state_error = str(error)
            state_error_action = "update"
            state_error_path = str(error.path)
            try:
                state = load_state(target)
            except StateFileError:
                state = {}
    errors = list(report.errors)
    if state_error:
        errors.append(f"failed to {state_error_action} verification state: {state_error}")
    ok = report.ok and not state_error
    if args.json:
        payload = {
            **report_payload,
            "ok": ok,
            "target": str(target),
            "check": args.check,
            "state_updated": state_updated,
            "errors": errors,
            "state": state,
        }
        if state_error:
            payload["state_error"] = state_error
            payload["error"] = state_error
            payload["path"] = state_error_path
        elif state:
            cwd = str(target.resolve())
            payload["local_commands"] = target_local_commands_payload(cwd=cwd)
            payload["next_actions"] = next_actions_payload(state, cwd=cwd)
        _print_json(payload)
        return 0 if ok else 1
    if ok:
        print("Governance verification passed.")
        return 0
    print("Governance verification failed:")
    for error in errors:
        print(f"- ERROR: {error}")
    for warning in report.warnings:
        print(f"- WARN: {warning}")
    return 1


def _cmd_status(args: argparse.Namespace) -> int:
    target = Path(args.target)
    try:
        state = load_state(target)
    except StateFileError as error:
        if args.json:
            _print_json(
                {
                    "ok": False,
                    "target": str(target),
                    "error": str(error),
                    "errors": [str(error)],
                    "path": str(error.path),
                    "state": {},
                }
            )
        else:
            print(f"State file error: {error}")
        return 1
    if not state:
        if args.json:
            _print_json(
                {
                    "ok": False,
                    "target": str(target),
                    "error": "No governance state found.",
                    "errors": ["No governance state found."],
                    "state": {},
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
                "local_commands": target_local_commands_payload(cwd=str(target.resolve())),
                "next_actions": next_actions_payload(state, cwd=str(target.resolve())),
            }
        )
        return 0
    for key in (
        "phase",
        "profile",
        "project_name",
        "product_source",
        "archived_product",
        "product_import_status",
        "product_can_derive_design",
        "updated_at",
    ):
        if key in state:
            print(f"{key}: {state[key]}")
    last = state.get("last_verification")
    if isinstance(last, dict):
        print(f"last_verification.ok: {last.get('ok')}")
    return 0


def _cmd_env(args: argparse.Namespace) -> int:
    target = Path(args.target)
    check = bool(getattr(args, "check", False))
    statuses = collect_status()
    system = collect_system_status()
    package_manager = detect_package_manager(system)
    git = collect_git_status(target)
    install_plan = build_install_plan(statuses, args.strict, package_manager)
    manual_repairs = manual_repair_items(statuses, args.strict, package_manager, install_plan)
    needs_escalation = bool(args.repair and install_plan and not system.is_root)
    install_results: list[dict[str, object]] = []
    for status in statuses:
        mark = "OK" if status.present else "MISSING"
        if not args.json:
            print(f"{mark:7} {status.name:10} {status.version or status.note}")
    repair_plan = None
    repairs: list[dict[str, object]] = []
    if args.repair:
        target_error = repair_target_error(target)
        if target_error:
            if args.json:
                _print_json(
                    build_env_payload(
                        target,
                        strict=args.strict,
                        check=check,
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
                    )
                )
            else:
                print("Environment repair failed:")
                print(f"- ERROR: {target_error}")
            return 1
        if check:
            would_repair = planned_repair_actions(target)
            if args.json:
                _print_json(
                    build_env_payload(
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
                _print_json(
                    build_env_payload(
                        target,
                        strict=args.strict,
                        check=check,
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
                    )
                )
            else:
                print("Environment repair failed:")
                print(f"- ERROR: {repair_error}")
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
    ok = environment_ok(statuses, args.strict)
    if args.json:
        _print_json(
            build_env_payload(
                target,
                strict=args.strict,
                check=check,
                statuses=statuses,
                system=system,
                package_manager=package_manager,
                git=git,
                install_plan=install_plan,
                needs_escalation=needs_escalation,
                install_results=install_results,
                repairs=repairs,
                repair_plan=repair_plan,
            )
        )
    return 0 if ok else 1


def _cmd_runtime_refresh(args: argparse.Namespace) -> int:
    target = Path(args.target)
    result = check_runtime_refresh(target) if args.check else refresh_runtime(target)
    payload = result.to_dict()
    if result.ok and not args.check and result.state:
        payload["local_commands"] = target_local_commands_payload(cwd=result.target)
        payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if not result.ok:
        print("Runtime refresh preflight failed:" if args.check else "Runtime refresh failed:")
        for error in result.errors:
            print(f"- ERROR: {error}")
        return 1
    if args.check:
        print("Runtime refresh preflight passed.")
        for path in result.would_refresh:
            print(f"- WOULD REFRESH: {path}")
        for path in result.would_remove:
            print(f"- WOULD REMOVE: {path}")
        return 0
    print(f"Runtime refreshed: {target}")
    for path in result.refreshed:
        print(f"- REFRESHED: {path}")
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    target = Path(args.target)
    result = evaluate_gate(target, args.gate)
    if args.json:
        payload = result.to_dict()
        if result.state:
            payload["local_commands"] = target_local_commands_payload(cwd=result.target)
            if result.ok:
                payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
        _print_json(payload)
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
    if args.scaffold != "product" and args.chapter:
        result = ScaffoldResult(
            scaffold=args.scaffold,
            target=str(target),
            ok=False,
            check=args.check,
            errors=[f"scaffold {args.scaffold} does not accept --chapter"],
            gate={},
        )
        if args.json:
            _print_json(result.to_dict())
            return 1
        print(f"Scaffold failed: {args.scaffold}")
        for error in result.errors:
            print(f"- ERROR: {error}")
        return 1
    if args.scaffold == "design":
        result = check_scaffold_design(target) if args.check else scaffold_design(target)
    elif args.scaffold == "product":
        result = check_scaffold_product(target, args.chapter) if args.check else scaffold_product(target, args.chapter)
    else:  # pragma: no cover - argparse choices prevent this
        raise ValueError(f"unknown scaffold: {args.scaffold}")
    payload = result.to_dict()
    payload.update(scaffold_continuation_payload(result))
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if not result.ok:
        print(f"Scaffold failed: {args.scaffold}")
        for error in result.errors:
            print(f"- ERROR: {error}")
        return 1
    if args.check:
        print(f"Scaffold preflight passed: {args.scaffold}")
        for path in result.would_create:
            print(f"- WOULD CREATE: {path}")
        for path in result.would_skip:
            print(f"- WOULD SKIP: {path}")
        for path in result.would_index:
            print(f"- WOULD INDEX: {path}")
        return 0
    print(f"Scaffold created: {args.scaffold}")
    for path in result.created:
        print(f"- CREATED: {path}")
    for path in result.skipped:
        print(f"- SKIPPED: {path}")
    return 0


def _cmd_advance(args: argparse.Namespace) -> int:
    target = Path(args.target)
    if args.check:
        result = check_advance_phase(target, args.phase)
    else:
        result = advance_phase(target, args.phase)
    if args.json:
        payload = result.to_dict()
        if result.ok and result.advanced and not args.check:
            payload["local_commands"] = target_local_commands_payload(cwd=result.target)
            payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
        _print_json(payload)
        return 0 if result.ok else 1
    if args.check and result.ok:
        print(f"Advance preflight passed: {args.phase}")
        return 0
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
    if args.check:
        result = check_product_import_ready(target, method=args.method, reviewed=args.reviewed)
    else:
        result = mark_product_import_ready(target, method=args.method, reviewed=args.reviewed)
    payload = result.to_dict()
    if result.ok and not args.check:
        payload["local_commands"] = target_local_commands_payload(cwd=result.target)
        payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if not result.ok:
        print("Product import readiness preflight failed:" if args.check else "Product import is not ready:")
        for error in result.errors:
            print(f"- ERROR: {error}")
        for warning in result.warnings:
            print(f"- WARN: {warning}")
        return 1
    if args.check:
        print("Product import readiness preflight passed.")
        for path in result.would_update:
            print(f"- WOULD UPDATE: {path}")
        for warning in result.warnings:
            print(f"- WARN: {warning}")
        return 0
    print("Product import marked ready for structuring.")
    for path in result.updated:
        print(f"- UPDATED: {path}")
    for warning in result.warnings:
        print(f"- WARN: {warning}")
    return 0


def _cmd_product_structure(args: argparse.Namespace) -> int:
    target = Path(args.target)
    result = check_structure_product(target, args.chapter) if args.check else structure_product(target, args.chapter)
    payload = result.to_dict()
    if result.ok and not args.check and result.state:
        cwd = result.target
        payload["local_commands"] = target_local_commands_payload(cwd=cwd)
        payload["next_actions"] = next_actions_payload(result.state, cwd=cwd)
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if not result.ok:
        print("Product structure failed:")
        for error in result.errors:
            print(f"- ERROR: {error}")
        for warning in result.warnings:
            print(f"- WARN: {warning}")
        return 1
    if args.check:
        print("Product structure preflight passed.")
        for path in result.would_update:
            print(f"- WOULD UPDATE: {path}")
        for warning in result.warnings:
            print(f"- WARN: {warning}")
        return 0
    print("Product structure updated.")
    for path in result.updated:
        print(f"- UPDATED: {path}")
    for warning in result.warnings:
        print(f"- WARN: {warning}")
    return 0


def _cmd_design_plan(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_design_plan(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("Design plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print(f"Design plan: {payload['phase']}")
    for track in payload["tracks"]:
        print(f"- {track['id']}: {track['status']}")
    return 0


def _cmd_design_api_candidates(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_api_candidates(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("API candidate extraction failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("API candidates:")
    for candidate in payload["candidates"]:
        print(f"- {candidate['candidate_id']}: {candidate['acceptance_id']} -> {candidate['suggested_endpoint_file']}")
    return 0


def _cmd_design_api_authoring(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_api_authoring(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("API authoring plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("API authoring tasks:")
    for task in payload["authoring_tasks"]:
        print(f"- {task['task_id']}: {task['acceptance_id']} -> {task['endpoint_file']}")
    return 0


def _cmd_design_backend_authoring(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_backend_authoring(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("Backend authoring plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("Backend authoring tasks:")
    for task in payload["authoring_tasks"]:
        print(f"- {task['task_id']}: {task['acceptance_id']}")
    return 0


def _cmd_design_frontend_authoring(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_frontend_authoring(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("Frontend authoring plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("Frontend authoring tasks:")
    for task in payload["authoring_tasks"]:
        print(f"- {task['task_id']}: {task['acceptance_id']}")
    return 0


def _cmd_design_test_strategy_authoring(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_test_strategy_authoring(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("Test strategy authoring plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("Test strategy authoring tasks:")
    for task in payload["authoring_tasks"]:
        print(f"- {task['task_id']}: {task['acceptance_id']}")
    return 0


def _cmd_design_implementation_planning_authoring(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_implementation_planning_authoring(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("Implementation planning authoring plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("Implementation planning authoring tasks:")
    for task in payload["authoring_tasks"]:
        print(f"- {task['task_id']}: {task['acceptance_id']} -> {task['suggested_task_id']}")
    return 0


def _cmd_design_architecture_decisions_authoring(args: argparse.Namespace) -> int:
    target = Path(args.target)
    payload = build_architecture_decisions_authoring(target)
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1
    if not payload["ok"]:
        print("Architecture decisions authoring plan failed:")
        for error in payload["errors"]:
            print(f"- ERROR: {error}")
        return 1
    print("Architecture decisions authoring tasks:")
    for task in payload["authoring_tasks"]:
        print(f"- {task['task_id']}: {task['acceptance_id']} -> ADR {task['requires_adr']}")
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
    verify_parser.add_argument("--check", action="store_true", help="Run verification without writing state.")
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
    env.add_argument("--check", action="store_true", help="Preview repair actions without writing files or installing packages.")
    env.add_argument("--target", default=".")
    env.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    env.set_defaults(func=_cmd_env)

    runtime = sub.add_parser("runtime", help="Repair or inspect target-local governance runtime.")
    runtime_sub = runtime.add_subparsers(dest="runtime_command", required=True)
    runtime_refresh = runtime_sub.add_parser(
        "refresh",
        help="Refresh generated bin/, scripts/, and workflow-pack snapshot files from this workflow pack.",
    )
    runtime_refresh.add_argument("target", nargs="?", default=".")
    runtime_refresh.add_argument("--check", action="store_true", help="Run refresh preflight without writing files.")
    runtime_refresh.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    runtime_refresh.set_defaults(func=_cmd_runtime_refresh)

    gate = sub.add_parser("gate", help="Check whether a workflow phase gate can be entered.")
    gate.add_argument("gate", choices=GATE_NAMES)
    gate.add_argument("target", nargs="?", default=".")
    gate.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    gate.set_defaults(func=_cmd_gate)

    scaffold = sub.add_parser("scaffold", help="Create standard governance document scaffolds.")
    scaffold.add_argument("scaffold", choices=("product", "design"))
    scaffold.add_argument("target", nargs="?", default=".")
    scaffold.add_argument(
        "--chapter",
        action="append",
        choices=PRODUCT_CHAPTER_CHOICES,
        default=[],
        help="Product chapter to scaffold. Repeat for multiple chapters.",
    )
    scaffold.add_argument("--check", action="store_true", help="Run scaffold preflight without writing files.")
    scaffold.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    scaffold.set_defaults(func=_cmd_scaffold)

    advance = sub.add_parser("advance", help="Advance workflow phase after the matching gate passes.")
    advance.add_argument("phase", choices=PHASE_NAMES)
    advance.add_argument("target", nargs="?", default=".")
    advance.add_argument("--check", action="store_true", help="Run phase advance preflight without writing state.")
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
    mark_ready.add_argument("--check", action="store_true", help="Run readiness preflight without writing files.")
    mark_ready.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    mark_ready.set_defaults(func=_cmd_product_mark_ready)
    structure = product_sub.add_parser("structure", help="Fill scaffolded product chapters from explicit PRD sections.")
    structure.add_argument("target", nargs="?", default=".")
    structure.add_argument(
        "--chapter",
        action="append",
        default=[],
        help="Chapter mapping as product-chapter-key=PRD heading. Repeat for multiple chapters.",
    )
    structure.add_argument("--check", action="store_true", help="Preview chapter updates without writing files.")
    structure.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    structure.set_defaults(func=_cmd_product_structure)

    design = sub.add_parser("design", help="Plan design-derivation authoring work.")
    design_sub = design.add_subparsers(dest="design_command", required=True)
    design_plan = design_sub.add_parser(
        "plan",
        help="Show the ordered design tracks, skills, references, documents, and current blockers.",
    )
    design_plan.add_argument("target", nargs="?", default=".")
    design_plan.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    design_plan.set_defaults(func=_cmd_design_plan)
    api_candidates = design_sub.add_parser(
        "api-candidates",
        help="Extract source-backed API endpoint candidates from product acceptance criteria.",
    )
    api_candidates.add_argument("target", nargs="?", default=".")
    api_candidates.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    api_candidates.set_defaults(func=_cmd_design_api_candidates)
    api_authoring = design_sub.add_parser(
        "api-authoring",
        help="Build source-backed API contract authoring tasks from endpoint candidates.",
    )
    api_authoring.add_argument("target", nargs="?", default=".")
    api_authoring.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    api_authoring.set_defaults(func=_cmd_design_api_authoring)
    backend_authoring = design_sub.add_parser(
        "backend-authoring",
        help="Build source-backed backend module and data-model authoring tasks.",
    )
    backend_authoring.add_argument("target", nargs="?", default=".")
    backend_authoring.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    backend_authoring.set_defaults(func=_cmd_design_backend_authoring)
    frontend_authoring = design_sub.add_parser(
        "frontend-authoring",
        help="Build source-backed UI and frontend module authoring tasks.",
    )
    frontend_authoring.add_argument("target", nargs="?", default=".")
    frontend_authoring.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    frontend_authoring.set_defaults(func=_cmd_design_frontend_authoring)
    test_strategy_authoring = design_sub.add_parser(
        "test-strategy-authoring",
        help="Build source-backed test strategy and acceptance matrix authoring tasks.",
    )
    test_strategy_authoring.add_argument("target", nargs="?", default=".")
    test_strategy_authoring.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    test_strategy_authoring.set_defaults(func=_cmd_design_test_strategy_authoring)
    implementation_planning_authoring = design_sub.add_parser(
        "implementation-planning-authoring",
        help="Build source-backed roadmap, task board, and verification-log authoring tasks.",
    )
    implementation_planning_authoring.add_argument("target", nargs="?", default=".")
    implementation_planning_authoring.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    implementation_planning_authoring.set_defaults(func=_cmd_design_implementation_planning_authoring)
    architecture_decisions_authoring = design_sub.add_parser(
        "architecture-decisions-authoring",
        help="Build source-backed ADR trigger review and architecture decision authoring tasks.",
    )
    architecture_decisions_authoring.add_argument("target", nargs="?", default=".")
    architecture_decisions_authoring.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    architecture_decisions_authoring.set_defaults(func=_cmd_design_architecture_decisions_authoring)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except StateFileError as error:
        target = Path(getattr(args, "target", "."))
        if getattr(args, "json", False):
            _print_json(
                {
                    "ok": False,
                    "target": str(target),
                    "error": str(error),
                    "errors": [str(error)],
                    "path": str(error.path),
                }
            )
        else:
            print(f"State file error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
