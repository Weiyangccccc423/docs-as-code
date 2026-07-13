from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


WORKFLOW_PRESETS: dict[str, tuple[str, ...]] = {
    "init": (),
    "product-structure": (
        "advance_product_structuring",
        "product_scaffold_preview",
        "product_structure_preview",
        "product_structure_apply",
    ),
    "design-scaffold": (
        "advance_product_structuring",
        "product_scaffold_preview",
        "product_structure_preview",
        "product_structure_apply",
        "advance_design_derivation",
        "design_scaffold_preview",
        "design_scaffold_apply",
    ),
    "design-routing": (
        "advance_product_structuring",
        "product_scaffold_preview",
        "product_structure_preview",
        "product_structure_apply",
        "advance_design_derivation",
        "design_scaffold_preview",
        "design_scaffold_apply",
        "design_authoring_preview",
    ),
    "implementation-routing": (
        "advance_product_structuring",
        "product_scaffold_preview",
        "product_structure_preview",
        "product_structure_apply",
        "advance_design_derivation",
        "design_scaffold_preview",
        "design_scaffold_apply",
        "design_authoring_preview",
        "implementation_readiness_preview",
        "implementation_advance_preview",
        "implementation_advance_apply",
        "implementation_start_preview",
        "implementation_start_apply",
        "implementation_closeout_preview",
        "implementation_closeout_apply",
    ),
}


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
    implementation_advance_preview: bool = False,
    implementation_advance_apply: bool = False,
    implementation_start_preview: bool = False,
    implementation_start_apply: bool = False,
    implementation_closeout_preview: bool = False,
    implementation_closeout_apply: bool = False,
    workflow_preset: str = "",
    auto_repair_env: bool = False,
    strict_authority_skills: bool = False,
    strict_authority_provenance: bool = False,
    pack_root: Path = ROOT,
) -> dict[str, object]:
    pack_root = pack_root.resolve()
    target = target.resolve()
    product = product.resolve() if product is not None else None
    expanded_flags: tuple[str, ...] = ()
    steps: list[dict[str, object]] = []
    env_auto_repair: dict[str, object] = _empty_env_auto_repair(auto_repair_env)
    try:
        expanded_flags = _workflow_preset_flags(workflow_preset)
        advance_product_structuring = advance_product_structuring or "advance_product_structuring" in expanded_flags
        product_scaffold_preview = product_scaffold_preview or "product_scaffold_preview" in expanded_flags
        product_structure_preview = product_structure_preview or "product_structure_preview" in expanded_flags
        product_structure_apply = product_structure_apply or "product_structure_apply" in expanded_flags
        advance_design_derivation = advance_design_derivation or "advance_design_derivation" in expanded_flags
        design_scaffold_preview = design_scaffold_preview or "design_scaffold_preview" in expanded_flags
        design_scaffold_apply = design_scaffold_apply or "design_scaffold_apply" in expanded_flags
        design_authoring_preview = design_authoring_preview or "design_authoring_preview" in expanded_flags
        implementation_readiness_preview = (
            implementation_readiness_preview or "implementation_readiness_preview" in expanded_flags
        )
        implementation_advance_preview = (
            implementation_advance_preview or "implementation_advance_preview" in expanded_flags
        )
        implementation_advance_apply = implementation_advance_apply or "implementation_advance_apply" in expanded_flags
        implementation_start_preview = implementation_start_preview or "implementation_start_preview" in expanded_flags
        implementation_start_apply = implementation_start_apply or "implementation_start_apply" in expanded_flags
        implementation_closeout_preview = (
            implementation_closeout_preview or "implementation_closeout_preview" in expanded_flags
        )
        implementation_closeout_apply = implementation_closeout_apply or "implementation_closeout_apply" in expanded_flags

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

        authority_skill_inventory = _run_json(
            steps,
            "authority_skill_inventory",
            _authority_skill_argv(
                strict=strict_authority_skills,
                strict_provenance=strict_authority_provenance,
            ),
            pack_root,
            allowed_returncodes=(0, 1),
        )
        _require(
            authority_skill_inventory.get("ok") is True,
            "authority skill inventory failed",
            payload=authority_skill_inventory,
        )

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
            allowed_returncodes=(0, 1),
        )
        env_auto_repair = _maybe_auto_repair_env(
            steps,
            pack_root,
            target,
            env_check,
            auto_repair_env=auto_repair_env,
            check=check,
        )
        env_check = env_auto_repair["final_env_check"]
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
        _require(
            not implementation_advance_preview or implementation_readiness_preview,
            "--implementation-advance-preview requires --implementation-readiness-preview",
            payload=init_check,
        )
        _require(
            not implementation_advance_apply or implementation_advance_preview,
            "--implementation-advance-apply requires --implementation-advance-preview",
            payload=init_check,
        )
        _require(
            not implementation_start_preview or implementation_readiness_preview,
            "--implementation-start-preview requires --implementation-readiness-preview",
            payload=init_check,
        )
        _require(
            not implementation_start_apply or implementation_start_preview,
            "--implementation-start-apply requires --implementation-start-preview",
            payload=init_check,
        )
        _require(
            not implementation_closeout_preview or implementation_start_apply,
            "--implementation-closeout-preview requires --implementation-start-apply",
            payload=init_check,
        )
        _require(
            not implementation_closeout_apply or implementation_closeout_preview,
            "--implementation-closeout-apply requires --implementation-closeout-preview",
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
            "workflow_preset": workflow_preset,
            "workflow_preset_expanded_flags": list(expanded_flags),
            "auto_repair_env": auto_repair_env,
            "strict_authority_skills": strict_authority_skills,
            "strict_authority_provenance": strict_authority_provenance,
            "env_auto_repair": env_auto_repair,
            "work_package_generated": False,
            "work_package_ok": False,
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
            "implementation_advance_preview_requested": implementation_advance_preview,
            "implementation_advance_previewed": False,
            "implementation_advance_preview_ok": False,
            "implementation_advance_apply_requested": implementation_advance_apply,
            "implementation_advance_applied": False,
            "implementation_advance_apply_ok": False,
            "implementation_start_preview_requested": implementation_start_preview,
            "implementation_start_previewed": False,
            "implementation_start_preview_ok": False,
            "implementation_start_apply_requested": implementation_start_apply,
            "implementation_start_applied": False,
            "implementation_start_apply_ok": False,
            "implementation_closeout_preview_requested": implementation_closeout_preview,
            "implementation_closeout_previewed": False,
            "implementation_closeout_preview_ok": False,
            "implementation_closeout_apply_requested": implementation_closeout_apply,
            "implementation_closeout_applied": False,
            "implementation_closeout_apply_ok": False,
            "pack_manifest_verification": pack_manifest_verification,
            "pack_verification": pack_verification,
            "authority_skill_inventory": authority_skill_inventory,
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
                                            if implementation_advance_preview:
                                                advance_preview = _preview_implementation_advance(steps, target)
                                                payload["implementation_advance_previewed"] = True
                                                payload["implementation_advance_preview"] = advance_preview
                                                payload["implementation_advance_preview_ok"] = (
                                                    advance_preview.get("ok") is True
                                                )
                                                if implementation_advance_apply:
                                                    advance_apply = _apply_implementation_advance(
                                                        steps,
                                                        target,
                                                        advance_preview,
                                                    )
                                                    payload["implementation_advance_apply"] = advance_apply
                                                    payload["implementation_advance_applied"] = (
                                                        advance_apply.get("apply_skipped") is not True
                                                    )
                                                    payload["implementation_advance_apply_ok"] = (
                                                        advance_apply.get("ok") is True
                                                    )
                                                    if advance_apply.get("apply_skipped") is not True:
                                                        payload["implementation_plan"] = advance_apply[
                                                            "post_implementation_plan"
                                                        ]
                                                        payload["target_local"] = _target_local_details(
                                                            target=target,
                                                            init_payload=init_payload,
                                                            verify_payload=advance_apply["post_verify_check"],
                                                            status_payload=advance_apply["post_status"],
                                                            workflow_plan_payload=advance_apply["post_workflow_plan"],
                                                            expected_phase="implementation",
                                                        )
                                                        readiness_preview = advance_apply["implementation_readiness"]
                                            if implementation_start_preview:
                                                start_preview = _preview_implementation_start(
                                                    steps,
                                                    target,
                                                    readiness_preview,
                                                )
                                                payload["implementation_start_previewed"] = True
                                                payload["implementation_start_preview"] = start_preview
                                                payload["implementation_start_preview_ok"] = (
                                                    start_preview.get("ok") is True
                                                )
                                                if implementation_start_apply:
                                                    start_apply = _apply_implementation_start(
                                                        steps,
                                                        target,
                                                        start_preview,
                                                    )
                                                    payload["implementation_start_apply"] = start_apply
                                                    payload["implementation_start_applied"] = (
                                                        start_apply.get("apply_skipped") is not True
                                                    )
                                                    payload["implementation_start_apply_ok"] = (
                                                        start_apply.get("ok") is True
                                                    )
                                                    if start_apply.get("apply_skipped") is not True:
                                                        payload["implementation_plan"] = start_apply[
                                                            "post_implementation_plan"
                                                        ]
                                                        payload["target_local"] = _target_local_details(
                                                            target=target,
                                                            init_payload=init_payload,
                                                            verify_payload=start_apply["post_verify_check"],
                                                            status_payload=start_apply["post_status"],
                                                            workflow_plan_payload=start_apply["post_workflow_plan"],
                                                            expected_phase="implementation",
                                                        )
                                                    if implementation_closeout_preview:
                                                        closeout_preview = _preview_implementation_closeout(
                                                            steps,
                                                            target,
                                                            start_apply,
                                                        )
                                                        payload["implementation_closeout_previewed"] = True
                                                        payload["implementation_closeout_preview"] = closeout_preview
                                                        payload["implementation_closeout_preview_ok"] = (
                                                            closeout_preview.get("ok") is True
                                                        )
                                                        if implementation_closeout_apply:
                                                            closeout_apply = _apply_implementation_closeout(
                                                                steps,
                                                                target,
                                                                closeout_preview,
                                                            )
                                                            payload["implementation_closeout_apply"] = closeout_apply
                                                            payload["implementation_closeout_applied"] = (
                                                                closeout_apply.get("apply_skipped") is not True
                                                            )
                                                            payload["implementation_closeout_apply_ok"] = (
                                                                closeout_apply.get("ok") is True
                                                            )
                                                            if closeout_apply.get("apply_skipped") is not True:
                                                                payload["implementation_plan"] = closeout_apply[
                                                                    "post_implementation_plan"
                                                                ]
                                                                payload["target_local"] = _target_local_details(
                                                                    target=target,
                                                                    init_payload=init_payload,
                                                                    verify_payload=closeout_apply["post_verify_check"],
                                                                    status_payload=closeout_apply["post_status"],
                                                                    workflow_plan_payload=closeout_apply[
                                                                        "post_workflow_plan"
                                                                    ],
                                                                    expected_phase="implementation",
                                                                )
        work_package = _run_json(
            steps,
            "target_local_work_package",
            ["make", "work-package"],
            target,
        )
        _require(work_package.get("ok") is True, "target-local work package failed", payload=work_package)
        payload["work_package_generated"] = True
        payload["work_package_ok"] = True
        payload["work_package"] = work_package
        if isinstance(status_payload.get("local_commands"), list):
            payload["local_commands"] = status_payload["local_commands"]
        elif isinstance(init_payload.get("local_commands"), list):
            payload["local_commands"] = init_payload["local_commands"]
        if (
            isinstance(payload.get("implementation_closeout_apply"), dict)
            and payload["implementation_closeout_apply"].get("apply_skipped") is not True
        ):
            latest_status = payload["implementation_closeout_apply"].get("post_status")
        elif (
            isinstance(payload.get("implementation_start_apply"), dict)
            and payload["implementation_start_apply"].get("apply_skipped") is not True
        ):
            latest_status = payload["implementation_start_apply"].get("post_status")
        elif (
            isinstance(payload.get("implementation_advance_apply"), dict)
            and payload["implementation_advance_apply"].get("apply_skipped") is not True
        ):
            latest_status = payload["implementation_advance_apply"].get("post_status")
        elif isinstance(payload.get("design_derivation"), dict):
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
        failed_step = error.step if error.step is not None else (steps[-1] if steps else None)
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
            "workflow_preset": workflow_preset,
            "workflow_preset_expanded_flags": list(expanded_flags),
            "auto_repair_env": auto_repair_env,
            "strict_authority_skills": strict_authority_skills,
            "strict_authority_provenance": strict_authority_provenance,
            "env_auto_repair": env_auto_repair,
            "work_package_generated": False,
            "work_package_ok": False,
            "authority_skill_inventory": error.payload
            if error.message == "authority skill inventory failed" and error.payload is not None
            else {},
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
            "implementation_advance_preview_requested": implementation_advance_preview,
            "implementation_advance_previewed": False,
            "implementation_advance_preview_ok": False,
            "implementation_advance_apply_requested": implementation_advance_apply,
            "implementation_advance_applied": False,
            "implementation_advance_apply_ok": False,
            "implementation_start_preview_requested": implementation_start_preview,
            "implementation_start_previewed": False,
            "implementation_start_preview_ok": False,
            "implementation_start_apply_requested": implementation_start_apply,
            "implementation_start_applied": False,
            "implementation_start_apply_ok": False,
            "implementation_closeout_preview_requested": implementation_closeout_preview,
            "implementation_closeout_previewed": False,
            "implementation_closeout_preview_ok": False,
            "implementation_closeout_apply_requested": implementation_closeout_apply,
            "implementation_closeout_applied": False,
            "implementation_closeout_apply_ok": False,
            "steps": steps,
            "failed_step": failed_step,
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
            "workflow_preset": workflow_preset,
            "workflow_preset_expanded_flags": list(expanded_flags),
            "auto_repair_env": auto_repair_env,
            "strict_authority_skills": strict_authority_skills,
            "strict_authority_provenance": strict_authority_provenance,
            "env_auto_repair": env_auto_repair,
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
            "implementation_advance_preview_requested": implementation_advance_preview,
            "implementation_advance_previewed": False,
            "implementation_advance_preview_ok": False,
            "implementation_advance_apply_requested": implementation_advance_apply,
            "implementation_advance_applied": False,
            "implementation_advance_apply_ok": False,
            "implementation_start_preview_requested": implementation_start_preview,
            "implementation_start_previewed": False,
            "implementation_start_preview_ok": False,
            "implementation_start_apply_requested": implementation_start_apply,
            "implementation_start_applied": False,
            "implementation_start_apply_ok": False,
            "implementation_closeout_preview_requested": implementation_closeout_preview,
            "implementation_closeout_previewed": False,
            "implementation_closeout_preview_ok": False,
            "implementation_closeout_apply_requested": implementation_closeout_apply,
            "implementation_closeout_applied": False,
            "implementation_closeout_apply_ok": False,
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


def _authority_skill_argv(*, strict: bool, strict_provenance: bool) -> list[str | Path]:
    argv: list[str | Path] = [
        sys.executable,
        "scripts/authority_skills.py",
        "--repair",
        "--check",
        "--json",
    ]
    if strict:
        argv.append("--strict")
    if strict_provenance:
        argv.append("--strict-provenance")
    return argv


def _empty_env_auto_repair(auto_repair_env: bool) -> dict[str, object]:
    return {
        "ok": False,
        "requested": auto_repair_env,
        "applied": False,
        "skipped": False,
        "skip_reason": "",
        "decision": "",
        "status": "",
        "stop_before_workflow": False,
        "can_continue": False,
        "can_auto_apply": False,
        "requires_approval": False,
        "manual_repair_required": False,
        "runnable_action_ids": [],
        "approval_action_ids": [],
        "manual_action_ids": [],
        "next_step": "",
        "final_env_check_ok": False,
        "final_missing_required": [],
        "initial_check": {},
        "repair": {},
        "post_check": {},
        "final_env_check": {},
    }


def _maybe_auto_repair_env(
    steps: list[dict[str, object]],
    pack_root: Path,
    target: Path,
    env_check: dict[str, object],
    *,
    auto_repair_env: bool,
    check: bool,
) -> dict[str, object]:
    payload = _empty_env_auto_repair(auto_repair_env)
    payload["initial_check"] = env_check
    payload["final_env_check"] = env_check
    _refresh_env_auto_repair_summary(payload, env_check)
    if not auto_repair_env:
        payload["skipped"] = True
        payload["skip_reason"] = "automatic environment repair was not requested"
        payload["decision"] = "auto_repair_not_requested"
        payload["status"] = "not_requested"
        payload["can_auto_apply"] = False
        if not payload["can_continue"]:
            payload["stop_before_workflow"] = True
            payload["next_step"] = "rerun with --auto-repair-env or repair environment manually"
        payload["ok"] = payload["final_env_check_ok"] is True
        return payload
    if check:
        payload["skipped"] = True
        payload["skip_reason"] = "check mode must not write environment repairs"
        payload["decision"] = "check_mode_no_repair"
        payload["status"] = "check_mode"
        payload["can_auto_apply"] = False
        if not payload["can_continue"]:
            payload["stop_before_workflow"] = True
            payload["next_step"] = "rerun without --check or repair environment manually"
        payload["ok"] = payload["final_env_check_ok"] is True
        return payload
    if _env_check_allows_workflow(env_check):
        payload["skipped"] = True
        payload["skip_reason"] = "environment already satisfies workflow requirements"
        payload["ok"] = True
        return payload
    if not _env_check_allows_auto_repair(env_check):
        payload["skipped"] = True
        payload["skip_reason"] = _env_auto_repair_skip_reason(payload)
        payload["ok"] = False
        return payload

    repair = _run_json(
        steps,
        "env_repair_auto_apply",
        [
            sys.executable,
            "scripts/governance_cli.py",
            "env",
            "--repair",
            "--target",
            target,
            "--json",
        ],
        pack_root,
        allowed_returncodes=(0, 1),
    )
    post_check = _run_json(
        steps,
        "env_repair_check_after_auto_repair",
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
        allowed_returncodes=(0, 1),
    )
    payload["applied"] = True
    payload["repair"] = repair
    payload["post_check"] = post_check
    payload["final_env_check"] = post_check
    _refresh_env_auto_repair_summary(payload, post_check)
    payload["ok"] = payload["final_env_check_ok"] is True
    return payload


def _refresh_env_auto_repair_summary(payload: dict[str, object], env_check: dict[str, object]) -> None:
    decision = _mapping(env_check.get("repair_decision"))
    execution = _mapping(env_check.get("repair_execution"))
    final_missing_required = _string_list(env_check.get("missing_required"))
    final_env_check_ok = env_check.get("ok") is True and final_missing_required == []
    repair_decision = _string_value(decision.get("decision"))
    repair_status = _string_value(decision.get("status")) or _string_value(execution.get("status"))
    if not repair_decision and final_env_check_ok:
        repair_decision = "continue_workflow"
    if not repair_status and final_env_check_ok:
        repair_status = "continue"
    runnable_action_ids = _string_list(decision.get("runnable_action_ids"))
    approval_action_ids = _string_list(decision.get("approval_action_ids"))
    manual_action_ids = _string_list(decision.get("manual_action_ids"))
    can_continue = decision.get("can_continue") is True or execution.get("can_continue") is True or final_env_check_ok
    can_auto_apply = decision.get("can_auto_apply") is True or execution.get("can_auto_apply") is True
    requires_approval = decision.get("requires_approval") is True or bool(approval_action_ids)
    manual_repair_required = decision.get("manual_repair_required") is True or bool(manual_action_ids)
    stop_before_workflow = (
        decision.get("stop_before_workflow") is True
        or not can_continue
        or requires_approval
        or manual_repair_required
    )
    next_step = _string_value(decision.get("next_step")) or _string_value(execution.get("next_step"))
    if not next_step:
        next_step = _env_auto_repair_next_step(repair_decision, repair_status, final_env_check_ok)
    payload.update(
        {
            "decision": repair_decision,
            "status": repair_status,
            "stop_before_workflow": stop_before_workflow,
            "can_continue": can_continue,
            "can_auto_apply": can_auto_apply,
            "requires_approval": requires_approval,
            "manual_repair_required": manual_repair_required,
            "runnable_action_ids": runnable_action_ids,
            "approval_action_ids": approval_action_ids,
            "manual_action_ids": manual_action_ids,
            "next_step": next_step,
            "final_env_check_ok": final_env_check_ok,
            "final_missing_required": final_missing_required,
            "ok": final_env_check_ok,
        }
    )


def _env_auto_repair_skip_reason(payload: dict[str, object]) -> str:
    if payload.get("requires_approval") is True:
        return "environment repair requires approval"
    if payload.get("manual_repair_required") is True:
        return "environment repair requires manual action"
    if payload.get("can_auto_apply") is not True:
        return "environment repair is not auto-applicable"
    return "environment repair requires approval or manual action"


def _env_auto_repair_next_step(decision: str, status: str, final_env_check_ok: bool) -> str:
    if decision == "continue_workflow" or final_env_check_ok:
        return "continue workflow"
    if decision == "run_repair_actions" or status == "ready_to_apply":
        return "run repair_commands[].argv from repair_commands[].cwd"
    if decision == "request_approval" or status == "approval_required":
        return "request approval before running repair_commands"
    if decision == "complete_manual_repairs" or status == "manual_repair_required":
        return "complete manual_repairs before continuing"
    if decision == "inspect_install_failure" or status == "install_failed":
        return "inspect install_results and repair package-manager failure"
    if decision == "inspect_unresolved_tools" or status == "applied_but_unresolved":
        return "inspect post-repair missing tools before retrying package-manager repair"
    if decision == "fix_repair_error" or status == "blocked_by_error":
        return "fix reported environment repair error"
    return "inspect environment repair payload"


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _env_check_allows_workflow(env_check: dict[str, object]) -> bool:
    return env_check.get("ok") is True and env_check.get("missing_required") == []


def _env_check_allows_auto_repair(env_check: dict[str, object]) -> bool:
    repair_decision = env_check.get("repair_decision")
    repair_execution = env_check.get("repair_execution")
    if not isinstance(repair_decision, dict) or not isinstance(repair_execution, dict):
        return False
    return (
        repair_decision.get("decision") == "run_repair_actions"
        and repair_decision.get("requires_approval") is not True
        and repair_decision.get("manual_repair_required") is not True
        and repair_decision.get("approval_action_ids") == []
        and repair_decision.get("manual_action_ids") == []
        and repair_execution.get("can_auto_apply") is True
    )


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
    queue_summaries, authoring_summary, active_work = _summarize_design_authoring(queues)
    return {
        "ok": ok,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": "design-derivation",
        "queue_order": [queue_id for queue_id, _step_id in DESIGN_AUTHORING_QUEUE_IDS],
        "queue_summaries": queue_summaries,
        "authoring_summary": authoring_summary,
        "active_work": active_work,
        "queues": queues,
    }


def _summarize_design_authoring(
    queues: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object]]:
    queue_summaries: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    for sequence, (queue_id, _step_id) in enumerate(DESIGN_AUTHORING_QUEUE_IDS, start=1):
        queue = queues.get(queue_id)
        queue_payload = queue if isinstance(queue, dict) else {}
        summary = queue_payload.get("authoring_summary")
        summary_payload = summary if isinstance(summary, dict) else {}
        active = queue_payload.get("active_work")
        active_payload = active if isinstance(active, dict) else {}
        queue_ok = queue_payload.get("ok") is True
        if not queue_ok:
            status = "error"
        elif active_payload:
            status = str(active_payload.get("status", "unknown") or "unknown")
        else:
            status = "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        queue_summaries.append(
            {
                "sequence": sequence,
                "queue_id": queue_id,
                "ok": queue_ok,
                "status": status,
                "task_count": _non_negative_int(summary_payload.get("task_count")),
                "open_decision_count": _non_negative_int(summary_payload.get("open_decision_count")),
                "non_satisfied_required_link_count": _non_negative_int(
                    summary_payload.get("non_satisfied_required_link_count")
                ),
                "link_repair_action_count": _non_negative_int(
                    summary_payload.get("link_repair_action_count")
                ),
                "primary_skill": str(active_payload.get("primary_skill", "")),
                "primary_specialist_skill": str(active_payload.get("primary_specialist_skill", "")),
                "active_work": active_payload,
            }
        )

    next_queue = next(
        (summary for summary in queue_summaries if summary["status"] not in {"ready", "complete"}),
        None,
    )
    if next_queue is None:
        active_work: dict[str, object] = {
            "kind": "design-authoring-queue",
            "status": "complete",
            "queue_id": "",
            "queue_sequence": 0,
            "blocker_count": 0,
            "open_decision_count": 0,
            "next_repair_action": {},
        }
        next_queue_id = ""
    else:
        queue_active = next_queue.get("active_work")
        active_work = dict(queue_active) if isinstance(queue_active, dict) else {}
        active_work.update(
            {
                "status": next_queue["status"],
                "queue_id": next_queue["queue_id"],
                "queue_sequence": next_queue["sequence"],
                "queue_ok": next_queue["ok"],
            }
        )
        next_queue_id = str(next_queue["queue_id"])

    authoring_summary: dict[str, object] = {
        "queue_count": len(queue_summaries),
        "blocked_queue_count": sum(
            1
            for summary in queue_summaries
            if summary["status"] not in {"ready", "complete", "decision_required"}
        ),
        "decision_required_queue_count": sum(
            1 for summary in queue_summaries if summary["status"] == "decision_required"
        ),
        "ready_queue_count": sum(
            1 for summary in queue_summaries if summary["status"] in {"ready", "complete"}
        ),
        "queue_status_counts": dict(sorted(status_counts.items())),
        "total_task_count": sum(int(summary["task_count"]) for summary in queue_summaries),
        "total_open_decision_count": sum(
            int(summary["open_decision_count"]) for summary in queue_summaries
        ),
        "total_non_satisfied_required_link_count": sum(
            int(summary["non_satisfied_required_link_count"]) for summary in queue_summaries
        ),
        "total_link_repair_action_count": sum(
            int(summary["link_repair_action_count"]) for summary in queue_summaries
        ),
        "next_queue_id": next_queue_id,
        "next_active_work": active_work,
    }
    return queue_summaries, authoring_summary, active_work


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


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
    blockers = _implementation_readiness_blockers(verify_check, gate, implementation_plan)
    source_counts = {
        source: sum(1 for blocker in blockers if blocker.get("source") == source)
        for source in ("verify_check", "implementation_gate", "implementation_plan")
    }
    blocker_codes = list(dict.fromkeys(str(blocker.get("code", "")) for blocker in blockers if blocker.get("code")))
    next_blocker = dict(blockers[0]) if blockers else {}
    readiness_summary = {
        "blocked": not readiness_ok,
        "blocker_count": len(blockers),
        "blocker_codes": blocker_codes,
        "source_counts": source_counts,
        "next_blocker": next_blocker,
    }
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
        "readiness_summary": readiness_summary,
        "blockers": blockers,
        "next_blocker": next_blocker,
        "next_repair_action": dict(next_blocker),
        "verify_check": verify_check,
        "gate": gate,
        "implementation_plan": implementation_plan,
    }


