from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .design_reviews import DESIGN_REVIEW_TRACK_ORDER, DESIGN_REVIEW_TRACK_SPECS
    from .source_process import run_source_command
except ImportError:  # pragma: no cover - direct script execution
    from design_reviews import DESIGN_REVIEW_TRACK_ORDER, DESIGN_REVIEW_TRACK_SPECS
    from source_process import run_source_command


ROOT = Path(__file__).resolve().parents[1]
DRY_RUN_STEP_TIMEOUT_SECONDS = 900.0
JSON_STEP_STDOUT_INLINE_BYTES = 64 * 1024
CLI = ROOT / "scripts" / "governance_cli.py"
CONSUMER_BOOTSTRAP = ROOT / "scripts" / "bootstrap_consumer_project.py"

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
IMPLEMENTATION_VERIFICATION_COMMAND = "dry-run-task-tests"
IMPLEMENTATION_VERIFICATION_RUN_ID = "VR-20260713T120000000000Z-01234567"
NODE_IMPLEMENTATION_VERIFICATION_COMMAND = "node-stack-tests"
NODE_IMPLEMENTATION_VERIFICATION_RUN_ID = "VR-20260713T120001000000Z-12345678"
RUST_IMPLEMENTATION_VERIFICATION_COMMAND = "rust-stack-tests"
RUST_IMPLEMENTATION_VERIFICATION_RUN_ID = "VR-20260713T120002000000Z-23456789"
DESIGN_REVIEW_REL = "docs/decisions/design-reviews.json"
OPTIONAL_PRODUCT_CHAPTERS = {
    "background-and-problems",
    "change-log",
    "functional-spec",
    "success-metrics",
}
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
    "make_project_env_plan",
]
MAKE_CLOCK_SKEW_WARNING_RES = (
    re.compile(
        r"^make(?:\[[0-9]+\])?: Warning: File '.+' has modification time "
        r"[0-9]+(?:\.[0-9]+)? s in the future$"
    ),
    re.compile(
        r"^make(?:\[[0-9]+\])?: warning:\s+Clock skew detected\.  "
        r"Your build may be incomplete\.$"
    ),
)


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


def _make_clock_skew_warnings(command: list[str], stderr: str) -> list[str]:
    if not stderr or not command or Path(command[0]).name != "make":
        return []
    lines = stderr.splitlines()
    if lines and all(any(pattern.fullmatch(line) for pattern in MAKE_CLOCK_SKEW_WARNING_RES) for line in lines):
        return lines
    return []


def _compact_successful_json_stdout(step: dict[str, object], stdout_text: str) -> None:
    stdout_bytes = stdout_text.encode("utf-8")
    if len(stdout_bytes) <= JSON_STEP_STDOUT_INLINE_BYTES:
        return
    step["stdout"] = ""
    step["stdout_compacted"] = True
    step["stdout_size_bytes"] = len(stdout_bytes)
    step["stdout_sha256"] = hashlib.sha256(stdout_bytes).hexdigest()


def _run_json(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    cwd: Path,
    *,
    expected_returncode: int = 0,
    env: dict[str, str] | None = None,
    timeout_seconds: float = DRY_RUN_STEP_TIMEOUT_SECONDS,
) -> dict[str, object]:
    command = _stringify_argv(argv)
    execution = run_source_command(
        command,
        cwd=cwd,
        env=env if env is not None else _agent_env(),
        timeout_seconds=timeout_seconds,
    )
    step = {
        "id": step_id,
        **execution,
        "expected_returncode": expected_returncode,
    }
    stdout = execution.get("stdout")
    stderr = execution.get("stderr")
    stdout_text = stdout if isinstance(stdout, str) else ""
    stderr_text = stderr if isinstance(stderr, str) else ""
    warnings = _make_clock_skew_warnings(command, stderr_text)
    if warnings:
        step["warnings"] = warnings
    steps.append(step)
    if execution.get("started") is not True:
        raise DryRunFailure(f"step did not start: {step_id}", step=step)
    if execution.get("timed_out") is True:
        raise DryRunFailure(f"step timed out: {step_id}", step=step)
    if execution.get("output_safe") is not True:
        raise DryRunFailure(f"step output is incomplete or redacted: {step_id}", step=step)
    if execution.get("returncode") != expected_returncode or (stderr_text and not warnings):
        raise DryRunFailure(f"step failed: {step_id}", step=step)
    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError as error:
        raise DryRunFailure(f"step did not return JSON: {step_id}: {error}", step=step) from error
    if not isinstance(payload, dict):
        raise DryRunFailure(f"step returned non-object JSON: {step_id}", step=step)
    step["payload_ok"] = payload.get("ok")
    _compact_successful_json_stdout(step, stdout_text)
    return payload


