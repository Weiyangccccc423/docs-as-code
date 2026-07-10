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
CLI = ROOT / "scripts" / "governance_cli.py"

SAMPLE_PRODUCT = """# Product

## Goals and Requirements

- Ship a governed project from one product document.
- Expose local governance checks after initialization.

## Acceptance Criteria

- The initialized repository exposes local governance checks.
"""

DESIGN_TRACK_IDS = [
    "architecture",
    "ui-interaction",
    "api-contracts",
    "backend-modules",
    "data-model",
    "frontend-modules",
    "test-strategy",
    "implementation-planning",
    "architecture-decisions",
]

AUTHORING_COMMANDS = [
    ("architecture_authoring", "architecture-authoring", "architecture"),
    ("api_authoring", "api-authoring", "api-contracts"),
    ("backend_authoring", "backend-authoring", "backend-modules"),
    ("data_model_authoring", "data-model-authoring", "data-model"),
    ("ui_interaction_authoring", "ui-interaction-authoring", "ui-interaction"),
    ("frontend_authoring", "frontend-authoring", "frontend-modules"),
    ("test_strategy_authoring", "test-strategy-authoring", "test-strategy"),
    ("implementation_planning_authoring", "implementation-planning-authoring", "implementation-planning"),
    ("architecture_decisions_authoring", "architecture-decisions-authoring", "architecture-decisions"),
]
ACCEPTANCE_ID_HEADING_RE = re.compile(r"^##[ \t]+(?P<id>A-[0-9]{3})\b", re.MULTILINE)
IMPLEMENTATION_TASK_ID = "TASK-001"
TARGET_LOCAL_MAKE_STEP_IDS = [
    "make_verify_governance",
    "make_verify_check",
    "make_governance_status",
    "make_workflow_plan_initialized",
    "make_work_package_initialized",
    "make_workflow_plan_product_structuring",
    "make_work_package_product_structuring",
    "make_workflow_plan_design_derivation",
    "make_work_package_design_derivation",
    "make_work_package_design_complete",
    "make_workflow_plan_implementation",
    "make_work_package_implementation",
    "make_work_package_complete_after_runtime_refresh",
    "make_product_plan",
    "make_design_plan",
    "make_implementation_plan",
    "make_check_env",
    "make_repair_env_check",
]


class DryRunFailure(Exception):
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


def _stringify_argv(argv: list[str | Path]) -> list[str]:
    return [str(item) for item in argv]


