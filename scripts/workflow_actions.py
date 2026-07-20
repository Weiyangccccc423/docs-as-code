from __future__ import annotations

from copy import deepcopy
from typing import Any


TARGET_WORKFLOW_ROOT = "docs/agent-workflow/workflow-pack"
CONVERTIBLE_PRODUCT_SUFFIXES = {".docx", ".html", ".htm", ".pdf", ".txt"}
RECORDED_CONVERSION_METHODS = {
    "pandoc-docx-to-gfm",
    "pandoc-html-to-gfm",
    "pdftotext-pdf-to-utf8-text",
    "utf8-text-to-markdown",
}

PRODUCT_CONVERSION_ACTIONS: tuple[dict[str, object], ...] = (
    {
        "id": "product-convert-check",
        "kind": "preflight",
        "phase": "product-document-archiving",
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/02-product-document-archiving.md",
        "skills": ("archiving-product-document", "verifying-governance-docs"),
        "command": "bin/governance product convert . --check --json",
        "argv": ("bin/governance", "product", "convert", ".", "--check", "--json"),
        "writes_state": False,
        "approval_required": False,
        "requires": "the archived TXT, DOCX, HTML, or PDF source passes hash and converter preflight",
        "sequence": 1,
        "preflight_for": "product-convert",
        "success_condition": "ok:true",
        "description": "preview source-preserving product conversion without writing target files",
    },
    {
        "id": "product-convert",
        "kind": "apply",
        "phase": "product-document-archiving",
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/02-product-document-archiving.md",
        "skills": ("archiving-product-document", "verifying-governance-docs"),
        "command": "bin/governance product convert . --json",
        "argv": ("bin/governance", "product", "convert", ".", "--json"),
        "writes_state": True,
        "approval_required": False,
        "requires": "product-convert-check ok:true",
        "sequence": 2,
        "requires_action": "product-convert-check",
        "success_condition": "ok:true",
        "description": "write reviewable Markdown and hash-bound conversion evidence",
    },
)

