from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

try:
    from .bootstrap_tree import target_local_commands_payload
    from .design_plan import (
        build_api_authoring,
        build_api_candidates,
        build_architecture_decisions_authoring,
        build_backend_authoring,
        build_design_plan,
        build_frontend_authoring,
        build_implementation_planning_authoring,
        build_test_strategy_authoring,
    )
    from .product_structure import build_product_plan
    from .state import load_state
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from design_plan import (
        build_api_authoring,
        build_api_candidates,
        build_architecture_decisions_authoring,
        build_backend_authoring,
        build_design_plan,
        build_frontend_authoring,
        build_implementation_planning_authoring,
        build_test_strategy_authoring,
    )
    from product_structure import build_product_plan
    from state import load_state
    from workflow_actions import next_actions_payload


PRODUCT_PHASE = "product-structuring"
DESIGN_PHASE = "design-derivation"

DESIGN_AUTHORING_BUILDERS: tuple[tuple[str, list[str], Callable[[Path], dict[str, object]]], ...] = (
    ("api-authoring", ["bin/governance", "design", "api-authoring", ".", "--json"], build_api_authoring),
    ("backend-authoring", ["bin/governance", "design", "backend-authoring", ".", "--json"], build_backend_authoring),
    ("frontend-authoring", ["bin/governance", "design", "frontend-authoring", ".", "--json"], build_frontend_authoring),
    (
        "test-strategy-authoring",
        ["bin/governance", "design", "test-strategy-authoring", ".", "--json"],
        build_test_strategy_authoring,
    ),
    (
        "implementation-planning-authoring",
        ["bin/governance", "design", "implementation-planning-authoring", ".", "--json"],
        build_implementation_planning_authoring,
    ),
    (
        "architecture-decisions-authoring",
        ["bin/governance", "design", "architecture-decisions-authoring", ".", "--json"],
        build_architecture_decisions_authoring,
    ),
)


