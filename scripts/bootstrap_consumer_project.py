from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class ConsumerBootstrapError(Exception):
    def __init__(
        self,
        message: str,
        *,
        step: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.step = step
        self.payload = payload


def _agent_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    env.pop("MAKELEVEL", None)
    return env


def _run_json(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    cwd: Path,
    *,
    expected_returncode: int = 0,
) -> dict[str, object]:
    command = [str(item) for item in argv]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=_agent_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    step: dict[str, object] = {
        "id": step_id,
        "argv": command,
        "cwd": str(cwd),
        "returncode": result.returncode,
        "expected_returncode": expected_returncode,
    }
    steps.append(step)
    payload: dict[str, object] | None = None
    try:
        parsed = json.loads(result.stdout)
        if isinstance(parsed, dict):
            payload = parsed
            step["payload_ok"] = parsed.get("ok")
    except json.JSONDecodeError:
        payload = None
    if result.returncode != expected_returncode:
        failed = {**step, "stdout": result.stdout, "stderr": result.stderr}
        raise ConsumerBootstrapError(f"step failed: {step_id}", step=failed, payload=payload)
    if payload is None:
        failed = {**step, "stdout": result.stdout, "stderr": result.stderr}
        raise ConsumerBootstrapError(f"step did not return JSON object: {step_id}", step=failed)
    return payload


def run_consumer_bootstrap(
    *,
    target: Path,
    product: Path | None = None,
    profile: str = "unknown",
    project_name: str = "Project Workspace",
    check: bool = False,
    force: bool = False,
    advance_product_structuring: bool = False,
    pack_root: Path = ROOT,
) -> dict[str, object]:
    pack_root = pack_root.resolve()
    target = target.resolve()
    product = product.resolve() if product is not None else None
    steps: list[dict[str, object]] = []
    try:
        pack_manifest_verification = _run_json(
            steps,
            "pack_manifest_verify",
            [sys.executable, "scripts/verify_pack_manifest.py", ".", "--json"],
            pack_root,
        )
        _require(
            pack_manifest_verification.get("ok") is True,
            "workflow-pack manifest verification failed",
            payload=pack_manifest_verification,
        )
        pack_verification = _run_json(
            steps,
            "pack_verify",
            [sys.executable, "scripts/verify_pack.py", "--json"],
            pack_root,
        )
        _require(pack_verification.get("ok") is True, "workflow-pack verification failed", payload=pack_verification)

        env_check = _run_json(
            steps,
            "env_repair_check",
            [
                sys.executable,
                "scripts/governance_cli.py",
                "env",
                "--repair",
                "--check",
                "--target",
                target,
                "--json",
            ],
            pack_root,
        )
        _require(env_check.get("ok") is True, "environment repair check failed", payload=env_check)
        _require(env_check.get("check") is True, "environment repair check did not run in check mode", payload=env_check)
        _require(env_check.get("missing_required") == [], "required environment tools are missing", payload=env_check)

        init_check = _run_json(
            steps,
            "init_check",
            _init_argv(target=target, product=product, profile=profile, project_name=project_name, check=True, force=force),
            pack_root,
        )
        _require(init_check.get("ok") is True, "initialization preflight failed", payload=init_check)

        base_payload: dict[str, object] = {
            "ok": True,
            "check": check,
            "initialized": False,
            "pack_root": str(pack_root),
            "target": str(target),
            "product": str(product) if product is not None else "",
            "profile": profile,
            "project_name": project_name,
            "force": force,
            "advance_product_structuring_requested": advance_product_structuring,
            "advanced_product_structuring": False,
            "pack_manifest_verification": pack_manifest_verification,
            "pack_verification": pack_verification,
            "env_check": env_check,
            "init_check": init_check,
            "steps": steps,
        }
        if check:
            return base_payload

        init_payload = _run_json(
            steps,
            "init",
            _init_argv(target=target, product=product, profile=profile, project_name=project_name, check=False, force=force),
            pack_root,
        )
        _require(init_payload.get("ok") is True, "initialization failed", payload=init_payload)

        verify_payload = _run_json(
            steps,
            "target_local_verify_check",
            ["bin/governance", "verify", ".", "--check", "--json"],
            target,
        )
        status_payload = _run_json(
            steps,
            "target_local_governance_status",
            ["make", "governance-status"],
            target,
        )
        workflow_plan_payload = _run_json(
            steps,
            "target_local_workflow_plan",
            ["make", "workflow-plan"],
            target,
        )
        target_local = _target_local_details(
            target=target,
            init_payload=init_payload,
            verify_payload=verify_payload,
            status_payload=status_payload,
            workflow_plan_payload=workflow_plan_payload,
        )
        _require(target_local.get("ok") is True, "target-local verification failed", payload=target_local)

        payload = {
            **base_payload,
            "initialized": True,
            "init": init_payload,
            "target_local": target_local,
        }
        if advance_product_structuring:
            product_structuring = _advance_product_structuring(steps, target)
            payload["advanced_product_structuring"] = True
            payload["product_structuring"] = product_structuring
            payload["product_plan"] = product_structuring["product_plan"]
            refreshed_status_payload = product_structuring["status"]
            refreshed_workflow_plan_payload = product_structuring["workflow_plan"]
            payload["target_local"] = _target_local_details(
                target=target,
                init_payload=init_payload,
                verify_payload=verify_payload,
                status_payload=refreshed_status_payload,
                workflow_plan_payload=refreshed_workflow_plan_payload,
                expected_phase="product-structuring",
            )
        if isinstance(status_payload.get("local_commands"), list):
            payload["local_commands"] = status_payload["local_commands"]
        elif isinstance(init_payload.get("local_commands"), list):
            payload["local_commands"] = init_payload["local_commands"]
        latest_status = payload.get("product_structuring", {}).get("status") if isinstance(payload.get("product_structuring"), dict) else status_payload
        if isinstance(latest_status, dict) and isinstance(latest_status.get("local_commands"), list):
            payload["local_commands"] = latest_status["local_commands"]
        if isinstance(latest_status, dict) and isinstance(latest_status.get("next_actions"), list):
            payload["next_actions"] = latest_status["next_actions"]
        elif isinstance(status_payload.get("next_actions"), list):
            payload["next_actions"] = status_payload["next_actions"]
        elif isinstance(init_payload.get("next_actions"), list):
            payload["next_actions"] = init_payload["next_actions"]
        return payload
    except ConsumerBootstrapError as error:
        return {
            "ok": False,
            "check": check,
            "initialized": False,
            "error": error.message,
            "pack_root": str(pack_root),
            "target": str(target),
            "product": str(product) if product is not None else "",
            "profile": profile,
            "project_name": project_name,
            "force": force,
            "advance_product_structuring_requested": advance_product_structuring,
            "advanced_product_structuring": False,
            "steps": steps,
            "failed_step": error.step,
            "failed_payload": error.payload,
        }
    except OSError as error:
        return {
            "ok": False,
            "check": check,
            "initialized": False,
            "error": error.strerror or str(error),
            "pack_root": str(pack_root),
            "target": str(target),
            "product": str(product) if product is not None else "",
            "profile": profile,
            "project_name": project_name,
            "force": force,
            "advance_product_structuring_requested": advance_product_structuring,
            "advanced_product_structuring": False,
            "steps": steps,
        }


def _init_argv(
    *,
    target: Path,
    product: Path | None,
    profile: str,
    project_name: str,
    check: bool,
    force: bool,
) -> list[str | Path]:
    argv: list[str | Path] = [
        sys.executable,
        "scripts/governance_cli.py",
        "init",
        "--target",
        target,
        "--profile",
        profile,
        "--project-name",
        project_name,
        "--json",
    ]
    if product is not None:
        argv.extend(["--product", product])
    if check:
        argv.append("--check")
    if force:
        argv.append("--force")
    return argv


def _target_local_details(
    *,
    target: Path,
    init_payload: dict[str, object],
    verify_payload: dict[str, object],
    status_payload: dict[str, object],
    workflow_plan_payload: dict[str, object],
    expected_phase: str = "initialized",
) -> dict[str, object]:
    init_product = init_payload.get("product")
    status_state = status_payload.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else ""
    profile = status_state.get("profile") if isinstance(status_state, dict) else ""
    project_name = status_state.get("project_name") if isinstance(status_state, dict) else ""
    return {
        "ok": (
            verify_payload.get("ok") is True
            and verify_payload.get("findings") == []
            and status_payload.get("ok") is True
            and workflow_plan_payload.get("ok") is True
            and workflow_plan_payload.get("phase") == phase
            and phase == expected_phase
            and (target / "bin/governance").is_file()
            and (target / "scripts/governance_cli.py").is_file()
            and (target / "docs/agent-workflow/runtime-manifest.json").is_file()
            and (target / "docs/agent-workflow/workflow-pack/manifest.json").is_file()
            and (target / "docs/product/core/source/source-manifest.json").is_file()
        ),
        "phase": phase,
        "profile": profile,
        "project_name": project_name,
        "product_selection": init_product.get("selection") if isinstance(init_product, dict) else "",
        "verify_ok": verify_payload.get("ok") is True and verify_payload.get("findings") == [],
        "status_ok": status_payload.get("ok") is True,
        "workflow_plan_ok": workflow_plan_payload.get("ok") is True,
        "local_governance_cli": (target / "bin/governance").is_file(),
        "runtime_manifest": (target / "docs/agent-workflow/runtime-manifest.json").is_file(),
        "workflow_pack_snapshot": (target / "docs/agent-workflow/workflow-pack/manifest.json").is_file(),
        "product_source_manifest": (target / "docs/product/core/source/source-manifest.json").is_file(),
    }


def _advance_product_structuring(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    advance_check = _run_json(
        steps,
        "advance_product_structuring_check",
        ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
        target,
    )
    _require(advance_check.get("ok") is True, "product-structuring advance preflight failed", payload=advance_check)
    advance = _run_json(
        steps,
        "advance_product_structuring",
        ["bin/governance", "advance", "product-structuring", ".", "--json"],
        target,
    )
    _require(advance.get("ok") is True, "product-structuring advance failed", payload=advance)
    status = _run_json(
        steps,
        "target_local_governance_status_product_structuring",
        ["make", "governance-status"],
        target,
    )
    workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_product_structuring",
        ["make", "workflow-plan"],
        target,
    )
    product_plan = _run_json(
        steps,
        "target_local_product_plan",
        ["make", "product-plan"],
        target,
    )
    status_state = status.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else ""
    return {
        "ok": (
            advance_check.get("ok") is True
            and advance.get("ok") is True
            and status.get("ok") is True
            and workflow_plan.get("ok") is True
            and product_plan.get("ok") is True
            and phase == "product-structuring"
            and workflow_plan.get("phase") == "product-structuring"
        ),
        "phase": phase,
        "advance_check_ok": advance_check.get("ok") is True,
        "advance_ok": advance.get("ok") is True,
        "status_ok": status.get("ok") is True,
        "workflow_plan_ok": workflow_plan.get("ok") is True,
        "product_plan_ok": product_plan.get("ok") is True,
        "advance_check": advance_check,
        "advance": advance,
        "status": status,
        "workflow_plan": workflow_plan,
        "product_plan": product_plan,
    }


def _require(condition: bool, message: str, *, payload: dict[str, object] | None = None) -> None:
    if not condition:
        raise ConsumerBootstrapError(message, payload=payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap a governed target repository from an exported docs-as-code workflow pack."
    )
    parser.add_argument("--target", required=True, type=Path, help="Target project directory to initialize.")
    parser.add_argument("--product", type=Path, help="Optional source product document path.")
    parser.add_argument("--profile", default="unknown", help="Project profile recorded in governance state.")
    parser.add_argument("--project-name", default="Project Workspace", help="Project name recorded in governance state.")
    parser.add_argument("--force", action="store_true", help="Pass --force through to governance init.")
    parser.add_argument("--check", action="store_true", help="Run source-pack, environment, and init checks without writing.")
    parser.add_argument(
        "--advance-product-structuring",
        action="store_true",
        help="After initialization, run target-local product-structuring advance and product-plan commands.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    if payload.get("ok"):
        mode = "preflight passed" if payload.get("check") else "initialized"
        print(f"Consumer bootstrap {mode}: {payload.get('target')}")
        return
    print(f"Consumer bootstrap failed: {payload.get('error')}")


def main() -> int:
    args = build_parser().parse_args()
    payload = run_consumer_bootstrap(
        target=args.target,
        product=args.product,
        profile=args.profile,
        project_name=args.project_name,
        check=args.check,
        force=args.force,
        advance_product_structuring=args.advance_product_structuring,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
