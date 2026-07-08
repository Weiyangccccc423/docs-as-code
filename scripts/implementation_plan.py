from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .bootstrap_tree import target_local_commands_payload
    from .design_plan import _skill_requirement_fields
    from .gates import evaluate_gate
    from .state import load_state
    from .verify_governance import (
        ACCEPTANCE_MATRIX_REL,
        SCAFFOLD_PLACEHOLDER,
        TASK_BOARD_ALLOWED_STATUSES,
        TASK_BOARD_READY_STATUSES,
        TASK_BOARD_REL,
        TASK_ID_RE,
        VERIFICATION_LOG_REL,
        _acceptance_matrix_mapped_acceptance_ids,
        _is_empty_task_board_value,
        _normalize_cell,
        _roadmap_milestone_rows,
        _task_board_acceptance_id,
        _task_board_local_references,
        _task_board_row_trace_complete,
        _task_board_row_trace_reference_errors,
        _task_board_rows,
        _verification_log_rows,
        _verification_log_task_ids,
        verify,
    )
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from design_plan import _skill_requirement_fields
    from gates import evaluate_gate
    from state import load_state
    from verify_governance import (
        ACCEPTANCE_MATRIX_REL,
        SCAFFOLD_PLACEHOLDER,
        TASK_BOARD_ALLOWED_STATUSES,
        TASK_BOARD_READY_STATUSES,
        TASK_BOARD_REL,
        TASK_ID_RE,
        VERIFICATION_LOG_REL,
        _acceptance_matrix_mapped_acceptance_ids,
        _is_empty_task_board_value,
        _normalize_cell,
        _roadmap_milestone_rows,
        _task_board_acceptance_id,
        _task_board_local_references,
        _task_board_row_trace_complete,
        _task_board_row_trace_reference_errors,
        _task_board_rows,
        _verification_log_rows,
        _verification_log_task_ids,
        verify,
    )
    from workflow_actions import next_actions_payload


IMPLEMENTATION_PHASE = "implementation"
IMPLEMENTATION_WORKFLOW_PATH = "workflows/06-implementation-execution.md"
IMPLEMENTATION_SKILLS = (
    "executing-implementation-task",
    "verifying-governance-docs",
)
BASE_SPECIALIST_SKILLS = (
    "senior-fullstack",
    "senior-qa",
    "senior-security",
)
BASE_SOURCE_DOCUMENTS = (
    TASK_BOARD_REL.as_posix(),
    VERIFICATION_LOG_REL.as_posix(),
    "docs/agent-workflow/command-contract.md",
    ACCEPTANCE_MATRIX_REL.as_posix(),
)
OPTIONAL_SOURCE_DOCUMENTS = (
    "docs/agent-workflow/task-handoff.md",
)
ROADMAP_REL = Path("docs/development/01-roadmap.md")
PASSING_VERIFICATION_RESULTS = {"ok", "pass", "passed", "success", "succeeded", "green"}


