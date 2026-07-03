from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable

try:
    from .bootstrap_tree import TARGET_LOCAL_COMMANDS, target_local_commands_payload
    from .state import StateFileError, load_state
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import TARGET_LOCAL_COMMANDS, target_local_commands_payload
    from state import StateFileError, load_state
    from workflow_actions import next_actions_payload


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
PRODUCT_IMPORT_STATUSES = ("conversion_required", "no_source", "ready_for_structuring")
UNRESOLVED_ID_RE = re.compile(r"^U-[0-9]{3}$")
TASK_ID_RE = re.compile(r"^TASK-[0-9]{3}$")
ACCEPTANCE_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])A-[0-9]{3}(?![A-Za-z0-9_-])")
FINDING_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
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
ADR_TEMPLATE_REL = Path("docs/decisions/_template.md")
ADR_TEMPLATE_GUARDRAILS = (
    "- Status: proposed",
    "- Date: YYYY-MM-DD",
    "- Related modules: TBD",
)
ADR_DECISION_RE = re.compile(r"^(?P<prefix>[0-9]{3})-[a-z0-9][a-z0-9-]*\.md$")
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
WORKFLOW_PACK_SNAPSHOT_ROOT = "docs/agent-workflow/workflow-pack"
WORKFLOW_PACK_IGNORED_FILE_NAMES = {".DS_Store", "manifest.json"}
MANIFEST_SCHEMA_VERSION = 1
RUNTIME_MANIFEST_SOURCE = "target-local governance runtime"
WORKFLOW_PACK_MANIFEST_SOURCE = "docs-as-code workflow pack"
GOVERNANCE_STATE_REL = Path(".governance/state.json")
WORKFLOW_PHASE_ORDER = ("initialized", "product-structuring", "design-derivation", "implementation")
WORKFLOW_PACK_REQUIRED_PATHS = (
    "README.md",
    "references/api-design-checklist.md",
    "references/architecture-methods.md",
    "references/backend-design-checklist.md",
    "references/community-practices.md",
    "references/runtime-strategy.md",
    "references/security-design-checklist.md",
    "skills/archiving-product-document/SKILL.md",
    "skills/capturing-architecture-decisions/SKILL.md",
    "skills/designing-api-contracts/SKILL.md",
    "skills/designing-backend-modules/SKILL.md",
    "skills/designing-data-models/SKILL.md",
    "skills/designing-frontend-modules/SKILL.md",
    "skills/designing-system-architecture/SKILL.md",
    "skills/designing-test-strategy/SKILL.md",
    "skills/designing-ui-interactions/SKILL.md",
    "skills/initializing-governance-repo/SKILL.md",
    "skills/planning-implementation-work/SKILL.md",
    "skills/structuring-product-requirements/SKILL.md",
    "skills/using-governance-workflow/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
    "templates/docs/agent-workflow/task-handoff.md",
    "templates/docs/api/00-conventions.md",
    "templates/docs/api/changelog.md",
    "templates/docs/api/endpoints/01-endpoint-contract.md",
    "templates/docs/api/endpoints/README.md",
    "templates/docs/api/error-codes.md",
    "templates/docs/architecture/01-system-context.md",
    "templates/docs/architecture/02-containers.md",
    "templates/docs/architecture/03-quality-attributes.md",
    "templates/docs/backend/01-modules.md",
    "templates/docs/backend/02-data-model.md",
    "templates/docs/backend/03-external-services.md",
    "templates/docs/decisions/ADR-template.md",
    "templates/docs/development/01-roadmap.md",
    "templates/docs/development/02-task-board.md",
    "templates/docs/development/03-verification-log.md",
    "templates/docs/frontend/01-modules.md",
    "templates/docs/frontend/02-api-consumption.md",
    "templates/docs/product/core/PRD.md",
    "templates/docs/tests/01-strategy.md",
    "templates/docs/tests/02-acceptance-matrix.md",
    "templates/docs/ui/01-interaction-model.md",
    "templates/root/README.md",
    "workflows/00-overview.md",
    "workflows/01-empty-repo-initialization.md",
    "workflows/02-product-document-archiving.md",
    "workflows/03-product-structuring.md",
    "workflows/04-design-derivation.md",
    "workflows/05-verification-and-drift-control.md",
)
RUNTIME_MANIFEST_REL = Path("docs/agent-workflow/runtime-manifest.json")
PRODUCT_SOURCE_ARCHIVE_ROOT = Path("docs/product/core/source")
PRODUCT_SOURCE_MANIFEST_REL = Path("docs/product/core/source/source-manifest.json")
PRODUCT_SOURCE_MANIFEST_TEMP_REL = Path("docs/product/core/source/.source-manifest.json.tmp")
RUNTIME_REQUIRED_BIN_FILES = (
    "governance",
    "governance-init",
    "governance-verify",
)
RUNTIME_REQUIRED_SCRIPT_FILES = (
    "__init__.py",
    "bootstrap_tree.py",
    "check_env.py",
    "gates.py",
    "governance_cli.py",
    "phases.py",
    "product_import.py",
    "scaffold.py",
    "state.py",
    "verify_governance.py",
    "workflow_actions.py",
)
RUNTIME_REQUIRED_PATHS = tuple(
    sorted(
        [Path("bin") / name for name in RUNTIME_REQUIRED_BIN_FILES]
        + [Path("scripts") / name for name in RUNTIME_REQUIRED_SCRIPT_FILES],
        key=lambda path: path.as_posix(),
    )
)
RUNTIME_EXECUTABLE_PATHS = tuple(Path("bin") / name for name in RUNTIME_REQUIRED_BIN_FILES)
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
VERIFICATION_LOG_REL = Path("docs/development/03-verification-log.md")
VERIFICATION_LOG_REQUIRED_SECTIONS = {
    "verification runs": "Verification Runs",
    "artifacts": "Artifacts",
    "open follow-ups": "Open Follow-ups",
}
VERIFICATION_LOG_REQUIRED_COLUMNS = {
    "task": "Task",
    "command": "Command",
    "result": "Result",
    "date": "Date",
    "notes": "Notes",
}
SECTION_PLACEHOLDER_VALUES = {"", "-", "tbd", "todo", "n/a", "na"}
ROOT_AGENTS_SOURCE_OF_TRUTH_GUARDRAILS = (
    "docs/product/core/prd.md",
    "docs/product/core/product-meta.md",
    "docs/product/nn-*.md",
    "docs/api/",
    "docs/architecture/",
    "docs/ui/",
    "docs/backend/",
    "docs/frontend/",
    "docs/tests/",
    "docs/development/",
)
ROOT_AGENTS_AGENT_RULE_GUARDRAILS = (
    "read docs/development/readme.md before implementation planning",
    "register unresolved product, api, db, or cross-module questions in docs/unresolved.md and ask",
    "do not silently modify upstream product meaning",
    "traceable to specs",
)
DOCS_AGENTS_REGISTERED_DIRECTORY_GUARDRAILS = tuple(f"docs/{name}/" for name in sorted(DOC_DIRS))
DOCS_AGENTS_RULE_GUARDRAILS = (
    "every non-empty top-level docs directory must have readme.md and agents.md",
    "do not create unregistered docs directories",
    "remove any reserved marker once a directory contains real content",
    "keep links relative and stable",
    "follow repository source-of-truth priority in root agents.md",
)
DOCS_README_GUARDRAILS = (
    "documentation is managed as code",
    "domain directories are listed below",
    *(f"{name}/" for name in sorted(DOC_DIRS)),
    "core cross-domain files",
    "unresolved.md",
    "glossary.md",
)
DOMAIN_AGENTS_RULE_GUARDRAILS = (
    "keep this directory focused on its declared domain",
    "update readme.md when adding or renaming documents",
    "link back to upstream source documents instead of copying large sections",
)
TARGET_MAKEFILE_REQUIRED_TARGETS = tuple(
    target for target, _recipe, _description, _writes_state in TARGET_LOCAL_COMMANDS
)
TARGET_MAKEFILE_REQUIRED_TARGET_RECIPES = {
    target: (recipe,)
    for target, recipe, _description, _writes_state in TARGET_LOCAL_COMMANDS
}
TARGET_LOCAL_MAKE_COMMANDS = tuple(
    f"make {target}"
    for target, _recipe, _description, _writes_state in TARGET_LOCAL_COMMANDS
)
TARGET_SUPPORT_FILE_GUARDRAILS = {
    "CONTRIBUTING.md": (
        "docs/agent-workflow/task-handoff.md",
        "task handoff and completion criteria",
    ),
    "GOVERNANCE.md": (
        "repository governance is defined by agents.md, docs/agents.md, and domain-level agents.md files",
    ),
    "SECURITY.md": (
        "do not commit secrets",
        "authentication, authorization, and data boundary decisions must be documented before implementation",
    ),
}
TARGET_ENTRY_DOC_GUARDRAILS = {
    "README.md": (
        "initialized with the docs-as-code governance workflow pack",
        "docs/product/core/prd.md",
        "docs/readme.md",
        "agents.md and docs/agents.md",
        "docs/agent-workflow/workflow-pack/",
        "docs/unresolved.md",
        "docs/development/readme.md",
        *TARGET_LOCAL_MAKE_COMMANDS,
    ),
    "SPEC.md": (
        "summary view",
        "must not become an independent source of truth",
        "docs/product/core/prd.md",
        "docs/product/core/product-meta.md",
    ),
}
TARGET_GITIGNORE_REQUIRED_PATTERNS = (
    ".governance/",
    ".lycheecache",
    "__pycache__/",
    "*.pyc",
    "node_modules/",
    ".venv/",
)
TASK_HANDOFF_REL = Path("docs/agent-workflow/task-handoff.md")
TASK_HANDOFF_REQUIRED_SECTIONS = {
    "task goal": "Task Goal",
    "related specs": "Related Specs",
    "definition of done": "Definition of Done",
    "verification record": "Verification Record",
    "handoff notes": "Handoff Notes",
}
TASK_HANDOFF_RELATED_SPEC_GUARDRAILS = (
    "product:",
    "api:",
    "architecture:",
    "acceptance:",
)
TASK_HANDOFF_DOD_GUARDRAILS = (
    "code and tests are complete",
    "documentation is synchronized",
    "verification commands pass and output is recorded",
)
TASK_HANDOFF_VERIFICATION_GUARDRAILS = (
    "command",
    "result",
    "evidence",
)
TASK_HANDOFF_NOTES_GUARDRAILS = (
    "open follow-ups:",
    "risks:",
)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(r"^\s{0,3}\[[^\]]+]:\s*(\S+)", re.MULTILINE)
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
BARE_MARKDOWN_REFERENCE_RE = re.compile(
    r"((?:\.{1,2}/)?docs/[^\s`<>\]),;]+\.md(?:#[^\s`<>\]),;]+)?|"
    r"(?:\.{1,2}/)[^\s`<>\]),;]+\.md(?:#[^\s`<>\]),;]+)?)"
)
VERIFICATION_FINDING_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERIFICATION_FINDING_SEVERITIES = {"error", "warning"}


