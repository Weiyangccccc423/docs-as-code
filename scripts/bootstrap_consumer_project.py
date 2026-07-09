from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
    allowed_returncodes: tuple[int, ...] | None = None,
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
    if allowed_returncodes is not None:
        step["allowed_returncodes"] = list(allowed_returncodes)
    steps.append(step)
    payload: dict[str, object] | None = None
    try:
        parsed = json.loads(result.stdout)
        if isinstance(parsed, dict):
            payload = parsed
            step["payload_ok"] = parsed.get("ok")
    except json.JSONDecodeError:
        payload = None
    accepted_returncodes = allowed_returncodes if allowed_returncodes is not None else (expected_returncode,)
    if result.returncode not in accepted_returncodes:
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
    product_scaffold_preview: bool = False,
    product_structure_preview: bool = False,
    product_structure_apply: bool = False,
    advance_design_derivation: bool = False,
    design_scaffold_preview: bool = False,
    design_scaffold_apply: bool = False,
    design_authoring_preview: bool = False,
    implementation_readiness_preview: bool = False,
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
        _require(
            not product_scaffold_preview or advance_product_structuring,
            "--product-scaffold-preview requires --advance-product-structuring",
            payload=init_check,
        )
        _require(
            not (check and product_scaffold_preview),
            "--product-scaffold-preview requires a write-mode bootstrap so the target can be initialized and advanced",
            payload=init_check,
        )
        _require(
            not product_structure_preview or product_scaffold_preview,
            "--product-structure-preview requires --product-scaffold-preview",
            payload=init_check,
        )
        _require(
            not product_structure_apply or product_structure_preview,
            "--product-structure-apply requires --product-structure-preview",
            payload=init_check,
        )
        _require(
            not advance_design_derivation or product_structure_apply,
            "--advance-design-derivation requires --product-structure-apply",
            payload=init_check,
        )
        _require(
            not design_scaffold_preview or advance_design_derivation,
            "--design-scaffold-preview requires --advance-design-derivation",
            payload=init_check,
        )
        _require(
            not (check and design_scaffold_preview),
            "--design-scaffold-preview requires a write-mode bootstrap so the target can be initialized and advanced",
            payload=init_check,
        )
        _require(
            not design_scaffold_apply or design_scaffold_preview,
            "--design-scaffold-apply requires --design-scaffold-preview",
            payload=init_check,
        )
        _require(
            not design_authoring_preview or design_scaffold_apply,
            "--design-authoring-preview requires --design-scaffold-apply",
            payload=init_check,
        )
        _require(
            not implementation_readiness_preview or design_authoring_preview,
            "--implementation-readiness-preview requires --design-authoring-preview",
            payload=init_check,
        )

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
            "product_scaffold_preview_requested": product_scaffold_preview,
            "product_scaffold_previewed": False,
            "product_scaffold_preview_ok": False,
            "product_structure_preview_requested": product_structure_preview,
            "product_structure_previewed": False,
            "product_structure_preview_ok": False,
            "product_structure_apply_requested": product_structure_apply,
            "product_structure_applied": False,
            "product_structure_apply_ok": False,
            "advance_design_derivation_requested": advance_design_derivation,
            "advanced_design_derivation": False,
            "design_scaffold_preview_requested": design_scaffold_preview,
            "design_scaffold_previewed": False,
            "design_scaffold_preview_ok": False,
            "design_scaffold_apply_requested": design_scaffold_apply,
            "design_scaffold_applied": False,
            "design_scaffold_apply_ok": False,
            "design_authoring_preview_requested": design_authoring_preview,
            "design_authoring_previewed": False,
            "design_authoring_preview_ok": False,
            "implementation_readiness_preview_requested": implementation_readiness_preview,
            "implementation_readiness_previewed": False,
            "implementation_readiness_preview_ok": False,
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
            _require(
                product_structuring.get("ok") is True,
                "product-structuring bootstrap sequence failed",
                payload=product_structuring,
            )
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
            if product_scaffold_preview:
                scaffold_preview = _preview_product_scaffold(
                    steps,
                    target,
                    product_structuring["product_plan"],
                )
                payload["product_scaffold_previewed"] = True
                payload["product_scaffold_preview"] = scaffold_preview
                payload["product_scaffold_preview_ok"] = scaffold_preview.get("ok") is True
                if product_structure_preview:
                    structure_preview = _preview_product_structure(
                        steps,
                        target,
                        product_structuring["product_plan"],
                    )
                    payload["product_structure_previewed"] = True
                    payload["product_structure_preview"] = structure_preview
                    payload["product_structure_preview_ok"] = structure_preview.get("ok") is True
                    if product_structure_apply:
                        structure_apply = _apply_product_structure(
                            steps,
                            target,
                            product_structuring["product_plan"],
                        )
                        payload["product_structure_applied"] = True
                        payload["product_structure_apply"] = structure_apply
                        payload["product_structure_apply_ok"] = structure_apply.get("ok") is True
                        payload["target_local"] = _target_local_details(
                            target=target,
                            init_payload=init_payload,
                            verify_payload=verify_payload,
                            status_payload=structure_apply["post_status"],
                            workflow_plan_payload=structure_apply["post_workflow_plan"],
                            expected_phase="product-structuring",
                        )
                        if advance_design_derivation:
                            _require(
                                structure_apply.get("apply_skipped") is not True,
                                "design-derivation advance requires product structure apply to write source-backed chapters",
                                payload=structure_apply,
                            )
                            design_derivation = _advance_design_derivation(steps, target)
                            _require(
                                design_derivation.get("ok") is True,
                                "design-derivation bootstrap sequence failed",
                                payload=design_derivation,
                            )
                            payload["advanced_design_derivation"] = True
                            payload["design_derivation"] = design_derivation
                            payload["design_plan"] = design_derivation["design_plan"]
                            payload["target_local"] = _target_local_details(
                                target=target,
                                init_payload=init_payload,
                                verify_payload=design_derivation["product_verify_check"],
                                status_payload=design_derivation["status"],
                                workflow_plan_payload=design_derivation["workflow_plan"],
                                expected_phase="design-derivation",
                            )
                            if design_scaffold_preview:
                                scaffold_preview = _preview_design_scaffold(steps, target)
                                payload["design_scaffold_previewed"] = True
                                payload["design_scaffold_preview"] = scaffold_preview
                                payload["design_scaffold_preview_ok"] = scaffold_preview.get("ok") is True
                                if design_scaffold_apply:
                                    scaffold_apply = _apply_design_scaffold(steps, target)
                                    payload["design_scaffold_applied"] = True
                                    payload["design_scaffold_apply"] = scaffold_apply
                                    payload["design_scaffold_apply_ok"] = scaffold_apply.get("ok") is True
                                    if design_authoring_preview:
                                        authoring_preview = _preview_design_authoring(steps, target)
                                        payload["design_authoring_previewed"] = True
                                        payload["design_authoring_preview"] = authoring_preview
                                        payload["design_authoring_preview_ok"] = authoring_preview.get("ok") is True
                                        if implementation_readiness_preview:
                                            readiness_preview = _preview_implementation_readiness(steps, target)
                                            payload["implementation_readiness_previewed"] = True
                                            payload["implementation_readiness_preview"] = readiness_preview
                                            payload["implementation_readiness_preview_ok"] = (
                                                readiness_preview.get("ok") is True
                                            )
        if isinstance(status_payload.get("local_commands"), list):
            payload["local_commands"] = status_payload["local_commands"]
        elif isinstance(init_payload.get("local_commands"), list):
            payload["local_commands"] = init_payload["local_commands"]
        if isinstance(payload.get("design_derivation"), dict):
            latest_status = payload["design_derivation"].get("status")
        elif isinstance(payload.get("product_structuring"), dict):
            latest_status = payload["product_structuring"].get("status")
        else:
            latest_status = status_payload
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
            "product_scaffold_preview_requested": product_scaffold_preview,
            "product_scaffold_previewed": False,
            "product_scaffold_preview_ok": False,
            "product_structure_preview_requested": product_structure_preview,
            "product_structure_previewed": False,
            "product_structure_preview_ok": False,
            "product_structure_apply_requested": product_structure_apply,
            "product_structure_applied": False,
            "product_structure_apply_ok": False,
            "advance_design_derivation_requested": advance_design_derivation,
            "advanced_design_derivation": False,
            "design_scaffold_preview_requested": design_scaffold_preview,
            "design_scaffold_previewed": False,
            "design_scaffold_preview_ok": False,
            "design_scaffold_apply_requested": design_scaffold_apply,
            "design_scaffold_applied": False,
            "design_scaffold_apply_ok": False,
            "design_authoring_preview_requested": design_authoring_preview,
            "design_authoring_previewed": False,
            "design_authoring_preview_ok": False,
            "implementation_readiness_preview_requested": implementation_readiness_preview,
            "implementation_readiness_previewed": False,
            "implementation_readiness_preview_ok": False,
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
            "product_scaffold_preview_requested": product_scaffold_preview,
            "product_scaffold_previewed": False,
            "product_scaffold_preview_ok": False,
            "product_structure_preview_requested": product_structure_preview,
            "product_structure_previewed": False,
            "product_structure_preview_ok": False,
            "product_structure_apply_requested": product_structure_apply,
            "product_structure_applied": False,
            "product_structure_apply_ok": False,
            "advance_design_derivation_requested": advance_design_derivation,
            "advanced_design_derivation": False,
            "design_scaffold_preview_requested": design_scaffold_preview,
            "design_scaffold_previewed": False,
            "design_scaffold_preview_ok": False,
            "design_scaffold_apply_requested": design_scaffold_apply,
            "design_scaffold_applied": False,
            "design_scaffold_apply_ok": False,
            "design_authoring_preview_requested": design_authoring_preview,
            "design_authoring_previewed": False,
            "design_authoring_preview_ok": False,
            "implementation_readiness_preview_requested": implementation_readiness_preview,
            "implementation_readiness_previewed": False,
            "implementation_readiness_preview_ok": False,
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


