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
    "make_workflow_plan_product_structuring",
    "make_workflow_plan_design_derivation",
    "make_workflow_plan_implementation",
    "make_product_plan",
    "make_design_plan",
    "make_implementation_plan",
    "make_check_env",
    "make_repair_env_check",
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
        fresh_target_init = _fresh_target_init_details(
            fresh_target=fresh_target,
            init_payload=init_payload,
            verify_payload=target_local_verify_payload,
            status_payload=target_local_status_payload,
            workflow_plan_payload=target_local_workflow_plan_payload,
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
        target_local_make_coverage = _dry_run_target_local_make_details(dry_run_payload)
        _require(
            target_local_make_coverage["missing_step_ids"] == [],
            "unpacked artifact dry-run did not prove target-local Make command coverage",
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
            "fresh_target_init": fresh_target_init,
            "consumer_bootstrap_product_structure": consumer_bootstrap_product_structure,
            "consumer_bootstrap_design_scaffold": consumer_bootstrap_design_scaffold,
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
) -> dict[str, object]:
    init_state = init_payload.get("state")
    status_state = status_payload.get("state")
    init_product = init_payload.get("product")
    phase = init_state.get("phase") if isinstance(init_state, dict) else ""
    profile = init_state.get("profile") if isinstance(init_state, dict) else ""
    project_name = init_state.get("project_name") if isinstance(init_state, dict) else ""
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
        "local_governance_cli": (fresh_target / "bin/governance").is_file(),
        "runtime_manifest": (fresh_target / "docs/agent-workflow/runtime-manifest.json").is_file(),
        "workflow_pack_snapshot": (fresh_target / "docs/agent-workflow/workflow-pack/manifest.json").is_file(),
        "product_source_manifest": (fresh_target / "docs/product/core/source/source-manifest.json").is_file(),
    }


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
    return {
        "ok": (
            bootstrap_payload.get("ok") is True
            and phase == "product-structuring"
            and workflow_preset == "product-structure"
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
    system_context_doc = target / "docs/architecture/01-system-context.md"
    endpoint_contract_doc = target / "docs/api/endpoints/01-endpoint-contract.md"
    return {
        "ok": (
            bootstrap_payload.get("ok") is True
            and phase == "design-derivation"
            and workflow_preset == "design-scaffold"
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
