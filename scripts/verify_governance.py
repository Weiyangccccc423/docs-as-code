from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


DOC_DIRS = {
    "product",
    "architecture",
    "ui",
    "api",
    "backend",
    "frontend",
    "tests",
    "decisions",
    "development",
    "agent-workflow",
}

NON_BLOCKING_SCOPES = {"", "-", "none", "n/a", "na", "non-blocking", "non blocking", "resolved"}
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
WORKFLOW_PACK_SNAPSHOT_ROOT = "docs/agent-workflow/workflow-pack"
TASK_BOARD_REL = Path("docs/development/02-task-board.md")
TASK_BOARD_REQUIRED_COLUMNS = {
    "id": "ID",
    "status": "Status",
    "task": "Task",
    "product": "Product",
    "design": "Design",
    "api": "API",
    "acceptance": "Acceptance",
    "verification": "Verification",
}
TASK_BOARD_TRACE_COLUMNS = ("product", "design", "api", "acceptance", "verification")
TASK_BOARD_REFERENCE_COLUMNS = ("product", "design", "api", "acceptance")
TASK_BOARD_READY_STATUSES = {"ready"}
TASK_BOARD_EMPTY_VALUES = {"", "-", "tbd", "todo", "n/a", "na", "none"}
TASK_BOARD_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
TASK_BOARD_BARE_REFERENCE_RE = re.compile(
    r"((?:\.{1,2}/)?docs/[^\s`<>\]),;]+\.md(?:#[^\s`<>\]),;]+)?|"
    r"(?:\.{1,2}/)[^\s`<>\]),;]+\.md(?:#[^\s`<>\]),;]+)?)"
)


@dataclass
class VerificationFinding:
    code: str
    severity: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class TaskBoardReference:
    raw: str
    rel: str
    exists: bool


@dataclass
class VerificationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    findings: list[VerificationFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, code: str, message: str, path: str = "") -> None:
        self.errors.append(message)
        self.findings.append(VerificationFinding(code=code, severity="error", path=path, message=message))

    def add_warning(self, code: str, message: str, path: str = "") -> None:
        self.warnings.append(message)
        self.findings.append(VerificationFinding(code=code, severity="warning", path=path, message=message))


def verify(root: Path) -> VerificationReport:
    root = root.resolve()
    report = VerificationReport()

    required_files = [
        "README.md",
        "AGENTS.md",
        "SPEC.md",
        "docs/README.md",
        "docs/AGENTS.md",
        "docs/unresolved.md",
        "docs/glossary.md",
        "docs/product/core/PRD.md",
        "docs/product/core/product-meta.md",
        "docs/product/core/source/source-manifest.json",
    ]
    for rel in required_files:
        if not (root / rel).exists():
            report.add_error("missing_required_file", f"missing required file: {rel}", rel)

    docs_root = root / "docs"
    docs_agents = docs_root / "AGENTS.md"
    docs_agents_text = docs_agents.read_text(encoding="utf-8") if docs_agents.exists() else ""

    if docs_root.exists():
        for child in sorted(docs_root.iterdir()):
            if not child.is_dir():
                continue
            rel = f"docs/{child.name}"
            if _is_effectively_empty(child):
                continue
            if child.name not in DOC_DIRS and f"`{rel}/`" not in docs_agents_text:
                report.add_error("docs_directory_unregistered", f"{rel} is not registered in docs/AGENTS.md", rel)
            if child.name in DOC_DIRS:
                for name in ("README.md", "AGENTS.md"):
                    if not (child / name).exists():
                        report.add_error("docs_directory_missing_governance_file", f"{rel} is missing {name}", f"{rel}/{name}")

    for path in [root / "README.md", docs_root / "README.md", docs_agents]:
        if path.exists():
            _check_reserved_markers(root, path, report)

    _check_product_source_manifest(root, report)
    _check_unresolved_items(root, report)
    _check_readme_indexes(root, report)
    _check_scaffold_placeholders(root, report)
    _check_workflow_pack_manifest(root, report)
    _check_task_board(root, report)

    return report


def _is_effectively_empty(path: Path) -> bool:
    return not any(child.name != ".gitkeep" for child in path.iterdir())