def _run_text(
    steps: list[dict[str, object]],
    step_id: str,
    argv: list[str | Path],
    cwd: Path,
    *,
    expected_returncode: int = 0,
    timeout_seconds: float = DRY_RUN_STEP_TIMEOUT_SECONDS,
) -> str:
    command = _stringify_argv(argv)
    execution = run_source_command(
        command,
        cwd=cwd,
        env=_agent_env(),
        timeout_seconds=timeout_seconds,
    )
    step = {
        "id": step_id,
        **execution,
        "expected_returncode": expected_returncode,
    }
    stdout = execution.get("stdout")
    stderr = execution.get("stderr")
    stdout_text = stdout if isinstance(stdout, str) else ""
    stderr_text = stderr if isinstance(stderr, str) else ""
    warnings = _make_clock_skew_warnings(command, stderr_text)
    if warnings:
        step["warnings"] = warnings
    steps.append(step)
    if execution.get("started") is not True:
        raise DryRunFailure(f"step did not start: {step_id}", step=step)
    if execution.get("timed_out") is True:
        raise DryRunFailure(f"step timed out: {step_id}", step=step)
    if execution.get("output_safe") is not True:
        raise DryRunFailure(f"step output is incomplete or redacted: {step_id}", step=step)
    if execution.get("returncode") != expected_returncode or (stderr_text and not warnings):
        raise DryRunFailure(f"step failed: {step_id}", step=step)
    stripped_stdout = stdout_text.strip()
    if stripped_stdout:
        step["stdout_first_line"] = stripped_stdout.splitlines()[0]
    return stdout_text


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

    _run_text(
        steps,
        "initialize_target_git",
        ["git", "init", "-q", "-b", "main"],
        target,
    )

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
    make_initialized_workflow_resume = _run_json(
        steps,
        "make_workflow_resume_initialized",
        ["make", "workflow-resume"],
        target,
    )
    _require_workflow_resume(
        make_initialized_workflow_resume,
        phase="initialized",
        status="action_ready",
        action_field="id",
        action_value="advance-product-structuring",
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

    make_project_env_plan = _run_json(
        steps,
        "make_project_env_plan",
        ["make", "project-env-plan"],
        target,
    )
    _require(make_project_env_plan.get("ok") is True, "make project-env-plan failed", payload=make_project_env_plan)
    _require(
        make_project_env_plan.get("status") == "registration_required"
        and make_project_env_plan.get("tool_count") == 0,
        "make project-env-plan did not report an empty reviewed project runtime",
        payload=make_project_env_plan,
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
    make_product_workflow_resume = _run_json(
        steps,
        "make_workflow_resume_product_structuring",
        ["make", "workflow-resume"],
        target,
    )
    _require_workflow_resume(
        make_product_workflow_resume,
        phase="product-structuring",
        status="work_ready",
        action_field="kind",
        action_value="decide-product-chapter",
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

    product_disposition_applies = _record_optional_product_dispositions(
        target,
        product_plan,
        steps,
    )
    product_plan_after_dispositions = _run_json(
        steps,
        "product_plan_after_dispositions",
        ["bin/governance", "product", "plan", ".", "--json"],
        target,
    )
    _require(
        product_plan_after_dispositions.get("ok") is True,
        "product plan failed after chapter dispositions",
        payload=product_plan_after_dispositions,
    )
    _require(
        product_plan_after_dispositions.get("required_decisions") == [],
        "product chapter dispositions did not resolve every unsupported optional chapter",
        payload=product_plan_after_dispositions,
    )
    disposition_summary = product_plan_after_dispositions.get("disposition_summary")
    _require(
        isinstance(disposition_summary, dict)
        and disposition_summary.get("active_count") == len(product_disposition_applies)
        and disposition_summary.get("omit_unsupported_count") == len(product_disposition_applies)
        and disposition_summary.get("stale_count") == 0,
        "product disposition summary did not match recorded decisions",
        payload=product_plan_after_dispositions,
    )
    work_package_after_product_dispositions = _run_json(
        steps,
        "work_package_after_product_dispositions",
        ["make", "work-package"],
        target,
    )
    _require_phase_action_work_package(
        work_package_after_product_dispositions,
        "product-structuring",
        "advance-design-derivation-check",
    )
    product_dispositions_verify = _run_json(
        steps,
        "product_dispositions_verify_check",
        ["bin/governance", "verify", ".", "--check", "--json"],
        target,
    )
    _require(
        product_dispositions_verify.get("ok") is True
        and product_dispositions_verify.get("findings") == [],
        "verification failed after product chapter dispositions",
        payload=product_dispositions_verify,
    )

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

    repair_installer = target / "tools/install-dry-run-runtime"
    repair_installer.parent.mkdir(parents=True, exist_ok=True)
    repair_installer.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "mkdir -p tools-bin\n"
        "printf '%s\\n' '#!/bin/sh' 'printf \"Dry 1.2.0\\n\"' > tools-bin/dry-run-runtime\n"
        "chmod +x tools-bin/dry-run-runtime\n",
        encoding="utf-8",
    )
    repair_installer.chmod(0o755)
    repair_env = _agent_env()
    repair_env["PATH"] = os.pathsep.join(
        [str(target / "tools-bin"), repair_env.get("PATH", "")]
    )
    project_runtime_registered = _run_json(
        steps,
        "project_environment_reviewed_repair_register",
        [
            "bin/governance",
            "project-env",
            "register",
            ".",
            "--tool-id",
            "dry-run-runtime",
            "--executable",
            "dry-run-runtime",
            "--version-prefix",
            "Dry ",
            "--minimum-version",
            "1.0.0",
            "--maximum-exclusive-version",
            "2.0.0",
            "--repair-strategy",
            "reviewed-command",
            "--repair-source-type",
            "official-url",
            "--repair-source",
            "https://example.com/dry-run-runtime",
            "--review-evidence",
            "docs/agent-workflow/workflow-pack/references/project-environment-contract.md",
            "--repair-instructions",
            "Run the reviewed dry-run runtime installer.",
            "--repair-command-cwd",
            ".",
            "--repair-command-arg",
            "tools/install-dry-run-runtime",
            "--reviewed",
            "--json",
        ],
        target,
        env=repair_env,
    )
    _require(
        project_runtime_registered.get("ok") is True
        and project_runtime_registered.get("action") == "register",
        "reviewed project runtime registration failed",
        payload=project_runtime_registered,
    )
    project_repair_preview = _run_json(
        steps,
        "project_environment_reviewed_repair_preview",
        [
            "bin/governance",
            "project-env",
            "repair",
            ".",
            "--tool-id",
            "dry-run-runtime",
            "--check",
            "--json",
        ],
        target,
        env=repair_env,
    )
    _require(
        project_repair_preview.get("ok") is True
        and project_repair_preview.get("action") == "approval-required"
        and project_repair_preview.get("repair_ready") is True
        and project_repair_preview.get("environment_ready") is False,
        "reviewed project runtime repair preview did not expose approval gating",
        payload=project_repair_preview,
    )
    project_repair_blocked = _run_json(
        steps,
        "project_environment_reviewed_repair_unapproved",
        [
            "bin/governance",
            "project-env",
            "repair",
            ".",
            "--tool-id",
            "dry-run-runtime",
            "--json",
        ],
        target,
        expected_returncode=1,
        env=repair_env,
    )
    _require(
        project_repair_blocked.get("action") == "approval-required"
        and not (target / "tools-bin/dry-run-runtime").exists(),
        "unapproved project runtime repair was not blocked",
        payload=project_repair_blocked,
    )
    project_repaired = _run_json(
        steps,
        "project_environment_reviewed_repair_apply",
        [
            "bin/governance",
            "project-env",
            "repair",
            ".",
            "--tool-id",
            "dry-run-runtime",
            "--approved",
            "--json",
        ],
        target,
        env=repair_env,
    )
    _require(
        project_repaired.get("ok") is True
        and project_repaired.get("action") == "repaired"
        and project_repaired.get("environment_ready") is True,
        "approved project runtime repair did not pass post-repair readiness",
        payload=project_repaired,
    )
    repaired_project_plan = _run_json(
        steps,
        "project_environment_repaired_plan",
        ["bin/governance", "project-env", "plan", ".", "--json"],
        target,
        env=repair_env,
    )
    repair_summary = repaired_project_plan.get("repair_evidence_summary")
    _require(
        isinstance(repair_summary, dict)
        and repair_summary.get("record_count") == 1
        and repair_summary.get("pending_count") == 0,
        "project runtime repair evidence summary is incomplete",
        payload=repaired_project_plan,
    )
    _remove_dry_run_runtime_registration(target)
    project_plan_after_repair_fixture_cleanup = _run_json(
        steps,
        "project_environment_plan_after_repair_fixture_cleanup",
        ["bin/governance", "project-env", "plan", ".", "--json"],
        target,
    )
    _require(
        project_plan_after_repair_fixture_cleanup.get("tool_count") == 0
        and project_plan_after_repair_fixture_cleanup.get("coverage_status") == "not_required",
        "dry-run repair fixture registration cleanup failed",
        payload=project_plan_after_repair_fixture_cleanup,
    )

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
    make_design_workflow_resume = _run_json(
        steps,
        "make_workflow_resume_design_derivation",
        ["make", "workflow-resume"],
        target,
    )
    _require_workflow_resume(
        make_design_workflow_resume,
        phase="design-derivation",
        status="work_ready",
        action_field="kind",
        action_value="author-design-documents",
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
    node_runtime_registration = _register_stack_runtime(
        target,
        steps,
        env=repair_env,
        stack="node",
        tool_id="node-runtime",
        executable="node",
        version_prefix="v",
        minimum_version="18.0.0",
        maximum_exclusive_version="24.0.0",
        repair_source="https://nodejs.org/en/download",
        repair_instructions="Install a reviewed Node.js LTS release from the official distribution.",
    )
    _write_threat_review_inputs(target)
    _write_reliability_review_inputs(target)
    _write_migration_review_inputs(target)
    threat_review_apply = _record_threat_review(target, steps)
    api_review_apply = _record_api_review(target, steps)
    reliability_review_apply = _record_reliability_review(target, steps)
    migration_review_apply = _record_migration_review(target, steps)
    design_review_applies = _record_design_reviews(
        target,
        acceptance_ids,
        steps,
    )
    reviewed_design_plan = _run_json(
        steps,
        "design_plan_after_reviews",
        ["bin/governance", "design", "plan", ".", "--json"],
        target,
    )
    expected_design_review_count = len(DESIGN_REVIEW_TRACK_ORDER) * len(acceptance_ids)
    authority_report_count = 0
    decision_report_count = 0
    for applied_review in design_review_applies:
        review = applied_review.get("review")
        review_value = review if isinstance(review, dict) else {}
        authority_report = review_value.get("authority_report")
        authority_report_value = authority_report if isinstance(authority_report, dict) else {}
        report_content = authority_report_value.get("content")
        report_content_value = report_content if isinstance(report_content, dict) else {}
        if (
            str(authority_report_value.get("path", "")).startswith(
                ".governance/design-review-reports/"
            )
            and re.fullmatch(r"[0-9a-f]{64}", str(authority_report_value.get("sha256", "")))
            is not None
            and report_content_value
        ):
            authority_report_count += 1
        report_decisions = report_content_value.get("decisions")
        decision_ids = (
            [
                str(item.get("id", ""))
                for item in report_decisions
                if isinstance(item, dict)
            ]
            if isinstance(report_decisions, list)
            else []
        )
        reviewed_decisions = review_value.get("reviewed_decisions")
        if isinstance(reviewed_decisions, list) and decision_ids == reviewed_decisions:
            decision_report_count += 1
    design_review_summary = reviewed_design_plan.get("design_review_summary")
    _require(
        reviewed_design_plan.get("ok") is True
        and isinstance(design_review_summary, dict)
        and design_review_summary.get("expected_count") == expected_design_review_count
        and design_review_summary.get("active_count") == expected_design_review_count
        and design_review_summary.get("missing_count") == 0
        and design_review_summary.get("stale_count") == 0
        and authority_report_count == expected_design_review_count
        and decision_report_count == expected_design_review_count,
        "design authority reviews did not cover every acceptance and track",
        payload=reviewed_design_plan,
    )
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

    consumer_resume_implementation_handoff: dict[str, object] = {}
    consumer_resume_implementation_reentry: dict[str, object] = {}
    if (ROOT / "pack-manifest.json").is_file():
        consumer_resume_implementation_handoff = _run_json(
            steps,
            "consumer_resume_implementation_handoff",
            [
                sys.executable,
                CONSUMER_BOOTSTRAP,
                "--target",
                target,
                "--resume",
                "--workflow-preset",
                "implementation-routing",
                "--json",
            ],
            ROOT,
        )
        _require(
            _consumer_resume_handoff_ready(consumer_resume_implementation_handoff, target),
            "consumer resume did not return a snapshot-guarded Ready task handoff",
            payload=consumer_resume_implementation_handoff,
        )
        consumer_resume_implementation_reentry = _run_json(
            steps,
            "consumer_resume_implementation_reentry",
            [
                sys.executable,
                CONSUMER_BOOTSTRAP,
                "--target",
                target,
                "--resume",
                "--workflow-preset",
                "implementation-routing",
                "--json",
            ],
            ROOT,
        )
        _require(
            _consumer_resume_reentry_ready(
                consumer_resume_implementation_reentry,
                consumer_resume_implementation_handoff,
                target,
            ),
            "consumer resume did not idempotently refresh the recorded implementation handoff",
            payload=consumer_resume_implementation_reentry,
        )
        resume_routing = consumer_resume_implementation_handoff.get("implementation_routing")
        resume_routing_map = resume_routing if isinstance(resume_routing, dict) else {}
        resume_advance_apply = resume_routing_map.get("implementation_advance_apply")
        resume_advance_apply_map = resume_advance_apply if isinstance(resume_advance_apply, dict) else {}
        resume_advance = resume_advance_apply_map.get("advance")
        implementation_advanced = resume_advance if isinstance(resume_advance, dict) else {}
    else:
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
    make_implementation_workflow_resume = _run_json(
        steps,
        "make_workflow_resume_implementation",
        ["make", "workflow-resume"],
        target,
    )
    _require_workflow_resume(
        make_implementation_workflow_resume,
        phase="implementation",
        status="work_ready",
        action_field="kind",
        action_value="claim-implementation-task",
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

    make_implementation_run_check = _run_json(
        steps,
        "make_implementation_run_check",
        ["make", "implementation-run-check"],
        target,
    )
    ready_snapshot = str(make_implementation_run_check.get("snapshot", {}).get("id", ""))
    _require(
        make_implementation_run_check.get("ok") is True
        and make_implementation_run_check.get("check") is True
        and make_implementation_run_check.get("status") == "ready_to_start"
        and make_implementation_run_check.get("task_id") == IMPLEMENTATION_TASK_ID
        and bool(ready_snapshot),
        "make implementation-run-check did not select a snapshot-guarded Ready task",
        payload=make_implementation_run_check,
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
    implementation_run_apply_start = _run_json(
        steps,
        "implementation_run_apply_start",
        [
            "bin/governance",
            "implementation",
            "run",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--apply-start",
            "--expect-snapshot",
            ready_snapshot,
            "--json",
        ],
        target,
    )
    _require(
        implementation_run_apply_start.get("ok") is True
        and implementation_run_apply_start.get("status") == "implementation_required"
        and implementation_run_apply_start.get("start_applied") is True
        and implementation_run_apply_start.get("executed") is False,
        "implementation run did not claim exactly one task and stop for code edits",
        payload=implementation_run_apply_start,
    )
    implementation_start_apply = dict(implementation_run_apply_start.get("start_apply", {}))
    _require(
        _implementation_start_apply_completed(implementation_start_apply),
        "implementation run start apply did not synchronize In Progress statuses",
        payload=implementation_start_apply,
    )
    _write_dry_run_implementation_change(target)
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

    implementation_verification_preview = _run_json(
        steps,
        "implementation_verification_preview",
        [
            "bin/governance",
            "implementation",
            "verify",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--command",
            IMPLEMENTATION_VERIFICATION_COMMAND,
            "--run-id",
            IMPLEMENTATION_VERIFICATION_RUN_ID,
            "--check",
            "--json",
        ],
        target,
    )
    _require(
        _implementation_verification_preview_ready(
            implementation_verification_preview,
            command_name=IMPLEMENTATION_VERIFICATION_COMMAND,
            executable="python3",
            environment_id="core-governance",
        ),
        "implementation verification preflight did not expose an exact no-write command plan",
        payload=implementation_verification_preview,
    )
    implementation_verification_execute = _run_json(
        steps,
        "implementation_verification_execute",
        [
            "bin/governance",
            "implementation",
            "verify",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--command",
            IMPLEMENTATION_VERIFICATION_COMMAND,
            "--run-id",
            IMPLEMENTATION_VERIFICATION_RUN_ID,
            "--json",
        ],
        target,
    )
    _require(
        _implementation_verification_completed(implementation_verification_execute),
        "implementation verification did not execute and atomically record passing evidence",
        payload=implementation_verification_execute,
    )
    node_verification_preview = _run_json(
        steps,
        "implementation_node_verification_preview",
        [
            "bin/governance",
            "implementation",
            "verify",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--command",
            NODE_IMPLEMENTATION_VERIFICATION_COMMAND,
            "--run-id",
            NODE_IMPLEMENTATION_VERIFICATION_RUN_ID,
            "--check",
            "--json",
        ],
        target,
        env=repair_env,
    )
    _require(
        _implementation_verification_preview_ready(
            node_verification_preview,
            command_name=NODE_IMPLEMENTATION_VERIFICATION_COMMAND,
            executable="node",
            environment_id="project-runtime",
        ),
        "Node.js stack verification preflight did not become ready",
        payload=node_verification_preview,
    )
    (
        rust_runtime_registration,
        rust_verification_preview,
        rust_verification_execute,
    ) = _run_optional_rust_stack_acceptance(target, steps, repair_env)

    implementation_run_check_in_progress = _run_json(
        steps,
        "implementation_run_check_in_progress",
        [
            "bin/governance",
            "implementation",
            "run",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--check",
            "--json",
        ],
        target,
        env=repair_env,
    )
    run_check_summary = implementation_run_check_in_progress.get("verification_summary", {})
    _require(
        implementation_run_check_in_progress.get("ok") is True
        and implementation_run_check_in_progress.get("status") == "verification_ready"
        and implementation_run_check_in_progress.get("executed") is False
        and run_check_summary.get("required_count") == 2
        and run_check_summary.get("ready_count") == 2
        and run_check_summary.get("all_ready") is True,
        "implementation run did not preflight every bound verification command",
        payload=implementation_run_check_in_progress,
    )
    implementation_run_execute_argv = implementation_run_check_in_progress.get("next_action", {}).get("argv", [])
    _require(
        isinstance(implementation_run_execute_argv, list)
        and "--execute" in implementation_run_execute_argv
        and "--expect-snapshot" in implementation_run_execute_argv,
        "implementation run preflight did not return a snapshot-guarded execute action",
        payload=implementation_run_check_in_progress,
    )
    implementation_run_execute = _run_json(
        steps,
        "implementation_run_execute",
        implementation_run_execute_argv,
        target,
        env=repair_env,
    )
    run_execute_summary = implementation_run_execute.get("verification_summary", {})
    _require(
        implementation_run_execute.get("ok") is True
        and implementation_run_execute.get("status") == "closeout_blocked"
        and implementation_run_execute.get("executed") is True
        and run_execute_summary.get("required_count") == 2
        and run_execute_summary.get("passed_count") == 2
        and run_execute_summary.get("all_passed") is True
        and implementation_run_execute.get("next_action", {}).get("id")
        == "inspect-implementation-code-review",
        "implementation run did not execute every binding and route the complete change set to review",
        payload=implementation_run_execute,
    )

    node_verification_execute = _run_json(
        steps,
        "implementation_node_verification_execute",
        [
            "bin/governance",
            "implementation",
            "verify",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--command",
            NODE_IMPLEMENTATION_VERIFICATION_COMMAND,
            "--run-id",
            NODE_IMPLEMENTATION_VERIFICATION_RUN_ID,
            "--json",
        ],
        target,
        env=repair_env,
    )
    _require(
        _implementation_verification_completed(node_verification_execute),
        "Node.js stack tests did not execute and record passing evidence",
        payload=node_verification_execute,
    )

    implementation_review_plan = _run_json(
        steps,
        "implementation_review_plan",
        ["bin/governance", "implementation", "review", ".", "--task", IMPLEMENTATION_TASK_ID, "--json"],
        target,
    )
    _require(
        implementation_review_plan.get("ok") is True
        and implementation_review_plan.get("status") == "review_required"
        and implementation_review_plan.get("authority_skill", {}).get("name") == "code-reviewer"
        and implementation_review_plan.get("authority_skill", {}).get("provenance_ready") is True
        and "src/dry_run_task.py" in implementation_review_plan.get("change_set", {}).get("changed_paths", []),
        "implementation review did not expose the provenance-backed complete task change set",
        payload=implementation_review_plan,
    )
    implementation_review_report = _write_implementation_review_report(target)
    implementation_review_preview = _run_json(
        steps,
        "implementation_review_preview",
        [
            "bin/governance",
            "implementation",
            "review",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--report",
            str(implementation_review_report.relative_to(target)),
            "--reviewed",
            "--check",
            "--json",
        ],
        target,
    )
    _require(
        implementation_review_preview.get("ok") is True
        and implementation_review_preview.get("review_ready") is True
        and implementation_review_preview.get("would_update")
        == ["docs/development/05-code-review-evidence.json"],
        "implementation review report preflight did not become ready",
        payload=implementation_review_preview,
    )
    implementation_review_record = _run_json(
        steps,
        "implementation_review_record",
        [
            "bin/governance",
            "implementation",
            "review",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--report",
            str(implementation_review_report.relative_to(target)),
            "--reviewed",
            "--json",
        ],
        target,
    )
    _require(
        implementation_review_record.get("ok") is True
        and implementation_review_record.get("status") == "current"
        and implementation_review_record.get("evidence_current") is True
        and implementation_review_record.get("updated")
        == ["docs/development/05-code-review-evidence.json"],
        "implementation review evidence was not recorded",
        payload=implementation_review_record,
    )
    implementation_run_reviewed_check = _run_json(
        steps,
        "implementation_run_reviewed_check",
        [
            "bin/governance",
            "implementation",
            "run",
            ".",
            "--task",
            IMPLEMENTATION_TASK_ID,
            "--check",
            "--json",
        ],
        target,
        env=repair_env,
    )
    _require(
        implementation_run_reviewed_check.get("ok") is True
        and implementation_run_reviewed_check.get("status") == "closeout_ready"
        and implementation_run_reviewed_check.get("executed") is False,
        "implementation runner did not accept current review evidence for closeout",
        payload=implementation_run_reviewed_check,
    )
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
    implementation_run_closeout_argv = implementation_run_reviewed_check.get("next_action", {}).get("argv", [])
    _require(
        isinstance(implementation_run_closeout_argv, list)
        and "--closeout" in implementation_run_closeout_argv
        and "--expect-snapshot" in implementation_run_closeout_argv,
        "implementation run execute did not return a snapshot-guarded closeout action",
        payload=implementation_run_reviewed_check,
    )
    implementation_run_closeout = _run_json(
        steps,
        "implementation_run_closeout",
        implementation_run_closeout_argv,
        target,
        env=repair_env,
    )
    _require(
        implementation_run_closeout.get("ok") is True
        and implementation_run_closeout.get("status") == "complete"
        and implementation_run_closeout.get("closeout_applied") is True,
        "implementation run did not apply closeout after passing evidence",
        payload=implementation_run_closeout,
    )
    closeout_apply = dict(implementation_run_closeout.get("closeout_apply", {}))
    _require(
        _closeout_apply_completed(closeout_apply),
        "implementation run closeout did not synchronize Done statuses",
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
    api_review_after_runtime_refresh = _run_json(
        steps,
        "api_review_check_after_runtime_refresh",
        ["bin/governance", "design", "api-review", ".", "--reviewed", "--check", "--json"],
        target,
    )
    _require(
        api_review_after_runtime_refresh.get("ok") is True
        and api_review_after_runtime_refresh.get("would_update") == [],
        "API machine-review evidence did not remain current after runtime refresh",
        payload=api_review_after_runtime_refresh,
    )
    threat_review_after_runtime_refresh = _run_json(
        steps,
        "threat_review_check_after_runtime_refresh",
        ["bin/governance", "design", "threat-review", ".", "--reviewed", "--check", "--json"],
        target,
    )
    _require(
        threat_review_after_runtime_refresh.get("ok") is True
        and threat_review_after_runtime_refresh.get("would_update") == [],
        "architecture threat-review evidence did not remain current after runtime refresh",
        payload=threat_review_after_runtime_refresh,
    )
    reliability_review_after_runtime_refresh = _run_json(
        steps,
        "reliability_review_check_after_runtime_refresh",
        ["bin/governance", "design", "reliability-review", ".", "--reviewed", "--check", "--json"],
        target,
    )
    _require(
        reliability_review_after_runtime_refresh.get("ok") is True
        and reliability_review_after_runtime_refresh.get("would_update") == [],
        "backend reliability-review evidence did not remain current after runtime refresh",
        payload=reliability_review_after_runtime_refresh,
    )
    migration_review_after_runtime_refresh = _run_json(
        steps,
        "migration_review_check_after_runtime_refresh",
        ["bin/governance", "design", "migration-review", ".", "--reviewed", "--check", "--json"],
        target,
    )
    _require(
        migration_review_after_runtime_refresh.get("ok") is True
        and migration_review_after_runtime_refresh.get("would_update") == [],
        "data-model migration-review evidence did not remain current after runtime refresh",
        payload=migration_review_after_runtime_refresh,
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
    make_workflow_resume_after_runtime_refresh = _run_json(
        steps,
        "make_workflow_resume_complete_after_runtime_refresh",
        ["make", "workflow-resume"],
        target,
    )
    _require_workflow_resume(
        make_workflow_resume_after_runtime_refresh,
        phase="implementation",
        status="complete",
    )

    final_status = _run_json(
        steps,
        "final_status",
        ["bin/governance", "status", ".", "--json"],
        target,
    )
    final_state = final_status.get("state")
    _require(isinstance(final_state, dict), "final status did not return state", payload=final_status)
    stack_acceptance = _build_stack_acceptance_summary(
        python_preview=implementation_verification_preview,
        python_execute=implementation_verification_execute,
        node_registration=node_runtime_registration,
        node_preview=node_verification_preview,
        node_execute=node_verification_execute,
        rust_registration=rust_runtime_registration,
        rust_preview=rust_verification_preview,
        rust_execute=rust_verification_execute,
    )

    return {
        "ok": True,
        "workflow": "fresh-target-governance-dry-run",
        "steps": steps,
        "stack_acceptance": stack_acceptance,
        "final_phase": final_state.get("phase"),
        "design_tracks": track_ids,
        "acceptance_ids": acceptance_ids,
        "acceptance_id_count": len(acceptance_ids),
        "api_candidate_count": len(api_candidates.get("candidates", [])),
        "authoring_task_counts": authoring_task_counts,
        "product_dispositions": {
            "recorded_count": len(product_disposition_applies),
            "omit_unsupported_count": disposition_summary.get("omit_unsupported_count", 0),
            "unresolved_decision_count": len(product_plan_after_dispositions.get("required_decisions", [])),
            "work_package_routed_to_phase_action": (
                work_package_after_product_dispositions.get("package_available") is False
                and work_package_after_product_dispositions.get("status") == "phase_action_required"
            ),
        },
        "api_review": {
            "preflight_ok": api_review_apply.get("preflight_ok") is True,
            "applied": api_review_apply.get("applied") is True,
            "baseline_mode": str(api_review_apply.get("baseline_mode", "")),
            "scorecard_grade": str(api_review_apply.get("scorecard_grade", "")),
            "current_after_runtime_refresh": (
                api_review_after_runtime_refresh.get("ok") is True
                and api_review_after_runtime_refresh.get("would_update") == []
            ),
            "evidence_paths": list(api_review_apply.get("evidence_paths", [])),
        },
        "threat_review": {
            "preflight_ok": threat_review_apply.get("preflight_ok") is True,
            "applied": threat_review_apply.get("applied") is True,
            "element_count": threat_review_apply.get("element_count", 0),
            "high_dread_threat_count": threat_review_apply.get("high_dread_threat_count", 0),
            "current_after_runtime_refresh": (
                threat_review_after_runtime_refresh.get("ok") is True
                and threat_review_after_runtime_refresh.get("would_update") == []
            ),
            "evidence_paths": list(threat_review_apply.get("evidence_paths", [])),
        },
        "reliability_review": {
            "preflight_ok": reliability_review_apply.get("preflight_ok") is True,
            "applied": reliability_review_apply.get("applied") is True,
            "mode": str(reliability_review_apply.get("mode", "")),
            "slo_count": reliability_review_apply.get("slo_count", 0),
            "current_after_runtime_refresh": (
                reliability_review_after_runtime_refresh.get("ok") is True
                and reliability_review_after_runtime_refresh.get("would_update") == []
            ),
            "evidence_paths": list(reliability_review_apply.get("evidence_paths", [])),
        },
        "migration_review": {
            "preflight_ok": migration_review_apply.get("preflight_ok") is True,
            "applied": migration_review_apply.get("applied") is True,
            "mode": str(migration_review_apply.get("mode", "")),
            "compatibility_status": str(migration_review_apply.get("compatibility_status", "")),
            "current_after_runtime_refresh": (
                migration_review_after_runtime_refresh.get("ok") is True
                and migration_review_after_runtime_refresh.get("would_update") == []
            ),
            "evidence_paths": list(migration_review_apply.get("evidence_paths", [])),
        },
        "design_reviews": {
            "recorded_count": len(design_review_applies),
            "expected_count": expected_design_review_count,
            "active_count": design_review_summary.get("active_count", 0),
            "authority_report_count": authority_report_count,
            "decision_report_count": decision_report_count,
            "missing_count": design_review_summary.get("missing_count", 0),
            "stale_count": design_review_summary.get("stale_count", 0),
            "work_package_complete": (
                make_design_complete_work_package.get("package_available") is False
                and make_design_complete_work_package.get("status") == "complete"
            ),
        },
        "project_environment_repair": {
            "registered": project_runtime_registered.get("action") == "register",
            "preview_approval_required": project_repair_preview.get("action") == "approval-required",
            "unapproved_blocked": project_repair_blocked.get("action") == "approval-required",
            "applied": project_repaired.get("action") == "repaired",
            "environment_ready": project_repaired.get("environment_ready") is True,
            "pending_count": repair_summary.get("pending_count", -1)
            if isinstance(repair_summary, dict)
            else -1,
            "evidence_path": ".governance/project-environment-repairs.json",
        },
        "target_local_make_coverage": _target_local_make_coverage_details(steps),
        "workflow_resume": {
            "initialized_status": make_initialized_workflow_resume.get("status"),
            "product_status": make_product_workflow_resume.get("status"),
            "design_status": make_design_workflow_resume.get("status"),
            "implementation_status": make_implementation_workflow_resume.get("status"),
            "complete_status": make_workflow_resume_after_runtime_refresh.get("status"),
            "stale_guard": make_workflow_resume_after_runtime_refresh.get("stale") is False,
        },
        "implementation_gate": {
            "placeholder_blocked_ok": implementation_preflight.get("ok"),
            "placeholder_expected_blocked": True,
            "ready_ok": implementation_gate.get("ok"),
        },
        "implementation_task_package": dict(make_implementation_work_package.get("work_package", {})),
        "consumer_resume_implementation_handoff": _consumer_resume_handoff_summary(
            consumer_resume_implementation_handoff,
            consumer_resume_implementation_reentry,
            target,
        ),
        "implementation_run": {
            "ready_check": make_implementation_run_check.get("status") == "ready_to_start",
            "snapshot_guarded_start": bool(ready_snapshot)
            and implementation_run_apply_start.get("snapshot", {}).get("id") == ready_snapshot,
            "start_applied": implementation_run_apply_start.get("start_applied") is True,
            "verification_ready": implementation_run_check_in_progress.get("status") == "verification_ready",
            "required_count": run_execute_summary.get("required_count", 0),
            "passed_count": run_execute_summary.get("passed_count", 0),
            "executed_all_required": implementation_run_execute.get("executed") is True
            and run_execute_summary.get("all_passed") is True
            and run_execute_summary.get("passed_count") == run_execute_summary.get("required_count"),
            "review_required_after_execution": implementation_run_execute.get("status")
            == "closeout_blocked",
            "reviewed_closeout_ready": implementation_run_reviewed_check.get("status")
            == "closeout_ready",
            "snapshot_guarded_closeout": "--expect-snapshot" in implementation_run_closeout_argv,
            "closeout_applied": implementation_run_closeout.get("closeout_applied") is True,
            "complete": implementation_run_closeout.get("status") == "complete",
        },
        "implementation_start": {
            "task_id": IMPLEMENTATION_TASK_ID,
            "ready": implementation_start_preview.get("start_ready") is True,
            "applied_status_updates": implementation_start_apply.get("applied") is True,
            "baseline_captured": implementation_start_apply.get("baseline_capture", {}).get("captured")
            is True,
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
        "implementation_verification": {
            "ok": _implementation_verification_completed(implementation_verification_execute)
            and closeout_with_evidence.get("evidence_summary", {}).get("all_verification_results_passing") is True,
            "task_id": IMPLEMENTATION_TASK_ID,
            "command": IMPLEMENTATION_VERIFICATION_COMMAND,
            "run_id": IMPLEMENTATION_VERIFICATION_RUN_ID,
            "preview_ready": implementation_verification_preview.get("verification_ready") is True,
            "environment_ready": implementation_verification_preview.get("environment_readiness", {}).get("ok")
            is True,
            "environment_version_ready": all(
                tool.get("version_satisfies") is True
                for tool in implementation_verification_preview.get("environment_readiness", {}).get(
                    "required_tools", []
                )
                if isinstance(tool, dict)
            ),
            "environment_id": implementation_verification_preview.get("environment_readiness", {})
            .get("environment_contract", {})
            .get("environment_id", ""),
            "executed": implementation_verification_execute.get("executed") is True,
            "evidence_recorded": implementation_verification_execute.get("evidence_recorded") is True,
            "command_passed": implementation_verification_execute.get("command_passed") is True,
            "all_current_results_passing": closeout_with_evidence.get("evidence_summary", {}).get(
                "all_verification_results_passing"
            )
            is True,
            "updated_paths": list(implementation_verification_execute.get("updated_paths", [])),
        },
        "implementation_review": {
            "authority_skill": implementation_review_plan.get("authority_skill", {}).get("name", ""),
            "provenance_ready": implementation_review_plan.get("authority_skill", {}).get(
                "provenance_ready"
            )
            is True,
            "change_set_bound": "src/dry_run_task.py"
            in implementation_review_plan.get("change_set", {}).get("changed_paths", []),
            "preview_ready": implementation_review_preview.get("review_ready") is True,
            "evidence_current": implementation_review_record.get("evidence_current") is True,
            "evidence_path": "docs/development/05-code-review-evidence.json",
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
            "check_version_transition": (
                dict(runtime_refresh_check["version_transition"])
                if isinstance(runtime_refresh_check.get("version_transition"), dict)
                else {}
            ),
            "version_transition": (
                dict(runtime_refresh["version_transition"])
                if isinstance(runtime_refresh.get("version_transition"), dict)
                else {}
            ),
            "check_migration_plan": (
                dict(runtime_refresh_check["migration_plan"])
                if isinstance(runtime_refresh_check.get("migration_plan"), dict)
                else {}
            ),
            "migration_plan": (
                dict(runtime_refresh["migration_plan"])
                if isinstance(runtime_refresh.get("migration_plan"), dict)
                else {}
            ),
            "runtime_refreshed_at": isinstance(runtime_refresh.get("state"), dict)
            and isinstance(runtime_refresh["state"].get("runtime_refreshed_at"), str),
            "workflow_plan_complete_after_refresh": make_workflow_plan_after_runtime_refresh.get("blocked") is False,
            "work_package_complete_after_refresh": make_work_package_after_runtime_refresh.get("status") == "complete",
            "refreshed_required_paths": [
                path
                for path in (
                    "bin/governance",
                    "scripts/governance_cli.py",
                    "scripts/implementation_run.py",
                    "scripts/implementation_review_evidence.py",
                    "scripts/implementation_verify.py",
                    "scripts/project_environment.py",
                    "scripts/bounded_process.py",
                    "scripts/workflow_resume.py",
                    "scripts/api_review_evidence.py",
                    "scripts/threat_review_evidence.py",
                    "scripts/reliability_review_evidence.py",
                    "scripts/migration_review_evidence.py",
                    "scripts/design_reviews.py",
                    "docs/agent-workflow/runtime-manifest.json",
                    "docs/agent-workflow/workflow-pack/manifest.json",
                )
                if path in runtime_refresh.get("refreshed", [])
            ],
        },
        "next": "execute exactly one Ready task, review its complete change set, and close only with current evidence",
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
        "docs/api/openapi.json": _openapi_contract_doc(),
        "docs/backend/01-modules.md": _backend_modules_doc(),
        "docs/backend/02-data-model.md": _backend_data_model_doc(),
        "docs/backend/03-external-services.md": _backend_external_services_doc(),
        "docs/ui/01-interaction-model.md": _ui_interaction_model_doc(),
        "docs/frontend/01-modules.md": _frontend_modules_doc(),
        "docs/frontend/02-api-consumption.md": _frontend_api_consumption_doc(),
        "docs/tests/01-strategy.md": _test_strategy_doc(),
        "docs/tests/02-acceptance-matrix.md": _acceptance_matrix_doc(acceptance_ids),
        "docs/development/01-roadmap.md": _roadmap_doc(),
        "docs/development/02-task-board.md": _task_board_doc(
            selected_acceptance,
            verification=(
                f"command:{IMPLEMENTATION_VERIFICATION_COMMAND} "
                f"command:{NODE_IMPLEMENTATION_VERIFICATION_COMMAND}"
            ),
        ),
        "docs/development/03-verification-log.md": _verification_log_doc(),
    }
    for rel, text in documents.items():
        (target / rel).write_text(text, encoding="utf-8")
    _write_stack_acceptance_fixtures(target)
    _register_implementation_verification_command(target)


def _register_implementation_verification_command(target: Path) -> None:
    path = target / "docs/agent-workflow/command-contract.md"
    text = path.read_text(encoding="utf-8")
    commands = (
        (
            IMPLEMENTATION_VERIFICATION_COMMAND,
            "Run real Python stack tests without third-party dependencies.",
            ["python3", "-m", "unittest", "discover", "-s", "stack-fixtures/python", "-p", "test_*.py"],
            False,
            "core-governance",
        ),
        (
            NODE_IMPLEMENTATION_VERIFICATION_COMMAND,
            "Run real Node.js stack tests with the built-in test runner.",
            ["node", "--test", "stack-fixtures/node/stack.test.mjs"],
            False,
            "project-runtime",
        ),
    )
    rows = "".join(
        f"| {name} | {purpose} | `.` | `{json.dumps(argv)}` | {str(writes_state).lower()} | false | "
        f"`docs/development/04-implementation-evidence.md` | {environment} |\n"
        for name, purpose, argv, writes_state, environment in commands
    )
    path.write_text(text.replace("\n## Project Commands", f"\n{rows}\n## Project Commands", 1), encoding="utf-8")


def _register_optional_rust_verification_command(target: Path) -> None:
    path = target / "docs/agent-workflow/command-contract.md"
    text = path.read_text(encoding="utf-8")
    argv = ["cargo", "test", "--offline", "--manifest-path", "stack-fixtures/rust/Cargo.toml"]
    row = (
        f"| {RUST_IMPLEMENTATION_VERIFICATION_COMMAND} | Run real Rust stack tests offline without third-party "
        f"crates. | `.` | `{json.dumps(argv)}` | true | false | "
        "`docs/development/04-implementation-evidence.md` | project-runtime |\n"
    )
    path.write_text(text.replace("\n## Project Commands", f"\n{row}\n## Project Commands", 1), encoding="utf-8")


def _remove_dry_run_runtime_registration(target: Path) -> None:
    path = target / "docs/agent-workflow/project-environment.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    environments = payload.get("environments", [])
    for environment in environments:
        if not isinstance(environment, dict) or environment.get("id") != "project-runtime":
            continue
        tools = environment.get("tools", [])
        if isinstance(tools, list):
            environment["tools"] = [
                tool
                for tool in tools
                if not isinstance(tool, dict) or tool.get("id") != "dry-run-runtime"
            ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_dry_run_implementation_change(target: Path) -> None:
    path = target / "src/dry_run_task.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "def governed_workflow_ready() -> bool:\n"
        "    return True\n",
        encoding="utf-8",
    )


def _write_implementation_review_report(target: Path) -> Path:
    path = target / ".governance/code-review-reports" / f"{IMPLEMENTATION_TASK_ID}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": IMPLEMENTATION_TASK_ID,
                "reviewer": {"kind": "agent", "id": "dry-run-code-reviewer"},
                "verdict": "approved",
                "summary": "Reviewed the complete dry-run task change set and local verification evidence.",
                "findings": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_stack_acceptance_fixtures(target: Path) -> None:
    fixtures = {
        "stack-fixtures/python/stack_math.py": (
            "def normalized_total(values):\n"
            "    if not all(isinstance(value, int) for value in values):\n"
            "        raise TypeError('values must contain integers')\n"
            "    return sum(values)\n"
        ),
        "stack-fixtures/python/test_stack_math.py": (
            "import unittest\n\n"
            "from stack_math import normalized_total\n\n\n"
            "class StackMathTest(unittest.TestCase):\n"
            "    def test_normalized_total(self):\n"
            "        self.assertEqual(6, normalized_total([1, 2, 3]))\n\n"
            "    def test_rejects_non_integer_values(self):\n"
            "        with self.assertRaises(TypeError):\n"
            "            normalized_total([1, '2'])\n\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        "stack-fixtures/node/stack.mjs": (
            "export function normalizedTotal(values) {\n"
            "  if (!values.every(Number.isInteger)) throw new TypeError('values must contain integers');\n"
            "  return values.reduce((total, value) => total + value, 0);\n"
            "}\n"
        ),
        "stack-fixtures/node/stack.test.mjs": (
            "import assert from 'node:assert/strict';\n"
            "import test from 'node:test';\n"
            "import { normalizedTotal } from './stack.mjs';\n\n"
            "test('normalizedTotal sums integer values', () => {\n"
            "  assert.equal(normalizedTotal([1, 2, 3]), 6);\n"
            "});\n\n"
            "test('normalizedTotal rejects non-integer values', () => {\n"
            "  assert.throws(() => normalizedTotal([1, '2']), TypeError);\n"
            "});\n"
        ),
        "stack-fixtures/rust/Cargo.toml": (
            "[package]\n"
            "name = \"docs-as-code-stack-acceptance\"\n"
            "version = \"0.1.0\"\n"
            "edition = \"2021\"\n"
            "publish = false\n\n"
            "[lib]\n"
            "path = \"src/lib.rs\"\n"
        ),
        "stack-fixtures/rust/src/lib.rs": (
            "pub fn normalized_total(values: &[i64]) -> i64 {\n"
            "    values.iter().sum()\n"
            "}\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::normalized_total;\n\n"
            "    #[test]\n"
            "    fn sums_integer_values() {\n"
            "        assert_eq!(normalized_total(&[1, 2, 3]), 6);\n"
            "    }\n"
            "}\n"
        ),
    }
    for rel, content in fixtures.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _register_stack_runtime(
    target: Path,
    steps: list[dict[str, object]],
    *,
    env: dict[str, str],
    stack: str,
    tool_id: str,
    executable: str,
    version_prefix: str,
    minimum_version: str,
    maximum_exclusive_version: str,
    repair_source: str,
    repair_instructions: str,
) -> dict[str, object]:
    argv = [
        "bin/governance",
        "project-env",
        "register",
        ".",
        "--tool-id",
        tool_id,
        "--executable",
        executable,
        "--version-prefix",
        version_prefix,
        "--minimum-version",
        minimum_version,
        "--maximum-exclusive-version",
        maximum_exclusive_version,
        "--repair-strategy",
        "manual",
        "--repair-source-type",
        "official-url",
        "--repair-source",
        repair_source,
        "--review-evidence",
        "docs/architecture/02-containers.md",
        "--repair-instructions",
        repair_instructions,
        "--reviewed",
    ]
    preview = _run_json(
        steps,
        f"project_environment_{stack}_register_check",
        [*argv, "--check", "--json"],
        target,
        env=env,
    )
    _require(
        preview.get("ok") is True
        and preview.get("check") is True
        and preview.get("action") in {"register", "already-registered"},
        f"{stack} runtime registration preflight failed",
        payload=preview,
    )
    applied = _run_json(
        steps,
        f"project_environment_{stack}_register",
        [*argv, "--json"],
        target,
        env=env,
    )
    _require(
        applied.get("ok") is True
        and applied.get("action") in {"register", "already-registered"},
        f"{stack} runtime registration failed",
        payload=applied,
    )
    return applied


def _run_optional_rust_stack_acceptance(
    target: Path,
    steps: list[dict[str, object]],
    env: dict[str, str],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="docs-as-code-rust-", dir=target.parent) as tmp:
        rust_target = Path(tmp) / "target"
        shutil.copytree(target, rust_target)
        _register_optional_rust_verification_command(rust_target)
        registration = _register_stack_runtime(
            rust_target,
            steps,
            env=env,
            stack="rust",
            tool_id="rust-cargo",
            executable="cargo",
            version_prefix="cargo ",
            minimum_version="1.70.0",
            maximum_exclusive_version="2.0.0",
            repair_source="https://www.rust-lang.org/tools/install",
            repair_instructions=(
                "Install a reviewed stable Rust toolchain with Cargo from the official distribution."
            ),
        )
        cargo_available = shutil.which("cargo", path=env.get("PATH")) is not None
        preview = _run_json(
            steps,
            "implementation_rust_verification_preview",
            [
                "bin/governance",
                "implementation",
                "verify",
                ".",
                "--task",
                IMPLEMENTATION_TASK_ID,
                "--command",
                RUST_IMPLEMENTATION_VERIFICATION_COMMAND,
                "--run-id",
                RUST_IMPLEMENTATION_VERIFICATION_RUN_ID,
                "--allow-writes",
                "--check",
                "--json",
            ],
            rust_target,
            expected_returncode=0 if cargo_available else 1,
            env=env,
        )
        executed: dict[str, object] = {}
        if cargo_available:
            _require(
                _implementation_verification_preview_ready(
                    preview,
                    command_name=RUST_IMPLEMENTATION_VERIFICATION_COMMAND,
                    executable="cargo",
                    environment_id="project-runtime",
                ),
                "Rust stack verification preflight did not become ready",
                payload=preview,
            )
            executed = _run_json(
                steps,
                "implementation_rust_verification_execute",
                [
                    "bin/governance",
                    "implementation",
                    "verify",
                    ".",
                    "--task",
                    IMPLEMENTATION_TASK_ID,
                    "--command",
                    RUST_IMPLEMENTATION_VERIFICATION_COMMAND,
                    "--run-id",
                    RUST_IMPLEMENTATION_VERIFICATION_RUN_ID,
                    "--allow-writes",
                    "--json",
                ],
                rust_target,
                env=env,
            )
            _require(
                _implementation_verification_completed(executed),
                "Rust stack tests did not execute and record passing evidence",
                payload=executed,
            )
        else:
            _require(
                preview.get("ok") is False
                and preview.get("executed") is False
                and preview.get("environment_readiness", {}).get("ok") is False
                and any(
                    action.get("strategy") == "manual" and action.get("tool_id") == "rust-cargo"
                    for action in preview.get("environment_readiness", {}).get("repair_actions", [])
                    if isinstance(action, dict)
                ),
                "missing Rust did not route to reviewed manual environment repair",
                payload=preview,
            )
        return registration, preview, executed


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


def _openapi_contract_doc() -> str:
    return json.dumps(
        {
            "openapi": "3.1.0",
            "info": {
                "title": "Governance Check API",
                "version": "1.0.0",
                "description": "Source-backed contract used by the disposable governance dry run.",
                "contact": {"name": "Governance maintainers"},
            },
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/governance/checks": {
                    "post": {
                        "operationId": "runGovernanceCheck",
                        "summary": "Run a governance check",
                        "description": "Runs one read-only governance check against a repository target.",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/GovernanceCheckRequest"}
                                }
                            },
                        },
                        "responses": {
                            "200": {"description": "Governance check completed."},
                            "400": {"description": "The target or request is invalid."},
                            "500": {"description": "The governance check failed unexpectedly."},
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "GovernanceCheckRequest": {
                        "type": "object",
                        "required": ["target"],
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Repository root to inspect.",
                                "example": ".",
                            }
                        },
                    }
                }
            },
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


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


def _record_optional_product_dispositions(
    target: Path,
    product_plan: dict[str, object],
    steps: list[dict[str, object]],
) -> list[dict[str, object]]:
    required_decisions = product_plan.get("required_decisions")
    _require(
        isinstance(required_decisions, list),
        "product plan did not expose required decisions for disposition recording",
        payload=product_plan,
    )
    applied: list[dict[str, object]] = []
    for decision in required_decisions:
        if not isinstance(decision, dict):
            continue
        chapter = str(decision.get("chapter", ""))
        _require(
            chapter in OPTIONAL_PRODUCT_CHAPTERS,
            f"dry-run refuses to omit required or unknown product chapter: {chapter or '<missing>'}",
            payload=product_plan,
        )
        step_slug = chapter.replace("-", "_")
        reason = (
            f"Golden dry-run source review confirms {chapter} has no conservatively mapped PRD heading."
        )
        argv = [
            "bin/governance",
            "product",
            "disposition",
            ".",
            "--chapter",
            chapter,
            "--decision",
            "omit-unsupported",
            "--reason",
            reason,
            "--reviewed",
        ]
        preview = _run_json(
            steps,
            f"product_disposition_{step_slug}_check",
            [*argv, "--check", "--json"],
            target,
        )
        _require(
            preview.get("ok") is True
            and preview.get("check") is True
            and preview.get("would_update") == ["docs/product/core/chapter-dispositions.json"],
            f"product disposition preflight failed for {chapter}",
            payload=preview,
        )
        result = _run_json(
            steps,
            f"product_disposition_{step_slug}_apply",
            [*argv, "--json"],
            target,
        )
        _require(
            result.get("ok") is True
            and result.get("applied") is True
            and result.get("updated") == ["docs/product/core/chapter-dispositions.json"],
            f"product disposition apply failed for {chapter}",
            payload=result,
        )
        applied.append(result)
    return applied


def _write_threat_review_inputs(target: Path) -> None:
    root = target / "docs/architecture/threat-model"
    root.mkdir(parents=True, exist_ok=True)
    categories = [
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
        "Elevation of Privilege",
    ]
    scope = {
        "schema_version": 1,
        "elements": [
            {
                "id": "governance-api",
                "name": "Governance API",
                "type": "process",
                "component": "REST API",
                "assets": ["governance_state", "workflow_evidence"],
                "trust_boundaries": ["agent-to-governance-runtime"],
                "source_references": [
                    "docs/architecture/01-system-context.md",
                    "docs/architecture/02-containers.md",
                    "docs/architecture/03-quality-attributes.md",
                ],
            }
        ],
        "stride_coverage": [
            {
                "element_id": "governance-api",
                "category": category,
                "status": "considered",
                "notes": f"Golden dry-run reviewed {category} against the governance API boundary.",
            }
            for category in categories
        ],
    }
    mitigations = {
        "schema_version": 1,
        "mitigations": [
            {
                "element_id": "governance-api",
                "category": "Spoofing",
                "threat_name": "API Key Impersonation",
                "owner": "governance-runtime-maintainers",
                "mitigation": "Use short-lived credentials and rotate exposed keys.",
                "evidence": ["docs/architecture/03-quality-attributes.md"],
            }
        ],
    }
    (root / "scope.json").write_text(
        json.dumps(scope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "mitigations.json").write_text(
        json.dumps(mitigations, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_reliability_review_inputs(target: Path) -> None:
    root = target / "docs/backend/reliability"
    root.mkdir(parents=True, exist_ok=True)
    policy_rel = "docs/backend/04-error-budget-policy.md"
    (target / policy_rel).write_text(
        "# Error Budget Policy\n\n"
        "## Scope\n\n- Protect governed workflow execution.\n\n"
        "## Budget Actions\n\n- Pause risky releases when the budget is exhausted.\n\n"
        "## Release Policy\n\n- Require burn-rate evidence before rollback.\n\n"
        "## Incident Policy\n\n- Page the governance runtime owner on fast or slow burn.\n\n"
        "## Review\n\n- Review quarterly with product and backend owners.\n",
        encoding="utf-8",
    )
    backend_readme = target / "docs/backend/README.md"
    readme_text = backend_readme.read_text(encoding="utf-8")
    if "04-error-budget-policy.md" not in readme_text:
        backend_readme.write_text(
            readme_text.rstrip() + "\n- [Error budget policy](04-error-budget-policy.md)\n",
            encoding="utf-8",
        )
    source_references = [
        "docs/product/08-acceptance-criteria.md",
        "docs/architecture/03-quality-attributes.md",
        "docs/backend/01-modules.md",
        "docs/backend/03-external-services.md",
    ]
    scope = {
        "schema_version": 1,
        "applicability": {
            "decision": "required",
            "owner": "governance-runtime-maintainers",
            "reason": "The governed workflow exposes a user-visible service success path that requires a measurable objective.",
            "source_references": source_references,
            "revisit_triggers": [
                "The production execution path or user-visible reliability commitment changes."
            ],
        },
        "slos": [
            {
                "id": "governance-api-success",
                "service": "governance-api",
                "sli_type": "request-success-rate",
                "target_percent": 99.9,
                "window_days": 28,
                "owner": "governance-runtime-maintainers",
                "user_journey": "A maintainer executes a governed workflow action and receives a valid result.",
                "sli_numerator": "count(governance_actions_total{outcome=\"success\"})",
                "sli_denominator": "count(governance_actions_total)",
                "sli_labels": ["environment=production"],
                "policy_doc": policy_rel,
                "review_cadence": "quarterly",
                "source_references": source_references,
                "target_basis": {
                    "kind": "provisional-prelaunch",
                    "rationale": "Use a provisional target until the first production measurement window completes.",
                    "source_references": [
                        "docs/product/08-acceptance-criteria.md",
                        "docs/architecture/03-quality-attributes.md",
                    ],
                    "validation_plan": "Measure the SLI for 28 days after launch and review the target before the next release.",
                },
            }
        ],
    }
    (root / "slo-scope.json").write_text(
        json.dumps(scope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_migration_review_inputs(target: Path) -> None:
    root = target / "docs/backend/migrations"
    root.mkdir(parents=True, exist_ok=True)
    sources = [
        "docs/product/08-acceptance-criteria.md",
        "docs/architecture/03-quality-attributes.md",
        "docs/backend/01-modules.md",
        "docs/backend/02-data-model.md",
    ]
    documents = {
        "review-scope.json": {
            "schema_version": 1,
            "applicability": {
                "decision": "required",
                "owner": "governance-runtime-maintainers",
                "reason": "The governed workflow persists auditable state and requires a deployable initial schema.",
                "source_references": sources,
                "revisit_triggers": ["The persistence schema or data lifecycle changes."],
            },
            "review": {
                "owner": "governance-runtime-maintainers",
                "reason": "Initial schema compatibility, validation, migration, and rollback evidence were reviewed.",
                "source_references": sources,
            },
        },
        "schema-before.json": {
            "schema_version": "0.0",
            "database": "governance_store",
            "tables": {},
            "views": {},
            "procedures": [],
        },
        "schema-after.json": {
            "schema_version": "1.0",
            "database": "governance_store",
            "tables": {
                "workflow_state": {
                    "columns": {
                        "id": {"type": "varchar", "length": 64, "nullable": False, "primary_key": True},
                        "phase": {"type": "varchar", "length": 64, "nullable": False},
                    },
                    "constraints": {"primary_key": ["id"], "unique": [], "foreign_key": [], "check": []},
                    "indexes": [{"name": "idx_workflow_state_phase", "columns": ["phase"]}],
                }
            },
            "views": {},
            "procedures": [],
        },
        "migration-spec.json": {
            "type": "database",
            "pattern": "schema_change",
            "source": "Empty governance_store schema",
            "target": "governance_store schema version 1.0",
            "description": "Deploy the initial source-backed governance state schema.",
            "constraints": {
                "max_downtime_minutes": 30,
                "data_volume_gb": 0,
                "dependencies": ["governance-api"],
                "compliance_requirements": [],
                "special_requirements": ["referential_integrity"],
            },
            "tables_to_migrate": [{"name": "workflow_state", "row_count": 0, "size_mb": 0, "critical": True}],
            "schema_changes": [{"table": "workflow_state", "changes": [{"type": "create_table"}]}],
            "governance": {
                "owner": "governance-runtime-maintainers",
                "strategy_rationale": "Use an explicit initial migration so deployment and rollback remain auditable.",
                "validation_plan": "Apply and roll back the schema in an isolated database before release.",
                "source_references": sources,
            },
        },
        "compatibility-acceptances.json": {"schema_version": 1, "decisions": []},
    }
    for name, document in documents.items():
        (root / name).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _record_api_review(
    target: Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    _install_dry_run_authority_skill_fixtures(target)
    argv = ["bin/governance", "design", "api-review", ".", "--reviewed"]
    expected_paths = {
        "docs/api/baselines/openapi-baseline.json",
        "docs/api/reviews/api-lint.json",
        "docs/api/reviews/api-breaking-changes.json",
        "docs/api/reviews/api-scorecard.json",
        "docs/api/reviews/review-evidence.json",
    }
    preview = _run_json(
        steps,
        "api_review_check",
        [*argv, "--check", "--json"],
        target,
    )
    _require(
        preview.get("ok") is True
        and preview.get("check") is True
        and set(preview.get("would_update", [])) == expected_paths,
        "API machine-review preflight did not plan complete evidence",
        payload=preview,
    )
    result = _run_json(
        steps,
        "api_review_apply",
        [*argv, "--json"],
        target,
    )
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    reports = evidence.get("reports") if isinstance(evidence.get("reports"), dict) else {}
    scorecard = reports.get("scorecard") if isinstance(reports.get("scorecard"), dict) else {}
    _require(
        result.get("ok") is True
        and result.get("applied") is True
        and set(result.get("updated", [])) == expected_paths
        and scorecard.get("grade") == "A",
        "API machine-review apply did not record passing authority-tool evidence",
        payload=result,
    )
    return {
        "preflight_ok": preview.get("ok") is True,
        "applied": result.get("applied") is True,
        "baseline_mode": str(result.get("baseline_mode", "")),
        "scorecard_grade": str(scorecard.get("grade", "")),
        "evidence_paths": sorted(expected_paths),
    }


def _record_threat_review(
    target: Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    _install_dry_run_authority_skill_fixtures(target)
    argv = ["bin/governance", "design", "threat-review", ".", "--reviewed"]
    expected_paths = {
        "docs/architecture/threat-model/stride-report.json",
        "docs/architecture/threat-model/review-evidence.json",
    }
    preview = _run_json(
        steps,
        "threat_review_check",
        [*argv, "--check", "--json"],
        target,
    )
    _require(
        preview.get("ok") is True
        and preview.get("check") is True
        and set(preview.get("would_update", [])) == expected_paths,
        "architecture threat-review preflight did not plan complete evidence",
        payload=preview,
    )
    result = _run_json(
        steps,
        "threat_review_apply",
        [*argv, "--json"],
        target,
    )
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    summary = evidence.get("summary") if isinstance(evidence.get("summary"), dict) else {}
    _require(
        result.get("ok") is True
        and result.get("applied") is True
        and set(result.get("updated", [])) == expected_paths
        and summary.get("element_count") == 1
        and summary.get("high_dread_threat_count") == 1
        and summary.get("mitigated_high_dread_threat_count") == 1,
        "architecture threat-review apply did not record passing authority-tool evidence",
        payload=result,
    )
    return {
        "preflight_ok": preview.get("ok") is True,
        "applied": result.get("applied") is True,
        "element_count": summary.get("element_count", 0),
        "high_dread_threat_count": summary.get("high_dread_threat_count", 0),
        "evidence_paths": sorted(expected_paths),
    }


def _record_reliability_review(
    target: Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    _install_dry_run_authority_skill_fixtures(target)
    argv = ["bin/governance", "design", "reliability-review", ".", "--reviewed"]
    expected_paths = {
        "docs/backend/reliability/slo-definitions.json",
        "docs/backend/reliability/error-budgets.json",
        "docs/backend/reliability/slo-review.json",
        "docs/backend/reliability/review-evidence.json",
    }
    preview = _run_json(
        steps,
        "reliability_review_check",
        [*argv, "--check", "--json"],
        target,
    )
    _require(
        preview.get("ok") is True
        and preview.get("check") is True
        and set(preview.get("would_update", [])) == expected_paths,
        "backend reliability-review preflight did not plan complete evidence",
        payload=preview,
    )
    result = _run_json(
        steps,
        "reliability_review_apply",
        [*argv, "--json"],
        target,
    )
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    summary = evidence.get("summary") if isinstance(evidence.get("summary"), dict) else {}
    _require(
        result.get("ok") is True
        and result.get("applied") is True
        and result.get("mode") == "required"
        and set(result.get("updated", [])) == expected_paths
        and summary.get("slo_count") == 1
        and summary.get("review_finding_count") == 0,
        "backend reliability-review apply did not record passing authority-tool evidence",
        payload=result,
    )
    return {
        "preflight_ok": preview.get("ok") is True,
        "applied": result.get("applied") is True,
        "mode": str(result.get("mode", "")),
        "slo_count": summary.get("slo_count", 0),
        "evidence_paths": sorted(expected_paths),
    }


def _record_migration_review(
    target: Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    _install_dry_run_authority_skill_fixtures(target)
    argv = ["bin/governance", "design", "migration-review", ".", "--reviewed"]
    expected_paths = {
        "docs/backend/migrations/migration-plan.json",
        "docs/backend/migrations/compatibility-report.json",
        "docs/backend/migrations/rollback-runbook.json",
        "docs/backend/migrations/review-evidence.json",
    }
    preview = _run_json(
        steps,
        "migration_review_check",
        [*argv, "--check", "--json"],
        target,
    )
    _require(
        preview.get("ok") is True
        and preview.get("check") is True
        and set(preview.get("would_update", [])) == expected_paths,
        "data-model migration-review preflight did not plan complete evidence",
        payload=preview,
    )
    result = _run_json(
        steps,
        "migration_review_apply",
        [*argv, "--json"],
        target,
    )
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    summary = evidence.get("summary") if isinstance(evidence.get("summary"), dict) else {}
    _require(
        result.get("ok") is True
        and result.get("applied") is True
        and result.get("mode") == "required"
        and result.get("compatibility_status") == "backward_compatible"
        and set(result.get("updated", [])) == expected_paths
        and summary.get("tool_run_count") == 3,
        "data-model migration-review apply did not record compatible migration and rollback evidence",
        payload=result,
    )
    return {
        "preflight_ok": preview.get("ok") is True,
        "applied": result.get("applied") is True,
        "mode": str(result.get("mode", "")),
        "compatibility_status": str(result.get("compatibility_status", "")),
        "evidence_paths": sorted(expected_paths),
    }


def _record_design_reviews(
    target: Path,
    acceptance_ids: list[str],
    steps: list[dict[str, object]],
) -> list[dict[str, object]]:
    _install_dry_run_authority_skill_fixtures(target)
    applied: list[dict[str, object]] = []
    for track in DESIGN_REVIEW_TRACK_ORDER:
        spec = DESIGN_REVIEW_TRACK_SPECS[track]
        work_prefix = str(spec["work_prefix"])
        authority_skill = str(spec["primary_authority_skill"])
        result_value = "not-applicable" if track == "architecture-decisions" else "approved"
        for index, acceptance_id in enumerate(acceptance_ids, start=1):
            work_id = f"{work_prefix}-{index:03d}"
            report_path = (
                target
                / ".governance/design-review-reports"
                / f"{track}-{work_id}.json"
            )
            report_path.parent.mkdir(parents=True, exist_ok=True)
            decision_status = (
                "not-applicable" if result_value == "not-applicable" else "approved"
            )
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "track": track,
                        "work_id": work_id,
                        "acceptance_id": acceptance_id,
                        "reviewer": {
                            "kind": "agent",
                            "id": "golden-dry-run-authority-review",
                        },
                        "verdict": "approved",
                        "summary": (
                            f"Reviewed every {track} decision for {acceptance_id} against "
                            "current source-backed repository evidence."
                        ),
                        "decisions": [
                            {
                                "id": decision,
                                "status": decision_status,
                                "rationale": (
                                    f"The {authority_skill} review resolved {decision} "
                                    f"for {acceptance_id}."
                                ),
                                "evidence": ["docs/product/core/PRD.md"],
                            }
                            for decision in spec["decisions"]
                        ],
                        "findings": [],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            reason = (
                f"Golden dry-run {authority_skill} review confirms {track} decisions for "
                f"{acceptance_id} are addressed in current repository evidence."
            )
            argv = [
                "bin/governance",
                "design",
                "review",
                ".",
                "--track",
                track,
                "--work",
                work_id,
                "--result",
                result_value,
                "--reason",
                reason,
                "--report",
                report_path.relative_to(target).as_posix(),
                "--reviewed",
            ]
            step_slug = f"{track.replace('-', '_')}_{acceptance_id.lower().replace('-', '_')}"
            preview = _run_json(
                steps,
                f"design_review_{step_slug}_check",
                [*argv, "--check", "--json"],
                target,
            )
            review = preview.get("review")
            review_authority = review.get("authority_skill") if isinstance(review, dict) else None
            _require(
                preview.get("ok") is True
                and preview.get("check") is True
                and preview.get("would_update") == [DESIGN_REVIEW_REL]
                and isinstance(review_authority, dict)
                and review_authority.get("name") == authority_skill,
                f"design review preflight failed for {track} {acceptance_id}",
                payload=preview,
            )
            result = _run_json(
                steps,
                f"design_review_{step_slug}_apply",
                [*argv, "--json"],
                target,
            )
            _require(
                result.get("ok") is True
                and result.get("applied") is True
                and result.get("updated") == [DESIGN_REVIEW_REL],
                f"design review apply failed for {track} {acceptance_id}",
                payload=result,
            )
            applied.append(result)
    return applied


def _install_dry_run_authority_skill_fixtures(target: Path) -> None:
    skill_names = {
        str(spec["primary_authority_skill"])
        for spec in DESIGN_REVIEW_TRACK_SPECS.values()
    }
    skill_names.add("senior-security")
    skill_names.add("slo-architect")
    skill_names.add("database-schema-designer")
    skill_names.add("migration-architect")
    for skill_name in sorted(skill_names):
        path = target / ".agents/skills" / skill_name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"name: {skill_name}\n"
            "description: Deterministic dry-run authority routing fixture; not a production skill.\n"
            "---\n\n"
            f"# {skill_name}\n\n"
            "Used only to exercise source-, evidence-, and skill-hash-bound design review mechanics.\n",
            encoding="utf-8",
        )
    reports = {
        "api_linter.py": {
            "summary": {
                "total_endpoints": 1,
                "endpoints_with_issues": 0,
                "total_issues": 0,
                "errors": 0,
                "warnings": 0,
                "info": 0,
                "score": 100.0,
            },
            "issues": [],
        },
        "breaking_change_detector.py": {
            "summary": {
                "total_changes": 0,
                "breaking_changes": 0,
                "potentially_breaking_changes": 0,
                "non_breaking_changes": 0,
                "enhancements": 0,
                "critical_severity": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0,
                "info_severity": 0,
            },
            "hasBreakingChanges": False,
            "changes": [],
        },
        "api_scorecard.py": {
            "overall": {"score": 95.0, "grade": "A", "totalEndpoints": 1},
            "api_info": {
                "title": "Governance Check API",
                "version": "1.0.0",
                "description": "Deterministic dry-run API review fixture.",
                "total_paths": 1,
                "openapi_version": "3.1.0",
            },
            "categories": {},
            "topRecommendations": [],
        },
    }
    skill_root = target / ".agents/skills/api-design-reviewer/scripts"
    skill_root.mkdir(parents=True, exist_ok=True)
    for script_name, report in reports.items():
        (skill_root / script_name).write_text(
            "# Deterministic dry-run fixture only; not a production authority tool.\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            f"REPORT = {report!r}\n"
            "output_index = sys.argv.index('--output') + 1\n"
            "Path(sys.argv[output_index]).write_text(json.dumps(REPORT, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
    threat_report = {
        "component": "REST API",
        "analysis_date": "2026-01-01T00:00:00+00:00",
        "summary": {
            "total_threats": 1,
            "by_risk_level": {"critical": 0, "high": 1, "medium": 0, "low": 0},
        },
        "threats": [
            {
                "category": "Spoofing",
                "name": "API Key Impersonation",
                "description": "An attacker uses a stolen API credential.",
                "attack_vector": "Credential exposure",
                "impact": "Unauthorized governance access",
                "likelihood": 4,
                "severity": 4,
                "risk_score": 16,
                "risk_level": "High",
                "dread": {
                    "damage": 8,
                    "reproducibility": 8,
                    "exploitability": 8,
                    "affected_users": 8,
                    "discoverability": 8,
                    "total": 8.0,
                },
                "mitigations": ["Use short-lived credentials and rotate exposed keys."],
            }
        ],
    }
    threat_tool = target / ".agents/skills/senior-security/scripts/threat_modeler.py"
    threat_tool.parent.mkdir(parents=True, exist_ok=True)
    threat_tool.write_text(
        "# Deterministic dry-run fixture only; not a production authority tool.\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        f"REPORT = {threat_report!r}\n"
        "output_index = sys.argv.index('--output') + 1\n"
        "Path(sys.argv[output_index]).write_text(json.dumps(REPORT, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    slo_tools = target / ".agents/skills/slo-architect/scripts"
    slo_tools.mkdir(parents=True, exist_ok=True)
    (slo_tools / "slo_designer.py").write_text(
        "import json\n"
        "import sys\n\n"
        "def arg(name, default=''):\n"
        "    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default\n\n"
        "target = float(arg('--target'))\n"
        "window = int(arg('--window-days'))\n"
        "payload = {\n"
        "    'service': arg('--service'),\n"
        "    'owner': arg('--owner'),\n"
        "    'user_journey': arg('--user-journey'),\n"
        "    'sli': {\n"
        "        'type': arg('--sli-type'),\n"
        "        'numerator': arg('--sli-numerator'),\n"
        "        'denominator': arg('--sli-denominator'),\n"
        "        'labels': arg('--sli-labels').split(',') if arg('--sli-labels') else [],\n"
        "    },\n"
        "    'target_percent': target,\n"
        "    'window_days': window,\n"
        "    'error_budget': {\n"
        "        'minutes_per_window': round((100 - target) / 100 * window * 24 * 60, 2),\n"
        "        'policy_doc': arg('--policy-doc'),\n"
        "    },\n"
        "    'alerts': {'fast_burn_threshold': 'calculated', 'slow_burn_threshold': 'calculated'},\n"
        "    'review_cadence': arg('--review-cadence'),\n"
        "}\n"
        "print(json.dumps(payload, indent=2, sort_keys=True))\n",
        encoding="utf-8",
    )
    (slo_tools / "error_budget_calculator.py").write_text(
        "import json\n"
        "import sys\n\n"
        "target = float(sys.argv[sys.argv.index('--target') + 1])\n"
        "window = int(sys.argv[sys.argv.index('--window-days') + 1])\n"
        "budget = round((100 - target) / 100 * window * 24 * 60, 4)\n"
        "payload = {\n"
        "    'target_percent': target,\n"
        "    'window_days': window,\n"
        "    'bad_fraction': round((100 - target) / 100, 6),\n"
        "    'budget_minutes': budget,\n"
        "    'budget_hours': round(budget / 60, 4),\n"
        "    'alert_rules': [\n"
        "        {'name': 'fast_burn'},\n"
        "        {'name': 'slow_burn'},\n"
        "        {'name': 'ticket_burn'},\n"
        "    ],\n"
        "}\n"
        "print(json.dumps(payload, indent=2, sort_keys=True))\n",
        encoding="utf-8",
    )
    (slo_tools / "slo_review.py").write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "root = Path(sys.argv[sys.argv.index('--slo-doc') + 1])\n"
        "results = []\n"
        "for path in sorted(root.glob('*.json')):\n"
        "    document = json.loads(path.read_text(encoding='utf-8'))\n"
        "    findings = []\n"
        "    if document.get('target') is None:\n"
        "        findings.append(['FAIL', 'no_target', 'no target'])\n"
        "    if findings:\n"
        "        results.append({'path': str(path), 'findings': findings})\n"
        "print(json.dumps(results, indent=2, sort_keys=True))\n",
        encoding="utf-8",
    )
    migration_tools = target / ".agents/skills/migration-architect/scripts"
    migration_tools.mkdir(parents=True, exist_ok=True)
    migration_plan = {
        "migration_id": "dry-run-migration",
        "source_system": "Empty governance_store schema",
        "target_system": "governance_store schema version 1.0",
        "migration_type": "database",
        "complexity": "low",
        "estimated_duration_hours": 4,
        "phases": [{
            "name": "migration",
            "description": "Apply initial schema",
            "duration_hours": 4,
            "dependencies": [],
            "validation_criteria": ["Schema validation passes"],
            "rollback_triggers": ["Validation fails"],
            "tasks": ["Apply schema"],
            "risk_level": "low",
            "resources_required": ["database owner"],
        }],
        "risks": [{
            "category": "technical",
            "description": "Schema application fails",
            "probability": "low",
            "impact": "medium",
            "severity": "medium",
            "mitigation": "Validate before cutover",
            "owner": "governance-runtime-maintainers",
        }],
        "success_criteria": ["Schema validation passes"],
        "rollback_plan": {"rollback_phases": [{"phase": "migration"}]},
        "stakeholders": ["governance-runtime-maintainers"],
    }
    compatibility_report = {
        "overall_compatibility": "backward_compatible",
        "breaking_changes_count": 0,
        "potentially_breaking_count": 0,
        "non_breaking_changes_count": 0,
        "additive_changes_count": 1,
        "issues": [],
        "migration_scripts": [{
            "script_type": "sql",
            "description": "Create workflow state table",
            "script_content": "CREATE TABLE workflow_state (id text primary key);",
            "rollback_script": "DROP TABLE workflow_state;",
            "dependencies": [],
            "validation_query": "SELECT 1 FROM workflow_state LIMIT 1;",
        }],
        "risk_assessment": {
            "overall_risk": "low",
            "deployment_risk": "safe_independent_deployment",
            "rollback_complexity": "low",
            "testing_requirements": ["migration_testing"],
        },
        "recommendations": ["Run migration tests"],
    }
    rollback_runbook = {
        "runbook_id": "dry-run-rollback",
        "migration_id": "dry-run-migration",
        "rollback_phases": [{
            "phase_name": "rollback_migration",
            "description": "Undo initial schema",
            "urgency_level": "medium",
            "estimated_duration_minutes": 15,
            "prerequisites": ["Database owner available"],
            "steps": [{
                "step_id": "rollback-1",
                "name": "Drop workflow state table",
                "description": "Restore empty schema",
                "script_type": "sql",
                "script_content": "DROP TABLE workflow_state;",
                "estimated_duration_minutes": 5,
                "dependencies": [],
                "validation_commands": ["SELECT 1;"],
                "success_criteria": ["Empty schema restored"],
                "failure_escalation": "Escalate to database owner",
                "rollback_order": 1,
            }],
            "validation_checkpoints": ["Empty schema restored"],
            "communication_requirements": ["Notify database owner"],
            "risk_level": "low",
        }],
        "trigger_conditions": [{
            "trigger_id": "validation_failure",
            "name": "Validation Failure",
            "condition": "migration_validation_failures > 0",
            "metric_threshold": {"metric": "migration_validation_failures", "operator": "greater_than", "value": 0},
            "evaluation_window_minutes": 1,
            "auto_execute": False,
            "escalation_contacts": ["governance-runtime-maintainers"],
        }],
        "data_recovery_plan": {
            "recovery_method": "backup_restore",
            "backup_location": "controlled-backup",
            "recovery_scripts": ["restore-governance-schema"],
            "data_validation_queries": ["SELECT 1;"],
            "estimated_recovery_time_minutes": 15,
            "recovery_dependencies": ["governance-runtime-maintainers"],
        },
        "communication_templates": [{
            "template_type": "start",
            "audience": "technical",
            "subject": "Governance schema rollback started",
            "body": "Notify the governance runtime maintainers.",
            "urgency": "high",
            "delivery_methods": ["incident-channel"],
        }],
        "escalation_matrix": {
            "high": {
                "trigger": "rollback failure",
                "contacts": ["governance-runtime-maintainers"],
            }
        },
        "validation_checklist": ["Schema validation passes"],
        "post_rollback_procedures": ["Monitor governance schema health"],
        "emergency_contacts": [{
            "role": "Governance runtime owner",
            "name": "governance-runtime-maintainers",
        }],
    }
    for script_name, report in (
        ("migration_planner.py", migration_plan),
        ("compatibility_checker.py", compatibility_report),
        ("rollback_generator.py", rollback_runbook),
    ):
        (migration_tools / script_name).write_text(
            "import json\n"
            "import sys\n"
            "from datetime import datetime, timezone\n"
            "from pathlib import Path\n\n"
            f"REPORT = {report!r}\n"
            "payload = dict(REPORT)\n"
            "payload['created_at' if 'rollback' in Path(__file__).name or 'planner' in Path(__file__).name else 'analysis_date'] = datetime.now(timezone.utc).isoformat()\n"
            "output = Path(sys.argv[sys.argv.index('--output') + 1])\n"
            "output.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\\n', encoding='utf-8')\n",
            encoding="utf-8",
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


def _require_workflow_resume(
    payload: dict[str, object],
    *,
    phase: str,
    status: str,
    action_field: str = "",
    action_value: str = "",
) -> None:
    _require(payload.get("ok") is True, f"{phase} workflow resume failed", payload=payload)
    _require(payload.get("workflow") == "workflow-resume", "workflow resume identity mismatch", payload=payload)
    _require(payload.get("phase") == phase, f"{phase} workflow resume phase mismatch", payload=payload)
    _require(payload.get("status") == status, f"{phase} workflow resume status mismatch", payload=payload)
    _require(payload.get("stale") is False, f"{phase} workflow resume unexpectedly stale", payload=payload)
    snapshot = payload.get("snapshot")
    _require(
        isinstance(snapshot, dict)
        and isinstance(snapshot.get("id"), str)
        and re.fullmatch(r"[0-9a-f]{64}", snapshot["id"]) is not None,
        f"{phase} workflow resume snapshot missing",
        payload=payload,
    )
    selected_action = payload.get("selected_action")
    if action_field:
        _require(
            payload.get("action_count") == 1
            and isinstance(selected_action, dict)
            and selected_action.get(action_field) == action_value,
            f"{phase} workflow resume selected action mismatch",
            payload=payload,
        )
        _require(payload.get("can_continue") is True, f"{phase} workflow resume cannot continue", payload=payload)
    else:
        _require(payload.get("action_count") == 0, f"{phase} workflow resume exposed an action", payload=payload)
        _require(selected_action == {}, f"{phase} workflow resume selected action was not empty", payload=payload)


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
    if updated_paths != {
        ".governance/implementation-change-baselines.json",
        "docs/development/01-roadmap.md",
        "docs/development/02-task-board.md",
    }:
        return False
    baseline_capture = payload.get("baseline_capture")
    if not isinstance(baseline_capture, dict) or baseline_capture.get("captured") is not True:
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


def _implementation_verification_preview_ready(
    payload: dict[str, object],
    *,
    command_name: str,
    executable: str,
    environment_id: str,
) -> bool:
    return (
        payload.get("ok") is True
        and payload.get("check") is True
        and payload.get("verification_ready") is True
        and payload.get("writes_state") is False
        and payload.get("executed") is False
        and payload.get("evidence_recorded") is False
        and payload.get("command_contract", {}).get("name") == command_name
        and payload.get("environment_readiness", {}).get("ok") is True
        and payload.get("environment_readiness", {}).get("required_executable") == executable
        and payload.get("environment_readiness", {}).get("environment_contract", {}).get("environment_id")
        == environment_id
        and payload.get("environment_readiness", {}).get("environment_probe_executed") is True
        and all(
            tool.get("version_satisfies") is True
            for tool in payload.get("environment_readiness", {}).get("required_tools", [])
            if isinstance(tool, dict)
        )
        and payload.get("environment_readiness", {}).get("repair_decision", {}).get("decision")
        == "continue_execution"
        and payload.get("would_write")
        == [
            "docs/development/04-implementation-evidence.md",
            "docs/development/03-verification-log.md",
            "docs/development/02-task-board.md",
            "docs/development/README.md",
        ]
    )


def _implementation_verification_completed(payload: dict[str, object]) -> bool:
    execution = payload.get("execution_result")
    return (
        payload.get("ok") is True
        and payload.get("executed") is True
        and payload.get("evidence_recorded") is True
        and payload.get("command_passed") is True
        and isinstance(execution, dict)
        and execution.get("returncode") == 0
        and execution.get("result") == "pass"
        and payload.get("updated_paths")
        == [
            "docs/development/04-implementation-evidence.md",
            "docs/development/03-verification-log.md",
            "docs/development/02-task-board.md",
            "docs/development/README.md",
        ]
    )


def _build_stack_acceptance_summary(
    *,
    python_preview: dict[str, object],
    python_execute: dict[str, object],
    node_registration: dict[str, object],
    node_preview: dict[str, object],
    node_execute: dict[str, object],
    rust_registration: dict[str, object],
    rust_preview: dict[str, object],
    rust_execute: dict[str, object],
) -> dict[str, object]:
    stacks = {
        "python": _stack_acceptance_entry(
            command_name=IMPLEMENTATION_VERIFICATION_COMMAND,
            run_id=IMPLEMENTATION_VERIFICATION_RUN_ID,
            executable="python3",
            registration_action="core-governance",
            preview=python_preview,
            execute=python_execute,
        ),
        "node": _stack_acceptance_entry(
            command_name=NODE_IMPLEMENTATION_VERIFICATION_COMMAND,
            run_id=NODE_IMPLEMENTATION_VERIFICATION_RUN_ID,
            executable="node",
            registration_action=str(node_registration.get("action", "")),
            preview=node_preview,
            execute=node_execute,
        ),
        "rust": _stack_acceptance_entry(
            command_name=RUST_IMPLEMENTATION_VERIFICATION_COMMAND,
            run_id=RUST_IMPLEMENTATION_VERIFICATION_RUN_ID,
            executable="cargo",
            registration_action=str(rust_registration.get("action", "")),
            preview=rust_preview,
            execute=rust_execute,
        ),
    }
    required_stacks = ["python", "node"]
    available = [item for item in stacks.values() if item.get("runtime_available") is True]
    return {
        "policy": "real_runtime_no_network_no_third_party_dependencies",
        "required_stacks": required_stacks,
        "optional_stacks": ["rust"],
        "all_required_passed": all(stacks[name].get("status") == "passed" for name in required_stacks),
        "all_available_passed": all(item.get("status") == "passed" for item in available),
        "strict_rust_passed": stacks["rust"].get("status") == "passed",
        "stacks": stacks,
    }


def _stack_acceptance_entry(
    *,
    command_name: str,
    run_id: str,
    executable: str,
    registration_action: str,
    preview: dict[str, object],
    execute: dict[str, object],
) -> dict[str, object]:
    readiness = preview.get("environment_readiness")
    readiness_map = readiness if isinstance(readiness, dict) else {}
    required_tools = readiness_map.get("required_tools")
    tool = next(
        (
            item
            for item in required_tools
            if isinstance(item, dict) and item.get("executable") == executable
        ),
        {},
    ) if isinstance(required_tools, list) else {}
    repair_actions = readiness_map.get("repair_actions")
    repair_action = next(
        (
            item
            for item in repair_actions
            if isinstance(item, dict) and item.get("executable") == executable
        ),
        {},
    ) if isinstance(repair_actions, list) else {}
    executed = execute.get("executed") is True
    command_passed = execute.get("command_passed") is True
    evidence_recorded = execute.get("evidence_recorded") is True
    runtime_available = tool.get("ready") is True
    passed = executed and command_passed and evidence_recorded
    return {
        "status": "passed" if passed else "unavailable" if not runtime_available else "failed",
        "command_name": command_name,
        "run_id": run_id,
        "executable": executable,
        "registration_action": registration_action,
        "runtime_available": runtime_available,
        "environment_ready": readiness_map.get("ok") is True,
        "observed_version": str(tool.get("observed_version", "")),
        "version_satisfies": tool.get("version_satisfies") is True,
        "executed": executed,
        "command_passed": command_passed,
        "evidence_recorded": evidence_recorded,
        "repair_strategy": str(repair_action.get("strategy", "")),
        "repair_action": dict(repair_action) if isinstance(repair_action, dict) else {},
    }


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
        "required_verification_commands_passing",
        "verification_results_all_passing",
        "task_verification_links_local_evidence",
        "code_review_evidence_current",
    }
    if not required_codes.issubset(blocking_codes):
        return False
    evidence = payload.get("evidence_summary")
    if not isinstance(evidence, dict):
        return False
    return (
        evidence.get("verification_logged") is False
        and evidence.get("passing_verification_logged") is False
        and evidence.get("required_verification_commands")
        == [IMPLEMENTATION_VERIFICATION_COMMAND, NODE_IMPLEMENTATION_VERIFICATION_COMMAND]
        and evidence.get("missing_verification_commands")
        == [IMPLEMENTATION_VERIFICATION_COMMAND, NODE_IMPLEMENTATION_VERIFICATION_COMMAND]
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
    if evidence.get("all_verification_results_passing") is not True:
        return False
    if evidence.get("verification_commands_registered") is not True:
        return False
    if evidence.get("required_verification_commands_passing") is not True:
        return False
    if evidence.get("missing_verification_commands") != []:
        return False
    if evidence.get("failing_verification_commands") != []:
        return False
    if evidence.get("verification_links_local_evidence") is not True:
        return False
    if evidence.get("code_review_evidence_current") is not True:
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
    if evidence.get("code_review_evidence_current") is not True:
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
    return (
        _runtime_refresh_same_version_transition_is_ready(payload.get("version_transition"))
        and _runtime_refresh_migration_plan_is_ready(payload.get("migration_plan"))
    )


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
    if not _runtime_refresh_same_version_transition_is_ready(payload.get("version_transition")):
        return False
    if not _runtime_refresh_migration_plan_is_ready(payload.get("migration_plan")):
        return False
    return any(
        isinstance(command, dict)
        and command.get("make_target") == "workflow-plan"
        and command.get("argv") == ["make", "workflow-plan"]
        for command in local_commands
    )


def _runtime_refresh_same_version_transition_is_ready(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    from_version = value.get("from_version")
    return (
        isinstance(from_version, str)
        and bool(from_version)
        and value.get("to_version") == from_version
        and value.get("classification") == "same"
        and value.get("evidence_status") == "consistent"
        and value.get("candidate_versions") == [from_version]
        and value.get("approval_required") is False
        and value.get("approval_flag") == ""
        and value.get("approval_granted") is False
        and value.get("can_apply") is True
        and value.get("decision") == "apply"
    )


def _runtime_refresh_migration_plan_is_ready(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if (
        value.get("schema_version") != 1
        or value.get("status") != "not_required"
        or value.get("required") is not False
    ):
        return False
    scope = value.get("scope")
    if not isinstance(scope, dict):
        return False
    preserved_roots = scope.get("preserved_project_document_roots")
    if not isinstance(preserved_roots, list) or "docs/product/" not in preserved_roots:
        return False
    steps = value.get("steps")
    if not isinstance(steps, list):
        return False
    expected_step_ids = [
        "inspect-transition",
        "apply-runtime-refresh",
        "verify-target",
        "resume-workflow",
    ]
    if [step.get("id") for step in steps if isinstance(step, dict)] != expected_step_ids:
        return False
    if not all(
        isinstance(step, dict)
        and step.get("enabled") is True
        for step in steps
    ):
        return False
    rollback = value.get("rollback")
    return (
        isinstance(rollback, dict)
        and rollback.get("required") is False
        and rollback.get("requires_trusted_artifact") is False
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
    expected = _task_collection_summary(
        tasks,
        item_key="required_links",
        status_counts_key="required_link_status_counts",
        non_satisfied_count_key="non_satisfied_required_link_count",
        repair_actions_key="link_repair_actions",
        repair_action_count_key="link_repair_action_count",
    )
    document_status_counts: dict[str, int] = {}
    non_authored_document_count = 0
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("documents"), list):
            continue
        for document in task["documents"]:
            if not isinstance(document, dict):
                continue
            status = str(document.get("status", "unknown") or "unknown")
            document_status_counts[status] = document_status_counts.get(status, 0) + 1
            if status not in {"authored", "reference_template"}:
                non_authored_document_count += 1
    expected["document_status_counts"] = dict(sorted(document_status_counts.items()))
    expected["non_authored_document_count"] = non_authored_document_count
    return summary == expected


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


def _consumer_resume_handoff_ready(payload: dict[str, object], target: Path) -> bool:
    routing = payload.get("implementation_routing")
    routing_map = routing if isinstance(routing, dict) else {}
    run_preview = payload.get("implementation_run_preview")
    run_preview_map = run_preview if isinstance(run_preview, dict) else {}
    snapshot = run_preview_map.get("snapshot")
    snapshot_map = snapshot if isinstance(snapshot, dict) else {}
    snapshot_id = snapshot_map.get("id")
    task_id = run_preview_map.get("task_id")
    next_action = run_preview_map.get("next_action")
    next_action_map = next_action if isinstance(next_action, dict) else {}
    expected_argv = [
        "bin/governance",
        "implementation",
        "run",
        ".",
        "--task",
        task_id,
        "--apply-start",
        "--expect-snapshot",
        snapshot_id,
        "--json",
    ]
    return (
        payload.get("ok") is True
        and payload.get("resume") is True
        and payload.get("writes_state") is True
        and payload.get("state_write_observed") is True
        and payload.get("phase_before") == "design-derivation"
        and payload.get("phase_after") == "implementation"
        and payload.get("implementation_routing_ok") is True
        and payload.get("implementation_route_ready") is True
        and payload.get("implementation_handoff_ready") is True
        and routing_map.get("ok") is True
        and routing_map.get("transition_applied") is True
        and routing_map.get("transition_already_current") is False
        and routing_map.get("status") == "ready_to_start"
        and run_preview_map.get("handoff_ready") is True
        and run_preview_map.get("runner_contract_valid") is True
        and run_preview_map.get("status") == "ready_to_start"
        and task_id == IMPLEMENTATION_TASK_ID
        and isinstance(snapshot_id, str)
        and re.fullmatch(r"[0-9a-f]{64}", snapshot_id) is not None
        and next_action_map.get("argv") == expected_argv
        and next_action_map.get("cwd") == str(target)
        and next_action_map.get("writes_state") is True
        and next_action_map.get("approval_required") is False
    )


def _consumer_resume_reentry_ready(
    payload: dict[str, object],
    initial_payload: dict[str, object],
    target: Path,
) -> bool:
    routing = payload.get("implementation_routing")
    routing_map = routing if isinstance(routing, dict) else {}
    run_preview = payload.get("implementation_run_preview")
    run_preview_map = run_preview if isinstance(run_preview, dict) else {}
    initial_preview = initial_payload.get("implementation_run_preview")
    initial_preview_map = initial_preview if isinstance(initial_preview, dict) else {}
    return (
        payload.get("ok") is True
        and payload.get("resume") is True
        and payload.get("writes_state") is False
        and payload.get("state_write_observed") is False
        and payload.get("phase_before") == "implementation"
        and payload.get("phase_after") == "implementation"
        and payload.get("implementation_routing_ok") is True
        and payload.get("implementation_route_ready") is True
        and payload.get("implementation_handoff_ready") is True
        and routing_map.get("ok") is True
        and routing_map.get("transition_applied") is False
        and routing_map.get("transition_already_current") is True
        and run_preview_map.get("handoff_ready") is True
        and run_preview_map.get("runner_contract_valid") is True
        and run_preview_map.get("status") == "ready_to_start"
        and run_preview_map.get("task_id") == IMPLEMENTATION_TASK_ID
        and run_preview_map.get("snapshot") == initial_preview_map.get("snapshot")
        and run_preview_map.get("next_action") == initial_preview_map.get("next_action")
        and isinstance(run_preview_map.get("next_action"), dict)
        and run_preview_map["next_action"].get("cwd") == str(target)
    )


def _consumer_resume_handoff_summary(
    payload: dict[str, object],
    reentry_payload: dict[str, object],
    target: Path,
) -> dict[str, object]:
    exercised = bool(payload)
    run_preview = payload.get("implementation_run_preview") if exercised else {}
    run_preview_map = run_preview if isinstance(run_preview, dict) else {}
    routing = payload.get("implementation_routing") if exercised else {}
    routing_map = routing if isinstance(routing, dict) else {}
    next_action = run_preview_map.get("next_action")
    next_action_map = next_action if isinstance(next_action, dict) else {}
    argv = next_action_map.get("argv")
    return {
        "exercised": exercised,
        "ok": _consumer_resume_handoff_ready(payload, target) if exercised else True,
        "phase_before": str(payload.get("phase_before", "")) if exercised else "",
        "phase_after": str(payload.get("phase_after", "")) if exercised else "",
        "transition_applied": routing_map.get("transition_applied") is True,
        "state_write_observed": payload.get("state_write_observed") is True,
        "routing_ok": payload.get("implementation_routing_ok") is True,
        "route_ready": payload.get("implementation_route_ready") is True,
        "runner_contract_valid": run_preview_map.get("runner_contract_valid") is True,
        "handoff_ready": run_preview_map.get("handoff_ready") is True,
        "status": str(run_preview_map.get("status", "")),
        "task_id": str(run_preview_map.get("task_id", "")),
        "snapshot_guarded": isinstance(argv, list) and "--expect-snapshot" in argv,
        "reentry_exercised": bool(reentry_payload),
        "reentry_ok": (
            _consumer_resume_reentry_ready(reentry_payload, payload, target)
            if reentry_payload
            else not exercised
        ),
        "reentry_transition_already_current": (
            reentry_payload.get("implementation_routing", {}).get("transition_already_current") is True
            if isinstance(reentry_payload.get("implementation_routing"), dict)
            else False
        ),
        "reentry_snapshot_stable": (
            reentry_payload.get("implementation_run_preview", {}).get("snapshot")
            == run_preview_map.get("snapshot")
            if isinstance(reentry_payload.get("implementation_run_preview"), dict)
            else False
        ),
    }


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