def build_implementation_plan(root: Path) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase != IMPLEMENTATION_PHASE:
        errors.append(f"implementation plan requires recorded phase {IMPLEMENTATION_PHASE}")

    rows, row_errors = _read_task_rows(root)
    errors.extend(row_errors)
    matrix_ids = _acceptance_matrix_mapped_acceptance_ids(root)
    verification_task_ids = _verification_log_task_ids(root)
    tasks = _implementation_tasks(root, rows, matrix_ids, verification_task_ids)
    gate = evaluate_gate(root, IMPLEMENTATION_PHASE).to_dict() if state else {}
    specialist_skills = _implementation_specialist_skills(tasks)
    active_work = _active_implementation_work(root, tasks, gate)
    summary = _implementation_summary(tasks, verification_task_ids, gate)

    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": IMPLEMENTATION_WORKFLOW_PATH,
        "decision_policy": "execute_exactly_one_ready_task",
        "primary_skill": "executing-implementation-task",
        "skills": list(IMPLEMENTATION_SKILLS),
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, IMPLEMENTATION_SKILLS, specialist_skills),
        "references": [
            "references/implementation-readiness-checklist.md",
            "references/implementation-execution-checklist.md",
        ],
        "source_documents": _source_documents(root),
        "implementation_summary": summary,
        "gate": gate,
        "gate_ok": gate.get("ok") is True,
        "blocked": _implementation_blocked(summary, active_work),
        "active_work": active_work,
        "tasks": tasks,
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def build_implementation_closeout(root: Path, task_id: str) -> dict[str, object]:
    root = root.resolve()
    state = load_state(root)
    phase = state.get("phase") if isinstance(state.get("phase"), str) else ""
    task_id = task_id.strip()
    errors: list[str] = []
    if not state:
        errors.append("No governance state found.")
    elif phase != IMPLEMENTATION_PHASE:
        errors.append(f"implementation closeout requires recorded phase {IMPLEMENTATION_PHASE}")
    if TASK_ID_RE.fullmatch(task_id) is None:
        errors.append("implementation closeout requires --task TASK-NNN")

    rows, row_errors = _read_task_rows(root)
    errors.extend(row_errors)
    row = _task_row_by_id(rows, task_id)
    if row is None and not any(error.startswith("implementation closeout requires --task") for error in errors):
        errors.append(f"implementation closeout task not found: {task_id}")

    verification_report = verify(root)
    gate = evaluate_gate(root, IMPLEMENTATION_PHASE).to_dict() if state else {}
    verification_rows = _verification_rows_for_task(root, task_id)
    roadmap_row = _roadmap_row_for_task(root, task_id)
    requirements = _closeout_requirements(root, row, task_id, gate, verification_report, verification_rows, roadmap_row)
    evidence_summary = _closeout_evidence_summary(root, row, task_id, verification_rows, roadmap_row)
    ready = not errors and all(requirement["status"] == "satisfied" for requirement in requirements)
    payload: dict[str, object] = {
        "ok": not errors,
        "target": str(root),
        "phase": phase,
        "workflow": IMPLEMENTATION_WORKFLOW_PATH,
        "decision_policy": "do_not_mark_done_without_passing_evidence",
        "primary_skill": "executing-implementation-task",
        "task_id": task_id,
        "closeout_ready": ready,
        "target_status": "Done",
        "gate": gate,
        "gate_ok": gate.get("ok") is True,
        "verification_ok": verification_report.ok,
        "task": _closeout_task_payload(root, row) if row is not None else {},
        "evidence_summary": evidence_summary,
        "requirements": requirements,
        "blocking_requirements": [
            requirement for requirement in requirements if requirement.get("status") != "satisfied"
        ],
        "status_update_plan": _status_update_plan(row, roadmap_row, "Done") if row is not None else {},
        "verify_command": _embedded_command(
            root,
            "verify-implementation-closeout",
            "Run read-only governance verification before and after task closeout evidence changes.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        "refresh_command": _embedded_command(
            root,
            "refresh-implementation-closeout",
            "Refresh this implementation closeout plan after evidence or status changes.",
            ["bin/governance", "implementation", "closeout", ".", "--task", task_id, "--json"],
        ),
        "errors": errors,
    }
    if not errors:
        payload["local_commands"] = target_local_commands_payload(cwd=str(root))
        payload["next_actions"] = next_actions_payload(state, cwd=str(root))
    return payload


def _read_task_rows(root: Path) -> tuple[list[dict[str, str]], list[str]]:
    path = root / TASK_BOARD_REL
    if not path.exists():
        return [], [f"required implementation plan file is missing: {TASK_BOARD_REL.as_posix()}"]
    if not path.is_file():
        return [], [f"required implementation plan path is not a file: {TASK_BOARD_REL.as_posix()}"]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], [f"required implementation plan file must be UTF-8 Markdown: {TASK_BOARD_REL.as_posix()}"]
    except OSError as error:
        reason = error.strerror or str(error)
        return [], [f"required implementation plan file is unreadable: {TASK_BOARD_REL.as_posix()}: {reason}"]
    if SCAFFOLD_PLACEHOLDER in text:
        return [], [f"required implementation plan file still contains scaffold placeholders: {TASK_BOARD_REL.as_posix()}"]
    rows, missing = _task_board_rows(text)
    if missing:
        return [], [
            f"{TASK_BOARD_REL.as_posix()} table is missing required columns: {', '.join(missing)}"
        ]
    return rows, []


