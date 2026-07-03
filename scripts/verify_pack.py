from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from .bootstrap_tree import TARGET_LOCAL_COMMANDS
    from .verify_governance import (
        RUNTIME_EXECUTABLE_PATHS,
        RUNTIME_REQUIRED_PATHS,
        WORKFLOW_PACK_REQUIRED_PATHS,
    )
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import TARGET_LOCAL_COMMANDS
    from verify_governance import RUNTIME_EXECUTABLE_PATHS, RUNTIME_REQUIRED_PATHS, WORKFLOW_PACK_REQUIRED_PATHS


WORKFLOW_PACK_RESOURCE_PATHS = (
    "README.md",
    "workflows",
    "skills",
    "references",
    "templates",
)
PACK_LINK_CHECK_RESOURCE_PATHS = (
    "README.md",
    "AGENTS.md",
    "workflows",
    "skills",
    "references",
)
REFERENCE_ENTRY_RESOURCE_PATHS = (
    "README.md",
    "AGENTS.md",
    "workflows",
    "skills",
)
TEMPLATE_ENTRY_RESOURCE_PATHS = (
    "README.md",
    "AGENTS.md",
    "workflows",
    "skills",
    "references",
)
TEMPLATE_REQUIRED_GUARDRAILS = {
    "templates/root/README.md": (
        "# Project Name",
        "One-sentence project summary.",
        "- Product source: `docs/product/core/PRD.md`",
        "- Documentation index: `docs/README.md`",
        "- Governance rules: `AGENTS.md`",
        "- Open questions: `docs/unresolved.md`",
        "make verify-governance",
    ),
    "templates/docs/product/core/PRD.md": (
        "# Product Requirements Document",
        "Replace this file with the archived and converted product source.",
        "- Original file:",
        "- Import date:",
        "- Conversion method:",
        "- Review status:",
    ),
    "templates/docs/agent-workflow/task-handoff.md": (
        "# Agent Task Handoff",
        "- Product:",
        "- API:",
        "- Architecture:",
        "- Acceptance:",
        "- Code and tests are complete.",
        "- Documentation is synchronized.",
        "- Verification commands pass and output is recorded.",
    ),
    "templates/docs/api/00-conventions.md": (
        "# API Conventions",
        "- Product scope source",
        "- Acceptance criteria source",
        "- JSON request and response bodies for product workflow APIs.",
        "- Stable endpoint paths and explicit compatibility notes for breaking changes.",
        "- Authentication boundary, authorization expectations, and public/private endpoint policy.",
        "- Idempotency key policy for retryable writes and duplicate submission handling.",
        "- Backward compatibility expectations, versioning policy, and downstream consumer impact.",
        "- Link unresolved API contract decisions or ADR candidates.",
    ),
    "templates/docs/api/changelog.md": (
        "# API Changelog",
        "| Date | Change | Source | Compatibility Impact |",
        "Initial API contract baseline.",
        "Record downstream frontend, backend, test, and client impact.",
        "- Record backward-compatible additions, breaking changes, migrations, deprecations, and consumer coordination requirements.",
        "- Link each contract-changing entry to local product, API, architecture, implementation, or ADR sources.",
    ),
    "templates/docs/api/endpoints/01-endpoint-contract.md": (
        "# Endpoint Contract",
        "POST /example",
        "- Authentication and authorization requirement derived from API conventions and product scope.",
        "- Idempotency key, retry, and duplicate-submission behavior for this endpoint.",
        "| Field | Type | Required | Source | Notes |",
        "| Field | Type | Source | Notes |",
        "- Reference `docs/api/error-codes.md` and list only registered endpoint errors.",
        "- Link local product, architecture, backend, decision, or unresolved Markdown sources.",
        "- Link local UI or frontend API-consumption Markdown sources.",
    ),
    "templates/docs/api/endpoints/README.md": (
        "# API Endpoints",
        "| Endpoint | Method and Path | Product Source | Frontend Consumer |",
        "[01-endpoint-contract.md](01-endpoint-contract.md)",
        "- Endpoint files must use `NN-<slug>.md` with unique `NN` prefixes.",
        "- Keep `01-endpoint-contract.md` only as the starter endpoint contract until replaced or renamed from product-derived API design.",
        "- Every listed endpoint must link to a local endpoint contract file.",
        "- Endpoint contracts must reference `docs/api/error-codes.md`.",
        "- Endpoint contracts must link upstream product, architecture, backend, decision, or unresolved Markdown sources.",
        "- Endpoint contracts must link local UI or frontend API-consumption Markdown consumers.",
    ),
    "templates/docs/api/error-codes.md": (
        "# API Error Codes",
        "- Product scope source",
        "- Acceptance criteria source",
        "- Validation, authentication, authorization, not-found, conflict, rate-limit, dependency, and internal errors.",
        "| Code | HTTP Status | Product Meaning | Retryable | User Action |",
        "ERR_EXAMPLE",
        "Replace with a product-derived error condition.",
        "- Mark every retryable error explicitly and define backoff, idempotency, and duplicate-submission expectations.",
        "- Map each user-visible error to copy, UI state, recovery action, and telemetry expectations.",
    ),
    "templates/docs/architecture/01-system-context.md": (
        "# System Context",
        "- Product scope source",
        "- Acceptance criteria source",
        "- Primary user or external actor",
        "- External system, service, or explicit `none`",
        "- Boundary between actors, clients, services, data stores, or external systems",
        "- Link ADR candidates or unresolved architecture questions.",
    ),
    "templates/docs/architecture/02-containers.md": (
        "# Containers",
        "- System context source",
        "- Acceptance criteria source",
        "- Runtime container name: responsibility and owner",
        "Describe runtime behavior, request flow, background work, and operational ownership.",
        "Map each container to owned data, shared data, and integration boundaries.",
        "- Link ADR candidates or unresolved container-boundary questions.",
    ),
    "templates/docs/architecture/03-quality-attributes.md": (
        "# Quality Attributes",
        "- Containers source",
        "- Acceptance criteria source",
        "- Availability target, failure budget, and recovery expectation",
        "- Latency, throughput, concurrency, or resource constraints tied to product expectations",
        "- Authentication, authorization, data protection, and abuse-case expectations",
        "- Logs, metrics, traces, audit events, and alerting expectations",
        "- Explicit quality tradeoffs, deferred constraints, and ADR candidates",
    ),
    "templates/docs/backend/01-modules.md": (
        "# Backend Modules",
        "- Product scope source",
        "- Acceptance criteria source",
        "- System context source",
        "- Container source",
        "- Quality attributes source",
        "- Data model source: `docs/backend/02-data-model.md`",
        "- External services source: `docs/backend/03-external-services.md`",
        "| Module | Responsibility | Upstream | Downstream | Owner |",
        "One primary backend responsibility derived from product and architecture sources.",
        "- Link owned API endpoints under `docs/api/endpoints/`.",
        "- Separate internal-only behavior from API-visible behavior.",
        "- Document success path, failure path, retry, timeout, compensation, observability, and security behavior.",
        "- Link unresolved module-boundary, API ownership, data ownership, or external dependency questions.",
    ),
    "templates/docs/backend/02-data-model.md": (
        "# Data Model",
        "- Product scope source",
        "- Acceptance criteria source",
        "- Backend modules source: `docs/backend/01-modules.md`",
        "- API endpoint source",
        "| Entity | Owning Module | API Owner | Data Steward |",
        "| Entity | Field | Type | Required | Source | Notes |",
        "Stable identifier and ownership boundary.",
        "| Entity | State | Allowed Transition | Trigger | Source |",
        "- Document uniqueness, idempotency keys, cross-user isolation, retention, soft-delete, and audit constraints.",
        "| Entity | Index | Query Path | Justification |",
        "- Document creation order, backfill strategy, compatibility window, rollback expectation, and data safety checks.",
    ),
    "templates/docs/backend/03-external-services.md": (
        "# External Services",
        "- Product scope source",
        "- Acceptance criteria source",
        "- Backend modules source: `docs/backend/01-modules.md`",
        "- API endpoint source",
        "| Service | Owner | Purpose | Criticality | Data Shared |",
        "Product-derived dependency purpose",
        "- Link service API, event, file, queue, or manual contract source.",
        "- Document request fields, response fields, error behavior, and compatibility expectations.",
        "- Document retryable failures, backoff policy, idempotency behavior, compensation, and duplicate-submission handling.",
        "- Document timeout budget, fallback behavior, user-visible impact, and upstream/downstream cancellation policy.",
        "- Document credential owner, auth mechanism, secret storage, rotation, and access boundary.",
        "- Document logs, metrics, traces, audit events, alerting, and sensitive-field handling.",
    ),
    "templates/docs/decisions/ADR-template.md": (
        "# ADR-NNN: Title",
        "- Status: proposed",
        "- Date: YYYY-MM-DD",
        "- Related modules: TBD",
    ),
    "templates/docs/development/01-roadmap.md": (
        "# Roadmap",
        "| ID | Status | Milestone |",
        "TASK-NNN",
        "Product-derived milestone",
        "List milestone ordering and dependency rationale.",
        "List delivery risks and mitigation owners.",
        "List explicitly deferred product or implementation scope.",
    ),
    "templates/docs/development/02-task-board.md": (
        "# Task Board",
        "| ID | Status | Task | Product | Design | API | Acceptance | Verification |",
        "TASK-NNN",
        "Allowed statuses: Backlog, Ready, In Progress, Blocked, Done, Deferred.",
        "Product, Design, API, and Acceptance cells must reference existing local Markdown sources.",
        "Ready tasks must have Product, Design, API, Acceptance, and Verification fields filled.",
        "Done tasks must link Verification to local Markdown evidence.",
    ),
    "templates/docs/development/03-verification-log.md": (
        "# Verification Log",
        "| Task | Command | Result | Date | Notes |",
        "- Link local evidence artifacts or summarize relevant command output here.",
        "- none",
    ),
    "templates/docs/frontend/01-modules.md": (
        "# Frontend Modules",
        "- Product scope source",
        "- Acceptance criteria source",
        "- Interaction model source: `docs/ui/01-interaction-model.md`",
        "- API consumption source: `docs/frontend/02-api-consumption.md`",
        "| Module | Responsibility | UI Surface | API Dependency | Owner |",
        "One primary frontend responsibility derived from UI and product flows.",
        "- Document local, shared, server-derived, cached, optimistic, and persisted state ownership.",
        "- Link each server-derived state to the API endpoint contract that owns it.",
        "| Route | Screen or Flow | Access Rule | Product Source |",
        "- Link unresolved frontend module, state, route, API, or accessibility questions.",
    ),
    "templates/docs/frontend/02-api-consumption.md": (
        "# API Consumption",
        "- Product scope source",
        "- Acceptance criteria source",
        "- Frontend modules source: `docs/frontend/01-modules.md`",
        "- API conventions source: `docs/api/00-conventions.md`",
        "- API error registry source: `docs/api/error-codes.md`",
        "- Endpoint index source: `docs/api/endpoints/README.md`",
        "| Flow or Screen | Frontend Module | Endpoint Contract | Request Trigger | Response Owner |",
        "State owner from frontend modules",
        "- Map pending, optimistic, empty, stale, retrying, and disabled states to flows and endpoint calls.",
        "- Map API error codes to user-visible copy, recovery action, retry behavior, telemetry, and acceptance criteria.",
    ),
    "templates/docs/tests/01-strategy.md": (
        "# Test Strategy",
        "- Unit tests cover isolated validation rules and state transitions.",
        "- Integration tests cover API contract and persistence behavior.",
        "- End-to-end checks cover critical product acceptance flows.",
        "Map high-risk product, architecture, backend, and frontend areas to verification coverage.",
        "Record performance, security, accessibility, observability, and recovery checks before implementation handoff.",
    ),
    "templates/docs/tests/02-acceptance-matrix.md": (
        "# Acceptance Matrix",
        "| Acceptance | Design | API | Test |",
        "A-NNN acceptance source",
        "endpoint contract source",
        "- A-NNN deferred or uncovered reason",
    ),
    "templates/docs/ui/01-interaction-model.md": (
        "# Interaction Model",
        "- Product scope source",
        "- Acceptance criteria source",
        "- API endpoint source",
        "| Flow | Actor | Trigger | Success Path | Source |",
        "| Screen | Purpose | Entry Flow | Exit or Next Step | Source |",
        "- Loading, empty, success, disabled, permission, and error states for each primary flow.",
        "- Map user-visible errors to API error codes, recovery actions, and acceptance criteria.",
        "- Keyboard navigation, focus order, labels, contrast, and screen reader expectations tied to product flows.",
    ),
}
TEMPLATE_REQUIRED_SECTIONS = {
    "templates/root/README.md": (
        "Start Here",
        "Development",
    ),
    "templates/docs/product/core/PRD.md": (
        "Source",
    ),
    "templates/docs/agent-workflow/task-handoff.md": (
        "Task Goal",
        "Related Specs",
        "Definition of Done",
    ),
    "templates/docs/api/00-conventions.md": (
        "Product Links",
        "HTTP Conventions",
        "Authentication",
        "Idempotency",
        "Compatibility",
        "Open Decisions",
    ),
    "templates/docs/api/changelog.md": (
        "Change Log",
        "Compatibility Notes",
    ),
    "templates/docs/api/endpoints/01-endpoint-contract.md": (
        "Method and Path",
        "Auth",
        "Idempotency",
        "Request Fields",
        "Response Fields",
        "Error Codes",
        "Upstream Links",
        "Frontend Consumers",
    ),
    "templates/docs/api/endpoints/README.md": (
        "Index",
        "Naming Rules",
        "Traceability Rules",
    ),
    "templates/docs/api/error-codes.md": (
        "Product Links",
        "Error Taxonomy",
        "Error Codes",
        "Retry Semantics",
        "Frontend Handling",
    ),
    "templates/docs/architecture/01-system-context.md": (
        "Product Links",
        "Actors",
        "External Systems",
        "Trust Boundaries",
        "Open Decisions",
    ),
    "templates/docs/architecture/02-containers.md": (
        "Product Links",
        "Containers",
        "Runtime Responsibilities",
        "Data Ownership",
        "Open Decisions",
    ),
    "templates/docs/architecture/03-quality-attributes.md": (
        "Product Links",
        "Availability",
        "Performance",
        "Security",
        "Observability",
        "Tradeoffs",
    ),
    "templates/docs/backend/01-modules.md": (
        "Product Links",
        "Architecture Links",
        "Modules",
        "API Ownership",
        "Failure Modes",
        "Open Decisions",
    ),
    "templates/docs/backend/02-data-model.md": (
        "Product Links",
        "Owners",
        "Entities",
        "State Machines",
        "Constraints",
        "Indexes",
        "Migrations",
    ),
    "templates/docs/backend/03-external-services.md": (
        "Product Links",
        "Dependencies",
        "Contracts",
        "Retries",
        "Timeouts",
        "Authentication",
        "Observability",
    ),
    "templates/docs/decisions/ADR-template.md": (
        "Context",
        "Decision",
        "Consequences",
        "References",
    ),
    "templates/docs/development/01-roadmap.md": (
        "Product Links",
        "Milestones",
        "Sequencing",
        "Risks",
        "Deferred Scope",
    ),
    "templates/docs/development/02-task-board.md": (
        "Task Table",
        "Status Policy",
        "Traceability Rules",
    ),
    "templates/docs/development/03-verification-log.md": (
        "Verification Runs",
        "Artifacts",
        "Open Follow-ups",
    ),
    "templates/docs/frontend/01-modules.md": (
        "Product Links",
        "UI Links",
        "Modules",
        "State Ownership",
        "Routes",
        "Open Decisions",
    ),
    "templates/docs/frontend/02-api-consumption.md": (
        "Product Links",
        "API Links",
        "Consumption Map",
        "Loading States",
        "Error Actions",
    ),
    "templates/docs/tests/01-strategy.md": (
        "Product Links",
        "Acceptance Links",
        "Test Layers",
        "Risk Coverage",
        "Non-Functional Checks",
    ),
    "templates/docs/tests/02-acceptance-matrix.md": (
        "Matrix",
        "Uncovered Criteria",
    ),
    "templates/docs/ui/01-interaction-model.md": (
        "Product Links",
        "Primary Flows",
        "Screens",
        "States",
        "Errors",
        "Accessibility",
    ),
}
README_PACKAGE_LAYOUT_DIRECTORIES = (
    "bin",
    "scripts",
    "skills",
    "references",
    "templates",
    "tests",
    "workflows",
)
README_QUICK_START_REQUIRED_COMMANDS = (
    "bin/governance env --repair --check --target",
    "bin/governance init --check --target",
    "bin/governance init --target",
    "bin/governance verify",
    "bin/governance gate product-structuring",
    "bin/governance status",
)
README_AGENT_AUTOMATION_REQUIRED_COMMANDS = (
    "bin/governance verify /path/to/new-project --check --json",
    "bin/governance verify /path/to/new-project --json",
    "bin/governance env --repair --check --target /path/to/new-project --json",
    "bin/governance env --repair --target /path/to/new-project --json",
)
TARGET_MAKEFILE_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/01-empty-repo-initialization.md",
    "workflows/05-verification-and-drift-control.md",
    "references/runtime-strategy.md",
    "skills/initializing-governance-repo/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
    "templates/root/README.md",
)
TARGET_MAKEFILE_REQUIRED_COMMANDS = tuple(
    f"make {target}" for target, _recipe, _description, _writes_state in TARGET_LOCAL_COMMANDS
)
ENV_REPAIR_DOC_PATHS = (
    "README.md",
    "references/runtime-strategy.md",
    "workflows/01-empty-repo-initialization.md",
    "workflows/05-verification-and-drift-control.md",
    "skills/initializing-governance-repo/SKILL.md",
    "skills/using-governance-workflow/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
ENV_REPAIR_REQUIRED_FIELDS = (
    "would_repair",
    "install_commands",
    "manual_repairs",
    "needs_escalation",
)
PRODUCT_ARCHIVE_DOC_PATHS = (
    "workflows/02-product-document-archiving.md",
    "skills/archiving-product-document/SKILL.md",
)
PRODUCT_ARCHIVE_REQUIRED_PHRASES = (
    "source-manifest.json",
    "SHA-256",
    "can_derive_design",
    "product mark-ready",
    "manual-reviewed-markdown",
    "would_update",
    "local_commands",
    "next_actions",
)
PRODUCT_STRUCTURE_DOC_PATHS = (
    "workflows/03-product-structuring.md",
    "skills/structuring-product-requirements/SKILL.md",
)
PRODUCT_STRUCTURE_REQUIRED_PHRASES = (
    "scaffold product",
    "would_create",
    "would_skip",
    "would_index",
    "governance:scaffold-placeholder",
    "background-and-problems",
    "change-log",
    "goals-and-requirements",
    "functional-spec",
    "acceptance-criteria",
    "success-metrics",
    "NN-<slug>.md",
    "A-NNN",
    "product-meta.md",
    "local_commands",
    "next_actions",
)
DESIGN_SCAFFOLD_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/using-governance-workflow/SKILL.md",
)
DESIGN_SCAFFOLD_REQUIRED_PHRASES = (
    "scaffold design",
    "would_create",
    "would_skip",
    "would_index",
    "governance:scaffold-placeholder",
    "docs/api/endpoints/01-endpoint-contract.md",
    "acceptance matrix",
    "roadmap",
    "task board",
    "verification log",
    "local_commands",
    "next_actions",
)
IMPLEMENTATION_HANDOFF_DOC_REQUIREMENTS = {
    "README.md": (
        "implementation",
        "Ready",
        "docs/development/03-verification-log.md",
        "task board",
    ),
    "workflows/04-design-derivation.md": (
        "docs/tests/02-acceptance-matrix.md",
        "docs/development/01-roadmap.md",
        "docs/development/02-task-board.md",
        "docs/development/03-verification-log.md",
        "TASK-NNN",
        "A-NNN",
        "Product",
        "Design",
        "API",
        "Acceptance",
        "local Markdown",
        "implementation handoff",
    ),
    "workflows/05-verification-and-drift-control.md": (
        "advance implementation",
        "gate implementation",
        "implementation gate",
        "docs/development/01-roadmap.md",
        "docs/development/02-task-board.md",
        "docs/development/03-verification-log.md",
        "Task",
        "Product",
        "Design",
        "API",
        "Acceptance",
        "Verification",
        "Ready",
        "Blocked",
        "Done",
        "TASK-NNN",
        "A-NNN",
        "docs/unresolved.md",
        "docs/tests/02-acceptance-matrix.md",
    ),
    "skills/planning-implementation-work/SKILL.md": (
        "advance implementation",
        "docs/development/01-roadmap.md",
        "docs/development/02-task-board.md",
        "docs/development/03-verification-log.md",
        "TASK-NNN",
        "Product",
        "Design",
        "API",
        "Acceptance",
        "Verification",
        "Ready",
        "Done",
        "A-NNN",
        "docs/tests/02-acceptance-matrix.md",
        "mapped in `docs/tests/02-acceptance-matrix.md`",
        "docs/unresolved.md",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "gate implementation",
        "advance implementation",
        "roadmap",
        "task board",
        "verification evidence",
        "TASK-NNN",
        "A-NNN",
        "Ready",
        "Blocked",
        "Done",
        "docs/unresolved.md",
        "docs/tests/02-acceptance-matrix.md",
        "local Markdown",
    ),
}
DESIGN_REFERENCE_DOC_REQUIREMENTS = (
    (
        "references/architecture-methods.md",
        (
            "workflows/04-design-derivation.md",
            "skills/capturing-architecture-decisions/SKILL.md",
            "skills/designing-api-contracts/SKILL.md",
            "skills/designing-system-architecture/SKILL.md",
        ),
    ),
    (
        "references/backend-design-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-backend-modules/SKILL.md",
            "skills/designing-data-models/SKILL.md",
        ),
    ),
)
METHOD_REFERENCE_BASELINES = {
    "references/architecture-methods.md": (
        ("C4 Model", ("## C4 Model", "https://c4model.com/")),
        ("arc42", ("## arc42", "https://docs.arc42.org/home/")),
        (
            "ADR",
            (
                "## ADR",
                "https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions",
            ),
        ),
        ("OpenAPI", ("## OpenAPI", "https://spec.openapis.org/oas/latest.html")),
    ),
    "references/backend-design-checklist.md": (
        ("Module Boundary", ("## Module Boundary", "one primary responsibility")),
        ("Data Model", ("## Data Model", "idempotency keys and uniqueness constraints")),
        ("API Contract", ("## API Contract", "request fields, response fields, auth")),
        ("Runtime Flow", ("## Runtime Flow", "retries, timeouts, and compensation behavior")),
        ("Observability and Security", ("## Observability and Security", "auth boundaries")),
        ("Acceptance and Tests", ("## Acceptance and Tests", "unit, integration, and contract tests")),
    ),
}
PHASE_ADVANCE_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/05-verification-and-drift-control.md",
    "skills/using-governance-workflow/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
