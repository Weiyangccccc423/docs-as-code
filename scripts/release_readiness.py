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
    start = payload.get("implementation_start")
    verification = payload.get("implementation_verification")
    closeout = payload.get("implementation_closeout")
    runtime_refresh = payload.get("runtime_refresh")
    return (
        isinstance(gate, dict)
        and gate.get("placeholder_blocked_ok") is False
        and gate.get("placeholder_expected_blocked") is True
        and gate.get("ready_ok") is True
        and isinstance(start, dict)
        and start.get("ready") is True
        and start.get("applied_status_updates") is True
        and start.get("implementation_plan_in_progress") is True
        and isinstance(verification, dict)
        and verification.get("ok") is True
        and verification.get("preview_ready") is True
        and verification.get("executed") is True
        and verification.get("evidence_recorded") is True
        and verification.get("command_passed") is True
        and verification.get("all_current_results_passing") is True
        and isinstance(closeout, dict)
        and closeout.get("blocked_without_evidence") is True
        and closeout.get("ready_with_evidence") is True
        and closeout.get("applied_status_updates") is True
        and closeout.get("implementation_plan_complete") is True
        and closeout.get("workflow_plan_complete") is True
        and isinstance(runtime_refresh, dict)
        and runtime_refresh.get("check_ok") is True
        and runtime_refresh.get("applied") is True
        and runtime_refresh.get("workflow_plan_complete_after_refresh") is True
    )


def _dry_run_implementation_task_package_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    package = payload.get("implementation_task_package")
    if not isinstance(package, dict):
        return False
    names = package.get("verification_command_names")
    commands = package.get("verification_commands")
    summary = package.get("verification_command_summary")
    contract = package.get("execution_contract")
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or not name for name in names)
        or len(names) != len(set(names))
        or not isinstance(commands, list)
        or len(commands) != len(names)
        or not isinstance(summary, dict)
        or not isinstance(contract, dict)
    ):
        return False
    for name, command in zip(names, commands):
        if not isinstance(command, dict) or command.get("name") != name or command.get("ready") is not True:
            return False
        for key in ("preflight_command", "execute_command"):
            embedded = command.get(key)
            if not isinstance(embedded, dict) or not isinstance(embedded.get("argv"), list) or not embedded["argv"]:
                return False
    return (
        summary.get("required_count") == len(names)
        and summary.get("ready_count") == len(names)
        and summary.get("blocked_count") == 0
        and summary.get("all_ready") is True
        and contract.get("decision_policy")
        == "claim_then_execute_all_required_verification_commands_then_closeout"
        and contract.get("verification_commands") == commands
    )


def _dry_run_implementation_runner_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    runner = payload.get("implementation_run")
    if not isinstance(runner, dict):
        return False
    required_count = runner.get("required_count")
    passed_count = runner.get("passed_count")
    return (
        runner.get("ready_check") is True
        and runner.get("snapshot_guarded_start") is True
        and runner.get("start_applied") is True
        and runner.get("verification_ready") is True
        and isinstance(required_count, int)
        and not isinstance(required_count, bool)
        and required_count > 0
        and passed_count == required_count
        and runner.get("executed_all_required") is True
        and runner.get("snapshot_guarded_closeout") is True
        and runner.get("closeout_applied") is True
        and runner.get("complete") is True
    )


def _dry_run_stack_acceptance_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    summary = payload.get("stack_acceptance")
    if not isinstance(summary, dict):
        return False
    stacks = summary.get("stacks")
    return isinstance(stacks, dict) and all(
        isinstance(stacks.get(name), dict) and stacks[name].get("status") == "passed"
        for name in ("python", "node")
    )


def _dry_run_target_local_make_coverage_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return False
    step_ids = {str(step.get("id")) for step in steps if isinstance(step, dict)}
    required = set(TARGET_LOCAL_MAKE_STEP_IDS)
    return required <= step_ids


def _dry_run_product_dispositions_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    dispositions = payload.get("product_dispositions")
    if not isinstance(dispositions, dict):
        return False
    recorded_count = dispositions.get("recorded_count")
    return (
        isinstance(recorded_count, int)
        and not isinstance(recorded_count, bool)
        and recorded_count > 0
        and dispositions.get("omit_unsupported_count") == recorded_count
        and dispositions.get("unresolved_decision_count") == 0
        and dispositions.get("work_package_routed_to_phase_action") is True
    )


def _dry_run_design_reviews_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    reviews = payload.get("design_reviews")
    if not isinstance(reviews, dict):
        return False
    expected_count = reviews.get("expected_count")
    return (
        isinstance(expected_count, int)
        and not isinstance(expected_count, bool)
        and expected_count > 0
        and reviews.get("recorded_count") == expected_count
        and reviews.get("active_count") == expected_count
        and reviews.get("missing_count") == 0
        and reviews.get("stale_count") == 0
        and reviews.get("work_package_complete") is True
    )


