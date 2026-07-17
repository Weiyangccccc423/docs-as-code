from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR_NAME = "docs-as-code-workflow-pack"
TARGET_LOCAL_MAKE_STEP_IDS = [
    "make_verify_governance",
    "make_verify_check",
    "make_governance_status",
    "make_workflow_plan_initialized",
    "make_work_package_initialized",
    "make_workflow_resume_initialized",
    "make_workflow_plan_product_structuring",
    "make_work_package_product_structuring",
    "make_workflow_resume_product_structuring",
    "make_workflow_plan_design_derivation",
    "make_work_package_design_derivation",
    "make_workflow_resume_design_derivation",
    "make_work_package_design_complete",
    "make_workflow_plan_implementation",
    "make_work_package_implementation",
    "make_workflow_resume_implementation",
    "make_work_package_complete_after_runtime_refresh",
    "make_workflow_resume_complete_after_runtime_refresh",
    "make_product_plan",
    "make_design_plan",
    "make_implementation_plan",
    "make_implementation_run_check",
    "make_check_env",
    "make_repair_env_check",
]
DESIGN_AUTHORING_QUEUE_IDS = [
    "architecture-authoring",
    "api-authoring",
    "backend-authoring",
    "data-model-authoring",
    "ui-interaction-authoring",
    "frontend-authoring",
    "test-strategy-authoring",
    "implementation-planning-authoring",
    "architecture-decisions-authoring",
]


class ArtifactSmokeError(Exception):
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
    step = {
        "id": step_id,
        "argv": command,
        "cwd": str(cwd),
        "returncode": result.returncode,
        "expected_returncode": expected_returncode,
    }
    steps.append(step)
    if result.returncode != expected_returncode:
        failed = {**step, "stdout": result.stdout, "stderr": result.stderr}
        raise ArtifactSmokeError(f"step failed: {step_id}", step=failed)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        failed = {**step, "stdout": result.stdout, "stderr": result.stderr}
        raise ArtifactSmokeError(f"step did not return JSON: {step_id}: {error}", step=failed) from error
    if not isinstance(payload, dict):
        raise ArtifactSmokeError(f"step returned non-object JSON: {step_id}", step=step)
    step["payload_ok"] = payload.get("ok")
    return payload