def _check_reserved_markers(root: Path, path: Path, report: VerificationReport) -> None:
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "预留" not in line and "[reserved]" not in line.lower():
            continue
        for match in re.finditer(r"docs/([a-z0-9-]+)", line):
            name = match.group(1)
            target = root / "docs" / name
            if target.exists() and target.is_dir() and not _is_effectively_empty(target):
                report.add_error("reserved_marker_stale", f"reserved marker references non-empty docs/{name}", f"docs/{name}")


def _check_product_source_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / "docs/product/core/source/source-manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.add_error(
            "product_source_manifest_invalid_json",
            f"invalid product source manifest: {error.msg}",
            "docs/product/core/source/source-manifest.json",
        )
        return

    source = manifest.get("source")
    archive = manifest.get("archive")
    imported = manifest.get("import")
    if not isinstance(source, dict) or not isinstance(archive, dict) or not isinstance(imported, dict):
        report.add_error(
            "product_source_manifest_invalid_schema",
            "invalid product source manifest: missing source/archive/import objects",
            "docs/product/core/source/source-manifest.json",
        )
        return

    status = imported.get("status")
    archived_rel = archive.get("path")
    if status == "no_source":
        report.add_error(
            "product_source_missing",
            "product source is missing; archive the original product document before design derivation",
            "docs/product/core/source/source-manifest.json",
        )
        return
    if not isinstance(archived_rel, str) or not archived_rel:
        report.add_error(
            "product_source_manifest_archive_path_missing",
            "invalid product source manifest: archive.path is missing",
            "docs/product/core/source/source-manifest.json",
        )
        return

    archived_path = root / archived_rel
    if not archived_path.exists():
        report.add_error("product_source_archive_missing", f"archived product source is missing: {archived_rel}", archived_rel)
        return

    expected_hash = archive.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        report.add_error(
            "product_source_manifest_archive_hash_missing",
            "invalid product source manifest: archive.sha256 is missing",
            "docs/product/core/source/source-manifest.json",
        )
    elif _sha256(archived_path) != expected_hash:
        report.add_error("product_source_hash_mismatch", f"archived product source hash mismatch: {archived_rel}", archived_rel)

    if imported.get("can_derive_design") is not True:
        report.add_error(
            "product_source_conversion_required",
            f"product source requires conversion before design derivation: {archived_rel}",
            archived_rel,
        )


def _check_unresolved_items(root: Path, report: VerificationReport) -> None:
    path = root / "docs/unresolved.md"
    if not path.exists():
        return
    rows = _markdown_table(path.read_text(encoding="utf-8"))
    if not rows:
        return
    header = [_normalize_cell(cell) for cell in rows[0]]
    required = ["id", "domain", "description", "blocking scope"]
    missing = [name for name in required if name not in header]
    if missing:
        report.add_error(
            "unresolved_table_missing_columns",
            f"docs/unresolved.md table is missing required columns: {', '.join(missing)}",
            "docs/unresolved.md",
        )
        return
    id_index = header.index("id")
    scope_index = header.index("blocking scope")
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        if len(row) <= max(id_index, scope_index):
            continue
        item_id = row[id_index].strip() or "(missing id)"
        blocking_scope = row[scope_index].strip()
        if _normalize_cell(blocking_scope) in NON_BLOCKING_SCOPES:
            continue
        report.add_error(
            "unresolved_blocking_item",
            f"blocking unresolved item {item_id} affects {blocking_scope}",
            "docs/unresolved.md",
        )


def _check_readme_indexes(root: Path, report: VerificationReport) -> None:
    docs_root = root / "docs"
    if not docs_root.exists():
        return
    for readme in sorted(docs_root.rglob("README.md")):
        directory = readme.parent
        readme_text = readme.read_text(encoding="utf-8")
        for child in sorted(directory.glob("*.md")):
            if child.name in {"README.md", "AGENTS.md"} or child.name.startswith("_"):
                continue
            if child.name in readme_text:
                continue
            rel_child = child.relative_to(root).as_posix()
            rel_readme = readme.relative_to(root).as_posix()
            report.add_error("docs_readme_unindexed_file", f"{rel_child} is not indexed in {rel_readme}", rel_child)