def _dry_run_api_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("api_review")
    return (
        isinstance(review, dict)
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and review.get("baseline_mode") == "initial-baseline"
        and review.get("scorecard_grade") in {"A", "B"}
        and isinstance(review.get("evidence_paths"), list)
        and len(review.get("evidence_paths", [])) == 5
    )


def _dry_run_threat_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("threat_review")
    return (
        isinstance(review, dict)
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and isinstance(review.get("element_count"), int)
        and not isinstance(review.get("element_count"), bool)
        and review.get("element_count", 0) > 0
        and isinstance(review.get("high_dread_threat_count"), int)
        and not isinstance(review.get("high_dread_threat_count"), bool)
        and review.get("high_dread_threat_count", -1) >= 0
        and isinstance(review.get("evidence_paths"), list)
        and len(review.get("evidence_paths", [])) == 2
    )


def _dry_run_reliability_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("reliability_review")
    return (
        isinstance(review, dict)
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and review.get("mode") == "required"
        and isinstance(review.get("slo_count"), int)
        and not isinstance(review.get("slo_count"), bool)
        and review.get("slo_count", 0) > 0
        and isinstance(review.get("evidence_paths"), list)
        and len(review.get("evidence_paths", [])) == 4
    )


def _dry_run_migration_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("migration_review")
    return (
        isinstance(review, dict)
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and review.get("mode") == "required"
        and review.get("compatibility_status") in {
            "fully_compatible", "backward_compatible", "accepted_with_mitigations"
        }
        and isinstance(review.get("evidence_paths"), list)
        and len(review.get("evidence_paths", [])) == 4
    )


def _dry_run_target_local_make_details(payload: dict[str, object] | None) -> dict[str, object]:
    steps = payload.get("steps") if payload else []
    step_ids = {str(step.get("id")) for step in steps if isinstance(step, dict)} if isinstance(steps, list) else set()
    return {
        "required_step_ids": TARGET_LOCAL_MAKE_STEP_IDS,
        "missing_step_ids": [step_id for step_id in TARGET_LOCAL_MAKE_STEP_IDS if step_id not in step_ids],
    }


def _artifact_smoke_fresh_target_init_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    fresh_target_init = payload.get("fresh_target_init")
    return (
        isinstance(fresh_target_init, dict)
        and fresh_target_init.get("ok") is True
        and fresh_target_init.get("target_local_verify_ok") is True
        and fresh_target_init.get("target_local_status_ok") is True
        and fresh_target_init.get("target_local_workflow_plan_ok") is True
        and fresh_target_init.get("target_local_work_package_ok") is True
        and fresh_target_init.get("runtime_manifest") is True
        and fresh_target_init.get("workflow_pack_snapshot") is True
        and fresh_target_init.get("product_source_manifest") is True
    )


def _artifact_smoke_stack_acceptance_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    summary = payload.get("stack_acceptance")
    return (
        isinstance(summary, dict)
        and summary.get("ok") is True
        and summary.get("all_required_passed") is True
        and isinstance(summary.get("stacks"), dict)
        and all(
            isinstance(summary["stacks"].get(name), dict)
            and summary["stacks"][name].get("status") == "passed"
            for name in ("python", "node")
        )
    )


def _artifact_smoke_product_dispositions_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    dispositions = payload.get("product_dispositions")
    return (
        isinstance(dispositions, dict)
        and dispositions.get("ok") is True
        and isinstance(dispositions.get("recorded_count"), int)
        and dispositions.get("recorded_count", 0) > 0
        and dispositions.get("omit_unsupported_count") == dispositions.get("recorded_count")
        and dispositions.get("unresolved_decision_count") == 0
        and dispositions.get("work_package_routed_to_phase_action") is True
    )


def _artifact_smoke_design_reviews_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    reviews = payload.get("design_reviews")
    return (
        isinstance(reviews, dict)
        and reviews.get("ok") is True
        and isinstance(reviews.get("expected_count"), int)
        and not isinstance(reviews.get("expected_count"), bool)
        and reviews.get("expected_count", 0) > 0
        and reviews.get("recorded_count") == reviews.get("expected_count")
        and reviews.get("active_count") == reviews.get("expected_count")
        and reviews.get("missing_count") == 0
        and reviews.get("stale_count") == 0
        and reviews.get("work_package_complete") is True
    )


def _artifact_smoke_api_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("api_review")
    return (
        isinstance(review, dict)
        and review.get("ok") is True
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and review.get("scorecard_grade") in {"A", "B"}
    )


def _artifact_smoke_threat_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("threat_review")
    return (
        isinstance(review, dict)
        and review.get("ok") is True
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and isinstance(review.get("element_count"), int)
        and not isinstance(review.get("element_count"), bool)
        and review.get("element_count", 0) > 0
    )


def _artifact_smoke_reliability_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("reliability_review")
    return (
        isinstance(review, dict)
        and review.get("ok") is True
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and review.get("mode") == "required"
        and isinstance(review.get("slo_count"), int)
        and not isinstance(review.get("slo_count"), bool)
        and review.get("slo_count", 0) > 0
    )


