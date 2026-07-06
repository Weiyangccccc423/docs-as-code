from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .bootstrap_tree import _product_meta, target_local_commands_payload
    from .state import STATE_REL, StateFileError, load_state, merge_state, utc_now
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import _product_meta, target_local_commands_payload
    from state import STATE_REL, StateFileError, load_state, merge_state, utc_now
    from workflow_actions import next_actions_payload


MANIFEST_REL = Path("docs/product/core/source/source-manifest.json")
PRD_REL = Path("docs/product/core/PRD.md")
PRODUCT_META_REL = Path("docs/product/core/product-meta.md")
UNRESOLVED_REL = Path("docs/unresolved.md")
PRODUCT_SOURCE_ARCHIVE_ROOT = Path("docs/product/core/source")
PRODUCT_SOURCE_MANIFEST_SCHEMA_VERSION = 1
PRODUCT_IMPORT_STATUSES = ("conversion_required", "no_source", "ready_for_structuring")
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
    check: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    conversion_blocker_resolved: bool = False
    would_resolve_conversion_blocker: bool = False
    manifest: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("product import result target must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise ValueError("product import result ok must be a boolean")
        if not isinstance(self.reviewed, bool):
            raise ValueError("product import result reviewed must be a boolean")
        if not isinstance(self.method, str) or not self.method:
            raise ValueError("product import result method must be a non-empty string")
        if not isinstance(self.check, bool):
            raise ValueError("product import result check must be a boolean")
        if not isinstance(self.errors, list) or not all(isinstance(item, str) for item in self.errors):
            raise ValueError("product import result errors must be strings")
        if not isinstance(self.warnings, list) or not all(isinstance(item, str) for item in self.warnings):
            raise ValueError("product import result warnings must be strings")
        _validate_product_import_path_list("updated", self.updated)
        _validate_product_import_path_list("would_update", self.would_update)
        if not isinstance(self.conversion_blocker_resolved, bool):
            raise ValueError("product import result conversion_blocker_resolved must be a boolean")
        if not isinstance(self.would_resolve_conversion_blocker, bool):
            raise ValueError("product import result would_resolve_conversion_blocker must be a boolean")
        if not isinstance(self.manifest, dict):
            raise ValueError("product import result manifest must be an object")
        if not isinstance(self.state, dict):
            raise ValueError("product import result state must be an object")
        if self.check and (self.updated or self.conversion_blocker_resolved):
            raise ValueError("product import result check mode cannot contain write outputs")
        if not self.check and (self.would_update or self.would_resolve_conversion_blocker):
            raise ValueError("product import result write mode cannot contain would outputs")
        if self.ok and self.errors:
            raise ValueError("product import result ok cannot include errors")
        if not self.ok and not self.errors:
            raise ValueError("product import result failure requires errors")
        self.errors = list(self.errors)
        self.warnings = list(self.warnings)
        self.updated = list(self.updated)
        self.would_update = list(self.would_update)
        self.manifest = copy.deepcopy(self.manifest)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "reviewed": self.reviewed,
            "method": self.method,
            "check": self.check,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "updated": list(self.updated),
            "would_update": list(self.would_update),
            "conversion_blocker_resolved": self.conversion_blocker_resolved,
            "would_resolve_conversion_blocker": self.would_resolve_conversion_blocker,
            "manifest": copy.deepcopy(self.manifest),
            "state": copy.deepcopy(self.state),
        }