@dataclass
class VerificationFinding:
    code: str
    severity: str
    message: str
    path: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not VERIFICATION_FINDING_CODE_RE.fullmatch(self.code):
            raise ValueError("verification finding code must use lowercase snake_case")
        if self.severity not in VERIFICATION_FINDING_SEVERITIES:
            raise ValueError("verification finding severity must be error or warning")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("verification finding message must be a non-empty string")
        if not isinstance(self.path, str):
            raise ValueError("verification finding path must be a string")

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

    def __post_init__(self) -> None:
        if not isinstance(self.errors, list) or not all(isinstance(error, str) for error in self.errors):
            raise ValueError("verification report errors must be strings")
        if not isinstance(self.warnings, list) or not all(isinstance(warning, str) for warning in self.warnings):
            raise ValueError("verification report warnings must be strings")
        if not isinstance(self.findings, list):
            raise ValueError("verification report findings must be a list")
        if not all(isinstance(finding, VerificationFinding) for finding in self.findings):
            raise ValueError("verification report findings must contain VerificationFinding entries")
        if self.errors != [finding.message for finding in self.findings if finding.severity == "error"]:
            raise ValueError("verification report errors must match error findings")
        if self.warnings != [finding.message for finding in self.findings if finding.severity == "warning"]:
            raise ValueError("verification report warnings must match warning findings")

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def add_error(self, code: str, message: str, path: str = "") -> None:
        finding = VerificationFinding(code=code, severity="error", path=path, message=message)
        self.errors.append(finding.message)
        self.findings.append(finding)

    def add_warning(self, code: str, message: str, path: str = "") -> None:
        finding = VerificationFinding(code=code, severity="warning", path=path, message=message)
        self.warnings.append(finding.message)
        self.findings.append(finding)


def verify(root: Path) -> VerificationReport:
    root = root.resolve()
    report = VerificationReport()

    required_directories = [
        "docs",
    ]
    for rel in required_directories:
        path = root / rel
        if path.exists() and not path.is_dir():
            report.add_error("required_directory_not_directory", f"required directory is not a directory: {rel}", rel)

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
        path = root / rel
        if not path.exists():
            report.add_error("missing_required_file", f"missing required file: {rel}", rel)
        elif not path.is_file():
            report.add_error("required_file_not_file", f"required file is not a file: {rel}", rel)

    docs_root = root / "docs"
    docs_agents = docs_root / "AGENTS.md"
    docs_agents_text = ""
    if docs_agents.is_file():
        docs_agents_text = _read_markdown_text(root, docs_agents, report) or ""

    if docs_root.is_dir():
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
                    governance_file = child / name
                    if not governance_file.exists():
                        report.add_error("docs_directory_missing_governance_file", f"{rel} is missing {name}", f"{rel}/{name}")
                    elif not governance_file.is_file():
                        report.add_error(
                            "docs_directory_governance_file_not_file",
                            f"{rel}/{name} is not a file",
                            f"{rel}/{name}",
                        )

    for path in [root / "README.md", docs_root / "README.md", docs_agents]:
        if path.is_file():
            _check_reserved_markers(root, path, report)

    _check_governance_state(root, report)
    _check_target_entry_docs(root, report)
    _check_target_support_files(root, report)
    _check_target_gitignore(root, report)
    _check_target_makefile(root, report)
    _check_task_handoff(root, report)
    _check_root_agents_guardrails(root, report)
    _check_docs_readme_guardrails(root, report)
    _check_docs_agents_guardrails(root, report)
    _check_domain_agents_guardrails(root, report)
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
    _check_adr_template(root, report)
    _check_architecture_decisions(root, report)
    _check_unresolved_items(root, report)
    _check_glossary_items(root, report)
    _check_readme_indexes(root, report)
    _check_local_markdown_links(root, report)
    _check_scaffold_placeholders(root, report)
    _check_runtime_manifest(root, report)
    _check_workflow_pack_manifest(root, report)
    _check_task_board(root, report)
    _check_verification_log(root, report)
    _check_roadmap(root, report)
    _check_roadmap_task_board_alignment(root, report)
    _check_task_board_acceptance_matrix_alignment(root, report)

    return report


def _is_effectively_empty(path: Path) -> bool:
    return not any(child.name != ".gitkeep" for child in path.iterdir())


def _read_markdown_text(root: Path, path: Path, report: VerificationReport) -> str | None:
    rel = path.relative_to(root).as_posix()
    if not path.is_file():
        if not any(finding.code == "markdown_not_file" and finding.path == rel for finding in report.findings):
            report.add_error(
                "markdown_not_file",
                f"Markdown path is not a file: {rel}",
                rel,
            )
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        if not any(finding.code == "markdown_invalid_encoding" and finding.path == rel for finding in report.findings):
            report.add_error(
                "markdown_invalid_encoding",
                f"invalid Markdown encoding: {rel} must be UTF-8",
                rel,
            )
        return None


def _check_governance_state(root: Path, report: VerificationReport) -> None:
    rel = GOVERNANCE_STATE_REL.as_posix()
    path = root / GOVERNANCE_STATE_REL
    if not path.exists():
        report.add_error("state_file_missing", f"missing governance state file: {rel}", rel)
        return
    if not path.is_file():
        report.add_error("state_file_not_file", f"governance state path is not a file: {rel}", rel)
        return
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        report.add_error("state_file_invalid_encoding", "invalid governance state encoding: expected UTF-8", rel)
        return
    except json.JSONDecodeError as error:
        report.add_error("state_file_invalid_json", f"invalid governance state: {error.msg}", rel)
        return
    if not isinstance(state, dict):
        report.add_error("state_file_invalid_schema", "invalid governance state: root must be an object", rel)
        return

    phase = state.get("phase")
    phase_is_valid = isinstance(phase, str) and phase in WORKFLOW_PHASE_ORDER
    if not phase_is_valid:
        report.add_error("state_phase_invalid", f"governance state phase is invalid: {phase}", rel)

    _check_governance_state_timestamps(state, rel, report)
    _check_governance_state_product_import_cache(root, state, rel, report)
    _check_governance_last_verification(state, rel, report)

    if phase_is_valid and phase == "initialized" and "last_gate" in state:
        report.add_error(
            "state_phase_last_gate_stale",
            "governance state last_gate must be absent while phase is initialized",
            rel,
        )
        return
    if phase_is_valid and phase == "initialized" and "phase_history" in state:
        report.add_error(
            "state_phase_history_stale",
            "governance state phase_history must be absent while phase is initialized",
            rel,
        )
        return

    history = state.get("phase_history")
    if history is None:
        if phase_is_valid and phase != "initialized":
            report.add_error(
                "state_phase_history_missing",
                f"governance state phase_history is required after phase {phase}",
                rel,
            )
        return
    if not isinstance(history, list):
        report.add_error("state_phase_history_invalid", "governance state phase_history must be a list", rel)
        return
    if not history:
        if phase_is_valid and phase != "initialized":
            report.add_error(
                "state_phase_history_missing",
                f"governance state phase_history is required after phase {phase}",
                rel,
            )
        return

    expected_from_phase = "initialized"
    previous_index = WORKFLOW_PHASE_ORDER.index(expected_from_phase)
    previous_advanced_at: datetime | None = None
    latest_phase = ""
    latest_history_item: dict[str, object] | None = None
    for item in history:
        if not isinstance(item, dict):
            report.add_error(
                "state_phase_history_invalid",
                "governance state phase_history entries must be objects",
                rel,
            )
            return
        item_phase = item.get("phase")
        if not isinstance(item_phase, str) or item_phase not in WORKFLOW_PHASE_ORDER:
            report.add_error(
                "state_phase_history_phase_invalid",
                f"governance state phase_history phase is invalid: {item_phase}",
                rel,
            )
            return
        item_index = WORKFLOW_PHASE_ORDER.index(item_phase)
        if item_index <= previous_index:
            report.add_error(
                "state_phase_history_non_monotonic",
                "governance state phase_history must move forward without repeats or rollback",
                rel,
            )
            return
        from_phase = item.get("from_phase")
        if from_phase != expected_from_phase:
            report.add_error(
                "state_phase_history_from_mismatch",
                f"governance state phase_history from_phase {from_phase} must match previous phase {expected_from_phase}",
                rel,
            )
            return
        expected_next_index = previous_index + 1
        if item_index != expected_next_index:
            skipped_phase = WORKFLOW_PHASE_ORDER[expected_next_index]
            report.add_error(
                "state_phase_history_non_sequential",
                "governance state phase_history must advance one phase at a time: "
                f"{expected_from_phase} -> {item_phase} skips {skipped_phase}",
                rel,
            )
            return
        gate = item.get("gate")
        if gate != item_phase:
            report.add_error(
                "state_phase_history_gate_mismatch",
                f"governance state phase_history gate {gate} must match phase {item_phase}",
                rel,
            )
            return
        advanced_at = item.get("advanced_at")
        if not isinstance(advanced_at, str) or not advanced_at:
            report.add_error(
                "state_phase_history_advanced_at_missing",
                f"governance state phase_history for phase {item_phase} must include advanced_at",
                rel,
            )
            return
        if not _is_iso_timestamp_with_timezone(advanced_at):
            report.add_error(
                "state_phase_history_advanced_at_invalid",
                f"governance state phase_history advanced_at for phase {item_phase} "
                "must be an ISO timestamp with timezone",
                rel,
            )
            return
        current_advanced_at = _parse_iso_timestamp_with_timezone(advanced_at)
        if (
            previous_advanced_at is not None
            and current_advanced_at is not None
            and current_advanced_at < previous_advanced_at
        ):
            report.add_error(
                "state_phase_history_advanced_at_order",
                "governance state phase_history advanced_at must not move backward",
                rel,
            )
            return
        previous_index = item_index
        previous_advanced_at = current_advanced_at
        latest_phase = item_phase
        latest_history_item = item
        expected_from_phase = item_phase

    updated_at = state.get("updated_at")
    updated_at_timestamp = (
        _parse_iso_timestamp_with_timezone(updated_at) if isinstance(updated_at, str) else None
    )
    latest_advanced_at = latest_history_item.get("advanced_at") if latest_history_item else None
    latest_advanced_at_timestamp = (
        _parse_iso_timestamp_with_timezone(latest_advanced_at) if isinstance(latest_advanced_at, str) else None
    )
    if (
        updated_at_timestamp is not None
        and latest_advanced_at_timestamp is not None
        and updated_at_timestamp < latest_advanced_at_timestamp
    ):
        report.add_error(
            "state_timestamp_updated_at_phase_stale",
            "governance state updated_at must not be older than latest phase_history advanced_at",
            rel,
        )
        return

    if phase_is_valid and latest_phase and latest_phase != phase:
        report.add_error(
            "state_phase_history_current_mismatch",
            f"governance state current phase {phase} must match latest phase_history phase {latest_phase}",
            rel,
        )
        return

    if phase_is_valid and phase != "initialized":
        last_gate = state.get("last_gate")
        if last_gate is None:
            report.add_error(
                "state_phase_last_gate_missing",
                f"governance state last_gate is required after phase {phase}",
                rel,
            )
            return
        if not isinstance(last_gate, dict):
            report.add_error("state_phase_last_gate_invalid", "governance state last_gate must be an object", rel)
            return
        gate_name = last_gate.get("name")
        if gate_name != phase:
            report.add_error(
                "state_phase_last_gate_name_mismatch",
                f"governance state last_gate name {gate_name} must match current phase {phase}",
                rel,
            )
            return
        if last_gate.get("ok") is not True:
            report.add_error(
                "state_phase_last_gate_not_ok",
                f"governance state last_gate for phase {phase} must have ok: true",
                rel,
            )
            return
        checked_at = last_gate.get("checked_at")
        if not isinstance(checked_at, str) or not checked_at:
            report.add_error(
                "state_phase_last_gate_checked_at_missing",
                f"governance state last_gate for phase {phase} must include checked_at",
                rel,
            )
            return
        if not _is_iso_timestamp_with_timezone(checked_at):
            report.add_error(
                "state_phase_last_gate_checked_at_invalid",
                f"governance state last_gate checked_at for phase {phase} must be an ISO timestamp with timezone",
                rel,
            )
            return
        latest_advanced_at = latest_history_item.get("advanced_at") if latest_history_item else None
        if isinstance(latest_advanced_at, str) and latest_advanced_at and checked_at != latest_advanced_at:
            report.add_error(
                "state_phase_last_gate_checked_at_mismatch",
                "governance state last_gate checked_at must match latest phase_history advanced_at",
                rel,
            )