PHASE_ADVANCE_REQUIRED_PHRASES = (
    "one phase at a time",
    "cannot skip phases",
)
PHASE_ADVANCE_AMBIGUOUS_PHRASES = (
    "forward-only",
    "only moves forward",
    "only moves the recorded workflow phase forward",
    "advance` is monotonic",
)
MAKEFILE_REQUIRED_TARGETS = (
    "test",
    "verify-pack",
)
MAKEFILE_REQUIRED_TARGET_RECIPES = {
    "test": (
        "python3 -m unittest discover -s tests",
    ),
    "verify-pack": (
        "python3 scripts/verify_pack.py",
        "python3 scripts/check_env.py",
    ),
}
RUNTIME_WRAPPER_REQUIRED_COMMANDS = {
    "bin/governance": 'python3 "$ROOT_DIR/scripts/governance_cli.py" "$@"',
    "bin/governance-init": 'python3 "$ROOT_DIR/scripts/governance_cli.py" init "$@"',
    "bin/governance-verify": 'python3 "$ROOT_DIR/scripts/governance_cli.py" verify "$@"',
}
GOVERNANCE_CLI_PATH = Path("scripts/governance_cli.py")
GOVERNANCE_CLI_REQUIRED_COMMANDS = (
    "init",
    "verify",
    "status",
    "env",
    "runtime",
    "gate",
    "scaffold",
    "advance",
    "product",
)
GOVERNANCE_CLI_REQUIRED_SUBCOMMANDS = {
    "runtime": ("refresh",),
    "product": ("mark-ready",),
}
GOVERNANCE_CLI_PARSER_VARIABLES = {
    "top-level": "sub",
    "runtime": "runtime_sub",
    "product": "product_sub",
}
RUNTIME_WRAPPER_REQUIRED_GUARDS = (
    "#!/usr/bin/env bash",
    "set -euo pipefail",
)
RUNTIME_WRAPPER_ROOT_DIR_LINE = 'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"'
CONTINUATION_RUNTIME_SCRIPT_PATHS = (
    "scripts/bootstrap_tree.py",
    "scripts/check_env.py",
    "scripts/gates.py",
    "scripts/governance_cli.py",
    "scripts/phases.py",
    "scripts/product_import.py",
    "scripts/scaffold.py",
    "scripts/verify_governance.py",
)
CONTINUATION_RUNTIME_REQUIRED_CALLS = (
    "target_local_commands_payload",
    "next_actions_payload",
)
RUNTIME_FILE_LIST_MODULES = {
    "scripts/bootstrap_tree.py": {
        "bin": "RUNTIME_BIN_FILES",
        "scripts": "RUNTIME_SCRIPT_FILES",
    },
    "scripts/verify_governance.py": {
        "bin": "RUNTIME_REQUIRED_BIN_FILES",
        "scripts": "RUNTIME_REQUIRED_SCRIPT_FILES",
    },
}
VERIFICATION_COMMAND_DOC_PATHS = (
    "README.md",
    "AGENTS.md",
)
PACK_REQUIRED_VERIFICATION_COMMANDS = (
    "make test",
    "make verify-pack",
)
AGENTS_PURPOSE_REQUIRED_PHRASES = (
    "reusable package for creating governed docs-as-code project workspaces",
    "do not treat it as a generated target project",
)
AGENTS_BASELINE_REQUIRED_PHRASES = (
    "commit after each coherent change",
    "future workflow behavior is traceable",
)
AGENTS_EDITING_REQUIRED_PHRASES = (
    "skills/ concise and trigger-focused",
    "deterministic behavior in scripts/",
    "generated repository examples in templates/",
    "phase procedures in workflows/",
    "tests before changing script behavior",
)
AGENTS_REQUIRED_READING_PHRASES = (
    "workflows/00-overview.md",
    "target phase file under workflows/",
    "affected skill under skills/",
    "relevant script tests under tests/",
)
AGENTS_VERIFICATION_REQUIRED_PHRASES = (
    "before claiming completion",
    "verification commands and results",
)
SOURCE_PACK_REQUIRED_PATHS = tuple(
    dict.fromkeys(
        (
            "README.md",
            "AGENTS.md",
            "Makefile",
            "scripts/verify_pack.py",
            *(path.as_posix() for path in RUNTIME_REQUIRED_PATHS),
            *WORKFLOW_PACK_REQUIRED_PATHS,
        )
    )
)
IGNORED_PACK_FILE_NAMES = {".DS_Store", "manifest.json"}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(r"^\s{0,3}\[[^\]]+]:\s*(\S+)", re.MULTILINE)
README_INDEX_ENTRY_RE = re.compile(r"^\s*-\s+`([^`\n]+)`(?P<trailing>[^\n]*)$")
SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
PHASE_WORKFLOW_PATHS = (
    "workflows/01-empty-repo-initialization.md",
    "workflows/02-product-document-archiving.md",
    "workflows/03-product-structuring.md",
    "workflows/04-design-derivation.md",
    "workflows/05-verification-and-drift-control.md",
)
PHASE_WORKFLOW_TITLES = {
    "workflows/01-empty-repo-initialization.md": "Empty Repository Initialization",
    "workflows/02-product-document-archiving.md": "Product Document Archiving",
    "workflows/03-product-structuring.md": "Product Structuring",
    "workflows/04-design-derivation.md": "Design Derivation",
    "workflows/05-verification-and-drift-control.md": "Verification and Drift Control",
}
PHASE_WORKFLOW_REQUIRED_SECTIONS = (
    "Input",
    "Skills",
    "Procedure",
    "Output",
    "Verification",
    "Stop Conditions",
)
PACK_FINDING_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PACK_FINDING_SEVERITIES = {"error", "warning"}


