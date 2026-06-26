from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .state import load_state
    from .verify_governance import verify
except ImportError:  # pragma: no cover - direct script execution
    from state import load_state
    from verify_governance import verify


GATE_NAMES = ("product-structuring", "design-derivation", "implementation")


@dataclass
class GateRequirement:
    code: str
    ok: bool
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "ok": self.ok,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class GateResult:
    gate: str
    target: str
    ok: bool
    requirements: list[GateRequirement] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate": self.gate,
            "target": self.target,
            "ok": self.ok,
            "requirements": [item.to_dict() for item in self.requirements],
            "verification": self.verification,
            "state": self.state,
        }


def evaluate_gate(root: Path, gate: str) -> GateResult:
    if gate not in GATE_NAMES:
        raise ValueError(f"unknown gate: {gate}")
    root = root.resolve()
    state = load_state(root)
    report = verify(root)
    requirements: list[GateRequirement] = []

    _add(requirements, "state_present", bool(state), ".governance/state.json", "governance state exists")
    _add(requirements, "verification_passed", report.ok, "", "governance verification passes")

    _add_product_import_requirements(requirements, root)
    if gate in {"design-derivation", "implementation"}:
        _add(requirements, "product_chapters_present", _has_product_chapter(root), "docs/product", "product chapters exist")
    if gate == "implementation":
        _add_implementation_requirements(requirements, root)

    return GateResult(
        gate=gate,
        target=str(root),
        ok=all(item.ok for item in requirements),
        requirements=requirements,
        verification={
            "ok": report.ok,
            "errors": report.errors,
            "warnings": report.warnings,
            "findings": [finding.to_dict() for finding in report.findings],
        },
        state=state,
    )


def _add(requirements: list[GateRequirement], code: str, ok: bool, path: str, message: str) -> None:
    requirements.append(GateRequirement(code=code, ok=ok, path=path, message=message))


def _add_product_import_requirements(requirements: list[GateRequirement], root: Path) -> None:
    manifest = _load_product_source_manifest(root)
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    archive = manifest.get("archive") if isinstance(manifest.get("archive"), dict) else {}
    imported = manifest.get("import") if isinstance(manifest.get("import"), dict) else {}
    _add(
        requirements,
        "product_source_present",
        source.get("provided") is True and bool(archive.get("path")),
        "docs/product/core/source/source-manifest.json",
        "product source is archived",
    )
    _add(
        requirements,
        "product_import_ready",
        imported.get("status") == "ready_for_structuring" and imported.get("can_derive_design") is True,
        "docs/product/core/source/source-manifest.json",
        "product import is ready for downstream derivation",
    )


def _load_product_source_manifest(root: Path) -> dict[str, Any]:
    path = root / "docs/product/core/source/source-manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _add_implementation_requirements(requirements: list[GateRequirement], root: Path) -> None:
    for domain, message in [
        ("architecture", "architecture docs exist"),
        ("api", "API contract docs exist"),
        ("backend", "backend design docs exist"),
        ("tests", "test strategy docs exist"),
        ("development", "development plan docs exist"),
    ]:
        _add(requirements, f"{domain}_docs_present", _has_authored_markdown(root / "docs" / domain), f"docs/{domain}", message)


def _has_product_chapter(root: Path) -> bool:
    product_root = root / "docs/product"
    return any(path.is_file() for path in product_root.glob("[0-9][0-9]-*.md"))


def _has_authored_markdown(directory: Path) -> bool:
    if not directory.exists():
        return False
    for path in directory.rglob("*.md"):
        if path.name in {"README.md", "AGENTS.md"} or path.name.startswith("_"):
            continue
        return True
    return False