def _preview_product_scaffold(
    steps: list[dict[str, object]],
    target: Path,
    product_plan: dict[str, object],
) -> dict[str, object]:
    suggested_mappings = product_plan.get("suggested_mappings")
    chapters: list[str] = []
    command_args: list[str] = []
    if isinstance(suggested_mappings, list):
        for mapping in suggested_mappings:
            if not isinstance(mapping, dict):
                continue
            chapter = mapping.get("chapter")
            command_arg = mapping.get("command_arg")
            if not isinstance(chapter, str) or not chapter:
                continue
            if chapter in chapters:
                continue
            chapters.append(chapter)
            if isinstance(command_arg, str) and command_arg:
                command_args.append(command_arg)
    required_decisions = product_plan.get("required_decisions")
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "decision_policy": str(product_plan.get("decision_policy", "do_not_guess_product_meaning")),
        "source": "product_plan.suggested_mappings",
        "selected_chapters": chapters,
        "command_args": command_args,
        "required_decisions": required_decisions if isinstance(required_decisions, list) else [],
        "scaffold_check": {},
        "preview_skipped": False,
        "skip_reason": "",
    }
    if not chapters:
        payload["preview_skipped"] = True
        payload["skip_reason"] = "product plan did not report conservative suggested_mappings"
        return payload

    argv: list[str] = ["bin/governance", "scaffold", "product", "."]
    for chapter in chapters:
        argv.extend(["--chapter", chapter])
    argv.extend(["--check", "--json"])
    scaffold_check = _run_json(steps, "target_local_product_scaffold_preview", argv, target)
    payload["scaffold_check"] = scaffold_check
    payload["ok"] = scaffold_check.get("ok") is True and scaffold_check.get("check") is True
    return payload