@dataclass(frozen=True)
class PackFinding:
    code: str
    message: str
    path: str
    severity: str = "error"

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not PACK_FINDING_CODE_RE.fullmatch(self.code):
            raise ValueError("pack finding code must use lowercase snake_case")
        if not isinstance(self.message, str) or not self.message:
            raise ValueError("pack finding message must be a non-empty string")
        if not isinstance(self.path, str) or not self.path:
            raise ValueError("pack finding path must be a non-empty string")
        if self.severity not in PACK_FINDING_SEVERITIES:
            raise ValueError("pack finding severity must be error or warning")

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class PackReport:
    target: str
    findings: list[PackFinding]

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("pack report target must be a non-empty string")
        if not isinstance(self.findings, list):
            raise ValueError("pack report findings must be a list")
        if not all(isinstance(finding, PackFinding) for finding in self.findings):
            raise ValueError("pack report findings must contain PackFinding entries")
        object.__setattr__(self, "findings", list(self.findings))

    @property
    def errors(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "target": self.target,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def verify_pack(root: Path) -> PackReport:
    root = root.resolve()
    findings: list[PackFinding] = []
    if not root.exists():
        findings.append(
            PackFinding(
                "pack_target_missing",
                f"pack target does not exist: {root}",
                ".",
            )
        )
        return PackReport(str(root), findings)
    if not root.is_dir():
        findings.append(
            PackFinding(
                "pack_target_not_directory",
                f"pack target is not a directory: {root}",
                ".",
            )
        )
        return PackReport(str(root), findings)

    _check_required_files(root, findings)
    _check_makefile_targets(root, findings)
    _check_verification_command_docs(root, findings)
    _check_agents_guardrails(root, findings)
    _check_workflow_pack_file_encoding(root, findings)
    _check_runtime_python_syntax(root, findings)
    _check_runtime_file_list_alignment(root, findings)
    _check_governance_cli_commands(root, findings)
    _check_runtime_continuation_calls(root, findings)
    _check_runtime_executable_bits(root, findings)
    _check_runtime_wrapper_commands(root, findings)
    _check_readme_package_layout(root, findings)
    _check_readme_quick_start(root, findings)
    _check_target_makefile_command_docs(root, findings)
    _check_env_repair_docs(root, findings)
    _check_product_archive_docs(root, findings)
    _check_product_structure_docs(root, findings)
    _check_design_scaffold_docs(root, findings)
    _check_implementation_handoff_docs(root, findings)
    _check_design_reference_docs(root, findings)
    _check_method_reference_baselines(root, findings)
    _check_phase_order_docs(root, findings)
    _check_phase_advance_docs(root, findings)
    _check_phase_primary_skill_alignment(root, findings)
    _check_phase_workflow_sections(root, findings)
    _check_skill_frontmatter(root, findings)
    _check_skill_references(root, findings)
    _check_skill_index_docs(root, findings)
    _check_local_markdown_links(root, findings)
    _check_reference_entry_points(root, findings)
    _check_reference_index_docs(root, findings)
    _check_template_entry_points(root, findings)
    _check_template_index_docs(root, findings)
    _check_template_guardrails(root, findings)
    _check_workflow_pack_file_list(root, findings)
    return PackReport(str(root), findings)


def _check_required_files(root: Path, findings: list[PackFinding]) -> None:
    for rel in SOURCE_PACK_REQUIRED_PATHS:
        path = root / rel
        if not path.exists():
            findings.append(
                PackFinding(
                    "pack_required_file_missing",
                    f"missing required pack file: {rel}",
                    rel,
                )
            )
        elif not path.is_file():
            findings.append(
                PackFinding(
                    "pack_required_file_not_file",
                    f"required pack path is not a file: {rel}",
                    rel,
                )
            )


def _check_makefile_targets(root: Path, findings: list[PackFinding]) -> None:
    makefile = root / "Makefile"
    if not makefile.is_file():
        return
    try:
        text = makefile.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    target_recipes = _makefile_target_recipes(text)
    targets = set(target_recipes)
    for target in MAKEFILE_REQUIRED_TARGETS:
        if target in targets:
            continue
        findings.append(
            PackFinding(
                "pack_makefile_target_missing",
                f"Makefile must define verification target: {target}",
                "Makefile",
            )
        )
    for target, required_recipes in MAKEFILE_REQUIRED_TARGET_RECIPES.items():
        if target not in targets:
            continue
        recipes = set(target_recipes[target])
        for recipe in required_recipes:
            if recipe in recipes:
                continue
            findings.append(
                PackFinding(
                    "pack_makefile_target_recipe_missing",
                    f"Makefile target {target} must run command: {recipe}",
                    "Makefile",
                )
            )


def _check_verification_command_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in VERIFICATION_COMMAND_DOC_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        section = _markdown_section(text, "Verification") or ""
        for command in PACK_REQUIRED_VERIFICATION_COMMANDS:
            if command in section:
                continue
            findings.append(
                PackFinding(
                    "pack_verification_command_missing",
                    f"{rel} Verification section must document command: {command}",
                    rel,
                )
            )


def _check_agents_guardrails(root: Path, findings: list[PackFinding]) -> None:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return
    try:
        text = agents.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    purpose = _normalized_prose(_markdown_section(text, "Purpose") or "")
    for phrase in AGENTS_PURPOSE_REQUIRED_PHRASES:
        if phrase in purpose:
            continue
        findings.append(
            PackFinding(
                "pack_agents_purpose_guardrail_missing",
                f"AGENTS.md Purpose section must preserve guardrail: {phrase}",
                "AGENTS.md",
            )
        )
    editing_rules = _normalized_prose(_markdown_section(text, "Editing Rules") or "")
    for phrase in AGENTS_EDITING_REQUIRED_PHRASES:
        if phrase in editing_rules:
            continue
        findings.append(
            PackFinding(
                "pack_agents_editing_rule_missing",
                f"AGENTS.md Editing Rules section must preserve guardrail: {phrase}",
                "AGENTS.md",
            )
        )
    required_reading = _normalized_prose(_markdown_section(text, "Required Reading") or "")
    for phrase in AGENTS_REQUIRED_READING_PHRASES:
        if phrase in required_reading:
            continue
        findings.append(
            PackFinding(
                "pack_agents_required_reading_missing",
                f"AGENTS.md Required Reading section must preserve guardrail: {phrase}",
                "AGENTS.md",
            )
        )
    verification = _normalized_prose(_markdown_section(text, "Verification") or "")
    for phrase in AGENTS_VERIFICATION_REQUIRED_PHRASES:
        if phrase in verification:
            continue
        findings.append(
            PackFinding(
                "pack_agents_verification_guardrail_missing",
                f"AGENTS.md Verification section must preserve guardrail: {phrase}",
                "AGENTS.md",
            )
        )
    baseline = _normalized_prose(_markdown_section(text, "Baseline Rule") or "")
    for phrase in AGENTS_BASELINE_REQUIRED_PHRASES:
        if phrase in baseline:
            continue
        findings.append(
            PackFinding(
                "pack_agents_baseline_guardrail_missing",
                f"AGENTS.md Baseline Rule section must preserve guardrail: {phrase}",
                "AGENTS.md",
            )
        )


def _check_workflow_pack_file_encoding(root: Path, findings: list[PackFinding]) -> None:
    for rel_path in _iter_workflow_pack_files(root):
        rel = rel_path.as_posix()
        path = root / rel_path
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_file_invalid_encoding",
                    f"workflow-pack source file must be UTF-8: {rel}",
                    rel,
                )
            )
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_file_unreadable",
                    f"workflow-pack source file is unreadable: {rel}: {_os_error_reason(error)}",
                    rel,
                )
            )