def _check_governance_state_timestamps(state: dict[str, object], rel: str, report: VerificationReport) -> None:
    updated_at = state.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        report.add_error(
            "state_timestamp_updated_at_missing",
            "governance state must include updated_at",
            rel,
        )
        return
    updated_at_timestamp = _parse_iso_timestamp_with_timezone(updated_at)
    if updated_at_timestamp is None:
        report.add_error(
            "state_timestamp_updated_at_invalid",
            "governance state updated_at must be an ISO timestamp with timezone",
            rel,
        )
        return
    last_verification = state.get("last_verification")
    if not isinstance(last_verification, dict):
        return
    checked_at = last_verification.get("checked_at")
    if not isinstance(checked_at, str):
        return
    checked_at_timestamp = _parse_iso_timestamp_with_timezone(checked_at)
    if checked_at_timestamp is None:
        return
    if updated_at_timestamp < checked_at_timestamp:
        report.add_error(
            "state_timestamp_updated_at_stale",
            "governance state updated_at must not be older than last_verification.checked_at",
            rel,
        )


def _check_governance_state_product_import_cache(
    root: Path,
    state: dict[str, object],
    rel: str,
    report: VerificationReport,
) -> None:
    manifest = _load_product_source_manifest_object(root)
    if manifest is None:
        return
    archive = manifest.get("archive")
    imported = manifest.get("import")
    if not isinstance(archive, dict) or not isinstance(imported, dict):
        return

    expected_status = imported.get("status")
    if isinstance(expected_status, str) and state.get("product_import_status") != expected_status:
        report.add_error(
            "state_product_import_status_mismatch",
            "governance state product_import_status must match product source manifest import.status",
            rel,
        )
        return
    expected_can_derive_design = imported.get("can_derive_design")
    if (
        isinstance(expected_can_derive_design, bool)
        and state.get("product_can_derive_design") != expected_can_derive_design
    ):
        report.add_error(
            "state_product_import_can_derive_design_mismatch",
            "governance state product_can_derive_design must match product source manifest import.can_derive_design",
            rel,
        )
        return
    expected_archived_product = archive.get("path")
    if (isinstance(expected_archived_product, str) or expected_archived_product is None) and state.get(
        "archived_product"
    ) != expected_archived_product:
        report.add_error(
            "state_product_archive_mismatch",
            "governance state archived_product must match product source manifest archive.path",
            rel,
        )


def _load_product_source_manifest_object(root: Path) -> dict[str, object] | None:
    manifest_path = root / "docs/product/core/source/source-manifest.json"
    if not manifest_path.exists() or not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return manifest if isinstance(manifest, dict) else None


def _check_governance_last_verification(state: dict[str, object], rel: str, report: VerificationReport) -> None:
    last_verification = state.get("last_verification")
    if last_verification is None:
        return
    if not isinstance(last_verification, dict):
        report.add_error(
            "state_last_verification_invalid",
            "governance state last_verification must be an object",
            rel,
        )
        return
    if not isinstance(last_verification.get("ok"), bool):
        report.add_error(
            "state_last_verification_ok_invalid",
            "governance state last_verification ok must be a boolean",
            rel,
        )
        return
    for key in ("errors", "warnings", "findings"):
        if not isinstance(last_verification.get(key), list):
            report.add_error(
                "state_last_verification_field_invalid",
                f"governance state last_verification {key} must be a list",
                rel,
            )
            return
    for key in ("errors", "warnings"):
        for item in last_verification[key]:
            if not isinstance(item, str):
                report.add_error(
                    "state_last_verification_field_invalid",
                    f"governance state last_verification {key} entries must be strings",
                    rel,
                )
                return
    for finding in last_verification["findings"]:
        if not isinstance(finding, dict):
            report.add_error(
                "state_last_verification_finding_invalid",
                "governance state last_verification findings entries must be objects",
                rel,
            )
            return
        for key in ("code", "severity", "path", "message"):
            if not isinstance(finding.get(key), str):
                report.add_error(
                    "state_last_verification_finding_invalid",
                    f"governance state last_verification findings entries must include string {key}",
                    rel,
                )
                return
        for key in ("code", "path", "message"):
            value = finding.get(key)
            if isinstance(value, str) and not value.strip():
                report.add_error(
                    "state_last_verification_finding_invalid",
                    f"governance state last_verification findings entries must include non-empty string {key}",
                    rel,
                )
                return
        finding_path = finding.get("path")
        if isinstance(finding_path, str):
            posix_path = PurePosixPath(finding_path)
            windows_path = PureWindowsPath(finding_path)
            normalized_path = posix_path.as_posix()
            if (
                posix_path.is_absolute()
                or windows_path.is_absolute()
                or ".." in posix_path.parts
                or ".." in windows_path.parts
            ):
                report.add_error(
                    "state_last_verification_finding_invalid",
                    "governance state last_verification findings path must be repository-relative",
                    rel,
                )
                return
            if "\\" in finding_path or finding_path != normalized_path:
                report.add_error(
                    "state_last_verification_finding_invalid",
                    "governance state last_verification findings path must use normalized POSIX form",
                    rel,
                )
                return
        finding_code = finding.get("code")
        if isinstance(finding_code, str) and not FINDING_CODE_RE.match(finding_code):
            report.add_error(
                "state_last_verification_finding_invalid",
                "governance state last_verification findings code must use lowercase snake_case",
                rel,
            )
            return
        if finding.get("severity") not in {"error", "warning"}:
            report.add_error(
                "state_last_verification_finding_invalid",
                "governance state last_verification findings severity must be error or warning",
                rel,
            )
            return
    has_error_finding = any(finding.get("severity") == "error" for finding in last_verification["findings"])
    if last_verification["ok"] is True and last_verification["errors"]:
        report.add_error(
            "state_last_verification_ok_mismatch",
            "governance state last_verification ok must be false when errors are present",
            rel,
        )
        return
    if last_verification["ok"] is True and has_error_finding:
        report.add_error(
            "state_last_verification_ok_mismatch",
            "governance state last_verification ok must be false when error findings are present",
            rel,
        )
        return
    if last_verification["ok"] is False and not last_verification["errors"] and not has_error_finding:
        report.add_error(
            "state_last_verification_ok_mismatch",
            "governance state last_verification ok must be true when no errors or error findings are present",
            rel,
        )
        return
    for summary_key, severity in (("errors", "error"), ("warnings", "warning")):
        finding_messages = [
            finding["message"]
            for finding in last_verification["findings"]
            if finding["severity"] == severity
        ]
        if last_verification[summary_key] != finding_messages:
            report.add_error(
                "state_last_verification_summary_mismatch",
                f"governance state last_verification {summary_key} must match {severity} finding messages",
                rel,
            )
            return
    checked_at = last_verification.get("checked_at")
    if not isinstance(checked_at, str) or not checked_at:
        report.add_error(
            "state_last_verification_checked_at_missing",
            "governance state last_verification must include checked_at",
            rel,
        )
        return
    if not _is_iso_timestamp_with_timezone(checked_at):
        report.add_error(
            "state_last_verification_checked_at_invalid",
            "governance state last_verification checked_at must be an ISO timestamp with timezone",
            rel,
        )


