from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .bootstrap_tree import _product_meta
    from .state import merge_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import _product_meta
    from state import merge_state, utc_now


MANIFEST_REL = Path("docs/product/core/source/source-manifest.json")
PRD_REL = Path("docs/product/core/PRD.md")
PRODUCT_META_REL = Path("docs/product/core/product-meta.md")
UNRESOLVED_REL = Path("docs/unresolved.md")
PRODUCT_SOURCE_ARCHIVE_ROOT = Path("docs/product/core/source")
CONVERSION_BLOCKER_ID = "U-001"
CONVERSION_BLOCKER_DOMAIN = "Product Archiving"
CONVERSION_PLACEHOLDER_MARKERS = (
    "## Conversion Required",
    "当前输入不是 Markdown",
    "转换完成前",
    "不得基于本文件派生 API",
)
DISALLOWED_READY_METHODS = {"", "none", "conversion-required"}


@dataclass
class ProductImportReadyResult:
    target: str
    ok: bool
    reviewed: bool
    method: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    conversion_blocker_resolved: bool = False
    manifest: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "reviewed": self.reviewed,
            "method": self.method,
            "errors": self.errors,
            "warnings": self.warnings,
            "updated": self.updated,
            "conversion_blocker_resolved": self.conversion_blocker_resolved,
            "manifest": self.manifest,
            "state": self.state,
        }


def mark_product_import_ready(root: Path, method: str = "manual-reviewed-markdown", reviewed: bool = False) -> ProductImportReadyResult:
    root = root.resolve()
    method = method.strip()
    errors: list[str] = []
    warnings: list[str] = []
    manifest = _load_manifest(root, errors)
    imported = manifest.get("import") if isinstance(manifest.get("import"), dict) else {}

    if not reviewed:
        errors.append("manual review confirmation is required")
    if method.lower() in DISALLOWED_READY_METHODS:
        errors.append("conversion method must describe the reviewed Markdown import")
    _check_prd_ready(root, errors)
    _check_archived_source(root, manifest, errors)
    if imported.get("status") == "no_source":
        errors.append("product source is missing; cannot mark import ready")

    if errors:
        return ProductImportReadyResult(
            target=str(root),
            ok=False,
            reviewed=reviewed,
            method=method,
            errors=errors,
            warnings=warnings,
            manifest=manifest,
        )

    reviewed_at = utc_now()
    imported["status"] = "ready_for_structuring"
    imported["conversion_method"] = method
    imported["can_derive_design"] = True
    imported["reviewed_at"] = reviewed_at
    manifest["import"] = imported

    updated: list[str] = []
    _write_json(root / MANIFEST_REL, manifest)
    updated.append(MANIFEST_REL.as_posix())
    _write_text(root / PRODUCT_META_REL, _product_meta(manifest))
    updated.append(PRODUCT_META_REL.as_posix())
    blocker_resolved = _resolve_conversion_blocker(root / UNRESOLVED_REL)
    if blocker_resolved:
        updated.append(UNRESOLVED_REL.as_posix())
    else:
        warnings.append(f"{CONVERSION_BLOCKER_ID} conversion blocker was not found or was already resolved")

    state = merge_state(
        root,
        product_import_status="ready_for_structuring",
        product_can_derive_design=True,
        product_conversion_method=method,
        product_conversion_reviewed_at=reviewed_at,
    )
    updated.append(".governance/state.json")

    return ProductImportReadyResult(
        target=str(root),
        ok=True,
        reviewed=reviewed,
        method=method,
        warnings=warnings,
        updated=updated,
        conversion_blocker_resolved=blocker_resolved,
        manifest=manifest,
        state=state,
    )


def _load_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    path = root / MANIFEST_REL
    if not path.exists():
        errors.append(f"missing product source manifest: {MANIFEST_REL.as_posix()}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        errors.append(f"invalid product source manifest: {error.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append("invalid product source manifest: root must be an object")
        return {}
    imported = payload.get("import")
    if not isinstance(imported, dict):
        errors.append("invalid product source manifest: missing import object")
    return payload


def _check_prd_ready(root: Path, errors: list[str]) -> None:
    path = root / PRD_REL
    if not path.exists():
        errors.append(f"missing reviewed PRD: {PRD_REL.as_posix()}")
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{PRD_REL.as_posix()} must be UTF-8 Markdown")
        return
    if not text.strip():
        errors.append(f"{PRD_REL.as_posix()} is empty")
        return
    if any(marker in text for marker in CONVERSION_PLACEHOLDER_MARKERS):
        errors.append(f"{PRD_REL.as_posix()} still contains the conversion placeholder")


def _check_archived_source(root: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    archive = manifest.get("archive")
    if not isinstance(archive, dict):
        errors.append("invalid product source manifest: missing archive object")
        return
    archived_rel = archive.get("path")
    if not isinstance(archived_rel, str) or not archived_rel:
        errors.append("invalid product source manifest: archive.path is missing")
        return
    if not _is_valid_product_source_archive_path(archived_rel):
        errors.append("invalid product source manifest: archive.path must be a relative path under docs/product/core/source")
        return
    archived_path = root / archived_rel
    if not archived_path.exists():
        errors.append(f"archived product source is missing: {archived_rel}")
        return
    if not archived_path.is_file():
        errors.append(f"invalid product source manifest: archive.path does not point to a file: {archived_rel}")
        return
    expected_size = archive.get("size_bytes")
    if not _is_valid_manifest_size(expected_size):
        errors.append("invalid product source manifest: archive.size_bytes is missing or invalid")
    elif archived_path.stat().st_size != expected_size:
        errors.append(f"archived product source size mismatch: {archived_rel}")
    expected_hash = archive.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        errors.append("invalid product source manifest: archive.sha256 is missing")
        return
    if _sha256(archived_path) != expected_hash:
        errors.append(f"archived product source hash mismatch: {archived_rel}")


def _is_valid_product_source_archive_path(value: str) -> bool:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        path.relative_to(PRODUCT_SOURCE_ARCHIVE_ROOT)
    except ValueError:
        return False
    return path != PRODUCT_SOURCE_ARCHIVE_ROOT


def _is_valid_manifest_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _resolve_conversion_blocker(path: Path) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = _find_unresolved_table_header(lines)
    if header_index is None:
        return False
    header = [_normalize_cell(cell) for cell in _split_table_row(lines[header_index])]
    try:
        id_index = header.index("id")
        domain_index = header.index("domain")
        blocking_index = header.index("blocking scope")
    except ValueError:
        return False

    changed = False
    for index in range(header_index + 1, len(lines)):
        line = lines[index]
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_table_row(line)
        if _is_separator_row(cells):
            continue
        if len(cells) <= max(id_index, domain_index, blocking_index):
            continue
        if cells[id_index].strip() != CONVERSION_BLOCKER_ID:
            continue
        if cells[domain_index].strip() != CONVERSION_BLOCKER_DOMAIN:
            continue
        if _normalize_cell(cells[blocking_index]) == "resolved":
            continue
        cells[blocking_index] = "resolved"
        lines[index] = _join_table_row(cells)
        changed = True
    if changed:
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return changed


def _find_unresolved_table_header(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        cells = [_normalize_cell(cell) for cell in _split_table_row(line)]
        if {"id", "domain", "blocking scope"}.issubset(set(cells)):
            return index
    return None


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _join_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _is_separator_row(cells: list[str]) -> bool:
    return all(cell.replace("-", "").replace(":", "").strip() == "" for cell in cells)


def _normalize_cell(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