def _check_runtime_python_syntax(root: Path, findings: list[PackFinding]) -> None:
    for rel_path in RUNTIME_REQUIRED_PATHS:
        if rel_path.suffix != ".py":
            continue
        rel = rel_path.as_posix()
        path = root / rel_path
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        try:
            compile(source, rel, "exec")
        except SyntaxError as error:
            detail = f"{error.msg} at line {error.lineno}" if error.lineno else error.msg
            findings.append(
                PackFinding(
                    "pack_runtime_python_syntax_invalid",
                    f"runtime Python file has invalid Python syntax: {rel}: {detail}",
                    rel,
                )
            )


def _check_runtime_file_list_alignment(root: Path, findings: list[PackFinding]) -> None:
    bootstrap_rel = "scripts/bootstrap_tree.py"
    verifier_rel = "scripts/verify_governance.py"
    bootstrap_lists = _runtime_file_lists(root, bootstrap_rel, findings)
    verifier_lists = _runtime_file_lists(root, verifier_rel, findings)
    for label in ("bin", "scripts"):
        bootstrap_name = RUNTIME_FILE_LIST_MODULES[bootstrap_rel][label]
        verifier_name = RUNTIME_FILE_LIST_MODULES[verifier_rel][label]
        bootstrap_values = bootstrap_lists.get(bootstrap_name)
        verifier_values = verifier_lists.get(verifier_name)
        if bootstrap_values is None or verifier_values is None:
            continue
        if bootstrap_values == verifier_values:
            continue
        details = _runtime_file_list_mismatch_details(
            bootstrap_name,
            verifier_name,
            bootstrap_values,
            verifier_values,
        )
        path = _runtime_file_list_mismatch_path(
            bootstrap_rel,
            verifier_rel,
            bootstrap_values,
            verifier_values,
        )
        findings.append(
            PackFinding(
                "pack_runtime_file_list_mismatch",
                f"runtime {label} file lists must stay aligned between {bootstrap_rel}:{bootstrap_name} "
                f"and {verifier_rel}:{verifier_name}: {details}",
                path,
            )
        )


