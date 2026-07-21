from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

try:
    from .api_review_evidence import (
        api_review_required_evidence_paths,
        build_api_review_evidence_inventory,
    )
    from .authority_skills import build_authority_skill_inventory
    from .bootstrap_tree import WORKFLOW_PACK_SNAPSHOT_ROOT, target_local_commands_payload
    from .design_reviews import DESIGN_REVIEW_TRACK_SPECS
    from .design_plan import (
        build_api_authoring,
        build_api_candidates,
        build_architecture_authoring,
        build_architecture_decisions_authoring,
        build_backend_authoring,
        build_data_model_authoring,
        build_design_plan,
        build_frontend_authoring,
        build_implementation_planning_authoring,
        build_test_strategy_authoring,
        build_ui_interaction_authoring,
    )
    from .implementation_plan import build_implementation_plan
    from .project_environment import build_project_environment_plan
    from .product_structure import build_product_plan
    from .reliability_review_evidence import (
        build_reliability_review_evidence_inventory,
        reliability_review_required_evidence_paths,
    )
    from .migration_review_evidence import (
        build_migration_review_evidence_inventory,
        migration_review_required_evidence_paths,
    )
    from .state import load_state
    from .workflow_actions import next_actions_payload
    from .threat_review_evidence import (
        build_threat_review_evidence_inventory,
        threat_review_required_evidence_paths,
    )
except ImportError:  # pragma: no cover - direct script execution
    from api_review_evidence import (
        api_review_required_evidence_paths,
        build_api_review_evidence_inventory,
    )
    from authority_skills import build_authority_skill_inventory
    from bootstrap_tree import WORKFLOW_PACK_SNAPSHOT_ROOT, target_local_commands_payload
    from design_reviews import DESIGN_REVIEW_TRACK_SPECS
    from design_plan import (
        build_api_authoring,
        build_api_candidates,
        build_architecture_authoring,
        build_architecture_decisions_authoring,
        build_backend_authoring,
        build_data_model_authoring,
        build_design_plan,
        build_frontend_authoring,
        build_implementation_planning_authoring,
        build_test_strategy_authoring,
        build_ui_interaction_authoring,
    )
    from implementation_plan import build_implementation_plan
    from project_environment import build_project_environment_plan
    from product_structure import build_product_plan
    from reliability_review_evidence import (
        build_reliability_review_evidence_inventory,
        reliability_review_required_evidence_paths,
    )
    from migration_review_evidence import (
        build_migration_review_evidence_inventory,
        migration_review_required_evidence_paths,
    )
    from state import load_state
    from workflow_actions import next_actions_payload
    from threat_review_evidence import (
        build_threat_review_evidence_inventory,
        threat_review_required_evidence_paths,
    )


PRODUCT_PHASE = "product-structuring"
DESIGN_PHASE = "design-derivation"
IMPLEMENTATION_PHASE = "implementation"

