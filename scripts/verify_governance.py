from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


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
UNRESOLVED_ID_RE = re.compile(r"^U-[0-9]{3}$")
TASK_ID_RE = re.compile(r"^TASK-[0-9]{3}$")
ACCEPTANCE_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])A-[0-9]{3}(?![A-Za-z0-9_-])")
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
ADR_REQUIRED_SECTIONS = {
    "context": "Context",
    "decision": "Decision",
    "consequences": "Consequences",
    "references": "References",
}
ADR_DECISION_RE = re.compile(r"^(?P<prefix>[0-9]{3})-[a-z0-9][a-z0-9-]*\.md$")
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
WORKFLOW_PACK_SNAPSHOT_ROOT = "docs/agent-workflow/workflow-pack"
ROADMAP_REL = Path("docs/development/01-roadmap.md")
ROADMAP_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "milestones": "Milestones",
    "sequencing": "Sequencing",
    "risks": "Risks",
    "deferred scope": "Deferred Scope",
}
ROADMAP_MILESTONE_REQUIRED_COLUMNS = {
    "id": "ID",
    "status": "Status",
    "milestone": "Milestone",
}
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
API_CONVENTIONS_REL = Path("docs/api/00-conventions.md")
API_CONVENTIONS_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "http conventions": "HTTP Conventions",
    "authentication": "Authentication",
    "idempotency": "Idempotency",
    "compatibility": "Compatibility",
    "open decisions": "Open Decisions",
}
API_ERROR_CODES_REL = Path("docs/api/error-codes.md")
API_ERROR_CODES_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "error taxonomy": "Error Taxonomy",
    "error codes": "Error Codes",
    "retry semantics": "Retry Semantics",
    "frontend handling": "Frontend Handling",
}
API_CHANGELOG_REL = Path("docs/api/changelog.md")
API_CHANGELOG_REQUIRED_SECTIONS = {
    "change log": "Change Log",
    "compatibility notes": "Compatibility Notes",
}
UI_INTERACTION_MODEL_REL = Path("docs/ui/01-interaction-model.md")
UI_INTERACTION_MODEL_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "primary flows": "Primary Flows",
    "screens": "Screens",
    "states": "States",
    "errors": "Errors",
    "accessibility": "Accessibility",
}
ARCHITECTURE_SYSTEM_CONTEXT_REL = Path("docs/architecture/01-system-context.md")
ARCHITECTURE_SYSTEM_CONTEXT_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "actors": "Actors",
    "external systems": "External Systems",
    "trust boundaries": "Trust Boundaries",
    "open decisions": "Open Decisions",
}
ARCHITECTURE_CONTAINERS_REL = Path("docs/architecture/02-containers.md")
ARCHITECTURE_CONTAINER_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "containers": "Containers",
    "runtime responsibilities": "Runtime Responsibilities",
    "data ownership": "Data Ownership",
    "open decisions": "Open Decisions",
}
ARCHITECTURE_QUALITY_ATTRIBUTES_REL = Path("docs/architecture/03-quality-attributes.md")
ARCHITECTURE_QUALITY_ATTRIBUTE_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "availability": "Availability",
    "performance": "Performance",
    "security": "Security",
    "observability": "Observability",
    "tradeoffs": "Tradeoffs",
}
BACKEND_MODULES_REL = Path("docs/backend/01-modules.md")
BACKEND_MODULE_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "architecture links": "Architecture Links",
    "modules": "Modules",
    "api ownership": "API Ownership",
    "failure modes": "Failure Modes",
    "open decisions": "Open Decisions",
}
BACKEND_DATA_MODEL_REL = Path("docs/backend/02-data-model.md")
BACKEND_DATA_MODEL_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "owners": "Owners",
    "entities": "Entities",
    "state machines": "State Machines",
    "constraints": "Constraints",
    "indexes": "Indexes",
    "migrations": "Migrations",
}
BACKEND_EXTERNAL_SERVICES_REL = Path("docs/backend/03-external-services.md")
BACKEND_EXTERNAL_SERVICES_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "dependencies": "Dependencies",
    "contracts": "Contracts",
    "retries": "Retries",
    "timeouts": "Timeouts",
    "authentication": "Authentication",
    "observability": "Observability",
}
FRONTEND_MODULES_REL = Path("docs/frontend/01-modules.md")
FRONTEND_MODULE_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "ui links": "UI Links",
    "modules": "Modules",
    "state ownership": "State Ownership",
    "routes": "Routes",
    "open decisions": "Open Decisions",
}
FRONTEND_API_CONSUMPTION_REL = Path("docs/frontend/02-api-consumption.md")
FRONTEND_API_CONSUMPTION_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "api links": "API Links",
    "consumption map": "Consumption Map",
    "loading states": "Loading States",
    "error actions": "Error Actions",
}
TEST_STRATEGY_REL = Path("docs/tests/01-strategy.md")
TEST_STRATEGY_REQUIRED_SECTIONS = {
    "product links": "Product Links",
    "acceptance links": "Acceptance Links",
    "test layers": "Test Layers",
    "risk coverage": "Risk Coverage",
    "non-functional checks": "Non-Functional Checks",
}
ACCEPTANCE_MATRIX_REL = Path("docs/tests/02-acceptance-matrix.md")
ACCEPTANCE_MATRIX_REQUIRED_SECTIONS = {
    "matrix": "Matrix",
    "uncovered criteria": "Uncovered Criteria",
}
ACCEPTANCE_MATRIX_REQUIRED_COLUMNS = {
    "acceptance": "Acceptance",
    "design": "Design",
    "api": "API",
    "test": "Test",
}
HTTP_METHOD_PATH_RE = re.compile(
    r"(?<![A-Za-z])(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%{}-]*",
    re.IGNORECASE,
)
TASK_BOARD_REL = Path("docs/development/02-task-board.md")
TASK_BOARD_REQUIRED_SECTIONS = {
    "task table": "Task Table",
    "status policy": "Status Policy",
    "traceability rules": "Traceability Rules",
}
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
    _check_api_conventions(root, report)
    _check_api_error_codes(root, report)
    _check_api_changelog(root, report)
    _check_api_endpoint_contract_filenames(root, report)
    _check_architecture_system_context_traceability(root, report)
    _check_architecture_containers_traceability(root, report)
    _check_architecture_quality_attributes(root, report)
    _check_backend_module_traceability(root, report)
    _check_backend_data_model(root, report)
    _check_backend_external_services(root, report)
    _check_ui_interaction_model(root, report)
    _check_frontend_module_traceability(root, report)
    _check_frontend_api_consumption(root, report)
    _check_test_strategy_traceability(root, report)
    _check_acceptance_matrix_traceability(root, report)
    _check_architecture_decisions(root, report)
    _check_unresolved_items(root, report)
    _check_glossary_items(root, report)
    _check_readme_indexes(root, report)
    _check_local_markdown_links(root, report)
    _check_scaffold_placeholders(root, report)
    _check_workflow_pack_manifest(root, report)
    _check_task_board(root, report)
    _check_roadmap(root, report)
    _check_roadmap_task_board_alignment(root, report)

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
    _check_product_acceptance_chapter_ids(root, chapters, report)

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