def _runtime_file_lists(root: Path, rel: str, findings: list[PackFinding]) -> dict[str, tuple[str, ...]]:
    path = root / rel
    if not path.is_file():
        return {}
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {}

    required_names = set(RUNTIME_FILE_LIST_MODULES[rel].values())
    assignments: dict[str, tuple[str, ...]] = {}
    invalid_names: set[str] = set()
    for node in tree.body:
        name: str | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            value = node.value
        if name not in required_names:
            continue
        sequence = _ast_string_sequence(value)
        if sequence is None:
            invalid_names.add(name)
            continue
        assignments[name] = sequence

    for name in sorted(required_names - set(assignments) - invalid_names):
        findings.append(
            PackFinding(
                "pack_runtime_file_list_missing",
                f"{rel} must define runtime file list: {name}",
                rel,
            )
        )
    for name in sorted(invalid_names):
        findings.append(
            PackFinding(
                "pack_runtime_file_list_not_literal",
                f"{rel} runtime file list must be a literal string list or tuple: {name}",
                rel,
            )
        )
    return assignments


def _ast_string_sequence(node: ast.AST | None) -> tuple[str, ...] | None:
    if not isinstance(node, ast.List | ast.Tuple):
        return None
    values: list[str] = []
    for element in node.elts:
        value = _ast_string_literal(element)
        if value is None:
            return None
        values.append(value)
    return tuple(values)


def _runtime_file_list_mismatch_details(
    bootstrap_name: str,
    verifier_name: str,
    bootstrap_values: tuple[str, ...],
    verifier_values: tuple[str, ...],
) -> str:
    missing_from_bootstrap = [value for value in verifier_values if value not in bootstrap_values]
    missing_from_verifier = [value for value in bootstrap_values if value not in verifier_values]
    details = []
    if missing_from_bootstrap:
        details.append(f"missing from {bootstrap_name}: {', '.join(missing_from_bootstrap)}")
    if missing_from_verifier:
        details.append(f"missing from {verifier_name}: {', '.join(missing_from_verifier)}")
    if not details:
        details.append("same entries but order differs")
    return "; ".join(details)


def _runtime_file_list_mismatch_path(
    bootstrap_rel: str,
    verifier_rel: str,
    bootstrap_values: tuple[str, ...],
    verifier_values: tuple[str, ...],
) -> str:
    if any(value not in bootstrap_values for value in verifier_values):
        return bootstrap_rel
    return verifier_rel


def _check_governance_cli_commands(root: Path, findings: list[PackFinding]) -> None:
    rel = GOVERNANCE_CLI_PATH.as_posix()
    path = root / GOVERNANCE_CLI_PATH
    if not path.is_file():
        return
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return
    build_parser = _find_function_def(tree, "build_parser")
    if build_parser is None:
        findings.append(
            PackFinding(
                "pack_governance_cli_build_parser_missing",
                "scripts/governance_cli.py must define build_parser()",
                rel,
            )
        )
        return
    parser_calls = _governance_cli_parser_calls(build_parser)
    for command in GOVERNANCE_CLI_REQUIRED_COMMANDS:
        if command in parser_calls["top-level"]:
            continue
        findings.append(
            PackFinding(
                "pack_governance_cli_command_missing",
                f"scripts/governance_cli.py build_parser() must expose top-level command: {command}",
                rel,
            )
        )
    for group, commands in GOVERNANCE_CLI_REQUIRED_SUBCOMMANDS.items():
        for command in commands:
            if command in parser_calls[group]:
                continue
            findings.append(
                PackFinding(
                    "pack_governance_cli_subcommand_missing",
                    f"scripts/governance_cli.py build_parser() must expose {group} subcommand: {command}",
                    rel,
                )
            )


def _check_runtime_continuation_calls(root: Path, findings: list[PackFinding]) -> None:
    for rel in CONTINUATION_RUNTIME_SCRIPT_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for function_name in CONTINUATION_RUNTIME_REQUIRED_CALLS:
            if _script_calls_function(tree, function_name):
                continue
            findings.append(
                PackFinding(
                    "pack_runtime_continuation_call_missing",
                    f"{rel} must call {function_name} for machine-readable continuation payloads",
                    rel,
                )
            )


