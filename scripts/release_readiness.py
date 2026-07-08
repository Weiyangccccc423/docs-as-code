from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MULTI_ACCEPTANCE_PRODUCT_FIXTURE = ROOT / "tests/fixtures/product-docs/field-service-ops.md"


def _agent_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("MAKEFLAGS", None)
    env.pop("MAKELEVEL", None)
    return env


def _run_step(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    *,
    parse_json: bool = False,
    expected_returncode: int = 0,
) -> dict[str, object] | None:
    command = [str(item) for item in argv]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_agent_env(),
        text=True,
        capture_output=True,
        check=False,
    )
    step: dict[str, object] = {
        "id": step_id,
        "argv": command,
        "cwd": str(ROOT),
        "returncode": result.returncode,
        "expected_returncode": expected_returncode,
        "ok": result.returncode == expected_returncode,
    }
    payload: dict[str, object] | None = None
    if parse_json and result.stdout:
        try:
            loaded = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            step["ok"] = False
            step["json_error"] = str(error)
        else:
            if isinstance(loaded, dict):
                payload = loaded
                step["payload_ok"] = loaded.get("ok")
            else:
                step["ok"] = False
                step["json_error"] = "top-level JSON payload must be an object"
    if not step["ok"]:
        step["stdout"] = result.stdout
        step["stderr"] = result.stderr
    steps.append(step)
    return payload


def _criterion(
    criteria: list[dict[str, object]],
    criterion_id: str,
    ok: bool,
    *,
    evidence: str,
    details: dict[str, object] | None = None,
    skipped: bool = False,
) -> None:
    status = "skipped" if skipped else "pass" if ok else "fail"
    item: dict[str, object] = {
        "id": criterion_id,
        "status": status,
        "ok": ok,
        "evidence": evidence,
    }
    if details is not None:
        item["details"] = details
    criteria.append(item)


def _dry_run_closeout_evidence_ok(payload: dict[str, object]) -> bool:
    gate = payload.get("implementation_gate")
    closeout = payload.get("implementation_closeout")
    return (
        isinstance(gate, dict)
        and gate.get("placeholder_blocked_ok") is False
        and gate.get("placeholder_expected_blocked") is True
        and gate.get("ready_ok") is True
        and isinstance(closeout, dict)
        and closeout.get("blocked_without_evidence") is True
        and closeout.get("ready_with_evidence") is True
    )