def _check_product_acceptance_chapter_ids(root: Path, chapters: list[Path], report: VerificationReport) -> None:
    for chapter in chapters:
        if "acceptance" not in chapter.stem.lower():
            continue
        rel = chapter.relative_to(root).as_posix()
        try:
            text = chapter.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SCAFFOLD_PLACEHOLDER in text:
            continue
        if ACCEPTANCE_ID_RE.search(_strip_markdown_code(text)) is None:
            report.add_error(
                "product_acceptance_missing_ids",
                f"{rel} must define at least one A-NNN acceptance ID",
                rel,
            )


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


def _check_api_conventions(root: Path, report: VerificationReport) -> None:
    path = root / API_CONVENTIONS_REL
    rel = API_CONVENTIONS_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in API_CONVENTIONS_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "api_conventions_missing_sections",
            f"{rel} is missing API convention sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in API_CONVENTIONS_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "api_conventions_empty_sections",
            f"{rel} has empty API convention sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "api_conventions_trace_reference_missing",
        "Product",
        _is_product_scope_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "api_conventions_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_api_error_codes(root: Path, report: VerificationReport) -> None:
    path = root / API_ERROR_CODES_REL
    rel = API_ERROR_CODES_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in API_ERROR_CODES_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "api_error_codes_missing_sections",
            f"{rel} is missing API error code sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in API_ERROR_CODES_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "api_error_codes_empty_sections",
            f"{rel} has empty API error code sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "api_error_codes_trace_reference_missing",
        "Product",
        _is_product_scope_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "api_error_codes_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_api_changelog(root: Path, report: VerificationReport) -> None:
    path = root / API_CHANGELOG_REL
    rel = API_CHANGELOG_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in API_CHANGELOG_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "api_changelog_missing_sections",
            f"{rel} is missing API changelog sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in API_CHANGELOG_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "api_changelog_empty_sections",
            f"{rel} has empty API changelog sections: {', '.join(empty)}",
            rel,
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
    frontend_consumers = sections["frontend consumers"]
    if _section_has_authored_content(frontend_consumers):
        references = _local_markdown_references(root, path, frontend_consumers, include_bare=True, strip_code=False)
        if not references:
            report.add_error(
                "api_endpoint_frontend_consumer_reference_missing",
                f"{rel} Frontend Consumers section must reference existing local Markdown consumer docs",
                rel,
            )
        for reference in references:
            if not reference.exists:
                report.add_error(
                    "api_endpoint_frontend_consumer_reference_missing",
                    f"{rel} references missing Frontend Consumers target: {reference.rel}",
                    rel,
                )