def _script_calls_function(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == name:
            return True
    return False


def _find_function_def(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _governance_cli_parser_calls(function: ast.FunctionDef) -> dict[str, set[str]]:
    calls = {group: set() for group in GOVERNANCE_CLI_PARSER_VARIABLES}
    variables = {variable: group for group, variable in GOVERNANCE_CLI_PARSER_VARIABLES.items()}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_parser":
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        group = variables.get(node.func.value.id)
        if group is None or not node.args:
            continue
        command = _ast_string_literal(node.args[0])
        if command is not None:
            calls[group].add(command)
    return calls


def _ast_string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _check_runtime_executable_bits(root: Path, findings: list[PackFinding]) -> None:
    for rel_path in RUNTIME_EXECUTABLE_PATHS:
        rel = rel_path.as_posix()
        path = root / rel_path
        if not path.exists() or not path.is_file():
            continue
        if path.stat().st_mode & 0o111:
            continue
        findings.append(
            PackFinding(
                "pack_runtime_file_not_executable",
                f"runtime wrapper is not executable: {rel}",
                rel,
            )
        )


def _check_runtime_wrapper_commands(root: Path, findings: list[PackFinding]) -> None:
    for rel, command in RUNTIME_WRAPPER_REQUIRED_COMMANDS.items():
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for guard in RUNTIME_WRAPPER_REQUIRED_GUARDS:
            if guard in text:
                continue
            findings.append(
                PackFinding(
                    "pack_runtime_wrapper_guard_missing",
                    f"runtime wrapper must include shell guard: {guard}",
                    rel,
                )
            )
        if RUNTIME_WRAPPER_ROOT_DIR_LINE not in text:
            findings.append(
                PackFinding(
                    "pack_runtime_wrapper_root_missing",
                    f"runtime wrapper must resolve repository root with ROOT_DIR: {RUNTIME_WRAPPER_ROOT_DIR_LINE}",
                    rel,
                )
            )
        if command in text:
            continue
        findings.append(
            PackFinding(
                "pack_runtime_wrapper_command_mismatch",
                f"runtime wrapper must invoke expected command: {command}",
                rel,
            )
        )


def _check_readme_package_layout(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    try:
        text = readme.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    layout = _package_layout_directories(_markdown_section(text, "Package Layout") or "")
    expected = set(README_PACKAGE_LAYOUT_DIRECTORIES)
    for directory in README_PACKAGE_LAYOUT_DIRECTORIES:
        if directory in layout:
            continue
        findings.append(
            PackFinding(
                "pack_package_layout_missing_directory",
                f"README.md Package Layout must list directory: {directory}/",
                "README.md",
            )
        )
    for directory in sorted(layout - expected):
        findings.append(
            PackFinding(
                "pack_package_layout_stale_directory",
                f"README.md Package Layout lists unexpected directory: {directory}/",
                "README.md",
            )
        )


def _check_readme_quick_start(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    try:
        text = readme.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    quick_start = _markdown_section(text, "Quick Start") or ""
    for command in README_QUICK_START_REQUIRED_COMMANDS:
        if command in quick_start:
            continue
        findings.append(
            PackFinding(
                "pack_readme_quick_start_command_missing",
                f"README.md Quick Start must document command: {command}",
                "README.md",
            )
        )
    for command in README_AGENT_AUTOMATION_REQUIRED_COMMANDS:
        if command in quick_start:
            continue
        findings.append(
            PackFinding(
                "pack_readme_agent_automation_command_missing",
                f"README.md Quick Start must document agent automation command: {command}",
                "README.md",
            )
        )


def _check_target_makefile_command_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in TARGET_MAKEFILE_DOC_PATHS:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for command in TARGET_MAKEFILE_REQUIRED_COMMANDS:
            if command in text:
                continue
            findings.append(
                PackFinding(
                    "pack_target_makefile_command_doc_missing",
                    f"{rel} must document generated target Makefile command: {command}",
                    rel,
                )
            )


def _check_env_repair_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in ENV_REPAIR_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [field for field in ENV_REPAIR_REQUIRED_FIELDS if field not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_env_repair_doc_field_missing",
                f"{rel} must document environment repair JSON field(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_product_archive_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in PRODUCT_ARCHIVE_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in PRODUCT_ARCHIVE_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_product_archive_doc_missing",
                f"{rel} must document product archive closeout phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_product_structure_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in PRODUCT_STRUCTURE_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in PRODUCT_STRUCTURE_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_product_structure_doc_missing",
                f"{rel} must document product scaffold phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_design_scaffold_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in DESIGN_SCAFFOLD_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in DESIGN_SCAFFOLD_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_design_scaffold_doc_missing",
                f"{rel} must document design scaffold phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_implementation_handoff_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in IMPLEMENTATION_HANDOFF_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_implementation_handoff_doc_missing",
                f"{rel} must document implementation handoff phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_design_reference_docs(root: Path, findings: list[PackFinding]) -> None:
    for reference, consumers in DESIGN_REFERENCE_DOC_REQUIREMENTS:
        for rel in consumers:
            text = _read_utf8_text_or_none(root / rel)
            if text is None or reference in text:
                continue
            findings.append(
                PackFinding(
                    "pack_design_reference_doc_missing",
                    f"{rel} must route design work through reference document: {reference}",
                    rel,
                )
            )


def _check_method_reference_baselines(root: Path, findings: list[PackFinding]) -> None:
    for rel, baselines in METHOD_REFERENCE_BASELINES.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for label, required_phrases in baselines:
            missing = [phrase for phrase in required_phrases if phrase not in text]
            if not missing:
                continue
            findings.append(
                PackFinding(
                    "pack_method_reference_baseline_missing",
                    f"{rel} must preserve {label} method baseline phrase(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_phase_order_docs(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if readme.is_file():
        try:
            text = readme.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        workflow_order = _ordered_numbered_backticked_values(_markdown_section(text, "Workflow Order") or "")
        expected = list(PHASE_WORKFLOW_PATHS)
        if workflow_order != expected:
            findings.append(
                PackFinding(
                    "pack_workflow_order_mismatch",
                    "README.md Workflow Order must match phase workflow files",
                    "README.md",
                )
            )

    overview = root / "workflows/00-overview.md"
    if overview.is_file():
        try:
            text = overview.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        phase_map_section = _markdown_section(text, "Phase Map") or ""
        phase_map = _phase_map_numbers(phase_map_section)
        expected_numbers = [Path(path).name.split("-", 1)[0] for path in PHASE_WORKFLOW_PATHS]
        if phase_map != expected_numbers:
            findings.append(
                PackFinding(
                    "pack_phase_map_mismatch",
                    "workflows/00-overview.md Phase Map must match phase workflow files",
                    "workflows/00-overview.md",
                )
            )
        _check_phase_map_titles(root, phase_map_section, findings)


def _check_phase_advance_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in PHASE_ADVANCE_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        normalized = text.lower()
        missing = [phrase for phrase in PHASE_ADVANCE_REQUIRED_PHRASES if phrase not in normalized]
        if missing:
            findings.append(
                PackFinding(
                    "pack_phase_advance_doc_missing",
                    f"{rel} must document sequential advance semantics: {', '.join(missing)}",
                    rel,
                )
            )
        ambiguous = [phrase for phrase in PHASE_ADVANCE_AMBIGUOUS_PHRASES if phrase in normalized]
        if ambiguous:
            findings.append(
                PackFinding(
                    "pack_phase_advance_doc_ambiguous",
                    f"{rel} must not describe advance with ambiguous phase movement wording: {', '.join(ambiguous)}",
                    rel,
                )
            )


def _check_phase_map_titles(root: Path, phase_map_section: str, findings: list[PackFinding]) -> None:
    phase_titles = _phase_map_titles(phase_map_section)
    if not phase_titles:
        return
    for rel in PHASE_WORKFLOW_PATHS:
        phase = Path(rel).name.split("-", 1)[0]
        listed_title = phase_titles.get(phase)
        if listed_title is None:
            continue
        workflow_title = _phase_workflow_title(root / rel)
        if workflow_title is None:
            continue
        if _normalize_heading(listed_title) == _normalize_heading(workflow_title):
            continue
        findings.append(
            PackFinding(
                "pack_phase_map_title_mismatch",
                f"workflows/00-overview.md Phase Map row {phase} purpose must match workflow title: {workflow_title}",
                "workflows/00-overview.md",
            )
        )


def _check_phase_primary_skill_alignment(root: Path, findings: list[PackFinding]) -> None:
    overview = root / "workflows/00-overview.md"
    if not overview.is_file():
        return
    try:
        overview_text = overview.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    phase_map = _phase_map_primary_skills(_markdown_section(overview_text, "Phase Map") or "")
    if not phase_map:
        return

    for rel in PHASE_WORKFLOW_PATHS:
        phase = Path(rel).name.split("-", 1)[0]
        expected_skills = phase_map.get(phase, [])
        if not expected_skills:
            if phase in phase_map:
                findings.append(
                    PackFinding(
                        "pack_phase_map_primary_skill_missing",
                        f"workflows/00-overview.md Phase Map row {phase} must name at least one primary skill",
                        "workflows/00-overview.md",
                    )
                )
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        workflow_skills = _extract_skill_tokens(_markdown_section(text, "Skills") or "")
        workflow_skill_set = set(workflow_skills)
        missing = [skill for skill in expected_skills if skill not in workflow_skill_set]
        if missing:
            findings.append(
                PackFinding(
                    "pack_phase_primary_skill_missing",
                    f"{rel} Skills section is missing overview primary skill(s): {', '.join(missing)}",
                    rel,
                )
            )
        elif _ordered_intersection(workflow_skills, expected_skills) != expected_skills:
            findings.append(
                PackFinding(
                    "pack_phase_primary_skill_order_mismatch",
                    f"workflows/00-overview.md Phase Map row {phase} primary skills must match {rel} Skills order",
                    "workflows/00-overview.md",
                )
            )

    router_rel = "skills/using-governance-workflow/SKILL.md"
    router = root / router_rel
    if not router.is_file():
        return
    try:
        router_text = router.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    router_skills = _extract_skill_tokens(_markdown_section(router_text, "Route") or "")
    router_skill_set = set(router_skills)
    phase_primary_skills = sorted({skill for skills in phase_map.values() for skill in skills})
    missing_router_skills = [skill for skill in phase_primary_skills if skill not in router_skill_set]
    if missing_router_skills:
        findings.append(
            PackFinding(
                "pack_router_primary_skill_missing",
                "router skill Route section must mention overview primary skill(s): "
                + ", ".join(missing_router_skills),
                router_rel,
            )
        )
    for phase, expected_skills in phase_map.items():
        if not expected_skills:
            continue
        phase_missing_router_skills = [skill for skill in expected_skills if skill not in router_skill_set]
        if phase_missing_router_skills:
            continue
        if _ordered_intersection(router_skills, expected_skills) != expected_skills:
            findings.append(
                PackFinding(
                    "pack_router_primary_skill_order_mismatch",
                    f"router skill Route section must preserve Phase Map row {phase} primary skill order",
                    router_rel,
                )
            )


def _check_phase_workflow_sections(root: Path, findings: list[PackFinding]) -> None:
    for rel in PHASE_WORKFLOW_PATHS:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_workflow_invalid_encoding",
                    f"workflow file must be UTF-8 Markdown: {rel}",
                    rel,
                )
            )
            continue
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_workflow_unreadable",
                    f"workflow file is unreadable: {rel}: {_os_error_reason(error)}",
                    rel,
                )
            )
            continue
        expected_heading_prefix = f"Phase {Path(rel).name.split('-', 1)[0]}:"
        heading_match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
        heading = heading_match.group(1).strip() if heading_match else ""
        if not heading.startswith(expected_heading_prefix):
            findings.append(
                PackFinding(
                    "pack_workflow_phase_heading_mismatch",
                    f"workflow phase H1 must start with '{expected_heading_prefix}': {rel}",
                    rel,
                )
            )
        else:
            expected_title = PHASE_WORKFLOW_TITLES.get(rel, "")
            title = heading.split(":", 1)[1].strip()
            if _normalize_heading(title) != _normalize_heading(expected_title):
                findings.append(
                    PackFinding(
                        "pack_workflow_phase_title_mismatch",
                        f"workflow phase H1 title must match canonical title '{expected_title}': {rel}",
                        rel,
                    )
                )
        ordered_sections = [_normalize_heading(match) for match in re.findall(r"(?m)^##\s+(.+?)\s*$", text)]
        sections = set(ordered_sections)
        for section in PHASE_WORKFLOW_REQUIRED_SECTIONS:
            if _normalize_heading(section) not in sections:
                findings.append(
                    PackFinding(
                        "pack_workflow_section_missing",
                        f"workflow phase missing section '{section}': {rel}",
                        rel,
                    )
            )
            elif not (_markdown_section(text, section) or "").strip():
                findings.append(
                    PackFinding(
                        "pack_workflow_section_empty",
                        f"workflow phase section is empty: {rel}#{section}",
                        rel,
                    )
                )
        if all(_normalize_heading(section) in sections for section in PHASE_WORKFLOW_REQUIRED_SECTIONS):
            required_positions = [
                ordered_sections.index(_normalize_heading(section))
                for section in PHASE_WORKFLOW_REQUIRED_SECTIONS
            ]
            if required_positions != sorted(required_positions):
                findings.append(
                    PackFinding(
                        "pack_workflow_section_order_mismatch",
                        "workflow phase sections must appear in operating-model order: "
                        + ", ".join(PHASE_WORKFLOW_REQUIRED_SECTIONS),
                        rel,
                    )
                )


def _check_skill_references(root: Path, findings: list[PackFinding]) -> None:
    skill_names = _available_skill_names(root)
    references: dict[str, set[str]] = {}
    for rel, section in _skill_reference_sections():
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        section_text = _markdown_section(text, section)
        if section_text is None:
            continue
        for skill in _extract_skill_tokens(section_text):
            references.setdefault(skill, set()).add(rel)
            if skill in skill_names:
                continue
            findings.append(
                PackFinding(
                    "pack_skill_reference_missing",
                    f"{rel} references missing skill: {skill}",
                    rel,
                )
            )
    for skill in sorted(skill_names - set(references)):
        findings.append(
            PackFinding(
                "pack_skill_unreferenced",
                f"skill is not referenced by workflow routing: {skill}",
                f"skills/{skill}/SKILL.md",
            )
        )


def _check_local_markdown_links(root: Path, findings: list[PackFinding]) -> None:
    for path in _iter_pack_link_check_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_markdown_invalid_encoding",
                    f"pack Markdown file must be UTF-8: {rel}",
                    rel,
                )
            )
            continue
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_markdown_unreadable",
                    f"pack Markdown file is unreadable: {rel}: {_os_error_reason(error)}",
                    rel,
                )
            )
            continue
        for target in _extract_local_markdown_link_targets(text):
            reference = _resolve_local_markdown_link(root, path, target)
            if reference is None:
                continue
            reference_rel, exists = reference
            if exists:
                continue
            findings.append(
                PackFinding(
                    "pack_local_markdown_link_missing",
                    f"{rel} links to missing local Markdown target: {reference_rel}",
                    rel,
                )
            )


