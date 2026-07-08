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
    ("api_authoring", "api-authoring", "api-contracts"),
    ("backend_authoring", "backend-authoring", "backend-modules"),
    ("frontend_authoring", "frontend-authoring", "frontend-modules"),
    ("test_strategy_authoring", "test-strategy-authoring", "test-strategy"),
    ("implementation_planning_authoring", "implementation-planning-authoring", "implementation-planning"),
    ("architecture_decisions_authoring", "architecture-decisions-authoring", "architecture-decisions"),
]
ACCEPTANCE_ID_HEADING_RE = re.compile(r"^##[ \t]+(?P<id>A-[0-9]{3})\b", re.MULTILINE)


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

    implementation_preflight = _run_json(
        steps,
        "implementation_advance_check",
        ["bin/governance", "advance", "implementation", ".", "--check", "--json"],
        target,
        expected_returncode=1,
    )
    _require(implementation_preflight.get("ok") is False, "implementation gate unexpectedly passed")

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
        "implementation_gate": {
            "ok": implementation_preflight.get("ok"),
            "expected_blocked": True,
        },
        "next": "replace design scaffold placeholders with source-backed content before implementation handoff",
    }


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