def _check_architecture_system_context_traceability(root: Path, report: VerificationReport) -> None:
    path = root / ARCHITECTURE_SYSTEM_CONTEXT_REL
    rel = ARCHITECTURE_SYSTEM_CONTEXT_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in ARCHITECTURE_SYSTEM_CONTEXT_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "architecture_system_context_missing_sections",
            f"{rel} is missing system context sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in ARCHITECTURE_SYSTEM_CONTEXT_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "architecture_system_context_empty_sections",
            f"{rel} has empty system context sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "architecture_system_context_trace_reference_missing",
        "Product",
        _is_product_scope_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "architecture_system_context_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_architecture_containers_traceability(root: Path, report: VerificationReport) -> None:
    path = root / ARCHITECTURE_CONTAINERS_REL
    rel = ARCHITECTURE_CONTAINERS_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in ARCHITECTURE_CONTAINER_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "architecture_containers_missing_sections",
            f"{rel} is missing container sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in ARCHITECTURE_CONTAINER_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "architecture_containers_empty_sections",
            f"{rel} has empty container sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "architecture_containers_trace_reference_missing",
        "System Context",
        lambda reference: reference.rel == ARCHITECTURE_SYSTEM_CONTEXT_REL.as_posix(),
        required_rel=ARCHITECTURE_SYSTEM_CONTEXT_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "architecture_containers_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_architecture_quality_attributes(root: Path, report: VerificationReport) -> None:
    path = root / ARCHITECTURE_QUALITY_ATTRIBUTES_REL
    rel = ARCHITECTURE_QUALITY_ATTRIBUTES_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in ARCHITECTURE_QUALITY_ATTRIBUTE_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "architecture_quality_attributes_missing_sections",
            f"{rel} is missing quality attribute sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in ARCHITECTURE_QUALITY_ATTRIBUTE_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "architecture_quality_attributes_empty_sections",
            f"{rel} has empty quality attribute sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "architecture_quality_attributes_trace_reference_missing",
        "Containers",
        lambda reference: reference.rel == ARCHITECTURE_CONTAINERS_REL.as_posix(),
        required_rel=ARCHITECTURE_CONTAINERS_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "architecture_quality_attributes_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_backend_module_traceability(root: Path, report: VerificationReport) -> None:
    path = root / BACKEND_MODULES_REL
    rel = BACKEND_MODULES_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in BACKEND_MODULE_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "backend_module_missing_sections",
            f"{rel} is missing backend module sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in BACKEND_MODULE_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "backend_module_empty_sections",
            f"{rel} has empty backend module sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_module_trace_reference_missing",
        "Architecture",
        _is_architecture_reference,
    )
    _check_design_reference_group(report, rel, references, "backend_module_trace_reference_missing", "API", _is_api_reference)
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_module_trace_reference_missing",
        "Data Model",
        lambda reference: reference.rel == BACKEND_DATA_MODEL_REL.as_posix(),
        required_rel=BACKEND_DATA_MODEL_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_module_trace_reference_missing",
        "External Services",
        lambda reference: reference.rel == BACKEND_EXTERNAL_SERVICES_REL.as_posix(),
        required_rel=BACKEND_EXTERNAL_SERVICES_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_module_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_backend_data_model(root: Path, report: VerificationReport) -> None:
    path = root / BACKEND_DATA_MODEL_REL
    rel = BACKEND_DATA_MODEL_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in BACKEND_DATA_MODEL_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "backend_data_model_missing_sections",
            f"{rel} is missing data model sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in BACKEND_DATA_MODEL_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "backend_data_model_empty_sections",
            f"{rel} has empty data model sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_data_model_trace_reference_missing",
        "Backend Modules",
        lambda reference: reference.rel == BACKEND_MODULES_REL.as_posix(),
        required_rel=BACKEND_MODULES_REL.as_posix(),
    )
    _check_design_reference_group(report, rel, references, "backend_data_model_trace_reference_missing", "API", _is_api_reference)
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_data_model_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_backend_external_services(root: Path, report: VerificationReport) -> None:
    path = root / BACKEND_EXTERNAL_SERVICES_REL
    rel = BACKEND_EXTERNAL_SERVICES_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in BACKEND_EXTERNAL_SERVICES_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "backend_external_services_missing_sections",
            f"{rel} is missing external services sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in BACKEND_EXTERNAL_SERVICES_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "backend_external_services_empty_sections",
            f"{rel} has empty external services sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_external_services_trace_reference_missing",
        "Backend Modules",
        lambda reference: reference.rel == BACKEND_MODULES_REL.as_posix(),
        required_rel=BACKEND_MODULES_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_external_services_trace_reference_missing",
        "API",
        _is_api_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "backend_external_services_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_ui_interaction_model(root: Path, report: VerificationReport) -> None:
    path = root / UI_INTERACTION_MODEL_REL
    rel = UI_INTERACTION_MODEL_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in UI_INTERACTION_MODEL_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "ui_interaction_model_missing_sections",
            f"{rel} is missing UI interaction sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in UI_INTERACTION_MODEL_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "ui_interaction_model_empty_sections",
            f"{rel} has empty UI interaction sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "ui_interaction_model_trace_reference_missing",
        "Product",
        _is_product_scope_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "ui_interaction_model_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_frontend_module_traceability(root: Path, report: VerificationReport) -> None:
    path = root / FRONTEND_MODULES_REL
    rel = FRONTEND_MODULES_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in FRONTEND_MODULE_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "frontend_module_missing_sections",
            f"{rel} is missing frontend module sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in FRONTEND_MODULE_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "frontend_module_empty_sections",
            f"{rel} has empty frontend module sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(report, rel, references, "frontend_module_trace_reference_missing", "UI", _is_ui_reference)
    _check_design_reference_group(report, rel, references, "frontend_module_trace_reference_missing", "API", _is_api_reference)
    _check_design_reference_group(
        report,
        rel,
        references,
        "frontend_module_trace_reference_missing",
        "API Consumption",
        lambda reference: reference.rel == FRONTEND_API_CONSUMPTION_REL.as_posix(),
        required_rel=FRONTEND_API_CONSUMPTION_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "frontend_module_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_frontend_api_consumption(root: Path, report: VerificationReport) -> None:
    path = root / FRONTEND_API_CONSUMPTION_REL
    rel = FRONTEND_API_CONSUMPTION_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in FRONTEND_API_CONSUMPTION_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "frontend_api_consumption_missing_sections",
            f"{rel} is missing API consumption sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in FRONTEND_API_CONSUMPTION_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "frontend_api_consumption_empty_sections",
            f"{rel} has empty API consumption sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "frontend_api_consumption_trace_reference_missing",
        "Frontend Modules",
        lambda reference: reference.rel == FRONTEND_MODULES_REL.as_posix(),
        required_rel=FRONTEND_MODULES_REL.as_posix(),
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "frontend_api_consumption_trace_reference_missing",
        "API",
        _is_api_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "frontend_api_consumption_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _check_test_strategy_traceability(root: Path, report: VerificationReport) -> None:
    path = root / TEST_STRATEGY_REL
    rel = TEST_STRATEGY_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in TEST_STRATEGY_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "test_strategy_missing_sections",
            f"{rel} is missing test strategy sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in TEST_STRATEGY_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "test_strategy_empty_sections",
            f"{rel} has empty test strategy sections: {', '.join(empty)}",
            rel,
        )

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "test_strategy_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )
    _check_design_reference_group(report, rel, references, "test_strategy_trace_reference_missing", "API", _is_api_reference)
    _check_design_reference_group(
        report,
        rel,
        references,
        "test_strategy_trace_reference_missing",
        "Design",
        _is_design_reference,
    )