def _task_row_by_id(rows: list[dict[str, str]], task_id: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("id", "").strip() == task_id:
            return row
    return None


def _verification_rows_for_task(root: Path, task_id: str) -> list[dict[str, str]]:
    path = root / VERIFICATION_LOG_REL
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    rows, missing = _verification_log_rows(text)
    if missing:
        return []
    return [row for row in rows if row.get("task", "").strip() == task_id]


def _roadmap_row_for_task(root: Path, task_id: str) -> dict[str, str] | None:
    path = root / ROADMAP_REL
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    rows, missing = _roadmap_milestone_rows(text)
    if missing:
        return None
    for row in rows:
        if row.get("id", "").strip() == task_id:
            return row
    return None


def _closeout_requirements(
    root: Path,
    row: dict[str, str] | None,
    task_id: str,
    gate: dict[str, object],
    verification_report: Any,
    verification_rows: list[dict[str, str]],
    roadmap_row: dict[str, str] | None,
) -> list[dict[str, object]]:
    requirements: list[dict[str, object]] = [
        _closeout_requirement(
            "implementation_gate_passed",
            gate.get("ok") is True,
            "implementation gate must pass before a task can be marked Done",
            repair_strategy="repair_failed_implementation_gate_requirement_before_marking_done",
        ),
        _closeout_requirement(
            "governance_verify_passed",
            verification_report.ok,
            "read-only governance verification must pass before closeout",
            repair_strategy="repair_governance_verification_findings_before_marking_done",
        ),
    ]
    if row is None:
        requirements.append(
            _closeout_requirement(
                "task_board_row_present",
                False,
                f"{task_id} must exist in {TASK_BOARD_REL.as_posix()}",
                path=TASK_BOARD_REL.as_posix(),
                repair_strategy="add_or_restore_task_board_row_before_closeout",
            )
        )
        return requirements

    acceptance_id = _task_board_acceptance_id(row.get("acceptance", ""))
    matrix_ids = _acceptance_matrix_mapped_acceptance_ids(root)
    trace_errors = _task_board_row_trace_reference_errors(root, row, task_id)
    requirements.extend(
        [
            _closeout_requirement(
                "task_board_row_present",
                True,
                f"{task_id} exists in {TASK_BOARD_REL.as_posix()}",
                path=TASK_BOARD_REL.as_posix(),
            ),
            _closeout_requirement(
                "task_trace_links_valid",
                not trace_errors and _task_board_row_trace_complete(row),
                "task Product, Design, API, Acceptance, and Verification sources must be traceable",
                path=TASK_BOARD_REL.as_posix(),
                detail="; ".join(message for _code, message in trace_errors),
                repair_strategy="repair_task_board_traceability_before_marking_done",
            ),
            _closeout_requirement(
                "acceptance_matrix_mapped",
                matrix_ids is not None and acceptance_id is not None and acceptance_id in matrix_ids,
                "task acceptance ID must be mapped in the acceptance matrix",
                path=ACCEPTANCE_MATRIX_REL.as_posix(),
                detail=acceptance_id or "missing acceptance ID",
                repair_strategy="map_task_acceptance_in_acceptance_matrix_before_marking_done",
            ),
            _closeout_requirement(
                "verification_log_row_present",
                bool(verification_rows),
                "verification log must contain a row for the task",
                path=VERIFICATION_LOG_REL.as_posix(),
                repair_strategy="record_task_verification_run_before_marking_done",
            ),
            _closeout_requirement(
                "verification_result_passing",
                any(_verification_row_passed(row) for row in verification_rows),
                "at least one task verification result must be passing",
                path=VERIFICATION_LOG_REL.as_posix(),
                detail=", ".join(row.get("result", "").strip() for row in verification_rows),
                repair_strategy="run_required_task_checks_and_record_passing_result",
            ),
            _closeout_requirement(
                "task_verification_links_local_evidence",
                _verification_cell_has_local_evidence(root, row),
                "task Verification cell must link local Markdown evidence before Done",
                path=TASK_BOARD_REL.as_posix(),
                repair_strategy="link_task_verification_to_local_markdown_evidence",
            ),
            _closeout_requirement(
                "roadmap_row_present",
                roadmap_row is not None,
                f"{task_id} must exist in {ROADMAP_REL.as_posix()}",
                path=ROADMAP_REL.as_posix(),
                repair_strategy="add_or_restore_matching_roadmap_row_before_closeout",
            ),
        ]
    )
    return requirements


def _closeout_requirement(
    code: str,
    satisfied: bool,
    message: str,
    *,
    path: str = "",
    detail: str = "",
    repair_strategy: str = "",
) -> dict[str, object]:
    return {
        "code": code,
        "status": "satisfied" if satisfied else "missing",
        "ok": satisfied,
        "path": path,
        "message": message,
        "detail": detail,
        "repair_strategy": repair_strategy,
    }


def _verification_row_passed(row: dict[str, str]) -> bool:
    result = _normalize_cell(row.get("result", ""))
    return result in PASSING_VERIFICATION_RESULTS


def _verification_cell_has_local_evidence(root: Path, row: dict[str, str]) -> bool:
    references = _task_board_local_references(root, row.get("verification", ""))
    return any(reference.exists for reference in references)


def _closeout_evidence_summary(
    root: Path,
    row: dict[str, str] | None,
    task_id: str,
    verification_rows: list[dict[str, str]],
    roadmap_row: dict[str, str] | None,
) -> dict[str, object]:
    verification_refs = _task_board_local_references(root, row.get("verification", "")) if row is not None else []
    return {
        "task_id": task_id,
        "task_status": row.get("status", "").strip() if row is not None else "",
        "roadmap_status": roadmap_row.get("status", "").strip() if roadmap_row is not None else "",
        "verification_logged": bool(verification_rows),
        "passing_verification_logged": any(_verification_row_passed(item) for item in verification_rows),
        "verification_results": [
            {
                "command": item.get("command", "").strip(),
                "result": item.get("result", "").strip(),
                "date": item.get("date", "").strip(),
                "notes": item.get("notes", "").strip(),
                "passing": _verification_row_passed(item),
            }
            for item in verification_rows
        ],
        "verification_references": _references_payload(verification_refs),
        "verification_links_local_evidence": any(reference.exists for reference in verification_refs),
    }


def _closeout_task_payload(root: Path, row: dict[str, str]) -> dict[str, object]:
    acceptance_id = _task_board_acceptance_id(row.get("acceptance", ""))
    return {
        "task_id": row.get("id", "").strip(),
        "status": row.get("status", "").strip(),
        "title": _plain_task_title(row.get("task", "")),
        "acceptance_id": acceptance_id or "",
        "source_references": _source_references(root, row),
        "verification": row.get("verification", "").strip(),
    }


def _status_update_plan(
    row: dict[str, str],
    roadmap_row: dict[str, str] | None,
    target_status: str,
) -> dict[str, object]:
    updates: list[dict[str, object]] = []
    current_task_status = row.get("status", "").strip()
    task_id = row.get("id", "").strip()
    if _normalize_cell(current_task_status) != _normalize_cell(target_status):
        updates.append(
            {
                "path": TASK_BOARD_REL.as_posix(),
                "task_id": task_id,
                "field": "Status",
                "from": current_task_status,
                "to": target_status,
            }
        )
    current_roadmap_status = roadmap_row.get("status", "").strip() if roadmap_row is not None else ""
    if roadmap_row is not None and _normalize_cell(current_roadmap_status) != _normalize_cell(target_status):
        updates.append(
            {
                "path": ROADMAP_REL.as_posix(),
                "task_id": task_id,
                "field": "Status",
                "from": current_roadmap_status,
                "to": target_status,
            }
        )
    return {
        "target_status": target_status,
        "can_auto_apply": False,
        "updates_required": bool(updates),
        "updates": updates,
        "manual_policy": "update_task_board_and_roadmap_together_after_closeout_ready",
    }


def _implementation_tasks(
    root: Path,
    rows: list[dict[str, str]],
    matrix_ids: set[str] | None,
    verification_task_ids: set[str] | None,
) -> list[dict[str, object]]:
    seen_ids: set[str] = set()
    tasks: list[dict[str, object]] = []
    for sequence, row in enumerate(rows, start=1):
        task = _implementation_task(root, row, sequence, matrix_ids, verification_task_ids, seen_ids)
        task_id = str(task.get("task_id", ""))
        if TASK_ID_RE.fullmatch(task_id) is not None:
            seen_ids.add(_normalize_cell(task_id))
        tasks.append(task)
    return tasks


def _implementation_task(
    root: Path,
    row: dict[str, str],
    sequence: int,
    matrix_ids: set[str] | None,
    verification_task_ids: set[str] | None,
    seen_ids: set[str],
) -> dict[str, object]:
    task_id = row.get("id", "").strip()
    normalized_status = _normalize_cell(row.get("status", ""))
    acceptance_id = _task_board_acceptance_id(row.get("acceptance", ""))
    blockers = _task_blockers(root, row, task_id, normalized_status, acceptance_id, matrix_ids, seen_ids)
    source_references = _source_references(root, row)
    specialist_skills = _task_specialist_skills(source_references)
    actionable = normalized_status in TASK_BOARD_READY_STATUSES and not blockers
    execution = {
        "stage": "implementation-execution",
        "primary_skill": "executing-implementation-task",
        "primary_specialist_skill": specialist_skills[0] if specialist_skills else "senior-fullstack",
        "verify_step": "verify-implementation-execution",
        "refresh_step": "refresh-implementation-plan",
        "stop_condition": "implementation_gate_failed_or_task_not_ready_or_required_sources_missing",
    }
    return {
        "task_id": task_id,
        "sequence": sequence,
        "status": row.get("status", "").strip(),
        "normalized_status": normalized_status,
        "actionable": actionable,
        "title": _plain_task_title(row.get("task", "")),
        "acceptance_id": acceptance_id or "",
        "source_references": source_references,
        "verification": row.get("verification", "").strip(),
        "verification_logged": task_id in verification_task_ids if verification_task_ids is not None else False,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "open_decisions": [],
        "open_decision_count": 0,
        "specialist_skills": specialist_skills,
        **_skill_requirement_fields(root, IMPLEMENTATION_SKILLS, specialist_skills),
        "read_order": _task_read_order(root, source_references),
        "execution": execution,
        "steps": _task_steps(root, specialist_skills),
    }


def _task_blockers(
    root: Path,
    row: dict[str, str],
    task_id: str,
    normalized_status: str,
    acceptance_id: str | None,
    matrix_ids: set[str] | None,
    seen_ids: set[str],
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    missing_fields = [
        column
        for column in ("id", "status", "task", "product", "design", "api", "acceptance", "verification")
        if _is_empty_task_board_value(row.get(column, ""))
    ]
    if missing_fields:
        blockers.append(_blocker(root, "task_board_row_missing_fields", TASK_BOARD_REL.as_posix(), ", ".join(missing_fields)))
    if task_id and TASK_ID_RE.fullmatch(task_id) is None:
        blockers.append(_blocker(root, "task_board_invalid_id", TASK_BOARD_REL.as_posix(), task_id))
    if task_id and _normalize_cell(task_id) in seen_ids:
        blockers.append(_blocker(root, "task_board_duplicate_id", TASK_BOARD_REL.as_posix(), task_id))
    if normalized_status and normalized_status not in TASK_BOARD_ALLOWED_STATUSES:
        blockers.append(_blocker(root, "task_board_invalid_status", TASK_BOARD_REL.as_posix(), row.get("status", "").strip()))
    if normalized_status not in TASK_BOARD_READY_STATUSES:
        blockers.append(_blocker(root, "task_board_task_not_ready", TASK_BOARD_REL.as_posix(), row.get("status", "").strip()))
    if not _task_board_row_trace_complete(row):
        blockers.append(_blocker(root, "task_board_trace_incomplete", TASK_BOARD_REL.as_posix(), "traceability fields"))
    for code, message in _task_board_row_trace_reference_errors(root, row, task_id or "(missing id)"):
        blockers.append(_blocker(root, code, TASK_BOARD_REL.as_posix(), message))
    if matrix_ids is None:
        blockers.append(_blocker(root, "acceptance_matrix_unavailable", ACCEPTANCE_MATRIX_REL.as_posix(), "mapped acceptance IDs"))
    elif acceptance_id is None or acceptance_id not in matrix_ids:
        blockers.append(
            _blocker(
                root,
                "task_board_acceptance_matrix_missing",
                ACCEPTANCE_MATRIX_REL.as_posix(),
                acceptance_id or "missing acceptance ID",
            )
        )
    return blockers


def _blocker(root: Path, code: str, path: str, detail: str) -> dict[str, object]:
    return {
        "code": code,
        "path": path,
        "detail": detail,
        "repair_strategy": _repair_strategy(code),
        "verify_command": _embedded_command(
            root,
            "verify-implementation-execution",
            "Run read-only governance verification after repairing this blocker.",
            ["bin/governance", "verify", ".", "--check", "--json"],
        ),
        "refresh_command": _embedded_command(
            root,
            "refresh-implementation-plan",
            "Refresh the implementation task plan after repairing this blocker.",
            ["bin/governance", "implementation", "plan", ".", "--json"],
        ),
    }


def _repair_strategy(code: str) -> str:
    if code == "task_board_task_not_ready":
        return "select_or_promote_one_source_backed_ready_task_before_editing_code"
    if code in {"task_board_trace_reference_missing", "task_board_trace_reference_mismatch"}:
        return "repair_task_board_local_markdown_traceability_before_editing_code"
    if code == "task_board_acceptance_matrix_missing":
        return "map_acceptance_id_in_acceptance_matrix_before_editing_code"
    if code == "acceptance_matrix_unavailable":
        return "restore_acceptance_matrix_with_product_design_api_test_mapping"
    if code == "task_board_trace_incomplete":
        return "fill_product_design_api_acceptance_and_verification_cells_from_local_sources"
    return "repair_task_board_row_before_editing_code"


def _source_references(root: Path, row: dict[str, str]) -> dict[str, object]:
    return {
        column: {
            "raw": row.get(column, "").strip(),
            "references": _references_payload(_task_board_local_references(root, row.get(column, ""))),
        }
        for column in ("product", "design", "api", "acceptance", "verification")
    }


def _references_payload(references: object) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    if not isinstance(references, list):
        return payload
    for reference in references:
        payload.append(
            {
                "raw": str(getattr(reference, "raw", "")),
                "path": str(getattr(reference, "rel", "")),
                "exists": bool(getattr(reference, "exists", False)),
            }
        )
    return payload


def _task_read_order(root: Path, source_references: dict[str, object]) -> list[str]:
    order: list[str] = [TASK_BOARD_REL.as_posix()]
    for column in ("product", "design", "api", "acceptance", "verification"):
        item = source_references.get(column)
        if not isinstance(item, dict):
            continue
        references = item.get("references")
        if not isinstance(references, list):
            continue
        for reference in references:
            if isinstance(reference, dict) and reference.get("exists") is True:
                _append_unique(order, str(reference.get("path", "")))
    for rel in (
        ACCEPTANCE_MATRIX_REL.as_posix(),
        "docs/agent-workflow/command-contract.md",
        "docs/agent-workflow/task-handoff.md",
        VERIFICATION_LOG_REL.as_posix(),
    ):
        if (root / rel).is_file():
            _append_unique(order, rel)
    return order


def _task_steps(root: Path, specialist_skills: list[str]) -> list[dict[str, object]]:
    return _sequence_steps(
        [
            {
                "id": "load-implementation-skill",
                "description": "Load local implementation execution and governance verification skills before editing code.",
                "skills": list(IMPLEMENTATION_SKILLS),
                "specialist_skills": specialist_skills,
                **_skill_requirement_fields(root, IMPLEMENTATION_SKILLS, specialist_skills),
            },
            {
                "id": "read-implementation-checklist",
                "description": "Read the implementation execution checklist and target-local command contract.",
                "references": [
                    "references/implementation-execution-checklist.md",
                    "docs/agent-workflow/command-contract.md",
                ],
            },
            _embedded_command(
                root,
                "implementation-gate",
                "Confirm the implementation gate before editing code.",
                ["bin/governance", "gate", "implementation", ".", "--json"],
            ),
            _embedded_command(
                root,
                "verify-implementation-execution",
                "Run read-only governance verification before and after implementation evidence changes.",
                ["bin/governance", "verify", ".", "--check", "--json"],
            ),
            {
                "id": "read-task-sources",
                "description": "Read the selected task row and every linked product, design, API, acceptance, and verification source.",
            },
            {
                "id": "inspect-code-surface",
                "description": "Inspect existing code, tests, generated files, build scripts, and local AGENTS.md rules before editing.",
            },
            {
                "id": "implement-one-task",
                "description": "Implement only the selected Ready TASK-NNN scope and update adjacent tests.",
            },
            {
                "id": "run-task-verification",
                "description": "Run the task-board, command-contract, or handoff verification commands and preserve evidence.",
            },
            {
                "id": "update-task-evidence",
                "description": "Update verification log, task board, and roadmap status consistently.",
            },
            _embedded_command(
                root,
                "implementation-closeout",
                "Check whether the selected implementation task has enough evidence to mark Done.",
                ["bin/governance", "implementation", "closeout", ".", "--task", "TASK-NNN", "--json"],
            ),
            _embedded_command(
                root,
                "refresh-implementation-plan",
                "Refresh the implementation plan after status or evidence changes.",
                ["bin/governance", "implementation", "plan", ".", "--json"],
            ),
        ]
    )


def _active_implementation_work(
    root: Path,
    tasks: list[dict[str, object]],
    gate: dict[str, object],
) -> dict[str, object]:
    selected = _selected_task(tasks)
    if not selected:
        blocker = {
            "code": "task_board_ready_task_missing",
            "path": TASK_BOARD_REL.as_posix(),
            "detail": "no Ready TASK-NNN row is actionable",
            "repair_strategy": "create_or_repair_one_source_backed_ready_task_before_editing_code",
        }
        return {
            "kind": "implementation-task",
            "status": "blocked",
            "primary_skill": "executing-implementation-task",
            "primary_specialist_skill": "senior-fullstack",
            "blocker_count": 1,
            "open_decision_count": 0,
            "next_blocker": blocker,
            "next_repair_action": blocker,
            "read_order": _source_documents(root),
            "verify_step": "verify-implementation-execution",
            "refresh_step": "refresh-implementation-plan",
            "stop_condition": "no_actionable_ready_task",
            "gate_ok": gate.get("ok") is True,
            "gate_command": _embedded_command(root, "implementation-gate", "Confirm the implementation gate.", ["bin/governance", "gate", "implementation", ".", "--json"]),
            "verify_command": _embedded_command(root, "verify-implementation-execution", "Run read-only governance verification.", ["bin/governance", "verify", ".", "--check", "--json"]),
            "closeout_command": _embedded_command(root, "implementation-closeout", "Check task closeout evidence before marking Done.", ["bin/governance", "implementation", "closeout", ".", "--task", "TASK-NNN", "--json"]),
            "refresh_command": _embedded_command(root, "refresh-implementation-plan", "Refresh the implementation task plan.", ["bin/governance", "implementation", "plan", ".", "--json"]),
        }
    blockers = selected.get("blockers") if isinstance(selected.get("blockers"), list) else []
    specialist_skills = selected.get("specialist_skills") if isinstance(selected.get("specialist_skills"), list) else []
    status = "ready" if selected.get("actionable") is True and gate.get("ok") is True else "blocked"
    return {
        "kind": "implementation-task",
        "task_id": str(selected.get("task_id", "")),
        "sequence": int(selected.get("sequence", 0)) if isinstance(selected.get("sequence"), int) else 0,
        "status": status,
        "task_status": str(selected.get("status", "")),
        "title": str(selected.get("title", "")),
        "acceptance_id": str(selected.get("acceptance_id", "")),
        "primary_skill": "executing-implementation-task",
        "primary_specialist_skill": str(specialist_skills[0]) if specialist_skills else "senior-fullstack",
        "specialist_skills": [str(skill) for skill in specialist_skills],
        "blocker_count": len(blockers) + (0 if gate.get("ok") is True else 1),
        "open_decision_count": 0,
        "next_blocker": dict(blockers[0]) if blockers and isinstance(blockers[0], dict) else _gate_blocker(gate),
        "next_repair_action": dict(blockers[0]) if blockers and isinstance(blockers[0], dict) else _gate_blocker(gate),
        "read_order": list(selected.get("read_order")) if isinstance(selected.get("read_order"), list) else [],
        "verify_step": "verify-implementation-execution",
        "refresh_step": "refresh-implementation-plan",
        "stop_condition": "implementation_gate_failed_or_task_not_ready_or_required_sources_missing",
        "gate_ok": gate.get("ok") is True,
        "gate_command": _embedded_command(root, "implementation-gate", "Confirm the implementation gate.", ["bin/governance", "gate", "implementation", ".", "--json"]),
        "verify_command": _embedded_command(root, "verify-implementation-execution", "Run read-only governance verification.", ["bin/governance", "verify", ".", "--check", "--json"]),
        "closeout_command": _embedded_command(root, "implementation-closeout", "Check task closeout evidence before marking Done.", ["bin/governance", "implementation", "closeout", ".", "--task", str(selected.get("task_id", "")), "--json"]),
        "refresh_command": _embedded_command(root, "refresh-implementation-plan", "Refresh the implementation task plan.", ["bin/governance", "implementation", "plan", ".", "--json"]),
    }


def _selected_task(tasks: list[dict[str, object]]) -> dict[str, object]:
    for task in tasks:
        if task.get("actionable") is True:
            return task
    for task in tasks:
        if _normalize_cell(str(task.get("status", ""))) in TASK_BOARD_READY_STATUSES:
            return task
    return tasks[0] if tasks else {}


def _gate_blocker(gate: dict[str, object]) -> dict[str, object]:
    if gate.get("ok") is True:
        return {}
    requirements = gate.get("requirements")
    if isinstance(requirements, list):
        for requirement in requirements:
            if isinstance(requirement, dict) and requirement.get("ok") is not True:
                return {
                    "code": str(requirement.get("code", "implementation_gate_failed")),
                    "path": str(requirement.get("path", "")),
                    "detail": str(requirement.get("message", "implementation gate failed")),
                    "repair_strategy": "repair_failed_implementation_gate_requirement_before_editing_code",
                }
    return {
        "code": "implementation_gate_failed",
        "path": "",
        "detail": "implementation gate failed",
        "repair_strategy": "repair_failed_implementation_gate_requirement_before_editing_code",
    }


def _implementation_summary(
    tasks: list[dict[str, object]],
    verification_task_ids: set[str] | None,
    gate: dict[str, object],
) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    for task in tasks:
        status = str(task.get("normalized_status", "unknown") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    actionable_count = sum(1 for task in tasks if task.get("actionable") is True)
    return {
        "task_count": len(tasks),
        "ready_task_count": status_counts.get("ready", 0),
        "actionable_ready_task_count": actionable_count,
        "blocked_task_count": status_counts.get("blocked", 0),
        "done_task_count": status_counts.get("done", 0),
        "invalid_task_count": sum(1 for task in tasks if int(task.get("blocker_count", 0)) > 0),
        "task_status_counts": dict(sorted(status_counts.items())),
        "verification_evidence_task_count": len(verification_task_ids) if verification_task_ids is not None else 0,
        "gate_ok": gate.get("ok") is True,
    }


def _implementation_blocked(summary: dict[str, object], active_work: dict[str, object]) -> bool:
    return (
        summary.get("gate_ok") is not True
        or int(summary.get("actionable_ready_task_count", 0)) == 0
        or active_work.get("status") != "ready"
    )


def _source_documents(root: Path) -> list[str]:
    documents: list[str] = []
    for rel in (*BASE_SOURCE_DOCUMENTS, *OPTIONAL_SOURCE_DOCUMENTS):
        if (root / rel).is_file():
            documents.append(rel)
    return documents


def _implementation_specialist_skills(tasks: list[dict[str, object]]) -> list[str]:
    skills = list(BASE_SPECIALIST_SKILLS)
    for task in tasks:
        task_skills = task.get("specialist_skills")
        if isinstance(task_skills, list):
            for skill in task_skills:
                if isinstance(skill, str):
                    _append_unique(skills, skill)
    return skills


def _task_specialist_skills(source_references: dict[str, object]) -> list[str]:
    paths = _referenced_paths(source_references)
    skills = list(BASE_SPECIALIST_SKILLS)
    if any(path.startswith("docs/api/") or path.startswith("docs/backend/") for path in paths):
        _append_unique(skills, "senior-backend")
    if any(path.startswith("docs/frontend/") or path.startswith("docs/ui/") for path in paths):
        _append_unique(skills, "senior-frontend")
    if any(path.startswith("docs/api/") for path in paths):
        _append_unique(skills, "api-design-reviewer")
    return skills


def _referenced_paths(source_references: dict[str, object]) -> list[str]:
    paths: list[str] = []
    for item in source_references.values():
        if not isinstance(item, dict):
            continue
        references = item.get("references")
        if not isinstance(references, list):
            continue
        for reference in references:
            if isinstance(reference, dict):
                path = str(reference.get("path", ""))
                if path:
                    paths.append(path)
    return paths


def _plain_task_title(value: str) -> str:
    return " ".join(value.replace("`", "").split())


def _embedded_command(root: Path, command_id: str, description: str, argv: list[str]) -> dict[str, object]:
    return {
        "id": command_id,
        "cwd": str(root),
        "command": " ".join(argv),
        "argv": list(argv),
        "writes_state": False,
        "approval_required": False,
        "description": description,
    }


def _sequence_steps(steps: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "sequence": index,
            **step,
        }
        for index, step in enumerate(steps, start=1)
    ]


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