def _run_json(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    cwd: Path,
    *,
    expected_returncode: int = 0,
) -> dict[str, object]:
    command = _stringify_argv(argv)
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
    if result.returncode != expected_returncode or result.stderr:
        failed = {
            **step,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        raise DryRunFailure(f"step failed: {step_id}", step=failed)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        failed = {
            **step,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        raise DryRunFailure(f"step did not return JSON: {step_id}: {error}", step=failed) from error
    if not isinstance(payload, dict):
        raise DryRunFailure(f"step returned non-object JSON: {step_id}", step=step)
    step["payload_ok"] = payload.get("ok")
    return payload


def _run_text(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    cwd: Path,
    *,
    expected_returncode: int = 0,
) -> str:
    command = _stringify_argv(argv)
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
    if result.returncode != expected_returncode or result.stderr:
        failed = {
            **step,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        raise DryRunFailure(f"step failed: {step_id}", step=failed)
    stdout = result.stdout.strip()
    if stdout:
        step["stdout_first_line"] = stdout.splitlines()[0]
    return result.stdout


def _require(condition: bool, message: str, *, payload: dict[str, object] | None = None) -> None:
    if not condition:
        raise DryRunFailure(message, payload=payload)


def _require_path(path: Path, message: str) -> None:
    _require(path.is_file(), message)


def _write_sample_product(path: Path) -> None:
    if path.exists():
        raise DryRunFailure(f"sample product path already exists: {path}")
    path.write_text(SAMPLE_PRODUCT, encoding="utf-8")


def _prepare_paths(
    target: Path | None,
    product: Path | None,
) -> tuple[Path, Path, Path, bool]:
    if target is None:
        workspace = Path(tempfile.mkdtemp(prefix="docs-as-code-dry-run-")).resolve()
        target_path = workspace / "fresh-target"
        product_path = product.resolve() if product else workspace / "product.md"
        return workspace, target_path, product_path, True

    target_path = target.resolve()
    workspace = target_path.parent
    product_path = product.resolve() if product else workspace / f"{target_path.name}-product.md"
    return workspace, target_path, product_path, False


def run_dry_run(
    *,
    target: Path | None = None,
    product: Path | None = None,
    keep: bool = False,
) -> dict[str, object]:
    workspace, target_path, product_path, created_workspace = _prepare_paths(target, product)
    steps: list[dict[str, object]] = []
    generated_product = product is None
    retained = True
    try:
        if generated_product:
            _write_sample_product(product_path)
        summary = _execute_workflow(target_path, product_path, steps)
        summary["workspace"] = str(workspace)
        summary["target"] = str(target_path)
        summary["product"] = str(product_path)
        if created_workspace and not keep:
            shutil.rmtree(workspace)
            retained = False
        summary["target_retained"] = retained
        return summary
    except DryRunFailure as error:
        return {
            "ok": False,
            "error": error.message,
            "workspace": str(workspace),
            "target": str(target_path),
            "product": str(product_path),
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
            "target": str(target_path),
            "product": str(product_path),
            "target_retained": True,
            "steps": steps,
        }


def _execute_workflow(target: Path, product: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    env_check = _run_json(
        steps,
        "env_repair_check",
        [sys.executable, CLI, "env", "--repair", "--check", "--target", target, "--json"],
        ROOT,
    )
    _require(env_check.get("ok") is True, "environment repair check failed", payload=env_check)
    _require(env_check.get("check") is True, "environment repair check did not run in check mode", payload=env_check)
    _require(env_check.get("missing_required") == [], "required environment tools are missing", payload=env_check)

    init_check = _run_json(
        steps,
        "init_check",
        [
            sys.executable,
            CLI,
            "init",
            "--check",
            "--target",
            target,
            "--product",
            product,
            "--profile",
            "service",
            "--project-name",
            "Dry Run Target",
            "--json",
        ],
        ROOT,
    )
    _require(init_check.get("ok") is True, "initialization preflight failed", payload=init_check)
    _require(init_check.get("conflicts") == [], "initialization preflight reported conflicts", payload=init_check)
    _require(not target.exists(), "initialization preflight wrote the target directory")

    init_payload = _run_json(
        steps,
        "init",
        [
            sys.executable,
            CLI,
            "init",
            "--target",
            target,
            "--product",
            product,
            "--profile",
            "service",
            "--project-name",
            "Dry Run Target",
            "--json",
        ],
        ROOT,
    )
    _require(init_payload.get("ok") is True, "initialization failed", payload=init_payload)
    init_state = init_payload.get("state")
    _require(isinstance(init_state, dict), "initialization did not return state", payload=init_payload)
    _require(init_state.get("phase") == "initialized", "initialization state phase mismatch", payload=init_payload)
    _require_path(target / "bin/governance", "target-local governance wrapper is missing")
    _require_path(target / "scripts/governance_cli.py", "target-local governance CLI is missing")
    _require_path(target / "docs/agent-workflow/runtime-manifest.json", "runtime manifest is missing")
    _require_path(target / "docs/agent-workflow/workflow-pack/manifest.json", "workflow-pack manifest is missing")
    _require_path(target / "docs/product/core/PRD.md", "archived PRD is missing")

    verify_check = _run_json(
        steps,
        "verify_check",
        [sys.executable, CLI, "verify", target, "--check", "--json"],
        ROOT,
    )
    _require(verify_check.get("ok") is True, "source CLI verify --check failed", payload=verify_check)
    _require(verify_check.get("findings") == [], "source CLI verify --check returned findings", payload=verify_check)

    status = _run_json(
        steps,
        "status",
        [sys.executable, CLI, "status", target, "--json"],
        ROOT,
    )
    _require(status.get("ok") is True, "source CLI status failed", payload=status)
    status_state = status.get("state")
    _require(isinstance(status_state, dict), "status did not return state", payload=status)
    _require(status_state.get("phase") == "initialized", "status phase mismatch", payload=status)

    target_verify = _run_json(
        steps,
        "target_local_verify_check",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    _require(target_verify.get("ok") is True, "target-local verify --check failed", payload=target_verify)

    target_status = _run_json(
        steps,
        "target_local_status",
        ["bin/governance", "status", ".", "--json"],
        target,
    )
    _require(target_status.get("ok") is True, "target-local status failed", payload=target_status)

    make_verify_governance = _run_text(
        steps,
        "make_verify_governance",
        ["make", "verify-governance"],
        target,
    )
    _require(
        "Governance verification passed." in make_verify_governance,
        "make verify-governance did not report success",
    )

    make_verify_check = _run_json(
        steps,
        "make_verify_check",
        ["make", "verify-check"],
        target,
    )
    _require(make_verify_check.get("ok") is True, "make verify-check failed", payload=make_verify_check)
    _require(make_verify_check.get("findings") == [], "make verify-check returned findings", payload=make_verify_check)

    make_governance_status = _run_json(
        steps,
        "make_governance_status",
        ["make", "governance-status"],
        target,
    )
    _require(
        make_governance_status.get("ok") is True,
        "make governance-status failed",
        payload=make_governance_status,
    )
    make_status_state = make_governance_status.get("state")
    _require(
        isinstance(make_status_state, dict) and make_status_state.get("phase") == "initialized",
        "make governance-status phase mismatch",
        payload=make_governance_status,
    )

    make_initialized_workflow_plan = _run_json(
        steps,
        "make_workflow_plan_initialized",
        ["make", "workflow-plan"],
        target,
    )
    _require_initialized_workflow_plan(make_initialized_workflow_plan, "make workflow-plan initialized")
    make_initialized_work_package = _run_json(
        steps,
        "make_work_package_initialized",
        ["make", "work-package"],
        target,
    )
    _require_phase_action_work_package(
        make_initialized_work_package,
        "initialized",
        "advance-product-structuring-check",
    )

    make_check_env = _run_json(
        steps,
        "make_check_env",
        ["make", "check-env"],
        target,
    )
    _require(make_check_env.get("ok") is True, "make check-env failed", payload=make_check_env)
    _require(make_check_env.get("target") == ".", "make check-env target mismatch", payload=make_check_env)
    _require(
        _env_repair_decision_allows_workflow(make_check_env),
        "make check-env did not expose a continue-workflow repair decision",
        payload=make_check_env,
    )

    make_repair_env_check = _run_json(
        steps,
        "make_repair_env_check",
        ["make", "repair-env-check"],
        target,
    )
    _require(make_repair_env_check.get("ok") is True, "make repair-env-check failed", payload=make_repair_env_check)
    _require(
        make_repair_env_check.get("check") is True,
        "make repair-env-check did not run in check mode",
        payload=make_repair_env_check,
    )
    _require(
        _env_repair_decision_allows_workflow(make_repair_env_check),
        "make repair-env-check did not expose a continue-workflow repair decision",
        payload=make_repair_env_check,
    )

    product_advanced = _run_json(
        steps,
        "advance_product_structuring",
        ["bin/governance", "advance", "product-structuring", ".", "--json"],
        target,
    )
    _require(product_advanced.get("ok") is True, "product-structuring advance failed", payload=product_advanced)
    product_state = product_advanced.get("state")
    _require(isinstance(product_state, dict), "product advance did not return state", payload=product_advanced)
    _require(product_state.get("phase") == "product-structuring", "product phase mismatch", payload=product_advanced)

    product_plan = _run_json(
        steps,
        "product_plan",
        ["bin/governance", "product", "plan", ".", "--json"],
        target,
    )
    _require(product_plan.get("ok") is True, "product plan failed", payload=product_plan)
    suggested_mappings = product_plan.get("suggested_mappings")
    _require(isinstance(suggested_mappings, list), "product plan did not return suggested mappings", payload=product_plan)
    manual_authoring_tasks = product_plan.get("manual_authoring_tasks")
    _require(
        isinstance(manual_authoring_tasks, list),
        "product plan did not return manual authoring tasks",
        payload=product_plan,
    )
    command_args = {
        str(mapping.get("command_arg"))
        for mapping in suggested_mappings
        if isinstance(mapping, dict)
    }
    _require(
        "goals-and-requirements=Goals and Requirements" in command_args,
        "product plan did not suggest goals mapping",
        payload=product_plan,
    )
    _require(
        "acceptance-criteria=Acceptance Criteria" in command_args,
        "product plan did not suggest acceptance mapping",
        payload=product_plan,
    )
    _require(
        any(isinstance(task, dict) and task.get("status") == "decision_required" for task in manual_authoring_tasks),
        "product plan did not expose decision-required manual authoring tasks",
        payload=product_plan,
    )
    _require(
        any(
            isinstance(task, dict)
            and isinstance(task.get("required_evidence"), list)
            and task["required_evidence"]
            for task in manual_authoring_tasks
        ),
        "product plan did not expose manual authoring evidence requirements",
        payload=product_plan,
    )
    _require(
        all(
            isinstance(item, dict) and isinstance(item.get("status"), str) and item["status"]
            for task in manual_authoring_tasks
            if isinstance(task, dict)
            for item in task.get("required_evidence", [])
            if isinstance(task.get("required_evidence"), list)
        ),
        "product plan evidence requirements did not expose machine-readable statuses",
        payload=product_plan,
    )
    _require(
        all(
            _task_evidence_repairs_cover_required_statuses(task)
            for task in manual_authoring_tasks
            if isinstance(task, dict)
        ),
        "product plan evidence repair actions did not cover non-satisfied required evidence",
        payload=product_plan,
    )
    _require(
        _manual_authoring_summary_matches_tasks(product_plan),
        "product plan manual authoring summary did not match task details",
        payload=product_plan,
    )
    _require(
        _active_work_is_actionable(product_plan.get("active_work")),
        "product plan did not expose actionable active work",
        payload=product_plan,
    )

    make_product_plan = _run_json(
        steps,
        "make_product_plan",
        ["make", "product-plan"],
        target,
    )
    _require(make_product_plan.get("ok") is True, "make product-plan failed", payload=make_product_plan)
    _require(
        isinstance(make_product_plan.get("suggested_mappings"), list),
        "make product-plan did not return suggested mappings",
        payload=make_product_plan,
    )
    _require(
        _active_work_is_actionable(make_product_plan.get("active_work")),
        "make product-plan did not expose actionable active work",
        payload=make_product_plan,
    )
    product_workflow_plan = _run_json(
        steps,
        "workflow_plan_product_structuring",
        ["bin/governance", "workflow", "plan", ".", "--json"],
        target,
    )
    _require_product_workflow_plan(product_workflow_plan, "product workflow plan")

    make_product_workflow_plan = _run_json(
        steps,
        "make_workflow_plan_product_structuring",
        ["make", "workflow-plan"],
        target,
    )
    _require_product_workflow_plan(make_product_workflow_plan, "make workflow-plan product structuring")
    make_product_work_package = _run_json(
        steps,
        "make_work_package_product_structuring",
        ["make", "work-package"],
        target,
    )
    _require_active_work_package(
        make_product_work_package,
        phase="product-structuring",
        kind="product-authoring",
        queue_id="product-plan",
    )

    product_scaffold_check = _run_json(
        steps,
        "product_scaffold_check",
        [
            "bin/governance",
            "scaffold",
            "product",
            ".",
            "--chapter",
            "goals-and-requirements",
            "--chapter",
            "acceptance-criteria",
            "--check",
            "--json",
        ],
        target,
    )
    _require(product_scaffold_check.get("ok") is True, "product scaffold preflight failed", payload=product_scaffold_check)
    _require(
        "docs/product/03-goals-and-requirements.md" in product_scaffold_check.get("would_create", []),
        "product scaffold preflight did not plan goals chapter",
        payload=product_scaffold_check,
    )

    product_scaffold = _run_json(
        steps,
        "product_scaffold",
        [
            "bin/governance",
            "scaffold",
            "product",
            ".",
            "--chapter",
            "goals-and-requirements",
            "--chapter",
            "acceptance-criteria",
            "--json",
        ],
        target,
    )
    _require(product_scaffold.get("ok") is True, "product scaffold failed", payload=product_scaffold)
    _require("next_actions_blocked_by" in product_scaffold, "product scaffold did not report placeholder blockers")

    product_blocked_verify = _run_json(
        steps,
        "product_blocked_verify_check",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
        expected_returncode=1,
    )
    _require(product_blocked_verify.get("ok") is False, "product placeholders did not block verification")

    product_structure_check = _run_json(
        steps,
        "product_structure_check",
        [
            "bin/governance",
            "product",
            "structure",
            ".",
            "--chapter",
            "goals-and-requirements=Goals and Requirements",
            "--chapter",
            "acceptance-criteria=Acceptance Criteria",
            "--check",
            "--json",
        ],
        target,
    )
    _require(product_structure_check.get("ok") is True, "product structure preflight failed", payload=product_structure_check)

    product_structured = _run_json(
        steps,
        "product_structure",
        [
            "bin/governance",
            "product",
            "structure",
            ".",
            "--chapter",
            "goals-and-requirements=Goals and Requirements",
            "--chapter",
            "acceptance-criteria=Acceptance Criteria",
            "--json",
        ],
        target,
    )
    _require(product_structured.get("ok") is True, "product structure failed", payload=product_structured)
    goals = (target / "docs/product/03-goals-and-requirements.md").read_text(encoding="utf-8")
    acceptance = (target / "docs/product/08-acceptance-criteria.md").read_text(encoding="utf-8")
    acceptance_ids = ACCEPTANCE_ID_HEADING_RE.findall(acceptance)
    _require("governance:scaffold-placeholder" not in goals, "goals chapter still contains scaffold placeholder")
    _require(acceptance_ids, "acceptance chapter did not receive stable acceptance IDs")

    clean_verify = _run_json(
        steps,
        "product_clean_verify_check",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    _require(clean_verify.get("ok") is True, "verification failed after product structuring", payload=clean_verify)
    _require(clean_verify.get("findings") == [], "verification returned findings after product structuring", payload=clean_verify)

    design_advanced = _run_json(
        steps,
        "advance_design_derivation",
        ["bin/governance", "advance", "design-derivation", ".", "--json"],
        target,
    )
    _require(design_advanced.get("ok") is True, "design-derivation advance failed", payload=design_advanced)
    design_state = design_advanced.get("state")
    _require(isinstance(design_state, dict), "design advance did not return state", payload=design_advanced)
    _require(design_state.get("phase") == "design-derivation", "design phase mismatch", payload=design_advanced)

    design_scaffold_check = _run_json(
        steps,
        "design_scaffold_check",
        ["bin/governance", "scaffold", "design", ".", "--check", "--json"],
        target,
    )
    _require(design_scaffold_check.get("ok") is True, "design scaffold preflight failed", payload=design_scaffold_check)
    for path in (
        "docs/architecture/01-system-context.md",
        "docs/api/endpoints/01-endpoint-contract.md",
        "docs/development/03-verification-log.md",
    ):
        _require(path in design_scaffold_check.get("would_create", []), f"design scaffold preflight missed {path}")

    design_scaffold = _run_json(
        steps,
        "design_scaffold",
        ["bin/governance", "scaffold", "design", ".", "--json"],
        target,
    )
    _require(design_scaffold.get("ok") is True, "design scaffold failed", payload=design_scaffold)
    _require("next_actions_blocked_by" in design_scaffold, "design scaffold did not report placeholder blockers")

    design_blocked_verify = _run_json(
        steps,
        "design_blocked_verify_check",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
        expected_returncode=1,
    )
    _require(design_blocked_verify.get("ok") is False, "design placeholders did not block verification")

    design_plan = _run_json(
        steps,
        "design_plan",
        ["bin/governance", "design", "plan", ".", "--json"],
        target,
    )
    _require(design_plan.get("ok") is True, "design plan failed", payload=design_plan)
    tracks = design_plan.get("tracks")
    _require(isinstance(tracks, list), "design plan did not return tracks", payload=design_plan)
    track_ids = [track.get("id") for track in tracks if isinstance(track, dict)]
    _require(track_ids == DESIGN_TRACK_IDS, "design plan track order changed", payload=design_plan)
    _require(
        _design_tracks_have_skill_loading_plans(tracks),
        "design plan tracks did not expose ordered skill loading plans",
        payload=design_plan,
    )
    _require(
        _active_work_is_actionable(design_plan.get("active_work")),
        "design plan did not expose actionable active work",
        payload=design_plan,
    )

    make_design_plan = _run_json(
        steps,
        "make_design_plan",
        ["make", "design-plan"],
        target,
    )
    _require(make_design_plan.get("ok") is True, "make design-plan failed", payload=make_design_plan)
    make_design_tracks = make_design_plan.get("tracks")
    _require(isinstance(make_design_tracks, list), "make design-plan did not return tracks", payload=make_design_plan)
    make_design_track_ids = [track.get("id") for track in make_design_tracks if isinstance(track, dict)]
    _require(make_design_track_ids == DESIGN_TRACK_IDS, "make design-plan track order changed", payload=make_design_plan)
    _require(
        _active_work_is_actionable(make_design_plan.get("active_work")),
        "make design-plan did not expose actionable active work",
        payload=make_design_plan,
    )

    api_candidates = _run_json(
        steps,
        "api_candidates",
        ["bin/governance", "design", "api-candidates", ".", "--json"],
        target,
    )
    _require(api_candidates.get("ok") is True, "API candidate extraction failed", payload=api_candidates)
    expected_task_count = len(acceptance_ids)
    _require(
        len(api_candidates.get("candidates", [])) == expected_task_count,
        "API candidate count mismatch",
        payload=api_candidates,
    )

    authoring_task_counts: dict[str, int] = {}
    for step_id, command, expected_track in AUTHORING_COMMANDS:
        payload = _run_json(
            steps,
            step_id,
            ["bin/governance", "design", command, ".", "--json"],
            target,
        )
        _require(payload.get("ok") is True, f"{command} failed", payload=payload)
        _require(payload.get("track") == expected_track, f"{command} track mismatch", payload=payload)
        tasks = payload.get("authoring_tasks")
        _require(isinstance(tasks, list), f"{command} did not return authoring_tasks", payload=payload)
        authoring_task_counts[command] = len(tasks)
        _require(len(tasks) == expected_task_count, f"{command} task count mismatch", payload=payload)
        _require(
            _authoring_summary_matches_tasks(payload),
            f"{command} authoring summary did not match task details",
            payload=payload,
        )
        _require(
            _skill_loading_plan_is_actionable(payload.get("skill_loading_plan")),
            f"{command} did not expose an actionable skill loading plan",
            payload=payload,
        )
        _require(
            _active_work_is_actionable(payload.get("active_work")),
            f"{command} did not expose actionable active work",
            payload=payload,
        )
        _require(
            all(
                isinstance(task, dict)
                and _skill_loading_plan_is_actionable(task.get("skill_loading_plan"))
                for task in tasks
            ),
            f"{command} tasks did not expose actionable skill loading plans",
            payload=payload,
        )
        _require(
            all(
                isinstance(link, dict) and isinstance(link.get("status"), str) and link["status"]
                for task in tasks
                if isinstance(task, dict)
                for link in task.get("required_links", [])
                if isinstance(task.get("required_links"), list)
            ),
            f"{command} required links did not expose machine-readable statuses",
            payload=payload,
        )
        _require(
            all(
                _task_link_repairs_cover_required_statuses(task)
                for task in tasks
                if isinstance(task, dict)
            ),
            f"{command} link repair actions did not cover non-satisfied required links",
            payload=payload,
        )

    design_workflow_plan = _run_json(
        steps,
        "workflow_plan_design_derivation",
        ["bin/governance", "workflow", "plan", ".", "--json"],
        target,
    )
    _require_design_workflow_plan(design_workflow_plan, "design workflow plan")

    make_design_workflow_plan = _run_json(
        steps,
        "make_workflow_plan_design_derivation",
        ["make", "workflow-plan"],
        target,
    )
    _require_design_workflow_plan(make_design_workflow_plan, "make workflow-plan design derivation")
    make_design_work_package = _run_json(
        steps,
        "make_work_package_design_derivation",
        ["make", "work-package"],
        target,
    )
    _require_active_work_package(
        make_design_work_package,
        phase="design-derivation",
        kind="design-authoring",
        queue_id="architecture-authoring",
    )

    implementation_preflight = _run_json(
        steps,
        "implementation_advance_check",
        ["bin/governance", "advance", "implementation", ".", "--check", "--json"],
        target,
        expected_returncode=1,
    )
    _require(implementation_preflight.get("ok") is False, "implementation gate unexpectedly passed")

    _write_minimal_implementation_ready_docs(target, acceptance_ids)
    implementation_ready_verify = _run_json(
        steps,
        "implementation_ready_verify_check",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    _require(implementation_ready_verify.get("ok") is True, "verification failed after implementation-ready docs")
    _require(
        implementation_ready_verify.get("findings") == [],
        "verification returned findings after implementation-ready docs",
        payload=implementation_ready_verify,
    )
    make_design_complete_work_package = _run_json(
        steps,
        "make_work_package_design_complete",
        ["make", "work-package"],
        target,
    )
    _require_complete_work_package(make_design_complete_work_package, "design-derivation")

    implementation_gate = _run_json(
        steps,
        "implementation_gate",
        ["bin/governance", "gate", "implementation", ".", "--json"],
        target,
    )
    _require(implementation_gate.get("ok") is True, "implementation gate did not pass after authored docs")

    implementation_advanced = _run_json(
        steps,
        "advance_implementation",
        ["bin/governance", "advance", "implementation", ".", "--json"],
        target,
    )
    _require(implementation_advanced.get("ok") is True, "implementation advance failed", payload=implementation_advanced)
    implementation_state = implementation_advanced.get("state")
    _require(
        isinstance(implementation_state, dict) and implementation_state.get("phase") == "implementation",
        "implementation advance did not record implementation phase",
        payload=implementation_advanced,
    )

    make_implementation_workflow_plan = _run_json(
        steps,
        "make_workflow_plan_implementation",
        ["make", "workflow-plan"],
        target,
    )
    _require_implementation_workflow_plan(
        make_implementation_workflow_plan,
        "make workflow-plan implementation",
    )
    make_implementation_work_package = _run_json(
        steps,
        "make_work_package_implementation",
        ["make", "work-package"],
        target,
    )
    _require_active_work_package(
        make_implementation_work_package,
        phase="implementation",
        kind="implementation-task",
        queue_id="implementation-plan",
    )

    implementation_plan = _run_json(
        steps,
        "implementation_plan",
        ["bin/governance", "implementation", "plan", ".", "--json"],
        target,
    )
    _require(
        _implementation_plan_is_actionable(implementation_plan),
        "implementation plan did not expose one actionable task with closeout command",
        payload=implementation_plan,
    )

    make_implementation_plan = _run_json(
        steps,
        "make_implementation_plan",
        ["make", "implementation-plan"],
        target,
    )
    _require(
        _implementation_plan_is_actionable(make_implementation_plan),
        "make implementation-plan did not expose one actionable task with closeout command",
        payload=make_implementation_plan,
    )

    implementation_start_preview = _run_json(
        steps,
        "implementation_start_preview",
        ["bin/governance", "implementation", "start", ".", "--task", IMPLEMENTATION_TASK_ID, "--json"],
        target,
    )
    _require(
        _implementation_start_ready(implementation_start_preview),
        "implementation start did not expose a safe In Progress status update plan",
        payload=implementation_start_preview,
    )
    implementation_start_apply = _run_json(
        steps,
        "implementation_start_apply",
        ["bin/governance", "implementation", "start", ".", "--task", IMPLEMENTATION_TASK_ID, "--apply", "--json"],
        target,
    )
    _require(
        _implementation_start_apply_completed(implementation_start_apply),
        "implementation start apply did not synchronize In Progress statuses",
        payload=implementation_start_apply,
    )
    implementation_plan_after_start = _run_json(
        steps,
        "implementation_plan_after_start",
        ["bin/governance", "implementation", "plan", ".", "--json"],
        target,
    )
    _require(
        _implementation_plan_is_in_progress(implementation_plan_after_start),
        "implementation plan did not resume the In Progress task after start apply",
        payload=implementation_plan_after_start,
    )

    closeout_without_evidence = _run_json(
        steps,
        "implementation_closeout_without_evidence",
        ["bin/governance", "implementation", "closeout", ".", "--task", IMPLEMENTATION_TASK_ID, "--json"],
        target,
    )
    _require(
        _closeout_blocks_without_evidence(closeout_without_evidence),
        "implementation closeout did not block Done without verification evidence",
        payload=closeout_without_evidence,
    )

    _write_minimal_closeout_evidence(target, acceptance_ids[0])
    closeout_with_evidence = _run_json(
        steps,
        "implementation_closeout_with_evidence",
        ["bin/governance", "implementation", "closeout", ".", "--task", IMPLEMENTATION_TASK_ID, "--json"],
        target,
    )
    _require(
        _closeout_ready_with_evidence(closeout_with_evidence),
        "implementation closeout did not become ready with passing local evidence",
        payload=closeout_with_evidence,
    )
    closeout_apply = _run_json(
        steps,
        "implementation_closeout_apply",
        ["bin/governance", "implementation", "closeout", ".", "--task", IMPLEMENTATION_TASK_ID, "--apply", "--json"],
        target,
    )
    _require(
        _closeout_apply_completed(closeout_apply),
        "implementation closeout apply did not synchronize Done statuses",
        payload=closeout_apply,
    )
    implementation_plan_after_closeout = _run_json(
        steps,
        "implementation_plan_after_closeout_apply",
        ["bin/governance", "implementation", "plan", ".", "--json"],
        target,
    )
    _require(
        _implementation_plan_is_complete(implementation_plan_after_closeout),
        "implementation plan did not report complete after closeout apply",
        payload=implementation_plan_after_closeout,
    )
    workflow_plan_after_closeout = _run_json(
        steps,
        "workflow_plan_after_closeout_apply",
        ["bin/governance", "workflow", "plan", ".", "--json"],
        target,
    )
    _require(
        _workflow_plan_is_implementation_complete(workflow_plan_after_closeout),
        "workflow plan did not report implementation complete after closeout apply",
        payload=workflow_plan_after_closeout,
    )
    runtime_refresh_check = _run_json(
        steps,
        "runtime_refresh_check_after_complete",
        [sys.executable, CLI, "runtime", "refresh", target, "--check", "--json"],
        ROOT,
    )
    _require(
        _runtime_refresh_check_is_ready(runtime_refresh_check),
        "runtime refresh check did not return a safe refresh plan after implementation complete",
        payload=runtime_refresh_check,
    )
    runtime_refresh = _run_json(
        steps,
        "runtime_refresh_after_complete",
        [sys.executable, CLI, "runtime", "refresh", target, "--json"],
        ROOT,
    )
    _require(
        _runtime_refresh_completed(runtime_refresh),
        "runtime refresh did not refresh target runtime and workflow-pack snapshot",
        payload=runtime_refresh,
    )
    make_workflow_plan_after_runtime_refresh = _run_json(
        steps,
        "make_workflow_plan_after_runtime_refresh",
        ["make", "workflow-plan"],
        target,
    )
    _require(
        _workflow_plan_is_implementation_complete(make_workflow_plan_after_runtime_refresh),
        "target-local make workflow-plan did not remain complete after runtime refresh",
        payload=make_workflow_plan_after_runtime_refresh,
    )
    make_work_package_after_runtime_refresh = _run_json(
        steps,
        "make_work_package_complete_after_runtime_refresh",
        ["make", "work-package"],
        target,
    )
    _require_complete_work_package(make_work_package_after_runtime_refresh, "implementation")

    final_status = _run_json(
        steps,
        "final_status",
        ["bin/governance", "status", ".", "--json"],
        target,
    )
    final_state = final_status.get("state")
    _require(isinstance(final_state, dict), "final status did not return state", payload=final_status)

    return {
        "ok": True,
        "workflow": "fresh-target-governance-dry-run",
        "steps": steps,
        "final_phase": final_state.get("phase"),
        "design_tracks": track_ids,
        "acceptance_ids": acceptance_ids,
        "acceptance_id_count": len(acceptance_ids),
        "api_candidate_count": len(api_candidates.get("candidates", [])),
        "authoring_task_counts": authoring_task_counts,
        "target_local_make_coverage": _target_local_make_coverage_details(steps),
        "implementation_gate": {
            "placeholder_blocked_ok": implementation_preflight.get("ok"),
            "placeholder_expected_blocked": True,
            "ready_ok": implementation_gate.get("ok"),
        },
        "implementation_start": {
            "task_id": IMPLEMENTATION_TASK_ID,
            "ready": implementation_start_preview.get("start_ready") is True,
            "applied_status_updates": implementation_start_apply.get("applied") is True,
            "implementation_plan_in_progress": implementation_plan_after_start.get("blocked") is False
            and implementation_plan_after_start.get("active_work", {}).get("status") == "in_progress",
            "status_update_paths": [
                str(update.get("path"))
                for update in implementation_start_preview.get("status_update_plan", {}).get("updates", [])
                if isinstance(update, dict)
            ],
            "apply_updated_paths": [
                str(path)
                for path in implementation_start_apply.get("updated_paths", [])
            ],
        },
        "implementation_closeout": {
            "task_id": IMPLEMENTATION_TASK_ID,
            "blocked_without_evidence": closeout_without_evidence.get("closeout_ready") is False,
            "ready_with_evidence": closeout_with_evidence.get("closeout_ready") is True,
            "applied_status_updates": closeout_apply.get("applied") is True,
            "implementation_plan_complete": implementation_plan_after_closeout.get("blocked") is False,
            "workflow_plan_complete": workflow_plan_after_closeout.get("blocked") is False,
            "blocking_codes_without_evidence": [
                str(requirement.get("code"))
                for requirement in closeout_without_evidence.get("blocking_requirements", [])
                if isinstance(requirement, dict)
            ],
            "status_update_paths": [
                str(update.get("path"))
                for update in closeout_with_evidence.get("status_update_plan", {}).get("updates", [])
                if isinstance(update, dict)
            ],
            "apply_updated_paths": [
                str(path)
                for path in closeout_apply.get("updated_paths", [])
            ],
        },
        "runtime_refresh": {
            "check_ok": runtime_refresh_check.get("ok") is True,
            "applied": runtime_refresh.get("ok") is True,
            "runtime_refreshed_at": isinstance(runtime_refresh.get("state"), dict)
            and isinstance(runtime_refresh["state"].get("runtime_refreshed_at"), str),
            "workflow_plan_complete_after_refresh": make_workflow_plan_after_runtime_refresh.get("blocked") is False,
            "work_package_complete_after_refresh": make_work_package_after_runtime_refresh.get("status") == "complete",
            "refreshed_required_paths": [
                path
                for path in (
                    "bin/governance",
                    "scripts/governance_cli.py",
                    "docs/agent-workflow/runtime-manifest.json",
                    "docs/agent-workflow/workflow-pack/manifest.json",
                )
                if path in runtime_refresh.get("refreshed", [])
            ],
        },
        "next": "execute exactly one Ready implementation task and apply closeout status updates after evidence passes",
    }


def _write_minimal_implementation_ready_docs(target: Path, acceptance_ids: list[str]) -> None:
    selected_acceptance = acceptance_ids[0]
    documents = {
        "docs/architecture/01-system-context.md": _architecture_system_context_doc(),
        "docs/architecture/02-containers.md": _architecture_containers_doc(),
        "docs/architecture/03-quality-attributes.md": _architecture_quality_attributes_doc(),
        "docs/api/00-conventions.md": _api_conventions_doc(),
        "docs/api/error-codes.md": _api_error_codes_doc(),
        "docs/api/changelog.md": _api_changelog_doc(),
        "docs/api/endpoints/01-endpoint-contract.md": _api_endpoint_contract_doc(),
        "docs/backend/01-modules.md": _backend_modules_doc(),
        "docs/backend/02-data-model.md": _backend_data_model_doc(),
        "docs/backend/03-external-services.md": _backend_external_services_doc(),
        "docs/ui/01-interaction-model.md": _ui_interaction_model_doc(),
        "docs/frontend/01-modules.md": _frontend_modules_doc(),
        "docs/frontend/02-api-consumption.md": _frontend_api_consumption_doc(),
        "docs/tests/01-strategy.md": _test_strategy_doc(),
        "docs/tests/02-acceptance-matrix.md": _acceptance_matrix_doc(acceptance_ids),
        "docs/development/01-roadmap.md": _roadmap_doc(),
        "docs/development/02-task-board.md": _task_board_doc(selected_acceptance, verification="make test"),
        "docs/development/03-verification-log.md": _verification_log_doc(),
    }
    for rel, text in documents.items():
        (target / rel).write_text(text, encoding="utf-8")


def _write_minimal_closeout_evidence(target: Path, acceptance_id: str) -> None:
    (target / "docs/development/02-task-board.md").write_text(
        _task_board_doc(acceptance_id, status="In Progress", verification="docs/development/03-verification-log.md"),
        encoding="utf-8",
    )
    (target / "docs/development/03-verification-log.md").write_text(
        _verification_log_doc(
            f"| {IMPLEMENTATION_TASK_ID} | make test | pass | 2026-07-08 | Local dry-run verification evidence. |\n"
        ),
        encoding="utf-8",
    )


def _architecture_system_context_doc() -> str:
    return (
        "# System Context\n\n"
        "## Product Links\n\n"
        "- [Product scope](../product/03-goals-and-requirements.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Actors\n\n"
        "- Maintainers use the governed workspace to run local checks.\n\n"
        "## External Systems\n\n"
        "- Git and local shell tools provide repository and verification execution.\n\n"
        "## Trust Boundaries\n\n"
        "- Product documents remain local Markdown sources before derived implementation.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _architecture_containers_doc() -> str:
    return (
        "# Containers\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [System context](01-system-context.md)\n\n"
        "## Containers\n\n"
        "- Governance CLI, docs tree, and project code form the first implementation boundary.\n\n"
        "## Runtime Responsibilities\n\n"
        "- The CLI checks repository state and reports machine-readable continuation payloads.\n\n"
        "## Data Ownership\n\n"
        "- Governance state is owned by `.governance/state.json` and Markdown sources.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _architecture_quality_attributes_doc() -> str:
    return (
        "# Quality Attributes\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [Containers](02-containers.md)\n\n"
        "## Availability\n\n"
        "- Local checks must fail clearly when required documents are incomplete.\n\n"
        "## Performance\n\n"
        "- Routine governance checks should run without network access or package installation.\n\n"
        "## Security\n\n"
        "- Agents must not guess behavior outside product and design sources.\n\n"
        "## Observability\n\n"
        "- Verification evidence is recorded in the local verification log.\n\n"
        "## Tradeoffs\n\n"
        "- Keep the first implementation slice small enough for a single Ready task.\n"
    )


def _api_conventions_doc() -> str:
    return (
        "# API Conventions\n\n"
        "## Product Links\n\n"
        "- [Product scope](../product/03-goals-and-requirements.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## HTTP Conventions\n\n"
        "- Use JSON for governance-related request and response examples.\n\n"
        "## Authentication\n\n"
        "- Local dry-run commands require no network authentication.\n\n"
        "## Idempotency\n\n"
        "- Repeated read-only checks must not write repository state.\n\n"
        "## Compatibility\n\n"
        "- Machine-readable payload fields should remain additive across workflow changes.\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _api_error_codes_doc() -> str:
    return (
        "# API Error Codes\n\n"
        "## Product Links\n\n"
        "- [Product scope](../product/03-goals-and-requirements.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Error Taxonomy\n\n"
        "- Governance failures are reported as stable findings with repair guidance.\n\n"
        "## Error Codes\n\n"
        "- GOVERNANCE_CHECK_FAILED: a local governance check failed before implementation.\n\n"
        "## Retry Semantics\n\n"
        "- Retry only after repairing the reported local source or environment issue.\n\n"
        "## Frontend Handling\n\n"
        "- User-facing agents summarize failures and stop before unsafe writes.\n"
    )


def _api_changelog_doc() -> str:
    return (
        "# API Changelog\n\n"
        "## Change Log\n\n"
        "- Initial governance dry-run contract baseline.\n\n"
        "## Compatibility Notes\n\n"
        "- Breaking payload changes require documentation and verification updates.\n"
    )


def _api_endpoint_contract_doc() -> str:
    return (
        "# Governance Check Endpoint\n\n"
        "## Method and Path\n\n"
        "POST /governance/checks\n\n"
        "## Auth\n\n"
        "- Local command execution uses repository permissions only.\n\n"
        "## Idempotency\n\n"
        "- Check requests are read-only unless explicitly marked as state-writing actions.\n\n"
        "## Request Fields\n\n"
        "- target: repository root to inspect.\n\n"
        "## Response Fields\n\n"
        "- ok: whether the governance check passed.\n"
        "- next_actions: ordered continuation actions when state is readable.\n\n"
        "## Error Codes\n\n"
        "- [GOVERNANCE_CHECK_FAILED](../error-codes.md)\n\n"
        "## Upstream Links\n\n"
        "- [Acceptance](../../product/08-acceptance-criteria.md#a-001)\n"
        "- [Backend owner](../../backend/01-modules.md)\n\n"
        "## Frontend Consumers\n\n"
        "- [Interaction model](../../ui/01-interaction-model.md)\n"
        "- [API consumption](../../frontend/02-api-consumption.md)\n"
    )


def _backend_modules_doc() -> str:
    return (
        "# Backend Modules\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Architecture Links\n\n"
        "- [Architecture context](../architecture/01-system-context.md)\n\n"
        "## Modules\n\n"
        "- Governance module owns local verification and continuation payload assembly.\n\n"
        "## API Ownership\n\n"
        "- Governance APIs follow [API conventions](../api/00-conventions.md).\n\n"
        "## Failure Modes\n\n"
        "- State failures follow [Data model](02-data-model.md).\n"
        "- Dependency failures follow [External services](03-external-services.md).\n\n"
        "## Open Decisions\n\n"
        "- none\n"
    )


def _backend_data_model_doc() -> str:
    return (
        "# Data Model\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Backend modules](01-modules.md)\n\n"
        "## Owners\n\n"
        "- Workflow state and verification evidence are local repository-owned data.\n\n"
        "## Entities\n\n"
        "- Task: a traceable implementation row with source and verification links.\n\n"
        "## State Machines\n\n"
        "- Task status moves from Backlog to Ready, In Progress, Blocked, Done, or Deferred.\n\n"
        "## Constraints\n\n"
        "- Done requires passing verification evidence linked from local Markdown.\n\n"
        "## Indexes\n\n"
        "- Task IDs and acceptance IDs provide lookup keys across governance documents.\n\n"
        "## Migrations\n\n"
        "- Schema changes require updated docs, tests, and verification evidence.\n"
    )


def _backend_external_services_doc() -> str:
    return (
        "# External Services\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Backend modules](01-modules.md)\n\n"
        "## Dependencies\n\n"
        "- Git, Python, ripgrep, Node, Corepack, and optional Pandoc are detected locally.\n\n"
        "## Contracts\n\n"
        "- Tool availability is reported by environment preflight JSON.\n\n"
        "## Retries\n\n"
        "- Retry environment repair only after explicit approval when escalation is required.\n\n"
        "## Timeouts\n\n"
        "- Long-running project checks should be recorded with their command and result.\n\n"
        "## Authentication\n\n"
        "- No external credentials are required for dry-run governance checks.\n\n"
        "## Observability\n\n"
        "- Tool status and command results are summarized in verification payloads.\n"
    )


def _ui_interaction_model_doc() -> str:
    return (
        "# Interaction Model\n\n"
        "## Product Links\n\n"
        "- [Product scope](../product/03-goals-and-requirements.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Primary Flows\n\n"
        "- An agent follows local commands, reads blockers, and continues from active work.\n\n"
        "## Screens\n\n"
        "- CLI JSON payloads are the primary interface for workflow continuation.\n\n"
        "## States\n\n"
        "- Ready, blocked, and closeout-ready states are explicit in payload fields.\n\n"
        "## Errors\n\n"
        "- Failed gates report repairable findings and stop before unsafe writes.\n\n"
        "## Accessibility\n\n"
        "- Human summaries keep command outcomes and next actions visible in text.\n"
    )


def _frontend_modules_doc() -> str:
    return (
        "# Frontend Modules\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## UI Links\n\n"
        "- [Interaction model](../ui/01-interaction-model.md)\n\n"
        "## Modules\n\n"
        "- Agent-facing workflow module reads JSON commands and active work payloads.\n\n"
        "## State Ownership\n\n"
        "- API-backed state follows [API consumption](02-api-consumption.md).\n\n"
        "## Routes\n\n"
        "- Implementation execution routes through task plan and closeout checks.\n\n"
        "## Open Decisions\n\n"
        "- API behavior follows [API conventions](../api/00-conventions.md).\n"
    )


def _frontend_api_consumption_doc() -> str:
    return (
        "# Frontend API Consumption\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## API Links\n\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Governance check endpoint](../api/endpoints/01-endpoint-contract.md)\n"
        "- [Frontend modules](01-modules.md)\n\n"
        "## Consumption Map\n\n"
        "- Implementation agents consume plan, gate, verify, and closeout payloads.\n\n"
        "## Loading States\n\n"
        "- Long checks report command progress through the local execution channel.\n\n"
        "## Error Actions\n\n"
        "- Missing evidence keeps Done unavailable until the closeout payload is ready.\n"
    )


def _test_strategy_doc() -> str:
    return (
        "# Test Strategy\n\n"
        "## Product Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n"
        "- [API conventions](../api/00-conventions.md)\n"
        "- [Architecture context](../architecture/01-system-context.md)\n\n"
        "## Acceptance Links\n\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Test Layers\n\n"
        "- Unit tests cover script behavior and JSON payload contracts.\n"
        "- Dry-run checks cover the repository workflow from product import to implementation planning.\n\n"
        "## Risk Coverage\n\n"
        "- Evidence gates prevent marking implementation tasks Done without passing local checks.\n\n"
        "## Non-Functional Checks\n\n"
        "- Pack verification and environment checks run before release handoff.\n"
    )


def _acceptance_matrix_doc(acceptance_ids: list[str]) -> str:
    rows = [
        f"| [{acceptance_id}](../product/08-acceptance-criteria.md#{acceptance_id.lower()}) | "
        "[Architecture context](../architecture/01-system-context.md) | "
        "[Governance check endpoint](../api/endpoints/01-endpoint-contract.md) | "
        "[Test strategy](01-strategy.md) |"
        for acceptance_id in acceptance_ids
    ]
    return (
        "# Acceptance Matrix\n\n"
        "## Matrix\n\n"
        "| Acceptance | Design | API | Test |\n"
        "| --- | --- | --- | --- |\n"
        + "\n".join(rows)
        + "\n\n"
        "## Uncovered Criteria\n\n"
        "- none\n"
    )


def _roadmap_doc() -> str:
    return (
        "# Roadmap\n\n"
        "## Product Links\n\n"
        "- [Product scope](../product/03-goals-and-requirements.md)\n"
        "- [Acceptance](../product/08-acceptance-criteria.md)\n\n"
        "## Milestones\n\n"
        "| ID | Status | Milestone |\n"
        "| --- | --- | --- |\n"
        f"| {IMPLEMENTATION_TASK_ID} | Ready | Implement local governance check flow |\n\n"
        "## Sequencing\n\n"
        "- Complete the first Ready task before marking downstream tasks Done.\n\n"
        "## Risks\n\n"
        "- Missing verification evidence must block Done status.\n\n"
        "## Deferred Scope\n\n"
        "- none\n"
    )


def _task_board_doc(acceptance_id: str, *, verification: str, status: str = "Ready") -> str:
    return (
        "# Task Board\n\n"
        "## Task Table\n\n"
        "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"| {IMPLEMENTATION_TASK_ID} | {status} | Implement local governance check flow | "
        "docs/product/03-goals-and-requirements.md | "
        "docs/architecture/01-system-context.md | "
        "docs/api/endpoints/01-endpoint-contract.md | "
        f"[{acceptance_id}](docs/product/08-acceptance-criteria.md#{acceptance_id.lower()}) | "
        f"{verification} |\n\n"
        "## Status Policy\n\n"
        "- Use Backlog, Ready, In Progress, Blocked, Done, or Deferred consistently.\n\n"
        "## Traceability Rules\n\n"
        "- Product, Design, API, and Acceptance fields must link to existing local Markdown sources.\n"
        "- Done tasks must link Verification to local Markdown evidence.\n"
    )


def _verification_log_doc(rows: str = "") -> str:
    return (
        "# Verification Log\n\n"
        "## Verification Runs\n\n"
        "| Task | Command | Result | Date | Notes |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"{rows}"
        "\n## Artifacts\n\n"
        "- none\n\n"
        "## Open Follow-ups\n\n"
        "- none\n"
    )


def _workflow_plan_has_queue(payload: dict[str, object], queue_id: str) -> bool:
    queues = payload.get("queues")
    if not isinstance(queues, list):
        return False
    return any(isinstance(queue, dict) and queue.get("id") == queue_id for queue in queues)


def _workflow_plan_has_skill(payload: dict[str, object], field: str, skill: str) -> bool:
    summary = payload.get("skill_summary")
    if not isinstance(summary, dict):
        return False
    skills = summary.get(field)
    return isinstance(skills, list) and skill in skills


def _target_local_make_coverage_details(steps: list[dict[str, object]]) -> dict[str, object]:
    step_ids = {str(step.get("id")) for step in steps if isinstance(step, dict)}
    return {
        "required_step_ids": TARGET_LOCAL_MAKE_STEP_IDS,
        "missing_step_ids": [step_id for step_id in TARGET_LOCAL_MAKE_STEP_IDS if step_id not in step_ids],
    }


def _env_repair_decision_allows_workflow(payload: dict[str, object]) -> bool:
    decision = payload.get("repair_decision")
    return (
        isinstance(decision, dict)
        and decision.get("decision") == "continue_workflow"
        and decision.get("stop_before_workflow") is False
        and decision.get("can_continue") is True
        and decision.get("runnable_action_ids") == []
        and decision.get("approval_action_ids") == []
        and decision.get("manual_action_ids") == []
    )


def _require_initialized_workflow_plan(payload: dict[str, object], label: str) -> None:
    _require(payload.get("ok") is True, f"{label} failed", payload=payload)
    _require(
        payload.get("phase") == "initialized",
        f"{label} phase mismatch",
        payload=payload,
    )
    _require(payload.get("queues") == [], f"{label} unexpectedly exposed phase queues", payload=payload)
    next_actions = payload.get("next_actions")
    _require(
        isinstance(next_actions, list)
        and any(isinstance(action, dict) and action.get("id") == "advance-product-structuring-check" for action in next_actions),
        f"{label} did not expose product-structuring continuation",
        payload=payload,
    )


def _require_phase_action_work_package(payload: dict[str, object], phase: str, next_action_id: str) -> None:
    _require(payload.get("ok") is True, f"{phase} work package failed", payload=payload)
    _require(payload.get("workflow") == "workflow-work-package", "work package workflow mismatch", payload=payload)
    _require(payload.get("phase") == phase, f"{phase} work package phase mismatch", payload=payload)
    _require(payload.get("package_available") is False, f"{phase} unexpectedly exposed a package", payload=payload)
    _require(payload.get("status") == "phase_action_required", f"{phase} work package status mismatch", payload=payload)
    next_action = payload.get("next_action")
    _require(
        isinstance(next_action, dict) and next_action.get("id") == next_action_id,
        f"{phase} work package did not expose {next_action_id}",
        payload=payload,
    )


def _require_active_work_package(
    payload: dict[str, object],
    *,
    phase: str,
    kind: str,
    queue_id: str,
) -> None:
    _require(payload.get("ok") is True, f"{phase} work package failed", payload=payload)
    _require(payload.get("workflow") == "workflow-work-package", "work package workflow mismatch", payload=payload)
    _require(payload.get("phase") == phase, f"{phase} work package phase mismatch", payload=payload)
    _require(payload.get("package_available") is True, f"{phase} work package missing", payload=payload)
    package = payload.get("work_package")
    _require(
        isinstance(package, dict)
        and package.get("kind") == kind
        and package.get("queue_id") == queue_id
        and bool(package.get("work_id")),
        f"{phase} work package identity mismatch",
        payload=payload,
    )
    readiness = payload.get("skill_readiness")
    _require(
        isinstance(readiness, dict)
        and isinstance(readiness.get("ready"), bool)
        and isinstance(readiness.get("resolved_requirements"), list),
        f"{phase} work package skill readiness missing",
        payload=payload,
    )
    _require(isinstance(payload.get("next_action"), dict), f"{phase} work package next action missing", payload=payload)


def _require_complete_work_package(payload: dict[str, object], phase: str) -> None:
    _require(payload.get("ok") is True, f"{phase} complete work package failed", payload=payload)
    _require(payload.get("phase") == phase, f"{phase} complete work package phase mismatch", payload=payload)
    _require(payload.get("package_available") is False, f"{phase} complete package unexpectedly available", payload=payload)
    _require(payload.get("status") == "complete", f"{phase} work package did not report complete", payload=payload)
    _require(payload.get("stop_before_work") is False, f"{phase} complete work package reported stop", payload=payload)


def _require_product_workflow_plan(payload: dict[str, object], label: str) -> None:
    _require(payload.get("ok") is True, f"{label} failed", payload=payload)
    _require(
        payload.get("phase") == "product-structuring",
        f"{label} phase mismatch",
        payload=payload,
    )
    _require(
        _workflow_plan_has_queue(payload, "product-plan"),
        f"{label} did not expose product-plan queue",
        payload=payload,
    )
    _require(
        _workflow_plan_has_skill(payload, "local_workflow_skills", "structuring-product-requirements"),
        f"{label} did not expose product structuring skill summary",
        payload=payload,
    )
    _require(
        _active_work_is_actionable(payload.get("active_work")),
        f"{label} did not expose actionable active work",
        payload=payload,
    )


def _require_design_workflow_plan(payload: dict[str, object], label: str) -> None:
    _require(payload.get("ok") is True, f"{label} failed", payload=payload)
    _require(
        payload.get("phase") == "design-derivation",
        f"{label} phase mismatch",
        payload=payload,
    )
    for queue_id in (
        "design-plan",
        "architecture-authoring",
        "api-candidates",
        "api-authoring",
        "backend-authoring",
        "data-model-authoring",
        "ui-interaction-authoring",
        "frontend-authoring",
    ):
        _require(
            _workflow_plan_has_queue(payload, queue_id),
            f"{label} did not expose {queue_id} queue",
            payload=payload,
        )
    for skill in (
        "senior-architect",
        "api-design-reviewer",
        "senior-backend",
        "database-schema-designer",
        "senior-frontend",
        "a11y-audit",
    ):
        _require(
            _workflow_plan_has_skill(payload, "authority_routing_skills", skill),
            f"{label} did not expose authority skill {skill}",
            payload=payload,
        )
    _require(
        _active_work_is_actionable(payload.get("active_work")),
        f"{label} did not expose actionable active work",
        payload=payload,
    )


def _require_implementation_workflow_plan(payload: dict[str, object], label: str) -> None:
    _require(payload.get("ok") is True, f"{label} failed", payload=payload)
    _require(
        payload.get("phase") == "implementation",
        f"{label} phase mismatch",
        payload=payload,
    )
    _require(
        _workflow_plan_has_queue(payload, "implementation-plan"),
        f"{label} did not expose implementation-plan queue",
        payload=payload,
    )
    _require(
        _workflow_plan_has_skill(payload, "local_workflow_skills", "executing-implementation-task"),
        f"{label} did not expose implementation execution skill summary",
        payload=payload,
    )
    _require(
        _workflow_plan_has_skill(payload, "authority_routing_skills", "senior-backend"),
        f"{label} did not expose backend authority skill",
        payload=payload,
    )
    _require(
        _active_work_is_actionable(payload.get("active_work")),
        f"{label} did not expose actionable active work",
        payload=payload,
    )


def _implementation_plan_is_actionable(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("decision_policy") != "execute_exactly_one_ready_task":
        return False
    if payload.get("gate_ok") is not True:
        return False
    summary = payload.get("implementation_summary")
    if not isinstance(summary, dict) or summary.get("actionable_ready_task_count") != 1:
        return False
    active_work = payload.get("active_work")
    if not isinstance(active_work, dict):
        return False
    if active_work.get("kind") != "implementation-task":
        return False
    if active_work.get("task_id") != IMPLEMENTATION_TASK_ID or active_work.get("status") != "ready":
        return False
    start_command = active_work.get("start_command")
    if not _valid_embedded_command(start_command):
        return False
    if start_command.get("argv") != [
        "bin/governance",
        "implementation",
        "start",
        ".",
        "--task",
        IMPLEMENTATION_TASK_ID,
        "--json",
    ]:
        return False
    closeout_command = active_work.get("closeout_command")
    if not _valid_embedded_command(closeout_command):
        return False
    if closeout_command.get("argv") != [
        "bin/governance",
        "implementation",
        "closeout",
        ".",
        "--task",
        IMPLEMENTATION_TASK_ID,
        "--json",
    ]:
        return False
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], dict):
        return False
    task = tasks[0]
    if task.get("task_id") != IMPLEMENTATION_TASK_ID or task.get("actionable") is not True:
        return False
    steps = task.get("steps")
    if not isinstance(steps, list):
        return False
    return any(isinstance(step, dict) and step.get("id") == "implementation-closeout" for step in steps)


def _implementation_start_ready(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("decision_policy") != "claim_exactly_one_ready_task_before_editing_code":
        return False
    if payload.get("start_ready") is not True or payload.get("target_status") != "In Progress":
        return False
    requirements = payload.get("requirements")
    if not isinstance(requirements, list) or any(
        not isinstance(requirement, dict) or requirement.get("status") != "satisfied"
        for requirement in requirements
    ):
        return False
    status_update_plan = payload.get("status_update_plan")
    if not isinstance(status_update_plan, dict):
        return False
    if status_update_plan.get("can_auto_apply") is not True:
        return False
    updates = status_update_plan.get("updates")
    if not isinstance(updates, list):
        return False
    update_paths = {str(update.get("path")) for update in updates if isinstance(update, dict)}
    update_targets = {str(update.get("to")) for update in updates if isinstance(update, dict)}
    return update_paths == {"docs/development/01-roadmap.md", "docs/development/02-task-board.md"} and update_targets == {
        "In Progress"
    }


def _implementation_start_apply_completed(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("start_ready") is not True:
        return False
    if payload.get("applied") is not True or payload.get("already_current") is not False:
        return False
    updated_paths = {str(path) for path in payload.get("updated_paths", [])}
    if updated_paths != {"docs/development/01-roadmap.md", "docs/development/02-task-board.md"}:
        return False
    status_update_plan = payload.get("post_apply_status_update_plan")
    return isinstance(status_update_plan, dict) and status_update_plan.get("updates_required") is False


def _implementation_plan_is_in_progress(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True or payload.get("blocked") is not False:
        return False
    summary = payload.get("implementation_summary")
    if not isinstance(summary, dict):
        return False
    if summary.get("in_progress_task_count") != 1 or summary.get("actionable_in_progress_task_count") != 1:
        return False
    active_work = payload.get("active_work")
    if not isinstance(active_work, dict):
        return False
    return active_work.get("task_id") == IMPLEMENTATION_TASK_ID and active_work.get("status") == "in_progress"


def _closeout_blocks_without_evidence(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("decision_policy") != "do_not_mark_done_without_passing_evidence":
        return False
    if payload.get("closeout_ready") is not False:
        return False
    blocking_codes = {
        str(requirement.get("code"))
        for requirement in payload.get("blocking_requirements", [])
        if isinstance(requirement, dict)
    }
    required_codes = {
        "verification_log_row_present",
        "verification_result_passing",
        "task_verification_links_local_evidence",
    }
    if not required_codes.issubset(blocking_codes):
        return False
    evidence = payload.get("evidence_summary")
    if not isinstance(evidence, dict):
        return False
    return (
        evidence.get("verification_logged") is False
        and evidence.get("passing_verification_logged") is False
        and evidence.get("verification_links_local_evidence") is False
    )


def _closeout_ready_with_evidence(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("closeout_ready") is not True:
        return False
    if payload.get("blocking_requirements") != []:
        return False
    evidence = payload.get("evidence_summary")
    if not isinstance(evidence, dict):
        return False
    if evidence.get("verification_logged") is not True:
        return False
    if evidence.get("passing_verification_logged") is not True:
        return False
    if evidence.get("verification_links_local_evidence") is not True:
        return False
    status_update_plan = payload.get("status_update_plan")
    if not isinstance(status_update_plan, dict):
        return False
    if status_update_plan.get("can_auto_apply") is not True:
        return False
    updates = status_update_plan.get("updates")
    if not isinstance(updates, list):
        return False
    update_paths = {str(update.get("path")) for update in updates if isinstance(update, dict)}
    return update_paths == {"docs/development/01-roadmap.md", "docs/development/02-task-board.md"}


def _closeout_apply_completed(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("apply_requested") is not True:
        return False
    if payload.get("applied") is not True:
        return False
    if payload.get("closeout_ready") is not True:
        return False
    if payload.get("blocking_requirements") != []:
        return False
    updated_paths = payload.get("updated_paths")
    if not isinstance(updated_paths, list):
        return False
    if set(str(path) for path in updated_paths) != {"docs/development/01-roadmap.md", "docs/development/02-task-board.md"}:
        return False
    evidence = payload.get("evidence_summary")
    if not isinstance(evidence, dict):
        return False
    if evidence.get("task_status") != "Done" or evidence.get("roadmap_status") != "Done":
        return False
    status_update_plan = payload.get("status_update_plan")
    if not isinstance(status_update_plan, dict):
        return False
    return (
        status_update_plan.get("updates_required") is False
        and status_update_plan.get("can_auto_apply") is False
        and status_update_plan.get("updates") == []
    )


def _implementation_plan_is_complete(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("blocked") is not False:
        return False
    summary = payload.get("implementation_summary")
    if not isinstance(summary, dict):
        return False
    if summary.get("execution_complete") is not True or summary.get("all_tasks_done") is not True:
        return False
    if int(summary.get("done_task_with_passing_evidence_count", 0)) != int(summary.get("task_count", -1)):
        return False
    active_work = payload.get("active_work")
    return (
        isinstance(active_work, dict)
        and active_work.get("kind") == "implementation-complete"
        and active_work.get("status") == "complete"
    )


def _workflow_plan_is_implementation_complete(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True:
        return False
    if payload.get("blocked") is not False:
        return False
    queues = payload.get("queues")
    if not isinstance(queues, list) or len(queues) != 1 or not isinstance(queues[0], dict):
        return False
    queue = queues[0]
    if queue.get("id") != "implementation-plan" or queue.get("status") != "complete":
        return False
    active_work = payload.get("active_work")
    return (
        isinstance(active_work, dict)
        and active_work.get("kind") == "implementation-complete"
        and active_work.get("status") == "complete"
        and active_work.get("queue_status") == "complete"
    )


def _runtime_refresh_check_is_ready(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True or payload.get("check") is not True:
        return False
    would_refresh = payload.get("would_refresh")
    if not isinstance(would_refresh, list):
        return False
    required_paths = {
        "bin/governance",
        "scripts/governance_cli.py",
        "docs/agent-workflow/runtime-manifest.json",
        "docs/agent-workflow/workflow-pack/manifest.json",
    }
    if not required_paths.issubset({str(path) for path in would_refresh}):
        return False
    if payload.get("refreshed") not in (None, []):
        return False
    if payload.get("removed") not in (None, []):
        return False
    return True


def _runtime_refresh_completed(payload: dict[str, object]) -> bool:
    if payload.get("ok") is not True or payload.get("check") is not False:
        return False
    refreshed = payload.get("refreshed")
    if not isinstance(refreshed, list):
        return False
    required_paths = {
        "bin/governance",
        "scripts/governance_cli.py",
        "docs/agent-workflow/runtime-manifest.json",
        "docs/agent-workflow/workflow-pack/manifest.json",
    }
    if not required_paths.issubset({str(path) for path in refreshed}):
        return False
    state = payload.get("state")
    if not isinstance(state, dict) or not isinstance(state.get("runtime_refreshed_at"), str):
        return False
    local_commands = payload.get("local_commands")
    if not isinstance(local_commands, list):
        return False
    return any(
        isinstance(command, dict)
        and command.get("make_target") == "workflow-plan"
        and command.get("argv") == ["make", "workflow-plan"]
        for command in local_commands
    )


def _design_tracks_have_skill_loading_plans(tracks: object) -> bool:
    if not isinstance(tracks, list) or not tracks:
        return False
    return all(
        isinstance(track, dict)
        and _skill_loading_plan_is_actionable(track.get("skill_loading_plan"))
        for track in tracks
    )


def _skill_loading_plan_is_actionable(plan: object) -> bool:
    if not isinstance(plan, dict):
        return False
    if plan.get("load_order") != "local_workflow_then_authority_routing":
        return False
    if plan.get("stop_condition") != "missing_required_local_workflow_skill_or_unavailable_authority_routing_skill":
        return False
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return False
    if [step.get("sequence") for step in steps if isinstance(step, dict)] != list(range(1, len(steps) + 1)):
        return False
    return all(
        isinstance(step, dict)
        and isinstance(step.get("name"), str)
        and step["name"]
        and step.get("action")
        in {"load_local_workflow_skill", "load_authority_routing_skill", "load_specialist_routing_skill"}
        and isinstance(step.get("missing_policy"), str)
        and step["missing_policy"]
        for step in steps
    )


def _active_work_is_actionable(work: object) -> bool:
    if not isinstance(work, dict):
        return False
    if not isinstance(work.get("kind"), str) or not work["kind"]:
        return False
    if not isinstance(work.get("status"), str) or not work["status"]:
        return False
    if not isinstance(work.get("blocker_count"), int):
        return False
    if not isinstance(work.get("open_decision_count"), int):
        return False
    if "queue_id" in work and not _valid_embedded_command(work.get("inspect_command")):
        return False
    if work["kind"] == "api-candidate":
        return _valid_embedded_command(work.get("refresh_command"))
    if work["kind"] in {"product-manual-authoring-task", "design-track", "design-authoring-task"}:
        return _valid_embedded_command(work.get("verify_command")) and _valid_embedded_command(
            work.get("refresh_command")
        )
    if work["kind"] == "implementation-task":
        if work.get("task_id") != IMPLEMENTATION_TASK_ID or work.get("status") not in {"ready", "in_progress"}:
            return False
        start_command = work.get("start_command")
        if start_command is not None and not _valid_embedded_command(start_command):
            return False
        closeout_command = work.get("closeout_command")
        refresh_command = work.get("refresh_command")
        if closeout_command is not None and not _valid_embedded_command(closeout_command):
            return False
        if refresh_command is not None and not _valid_embedded_command(refresh_command):
            return False
        return True
    return False


def _manual_authoring_summary_matches_tasks(payload: dict[str, object]) -> bool:
    tasks = payload.get("manual_authoring_tasks")
    summary = payload.get("manual_authoring_summary")
    if not isinstance(tasks, list) or not isinstance(summary, dict):
        return False
    return summary == _task_collection_summary(
        tasks,
        item_key="required_evidence",
        status_counts_key="required_evidence_status_counts",
        non_satisfied_count_key="non_satisfied_required_evidence_count",
        repair_actions_key="evidence_repair_actions",
        repair_action_count_key="evidence_repair_action_count",
    )


def _authoring_summary_matches_tasks(payload: dict[str, object]) -> bool:
    tasks = payload.get("authoring_tasks")
    summary = payload.get("authoring_summary")
    if not isinstance(tasks, list) or not isinstance(summary, dict):
        return False
    return summary == _task_collection_summary(
        tasks,
        item_key="required_links",
        status_counts_key="required_link_status_counts",
        non_satisfied_count_key="non_satisfied_required_link_count",
        repair_actions_key="link_repair_actions",
        repair_action_count_key="link_repair_action_count",
    )


def _task_collection_summary(
    tasks: list[object],
    *,
    item_key: str,
    status_counts_key: str,
    non_satisfied_count_key: str,
    repair_actions_key: str,
    repair_action_count_key: str,
) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    non_satisfied_count = 0
    open_decision_count = 0
    repair_action_count = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        open_decisions = task.get("open_decisions")
        if isinstance(open_decisions, list):
            open_decision_count += len(open_decisions)
        repair_actions = task.get(repair_actions_key)
        if isinstance(repair_actions, list):
            repair_action_count += len(repair_actions)
        items = task.get(item_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "unknown") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            if status != "satisfied":
                non_satisfied_count += 1
    return {
        "task_count": len(tasks),
        "open_decision_count": open_decision_count,
        status_counts_key: dict(sorted(status_counts.items())),
        non_satisfied_count_key: non_satisfied_count,
        repair_action_count_key: repair_action_count,
    }


def _task_link_repairs_cover_required_statuses(task: dict[str, object]) -> bool:
    links = task.get("required_links")
    actions = task.get("link_repair_actions")
    if not isinstance(links, list) or not isinstance(actions, list):
        return False
    action_keys = {
        (str(action.get("link_kind")), str(action.get("target")))
        for action in actions
        if _valid_repair_action(action, expected_kind="required-link-repair", item_key="link_kind")
    }
    for link in links:
        if not isinstance(link, dict):
            return False
        if link.get("status") == "satisfied":
            continue
        key = (str(link.get("kind")), str(link.get("target")))
        if key not in action_keys:
            return False
    return True


def _task_evidence_repairs_cover_required_statuses(task: dict[str, object]) -> bool:
    evidence_items = task.get("required_evidence")
    actions = task.get("evidence_repair_actions")
    if not isinstance(evidence_items, list) or not isinstance(actions, list):
        return False
    action_keys = {
        (str(action.get("evidence_id")), str(action.get("target")))
        for action in actions
        if _valid_repair_action(action, expected_kind="required-evidence-repair", item_key="evidence_id")
    }
    for evidence in evidence_items:
        if not isinstance(evidence, dict):
            return False
        if evidence.get("status") == "satisfied":
            continue
        key = (str(evidence.get("id")), str(evidence.get("target")))
        if key not in action_keys:
            return False
    return True


def _valid_repair_action(action: object, *, expected_kind: str, item_key: str) -> bool:
    if not isinstance(action, dict):
        return False
    required_strings = ("id", item_key, "target", "status", "repair_strategy", "success_condition")
    if any(not isinstance(action.get(key), str) or not action[key] for key in required_strings):
        return False
    if action.get("kind") != expected_kind:
        return False
    if not isinstance(action.get("sequence"), int) or action["sequence"] < 1:
        return False
    if not isinstance(action.get("reason"), str):
        return False
    if action.get("status") == "satisfied":
        return False
    if action.get("can_auto_apply") is not False:
        return False
    if action.get("writes_state") is not True:
        return False
    if action.get("approval_required") is not False:
        return False
    verify_command = action.get("verify_command")
    if not _valid_embedded_command(verify_command):
        return False
    if verify_command.get("argv") != ["bin/governance", "verify", ".", "--check", "--json"]:
        return False
    if not _valid_embedded_command(action.get("refresh_command")):
        return False
    return True


def _valid_embedded_command(command: object) -> bool:
    if not isinstance(command, dict):
        return False
    if not isinstance(command.get("id"), str) or not command["id"]:
        return False
    if not isinstance(command.get("cwd"), str) or not command["cwd"]:
        return False
    if not isinstance(command.get("command"), str) or not command["command"]:
        return False
    argv = command.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        return False
    if command.get("writes_state") is not False:
        return False
    if command.get("approval_required") is not False:
        return False
    if not isinstance(command.get("description"), str) or not command["description"]:
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a disposable docs-as-code governance workflow dry run.")
    parser.add_argument("--target", type=Path, help="Optional explicit target directory. The target is retained.")
    parser.add_argument("--product", type=Path, help="Optional product document. Defaults to a generated sample PRD.")
    parser.add_argument("--keep", action="store_true", help="Retain the generated temporary target on success.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    if payload.get("ok"):
        print(f"Dry run passed: {len(payload.get('steps', []))} steps")
        print(f"Final phase: {payload.get('final_phase')}")
        print(f"Target retained: {payload.get('target_retained')} ({payload.get('target')})")
        print(f"Next: {payload.get('next')}")
        return
    print(f"Dry run failed: {payload.get('error')}")
    print(f"Target retained: {payload.get('target_retained')} ({payload.get('target')})")
    failed_step = payload.get("failed_step")
    if failed_step:
        print(f"Failed step: {failed_step}")


def main() -> int:
    args = build_parser().parse_args()
    payload = run_dry_run(target=args.target, product=args.product, keep=args.keep)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
