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
UNRESOLVED_REQUIRED_COLUMNS = {
    "id": "ID",
    "domain": "Domain",
    "description": "Description",
    "blocking scope": "Blocking Scope",
}
GLOSSARY_REQUIRED_COLUMNS = {
    "term": "Term",
    "meaning": "Meaning",
    "source": "Source",
}
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
WORKFLOW_PACK_SNAPSHOT_ROOT = "docs/agent-workflow/workflow-pack"
ROADMAP_REL = Path("docs/development/01-roadmap.md")
PRODUCT_CHAPTER_RE = re.compile(r"^(?P<prefix>[0-9]{2})-[a-z0-9][a-z0-9-]*\.md$")
API_ENDPOINT_CONTRACT_RE = re.compile(r"^(?P<prefix>[0-9]{2})-[a-z0-9][a-z0-9-]*\.md$")
API_ENDPOINT_REQUIRED_SECTIONS = {
    "method and path": "Method and Path",
    "auth": "Auth",
    "idempotency": "Idempotency",
    "request fields": "Request Fields",
    "response fields": "Response Fields",
    "error codes": "Error Codes",
    "upstream links": "Upstream Links",
    "frontend consumers": "Frontend Consumers",
}
API_ERROR_CODES_REL = Path("docs/api/error-codes.md")
HTTP_METHOD_PATH_RE = re.compile(
    r"(?<![A-Za-z])(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%{}-]*",
    re.IGNORECASE,
)
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
TASK_BOARD_ALLOWED_STATUSES = {
    "backlog",
    "ready",
    "in progress",
    "blocked",
    "done",
    "deferred",
}
TASK_BOARD_READY_STATUSES = {"ready"}
TASK_BOARD_DONE_STATUSES = {"done"}
TASK_BOARD_BLOCKED_STATUSES = {"blocked"}
TASK_BOARD_EMPTY_VALUES = {"", "-", "tbd", "todo", "n/a", "na", "none"}
SECTION_PLACEHOLDER_VALUES = {"", "-", "tbd", "todo", "n/a", "na"}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(r"^\s{0,3}\[[^\]]+]:\s*(\S+)", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
BARE_MARKDOWN_REFERENCE_RE = re.compile(
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
class LocalMarkdownReference:
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
    _check_product_chapter_links(root, report)
    _check_api_endpoint_contract_filenames(root, report)
    _check_unresolved_items(root, report)
    _check_glossary_items(root, report)
    _check_readme_indexes(root, report)
    _check_local_markdown_links(root, report)
    _check_scaffold_placeholders(root, report)
    _check_workflow_pack_manifest(root, report)
    _check_task_board(root, report)
    _check_roadmap_task_board_status(root, report)

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


def _check_product_chapter_links(root: Path, report: VerificationReport) -> None:
    product_root = root / "docs/product"
    if not product_root.exists():
        return
    _check_product_chapter_filenames(root, report)
    chapters = _product_chapters(product_root)
    if not chapters:
        return

    prd_rel = "docs/product/core/PRD.md"
    prd_path = root / prd_rel
    for chapter in chapters:
        rel = chapter.relative_to(root).as_posix()
        if not _markdown_file_references_path(root, chapter, prd_path):
            report.add_error(
                "product_chapter_missing_prd_link",
                f"{rel} must link back to {prd_rel}",
                rel,
            )

    meta = root / "docs/product/core/product-meta.md"
    if not meta.exists():
        return
    for chapter in chapters:
        rel = chapter.relative_to(root).as_posix()
        if not _markdown_file_references_path(root, meta, chapter):
            report.add_error(
                "product_meta_missing_chapter_link",
                f"docs/product/core/product-meta.md must link to product chapter: {rel}",
                "docs/product/core/product-meta.md",
            )


def _check_product_chapter_filenames(root: Path, report: VerificationReport) -> None:
    product_root = root / "docs/product"
    prefix_paths: dict[str, list[Path]] = {}
    for path in sorted(product_root.glob("*.md")):
        if path.name in {"README.md", "AGENTS.md"} or path.name.startswith("_"):
            continue
        rel = path.relative_to(root).as_posix()
        match = PRODUCT_CHAPTER_RE.fullmatch(path.name)
        if not match:
            report.add_error(
                "product_chapter_invalid_filename",
                f"{rel} must use NN-<slug>.md product chapter naming",
                rel,
            )
            continue
        prefix_paths.setdefault(match.group("prefix"), []).append(path)
    for prefix, paths in prefix_paths.items():
        if len(paths) <= 1:
            continue
        rels = [path.relative_to(root).as_posix() for path in paths]
        report.add_error(
            "product_chapter_duplicate_prefix",
            f"duplicate product chapter prefix {prefix}: {', '.join(rels)}",
            rels[-1],
        )


def _product_chapters(product_root: Path) -> list[Path]:
    return [
        path
        for path in sorted(product_root.glob("*.md"))
        if path.is_file() and PRODUCT_CHAPTER_RE.fullmatch(path.name)
    ]


def _check_api_endpoint_contract_filenames(root: Path, report: VerificationReport) -> None:
    endpoint_root = root / "docs/api/endpoints"
    if not endpoint_root.exists():
        return
    prefix_paths: dict[str, list[Path]] = {}
    for path in sorted(endpoint_root.glob("*.md")):
        if path.name in {"README.md", "AGENTS.md"} or path.name.startswith("_"):
            continue
        rel = path.relative_to(root).as_posix()
        match = API_ENDPOINT_CONTRACT_RE.fullmatch(path.name)
        if not match:
            report.add_error(
                "api_endpoint_invalid_filename",
                f"{rel} must use NN-<slug>.md endpoint contract naming",
                rel,
            )
            continue
        prefix_paths.setdefault(match.group("prefix"), []).append(path)
        _check_api_endpoint_contract_sections(root, path, report)
    for prefix, paths in prefix_paths.items():
        if len(paths) <= 1:
            continue
        rels = [path.relative_to(root).as_posix() for path in paths]
        report.add_error(
            "api_endpoint_duplicate_prefix",
            f"duplicate API endpoint contract prefix {prefix}: {', '.join(rels)}",
            rels[-1],
        )


def _check_api_endpoint_contract_sections(root: Path, path: Path, report: VerificationReport) -> None:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in API_ENDPOINT_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "api_endpoint_missing_sections",
            f"{rel} is missing endpoint contract sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in API_ENDPOINT_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "api_endpoint_empty_sections",
            f"{rel} has empty endpoint contract sections: {', '.join(empty)}",
            rel,
        )
    method_and_path = sections["method and path"]
    if _section_has_authored_content(method_and_path) and not _api_endpoint_method_path_valid(method_and_path):
        report.add_error(
            "api_endpoint_method_path_invalid",
            f"{rel} Method and Path section must include an HTTP method and absolute path",
            rel,
        )
    error_codes = sections["error codes"]
    if _section_has_authored_content(error_codes):
        references = _local_markdown_references(root, path, error_codes, include_bare=True, strip_code=False)
        registry_references = [
            reference
            for reference in references
            if reference.rel == API_ERROR_CODES_REL.as_posix()
        ]
        if not registry_references:
            report.add_error(
                "api_endpoint_error_codes_reference_missing",
                f"{rel} Error Codes section must reference {API_ERROR_CODES_REL.as_posix()}",
                rel,
            )
        for reference in registry_references:
            if not reference.exists:
                report.add_error(
                    "api_endpoint_error_codes_reference_missing",
                    f"{rel} references missing Error Codes registry target: {reference.rel}",
                    rel,
                )
    upstream_links = sections["upstream links"]
    if _section_has_authored_content(upstream_links):
        references = _local_markdown_references(root, path, upstream_links, include_bare=True, strip_code=False)
        if not references:
            report.add_error(
                "api_endpoint_upstream_reference_missing",
                f"{rel} Upstream Links section must reference existing local Markdown source",
                rel,
            )
        for reference in references:
            if not reference.exists:
                report.add_error(
                    "api_endpoint_upstream_reference_missing",
                    f"{rel} references missing Upstream Links target: {reference.rel}",
                    rel,
                )


def _check_unresolved_items(root: Path, report: VerificationReport) -> None:
    path = root / "docs/unresolved.md"
    if not path.exists():
        return
    rows = _markdown_table(path.read_text(encoding="utf-8"))
    if not rows:
        return
    header = [_normalize_cell(cell) for cell in rows[0]]
    required = list(UNRESOLVED_REQUIRED_COLUMNS)
    missing = [name for name in required if name not in header]
    if missing:
        report.add_error(
            "unresolved_table_missing_columns",
            f"docs/unresolved.md table is missing required columns: {', '.join(missing)}",
            "docs/unresolved.md",
        )
        return
    column_index = {name: header.index(name) for name in required}
    seen_ids: set[str] = set()
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        if not any(cell.strip() for cell in row):
            continue
        item_id = _table_cell(row, column_index["id"]) or "(missing id)"
        missing_fields = [
            UNRESOLVED_REQUIRED_COLUMNS[name]
            for name in ("id", "domain", "description")
            if not _table_cell(row, column_index[name])
        ]
        if missing_fields:
            report.add_error(
                "unresolved_row_missing_fields",
                f"docs/unresolved.md row {item_id} is missing required fields: {', '.join(missing_fields)}",
                "docs/unresolved.md",
            )
        if item_id != "(missing id)":
            item_key = _normalize_cell(item_id)
            if item_key in seen_ids:
                report.add_error(
                    "unresolved_duplicate_id",
                    f"duplicate unresolved item ID: {item_id}",
                    "docs/unresolved.md",
                )
            else:
                seen_ids.add(item_key)
        blocking_scope = _table_cell(row, column_index["blocking scope"])
        if _normalize_cell(blocking_scope) in NON_BLOCKING_SCOPES:
            continue
        report.add_error(
            "unresolved_blocking_item",
            f"blocking unresolved item {item_id} affects {blocking_scope}",
            "docs/unresolved.md",
        )


def _check_glossary_items(root: Path, report: VerificationReport) -> None:
    path = root / "docs/glossary.md"
    if not path.exists():
        return
    rows = _markdown_table(path.read_text(encoding="utf-8"))
    if not rows:
        return
    header = [_normalize_cell(cell) for cell in rows[0]]
    required = list(GLOSSARY_REQUIRED_COLUMNS)
    missing = [name for name in required if name not in header]
    if missing:
        report.add_error(
            "glossary_table_missing_columns",
            f"docs/glossary.md table is missing required columns: {', '.join(missing)}",
            "docs/glossary.md",
        )
        return
    column_index = {name: header.index(name) for name in required}
    seen_terms: set[str] = set()
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        term = _table_cell(row, column_index["term"])
        row_label = term or "(missing term)"
        missing_fields = [
            GLOSSARY_REQUIRED_COLUMNS[name]
            for name in required
            if not _table_cell(row, column_index[name])
        ]
        if missing_fields:
            report.add_error(
                "glossary_row_missing_fields",
                f"docs/glossary.md row {row_label} is missing required fields: {', '.join(missing_fields)}",
                "docs/glossary.md",
            )
            continue
        term_key = _normalize_cell(term)
        if term_key in seen_terms:
            report.add_error(
                "glossary_duplicate_term",
                f"duplicate glossary term: {term}",
                "docs/glossary.md",
            )
            continue
        seen_terms.add(term_key)
        references = _local_markdown_references(
            root,
            path,
            _table_cell(row, column_index["source"]),
            include_bare=True,
            strip_code=False,
        )
        if not references:
            report.add_error(
                "glossary_source_reference_missing",
                f"glossary row {term} Source field has no local Markdown reference",
                "docs/glossary.md",
            )
            continue
        for reference in references:
            if not reference.exists:
                report.add_error(
                    "glossary_source_reference_missing",
                    f"glossary row {term} references missing Source target: {reference.rel}",
                    "docs/glossary.md",
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


def _check_local_markdown_links(root: Path, report: VerificationReport) -> None:
    for path in _iter_markdown_files_for_link_check(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for reference in _local_markdown_references(root, path, text):
            if reference.exists:
                continue
            report.add_error(
                "docs_local_markdown_link_missing",
                f"{rel} links to missing local Markdown target: {reference.rel}",
                rel,
            )


def _iter_markdown_files_for_link_check(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.glob("*.md")):
        if path.is_file() and not path.name.startswith("_"):
            files.append(path)
    docs_root = root / "docs"
    if not docs_root.exists():
        return files
    for path in sorted(docs_root.rglob("*.md")):
        if not path.is_file() or path.name.startswith("_"):
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/"):
            continue
        if rel.startswith("docs/product/core/source/"):
            continue
        files.append(path)
    return files


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
    seen_ids: set[str] = set()
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
        status = row.get("status", "").strip()
        if _normalize_cell(status) not in TASK_BOARD_ALLOWED_STATUSES:
            report.add_error(
                "task_board_invalid_status",
                f"task board row {task_id} has invalid Status: {status}",
                rel,
            )
            continue
        task_key = _normalize_cell(task_id)
        if task_key in seen_ids:
            report.add_error(
                "task_board_duplicate_id",
                f"duplicate task board ID: {task_id}",
                rel,
            )
            continue
        seen_ids.add(task_key)
        reference_errors = _task_board_row_trace_reference_errors(root, row, task_id)
        if reference_errors:
            for code, message in reference_errors:
                report.add_error(code, message, rel)
            continue
        blocked_errors = _task_board_blocked_unresolved_errors(root, row, task_id)
        if blocked_errors:
            for code, message in blocked_errors:
                report.add_error(code, message, rel)
            continue
        evidence_errors = _task_board_done_evidence_errors(root, row, task_id)
        if evidence_errors:
            for message in evidence_errors:
                report.add_error("task_board_done_evidence_missing", message, rel)
            continue
        if _normalize_cell(row.get("status", "")) in TASK_BOARD_READY_STATUSES:
            ready_count += 1
    if ready_count == 0:
        report.add_error("task_board_ready_task_missing", f"{rel} must contain at least one Ready task", rel)


def _check_roadmap_task_board_status(root: Path, report: VerificationReport) -> None:
    roadmap_path = root / ROADMAP_REL
    task_board_path = root / TASK_BOARD_REL
    if not roadmap_path.exists() or not task_board_path.exists():
        return
    try:
        roadmap_text = roadmap_path.read_text(encoding="utf-8")
        task_board_text = task_board_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in roadmap_text or SCAFFOLD_PLACEHOLDER in task_board_text:
        return

    roadmap_rows = _rows_with_columns(roadmap_text, ("id", "status"))
    if not roadmap_rows:
        return
    task_rows, task_missing = _task_board_rows(task_board_text)
    if task_missing:
        return

    task_status_by_id = {_normalize_cell(row.get("id", "")): row.get("status", "").strip() for row in task_rows}
    for row in roadmap_rows:
        item_id = row.get("id", "").strip()
        if not item_id:
            continue
        task_status = task_status_by_id.get(_normalize_cell(item_id))
        if task_status is None:
            continue
        roadmap_status = row.get("status", "").strip()
        if _normalize_cell(roadmap_status) == _normalize_cell(task_status):
            continue
        report.add_error(
            "roadmap_task_status_conflict",
            f"roadmap status for {item_id} is {roadmap_status} but task board status is {task_status}",
            ROADMAP_REL.as_posix(),
        )


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


def _rows_with_columns(text: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
    table = _markdown_table(text)
    if not table:
        return []
    for index, row in enumerate(table):
        header = [_normalize_cell(cell) for cell in row]
        if not all(column in header for column in columns):
            continue
        rows: list[dict[str, str]] = []
        for data in table[index + 1 :]:
            if _is_separator_row(data):
                continue
            if not any(cell.strip() for cell in data):
                continue
            rows.append({column: _table_cell(data, header.index(column)) for column in columns})
        return rows
    return []


def _task_board_row_trace_complete(row: dict[str, str]) -> bool:
    return all(not _is_empty_task_board_value(row.get(column, "")) for column in TASK_BOARD_TRACE_COLUMNS)


def _task_board_row_trace_references_valid(root: Path, row: dict[str, str]) -> bool:
    task_id = row.get("id", "").strip() or "(missing id)"
    return not _task_board_row_trace_reference_errors(root, row, task_id)


def _task_board_row_trace_reference_errors(root: Path, row: dict[str, str], task_id: str) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    for column in TASK_BOARD_REFERENCE_COLUMNS:
        label = TASK_BOARD_REQUIRED_COLUMNS[column]
        references = _task_board_local_references(root, row.get(column, ""))
        if not references:
            errors.append((
                "task_board_trace_reference_missing",
                f"task board row {task_id} {label} field has no local Markdown reference",
            ))
            continue
        for reference in references:
            if not reference.exists:
                errors.append((
                    "task_board_trace_reference_missing",
                    f"task board row {task_id} references missing {label} target: {reference.rel}",
                ))
        if (
            column == "acceptance"
            and all(reference.exists for reference in references)
            and not any(_is_product_acceptance_reference(reference) for reference in references)
        ):
            errors.append((
                "task_board_acceptance_reference_missing",
                f"task board row {task_id} Acceptance field must reference a product acceptance chapter",
            ))
    return errors


def _is_product_acceptance_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return (
        reference.exists
        and len(path.parts) == 3
        and path.parts[0] == "docs"
        and path.parts[1] == "product"
        and PRODUCT_CHAPTER_RE.fullmatch(path.parts[2]) is not None
        and "acceptance" in path.stem.lower()
    )


def _task_board_done_evidence_errors(root: Path, row: dict[str, str], task_id: str) -> list[str]:
    if _normalize_cell(row.get("status", "")) not in TASK_BOARD_DONE_STATUSES:
        return []
    references = _task_board_local_references(root, row.get("verification", ""))
    if not references:
        return [f"task board row {task_id} is Done but Verification has no local Markdown evidence"]
    return [
        f"task board row {task_id} references missing Verification evidence: {reference.rel}"
        for reference in references
        if not reference.exists
    ]


def _task_board_blocked_unresolved_errors(root: Path, row: dict[str, str], task_id: str) -> list[tuple[str, str]]:
    if _normalize_cell(row.get("status", "")) not in TASK_BOARD_BLOCKED_STATUSES:
        return []
    cited_id = _task_board_cited_unresolved_id(root, row)
    if cited_id is None:
        return [
            (
                "task_board_blocked_unresolved_missing",
                f"task board row {task_id} is Blocked but does not cite an existing unresolved item ID",
            )
        ]
    if not _task_board_links_unresolved_registry(root, row):
        return [
            (
                "task_board_blocked_unresolved_link_missing",
                f"task board row {task_id} is Blocked but does not link to docs/unresolved.md",
            )
        ]
    return []


def _task_board_cited_unresolved_id(root: Path, row: dict[str, str]) -> str | None:
    haystack = " ".join(row.get(column, "") for column in ("task", "verification"))
    for item_id in _unresolved_item_ids(root):
        if _text_contains_identifier(haystack, item_id):
            return item_id
    return None


def _task_board_links_unresolved_registry(root: Path, row: dict[str, str]) -> bool:
    references = []
    references.extend(_task_board_local_references(root, row.get("task", "")))
    references.extend(_task_board_local_references(root, row.get("verification", "")))
    return any(reference.rel == "docs/unresolved.md" for reference in references)


def _unresolved_item_ids(root: Path) -> list[str]:
    path = root / "docs/unresolved.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [row["id"].strip() for row in _rows_with_columns(text, ("id",)) if row.get("id", "").strip()]


def _text_contains_identifier(text: str, identifier: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_-]){re.escape(identifier)}(?![A-Za-z0-9_-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _task_board_local_references(root: Path, value: str) -> list[LocalMarkdownReference]:
    return _local_markdown_references(root, root / TASK_BOARD_REL, value, include_bare=True, strip_code=False)


def _local_markdown_references(
    root: Path,
    source_path: Path,
    text: str,
    *,
    include_bare: bool = False,
    strip_code: bool = True,
) -> list[LocalMarkdownReference]:
    references: list[LocalMarkdownReference] = []
    seen: set[str] = set()
    for target in _extract_local_markdown_reference_targets(text, include_bare=include_bare, strip_code=strip_code):
        reference = _resolve_local_markdown_reference(root, source_path, target)
        if reference is None or reference.rel in seen:
            continue
        references.append(reference)
        seen.add(reference.rel)
    return references


def _markdown_file_references_path(root: Path, source_path: Path, target_path: Path) -> bool:
    try:
        text = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    try:
        expected = target_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    return any(reference.rel == expected for reference in _local_markdown_references(root, source_path, text))


def _extract_local_markdown_reference_targets(text: str, *, include_bare: bool, strip_code: bool) -> list[str]:
    if strip_code:
        text = _strip_markdown_code(text)
    targets: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        targets.append(match.group(1))
    for match in MARKDOWN_REFERENCE_DEFINITION_RE.finditer(text):
        targets.append(match.group(1))
    if include_bare:
        for match in BARE_MARKDOWN_REFERENCE_RE.finditer(text):
            targets.append(match.group(1))
    return targets


def _resolve_local_markdown_reference(root: Path, source_path: Path, target: str) -> LocalMarkdownReference | None:
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
    base = root if target.startswith("docs/") else source_path.parent
    candidate = (base / target_path).resolve()
    try:
        rel = candidate.relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = target
    return LocalMarkdownReference(raw=raw, rel=rel, exists=candidate.is_file())


def _strip_markdown_code(text: str) -> str:
    text = re.sub(r"(?s)```.*?```", "", text)
    text = re.sub(r"(?s)~~~.*?~~~", "", text)
    return re.sub(r"`[^`\n]*`", "", text)


def _markdown_sections(text: str) -> dict[str, str]:
    matches = list(MARKDOWN_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = _normalize_cell(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[heading] = text[start:end]
    return sections


def _section_has_authored_content(text: str) -> bool:
    text = _strip_markdown_code(text)
    text = re.sub(r"(?s)<!--.*?-->", "", text)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^>\s*", "", line)
        line = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", line).strip()
        if _normalize_cell(line) not in SECTION_PLACEHOLDER_VALUES:
            return True
    return False


def _api_endpoint_method_path_valid(text: str) -> bool:
    return HTTP_METHOD_PATH_RE.search(text) is not None


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


def _table_cell(row: list[str], index: int) -> str:
    return row[index].strip() if len(row) > index else ""


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