def _check_acceptance_matrix_traceability(root: Path, report: VerificationReport) -> None:
    path = root / ACCEPTANCE_MATRIX_REL
    rel = ACCEPTANCE_MATRIX_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing_sections = [
        label
        for key, label in ACCEPTANCE_MATRIX_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing_sections:
        report.add_error(
            "acceptance_matrix_missing_sections",
            f"{rel} is missing acceptance matrix sections: {', '.join(missing_sections)}",
            rel,
        )
    empty_sections = [
        label
        for key, label in ACCEPTANCE_MATRIX_REQUIRED_SECTIONS.items()
        if key in sections and not _section_has_authored_content(sections[key])
    ]
    if empty_sections:
        report.add_error(
            "acceptance_matrix_empty_sections",
            f"{rel} has empty acceptance matrix sections: {', '.join(empty_sections)}",
            rel,
        )

    rows, missing = _acceptance_matrix_rows(text)
    if missing:
        report.add_error(
            "acceptance_matrix_missing_columns",
            f"{rel} table is missing required columns: {', '.join(ACCEPTANCE_MATRIX_REQUIRED_COLUMNS[column] for column in missing)}",
            rel,
        )
        return
    if not rows:
        report.add_error("acceptance_matrix_no_rows", f"{rel} must contain at least one acceptance mapping row", rel)
        return

    seen_acceptance_ids: set[str] = set()
    for row in rows:
        row_label = _acceptance_matrix_row_label(root, path, row)
        missing_fields = [
            ACCEPTANCE_MATRIX_REQUIRED_COLUMNS[column]
            for column in ACCEPTANCE_MATRIX_REQUIRED_COLUMNS
            if _normalize_cell(row.get(column, "")) in SECTION_PLACEHOLDER_VALUES
        ]
        if missing_fields:
            report.add_error(
                "acceptance_matrix_row_missing_fields",
                f"acceptance matrix row {row_label} is missing required fields: {', '.join(missing_fields)}",
                rel,
            )
            continue
        acceptance_id = _acceptance_matrix_acceptance_id(row["acceptance"])
        if acceptance_id is None:
            report.add_error(
                "acceptance_matrix_invalid_acceptance_id",
                f"acceptance matrix row {row_label} Acceptance field must include A-NNN acceptance ID",
                rel,
            )
            continue
        if acceptance_id in seen_acceptance_ids:
            report.add_error(
                "acceptance_matrix_duplicate_acceptance_id",
                f"duplicate acceptance matrix Acceptance ID: {acceptance_id}",
                rel,
            )
            continue
        seen_acceptance_ids.add(acceptance_id)
        _check_acceptance_matrix_acceptance_id_source(root, path, report, row_label, row["acceptance"], acceptance_id)
        _check_acceptance_matrix_reference(
            root,
            path,
            report,
            row_label,
            "acceptance",
            row["acceptance"],
            "a product acceptance chapter",
            _is_product_acceptance_reference_path,
        )
        _check_acceptance_matrix_reference(
            root,
            path,
            report,
            row_label,
            "design",
            row["design"],
            "existing Design docs",
            _is_design_reference,
        )
        _check_acceptance_matrix_reference(
            root,
            path,
            report,
            row_label,
            "api",
            row["api"],
            "existing API docs",
            _is_api_reference,
        )
        _check_acceptance_matrix_reference(
            root,
            path,
            report,
            row_label,
            "test",
            row["test"],
            "existing Test docs",
            _is_test_reference,
        )


def _acceptance_matrix_rows(text: str) -> tuple[list[dict[str, str]], list[str]]:
    table = _markdown_table(text)
    if not table:
        return [], list(ACCEPTANCE_MATRIX_REQUIRED_COLUMNS)
    for index, row in enumerate(table):
        header = [_normalize_cell(cell) for cell in row]
        if "acceptance" not in header:
            continue
        missing = [column for column in ACCEPTANCE_MATRIX_REQUIRED_COLUMNS if column not in header]
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
                    column: _table_cell(data, header.index(column))
                    for column in ACCEPTANCE_MATRIX_REQUIRED_COLUMNS
                }
            )
        return rows, []
    return [], list(ACCEPTANCE_MATRIX_REQUIRED_COLUMNS)