def _implementation_readiness_blockers(
    verify_check: dict[str, object],
    gate: dict[str, object],
    implementation_plan: dict[str, object],
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()

    def append(
        source: str,
        code: str,
        path: str,
        detail: str,
        repair_strategy: str,
    ) -> None:
        normalized_code = code.strip()
        normalized_path = path.strip()
        normalized_detail = detail.strip()
        if not normalized_code or not normalized_detail:
            return
        identity = (normalized_code, normalized_path, normalized_detail)
        if identity in seen:
            return
        seen.add(identity)
        blockers.append(
            {
                "sequence": len(blockers) + 1,
                "source": source,
                "code": normalized_code,
                "path": normalized_path,
                "detail": normalized_detail,
                "repair_strategy": repair_strategy,
            }
        )

    findings = verify_check.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            append(
                "verify_check",
                _string_value(finding.get("code")) or "governance_verification_finding",
                _string_value(finding.get("path")),
                _string_value(finding.get("message")) or _string_value(finding.get("detail")),
                _string_value(finding.get("repair_strategy"))
                or "repair_governance_verification_finding_before_implementation",
            )
    if verify_check.get("ok") is not True and not any(
        blocker.get("source") == "verify_check" for blocker in blockers
    ):
        append(
            "verify_check",
            "governance_verification_failed",
            "",
            "governance verification did not pass before implementation",
            "inspect_verify_check_findings_and_repair_before_implementation",
        )

    requirements = gate.get("requirements")
    if isinstance(requirements, list):
        for requirement in requirements:
            if not isinstance(requirement, dict) or requirement.get("ok") is True:
                continue
            append(
                "implementation_gate",
                _string_value(requirement.get("code")) or "implementation_gate_requirement_failed",
                _string_value(requirement.get("path")),
                _string_value(requirement.get("message")) or "implementation gate requirement failed",
                _string_value(requirement.get("repair_strategy"))
                or "repair_failed_implementation_gate_requirement_before_implementation",
            )
    if gate.get("ok") is not True and not any(
        blocker.get("source") == "implementation_gate" for blocker in blockers
    ):
        append(
            "implementation_gate",
            "implementation_gate_failed",
            "",
            "implementation gate did not pass",
            "inspect_gate_requirements_and_repair_before_implementation",
        )

    active_work = implementation_plan.get("active_work")
    next_repair_action = active_work.get("next_repair_action") if isinstance(active_work, dict) else {}
    if isinstance(next_repair_action, dict) and next_repair_action:
        append(
            "implementation_plan",
            _string_value(next_repair_action.get("code")) or "implementation_plan_repair_required",
            _string_value(next_repair_action.get("path")),
            _string_value(next_repair_action.get("detail"))
            or _string_value(next_repair_action.get("message"))
            or "implementation plan requires repair before execution",
            _string_value(next_repair_action.get("repair_strategy"))
            or "follow_implementation_plan_next_repair_action",
        )
    errors = implementation_plan.get("errors")
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, str) and error.strip():
                append(
                    "implementation_plan",
                    "implementation_plan_error",
                    "",
                    error,
                    "repair_implementation_plan_precondition_before_execution",
                )
    if implementation_plan.get("ok") is not True and not any(
        blocker.get("source") == "implementation_plan" for blocker in blockers
    ):
        append(
            "implementation_plan",
            "implementation_plan_failed",
            "",
            "implementation plan did not pass",
            "inspect_implementation_plan_errors_and_active_work_before_execution",
        )
    return blockers