def _artifact_smoke_migration_review_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    review = payload.get("migration_review")
    return (
        isinstance(review, dict)
        and review.get("ok") is True
        and review.get("preflight_ok") is True
        and review.get("applied") is True
        and review.get("current_after_runtime_refresh") is True
        and review.get("mode") == "required"
        and review.get("compatibility_status") in {
            "fully_compatible", "backward_compatible", "accepted_with_mitigations"
        }
    )


def _artifact_smoke_work_package_ok(
    bootstrap_summary: dict[str, object],
    *,
    expected_phase: str,
    expected_kind: str,
    expected_queue_id: str,
) -> bool:
    work_package = bootstrap_summary.get("work_package")
    if not isinstance(work_package, dict):
        return False
    can_start = work_package.get("can_start")
    stop_before_work = work_package.get("stop_before_work")
    skill_ready = work_package.get("skill_ready")
    return (
        work_package.get("ok") is True
        and work_package.get("phase") == expected_phase
        and work_package.get("kind") == expected_kind
        and work_package.get("queue_id") == expected_queue_id
        and isinstance(work_package.get("work_id"), str)
        and bool(work_package.get("work_id"))
        and isinstance(work_package.get("status"), str)
        and bool(work_package.get("status"))
        and isinstance(work_package.get("next_action_kind"), str)
        and bool(work_package.get("next_action_kind"))
        and isinstance(can_start, bool)
        and isinstance(stop_before_work, bool)
        and isinstance(skill_ready, bool)
        and can_start is skill_ready
        and stop_before_work is (not skill_ready)
        and isinstance(work_package.get("missing_local_workflow_skills"), list)
        and isinstance(work_package.get("missing_authority_routing_skills"), list)
    )


def _artifact_smoke_consumer_bootstrap_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    consumer_bootstrap = payload.get("consumer_bootstrap_product_structure")
    expanded_flags = consumer_bootstrap.get("workflow_preset_expanded_flags") if isinstance(consumer_bootstrap, dict) else []
    return (
        isinstance(consumer_bootstrap, dict)
        and consumer_bootstrap.get("ok") is True
        and consumer_bootstrap.get("phase") == "product-structuring"
        and consumer_bootstrap.get("workflow_preset") == "product-structure"
        and _artifact_smoke_bootstrap_authority_inventory_ok(consumer_bootstrap)
        and _artifact_smoke_bootstrap_env_auto_repair_ok(consumer_bootstrap)
        and _artifact_smoke_work_package_ok(
            consumer_bootstrap,
            expected_phase="product-structuring",
            expected_kind="product-authoring",
            expected_queue_id="product-plan",
        )
        and consumer_bootstrap.get("auto_repair_env") is True
        and consumer_bootstrap.get("product_structure_apply_ok") is True
        and consumer_bootstrap.get("goals_chapter") is True
        and consumer_bootstrap.get("acceptance_chapter") is True
        and isinstance(expanded_flags, list)
        and "product_structure_apply" in expanded_flags
    )


def _artifact_smoke_consumer_design_scaffold_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    design_scaffold = payload.get("consumer_bootstrap_design_scaffold")
    expanded_flags = design_scaffold.get("workflow_preset_expanded_flags") if isinstance(design_scaffold, dict) else []
    return (
        isinstance(design_scaffold, dict)
        and design_scaffold.get("ok") is True
        and design_scaffold.get("phase") == "design-derivation"
        and design_scaffold.get("workflow_preset") == "design-scaffold"
        and _artifact_smoke_bootstrap_authority_inventory_ok(design_scaffold)
        and _artifact_smoke_bootstrap_env_auto_repair_ok(design_scaffold)
        and _artifact_smoke_work_package_ok(
            design_scaffold,
            expected_phase="design-derivation",
            expected_kind="design-authoring",
            expected_queue_id="architecture-authoring",
        )
        and design_scaffold.get("auto_repair_env") is True
        and design_scaffold.get("product_structure_apply_ok") is True
        and design_scaffold.get("advanced_design_derivation") is True
        and design_scaffold.get("design_scaffold_apply_ok") is True
        and design_scaffold.get("post_verify_blocked_by_placeholders") is True
        and design_scaffold.get("system_context_doc") is True
        and design_scaffold.get("endpoint_contract_doc") is True
        and isinstance(expanded_flags, list)
        and "design_scaffold_apply" in expanded_flags
    )