def _check_scaffold_placeholders(root: Path, report: VerificationReport) -> None:
    docs_root = root / "docs"
    if not docs_root.exists():
        return
    for path in sorted(docs_root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SCAFFOLD_PLACEHOLDER not in text:
            continue
        report.add_error(
            "governance_scaffold_placeholder",
            f"{rel} still contains a governance scaffold placeholder",
            rel,
        )


def _check_workflow_pack_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / WORKFLOW_PACK_SNAPSHOT_ROOT / "manifest.json"
    manifest_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/manifest.json"
    if not manifest_path.exists():
        report.add_error("workflow_pack_manifest_missing", f"missing workflow pack manifest: {manifest_rel}", manifest_rel)
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.add_error("workflow_pack_manifest_invalid_json", f"invalid workflow pack manifest: {error.msg}", manifest_rel)
        return
    files = manifest.get("files")
    if not isinstance(files, list):
        report.add_error("workflow_pack_manifest_invalid_schema", "invalid workflow pack manifest: files must be a list", manifest_rel)
        return
    snapshot_root = root / WORKFLOW_PACK_SNAPSHOT_ROOT
    for item in files:
        if not isinstance(item, dict):
            report.add_error("workflow_pack_manifest_invalid_schema", "invalid workflow pack manifest: file entry must be an object", manifest_rel)
            continue
        rel = item.get("path")
        expected_hash = item.get("sha256")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            report.add_error("workflow_pack_manifest_invalid_path", f"invalid workflow pack file path: {rel}", manifest_rel)
            continue
        path = snapshot_root / rel
        file_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{rel}"
        if not path.exists():
            report.add_error("workflow_pack_file_missing", f"workflow pack file is missing: {file_rel}", file_rel)
            continue
        if not isinstance(expected_hash, str) or not expected_hash:
            report.add_error("workflow_pack_manifest_hash_missing", f"workflow pack file hash is missing: {file_rel}", manifest_rel)
            continue
        if _sha256(path) != expected_hash:
            report.add_error("workflow_pack_file_hash_mismatch", f"workflow pack file hash mismatch: {file_rel}", file_rel)


def task_board_ready_tasks(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    path = root / TASK_BOARD_REL
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    if SCAFFOLD_PLACEHOLDER in text:
        return []
    rows, _missing = _task_board_rows(text)
    return [
        row
        for row in rows
        if _normalize_cell(row.get("status", "")) in TASK_BOARD_READY_STATUSES and _task_board_row_trace_complete(row)
        and _task_board_row_trace_references_valid(root, row)
    ]


def _check_task_board(root: Path, report: VerificationReport) -> None:
    path = root / TASK_BOARD_REL
    if not path.exists():
        return
    rel = TASK_BOARD_REL.as_posix()
    text = path.read_text(encoding="utf-8")
    if SCAFFOLD_PLACEHOLDER in text:
        return
    rows, missing = _task_board_rows(text)
    if missing:
        report.add_error(
            "task_board_missing_columns",
            f"{rel} table is missing required columns: {', '.join(TASK_BOARD_REQUIRED_COLUMNS[column] for column in missing)}",
            rel,
        )
        return
    if not rows:
        report.add_error("task_board_no_tasks", f"{rel} must contain at least one implementation task row", rel)
        return
    ready_count = 0
    for row in rows:
        task_id = row.get("id", "").strip() or "(missing id)"
        missing_fields = [
            TASK_BOARD_REQUIRED_COLUMNS[column]
            for column in TASK_BOARD_REQUIRED_COLUMNS
            if _is_empty_task_board_value(row.get(column, ""))
        ]
        if missing_fields:
            report.add_error(
                "task_board_row_missing_fields",
                f"task board row {task_id} is missing required fields: {', '.join(missing_fields)}",
                rel,
            )
            continue
        reference_errors = _task_board_row_trace_reference_errors(root, row, task_id)
        if reference_errors:
            for message in reference_errors:
                report.add_error("task_board_trace_reference_missing", message, rel)
            continue
        if _normalize_cell(row.get("status", "")) in TASK_BOARD_READY_STATUSES:
            ready_count += 1
    if ready_count == 0:
        report.add_error("task_board_ready_task_missing", f"{rel} must contain at least one Ready task", rel)


def _task_board_rows(text: str) -> tuple[list[dict[str, str]], list[str]]:
    table = _markdown_table(text)
    if not table:
        return [], list(TASK_BOARD_REQUIRED_COLUMNS)
    for index, row in enumerate(table):
        header = [_normalize_cell(cell) for cell in row]
        if "id" not in header or "status" not in header:
            continue
        missing = [column for column in TASK_BOARD_REQUIRED_COLUMNS if column not in header]
        if missing:
            return [], missing
        rows: list[dict[str, str]] = []
        for data in table[index + 1 :]:
            if _is_separator_row(data):
                continue
            if not any(cell.strip() for cell in data):
                continue
            rows.append(
                {
                    column: data[header.index(column)].strip() if len(data) > header.index(column) else ""
                    for column in TASK_BOARD_REQUIRED_COLUMNS
                }
            )
        return rows, []
    return [], list(TASK_BOARD_REQUIRED_COLUMNS)


def _task_board_row_trace_complete(row: dict[str, str]) -> bool:
    return all(not _is_empty_task_board_value(row.get(column, "")) for column in TASK_BOARD_TRACE_COLUMNS)


def _task_board_row_trace_references_valid(root: Path, row: dict[str, str]) -> bool:
    task_id = row.get("id", "").strip() or "(missing id)"
    return not _task_board_row_trace_reference_errors(root, row, task_id)


def _task_board_row_trace_reference_errors(root: Path, row: dict[str, str], task_id: str) -> list[str]:
    errors: list[str] = []
    for column in TASK_BOARD_REFERENCE_COLUMNS:
        label = TASK_BOARD_REQUIRED_COLUMNS[column]
        references = _task_board_local_references(root, row.get(column, ""))
        if not references:
            errors.append(f"task board row {task_id} {label} field has no local Markdown reference")
            continue
        for reference in references:
            if not reference.exists:
                errors.append(f"task board row {task_id} references missing {label} target: {reference.rel}")
    return errors


def _task_board_local_references(root: Path, value: str) -> list[TaskBoardReference]:
    references: list[TaskBoardReference] = []
    seen: set[str] = set()
    for target in _extract_task_board_reference_targets(value):
        reference = _resolve_task_board_reference(root, target)
        if reference is None or reference.rel in seen:
            continue
        references.append(reference)
        seen.add(reference.rel)
    return references


def _extract_task_board_reference_targets(value: str) -> list[str]:
    targets: list[str] = []
    for match in TASK_BOARD_MARKDOWN_LINK_RE.finditer(value):
        targets.append(match.group(1))
    for match in TASK_BOARD_BARE_REFERENCE_RE.finditer(value):
        targets.append(match.group(1))
    return targets


def _resolve_task_board_reference(root: Path, target: str) -> TaskBoardReference | None:
    raw = target.strip()
    target = raw.strip("`").strip("<>").strip().rstrip(".,;")
    if not target or target.startswith("#") or _is_external_reference_target(target):
        return None
    target = target.replace("\\", "/")
    target = target.split("#", 1)[0].split("?", 1)[0]
    if target.startswith("/"):
        target = target.lstrip("/")
    if not target.endswith(".md"):
        return None
    target_path = Path(target)
    if target_path.is_absolute():
        return None
    base = root if target.startswith("docs/") else root / TASK_BOARD_REL.parent
    candidate = (base / target_path).resolve()
    try:
        rel = candidate.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    return TaskBoardReference(raw=raw, rel=rel, exists=candidate.is_file())


def _is_external_reference_target(target: str) -> bool:
    return target.startswith("//") or re.match(r"^[a-z][a-z0-9+.-]*:", target.lower()) is not None


def _is_empty_task_board_value(value: str) -> bool:
    return _normalize_cell(value) in TASK_BOARD_EMPTY_VALUES


def _markdown_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows


def _normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_separator_row(row: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify docs-as-code governance consistency.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to verify.")
    args = parser.parse_args()
    report = verify(Path(args.target))
    if report.errors:
        print("Governance verification failed:")
        for error in report.errors:
            print(f"- ERROR: {error}")
    if report.warnings:
        print("Governance warnings:")
        for warning in report.warnings:
            print(f"- WARN: {warning}")
    if report.ok:
        print("Governance verification passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