def _preview_implementation_advance(steps: list[dict[str, object]], target: Path) -> dict[str, object]:
    advance_check = _run_json(
        steps,
        "target_local_implementation_advance_preview",
        ["bin/governance", "advance", "implementation", ".", "--check", "--json"],
        target,
        allowed_returncodes=(0, 1),
    )
    return {
        "ok": True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": str(advance_check.get("phase", "implementation")),
        "advance_ready": advance_check.get("ok") is True and advance_check.get("would_advance") is True,
        "advance_check_ok": advance_check.get("ok") is True,
        "would_advance": advance_check.get("would_advance") is True,
        "advanced": advance_check.get("advanced") is True,
        "advance_check": advance_check,
    }


def _apply_implementation_advance(
    steps: list[dict[str, object]],
    target: Path,
    advance_preview: dict[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": False,
        "writes_state": True,
        "phase": "implementation",
        "advance_ready": advance_preview.get("advance_ready") is True,
        "apply_skipped": False,
        "skip_code": "",
        "blocked_by": "",
        "required_preview_ready": advance_preview.get("advance_ready") is True,
        "skip_reason": "",
        "advance": {},
        "post_verify_check": {},
        "post_status": {},
        "post_workflow_plan": {},
        "post_implementation_plan": {},
        "implementation_readiness": {},
    }
    if advance_preview.get("advance_ready") is not True:
        payload["apply_skipped"] = True
        payload["skip_code"] = "advance_preview_not_ready"
        payload["blocked_by"] = "implementation_advance_preview"
        payload["required_preview_ready"] = False
        payload["skip_reason"] = "implementation advance preview did not pass"
        return payload

    advance = _run_json(
        steps,
        "target_local_implementation_advance_apply",
        ["bin/governance", "advance", "implementation", ".", "--json"],
        target,
    )
    _require(advance.get("ok") is True, "implementation advance apply failed", payload=advance)
    post_verify_check = _run_json(
        steps,
        "target_local_verify_check_after_implementation_advance_apply",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    post_status = _run_json(
        steps,
        "target_local_governance_status_after_implementation_advance_apply",
        ["make", "governance-status"],
        target,
    )
    post_workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_after_implementation_advance_apply",
        ["make", "workflow-plan"],
        target,
    )
    post_implementation_plan = _run_json(
        steps,
        "target_local_implementation_plan_after_implementation_advance_apply",
        ["make", "implementation-plan"],
        target,
    )
    implementation_readiness = _preview_implementation_readiness(steps, target)
    status_state = post_status.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else ""
    payload.update(
        {
            "phase": phase,
            "advance": advance,
            "post_verify_check": post_verify_check,
            "post_status": post_status,
            "post_workflow_plan": post_workflow_plan,
            "post_implementation_plan": post_implementation_plan,
            "implementation_readiness": implementation_readiness,
            "ok": (
                advance.get("ok") is True
                and post_verify_check.get("ok") is True
                and post_verify_check.get("findings") == []
                and post_status.get("ok") is True
                and post_workflow_plan.get("ok") is True
                and post_workflow_plan.get("phase") == "implementation"
                and post_implementation_plan.get("ok") is True
                and implementation_readiness.get("readiness_ok") is True
                and phase == "implementation"
            ),
        }
    )
    return payload


TASK_ID_PATTERN = re.compile(r"^TASK-\d{3}$")


def _preview_implementation_start(
    steps: list[dict[str, object]],
    target: Path,
    readiness_preview: dict[str, object],
) -> dict[str, object]:
    implementation_plan = readiness_preview.get("implementation_plan")
    active_work = implementation_plan.get("active_work") if isinstance(implementation_plan, dict) else {}
    task_id = active_work.get("task_id") if isinstance(active_work, dict) else ""
    normalized_task_id = task_id if isinstance(task_id, str) else ""
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": str(readiness_preview.get("phase", "")),
        "source": "implementation_readiness_preview.implementation_plan.active_work.task_id",
        "task_id": normalized_task_id,
        "start_ready": False,
        "preview_skipped": False,
        "skip_code": "",
        "blocked_by": "",
        "required_readiness_ok": readiness_preview.get("readiness_ok") is True,
        "skip_reason": "",
        "implementation_start": {},
    }
    if readiness_preview.get("readiness_ok") is not True:
        payload["preview_skipped"] = True
        payload["skip_code"] = "readiness_preview_not_ready"
        payload["blocked_by"] = "implementation_readiness_preview"
        payload["required_readiness_ok"] = False
        payload["skip_reason"] = "implementation readiness preview did not pass"
        return payload
    if not TASK_ID_PATTERN.match(normalized_task_id):
        payload["preview_skipped"] = True
        payload["skip_code"] = "active_task_id_missing"
        payload["blocked_by"] = "implementation_plan.active_work.task_id"
        payload["skip_reason"] = "implementation plan did not expose a concrete active_work.task_id"
        return payload

    implementation_start = _run_json(
        steps,
        "target_local_implementation_start_preview",
        ["bin/governance", "implementation", "start", ".", "--task", normalized_task_id, "--json"],
        target,
        allowed_returncodes=(0, 1),
    )
    payload["implementation_start"] = implementation_start
    payload["start_ready"] = implementation_start.get("start_ready") is True
    return payload


