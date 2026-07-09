from __future__ import annotations

import argparse
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


def run_artifact_smoke(*, keep: bool = False) -> dict[str, object]:
    workspace = Path(tempfile.mkdtemp(prefix="docs-as-code-artifact-")).resolve()
    steps: list[dict[str, object]] = []
    retained = True
    try:
        staged = workspace / "staged" / PACK_DIR_NAME
        archive = workspace / f"{PACK_DIR_NAME}.tar.gz"
        unpack_dir = workspace / "unpacked"
        export_payload = _run_json(
            steps,
            "export_artifact",
            [
                sys.executable,
                ROOT / "scripts/export_workflow_pack.py",
                "--output",
                staged,
                "--archive",
                archive,
                "--force",
                "--json",
            ],
            ROOT,
        )
        _require(export_payload.get("ok") is True, "source export failed", payload=export_payload)
        _require(archive.is_file(), "export did not create archive")
        archive_members = _safe_extract_archive(archive, unpack_dir)
        unpacked_root = unpack_dir / PACK_DIR_NAME
        _require(unpacked_root.is_dir(), "archive did not unpack to expected root directory")
        _require((unpacked_root / "pack-manifest.json").is_file(), "unpacked artifact is missing pack-manifest.json")

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
            "archive": str(archive),
            "unpacked_root": str(unpacked_root),
            "archive_member_count": len(archive_members),
            "archive_sha256": export_payload.get("archive_sha256"),
            "manifest_sha256": export_payload.get("manifest_sha256"),
            "target_local_make_coverage": target_local_make_coverage,
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
            "target_retained": True,
            "steps": steps,
        }


def _safe_extract_archive(archive: Path, destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            _validate_member(destination, member)
        tar.extractall(destination, members)
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


def _require(condition: bool, message: str, *, payload: dict[str, object] | None = None) -> None:
    if not condition:
        raise ArtifactSmokeError(message, payload=payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test the exported workflow-pack tar.gz artifact.")
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
    payload = run_artifact_smoke(keep=args.keep)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