def _preview_product_structure(
    steps: list[dict[str, object]],
    target: Path,
    product_plan: dict[str, object],
) -> dict[str, object]:
    suggested_mappings = product_plan.get("suggested_mappings")
    command_args: list[str] = []
    selected_chapters: list[str] = []
    if isinstance(suggested_mappings, list):
        for mapping in suggested_mappings:
            if not isinstance(mapping, dict):
                continue
            chapter = mapping.get("chapter")
            command_arg = mapping.get("command_arg")
            if not isinstance(chapter, str) or not isinstance(command_arg, str) or not command_arg:
                continue
            if chapter in selected_chapters:
                continue
            selected_chapters.append(chapter)
            command_args.append(command_arg)
    required_decisions = product_plan.get("required_decisions")
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "preview_mode": "sandboxed_no_target_writes",
        "decision_policy": str(product_plan.get("decision_policy", "do_not_guess_product_meaning")),
        "source": "product_plan.suggested_mappings[].command_arg",
        "selected_chapters": selected_chapters,
        "command_args": command_args,
        "required_decisions": required_decisions if isinstance(required_decisions, list) else [],
        "sandbox_scaffold": {},
        "structure_check": {},
        "preview_skipped": False,
        "skip_reason": "",
    }
    if not command_args:
        payload["preview_skipped"] = True
        payload["skip_reason"] = "product plan did not report conservative command_arg mappings"
        return payload

    with tempfile.TemporaryDirectory(prefix="docs-as-code-product-structure-preview-") as tmp:
        sandbox = Path(tmp) / "target"
        shutil.copytree(target, sandbox, symlinks=True)
        scaffold_argv: list[str] = ["bin/governance", "scaffold", "product", "."]
        for chapter in selected_chapters:
            scaffold_argv.extend(["--chapter", chapter])
        scaffold_argv.append("--json")
        sandbox_scaffold = _run_json(
            steps,
            "product_structure_preview_sandbox_scaffold",
            scaffold_argv,
            sandbox,
        )
        _require(
            sandbox_scaffold.get("ok") is True,
            "product structure preview sandbox scaffold failed",
            payload=sandbox_scaffold,
        )
        structure_argv: list[str] = ["bin/governance", "product", "structure", "."]
        for command_arg in command_args:
            structure_argv.extend(["--chapter", command_arg])
        structure_argv.extend(["--check", "--json"])
        structure_check = _run_json(
            steps,
            "target_local_product_structure_preview",
            structure_argv,
            sandbox,
        )
    payload["sandbox_scaffold"] = sandbox_scaffold
    payload["structure_check"] = structure_check
    payload["ok"] = structure_check.get("ok") is True and structure_check.get("check") is True
    return payload