def _apply_implementation_start(
    steps: list[dict[str, object]],
    target: Path,
    start_preview: dict[str, object],
) -> dict[str, object]:
    task_id = str(start_preview.get("task_id", ""))
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": False,
        "writes_state": True,
        "phase": str(start_preview.get("phase", "")),
        "task_id": task_id,
        "start_ready": start_preview.get("start_ready") is True,
        "apply_skipped": False,
        "skip_code": "",
        "blocked_by": "",
        "required_preview_ready": start_preview.get("start_ready") is True,
        "skip_reason": "",
        "implementation_start_apply": {},
        "post_verify_check": {},
        "post_status": {},
        "post_workflow_plan": {},
        "post_implementation_plan": {},
    }
    if start_preview.get("start_ready") is not True:
        payload["apply_skipped"] = True
        payload["skip_code"] = "start_preview_not_ready"
        payload["blocked_by"] = "implementation_start_preview"
        payload["required_preview_ready"] = False
        payload["skip_reason"] = "implementation start preview did not pass"
        return payload
    if TASK_ID_PATTERN.match(task_id) is None:
        payload["apply_skipped"] = True
        payload["skip_code"] = "task_id_missing"
        payload["blocked_by"] = "implementation_start_preview.task_id"
        payload["skip_reason"] = "implementation start preview did not expose a concrete task_id"
        return payload

    implementation_start_apply = _run_json(
        steps,
        "target_local_implementation_start_apply",
        ["bin/governance", "implementation", "start", ".", "--task", task_id, "--apply", "--json"],
        target,
    )
    _require(
        implementation_start_apply.get("ok") is True,
        "implementation start apply failed",
        payload=implementation_start_apply,
    )
    post_verify_check = _run_json(
        steps,
        "target_local_verify_check_after_implementation_start_apply",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    post_status = _run_json(
        steps,
        "target_local_governance_status_after_implementation_start_apply",
        ["make", "governance-status"],
        target,
    )
    post_workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_after_implementation_start_apply",
        ["make", "workflow-plan"],
        target,
    )
    post_implementation_plan = _run_json(
        steps,
        "target_local_implementation_plan_after_implementation_start_apply",
        ["make", "implementation-plan"],
        target,
    )
    status_state = post_status.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else ""
    active_work = post_implementation_plan.get("active_work")
    active_status = active_work.get("status") if isinstance(active_work, dict) else ""
    payload.update(
        {
            "phase": phase,
            "implementation_start_apply": implementation_start_apply,
            "post_verify_check": post_verify_check,
            "post_status": post_status,
            "post_workflow_plan": post_workflow_plan,
            "post_implementation_plan": post_implementation_plan,
            "ok": (
                implementation_start_apply.get("ok") is True
                and implementation_start_apply.get("apply_requested") is True
                and (
                    implementation_start_apply.get("applied") is True
                    or implementation_start_apply.get("already_current") is True
                )
                and post_verify_check.get("ok") is True
                and post_verify_check.get("findings") == []
                and post_status.get("ok") is True
                and post_workflow_plan.get("ok") is True
                and post_workflow_plan.get("phase") == "implementation"
                and post_implementation_plan.get("ok") is True
                and active_status == "in_progress"
                and phase == "implementation"
            ),
        }
    )
    return payload