def _artifact_smoke_consumer_design_routing_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    design_routing = payload.get("consumer_bootstrap_design_routing")
    expanded_flags = design_routing.get("workflow_preset_expanded_flags") if isinstance(design_routing, dict) else []
    return (
        isinstance(design_routing, dict)
        and design_routing.get("ok") is True
        and design_routing.get("phase") == "design-derivation"
        and design_routing.get("workflow_preset") == "design-routing"
        and _artifact_smoke_bootstrap_authority_inventory_ok(design_routing)
        and _artifact_smoke_bootstrap_env_auto_repair_ok(design_routing)
        and _artifact_smoke_work_package_ok(
            design_routing,
            expected_phase="design-derivation",
            expected_kind="design-authoring",
            expected_queue_id="architecture-authoring",
        )
        and design_routing.get("design_scaffold_apply_ok") is True
        and design_routing.get("design_authoring_preview_ok") is True
        and design_routing.get("queue_count") == 9
        and design_routing.get("missing_queue_ids") == []
        and design_routing.get("failed_queue_ids") == []
        and _artifact_smoke_design_authoring_summary_ok(design_routing)
        and isinstance(expanded_flags, list)
        and "design_authoring_preview" in expanded_flags
    )


def _artifact_smoke_design_authoring_summary_ok(design_routing: dict[str, object]) -> bool:
    queue_summaries = design_routing.get("queue_summaries")
    authoring_summary = design_routing.get("authoring_summary")
    active_work = design_routing.get("active_work")
    if (
        design_routing.get("authoring_summary_ok") is not True
        or not isinstance(queue_summaries, list)
        or not isinstance(authoring_summary, dict)
        or not isinstance(active_work, dict)
    ):
        return False
    normalized_queues = [summary for summary in queue_summaries if isinstance(summary, dict)]
    if len(normalized_queues) != len(DESIGN_AUTHORING_QUEUE_IDS):
        return False
    if [summary.get("queue_id") for summary in normalized_queues] != DESIGN_AUTHORING_QUEUE_IDS:
        return False
    if [summary.get("sequence") for summary in normalized_queues] != list(
        range(1, len(DESIGN_AUTHORING_QUEUE_IDS) + 1)
    ):
        return False
    category_counts = [
        authoring_summary.get("blocked_queue_count"),
        authoring_summary.get("decision_required_queue_count"),
        authoring_summary.get("ready_queue_count"),
    ]
    if not all(
        isinstance(count, int) and not isinstance(count, bool) and count >= 0
        for count in category_counts
    ):
        return False
    if sum(category_counts) != len(DESIGN_AUTHORING_QUEUE_IDS):
        return False
    status_counts: dict[str, int] = {}
    for summary in normalized_queues:
        status = summary.get("status")
        if not isinstance(status, str) or not status:
            return False
        status_counts[status] = status_counts.get(status, 0) + 1
    total_fields = {
        "total_task_count": "task_count",
        "total_open_decision_count": "open_decision_count",
        "total_non_satisfied_required_link_count": "non_satisfied_required_link_count",
        "total_link_repair_action_count": "link_repair_action_count",
    }
    for total_field, queue_field in total_fields.items():
        values = [summary.get(queue_field) for summary in normalized_queues]
        if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values):
            return False
        if authoring_summary.get(total_field) != sum(values):
            return False
    next_queue = next(
        (summary for summary in normalized_queues if summary.get("status") not in {"ready", "complete"}),
        None,
    )
    return (
        next_queue is not None
        and authoring_summary.get("queue_count") == len(DESIGN_AUTHORING_QUEUE_IDS)
        and authoring_summary.get("queue_status_counts") == dict(sorted(status_counts.items()))
        and authoring_summary.get("next_queue_id") == next_queue.get("queue_id")
        and authoring_summary.get("next_active_work") == active_work
        and active_work.get("queue_id") == next_queue.get("queue_id")
        and active_work.get("queue_sequence") == next_queue.get("sequence")
        and active_work.get("status") == next_queue.get("status")
        and category_counts[0] > 0
        and authoring_summary.get("total_task_count", 0) > 0
        and authoring_summary.get("total_non_satisfied_required_link_count", 0) > 0
    )