def run_artifact_smoke(*, archive: Path | None = None, keep: bool = False) -> dict[str, object]:
    workspace = Path(tempfile.mkdtemp(prefix="docs-as-code-artifact-")).resolve()
    steps: list[dict[str, object]] = []
    retained = True
    archive_path = archive.resolve() if archive is not None else workspace / f"{PACK_DIR_NAME}.tar.gz"
    archive_source = "provided-archive" if archive is not None else "temporary-export"
    try:
        staged = workspace / "staged" / PACK_DIR_NAME
        unpack_dir = workspace / "unpacked"
        export_payload: dict[str, object] = {}
        if archive is None:
            export_payload = _run_json(
                steps,
                "export_artifact",
                [
                    sys.executable,
                    ROOT / "scripts/export_workflow_pack.py",
                    "--output",
                    staged,
                    "--archive",
                    archive_path,
                    "--force",
                    "--json",
                ],
                ROOT,
            )
            _require(export_payload.get("ok") is True, "source export failed", payload=export_payload)
        _require(archive_path.is_file(), "artifact archive is not a file")
        archive_sha256 = _sha256_file(archive_path)
        if export_payload:
            _require(
                export_payload.get("archive_sha256") == archive_sha256,
                "export archive hash does not match exported file",
                payload=export_payload,
            )
        archive_members = _safe_extract_archive(archive_path, unpack_dir)
        unpacked_root = unpack_dir / PACK_DIR_NAME
        _require(unpacked_root.is_dir(), "archive did not unpack to expected root directory")
        _require((unpacked_root / "pack-manifest.json").is_file(), "unpacked artifact is missing pack-manifest.json")
        manifest_sha256 = _sha256_file(unpacked_root / "pack-manifest.json")
        if export_payload:
            _require(
                export_payload.get("manifest_sha256") == manifest_sha256,
                "export manifest hash does not match unpacked manifest",
                payload=export_payload,
            )

        manifest_payload = _run_json(
            steps,
            "unpacked_verify_pack_manifest",
            [sys.executable, "scripts/verify_pack_manifest.py", "--json"],
            unpacked_root,
        )
        _require(
            manifest_payload.get("ok") is True,
            "unpacked artifact verify_pack_manifest failed",
            payload=manifest_payload,
        )
        _require(
            manifest_payload.get("findings") == [],
            "unpacked artifact verify_pack_manifest returned findings",
            payload=manifest_payload,
        )

        verify_payload = _run_json(
            steps,
            "unpacked_verify_pack",
            [sys.executable, "scripts/verify_pack.py", "--json"],
            unpacked_root,
        )
        _require(verify_payload.get("ok") is True, "unpacked artifact verify_pack failed", payload=verify_payload)
        _require(verify_payload.get("findings") == [], "unpacked artifact verify_pack returned findings", payload=verify_payload)

        fresh_target = workspace / "fresh-target"
        fresh_product = _write_fresh_target_product(fresh_target)
        init_check_payload = _run_json(
            steps,
            "unpacked_init_fresh_target_check",
            [
                sys.executable,
                "scripts/governance_cli.py",
                "init",
                "--check",
                "--target",
                fresh_target,
                "--profile",
                "service",
                "--project-name",
                "Artifact Fresh Target",
                "--json",
            ],
            unpacked_root,
        )
        _require(
            init_check_payload.get("ok") is True,
            "unpacked artifact fresh-target init preflight failed",
            payload=init_check_payload,
        )
        init_check_product = init_check_payload.get("product")
        _require(
            isinstance(init_check_product, dict)
            and init_check_product.get("selection") == "auto-discovered"
            and init_check_product.get("path") == str(fresh_product.resolve()),
            "unpacked artifact fresh-target init preflight did not auto-discover product.md",
            payload=init_check_payload,
        )
        init_payload = _run_json(
            steps,
            "unpacked_init_fresh_target",
            [
                sys.executable,
                "scripts/governance_cli.py",
                "init",
                "--target",
                fresh_target,
                "--profile",
                "service",
                "--project-name",
                "Artifact Fresh Target",
                "--json",
            ],
            unpacked_root,
        )
        _require(
            init_payload.get("ok") is True,
            "unpacked artifact fresh-target init failed",
            payload=init_payload,
        )
        target_local_verify_payload = _run_json(
            steps,
            "fresh_target_verify_check",
            ["bin/governance", "verify", ".", "--check", "--json"],
            fresh_target,
        )
        target_local_status_payload = _run_json(
            steps,
            "fresh_target_governance_status",
            ["make", "governance-status"],
            fresh_target,
        )
        target_local_workflow_plan_payload = _run_json(
            steps,
            "fresh_target_workflow_plan",
            ["make", "workflow-plan"],
            fresh_target,
        )
        target_local_work_package_payload = _run_json(
            steps,
            "fresh_target_work_package",
            ["make", "work-package"],
            fresh_target,
        )
        target_local_workflow_resume_payload = _run_json(
            steps,
            "fresh_target_workflow_resume",
            ["make", "workflow-resume"],
            fresh_target,
        )
        fresh_target_init = _fresh_target_init_details(
            fresh_target=fresh_target,
            init_payload=init_payload,
            verify_payload=target_local_verify_payload,
            status_payload=target_local_status_payload,
            workflow_plan_payload=target_local_workflow_plan_payload,
            work_package_payload=target_local_work_package_payload,
            workflow_resume_payload=target_local_workflow_resume_payload,
        )
        _require(
            fresh_target_init.get("ok") is True,
            "unpacked artifact did not initialize a verifiable fresh target",
            payload=fresh_target_init,
        )

        consumer_target = workspace / "consumer-bootstrap-target"
        consumer_product = _write_fresh_target_product(consumer_target)
        consumer_bootstrap_payload = _run_json(
            steps,
            "unpacked_consumer_bootstrap_product_structure",
            [
                sys.executable,
                "scripts/bootstrap_consumer_project.py",
                "--target",
                consumer_target,
                "--product",
                consumer_product,
                "--profile",
                "service",
                "--project-name",
                "Artifact Consumer Bootstrap",
                "--auto-repair-env",
                "--workflow-preset",
                "product-structure",
                "--json",
            ],
            unpacked_root,
        )
        consumer_bootstrap_product_structure = _consumer_bootstrap_details(
            target=consumer_target,
            bootstrap_payload=consumer_bootstrap_payload,
        )
        _require(
            consumer_bootstrap_product_structure.get("ok") is True,
            "unpacked artifact consumer bootstrap product-structure fast path failed",
            payload=consumer_bootstrap_product_structure,
        )

        design_target = workspace / "consumer-design-scaffold-target"
        design_product = _write_fresh_target_product(design_target)
        design_bootstrap_payload = _run_json(
            steps,
            "unpacked_consumer_bootstrap_design_scaffold",
            [
                sys.executable,
                "scripts/bootstrap_consumer_project.py",
                "--target",
                design_target,
                "--product",
                design_product,
                "--profile",
                "service",
                "--project-name",
                "Artifact Consumer Design Scaffold",
                "--auto-repair-env",
                "--workflow-preset",
                "design-scaffold",
                "--json",
            ],
            unpacked_root,
        )
        consumer_bootstrap_design_scaffold = _consumer_bootstrap_design_scaffold_details(
            target=design_target,
            bootstrap_payload=design_bootstrap_payload,
        )
        _require(
            consumer_bootstrap_design_scaffold.get("ok") is True,
            "unpacked artifact consumer bootstrap design-scaffold fast path failed",
            payload=consumer_bootstrap_design_scaffold,
        )

        routing_target = workspace / "consumer-design-routing-target"
        routing_product = _write_fresh_target_product(routing_target)
        routing_bootstrap_payload = _run_json(
            steps,
            "unpacked_consumer_bootstrap_design_routing",
            [
                sys.executable,
                "scripts/bootstrap_consumer_project.py",
                "--target",
                routing_target,
                "--product",
                routing_product,
                "--profile",
                "service",
                "--project-name",
                "Artifact Consumer Design Routing",
                "--auto-repair-env",
                "--workflow-preset",
                "design-routing",
                "--json",
            ],
            unpacked_root,
        )
        consumer_bootstrap_design_routing = _consumer_bootstrap_design_routing_details(
            target=routing_target,
            bootstrap_payload=routing_bootstrap_payload,
        )
        _require(
            consumer_bootstrap_design_routing.get("ok") is True,
            "unpacked artifact consumer bootstrap design-routing fast path failed",
            payload=consumer_bootstrap_design_routing,
        )

        implementation_target = workspace / "consumer-implementation-routing-target"
        implementation_product = _write_fresh_target_product(implementation_target)
        implementation_bootstrap_payload = _run_json(
            steps,
            "unpacked_consumer_bootstrap_implementation_routing",
            [
                sys.executable,
                "scripts/bootstrap_consumer_project.py",
                "--target",
                implementation_target,
                "--product",
                implementation_product,
                "--profile",
                "service",
                "--project-name",
                "Artifact Consumer Implementation Routing",
                "--auto-repair-env",
                "--workflow-preset",
                "implementation-routing",
                "--json",
            ],
            unpacked_root,
        )
        consumer_bootstrap_implementation_routing = _consumer_bootstrap_implementation_routing_details(
            target=implementation_target,
            bootstrap_payload=implementation_bootstrap_payload,
        )
        _require(
            consumer_bootstrap_implementation_routing.get("ok") is True,
            "unpacked artifact consumer bootstrap implementation-routing fast path failed",
            payload=consumer_bootstrap_implementation_routing,
        )

        dry_run_payload = _run_json(
            steps,
            "unpacked_dry_run",
            [sys.executable, "scripts/dry_run_workflow.py", "--json"],
            unpacked_root,
        )
        _require(dry_run_payload.get("ok") is True, "unpacked artifact dry-run failed", payload=dry_run_payload)
        _require(
            dry_run_payload.get("final_phase") == "implementation",
            "unpacked artifact dry-run did not reach implementation",
            payload=dry_run_payload,
        )
        start = dry_run_payload.get("implementation_start")
        implementation_run = dry_run_payload.get("implementation_run")
        implementation_verification = dry_run_payload.get("implementation_verification")
        implementation_task_package = _dry_run_implementation_task_package_details(dry_run_payload)
        closeout = dry_run_payload.get("implementation_closeout")
        runtime_refresh = dry_run_payload.get("runtime_refresh")
        _require(
            isinstance(start, dict)
            and start.get("ready") is True
            and start.get("applied_status_updates") is True
            and start.get("implementation_plan_in_progress") is True,
            "unpacked artifact dry-run did not prove implementation start status gates",
            payload=dry_run_payload,
        )
        _require(
            isinstance(implementation_run, dict)
            and implementation_run.get("ready_check") is True
            and implementation_run.get("snapshot_guarded_start") is True
            and implementation_run.get("start_applied") is True
            and implementation_run.get("verification_ready") is True
            and implementation_run.get("required_count") == 2
            and implementation_run.get("passed_count") == 2
            and implementation_run.get("executed_all_required") is True
            and implementation_run.get("snapshot_guarded_closeout") is True
            and implementation_run.get("closeout_applied") is True
            and implementation_run.get("complete") is True,
            "unpacked artifact dry-run did not prove guarded implementation runner completion",
            payload=dry_run_payload,
        )
        _require(
            isinstance(implementation_verification, dict)
            and implementation_verification.get("ok") is True
            and implementation_verification.get("preview_ready") is True
            and implementation_verification.get("executed") is True
            and implementation_verification.get("evidence_recorded") is True
            and implementation_verification.get("command_passed") is True
            and implementation_verification.get("all_current_results_passing") is True,
            "unpacked artifact dry-run did not prove automated implementation verification evidence",
            payload=dry_run_payload,
        )
        _require(
            implementation_task_package.get("ok") is True,
            "unpacked artifact dry-run did not preserve implementation task command bindings",
            payload=dry_run_payload,
        )
        _require(
            isinstance(closeout, dict)
            and closeout.get("blocked_without_evidence") is True
            and closeout.get("ready_with_evidence") is True
            and closeout.get("applied_status_updates") is True
            and closeout.get("implementation_plan_complete") is True
            and closeout.get("workflow_plan_complete") is True,
            "unpacked artifact dry-run did not prove implementation closeout evidence gates",
            payload=dry_run_payload,
        )
        _require(
            isinstance(runtime_refresh, dict)
            and runtime_refresh.get("check_ok") is True
            and runtime_refresh.get("applied") is True
            and runtime_refresh.get("workflow_plan_complete_after_refresh") is True,
            "unpacked artifact dry-run did not prove runtime refresh preserves completion state",
            payload=dry_run_payload,
        )
        stack_acceptance = _dry_run_stack_acceptance_details(dry_run_payload)
        _require(
            stack_acceptance.get("ok") is True,
            "unpacked artifact dry-run did not prove required real stack acceptance",
            payload=dry_run_payload,
        )
        target_local_make_coverage = _dry_run_target_local_make_details(dry_run_payload)
        _require(
            target_local_make_coverage["missing_step_ids"] == [],
            "unpacked artifact dry-run did not prove target-local Make command coverage",
            payload=dry_run_payload,
        )
        product_dispositions = _dry_run_product_disposition_details(dry_run_payload)
        _require(
            product_dispositions.get("ok") is True,
            "unpacked artifact dry-run did not prove source-bound product chapter dispositions",
            payload=dry_run_payload,
        )
        design_reviews = _dry_run_design_review_details(dry_run_payload)
        _require(
            design_reviews.get("ok") is True,
            "unpacked artifact dry-run did not prove source- and authority-bound design reviews",
            payload=dry_run_payload,
        )
        api_review = _dry_run_api_review_details(dry_run_payload)
        _require(
            api_review.get("ok") is True,
            "unpacked artifact dry-run did not prove machine-reviewed OpenAPI evidence",
            payload=dry_run_payload,
        )
        threat_review = _dry_run_threat_review_details(dry_run_payload)
        _require(
            threat_review.get("ok") is True,
            "unpacked artifact dry-run did not prove machine-reviewed architecture threat evidence",
            payload=dry_run_payload,
        )
        reliability_review = _dry_run_reliability_review_details(dry_run_payload)
        _require(
            reliability_review.get("ok") is True,
            "unpacked artifact dry-run did not prove machine-reviewed backend reliability evidence",
            payload=dry_run_payload,
        )
        migration_review = _dry_run_migration_review_details(dry_run_payload)
        _require(
            migration_review.get("ok") is True,
            "unpacked artifact dry-run did not prove migration compatibility and rollback evidence",
            payload=dry_run_payload,
        )

        payload = {
            "ok": True,
            "workspace": str(workspace),
            "archive": str(archive_path),
            "archive_source": archive_source,
            "unpacked_root": str(unpacked_root),
            "archive_member_count": len(archive_members),
            "archive_sha256": archive_sha256,
            "manifest_sha256": manifest_sha256,
            "target_local_make_coverage": target_local_make_coverage,
            "product_dispositions": product_dispositions,
            "design_reviews": design_reviews,
            "implementation_verification": dict(implementation_verification),
            "implementation_run": dict(implementation_run),
            "implementation_task_package": implementation_task_package,
            "stack_acceptance": stack_acceptance,
            "api_review": api_review,
            "threat_review": threat_review,
            "reliability_review": reliability_review,
            "migration_review": migration_review,
            "fresh_target_init": fresh_target_init,
            "consumer_bootstrap_product_structure": consumer_bootstrap_product_structure,
            "consumer_bootstrap_design_scaffold": consumer_bootstrap_design_scaffold,
            "consumer_bootstrap_design_routing": consumer_bootstrap_design_routing,
            "consumer_bootstrap_implementation_routing": consumer_bootstrap_implementation_routing,
            "steps": steps,
            "target_retained": True,
        }
        if not keep:
            shutil.rmtree(workspace)
            retained = False
        payload["target_retained"] = retained
        return payload
    except ArtifactSmokeError as error:
        return {
            "ok": False,
            "error": error.message,
            "workspace": str(workspace),
            "archive": str(archive_path),
            "archive_source": archive_source,
            "target_retained": True,
            "steps": steps,
            "failed_step": error.step,
            "failed_payload": error.payload,
        }
    except OSError as error:
        return {
            "ok": False,
            "error": error.strerror or str(error),
            "workspace": str(workspace),
            "archive": str(archive_path),
            "archive_source": archive_source,
            "target_retained": True,
            "steps": steps,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract_archive(archive: Path, destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                _validate_member(destination, member)
            tar.extractall(destination, members)
    except tarfile.TarError as error:
        raise ArtifactSmokeError(f"artifact archive could not be read: {error}") from error
    return [member.name for member in members]


def _validate_member(destination: Path, member: tarfile.TarInfo) -> None:
    if member.name.startswith("/") or ".." in Path(member.name).parts:
        raise ArtifactSmokeError(f"unsafe archive member path: {member.name}")
    target = (destination / member.name).resolve()
    try:
        target.relative_to(destination.resolve())
    except ValueError as error:
        raise ArtifactSmokeError(f"archive member escapes destination: {member.name}") from error
    if member.issym() or member.islnk():
        raise ArtifactSmokeError(f"archive member links are not allowed: {member.name}")


def _dry_run_target_local_make_details(payload: dict[str, object]) -> dict[str, object]:
    steps = payload.get("steps")
    step_ids = (
        {str(step.get("id")) for step in steps if isinstance(step, dict)}
        if isinstance(steps, list)
        else set()
    )
    return {
        "required_step_ids": TARGET_LOCAL_MAKE_STEP_IDS,
        "missing_step_ids": [step_id for step_id in TARGET_LOCAL_MAKE_STEP_IDS if step_id not in step_ids],
    }


def _dry_run_implementation_task_package_details(payload: dict[str, object]) -> dict[str, object]:
    package = payload.get("implementation_task_package")
    if not isinstance(package, dict):
        return {"ok": False, "verification_command_names": [], "decision_policy": ""}
    names = package.get("verification_command_names")
    commands = package.get("verification_commands")
    summary = package.get("verification_command_summary")
    contract = package.get("execution_contract")
    valid_names = (
        isinstance(names, list)
        and bool(names)
        and all(isinstance(name, str) and name for name in names)
        and len(names) == len(set(names))
    )
    valid_commands = (
        isinstance(commands, list)
        and valid_names
        and [command.get("name") for command in commands if isinstance(command, dict)] == names
        and all(_implementation_binding_command_ready(command) for command in commands)
    )
    valid_summary = (
        isinstance(summary, dict)
        and valid_names
        and summary.get("required_count") == len(names)
        and summary.get("ready_count") == len(names)
        and summary.get("blocked_count") == 0
        and summary.get("all_ready") is True
    )
    decision_policy = (
        str(contract.get("decision_policy", "")) if isinstance(contract, dict) else ""
    )
    valid_contract = (
        isinstance(contract, dict)
        and decision_policy == "claim_then_execute_all_required_verification_commands_then_closeout"
        and contract.get("verification_commands") == commands
    )
    return {
        "ok": valid_names and valid_commands and valid_summary and valid_contract,
        "verification_command_names": list(names) if isinstance(names, list) else [],
        "required_count": summary.get("required_count", 0) if isinstance(summary, dict) else 0,
        "decision_policy": decision_policy,
    }


def _implementation_binding_command_ready(command: object) -> bool:
    if not isinstance(command, dict):
        return False
    preflight = command.get("preflight_command")
    execute = command.get("execute_command")
    return (
        command.get("ready") is True
        and isinstance(preflight, dict)
        and isinstance(preflight.get("argv"), list)
        and bool(preflight["argv"])
        and isinstance(execute, dict)
        and isinstance(execute.get("argv"), list)
        and bool(execute["argv"])
    )


def _dry_run_stack_acceptance_details(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("stack_acceptance")
    summary_map = summary if isinstance(summary, dict) else {}
    raw_stacks = summary_map.get("stacks")
    stacks = dict(raw_stacks) if isinstance(raw_stacks, dict) else {}
    required_stacks = ["python", "node"]
    all_required_passed = all(
        isinstance(stacks.get(name), dict) and stacks[name].get("status") == "passed"
        for name in required_stacks
    )
    return {
        "ok": all_required_passed,
        "policy": str(summary_map.get("policy", "")),
        "required_stacks": required_stacks,
        "optional_stacks": ["rust"],
        "all_required_passed": all_required_passed,
        "all_available_passed": summary_map.get("all_available_passed") is True,
        "strict_rust_passed": (
            isinstance(stacks.get("rust"), dict) and stacks["rust"].get("status") == "passed"
        ),
        "stacks": stacks,
    }


def _dry_run_product_disposition_details(payload: dict[str, object]) -> dict[str, object]:
    dispositions = payload.get("product_dispositions")
    disposition_map = dispositions if isinstance(dispositions, dict) else {}
    recorded_count = disposition_map.get("recorded_count")
    omitted_count = disposition_map.get("omit_unsupported_count")
    unresolved_count = disposition_map.get("unresolved_decision_count")
    routed = disposition_map.get("work_package_routed_to_phase_action") is True
    return {
        "ok": (
            isinstance(recorded_count, int)
            and not isinstance(recorded_count, bool)
            and recorded_count > 0
            and omitted_count == recorded_count
            and unresolved_count == 0
            and routed
        ),
        "recorded_count": recorded_count if isinstance(recorded_count, int) else 0,
        "omit_unsupported_count": omitted_count if isinstance(omitted_count, int) else 0,
        "unresolved_decision_count": unresolved_count if isinstance(unresolved_count, int) else 0,
        "work_package_routed_to_phase_action": routed,
    }


def _dry_run_design_review_details(payload: dict[str, object]) -> dict[str, object]:
    reviews = payload.get("design_reviews")
    review_map = reviews if isinstance(reviews, dict) else {}
    expected_count = review_map.get("expected_count")
    recorded_count = review_map.get("recorded_count")
    active_count = review_map.get("active_count")
    missing_count = review_map.get("missing_count")
    stale_count = review_map.get("stale_count")
    work_package_complete = review_map.get("work_package_complete") is True
    ok = (
        isinstance(expected_count, int)
        and not isinstance(expected_count, bool)
        and expected_count > 0
        and recorded_count == expected_count
        and active_count == expected_count
        and missing_count == 0
        and stale_count == 0
        and work_package_complete
    )
    return {
        "ok": ok,
        "expected_count": expected_count if isinstance(expected_count, int) else 0,
        "recorded_count": recorded_count if isinstance(recorded_count, int) else 0,
        "active_count": active_count if isinstance(active_count, int) else 0,
        "missing_count": missing_count if isinstance(missing_count, int) else 0,
        "stale_count": stale_count if isinstance(stale_count, int) else 0,
        "work_package_complete": work_package_complete,
    }


def _dry_run_api_review_details(payload: dict[str, object]) -> dict[str, object]:
    review = payload.get("api_review")
    review_map = review if isinstance(review, dict) else {}
    preflight_ok = review_map.get("preflight_ok") is True
    applied = review_map.get("applied") is True
    current_after_runtime_refresh = review_map.get("current_after_runtime_refresh") is True
    scorecard_grade = str(review_map.get("scorecard_grade", ""))
    evidence_paths = review_map.get("evidence_paths")
    return {
        "ok": (
            preflight_ok
            and applied
            and current_after_runtime_refresh
            and scorecard_grade in {"A", "B"}
            and isinstance(evidence_paths, list)
            and len(evidence_paths) == 5
        ),
        "preflight_ok": preflight_ok,
        "applied": applied,
        "current_after_runtime_refresh": current_after_runtime_refresh,
        "baseline_mode": str(review_map.get("baseline_mode", "")),
        "scorecard_grade": scorecard_grade,
        "evidence_paths": list(evidence_paths) if isinstance(evidence_paths, list) else [],
    }


def _dry_run_threat_review_details(payload: dict[str, object]) -> dict[str, object]:
    review = payload.get("threat_review")
    review_map = review if isinstance(review, dict) else {}
    preflight_ok = review_map.get("preflight_ok") is True
    applied = review_map.get("applied") is True
    current_after_runtime_refresh = review_map.get("current_after_runtime_refresh") is True
    element_count = review_map.get("element_count")
    high_dread_threat_count = review_map.get("high_dread_threat_count")
    evidence_paths = review_map.get("evidence_paths")
    return {
        "ok": (
            preflight_ok
            and applied
            and current_after_runtime_refresh
            and isinstance(element_count, int)
            and not isinstance(element_count, bool)
            and element_count > 0
            and isinstance(high_dread_threat_count, int)
            and not isinstance(high_dread_threat_count, bool)
            and high_dread_threat_count >= 0
            and isinstance(evidence_paths, list)
            and len(evidence_paths) == 2
        ),
        "preflight_ok": preflight_ok,
        "applied": applied,
        "current_after_runtime_refresh": current_after_runtime_refresh,
        "element_count": element_count if isinstance(element_count, int) else 0,
        "high_dread_threat_count": (
            high_dread_threat_count if isinstance(high_dread_threat_count, int) else 0
        ),
        "evidence_paths": list(evidence_paths) if isinstance(evidence_paths, list) else [],
    }


def _dry_run_reliability_review_details(payload: dict[str, object]) -> dict[str, object]:
    review = payload.get("reliability_review")
    review_map = review if isinstance(review, dict) else {}
    preflight_ok = review_map.get("preflight_ok") is True
    applied = review_map.get("applied") is True
    current_after_runtime_refresh = review_map.get("current_after_runtime_refresh") is True
    mode = str(review_map.get("mode", ""))
    slo_count = review_map.get("slo_count")
    evidence_paths = review_map.get("evidence_paths")
    return {
        "ok": (
            preflight_ok
            and applied
            and current_after_runtime_refresh
            and mode == "required"
            and isinstance(slo_count, int)
            and not isinstance(slo_count, bool)
            and slo_count > 0
            and isinstance(evidence_paths, list)
            and len(evidence_paths) == 4
        ),
        "preflight_ok": preflight_ok,
        "applied": applied,
        "current_after_runtime_refresh": current_after_runtime_refresh,
        "mode": mode,
        "slo_count": slo_count if isinstance(slo_count, int) else 0,
        "evidence_paths": list(evidence_paths) if isinstance(evidence_paths, list) else [],
    }


def _dry_run_migration_review_details(payload: dict[str, object]) -> dict[str, object]:
    review = payload.get("migration_review")
    review_map = review if isinstance(review, dict) else {}
    preflight_ok = review_map.get("preflight_ok") is True
    applied = review_map.get("applied") is True
    current_after_runtime_refresh = review_map.get("current_after_runtime_refresh") is True
    mode = str(review_map.get("mode", ""))
    compatibility_status = str(review_map.get("compatibility_status", ""))
    evidence_paths = review_map.get("evidence_paths")
    return {
        "ok": (
            preflight_ok
            and applied
            and current_after_runtime_refresh
            and mode == "required"
            and compatibility_status in {
                "fully_compatible", "backward_compatible", "accepted_with_mitigations"
            }
            and isinstance(evidence_paths, list)
            and len(evidence_paths) == 4
        ),
        "preflight_ok": preflight_ok,
        "applied": applied,
        "current_after_runtime_refresh": current_after_runtime_refresh,
        "mode": mode,
        "compatibility_status": compatibility_status,
        "evidence_paths": list(evidence_paths) if isinstance(evidence_paths, list) else [],
    }


def _write_fresh_target_product(target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    product = target / "product.md"
    product.write_text(
        "# Artifact Fresh Target\n\n"
        "## Goals and Requirements\n\n"
        "- Initialize a governed repository from an exported workflow pack.\n"
        "- Expose target-local governance commands after initialization.\n\n"
        "## Acceptance Criteria\n\n"
        "- The initialized repository verifies from its own local governance runtime.\n",
        encoding="utf-8",
    )
    return product


def _fresh_target_init_details(
    *,
    fresh_target: Path,
    init_payload: dict[str, object],
    verify_payload: dict[str, object],
    status_payload: dict[str, object],
    workflow_plan_payload: dict[str, object],
    work_package_payload: dict[str, object],
    workflow_resume_payload: dict[str, object],
) -> dict[str, object]:
    init_state = init_payload.get("state")
    status_state = status_payload.get("state")
    init_product = init_payload.get("product")
    phase = init_state.get("phase") if isinstance(init_state, dict) else ""
    profile = init_state.get("profile") if isinstance(init_state, dict) else ""
    project_name = init_state.get("project_name") if isinstance(init_state, dict) else ""
    workflow_resume = _workflow_resume_payload_details(
        workflow_resume_payload,
        expected_phase="initialized",
    )
    return {
        "ok": (
            phase == "initialized"
            and verify_payload.get("ok") is True
            and verify_payload.get("findings") == []
            and status_payload.get("ok") is True
            and isinstance(status_state, dict)
            and status_state.get("phase") == "initialized"
            and workflow_plan_payload.get("ok") is True
            and workflow_plan_payload.get("phase") == "initialized"
            and work_package_payload.get("ok") is True
            and work_package_payload.get("workflow") == "workflow-work-package"
            and work_package_payload.get("phase") == "initialized"
            and work_package_payload.get("package_available") is False
            and work_package_payload.get("status") == "phase_action_required"
            and workflow_resume.get("ok") is True
            and (fresh_target / "bin/governance").is_file()
            and (fresh_target / "scripts/governance_cli.py").is_file()
            and (fresh_target / "docs/agent-workflow/runtime-manifest.json").is_file()
            and (fresh_target / "docs/agent-workflow/workflow-pack/manifest.json").is_file()
            and (fresh_target / "docs/product/core/source/source-manifest.json").is_file()
        ),
        "target": str(fresh_target),
        "phase": phase,
        "profile": profile,
        "project_name": project_name,
        "product_selection": init_product.get("selection") if isinstance(init_product, dict) else "",
        "target_local_verify_ok": verify_payload.get("ok") is True and verify_payload.get("findings") == [],
        "target_local_status_ok": status_payload.get("ok") is True,
        "target_local_workflow_plan_ok": workflow_plan_payload.get("ok") is True,
        "target_local_work_package_ok": (
            work_package_payload.get("ok") is True
            and work_package_payload.get("workflow") == "workflow-work-package"
            and work_package_payload.get("phase") == "initialized"
            and work_package_payload.get("package_available") is False
            and work_package_payload.get("status") == "phase_action_required"
        ),
        "target_local_workflow_resume_ok": workflow_resume.get("ok") is True,
        "workflow_resume": workflow_resume,
        "local_governance_cli": (fresh_target / "bin/governance").is_file(),
        "runtime_manifest": (fresh_target / "docs/agent-workflow/runtime-manifest.json").is_file(),
        "workflow_pack_snapshot": (fresh_target / "docs/agent-workflow/workflow-pack/manifest.json").is_file(),
        "product_source_manifest": (fresh_target / "docs/product/core/source/source-manifest.json").is_file(),
    }


def _consumer_work_package_details(
    bootstrap_payload: dict[str, object],
    *,
    expected_phase: str,
    expected_kind: str,
) -> dict[str, object]:
    payload = bootstrap_payload.get("work_package")
    payload_map = payload if isinstance(payload, dict) else {}
    package = payload_map.get("work_package")
    package_map = package if isinstance(package, dict) else {}
    skill_readiness = payload_map.get("skill_readiness")
    skill_readiness_map = skill_readiness if isinstance(skill_readiness, dict) else {}
    next_action = payload_map.get("next_action")
    next_action_map = next_action if isinstance(next_action, dict) else {}
    refresh_command = payload_map.get("refresh_command")
    refresh_command_map = refresh_command if isinstance(refresh_command, dict) else {}
    read_order = package_map.get("read_order")
    write_scope = package_map.get("write_scope")
    return {
        "ok": (
            bootstrap_payload.get("work_package_generated") is True
            and bootstrap_payload.get("work_package_ok") is True
            and payload_map.get("ok") is True
            and payload_map.get("workflow") == "workflow-work-package"
            and payload_map.get("phase") == expected_phase
            and payload_map.get("package_available") is True
            and package_map.get("kind") == expected_kind
            and isinstance(package_map.get("package_id"), str)
            and bool(package_map.get("package_id"))
            and isinstance(package_map.get("queue_id"), str)
            and bool(package_map.get("queue_id"))
            and isinstance(package_map.get("work_id"), str)
            and bool(package_map.get("work_id"))
            and isinstance(read_order, list)
            and bool(read_order)
            and isinstance(write_scope, dict)
            and isinstance(skill_readiness_map.get("ready"), bool)
            and isinstance(skill_readiness_map.get("resolved_requirements"), list)
            and bool(next_action_map)
            and isinstance(refresh_command_map.get("argv"), list)
            and refresh_command_map.get("writes_state") is False
        ),
        "phase": str(payload_map.get("phase", "")),
        "status": str(payload_map.get("status", "")),
        "can_start": payload_map.get("can_start") is True,
        "stop_before_work": payload_map.get("stop_before_work") is True,
        "kind": str(package_map.get("kind", "")),
        "queue_id": str(package_map.get("queue_id", "")),
        "work_id": str(package_map.get("work_id", "")),
        "skill_ready": skill_readiness_map.get("ready") is True,
        "missing_local_workflow_skills": skill_readiness_map.get("missing_local_workflow_skills", []),
        "missing_authority_routing_skills": skill_readiness_map.get("missing_authority_routing_skills", []),
        "next_action_kind": str(next_action_map.get("kind", "")),
    }


def _workflow_resume_payload_details(
    payload: object,
    *,
    expected_phase: str,
) -> dict[str, object]:
    payload_map = payload if isinstance(payload, dict) else {}
    snapshot = payload_map.get("snapshot")
    snapshot_map = snapshot if isinstance(snapshot, dict) else {}
    selected_action = payload_map.get("selected_action")
    selected_action_map = selected_action if isinstance(selected_action, dict) else {}
    assert_command = payload_map.get("assert_snapshot_command")
    assert_command_map = assert_command if isinstance(assert_command, dict) else {}
    refresh_command = payload_map.get("refresh_command")
    refresh_command_map = refresh_command if isinstance(refresh_command, dict) else {}
    action_count = payload_map.get("action_count")
    snapshot_id = snapshot_map.get("id")
    return {
        "ok": (
            payload_map.get("ok") is True
            and payload_map.get("workflow") == "workflow-resume"
            and payload_map.get("phase") == expected_phase
            and payload_map.get("stale") is False
            and isinstance(snapshot_id, str)
            and len(snapshot_id) == 64
            and all(character in "0123456789abcdef" for character in snapshot_id)
            and isinstance(action_count, int)
            and not isinstance(action_count, bool)
            and action_count in {0, 1}
            and bool(selected_action_map) is (action_count == 1)
            and isinstance(assert_command_map.get("argv"), list)
            and isinstance(refresh_command_map.get("argv"), list)
        ),
        "phase": str(payload_map.get("phase", "")),
        "status": str(payload_map.get("status", "")),
        "snapshot_id": snapshot_id if isinstance(snapshot_id, str) else "",
        "action_count": action_count if isinstance(action_count, int) and not isinstance(action_count, bool) else -1,
        "selected_action_kind": str(selected_action_map.get("kind", "")),
        "can_continue": payload_map.get("can_continue") is True,
        "stop_before_action": payload_map.get("stop_before_action") is True,
    }


def _consumer_workflow_resume_details(
    bootstrap_payload: dict[str, object],
    *,
    expected_phase: str,
) -> dict[str, object]:
    details = _workflow_resume_payload_details(
        bootstrap_payload.get("workflow_resume"),
        expected_phase=expected_phase,
    )
    details["ok"] = (
        details.get("ok") is True
        and bootstrap_payload.get("workflow_resume_generated") is True
        and bootstrap_payload.get("workflow_resume_ok") is True
    )
    return details


def _consumer_bootstrap_details(
    *,
    target: Path,
    bootstrap_payload: dict[str, object],
) -> dict[str, object]:
    target_local = bootstrap_payload.get("target_local")
    phase = target_local.get("phase") if isinstance(target_local, dict) else ""
    workflow_preset = bootstrap_payload.get("workflow_preset")
    expanded_flags = bootstrap_payload.get("workflow_preset_expanded_flags")
    expanded_flag_list = [
        str(flag)
        for flag in expanded_flags
        if isinstance(flag, str)
    ] if isinstance(expanded_flags, list) else []
    goals_chapter = target / "docs/product/03-goals-and-requirements.md"
    acceptance_chapter = target / "docs/product/08-acceptance-criteria.md"
    authority_skill_inventory = _authority_skill_inventory_details(bootstrap_payload)
    env_auto_repair = _env_auto_repair_details(bootstrap_payload)
    work_package = _consumer_work_package_details(
        bootstrap_payload,
        expected_phase="product-structuring",
        expected_kind="product-authoring",
    )
    workflow_resume = _consumer_workflow_resume_details(
        bootstrap_payload,
        expected_phase="product-structuring",
    )
    return {
        "ok": (
            bootstrap_payload.get("ok") is True
            and phase == "product-structuring"
            and workflow_preset == "product-structure"
            and authority_skill_inventory.get("ok") is True
            and env_auto_repair.get("ok") is True
            and work_package.get("ok") is True
            and workflow_resume.get("ok") is True
            and bootstrap_payload.get("auto_repair_env") is True
            and bootstrap_payload.get("product_structure_apply_ok") is True
            and "advance_product_structuring" in expanded_flag_list
            and "product_scaffold_preview" in expanded_flag_list
            and "product_structure_preview" in expanded_flag_list
            and "product_structure_apply" in expanded_flag_list
            and goals_chapter.is_file()
            and acceptance_chapter.is_file()
        ),
        "target": str(target),
        "phase": phase,
        "workflow_preset": workflow_preset if isinstance(workflow_preset, str) else "",
        "workflow_preset_expanded_flags": expanded_flag_list,
        "authority_skill_inventory": authority_skill_inventory,
        "env_auto_repair": env_auto_repair,
        "work_package": work_package,
        "workflow_resume": workflow_resume,
        "auto_repair_env": bootstrap_payload.get("auto_repair_env") is True,
        "product_structure_apply_ok": bootstrap_payload.get("product_structure_apply_ok") is True,
        "target_local_ok": target_local.get("ok") is True if isinstance(target_local, dict) else False,
        "goals_chapter": goals_chapter.is_file(),
        "acceptance_chapter": acceptance_chapter.is_file(),
    }


def _consumer_bootstrap_design_scaffold_details(
    *,
    target: Path,
    bootstrap_payload: dict[str, object],
    expected_workflow_preset: str = "design-scaffold",
) -> dict[str, object]:
    target_local = bootstrap_payload.get("target_local")
    phase = target_local.get("phase") if isinstance(target_local, dict) else ""
    workflow_preset = bootstrap_payload.get("workflow_preset")
    expanded_flags = bootstrap_payload.get("workflow_preset_expanded_flags")
    expanded_flag_list = [
        str(flag)
        for flag in expanded_flags
        if isinstance(flag, str)
    ] if isinstance(expanded_flags, list) else []
    design_scaffold_apply = bootstrap_payload.get("design_scaffold_apply")
    post_verify_blocked = (
        design_scaffold_apply.get("post_verify_blocked_by_placeholders")
        if isinstance(design_scaffold_apply, dict)
        else False
    )
    authority_skill_inventory = _authority_skill_inventory_details(bootstrap_payload)
    env_auto_repair = _env_auto_repair_details(bootstrap_payload)
    work_package = _consumer_work_package_details(
        bootstrap_payload,
        expected_phase="design-derivation",
        expected_kind="design-authoring",
    )
    workflow_resume = _consumer_workflow_resume_details(
        bootstrap_payload,
        expected_phase="design-derivation",
    )
    system_context_doc = target / "docs/architecture/01-system-context.md"
    endpoint_contract_doc = target / "docs/api/endpoints/01-endpoint-contract.md"
    return {
        "ok": (
            bootstrap_payload.get("ok") is True
            and phase == "design-derivation"
            and workflow_preset == expected_workflow_preset
            and authority_skill_inventory.get("ok") is True
            and env_auto_repair.get("ok") is True
            and work_package.get("ok") is True
            and workflow_resume.get("ok") is True
            and bootstrap_payload.get("auto_repair_env") is True
            and bootstrap_payload.get("product_structure_apply_ok") is True
            and bootstrap_payload.get("advanced_design_derivation") is True
            and bootstrap_payload.get("design_scaffold_preview_ok") is True
            and bootstrap_payload.get("design_scaffold_apply_ok") is True
            and post_verify_blocked is True
            and "advance_design_derivation" in expanded_flag_list
            and "design_scaffold_preview" in expanded_flag_list
            and "design_scaffold_apply" in expanded_flag_list
            and system_context_doc.is_file()
            and endpoint_contract_doc.is_file()
        ),
        "target": str(target),
        "phase": phase,
        "workflow_preset": workflow_preset if isinstance(workflow_preset, str) else "",
        "workflow_preset_expanded_flags": expanded_flag_list,
        "authority_skill_inventory": authority_skill_inventory,
        "env_auto_repair": env_auto_repair,
        "work_package": work_package,
        "workflow_resume": workflow_resume,
        "auto_repair_env": bootstrap_payload.get("auto_repair_env") is True,
        "product_structure_apply_ok": bootstrap_payload.get("product_structure_apply_ok") is True,
        "advanced_design_derivation": bootstrap_payload.get("advanced_design_derivation") is True,
        "design_scaffold_preview_ok": bootstrap_payload.get("design_scaffold_preview_ok") is True,
        "design_scaffold_apply_ok": bootstrap_payload.get("design_scaffold_apply_ok") is True,
        "post_verify_blocked_by_placeholders": post_verify_blocked is True,
        "target_local_ok": target_local.get("ok") is True if isinstance(target_local, dict) else False,
        "system_context_doc": system_context_doc.is_file(),
        "endpoint_contract_doc": endpoint_contract_doc.is_file(),
    }


def _consumer_bootstrap_design_routing_details(
    *,
    target: Path,
    bootstrap_payload: dict[str, object],
    expected_workflow_preset: str = "design-routing",
) -> dict[str, object]:
    base = _consumer_bootstrap_design_scaffold_details(
        target=target,
        bootstrap_payload=bootstrap_payload,
        expected_workflow_preset=expected_workflow_preset,
    )
    workflow_preset = bootstrap_payload.get("workflow_preset")
    expanded_flags = base["workflow_preset_expanded_flags"]
    design_authoring_preview = bootstrap_payload.get("design_authoring_preview")
    queue_order = design_authoring_preview.get("queue_order") if isinstance(design_authoring_preview, dict) else []
    queues = design_authoring_preview.get("queues") if isinstance(design_authoring_preview, dict) else {}
    queue_summaries = (
        design_authoring_preview.get("queue_summaries") if isinstance(design_authoring_preview, dict) else []
    )
    authoring_summary = (
        design_authoring_preview.get("authoring_summary") if isinstance(design_authoring_preview, dict) else {}
    )
    active_work = design_authoring_preview.get("active_work") if isinstance(design_authoring_preview, dict) else {}
    queue_ids = [str(queue_id) for queue_id in queue_order] if isinstance(queue_order, list) else []
    queue_map = queues if isinstance(queues, dict) else {}
    queue_summary_list = queue_summaries if isinstance(queue_summaries, list) else []
    authoring_summary_map = authoring_summary if isinstance(authoring_summary, dict) else {}
    active_work_map = active_work if isinstance(active_work, dict) else {}
    missing_queue_ids = [
        queue_id
        for queue_id in DESIGN_AUTHORING_QUEUE_IDS
        if queue_id not in queue_ids or not isinstance(queue_map.get(queue_id), dict)
    ]
    failed_queue_ids = [
        queue_id
        for queue_id in DESIGN_AUTHORING_QUEUE_IDS
        if isinstance(queue_map.get(queue_id), dict) and queue_map[queue_id].get("ok") is not True
    ]
    authoring_summary_ok = _design_authoring_summary_ok(
        queue_summaries=queue_summary_list,
        authoring_summary=authoring_summary_map,
        active_work=active_work_map,
    )
    return {
        **base,
        "ok": (
            base.get("ok") is True
            and workflow_preset == expected_workflow_preset
            and bootstrap_payload.get("design_authoring_preview_ok") is True
            and isinstance(expanded_flags, list)
            and "design_authoring_preview" in expanded_flags
            and missing_queue_ids == []
            and failed_queue_ids == []
            and authoring_summary_ok
        ),
        "workflow_preset": workflow_preset if isinstance(workflow_preset, str) else "",
        "design_authoring_preview_ok": bootstrap_payload.get("design_authoring_preview_ok") is True,
        "queue_count": len(queue_ids),
        "required_queue_ids": DESIGN_AUTHORING_QUEUE_IDS,
        "missing_queue_ids": missing_queue_ids,
        "failed_queue_ids": failed_queue_ids,
        "queue_summaries": queue_summary_list,
        "authoring_summary": authoring_summary_map,
        "active_work": active_work_map,
        "authoring_summary_ok": authoring_summary_ok,
    }


def _design_authoring_summary_ok(
    *,
    queue_summaries: list[object],
    authoring_summary: dict[str, object],
    active_work: dict[str, object],
) -> bool:
    normalized_queues = [summary for summary in queue_summaries if isinstance(summary, dict)]
    summary_queue_ids = [str(summary.get("queue_id", "")) for summary in normalized_queues]
    status_counts = authoring_summary.get("queue_status_counts")
    next_active_work = authoring_summary.get("next_active_work")
    category_counts = [
        authoring_summary.get("blocked_queue_count"),
        authoring_summary.get("decision_required_queue_count"),
        authoring_summary.get("ready_queue_count"),
    ]
    total_counts = [
        authoring_summary.get("total_task_count"),
        authoring_summary.get("total_open_decision_count"),
        authoring_summary.get("total_non_satisfied_required_link_count"),
        authoring_summary.get("total_link_repair_action_count"),
    ]
    return (
        len(normalized_queues) == len(DESIGN_AUTHORING_QUEUE_IDS)
        and summary_queue_ids == DESIGN_AUTHORING_QUEUE_IDS
        and [summary.get("sequence") for summary in normalized_queues]
        == list(range(1, len(DESIGN_AUTHORING_QUEUE_IDS) + 1))
        and all(summary.get("ok") is True for summary in normalized_queues)
        and authoring_summary.get("queue_count") == len(DESIGN_AUTHORING_QUEUE_IDS)
        and all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in category_counts)
        and sum(category_counts) == len(DESIGN_AUTHORING_QUEUE_IDS)
        and isinstance(status_counts, dict)
        and all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in status_counts.values())
        and sum(status_counts.values()) == len(DESIGN_AUTHORING_QUEUE_IDS)
        and all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in total_counts)
        and authoring_summary.get("total_task_count", 0) > 0
        and authoring_summary.get("total_non_satisfied_required_link_count", 0) > 0
        and isinstance(authoring_summary.get("next_queue_id"), str)
        and authoring_summary.get("next_queue_id") in DESIGN_AUTHORING_QUEUE_IDS
        and isinstance(next_active_work, dict)
        and next_active_work == active_work
        and active_work.get("queue_id") == authoring_summary.get("next_queue_id")
        and active_work.get("queue_sequence")
        == DESIGN_AUTHORING_QUEUE_IDS.index(str(active_work.get("queue_id"))) + 1
        and active_work.get("status") not in {"ready", "complete"}
    )


def _consumer_bootstrap_implementation_routing_details(
    *,
    target: Path,
    bootstrap_payload: dict[str, object],
) -> dict[str, object]:
    base = _consumer_bootstrap_design_routing_details(
        target=target,
        bootstrap_payload=bootstrap_payload,
        expected_workflow_preset="implementation-routing",
    )
    workflow_preset = bootstrap_payload.get("workflow_preset")
    expanded_flags = base["workflow_preset_expanded_flags"]
    readiness_preview = bootstrap_payload.get("implementation_readiness_preview")
    advance_preview = bootstrap_payload.get("implementation_advance_preview")
    advance_apply = bootstrap_payload.get("implementation_advance_apply")
    run_preview = bootstrap_payload.get("implementation_run_preview")
    readiness_preview_map = readiness_preview if isinstance(readiness_preview, dict) else {}
    readiness_summary = readiness_preview_map.get("readiness_summary")
    readiness_summary_map = readiness_summary if isinstance(readiness_summary, dict) else {}
    readiness_blocker_codes = readiness_summary_map.get("blocker_codes")
    readiness_blocker_codes_list = (
        [code for code in readiness_blocker_codes if isinstance(code, str)]
        if isinstance(readiness_blocker_codes, list)
        else []
    )
    readiness_next_blocker = readiness_summary_map.get("next_blocker")
    readiness_next_blocker_map = readiness_next_blocker if isinstance(readiness_next_blocker, dict) else {}
    readiness_next_repair_action = readiness_preview_map.get("next_repair_action")
    readiness_next_repair_action_map = (
        readiness_next_repair_action if isinstance(readiness_next_repair_action, dict) else {}
    )
    readiness_blocker_count_value = readiness_summary_map.get("blocker_count")
    readiness_blocker_count = readiness_blocker_count_value if isinstance(readiness_blocker_count_value, int) else 0
    advance_preview_map = advance_preview if isinstance(advance_preview, dict) else {}
    advance_apply_map = advance_apply if isinstance(advance_apply, dict) else {}
    run_preview_map = run_preview if isinstance(run_preview, dict) else {}
    verify_check = readiness_preview_map.get("verify_check")
    findings = verify_check.get("findings") if isinstance(verify_check, dict) else []
    blocked_by_placeholders = _has_finding_code(findings, "governance_scaffold_placeholder")
    readiness_ok = readiness_preview_map.get("readiness_ok") is True
    implementation_ready = readiness_preview_map.get("implementation_ready") is True
    advance_ready = advance_preview_map.get("advance_ready") is True
    advance_apply_skipped = advance_apply_map.get("apply_skipped") is True
    run_preview_skipped = run_preview_map.get("preview_skipped") is True
    advance_apply_skip_code = _string_field(advance_apply_map, "skip_code")
    run_preview_skip_code = _string_field(run_preview_map, "skip_code")
    return {
        **base,
        "ok": (
            base.get("ok") is True
            and workflow_preset == "implementation-routing"
            and bootstrap_payload.get("implementation_readiness_preview_ok") is True
            and bootstrap_payload.get("implementation_advance_preview_ok") is True
            and bootstrap_payload.get("implementation_advance_apply_ok") is True
            and bootstrap_payload.get("implementation_run_preview_ok") is True
            and isinstance(expanded_flags, list)
            and "implementation_readiness_preview" in expanded_flags
            and "implementation_advance_preview" in expanded_flags
            and "implementation_advance_apply" in expanded_flags
            and "implementation_run_preview" in expanded_flags
            and "implementation_start_apply" not in expanded_flags
            and "implementation_closeout_apply" not in expanded_flags
            and readiness_ok is False
            and implementation_ready is False
            and readiness_blocker_count > 0
            and "governance_scaffold_placeholder" in readiness_blocker_codes_list
            and isinstance(readiness_next_blocker_map.get("code"), str)
            and readiness_next_blocker_map.get("code") in readiness_blocker_codes_list
            and bool(readiness_next_repair_action_map)
            and advance_ready is False
            and advance_apply_skipped
            and advance_apply_skip_code == "advance_preview_not_ready"
            and run_preview_skipped
            and run_preview_skip_code == "advance_apply_not_applied"
            and _string_field(run_preview_map, "blocked_by") == "implementation_advance_apply"
            and run_preview_map.get("required_advance_applied") is False
            and run_preview_map.get("handoff_ready") is False
            and run_preview_map.get("implementation_run") == {}
            and blocked_by_placeholders
        ),
        "workflow_preset": workflow_preset if isinstance(workflow_preset, str) else "",
        "implementation_readiness_preview_ok": bootstrap_payload.get("implementation_readiness_preview_ok") is True,
        "implementation_advance_preview_ok": bootstrap_payload.get("implementation_advance_preview_ok") is True,
        "implementation_advance_apply_ok": bootstrap_payload.get("implementation_advance_apply_ok") is True,
        "implementation_run_preview_ok": bootstrap_payload.get("implementation_run_preview_ok") is True,
        "readiness_previewed": bootstrap_payload.get("implementation_readiness_previewed") is True,
        "readiness_ok": readiness_ok,
        "implementation_ready": implementation_ready,
        "readiness_blocker_count": readiness_blocker_count,
        "readiness_blocker_codes": readiness_blocker_codes_list,
        "readiness_next_blocker": dict(readiness_next_blocker_map),
        "readiness_next_repair_action": dict(readiness_next_repair_action_map),
        "verify_ok": readiness_preview_map.get("verify_ok") is True,
        "gate_ok": readiness_preview_map.get("gate_ok") is True,
        "implementation_plan_ok": readiness_preview_map.get("implementation_plan_ok") is True,
        "advance_previewed": bootstrap_payload.get("implementation_advance_previewed") is True,
        "advance_ready": advance_ready,
        "advance_check_ok": advance_preview_map.get("advance_check_ok") is True,
        "would_advance": advance_preview_map.get("would_advance") is True,
        "advance_apply_skipped": advance_apply_skipped,
        "advance_apply_skip_code": advance_apply_skip_code,
        "advance_apply_blocked_by": _string_field(advance_apply_map, "blocked_by"),
        "run_previewed": bootstrap_payload.get("implementation_run_previewed") is True,
        "run_preview_skipped": run_preview_skipped,
        "run_preview_skip_code": run_preview_skip_code,
        "run_preview_blocked_by": _string_field(run_preview_map, "blocked_by"),
        "run_required_advance_applied": run_preview_map.get("required_advance_applied") is True,
        "run_handoff_ready": run_preview_map.get("handoff_ready") is True,
        "run_status": _string_field(run_preview_map, "status"),
        "run_task_id": _string_field(run_preview_map, "task_id"),
        "run_snapshot": run_preview_map.get("snapshot") if isinstance(run_preview_map.get("snapshot"), dict) else {},
        "run_next_action": run_preview_map.get("next_action")
        if isinstance(run_preview_map.get("next_action"), dict)
        else {},
        "blocked_by_placeholders": blocked_by_placeholders,
    }


def _has_finding_code(findings: object, code: str) -> bool:
    if not isinstance(findings, list):
        return False
    return any(isinstance(finding, dict) and finding.get("code") == code for finding in findings)


def _string_field(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _authority_skill_inventory_details(bootstrap_payload: dict[str, object]) -> dict[str, object]:
    inventory = bootstrap_payload.get("authority_skill_inventory")
    inventory_map = inventory if isinstance(inventory, dict) else {}
    manifest = inventory_map.get("manifest")
    manifest_map = manifest if isinstance(manifest, dict) else {}
    repair_plan = inventory_map.get("repair_plan")
    repair_map = repair_plan if isinstance(repair_plan, dict) else {}
    return {
        "ok": inventory_map.get("ok") is True,
        "strict": inventory_map.get("strict") is True,
        "strict_provenance": inventory_map.get("strict_provenance") is True,
        "manifest_ok": manifest_map.get("ok") is True,
        "manifest_aligned_with_routing": manifest_map.get("aligned_with_routing") is True,
        "status_counts": inventory_map.get("status_counts")
        if isinstance(inventory_map.get("status_counts"), dict)
        else {},
        "provenance_issue_count": inventory_map.get("provenance_issue_count")
        if isinstance(inventory_map.get("provenance_issue_count"), int)
        else 0,
        "repair_requested": repair_map.get("requested") is True,
        "repair_check": repair_map.get("check") is True,
        "repair_writes_state": repair_map.get("writes_state") is True,
        "repair_action_count": repair_map.get("action_count")
        if isinstance(repair_map.get("action_count"), int)
        else 0,
        "required_skill_count": inventory_map.get("required_skill_count")
        if isinstance(inventory_map.get("required_skill_count"), int)
        else 0,
        "available_skill_count": inventory_map.get("available_skill_count")
        if isinstance(inventory_map.get("available_skill_count"), int)
        else 0,
        "missing_skill_count": inventory_map.get("missing_skill_count")
        if isinstance(inventory_map.get("missing_skill_count"), int)
        else 0,
        "missing_policy": inventory_map.get("missing_policy") if isinstance(inventory_map.get("missing_policy"), str) else "",
    }


def _env_auto_repair_details(bootstrap_payload: dict[str, object]) -> dict[str, object]:
    auto_repair = bootstrap_payload.get("env_auto_repair")
    auto_repair_map = auto_repair if isinstance(auto_repair, dict) else {}
    initial_check = auto_repair_map.get("initial_check")
    initial_check_map = initial_check if isinstance(initial_check, dict) else {}
    final_env_check = auto_repair_map.get("final_env_check")
    final_env_check_map = final_env_check if isinstance(final_env_check, dict) else {}
    repair = auto_repair_map.get("repair")
    repair_map = repair if isinstance(repair, dict) else {}
    post_check = auto_repair_map.get("post_check")
    post_check_map = post_check if isinstance(post_check, dict) else {}
    initial_decision = initial_check_map.get("repair_decision")
    initial_decision_map = initial_decision if isinstance(initial_decision, dict) else {}
    final_decision = final_env_check_map.get("repair_decision")
    final_decision_map = final_decision if isinstance(final_decision, dict) else {}
    final_missing_required = final_env_check_map.get("missing_required")
    final_missing_required_list = final_missing_required if isinstance(final_missing_required, list) else []
    requested = auto_repair_map.get("requested") is True
    applied = auto_repair_map.get("applied") is True
    skipped = auto_repair_map.get("skipped") is True
    final_ok = final_env_check_map.get("ok") is True and final_missing_required_list == []
    decision = auto_repair_map.get("decision")
    status = auto_repair_map.get("status")
    runnable_action_ids = auto_repair_map.get("runnable_action_ids")
    approval_action_ids = auto_repair_map.get("approval_action_ids")
    manual_action_ids = auto_repair_map.get("manual_action_ids")
    next_step = auto_repair_map.get("next_step")
    return {
        "ok": requested and final_ok and (applied or skipped),
        "requested": requested,
        "applied": applied,
        "skipped": skipped,
        "skip_reason": auto_repair_map.get("skip_reason") if isinstance(auto_repair_map.get("skip_reason"), str) else "",
        "decision": decision if isinstance(decision, str) else "",
        "status": status if isinstance(status, str) else "",
        "stop_before_workflow": auto_repair_map.get("stop_before_workflow") is True,
        "can_continue": auto_repair_map.get("can_continue") is True,
        "can_auto_apply": auto_repair_map.get("can_auto_apply") is True,
        "requires_approval": auto_repair_map.get("requires_approval") is True,
        "manual_repair_required": auto_repair_map.get("manual_repair_required") is True,
        "runnable_action_ids": runnable_action_ids if isinstance(runnable_action_ids, list) else [],
        "approval_action_ids": approval_action_ids if isinstance(approval_action_ids, list) else [],
        "manual_action_ids": manual_action_ids if isinstance(manual_action_ids, list) else [],
        "next_step": next_step if isinstance(next_step, str) else "",
        "initial_check_ok": initial_check_map.get("ok") is True,
        "initial_decision": initial_decision_map.get("decision")
        if isinstance(initial_decision_map.get("decision"), str)
        else "",
        "repair_ok": repair_map.get("ok") is True,
        "post_check_ok": post_check_map.get("ok") is True,
        "final_env_check_ok": final_env_check_map.get("ok") is True,
        "final_missing_required": final_missing_required_list,
        "final_decision": final_decision_map.get("decision")
        if isinstance(final_decision_map.get("decision"), str)
        else "",
    }


def _require(condition: bool, message: str, *, payload: dict[str, object] | None = None) -> None:
    if not condition:
        raise ArtifactSmokeError(message, payload=payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test the exported workflow-pack tar.gz artifact.")
    parser.add_argument(
        "--archive",
        type=Path,
        help="Validate an existing workflow-pack tar.gz instead of exporting a temporary artifact first.",
    )
    parser.add_argument("--keep", action="store_true", help="Retain the temporary export and unpacked artifact.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    if payload.get("ok"):
        print(f"Artifact smoke passed: {payload.get('archive')}")
        print(f"Target retained: {payload.get('target_retained')} ({payload.get('workspace')})")
        return
    print(f"Artifact smoke failed: {payload.get('error')}")
    print(f"Target retained: {payload.get('target_retained')} ({payload.get('workspace')})")


def main() -> int:
    args = build_parser().parse_args()
    payload = run_artifact_smoke(archive=args.archive, keep=args.keep)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