def _check_reference_entry_points(root: Path, findings: list[PackFinding]) -> None:
    entry_text = "\n".join(_read_reference_entry_texts(root))
    for reference in _iter_reference_files(root):
        rel = reference.relative_to(root).as_posix()
        if rel in entry_text:
            continue
        findings.append(
            PackFinding(
                "pack_reference_unrouted",
                f"reference document is not mentioned by README, AGENTS, workflows, or skills: {rel}",
                rel,
            )
        )


def _check_template_entry_points(root: Path, findings: list[PackFinding]) -> None:
    entry_text = "\n".join(_read_template_entry_texts(root))
    for template in _iter_template_files(root):
        rel = template.relative_to(root).as_posix()
        if rel in entry_text:
            continue
        findings.append(
            PackFinding(
                "pack_template_unrouted",
                f"template document is not mentioned by README, AGENTS, workflows, skills, or references: {rel}",
                rel,
            )
        )


def _check_reference_index_docs(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    try:
        text = readme.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    section = _markdown_section(text, "Reference Files") or ""
    reference_index, missing_descriptions = _readme_index_entries(section, "references/", ".md")
    references = {path.relative_to(root).as_posix() for path in _iter_reference_files(root)}
    _check_readme_index_entry_descriptions("Reference Files", missing_descriptions, findings)
    for rel in sorted(references - reference_index):
        findings.append(
            PackFinding(
                "pack_reference_index_missing",
                f"README.md Reference Files must list reference file: {rel}",
                "README.md",
            )
        )
    for rel in sorted(reference_index - references):
        findings.append(
            PackFinding(
                "pack_reference_index_stale",
                f"README.md Reference Files lists missing reference file: {rel}",
                "README.md",
            )
        )


def _check_template_index_docs(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    try:
        text = readme.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    section = _markdown_section(text, "Template Files") or ""
    template_index, missing_descriptions = _readme_index_entries(section, "templates/", ".md")
    templates = {path.relative_to(root).as_posix() for path in _iter_template_files(root)}
    _check_readme_index_entry_descriptions("Template Files", missing_descriptions, findings)
    for rel in sorted(templates - template_index):
        findings.append(
            PackFinding(
                "pack_template_index_missing",
                f"README.md Template Files must list template file: {rel}",
                "README.md",
            )
        )
    for rel in sorted(template_index - templates):
        findings.append(
            PackFinding(
                "pack_template_index_stale",
                f"README.md Template Files lists missing template file: {rel}",
                "README.md",
            )
        )


def _check_template_guardrails(root: Path, findings: list[PackFinding]) -> None:
    for rel in sorted(set(TEMPLATE_REQUIRED_GUARDRAILS) | set(TEMPLATE_REQUIRED_SECTIONS)):
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for guardrail in TEMPLATE_REQUIRED_GUARDRAILS.get(rel, ()):
            if guardrail in text:
                continue
            findings.append(
                PackFinding(
                    "pack_template_guardrail_missing",
                    f"{rel} template must preserve guardrail: {guardrail}",
                    rel,
                )
            )
        for section in TEMPLATE_REQUIRED_SECTIONS.get(rel, ()):
            if _markdown_section(text, section) is not None:
                continue
            findings.append(
                PackFinding(
                    "pack_template_section_missing",
                    f"{rel} template must include section: {section}",
                    rel,
                )
            )


def _check_skill_frontmatter(root: Path, findings: list[PackFinding]) -> None:
    skills_root = root / "skills"
    if not skills_root.exists() or not skills_root.is_dir():
        return
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        rel = Path("skills") / skill_dir.name / "SKILL.md"
        skill_file = root / rel
        if not skill_file.exists():
            findings.append(
                PackFinding(
                    "pack_skill_missing_file",
                    f"missing skill file: {rel.as_posix()}",
                    rel.as_posix(),
                )
            )
            continue
        if not skill_file.is_file():
            findings.append(
                PackFinding(
                    "pack_skill_file_not_file",
                    f"skill path is not a file: {rel.as_posix()}",
                    rel.as_posix(),
                )
            )
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_skill_invalid_encoding",
                    f"skill file must be UTF-8 Markdown: {rel.as_posix()}",
                    rel.as_posix(),
                )
            )
            continue
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_skill_unreadable",
                    f"skill file is unreadable: {rel.as_posix()}: {_os_error_reason(error)}",
                    rel.as_posix(),
                )
            )
            continue
        _check_single_skill_frontmatter(skill_dir.name, rel.as_posix(), text, findings)


def _check_skill_index_docs(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    try:
        text = readme.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    section = _markdown_section(text, "Skill Files") or ""
    skill_index, missing_descriptions = _readme_index_entries(section, "skills/", "/SKILL.md")
    skills = {path.relative_to(root).as_posix() for path in _iter_skill_files(root)}
    _check_readme_index_entry_descriptions("Skill Files", missing_descriptions, findings)
    for rel in sorted(skills - skill_index):
        findings.append(
            PackFinding(
                "pack_skill_index_missing",
                f"README.md Skill Files must list skill file: {rel}",
                "README.md",
            )
        )
    for rel in sorted(skill_index - skills):
        findings.append(
            PackFinding(
                "pack_skill_index_stale",
                f"README.md Skill Files lists missing skill file: {rel}",
                "README.md",
            )
        )


def _check_single_skill_frontmatter(
    skill_name: str,
    rel: str,
    text: str,
    findings: list[PackFinding],
) -> None:
    if not text.startswith("---\n"):
        findings.append(
            PackFinding(
                "pack_skill_frontmatter_missing",
                f"skill file missing frontmatter: {rel}",
                rel,
            )
        )
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        findings.append(
            PackFinding(
                "pack_skill_frontmatter_unclosed",
                f"skill file frontmatter is not closed: {rel}",
                rel,
            )
        )
        return
    frontmatter = parts[1].strip()
    if not re.search(rf"(?m)^name:\s*{re.escape(skill_name)}$", frontmatter):
        findings.append(
            PackFinding(
                "pack_skill_name_mismatch",
                f"skill frontmatter name must match directory: {rel}",
                rel,
            )
        )
    if not re.search(r"(?m)^description:\s*Use when .+", frontmatter):
        findings.append(
            PackFinding(
                "pack_skill_description_invalid",
                f"skill frontmatter description must start with 'Use when': {rel}",
                rel,
            )
        )
    heading_match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    heading_slug = _slug_from_heading(heading_match.group(1)) if heading_match else ""
    if heading_slug != skill_name:
        findings.append(
            PackFinding(
                "pack_skill_heading_mismatch",
                f"skill H1 must match skill name: {rel}",
                rel,
            )
        )


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _normalized_prose(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("`", "").strip().lower())


def _slug_from_heading(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.lower()))


def _available_skill_names(root: Path) -> set[str]:
    skills_root = root / "skills"
    if not skills_root.exists() or not skills_root.is_dir():
        return set()
    return {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def _skill_reference_sections() -> list[tuple[str, str]]:
    sections = [("workflows/00-overview.md", "Phase Map")]
    sections.extend((rel, "Skills") for rel in PHASE_WORKFLOW_PATHS)
    sections.append(("skills/using-governance-workflow/SKILL.md", "Route"))
    return sections


def _markdown_section(text: str, heading: str) -> str | None:
    pattern = re.compile(r"(?m)^##\s+(.+?)\s*$")
    matches = list(pattern.finditer(text))
    wanted = _normalize_heading(heading)
    for index, match in enumerate(matches):
        if _normalize_heading(match.group(1)) != wanted:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end]
    return None