PRODUCT_IMPORT_ACTIONS: tuple[dict[str, object], ...] = (
    {
        "id": "product-mark-ready-check",
        "kind": "preflight",
        "phase": "product-document-archiving",
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/02-product-document-archiving.md",
        "skills": ("archiving-product-document", "verifying-governance-docs"),
        "command": "bin/governance product mark-ready . --reviewed --method manual-reviewed-markdown --check --json",
        "argv": (
            "bin/governance",
            "product",
            "mark-ready",
            ".",
            "--reviewed",
            "--method",
            "manual-reviewed-markdown",
            "--check",
            "--json",
        ),
        "writes_state": False,
        "approval_required": False,
        "requires": "docs/product/core/PRD.md has been manually reviewed against the archived source",
        "sequence": 1,
        "preflight_for": "product-mark-ready",
        "success_condition": "ok:true",
        "description": "preview product import readiness closeout before allowing downstream derivation",
    },
    {
        "id": "product-mark-ready",
        "kind": "apply",
        "phase": "product-document-archiving",
        "workflow": f"{TARGET_WORKFLOW_ROOT}/workflows/02-product-document-archiving.md",
        "skills": ("archiving-product-document", "verifying-governance-docs"),
        "command": "bin/governance product mark-ready . --reviewed --method manual-reviewed-markdown --json",
        "argv": (
            "bin/governance",
            "product",
            "mark-ready",
            ".",
            "--reviewed",
            "--method",
            "manual-reviewed-markdown",
            "--json",
        ),
        "writes_state": True,
        "approval_required": False,
        "requires": "product-mark-ready-check ok:true",
        "sequence": 2,
        "requires_action": "product-mark-ready-check",
        "success_condition": "ok:true",
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
            "configuring-project-runtime",
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


def next_actions_payload(state: dict[str, Any], cwd: str = ".") -> list[dict[str, object]]:
    if not isinstance(state, dict):
        raise ValueError("workflow action state must be an object")
    if not isinstance(cwd, str) or not cwd.strip():
        raise ValueError("workflow action cwd must be a non-empty string")
    phase = state.get("phase")
    if phase == "initialized" and state.get("product_import_status") != "ready_for_structuring":
        if _product_conversion_pending(state):
            return _copy_actions(PRODUCT_CONVERSION_ACTIONS, cwd)
        return _product_mark_ready_actions(state, cwd)
    next_phase = _next_phase(phase)
    if not next_phase:
        return []
    return _advance_actions(next_phase, cwd)


def _next_phase(phase: object) -> str:
    if not isinstance(phase, str) or phase not in PHASE_ORDER:
        return ""
    index = PHASE_ORDER.index(phase)
    if index >= len(PHASE_ORDER) - 1:
        return ""
    return PHASE_ORDER[index + 1]


def _product_conversion_pending(state: dict[str, Any]) -> bool:
    if state.get("product_conversion_status") in {"pending_review", "reviewed"}:
        return False
    archived = state.get("archived_product")
    if not isinstance(archived, str) or not archived:
        return False
    suffix = "." + archived.rsplit(".", 1)[-1].lower() if "." in archived else ""
    return suffix in CONVERTIBLE_PRODUCT_SUFFIXES


def _product_mark_ready_actions(state: dict[str, Any], cwd: str) -> list[dict[str, object]]:
    actions = _copy_actions(PRODUCT_IMPORT_ACTIONS, cwd)
    conversion_method = state.get("product_conversion_method")
    if not isinstance(conversion_method, str) or conversion_method not in RECORDED_CONVERSION_METHODS:
        return actions
    review_method = f"reviewed-{conversion_method}"
    for action in actions:
        argv = action.get("argv")
        if not isinstance(argv, list):
            continue
        method_index = argv.index("--method") + 1
        argv[method_index] = review_method
        action["command"] = _command_text(argv)
    return actions


def _advance_actions(phase: str, cwd: str) -> list[dict[str, object]]:
    metadata = PHASE_ACTIONS[phase]
    preflight_argv = ["bin/governance", "advance", phase, ".", "--check", "--json"]
    apply_argv = ["bin/governance", "advance", phase, ".", "--json"]
    return [
        {
            "id": f"advance-{phase}-check",
            "kind": "preflight",
            "cwd": cwd,
            "phase": phase,
            "workflow": metadata["workflow"],
            "skills": list(metadata["skills"]),
            "command": _command_text(preflight_argv),
            "argv": preflight_argv,
            "writes_state": False,
            "approval_required": False,
            "requires": "current phase is the previous workflow phase and the gate can pass",
            "sequence": 1,
            "preflight_for": f"advance-{phase}",
            "success_condition": "ok:true",
            "description": f"preflight {metadata['description']}",
        },
        {
            "id": f"advance-{phase}",
            "kind": "apply",
            "cwd": cwd,
            "phase": phase,
            "workflow": metadata["workflow"],
            "skills": list(metadata["skills"]),
            "command": _command_text(apply_argv),
            "argv": apply_argv,
            "writes_state": True,
            "approval_required": False,
            "requires": f"advance-{phase}-check ok:true",
            "sequence": 2,
            "requires_action": f"advance-{phase}-check",
            "success_condition": "ok:true",
            "description": f"record {metadata['description']}",
        },
    ]


def _copy_actions(actions: tuple[dict[str, object], ...], cwd: str) -> list[dict[str, object]]:
    payload = [deepcopy(action) for action in actions]
    for action in payload:
        action["cwd"] = cwd
        if isinstance(action.get("skills"), tuple):
            action["skills"] = list(action["skills"])
        if isinstance(action.get("argv"), tuple):
            action["argv"] = list(action["argv"])
    return payload


def _command_text(argv: list[str]) -> str:
    return " ".join(argv)