DESIGN_AUTHORING_BUILDERS: tuple[tuple[str, list[str], Callable[[Path], dict[str, object]]], ...] = (
    (
        "architecture-authoring",
        ["bin/governance", "design", "architecture-authoring", ".", "--json"],
        build_architecture_authoring,
    ),
    ("api-authoring", ["bin/governance", "design", "api-authoring", ".", "--json"], build_api_authoring),
    ("backend-authoring", ["bin/governance", "design", "backend-authoring", ".", "--json"], build_backend_authoring),
    (
        "data-model-authoring",
        ["bin/governance", "design", "data-model-authoring", ".", "--json"],
        build_data_model_authoring,
    ),
    (
        "ui-interaction-authoring",
        ["bin/governance", "design", "ui-interaction-authoring", ".", "--json"],
        build_ui_interaction_authoring,
    ),
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
DESIGN_WORK_PACKAGE_BUILDERS: dict[str, tuple[str, Callable[[Path], dict[str, object]]]] = {
    "architecture": ("architecture-authoring", build_architecture_authoring),
    "ui-interaction": ("ui-interaction-authoring", build_ui_interaction_authoring),
    "api-contracts": ("api-authoring", build_api_authoring),
    "backend-modules": ("backend-authoring", build_backend_authoring),
    "data-model": ("data-model-authoring", build_data_model_authoring),
    "frontend-modules": ("frontend-authoring", build_frontend_authoring),
    "test-strategy": ("test-strategy-authoring", build_test_strategy_authoring),
    "implementation-planning": ("implementation-planning-authoring", build_implementation_planning_authoring),
    "architecture-decisions": ("architecture-decisions-authoring", build_architecture_decisions_authoring),
}


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
            "active_work": {},
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
    elif phase == IMPLEMENTATION_PHASE:
        queue = _implementation_plan_queue(root)
        queues.append(queue)
        commands.append(queue["command"])

    return {
        "ok": True,
        "target": str(root),
        "workflow": "workflow-plan",
        "phase": phase,
        "state": state,
        "blocked": any(queue.get("status") not in {"ready", "complete"} for queue in queues),
        "queues": queues,
        "commands": commands,
        "active_work": _workflow_active_work(queues),
        "skill_summary": _queue_skill_summary(queues),
        "skill_loading_plan": _queue_skill_loading_plan(queues),
        "local_commands": target_local_commands_payload(cwd=str(root)),
        "next_actions": next_actions_payload(state, cwd=str(root)),
        "errors": [],
    }


def build_work_package(
    root: Path,
    *,
    skill_roots: list[Path] | None = None,
) -> dict[str, object]:
    root = root.resolve()
    explicit_skill_roots = list(skill_roots or [])
    resolved_skill_roots = [root / ".agents/skills", root / ".codex/skills", *explicit_skill_roots]
    state = load_state(root)
    if not state:
        errors = ["No governance state found."]
        return {
            "ok": False,
            "schema_version": 1,
            "target": str(root),
            "workflow": "workflow-work-package",
            "phase": "",
            "package_available": False,
            "status": "failed",
            "blocked": True,
            "can_start": False,
            "stop_before_work": True,
            "stop_reasons": errors,
            "work_package": {},
            "skill_readiness": _empty_work_package_skill_readiness(),
            "next_action": {},
            "refresh_command": _work_package_refresh_command(root, explicit_skill_roots),
            "local_commands": [],
            "next_actions": [],
            "errors": errors,
        }

    phase = str(state.get("phase", ""))
    package: dict[str, object] = {}
    package_errors: list[str] = []
    no_package_status = "phase_action_required"
    if phase == PRODUCT_PHASE:
        package, package_errors, no_package_status = _product_work_package(root)
    elif phase == DESIGN_PHASE:
        package, package_errors, no_package_status = _design_work_package(root)
    elif phase == IMPLEMENTATION_PHASE:
        package, package_errors, no_package_status = _implementation_work_package(root)

    package_available = bool(package)
    status = str(package.get("status", "")) if package_available else no_package_status
    skill_readiness = _work_package_skill_readiness(
        package.get("skill_requirements"),
        skill_roots=resolved_skill_roots,
    )
    can_start = package_available and skill_readiness["ready"] is True and status != "complete"
    stop_reasons = _work_package_stop_reasons(package_available, status, skill_readiness, package_errors)
    next_actions = next_actions_payload(state, cwd=str(root))
    next_action = _work_package_next_action(
        root,
        package,
        skill_readiness,
        list(next_actions) if isinstance(next_actions, list) else [],
    )
    errors = package_errors
    return {
        "ok": not errors,
        "schema_version": 1,
        "target": str(root),
        "workflow": "workflow-work-package",
        "phase": phase,
        "package_available": package_available,
        "status": status,
        "blocked": status not in {"ready", "in_progress", "complete"} or skill_readiness["ready"] is not True,
        "can_start": can_start,
        "stop_before_work": bool(stop_reasons),
        "stop_reasons": stop_reasons,
        "work_package": package,
        "skill_readiness": skill_readiness,
        "next_action": next_action,
        "refresh_command": _work_package_refresh_command(root, explicit_skill_roots),
        "local_commands": target_local_commands_payload(cwd=str(root)),
        "next_actions": next_actions,
        "errors": errors,
    }


def _product_work_package(root: Path) -> tuple[dict[str, object], list[str], str]:
    payload = build_product_plan(root)
    if payload.get("ok") is not True:
        return {}, _string_list(payload.get("errors")), "failed"
    tasks = _dict_items(payload.get("manual_authoring_tasks"))
    active_work = _dict_value(payload.get("active_work"))
    if active_work.get("status") in {"ready", "complete"} and not active_work.get("task_id"):
        return {}, [], "phase_action_required"
    task = _selected_work_item(tasks, str(active_work.get("task_id", "")))
    if not task:
        return {}, [], "phase_action_required"
    primary_path = str(task.get("path", ""))
    source_documents = _string_list(payload.get("source_documents"))
    references = _target_read_paths(root, ["references/product-requirements-checklist.md"])
    required_evidence = _dict_items(task.get("required_evidence"))
    blockers = [item for item in required_evidence if item.get("status") != "satisfied"]
    return {
        "package_id": _package_id(PRODUCT_PHASE, "product-plan", str(task.get("task_id", ""))),
        "kind": "product-authoring",
        "phase": PRODUCT_PHASE,
        "queue_id": "product-plan",
        "work_id": str(task.get("task_id", "")),
        "chapter": str(task.get("chapter", "")),
        "status": str(active_work.get("status", task.get("status", "decision_required"))),
        "title": str(task.get("title", "")),
        "objective": str(task.get("decision", "")),
        "decision_policy": str(task.get("decision_policy", "do_not_guess_product_meaning")),
        "source_documents": source_documents,
        "references": references,
        "read_order": _dedupe_strings([*source_documents, *references]),
        "write_scope": {
            "mode": "declared_product_document_and_traceability",
            "primary_paths": [primary_path] if primary_path else [],
            "supporting_paths": [
                "docs/product/README.md",
                "docs/product/core/product-meta.md",
                "docs/product/core/chapter-dispositions.json",
                "docs/unresolved.md",
                "docs/glossary.md",
            ],
            "requires_codebase_mapping": False,
        },
        "required_sections": _string_list(task.get("required_sections")),
        "required_links": _dict_items(task.get("required_links")),
        "required_evidence": required_evidence,
        "open_decisions": _string_list(task.get("open_decisions")),
        "blockers": blockers,
        "repair_actions": _dict_items(task.get("evidence_repair_actions")),
        "action_options": _string_list(task.get("action_options")),
        "disposition": _dict_value(task.get("disposition")),
        "skill_requirements": _dict_items(task.get("skill_requirements")),
        "authority_skill_requirements": _dict_items(task.get("authority_skill_requirements")),
        "skill_loading_plan": _dict_value(task.get("skill_loading_plan")),
        "execution": _dict_value(task.get("execution")),
        "steps": _dict_items(task.get("steps")),
        "verify_command": _dict_value(active_work.get("verify_command")),
        "refresh_command": _dict_value(active_work.get("refresh_command")),
    }, [], ""


def _design_work_package(root: Path) -> tuple[dict[str, object], list[str], str]:
    design_plan = build_design_plan(root)
    if design_plan.get("ok") is not True:
        return {}, _string_list(design_plan.get("errors")), "failed"
    tracks = _dict_items(design_plan.get("tracks"))
    queues: list[tuple[dict[str, object], str, dict[str, object]]] = []
    for track in tracks:
        track_id = str(track.get("id", ""))
        builder_entry = DESIGN_WORK_PACKAGE_BUILDERS.get(track_id)
        if builder_entry is None:
            return {}, [f"No design authoring builder registered for track {track_id or '<missing>'}."], "failed"
        queue_id, builder = builder_entry
        authoring_payload = builder(root)
        if authoring_payload.get("ok") is not True:
            return {}, _string_list(authoring_payload.get("errors")), "failed"
        queues.append((track, queue_id, authoring_payload))

    selected: tuple[dict[str, object], str, dict[str, object], dict[str, object], str] | None = None
    for stage in (
        "authoring",
        "integration",
        "threat-review",
        "machine-review",
        "reliability-review",
        "migration-review",
        "review",
    ):
        for track, queue_id, authoring_payload in queues:
            authoring_tasks = _dict_items(authoring_payload.get("authoring_tasks"))
            task = _first_design_task_for_stage(
                root,
                str(track.get("id", "")),
                authoring_tasks,
                stage,
            )
            if (
                not task
                and stage == "review"
                and authoring_tasks
                and any(
                    blocker.get("code") == "design_review_orphan"
                    for blocker in _dict_items(track.get("blockers"))
                )
            ):
                task = authoring_tasks[0]
            if task:
                selected = (track, queue_id, authoring_payload, task, stage)
                break
        if selected is not None:
            break
    if selected is None:
        return _project_runtime_work_package(root)

    track, queue_id, authoring_payload, task, stage = selected
    track_id = str(track.get("id", ""))
    active_work = _dict_value(authoring_payload.get("active_work"))
    work_id = str(task.get("task_id", track_id))
    source_documents = _string_list(authoring_payload.get("source_documents"))
    references = _target_read_paths(
        root,
        [
            *_string_list(track.get("references")),
            "references/design-review-checklist.md",
            *(
                [
                    "references/security-design-checklist.md",
                    "templates/docs/architecture/threat-model/scope.json",
                    "templates/docs/architecture/threat-model/mitigations.json",
                ]
                if str(track.get("id", "")) == "architecture"
                else []
            ),
        ],
    )
    primary_paths = [
        str(item.get("path", ""))
        for item in _dict_items(task.get("documents"))
        if str(item.get("path", "")) and not Path(str(item.get("path", ""))).name.startswith("_")
    ]
    document_blockers = _dict_items(task.get("document_blockers"))
    link_blockers = [
        item
        for item in _dict_items(task.get("required_links"))
        if item.get("status") != "satisfied"
    ]
    review_blockers = [
        blocker
        for blocker in _dict_items(track.get("blockers"))
        if str(blocker.get("code", "")).startswith("design_review_")
    ]
    api_machine_review = (
        build_api_review_evidence_inventory(root)
        if stage == "machine-review"
        else {}
    )
    architecture_threat_review = (
        build_threat_review_evidence_inventory(root)
        if stage == "threat-review"
        else {}
    )
    backend_reliability_review = (
        build_reliability_review_evidence_inventory(root)
        if stage == "reliability-review"
        else {}
    )
    data_model_migration_review = (
        build_migration_review_evidence_inventory(root)
        if stage == "migration-review"
        else {}
    )
    machine_review_blockers = (
        _threat_review_blockers(architecture_threat_review)
        if stage == "threat-review"
        else _reliability_review_blockers(backend_reliability_review)
        if stage == "reliability-review"
        else _migration_review_blockers(data_model_migration_review)
        if stage == "migration-review"
        else _api_machine_review_blockers(api_machine_review)
    )
    blockers = (
        document_blockers
        if stage == "authoring"
        else link_blockers
        if stage == "integration"
        else machine_review_blockers
        if stage in {"threat-review", "machine-review", "reliability-review", "migration-review"}
        else review_blockers
    )
    repair_actions = (
        _dict_items(task.get("document_repair_actions"))
        if stage == "authoring"
        else _dict_items(task.get("link_repair_actions"))
        if stage == "integration"
        else []
    )
    status_by_stage = {
        "authoring": "authoring_required",
        "integration": "integration_required",
        "machine-review": "machine_review_required",
        "threat-review": "threat_review_required",
        "reliability-review": "reliability_review_required",
        "migration-review": "migration_review_required",
        "review": "review_required",
    }
    return {
        "package_id": _package_id(DESIGN_PHASE, queue_id, work_id),
        "kind": "design-authoring",
        "phase": DESIGN_PHASE,
        "queue_id": queue_id,
        "track_id": track_id,
        "work_stage": stage,
        "track_sequence": track.get("sequence", 0),
        "work_id": work_id,
        "status": status_by_stage[stage],
        "title": str(track.get("title", task.get("title", ""))),
        "objective": str(track.get("purpose", "")),
        "procedure": str(track.get("procedure", "")),
        "decision_policy": str(authoring_payload.get("decision_policy", "")),
        "acceptance_id": str(task.get("acceptance_id", "")),
        "source_documents": source_documents,
        "references": references,
        "read_order": _dedupe_strings([*source_documents, *references]),
        "write_scope": {
            "mode": "declared_design_track_documents",
            "primary_paths": primary_paths,
            "supporting_paths": _dedupe_strings(
                [
                    "docs/unresolved.md",
                    "docs/decisions/design-reviews.json",
                    *(threat_review_required_evidence_paths() if track_id == "architecture" else []),
                    *(api_review_required_evidence_paths() if track_id == "api-contracts" else []),
                    *(
                        reliability_review_required_evidence_paths(root)
                        if track_id == "backend-modules"
                        else []
                    ),
                    *(
                        migration_review_required_evidence_paths(root)
                        if track_id == "data-model"
                        else []
                    ),
                ]
            ),
            "requires_codebase_mapping": False,
        },
        "documents": _dict_items(task.get("documents")),
        "document_blockers": document_blockers,
        "document_repair_actions": _dict_items(task.get("document_repair_actions")),
        "required_links": _dict_items(task.get("required_links")),
        "required_decisions": _string_list(task.get("required_decisions")),
        "open_decisions": _string_list(task.get("open_decisions")),
        "blockers": blockers,
        "repair_actions": repair_actions,
        "review_status": str(task.get("review_status", "missing")),
        "api_machine_review": api_machine_review,
        "architecture_threat_review": architecture_threat_review,
        "backend_reliability_review": backend_reliability_review,
        "data_model_migration_review": data_model_migration_review,
        "design_review": _dict_value(task.get("design_review")),
        "required_authority_skill": str(
            _dict_value(task.get("execution")).get("primary_specialist_skill", "")
        ),
        "review_result_options": _string_list(
            DESIGN_REVIEW_TRACK_SPECS.get(track_id, {}).get("results")
        ),
        "skill_requirements": _dict_items(track.get("skill_requirements")),
        "authority_skill_requirements": _dict_items(track.get("authority_skill_requirements")),
        "skill_loading_plan": _dict_value(track.get("skill_loading_plan")),
        "execution": _dict_value(task.get("execution")),
        "steps": _dict_items(task.get("steps")) or _dict_items(track.get("steps")),
        "verify_command": _dict_value(active_work.get("verify_command")),
        "refresh_command": _dict_value(active_work.get("refresh_command")),
    }, [], ""


def _project_runtime_work_package(root: Path) -> tuple[dict[str, object], list[str], str]:
    payload = build_project_environment_plan(root)
    coverage_status = str(payload.get("coverage_status", ""))
    if not coverage_status:
        return {}, _string_list(payload.get("errors")), "failed"
    if payload.get("configuration_complete") is True:
        return {}, [], "complete"

    references = _target_read_paths(
        root,
        [
            "references/project-environment-contract.md",
            "references/runtime-strategy.md",
            "references/community-practices.md",
        ],
    )
    read_order = _dedupe_strings(
        [
            *_string_list(payload.get("read_order")),
            *references,
        ]
    )
    return {
        "package_id": _package_id(DESIGN_PHASE, "project-runtime", "project-runtime"),
        "kind": "project-runtime-configuration",
        "phase": DESIGN_PHASE,
        "queue_id": "project-runtime",
        "work_id": "project-runtime",
        "status": coverage_status,
        "title": "Project runtime configuration",
        "objective": "Cover every project-runtime command with a reviewed and ready executable contract.",
        "decision_policy": str(payload.get("decision_policy", "")),
        "references": references,
        "read_order": read_order,
        "write_scope": {
            "mode": "reviewed_project_runtime_contract",
            "primary_paths": [
                "docs/agent-workflow/project-environment.json",
                "docs/agent-workflow/command-contract.md",
            ],
            "supporting_paths": [
                "docs/architecture",
                "docs/decisions",
                ".governance/project-environment-repairs.json",
            ],
            "requires_codebase_mapping": False,
        },
        "command_contract_path": str(payload.get("command_contract_path", "")),
        "command_contract_errors": _string_list(payload.get("command_contract_errors")),
        "required_commands": _dict_items(payload.get("required_commands")),
        "command_coverage": _dict_items(payload.get("command_coverage")),
        "missing_command_registrations": _dict_items(payload.get("missing_command_registrations")),
        "tool_readiness": _dict_items(payload.get("tool_readiness")),
        "unready_tool_ids": _string_list(payload.get("unready_tool_ids")),
        "unused_tool_ids": _string_list(payload.get("unused_tool_ids")),
        "repair_evidence_summary": _dict_value(payload.get("repair_evidence_summary")),
        "repair_routes": _dict_items(payload.get("repair_routes")),
        "register_command": _dict_value(payload.get("register_command")),
        "skill_requirements": _dict_items(payload.get("skill_requirements")),
        "specialist_skills": _string_list(payload.get("specialist_skills")),
        "steps": [
            {
                "id": "inspect-project-runtime-contracts",
                "action": "Read the command contract, reviewed stack evidence, and project environment inventory.",
            },
            {
                "id": "register-or-repair-project-runtime",
                "action": "Preview and apply only source-backed runtime registration or approved repair actions.",
            },
            {
                "id": "verify-project-runtime",
                "action": "Refresh project-env plan and governance verification until configuration_complete is true.",
            },
        ],
        "verify_command": {
            "argv": ["bin/governance", "verify", ".", "--check", "--json"],
            "cwd": ".",
            "writes_state": False,
            "approval_required": False,
        },
        "refresh_command": {
            "argv": ["bin/governance", "project-env", "plan", ".", "--json"],
            "cwd": ".",
            "writes_state": False,
            "approval_required": False,
        },
    }, [], ""


def _first_design_task_for_stage(
    root: Path,
    track_id: str,
    tasks: list[dict[str, object]],
    stage: str,
) -> dict[str, object]:
    for task in tasks:
        if stage == "authoring" and _dict_items(task.get("document_blockers")):
            return task
        if stage == "integration" and any(
            item.get("status") != "satisfied"
            for item in _dict_items(task.get("required_links"))
        ):
            return task
        if (
            stage == "threat-review"
            and track_id == "architecture"
            and build_threat_review_evidence_inventory(root).get("ok") is not True
        ):
            return task
        if (
            stage == "machine-review"
            and track_id == "api-contracts"
            and build_api_review_evidence_inventory(root).get("ok") is not True
        ):
            return task
        if (
            stage == "reliability-review"
            and track_id == "backend-modules"
            and build_reliability_review_evidence_inventory(root).get("ok") is not True
        ):
            return task
        if (
            stage == "migration-review"
            and track_id == "data-model"
            and build_migration_review_evidence_inventory(root).get("ok") is not True
        ):
            return task
        if stage == "review" and _string_list(task.get("open_decisions")):
            return task
    return {}


def _api_machine_review_blockers(inventory: dict[str, object]) -> list[dict[str, object]]:
    if not inventory or inventory.get("ok") is True:
        return []
    status = str(inventory.get("status", "missing"))
    details = _string_list(inventory.get("errors"))
    if status == "stale":
        details = _string_list(inventory.get("stale_reasons"))
    return [
        {
            "kind": "api_machine_review",
            "target": str(inventory.get("path", "docs/api/reviews/review-evidence.json")),
            "status": status,
            "details": details,
        }
    ]


def _threat_review_blockers(inventory: dict[str, object]) -> list[dict[str, object]]:
    if not inventory or inventory.get("ok") is True:
        return []
    status = str(inventory.get("status", "missing"))
    details = _string_list(inventory.get("errors"))
    if status == "stale":
        details = _string_list(inventory.get("stale_reasons"))
    return [
        {
            "kind": "architecture_threat_review",
            "target": str(
                inventory.get(
                    "path",
                    "docs/architecture/threat-model/review-evidence.json",
                )
            ),
            "status": status,
            "details": details,
        }
    ]


def _reliability_review_blockers(inventory: dict[str, object]) -> list[dict[str, object]]:
    if not inventory or inventory.get("ok") is True:
        return []
    status = str(inventory.get("status", "missing"))
    details = _string_list(inventory.get("errors"))
    if status == "stale":
        details = _string_list(inventory.get("stale_reasons"))
    return [
        {
            "kind": "backend_reliability_review",
            "target": str(
                inventory.get(
                    "path",
                    "docs/backend/reliability/review-evidence.json",
                )
            ),
            "status": status,
            "details": details,
        }
    ]


def _migration_review_blockers(inventory: dict[str, object]) -> list[dict[str, object]]:
    if not inventory or inventory.get("ok") is True:
        return []
    status = str(inventory.get("status", "missing"))
    details = _string_list(inventory.get("errors"))
    if status == "stale":
        details = _string_list(inventory.get("stale_reasons"))
    return [
        {
            "kind": "data_model_migration_review",
            "target": str(inventory.get("path", "docs/backend/migrations/review-evidence.json")),
            "status": status,
            "details": details,
        }
    ]


def _implementation_work_package(root: Path) -> tuple[dict[str, object], list[str], str]:
    payload = build_implementation_plan(root)
    if payload.get("ok") is not True:
        return {}, _string_list(payload.get("errors")), "failed"
    summary = _dict_value(payload.get("implementation_summary"))
    if summary.get("execution_complete") is True:
        return {}, [], "complete"
    tasks = _dict_items(payload.get("tasks"))
    active_work = _dict_value(payload.get("active_work"))
    task = _selected_work_item(tasks, str(active_work.get("task_id", "")))
    if not task:
        return {}, ["Implementation plan did not expose a selected task."], "failed"
    blockers = _dict_items(task.get("blockers"))
    next_repair_action = _dict_value(active_work.get("next_repair_action"))
    repair_actions = [next_repair_action] if next_repair_action else []
    references = _target_read_paths(
        root,
        [
            "references/implementation-readiness-checklist.md",
            "references/implementation-execution-checklist.md",
        ],
    )
    source_documents = _string_list(task.get("read_order"))
    read_order = _dedupe_strings([*source_documents, *references])
    package = {
        "package_id": _package_id(IMPLEMENTATION_PHASE, "implementation-plan", str(task.get("task_id", ""))),
        "kind": "implementation-task",
        "phase": IMPLEMENTATION_PHASE,
        "queue_id": "implementation-plan",
        "work_id": str(task.get("task_id", "")),
        "status": str(active_work.get("status", task.get("normalized_status", "blocked"))),
        "title": str(task.get("title", "")),
        "objective": "Implement exactly one selected task and preserve passing local verification evidence.",
        "decision_policy": str(payload.get("decision_policy", "execute_exactly_one_ready_task")),
        "acceptance_id": str(task.get("acceptance_id", "")),
        "risk_tags": _string_list(task.get("risk_tags")),
        "source_documents": source_documents,
        "references": references,
        "read_order": read_order,
        "write_scope": {
            "mode": "selected_task_code_surface_after_repository_mapping",
            "primary_paths": [],
            "supporting_paths": [
                "docs/development/01-roadmap.md",
                "docs/development/02-task-board.md",
                "docs/development/03-verification-log.md",
                "docs/agent-workflow/task-handoff.md",
            ],
            "requires_codebase_mapping": True,
        },
        "source_references": _dict_value(task.get("source_references")),
        "verification_command_names": _string_list(task.get("verification_command_names")),
        "verification_commands": _dict_items(task.get("verification_commands")),
        "verification_command_summary": _dict_value(task.get("verification_command_summary")),
        "open_decisions": _string_list(task.get("open_decisions")),
        "blockers": blockers,
        "repair_actions": repair_actions,
        "skill_requirements": _dict_items(task.get("skill_requirements")),
        "authority_skill_requirements": _dict_items(task.get("authority_skill_requirements")),
        "skill_loading_plan": _dict_value(task.get("skill_loading_plan")),
        "execution": _dict_value(task.get("execution")),
        "steps": _dict_items(task.get("steps")),
        "gate_command": _dict_value(active_work.get("gate_command")),
        "start_command": _dict_value(active_work.get("start_command")),
        "verify_command": _dict_value(active_work.get("verify_command")),
        "closeout_command": _dict_value(active_work.get("closeout_command")),
        "refresh_command": _dict_value(active_work.get("refresh_command")),
    }
    package["execution_contract"] = _implementation_execution_contract(root, package)
    return package, [], ""


def _implementation_execution_contract(root: Path, package: dict[str, object]) -> dict[str, object]:
    task_id = str(package.get("work_id", ""))
    start_apply = _command(
        root,
        "apply-implementation-start",
        "Claim the selected task after the start preflight reports start_ready:true.",
        [
            "bin/governance",
            "implementation",
            "start",
            ".",
            "--task",
            task_id,
            "--apply",
            "--json",
        ],
    )
    start_apply["writes_state"] = True
    closeout_apply = _command(
        root,
        "apply-implementation-closeout",
        "Synchronize Done status after closeout preflight reports closeout_ready:true.",
        [
            "bin/governance",
            "implementation",
            "closeout",
            ".",
            "--task",
            task_id,
            "--apply",
            "--json",
        ],
    )
    closeout_apply["writes_state"] = True
    return {
        "schema_version": 1,
        "task_id": task_id,
        "decision_policy": "claim_then_execute_all_required_verification_commands_then_closeout",
        "start": {
            "preflight_command": _dict_value(package.get("start_command")),
            "apply_command": start_apply,
            "apply_condition": "start_ready:true and status_update_plan.can_auto_apply:true",
        },
        "verification_commands": _dict_items(package.get("verification_commands")),
        "verification_policy": "run_each_preflight_then_execute_only_when_verification_ready_true",
        "closeout": {
            "preflight_command": _dict_value(package.get("closeout_command")),
            "apply_command": closeout_apply,
            "apply_condition": "closeout_ready:true and status_update_plan.can_auto_apply:true",
        },
        "refresh_command": _dict_value(package.get("refresh_command")),
        "success_condition": "all registered task commands pass and implementation closeout is applied",
    }


def _work_package_skill_readiness(
    requirements: object,
    *,
    skill_roots: list[Path],
) -> dict[str, object]:
    requirement_list = _dict_items(requirements)
    if not requirement_list:
        return _empty_work_package_skill_readiness()
    needs_authority_inventory = any(
        requirement.get("type") != "local-workflow"
        for requirement in requirement_list
    )
    inventory = (
        build_authority_skill_inventory(skill_roots=skill_roots, strict=False)
        if needs_authority_inventory
        else {}
    )
    inventory_by_name = {
        str(skill.get("name", "")): skill
        for skill in _dict_items(inventory.get("skills"))
    }
    resolved: list[dict[str, object]] = []
    missing_local: list[str] = []
    missing_authority: list[str] = []
    for requirement in requirement_list:
        name = str(requirement.get("name", ""))
        requirement_type = str(requirement.get("type", ""))
        item = dict(requirement)
        if requirement_type == "local-workflow":
            available = requirement.get("available_in_workflow_pack") is True
            item["available"] = available
            item["resolved_path"] = str(requirement.get("path", "")) if available else ""
            if not available and name:
                missing_local.append(name)
        else:
            installed = inventory_by_name.get(name, {})
            available = installed.get("available_in_agent_environment") is True
            item["available"] = available
            item["available_in_agent_environment"] = available
            item["resolved_path"] = str(installed.get("skill_path", "")) if available else ""
            if not available and name:
                missing_authority.append(name)
        resolved.append(item)
    missing_local = _dedupe_strings(missing_local)
    missing_authority = _dedupe_strings(missing_authority)
    return {
        "ready": not missing_local and not missing_authority,
        "required_skill_count": len(resolved),
        "available_skill_count": sum(1 for item in resolved if item.get("available") is True),
        "missing_local_workflow_skills": missing_local,
        "missing_authority_routing_skills": missing_authority,
        "authority_skill_roots": _string_list(inventory.get("available_skill_roots")),
        "resolved_requirements": resolved,
        "missing_policy": "load_from_agent_environment_or_stop_before_guessing",
    }


def _empty_work_package_skill_readiness() -> dict[str, object]:
    return {
        "ready": True,
        "required_skill_count": 0,
        "available_skill_count": 0,
        "missing_local_workflow_skills": [],
        "missing_authority_routing_skills": [],
        "authority_skill_roots": [],
        "resolved_requirements": [],
        "missing_policy": "load_from_agent_environment_or_stop_before_guessing",
    }


def _work_package_next_action(
    root: Path,
    package: dict[str, object],
    skill_readiness: dict[str, object],
    workflow_next_actions: list[object],
) -> dict[str, object]:
    if not package:
        return next((dict(action) for action in workflow_next_actions if isinstance(action, dict)), {})
    if package.get("kind") == "project-runtime-configuration":
        status = str(package.get("status", ""))
        if status == "command_contract_invalid":
            return {
                "kind": "repair-command-contract",
                "path": str(package.get("command_contract_path", "")),
                "errors": _string_list(package.get("command_contract_errors")),
                "decision_policy": "repair_deterministic_contract_errors_before_runtime_registration",
            }
        if status == "repair_evidence_pending":
            return {
                "kind": "investigate-pending-project-runtime-repair",
                "path": ".governance/project-environment-repairs.json",
                "repair_evidence_summary": _dict_value(package.get("repair_evidence_summary")),
                "decision_policy": "pending_repair_evidence_never_implies_success",
            }
    missing_local = _string_list(skill_readiness.get("missing_local_workflow_skills"))
    if missing_local:
        return {
            "kind": "repair-workflow-pack",
            "skills": missing_local,
            "command": _command(
                root,
                "runtime-refresh-check",
                "Preview target-local workflow runtime repair before loading missing local skills.",
                ["bin/governance", "runtime", "refresh", ".", "--check", "--json"],
            ),
        }
    missing_authority = _string_list(skill_readiness.get("missing_authority_routing_skills"))
    if missing_authority:
        return {
            "kind": "load-authority-skills",
            "skills": missing_authority,
            "approval_required": True,
            "missing_policy": "load_from_agent_environment_or_stop_before_guessing",
        }
    if package.get("kind") == "project-runtime-configuration":
        missing_registrations = _dict_items(package.get("missing_command_registrations"))
        if missing_registrations:
            return {
                "kind": "register-project-runtime-tool",
                "missing_command_registrations": missing_registrations,
                "register_command": _dict_value(package.get("register_command")),
                "decision_policy": str(package.get("decision_policy", "")),
                "success_condition": "registration is reviewed and every affected command reports ready coverage",
            }
        unready_tool_ids = _string_list(package.get("unready_tool_ids"))
        if unready_tool_ids:
            tool_id = unready_tool_ids[0]
            return {
                "kind": "preflight-project-runtime-repair",
                "tool_id": tool_id,
                "command": _command(
                    root,
                    f"project-runtime-repair-{tool_id}-check",
                    "Preview the registered project runtime repair without applying it.",
                    [
                        "bin/governance",
                        "project-env",
                        "repair",
                        ".",
                        "--tool-id",
                        tool_id,
                        "--check",
                        "--json",
                    ],
                ),
            }
        blocked_commands = [
            item
            for item in _dict_items(package.get("command_coverage"))
            if item.get("ready") is not True
        ]
        if blocked_commands:
            return {
                "kind": "repair-project-runtime-command",
                "command_coverage": blocked_commands[0],
                "decision_policy": "repair_declared_command_path_without_inferring_a_tool_or_install_command",
            }
    if package.get("kind") == "product-authoring" and not _dict_value(package.get("disposition")):
        chapter = str(package.get("chapter", ""))
        return {
            "kind": "decide-product-chapter",
            "chapter": chapter,
            "decision_policy": str(package.get("decision_policy", "")),
            "options": ["author-required", "omit-unsupported"],
            "command_contract": {
                "cwd": str(root),
                "argv_prefix": [
                    "bin/governance",
                    "product",
                    "disposition",
                    ".",
                    "--chapter",
                    chapter,
                ],
                "required_arguments": ["--decision", "--reason", "--reviewed"],
                "preflight_argument": "--check",
                "writes_state": True,
                "approval_required": False,
            },
        }
    if package.get("kind") == "design-authoring" and package.get("work_stage") == "authoring":
        paths = [
            str(item.get("target", ""))
            for item in _dict_items(package.get("document_blockers"))
            if str(item.get("target", ""))
        ]
        return {
            "kind": "author-design-documents",
            "track": str(package.get("track_id", "")),
            "work_id": str(package.get("work_id", "")),
            "paths": paths,
            "decision_policy": str(package.get("decision_policy", "")),
            "required_decisions": _string_list(package.get("required_decisions")),
            "authority_skill": str(package.get("required_authority_skill", "")),
            "success_condition": "declared design documents become authored before integration review",
        }
    if package.get("kind") == "design-authoring" and package.get("work_stage") == "threat-review":
        scope_template = _target_read_paths(
            root,
            ["templates/docs/architecture/threat-model/scope.json"],
        )[0]
        mitigations_template = _target_read_paths(
            root,
            ["templates/docs/architecture/threat-model/mitigations.json"],
        )[0]
        return {
            "kind": "run-threat-review",
            "track": str(package.get("track_id", "")),
            "work_id": str(package.get("work_id", "")),
            "authority_skill": "senior-security",
            "machine_review": _dict_value(package.get("architecture_threat_review")),
            "input_contract": {
                "scope_path": "docs/architecture/threat-model/scope.json",
                "scope_template": scope_template,
                "mitigations_path": "docs/architecture/threat-model/mitigations.json",
                "mitigations_template": mitigations_template,
                "dread_threshold": 7.0,
                "required_element_types": [
                    "external-entity",
                    "process",
                    "data-store",
                    "data-flow",
                ],
            },
            "decision_policy": "run_stride_dread_review_before_architecture_authority_signoff",
            "command_contract": {
                "cwd": str(root),
                "argv_prefix": ["bin/governance", "design", "threat-review", "."],
                "required_arguments": ["--reviewed"],
                "optional_arguments": ["--skill-root"],
                "preflight_argument": "--check",
                "writes_state": True,
                "approval_required": False,
            },
            "success_condition": "every DFD element has complete STRIDE coverage and every DREAD >= 7 threat has a named owner, mitigation, and repository evidence",
        }
    if package.get("kind") == "design-authoring" and package.get("work_stage") == "machine-review":
        return {
            "kind": "run-api-review",
            "track": str(package.get("track_id", "")),
            "work_id": str(package.get("work_id", "")),
            "authority_skill": str(package.get("required_authority_skill", "")),
            "machine_review": _dict_value(package.get("api_machine_review")),
            "decision_policy": "run_api_design_reviewer_tools_before_authority_signoff",
            "command_contract": {
                "cwd": str(root),
                "argv_prefix": ["bin/governance", "design", "api-review", "."],
                "required_arguments": ["--reviewed"],
                "optional_arguments": ["--min-grade", "--skill-root"],
                "preflight_argument": "--check",
                "writes_state": True,
                "approval_required": False,
            },
            "success_condition": "API lint and warning counts are zero, no breaking changes exist, and scorecard grade meets the configured minimum",
        }
    if package.get("kind") == "design-authoring" and package.get("work_stage") == "reliability-review":
        scope_template = _target_read_paths(
            root,
            ["templates/docs/backend/reliability/slo-scope.json"],
        )[0]
        policy_template = _target_read_paths(
            root,
            ["templates/docs/backend/04-error-budget-policy.md"],
        )[0]
        return {
            "kind": "run-reliability-review",
            "track": str(package.get("track_id", "")),
            "work_id": str(package.get("work_id", "")),
            "authority_skill": "slo-architect",
            "machine_review": _dict_value(package.get("backend_reliability_review")),
            "input_contract": {
                "scope_path": "docs/backend/reliability/slo-scope.json",
                "scope_template": scope_template,
                "policy_path": "docs/backend/04-error-budget-policy.md",
                "policy_template": policy_template,
                "applicability_modes": ["required", "not-applicable"],
                "required_source_domains": [
                    "product acceptance",
                    "architecture quality attributes",
                    "backend modules",
                    "external services",
                ],
            },
            "decision_policy": "decide_slo_applicability_then_run_slo_architect_before_backend_signoff",
            "command_contract": {
                "cwd": str(root),
                "argv_prefix": ["bin/governance", "design", "reliability-review", "."],
                "required_arguments": ["--reviewed"],
                "optional_arguments": ["--skill-root"],
                "preflight_argument": "--check",
                "writes_state": True,
                "approval_required": False,
            },
            "success_condition": "SLO applicability is source-backed; required SLOs pass designer, error-budget, and reviewer tools with zero findings",
        }
    if package.get("kind") == "design-authoring" and package.get("work_stage") == "migration-review":
        template_paths = {
            "review_scope": "templates/docs/backend/migrations/review-scope.json",
            "schema_before": "templates/docs/backend/migrations/schema-before.json",
            "schema_after": "templates/docs/backend/migrations/schema-after.json",
            "migration_spec": "templates/docs/backend/migrations/migration-spec.json",
            "compatibility_acceptances": "templates/docs/backend/migrations/compatibility-acceptances.json",
        }
        templates = {
            key: _target_read_paths(root, [path])[0]
            for key, path in template_paths.items()
        }
        return {
            "kind": "run-migration-review",
            "track": str(package.get("track_id", "")),
            "work_id": str(package.get("work_id", "")),
            "authority_skills": ["database-schema-designer", "migration-architect"],
            "machine_review": _dict_value(package.get("data_model_migration_review")),
            "input_contract": {
                "root": "docs/backend/migrations",
                "templates": templates,
                "applicability_modes": ["required", "not-applicable"],
                "compatibility_policy": "fully compatible or every breaking and potentially-breaking issue explicitly accepted",
            },
            "decision_policy": "design_schema_with_database_schema_designer_then_run_migration_architect_before_data_model_signoff",
            "command_contract": {
                "cwd": str(root),
                "argv_prefix": ["bin/governance", "design", "migration-review", "."],
                "required_arguments": ["--reviewed"],
                "optional_arguments": ["--skill-root"],
                "preflight_argument": "--check",
                "writes_state": True,
                "approval_required": False,
            },
            "success_condition": "schema applicability is source-backed, compatibility is approved, and every migration phase has rollback evidence",
        }
    if package.get("kind") == "design-authoring" and package.get("work_stage") == "review":
        track = str(package.get("track_id", ""))
        work_id = str(package.get("work_id", ""))
        return {
            "kind": "record-design-review",
            "track": track,
            "work_id": work_id,
            "authority_skill": str(package.get("required_authority_skill", "")),
            "reviewed_decisions": _string_list(package.get("required_decisions")),
            "result_options": _string_list(package.get("review_result_options")),
            "decision_policy": str(package.get("decision_policy", "")),
            "command_contract": {
                "cwd": str(root),
                "argv_prefix": [
                    "bin/governance",
                    "design",
                    "review",
                    ".",
                    "--track",
                    track,
                    "--work",
                    work_id,
                ],
                "required_arguments": ["--result", "--reason", "--reviewed"],
                "optional_arguments": ["--evidence", "--skill-root"],
                "preflight_argument": "--check",
                "writes_state": True,
                "approval_required": False,
            },
        }
    repair_actions = _dict_items(package.get("repair_actions"))
    if repair_actions:
        return {"kind": "repair", "source": "repair_actions", "action": repair_actions[0]}
    blockers = _dict_items(package.get("blockers"))
    if blockers:
        return {"kind": "repair", "source": "blockers", "action": blockers[0]}
    if package.get("kind") == "implementation-task" and package.get("status") == "ready":
        return {
            "kind": "claim-implementation-task",
            "command": _dict_value(package.get("start_command")),
        }
    open_decisions = _string_list(package.get("open_decisions"))
    if open_decisions:
        return {
            "kind": "resolve-decision",
            "decision": open_decisions[0],
            "decision_policy": str(package.get("decision_policy", "")),
        }
    steps = _dict_items(package.get("steps"))
    return {
        "kind": "execute-work-package",
        "step": steps[0] if steps else {},
    }


def _work_package_stop_reasons(
    package_available: bool,
    status: str,
    skill_readiness: dict[str, object],
    errors: list[str],
) -> list[str]:
    reasons = list(errors)
    if not package_available and status != "complete" and not errors:
        reasons.append("no_authoring_work_package_for_current_phase")
    if _string_list(skill_readiness.get("missing_local_workflow_skills")):
        reasons.append("required_local_workflow_skills_missing")
    if _string_list(skill_readiness.get("missing_authority_routing_skills")):
        reasons.append("required_authority_routing_skills_missing")
    return _dedupe_strings(reasons)


def _work_package_refresh_command(root: Path, skill_roots: list[Path]) -> dict[str, object]:
    argv = ["bin/governance", "workflow", "work-package", "."]
    for skill_root in skill_roots:
        argv.extend(["--skill-root", str(skill_root.expanduser().resolve())])
    argv.append("--json")
    return _command(
        root,
        "refresh-work-package",
        "Rebuild the single active work package from current repository evidence.",
        argv,
    )


def _selected_work_item(items: list[dict[str, object]], work_id: str) -> dict[str, object]:
    if work_id:
        for item in items:
            if item.get("task_id") == work_id:
                return item
    return items[0] if items else {}


def _package_id(phase: str, queue_id: str, work_id: str) -> str:
    return ":".join(part for part in (phase, queue_id, work_id) if part)


def _dict_items(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dict_value(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    return (
        [str(item) for item in value if isinstance(item, str) and item]
        if isinstance(value, (list, tuple))
        else []
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _target_read_paths(root: Path, values: list[str]) -> list[str]:
    resolved: list[str] = []
    snapshot_root = Path(WORKFLOW_PACK_SNAPSHOT_ROOT)
    for value in values:
        rel = Path(value)
        if not rel.is_absolute() and not (root / rel).is_file():
            snapshot_rel = snapshot_root / rel
            if (root / snapshot_rel).is_file():
                rel = snapshot_rel
        resolved.append(rel.as_posix())
    return _dedupe_strings(resolved)


def _product_plan_queue(root: Path) -> dict[str, object]:
    payload = build_product_plan(root)
    summary = {
        "source_document_count": _list_count(payload.get("source_documents")),
        "available_chapter_count": _list_count(payload.get("available_chapters")),
        "prd_heading_count": _list_count(payload.get("prd_headings")),
        "suggested_mapping_count": _list_count(payload.get("suggested_mappings")),
        "required_decision_count": _list_count(payload.get("required_decisions")),
        "manual_authoring_summary": payload.get("manual_authoring_summary", {}),
        "active_work": _payload_active_work(payload),
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

    for queue_id, argv, builder in DESIGN_AUTHORING_BUILDERS[:1]:
        payload = builder(root)
        summary = {
            "authoring_summary": payload.get("authoring_summary", {}),
            "source_document_count": _list_count(payload.get("source_documents")),
            "active_work": _payload_active_work(payload),
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
                "active_work": _payload_active_work(api_candidates),
                "skill_summary": _payload_skill_summary(api_candidates),
                "skill_loading_plan": _payload_skill_loading_plan(api_candidates),
            },
            api_candidates.get("errors"),
        )
    )

    for queue_id, argv, builder in DESIGN_AUTHORING_BUILDERS[1:]:
        payload = builder(root)
        summary = {
            "authoring_summary": payload.get("authoring_summary", {}),
            "source_document_count": _list_count(payload.get("source_documents")),
            "active_work": _payload_active_work(payload),
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
    queues.append(_project_runtime_queue(root))
    return queues


def _project_runtime_queue(root: Path) -> dict[str, object]:
    payload = build_project_environment_plan(root)
    summary = {
        "coverage_status": str(payload.get("coverage_status", "")),
        "configuration_complete": payload.get("configuration_complete") is True,
        "required_command_count": int(payload.get("required_command_count", 0)),
        "command_coverage": _dict_items(payload.get("command_coverage")),
        "missing_command_registrations": _dict_items(payload.get("missing_command_registrations")),
        "unready_tool_ids": _string_list(payload.get("unready_tool_ids")),
        "unused_tool_ids": _string_list(payload.get("unused_tool_ids")),
        "repair_evidence_summary": _dict_value(payload.get("repair_evidence_summary")),
        "active_work": _payload_active_work(payload),
        "skill_summary": _payload_skill_summary(payload),
        "skill_loading_plan": _payload_skill_loading_plan(payload),
    }
    configuration_complete = summary["configuration_complete"] is True
    return _queue(
        "project-runtime",
        DESIGN_PHASE,
        "project-runtime-plan",
        payload.get("ok") is True,
        not configuration_complete,
        _command(
            root,
            "project-runtime",
            "Inspect project-runtime command coverage, tool readiness, and reviewed repair routes.",
            ["bin/governance", "project-env", "plan", ".", "--json"],
        ),
        summary,
        payload.get("errors"),
        complete=configuration_complete,
    )


def _implementation_plan_queue(root: Path) -> dict[str, object]:
    payload = build_implementation_plan(root)
    summary = {
        "implementation_summary": payload.get("implementation_summary", {}),
        "source_document_count": _list_count(payload.get("source_documents")),
        "task_count": _list_count(payload.get("tasks")),
        "active_work": _payload_active_work(payload),
        "step_count": _implementation_step_count(payload.get("tasks")),
        "skill_summary": _payload_skill_summary(payload),
        "skill_loading_plan": _payload_skill_loading_plan(payload),
    }
    return _queue(
        "implementation-plan",
        IMPLEMENTATION_PHASE,
        "implementation-task-plan",
        payload.get("ok") is True,
        _implementation_summary_blocked(summary),
        _command(
            root,
            "implementation-plan",
            "Inspect Ready implementation tasks, source read order, gate status, and execution commands.",
            ["bin/governance", "implementation", "plan", ".", "--json"],
        ),
        summary,
        payload.get("errors"),
        complete=_implementation_summary_complete(summary),
    )


def _queue(
    queue_id: str,
    phase: str,
    kind: str,
    ok: bool,
    blocked: bool,
    command: dict[str, object],
    summary: dict[str, object],
    errors: object,
    *,
    complete: bool = False,
) -> dict[str, object]:
    return {
        "id": queue_id,
        "phase": phase,
        "kind": kind,
        "ok": ok,
        "status": _queue_status(ok, blocked, complete),
        "command": command,
        "summary": summary,
        "errors": list(errors) if isinstance(errors, list) else [],
    }


def _queue_status(ok: bool, blocked: bool, complete: bool = False) -> str:
    if not ok:
        return "failed"
    if complete:
        return "complete"
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
        "active_work": _payload_active_work(payload),
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


def _implementation_summary_blocked(summary: dict[str, object]) -> bool:
    implementation_summary = summary.get("implementation_summary")
    if not isinstance(implementation_summary, dict):
        return True
    if implementation_summary.get("execution_complete") is True:
        return False
    active_work = summary.get("active_work")
    return (
        implementation_summary.get("gate_ok") is not True
        or int(implementation_summary.get("actionable_task_count", 0)) == 0
        or not isinstance(active_work, dict)
        or active_work.get("status") not in {"ready", "in_progress"}
    )


def _implementation_summary_complete(summary: dict[str, object]) -> bool:
    implementation_summary = summary.get("implementation_summary")
    active_work = summary.get("active_work")
    return (
        isinstance(implementation_summary, dict)
        and implementation_summary.get("execution_complete") is True
        and isinstance(active_work, dict)
        and active_work.get("status") == "complete"
    )


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


def _implementation_step_count(tasks: object) -> int:
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


def _payload_active_work(payload: dict[str, object]) -> dict[str, object]:
    active_work = payload.get("active_work")
    return dict(active_work) if isinstance(active_work, dict) else {}


def _workflow_active_work(queues: list[dict[str, object]]) -> dict[str, object]:
    if not queues:
        return {}
    queue = next((item for item in queues if item.get("status") not in {"ready", "complete"}), queues[0])
    summary = queue.get("summary")
    active_work = {}
    if isinstance(summary, dict):
        active = summary.get("active_work")
        if isinstance(active, dict):
            active_work = dict(active)
    active_work["queue_id"] = str(queue.get("id", ""))
    active_work["queue_status"] = str(queue.get("status", ""))
    command = queue.get("command")
    active_work["inspect_command"] = dict(command) if isinstance(command, dict) else {}
    return active_work


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