def _acceptance_matrix_row_label(root: Path, matrix_path: Path, row: dict[str, str]) -> str:
    references = _local_markdown_references(root, matrix_path, row.get("acceptance", ""), include_bare=True, strip_code=False)
    if references:
        return references[0].rel
    label = _plain_cell_label(row.get("acceptance", ""))
    return label or "(missing acceptance)"


def _acceptance_matrix_acceptance_id(value: str) -> str | None:
    label = _plain_cell_label(value)
    match = ACCEPTANCE_ID_RE.search(label)
    if match is None:
        return None
    return match.group(0)


def _check_acceptance_matrix_acceptance_id_source(
    root: Path,
    matrix_path: Path,
    report: VerificationReport,
    row_label: str,
    value: str,
    acceptance_id: str,
) -> None:
    references = _local_markdown_references(root, matrix_path, value, include_bare=True, strip_code=False)
    product_acceptance_refs = [
        reference
        for reference in references
        if reference.exists and _is_product_acceptance_reference_path(reference)
    ]
    if product_acceptance_refs and not any(
        _product_acceptance_reference_has_id(root, reference, acceptance_id)
        for reference in product_acceptance_refs
    ):
        report.add_error(
            "acceptance_matrix_acceptance_id_unknown",
            f"acceptance matrix row {row_label} Acceptance ID {acceptance_id} is not defined in referenced product acceptance chapter",
            ACCEPTANCE_MATRIX_REL.as_posix(),
        )