def _is_iso_timestamp_with_timezone(value: str) -> bool:
    return _parse_iso_timestamp_with_timezone(value) is not None


def _parse_iso_timestamp_with_timezone(value: str) -> datetime | None:
    if "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _check_reserved_markers(root: Path, path: Path, report: VerificationReport) -> None:
    if not path.is_file():
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    for line in text.splitlines():
        if "预留" not in line and "[reserved]" not in line.lower():
            continue
        for match in re.finditer(r"docs/([a-z0-9-]+)", line):
            name = match.group(1)
            target = root / "docs" / name
            if target.exists() and target.is_dir() and not _is_effectively_empty(target):
                report.add_error("reserved_marker_stale", f"reserved marker references non-empty docs/{name}", f"docs/{name}")


def _check_task_handoff(root: Path, report: VerificationReport) -> None:
    rel = TASK_HANDOFF_REL.as_posix()
    path = root / TASK_HANDOFF_REL
    if not path.exists():
        report.add_error("target_task_handoff_missing", f"missing required agent handoff file: {rel}", rel)
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    sections = _markdown_sections(text, min_level=2)
    missing_sections = [
        title
        for key, title in TASK_HANDOFF_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing_sections:
        report.add_error(
            "target_task_handoff_section_missing",
            f"{rel} is missing required sections: {', '.join(missing_sections)}",
            rel,
        )
        return
    _check_task_handoff_section_guardrails(
        rel,
        "Related Specs",
        sections["related specs"],
        TASK_HANDOFF_RELATED_SPEC_GUARDRAILS,
        report,
    )
    _check_task_handoff_section_guardrails(
        rel,
        "Definition of Done",
        sections["definition of done"],
        TASK_HANDOFF_DOD_GUARDRAILS,
        report,
    )
    _check_task_handoff_section_guardrails(
        rel,
        "Verification Record",
        sections["verification record"],
        TASK_HANDOFF_VERIFICATION_GUARDRAILS,
        report,
    )
    _check_task_handoff_section_guardrails(
        rel,
        "Handoff Notes",
        sections["handoff notes"],
        TASK_HANDOFF_NOTES_GUARDRAILS,
        report,
    )


def _check_task_handoff_section_guardrails(
    rel: str,
    section_title: str,
    section_text: str,
    guardrails: tuple[str, ...],
    report: VerificationReport,
) -> None:
    normalized = _normalize_guardrail_text(section_text)
    for guardrail in guardrails:
        if guardrail in normalized:
            continue
        report.add_error(
            "target_task_handoff_guardrail_missing",
            f"{rel} {section_title} section must preserve guardrail: {guardrail}",
            rel,
        )


def _check_target_gitignore(root: Path, report: VerificationReport) -> None:
    rel = ".gitignore"
    path = root / rel
    if not path.exists():
        report.add_error("target_gitignore_missing", "missing required target ignore file: .gitignore", rel)
        return
    if not path.is_file():
        report.add_error("target_gitignore_not_file", "target ignore path is not a file: .gitignore", rel)
        return
    text = _read_target_text_file(path, rel, "target_gitignore", report)
    if text is None:
        return
    patterns = _gitignore_patterns(text)
    for pattern in TARGET_GITIGNORE_REQUIRED_PATTERNS:
        if pattern in patterns:
            continue
        report.add_error(
            "target_gitignore_pattern_missing",
            f".gitignore must ignore generated/local path: {pattern}",
            rel,
        )


def _gitignore_patterns(text: str) -> set[str]:
    patterns: set[str] = set()
    for line in text.splitlines():
        pattern = line.strip()
        if not pattern or pattern.startswith("#"):
            continue
        patterns.add(pattern)
    return patterns


def _check_target_entry_docs(root: Path, report: VerificationReport) -> None:
    for rel, guardrails in TARGET_ENTRY_DOC_GUARDRAILS.items():
        path = root / rel
        if not path.is_file():
            continue
        text = _read_markdown_text(root, path, report)
        if text is None:
            continue
        _check_target_text_guardrails(
            rel,
            text,
            guardrails,
            report,
            code="target_entry_doc_guardrail_missing",
        )


def _check_target_support_files(root: Path, report: VerificationReport) -> None:
    for rel, guardrails in TARGET_SUPPORT_FILE_GUARDRAILS.items():
        path = root / rel
        if not path.exists():
            report.add_error("target_support_file_missing", f"missing required target support file: {rel}", rel)
            continue
        if not path.is_file():
            report.add_error("target_support_file_not_file", f"target support file is not a file: {rel}", rel)
            continue
        text = _read_target_text_file(path, rel, "target_support_file", report)
        if text is None:
            continue
        _check_target_text_guardrails(
            rel,
            text,
            guardrails,
            report,
            code="target_support_file_guardrail_missing",
        )


def _check_target_text_guardrails(
    rel: str,
    text: str,
    guardrails: tuple[str, ...],
    report: VerificationReport,
    *,
    code: str,
) -> None:
    normalized = _normalize_guardrail_text(text)
    for guardrail in guardrails:
        if guardrail in normalized:
            continue
        report.add_error(
            code,
            f"{rel} must preserve guardrail: {guardrail}",
            rel,
        )


def _read_target_text_file(path: Path, rel: str, code_prefix: str, report: VerificationReport) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.add_error(f"{code_prefix}_invalid_encoding", f"{rel} must be UTF-8", rel)
    except OSError as error:
        reason = error.strerror or str(error)
        report.add_error(f"{code_prefix}_unreadable", f"{rel} is unreadable: {reason}", rel)
    return None


def _check_target_makefile(root: Path, report: VerificationReport) -> None:
    path = root / "Makefile"
    if not path.exists():
        report.add_error("target_makefile_missing", "missing required target Makefile: Makefile", "Makefile")
        return
    if not path.is_file():
        report.add_error("target_makefile_not_file", "target Makefile is not a file: Makefile", "Makefile")
        return
    text = _read_target_text_file(path, "Makefile", "target_makefile", report)
    if text is None:
        return
    target_recipes = _makefile_target_recipes(text)
    targets = set(target_recipes)
    for target in TARGET_MAKEFILE_REQUIRED_TARGETS:
        if target in targets:
            continue
        report.add_error(
            "target_makefile_target_missing",
            f"Makefile must define target: {target}",
            "Makefile",
        )
    for target, required_recipes in TARGET_MAKEFILE_REQUIRED_TARGET_RECIPES.items():
        if target not in targets:
            continue
        recipes = set(target_recipes[target])
        for recipe in required_recipes:
            if recipe in recipes:
                continue
            report.add_error(
                "target_makefile_target_recipe_missing",
                f"Makefile target {target} must run command: {recipe}",
                "Makefile",
            )


def _check_root_agents_guardrails(root: Path, report: VerificationReport) -> None:
    path = root / "AGENTS.md"
    if not path.is_file():
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    sections = _markdown_sections(text, min_level=2)
    _check_agents_section_guardrails(
        report,
        sections,
        "source-of-truth priority",
        "Source-of-Truth Priority",
        ROOT_AGENTS_SOURCE_OF_TRUTH_GUARDRAILS,
    )
    _check_agents_section_guardrails(
        report,
        sections,
        "agent rules",
        "Agent Rules",
        ROOT_AGENTS_AGENT_RULE_GUARDRAILS,
    )


def _check_docs_agents_guardrails(root: Path, report: VerificationReport) -> None:
    path = root / "docs/AGENTS.md"
    if not path.is_file():
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    sections = _markdown_sections(text, min_level=2)
    _check_agents_section_guardrails(
        report,
        sections,
        "registered directories",
        "Registered Directories",
        DOCS_AGENTS_REGISTERED_DIRECTORY_GUARDRAILS,
        document="docs/AGENTS.md",
        section_missing_code="docs_agents_section_missing",
        guardrail_missing_code="docs_agents_guardrail_missing",
    )
    _check_agents_section_guardrails(
        report,
        sections,
        "rules",
        "Rules",
        DOCS_AGENTS_RULE_GUARDRAILS,
        document="docs/AGENTS.md",
        section_missing_code="docs_agents_section_missing",
        guardrail_missing_code="docs_agents_guardrail_missing",
    )


def _check_docs_readme_guardrails(root: Path, report: VerificationReport) -> None:
    path = root / "docs/README.md"
    if not path.is_file():
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    _check_target_text_guardrails(
        "docs/README.md",
        text,
        DOCS_README_GUARDRAILS,
        report,
        code="docs_readme_guardrail_missing",
    )


def _check_domain_agents_guardrails(root: Path, report: VerificationReport) -> None:
    docs_root = root / "docs"
    if not docs_root.is_dir():
        return
    for name in sorted(DOC_DIRS):
        path = docs_root / name / "AGENTS.md"
        if not path.is_file():
            continue
        text = _read_markdown_text(root, path, report)
        if text is None:
            continue
        rel = path.relative_to(root).as_posix()
        sections = _markdown_sections(text, min_level=2)
        _check_agents_section_guardrails(
            report,
            sections,
            "rules",
            "Rules",
            DOMAIN_AGENTS_RULE_GUARDRAILS,
            document=rel,
            section_missing_code="domain_agents_section_missing",
            guardrail_missing_code="domain_agents_guardrail_missing",
        )


def _check_agents_section_guardrails(
    report: VerificationReport,
    sections: dict[str, str],
    section_key: str,
    section_title: str,
    guardrails: tuple[str, ...],
    *,
    document: str = "AGENTS.md",
    section_missing_code: str = "root_agents_section_missing",
    guardrail_missing_code: str = "root_agents_guardrail_missing",
) -> None:
    section = sections.get(section_key)
    if section is None:
        report.add_error(
            section_missing_code,
            f"{document} is missing required section: {section_title}",
            document,
        )
        return
    normalized = _normalize_guardrail_text(section)
    for guardrail in guardrails:
        if guardrail in normalized:
            continue
        report.add_error(
            guardrail_missing_code,
            f"{document} {section_title} section must preserve guardrail: {guardrail}",
            document,
        )


def _normalize_guardrail_text(text: str) -> str:
    text = _strip_fenced_markdown_code(text)
    text = re.sub(r"\[([^\]]*)]\(([^)]*)\)", r"\1 \2", text)
    text = text.replace("`", "")
    return re.sub(r"\s+", " ", text.strip().lower())


def _check_product_source_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / "docs/product/core/source/source-manifest.json"
    if not manifest_path.exists():
        return
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        report.add_error(
            "product_source_manifest_invalid_encoding",
            "invalid product source manifest encoding: expected UTF-8",
            "docs/product/core/source/source-manifest.json",
        )
        return
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
    if not isinstance(status, str) or status not in PRODUCT_IMPORT_STATUSES:
        report.add_error(
            "product_source_import_status_invalid",
            f"invalid product import status: {status}; expected one of {', '.join(PRODUCT_IMPORT_STATUSES)}",
            "docs/product/core/source/source-manifest.json",
        )
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
    if not _is_valid_product_source_archive_path(archived_rel):
        report.add_error(
            "product_source_manifest_archive_path_invalid",
            "invalid product source manifest: archive.path must be a relative path under docs/product/core/source",
            "docs/product/core/source/source-manifest.json",
        )
        return

    archived_path = root / archived_rel
    if not archived_path.exists():
        report.add_error("product_source_archive_missing", f"archived product source is missing: {archived_rel}", archived_rel)
        return
    if not archived_path.is_file():
        report.add_error(
            "product_source_manifest_archive_path_not_file",
            f"invalid product source manifest: archive.path does not point to a file: {archived_rel}",
            "docs/product/core/source/source-manifest.json",
        )
        return

    expected_size = archive.get("size_bytes")
    if not _is_valid_manifest_size(expected_size):
        report.add_error(
            "product_source_manifest_archive_size_missing",
            "invalid product source manifest: archive.size_bytes is missing or invalid",
            "docs/product/core/source/source-manifest.json",
        )
    elif archived_path.stat().st_size != expected_size:
        report.add_error("product_source_size_mismatch", f"archived product source size mismatch: {archived_rel}", archived_rel)

    expected_hash = archive.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        report.add_error(
            "product_source_manifest_archive_hash_missing",
            "invalid product source manifest: archive.sha256 is missing",
            "docs/product/core/source/source-manifest.json",
        )
    elif _sha256(archived_path) != expected_hash:
        report.add_error("product_source_hash_mismatch", f"archived product source hash mismatch: {archived_rel}", archived_rel)

    source_size = source.get("size_bytes")
    if not _is_valid_manifest_size(source_size):
        report.add_error(
            "product_source_manifest_source_size_missing",
            "invalid product source manifest: source.size_bytes is missing or invalid",
            "docs/product/core/source/source-manifest.json",
        )
    elif _is_valid_manifest_size(expected_size) and source_size != expected_size:
        report.add_error(
            "product_source_manifest_source_size_mismatch",
            "invalid product source manifest: source.size_bytes does not match archive.size_bytes",
            "docs/product/core/source/source-manifest.json",
        )

    source_hash = source.get("sha256")
    if not isinstance(source_hash, str) or not source_hash:
        report.add_error(
            "product_source_manifest_source_hash_missing",
            "invalid product source manifest: source.sha256 is missing",
            "docs/product/core/source/source-manifest.json",
        )
    elif isinstance(expected_hash, str) and expected_hash and source_hash != expected_hash:
        report.add_error(
            "product_source_manifest_source_hash_mismatch",
            "invalid product source manifest: source.sha256 does not match archive.sha256",
            "docs/product/core/source/source-manifest.json",
        )

    can_derive_design = imported.get("can_derive_design")
    if status == "ready_for_structuring" and can_derive_design is not True:
        report.add_error(
            "product_source_import_inconsistent",
            "product import status ready_for_structuring requires can_derive_design: true",
            "docs/product/core/source/source-manifest.json",
        )
    if status == "conversion_required" and can_derive_design is True:
        report.add_error(
            "product_source_import_inconsistent",
            "product import status conversion_required requires can_derive_design: false",
            "docs/product/core/source/source-manifest.json",
        )
    if status == "conversion_required" or can_derive_design is not True:
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
        text = _read_markdown_text(root, chapter, report)
        if text is None:
            continue
        if not _markdown_text_references_path(root, chapter, text, prd_path):
            report.add_error(
                "product_chapter_missing_prd_link",
                f"{rel} must link back to {prd_rel}",
                rel,
            )

    meta = root / "docs/product/core/product-meta.md"
    if not meta.exists():
        return
    meta_text = _read_markdown_text(root, meta, report)
    if meta_text is None:
        return
    for chapter in chapters:
        rel = chapter.relative_to(root).as_posix()
        if not _markdown_text_references_path(root, meta, meta_text, chapter):
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
    seen_ids: dict[str, str] = {}
    for chapter in chapters:
        if "acceptance" not in chapter.stem.lower():
            continue
        rel = chapter.relative_to(root).as_posix()
        text = _read_markdown_text(root, chapter, report)
        if text is None:
            continue
        if SCAFFOLD_PLACEHOLDER in text:
            continue
        content = _strip_markdown_code(text)
        if ACCEPTANCE_ID_RE.search(content) is None:
            report.add_error(
                "product_acceptance_missing_ids",
                f"{rel} must define at least one A-NNN acceptance ID",
                rel,
            )
            continue
        for acceptance_id in ACCEPTANCE_ID_RE.findall(content):
            previous_rel = seen_ids.get(acceptance_id)
            if previous_rel is not None:
                report.add_error(
                    "product_acceptance_duplicate_id",
                    f"duplicate product acceptance ID {acceptance_id}: {rel} also defined in {previous_rel}",
                    rel,
                )
                continue
            seen_ids[acceptance_id] = rel


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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
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
            "an API endpoint contract under docs/api/endpoints/NN-<slug>.md",
            _is_api_endpoint_contract_reference,
            mismatch_code="acceptance_matrix_api_endpoint_reference_missing",
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
    if "uncovered criteria" in sections:
        _check_acceptance_matrix_product_coverage(root, report, seen_acceptance_ids, sections["uncovered criteria"])


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


def _check_acceptance_matrix_product_coverage(
    root: Path,
    report: VerificationReport,
    matrix_acceptance_ids: set[str],
    uncovered_criteria: str,
) -> None:
    product_acceptance_ids = _product_acceptance_ids(root, report)
    if not product_acceptance_ids:
        return
    uncovered_acceptance_ids = set(ACCEPTANCE_ID_RE.findall(_strip_markdown_code(uncovered_criteria)))
    unknown_uncovered_ids = sorted(uncovered_acceptance_ids - product_acceptance_ids)
    if unknown_uncovered_ids:
        report.add_error(
            "acceptance_matrix_uncovered_id_unknown",
            f"acceptance matrix Uncovered Criteria references unknown product acceptance IDs: {', '.join(unknown_uncovered_ids)}",
            ACCEPTANCE_MATRIX_REL.as_posix(),
        )
    covered_ids = matrix_acceptance_ids | uncovered_acceptance_ids
    missing_ids = sorted(product_acceptance_ids - covered_ids)
    if missing_ids:
        report.add_error(
            "acceptance_matrix_product_coverage_missing",
            f"acceptance matrix must map or list uncovered product acceptance IDs: {', '.join(missing_ids)}",
            ACCEPTANCE_MATRIX_REL.as_posix(),
        )


def _product_acceptance_ids(root: Path, report: VerificationReport | None = None) -> set[str]:
    product_root = root / "docs/product"
    if not product_root.exists():
        return set()
    acceptance_ids: set[str] = set()
    for path in sorted(product_root.glob("*.md")):
        if PRODUCT_CHAPTER_RE.fullmatch(path.name) is None or "acceptance" not in path.stem.lower():
            continue
        if report is None:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
        else:
            text = _read_markdown_text(root, path, report)
            if text is None:
                continue
        if SCAFFOLD_PLACEHOLDER in text:
            continue
        acceptance_ids.update(ACCEPTANCE_ID_RE.findall(_strip_markdown_code(text)))
    return acceptance_ids


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
    for reference in product_acceptance_refs:
        fragment_id = _reference_fragment_acceptance_id(reference)
        if fragment_id is not None and fragment_id != acceptance_id:
            report.add_error(
                "acceptance_matrix_acceptance_anchor_mismatch",
                f"acceptance matrix row {row_label} Acceptance link fragment {fragment_id} does not match Acceptance ID {acceptance_id}",
                ACCEPTANCE_MATRIX_REL.as_posix(),
            )
    has_acceptance_id = _product_acceptance_references_have_id(root, product_acceptance_refs, acceptance_id, report)
    if product_acceptance_refs and has_acceptance_id is False:
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
    *,
    mismatch_code: str | None = None,
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
            mismatch_code or "acceptance_matrix_trace_reference_missing",
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


def _check_adr_template(root: Path, report: VerificationReport) -> None:
    rel = ADR_TEMPLATE_REL.as_posix()
    path = root / ADR_TEMPLATE_REL
    if not path.exists():
        report.add_error("adr_template_missing", f"missing required ADR template: {rel}", rel)
        return
    if not path.is_file():
        report.add_error("adr_template_not_file", f"ADR template path is not a file: {rel}", rel)
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    sections = _markdown_sections(text, min_level=2)
    missing_sections = [
        label
        for key, label in ADR_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing_sections:
        report.add_error(
            "adr_template_missing_sections",
            f"{rel} is missing ADR template sections: {', '.join(missing_sections)}",
            rel,
        )
    normalized = _normalize_guardrail_text(text)
    for guardrail in ADR_TEMPLATE_GUARDRAILS:
        if guardrail.lower() in normalized:
            continue
        report.add_error(
            "adr_template_guardrail_missing",
            f"{rel} must preserve ADR template guardrail: {guardrail}",
            rel,
        )


def _check_architecture_decision(root: Path, path: Path, report: VerificationReport) -> None:
    rel = path.relative_to(root).as_posix()
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    rows = _markdown_table(text)
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
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    rows = _markdown_table(text)
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
    if not docs_root.is_dir():
        return
    for readme in sorted(docs_root.rglob("README.md")):
        directory = readme.parent
        if not readme.is_file():
            rel_readme = readme.relative_to(root).as_posix()
            report.add_error("docs_readme_not_file", f"{rel_readme} is not a file", rel_readme)
            continue
        readme_text = _read_markdown_text(root, readme, report)
        if readme_text is None:
            continue
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
        text = _read_markdown_text(root, path, report)
        if text is None:
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
    if not docs_root.is_dir():
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
    if not docs_root.is_dir():
        return
    for path in sorted(docs_root.rglob("*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/"):
            continue
        text = _read_markdown_text(root, path, report)
        if text is None:
            continue
        if SCAFFOLD_PLACEHOLDER not in text:
            continue
        report.add_error(
            "governance_scaffold_placeholder",
            f"{rel} still contains a governance scaffold placeholder",
            rel,
        )


def _check_runtime_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / RUNTIME_MANIFEST_REL
    manifest_rel = RUNTIME_MANIFEST_REL.as_posix()
    if not manifest_path.exists():
        report.add_error("runtime_manifest_missing", f"missing runtime manifest: {manifest_rel}", manifest_rel)
        return
    if not manifest_path.is_file():
        report.add_error("runtime_manifest_not_file", f"runtime manifest is not a file: {manifest_rel}", manifest_rel)
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        report.add_error("runtime_manifest_invalid_encoding", "invalid runtime manifest encoding: expected UTF-8", manifest_rel)
        return
    except json.JSONDecodeError as error:
        report.add_error("runtime_manifest_invalid_json", f"invalid runtime manifest: {error.msg}", manifest_rel)
        return
    if not isinstance(manifest, dict):
        report.add_error("runtime_manifest_invalid_schema", "invalid runtime manifest: manifest must be an object", manifest_rel)
        return
    _check_manifest_identity(
        manifest,
        manifest_rel,
        "runtime_manifest",
        "runtime manifest",
        RUNTIME_MANIFEST_SOURCE,
        report,
    )
    files = manifest.get("files")
    if not isinstance(files, list):
        report.add_error("runtime_manifest_invalid_schema", "invalid runtime manifest: files must be a list", manifest_rel)
        return
    listed_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            report.add_error("runtime_manifest_invalid_schema", "invalid runtime manifest: file entry must be an object", manifest_rel)
            continue
        rel = item.get("path")
        expected_hash = item.get("sha256")
        expected_size = item.get("size_bytes")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            report.add_error("runtime_manifest_invalid_path", f"invalid runtime file path: {rel}", manifest_rel)
            continue
        if rel in listed_paths:
            report.add_error("runtime_manifest_duplicate_path", f"duplicate runtime manifest path: {rel}", manifest_rel)
            continue
        listed_paths.add(rel)
        path = root / rel
        if not path.exists():
            report.add_error("runtime_file_missing", f"runtime file is missing: {rel}", rel)
            continue
        if not path.is_file():
            report.add_error("runtime_file_not_file", f"runtime file is not a file: {rel}", rel)
            continue
        if not _is_valid_manifest_size(expected_size):
            report.add_error("runtime_manifest_size_missing", f"runtime file size is missing or invalid: {rel}", manifest_rel)
        elif path.stat().st_size != expected_size:
            report.add_error("runtime_file_size_mismatch", f"runtime file size mismatch: {rel}", rel)
        if not isinstance(expected_hash, str) or not expected_hash:
            report.add_error("runtime_manifest_hash_missing", f"runtime file hash is missing: {rel}", manifest_rel)
            continue
        if _sha256(path) != expected_hash:
            report.add_error("runtime_file_hash_mismatch", f"runtime file hash mismatch: {rel}", rel)
    for required_path in RUNTIME_REQUIRED_PATHS:
        rel = required_path.as_posix()
        if rel not in listed_paths:
            report.add_error(
                "runtime_manifest_required_file_missing",
                f"runtime manifest is missing required file entry: {rel}",
                manifest_rel,
            )
    for executable_path in RUNTIME_EXECUTABLE_PATHS:
        path = root / executable_path
        rel = executable_path.as_posix()
        if path.is_file() and (path.stat().st_mode & stat.S_IXUSR) == 0:
            report.add_error("runtime_file_not_executable", f"runtime file is not executable: {rel}", rel)


def _check_workflow_pack_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / WORKFLOW_PACK_SNAPSHOT_ROOT / "manifest.json"
    manifest_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/manifest.json"
    if not manifest_path.exists():
        report.add_error("workflow_pack_manifest_missing", f"missing workflow pack manifest: {manifest_rel}", manifest_rel)
        return
    if not manifest_path.is_file():
        report.add_error("workflow_pack_manifest_not_file", f"workflow pack manifest is not a file: {manifest_rel}", manifest_rel)
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        report.add_error(
            "workflow_pack_manifest_invalid_encoding",
            "invalid workflow pack manifest encoding: expected UTF-8",
            manifest_rel,
        )
        return
    except json.JSONDecodeError as error:
        report.add_error("workflow_pack_manifest_invalid_json", f"invalid workflow pack manifest: {error.msg}", manifest_rel)
        return
    if not isinstance(manifest, dict):
        report.add_error(
            "workflow_pack_manifest_invalid_schema",
            "invalid workflow pack manifest: manifest must be an object",
            manifest_rel,
        )
        return
    _check_manifest_identity(
        manifest,
        manifest_rel,
        "workflow_pack_manifest",
        "workflow pack manifest",
        WORKFLOW_PACK_MANIFEST_SOURCE,
        report,
    )
    files = manifest.get("files")
    if not isinstance(files, list):
        report.add_error("workflow_pack_manifest_invalid_schema", "invalid workflow pack manifest: files must be a list", manifest_rel)
        return
    snapshot_root = root / WORKFLOW_PACK_SNAPSHOT_ROOT
    listed_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            report.add_error("workflow_pack_manifest_invalid_schema", "invalid workflow pack manifest: file entry must be an object", manifest_rel)
            continue
        rel = item.get("path")
        expected_hash = item.get("sha256")
        expected_size = item.get("size_bytes")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            report.add_error("workflow_pack_manifest_invalid_path", f"invalid workflow pack file path: {rel}", manifest_rel)
            continue
        if rel in listed_paths:
            report.add_error("workflow_pack_manifest_duplicate_path", f"duplicate workflow pack manifest path: {rel}", manifest_rel)
            continue
        listed_paths.add(rel)
        path = snapshot_root / rel
        file_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{rel}"
        if not path.exists():
            report.add_error("workflow_pack_file_missing", f"workflow pack file is missing: {file_rel}", file_rel)
            continue
        if not path.is_file():
            report.add_error("workflow_pack_file_not_file", f"workflow pack file is not a file: {file_rel}", file_rel)
            continue
        if not _is_valid_manifest_size(expected_size):
            report.add_error(
                "workflow_pack_manifest_size_missing",
                f"workflow pack file size is missing or invalid: {file_rel}",
                manifest_rel,
            )
        elif path.stat().st_size != expected_size:
            report.add_error("workflow_pack_file_size_mismatch", f"workflow pack file size mismatch: {file_rel}", file_rel)
        if not isinstance(expected_hash, str) or not expected_hash:
            report.add_error("workflow_pack_manifest_hash_missing", f"workflow pack file hash is missing: {file_rel}", manifest_rel)
            continue
        if _sha256(path) != expected_hash:
            report.add_error("workflow_pack_file_hash_mismatch", f"workflow pack file hash mismatch: {file_rel}", file_rel)
    for rel in WORKFLOW_PACK_REQUIRED_PATHS:
        if rel not in listed_paths:
            file_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{rel}"
            report.add_error(
                "workflow_pack_manifest_required_file_missing",
                f"workflow pack manifest is missing required file entry: {file_rel}",
                manifest_rel,
            )
    for path in _workflow_pack_snapshot_files(snapshot_root):
        rel = path.relative_to(snapshot_root).as_posix()
        if rel not in listed_paths:
            file_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{rel}"
            report.add_error(
                "workflow_pack_file_unmanifested",
                f"workflow pack file is not listed in manifest: {file_rel}",
                file_rel,
            )


def _check_manifest_identity(
    manifest: dict[str, object],
    manifest_rel: str,
    code_prefix: str,
    label: str,
    expected_source: str,
    report: VerificationReport,
) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        report.add_error(
            f"{code_prefix}_schema_version_invalid",
            f"{label} schema_version must be {MANIFEST_SCHEMA_VERSION}",
            manifest_rel,
        )
    if manifest.get("source") != expected_source:
        report.add_error(
            f"{code_prefix}_source_invalid",
            f"{label} source must be {expected_source}",
            manifest_rel,
        )


def _workflow_pack_snapshot_files(snapshot_root: Path) -> list[Path]:
    files: list[Path] = []
    if not snapshot_root.exists():
        return files
    for path in sorted(snapshot_root.rglob("*")):
        if path.is_file() and not _is_ignored_workflow_pack_file(path):
            files.append(path)
    return files


def _is_valid_manifest_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_valid_product_source_archive_path(value: str) -> bool:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    try:
        path.relative_to(PRODUCT_SOURCE_ARCHIVE_ROOT)
    except ValueError:
        return False
    return path not in {PRODUCT_SOURCE_ARCHIVE_ROOT, PRODUCT_SOURCE_MANIFEST_REL, PRODUCT_SOURCE_MANIFEST_TEMP_REL}


def _is_ignored_workflow_pack_file(path: Path) -> bool:
    parts = set(path.parts)
    return (
        "__pycache__" in parts
        or ".git" in parts
        or path.suffix == ".pyc"
        or path.name in WORKFLOW_PACK_IGNORED_FILE_NAMES
    )


def task_board_ready_tasks(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    path = root / TASK_BOARD_REL
    if not path.exists():
        return []
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    if SCAFFOLD_PLACEHOLDER in text:
        return []
    rows, _missing = _task_board_rows(text)
    matrix_ids = _acceptance_matrix_mapped_acceptance_ids(root)
    if matrix_ids is None:
        return []
    return [
        row
        for row in rows
        if _normalize_cell(row.get("status", "")) in TASK_BOARD_READY_STATUSES and _task_board_row_trace_complete(row)
        and _task_board_row_trace_references_valid(root, row)
        and _task_board_row_acceptance_mapped(row, matrix_ids)
    ]


def _check_task_board(root: Path, report: VerificationReport) -> None:
    path = root / TASK_BOARD_REL
    if not path.exists():
        return
    rel = TASK_BOARD_REL.as_posix()
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
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
        reference_errors = _task_board_row_trace_reference_errors(root, row, task_id, report)
        if reference_errors:
            for code, message in reference_errors:
                report.add_error(code, message, rel)
            continue
        blocked_errors = _task_board_blocked_unresolved_errors(root, row, task_id, report)
        if blocked_errors:
            for code, message in blocked_errors:
                report.add_error(code, message, rel)
            continue
        evidence_errors = _task_board_done_evidence_errors(root, row, task_id, report)
        if evidence_errors:
            for message in evidence_errors:
                report.add_error("task_board_done_evidence_missing", message, rel)
            continue
        if _normalize_cell(row.get("status", "")) in TASK_BOARD_READY_STATUSES:
            ready_count += 1
    if ready_count == 0:
        report.add_error("task_board_ready_task_missing", f"{rel} must contain at least one Ready task", rel)


def _check_verification_log(root: Path, report: VerificationReport) -> None:
    path = root / VERIFICATION_LOG_REL
    rel = VERIFICATION_LOG_REL.as_posix()
    if not path.exists():
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
        return
    if SCAFFOLD_PLACEHOLDER in text:
        return

    sections = _markdown_sections(text, min_level=2)
    missing_sections = [
        label
        for key, label in VERIFICATION_LOG_REQUIRED_SECTIONS.items()
        if key not in sections
    ]
    if missing_sections:
        report.add_error(
            "verification_log_missing_sections",
            f"{rel} is missing verification log sections: {', '.join(missing_sections)}",
            rel,
        )
    empty_sections = [
        label
        for key, label in VERIFICATION_LOG_REQUIRED_SECTIONS.items()
        if key in sections and not _section_has_authored_content(sections[key])
    ]
    if empty_sections:
        report.add_error(
            "verification_log_empty_sections",
            f"{rel} has empty verification log sections: {', '.join(empty_sections)}",
            rel,
        )
    if "verification runs" not in sections:
        return
    _check_verification_log_runs_table(sections["verification runs"], report)


def _check_verification_log_runs_table(text: str, report: VerificationReport) -> None:
    rel = VERIFICATION_LOG_REL.as_posix()
    rows, missing = _verification_log_rows(text)
    if missing:
        report.add_error(
            "verification_log_missing_columns",
            f"{rel} Verification Runs table is missing required columns: "
            f"{', '.join(VERIFICATION_LOG_REQUIRED_COLUMNS[column] for column in missing)}",
            rel,
        )
        return
    seen_tasks: set[str] = set()
    for row in rows:
        task_id = row.get("task", "").strip()
        if TASK_ID_RE.fullmatch(task_id) is None:
            report.add_error(
                "verification_log_invalid_task_id",
                f"verification log row {task_id or '(missing task)'} must use TASK-NNN task ID format",
                rel,
            )
            continue
        task_key = _normalize_cell(task_id)
        if task_key in seen_tasks:
            report.add_error("verification_log_duplicate_task_id", f"duplicate verification log Task ID: {task_id}", rel)
            continue
        seen_tasks.add(task_key)


def _verification_log_rows(text: str) -> tuple[list[dict[str, str]], list[str]]:
    table = _markdown_table(text)
    if not table:
        return [], list(VERIFICATION_LOG_REQUIRED_COLUMNS)
    for index, row in enumerate(table):
        header = [_normalize_cell(cell) for cell in row]
        if "task" not in header:
            continue
        missing = [column for column in VERIFICATION_LOG_REQUIRED_COLUMNS if column not in header]
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
                    for column in VERIFICATION_LOG_REQUIRED_COLUMNS
                }
            )
        return rows, []
    return [], list(VERIFICATION_LOG_REQUIRED_COLUMNS)


def _verification_log_task_ids(root: Path, report: VerificationReport | None = None) -> set[str] | None:
    path = root / VERIFICATION_LOG_REL
    if not path.exists():
        return None
    if report is None:
        if not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return None
    else:
        text = _read_markdown_text(root, path, report)
        if text is None:
            return None
    if SCAFFOLD_PLACEHOLDER in text:
        return None
    sections = _markdown_sections(text, min_level=2)
    runs = sections.get("verification runs")
    if runs is None:
        return None
    rows, missing = _verification_log_rows(runs)
    if missing:
        return None
    return {
        row["task"].strip()
        for row in rows
        if TASK_ID_RE.fullmatch(row.get("task", "").strip()) is not None
    }


def _check_roadmap(root: Path, report: VerificationReport) -> None:
    path = root / ROADMAP_REL
    rel = ROADMAP_REL.as_posix()
    if not path.exists():
        return
    text = _read_markdown_text(root, path, report)
    if text is None:
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
    roadmap_text = _read_markdown_text(root, roadmap_path, report)
    task_board_text = _read_markdown_text(root, task_board_path, report)
    if roadmap_text is None or task_board_text is None:
        return
    if SCAFFOLD_PLACEHOLDER in roadmap_text or SCAFFOLD_PLACEHOLDER in task_board_text:
        return

    roadmap_rows = _rows_with_columns(roadmap_text, ("id", "status"))
    if not roadmap_rows:
        return
    task_rows, task_missing = _task_board_rows(task_board_text)
    if task_missing:
        return

    roadmap_ids = {
        _normalize_cell(row.get("id", "").strip())
        for row in roadmap_rows
        if TASK_ID_RE.fullmatch(row.get("id", "").strip()) is not None
    }
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
    reported_missing_task_ids: set[str] = set()
    for row in task_rows:
        item_id = row.get("id", "").strip()
        normalized_id = _normalize_cell(item_id)
        if TASK_ID_RE.fullmatch(item_id) is None:
            continue
        if normalized_id in roadmap_ids or normalized_id in reported_missing_task_ids:
            continue
        reported_missing_task_ids.add(normalized_id)
        report.add_error(
            "task_board_roadmap_missing",
            f"task board row {item_id} has no matching roadmap milestone",
            TASK_BOARD_REL.as_posix(),
        )


def _check_task_board_acceptance_matrix_alignment(root: Path, report: VerificationReport) -> None:
    task_board_path = root / TASK_BOARD_REL
    matrix_ids = _acceptance_matrix_mapped_acceptance_ids(root)
    if matrix_ids is None or not task_board_path.exists():
        return
    task_board_text = _read_markdown_text(root, task_board_path, report)
    if task_board_text is None:
        return
    if SCAFFOLD_PLACEHOLDER in task_board_text:
        return
    task_rows, task_missing = _task_board_rows(task_board_text)
    if task_missing:
        return

    reported: set[tuple[str, str]] = set()
    for row in task_rows:
        task_id = row.get("id", "").strip()
        if TASK_ID_RE.fullmatch(task_id) is None:
            continue
        acceptance_id = _task_board_acceptance_id(row.get("acceptance", ""))
        if acceptance_id is None or acceptance_id in matrix_ids:
            continue
        report_key = (task_id, acceptance_id)
        if report_key in reported:
            continue
        reported.add(report_key)
        report.add_error(
            "task_board_acceptance_matrix_missing",
            f"task board row {task_id} Acceptance ID {acceptance_id} is not mapped in {ACCEPTANCE_MATRIX_REL.as_posix()}",
            TASK_BOARD_REL.as_posix(),
        )


def _acceptance_matrix_mapped_acceptance_ids(root: Path) -> set[str] | None:
    path = root / ACCEPTANCE_MATRIX_REL
    if not path.exists():
        return None
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    if SCAFFOLD_PLACEHOLDER in text:
        return None
    rows, missing = _acceptance_matrix_rows(text)
    if missing or not rows:
        return None
    mapped_ids: set[str] = set()
    for row in rows:
        acceptance_id = _acceptance_matrix_acceptance_id(row.get("acceptance", ""))
        if acceptance_id is None:
            return None
        if _acceptance_matrix_row_is_complete_mapping(root, path, row, acceptance_id):
            mapped_ids.add(acceptance_id)
    return mapped_ids


def _acceptance_matrix_row_is_complete_mapping(
    root: Path,
    matrix_path: Path,
    row: dict[str, str],
    acceptance_id: str,
) -> bool:
    for column in ACCEPTANCE_MATRIX_REQUIRED_COLUMNS:
        if _normalize_cell(row.get(column, "")) in SECTION_PLACEHOLDER_VALUES:
            return False
    if not _acceptance_matrix_acceptance_reference_complete(root, matrix_path, row.get("acceptance", ""), acceptance_id):
        return False
    return (
        _acceptance_matrix_field_reference_complete(root, matrix_path, row.get("design", ""), _is_design_reference)
        and _acceptance_matrix_field_reference_complete(
            root,
            matrix_path,
            row.get("api", ""),
            _is_api_endpoint_contract_reference,
        )
        and _acceptance_matrix_field_reference_complete(root, matrix_path, row.get("test", ""), _is_test_reference)
    )


def _acceptance_matrix_acceptance_reference_complete(
    root: Path,
    matrix_path: Path,
    value: str,
    acceptance_id: str,
) -> bool:
    references = _local_markdown_references(root, matrix_path, value, include_bare=True, strip_code=False)
    if not references or any(not reference.exists for reference in references):
        return False
    product_acceptance_refs = [reference for reference in references if _is_product_acceptance_reference_path(reference)]
    if not product_acceptance_refs:
        return False
    for reference in product_acceptance_refs:
        fragment_id = _reference_fragment_acceptance_id(reference)
        if fragment_id is not None and fragment_id != acceptance_id:
            return False
    return _product_acceptance_references_have_id(root, product_acceptance_refs, acceptance_id) is True


def _acceptance_matrix_field_reference_complete(
    root: Path,
    matrix_path: Path,
    value: str,
    predicate: Callable[[LocalMarkdownReference], bool],
) -> bool:
    references = _local_markdown_references(root, matrix_path, value, include_bare=True, strip_code=False)
    if not references or any(not reference.exists for reference in references):
        return False
    return any(predicate(reference) for reference in references)


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


def _task_board_row_acceptance_mapped(row: dict[str, str], matrix_ids: set[str]) -> bool:
    acceptance_id = _task_board_acceptance_id(row.get("acceptance", ""))
    return acceptance_id is not None and acceptance_id in matrix_ids


def _task_board_row_trace_reference_errors(
    root: Path,
    row: dict[str, str],
    task_id: str,
    report: VerificationReport | None = None,
) -> list[tuple[str, str]]:
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
        if any(not reference.exists for reference in references):
            continue
        expected_reference = _task_board_expected_reference(column)
        if expected_reference is not None:
            expected, predicate = expected_reference
            if not any(predicate(reference) for reference in references):
                errors.append((
                    "task_board_trace_reference_mismatch",
                    f"task board row {task_id} {label} field must reference {expected}",
                ))
        if (
            column == "acceptance"
            and not any(_is_product_acceptance_reference(reference) for reference in references)
        ):
            errors.append((
                "task_board_acceptance_reference_missing",
                f"task board row {task_id} Acceptance field must reference a product acceptance chapter",
            ))
        if column == "acceptance":
            product_acceptance_refs = [reference for reference in references if _is_product_acceptance_reference(reference)]
            acceptance_id = _task_board_acceptance_id(row.get(column, ""))
            if product_acceptance_refs and acceptance_id is None:
                errors.append((
                    "task_board_acceptance_id_missing",
                    f"task board row {task_id} Acceptance field must include A-NNN acceptance ID",
                ))
            elif (
                product_acceptance_refs
                and acceptance_id is not None
                and _product_acceptance_references_have_id(root, product_acceptance_refs, acceptance_id, report) is False
            ):
                errors.append((
                    "task_board_acceptance_id_unknown",
                    f"task board row {task_id} Acceptance ID {acceptance_id} is not defined in referenced product acceptance chapter",
                ))
            if product_acceptance_refs and acceptance_id is not None:
                for reference in product_acceptance_refs:
                    fragment_id = _reference_fragment_acceptance_id(reference)
                    if fragment_id is not None and fragment_id != acceptance_id:
                        errors.append((
                            "task_board_acceptance_anchor_mismatch",
                            f"task board row {task_id} Acceptance link fragment {fragment_id} does not match Acceptance ID {acceptance_id}",
                        ))
    return errors


def _task_board_expected_reference(column: str) -> tuple[str, Callable[[LocalMarkdownReference], bool]] | None:
    if column == "product":
        return "product scope docs", _is_product_scope_reference
    if column == "design":
        return "design docs", _is_design_reference
    if column == "api":
        return "API docs", _is_api_reference
    return None


def _task_board_acceptance_id(value: str) -> str | None:
    label = _plain_cell_label(value)
    match = ACCEPTANCE_ID_RE.search(label)
    if match is None:
        return None
    return match.group(0)


def _reference_fragment_acceptance_id(reference: LocalMarkdownReference) -> str | None:
    target = reference.raw.strip().strip("`").strip("<>").strip().rstrip(".,;").replace("\\", "/")
    if "#" not in target:
        return None
    fragment = target.split("#", 1)[1].split("?", 1)[0]
    match = re.search(r"A-[0-9]{3}", fragment, flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(0).upper()


def _product_acceptance_references_have_id(
    root: Path,
    references: list[LocalMarkdownReference],
    acceptance_id: str,
    report: VerificationReport | None = None,
) -> bool | None:
    saw_unreadable = False
    for reference in references:
        has_id = _product_acceptance_reference_has_id(root, reference, acceptance_id, report)
        if has_id is True:
            return True
        if has_id is None:
            saw_unreadable = True
    if saw_unreadable:
        return None
    return False


def _product_acceptance_reference_has_id(
    root: Path,
    reference: LocalMarkdownReference,
    acceptance_id: str,
    report: VerificationReport | None = None,
) -> bool | None:
    path = root / reference.rel
    if report is None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
    else:
        text = _read_markdown_text(root, path, report)
        if text is None:
            return None
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


def _is_api_endpoint_contract_reference(reference: LocalMarkdownReference) -> bool:
    path = Path(reference.rel)
    return (
        len(path.parts) == 4
        and path.parts[0] == "docs"
        and path.parts[1] == "api"
        and path.parts[2] == "endpoints"
        and API_ENDPOINT_CONTRACT_RE.fullmatch(path.parts[3]) is not None
    )


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


def _task_board_done_evidence_errors(
    root: Path,
    row: dict[str, str],
    task_id: str,
    report: VerificationReport | None = None,
) -> list[str]:
    if _normalize_cell(row.get("status", "")) not in TASK_BOARD_DONE_STATUSES:
        return []
    references = _task_board_local_references(root, row.get("verification", ""))
    if not references:
        return [f"task board row {task_id} is Done but Verification has no local Markdown evidence"]
    errors: list[str] = []
    for reference in references:
        path = root / reference.rel
        if reference.exists:
            if report is not None:
                _read_markdown_text(root, path, report)
            if reference.rel == VERIFICATION_LOG_REL.as_posix():
                task_ids = _verification_log_task_ids(root, report)
                if task_ids is not None and task_id not in task_ids:
                    errors.append(
                        f"task board row {task_id} references verification log without matching run: {reference.rel}"
                    )
            continue
        if report is not None and path.exists():
            _read_markdown_text(root, path, report)
            continue
        errors.append(f"task board row {task_id} references missing Verification evidence: {reference.rel}")
    return errors


def _task_board_blocked_unresolved_errors(
    root: Path,
    row: dict[str, str],
    task_id: str,
    report: VerificationReport | None = None,
) -> list[tuple[str, str]]:
    if _normalize_cell(row.get("status", "")) not in TASK_BOARD_BLOCKED_STATUSES:
        return []
    item_ids = _unresolved_item_ids(root, report)
    if item_ids is None:
        return []
    cited_id = _task_board_cited_unresolved_id(row, item_ids)
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


def _task_board_cited_unresolved_id(row: dict[str, str], item_ids: list[str]) -> str | None:
    haystack = " ".join(row.get(column, "") for column in ("task", "verification"))
    for item_id in item_ids:
        if _text_contains_identifier(haystack, item_id):
            return item_id
    return None


def _task_board_links_unresolved_registry(root: Path, row: dict[str, str]) -> bool:
    references = []
    references.extend(_task_board_local_references(root, row.get("task", "")))
    references.extend(_task_board_local_references(root, row.get("verification", "")))
    return any(reference.rel == "docs/unresolved.md" for reference in references)


def _unresolved_item_ids(root: Path, report: VerificationReport | None = None) -> list[str] | None:
    path = root / "docs/unresolved.md"
    if report is None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
    else:
        if not path.exists():
            return []
        text = _read_markdown_text(root, path, report)
        if text is None:
            return None
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


def _markdown_text_references_path(root: Path, source_path: Path, text: str, target_path: Path) -> bool:
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
    text = _strip_fenced_markdown_code(text)
    return re.sub(r"`[^`\n]*`", "", text)


def _strip_fenced_markdown_code(text: str) -> str:
    text = re.sub(r"(?s)```.*?```", "", text)
    return re.sub(r"(?s)~~~.*?~~~", "", text)


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


def _makefile_target_recipes(text: str) -> dict[str, list[str]]:
    target_recipes: dict[str, list[str]] = {}
    current_targets: list[str] = []
    for line in text.splitlines():
        if line and line[0].isspace():
            recipe = line.strip()
            if recipe.startswith("@"):
                recipe = recipe[1:].lstrip()
            if current_targets and recipe and not recipe.startswith("#"):
                for target in current_targets:
                    target_recipes[target].append(recipe)
            continue
        current_targets = []
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        name_text = line.split(":", 1)[0].strip()
        if not name_text or name_text.startswith(".") or "=" in name_text:
            continue
        parsed_targets: list[str] = []
        for target in name_text.split():
            if re.fullmatch(r"[A-Za-z0-9_.-]+", target):
                target_recipes.setdefault(target, [])
                parsed_targets.append(target)
        current_targets = parsed_targets
    return target_recipes


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


def verification_continuation_payload(target: Path) -> dict[str, object]:
    try:
        state = load_state(target)
    except (OSError, StateFileError):
        return {}
    if not state:
        return {}
    cwd = str(target.resolve())
    return {
        "state": state,
        "local_commands": target_local_commands_payload(cwd=cwd),
        "next_actions": next_actions_payload(state, cwd=cwd),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify docs-as-code governance consistency.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to verify.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable verification report.")
    args = parser.parse_args()
    target = Path(args.target)
    report = verify(target)
    if args.json:
        payload = report.to_dict()
        payload["target"] = str(target)
        payload.update(verification_continuation_payload(target))
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report.ok else 1
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
