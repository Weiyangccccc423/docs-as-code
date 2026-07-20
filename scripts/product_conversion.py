from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .bounded_process import run_bounded_command
    from .bootstrap_tree import target_local_commands_payload
    from .state import STATE_REL, StateFileError, load_state, merge_state, utc_now
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command
    from bootstrap_tree import target_local_commands_payload
    from state import STATE_REL, StateFileError, load_state, merge_state, utc_now
    from workflow_actions import next_actions_payload


MANIFEST_REL = Path("docs/product/core/source/source-manifest.json")
CONVERSION_REPORT_REL = Path("docs/product/core/source/conversion-report.json")
PRD_REL = Path("docs/product/core/PRD.md")
PRODUCT_SOURCE_ROOT = Path("docs/product/core/source")
CONVERSION_REPORT_SCHEMA_VERSION = 1
PANDOC_SUFFIX_FORMATS = {
    ".docx": ("docx", "pandoc-docx-to-gfm"),
    ".html": ("html", "pandoc-html-to-gfm"),
    ".htm": ("html", "pandoc-html-to-gfm"),
}
BUILTIN_SUFFIX_METHODS = {".txt": "utf8-text-to-markdown"}
MAX_CONVERTED_BYTES = 32 * 1024 * 1024
CONVERSION_TIMEOUT_SECONDS = 120.0
MAX_PROCESS_OUTPUT_BYTES = 64 * 1024


@dataclass
class ProductConversionResult:
    target: str
    ok: bool
    check: bool
    source_path: str = ""
    source_suffix: str = ""
    method: str = ""
    converter: str = ""
    converter_path: str = ""
    converter_version: str = ""
    required_tool: str = ""
    repair_required: bool = False
    repair_check_command: dict[str, object] = field(default_factory=dict)
    repair_apply_command: dict[str, object] = field(default_factory=dict)
    command_argv: list[str] = field(default_factory=list)
    output_path: str = PRD_REL.as_posix()
    report_path: str = CONVERSION_REPORT_REL.as_posix()
    review_required: bool = True
    review_method: str = ""
    output_sha256: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    execution: dict[str, object] = field(default_factory=dict)
    report: dict[str, object] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("product conversion target must be a non-empty string")
        if not isinstance(self.ok, bool) or not isinstance(self.check, bool):
            raise ValueError("product conversion ok and check must be booleans")
        if not isinstance(self.repair_required, bool) or not isinstance(self.review_required, bool):
            raise ValueError("product conversion repair_required and review_required must be booleans")
        for field_name in (
            "source_path",
            "source_suffix",
            "method",
            "converter",
            "converter_path",
            "converter_version",
            "required_tool",
            "output_path",
            "report_path",
            "review_method",
            "output_sha256",
        ):
            if not isinstance(getattr(self, field_name), str):
                raise ValueError(f"product conversion {field_name} must be a string")
        for field_name in ("errors", "warnings", "would_update", "updated", "command_argv"):
            value = getattr(self, field_name)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"product conversion {field_name} must be a list of strings")
        for field_name in ("repair_check_command", "repair_apply_command", "execution", "report", "state"):
            if not isinstance(getattr(self, field_name), dict):
                raise ValueError(f"product conversion {field_name} must be an object")
        if self.ok and self.errors:
            raise ValueError("successful product conversion cannot include errors")
        if not self.ok and not self.errors:
            raise ValueError("failed product conversion must include errors")
        if self.check and self.updated:
            raise ValueError("product conversion check mode cannot report updated paths")
        if not self.check and self.would_update:
            raise ValueError("product conversion write mode cannot report would_update paths")
        self.repair_check_command = copy.deepcopy(self.repair_check_command)
        self.repair_apply_command = copy.deepcopy(self.repair_apply_command)
        self.command_argv = list(self.command_argv)
        self.errors = list(self.errors)
        self.warnings = list(self.warnings)
        self.would_update = list(self.would_update)
        self.updated = list(self.updated)
        self.execution = copy.deepcopy(self.execution)
        self.report = copy.deepcopy(self.report)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "check": self.check,
            "source_path": self.source_path,
            "source_suffix": self.source_suffix,
            "method": self.method,
            "converter": self.converter,
            "converter_path": self.converter_path,
            "converter_version": self.converter_version,
            "required_tool": self.required_tool,
            "repair_required": self.repair_required,
            "repair_check_command": copy.deepcopy(self.repair_check_command),
            "repair_apply_command": copy.deepcopy(self.repair_apply_command),
            "command_argv": list(self.command_argv),
            "output_path": self.output_path,
            "report_path": self.report_path,
            "review_required": self.review_required,
            "review_method": self.review_method,
            "output_sha256": self.output_sha256,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "would_update": list(self.would_update),
            "updated": list(self.updated),
            "execution": copy.deepcopy(self.execution),
            "report": copy.deepcopy(self.report),
            "state": copy.deepcopy(self.state),
        }