def _ordered_numbered_backticked_values(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        if not re.match(r"^\s*[0-9]+\.\s+", line):
            continue
        match = re.search(r"`([^`\n]+)`", line)
        if match:
            values.append(match.group(1).strip())
    return values


def _readme_index_entries(text: str, prefix: str, suffix: str) -> tuple[set[str], set[str]]:
    entries: set[str] = set()
    missing_descriptions: set[str] = set()
    for line in _strip_fenced_markdown_code(text).splitlines():
        match = README_INDEX_ENTRY_RE.match(line)
        if match is None:
            continue
        rel = match.group(1).strip()
        if not rel.startswith(prefix) or not rel.endswith(suffix):
            continue
        entries.add(rel)
        if not re.match(r"\s*:\s*\S", match.group("trailing")):
            missing_descriptions.add(rel)
    return entries, missing_descriptions


def _check_readme_index_entry_descriptions(
    section: str,
    missing_descriptions: set[str],
    findings: list[PackFinding],
) -> None:
    for rel in sorted(missing_descriptions):
        findings.append(
            PackFinding(
                "pack_index_entry_description_missing",
                f"README.md {section} entry must include a purpose after ':': {rel}",
                "README.md",
            )
        )


def _package_layout_directories(text: str) -> set[str]:
    return set(re.findall(r"\b([A-Za-z0-9_.-]+)/", text))


def _makefile_target_recipes(text: str) -> dict[str, list[str]]:
    target_recipes: dict[str, list[str]] = {}
    current_targets: list[str] = []
    for line in text.splitlines():
        if line and line[0].isspace():
            recipe = line.strip()
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


def _phase_map_numbers(text: str) -> list[str]:
    numbers: list[str] = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[0-9]{2}", cells[0]):
            continue
        numbers.append(cells[0])
    return numbers


def _phase_map_titles(text: str) -> dict[str, str]:
    titles_by_phase: dict[str, str] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[0-9]{2}", cells[0]):
            continue
        titles_by_phase[cells[0]] = cells[1]
    return titles_by_phase


def _phase_workflow_title(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    match = re.search(r"(?m)^#\s+Phase\s+[0-9]{2}:\s+(.+?)\s*$", text)
    if match is None:
        return None
    return match.group(1).strip()


def _phase_map_primary_skills(text: str) -> dict[str, list[str]]:
    skills_by_phase: dict[str, list[str]] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[0-9]{2}", cells[0]):
            continue
        skills_by_phase[cells[0]] = _extract_skill_tokens(cells[2])
    return skills_by_phase


def _extract_skill_tokens(text: str) -> list[str]:
    text = _strip_fenced_markdown_code(text)
    tokens = []
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip()
        if SKILL_NAME_RE.fullmatch(token):
            tokens.append(token)
    return tokens


def _ordered_intersection(values: list[str], expected: list[str]) -> list[str]:
    expected_set = set(expected)
    return [value for value in values if value in expected_set]


def _iter_pack_link_check_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in PACK_LINK_CHECK_RESOURCE_PATHS:
        source = root / rel
        if not source.exists():
            continue
        if source.is_file():
            if source.suffix == ".md" and not _is_ignored_pack_file(source):
                files.append(source)
            continue
        for path in sorted(source.rglob("*.md")):
            if path.is_file() and not _is_ignored_pack_file(path):
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _iter_reference_files(root: Path) -> list[Path]:
    references_root = root / "references"
    if not references_root.exists() or not references_root.is_dir():
        return []
    return sorted(
        (
            path
            for path in references_root.rglob("*.md")
            if path.is_file() and not _is_ignored_pack_file(path)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _iter_skill_files(root: Path) -> list[Path]:
    skills_root = root / "skills"
    if not skills_root.exists() or not skills_root.is_dir():
        return []
    return sorted(
        (
            path
            for path in skills_root.glob("*/SKILL.md")
            if path.is_file() and not _is_ignored_pack_file(path)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _iter_template_files(root: Path) -> list[Path]:
    templates_root = root / "templates"
    if not templates_root.exists() or not templates_root.is_dir():
        return []
    return sorted(
        (
            path
            for path in templates_root.rglob("*.md")
            if path.is_file() and not _is_ignored_pack_file(path)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _read_reference_entry_texts(root: Path) -> list[str]:
    return _read_entry_texts(root, REFERENCE_ENTRY_RESOURCE_PATHS)


def _read_template_entry_texts(root: Path) -> list[str]:
    return _read_entry_texts(root, TEMPLATE_ENTRY_RESOURCE_PATHS)


def _read_entry_texts(root: Path, resource_paths: tuple[str, ...]) -> list[str]:
    texts: list[str] = []
    for rel in resource_paths:
        source = root / rel
        if not source.exists():
            continue
        if source.is_file():
            if source.suffix == ".md" and not _is_ignored_pack_file(source):
                text = _read_utf8_text_or_none(source)
                if text is not None:
                    texts.append(text)
            continue
        for path in sorted(source.rglob("*.md")):
            if not path.is_file() or _is_ignored_pack_file(path):
                continue
            text = _read_utf8_text_or_none(path)
            if text is not None:
                texts.append(text)
    return texts


def _extract_local_markdown_link_targets(text: str) -> list[str]:
    text = _strip_markdown_code(text)
    targets = [match.group(1) for match in MARKDOWN_LINK_RE.finditer(text)]
    targets.extend(match.group(1) for match in MARKDOWN_REFERENCE_DEFINITION_RE.finditer(text))
    return targets


def _resolve_local_markdown_link(root: Path, source_path: Path, target: str) -> tuple[str, bool] | None:
    raw = target.strip()
    target = raw.strip("`").strip("<>").strip().rstrip(".,;")
    if not target or target.startswith("#") or _is_external_reference_target(target):
        return None
    target = target.replace("\\", "/").split("#", 1)[0].split("?", 1)[0]
    if target.startswith("/"):
        target = target.lstrip("/")
        base = root
    else:
        base = source_path.parent
    if not target.endswith(".md"):
        return None
    candidate = (base / Path(target)).resolve()
    try:
        rel = candidate.relative_to(root.resolve()).as_posix()
    except ValueError:
        return (target, False)
    return (rel, candidate.is_file())


def _is_external_reference_target(target: str) -> bool:
    lowered = target.lower()
    return (
        "://" in lowered
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
        or lowered.startswith("urn:")
    )


def _strip_markdown_code(text: str) -> str:
    text = _strip_fenced_markdown_code(text)
    return re.sub(r"`[^`\n]*`", "", text)


def _strip_fenced_markdown_code(text: str) -> str:
    text = re.sub(r"(?s)```.*?```", "", text)
    return re.sub(r"(?s)~~~.*?~~~", "", text)


def _check_workflow_pack_file_list(root: Path, findings: list[PackFinding]) -> None:
    copied = [path.as_posix() for path in _iter_workflow_pack_files(root)]
    required = list(_workflow_pack_required_paths(root, findings))
    copied_set = set(copied)
    required_set = set(required)
    for rel in sorted(required_set - copied_set):
        findings.append(
            PackFinding(
                "pack_snapshot_required_file_missing",
                f"workflow-pack snapshot source file is missing: {rel}",
                rel,
            )
        )
    for rel in sorted(copied_set - required_set):
        findings.append(
            PackFinding(
                "pack_snapshot_unverified_file",
                f"workflow-pack source file is not listed in verifier required paths: {rel}",
                rel,
            )
        )
    if copied != required and copied_set == required_set:
        findings.append(
            PackFinding(
                "pack_snapshot_order_mismatch",
                "workflow-pack snapshot file order differs from verifier required paths",
                "docs/agent-workflow/workflow-pack/manifest.json",
            )
        )


def _workflow_pack_required_paths(root: Path, findings: list[PackFinding]) -> tuple[str, ...]:
    rel = "scripts/verify_governance.py"
    path = root / rel
    if not path.is_file():
        return tuple(WORKFLOW_PACK_REQUIRED_PATHS)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return tuple(WORKFLOW_PACK_REQUIRED_PATHS)
    value = _top_level_string_sequence(tree, "WORKFLOW_PACK_REQUIRED_PATHS")
    if value is None:
        findings.append(
            PackFinding(
                "pack_workflow_pack_required_paths_not_literal",
                f"{rel} must define WORKFLOW_PACK_REQUIRED_PATHS as a literal string list or tuple",
                rel,
            )
        )
        return tuple(WORKFLOW_PACK_REQUIRED_PATHS)
    return value


def _top_level_string_sequence(tree: ast.AST, name: str) -> tuple[str, ...] | None:
    if not isinstance(tree, ast.Module):
        return None
    for node in tree.body:
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == name:
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        if value is None:
            continue
        return _ast_string_sequence(value)
    return None


def _iter_workflow_pack_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in WORKFLOW_PACK_RESOURCE_PATHS:
        source = root / rel
        if not source.exists():
            continue
        if source.is_file():
            if not _is_ignored_pack_file(source):
                files.append(Path(rel))
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and not _is_ignored_pack_file(path):
                files.append(path.relative_to(root))
    return sorted(files, key=lambda path: path.as_posix())


def _is_ignored_pack_file(path: Path) -> bool:
    parts = set(path.parts)
    return (
        "__pycache__" in parts
        or ".git" in parts
        or path.suffix == ".pyc"
        or path.name in IGNORED_PACK_FILE_NAMES
    )


def _read_utf8_text_or_none(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify workflow-pack source structure.")
    parser.add_argument("target", nargs="?", default=".", help="Workflow-pack repository root.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable pack report.")
    args = parser.parse_args()

    report = verify_pack(Path(args.target))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report.ok else 1
    if report.ok:
        print("Workflow pack verification passed.")
        return 0
    print("Workflow pack verification failed:")
    for error in report.errors:
        print(f"- ERROR: {error}")
    for warning in report.warnings:
        print(f"- WARN: {warning}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