def _validate_product_import_path_list(field_name: str, paths: object) -> None:
    if not isinstance(paths, list):
        raise ValueError(f"product import result {field_name} must be a list")
    if not all(isinstance(path, str) for path in paths):
        raise ValueError(f"product import result {field_name} paths must be strings")
    if len(paths) != len(set(paths)):
        raise ValueError(f"product import result {field_name} paths must be unique")
    for path in paths:
        posix_path = PurePosixPath(path)
        windows_path = PureWindowsPath(path)
        normalized_path = posix_path.as_posix()
        if (
            not path
            or path == "."
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError(f"product import result {field_name} paths must be repository-relative")
        if "\\" in path or path != normalized_path:
            raise ValueError(f"product import result {field_name} paths must use normalized POSIX form")


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: bytes = b""


@dataclass
class _ProductImportReadyPlan:
    target: str
    reviewed: bool
    method: str
    errors: list[str]
    warnings: list[str]
    manifest: dict[str, Any]
    reviewed_at: str = ""
    would_update: list[str] = field(default_factory=list)
    would_resolve_conversion_blocker: bool = False
    state: dict[str, Any] = field(default_factory=dict)


def check_product_import_ready(
    root: Path,
    method: str = "manual-reviewed-markdown",
    reviewed: bool = False,
) -> ProductImportReadyResult:
    plan = _build_product_import_ready_plan(root, method=method, reviewed=reviewed)
    return ProductImportReadyResult(
        target=plan.target,
        ok=not plan.errors,
        reviewed=plan.reviewed,
        method=plan.method,
        check=True,
        errors=plan.errors,
        warnings=plan.warnings,
        would_update=plan.would_update,
        would_resolve_conversion_blocker=plan.would_resolve_conversion_blocker,
        manifest=plan.manifest,
        state=plan.state,
    )


def mark_product_import_ready(root: Path, method: str = "manual-reviewed-markdown", reviewed: bool = False) -> ProductImportReadyResult:
    root = root.resolve()
    plan = _build_product_import_ready_plan(root, method=method, reviewed=reviewed)
    if plan.errors:
        return ProductImportReadyResult(
            target=plan.target,
            ok=False,
            reviewed=plan.reviewed,
            method=plan.method,
            errors=plan.errors,
            warnings=plan.warnings,
            manifest=plan.manifest,
            state=plan.state,
        )

    original_manifest = _load_manifest(root, [])
    manifest = copy.deepcopy(plan.manifest)
    warnings = list(plan.warnings)
    errors: list[str] = []
    updated: list[str] = []
    blocker_resolved = False
    state: dict[str, Any] = {}
    snapshots: dict[str, _FileSnapshot] = {}
    try:
        snapshots = _snapshot_files(root, (MANIFEST_REL, PRODUCT_META_REL, UNRESOLVED_REL))
        _write_json(root / MANIFEST_REL, manifest)
        updated.append(MANIFEST_REL.as_posix())
        _write_text(root / PRODUCT_META_REL, _product_meta(manifest))
        updated.append(PRODUCT_META_REL.as_posix())
        blocker_resolved = _resolve_conversion_blocker(root / UNRESOLVED_REL)
        if blocker_resolved:
            updated.append(UNRESOLVED_REL.as_posix())
        elif plan.would_resolve_conversion_blocker:
            warnings.append(f"{CONVERSION_BLOCKER_ID} conversion blocker was not found or was already resolved")

        state = merge_state(
            root,
            product_import_status="ready_for_structuring",
            product_can_derive_design=True,
            product_conversion_method=plan.method,
            product_conversion_reviewed_at=plan.reviewed_at,
        )
        updated.append(".governance/state.json")
    except OSError as error:
        errors.append(f"failed to update product import readiness: {_os_error_reason(error)}")
    except StateFileError as error:
        errors.append(f"failed to update product import readiness: {error}")

    if errors:
        rollback_errors = _rollback_updated_files(root, snapshots, updated)
        errors.extend(rollback_errors)
        if UNRESOLVED_REL.as_posix() not in updated:
            blocker_resolved = False
        result_manifest = manifest if MANIFEST_REL.as_posix() in updated else original_manifest
        return ProductImportReadyResult(
            target=str(root),
            ok=False,
            reviewed=plan.reviewed,
            method=plan.method,
            errors=errors,
            warnings=warnings,
            updated=updated,
            conversion_blocker_resolved=blocker_resolved,
            manifest=result_manifest,
            state=state,
        )

    return ProductImportReadyResult(
        target=str(root),
        ok=True,
        reviewed=plan.reviewed,
        method=plan.method,
        warnings=warnings,
        updated=updated,
        conversion_blocker_resolved=blocker_resolved,
        manifest=manifest,
        state=state,
    )


def _build_product_import_ready_plan(
    root: Path,
    method: str = "manual-reviewed-markdown",
    reviewed: bool = False,
) -> _ProductImportReadyPlan:
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
    _check_conversion_blocker_registry(root, errors)
    _check_output_targets(root, errors)
    if imported.get("status") == "no_source":
        errors.append("product source is missing; cannot mark import ready")

    state = _load_current_state(root) if not errors else {}
    if errors:
        return _ProductImportReadyPlan(
            target=str(root),
            reviewed=reviewed,
            method=method,
            errors=errors,
            warnings=warnings,
            manifest=manifest,
            state=state,
        )

    planned_manifest = copy.deepcopy(manifest)
    planned_imported = planned_manifest.get("import")
    if not isinstance(planned_imported, dict):
        planned_imported = {}
    reviewed_at = utc_now()
    planned_imported["status"] = "ready_for_structuring"
    planned_imported["conversion_method"] = method
    planned_imported["can_derive_design"] = True
    planned_imported["reviewed_at"] = reviewed_at
    planned_manifest["import"] = planned_imported

    would_resolve = _conversion_blocker_would_resolve(root / UNRESOLVED_REL)
    if not would_resolve:
        warnings.append(f"{CONVERSION_BLOCKER_ID} conversion blocker was not found or was already resolved")
    would_update = [
        MANIFEST_REL.as_posix(),
        PRODUCT_META_REL.as_posix(),
    ]
    if would_resolve:
        would_update.append(UNRESOLVED_REL.as_posix())
    would_update.append(STATE_REL.as_posix())

    return _ProductImportReadyPlan(
        target=str(root),
        reviewed=reviewed,
        method=method,
        errors=errors,
        warnings=warnings,
        manifest=planned_manifest,
        reviewed_at=reviewed_at,
        would_update=would_update,
        would_resolve_conversion_blocker=would_resolve,
        state=state,
    )


def _snapshot_files(root: Path, rels: tuple[Path, ...]) -> dict[str, _FileSnapshot]:
    snapshots: dict[str, _FileSnapshot] = {}
    for rel in rels:
        path = root / rel
        if path.exists():
            snapshots[rel.as_posix()] = _FileSnapshot(exists=True, content=path.read_bytes())
        else:
            snapshots[rel.as_posix()] = _FileSnapshot(exists=False)
    return snapshots


def _rollback_updated_files(root: Path, snapshots: dict[str, _FileSnapshot], updated: list[str]) -> list[str]:
    rollback_errors: list[str] = []
    for rel_posix in list(reversed(updated)):
        snapshot = snapshots.get(rel_posix)
        if snapshot is None:
            continue
        try:
            _restore_file(root / rel_posix, snapshot)
        except OSError as error:
            rollback_errors.append(f"failed to rollback {rel_posix}: {_os_error_reason(error)}")
        else:
            updated.remove(rel_posix)
    return rollback_errors


def _restore_file(path: Path, snapshot: _FileSnapshot) -> None:
    if snapshot.exists:
        _write_atomic_bytes(path, snapshot.content)
        return
    if path.exists():
        path.unlink()


def _load_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    path = root / MANIFEST_REL
    if not path.exists():
        errors.append(f"missing product source manifest: {MANIFEST_REL.as_posix()}")
        return {}
    if not path.is_file():
        errors.append(f"product source manifest is not a file: {MANIFEST_REL.as_posix()}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        errors.append("invalid product source manifest encoding: expected UTF-8")
        return {}
    except OSError as error:
        errors.append(f"product source manifest is unreadable: {_os_error_reason(error)}")
        return {}
    except json.JSONDecodeError as error:
        errors.append(f"invalid product source manifest: {error.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append("invalid product source manifest: root must be an object")
        return {}
    if payload.get("schema_version") != PRODUCT_SOURCE_MANIFEST_SCHEMA_VERSION:
        errors.append(f"product source manifest schema_version must be {PRODUCT_SOURCE_MANIFEST_SCHEMA_VERSION}")
    source = payload.get("source")
    if not isinstance(source, dict):
        errors.append("invalid product source manifest: missing source object")
    elif source.get("provided") is not True:
        errors.append("invalid product source manifest: source.provided must be true when product source is archived")
    else:
        original_path_error = _product_source_original_path_error(source.get("original_path"), source.get("filename"))
        if original_path_error is not None:
            errors.append(original_path_error)
    imported = payload.get("import")
    if not isinstance(imported, dict):
        errors.append("invalid product source manifest: missing import object")
    else:
        status = imported.get("status")
        if not isinstance(status, str) or status not in PRODUCT_IMPORT_STATUSES:
            errors.append(
                f"invalid product import status: {status}; expected one of {', '.join(PRODUCT_IMPORT_STATUSES)}"
            )
        if imported.get("prd_path") != PRD_REL.as_posix():
            errors.append(f"invalid product source manifest: import.prd_path must be {PRD_REL.as_posix()}")
        conversion_method = imported.get("conversion_method")
        if not isinstance(conversion_method, str) or not conversion_method.strip():
            errors.append("invalid product source manifest: import.conversion_method must be a non-empty string")
        can_derive_design = imported.get("can_derive_design")
        if not isinstance(can_derive_design, bool):
            errors.append("invalid product source manifest: import.can_derive_design must be a boolean")
        if status == "ready_for_structuring" and can_derive_design is not True:
            errors.append("product import status ready_for_structuring requires can_derive_design: true")
        if status == "conversion_required" and can_derive_design is True:
            errors.append("product import status conversion_required requires can_derive_design: false")
    return payload


def _check_prd_ready(root: Path, errors: list[str]) -> None:
    path = root / PRD_REL
    if not path.exists():
        errors.append(f"missing reviewed PRD: {PRD_REL.as_posix()}")
        return
    if not path.is_file():
        errors.append(f"reviewed PRD is not a file: {PRD_REL.as_posix()}")
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{PRD_REL.as_posix()} must be UTF-8 Markdown")
        return
    except OSError as error:
        errors.append(f"{PRD_REL.as_posix()} is unreadable: {_os_error_reason(error)}")
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
    source = manifest.get("source")
    if isinstance(source, dict):
        filename_error = _product_source_filename_error(source.get("filename"), archived_rel)
        if filename_error is not None:
            errors.append(filename_error)
        suffix_error = _product_source_suffix_error(source.get("suffix"), source.get("filename"))
        if suffix_error is not None:
            errors.append(suffix_error)
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
    else:
        try:
            actual_size = archived_path.stat().st_size
        except OSError as error:
            errors.append(f"archived product source is unreadable: {archived_rel}: {_os_error_reason(error)}")
            return
        if actual_size != expected_size:
            errors.append(f"archived product source size mismatch: {archived_rel}")
    if isinstance(source, dict):
        source_size = source.get("size_bytes")
        if not _is_valid_manifest_size(source_size):
            errors.append("invalid product source manifest: source.size_bytes is missing or invalid")
        elif _is_valid_manifest_size(expected_size) and source_size != expected_size:
            errors.append("invalid product source manifest: source.size_bytes does not match archive.size_bytes")
    expected_hash = archive.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        errors.append("invalid product source manifest: archive.sha256 is missing")
        return
    if not _is_valid_sha256_digest(expected_hash):
        errors.append("invalid product source manifest: archive.sha256 must be a lowercase SHA-256 hex digest")
        return
    try:
        actual_hash = _sha256(archived_path)
    except OSError as error:
        errors.append(f"archived product source is unreadable: {archived_rel}: {_os_error_reason(error)}")
        return
    if actual_hash != expected_hash:
        errors.append(f"archived product source hash mismatch: {archived_rel}")
    if isinstance(source, dict):
        source_hash = source.get("sha256")
        if not isinstance(source_hash, str) or not source_hash:
            errors.append("invalid product source manifest: source.sha256 is missing")
        elif not _is_valid_sha256_digest(source_hash):
            errors.append("invalid product source manifest: source.sha256 must be a lowercase SHA-256 hex digest")
        elif source_hash != expected_hash:
            errors.append("invalid product source manifest: source.sha256 does not match archive.sha256")


def _check_conversion_blocker_registry(root: Path, errors: list[str]) -> None:
    path = root / UNRESOLVED_REL
    if not path.exists():
        return
    if not path.is_file():
        errors.append(f"{UNRESOLVED_REL.as_posix()} is not a file; cannot resolve conversion blocker")
        return
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{UNRESOLVED_REL.as_posix()} must be UTF-8 Markdown to resolve conversion blocker")
    except OSError as error:
        errors.append(f"{UNRESOLVED_REL.as_posix()} is unreadable; cannot resolve conversion blocker: {_os_error_reason(error)}")


def _check_output_targets(root: Path, errors: list[str]) -> None:
    _check_atomic_output_target(root, MANIFEST_REL, "product source manifest", errors)
    _check_atomic_output_target(root, PRODUCT_META_REL, "product metadata", errors)
    _check_atomic_output_target(root, STATE_REL, "product import state", errors)
    _check_state_readable(root, errors)
    if (root / UNRESOLVED_REL).exists():
        _check_atomic_output_target(root, UNRESOLVED_REL, "conversion blocker registry", errors)


def _check_state_readable(root: Path, errors: list[str]) -> None:
    path = root / STATE_REL
    if not path.exists() or not path.is_file():
        return
    try:
        load_state(root)
    except StateFileError as error:
        errors.append(f"product import state is invalid: {error}")


def _load_current_state(root: Path) -> dict[str, Any]:
    path = root / STATE_REL
    if not path.exists() or not path.is_file():
        return {}
    try:
        return load_state(root)
    except StateFileError:
        return {}


def _check_atomic_output_target(root: Path, rel: Path, label: str, errors: list[str]) -> None:
    path = root / rel
    if path.parent.exists() and not path.parent.is_dir():
        errors.append(f"{path.parent.relative_to(root).as_posix()} is not a directory; cannot update {label}")
        return
    if path.exists() and not path.is_file():
        errors.append(f"{rel.as_posix()} is not a file; cannot update {label}")
        return
    temp = _atomic_temp_path(path)
    if temp.exists() and not temp.is_file():
        errors.append(f"{temp.relative_to(root).as_posix()} is not a file; cannot prepare {label}")


def _is_valid_product_source_archive_path(value: str) -> bool:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        path.relative_to(PRODUCT_SOURCE_ARCHIVE_ROOT)
    except ValueError:
        return False
    return path not in {PRODUCT_SOURCE_ARCHIVE_ROOT, MANIFEST_REL, _atomic_temp_path(MANIFEST_REL)}


def _product_source_filename_error(value: object, archived_rel: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "invalid product source manifest: source.filename is missing"
    if not _is_safe_basename(value):
        return "invalid product source manifest: source.filename must be a plain filename"
    if value != PurePosixPath(archived_rel).name:
        return "invalid product source manifest: source.filename must match archive.path filename"
    return None


def _product_source_suffix_error(value: object, filename: object) -> str | None:
    if not isinstance(value, str) or not value:
        return "invalid product source manifest: source.suffix is missing"
    if not value.startswith(".") or "/" in value or "\\" in value or value != value.lower():
        return "invalid product source manifest: source.suffix must be a lowercase file suffix"
    if isinstance(filename, str) and _is_safe_basename(filename) and value != PurePosixPath(filename).suffix.lower():
        return "invalid product source manifest: source.suffix must match source.filename suffix"
    return None


def _product_source_original_path_error(value: object, filename: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "invalid product source manifest: source.original_path must be a non-empty string"
    if isinstance(filename, str) and _is_safe_basename(filename) and not _path_leaf_matches_filename(value, filename):
        return "invalid product source manifest: source.original_path filename must match source.filename"
    return None


def _path_leaf_matches_filename(path_value: str, filename: str) -> bool:
    leaf_names = {PurePosixPath(path_value).name, PureWindowsPath(path_value).name}
    return filename in leaf_names


def _is_safe_basename(value: str) -> bool:
    if "/" in value or "\\" in value or value.startswith("~"):
        return False
    windows = PureWindowsPath(value)
    if windows.is_absolute() or windows.drive:
        return False
    posix = PurePosixPath(value)
    return bool(posix.name) and posix.name == value and posix.as_posix() == value


def _is_valid_manifest_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_valid_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _resolve_conversion_blocker(path: Path) -> bool:
    if not path.exists():
        return False
    if not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
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
        _write_text(path, "\n".join(lines).rstrip() + "\n")
    return changed


def _conversion_blocker_would_resolve(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
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

    for line in lines[header_index + 1 :]:
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
        return True
    return False


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
    _write_atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, content: str) -> None:
    _write_atomic_text(path, content)


def _write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _atomic_temp_path(path)
    try:
        temp.write_text(content, encoding="utf-8")
        temp.replace(path)
    except OSError:
        if temp.exists() and temp.is_file():
            try:
                temp.unlink()
            except OSError:
                pass
        raise


def _write_atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _atomic_temp_path(path)
    try:
        temp.write_bytes(content)
        temp.replace(path)
    except OSError:
        if temp.exists() and temp.is_file():
            try:
                temp.unlink()
            except OSError:
                pass
        raise


def _atomic_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _os_error_reason(error: OSError) -> str:
    return error.strerror or error.__class__.__name__


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage docs-as-code product document import readiness.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    mark_ready = subparsers.add_parser("mark-ready", help="Mark reviewed product import ready for structuring.")
    mark_ready.add_argument("target", nargs="?", default=".", help="Repository root to update.")
    mark_ready.add_argument("--reviewed", action="store_true", help="Confirm PRD was manually reviewed.")
    mark_ready.add_argument(
        "--method",
        default="manual-reviewed-markdown",
        help="Reviewed conversion method to record in the source manifest.",
    )
    mark_ready.add_argument("--check", action="store_true", help="Run readiness preflight without writing files.")
    mark_ready.add_argument("--json", action="store_true", help="Print a machine-readable readiness result.")
    args = parser.parse_args()
    if args.command == "mark-ready":
        if args.check:
            result = check_product_import_ready(Path(args.target), method=args.method, reviewed=args.reviewed)
        else:
            result = mark_product_import_ready(Path(args.target), method=args.method, reviewed=args.reviewed)
        if args.json:
            payload = result.to_dict()
            if result.ok and not args.check:
                payload["local_commands"] = target_local_commands_payload(cwd=result.target)
                payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result.ok else 1
        if not result.ok:
            print("Product import readiness preflight failed:" if args.check else "Product import is not ready:")
            for error in result.errors:
                print(f"- ERROR: {error}")
            for warning in result.warnings:
                print(f"- WARN: {warning}")
            return 1
        if args.check:
            print("Product import readiness preflight passed.")
            for path in result.would_update:
                print(f"- WOULD UPDATE: {path}")
            for warning in result.warnings:
                print(f"- WARN: {warning}")
            return 0
        print("Product import marked ready for structuring.")
        for path in result.updated:
            print(f"- UPDATED: {path}")
        for warning in result.warnings:
            print(f"- WARN: {warning}")
        return 0
    raise ValueError(f"unknown product import command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