def _check_acceptance_matrix_reference(
    root: Path,
    matrix_path: Path,
    report: VerificationReport,
    row_label: str,
    column: str,
    value: str,
    expected: str,
    predicate: Callable[[LocalMarkdownReference], bool],
) -> None:
    rel = ACCEPTANCE_MATRIX_REL.as_posix()
    label = ACCEPTANCE_MATRIX_REQUIRED_COLUMNS[column]
    references = _local_markdown_references(root, matrix_path, value, include_bare=True, strip_code=False)
    if not references:
        report.add_error(
            "acceptance_matrix_trace_reference_missing",
            f"acceptance matrix row {row_label} {label} field has no local Markdown reference",
            rel,
        )
        return
    for reference in references:
        if not reference.exists:
            report.add_error(
                "acceptance_matrix_trace_reference_missing",
                f"acceptance matrix row {row_label} {label} references missing target: {reference.rel}",
                rel,
            )
    if any(not reference.exists for reference in references):
        return
    if not any(predicate(reference) for reference in references):
        report.add_error(
            "acceptance_matrix_trace_reference_missing",
            f"acceptance matrix row {row_label} {label} field must reference {expected}",
            rel,
        )


def _check_design_reference_group(
    report: VerificationReport,
    source_rel: str,
    references: list[LocalMarkdownReference],
    code: str,
    label: str,
    predicate: Callable[[LocalMarkdownReference], bool],
    *,
    required_rel: str = "",
) -> None:
    matching = [reference for reference in references if predicate(reference)]
    if not matching:
        if required_rel:
            message = f"{source_rel} must reference {required_rel}"
        elif label == "Acceptance":
            message = f"{source_rel} must reference a product acceptance chapter"
        else:
            message = f"{source_rel} must reference existing {label} docs"
        report.add_error(code, message, source_rel)
        return
    for reference in matching:
        if not reference.exists:
            report.add_error(
                code,
                f"{source_rel} references missing {label} target: {reference.rel}",
                source_rel,
            )


def _check_architecture_decisions(root: Path, report: VerificationReport) -> None:
    decisions_root = root / "docs/decisions"
    if not decisions_root.exists():
        return
    prefix_paths: dict[str, list[Path]] = {}
    for path in sorted(decisions_root.glob("*.md")):
        if path.name in {"README.md", "AGENTS.md"} or path.name.startswith("_"):
            continue
        rel = path.relative_to(root).as_posix()
        match = ADR_DECISION_RE.fullmatch(path.name)
        if not match:
            report.add_error(
                "adr_invalid_filename",
                f"{rel} must use NNN-<slug>.md ADR naming",
                rel,
            )
        else:
            prefix_paths.setdefault(match.group("prefix"), []).append(path)
        _check_architecture_decision(root, path, report)
    for prefix, paths in prefix_paths.items():
        if len(paths) <= 1:
            continue
        rels = [path.relative_to(root).as_posix() for path in paths]
        report.add_error(
            "adr_duplicate_prefix",
            f"duplicate ADR prefix {prefix}: {', '.join(rels)}",
            rels[-1],
        )