def _preview_implementation_closeout(
    steps: list[dict[str, object]],
    target: Path,
    start_apply: dict[str, object],
) -> dict[str, object]:
    post_implementation_plan = start_apply.get("post_implementation_plan")
    active_work = post_implementation_plan.get("active_work") if isinstance(post_implementation_plan, dict) else {}
    task_id = active_work.get("task_id") if isinstance(active_work, dict) else ""
    normalized_task_id = task_id if isinstance(task_id, str) else ""
    post_status = start_apply.get("post_status")
    status_state = post_status.get("state") if isinstance(post_status, dict) else {}
    phase = status_state.get("phase") if isinstance(status_state, dict) else start_apply.get("phase", "")
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": True,
        "writes_state": False,
        "phase": str(phase),
        "source": "implementation_start_apply.post_implementation_plan.active_work.task_id",
        "task_id": normalized_task_id,
        "closeout_ready": False,
        "preview_skipped": False,
        "skip_code": "",
        "blocked_by": "",
        "required_start_applied": (
            start_apply.get("ok") is True and start_apply.get("apply_skipped") is not True
        ),
        "skip_reason": "",
        "implementation_closeout": {},
    }
    if start_apply.get("ok") is not True or start_apply.get("apply_skipped") is True:
        payload["preview_skipped"] = True
        payload["skip_code"] = "start_apply_not_applied"
        payload["blocked_by"] = "implementation_start_apply"
        payload["required_start_applied"] = False
        payload["skip_reason"] = "implementation start apply did not pass"
        return payload
    if TASK_ID_PATTERN.match(normalized_task_id) is None:
        payload["preview_skipped"] = True
        payload["skip_code"] = "active_task_id_missing"
        payload["blocked_by"] = "implementation_plan.active_work.task_id"
        payload["skip_reason"] = "implementation plan did not expose a concrete active_work.task_id"
        return payload

    implementation_closeout = _run_json(
        steps,
        "target_local_implementation_closeout_preview",
        ["bin/governance", "implementation", "closeout", ".", "--task", normalized_task_id, "--json"],
        target,
        allowed_returncodes=(0, 1),
    )
    payload["implementation_closeout"] = implementation_closeout
    payload["closeout_ready"] = implementation_closeout.get("closeout_ready") is True
    return payload