def _artifact_smoke_consumer_implementation_routing_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    implementation_routing = payload.get("consumer_bootstrap_implementation_routing")
    expanded_flags = (
        implementation_routing.get("workflow_preset_expanded_flags")
        if isinstance(implementation_routing, dict)
        else []
    )
    return (
        isinstance(implementation_routing, dict)
        and implementation_routing.get("ok") is True
        and implementation_routing.get("phase") == "design-derivation"
        and implementation_routing.get("workflow_preset") == "implementation-routing"
        and _artifact_smoke_bootstrap_authority_inventory_ok(implementation_routing)
        and _artifact_smoke_bootstrap_env_auto_repair_ok(implementation_routing)
        and _artifact_smoke_work_package_ok(
            implementation_routing,
            expected_phase="design-derivation",
            expected_kind="design-authoring",
            expected_queue_id="architecture-authoring",
        )
        and implementation_routing.get("design_authoring_preview_ok") is True
        and implementation_routing.get("implementation_readiness_preview_ok") is True
        and implementation_routing.get("readiness_previewed") is True
        and implementation_routing.get("readiness_ok") is False
        and implementation_routing.get("implementation_ready") is False
        and isinstance(implementation_routing.get("readiness_blocker_count"), int)
        and implementation_routing["readiness_blocker_count"] > 0
        and isinstance(implementation_routing.get("readiness_blocker_codes"), list)
        and "governance_scaffold_placeholder" in implementation_routing["readiness_blocker_codes"]
        and isinstance(implementation_routing.get("readiness_next_blocker"), dict)
        and isinstance(implementation_routing["readiness_next_blocker"].get("code"), str)
        and implementation_routing["readiness_next_blocker"]["code"]
        in implementation_routing["readiness_blocker_codes"]
        and isinstance(implementation_routing.get("readiness_next_repair_action"), dict)
        and bool(implementation_routing["readiness_next_repair_action"])
        and implementation_routing.get("advance_previewed") is True
        and implementation_routing.get("advance_ready") is False
        and implementation_routing.get("advance_apply_skipped") is True
        and implementation_routing.get("advance_apply_skip_code") == "advance_preview_not_ready"
        and implementation_routing.get("advance_apply_blocked_by") == "implementation_advance_preview"
        and implementation_routing.get("start_preview_skipped") is True
        and implementation_routing.get("start_preview_skip_code") == "readiness_preview_not_ready"
        and implementation_routing.get("start_preview_blocked_by") == "implementation_readiness_preview"
        and implementation_routing.get("start_apply_skipped") is True
        and implementation_routing.get("start_apply_skip_code") == "start_preview_not_ready"
        and implementation_routing.get("start_apply_blocked_by") == "implementation_start_preview"
        and implementation_routing.get("closeout_preview_skipped") is True
        and implementation_routing.get("closeout_preview_skip_code") == "start_apply_not_applied"
        and implementation_routing.get("closeout_preview_blocked_by") == "implementation_start_apply"
        and implementation_routing.get("closeout_apply_skipped") is True
        and implementation_routing.get("closeout_apply_skip_code") == "closeout_preview_not_ready"
        and implementation_routing.get("closeout_apply_blocked_by") == "implementation_closeout_preview"
        and implementation_routing.get("blocked_by_placeholders") is True
        and isinstance(expanded_flags, list)
        and "implementation_readiness_preview" in expanded_flags
        and "implementation_advance_preview" in expanded_flags
        and "implementation_closeout_apply" in expanded_flags
    )


def _artifact_smoke_bootstrap_authority_inventory_ok(bootstrap_summary: dict[str, object]) -> bool:
    inventory = bootstrap_summary.get("authority_skill_inventory")
    if not isinstance(inventory, dict):
        return False
    return (
        inventory.get("ok") is True
        and inventory.get("strict") is False
        and inventory.get("manifest_ok") is True
        and inventory.get("manifest_aligned_with_routing") is True
        and inventory.get("repair_requested") is True
        and inventory.get("repair_check") is True
        and inventory.get("repair_writes_state") is False
        and inventory.get("required_skill_count", 0) >= 19
        and inventory.get("missing_policy") == "load_from_agent_environment_or_stop_before_guessing"
    )


def _artifact_smoke_bootstrap_env_auto_repair_ok(bootstrap_summary: dict[str, object]) -> bool:
    env_auto_repair = bootstrap_summary.get("env_auto_repair")
    if not isinstance(env_auto_repair, dict):
        return False
    return (
        env_auto_repair.get("ok") is True
        and env_auto_repair.get("requested") is True
        and env_auto_repair.get("decision") == "continue_workflow"
        and env_auto_repair.get("status") == "continue"
        and env_auto_repair.get("stop_before_workflow") is False
        and env_auto_repair.get("can_continue") is True
        and env_auto_repair.get("can_auto_apply") is False
        and env_auto_repair.get("requires_approval") is False
        and env_auto_repair.get("manual_repair_required") is False
        and env_auto_repair.get("runnable_action_ids") == []
        and env_auto_repair.get("approval_action_ids") == []
        and env_auto_repair.get("manual_action_ids") == []
        and env_auto_repair.get("next_step") == "continue workflow"
        and env_auto_repair.get("final_env_check_ok") is True
        and env_auto_repair.get("final_missing_required") == []
    )