def _check_architecture_decision(root: Path, path: Path, report: VerificationReport) -> None:
    rel = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return
    sections = _markdown_sections(text)
    missing = [
        label
        for key, label in ADR_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "adr_missing_sections",
            f"{rel} is missing ADR sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in ADR_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "adr_empty_sections",
            f"{rel} has empty ADR sections: {', '.join(empty)}",
            rel,
        )
    references_section = sections["references"]
    if _section_has_authored_content(references_section):
        references = _local_markdown_references(root, path, references_section, include_bare=True, strip_code=False)
        if not references:
            report.add_error(
                "adr_reference_missing",
                f"{rel} References section must reference existing local Markdown sources",
                rel,
            )
        for reference in references:
            if not reference.exists:
                report.add_error(
                    "adr_reference_missing",
                    f"{rel} references missing ADR References target: {reference.rel}",
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
            if UNRESOLVED_ID_RE.fullmatch(item_id) is None:
                report.add_error(
                    "unresolved_invalid_id",
                    f"docs/unresolved.md row {item_id} must use U-NNN unresolved item ID format",
                    "docs/unresolved.md",
                )
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
    sections = _markdown_sections(text, min_level=2)
    missing_sections = [
        label
        for key, label in TASK_BOARD_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing_sections:
        report.add_error(
            "task_board_missing_sections",
            f"{rel} is missing task board sections: {', '.join(missing_sections)}",
            rel,
        )
    empty_sections = [
        label
        for key, label in TASK_BOARD_REQUIRED_SECTIONS.items()
        if key in sections and not _section_has_authored_content(sections[key])
    ]
    if empty_sections:
        report.add_error(
            "task_board_empty_sections",
            f"{rel} has empty task board sections: {', '.join(empty_sections)}",
            rel,
        )
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
        if TASK_ID_RE.fullmatch(task_id) is None:
            report.add_error(
                "task_board_invalid_id",
                f"task board row {task_id} must use TASK-NNN task ID format",
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


def _check_roadmap(root: Path, report: VerificationReport) -> None:
    path = root / ROADMAP_REL
    rel = ROADMAP_REL.as_posix()
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing = [
        label
        for key, label in ROADMAP_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing:
        report.add_error(
            "roadmap_missing_sections",
            f"{rel} is missing roadmap sections: {', '.join(missing)}",
            rel,
        )
        return
    empty = [
        label
        for key, label in ROADMAP_REQUIRED_SECTIONS.items()
        if not _section_has_authored_content(sections[key])
    ]
    if empty:
        report.add_error(
            "roadmap_empty_sections",
            f"{rel} has empty roadmap sections: {', '.join(empty)}",
            rel,
        )

    milestone_rows, milestone_missing = _roadmap_milestone_rows(sections["milestones"])
    if milestone_missing:
        report.add_error(
            "roadmap_milestone_missing_columns",
            f"{rel} Milestones table is missing required columns: "
            f"{', '.join(ROADMAP_MILESTONE_REQUIRED_COLUMNS[column] for column in milestone_missing)}",
            rel,
        )
    elif not milestone_rows:
        report.add_error("roadmap_milestone_no_rows", f"{rel} must contain at least one milestone row", rel)
    else:
        seen_ids: set[str] = set()
        for row in milestone_rows:
            item_id = row.get("id", "").strip() or "(missing id)"
            missing_fields = [
                ROADMAP_MILESTONE_REQUIRED_COLUMNS[column]
                for column in ROADMAP_MILESTONE_REQUIRED_COLUMNS
                if _is_empty_roadmap_milestone_value(row.get(column, ""))
            ]
            if missing_fields:
                report.add_error(
                    "roadmap_milestone_row_missing_fields",
                    f"roadmap milestone row {item_id} is missing required fields: {', '.join(missing_fields)}",
                    rel,
                )
                continue
            if TASK_ID_RE.fullmatch(item_id) is None:
                report.add_error(
                    "roadmap_milestone_invalid_id",
                    f"roadmap milestone row {item_id} must use TASK-NNN task ID format",
                    rel,
                )
                continue
            status = row.get("status", "").strip()
            if _normalize_cell(status) not in TASK_BOARD_ALLOWED_STATUSES:
                report.add_error(
                    "roadmap_milestone_invalid_status",
                    f"roadmap milestone row {item_id} has invalid Status: {status}",
                    rel,
                )
                continue
            item_key = _normalize_cell(item_id)
            if item_key in seen_ids:
                report.add_error(
                    "roadmap_milestone_duplicate_id",
                    f"duplicate roadmap milestone ID: {item_id}",
                    rel,
                )
                continue
            seen_ids.add(item_key)

    references = _local_markdown_references(root, path, text, include_bare=True, strip_code=False)
    _check_design_reference_group(
        report,
        rel,
        references,
        "roadmap_trace_reference_missing",
        "Product",
        _is_product_scope_reference,
    )
    _check_design_reference_group(
        report,
        rel,
        references,
        "roadmap_trace_reference_missing",
        "Acceptance",
        _is_product_acceptance_reference_path,
    )


def _roadmap_milestone_rows(text: str) -> tuple[list[dict[str, str]], list[str]]:
    table = _markdown_table(text)
    if not table:
        return [], list(ROADMAP_MILESTONE_REQUIRED_COLUMNS)
    for index, row in enumerate(table):
        header = [_normalize_cell(cell) for cell in row]
        if not any(column in header for column in ROADMAP_MILESTONE_REQUIRED_COLUMNS):
            continue
        missing = [column for column in ROADMAP_MILESTONE_REQUIRED_COLUMNS if column not in header]
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
                    column: _table_cell(data, header.index(column))
                    for column in ROADMAP_MILESTONE_REQUIRED_COLUMNS
                }
            )
        return rows, []
    return [], list(ROADMAP_MILESTONE_REQUIRED_COLUMNS)


def _is_empty_roadmap_milestone_value(value: str) -> bool:
    return _normalize_cell(value) in TASK_BOARD_EMPTY_VALUES


def _check_roadmap_task_board_alignment(root: Path, report: VerificationReport) -> None:
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
            if TASK_ID_RE.fullmatch(item_id) is not None:
                report.add_error(
                    "roadmap_task_missing",
                    f"roadmap milestone {item_id} has no matching task board row",
                    ROADMAP_REL.as_posix(),
                )
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
        if column == "acceptance" and all(reference.exists for reference in references):
            product_acceptance_refs = [reference for reference in references if _is_product_acceptance_reference(reference)]
            acceptance_id = _task_board_acceptance_id(row.get(column, ""))
            if product_acceptance_refs and acceptance_id is None:
                errors.append((
                    "task_board_acceptance_id_missing",
                    f"task board row {task_id} Acceptance field must include A-NNN acceptance ID",
                ))
            elif product_acceptance_refs and acceptance_id is not None and not any(
                _product_acceptance_reference_has_id(root, reference, acceptance_id)
                for reference in product_acceptance_refs
            ):
                errors.append((
                    "task_board_acceptance_id_unknown",
                    f"task board row {task_id} Acceptance ID {acceptance_id} is not defined in referenced product acceptance chapter",
                ))
    return errors


def _task_board_acceptance_id(value: str) -> str | None:
    label = _plain_cell_label(value)
    match = ACCEPTANCE_ID_RE.search(label)
    if match is None:
        return None
    return match.group(0)


def _product_acceptance_reference_has_id(root: Path, reference: LocalMarkdownReference, acceptance_id: str) -> bool:
    try:
        text = (root / reference.rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return _text_contains_identifier(_strip_markdown_code(text), acceptance_id)


def _is_product_acceptance_reference(reference: LocalMarkdownReference) -> bool:
    return reference.exists and _is_product_acceptance_reference_path(reference)


def _is_product_acceptance_reference_path(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return (
        len(path.parts) == 3
        and path.parts[0] == "docs"
        and path.parts[1] == "product"
        and PRODUCT_CHAPTER_RE.fullmatch(path.parts[2]) is not None
        and "acceptance" in path.stem.lower()
    )


def _is_product_scope_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    if reference.rel == "docs/product/core/PRD.md":
        return True
    return (
        len(path.parts) == 3
        and path.parts[0] == "docs"
        and path.parts[1] == "product"
        and PRODUCT_CHAPTER_RE.fullmatch(path.parts[2]) is not None
        and "acceptance" not in path.stem.lower()
    )


def _is_api_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return len(path.parts) >= 2 and path.parts[0] == "docs" and path.parts[1] == "api"


def _is_architecture_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return len(path.parts) >= 2 and path.parts[0] == "docs" and path.parts[1] == "architecture"


def _is_ui_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return len(path.parts) >= 2 and path.parts[0] == "docs" and path.parts[1] == "ui"


def _is_design_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return len(path.parts) >= 2 and path.parts[0] == "docs" and path.parts[1] in {"architecture", "backend", "frontend"}


def _is_test_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return len(path.parts) >= 2 and path.parts[0] == "docs" and path.parts[1] == "tests"


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


def _plain_cell_label(value: str) -> str:
    value = _strip_markdown_code(value)
    value = re.sub(r"\[([^\]]*)]\([^)]*\)", r"\1", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" `*_")


def _markdown_sections(text: str, min_level: int = 1) -> dict[str, str]:
    matches = list(MARKDOWN_HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        marker = match.group(0).lstrip().split(maxsplit=1)[0]
        if len(marker) < min_level:
            continue
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