@dataclass
class _ConversionPlan:
    target: Path
    manifest: dict[str, Any]
    archived_path: Path | None
    archived_rel: str
    source_suffix: str
    method: str
    converter: str
    converter_path: str
    converter_version: str
    required_tool: str
    repair_required: bool
    repair_check_command: dict[str, object]
    repair_apply_command: dict[str, object]
    command_argv: list[str]
    errors: list[str]
    warnings: list[str]

    @property
    def review_method(self) -> str:
        if self.method:
            return f"reviewed-{self.method}"
        if self.source_suffix == ".pdf":
            return "manual-reviewed-pdf-to-markdown"
        return "manual-reviewed-markdown"


@dataclass(frozen=True)
class _FileSnapshot:
    exists: bool
    content: bytes = b""


def check_product_conversion(root: Path) -> ProductConversionResult:
    plan = _build_conversion_plan(root)
    return _result_from_plan(
        plan,
        ok=not plan.errors,
        check=True,
        would_update=_conversion_outputs() if not plan.errors else [],
    )


def convert_product_document(root: Path) -> ProductConversionResult:
    plan = _build_conversion_plan(root)
    if plan.errors or plan.archived_path is None:
        return _result_from_plan(plan, ok=False, check=False)

    output_bytes: bytes
    execution: dict[str, object] = {}
    temp_path = _conversion_temp_path(plan.target / PRD_REL)
    try:
        if plan.converter == "builtin-utf8":
            output_bytes = _read_utf8_source(plan.archived_path)
        else:
            execution = run_bounded_command(
                plan.command_argv,
                cwd=plan.target,
                timeout_seconds=CONVERSION_TIMEOUT_SECONDS,
                max_output_bytes=MAX_PROCESS_OUTPUT_BYTES,
            )
            if execution.get("result") != "pass":
                reason = str(execution.get("stderr") or execution.get("result") or "unknown failure")
                return _result_from_plan(
                    plan,
                    ok=False,
                    check=False,
                    errors=[*plan.errors, f"product conversion command failed: {reason}"],
                    execution=execution,
                )
            output_bytes = _read_converted_output(temp_path)
        _validate_converted_output(output_bytes)
    except (OSError, UnicodeError, ValueError) as error:
        return _result_from_plan(
            plan,
            ok=False,
            check=False,
            errors=[*plan.errors, f"product conversion output is invalid: {_error_reason(error)}"],
            execution=execution,
        )
    finally:
        _remove_temp_file(temp_path)

    output_sha256 = hashlib.sha256(output_bytes).hexdigest()
    report = _conversion_report(plan, output_bytes, output_sha256)
    snapshots = _snapshot_files(plan.target, (PRD_REL, CONVERSION_REPORT_REL, STATE_REL))
    updated: list[str] = []
    state: dict[str, Any] = {}
    try:
        _write_atomic_bytes(plan.target / PRD_REL, output_bytes)
        updated.append(PRD_REL.as_posix())
        _write_atomic_text(
            plan.target / CONVERSION_REPORT_REL,
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        updated.append(CONVERSION_REPORT_REL.as_posix())
        state = merge_state(
            plan.target,
            product_conversion_status="pending_review",
            product_conversion_method=plan.method,
            product_conversion_report=CONVERSION_REPORT_REL.as_posix(),
        )
        updated.append(STATE_REL.as_posix())
    except (OSError, StateFileError) as error:
        rollback_errors = _rollback_files(plan.target, snapshots, updated)
        errors = [f"failed to record product conversion: {_error_reason(error)}", *rollback_errors]
        return _result_from_plan(
            plan,
            ok=False,
            check=False,
            errors=errors,
            execution=execution,
            updated=updated,
            report=report,
            state=state,
        )

    return _result_from_plan(
        plan,
        ok=True,
        check=False,
        execution=execution,
        updated=updated,
        output_sha256=output_sha256,
        report=report,
        state=state,
    )


def plan_conversion_review(
    root: Path,
    manifest: dict[str, Any],
    *,
    method: str,
    reviewed_at: str,
    errors: list[str],
    warnings: list[str],
) -> dict[str, object]:
    report_path = root / CONVERSION_REPORT_REL
    if not report_path.exists():
        return {}
    report = _load_json_object(report_path, "product conversion report", errors)
    if not report:
        return {}
    _validate_conversion_report(root, manifest, report, errors)
    conversion = report.get("conversion") if isinstance(report.get("conversion"), dict) else {}
    expected_method = f"reviewed-{conversion.get('method', '')}"
    if method != expected_method:
        errors.append(f"review method must be {expected_method} for the recorded product conversion")
    try:
        reviewed_bytes = (root / PRD_REL).read_bytes()
    except OSError as error:
        errors.append(f"reviewed PRD is unreadable for conversion closeout: {_error_reason(error)}")
        return {}
    if not reviewed_bytes:
        errors.append("reviewed PRD is empty for conversion closeout")
        return {}
    reviewed_sha256 = hashlib.sha256(reviewed_bytes).hexdigest()
    output = report.get("output") if isinstance(report.get("output"), dict) else {}
    if output.get("sha256") != reviewed_sha256:
        warnings.append("reviewed PRD differs from the generated conversion output; closeout will bind the reviewed hash")
    planned = copy.deepcopy(report)
    planned["review"] = {
        "status": "reviewed",
        "method": method,
        "reviewed_at": reviewed_at,
        "reviewed_prd_sha256": reviewed_sha256,
    }
    return planned


def _build_conversion_plan(root: Path) -> _ConversionPlan:
    target = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest = _load_json_object(target / MANIFEST_REL, "product source manifest", errors)
    archived_rel, source_suffix = _validate_manifest_for_conversion(target, manifest, errors)
    archived_path = target / archived_rel if archived_rel else None
    method = ""
    converter = ""
    converter_path = ""
    converter_version = ""
    required_tool = ""
    repair_required = False
    repair_check_command: dict[str, object] = {}
    repair_apply_command: dict[str, object] = {}
    command_argv: list[str] = []

    _check_output_path(target, PRD_REL, "converted PRD", errors)
    _check_output_path(target, CONVERSION_REPORT_REL, "product conversion report", errors)
    _check_output_path(target, STATE_REL, "governance state", errors)
    conversion_temp_rel = _conversion_temp_path(PRD_REL)
    _check_output_path(target, conversion_temp_rel, "product conversion temporary output", errors)
    if (target / conversion_temp_rel).exists():
        errors.append(
            f"stale product conversion temporary output exists: {conversion_temp_rel.as_posix()}"
        )
    try:
        state = load_state(target)
    except StateFileError as error:
        errors.append(f"governance state is invalid: {error.reason}")
        state = {}
    if state and state.get("product_import_status") != "conversion_required":
        errors.append("governance state product import status must be conversion_required")

    if source_suffix in BUILTIN_SUFFIX_METHODS:
        method = BUILTIN_SUFFIX_METHODS[source_suffix]
        converter = "builtin-utf8"
        converter_version = "python-standard-library"
    elif source_suffix in PANDOC_SUFFIX_FORMATS:
        source_format, method = PANDOC_SUFFIX_FORMATS[source_suffix]
        converter = "pandoc"
        required_tool = "pandoc"
        converter_path = shutil.which("pandoc") or ""
        if not converter_path:
            repair_required = True
            errors.append("required conversion tool is missing: pandoc")
            repair_check_command, repair_apply_command = _pandoc_repair_commands(target)
        else:
            probe = run_bounded_command(
                [converter_path, "--version"],
                cwd=target,
                timeout_seconds=5.0,
                max_output_bytes=MAX_PROCESS_OUTPUT_BYTES,
            )
            if probe.get("result") != "pass":
                errors.append("required conversion tool version probe failed: pandoc")
            else:
                converter_version = str(probe.get("stdout", "")).strip().splitlines()[0][:120]
                if not converter_version:
                    errors.append("required conversion tool returned an empty version: pandoc")
            if archived_path is not None:
                command_argv = [
                    converter_path,
                    str(archived_path),
                    f"--from={source_format}",
                    "--to=gfm",
                    "--wrap=none",
                    "--output",
                    str(_conversion_temp_path(target / PRD_REL)),
                ]
    elif source_suffix == ".pdf":
        errors.append("automatic PDF conversion is unsupported; extract and review Markdown manually")
    elif source_suffix:
        errors.append(f"unsupported product conversion source suffix: {source_suffix}")

    return _ConversionPlan(
        target=target,
        manifest=manifest,
        archived_path=archived_path,
        archived_rel=archived_rel,
        source_suffix=source_suffix,
        method=method,
        converter=converter,
        converter_path=converter_path,
        converter_version=converter_version,
        required_tool=required_tool,
        repair_required=repair_required,
        repair_check_command=repair_check_command,
        repair_apply_command=repair_apply_command,
        command_argv=command_argv,
        errors=errors,
        warnings=warnings,
    )


def _validate_manifest_for_conversion(
    target: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> tuple[str, str]:
    if not manifest:
        return "", ""
    if manifest.get("schema_version") != 1:
        errors.append("product source manifest schema_version must be 1")
    imported = manifest.get("import")
    if not isinstance(imported, dict):
        errors.append("product source manifest import must be an object")
    elif imported.get("status") != "conversion_required" or imported.get("can_derive_design") is not False:
        errors.append("product import must remain conversion_required before conversion review")
    source = manifest.get("source")
    source_suffix = ""
    if not isinstance(source, dict) or source.get("provided") is not True:
        errors.append("product source manifest must describe one provided source")
    else:
        value = source.get("suffix")
        if not isinstance(value, str) or not value.startswith(".") or value != value.lower():
            errors.append("product source manifest source.suffix is invalid")
        else:
            source_suffix = value
    archive = manifest.get("archive")
    archived_rel = ""
    if not isinstance(archive, dict):
        errors.append("product source manifest archive must be an object")
        return archived_rel, source_suffix
    value = archive.get("path")
    if not isinstance(value, str) or not _safe_archive_path(value):
        errors.append("product source manifest archive.path must be a safe path under docs/product/core/source")
        return archived_rel, source_suffix
    archived_rel = value
    archived_path = target / archived_rel
    if not archived_path.exists() or not archived_path.is_file() or archived_path.is_symlink():
        errors.append(f"archived product source is missing or unsafe: {archived_rel}")
        return archived_rel, source_suffix
    expected_size = archive.get("size_bytes")
    expected_hash = archive.get("sha256")
    try:
        actual_size = archived_path.stat().st_size
        actual_hash = _sha256(archived_path)
    except OSError as error:
        errors.append(f"archived product source is unreadable: {_error_reason(error)}")
        return archived_rel, source_suffix
    if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size != actual_size:
        errors.append(f"archived product source size mismatch: {archived_rel}")
    if not _valid_sha256(expected_hash) or expected_hash != actual_hash:
        errors.append(f"archived product source hash mismatch: {archived_rel}")
    if isinstance(source, dict):
        if source.get("sha256") != expected_hash or source.get("size_bytes") != expected_size:
            errors.append("product source and archive evidence do not match")
        filename = source.get("filename")
        if not isinstance(filename, str) or Path(archived_rel).name != filename:
            errors.append("product source filename does not match archived source")
        if isinstance(filename, str) and Path(filename).suffix.lower() != source_suffix:
            errors.append("product source suffix does not match source filename")
    return archived_rel, source_suffix


def _conversion_report(
    plan: _ConversionPlan,
    output_bytes: bytes,
    output_sha256: str,
) -> dict[str, object]:
    archive = plan.manifest.get("archive") if isinstance(plan.manifest.get("archive"), dict) else {}
    logical_argv = [
        plan.converter,
        plan.archived_rel,
        *([f"--from={PANDOC_SUFFIX_FORMATS[plan.source_suffix][0]}", "--to=gfm", "--wrap=none"] if plan.converter == "pandoc" else []),
        *( ["--output", PRD_REL.as_posix()] if plan.converter == "pandoc" else []),
    ]
    return {
        "schema_version": CONVERSION_REPORT_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "source": {
            "archive_path": plan.archived_rel,
            "suffix": plan.source_suffix,
            "size_bytes": archive.get("size_bytes"),
            "sha256": archive.get("sha256"),
        },
        "conversion": {
            "method": plan.method,
            "tool": plan.converter,
            "tool_version": plan.converter_version,
            "argv": logical_argv,
        },
        "output": {
            "path": PRD_REL.as_posix(),
            "size_bytes": len(output_bytes),
            "sha256": output_sha256,
        },
        "review": {
            "status": "pending",
            "method": None,
            "reviewed_at": None,
            "reviewed_prd_sha256": None,
        },
    }


def _validate_conversion_report(
    root: Path,
    manifest: dict[str, Any],
    report: dict[str, object],
    errors: list[str],
) -> None:
    if report.get("schema_version") != CONVERSION_REPORT_SCHEMA_VERSION:
        errors.append(f"product conversion report schema_version must be {CONVERSION_REPORT_SCHEMA_VERSION}")
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    archive = manifest.get("archive") if isinstance(manifest.get("archive"), dict) else {}
    if source.get("archive_path") != archive.get("path"):
        errors.append("product conversion report source path does not match source manifest")
    if source.get("sha256") != archive.get("sha256") or source.get("size_bytes") != archive.get("size_bytes"):
        errors.append("product conversion report source evidence does not match source manifest")
    conversion = report.get("conversion") if isinstance(report.get("conversion"), dict) else {}
    if not isinstance(conversion.get("method"), str) or not conversion.get("method"):
        errors.append("product conversion report method is missing")
    output = report.get("output") if isinstance(report.get("output"), dict) else {}
    if output.get("path") != PRD_REL.as_posix() or not _valid_sha256(output.get("sha256")):
        errors.append("product conversion report output evidence is invalid")
    review = report.get("review") if isinstance(report.get("review"), dict) else {}
    if review.get("status") not in {"pending", "reviewed"}:
        errors.append("product conversion report review.status is invalid")
    _check_output_path(root, CONVERSION_REPORT_REL, "product conversion report", errors)


def _result_from_plan(
    plan: _ConversionPlan,
    *,
    ok: bool,
    check: bool,
    errors: list[str] | None = None,
    would_update: list[str] | None = None,
    updated: list[str] | None = None,
    execution: dict[str, object] | None = None,
    output_sha256: str = "",
    report: dict[str, object] | None = None,
    state: dict[str, Any] | None = None,
) -> ProductConversionResult:
    return ProductConversionResult(
        target=str(plan.target),
        ok=ok,
        check=check,
        source_path=plan.archived_rel,
        source_suffix=plan.source_suffix,
        method=plan.method,
        converter=plan.converter,
        converter_path=plan.converter_path,
        converter_version=plan.converter_version,
        required_tool=plan.required_tool,
        repair_required=plan.repair_required,
        repair_check_command=plan.repair_check_command,
        repair_apply_command=plan.repair_apply_command,
        command_argv=plan.command_argv,
        review_method=plan.review_method,
        output_sha256=output_sha256,
        errors=list(plan.errors if errors is None else errors),
        warnings=list(plan.warnings),
        would_update=list(would_update or []),
        updated=list(updated or []),
        execution=dict(execution or {}),
        report=dict(report or {}),
        state=dict(state or {}),
    )


def _conversion_outputs() -> list[str]:
    return [PRD_REL.as_posix(), CONVERSION_REPORT_REL.as_posix(), STATE_REL.as_posix()]


def _pandoc_repair_commands(target: Path) -> tuple[dict[str, object], dict[str, object]]:
    check_argv = [
        "bin/governance",
        "env",
        "--repair",
        "--require-tool",
        "pandoc",
        "--check",
        "--target",
        ".",
        "--json",
    ]
    apply_argv = [item for item in check_argv if item != "--check"]
    cwd = str(target)
    return (
        {
            "id": "product-conversion-env-repair-check",
            "kind": "preflight",
            "cwd": cwd,
            "argv": check_argv,
            "writes_state": False,
            "approval_required": False,
            "success_condition": "ok:true",
        },
        {
            "id": "product-conversion-env-repair",
            "kind": "apply",
            "cwd": cwd,
            "argv": apply_argv,
            "writes_state": True,
            "approval_required": True,
            "requires_action": "product-conversion-env-repair-check",
            "success_condition": "ok:true",
        },
    )


def _read_utf8_source(path: Path) -> bytes:
    data = _read_bounded_file(path)
    _validate_converted_output(data)
    data.decode("utf-8")
    return data


def _read_converted_output(path: Path) -> bytes:
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise ValueError("converter did not create a safe output file")
    return _read_bounded_file(path)


def _read_bounded_file(path: Path) -> bytes:
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("converted Markdown is empty")
    if size > MAX_CONVERTED_BYTES:
        raise ValueError(f"converted Markdown exceeds {MAX_CONVERTED_BYTES} bytes")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError("converted Markdown changed while it was being read")
    return data


def _validate_converted_output(data: bytes) -> None:
    if not data:
        raise ValueError("converted Markdown is empty")
    if len(data) > MAX_CONVERTED_BYTES:
        raise ValueError(f"converted Markdown exceeds {MAX_CONVERTED_BYTES} bytes")
    text = data.decode("utf-8")
    if not text.strip():
        raise ValueError("converted Markdown contains no readable text")


def _safe_archive_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        not value
        or "\\" in value
        or posix.is_absolute()
        or windows.is_absolute()
        or ".." in posix.parts
        or ".." in windows.parts
        or posix.as_posix() != value
    ):
        return False
    try:
        posix.relative_to(PurePosixPath(PRODUCT_SOURCE_ROOT.as_posix()))
    except ValueError:
        return False
    return posix not in {
        PurePosixPath(PRODUCT_SOURCE_ROOT.as_posix()),
        PurePosixPath(MANIFEST_REL.as_posix()),
        PurePosixPath(CONVERSION_REPORT_REL.as_posix()),
    }


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        errors.append(f"missing or unsafe {label}: {path.name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"invalid {label}: {_error_reason(error)}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"invalid {label}: root must be an object")
        return {}
    return payload


def _check_output_path(root: Path, rel: Path, label: str, errors: list[str]) -> None:
    path = root / rel
    if path.parent.exists() and (not path.parent.is_dir() or path.parent.is_symlink()):
        errors.append(f"cannot write {label}: unsafe parent {path.parent.relative_to(root).as_posix()}")
        return
    if path.exists() and (not path.is_file() or path.is_symlink()):
        errors.append(f"cannot write {label}: unsafe path {rel.as_posix()}")
    temp = _atomic_temp_path(path)
    if temp.exists() and (not temp.is_file() or temp.is_symlink()):
        errors.append(f"cannot write {label}: unsafe temporary path {temp.relative_to(root).as_posix()}")


def _snapshot_files(root: Path, rels: tuple[Path, ...]) -> dict[str, _FileSnapshot]:
    snapshots: dict[str, _FileSnapshot] = {}
    for rel in rels:
        path = root / rel
        snapshots[rel.as_posix()] = _FileSnapshot(path.exists(), path.read_bytes() if path.exists() else b"")
    return snapshots


def _rollback_files(root: Path, snapshots: dict[str, _FileSnapshot], updated: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in reversed(list(updated)):
        snapshot = snapshots.get(rel)
        if snapshot is None:
            continue
        try:
            path = root / rel
            if snapshot.exists:
                _write_atomic_bytes(path, snapshot.content)
            elif path.exists():
                path.unlink()
        except OSError as error:
            errors.append(f"failed to rollback {rel}: {_error_reason(error)}")
        else:
            updated.remove(rel)
    return errors


def _write_atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = _atomic_temp_path(path)
    try:
        temp.write_bytes(content)
        temp.replace(path)
    except OSError:
        _remove_temp_file(temp)
        raise


def _write_atomic_text(path: Path, content: str) -> None:
    _write_atomic_bytes(path, content.encode("utf-8"))


def _atomic_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def _conversion_temp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.conversion.tmp")


def _remove_temp_file(path: Path) -> None:
    if path.exists() and path.is_file() and not path.is_symlink():
        try:
            path.unlink()
        except OSError:
            pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _error_reason(error: BaseException) -> str:
    if isinstance(error, OSError) and error.strerror:
        return error.strerror
    if isinstance(error, json.JSONDecodeError):
        return error.msg
    return str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert one archived product source into reviewable Markdown.")
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument("--check", action="store_true", help="Preview conversion without writing files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    result = check_product_conversion(Path(args.target)) if args.check else convert_product_document(Path(args.target))
    payload = result.to_dict()
    if result.ok and not args.check:
        payload["local_commands"] = target_local_commands_payload(cwd=result.target)
        payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif result.ok:
        print("Product conversion preflight passed." if args.check else "Product document converted for review.")
    else:
        print("Product conversion failed:")
        for error in result.errors:
            print(f"- ERROR: {error}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