def _env_repair_decision_allows_workflow(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
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


def _authority_skill_inventory_ok(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    skills = payload.get("skills")
    if not isinstance(skills, list):
        return False
    skill_names = {str(skill.get("name")) for skill in skills if isinstance(skill, dict)}
    required = {
        "senior-architect",
        "api-design-reviewer",
        "senior-backend",
        "database-designer",
        "database-schema-designer",
        "migration-architect",
        "senior-security",
        "ci-cd-pipeline-builder",
    }
    manifest = payload.get("manifest")
    repair_plan = payload.get("repair_plan")
    status_counts = payload.get("status_counts")
    return (
        payload.get("ok") is True
        and payload.get("strict") is False
        and isinstance(manifest, dict)
        and manifest.get("ok") is True
        and manifest.get("aligned_with_routing") is True
        and isinstance(status_counts, dict)
        and sum(value for value in status_counts.values() if isinstance(value, int) and not isinstance(value, bool))
        == len(skills)
        and isinstance(repair_plan, dict)
        and repair_plan.get("requested") is True
        and repair_plan.get("check") is True
        and repair_plan.get("writes_state") is False
        and repair_plan.get("applied") is False
        and payload.get("missing_policy") == "load_from_agent_environment_or_stop_before_guessing"
        and payload.get("availability_scope") == "agent-environment"
        and required <= skill_names
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
        bool(steps[-1]["ok"])
        and bool(env_payload and env_payload.get("ok") is True)
        and _env_repair_decision_allows_workflow(env_payload),
        evidence="python3 scripts/check_env.py --json",
        details={
            "missing_required": env_payload.get("missing_required", []) if env_payload else [],
            "missing_recommended": env_payload.get("missing_recommended", []) if env_payload else [],
            "repair_decision": env_payload.get("repair_decision", {}) if env_payload else {},
        },
    )

    authority_payload = _run_step(
        steps,
        "authority_skill_inventory",
        [sys.executable, "scripts/authority_skills.py", "--repair", "--check", "--json"],
        parse_json=True,
    )
    _criterion(
        criteria,
        "authority-skill-inventory",
        bool(steps[-1]["ok"]) and _authority_skill_inventory_ok(authority_payload),
        evidence="python3 scripts/authority_skills.py --repair --check --json",
        details={
            "required_skill_count": authority_payload.get("required_skill_count") if authority_payload else 0,
            "available_skill_count": authority_payload.get("available_skill_count") if authority_payload else 0,
            "missing_skill_count": authority_payload.get("missing_skill_count") if authority_payload else 0,
            "missing_policy": authority_payload.get("missing_policy") if authority_payload else "",
            "manifest_ok": authority_payload.get("manifest", {}).get("ok")
            if authority_payload and isinstance(authority_payload.get("manifest"), dict)
            else False,
            "manifest_aligned_with_routing": authority_payload.get("manifest", {}).get("aligned_with_routing")
            if authority_payload and isinstance(authority_payload.get("manifest"), dict)
            else False,
            "status_counts": authority_payload.get("status_counts", {}) if authority_payload else {},
            "repair_plan": authority_payload.get("repair_plan", {}) if authority_payload else {},
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
        and _dry_run_closeout_evidence_ok(dry_run_payload)
        and _dry_run_implementation_task_package_ok(dry_run_payload)
        and _dry_run_implementation_runner_ok(dry_run_payload)
        and _dry_run_stack_acceptance_ok(dry_run_payload)
        and _dry_run_product_dispositions_ok(dry_run_payload)
        and _dry_run_api_review_ok(dry_run_payload)
        and _dry_run_threat_review_ok(dry_run_payload)
        and _dry_run_reliability_review_ok(dry_run_payload)
        and _dry_run_migration_review_ok(dry_run_payload)
        and _dry_run_design_reviews_ok(dry_run_payload)
        and _dry_run_target_local_make_coverage_ok(dry_run_payload),
        evidence="python3 scripts/dry_run_workflow.py --json",
        details={
            "final_phase": dry_run_payload.get("final_phase") if dry_run_payload else "",
            "api_candidate_count": dry_run_payload.get("api_candidate_count") if dry_run_payload else 0,
            "implementation_closeout": dry_run_payload.get("implementation_closeout") if dry_run_payload else {},
            "implementation_verification": dry_run_payload.get("implementation_verification")
            if dry_run_payload
            else {},
            "implementation_task_package": dry_run_payload.get("implementation_task_package")
            if dry_run_payload
            else {},
            "implementation_run": dry_run_payload.get("implementation_run") if dry_run_payload else {},
            "stack_acceptance": dry_run_payload.get("stack_acceptance") if dry_run_payload else {},
            "product_dispositions": dry_run_payload.get("product_dispositions") if dry_run_payload else {},
            "api_review": dry_run_payload.get("api_review") if dry_run_payload else {},
            "threat_review": dry_run_payload.get("threat_review") if dry_run_payload else {},
            "reliability_review": dry_run_payload.get("reliability_review") if dry_run_payload else {},
            "migration_review": dry_run_payload.get("migration_review") if dry_run_payload else {},
            "design_reviews": dry_run_payload.get("design_reviews") if dry_run_payload else {},
            "target_local_make_coverage": _dry_run_target_local_make_details(dry_run_payload),
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
        and _dry_run_implementation_task_package_ok(multi_acceptance_payload)
        and _dry_run_implementation_runner_ok(multi_acceptance_payload)
        and _dry_run_stack_acceptance_ok(multi_acceptance_payload)
        and _dry_run_product_dispositions_ok(multi_acceptance_payload)
        and _dry_run_api_review_ok(multi_acceptance_payload)
        and _dry_run_threat_review_ok(multi_acceptance_payload)
        and _dry_run_reliability_review_ok(multi_acceptance_payload)
        and _dry_run_migration_review_ok(multi_acceptance_payload)
        and _dry_run_design_reviews_ok(multi_acceptance_payload)
        and multi_acceptance_payload.get("acceptance_id_count") == 4
        and multi_acceptance_payload.get("api_candidate_count") == 4
        and isinstance(authoring_counts, dict)
        and len(authoring_counts) == 9
        and all(value == 4 for value in authoring_counts.values())
        and _dry_run_target_local_make_coverage_ok(multi_acceptance_payload),
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
            "implementation_verification": multi_acceptance_payload.get("implementation_verification")
            if multi_acceptance_payload
            else {},
            "implementation_task_package": multi_acceptance_payload.get("implementation_task_package")
            if multi_acceptance_payload
            else {},
            "implementation_run": multi_acceptance_payload.get("implementation_run")
            if multi_acceptance_payload
            else {},
            "stack_acceptance": multi_acceptance_payload.get("stack_acceptance")
            if multi_acceptance_payload
            else {},
            "product_dispositions": multi_acceptance_payload.get("product_dispositions")
            if multi_acceptance_payload
            else {},
            "api_review": multi_acceptance_payload.get("api_review")
            if multi_acceptance_payload
            else {},
            "threat_review": multi_acceptance_payload.get("threat_review")
            if multi_acceptance_payload
            else {},
            "reliability_review": multi_acceptance_payload.get("reliability_review")
            if multi_acceptance_payload
            else {},
            "migration_review": multi_acceptance_payload.get("migration_review")
            if multi_acceptance_payload
            else {},
            "design_reviews": multi_acceptance_payload.get("design_reviews")
            if multi_acceptance_payload
            else {},
            "target_local_make_coverage": _dry_run_target_local_make_details(multi_acceptance_payload),
        },
    )

    with tempfile.TemporaryDirectory(prefix="docs-as-code-release-") as tmp:
        base = Path(tmp)
        export_check_payload = _run_step(
            steps,
            "source_pack_export_check",
            [
                sys.executable,
                "scripts/export_workflow_pack.py",
                "--check",
                "--output",
                base / "docs-as-code-workflow-pack",
                "--archive",
                base / "docs-as-code-workflow-pack.tar.gz",
                "--json",
            ],
            parse_json=True,
        )
        export_check_would_write = export_check_payload.get("would_write", []) if export_check_payload else []
        _criterion(
            criteria,
            "source-pack-export-check",
            bool(steps[-1]["ok"])
            and bool(export_check_payload and export_check_payload.get("ok") is True)
            and export_check_payload.get("check") is True
            and isinstance(export_check_would_write, list)
            and "pack-manifest.json" in export_check_would_write
            and bool(export_check_payload.get("would_archive")),
            evidence="python3 scripts/export_workflow_pack.py --check --output <tmp>/docs-as-code-workflow-pack --archive <tmp>/docs-as-code-workflow-pack.tar.gz --json",
            details={
                "file_count": export_check_payload.get("file_count") if export_check_payload else 0,
                "would_write_count": len(export_check_would_write) if isinstance(export_check_would_write, list) else 0,
                "would_archive": export_check_payload.get("would_archive") if export_check_payload else "",
            },
        )

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
        export_step_ok = bool(steps[-1]["ok"])
        repeat_export_payload = _run_step(
            steps,
            "source_pack_export_repeat",
            [
                sys.executable,
                "scripts/export_workflow_pack.py",
                "--output",
                base / "repeat" / "docs-as-code-workflow-pack",
                "--archive",
                base / "repeat" / "docs-as-code-workflow-pack.tar.gz",
                "--force",
                "--json",
            ],
            parse_json=True,
        )
        repeat_export_step_ok = bool(steps[-1]["ok"])
        artifact_smoke_payload = _run_step(
            steps,
            "release_artifact_smoke",
            [
                sys.executable,
                "scripts/smoke_workflow_pack_artifact.py",
                "--archive",
                base / "docs-as-code-workflow-pack.tar.gz",
                "--json",
            ],
            parse_json=True,
        )
        artifact_smoke_step_ok = bool(steps[-1]["ok"])
    verification = export_payload.get("verification", {}) if export_payload else {}
    _criterion(
        criteria,
        "source-pack-export",
        export_step_ok
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
    _criterion(
        criteria,
        "source-pack-reproducible-export",
        repeat_export_step_ok
        and bool(export_payload and export_payload.get("ok") is True)
        and bool(repeat_export_payload and repeat_export_payload.get("ok") is True)
        and export_payload.get("manifest_sha256") == repeat_export_payload.get("manifest_sha256")
        and export_payload.get("archive_sha256") == repeat_export_payload.get("archive_sha256")
        and export_payload.get("archive_size_bytes") == repeat_export_payload.get("archive_size_bytes"),
        evidence="python3 scripts/export_workflow_pack.py --output <tmp>/... --archive <tmp>/... --force --json twice",
        details={
            "first_manifest_sha256": export_payload.get("manifest_sha256") if export_payload else "",
            "second_manifest_sha256": repeat_export_payload.get("manifest_sha256") if repeat_export_payload else "",
            "first_archive_sha256": export_payload.get("archive_sha256") if export_payload else "",
            "second_archive_sha256": repeat_export_payload.get("archive_sha256") if repeat_export_payload else "",
            "first_archive_size_bytes": export_payload.get("archive_size_bytes") if export_payload else 0,
            "second_archive_size_bytes": repeat_export_payload.get("archive_size_bytes") if repeat_export_payload else 0,
        },
    )

    _criterion(
        criteria,
        "release-artifact-smoke",
        artifact_smoke_step_ok
        and bool(artifact_smoke_payload and artifact_smoke_payload.get("ok") is True)
        and artifact_smoke_payload.get("archive_source") == "provided-archive"
        and artifact_smoke_payload.get("archive_sha256") == export_payload.get("archive_sha256")
        and artifact_smoke_payload.get("manifest_sha256") == export_payload.get("manifest_sha256")
        and _artifact_smoke_fresh_target_init_ok(artifact_smoke_payload)
        and _artifact_smoke_stack_acceptance_ok(artifact_smoke_payload)
        and _dry_run_implementation_runner_ok(artifact_smoke_payload)
        and _artifact_smoke_product_dispositions_ok(artifact_smoke_payload)
        and _artifact_smoke_api_review_ok(artifact_smoke_payload)
        and _artifact_smoke_threat_review_ok(artifact_smoke_payload)
        and _artifact_smoke_reliability_review_ok(artifact_smoke_payload)
        and _artifact_smoke_migration_review_ok(artifact_smoke_payload)
        and _artifact_smoke_design_reviews_ok(artifact_smoke_payload)
        and _artifact_smoke_consumer_bootstrap_ok(artifact_smoke_payload)
        and _artifact_smoke_consumer_design_scaffold_ok(artifact_smoke_payload)
        and _artifact_smoke_consumer_design_routing_ok(artifact_smoke_payload)
        and _artifact_smoke_consumer_implementation_routing_ok(artifact_smoke_payload),
        evidence="python3 scripts/smoke_workflow_pack_artifact.py --archive <tmp>/docs-as-code-workflow-pack.tar.gz --json",
        details={
            "archive_source": artifact_smoke_payload.get("archive_source") if artifact_smoke_payload else "",
            "archive_member_count": artifact_smoke_payload.get("archive_member_count") if artifact_smoke_payload else 0,
            "archive_sha256": artifact_smoke_payload.get("archive_sha256") if artifact_smoke_payload else "",
            "export_archive_sha256": export_payload.get("archive_sha256") if export_payload else "",
            "manifest_sha256": artifact_smoke_payload.get("manifest_sha256") if artifact_smoke_payload else "",
            "export_manifest_sha256": export_payload.get("manifest_sha256") if export_payload else "",
            "fresh_target_init": artifact_smoke_payload.get("fresh_target_init", {})
            if artifact_smoke_payload
            else {},
            "product_dispositions": artifact_smoke_payload.get("product_dispositions", {})
            if artifact_smoke_payload
            else {},
            "api_review": artifact_smoke_payload.get("api_review", {})
            if artifact_smoke_payload
            else {},
            "threat_review": artifact_smoke_payload.get("threat_review", {})
            if artifact_smoke_payload
            else {},
            "reliability_review": artifact_smoke_payload.get("reliability_review", {})
            if artifact_smoke_payload
            else {},
            "migration_review": artifact_smoke_payload.get("migration_review", {})
            if artifact_smoke_payload
            else {},
            "design_reviews": artifact_smoke_payload.get("design_reviews", {})
            if artifact_smoke_payload
            else {},
            "implementation_verification": artifact_smoke_payload.get("implementation_verification", {})
            if artifact_smoke_payload
            else {},
            "implementation_task_package": artifact_smoke_payload.get("implementation_task_package", {})
            if artifact_smoke_payload
            else {},
            "implementation_run": artifact_smoke_payload.get("implementation_run", {})
            if artifact_smoke_payload
            else {},
            "stack_acceptance": artifact_smoke_payload.get("stack_acceptance", {})
            if artifact_smoke_payload
            else {},
            "consumer_bootstrap_product_structure": artifact_smoke_payload.get(
                "consumer_bootstrap_product_structure",
                {},
            )
            if artifact_smoke_payload
            else {},
            "consumer_bootstrap_design_scaffold": artifact_smoke_payload.get(
                "consumer_bootstrap_design_scaffold",
                {},
            )
            if artifact_smoke_payload
            else {},
            "consumer_bootstrap_design_routing": artifact_smoke_payload.get(
                "consumer_bootstrap_design_routing",
                {},
            )
            if artifact_smoke_payload
            else {},
            "consumer_bootstrap_implementation_routing": artifact_smoke_payload.get(
                "consumer_bootstrap_implementation_routing",
                {},
            )
            if artifact_smoke_payload
            else {},
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