def _apply_product_structure(
    steps: list[dict[str, object]],
    target: Path,
    product_plan: dict[str, object],
) -> dict[str, object]:
    mapping = _product_plan_mapping(product_plan)
    chapters = mapping["chapters"]
    command_args = mapping["command_args"]
    required_decisions = product_plan.get("required_decisions")
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": False,
        "writes_state": True,
        "decision_policy": str(product_plan.get("decision_policy", "do_not_guess_product_meaning")),
        "source": "product_plan.suggested_mappings[].command_arg",
        "selected_chapters": chapters,
        "command_args": command_args,
        "required_decisions": required_decisions if isinstance(required_decisions, list) else [],
        "scaffold": {},
        "structure_check": {},
        "structure": {},
        "post_status": {},
        "post_workflow_plan": {},
        "apply_skipped": False,
        "skip_reason": "",
    }
    if not command_args:
        payload["apply_skipped"] = True
        payload["skip_reason"] = "product plan did not report conservative command_arg mappings"
        return payload

    scaffold_argv: list[str] = ["bin/governance", "scaffold", "product", "."]
    for chapter in chapters:
        scaffold_argv.extend(["--chapter", chapter])
    scaffold_argv.append("--json")
    scaffold = _run_json(steps, "target_local_product_scaffold_apply", scaffold_argv, target)
    _require(scaffold.get("ok") is True, "product scaffold apply failed", payload=scaffold)

    structure_check_argv: list[str] = ["bin/governance", "product", "structure", "."]
    for command_arg in command_args:
        structure_check_argv.extend(["--chapter", command_arg])
    structure_check_argv.extend(["--check", "--json"])
    structure_check = _run_json(
        steps,
        "target_local_product_structure_apply_check",
        structure_check_argv,
        target,
    )
    _require(structure_check.get("ok") is True, "product structure apply preflight failed", payload=structure_check)

    structure_argv: list[str] = ["bin/governance", "product", "structure", "."]
    for command_arg in command_args:
        structure_argv.extend(["--chapter", command_arg])
    structure_argv.append("--json")
    structure = _run_json(steps, "target_local_product_structure_apply", structure_argv, target)
    _require(structure.get("ok") is True, "product structure apply failed", payload=structure)

    post_status = _run_json(
        steps,
        "target_local_governance_status_after_product_structure_apply",
        ["make", "governance-status"],
        target,
    )
    post_workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_after_product_structure_apply",
        ["make", "workflow-plan"],
        target,
    )
    payload["scaffold"] = scaffold
    payload["structure_check"] = structure_check
    payload["structure"] = structure
    payload["post_status"] = post_status
    payload["post_workflow_plan"] = post_workflow_plan
    payload["ok"] = (
        scaffold.get("ok") is True
        and structure_check.get("ok") is True
        and structure.get("ok") is True
        and post_status.get("ok") is True
        and post_workflow_plan.get("ok") is True
    )
    return payload