def _apply_implementation_closeout(
    steps: list[dict[str, object]],
    target: Path,
    closeout_preview: dict[str, object],
) -> dict[str, object]:
    task_id = str(closeout_preview.get("task_id", ""))
    payload: dict[str, object] = {
        "ok": True,
        "target": str(target),
        "check": False,
        "writes_state": True,
        "phase": str(closeout_preview.get("phase", "")),
        "task_id": task_id,
        "closeout_ready": closeout_preview.get("closeout_ready") is True,
        "apply_skipped": False,
        "skip_code": "",
        "blocked_by": "",
        "required_preview_ready": closeout_preview.get("closeout_ready") is True,
        "skip_reason": "",
        "implementation_closeout_apply": {},
        "post_verify_check": {},
        "post_status": {},
        "post_workflow_plan": {},
        "post_implementation_plan": {},
    }
    if closeout_preview.get("closeout_ready") is not True:
        payload["apply_skipped"] = True
        payload["skip_code"] = "closeout_preview_not_ready"
        payload["blocked_by"] = "implementation_closeout_preview"
        payload["required_preview_ready"] = False
        payload["skip_reason"] = "implementation closeout preview did not pass"
        return payload
    if TASK_ID_PATTERN.match(task_id) is None:
        payload["apply_skipped"] = True
        payload["skip_code"] = "task_id_missing"
        payload["blocked_by"] = "implementation_closeout_preview.task_id"
        payload["skip_reason"] = "implementation closeout preview did not expose a concrete task_id"
        return payload

    implementation_closeout_apply = _run_json(
        steps,
        "target_local_implementation_closeout_apply",
        ["bin/governance", "implementation", "closeout", ".", "--task", task_id, "--apply", "--json"],
        target,
    )
    _require(
        implementation_closeout_apply.get("ok") is True,
        "implementation closeout apply failed",
        payload=implementation_closeout_apply,
    )
    post_verify_check = _run_json(
        steps,
        "target_local_verify_check_after_implementation_closeout_apply",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    post_status = _run_json(
        steps,
        "target_local_governance_status_after_implementation_closeout_apply",
        ["make", "governance-status"],
        target,
    )
    post_workflow_plan = _run_json(
        steps,
        "target_local_workflow_plan_after_implementation_closeout_apply",
        ["make", "workflow-plan"],
        target,
    )
    post_implementation_plan = _run_json(
        steps,
        "target_local_implementation_plan_after_implementation_closeout_apply",
        ["make", "implementation-plan"],
        target,
    )
    status_state = post_status.get("state")
    phase = status_state.get("phase") if isinstance(status_state, dict) else ""
    active_work = post_implementation_plan.get("active_work")
    active_status = active_work.get("status") if isinstance(active_work, dict) else ""
    payload.update(
        {
            "phase": phase,
            "implementation_closeout_apply": implementation_closeout_apply,
            "post_verify_check": post_verify_check,
            "post_status": post_status,
            "post_workflow_plan": post_workflow_plan,
            "post_implementation_plan": post_implementation_plan,
            "ok": (
                implementation_closeout_apply.get("ok") is True
                and implementation_closeout_apply.get("apply_requested") is True
                and (
                    implementation_closeout_apply.get("applied") is True
                    or implementation_closeout_apply.get("already_current") is True
                )
                and post_verify_check.get("ok") is True
                and post_verify_check.get("findings") == []
                and post_status.get("ok") is True
                and post_workflow_plan.get("ok") is True
                and post_workflow_plan.get("phase") == "implementation"
                and post_implementation_plan.get("ok") is True
                and active_status == "complete"
                and phase == "implementation"
            ),
        }
    )
    return payload


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


def _workflow_preset_flags(workflow_preset: str) -> tuple[str, ...]:
    if not workflow_preset:
        return ()
    if workflow_preset not in WORKFLOW_PRESETS:
        raise ConsumerBootstrapError(f"unknown workflow preset: {workflow_preset}")
    return WORKFLOW_PRESETS[workflow_preset]


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
        "--workflow-preset",
        choices=sorted(WORKFLOW_PRESETS),
        default="",
        help=(
            "Expand a named workflow preset into existing bootstrap flags. Presets never bypass the normal "
            "phase dependency and write-safety checks."
        ),
    )
    parser.add_argument(
        "--auto-repair-env",
        action="store_true",
        help=(
            "After env --repair --check, run write-mode env repair and recheck only when repair_decision "
            "allows non-approval automatic repair. Ignored in --check mode."
        ),
    )
    parser.add_argument(
        "--strict-authority-skills",
        action="store_true",
        help=(
            "Run authority_skills.py in strict mode before environment and target initialization checks; missing "
            "agent-environment specialist skills stop bootstrap."
        ),
    )
    parser.add_argument(
        "--strict-authority-provenance",
        action="store_true",
        help=(
            "Require every authority-routing skill to match an approved immutable source lock before environment "
            "and target initialization checks."
        ),
    )
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
    parser.add_argument(
        "--implementation-advance-preview",
        action="store_true",
        help=(
            "With --implementation-readiness-preview, run read-only advance implementation --check and return "
            "phase-transition blockers without recording the implementation phase."
        ),
    )
    parser.add_argument(
        "--implementation-advance-apply",
        action="store_true",
        help=(
            "With --implementation-advance-preview, record the implementation phase only when the advance "
            "preflight passed, then refresh implementation routing payloads."
        ),
    )
    parser.add_argument(
        "--implementation-start-preview",
        action="store_true",
        help=(
            "With --implementation-readiness-preview, run a read-only implementation start check for the "
            "selected TASK-NNN without applying task status updates."
        ),
    )
    parser.add_argument(
        "--implementation-start-apply",
        action="store_true",
        help=(
            "With --implementation-start-preview, apply the safe implementation start status update only when "
            "the start preview passed, then refresh implementation routing payloads."
        ),
    )
    parser.add_argument(
        "--implementation-closeout-preview",
        action="store_true",
        help=(
            "With --implementation-start-apply, run a read-only implementation closeout check for the selected "
            "TASK-NNN without applying Done status updates."
        ),
    )
    parser.add_argument(
        "--implementation-closeout-apply",
        action="store_true",
        help=(
            "With --implementation-closeout-preview, apply the safe implementation closeout status update only "
            "when closeout evidence passed, then refresh implementation routing payloads."
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
        implementation_advance_preview=args.implementation_advance_preview,
        implementation_advance_apply=args.implementation_advance_apply,
        implementation_start_preview=args.implementation_start_preview,
        implementation_start_apply=args.implementation_start_apply,
        implementation_closeout_preview=args.implementation_closeout_preview,
        implementation_closeout_apply=args.implementation_closeout_apply,
        workflow_preset=args.workflow_preset,
        auto_repair_env=args.auto_repair_env,
        strict_authority_skills=args.strict_authority_skills,
        strict_authority_provenance=args.strict_authority_provenance,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