def run_release_readiness(*, skip_tests: bool = False) -> dict[str, object]:
    steps: list[dict[str, object]] = []
    criteria: list[dict[str, object]] = []

    _run_step(steps, "diff_check", ["git", "diff", "--check"])
    _criterion(
        criteria,
        "diff-whitespace",
        bool(steps[-1]["ok"]),
        evidence="git diff --check",
    )

    _run_step(steps, "cached_diff_check", ["git", "diff", "--cached", "--check"])
    _criterion(
        criteria,
        "cached-diff-whitespace",
        bool(steps[-1]["ok"]),
        evidence="git diff --cached --check",
    )

    if skip_tests:
        _criterion(
            criteria,
            "unit-tests",
            False,
            evidence="python3 -m unittest discover -s tests",
            skipped=True,
        )
    else:
        _run_step(steps, "unit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
        _criterion(
            criteria,
            "unit-tests",
            bool(steps[-1]["ok"]),
            evidence="python3 -m unittest discover -s tests",
        )

    pack_payload = _run_step(
        steps,
        "pack_verification",
        [sys.executable, "scripts/verify_pack.py", "--json"],
        parse_json=True,
    )
    _criterion(
        criteria,
        "pack-verification",
        bool(steps[-1]["ok"]) and bool(pack_payload and pack_payload.get("ok") is True),
        evidence="python3 scripts/verify_pack.py --json",
        details={"findings": pack_payload.get("findings", []) if pack_payload else []},
    )

    env_payload = _run_step(
        steps,
        "environment_inventory",
        [sys.executable, "scripts/check_env.py", "--json"],
        parse_json=True,
    )
    _criterion(
        criteria,
        "environment-inventory",
        bool(steps[-1]["ok"]) and bool(env_payload and env_payload.get("ok") is True),
        evidence="python3 scripts/check_env.py --json",
        details={
            "missing_required": env_payload.get("missing_required", []) if env_payload else [],
            "missing_recommended": env_payload.get("missing_recommended", []) if env_payload else [],
        },
    )

    dry_run_payload = _run_step(
        steps,
        "fresh_target_dry_run",
        [sys.executable, "scripts/dry_run_workflow.py", "--json"],
        parse_json=True,
    )
    _criterion(
        criteria,
        "fresh-target-dry-run",
        bool(steps[-1]["ok"])
        and bool(dry_run_payload and dry_run_payload.get("ok") is True)
        and dry_run_payload.get("final_phase") == "implementation"
        and _dry_run_closeout_evidence_ok(dry_run_payload),
        evidence="python3 scripts/dry_run_workflow.py --json",
        details={
            "final_phase": dry_run_payload.get("final_phase") if dry_run_payload else "",
            "api_candidate_count": dry_run_payload.get("api_candidate_count") if dry_run_payload else 0,
            "implementation_closeout": dry_run_payload.get("implementation_closeout") if dry_run_payload else {},
        },
    )

    multi_acceptance_payload = _run_step(
        steps,
        "multi_acceptance_dry_run",
        [
            sys.executable,
            "scripts/dry_run_workflow.py",
            "--product",
            MULTI_ACCEPTANCE_PRODUCT_FIXTURE,
            "--json",
        ],
        parse_json=True,
    )
    authoring_counts = multi_acceptance_payload.get("authoring_task_counts", {}) if multi_acceptance_payload else {}
    _criterion(
        criteria,
        "multi-acceptance-dry-run",
        bool(steps[-1]["ok"])
        and bool(multi_acceptance_payload and multi_acceptance_payload.get("ok") is True)
        and multi_acceptance_payload.get("final_phase") == "implementation"
        and _dry_run_closeout_evidence_ok(multi_acceptance_payload)
        and multi_acceptance_payload.get("acceptance_id_count") == 4
        and multi_acceptance_payload.get("api_candidate_count") == 4
        and isinstance(authoring_counts, dict)
        and len(authoring_counts) == 6
        and all(value == 4 for value in authoring_counts.values()),
        evidence="python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json",
        details={
            "acceptance_id_count": multi_acceptance_payload.get("acceptance_id_count")
            if multi_acceptance_payload
            else 0,
            "api_candidate_count": multi_acceptance_payload.get("api_candidate_count") if multi_acceptance_payload else 0,
            "authoring_task_counts": authoring_counts,
            "implementation_closeout": multi_acceptance_payload.get("implementation_closeout")
            if multi_acceptance_payload
            else {},
        },
    )

    with tempfile.TemporaryDirectory(prefix="docs-as-code-release-") as tmp:
        base = Path(tmp)
        export_payload = _run_step(
            steps,
            "source_pack_export",
            [
                sys.executable,
                "scripts/export_workflow_pack.py",
                "--output",
                base / "docs-as-code-workflow-pack",
                "--archive",
                base / "docs-as-code-workflow-pack.tar.gz",
                "--force",
                "--json",
            ],
            parse_json=True,
        )
    verification = export_payload.get("verification", {}) if export_payload else {}
    _criterion(
        criteria,
        "source-pack-export",
        bool(steps[-1]["ok"])
        and bool(export_payload and export_payload.get("ok") is True)
        and isinstance(verification, dict)
        and verification.get("ok") is True,
        evidence="python3 scripts/export_workflow_pack.py --output <tmp>/docs-as-code-workflow-pack --archive <tmp>/docs-as-code-workflow-pack.tar.gz --force --json",
        details={
            "file_count": export_payload.get("file_count") if export_payload else 0,
            "manifest_sha256": export_payload.get("manifest_sha256") if export_payload else "",
            "archive_sha256": export_payload.get("archive_sha256") if export_payload else "",
        },
    )

    artifact_smoke_payload = _run_step(
        steps,
        "release_artifact_smoke",
        [sys.executable, "scripts/smoke_workflow_pack_artifact.py", "--json"],
        parse_json=True,
    )
    _criterion(
        criteria,
        "release-artifact-smoke",
        bool(steps[-1]["ok"]) and bool(artifact_smoke_payload and artifact_smoke_payload.get("ok") is True),
        evidence="python3 scripts/smoke_workflow_pack_artifact.py --json",
        details={
            "archive_member_count": artifact_smoke_payload.get("archive_member_count") if artifact_smoke_payload else 0,
            "archive_sha256": artifact_smoke_payload.get("archive_sha256") if artifact_smoke_payload else "",
            "manifest_sha256": artifact_smoke_payload.get("manifest_sha256") if artifact_smoke_payload else "",
        },
    )

    ok = all(bool(item["ok"]) or item["status"] == "skipped" for item in criteria)
    release_ready = ok and not any(item["status"] == "skipped" for item in criteria)
    return {
        "ok": ok,
        "release_ready": release_ready,
        "tests_skipped": skip_tests,
        "criteria": criteria,
        "steps": steps,
        "next": "run without --skip-tests before tagging or handing off a release" if skip_tests else "ready to tag or hand off when release_ready is true",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run source workflow-pack release readiness checks.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the full unit test suite for fast local smoke checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    status = "ready" if payload.get("release_ready") else "not ready"
    print(f"Release readiness: {status}")
    for item in payload.get("criteria", []):
        if isinstance(item, dict):
            print(f"- {item.get('id')}: {item.get('status')}")


def main() -> int:
    args = build_parser().parse_args()
    payload = run_release_readiness(skip_tests=args.skip_tests)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