def _advance_design_derivation(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    product_verify_check = _run_json(
        steps,
        "product_clean_verify_check_before_design_derivation",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    _require(
        product_verify_check.get("ok") is True and product_verify_check.get("findings") == [],
        "verification failed before design-derivation advance",
        payload=product_verify_check,
    )
    advance_check = _run_json(
        steps,
        "advance_design_derivation_check",
        ["bin/governance", "advance", "design-derivation", ".", "--check", "--json"],
        target,
    )
    _require(advance_check.get("ok") is True, "design-derivation advance preflight failed", payload=advance_check)
    advance = _run_json(
        steps,
        "advance_design_derivation",
        ["bin/governance", "advance", "design-derivation", ".", "--json"],
        target,
    )
    _require(advance.get("ok") is True, "design-derivation advance failed", payload=advance)
    status = _run_json(
        steps,
        "target_local_governance_status_design_derivation",
        ["make", "governance-status"],
        target,
    )
    workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_design_derivation",
        ["make", "workflow-plan"],
        target,
    )
    design_plan = _run_json(
        steps,
        "target_local_design_plan",
        ["make", "design-plan"],
        target,
    )
    status_state = status.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else ""
    return {
        "ok": (
            product_verify_check.get("ok") is True
            and product_verify_check.get("findings") == []
            and advance_check.get("ok") is True
            and advance.get("ok") is True
            and status.get("ok") is True
            and workflow_plan.get("ok") is True
            and design_plan.get("ok") is True
            and phase == "design-derivation"
            and workflow_plan.get("phase") == "design-derivation"
            and design_plan.get("phase") == "design-derivation"
        ),
        "phase": phase,
        "product_verify_check_ok": product_verify_check.get("ok") is True
        and product_verify_check.get("findings") == [],
        "advance_check_ok": advance_check.get("ok") is True,
        "advance_ok": advance.get("ok") is True,
        "status_ok": status.get("ok") is True,
        "workflow_plan_ok": workflow_plan.get("ok") is True,
        "design_plan_ok": design_plan.get("ok") is True,
        "product_verify_check": product_verify_check,
        "advance_check": advance_check,
        "advance": advance,
        "status": status,
        "workflow_plan": workflow_plan,
        "design_plan": design_plan,
    }


def _preview_design_scaffold(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    scaffold_check = _run_json(
        steps,
        "target_local_design_scaffold_preview",
        ["bin/governance", "scaffold", "design", ".", "--check", "--json"],
        target,
    )
    status_state = scaffold_check.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else "design-derivation"
    return {
        "ok": scaffold_check.get("ok") is True and scaffold_check.get("check") is True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": phase,
        "scaffold_check": scaffold_check,
    }


def _apply_design_scaffold(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    scaffold = _run_json(
        steps,
        "target_local_design_scaffold_apply",
        ["bin/governance", "scaffold", "design", ".", "--json"],
        target,
    )
    _require(scaffold.get("ok") is True, "design scaffold apply failed", payload=scaffold)

    post_verify_check = _run_json(
        steps,
        "target_local_verify_check_after_design_scaffold_apply",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
        expected_returncode=1,
    )
    post_status = _run_json(
        steps,
        "target_local_governance_status_after_design_scaffold_apply",
        ["make", "governance-status"],
        target,
    )
    post_workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_after_design_scaffold_apply",
        ["make", "workflow-plan"],
        target,
    )
    blockers = scaffold.get("next_actions_blocked_by")
    findings = post_verify_check.get("findings")
    status_state = post_status.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else "design-derivation"
    return {
        "ok": (
            scaffold.get("ok") is True
            and post_verify_check.get("ok") is False
            and post_status.get("ok") is True
            and post_workflow_plan.get("ok") is True
            and phase == "design-derivation"
        ),
        "target": str(target),
        "check": False,
        "writes_state": True,
        "phase": phase,
        "scaffold": scaffold,
        "post_verify_check": post_verify_check,
        "post_status": post_status,
        "post_workflow_plan": post_workflow_plan,
        "next_actions_blocked_by": blockers if isinstance(blockers, list) else [],
        "post_verify_blocked_by_placeholders": _has_scaffold_placeholder_findings(findings),
    }


def _has_scaffold_placeholder_findings(findings: object) -> bool:
    if not isinstance(findings, list):
        return False
    return any(
        isinstance(finding, dict) and finding.get("code") == "governance_scaffold_placeholder"
        for finding in findings
    )


DESIGN_AUTHORING_QUEUE_IDS = [
    ("architecture-authoring", "target_local_design_architecture_authoring_preview"),
    ("api-authoring", "target_local_design_api_authoring_preview"),
    ("backend-authoring", "target_local_design_backend_authoring_preview"),
    ("data-model-authoring", "target_local_design_data_model_authoring_preview"),
    ("ui-interaction-authoring", "target_local_design_ui_interaction_authoring_preview"),
    ("frontend-authoring", "target_local_design_frontend_authoring_preview"),
    ("test-strategy-authoring", "target_local_design_test_strategy_authoring_preview"),
    ("implementation-planning-authoring", "target_local_design_implementation_planning_authoring_preview"),
    ("architecture-decisions-authoring", "target_local_design_architecture_decisions_authoring_preview"),
]


def _preview_design_authoring(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    queues: dict[str, object] = {}
    ok = True
    for queue_id, step_id in DESIGN_AUTHORING_QUEUE_IDS:
        payload = _run_json(
            steps,
            step_id,
            ["bin/governance", "design", queue_id, ".", "--json"],
            target,
        )
        queues[queue_id] = payload
        ok = ok and payload.get("ok") is True
    return {
        "ok": ok,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": "design-derivation",
        "queue_order": [queue_id for queue_id, _step_id in DESIGN_AUTHORING_QUEUE_IDS],
        "queues": queues,
    }


def _preview_implementation_readiness(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    verify_check = _run_json(
        steps,
        "target_local_verify_check_implementation_readiness_preview",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
        allowed_returncodes=(0, 1),
    )
    gate = _run_json(
        steps,
        "target_local_implementation_gate_preview",
        ["bin/governance", "gate", "implementation", ".", "--json"],
        target,
        allowed_returncodes=(0, 1),
    )
    implementation_plan = _run_json(
        steps,
        "target_local_implementation_plan_preview",
        ["bin/governance", "implementation", "plan", ".", "--json"],
        target,
        allowed_returncodes=(0, 1),
    )
    readiness_ok = (
        verify_check.get("ok") is True
        and gate.get("ok") is True
        and implementation_plan.get("ok") is True
        and implementation_plan.get("gate_ok") is True
    )
    status_state = gate.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else str(implementation_plan.get("phase", ""))
    return {
        "ok": True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": phase,
        "readiness_ok": readiness_ok,
        "implementation_ready": readiness_ok,
        "verify_ok": verify_check.get("ok") is True,
        "gate_ok": gate.get("ok") is True,
        "implementation_plan_ok": implementation_plan.get("ok") is True,
        "verify_check": verify_check,
        "gate": gate,
        "implementation_plan": implementation_plan,
    }


def _product_plan_mapping(product_plan: dict[str, object]) -> dict[str, list[str]]:
    suggested_mappings = product_plan.get("suggested_mappings")
    chapters: list[str] = []
    command_args: list[str] = []
    if isinstance(suggested_mappings, list):
        for mapping in suggested_mappings:
            if not isinstance(mapping, dict):
                continue
            chapter = mapping.get("chapter")
            command_arg = mapping.get("command_arg")
            if not isinstance(chapter, str) or not chapter:
                continue
            if chapter in chapters:
                continue
            chapters.append(chapter)
            if isinstance(command_arg, str) and command_arg:
                command_args.append(command_arg)
    return {"chapters": chapters, "command_args": command_args}


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
    parser.add_argument(
        "--product-scaffold-preview",
        action="store_true",
        help=(
            "With --advance-product-structuring, run target-local scaffold product --check from conservative "
            "product-plan suggestions without writing product chapters."
        ),
    )
    parser.add_argument(
        "--product-structure-preview",
        action="store_true",
        help=(
            "With --product-scaffold-preview, run target-local product structure --check from conservative "
            "product-plan command_arg mappings without writing product chapters."
        ),
    )
    parser.add_argument(
        "--product-structure-apply",
        action="store_true",
        help=(
            "With --product-structure-preview, apply product scaffold and product structure using conservative "
            "product-plan command_arg mappings."
        ),
    )
    parser.add_argument(
        "--advance-design-derivation",
        action="store_true",
        help=(
            "With --product-structure-apply, verify clean product docs, advance to design-derivation, "
            "and return the target-local design plan."
        ),
    )
    parser.add_argument(
        "--design-scaffold-preview",
        action="store_true",
        help=(
            "With --advance-design-derivation, run scaffold design --check and return would_create, "
            "would_skip, and would_index without writing design placeholders."
        ),
    )
    parser.add_argument(
        "--design-scaffold-apply",
        action="store_true",
        help=(
            "With --design-scaffold-preview, write the standard design scaffold and return placeholder blockers "
            "without treating design authoring as complete."
        ),
    )
    parser.add_argument(
        "--design-authoring-preview",
        action="store_true",
        help=(
            "With --design-scaffold-apply, run all read-only design authoring queue commands and return their "
            "skill, blocker, and active-work payloads."
        ),
    )
    parser.add_argument(
        "--implementation-readiness-preview",
        action="store_true",
        help=(
            "With --design-authoring-preview, run read-only implementation verify/gate/plan commands and return "
            "readiness blockers without advancing implementation or claiming a task."
        ),
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
        product_scaffold_preview=args.product_scaffold_preview,
        product_structure_preview=args.product_structure_preview,
        product_structure_apply=args.product_structure_apply,
        advance_design_derivation=args.advance_design_derivation,
        design_scaffold_preview=args.design_scaffold_preview,
        design_scaffold_apply=args.design_scaffold_apply,
        design_authoring_preview=args.design_authoring_preview,
        implementation_readiness_preview=args.implementation_readiness_preview,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
