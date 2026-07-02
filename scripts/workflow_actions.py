from __future__ import annotations

from copy import deepcopy
from typing import Any


TARGET_WORKFLOW_ROOT = "docs/agent-workflow/workflow-pack"

PRODUCT_IMPORT_ACTIONS: tuple[dict[str, object], ...] = (
    {
        "id": "product-mark-ready-check",
        "kind": "preflight",
        "phase": "product-document-archiving",
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/02-product-document-archiving.md",
        "skills": ("archiving-product-document", "verifying-governance-docs"),
        "command": "bin/governance product mark-ready . --reviewed --method manual-reviewed-markdown --check --json",
        "writes_state": False,
        "requires": "docs/product/core/PRD.md has been manually reviewed against the archived source",
        "description": "preview product import readiness closeout before allowing downstream derivation",
    },
    {
        "id": "product-mark-ready",
        "kind": "apply",
        "phase": "product-document-archiving",
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/02-product-document-archiving.md",
        "skills": ("archiving-product-document", "verifying-governance-docs"),
        "command": "bin/governance product mark-ready . --reviewed --method manual-reviewed-markdown --json",
        "writes_state": True,
        "requires": "product-mark-ready-check ok:true",
        "description": "record reviewed product import readiness in source manifest and governance state",
    },
)

PHASE_ACTIONS: dict[str, dict[str, object]] = {
    "product-structuring": {
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/03-product-structuring.md",
        "skills": ("structuring-product-requirements", "verifying-governance-docs"),
        "description": "advance from initialization into product structuring",
    },
    "design-derivation": {
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/04-design-derivation.md",
        "skills": (
            "designing-system-architecture",
            "designing-ui-interactions",
            "designing-api-contracts",
            "designing-backend-modules",
            "designing-data-models",
            "capturing-architecture-decisions",
            "designing-frontend-modules",
            "designing-test-strategy",
            "planning-implementation-work",
            "verifying-governance-docs",
        ),
        "description": "advance from product structuring into design derivation",
    },
    "implementation": {
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/05-verification-and-drift-control.md",
        "skills": ("verifying-governance-docs",),
        "description": "advance from design derivation into implementation readiness",
    },
}

PHASE_ORDER = ("initialized", "product-structuring", "design-derivation", "implementation")


def next_actions_payload(state: dict[str, Any]) -> list[dict[str, object]]:
    if not isinstance(state, dict):
        raise ValueError("workflow action state must be an object")
    phase = state.get("phase")
    if phase == "initialized" and state.get("product_import_status") != "ready_for_structuring":
        return _copy_actions(PRODUCT_IMPORT_ACTIONS)
    next_phase = _next_phase(phase)
    if not next_phase:
        return []
    return _advance_actions(next_phase)


def _next_phase(phase: object) -> str:
    if not isinstance(phase, str) or phase not in PHASE_ORDER:
        return ""
    index = PHASE_ORDER.index(phase)
    if index >= len(PHASE_ORDER) - 1:
        return ""
    return PHASE_ORDER[index + 1]


def _advance_actions(phase: str) -> list[dict[str, object]]:
    metadata = PHASE_ACTIONS[phase]
    return [
        {
            "id": f"advance-{phase}-check",
            "kind": "preflight",
            "phase": phase,
            "workflow": metadata["workflow"],
            "skills": list(metadata["skills"]),
            "command": f"bin/governance advance {phase} . --check --json",
            "writes_state": False,
            "requires": "current phase is the previous workflow phase and the gate can pass",
            "description": f"preflight {metadata['description']}",
        },
        {
            "id": f"advance-{phase}",
            "kind": "apply",
            "phase": phase,
            "workflow": metadata["workflow"],
            "skills": list(metadata["skills"]),
            "command": f"bin/governance advance {phase} . --json",
            "writes_state": True,
            "requires": f"advance-{phase}-check ok:true",
            "description": f"record {metadata['description']}",
        },
    ]


def _copy_actions(actions: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    payload = [deepcopy(action) for action in actions]
    for action in payload:
        if isinstance(action.get("skills"), tuple):
            action["skills"] = list(action["skills"])
    return payload