def build_workflow_plan(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    if not state:
        return {
            "ok": False,
            "target": str(root),
            "workflow": "workflow-plan",
            "phase": "",
            "blocked": True,
            "queues": [],
            "commands": [],
            "skill_summary": _empty_skill_summary(),
            "skill_loading_plan": _empty_skill_loading_plan(),
            "errors": ["No governance state found."],
        }

    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    queues: list[dict[str, object]] = []
    commands: list[dict[str, object]] = []
    if phase == PRODUCT_PHASE:
        queue = _product_plan_queue(root)
        queues.append(queue)
        commands.append(queue["command"])
    elif phase == DESIGN_PHASE:
        for queue in _design_queues(root):
            queues.append(queue)
            commands.append(queue["command"])

    return {
        "ok": True,
        "target": str(root),
        "workflow": "workflow-plan",
        "phase": phase,
        "state": state,
        "blocked": any(queue.get("status") != "ready" for queue in queues),
        "queues": queues,
        "commands": commands,
        "skill_summary": _queue_skill_summary(queues),
        "skill_loading_plan": _queue_skill_loading_plan(queues),
        "local_commands": target_local_commands_payload(cwd=str(root)),
        "next_actions": next_actions_payload(state, cwd=str(root)),
        "errors": [],
    }


def _product_plan_queue(root: Path) -> dict[str, object]:
    payload = build_product_plan(root)
    summary = {
        "source_document_count": _list_count(payload.get("source_documents")),
        "available_chapter_count": _list_count(payload.get("available_chapters")),
        "prd_heading_count": _list_count(payload.get("prd_headings")),
        "suggested_mapping_count": _list_count(payload.get("suggested_mappings")),
        "required_decision_count": _list_count(payload.get("required_decisions")),
        "manual_authoring_summary": payload.get("manual_authoring_summary", {}),
        "step_count": _list_count(payload.get("steps")),
        "skill_summary": _payload_skill_summary(payload),
        "skill_loading_plan": _payload_skill_loading_plan(payload),
    }
    return _queue(
        "product-plan",
        PRODUCT_PHASE,
        "product-structuring-plan",
        payload.get("ok") is True,
        _product_summary_blocked(summary),
        _command(
            root,
            "product-plan",
            "Inspect product structuring mappings, manual authoring tasks, and evidence status.",
            ["bin/governance", "product", "plan", ".", "--json"],
        ),
        summary,
        payload.get("errors"),
    )


def _design_queues(root: Path) -> list[dict[str, object]]:
    queues: list[dict[str, object]] = []
    design_plan = build_design_plan(root)
    queues.append(
        _queue(
            "design-plan",
            DESIGN_PHASE,
            "design-track-plan",
            design_plan.get("ok") is True,
            _design_plan_blocked(design_plan),
            _command(
                root,
                "design-plan",
                "Inspect ordered design tracks, required skills, source documents, and blockers.",
                ["bin/governance", "design", "plan", ".", "--json"],
            ),
            _design_plan_summary(design_plan),
            design_plan.get("errors"),
        )
    )

    api_candidates = build_api_candidates(root)
    queues.append(
        _queue(
            "api-candidates",
            DESIGN_PHASE,
            "api-candidate-plan",
            api_candidates.get("ok") is True,
            False,
            _command(
                root,
                "api-candidates",
                "Extract source-backed API endpoint candidates from product acceptance criteria.",
                ["bin/governance", "design", "api-candidates", ".", "--json"],
            ),
            {
                "candidate_count": _list_count(api_candidates.get("candidates")),
                "source_document_count": _list_count(api_candidates.get("source_documents")),
                "skill_summary": _payload_skill_summary(api_candidates),
                "skill_loading_plan": _payload_skill_loading_plan(api_candidates),
            },
            api_candidates.get("errors"),
        )
    )

    for queue_id, argv, builder in DESIGN_AUTHORING_BUILDERS:
        payload = builder(root)
        summary = {
            "authoring_summary": payload.get("authoring_summary", {}),
            "source_document_count": _list_count(payload.get("source_documents")),
            "step_count": _authoring_step_count(payload.get("authoring_tasks")),
            "skill_summary": _payload_skill_summary(payload),
            "skill_loading_plan": _payload_skill_loading_plan(payload),
        }
        queues.append(
            _queue(
                queue_id,
                DESIGN_PHASE,
                "design-authoring-plan",
                payload.get("ok") is True,
                _authoring_summary_blocked(summary),
                _command(root, queue_id, f"Inspect {queue_id} task queue and repair signals.", argv),
                summary,
                payload.get("errors"),
            )
        )
    return queues


def _queue(
    queue_id: str,
    phase: str,
    kind: str,
    ok: bool,
    blocked: bool,
    command: dict[str, object],
    summary: dict[str, object],
    errors: object,
) -> dict[str, object]:
    return {
        "id": queue_id,
        "phase": phase,
        "kind": kind,
        "ok": ok,
        "status": _queue_status(ok, blocked),
        "command": command,
        "summary": summary,
        "errors": list(errors) if isinstance(errors, list) else [],
    }


def _queue_status(ok: bool, blocked: bool) -> str:
    if not ok:
        return "failed"
    if blocked:
        return "blocked"
    return "ready"


def _command(root: Path, command_id: str, description: str, argv: list[str]) -> dict[str, object]:
    return {
        "id": command_id,
        "cwd": str(root),
        "command": " ".join(argv),
        "argv": list(argv),
        "writes_state": False,
        "approval_required": False,
        "description": description,
    }


def _product_summary_blocked(summary: dict[str, object]) -> bool:
    manual_summary = summary.get("manual_authoring_summary")
    if not isinstance(manual_summary, dict):
        return True
    return (
        int(summary.get("required_decision_count", 0)) > 0
        or int(manual_summary.get("non_satisfied_required_evidence_count", 0)) > 0
    )


def _design_plan_summary(payload: dict[str, object]) -> dict[str, object]:
    tracks = payload.get("tracks")
    status_counts: dict[str, int] = {}
    blocker_count = 0
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            status = str(track.get("status", "unknown") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            blockers = track.get("blockers")
            if isinstance(blockers, list):
                blocker_count += len(blockers)
    return {
        "track_count": _list_count(tracks),
        "track_status_counts": dict(sorted(status_counts.items())),
        "blocker_count": blocker_count,
        "step_count": _design_step_count(tracks),
        "skill_summary": _payload_skill_summary(payload),
        "skill_loading_plan": _payload_skill_loading_plan(payload),
    }


def _design_plan_blocked(payload: dict[str, object]) -> bool:
    summary = _design_plan_summary(payload)
    return int(summary.get("blocker_count", 0)) > 0


def _authoring_summary_blocked(summary: dict[str, object]) -> bool:
    authoring_summary = summary.get("authoring_summary")
    if not isinstance(authoring_summary, dict):
        return True
    return int(authoring_summary.get("non_satisfied_required_link_count", 0)) > 0


def _design_step_count(tracks: object) -> int:
    if not isinstance(tracks, list):
        return 0
    count = 0
    for track in tracks:
        if not isinstance(track, dict):
            continue
        steps = track.get("steps")
        if isinstance(steps, list):
            count += len(steps)
    return count


def _authoring_step_count(tasks: object) -> int:
    if not isinstance(tasks, list):
        return 0
    count = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        steps = task.get("steps")
        if isinstance(steps, list):
            count += len(steps)
    return count


def _list_count(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _payload_skill_summary(payload: dict[str, object]) -> dict[str, object]:
    requirements = _payload_skill_requirements(payload)
    return _skill_summary_from_requirements(requirements)


def _queue_skill_summary(queues: list[dict[str, object]]) -> dict[str, object]:
    summaries: list[dict[str, object]] = []
    for queue in queues:
        summary = queue.get("summary")
        if not isinstance(summary, dict):
            continue
        skill_summary = summary.get("skill_summary")
        if isinstance(skill_summary, dict):
            summaries.append(skill_summary)
    return _merge_skill_summaries(summaries)


def _payload_skill_loading_plan(payload: dict[str, object]) -> dict[str, object]:
    plan = payload.get("skill_loading_plan")
    if isinstance(plan, dict):
        return _normalize_skill_loading_plan(plan)

    plans: list[dict[str, object]] = []
    tracks = payload.get("tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            track_plan = track.get("skill_loading_plan")
            if isinstance(track_plan, dict):
                plans.append(track_plan)
    if plans:
        return _merge_skill_loading_plans(plans)

    requirements = _payload_skill_requirements(payload)
    return _skill_loading_plan_from_requirements(requirements)


def _queue_skill_loading_plan(queues: list[dict[str, object]]) -> dict[str, object]:
    plans: list[dict[str, object]] = []
    for queue in queues:
        summary = queue.get("summary")
        if not isinstance(summary, dict):
            continue
        plan = summary.get("skill_loading_plan")
        if isinstance(plan, dict):
            plans.append(plan)
    return _merge_skill_loading_plans(plans)


def _payload_skill_requirements(payload: dict[str, object]) -> list[dict[str, object]]:
    requirements: list[dict[str, object]] = []
    _extend_requirement_objects(requirements, payload.get("skill_requirements"))
    _extend_requirement_objects(requirements, payload.get("authority_skill_requirements"))

    tracks = payload.get("tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            _extend_requirement_objects(requirements, track.get("skill_requirements"))
            _extend_requirement_objects(requirements, track.get("authority_skill_requirements"))
    return requirements


def _extend_requirement_objects(target: list[dict[str, object]], value: object) -> None:
    if not isinstance(value, list):
        return
    for item in value:
        if isinstance(item, dict):
            target.append(item)


def _skill_summary_from_requirements(requirements: list[dict[str, object]]) -> dict[str, object]:
    local_skills: list[str] = []
    authority_skills: list[str] = []
    specialist_skills: list[str] = []
    missing_local_skills: list[str] = []
    authority_missing_policy = ""
    seen_requirements: set[str] = set()

    for requirement in requirements:
        name = requirement.get("name")
        if not isinstance(name, str) or not name or name in seen_requirements:
            continue
        seen_requirements.add(name)
        kind = requirement.get("type")
        if kind == "local-workflow":
            _append_unique(local_skills, name)
            if requirement.get("available_in_workflow_pack") is not True:
                _append_unique(missing_local_skills, name)
        elif kind == "authority-routing":
            _append_unique(authority_skills, name)
            policy = requirement.get("missing_policy")
            if isinstance(policy, str) and policy and not authority_missing_policy:
                authority_missing_policy = policy
        else:
            _append_unique(specialist_skills, name)

    return {
        "local_workflow_skills": local_skills,
        "authority_routing_skills": authority_skills,
        "specialist_routing_skills": specialist_skills,
        "missing_local_workflow_skills": missing_local_skills,
        "local_workflow_skill_count": len(local_skills),
        "authority_routing_skill_count": len(authority_skills),
        "specialist_routing_skill_count": len(specialist_skills),
        "missing_local_workflow_skill_count": len(missing_local_skills),
        "authority_missing_policy": authority_missing_policy,
    }


def _merge_skill_summaries(summaries: list[dict[str, object]]) -> dict[str, object]:
    merged = _empty_skill_summary()
    for summary in summaries:
        _merge_skill_list(merged, "local_workflow_skills", summary.get("local_workflow_skills"))
        _merge_skill_list(merged, "authority_routing_skills", summary.get("authority_routing_skills"))
        _merge_skill_list(merged, "specialist_routing_skills", summary.get("specialist_routing_skills"))
        _merge_skill_list(
            merged,
            "missing_local_workflow_skills",
            summary.get("missing_local_workflow_skills"),
        )
        if not merged["authority_missing_policy"]:
            policy = summary.get("authority_missing_policy")
            if isinstance(policy, str):
                merged["authority_missing_policy"] = policy

    merged["local_workflow_skill_count"] = len(merged["local_workflow_skills"])
    merged["authority_routing_skill_count"] = len(merged["authority_routing_skills"])
    merged["specialist_routing_skill_count"] = len(merged["specialist_routing_skills"])
    merged["missing_local_workflow_skill_count"] = len(merged["missing_local_workflow_skills"])
    return merged


def _skill_loading_plan_from_requirements(requirements: list[dict[str, object]]) -> dict[str, object]:
    steps = [
        _skill_loading_step(sequence, requirement)
        for sequence, requirement in enumerate(requirements, start=1)
    ]
    return _skill_loading_plan_from_steps(steps)


def _skill_loading_step(sequence: int, requirement: dict[str, object]) -> dict[str, object]:
    kind = str(requirement.get("type", ""))
    return {
        "sequence": sequence,
        "name": str(requirement.get("name", "")),
        "type": kind,
        "required": requirement.get("required") is True,
        "action": _skill_loading_action(kind),
        "load_from": str(requirement.get("availability_scope", "")),
        "available_in_workflow_pack": requirement.get("available_in_workflow_pack") is True,
        "path": str(requirement.get("path", "")),
        "missing_policy": str(requirement.get("missing_policy", "")),
    }


def _skill_loading_action(kind: str) -> str:
    if kind == "local-workflow":
        return "load_local_workflow_skill"
    if kind == "authority-routing":
        return "load_authority_routing_skill"
    return "load_specialist_routing_skill"


def _merge_skill_loading_plans(plans: list[dict[str, object]]) -> dict[str, object]:
    steps: list[dict[str, object]] = []
    seen: set[str] = set()
    for plan in plans:
        plan_steps = plan.get("steps")
        if not isinstance(plan_steps, list):
            continue
        for item in plan_steps:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name or name in seen:
                continue
            seen.add(name)
            copied = dict(item)
            copied["sequence"] = len(steps) + 1
            steps.append(copied)
    return _skill_loading_plan_from_steps(steps)


def _normalize_skill_loading_plan(plan: dict[str, object]) -> dict[str, object]:
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return _empty_skill_loading_plan()
    normalized_steps: list[dict[str, object]] = []
    for item in steps:
        if not isinstance(item, dict):
            continue
        copied = dict(item)
        copied["sequence"] = len(normalized_steps) + 1
        normalized_steps.append(copied)
    return _skill_loading_plan_from_steps(normalized_steps)


def _skill_loading_plan_from_steps(steps: list[dict[str, object]]) -> dict[str, object]:
    local_steps = [step for step in steps if step.get("type") == "local-workflow"]
    authority_steps = [step for step in steps if step.get("type") == "authority-routing"]
    missing_local_steps = [
        step
        for step in local_steps
        if step.get("available_in_workflow_pack") is not True
    ]
    return {
        "load_order": "local_workflow_then_authority_routing",
        "stop_condition": "missing_required_local_workflow_skill_or_unavailable_authority_routing_skill",
        "local_workflow_all_available": not missing_local_steps,
        "authority_routing_requires_agent_environment": bool(authority_steps),
        "local_workflow_skill_count": len(local_steps),
        "authority_routing_skill_count": len(authority_steps),
        "missing_local_workflow_skills": [
            step["name"]
            for step in missing_local_steps
            if isinstance(step.get("name"), str)
        ],
        "steps": steps,
    }


def _merge_skill_list(summary: dict[str, object], key: str, value: object) -> None:
    if not isinstance(value, list):
        return
    target = summary.get(key)
    if not isinstance(target, list):  # pragma: no cover - internal invariant
        return
    for item in value:
        if isinstance(item, str):
            _append_unique(target, item)


def _empty_skill_summary() -> dict[str, object]:
    return {
        "local_workflow_skills": [],
        "authority_routing_skills": [],
        "specialist_routing_skills": [],
        "missing_local_workflow_skills": [],
        "local_workflow_skill_count": 0,
        "authority_routing_skill_count": 0,
        "specialist_routing_skill_count": 0,
        "missing_local_workflow_skill_count": 0,
        "authority_missing_policy": "",
    }


def _empty_skill_loading_plan() -> dict[str, object]:
    return _skill_loading_plan_from_steps([])


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
