from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
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

try:
    from .authority_skills import validate_authority_skill_lock
except Exception:  # pragma: no cover - direct execution or damaged source pack
    try:
        from authority_skills import validate_authority_skill_lock
    except Exception as error:  # pragma: no cover - verifier must report damaged optional validator
        validate_authority_skill_lock = None  # type: ignore[assignment]
        AUTHORITY_SKILL_LOCK_VALIDATOR_IMPORT_ERROR = str(error)
    else:
        AUTHORITY_SKILL_LOCK_VALIDATOR_IMPORT_ERROR = ""
else:
    AUTHORITY_SKILL_LOCK_VALIDATOR_IMPORT_ERROR = ""


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
    "templates/docs/agent-workflow/command-contract.md": (
        "# Agent Command Contract",
        "| Name | Purpose | Cwd | Argv | Writes State | Approval Required | Evidence | Environment |",
        '`["bin/governance", "verify", ".", "--check", "--json"]`',
        "| governance-status |",
        '`["bin/governance", "status", ".", "--json"]`',
        "| workflow-plan |",
        '`["bin/governance", "workflow", "plan", ".", "--json"]`',
        "| product-plan |",
        '`["bin/governance", "product", "plan", ".", "--json"]`',
        "| design-plan |",
        '`["bin/governance", "design", "plan", ".", "--json"]`',
        "| implementation-plan |",
        '`["bin/governance", "implementation", "plan", ".", "--json"]`',
        "| implementation-run-check |",
        '`["bin/governance", "implementation", "run", ".", "--check", "--json"]`',
        "| check-env |",
        '`["bin/governance", "env", "--target", ".", "--json"]`',
        "| repair-env-check |",
        '`["bin/governance", "env", "--repair", "--check", "--target", ".", "--json"]`',
        "Add project-specific build, lint, typecheck, unit, integration, contract, end-to-end, migration, and security commands",
        "Keep `Cwd` as `.` or a normalized relative POSIX path inside the repository.",
        "Prefer structured `Argv` arrays over shell strings.",
        "Mark `Approval Required` as `true`",
        "Do not run commands with `Approval Required` set to `true` unless the task explicitly authorizes them.",
        "docs/development/03-verification-log.md",
        "implementation verify . --task TASK-NNN --command command-name --check --json",
        "environment_readiness.ok: true",
        "docs/development/04-implementation-evidence.md",
        "requires `--allow-writes` for state-writing rows",
    ),
    "templates/docs/agent-workflow/project-environment.json": (
        '"schema_version": 1',
        '"id": "core-governance"',
        '"id": "project-runtime"',
        '"executable": "python3"',
        '"minimum": "3.10.0"',
        '"maximum_exclusive": "4.0.0"',
        '"strategy": "governance-env"',
        '"location": "scripts/check_env.py"',
        '"review_evidence": "docs/agent-workflow/workflow-pack/references/project-environment-contract.md"',
    ),
    "templates/docs/agent-workflow/task-handoff.md": (
        "# Agent Task Handoff",
        "- Product:",
        "- API:",
        "- Architecture:",
        "- Design:",
        "- Acceptance:",
        "- Task:",
        "## Implementation Scope",
        "- Allowed files or modules:",
        "- Out of scope:",
        "- Dependencies or sequencing:",
        "- Open questions:",
        "- Code and tests are complete.",
        "- Documentation is synchronized.",
        "- Verification commands pass and output is recorded.",
        "- Required command bindings: `command:<registered-name>`",
        "Resolve exact preflight and execute `argv` from `workflow work-package`",
        "Every required binding must have a current passing row",
        "- Task satisfies `docs/agent-workflow/workflow-pack/references/implementation-readiness-checklist.md`.",
        "- Task execution satisfies `docs/agent-workflow/workflow-pack/references/implementation-execution-checklist.md`.",
        "| Command | Result | Evidence |",
        "- Open follow-ups:",
        "- Risks:",
        "- Supply-chain or release evidence:",
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
        "- Document success path, failure path, retry, timeout, compensation, transaction boundaries, consistency expectations, concurrency conflicts, duplicate-submission handling, observability, and security behavior.",
        "- Document sensitive data, authorization, audit, abuse-limit, and least-privilege dependency behavior where the module is security-sensitive.",
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
        "- Document uniqueness, idempotency keys, cross-user isolation, transaction boundaries, consistency expectations, concurrency conflicts, retention, soft-delete, and audit constraints.",
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
        "- Document dependency trust boundary, update path, version-drift risk, and ADR link for high-risk dependencies.",
        "- Link service API, event, file, queue, or manual contract source.",
        "- Document request fields, response fields, error behavior, and compatibility expectations.",
        "- Document retryable failures, backoff policy, idempotency behavior, compensation, and duplicate-submission handling.",
        "- Document timeout budget, fallback behavior, user-visible impact, and upstream/downstream cancellation policy.",
        "- Document credential owner, auth mechanism, secret storage, rotation, least-privilege access, and access boundary.",
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
        "Ready and In Progress tasks must bind every required check",
        "Done tasks must link Verification to local Markdown evidence.",
        "command:<registered-name>",
        "docs/agent-workflow/command-contract.md",
        "local Markdown evidence path",
    ),
    "templates/docs/development/03-verification-log.md": (
        "# Verification Log",
        "| Task | Command | Result | Date | Notes |",
        "one current summary row per `(Task, Command)`",
        "04-implementation-evidence.md",
        "- none",
    ),
    "templates/docs/development/04-implementation-evidence.md": (
        "# Implementation Verification Evidence",
        "Append-only ledger",
        "Current command status is summarized in `03-verification-log.md`",
        "exact structured `Argv`",
        "redaction metadata",
        "stdout",
        "stderr",
    ),
    "templates/docs/development/05-code-review-evidence.json": (
        '"schema_version": 1',
        '"reviews": []',
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
        "Implementation Scope",
        "Definition of Done",
        "Verification Record",
        "Handoff Notes",
    ),
    "templates/docs/agent-workflow/command-contract.md": (
        "Command Table",
        "Project Commands",
        "Usage Rules",
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
README_ARTIFACT_CONSUMER_QUICK_START_REQUIRED_PHRASES = (
    "## Artifact Consumer Quick Start",
    "source-pack commands from the unpacked workflow pack",
    "target-local commands from the generated project",
    "tar -xzf /path/to/docs-as-code-workflow-pack.tar.gz -C /path/to/workflow-pack",
    "cd /path/to/workflow-pack/docs-as-code-workflow-pack",
    "python3 scripts/verify_pack_manifest.py . --json",
    "python3 scripts/verify_pack.py --json",
    "python3 scripts/smoke_workflow_pack_artifact.py --archive /path/to/docs-as-code-workflow-pack.tar.gz --json",
    "mkdir -p /path/to/new-project",
    "cp /path/to/product.md /path/to/new-project/product.md",
    "bin/governance env --repair --check --target /path/to/new-project --json",
    'bin/governance init --check --target /path/to/new-project --profile web-app --project-name "Project Name" --json',
    'bin/governance init --target /path/to/new-project --profile web-app --project-name "Project Name" --json',
    "cd /path/to/new-project",
    "bin/governance verify . --check --json",
    "make governance-status",
    "make workflow-plan",
    "make product-plan",
    "source-pack check has passed",
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
TARGET_LOCAL_COMMAND_REQUIRED_TARGETS = (
    "verify-governance",
    "verify-check",
    "governance-status",
    "workflow-plan",
    "product-plan",
    "design-plan",
    "implementation-plan",
    "implementation-run-check",
    "check-env",
    "repair-env-check",
    "project-env-plan",
)
FRESH_TARGET_SMOKE_TEST_PATH = "tests/test_fresh_target_workflow.py"
FRESH_TARGET_SMOKE_TEST_REQUIRED_PHRASES = (
    "test_fresh_folder_initializes_and_uses_target_local_commands",
    "TemporaryDirectory",
    "product.md",
    "auto-discovered",
    "Workflow Startup",
    "skill_loading_plan.steps[]",
    "docs/agent-workflow/workflow-pack/skills/",
    "load_authority_routing_skill",
    '"env"',
    '"--repair"',
    '"--check"',
    '"init"',
    '"verify"',
    '"status"',
    "would_repair",
    "repair_commands",
    "repair_actions",
    "repair_execution",
    "can_auto_apply",
    "next_step",
    "local_commands",
    "next_actions",
    "sequence",
    "preflight_for",
    "requires_action",
    "success_condition",
    "advance-product-structuring-check",
    "advance-product-structuring",
    "make_target",
    "make_product_plan",
    '["make", "product-plan"]',
    '"decision_policy"',
    '"do_not_guess_product_meaning"',
    '"manual_authoring_summary"',
    "product-plan",
    "design-plan",
    "repair-env-check",
    "bin/governance",
    '"scaffold"',
    '"product"',
    '"structure"',
    "goals-and-requirements",
    "acceptance-criteria",
    "goals-and-requirements=Goals and Requirements",
    "acceptance-criteria=Acceptance Criteria",
    "would_create",
    "would_index",
    "would_update",
    "scaffold_phase",
    "next_actions_blocked_by",
    "governance_scaffold_placeholder",
    "advance-design-derivation-check",
    "design_advanced",
    "advance-implementation-check",
    "make_design_plan",
    '["make", "design-plan"]',
    "design_scaffold_check",
    "design_scaffold",
    "design_plan",
    '"design"',
    '"plan"',
    "source_documents",
    "tracks",
    "steps",
    "read-product-sources",
    "verify-track",
    "api_candidates",
    "api-candidates",
    "candidates",
    "open_decisions",
    "suggested_endpoint_file",
    "api_authoring",
    "api-authoring",
    "authoring_tasks",
    "decision_policy",
    "backend_authoring",
    "backend-authoring",
    "module_boundaries",
    "observability",
    "architecture_authoring",
    "architecture-authoring",
    "system_boundary",
    "quality_scenarios",
    "adr_candidates",
    "data_model_authoring",
    "data-model-authoring",
    "entity_ownership",
    "migration_order",
    "rollback_strategy",
    "ui_interaction_authoring",
    "ui-interaction-authoring",
    "do_not_guess_ui_behavior",
    "primary_flows",
    "screens",
    "states",
    "frontend_authoring",
    "frontend-authoring",
    "state_ownership",
    "error_actions",
    "test_strategy_authoring",
    "test-strategy-authoring",
    "acceptance_coverage",
    "evidence_targets",
    "implementation_planning_authoring",
    "implementation-planning-authoring",
    "task_scope",
    "ready_criteria",
    "agent_handoff",
    "architecture_decisions_authoring",
    "architecture-decisions-authoring",
    "adr_trigger",
    "decision_scope",
    "alternatives",
    "api-contracts",
    "backend-modules",
    "data-model",
    "ui-interaction",
    "frontend-modules",
    "test-strategy",
    "implementation-planning",
    "architecture-decisions",
    "designing-api-contracts",
    "designing-backend-modules",
    "designing-data-models",
    "designing-ui-interactions",
    "designing-frontend-modules",
    "designing-test-strategy",
    "planning-implementation-work",
    "capturing-architecture-decisions",
    "design_blocked_verify",
    "docs/architecture/01-system-context.md",
    "docs/api/endpoints/README.md",
    "docs/api/endpoints/01-endpoint-contract.md",
    "docs/backend/02-data-model.md",
    "docs/development/03-verification-log.md",
    "METHOD /product-derived-path",
    "| Acceptance | Design | API | Test |",
    '"design-derivation"',
    "runtime-manifest.json",
    "workflow-pack/manifest.json",
    "state_updated",
    "expected_returncode=1",
)
DRY_RUN_WORKFLOW_PATH = "scripts/dry_run_workflow.py"
DRY_RUN_WORKFLOW_REQUIRED_PHRASES = (
    "run_dry_run",
    "fresh-target-governance-dry-run",
    "SAMPLE_PRODUCT",
    "DESIGN_REVIEW_TRACK_ORDER",
    "DESIGN_REVIEW_TRACK_SPECS",
    "ACCEPTANCE_ID_HEADING_RE",
    "acceptance_id_count",
    "expected_task_count",
    "mkdtemp",
    '"env"',
    '"--repair"',
    '"--check"',
    '"init"',
    '"verify"',
    '"status"',
    "TARGET_LOCAL_MAKE_STEP_IDS",
    "make_verify_governance",
    "make_verify_check",
    "make_governance_status",
    "make_workflow_plan_initialized",
    "make_work_package_initialized",
    "make_workflow_resume_initialized",
    "make_workflow_plan_product_structuring",
    "make_work_package_product_structuring",
    "make_workflow_resume_product_structuring",
    "make_workflow_plan_design_derivation",
    "make_work_package_design_derivation",
    "make_workflow_resume_design_derivation",
    "make_work_package_design_complete",
    "make_workflow_plan_implementation",
    "make_work_package_implementation",
    "make_workflow_resume_implementation",
    "make_work_package_complete_after_runtime_refresh",
    "make_workflow_resume_complete_after_runtime_refresh",
    '["make", "workflow-plan"]',
    '["make", "work-package"]',
    '["make", "workflow-resume"]',
    '"scaffold"',
    '"product"',
    "product_plan",
    "make_product_plan",
    '["make", "product-plan"]',
    "suggested_mappings",
    "OPTIONAL_PRODUCT_CHAPTERS",
    "_record_optional_product_dispositions",
    "product_disposition_{step_slug}_check",
    "product_disposition_{step_slug}_apply",
    "product_plan_after_dispositions",
    "work_package_after_product_dispositions",
    "product_dispositions_verify_check",
    "chapter-dispositions.json",
    "product_dispositions",
    '"structure"',
    "goals-and-requirements=Goals and Requirements",
    "acceptance-criteria=Acceptance Criteria",
    '"advance"',
    '"product-structuring"',
    '"design-derivation"',
    '"design"',
    '"plan"',
    "make_design_plan",
    '["make", "design-plan"]',
    '"api-candidates"',
    '"architecture-authoring"',
    '"api-authoring"',
    '"backend-authoring"',
    '"data-model-authoring"',
    '"ui-interaction-authoring"',
    '"frontend-authoring"',
    '"test-strategy-authoring"',
    '"implementation-planning-authoring"',
    '"architecture-decisions-authoring"',
    "_record_design_reviews",
    "_record_reliability_review",
    "_record_migration_review",
    "design_review_{step_slug}_check",
    "design_review_{step_slug}_apply",
    "design_plan_after_reviews",
    "expected_design_review_count",
    "design_reviews",
    "work_package_complete",
    "implementation_advance_check",
    "CONSUMER_BOOTSTRAP",
    "consumer_resume_implementation_handoff",
    "_consumer_resume_handoff_ready",
    "_consumer_resume_handoff_summary",
    "state_write_observed",
    "routing_ok",
    "route_ready",
    "runner_contract_valid",
    '"--resume"',
    "implementation_plan",
    "make_implementation_plan",
    '["make", "implementation-plan"]',
    "make_implementation_run_check",
    '["make", "implementation-run-check"]',
    "implementation_run_apply_start",
    "implementation_run_check_in_progress",
    "implementation_run_execute",
    "implementation_review_plan",
    "implementation_review_preview",
    "implementation_review_record",
    "implementation_run_reviewed_check",
    "implementation_run_closeout",
    '"implementation_run"',
    "snapshot_guarded_start",
    "executed_all_required",
    "snapshot_guarded_closeout",
    "implementation_start_preview",
    "implementation_start_apply",
    "implementation_plan_after_start",
    "implementation_start",
    "implementation_verification_preview",
    "implementation_verification_execute",
    "NODE_IMPLEMENTATION_VERIFICATION_COMMAND",
    "RUST_IMPLEMENTATION_VERIFICATION_COMMAND",
    "_register_stack_runtime",
    "_write_stack_acceptance_fixtures",
    "_build_stack_acceptance_summary",
    '"stack_acceptance"',
    '"implementation_verification"',
    '"implementation_review"',
    '"implementation_task_package"',
    "required_verification_commands_passing",
    "04-implementation-evidence.md",
    "05-code-review-evidence.json",
    "all_current_results_passing",
    "make_check_env",
    "make_repair_env_check",
    "project_environment_reviewed_repair_register",
    "project_environment_reviewed_repair_preview",
    "project_environment_reviewed_repair_unapproved",
    "project_environment_reviewed_repair_apply",
    "project_environment_repaired_plan",
    "project-environment-repairs.json",
    "reviewed-command",
    "--approved",
    "scripts/bounded_process.py",
    "_env_repair_decision_allows_workflow",
    "repair_decision",
    "continue_workflow",
    "stop_before_workflow",
    "target_local_make_coverage",
    "workflow_resume",
    "_require_workflow_resume",
    "implementation_closeout_without_evidence",
    "implementation_closeout_with_evidence",
    "implementation_plan_after_closeout_apply",
    "workflow_plan_after_closeout_apply",
    "implementation_closeout",
    "applied_status_updates",
    "blocked_without_evidence",
    "ready_with_evidence",
    "implementation_plan_complete",
    "workflow_plan_complete",
    "runtime_refresh_check_after_complete",
    "runtime_refresh_after_complete",
    "make_workflow_plan_after_runtime_refresh",
    "runtime_refresh",
    "workflow_plan_complete_after_refresh",
    "do_not_mark_done_without_passing_evidence",
    "closeout_ready",
    "expected_returncode=1",
    "governance:scaffold-placeholder",
    "authoring_task_counts",
    "target_retained",
)
DRY_RUN_GOLDEN_FIXTURE_PATH = "tests/fixtures/product-docs/field-service-ops.md"
DRY_RUN_GOLDEN_TEST_PATH = "tests/test_dry_run_workflow.py"
DRY_RUN_GOLDEN_FIXTURE_REQUIRED_PHRASES = (
    "Field Service Operations Portal",
    "Goals and Requirements",
    "Acceptance Criteria",
    "coordinator can submit a complete service request",
    "dispatcher can assign an unassigned request",
    "technician can mark an assigned work order as checked in",
    "operations manager can view an audit timeline",
)
DRY_RUN_GOLDEN_TEST_REQUIRED_PHRASES = (
    "test_dry_run_handles_realistic_multi_acceptance_product_fixture",
    "tests/fixtures/product-docs/field-service-ops.md",
    "acceptance_id_count",
    "api_candidate_count",
    "authoring_task_counts",
    "design_reviews",
    "active_count",
    "work_package_complete",
    "A-004",
)
DRY_RUN_DOC_REQUIREMENTS = {
    "README.md": (
        "make dry-run",
        "make dry-run-golden",
        "python3 scripts/dry_run_workflow.py --json",
        "python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json",
        "temporary target",
        "multi-acceptance",
        "design_reviews",
        "implementation gate remains blocked",
        "closeout blocks `Done`",
        "passing local evidence",
        "code_review_evidence_current",
        "consumer_resume_implementation_handoff",
    ),
    "workflows/00-overview.md": (
        "make dry-run",
        "make dry-run-golden",
        "python3 scripts/dry_run_workflow.py --json",
        "python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json",
        "temporary target",
        "multi-acceptance",
        "design_reviews",
        "implementation gate remains blocked",
        "implementation closeout blocks `Done`",
        "passing local evidence",
        "code_review_evidence_current",
        "consumer_resume_implementation_handoff",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "source workflow-pack health",
        "make dry-run",
        "make dry-run-golden",
        "python3 scripts/dry_run_workflow.py --json",
        "python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json",
        "design_reviews",
        "implementation closeout",
        "code_review_evidence_current",
        "consumer_resume_implementation_handoff",
    ),
    "references/release-readiness-checklist.md": (
        "make dry-run-golden",
        "python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json",
        "final_phase: implementation",
        "acceptance_id_count: 4",
        "api_candidate_count: 4",
        "design_reviews",
        "implementation closeout blocked without evidence",
        "code_review_evidence_current",
        "passing local evidence",
        "consumer_resume_implementation_handoff",
    ),
}
STACK_ACCEPTANCE_PATH = "scripts/stack_acceptance.py"
STACK_ACCEPTANCE_TEST_PATH = "tests/test_stack_acceptance.py"
STACK_ACCEPTANCE_REQUIRED_PHRASES = (
    "run_stack_acceptance",
    "run_dry_run",
    "REQUIRED_STACKS",
    "OPTIONAL_STACKS",
    "real-stack-acceptance",
    "dry_run_failed",
    "stack_acceptance_missing",
    "all_required_passed",
    "strict_rust_passed",
    "--strict-rust",
)
STACK_ACCEPTANCE_TEST_REQUIRED_PHRASES = (
    "test_default_policy_requires_python_and_node_but_not_rust",
    "test_strict_rust_blocks_when_rust_did_not_pass",
    "test_required_stack_failure_is_derived_from_stack_status",
    "test_dry_run_failure_is_preserved_as_a_blocker",
)
STACK_ACCEPTANCE_DOC_REQUIREMENTS = {
    "README.md": (
        "make stack-acceptance",
        "python3 scripts/stack_acceptance.py --json",
        "--strict-rust",
        "Python and Node",
    ),
    "workflows/00-overview.md": (
        "make stack-acceptance",
        "python3 scripts/stack_acceptance.py --json",
        "--strict-rust",
        "Python and Node",
    ),
    "workflows/05-verification-and-drift-control.md": (
        "make stack-acceptance",
        "python3 scripts/stack_acceptance.py --json",
        "--strict-rust",
        "Python and Node",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "make stack-acceptance",
        "python3 scripts/stack_acceptance.py --json",
        "--strict-rust",
        "Python and Node",
    ),
    "references/release-readiness-checklist.md": (
        "make stack-acceptance",
        "python3 scripts/stack_acceptance.py --json",
        "--strict-rust",
        "Python and Node",
    ),
}
SOURCE_PACK_EXPORT_PATH = "scripts/export_workflow_pack.py"
SOURCE_PACK_EXPORT_REQUIRED_PHRASES = (
    "run_export",
    "EXPORT_RESOURCE_PATHS",
    ".github",
    "pack-manifest.json",
    "verify_pack_manifest",
    "verify_pack",
    "sha256_file",
    "tarfile",
    "gzip.GzipFile",
    "--check",
    "--force",
    "--archive",
    "--no-archive",
    "dist/docs-as-code-workflow-pack",
    "docs-as-code source workflow pack",
)
SOURCE_PACK_EXPORT_DOC_REQUIREMENTS = {
    "README.md": (
        "make package",
        "python3 scripts/export_workflow_pack.py --check --json",
        "pack-manifest.json",
        "SHA-256 evidence",
        "tar.gz artifact",
    ),
    "workflows/00-overview.md": (
        "make package",
        "python3 scripts/export_workflow_pack.py --check --json",
        "pack-manifest.json",
        "SHA-256 evidence",
        "tar.gz artifact",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "make package",
        "python3 scripts/export_workflow_pack.py --check --json",
        "python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json",
    ),
}
PACK_MANIFEST_VERIFY_PATH = "scripts/verify_pack_manifest.py"
PACK_MANIFEST_VERIFY_REQUIRED_PHRASES = (
    "verify_pack_manifest",
    "pack-manifest.json",
    "sha256_file",
    "size_bytes",
    "sha256",
    "executable",
    "pack_manifest_file_unmanifested",
    "duplicate",
    "PurePosixPath",
    "PureWindowsPath",
)
PACK_MANIFEST_VERIFY_DOC_REQUIREMENTS = {
    "README.md": (
        "python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json",
        "validates `pack-manifest.json`",
        "SHA-256",
        "unmanifested",
    ),
    "workflows/00-overview.md": (
        "python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json",
        "validates `pack-manifest.json`",
    ),
    "references/release-readiness-checklist.md": (
        "python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json",
        "manifest verification",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "python3 scripts/verify_pack_manifest.py dist/docs-as-code-workflow-pack --json",
    ),
}
CONSUMER_BOOTSTRAP_PATH = "scripts/bootstrap_consumer_project.py"
CONSUMER_BOOTSTRAP_WRAPPER_PATH = "bin/governance-bootstrap"
ONE_COMMAND_CONSUMER_CHECK = "./docs-as-code-workflow-pack/bin/governance-bootstrap --check --json"
ONE_COMMAND_CONSUMER_APPLY = "./docs-as-code-workflow-pack/bin/governance-bootstrap --json"
ONE_COMMAND_CONSUMER_GIT_CHECK = './docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --check --json'
ONE_COMMAND_CONSUMER_GIT_APPLY = './docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --json'
CONSUMER_BOOTSTRAP_REQUIRED_PHRASES = (
    "run_consumer_bootstrap",
    "run_consumer_resume",
    "_consumer_pack_environment_preflight",
    "RESUME_WORKFLOW_PRESETS",
    "_resume_workflow_preset_flags",
    "_collect_consumer_resume_state",
    "_consumer_resume_state_write_observed",
    "_route_consumer_resume_to_implementation",
    "_preview_recorded_implementation_run",
    "_preview_guarded_implementation_run",
    "_snapshot_guarded_runner_action_ready",
    "pack_manifest_verify",
    "pack_verify",
    "authority_skill_inventory",
    "_authority_skill_argv",
    "_authority_skill_apply_argv",
    "authority_skill_repair_apply",
    "--approve-authority-installs",
    "authority_skill_auto_repair",
    "input_resolution",
    "current-directory",
    "target-directory-name",
    "consumer target must not be the workflow-pack root or its descendant",
    "--initialize-git",
    "--git-default-branch",
    "--git-author-name",
    "--git-author-email",
    "--git-origin",
    "--reviewed-git",
    "repository_git_check",
    "target_local_repository_git_apply",
    "repository_git_initialized",
    "product_conversion_env_repair_check",
    "target_local_product_conversion_check",
    "target_local_product_conversion_apply",
    "pending_product_review",
    "--require-tool",
    "--strict-authority-skills",
    "strict_authority_skills",
    "--strict-authority-provenance",
    "strict_authority_provenance",
    "env_repair_check",
    "env_repair_auto_apply",
    "env_repair_check_after_auto_repair",
    "init_check",
    '"target_local_verify_check",',
    '"target_local_governance_status",',
    '"target_local_workflow_plan",',
    '"target_local_work_package",',
    '"target_local_workflow_resume",',
    "workflow_resume_generated",
    "workflow_resume_ok",
    "_workflow_resume_contract_ok",
    "advance_product_structuring_check",
    "advance_product_structuring",
    "target_local_product_plan",
    "target_local_product_scaffold_preview",
    "target_local_product_structure_preview",
    "product_structure_preview_sandbox_scaffold",
    "target_local_product_scaffold_apply",
    "target_local_product_structure_apply_check",
    "target_local_product_structure_apply",
    "target_local_governance_status_after_product_structure_apply",
    "target_local_workflow_plan_after_product_structure_apply",
    "product_clean_verify_check_before_design_derivation",
    "advance_design_derivation_check",
    "advance_design_derivation",
    "target_local_governance_status_design_derivation",
    "target_local_workflow_plan_design_derivation",
    "target_local_design_plan",
    "target_local_design_scaffold_preview",
    "target_local_design_scaffold_apply",
    "target_local_verify_check_after_design_scaffold_apply",
    "target_local_governance_status_after_design_scaffold_apply",
    "target_local_workflow_plan_after_design_scaffold_apply",
    "target_local_design_architecture_authoring_preview",
    "target_local_design_api_authoring_preview",
    "target_local_design_backend_authoring_preview",
    "target_local_design_data_model_authoring_preview",
    "target_local_design_ui_interaction_authoring_preview",
    "target_local_design_frontend_authoring_preview",
    "target_local_design_test_strategy_authoring_preview",
    "target_local_design_implementation_planning_authoring_preview",
    "target_local_design_architecture_decisions_authoring_preview",
    "target_local_verify_check_implementation_readiness_preview",
    "target_local_implementation_gate_preview",
    "target_local_implementation_plan_preview",
    "target_local_implementation_advance_preview",
    "target_local_implementation_advance_apply",
    "target_local_verify_check_after_implementation_advance_apply",
    "target_local_governance_status_after_implementation_advance_apply",
    "target_local_workflow_plan_after_implementation_advance_apply",
    "target_local_implementation_plan_after_implementation_advance_apply",
    "target_local_implementation_run_preview",
    "target_local_implementation_start_preview",
    "target_local_implementation_start_apply",
    "target_local_verify_check_after_implementation_start_apply",
    "target_local_governance_status_after_implementation_start_apply",
    "target_local_workflow_plan_after_implementation_start_apply",
    "target_local_implementation_plan_after_implementation_start_apply",
    "target_local_implementation_closeout_preview",
    "target_local_implementation_closeout_apply",
    "target_local_verify_check_after_implementation_closeout_apply",
    "target_local_governance_status_after_implementation_closeout_apply",
    "target_local_workflow_plan_after_implementation_closeout_apply",
    "target_local_implementation_plan_after_implementation_closeout_apply",
    "_advance_product_structuring",
    "_preview_product_scaffold",
    "_preview_product_structure",
    "_apply_product_structure",
    "_advance_design_derivation",
    "_preview_design_scaffold",
    "_apply_design_scaffold",
    "_has_scaffold_placeholder_findings",
    "_preview_design_authoring",
    "_summarize_design_authoring",
    "_non_negative_int",
    "_preview_implementation_readiness",
    "_implementation_readiness_blockers",
    "_preview_implementation_advance",
    "_apply_implementation_advance",
    "_preview_implementation_run",
    "_preview_implementation_start",
    "_apply_implementation_start",
    "_preview_implementation_closeout",
    "_apply_implementation_closeout",
    "DESIGN_AUTHORING_QUEUE_IDS",
    "TASK_ID_PATTERN",
    "WORKFLOW_PRESETS",
    "_workflow_preset_flags",
    "_maybe_auto_repair_env",
    "_refresh_env_auto_repair_summary",
    "_env_auto_repair_skip_reason",
    "_env_auto_repair_next_step",
    "_env_check_allows_auto_repair",
    "_env_check_allows_workflow",
    "_product_plan_mapping",
    "_target_local_details",
    "local_commands",
    "next_actions",
    "--workflow-preset",
    "--resume",
    "--auto-repair-env",
    "workflow_preset",
    "workflow_preset_expanded_flags",
    "auto_repair_env",
    "env_auto_repair",
    "stop_before_workflow",
    "can_continue",
    "can_auto_apply",
    "requires_approval",
    "manual_repair_required",
    "runnable_action_ids",
    "approval_action_ids",
    "manual_action_ids",
    "next_step",
    "final_env_check_ok",
    "final_missing_required",
    "product-structure",
    "design-scaffold",
    "design-routing",
    "implementation-routing",
    "--advance-product-structuring",
    "--product-scaffold-preview",
    "--product-structure-preview",
    "--product-structure-apply",
    "--advance-design-derivation",
    "--design-scaffold-preview",
    "--design-scaffold-apply",
    "--design-authoring-preview",
    "--implementation-readiness-preview",
    "--implementation-advance-preview",
    "--implementation-advance-apply",
    "--implementation-run-preview",
    "--implementation-start-preview",
    "--implementation-start-apply",
    "--implementation-closeout-preview",
    "--implementation-closeout-apply",
    "product_scaffold_preview_requested",
    "product_scaffold_previewed",
    "product_scaffold_preview_ok",
    "product_structure_preview_requested",
    "product_structure_previewed",
    "product_structure_preview_ok",
    "product_structure_apply_requested",
    "product_structure_applied",
    "product_structure_apply_ok",
    "advance_design_derivation_requested",
    "advanced_design_derivation",
    "design_scaffold_preview_requested",
    "design_scaffold_previewed",
    "design_scaffold_preview_ok",
    "design_scaffold_apply_requested",
    "design_scaffold_applied",
    "design_scaffold_apply_ok",
    "design_authoring_preview_requested",
    "design_authoring_previewed",
    "design_authoring_preview_ok",
    "work_package_generated",
    "work_package_ok",
    "work_package",
    "implementation_readiness_preview_requested",
    "implementation_readiness_previewed",
    "implementation_readiness_preview_ok",
    "implementation_advance_preview_requested",
    "implementation_advance_previewed",
    "implementation_advance_preview_ok",
    "implementation_advance_apply_requested",
    "implementation_advance_applied",
    "implementation_advance_apply_ok",
    "implementation_run_preview_requested",
    "implementation_run_previewed",
    "implementation_run_preview_ok",
    "implementation_routing_requested",
    "implementation_routing_ok",
    "implementation_route_ready",
    "implementation_handoff_ready",
    "implementation_continuation_ready",
    "implementation_terminal",
    "state_write_observed",
    "runner_contract_valid",
    'implementation_run.get("workflow") == "implementation-run"',
    'implementation_run.get("target") == str(target)',
    'implementation_run.get("check") is True',
    'implementation_run.get("writes_requested") is False',
    "transition_already_current",
    "required_advance_applied",
    "handoff_ready",
    'next_action.get("argv") == expected_argv',
    "--implementation-run-preview cannot be combined with implementation start/closeout flags",
    "implementation_start_preview_requested",
    "implementation_start_previewed",
    "implementation_start_preview_ok",
    "implementation_start_apply_requested",
    "implementation_start_applied",
    "implementation_start_apply_ok",
    "implementation_closeout_preview_requested",
    "implementation_closeout_previewed",
    "implementation_closeout_preview_ok",
    "implementation_closeout_apply_requested",
    "implementation_closeout_applied",
    "implementation_closeout_apply_ok",
    "design_derivation",
    "design_scaffold_preview",
    "design_scaffold_apply",
    "design_authoring_preview",
    "queue_summaries",
    "authoring_summary",
    "blocked_queue_count",
    "decision_required_queue_count",
    "ready_queue_count",
    "queue_status_counts",
    "total_task_count",
    "total_open_decision_count",
    "total_non_satisfied_required_link_count",
    "total_link_repair_action_count",
    "next_queue_id",
    "next_active_work",
    "queue_sequence",
    "implementation_readiness_preview",
    "implementation_advance_preview",
    "implementation_advance_apply",
    "implementation_start_preview",
    "implementation_start_apply",
    "implementation_closeout_preview",
    "implementation_closeout_apply",
    "post_implementation_plan",
    "implementation_readiness",
    "readiness_summary",
    "blocker_count",
    "blocker_codes",
    "source_counts",
    "next_blocker",
    "next_repair_action",
    "implementation_plan_error",
    "apply_skipped",
    "skip_reason",
    "skip_code",
    "blocked_by",
    "required_preview_ready",
    "required_readiness_ok",
    "required_start_applied",
    "advance_preview_not_ready",
    "readiness_preview_not_ready",
    "start_preview_not_ready",
    "start_apply_not_applied",
    "closeout_preview_not_ready",
    "design_plan",
    '"writes_state": False',
    '"writes_state": True',
    "product_plan.suggested_mappings",
    "product_plan.suggested_mappings[].command_arg",
    '"scaffold", "product", "."',
    '"product", "structure", "."',
    '"advance", "design-derivation", "."',
    '"advance", "implementation", "."',
    '"scaffold", "design", "."',
    "post_verify_blocked_by_placeholders",
    "governance_scaffold_placeholder",
    '"design", queue_id, "."',
    '"gate", "implementation", "."',
    '"implementation", "plan", "."',
    '"implementation", "start", "."',
    '"implementation", "closeout", "."',
    '"make", "implementation-plan"',
    "TASK-NNN",
    "task_id",
    "allowed_returncodes=(0, 1)",
    "sandboxed_no_target_writes",
    "--check",
    "--force",
    "scripts/verify_pack_manifest.py",
    "scripts/verify_pack.py",
    "scripts/governance_cli.py",
    "bin/governance",
    "make",
    "workflow-plan",
)
CONSUMER_BOOTSTRAP_DOC_REQUIREMENTS = {
    "README.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        ONE_COMMAND_CONSUMER_GIT_CHECK,
        ONE_COMMAND_CONSUMER_GIT_APPLY,
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --check --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --workflow-preset product-structure --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --workflow-preset implementation-routing --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --resume --workflow-preset implementation-routing --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --implementation-run-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-start-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-start-preview --implementation-start-apply --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --implementation-start-preview --implementation-start-apply --implementation-closeout-preview --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --advance-product-structuring --product-scaffold-preview --product-structure-preview --product-structure-apply --advance-design-derivation --design-scaffold-preview --design-scaffold-apply --design-authoring-preview --implementation-readiness-preview --implementation-advance-preview --implementation-advance-apply --implementation-start-preview --implementation-start-apply --implementation-closeout-preview --implementation-closeout-apply --json",
        "source-pack manifest verification",
        "target-local verify/status/workflow-plan checks",
        "--strict-authority-provenance",
        "authority_skill_inventory.repair_plan",
        "--workflow-preset",
        "--auto-repair-env",
        "env_auto_repair",
        "workflow_preset_expanded_flags",
        "product-structure",
        "design-scaffold",
        "design-routing",
        "implementation-routing",
        "state-writing",
        "make product-plan",
        "make design-plan",
        "make implementation-plan",
        "product_plan.suggested_mappings",
        "product_plan.suggested_mappings[].command_arg",
        "scaffold product --check --json",
        "product structure --check --json",
        "--product-structure-apply",
        "--advance-design-derivation",
        "--design-scaffold-preview",
        "--design-scaffold-apply",
        "--design-authoring-preview",
        "--implementation-readiness-preview",
        "--implementation-advance-preview",
        "--implementation-advance-apply",
        "--implementation-run-preview",
        "--resume",
        "--implementation-start-preview",
        "--implementation-start-apply",
        "--implementation-closeout-preview",
        "--implementation-closeout-apply",
        "design_derivation",
        "design_scaffold_preview",
        "design_scaffold_apply",
        "design_authoring_preview",
        "queue_summaries[]",
        "authoring_summary",
        "queue_status_counts",
        "next_queue_id",
        "next_active_work",
        "active_work.queue_id",
        "implementation_readiness_preview",
        "readiness_summary",
        "blockers[]",
        "next_blocker",
        "next_repair_action",
        "implementation_advance_preview",
        "implementation_advance_apply",
        "implementation_run_preview",
        "handoff_ready",
        "runner_contract_valid",
        "implementation_routing_ok",
        "implementation_route_ready",
        "state_write_observed",
        "implementation_handoff_ready",
        "implementation_continuation_ready",
        "implementation_terminal",
        "transition_already_current",
        "implementation_start_preview",
        "implementation_start_apply",
        "implementation_closeout_preview",
        "implementation_closeout_apply",
        "scaffold design --check --json",
        "design architecture-authoring",
        "design api-authoring",
        "design backend-authoring",
        "gate implementation",
        "implementation plan",
        "advance implementation",
        "records the implementation phase",
        "implementation start",
        "In Progress",
        "implementation closeout",
        "Done",
        "TASK-NNN",
        "governance_scaffold_placeholder",
        "writes_state",
        "would_update",
        "local_commands",
        "next_actions",
        "make workflow-resume",
        "workflow_resume",
        "workflow_resume_generated",
        "workflow_resume_ok",
        "snapshot.id",
        "selected_action",
    ),
    "workflows/00-overview.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        ONE_COMMAND_CONSUMER_GIT_CHECK,
        ONE_COMMAND_CONSUMER_GIT_APPLY,
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --check --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --workflow-preset product-structure --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --product /path/to/product.md --profile web-app --project-name \"Project Name\" --workflow-preset implementation-routing --json",
        "python3 scripts/bootstrap_consumer_project.py --target /path/to/new-project --resume --workflow-preset implementation-routing --json",
        "verify_pack_manifest",
        "verify_pack",
        "--strict-authority-provenance",
        "authority_skill_inventory.repair_plan",
        "env --repair --check",
        "init --check",
        "--workflow-preset",
        "--auto-repair-env",
        "env_auto_repair",
        "workflow_preset_expanded_flags",
        "product-structure",
        "design-scaffold",
        "design-routing",
        "implementation-routing",
        "--advance-product-structuring",
        "--product-scaffold-preview",
        "--product-structure-preview",
        "--product-structure-apply",
        "--advance-design-derivation",
        "--design-scaffold-preview",
        "--design-scaffold-apply",
        "--design-authoring-preview",
        "--implementation-readiness-preview",
        "--implementation-advance-preview",
        "--implementation-advance-apply",
        "--implementation-run-preview",
        "--resume",
        "--implementation-start-preview",
        "--implementation-start-apply",
        "--implementation-closeout-preview",
        "--implementation-closeout-apply",
        "target-local",
        "make product-plan",
        "make design-plan",
        "make implementation-plan",
        "product_plan.suggested_mappings",
        "product_plan.suggested_mappings[].command_arg",
        "scaffold product",
        "product structure",
        "design-derivation",
        "scaffold design --check --json",
        "scaffold design",
        "design architecture-authoring",
        "design api-authoring",
        "design backend-authoring",
        "governance_scaffold_placeholder",
        "would_create",
        "would_index",
        "would_update",
        "sandboxed_no_target_writes",
        "writes_state: true",
        "product_structure_apply",
        "design_derivation",
        "design_scaffold_preview",
        "design_scaffold_apply",
        "design_authoring_preview",
        "queue_summaries[]",
        "authoring_summary",
        "queue_status_counts",
        "next_queue_id",
        "next_active_work",
        "active_work.queue_id",
        "implementation_readiness_preview",
        "readiness_summary",
        "blockers[]",
        "next_blocker",
        "next_repair_action",
        "implementation_advance_preview",
        "implementation_advance_apply",
        "implementation_run_preview",
        "handoff_ready",
        "runner_contract_valid",
        "implementation_routing_ok",
        "implementation_route_ready",
        "state_write_observed",
        "implementation_handoff_ready",
        "implementation_continuation_ready",
        "implementation_terminal",
        "transition_already_current",
        "implementation_start_preview",
        "implementation_start_apply",
        "implementation_closeout_preview",
        "implementation_closeout_apply",
        "gate implementation",
        "implementation plan",
        "advance implementation",
        "records the implementation phase",
        "implementation start",
        "In Progress",
        "implementation closeout",
        "Done",
        "TASK-NNN",
        "post-status",
        "post-workflow-plan",
        "local_commands",
        "next_actions",
        "make workflow-resume",
        "workflow_resume",
        "workflow_resume_generated",
        "workflow_resume_ok",
        "snapshot.id",
        "selected_action",
    ),
    "workflows/04-design-derivation.md": (
        "design_authoring_preview",
        "queue_summaries[]",
        "authoring_summary",
        "queue_status_counts",
        "next_queue_id",
        "next_active_work",
        "active_work.queue_id",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        "python3 scripts/bootstrap_consumer_project.py --target <target> --product <product-doc> --profile <profile> --project-name \"<name>\" --check --json",
        "--strict-authority-provenance",
        "authority_skill_inventory.repair_plan",
        "python3 scripts/bootstrap_consumer_project.py --target <target> --product <product-doc> --profile <profile> --project-name \"<name>\" --workflow-preset product-structure --json",
        "--workflow-preset implementation-routing",
        "python3 scripts/bootstrap_consumer_project.py --target <target> --resume --workflow-preset implementation-routing --json",
        "--auto-repair-env",
        "env_auto_repair",
        "workflow_preset_expanded_flags",
        "--advance-product-structuring",
        "--product-scaffold-preview",
        "--product-structure-preview",
        "--product-structure-apply",
        "--advance-design-derivation",
        "--design-scaffold-preview",
        "--design-scaffold-apply",
        "--design-authoring-preview",
        "--implementation-readiness-preview",
        "--implementation-advance-preview",
        "--implementation-advance-apply",
        "--implementation-run-preview",
        "--resume",
        "--implementation-start-preview",
        "--implementation-start-apply",
        "--implementation-closeout-preview",
        "--implementation-closeout-apply",
        "make product-plan",
        "make design-plan",
        "make implementation-plan",
        "product_scaffold_preview",
        "product_structure_preview",
        "product_structure_apply",
        "design_derivation",
        "design_scaffold_preview",
        "design_scaffold_apply",
        "design_authoring_preview",
        "queue_summaries[]",
        "authoring_summary",
        "queue_status_counts",
        "next_queue_id",
        "next_active_work",
        "active_work.queue_id",
        "implementation_readiness_preview",
        "readiness_summary",
        "blockers[]",
        "next_blocker",
        "next_repair_action",
        "implementation_advance_preview",
        "implementation_advance_apply",
        "implementation_run_preview",
        "handoff_ready",
        "runner_contract_valid",
        "implementation_routing_ok",
        "implementation_route_ready",
        "state_write_observed",
        "implementation_handoff_ready",
        "implementation_continuation_ready",
        "implementation_terminal",
        "transition_already_current",
        "implementation_start_preview",
        "implementation_start_apply",
        "implementation_closeout_preview",
        "implementation_closeout_apply",
        "product_plan.suggested_mappings",
        "product_plan.suggested_mappings[].command_arg",
        "scaffold product --check --json",
        "product structure --check --json",
        "product structure --json",
        "advance design-derivation",
        "scaffold design --check --json",
        "design architecture-authoring",
        "design api-authoring",
        "design backend-authoring",
        "gate implementation",
        "implementation plan",
        "advance implementation",
        "records the implementation phase",
        "implementation start",
        "In Progress",
        "implementation closeout",
        "Done",
        "TASK-NNN",
        "governance_scaffold_placeholder",
        "local_commands",
        "next_actions",
    ),
    "workflows/01-empty-repo-initialization.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        ONE_COMMAND_CONSUMER_GIT_CHECK,
        ONE_COMMAND_CONSUMER_GIT_APPLY,
        "target-root-auto-discovery",
        "repository_git_initialized",
    ),
    "skills/initializing-governance-repo/SKILL.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        ONE_COMMAND_CONSUMER_GIT_CHECK,
        ONE_COMMAND_CONSUMER_GIT_APPLY,
        "target-root-auto-discovery",
        "repository_git_initialized",
    ),
    "references/runtime-strategy.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        ONE_COMMAND_CONSUMER_GIT_CHECK,
        ONE_COMMAND_CONSUMER_GIT_APPLY,
        "input_resolution",
        "repository_git_initialized",
    ),
    "references/repository-initialization-checklist.md": (
        ONE_COMMAND_CONSUMER_CHECK,
        ONE_COMMAND_CONSUMER_APPLY,
        ONE_COMMAND_CONSUMER_GIT_CHECK,
        ONE_COMMAND_CONSUMER_GIT_APPLY,
        "input_resolution",
        "repository_git_initialized",
    ),
}
ARTIFACT_SMOKE_PATH = "scripts/smoke_workflow_pack_artifact.py"
ARTIFACT_SMOKE_REQUIRED_PHRASES = (
    "run_artifact_smoke",
    "export_artifact",
    "unpacked_verify_pack_manifest",
    "unpacked_verify_pack",
    "unpacked_init_fresh_target_check",
    "unpacked_init_fresh_target",
    "unpacked_consumer_bootstrap_one_command_check",
    "unpacked_consumer_bootstrap_one_command_apply",
    "consumer_bootstrap_one_command",
    "_consumer_bootstrap_one_command_details",
    "ONE_COMMAND_GIT_ARGS",
    "repository_git_check_ok",
    "repository_git_initialized",
    "repository_git_apply_ok",
    "repository_git_has_commits",
    "unpacked_consumer_bootstrap_product_conversion_check",
    "unpacked_consumer_bootstrap_product_conversion_apply",
    "consumer_bootstrap_product_conversion",
    "_consumer_bootstrap_product_conversion_details",
    "bin/governance-bootstrap",
    "fresh_target_verify_check",
    "fresh_target_governance_status",
    "fresh_target_workflow_plan",
    "fresh_target_work_package",
    "fresh_target_workflow_resume",
    "unpacked_consumer_bootstrap_product_structure",
    "unpacked_consumer_bootstrap_design_scaffold",
    "unpacked_consumer_bootstrap_design_routing",
    "unpacked_consumer_bootstrap_implementation_routing",
    "consumer_bootstrap_product_structure",
    "consumer_bootstrap_design_scaffold",
    "consumer_bootstrap_design_routing",
    "consumer_bootstrap_implementation_routing",
    "authority_skill_inventory",
    "_authority_skill_inventory_details",
    "manifest_aligned_with_routing",
    "repair_requested",
    "repair_writes_state",
    "env_auto_repair",
    "_env_auto_repair_details",
    "stop_before_workflow",
    "can_continue",
    "can_auto_apply",
    "requires_approval",
    "manual_repair_required",
    "runnable_action_ids",
    "approval_action_ids",
    "manual_action_ids",
    "next_step",
    "final_env_check_ok",
    "final_missing_required",
    "_consumer_bootstrap_details",
    "_consumer_work_package_details",
    "_workflow_resume_payload_details",
    "_consumer_workflow_resume_details",
    "_consumer_bootstrap_design_scaffold_details",
    "_consumer_bootstrap_design_routing_details",
    "_design_authoring_summary_ok",
    "_consumer_bootstrap_implementation_routing_details",
    "_has_finding_code",
    "unpacked_dry_run",
    "implementation_verification",
    "implementation_run",
    "guarded implementation runner completion",
    "consumer_resume_implementation_handoff",
    "consumer resume implementation handoff",
    "state_write_observed",
    "routing_ok",
    "route_ready",
    "runner_contract_valid",
    "implementation_task_package",
    "_dry_run_implementation_task_package_details",
    "claim_then_execute_all_required_verification_commands_then_closeout",
    "_dry_run_stack_acceptance_details",
    "required real stack acceptance",
    "stack_acceptance",
    "automated implementation verification evidence",
    "all_current_results_passing",
    "_write_fresh_target_product",
    "_fresh_target_init_details",
    "_sha256_file",
    "--archive",
    "provided-archive",
    "archive_source",
    "fresh_target_init",
    "product_selection",
    "target_local_verify_ok",
    "target_local_status_ok",
    "target_local_workflow_plan_ok",
    "target_local_work_package_ok",
    "target_local_workflow_resume_ok",
    "workflow_resume_generated",
    "workflow_resume_ok",
    "work_package_generated",
    "work_package_ok",
    "work_package",
    "workflow-work-package",
    "skill_readiness",
    "next_action",
    "refresh_command",
    "runtime_manifest",
    "workflow_pack_snapshot",
    "product_source_manifest",
    "safe_extract_archive",
    "pack-manifest.json",
    "archive_member_count",
    "target_retained",
    "scripts/export_workflow_pack.py",
    "scripts/verify_pack_manifest.py",
    "scripts/verify_pack.py",
    "scripts/bootstrap_consumer_project.py",
    "scripts/dry_run_workflow.py",
    "--workflow-preset",
    "product-structure",
    "design-scaffold",
    "design-routing",
    "implementation-routing",
    "--auto-repair-env",
    "product_structure_apply_ok",
    "design_scaffold_apply_ok",
    "design_authoring_preview_ok",
    "implementation_readiness_preview_ok",
    "implementation_advance_preview_ok",
    "implementation_advance_apply_ok",
    "implementation_run_preview_ok",
    "readiness_previewed",
    "readiness_ok",
    "implementation_ready",
    "readiness_blocker_count",
    "readiness_blocker_codes",
    "readiness_next_blocker",
    "readiness_next_repair_action",
    "advance_previewed",
    "advance_ready",
    "advance_apply_skipped",
    "advance_apply_skip_code",
    "advance_apply_blocked_by",
    "run_previewed",
    "run_preview_skipped",
    "run_preview_skip_code",
    "run_preview_blocked_by",
    "run_required_advance_applied",
    "run_handoff_ready",
    "run_status",
    "run_task_id",
    "run_snapshot",
    "run_next_action",
    "blocked_by_placeholders",
    "queue_count",
    "queue_summaries",
    "authoring_summary",
    "authoring_summary_ok",
    "queue_status_counts",
    "next_queue_id",
    "next_active_work",
    "active_work",
    "missing_queue_ids",
    "post_verify_blocked_by_placeholders",
    "workflow_preset_expanded_flags",
    "docs/product/03-goals-and-requirements.md",
    "docs/product/08-acceptance-criteria.md",
    "docs/architecture/01-system-context.md",
    "docs/api/endpoints/01-endpoint-contract.md",
    "final_phase",
    '"implementation"',
    "implementation_closeout",
    "implementation_start",
    "blocked_without_evidence",
    "ready_with_evidence",
    "_dry_run_target_local_make_details",
    "_dry_run_product_disposition_details",
    "_dry_run_design_review_details",
    "_dry_run_reliability_review_details",
    "_dry_run_migration_review_details",
    "target_local_make_coverage",
    "product_dispositions",
    "design_reviews",
    "recorded_count",
    "expected_count",
    "active_count",
    "missing_count",
    "stale_count",
    "work_package_complete",
    "omit_unsupported_count",
    "unresolved_decision_count",
    "work_package_routed_to_phase_action",
    "make_verify_governance",
    "make_verify_check",
    "make_governance_status",
    "make_workflow_plan_initialized",
    "make_work_package_initialized",
    "make_workflow_resume_initialized",
    "make_workflow_plan_product_structuring",
    "make_work_package_product_structuring",
    "make_workflow_resume_product_structuring",
    "make_workflow_plan_design_derivation",
    "make_work_package_design_derivation",
    "make_workflow_resume_design_derivation",
    "make_work_package_design_complete",
    "make_workflow_plan_implementation",
    "make_work_package_implementation",
    "make_workflow_resume_implementation",
    "make_work_package_complete_after_runtime_refresh",
    "make_workflow_resume_complete_after_runtime_refresh",
    "make_product_plan",
    "make_design_plan",
    "make_implementation_plan",
    "make_implementation_run_check",
    "make_check_env",
    "make_repair_env_check",
)
ARTIFACT_SMOKE_DOC_REQUIREMENTS = {
    "README.md": (
        "make artifact-smoke",
        "python3 scripts/smoke_workflow_pack_artifact.py --json",
        "python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json",
        "unpacks the tar.gz artifact",
        "initializes a fresh target folder",
        "target-local verify/status/workflow-plan/work-package/workflow-resume commands",
        "consumer_bootstrap_one_command.ok: true",
        "consumer_bootstrap_one_command.repository_git_initialized: true",
        "consumer_bootstrap_product_conversion.ok: true",
        "--auto-repair-env --workflow-preset product-structure",
        "--auto-repair-env --workflow-preset design-scaffold",
        "--auto-repair-env --workflow-preset design-routing",
        "--auto-repair-env --workflow-preset implementation-routing",
        "consumer_resume_implementation_handoff",
        "design_reviews.ok: true",
    ),
    "workflows/00-overview.md": (
        "make artifact-smoke",
        "python3 scripts/smoke_workflow_pack_artifact.py --json",
        "python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json",
        "unpacks the tar.gz artifact",
        "fresh target",
        "consumer_bootstrap_one_command.ok: true",
        "consumer_bootstrap_one_command.repository_git_initialized: true",
        "consumer_bootstrap_product_conversion.ok: true",
        "--auto-repair-env --workflow-preset product-structure",
        "--auto-repair-env --workflow-preset design-scaffold",
        "--auto-repair-env --workflow-preset design-routing",
        "--auto-repair-env --workflow-preset implementation-routing",
        "consumer_resume_implementation_handoff",
        "design_reviews.ok: true",
    ),
    "references/release-readiness-checklist.md": (
        "make artifact-smoke",
        "python3 scripts/smoke_workflow_pack_artifact.py --json",
        "python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json",
        "unpacked artifact",
        "fresh_target_init.ok: true",
        "consumer_bootstrap_one_command.ok: true",
        "consumer_bootstrap_one_command.repository_git_initialized: true",
        "consumer_bootstrap_product_conversion.ok: true",
        "design_reviews.ok: true",
        "consumer_bootstrap_implementation_routing.ok: true",
        "consumer_resume_implementation_handoff.ok: true",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "make artifact-smoke",
        "python3 scripts/smoke_workflow_pack_artifact.py --json",
        "python3 scripts/smoke_workflow_pack_artifact.py --archive dist/docs-as-code-workflow-pack.tar.gz --json",
        "fresh target folder",
        "consumer_bootstrap_one_command.ok: true",
        "consumer_bootstrap_product_conversion.ok: true",
        "--auto-repair-env --workflow-preset product-structure",
        "--auto-repair-env --workflow-preset design-scaffold",
        "--auto-repair-env --workflow-preset design-routing",
        "--auto-repair-env --workflow-preset implementation-routing",
        "consumer_resume_implementation_handoff",
        "design_reviews.ok: true",
    ),
}
RELEASE_READINESS_PATH = "scripts/release_readiness.py"
RELEASE_READINESS_REQUIRED_PHRASES = (
    "run_release_readiness",
    "release_ready",
    "criteria",
    "diff_check",
    "cached_diff_check",
    "unit_tests",
    "pack_verification",
    "environment_inventory",
    "authority_skill_inventory",
    "_authority_skill_inventory_ok",
    '"--repair", "--check"',
    "_env_repair_decision_allows_workflow",
    "repair_decision",
    "continue_workflow",
    "stop_before_workflow",
    "_dry_run_closeout_evidence_ok",
    "_dry_run_implementation_task_package_ok",
    "_dry_run_implementation_runner_ok",
    "_dry_run_stack_acceptance_ok",
    "_artifact_smoke_stack_acceptance_ok",
    "stack_acceptance",
    "implementation_verification",
    "implementation_task_package",
    "implementation_run",
    "_artifact_smoke_consumer_resume_handoff_ok",
    "consumer_resume_implementation_handoff",
    "state_write_observed",
    "routing_ok",
    "route_ready",
    "runner_contract_valid",
    "all_current_results_passing",
    "_dry_run_product_dispositions_ok",
    "_dry_run_design_reviews_ok",
    "_dry_run_reliability_review_ok",
    "_dry_run_migration_review_ok",
    "_dry_run_target_local_make_coverage_ok",
    "_artifact_smoke_fresh_target_init_ok",
    "_artifact_smoke_product_dispositions_ok",
    "_artifact_smoke_design_reviews_ok",
    "_artifact_smoke_reliability_review_ok",
    "_artifact_smoke_migration_review_ok",
    "_artifact_smoke_consumer_bootstrap_ok",
    "_artifact_smoke_work_package_ok",
    "_artifact_smoke_consumer_design_scaffold_ok",
    "_artifact_smoke_consumer_design_routing_ok",
    "_artifact_smoke_design_authoring_summary_ok",
    "_artifact_smoke_consumer_implementation_routing_ok",
    "fresh_target_init",
    "consumer_bootstrap_product_structure",
    "consumer_bootstrap_design_scaffold",
    "consumer_bootstrap_design_routing",
    "consumer_bootstrap_implementation_routing",
    "target_local_verify_ok",
    "target_local_status_ok",
    "target_local_workflow_plan_ok",
    "target_local_work_package_ok",
    "work_package",
    "skill_ready",
    "missing_local_workflow_skills",
    "missing_authority_routing_skills",
    "next_action_kind",
    "runtime_manifest",
    "workflow_pack_snapshot",
    "product_source_manifest",
    "design_reviews",
    "active_count",
    "missing_count",
    "stale_count",
    "work_package_complete",
    "product-structure",
    "design-scaffold",
    "design-routing",
    "implementation-routing",
    "product_structure_apply_ok",
    "design_scaffold_apply_ok",
    "design_authoring_preview_ok",
    "implementation_readiness_preview_ok",
    "readiness_previewed",
    "readiness_ok",
    "implementation_ready",
    "readiness_blocker_count",
    "readiness_blocker_codes",
    "readiness_next_blocker",
    "readiness_next_repair_action",
    "advance_previewed",
    "advance_ready",
    "advance_apply_skipped",
    "advance_apply_skip_code",
    "advance_apply_blocked_by",
    "implementation_run_preview_ok",
    "run_previewed",
    "run_preview_skipped",
    "run_preview_skip_code",
    "run_preview_blocked_by",
    "run_required_advance_applied",
    "run_handoff_ready",
    "run_status",
    "run_task_id",
    "run_snapshot",
    "run_next_action",
    "blocked_by_placeholders",
    "queue_count",
    "DESIGN_AUTHORING_QUEUE_IDS",
    "queue_summaries",
    "authoring_summary",
    "authoring_summary_ok",
    "queue_status_counts",
    "next_queue_id",
    "next_active_work",
    "active_work",
    "missing_queue_ids",
    "post_verify_blocked_by_placeholders",
    "target_local_make_coverage",
    "make_verify_governance",
    "make_verify_check",
    "make_governance_status",
    "make_workflow_plan_initialized",
    "make_work_package_initialized",
    "make_workflow_plan_product_structuring",
    "make_work_package_product_structuring",
    "make_workflow_plan_design_derivation",
    "make_work_package_design_derivation",
    "make_work_package_design_complete",
    "make_workflow_plan_implementation",
    "make_work_package_implementation",
    "make_work_package_complete_after_runtime_refresh",
    "make_product_plan",
    "make_design_plan",
    "make_implementation_plan",
    "make_implementation_run_check",
    "make_check_env",
    "make_repair_env_check",
    "fresh_target_dry_run",
    "multi_acceptance_dry_run",
    "multi-acceptance-dry-run",
    "tests/fixtures/product-docs/field-service-ops.md",
    "acceptance_id_count",
    "final_phase",
    '"implementation"',
    "implementation_closeout",
    "implementation_start",
    "blocked_without_evidence",
    "ready_with_evidence",
    "source_pack_export_check",
    "source-pack-export-check",
    "would_write",
    "would_archive",
    "source_pack_export",
    "release_artifact_smoke",
    "_artifact_smoke_product_conversion_ok",
    "consumer_bootstrap_product_conversion",
    "release-artifact-smoke",
    "_artifact_smoke_bootstrap_authority_inventory_ok",
    "_artifact_smoke_bootstrap_env_auto_repair_ok",
    "stop_before_workflow",
    "can_continue",
    "can_auto_apply",
    "requires_approval",
    "manual_repair_required",
    "runnable_action_ids",
    "approval_action_ids",
    "manual_action_ids",
    "next_step",
    "final_env_check_ok",
    "final_missing_required",
    "--archive",
    "provided-archive",
    "archive_source",
    "export_archive_sha256",
    "export_manifest_sha256",
    "--skip-tests",
    "scripts/verify_pack.py",
    "scripts/check_env.py",
    "scripts/dry_run_workflow.py",
    "scripts/export_workflow_pack.py",
    "scripts/smoke_workflow_pack_artifact.py",
)
RELEASE_READINESS_DOC_REQUIREMENTS = {
    "README.md": (
        ".github/workflows/ci.yml",
        "make release-check",
        "python3 scripts/release_readiness.py --json",
        "references/release-readiness-checklist.md",
        "release readiness gate",
    ),
    "workflows/00-overview.md": (
        "make release-check",
        "python3 scripts/release_readiness.py --json",
        "references/release-readiness-checklist.md",
    ),
    "workflows/05-verification-and-drift-control.md": (
        "make release-check",
        "python3 scripts/release_readiness.py --json",
        "references/release-readiness-checklist.md",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "make release-check",
        "python3 scripts/release_readiness.py --json",
        "references/release-readiness-checklist.md",
    ),
    "references/release-readiness-checklist.md": (
        ".github/workflows/ci.yml",
        "make test",
        "python3 scripts/verify_pack.py --json",
        "python3 scripts/check_env.py --json",
        "--auto-repair-env --workflow-preset product-structure",
        "--auto-repair-env --workflow-preset design-scaffold",
        "--auto-repair-env --workflow-preset design-routing",
        "--auto-repair-env --workflow-preset implementation-routing",
        "env_auto_repair",
        "authority_skill_inventory",
        "consumer_bootstrap_product_structure.ok: true",
        "consumer_bootstrap_design_scaffold.ok: true",
        "consumer_bootstrap_design_routing.ok: true",
        "consumer_bootstrap_implementation_routing.ok: true",
        "consumer_resume_implementation_handoff.ok: true",
        "design_reviews.ok: true",
        "readiness_blocker_codes",
        "readiness_next_repair_action",
        "advance_preview_not_ready",
        "readiness_preview_not_ready",
        "start_preview_not_ready",
        "start_apply_not_applied",
        "closeout_preview_not_ready",
    ),
}
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
    "repair_commands",
    "repair_actions",
    "manual_repairs",
    "needs_escalation",
    "repair_execution",
    "repair_decision",
    "stop_before_workflow",
    "runnable_action_ids",
    "approval_action_ids",
    "manual_action_ids",
    "can_auto_apply",
    "install_attempted",
    "install_failed",
    "post_repair_missing_required",
    "post_repair_missing_recommended",
    "applied_but_unresolved",
    "next_step",
)
RUNTIME_REFRESH_DOC_REQUIREMENTS = {
    "README.md": (
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
        "docs/agent-workflow/runtime-manifest.json",
        "docs/agent-workflow/workflow-pack/",
        "would_refresh",
        "would_remove",
        "without rewriting product, design, planning, or implementation documents",
    ),
    "workflows/00-overview.md": (
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
        "without rewriting product or design documents",
        "no-write plan",
        "local_commands",
        "next_actions",
        "docs/agent-workflow/workflow-pack/",
    ),
    "workflows/01-empty-repo-initialization.md": (
        "docs/agent-workflow/runtime-manifest.json",
        "docs/agent-workflow/workflow-pack/",
        "trusted source workflow-pack checkout",
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
    ),
    "workflows/05-verification-and-drift-control.md": (
        "target-local runtime or workflow-pack snapshot drift",
        "trusted source workflow-pack checkout",
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
        "no-write repair plan",
        "local_commands",
        "next_actions",
    ),
    "references/runtime-strategy.md": (
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
        "docs/agent-workflow/runtime-manifest.json",
        "docs/agent-workflow/workflow-pack/",
        "does not rewrite product, design, planning, or implementation documents",
        "would_refresh",
        "would_remove",
        "leaving target files and `.governance/state.json` unchanged",
        "local_commands",
        "next_actions",
        "environment_readiness",
        "project-environment.json",
        "required_tools[]",
        "No package name, source, or install command is inferred",
    ),
    "skills/initializing-governance-repo/SKILL.md": (
        "trusted source workflow-pack checkout",
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
        "docs/agent-workflow/workflow-pack/manifest.json",
        "local workflow-pack snapshot",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "bin/governance runtime refresh <target> --check --json",
        "bin/governance runtime refresh <target> --json",
        "runtime_manifest_*",
        "workflow_pack_manifest_*",
        "trusted source workflow-pack checkout",
        "no-write plan",
        "local_commands",
        "next_actions",
    ),
}
RUNTIME_REFRESH_TEST_PATH = "tests/test_governance_cli.py"
RUNTIME_REFRESH_TEST_REQUIRED_PHRASES = (
    "test_runtime_refresh_repairs_target_runtime_and_workflow_pack",
    "runtime_local_commands",
    '"verify-check"',
    '"workflow-plan"',
    "runtime_preflight",
    "advance-product-structuring-check",
    "_agent_env()",
)
PRODUCT_ARCHIVE_DOC_PATHS = (
    "workflows/02-product-document-archiving.md",
    "skills/archiving-product-document/SKILL.md",
)
PRODUCT_CONVERSION_SOURCE_PATH = "scripts/product_conversion.py"
PRODUCT_CONVERSION_SOURCE_REQUIRED_PHRASES = (
    "check_product_conversion",
    "convert_product_document",
    "run_bounded_command",
    "CONVERSION_REPORT_SCHEMA_VERSION",
    "MAX_CONVERTED_BYTES",
    "CONVERSION_TIMEOUT_SECONDS",
    "required conversion tool is missing: pandoc",
    "required conversion tool is missing: pdftotext",
    "pdftotext-pdf-to-utf8-text",
    "pending_review",
    "reviewed_prd_sha256",
    "plan_conversion_review",
)
PRODUCT_ARCHIVE_REQUIRED_PHRASES = (
    "source-manifest.json",
    "SHA-256",
    "can_derive_design",
    "product mark-ready",
    "product convert",
    "conversion-report.json",
    "--require-tool pandoc",
    "--require-tool pdftotext",
    "pending_review",
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
    "product plan",
    "source_documents",
    "available_chapters",
    "prd_headings",
    "suggested_mappings",
    "required_decisions",
    "chapter_dispositions",
    "stale_chapter_dispositions",
    "disposition_summary",
    "manual_authoring_tasks",
    "manual_authoring_summary",
    "status: decision_required",
    "skill_requirements",
    "authority_skill_requirements",
    "decision_policy",
    "do_not_guess_product_meaning",
    "execution",
    "required_sections",
    "required_links",
    "required_evidence",
    "required_evidence[].status",
    "required_evidence_status_counts",
    "non_satisfied_required_evidence_count",
    "evidence_repair_actions",
    "evidence_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "PRD source support",
    "product-meta.md",
    "A-NNN",
    "open_decisions",
    "steps",
    "scaffold product",
    "would_create",
    "would_skip",
    "would_index",
    "product structure",
    "product disposition",
    "author-required",
    "omit-unsupported",
    "chapter-dispositions.json",
    "PRD SHA-256",
    "key=PRD Heading",
    "would_update",
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
PRODUCT_DISPOSITION_SOURCE_PATH = "scripts/product_dispositions.py"
PRODUCT_DISPOSITION_SOURCE_REQUIRED_PHRASES = (
    "ProductDispositionResult",
    "check_product_disposition",
    "record_product_disposition",
    "build_product_disposition_inventory",
    "PRODUCT_DISPOSITION_SCHEMA_VERSION",
    "PRODUCT_DISPOSITION_DECISION_POLICY",
    "PRODUCT_DISPOSITION_REVIEW_SCOPE",
    "author-required",
    "omit-unsupported",
    "NON_OMITTABLE_PRODUCT_CHAPTERS",
    "prd_sha256",
    "review_scope",
    "_write_atomic_bytes",
)
PRODUCT_DISPOSITION_DOC_REQUIREMENTS = {
    "README.md": (
        "product disposition",
        "author-required",
        "omit-unsupported",
        "docs/product/core/chapter-dispositions.json",
        "PRD SHA-256",
        "review scope",
    ),
    "workflows/00-overview.md": (
        "product disposition",
        "author-required",
        "omit-unsupported",
        "docs/product/core/chapter-dispositions.json",
        "PRD SHA-256",
        "review_scope",
    ),
    "workflows/03-product-structuring.md": (
        "next_action.kind",
        "decide-product-chapter",
        "product disposition",
        "author-required",
        "omit-unsupported",
        "chapter-dispositions.json",
        "SHA-256",
        "stale",
    ),
    "skills/structuring-product-requirements/SKILL.md": (
        "next_action.kind: decide-product-chapter",
        "product disposition",
        "author-required",
        "omit-unsupported",
        "chapter-dispositions.json",
        "PRD SHA-256",
        "review_scope",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "decide-product-chapter",
        "product disposition",
        "author-required",
        "omit-unsupported",
        "stale dispositions",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "product_chapter_disposition_invalid",
        "product_chapter_disposition_stale",
        "product disposition --check",
        "chapter-dispositions.json",
    ),
    "references/product-requirements-checklist.md": (
        "Chapter Dispositions",
        "product disposition --check",
        "author-required",
        "omit-unsupported",
        "chapter-dispositions.json",
        "canonical PRD SHA-256",
        "review_scope",
    ),
}
DESIGN_REVIEW_SOURCE_PATH = "scripts/design_reviews.py"
DESIGN_REVIEW_SOURCE_REQUIRED_PHRASES = (
    "DesignReviewResult",
    "check_design_review",
    "record_design_review",
    "apply_design_reviews",
    "build_design_review_inventory",
    "design_review_enforcement_ready",
    "DESIGN_REVIEWS_REL",
    "DESIGN_REVIEW_SCHEMA_VERSION",
    "DESIGN_REVIEW_DECISION_POLICY",
    "DESIGN_REVIEW_ALLOWED_PHASES",
    "DESIGN_REVIEW_TRACK_SPECS",
    "DESIGN_REVIEW_SCOPE",
    "approved",
    "not-applicable",
    "primary_authority_skill",
    "source_snapshots",
    "evidence_snapshots",
    "authority_skill",
    "sha256",
    "IMPLEMENTATION_MUTABLE_TABLE_COLUMNS",
    "IMPLEMENTATION_EXECUTION_LOG_REVIEW_EVIDENCE",
    "semantic_sha256",
    "_safe_relative_path",
    "_write_atomic_bytes",
)
DESIGN_REVIEW_DOC_REQUIREMENTS = {
    "README.md": (
        "author-design-documents",
        "record-design-review",
        "docs/decisions/design-reviews.json",
        "authority `SKILL.md` SHA-256",
        "Missing, malformed, orphaned, or stale reviews block implementation",
        "roadmap/task-board `Status`",
        "implementation phase",
    ),
    "workflows/00-overview.md": (
        "document-first, integration-second, authority-review-last",
        "docs/decisions/design-reviews.json",
        "source/evidence hashes",
        "primary authority skill hash",
        "missing, malformed, orphaned, or stale reviews block implementation",
    ),
    "workflows/04-design-derivation.md": (
        "record-design-review",
        "references/design-review-checklist.md",
        "docs/decisions/design-reviews.json",
        "`not-applicable`",
        "requires `--evidence docs/decisions/NNN-<slug>.md`",
        "semantic hashes",
        "During implementation",
    ),
    "skills/designing-system-architecture/SKILL.md": (
        "design review --track architecture",
        "references/design-review-checklist.md",
        "`senior-architect` skill SHA-256",
    ),
    "skills/designing-backend-modules/SKILL.md": (
        "design review --track backend-modules",
        "references/design-review-checklist.md",
        "`senior-backend` skill SHA-256",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "record-design-review",
        "references/design-review-checklist.md",
        "docs/decisions/design-reviews.json",
        "missing, malformed, orphaned, or stale",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "design review --check",
        "source/evidence snapshots",
        "design_review_invalid",
        "design_review_missing",
        "design_review_orphan",
        "design_review_stale",
        "semantic planning changes",
        "implementation phase",
    ),
    "references/design-review-checklist.md": (
        "docs/decisions/design-reviews.json",
        "documents[].status",
        "required_links[].status",
        "authority skill name and SHA-256",
        "source and evidence snapshots",
        "semantic_sha256",
        "`not-applicable`",
        "`--check`",
    ),
    "references/architecture-quality-checklist.md": (
        "Authority Review Evidence",
        "`senior-architect`",
        "docs/decisions/design-reviews.json",
        "design review --check",
    ),
    "references/backend-design-checklist.md": (
        "Authority Review Evidence",
        "`senior-backend`",
        "docs/decisions/design-reviews.json",
        "design review --check",
    ),
    "references/workflow-routing-checklist.md": (
        "work_stage",
        "record-design-review",
        "design review --check",
        "docs/decisions/design-reviews.json",
    ),
}
API_REVIEW_SOURCE_PATH = "scripts/api_review_evidence.py"
API_REVIEW_SOURCE_REQUIRED_PHRASES = (
    "ApiReviewEvidenceResult",
    "check_api_review_evidence",
    "record_api_review_evidence",
    "build_api_review_evidence_inventory",
    "build_openapi_contract_inventory",
    "API_OPENAPI_REL",
    "API_BASELINE_REL",
    "API_REVIEW_EVIDENCE_REL",
    "API_REVIEW_AUTHORITY_SKILL",
    "API_REVIEW_TOOL_FILES",
    "api_linter.py",
    "breaking_change_detector.py",
    "api_scorecard.py",
    "sys.executable",
    "subprocess.run",
    "TemporaryDirectory",
    "--exit-on-breaking",
    "_write_outputs_atomically",
)
API_REVIEW_DOC_REQUIREMENTS = {
    "README.md": (
        "design api-review",
        "docs/api/openapi.json",
        "work_stage: machine-review",
        "run-api-review",
        "grade B",
    ),
    "workflows/00-overview.md": (
        "design api-review",
        "API-machine-review-fourth",
        "run-api-review",
        "zero lint errors/warnings",
    ),
    "workflows/04-design-derivation.md": (
        "design api-review",
        "work_stage: machine-review",
        "api_linter.py",
        "breaking_change_detector.py",
        "api_scorecard.py",
        "api_review_evidence_stale",
    ),
    "skills/designing-api-contracts/SKILL.md": (
        "design api-review",
        "docs/api/openapi.json",
        "zero errors and zero warnings",
        "breaking or potentially breaking changes",
        "grade B or better",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "machine-review",
        "run-api-review",
        "api_review_evidence_stale",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "api_review.ok: true",
        "api_review_evidence_missing",
        "api_review_evidence_invalid",
        "api_review_evidence_stale",
    ),
    "references/api-design-checklist.md": (
        "Machine Review Evidence",
        "design api-review",
        "zero errors and zero warnings",
        "grade B or better",
    ),
    "references/design-review-checklist.md": (
        "API Machine Review",
        "work_stage: machine-review",
        "api_linter.py",
        "docs/api/reviews/review-evidence.json",
    ),
    "references/workflow-routing-checklist.md": (
        "machine-review",
        "run-api-review",
        "design api-review --reviewed --min-grade B --check",
    ),
}
THREAT_REVIEW_SOURCE_PATH = "scripts/threat_review_evidence.py"
THREAT_REVIEW_SOURCE_REQUIRED_PHRASES = (
    "ThreatReviewEvidenceResult",
    "check_threat_review_evidence",
    "record_threat_review_evidence",
    "build_threat_review_evidence_inventory",
    "THREAT_SCOPE_REL",
    "THREAT_MITIGATIONS_REL",
    "THREAT_REPORT_REL",
    "THREAT_REVIEW_EVIDENCE_REL",
    "THREAT_REVIEW_AUTHORITY_SKILL",
    "THREAT_REVIEW_DREAD_THRESHOLD = 7.0",
    "threat_modeler.py",
    "sys.executable",
    "subprocess.run",
    "TemporaryDirectory",
    "_write_outputs_atomically",
)
THREAT_REVIEW_DOC_REQUIREMENTS = {
    "README.md": (
        "design threat-review",
        "docs/architecture/threat-model/scope.json",
        "work_stage: threat-review",
        "run-threat-review",
        "DREAD >= 7",
    ),
    "workflows/00-overview.md": (
        "design threat-review",
        "architecture-threat-review-third",
        "run-threat-review",
        "DREAD >= 7",
    ),
    "workflows/04-design-derivation.md": (
        "design threat-review",
        "threat_modeler.py",
        "threat_review_evidence_stale",
    ),
    "skills/designing-system-architecture/SKILL.md": (
        "design threat-review",
        "docs/architecture/threat-model/scope.json",
        "threat_modeler.py",
        "DREAD >= 7",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "threat-review",
        "run-threat-review",
        "threat_review_evidence_stale",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "threat_review_evidence_missing",
        "threat_review_evidence_invalid",
        "threat_review_evidence_stale",
    ),
    "references/architecture-quality-checklist.md": (
        "Threat Review Evidence",
        "design threat-review",
        "DREAD >= 7",
    ),
    "references/design-review-checklist.md": (
        "Architecture Threat Review",
        "work_stage: threat-review",
        "threat_modeler.py",
        "docs/architecture/threat-model/review-evidence.json",
    ),
    "references/workflow-routing-checklist.md": (
        "run-threat-review",
        "design threat-review",
    ),
}
RELIABILITY_REVIEW_SOURCE_PATH = "scripts/reliability_review_evidence.py"
RELIABILITY_REVIEW_SOURCE_REQUIRED_PHRASES = (
    "ReliabilityReviewEvidenceResult",
    "check_reliability_review_evidence",
    "record_reliability_review_evidence",
    "build_reliability_review_evidence_inventory",
    "RELIABILITY_SCOPE_REL",
    "RELIABILITY_EVIDENCE_REL",
    "RELIABILITY_AUTHORITY_SKILL",
    "RELIABILITY_TOOL_FILES",
    "RELIABILITY_REVIEW_ADAPTER",
    "slo_designer.py",
    "error_budget_calculator.py",
    "slo_review.py",
    "sys.executable",
    "subprocess.run",
    "TemporaryDirectory",
    "_write_outputs_atomically",
)
RELIABILITY_REVIEW_DOC_REQUIREMENTS = {
    "README.md": (
        "design reliability-review",
        "docs/backend/reliability/slo-scope.json",
        "work_stage: reliability-review",
        "run-reliability-review",
        "not-applicable",
    ),
    "workflows/00-overview.md": (
        "design reliability-review",
        "backend-reliability-review-fifth",
        "run-reliability-review",
        "not-applicable",
    ),
    "workflows/04-design-derivation.md": (
        "design reliability-review",
        "slo_designer.py",
        "error_budget_calculator.py",
        "slo_review.py",
        "reliability_review_evidence_stale",
    ),
    "skills/designing-backend-modules/SKILL.md": (
        "design reliability-review",
        "docs/backend/reliability/slo-scope.json",
        "slo-architect",
        "not-applicable",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "reliability-review",
        "run-reliability-review",
        "reliability_review_evidence_stale",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "reliability_review_evidence_missing",
        "reliability_review_evidence_invalid",
        "reliability_review_evidence_stale",
    ),
    "references/backend-operability-checklist.md": (
        "Reliability Review Evidence",
        "design reliability-review",
        "not-applicable",
    ),
    "references/design-review-checklist.md": (
        "Backend Reliability Review",
        "work_stage: reliability-review",
        "docs/backend/reliability/review-evidence.json",
    ),
    "references/workflow-routing-checklist.md": (
        "run-reliability-review",
        "design reliability-review",
    ),
}
MIGRATION_REVIEW_SOURCE_PATH = "scripts/migration_review_evidence.py"
MIGRATION_REVIEW_SOURCE_REQUIRED_PHRASES = (
    "MigrationReviewEvidenceResult",
    "check_migration_review_evidence",
    "record_migration_review_evidence",
    "build_migration_review_evidence_inventory",
    "MIGRATION_SCOPE_REL",
    "MIGRATION_EVIDENCE_REL",
    "MIGRATION_AUTHORITY_SKILLS",
    "MIGRATION_TOOL_FILES",
    "migration_planner.py",
    "compatibility_checker.py",
    "rollback_generator.py",
    "accepted_with_mitigations",
    "_compatibility_returncode_errors",
    "_persisted_report_errors",
    "data_recovery_plan",
    "communication_templates",
    "validation_checklist",
    "sys.executable",
    "subprocess.run",
    "TemporaryDirectory",
    "_write_outputs_atomically",
)
MIGRATION_REVIEW_DOC_REQUIREMENTS = {
    "README.md": (
        "design migration-review",
        "docs/backend/migrations/review-scope.json",
        "work_stage: migration-review",
        "run-migration-review",
        "accepted_with_mitigations",
    ),
    "workflows/00-overview.md": (
        "design migration-review",
        "data-model-migration-review-sixth",
        "run-migration-review",
        "accepted_with_mitigations",
    ),
    "workflows/04-design-derivation.md": (
        "design migration-review",
        "migration_planner.py",
        "compatibility_checker.py",
        "rollback_generator.py",
        "migration_review_evidence_stale",
    ),
    "skills/designing-data-models/SKILL.md": (
        "design migration-review",
        "database-schema-designer",
        "migration-architect",
        "compatibility-acceptances.json",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "migration-review",
        "run-migration-review",
        "migration_review_evidence_stale",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "migration_review_evidence_missing",
        "migration_review_evidence_invalid",
        "migration_review_evidence_stale",
    ),
    "references/data-model-design-checklist.md": (
        "Migration Review Evidence",
        "design migration-review",
        "accepted_with_mitigations",
    ),
    "references/design-review-checklist.md": (
        "Data-Model Migration Review",
        "work_stage: migration-review",
        "docs/backend/migrations/review-evidence.json",
    ),
    "references/workflow-routing-checklist.md": (
        "run-migration-review",
        "design migration-review",
    ),
}
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
DESIGN_PLAN_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/using-governance-workflow/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
DESIGN_PLAN_REQUIRED_PHRASES = (
    "design plan",
    "source_documents",
    "tracks",
    "sequence",
    "skills",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "available_in_workflow_pack",
    "missing_policy",
    "primary_skill",
    "primary_specialist_skill",
    "references",
    "documents",
    "blockers",
    "required_decisions",
    "docs/decisions/design-reviews.json",
    "steps",
    "local_commands",
    "next_actions",
)
DESIGN_PLAN_SOURCE_PATH = "scripts/design_plan.py"
DESIGN_PLAN_SOURCE_REQUIRED_PHRASES = (
    "DESIGN_TRACKS",
    "DesignTrack",
    "AUTHORITY_ROUTING_SPECIALIST_SKILLS",
    "AUTHORITY_ROUTING_SKILL_MISSING_POLICY",
    "load_from_agent_environment_or_stop_before_guessing",
    "_skill_requirement_fields",
    "_skill_loading_plan",
    "specialist_skills",
    "primary_specialist_skill",
    "skill_requirements",
    "authority_skill_requirements",
    "senior-architect",
    "api-design-reviewer",
    "senior-backend",
    "database-designer",
    "database-schema-designer",
    "migration-architect",
    "observability-designer",
    "senior-security",
    "senior-frontend",
    "a11y-audit",
    "performance-profiler",
    "senior-qa",
    "playwright-pro",
    "security-pen-testing",
    "senior-fullstack",
    "ci-cd-pipeline-builder",
    "tech-debt-tracker",
    "tech-stack-evaluator",
    "slo-architect",
    "DESIGN_REVIEW_TRACK_SPECS",
    "DESIGN_AUTHORING_PHASES",
    "build_design_review_inventory",
    "design_review_enforcement_ready",
    "design_review_summary",
    "review_summary",
    "review_status",
)
IMPLEMENTATION_RUN_SOURCE_PATH = "scripts/implementation_run.py"
IMPLEMENTATION_VERIFY_SOURCE_PATH = "scripts/implementation_verify.py"
IMPLEMENTATION_REVIEW_SOURCE_PATH = "scripts/implementation_review_evidence.py"
PROJECT_ENVIRONMENT_SOURCE_PATH = "scripts/project_environment.py"
BOUNDED_PROCESS_SOURCE_PATH = "scripts/bounded_process.py"
BOUNDED_PROCESS_SOURCE_REQUIRED_PHRASES = (
    "run_bounded_command",
    "subprocess.Popen",
    "shell=False",
    "start_new_session",
    "timeout_seconds",
    "max_output_bytes",
    "stdout_truncated",
    "stderr_truncated",
    "output_redacted",
    "_redact_sensitive_output",
    "SENSITIVE_OUTPUT_PATTERNS",
    "_kill_process_group",
)
PROJECT_ENVIRONMENT_SOURCE_REQUIRED_PHRASES = (
    "PROJECT_ENVIRONMENT_REL",
    "PROJECT_ENVIRONMENT_SCHEMA_VERSION",
    "APPROVED_VERSION_PROBE_ARGS =",
    "load_project_environment_contract",
    "validate_project_environment_contract",
    "project_environment_by_id",
    "parse_numeric_version",
    "extract_probed_version",
    "version_satisfies_requirement",
    "ProjectEnvironmentRegistrationResult",
    "build_project_environment_plan",
    "check_project_environment_tool_registration",
    "register_project_environment_tool",
    "ProjectEnvironmentRepairResult",
    "check_project_environment_tool_repair",
    "repair_project_environment_tool",
    "reviewed-command",
    "--approved",
    "PROJECT_ENVIRONMENT_REPAIR_EVIDENCE_REL",
    "load_project_environment_repair_evidence",
    "validate_project_environment_repair_evidence",
    "pending",
    "inspect_project_environment_tool",
    "run_bounded_command",
    "PROJECT_ENVIRONMENT_LOCK_REL",
    "ProjectEnvironmentLockUnavailable",
    "_project_environment_lock",
    "fcntl.flock",
    "already-registered",
    "rerun with --replace",
    "_write_project_environment_contract",
    "temp_path.replace(path)",
    "governance-env",
    "manual",
    "official-url",
    "review_evidence",
    "duplicate key",
)
IMPLEMENTATION_VERIFY_SOURCE_REQUIRED_PHRASES = (
    "build_implementation_verify",
    "run_implementation_verify",
    "EVIDENCE_OUTPUT_PATHS",
    "IMPLEMENTATION_EVIDENCE_REL",
    "command_approval_not_allowed",
    "command_writes_state_requires_opt_in",
    "command_environment_ready",
    "_command_environment_readiness",
    "run_governance_environment_repair_preflight",
    "register_project_environment_tool",
    "repair_preflight_command",
    "argv0_and_declared_environment_tools",
    "version_constraints_enforced",
    "package_source_inferred",
    "load_project_environment_contract",
    "environment_probe_executed",
    "allow_probes=governance_report.ok",
    "required_tools",
    "_project_environment_tool_readiness",
    "complete_manual_environment_repairs",
    "run_reviewed_project_environment_repair_preflight",
    "project-env",
    "repair",
    "verification_run_id_unique",
    "IMPLEMENTATION_VERIFY_LOCK_REL",
    "timeout_seconds",
    "max_output_bytes",
    "stdout_truncated",
    "stderr_truncated",
    "output_redacted",
    "_upsert_verification_log",
    "_update_task_evidence_link",
    "_write_outputs_atomically",
    "post-write governance verification failed",
)
IMPLEMENTATION_RUN_SOURCE_REQUIRED_PHRASES = (
    "run_implementation_task",
    "DECISION_POLICY",
    "IMPLEMENTATION_RUN_LOCK_REL",
    "_implementation_run_lock",
    "build_workflow_resume",
    "apply_implementation_start",
    "claim_task_then_edit_implementation_before_verification",
    "_verification_preflights",
    "_all_preflights_ready",
    "_execute_verifications",
    "_attempt_environment_repairs",
    "can_auto_apply",
    "approve_repairs",
    "apply_implementation_closeout",
    "run_bounded_command",
)
IMPLEMENTATION_REVIEW_SOURCE_REQUIRED_PHRASES = (
    "CODE_REVIEW_EVIDENCE_REL",
    "IMPLEMENTATION_BASELINES_REL",
    "CODE_REVIEW_AUTHORITY_SKILL",
    "build_implementation_baseline_capture",
    "capture_implementation_baseline",
    "build_implementation_review",
    "record_implementation_review",
    "IMPLEMENTATION_REVIEW_LOCK_REL",
    "_implementation_review_lock",
    "fcntl.flock",
    "git-ls-files",
    "_build_change_set",
    "provenance_ready",
    "_verification_evidence",
    "_task_fingerprint",
    "_review_status",
    "NamedTemporaryFile",
    "os.fsync",
    ".governance/code-review-reports/",
    "reviewed",
)
IMPLEMENTATION_RUN_DOC_REQUIREMENTS = {
    "README.md": (
        "implementation run <target> --check --json",
        "make implementation-run-check",
        "--apply-start",
        "--execute",
        "--closeout",
        "--approve-repairs",
    ),
    "workflows/00-overview.md": (
        "implementation run --check",
        "status: implementation_required",
        "closeout_applied: true",
    ),
    "workflows/06-implementation-execution.md": (
        "implementation run <target> --task TASK-NNN --check --json",
        "--apply-start --expect-snapshot",
        "verification_summary.all_ready: true",
        "--approve-repairs",
        "status: complete",
    ),
    "skills/executing-implementation-task/SKILL.md": (
        "implementation run . --task TASK-NNN --check --json",
        "--apply-start --expect-snapshot",
        "implementation_required",
        "executed: false",
        "--approve-repairs",
        "closeout_applied: true",
    ),
    "references/implementation-execution-checklist.md": (
        "implementation run --check",
        "--apply-start",
        "ready_count == required_count",
        "--approve-repairs",
        "status: complete",
    ),
    "templates/docs/agent-workflow/command-contract.md": (
        "implementation-run-check",
        '`["bin/governance", "implementation", "run", ".", "--check", "--json"]`',
        "Use `implementation run --check`",
    ),
}
IMPLEMENTATION_REVIEW_DOC_REQUIREMENTS = {
    "README.md": (
        "implementation review <target> --task TASK-NNN --json",
        ".governance/implementation-change-baselines.json",
        "docs/development/05-code-review-evidence.json",
        "code-reviewer",
        "--report",
        "--reviewed",
        "code_review_evidence_current",
    ),
    "workflows/00-overview.md": (
        "implementation review --task TASK-NNN --json",
        "complete task change set",
        "code-reviewer",
        "code_review_evidence_current",
    ),
    "workflows/06-implementation-execution.md": (
        ".governance/implementation-change-baselines.json",
        "implementation review <target> --task TASK-NNN --json",
        ".governance/code-review-reports/TASK-NNN.json",
        "--reviewed --check",
        "docs/development/05-code-review-evidence.json",
        "code_review_evidence_current",
    ),
    "skills/executing-implementation-task/SKILL.md": (
        "code-reviewer",
        "implementation review . --task TASK-NNN --json",
        ".governance/code-review-reports/TASK-NNN.json",
        "--reviewed --check",
        "code_review_evidence_current",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "code-reviewer",
        "code_review_required",
        "implementation review",
    ),
    "references/implementation-execution-checklist.md": (
        "immutable Git change baseline",
        "complete task change set",
        "code-reviewer",
        "code_review_evidence_current",
    ),
    "templates/docs/agent-workflow/task-handoff.md": (
        "Code Review Record",
        "docs/development/05-code-review-evidence.json",
        "code-reviewer",
    ),
}
IMPLEMENTATION_VERIFY_DOC_REQUIREMENTS = {
    "README.md": (
        "implementation verify <target> --task TASK-NNN --command command-name --check --json",
        "docs/development/04-implementation-evidence.md",
        "one current verification-log row per `(Task, Command)`",
        "evidence_summary.all_verification_results_passing",
        "environment_readiness",
        "project-environment.json",
        "required_tools[]",
        "project-env register --reviewed --check",
        "project-env repair --tool-id <tool-id> --check --json",
        ".governance/project-environment-repairs.json",
        "command:<registered-name>",
        "verification_command_names",
        "required_verification_commands_passing",
    ),
    "workflows/00-overview.md": (
        "implementation verify --task TASK-NNN --command command-name --check --json",
        "without a shell",
        "all_verification_results_passing",
        "environment_readiness",
        "project-environment.json",
        "version probes",
        "reviewed-command",
        "project-env repair --check",
        "command:<registered-name>",
        "verification_command_names",
        "required_verification_commands_passing",
    ),
    "workflows/05-verification-and-drift-control.md": (
        "verification-log rows are unique by `(Task, Command)`",
        "one passing row cannot mask another failing row",
    ),
    "workflows/06-implementation-execution.md": (
        "implementation verify <target> --task TASK-NNN --command command-name --check --json",
        "`Approval Required: true` are refused",
        "require `--allow-writes`",
        "`--timeout-seconds`",
        "one summary row per `(Task, Command)`",
        "best-effort redaction",
        "environment_readiness",
        "project-environment.json",
        "required_tools",
        "evidence_summary.all_verification_results_passing",
        "project-env register --reviewed --check",
        "project-env repair --check",
        "approval-required apply action",
        "command:<registered-name>",
        "verification_command_names",
        "missing_verification_commands",
        "required_verification_commands_passing",
    ),
    "skills/executing-implementation-task/SKILL.md": (
        "implementation verify . --task TASK-NNN --command command-name --check --json",
        "docs/development/04-implementation-evidence.md",
        "environment_readiness",
        "project-environment.json",
        "required_tools",
        "evidence_summary.all_verification_results_passing",
        "project-env register --reviewed --check",
        "project-env repair --check",
        ".governance/project-environment-repairs.json",
        "command:<registered-name>",
        "verification_command_names",
        "missing_verification_commands",
        "required_verification_commands_passing",
    ),
    "references/implementation-execution-checklist.md": (
        "implementation verify --task TASK-NNN --command command-name --check --json",
        "bounded timeout and bounded stdout/stderr capture",
        "best-effort output redaction",
        "environment_readiness",
        "project-environment.json",
        "version probe",
        "exactly one current summary row per `(Task, Command)`",
        "evidence_summary.all_verification_results_passing",
        "project-env repair --check",
        ".governance/project-environment-repairs.json",
        "command:<registered-name>",
        "verification_commands[]",
        "missing_verification_commands",
        "required_verification_commands_passing",
    ),
    "templates/docs/agent-workflow/command-contract.md": (
        "environment_readiness.ok: true",
        "project-environment.json",
        "instead of guessing installation commands",
        "project-env register --reviewed --check",
        "reviewed-command",
        "project-env repair --tool-id <tool-id> --check",
    ),
    "references/project-environment-contract.md": (
        "Version probes are executable metadata checks",
        "governance-env",
        "manual",
        "review_evidence",
        "five-second timeout",
        "4096-byte output limit",
        "never installs tools",
        "project-env register --reviewed --check --json",
        "--replace",
        "atomic",
        "reviewed-command",
        "shell=False",
        "project-env repair <target> --tool-id <tool-id> --check --json",
        "--approved",
        ".governance/project-environment-repairs.json",
        "pending",
        "coverage_status",
        "configuration_complete",
        "project_runtime_ready",
    ),
    "references/runtime-strategy.md": (
        "project-env plan",
        "project-env register --reviewed --check",
        "idempotent",
        "--replace",
        "reviewed-command",
        "project-env repair --check",
        ".governance/project-environment-repairs.json",
    ),
    "workflows/04-design-derivation.md": (
        "configuring-project-runtime",
        "tech-stack-evaluator",
        "senior-architect",
        "senior-devops",
        "project-env plan",
        "project-env register --reviewed --check",
        "project-env repair --tool-id <tool-id> --check --json",
        "project-runtime-configuration",
        "configuration_complete",
        "project_runtime_ready",
    ),
    "skills/configuring-project-runtime/SKILL.md": (
        "configuring-project-runtime",
        "tech-stack-evaluator",
        "senior-architect",
        "project-env plan",
        "project-env register --reviewed --check",
        "project-env repair <target> --tool-id <tool-id> --check --json",
        "approval-required",
        ".governance/project-environment-repairs.json",
        "--replace",
        "coverage_status",
        "configuration_complete",
        "project_runtime_ready",
    ),
}
WORK_PACKAGE_SOURCE_PATH = "scripts/workflow_plan.py"
WORK_PACKAGE_SOURCE_REQUIRED_PHRASES = (
    "build_work_package",
    "DESIGN_WORK_PACKAGE_BUILDERS",
    "build_authority_skill_inventory",
    "WORKFLOW_PACK_SNAPSHOT_ROOT",
    "_target_read_paths",
    "--skill-root",
    ".agents/skills",
    ".codex/skills",
    "workflow-work-package",
    "package_available",
    "can_start",
    "stop_before_work",
    "work_package",
    "skill_readiness",
    "resolved_requirements",
    "read_order",
    "write_scope",
    "next_action",
    "refresh_command",
    "load-authority-skills",
    "claim-implementation-task",
    "verification_command_names",
    "_implementation_execution_contract",
    "claim_then_execute_all_required_verification_commands_then_closeout",
    "work_stage",
    "author-design-documents",
    "record-design-review",
    "design_review_orphan",
    "project-runtime-configuration",
    "register-project-runtime-tool",
)
WORKFLOW_RESUME_SOURCE_PATH = "scripts/workflow_resume.py"
WORKFLOW_RESUME_SOURCE_REQUIRED_PHRASES = (
    "build_workflow_resume",
    "build_workflow_plan",
    "build_work_package",
    "sha256-canonical-json-v1",
    "execute_exactly_one_selected_action_then_refresh",
    "refresh_after_action",
    "reject_stale_snapshot",
    "never_guess_missing_decisions",
    "expect_snapshot",
    "expected_snapshot_invalid",
    "workflow_snapshot_changed",
    "selected_action",
    "guarded-sequence",
    "run_preflight_then_apply_only_when_preflight_succeeds",
    "continuation_preflight_apply_pair_invalid",
    "action_count",
    "stop_before_action",
    "BASELINE_INPUT_PATHS",
    "_path_evidence",
    "is_symlink",
    "approval_required",
)
WORKFLOW_RESUME_DOC_REQUIREMENTS = {
    "README.md": (
        "workflow resume <target> --json",
        "make workflow-resume",
        "snapshot.id",
        "assert_snapshot_command.argv",
        "status: stale",
        "selected_action",
        "can_continue: true",
        "stop_before_action: false",
        "refresh_command.argv",
        "approval_required",
        "action_count: 0",
        "not a repository lock",
    ),
    "workflows/00-overview.md": (
        "workflow resume . --json",
        "make workflow-resume",
        "snapshot.id",
        "assert_snapshot_command.argv",
        "status: stale",
        "selected_action",
        "refresh_command.argv",
        "action_count: 0",
        "not a repository lock",
    ),
    "workflows/05-verification-and-drift-control.md": (
        "make workflow-resume",
        "snapshot.id",
        "assert_snapshot_command.argv",
        "selected_action",
        "refresh_command.argv",
        "status: stale",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "workflow resume <target> --json",
        "make workflow-resume",
        "snapshot.id",
        "assert_snapshot_command.argv",
        "selected_action",
        "stop_before_action",
        "refresh_command.argv",
        "action_count",
        "not a concurrency lock",
    ),
    "references/workflow-routing-checklist.md": (
        "workflow resume --json",
        "make workflow-resume",
        "snapshot.id",
        "assert_snapshot_command.argv",
        "status: stale",
        "selected_action",
        "can_continue: true",
        "stop_before_action: false",
        "refresh_command.argv",
        "action_count: 0",
        "repository lock",
    ),
    "templates/root/README.md": (
        "make workflow-resume",
        "stale-snapshot guard",
    ),
    "templates/docs/agent-workflow/command-contract.md": (
        "workflow-resume",
        '["bin/governance", "workflow", "resume", ".", "--json"]',
        "stale-snapshot guard",
    ),
}
WORK_PACKAGE_DOC_REQUIREMENTS = {
    "README.md": (
        "workflow work-package",
        "make work-package",
        "--skill-root",
        ".agents/skills",
        ".codex/skills",
        "package_available",
        "can_start",
        "skill_readiness",
        "read_order",
        "write_scope",
        "next_action",
        "refresh_command",
        "work_stage",
        "author-design-documents",
        "record-design-review",
        "docs/agent-workflow/workflow-pack/references/",
    ),
    "workflows/00-overview.md": (
        "workflow work-package",
        "make work-package",
        "--skill-root",
        ".agents/skills",
        ".codex/skills",
        "package_available",
        "can_start",
        "skill_readiness",
        "read_order",
        "write_scope",
        "next_action",
        "refresh_command",
        "work_stage",
        "author-design-documents",
        "record-design-review",
        "docs/agent-workflow/workflow-pack/references/",
    ),
    "skills/using-governance-workflow/SKILL.md": (
        "workflow work-package",
        "make work-package",
        "--skill-root",
        ".agents/skills",
        ".codex/skills",
        "package_available",
        "can_start",
        "skill_readiness.resolved_requirements",
        "work_package.read_order",
        "work_package.write_scope",
        "next_action",
        "refresh_command",
        "work_stage",
        "author-design-documents",
        "record-design-review",
        "docs/agent-workflow/workflow-pack/references/",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        "workflow work-package",
        "make work-package",
        "package_id",
        "read_order",
        "write_scope",
        "skill_readiness.resolved_requirements",
        "next_action",
        "refresh_command",
        "can_start: true",
        "package_available: false",
        "work_stage",
        "record-design-review",
    ),
    "workflows/03-product-structuring.md": (
        "workflow work-package",
        "PRODUCT-AUTHOR-NNN",
        "read_order",
        "write_scope",
        "required_evidence",
        "next_action",
        "skill_readiness",
    ),
    "workflows/04-design-derivation.md": (
        "workflow work-package",
        "make work-package",
        "work_stage",
        "author-design-documents",
        "record-design-review",
        "work_id",
        "read_order",
        "write_scope",
        "next_action",
    ),
    "workflows/06-implementation-execution.md": (
        "workflow work-package",
        "make work-package",
        "requires_codebase_mapping: true",
        "claim-implementation-task",
        "verification_command_names",
        "verification_commands",
        "verification_command_summary",
        "execution_contract",
        "required_verification_commands_passing",
    ),
}
API_CANDIDATES_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-api-contracts/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
API_CANDIDATES_REQUIRED_PHRASES = (
    "design api-candidates",
    "candidates",
    "acceptance_id",
    "reference",
    "suggested_endpoint_file",
    "replaceable_starter_endpoint",
    "open_decisions",
    "method/path",
    "specialist_skills",
    "api-design-reviewer",
    "senior-backend",
    "senior-security",
)
ARCHITECTURE_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-system-architecture/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
ARCHITECTURE_AUTHORING_REQUIRED_PHRASES = (
    "design architecture-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_architecture_boundaries",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "system_boundary",
    "container_responsibilities",
    "quality_scenarios",
    "deployment_assumptions",
    "adr_candidates",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-architect",
    "senior-security",
    "observability-designer",
    "slo-architect",
    "verify-architecture-authoring",
    "refresh-architecture-authoring",
)
ARCHITECTURE_AUTHORING_SKILL_PATH = "skills/designing-system-architecture/SKILL.md"
ARCHITECTURE_AUTHORING_SKILL_REQUIRED_PHRASES = (
    "design architecture-authoring",
    "authoring_summary",
    "document_status_counts",
    "non_authored_document_count",
    "required_decisions",
    "open_decisions",
    "review_status",
    "document_blockers",
    "skill_loading_plan.steps[]",
    "authority-routing",
    "senior-architect",
    "load_from_agent_environment_or_stop_before_guessing",
    "workflow work-package",
    "references/design-review-checklist.md",
    "design review --track architecture",
)
API_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-api-contracts/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
API_AUTHORING_REQUIRED_PHRASES = (
    "design api-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_contract_details",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "api-design-reviewer",
    "senior-backend",
    "senior-security",
    "verify-api-authoring",
    "refresh-api-authoring",
)
BACKEND_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-backend-modules/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
BACKEND_AUTHORING_REQUIRED_PHRASES = (
    "design backend-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_backend_boundaries",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "module_boundaries",
    "observability",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-backend",
    "observability-designer",
    "senior-security",
    "verify-backend-authoring",
    "refresh-backend-authoring",
)
BACKEND_AUTHORING_SKILL_PATH = "skills/designing-backend-modules/SKILL.md"
BACKEND_AUTHORING_SKILL_REQUIRED_PHRASES = (
    "design backend-authoring",
    "authoring_summary",
    "document_status_counts",
    "non_authored_document_count",
    "required_decisions",
    "open_decisions",
    "review_status",
    "senior-backend",
    "observability-designer",
    "senior-security",
    "workflow work-package",
    "references/design-review-checklist.md",
    "design review --track backend-modules",
)
DATA_MODEL_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-data-models/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
DATA_MODEL_AUTHORING_REQUIRED_PHRASES = (
    "design data-model-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_data_model",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "entity_ownership",
    "transaction_boundaries",
    "migration_order",
    "rollback_strategy",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "database-designer",
    "database-schema-designer",
    "migration-architect",
    "senior-backend",
    "senior-security",
    "verify-data-model-authoring",
    "refresh-data-model-authoring",
)
UI_INTERACTION_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-ui-interactions/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
UI_INTERACTION_AUTHORING_REQUIRED_PHRASES = (
    "design ui-interaction-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_ui_behavior",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "primary_flows",
    "screens",
    "states",
    "error_actions",
    "accessibility",
    "copy_and_content",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-frontend",
    "a11y-audit",
    "verify-ui-interaction-authoring",
    "refresh-ui-interaction-authoring",
)
FRONTEND_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-frontend-modules/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
FRONTEND_AUTHORING_REQUIRED_PHRASES = (
    "design frontend-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_frontend_behavior",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "state_ownership",
    "error_actions",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-frontend",
    "a11y-audit",
    "performance-profiler",
    "verify-frontend-authoring",
    "refresh-frontend-authoring",
)
TEST_STRATEGY_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/designing-test-strategy/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
TEST_STRATEGY_AUTHORING_REQUIRED_PHRASES = (
    "design test-strategy-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_verification_scope",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "acceptance_coverage",
    "evidence_targets",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-qa",
    "playwright-pro",
    "a11y-audit",
    "security-pen-testing",
    "verify-test-strategy-authoring",
    "refresh-test-strategy-authoring",
)
IMPLEMENTATION_PLANNING_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/planning-implementation-work/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
IMPLEMENTATION_PLANNING_AUTHORING_REQUIRED_PHRASES = (
    "design implementation-planning-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_task_scope",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "task_scope",
    "ready_criteria",
    "verification_plan",
    "agent_handoff",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-fullstack",
    "ci-cd-pipeline-builder",
    "tech-debt-tracker",
    "verify-implementation-planning-authoring",
    "refresh-implementation-planning-authoring",
)
ARCHITECTURE_DECISIONS_AUTHORING_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/04-design-derivation.md",
    "skills/capturing-architecture-decisions/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
ARCHITECTURE_DECISIONS_AUTHORING_REQUIRED_PHRASES = (
    "design architecture-decisions-authoring",
    "authoring_tasks",
    "authoring_summary",
    "sequence",
    "execution",
    "decision_policy",
    "do_not_guess_architecture_decisions",
    "primary_skill",
    "primary_specialist_skill",
    "verify_step",
    "refresh_step",
    "stop_condition",
    "documents",
    "sections",
    "required_links",
    "required_links[].status",
    "required_link_status_counts",
    "non_satisfied_required_link_count",
    "link_repair_actions",
    "link_repair_action_count",
    "repair_strategy",
    "verify_command",
    "refresh_command",
    "open_decisions",
    "adr_trigger",
    "decision_scope",
    "alternatives",
    "requires_adr",
    "specialist_skills",
    "skill_requirements",
    "authority_skill_requirements",
    "authority-routing",
    "missing_policy",
    "senior-architect",
    "migration-architect",
    "tech-stack-evaluator",
    "verify-architecture-decisions-authoring",
    "refresh-architecture-decisions-authoring",
)
SCAFFOLD_CONTINUATION_DOC_PATHS = (
    "README.md",
    "workflows/00-overview.md",
    "workflows/03-product-structuring.md",
    "workflows/04-design-derivation.md",
    "skills/using-governance-workflow/SKILL.md",
    "skills/structuring-product-requirements/SKILL.md",
    "skills/designing-system-architecture/SKILL.md",
    "skills/designing-ui-interactions/SKILL.md",
    "skills/designing-api-contracts/SKILL.md",
    "skills/designing-backend-modules/SKILL.md",
    "skills/designing-data-models/SKILL.md",
    "skills/designing-frontend-modules/SKILL.md",
    "skills/designing-test-strategy/SKILL.md",
    "skills/planning-implementation-work/SKILL.md",
    "skills/verifying-governance-docs/SKILL.md",
)
SCAFFOLD_CONTINUATION_REQUIRED_PHRASES = (
    "scaffold_phase",
    "scaffold_phase.matches",
    "next_actions_blocked_by",
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
        "references/architecture-decision-record-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/capturing-architecture-decisions/SKILL.md",
        ),
    ),
    (
        "references/api-design-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-api-contracts/SKILL.md",
        ),
    ),
    (
        "references/architecture-quality-checklist.md",
        (
            "workflows/04-design-derivation.md",
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
    (
        "references/data-model-design-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-backend-modules/SKILL.md",
            "skills/designing-data-models/SKILL.md",
        ),
    ),
    (
        "references/backend-operability-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-backend-modules/SKILL.md",
        ),
    ),
    (
        "references/frontend-interaction-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-frontend-modules/SKILL.md",
            "skills/designing-ui-interactions/SKILL.md",
        ),
    ),
    (
        "references/implementation-readiness-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/planning-implementation-work/SKILL.md",
        ),
    ),
    (
        "references/security-design-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-api-contracts/SKILL.md",
            "skills/designing-backend-modules/SKILL.md",
            "skills/designing-test-strategy/SKILL.md",
        ),
    ),
    (
        "references/test-strategy-checklist.md",
        (
            "workflows/04-design-derivation.md",
            "skills/designing-test-strategy/SKILL.md",
        ),
    ),
)
INITIALIZATION_REFERENCE_DOC_REQUIREMENTS = (
    (
        "references/repository-initialization-checklist.md",
        (
            "workflows/01-empty-repo-initialization.md",
            "skills/initializing-governance-repo/SKILL.md",
        ),
    ),
)
VERIFICATION_REFERENCE_DOC_REQUIREMENTS = (
    (
        "references/governance-verification-checklist.md",
        (
            "workflows/05-verification-and-drift-control.md",
            "skills/verifying-governance-docs/SKILL.md",
        ),
    ),
    (
        "references/release-readiness-checklist.md",
        (
            "README.md",
            "workflows/00-overview.md",
            "workflows/05-verification-and-drift-control.md",
            "skills/verifying-governance-docs/SKILL.md",
        ),
    ),
)
IMPLEMENTATION_REFERENCE_DOC_REQUIREMENTS = (
    (
        "references/implementation-execution-checklist.md",
        (
            "workflows/05-verification-and-drift-control.md",
            "workflows/06-implementation-execution.md",
            "skills/executing-implementation-task/SKILL.md",
            "skills/planning-implementation-work/SKILL.md",
        ),
    ),
)
WORKFLOW_ROUTING_REFERENCE_DOC_REQUIREMENTS = (
    (
        "references/workflow-routing-checklist.md",
        (
            "workflows/00-overview.md",
            "skills/using-governance-workflow/SKILL.md",
        ),
    ),
)
PRODUCT_REFERENCE_DOC_REQUIREMENTS = (
    (
        "references/product-archive-checklist.md",
        (
            "workflows/02-product-document-archiving.md",
            "skills/archiving-product-document/SKILL.md",
        ),
    ),
    (
        "references/product-requirements-checklist.md",
        (
            "workflows/03-product-structuring.md",
            "skills/structuring-product-requirements/SKILL.md",
        ),
    ),
)
METHOD_REFERENCE_BASELINES = {
    "references/workflow-routing-checklist.md": (
        (
            "Entry Classification",
            (
                "## Entry Classification",
                "target state classified from current files and governance state",
                "routed to `initializing-governance-repo`",
                "https://www.omg.org/spec/BPMN/2.0.2/",
            ),
        ),
        (
            "Machine-Readable Continuation",
            (
                "## Machine-Readable Continuation",
                "`local_commands[].argv` and `next_actions[].argv` executed from their reported `cwd`",
                "`sequence`, `preflight_for`, `requires_action`, and `success_condition`",
                "https://www.rfc-editor.org/rfc/rfc8259.html",
            ),
        ),
        (
            "Gate and Advance Discipline",
            (
                "## Gate and Advance Discipline",
                "advance --check --json",
                "requirements[].code",
            ),
        ),
        (
            "Scaffold Continuation",
            (
                "## Scaffold Continuation",
                "scaffold_phase.matches",
                "next_actions_blocked_by",
                "governance:scaffold-placeholder",
            ),
        ),
        (
            "Repair Routing",
            (
                "## Repair Routing",
                "runtime refresh --check --json",
                "trusted source workflow-pack checkout",
            ),
        ),
        (
            "Schema and Payload Expectations",
            (
                "## Schema and Payload Expectations",
                "`cwd`, `command`, `argv`, `writes_state`, and `approval_required`",
                "`sequence`, `preflight_for`, `requires_action`, and `success_condition`",
                "https://json-schema.org/draft/2020-12/json-schema-core",
            ),
        ),
        (
            "Source-of-Truth Priority",
            (
                "## Source-of-Truth Priority",
                "stronger evidence than prior chat context",
                "explicit stop conditions escalated to the user",
            ),
        ),
        (
            "Normative Language",
            (
                "## Normative Language",
                "hard requirements",
                "https://www.rfc-editor.org/rfc/rfc2119.html",
            ),
        ),
    ),
    "references/architecture-decision-record-checklist.md": (
        (
            "Decision Trigger",
            (
                "## Decision Trigger",
                "multiple modules, runtime topology, state machines, external dependencies, security posture, data ownership, API compatibility",
                "https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions",
            ),
        ),
        (
            "Context and Forces",
            (
                "## Context and Forces",
                "decision drivers or forces",
                "https://www.iso.org/standard/74393.html",
            ),
        ),
        (
            "Options and Rationale",
            (
                "## Options and Rationale",
                "credible considered options",
                "docs/unresolved.md",
                "https://adr.github.io/madr/",
            ),
        ),
        (
            "Consequences and Verification",
            (
                "## Consequences and Verification",
                "positive, negative, operational, security, performance, cost, migration, and maintenance consequences",
                "https://docs.arc42.org/section-9/",
            ),
        ),
        (
            "Identity and Lifecycle",
            (
                "## Identity and Lifecycle",
                "unique `NNN-<slug>.md`",
                "proposed, accepted, rejected, deprecated, or superseded",
            ),
        ),
        (
            "Traceability and Indexing",
            (
                "## Traceability and Indexing",
                "docs/decisions/README.md",
                "local Markdown references",
            ),
        ),
    ),
    "references/governance-verification-checklist.md": (
        (
            "Command Discipline",
            (
                "## Command Discipline",
                "matching `--check --json` preflight",
                "`findings[].code`, `findings[].path`, and `requirements[].code`",
                "https://dora.dev/capabilities/test-automation/",
            ),
        ),
        (
            "Environment Repair Control",
            (
                "## Environment Repair Control",
                "bin/governance env --strict --repair --check --target <target> --json",
                "`would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, and `needs_escalation`",
            ),
        ),
        (
            "Drift and Refresh",
            (
                "## Drift and Refresh",
                "runtime_manifest_*",
                "workflow_pack_manifest_*",
                "bin/governance runtime refresh <target> --check --json",
                "https://slsa.dev/spec/v1.2/about",
            ),
        ),
        (
            "Phase Gates and State",
            (
                "## Phase Gates and State",
                "recording adjacent phase transitions",
                ".governance/state.json",
            ),
        ),
        (
            "Repair Ordering",
            (
                "## Repair Ordering",
                "document-integrity findings",
                "missing acceptance IDs, unresolved IDs, links, and evidence",
            ),
        ),
        (
            "Traceability and Evidence",
            (
                "## Traceability and Evidence",
                "existing local Markdown sources",
                "verification commands and results",
            ),
        ),
        (
            "Security and Supply Chain Sanity",
            (
                "## Security and Supply Chain Sanity",
                "SECURITY.md",
                "https://csrc.nist.gov/pubs/sp/800/218/final",
                "https://github.com/ossf/scorecard",
            ),
        ),
        (
            "Completion Gate",
            (
                "## Completion Gate",
                "bin/governance verify <target> --check --json",
                "bin/governance advance implementation <target> --check --json",
            ),
        ),
    ),
    "references/repository-initialization-checklist.md": (
        (
            "Target Safety",
            (
                "## Target Safety",
                "bin/governance init --check --target <target> --json",
                "bin/governance init --check --target <target> --product <product-doc> --json",
                "multiple product document candidates",
                "`--force`",
                "https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository",
            ),
        ),
        (
            "Environment and Repair",
            (
                "## Environment and Repair",
                "`would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, and `needs_escalation`",
                "POSIX shell plus Python standard-library runtime",
            ),
        ),
        (
            "Governance Entry Points",
            (
                "## Governance Entry Points",
                "README.md`, `AGENTS.md`, `SPEC.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, and `Makefile",
                "https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes",
            ),
        ),
        (
            "Runtime and Snapshot Integrity",
            (
                "## Runtime and Snapshot Integrity",
                "docs/agent-workflow/runtime-manifest.json",
                "docs/agent-workflow/workflow-pack/manifest.json",
                "make verify-governance",
            ),
        ),
        (
            "Product Seed",
            (
                "## Product Seed",
                "docs/product/core/PRD.md",
                "docs/product/core/source/source-manifest.json",
                "product selection as `explicit`, `auto-discovered`, `none`, or `ambiguous`",
                ".governance/state.json",
            ),
        ),
        (
            "Git Readiness",
            (
                "## Git Readiness",
                "default branch, remote, and author identity",
                "https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository",
            ),
        ),
        (
            "Baseline Security Posture",
            (
                "## Baseline Security Posture",
                "SECURITY.md",
                "branch protection or code scanning",
                "https://scorecard.dev/",
            ),
        ),
        (
            "Editor and Tooling Consistency",
            (
                "## Editor and Tooling Consistency",
                "formatting, line ending, and editor expectations",
                "https://editorconfig.org/",
            ),
        ),
        (
            "Handoff Readiness",
            (
                "## Handoff Readiness",
                "bin/governance verify <target> --check --json",
                "bin/governance advance product-structuring <target> --check --json",
            ),
        ),
    ),
    "references/product-archive-checklist.md": (
        (
            "Source Preservation",
            (
                "## Source Preservation",
                "untouched original copied under `docs/product/core/source/`",
                "https://www.w3.org/TR/prov-overview/",
            ),
        ),
        (
            "Manifest Evidence",
            (
                "## Manifest Evidence",
                "source path, archived path, byte size, SHA-256, conversion method, import status, and `can_derive_design`",
                "https://csrc.nist.gov/pubs/fips/180-4/upd1/final",
            ),
        ),
        (
            "Conversion Fidelity",
            (
                "## Conversion Fidelity",
                "not a summary",
                "tables, acceptance rules, field names, constraints, diagrams",
                "https://pandoc.org/MANUAL.html",
            ),
        ),
        (
            "Markdown Portability",
            (
                "## Markdown Portability",
                "valid UTF-8 Markdown",
                "https://spec.commonmark.org/0.31.2/",
            ),
        ),
        (
            "Review Closeout",
            (
                "## Review Closeout",
                "`would_update`",
                "instead of hand-editing manifest readiness fields",
            ),
        ),
        (
            "Unresolved Import Limits",
            (
                "## Unresolved Import Limits",
                "docs/unresolved.md",
                "`U-001`",
            ),
        ),
        (
            "Handoff Readiness",
            (
                "## Handoff Readiness",
                "bin/governance verify <target> --check --json",
                "bin/governance gate product-structuring <target> --json",
            ),
        ),
    ),
    "references/product-requirements-checklist.md": (
        (
            "Source Fidelity",
            (
                "## Source Fidelity",
                "without invented actors, workflows, constraints, or success targets",
                "https://www.iso.org/standard/72089.html",
            ),
        ),
        (
            "Requirement Quality",
            (
                "## Requirement Quality",
                "clear, necessary, feasible, unambiguous, verifiable, and traceable",
                "https://www.iso.org/standard/72089.html",
            ),
        ),
        (
            "Scope and Story Slicing",
            (
                "## Scope and Story Slicing",
                "independent, negotiable, valuable, estimable, small, and testable",
                "https://xp123.com/articles/invest-in-good-stories-and-smart-tasks/",
            ),
        ),
        (
            "Acceptance Criteria",
            (
                "## Acceptance Criteria",
                "stable product-defined `A-NNN` ID",
                "Given/When/Then",
                "https://cucumber.io/docs/gherkin/reference/",
            ),
        ),
        (
            "Glossary and Domain Language",
            (
                "## Glossary and Domain Language",
                "unique `Term`, filled `Meaning`, and local Markdown `Source`",
            ),
        ),
        (
            "Unresolved Questions",
            (
                "## Unresolved Questions",
                "unique `U-NNN` ID",
                "`Blocking Scope`",
            ),
        ),
        (
            "Design Readiness",
            (
                "## Design Readiness",
                "no blocking unresolved rows",
                "docs/unresolved.md",
            ),
        ),
    ),
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
    "references/api-design-checklist.md": (
        (
            "Contract Shape",
            (
                "## Contract Shape",
                "OpenAPI",
                "https://spec.openapis.org/oas/latest.html",
            ),
        ),
        (
            "HTTP Semantics",
            (
                "## HTTP Semantics",
                "safe, idempotent, and cacheable methods",
                "https://www.rfc-editor.org/rfc/rfc9110.html",
            ),
        ),
        (
            "Error Responses",
            (
                "## Error Responses",
                "machine-readable problem details",
                "https://www.rfc-editor.org/rfc/rfc9457.html",
            ),
        ),
        (
            "Idempotency and Concurrency",
            (
                "## Idempotency and Concurrency",
                "Idempotency-Key",
                "duplicate submission",
            ),
        ),
        (
            "Compatibility and Change Control",
            (
                "## Compatibility and Change Control",
                "backward-compatible additions, deprecations, and breaking changes",
            ),
        ),
    ),
    "references/architecture-quality-checklist.md": (
        (
            "Architecture Description",
            (
                "## Architecture Description",
                "stakeholders, concerns, system boundary, views, decisions, rationale",
                "https://www.iso.org/standard/74393.html",
            ),
        ),
        (
            "Quality Model Coverage",
            (
                "## Quality Model Coverage",
                "availability, performance efficiency, compatibility, usability, reliability, security",
                "https://www.iso.org/standard/78176.html",
            ),
        ),
        (
            "Quality Scenarios",
            (
                "## Quality Scenarios",
                "source, stimulus, environment, affected artifact, response, and response measure",
                "https://docs.arc42.org/section-10/",
            ),
        ),
        (
            "Tradeoff Review",
            (
                "## Tradeoff Review",
                "sensitivity points, tradeoffs, risks, and non-risks",
                "https://resources.sei.cmu.edu/asset_files/TechnicalReport/2000_005_001_13706.pdf",
            ),
        ),
        (
            "Implementation Readiness",
            (
                "## Implementation Readiness",
                "without inventing architecture meaning",
                "verification hooks",
            ),
        ),
    ),
    "references/backend-design-checklist.md": (
        ("Module Boundary", ("## Module Boundary", "one primary responsibility")),
        (
            "Data Model",
            (
                "## Data Model",
                "idempotency keys and uniqueness constraints",
                "transaction boundaries, consistency expectations, and concurrency conflicts",
            ),
        ),
        ("API Contract", ("## API Contract", "request fields, response fields, auth")),
        (
            "Runtime Flow",
            (
                "## Runtime Flow",
                "retries, timeouts, and compensation behavior",
                "duplicate-submission handling",
            ),
        ),
        ("Observability and Security", ("## Observability and Security", "auth boundaries")),
        ("Acceptance and Tests", ("## Acceptance and Tests", "unit, integration, and contract tests")),
    ),
    "references/data-model-design-checklist.md": (
        (
            "Product Traceability and Ownership",
            (
                "## Product Traceability and Ownership",
                "owning backend module",
                "docs/unresolved.md",
            ),
        ),
        (
            "Identity and Relationships",
            (
                "## Identity and Relationships",
                "primary key, external identifier, and tenant or user isolation boundary",
                "https://www.postgresql.org/docs/current/ddl-constraints.html",
            ),
        ),
        (
            "Constraints and Invariants",
            (
                "## Constraints and Invariants",
                "idempotency keys, duplicate-submission behavior, and cross-user isolation",
                "https://www.postgresql.org/docs/current/ddl-constraints.html",
            ),
        ),
        (
            "State and Concurrency",
            (
                "## State and Concurrency",
                "transaction boundaries, isolation expectations, lock or version strategy, and conflict outcomes",
                "https://www.postgresql.org/docs/current/transaction-iso.html",
            ),
        ),
        (
            "Query Paths and Indexes",
            (
                "## Query Paths and Indexes",
                "filter, sort, uniqueness rule, or foreign-key access pattern",
                "https://www.postgresql.org/docs/current/indexes.html",
            ),
        ),
        (
            "Migration and Backfill",
            (
                "## Migration and Backfill",
                "forward migration, compatibility, backfill, validation",
                "https://martinfowler.com/articles/evodb.html",
            ),
        ),
        (
            "Retention, Deletion, and Audit",
            (
                "## Retention, Deletion, and Audit",
                "retention, archival, soft-delete, restore, legal hold, and hard-delete",
                "references/security-design-checklist.md",
            ),
        ),
        (
            "Verification",
            (
                "## Verification",
                "constraint tests, migration tests, concurrency tests, query-performance checks",
                "docs/unresolved.md",
            ),
        ),
    ),
    "references/backend-operability-checklist.md": (
        (
            "Service Levels",
            (
                "## Service Levels",
                "SLIs and SLOs",
                "https://sre.google/sre-book/service-level-objectives/",
            ),
        ),
        (
            "Observability Signals",
            (
                "## Observability Signals",
                "logs, metrics, traces, and audit events",
                "https://opentelemetry.io/docs/concepts/signals/",
            ),
        ),
        (
            "Configuration and Secrets",
            (
                "## Configuration and Secrets",
                "secrets, credentials, tokens, rotation expectations",
                "https://12factor.net/config",
            ),
        ),
        (
            "Runtime Controls",
            (
                "## Runtime Controls",
                "timeouts, retries, backoff, circuit breakers, rate limits, quotas",
            ),
        ),
        (
            "Operational Logs",
            (
                "## Operational Logs",
                "logs treated as event streams",
                "https://12factor.net/logs",
            ),
        ),
    ),
    "references/frontend-interaction-checklist.md": (
        (
            "Accessibility and Semantics",
            (
                "## Accessibility and Semantics",
                "keyboard operation, focus order, visible focus, labels",
                "https://www.w3.org/TR/WCAG22/",
                "https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA",
            ),
        ),
        (
            "Component Behavior",
            (
                "## Component Behavior",
                "role, state, property, keyboard interaction, and focus-management behavior",
                "https://www.w3.org/WAI/ARIA/apg/",
            ),
        ),
        (
            "API Consumption and Error UX",
            (
                "## API Consumption and Error UX",
                "user-visible copy, recovery action, retry behavior, telemetry",
            ),
        ),
        (
            "State and Routing",
            (
                "## State and Routing",
                "local, shared, server-derived, cached, optimistic, persisted, and URL/route state",
            ),
        ),
        (
            "Performance and Responsiveness",
            (
                "## Performance and Responsiveness",
                "Core Web Vitals",
                "https://web.dev/articles/vitals",
            ),
        ),
    ),
    "references/implementation-readiness-checklist.md": (
        (
            "Ready Task Contract",
            (
                "## Ready Task Contract",
                "Product, Design, API, Acceptance, and Verification cells",
                "https://scrumguides.org/scrum-guide.html",
            ),
        ),
        (
            "Definition of Done",
            (
                "## Definition of Done",
                "working code, synchronized docs, passing verification commands",
                "https://scrumguides.org/scrum-guide.html",
            ),
        ),
        (
            "Verification Plan",
            (
                "## Verification Plan",
                "exact commands, test layers, expected evidence target",
                "https://dora.dev/capabilities/test-automation/",
            ),
        ),
        (
            "Change Integration",
            (
                "## Change Integration",
                "small enough to review, integrate, and verify independently",
                "https://dora.dev/capabilities/trunk-based-development/",
            ),
        ),
        (
            "Supply Chain Evidence",
            (
                "## Supply Chain Evidence",
                "provenance, integrity, and dependency update expectations",
                "https://slsa.dev/spec/v1.1/about",
            ),
        ),
    ),
    "references/release-readiness-checklist.md": (
        (
            "Source Pack Verification",
            (
                "## Source Pack Verification",
                "make verify-pack",
                "python3 scripts/verify_pack.py --json",
            ),
        ),
        (
            "Dry Run Validation",
            (
                "## Dry Run Validation",
                "make dry-run",
                "fresh-target-governance-dry-run",
            ),
        ),
        (
            "Export Artifact Integrity",
            (
                "## Export Artifact Integrity",
                "make package",
                "pack-manifest.json",
                "SHA-256 evidence",
            ),
        ),
        (
            "Environment and Tooling",
            (
                "## Environment and Tooling",
                "python3 scripts/check_env.py --json",
                "missing_required",
            ),
        ),
        (
            "Release Evidence",
            (
                "## Release Evidence",
                "python3 scripts/release_readiness.py --json",
                "release_ready",
            ),
        ),
    ),
    "references/implementation-execution-checklist.md": (
        (
            "Task Intake",
            (
                "## Task Intake",
                "exactly one `Ready` `TASK-NNN`",
                "mapped in `docs/tests/02-acceptance-matrix.md`",
                "https://google.github.io/eng-practices/review/developer/",
            ),
        ),
        (
            "Scope Control",
            (
                "## Scope Control",
                "modified files limited to the task goal",
                "registered in `docs/unresolved.md` instead of silently guessed",
                "https://google.github.io/eng-practices/review/developer/small-cls.html",
            ),
        ),
        (
            "Verification Execution",
            (
                "## Verification Execution",
                "preferring target-local `local_commands[].argv`",
                "skipped, flaky, unavailable, or failed checks recorded honestly",
                "https://dora.dev/capabilities/test-automation/",
            ),
        ),
        (
            "Security and Supply Chain",
            (
                "## Security and Supply Chain",
                "secrets, credentials, tokens, private keys",
                "https://slsa.dev/spec/v1.2/about",
                "https://openssf.org/projects/scorecard/",
            ),
        ),
    ),
    "references/security-design-checklist.md": (
        (
            "Identity and Access",
            ("## Identity and Access", "authentication boundaries", "authorization checks"),
        ),
        (
            "API Abuse and Input",
            ("## API Abuse and Input", "object-level authorization", "mass-assignment", "rate limits"),
        ),
        (
            "Data Protection",
            ("## Data Protection", "sensitive fields", "logging", "retention"),
        ),
        (
            "Dependency and Supply Chain",
            ("## Dependency and Supply Chain", "secret storage", "least-privilege access"),
        ),
        (
            "Security Verification",
            ("## Verification", "manual review", "docs/unresolved.md"),
        ),
        ("OWASP ASVS", ("OWASP ASVS", "https://owasp.org/www-project-application-security-verification-standard/")),
        ("OWASP API Security Top 10", ("OWASP API Security Top 10 2023", "https://owasp.org/API-Security/editions/2023/en/0x11-t10/")),
        ("OpenSSF Best Practices", ("OpenSSF Best Practices", "https://bestpractices.coreinfrastructure.org/en")),
    ),
    "references/test-strategy-checklist.md": (
        (
            "Acceptance Traceability",
            (
                "## Acceptance Traceability",
                "product-defined `A-NNN` acceptance criterion",
                "Uncovered Criteria",
            ),
        ),
        (
            "Test Portfolio",
            (
                "## Test Portfolio",
                "unit tests, integration tests, contract tests, and end-to-end tests",
                "https://martinfowler.com/bliki/TestPyramid.html",
            ),
        ),
        (
            "Automation and Feedback",
            (
                "## Automation and Feedback",
                "local, deterministic, and suitable for agent execution",
                "https://dora.dev/capabilities/test-automation/",
            ),
        ),
        (
            "Test Data and Environments",
            (
                "## Test Data and Environments",
                "fixtures, seed data, cleanup, privacy constraints",
                "https://dora.dev/capabilities/test-data-management/",
            ),
        ),
        (
            "Non-Functional Verification",
            (
                "## Non-Functional Verification",
                "performance, accessibility, security, reliability, observability",
                "https://www.w3.org/TR/WCAG22/",
                "https://opentelemetry.io/docs/concepts/signals/",
            ),
        ),
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
    "dry-run",
    "dry-run-golden",
    "stack-acceptance",
    "package",
    "artifact-smoke",
    "release-check",
    "authority-skills",
    "verify-pack",
)
MAKEFILE_REQUIRED_TARGET_RECIPES = {
    "test": (
        "python3 -m unittest discover -s tests",
    ),
    "dry-run": (
        "python3 scripts/dry_run_workflow.py --json",
    ),
    "dry-run-golden": (
        "python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json",
    ),
    "stack-acceptance": (
        "python3 scripts/stack_acceptance.py --json",
    ),
    "package": (
        "python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json",
    ),
    "artifact-smoke": (
        "python3 scripts/smoke_workflow_pack_artifact.py --json",
    ),
    "release-check": (
        "python3 scripts/release_readiness.py --json",
    ),
    "authority-skills": (
        "python3 scripts/authority_skills.py --json",
    ),
    "verify-pack": (
        "python3 scripts/verify_pack.py",
        "python3 scripts/check_env.py",
    ),
}
RUNTIME_WRAPPER_REQUIRED_COMMANDS = {
    "bin/governance": 'python3 "$ROOT_DIR/scripts/governance_cli.py" "$@"',
    CONSUMER_BOOTSTRAP_WRAPPER_PATH: (
        'python3 "$ROOT_DIR/scripts/bootstrap_consumer_project.py" --auto-repair-env "$@"'
    ),
    "bin/governance-init": 'python3 "$ROOT_DIR/scripts/governance_cli.py" init "$@"',
    "bin/governance-verify": 'python3 "$ROOT_DIR/scripts/governance_cli.py" verify "$@"',
}
BOOTSTRAP_TREE_PATH = Path("scripts/bootstrap_tree.py")
GENERATED_ROOT_AGENTS_REQUIRED_PHRASES = (
    "## Workflow Startup",
    "Read `docs/agent-workflow/workflow-pack/workflows/00-overview.md`",
    "Run `make workflow-resume` before selecting work",
    "can_continue: true",
    "stop_before_action: false",
    "assert_snapshot_command.argv",
    "work_package.read_order",
    "skill_loading_plan.steps[]",
    "load_local_workflow_skill",
    "docs/agent-workflow/workflow-pack/skills/",
    "load_authority_routing_skill",
    "missing_policy",
    "refresh_command.argv",
)
GENERATED_ROOT_AGENTS_DOC_REQUIREMENTS = {
    "README.md": (
        "Generated root `AGENTS.md`",
        "`Workflow Startup`",
        "`make workflow-resume`",
        "`work_package.read_order`",
        "`skill_loading_plan.steps[]`",
        "`docs/agent-workflow/workflow-pack/skills/`",
        "`missing_policy`",
        "`refresh_command.argv`",
    ),
    "workflows/01-empty-repo-initialization.md": (
        "root `AGENTS.md`",
        "`Workflow Startup`",
        "`make workflow-resume`",
        "`assert_snapshot_command.argv`",
        "`work_package.read_order`",
        "`skill_loading_plan.steps[]`",
        "`docs/agent-workflow/workflow-pack/skills/`",
        "`missing_policy`",
        "`refresh_command.argv`",
    ),
    "skills/initializing-governance-repo/SKILL.md": (
        "root `AGENTS.md`",
        "`Workflow Startup`",
        "`make workflow-resume`",
        "`assert_snapshot_command.argv`",
        "`work_package.read_order`",
        "`skill_loading_plan.steps[]`",
        "`docs/agent-workflow/workflow-pack/skills/`",
        "`missing_policy`",
        "`refresh_command.argv`",
    ),
    "references/repository-initialization-checklist.md": (
        "root `AGENTS.md`",
        "`make workflow-resume`",
        "snapshot assertion",
        "work-package read order",
        "ordered local/authority skill loading",
        "one selected action",
        "refresh before the next action",
    ),
}
GOVERNANCE_CLI_PATH = Path("scripts/governance_cli.py")
WORKFLOW_ACTIONS_PATH = Path("scripts/workflow_actions.py")
GOVERNANCE_CLI_REQUIRED_COMMANDS = (
    "init",
    "verify",
    "status",
    "env",
    "project-env",
    "workflow",
    "runtime",
    "gate",
    "scaffold",
    "advance",
    "product",
    "design",
    "implementation",
)
GOVERNANCE_CLI_REQUIRED_SUBCOMMANDS = {
    "runtime": ("refresh",),
    "project-env": ("plan", "register", "repair"),
    "workflow": ("plan", "work-package", "resume"),
    "product": ("convert", "mark-ready", "plan", "disposition", "structure"),
    "design": (
        "plan",
        "review",
        "api-review",
        "api-candidates",
        "architecture-authoring",
        "api-authoring",
        "backend-authoring",
        "data-model-authoring",
        "ui-interaction-authoring",
        "frontend-authoring",
        "test-strategy-authoring",
        "implementation-planning-authoring",
        "architecture-decisions-authoring",
    ),
    "implementation": ("plan", "start", "verify", "closeout", "run"),
}
GOVERNANCE_CLI_PARSER_VARIABLES = {
    "top-level": "sub",
    "runtime": "runtime_sub",
    "project-env": "project_environment_sub",
    "workflow": "workflow_sub",
    "product": "product_sub",
    "design": "design_sub",
    "implementation": "implementation_sub",
}
RUNTIME_WRAPPER_REQUIRED_GUARDS = (
    "#!/usr/bin/env bash",
    "set -euo pipefail",
)
RUNTIME_WRAPPER_ROOT_DIR_LINE = 'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"'
CONTINUATION_RUNTIME_SCRIPT_PATHS = (
    "scripts/bootstrap_tree.py",
    "scripts/check_env.py",
    "scripts/design_plan.py",
    "scripts/gates.py",
    "scripts/governance_cli.py",
    "scripts/implementation_plan.py",
    "scripts/phases.py",
    "scripts/product_conversion.py",
    "scripts/product_import.py",
    "scripts/product_structure.py",
    "scripts/scaffold.py",
    "scripts/verify_governance.py",
)
CONTINUATION_RUNTIME_REQUIRED_CALLS = (
    "target_local_commands_payload",
    "next_actions_payload",
)
TARGET_LOCAL_COMMAND_PAYLOAD_REQUIRED_KEYS = (
    "make_target",
    "cwd",
    "command",
    "argv",
    "recipe",
    "writes_state",
    "approval_required",
    "description",
)
WORKFLOW_ACTION_SOURCE_REQUIRED_KEYS = (
    "id",
    "kind",
    "phase",
    "workflow",
    "skills",
    "command",
    "argv",
    "writes_state",
    "approval_required",
    "requires",
    "sequence",
    "success_condition",
    "description",
)
WORKFLOW_ACTION_PAYLOAD_REQUIRED_KEYS = (
    "cwd",
    *WORKFLOW_ACTION_SOURCE_REQUIRED_KEYS,
)
WORKFLOW_ACTION_PHASE_METADATA_REQUIRED_KEYS = (
    "workflow",
    "skills",
    "description",
)
WORKFLOW_ACTION_PHASE_WORKFLOWS = {
    "product-document-archiving": "workflows/02-product-document-archiving.md",
    "product-structuring": "workflows/03-product-structuring.md",
    "design-derivation": "workflows/04-design-derivation.md",
    "implementation": "workflows/05-verification-and-drift-control.md",
}
WORKFLOW_ACTION_REQUIRED_SUPPORT_SKILLS = (
    "verifying-governance-docs",
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
            ".github/workflows/ci.yml",
            "README.md",
            "AGENTS.md",
            "Makefile",
            "scripts/authority_skills.py",
            "references/authority-skills.lock.json",
            "scripts/verify_pack_manifest.py",
            "scripts/verify_pack.py",
            STACK_ACCEPTANCE_PATH,
            STACK_ACCEPTANCE_TEST_PATH,
            CONSUMER_BOOTSTRAP_PATH,
            CONSUMER_BOOTSTRAP_WRAPPER_PATH,
            *(path.as_posix() for path in RUNTIME_REQUIRED_PATHS),
            *WORKFLOW_PACK_REQUIRED_PATHS,
        )
    )
)
CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
CI_WORKFLOW_REQUIRED_PHRASES = (
    "name: CI",
    "on:",
    "workflow_dispatch:",
    "timeout-minutes: 30",
    "actions/checkout@v4",
    "actions/setup-python@v5",
    "python-version: '3.10'",
    "actions/setup-node@v4",
    "node-version: '22'",
    "sudo apt-get update",
    "sudo apt-get install -y ripgrep",
    "make test",
    "make stack-acceptance",
    "python3 scripts/verify_pack.py --json",
    "python3 scripts/check_env.py --json",
)
CI_WORKFLOW_FORBIDDEN_TRIGGERS = (
    "\n  push:",
    "\n  pull_request:",
)
AUTHORITY_SKILL_INVENTORY_PATH = "scripts/authority_skills.py"
AUTHORITY_SKILL_LOCK_PATH = "references/authority-skills.lock.json"
AUTHORITY_SKILL_INVENTORY_REQUIRED_PHRASES = (
    "DESIGN_TRACKS",
    "BASE_SPECIALIST_SKILLS",
    "AUTHORITY_ROUTING_SPECIALIST_SKILLS",
    "AUTHORITY_ROUTING_SKILL_MISSING_POLICY",
    "load_from_agent_environment_or_stop_before_guessing",
    "agent-environment",
    "authority-routing",
    "--strict",
    "--strict-provenance",
    "--repair",
    "--check",
    "authority-skills.lock.json",
    "skill-tree",
    "source-unregistered",
    "drifted",
    "--skill-root",
    "required_by",
    "available_in_agent_environment",
    "missing_skills",
    "_installed_skill_index",
    "_installed_skill_candidates",
    "installation_ambiguous",
    "_skill_frontmatter_name",
    "validate_authority_skill_lock",
    "apply_authority_skill_repairs",
    "run_bounded_command",
    "--apply",
    "--approve-installs",
    "integrity_failed",
    "blocked_unsupported_actions",
    "manual_cleanup_required",
    "_task_specialist_skills",
)
AUTHORITY_SKILL_REPAIR_COMMAND = (
    "python3 scripts/authority_skills.py --repair --apply "
    "--approve-installs --strict-provenance --json"
)
AUTHORITY_SKILL_REPAIR_DOC_REQUIREMENTS = {
    "README.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "--approve-authority-installs --strict-authority-provenance --json",
        "authority_skill_auto_repair",
        "manual_cleanup_required",
    ),
    "workflows/00-overview.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "--approve-authority-installs --strict-authority-provenance --json",
        "authority_skill_auto_repair",
        "manual_cleanup_required",
    ),
    "workflows/01-empty-repo-initialization.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "manual_cleanup_required",
    ),
    "skills/initializing-governance-repo/SKILL.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "manual_cleanup_required",
    ),
    "skills/verifying-governance-docs/SKILL.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "--approve-authority-installs --strict-authority-provenance --json",
        "authority_skill_auto_repair",
    ),
    "references/runtime-strategy.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "120 seconds",
        "65,536 bytes",
    ),
    "references/repository-initialization-checklist.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "--approve-authority-installs --strict-authority-provenance",
    ),
    "references/authority-skills-source-review.md": (
        AUTHORITY_SKILL_REPAIR_COMMAND,
        "non-symlink Codex system installer",
        "manual_cleanup_required",
    ),
}
IGNORED_PACK_FILE_NAMES = {".DS_Store", "manifest.json"}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(r"^\s{0,3}\[[^\]]+]:\s*(\S+)", re.MULTILINE)
README_INDEX_ENTRY_RE = re.compile(r"^\s*-\s+`([^`\n]+)`(?P<trailing>[^\n]*)$")
SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
AUTHORITY_ROUTING_SPECIALIST_SKILLS = frozenset(
    {
        "a11y-audit",
        "api-design-reviewer",
        "ci-cd-pipeline-builder",
        "code-reviewer",
        "database-designer",
        "database-schema-designer",
        "migration-architect",
        "observability-designer",
        "performance-profiler",
        "playwright-pro",
        "security-pen-testing",
        "senior-architect",
        "senior-backend",
        "senior-devops",
        "senior-frontend",
        "senior-fullstack",
        "senior-qa",
        "senior-security",
        "slo-architect",
        "tech-debt-tracker",
        "tech-stack-evaluator",
    }
)
PHASE_WORKFLOW_PATHS = (
    "workflows/01-empty-repo-initialization.md",
    "workflows/02-product-document-archiving.md",
    "workflows/03-product-structuring.md",
    "workflows/04-design-derivation.md",
    "workflows/05-verification-and-drift-control.md",
    "workflows/06-implementation-execution.md",
)
PHASE_WORKFLOW_TITLES = {
    "workflows/01-empty-repo-initialization.md": "Empty Repository Initialization",
    "workflows/02-product-document-archiving.md": "Product Document Archiving",
    "workflows/03-product-structuring.md": "Product Structuring",
    "workflows/04-design-derivation.md": "Design Derivation",
    "workflows/05-verification-and-drift-control.md": "Verification and Drift Control",
    "workflows/06-implementation-execution.md": "Implementation Execution",
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
    _check_generated_root_agents_contract(root, findings)
    _check_generated_root_agents_docs(root, findings)
    _check_governance_cli_commands(root, findings)
    _check_fresh_target_workflow_smoke_test(root, findings)
    _check_dry_run_workflow(root, findings)
    _check_dry_run_golden_fixture(root, findings)
    _check_stack_acceptance_workflow(root, findings)
    _check_source_pack_export_workflow(root, findings)
    _check_pack_manifest_verify_workflow(root, findings)
    _check_consumer_bootstrap_workflow(root, findings)
    _check_artifact_smoke_workflow(root, findings)
    _check_release_readiness_workflow(root, findings)
    _check_ci_workflow(root, findings)
    _check_authority_skill_inventory(root, findings)
    _check_authority_skill_lock(root, findings)
    _check_authority_skill_repair_docs(root, findings)
    _check_runtime_continuation_calls(root, findings)
    _check_target_local_command_source(root, findings)
    _check_target_local_command_schema(root, findings)
    _check_workflow_action_schema(root, findings)
    _check_runtime_executable_bits(root, findings)
    _check_runtime_wrapper_commands(root, findings)
    _check_readme_package_layout(root, findings)
    _check_readme_quick_start(root, findings)
    _check_readme_artifact_consumer_quick_start(root, findings)
    _check_dry_run_docs(root, findings)
    _check_stack_acceptance_docs(root, findings)
    _check_source_pack_export_docs(root, findings)
    _check_pack_manifest_verify_docs(root, findings)
    _check_consumer_bootstrap_docs(root, findings)
    _check_artifact_smoke_docs(root, findings)
    _check_release_readiness_docs(root, findings)
    _check_target_makefile_command_docs(root, findings)
    _check_env_repair_docs(root, findings)
    _check_runtime_refresh_test_coverage(root, findings)
    _check_runtime_refresh_docs(root, findings)
    _check_product_conversion_source(root, findings)
    _check_product_archive_docs(root, findings)
    _check_product_structure_docs(root, findings)
    _check_product_disposition_source(root, findings)
    _check_product_disposition_docs(root, findings)
    _check_design_review_source(root, findings)
    _check_design_review_docs(root, findings)
    _check_api_review_source(root, findings)
    _check_api_review_docs(root, findings)
    _check_threat_review_source(root, findings)
    _check_threat_review_docs(root, findings)
    _check_reliability_review_source(root, findings)
    _check_reliability_review_docs(root, findings)
    _check_migration_review_source(root, findings)
    _check_migration_review_docs(root, findings)
    _check_design_scaffold_docs(root, findings)
    _check_design_plan_source(root, findings)
    _check_design_plan_docs(root, findings)
    _check_project_environment_source(root, findings)
    _check_bounded_process_source(root, findings)
    _check_implementation_run_source(root, findings)
    _check_implementation_run_docs(root, findings)
    _check_implementation_review_source(root, findings)
    _check_implementation_review_docs(root, findings)
    _check_implementation_verify_source(root, findings)
    _check_implementation_verify_docs(root, findings)
    _check_work_package_source(root, findings)
    _check_work_package_docs(root, findings)
    _check_workflow_resume_source(root, findings)
    _check_workflow_resume_docs(root, findings)
    _check_api_candidates_docs(root, findings)
    _check_architecture_authoring_docs(root, findings)
    _check_api_authoring_docs(root, findings)
    _check_backend_authoring_docs(root, findings)
    _check_data_model_authoring_docs(root, findings)
    _check_ui_interaction_authoring_docs(root, findings)
    _check_frontend_authoring_docs(root, findings)
    _check_test_strategy_authoring_docs(root, findings)
    _check_implementation_planning_authoring_docs(root, findings)
    _check_architecture_decisions_authoring_docs(root, findings)
    _check_scaffold_continuation_docs(root, findings)
    _check_implementation_handoff_docs(root, findings)
    _check_initialization_reference_docs(root, findings)
    _check_verification_reference_docs(root, findings)
    _check_implementation_reference_docs(root, findings)
    _check_product_reference_docs(root, findings)
    _check_workflow_routing_reference_docs(root, findings)
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
    _check_command_contract_template_defaults(root, findings)
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


def _check_fresh_target_workflow_smoke_test(root: Path, findings: list[PackFinding]) -> None:
    path = root / FRESH_TARGET_SMOKE_TEST_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_fresh_target_smoke_test_missing",
                f"missing fresh target workflow smoke test: {FRESH_TARGET_SMOKE_TEST_PATH}",
                FRESH_TARGET_SMOKE_TEST_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in FRESH_TARGET_SMOKE_TEST_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_fresh_target_smoke_test_incomplete",
            (
                f"{FRESH_TARGET_SMOKE_TEST_PATH} must cover fresh-folder env, init, verify, status, "
                f"next_actions, and target-local commands; missing phrase(s): {', '.join(missing)}"
            ),
            FRESH_TARGET_SMOKE_TEST_PATH,
        )
    )


def _check_dry_run_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / DRY_RUN_WORKFLOW_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_dry_run_workflow_missing",
                f"missing dry-run workflow script: {DRY_RUN_WORKFLOW_PATH}",
                DRY_RUN_WORKFLOW_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in DRY_RUN_WORKFLOW_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_dry_run_workflow_incomplete",
            (
                f"{DRY_RUN_WORKFLOW_PATH} must run the disposable fresh-target workflow through "
                f"product structuring, design authoring queues, and implementation gate preflight; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            DRY_RUN_WORKFLOW_PATH,
        )
    )


def _check_dry_run_golden_fixture(root: Path, findings: list[PackFinding]) -> None:
    fixture = root / DRY_RUN_GOLDEN_FIXTURE_PATH
    if not fixture.is_file():
        findings.append(
            PackFinding(
                "pack_dry_run_golden_fixture_missing",
                f"missing dry-run product-doc golden fixture: {DRY_RUN_GOLDEN_FIXTURE_PATH}",
                DRY_RUN_GOLDEN_FIXTURE_PATH,
            )
        )
        return
    fixture_text = _read_utf8_text_or_none(fixture)
    if fixture_text is not None:
        missing = [phrase for phrase in DRY_RUN_GOLDEN_FIXTURE_REQUIRED_PHRASES if phrase not in fixture_text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_dry_run_golden_fixture_incomplete",
                    (
                        f"{DRY_RUN_GOLDEN_FIXTURE_PATH} must exercise a realistic multi-acceptance PRD; "
                        f"missing phrase(s): {', '.join(missing)}"
                    ),
                    DRY_RUN_GOLDEN_FIXTURE_PATH,
                )
            )

    test = root / DRY_RUN_GOLDEN_TEST_PATH
    if not test.is_file():
        findings.append(
            PackFinding(
                "pack_dry_run_golden_test_missing",
                f"missing dry-run golden fixture test: {DRY_RUN_GOLDEN_TEST_PATH}",
                DRY_RUN_GOLDEN_TEST_PATH,
            )
        )
        return
    test_text = _read_utf8_text_or_none(test)
    if test_text is None:
        return
    missing = [phrase for phrase in DRY_RUN_GOLDEN_TEST_REQUIRED_PHRASES if phrase not in test_text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_dry_run_golden_test_incomplete",
            (
                f"{DRY_RUN_GOLDEN_TEST_PATH} must run dry-run against the realistic product-doc fixture; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            DRY_RUN_GOLDEN_TEST_PATH,
        )
    )


def _check_stack_acceptance_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / STACK_ACCEPTANCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_stack_acceptance_missing",
                f"missing stack acceptance script: {STACK_ACCEPTANCE_PATH}",
                STACK_ACCEPTANCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is not None:
        missing = [phrase for phrase in STACK_ACCEPTANCE_REQUIRED_PHRASES if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_stack_acceptance_incomplete",
                    (
                        f"{STACK_ACCEPTANCE_PATH} must gate real Python and Node acceptance with optional "
                        f"strict Rust enforcement; missing phrase(s): {', '.join(missing)}"
                    ),
                    STACK_ACCEPTANCE_PATH,
                )
            )

    test = root / STACK_ACCEPTANCE_TEST_PATH
    if not test.is_file():
        findings.append(
            PackFinding(
                "pack_stack_acceptance_test_missing",
                f"missing stack acceptance test: {STACK_ACCEPTANCE_TEST_PATH}",
                STACK_ACCEPTANCE_TEST_PATH,
            )
        )
        return
    test_text = _read_utf8_text_or_none(test)
    if test_text is None:
        return
    missing = [phrase for phrase in STACK_ACCEPTANCE_TEST_REQUIRED_PHRASES if phrase not in test_text]
    if missing:
        findings.append(
            PackFinding(
                "pack_stack_acceptance_test_incomplete",
                f"{STACK_ACCEPTANCE_TEST_PATH} must cover default and strict stack policy; missing phrase(s): {', '.join(missing)}",
                STACK_ACCEPTANCE_TEST_PATH,
            )
        )


def _check_source_pack_export_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / SOURCE_PACK_EXPORT_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_source_pack_export_missing",
                f"missing source-pack export script: {SOURCE_PACK_EXPORT_PATH}",
                SOURCE_PACK_EXPORT_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in SOURCE_PACK_EXPORT_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_source_pack_export_incomplete",
            (
                f"{SOURCE_PACK_EXPORT_PATH} must export a manifest-checked source workflow pack; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            SOURCE_PACK_EXPORT_PATH,
        )
    )


def _check_pack_manifest_verify_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / PACK_MANIFEST_VERIFY_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_manifest_verify_missing",
                f"missing pack manifest verifier script: {PACK_MANIFEST_VERIFY_PATH}",
                PACK_MANIFEST_VERIFY_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in PACK_MANIFEST_VERIFY_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_manifest_verify_incomplete",
            (
                f"{PACK_MANIFEST_VERIFY_PATH} must verify pack-manifest.json hashes, sizes, "
                f"executable flags, duplicates, invalid paths, and unmanifested files; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            PACK_MANIFEST_VERIFY_PATH,
        )
    )


def _check_consumer_bootstrap_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / CONSUMER_BOOTSTRAP_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_consumer_bootstrap_missing",
                f"missing consumer bootstrap script: {CONSUMER_BOOTSTRAP_PATH}",
                CONSUMER_BOOTSTRAP_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in CONSUMER_BOOTSTRAP_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_consumer_bootstrap_incomplete",
            (
                f"{CONSUMER_BOOTSTRAP_PATH} must compose source-pack verification, env/init "
                f"preflight, initialization, and target-local continuation checks; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            CONSUMER_BOOTSTRAP_PATH,
        )
    )


def _check_artifact_smoke_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / ARTIFACT_SMOKE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_artifact_smoke_missing",
                f"missing artifact smoke script: {ARTIFACT_SMOKE_PATH}",
                ARTIFACT_SMOKE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in ARTIFACT_SMOKE_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_artifact_smoke_incomplete",
            (
                f"{ARTIFACT_SMOKE_PATH} must unpack and smoke-test the exported workflow-pack artifact; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            ARTIFACT_SMOKE_PATH,
        )
    )


def _check_release_readiness_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / RELEASE_READINESS_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_release_readiness_missing",
                f"missing release readiness script: {RELEASE_READINESS_PATH}",
                RELEASE_READINESS_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in RELEASE_READINESS_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_release_readiness_incomplete",
            (
                f"{RELEASE_READINESS_PATH} must run the source workflow-pack release readiness gate; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            RELEASE_READINESS_PATH,
        )
    )


def _check_ci_workflow(root: Path, findings: list[PackFinding]) -> None:
    path = root / CI_WORKFLOW_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_ci_workflow_missing",
                f"missing GitHub Actions CI workflow: {CI_WORKFLOW_PATH}",
                CI_WORKFLOW_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in CI_WORKFLOW_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_ci_workflow_incomplete",
                (
                    f"{CI_WORKFLOW_PATH} must run the source workflow-pack CI baseline; "
                    f"missing phrase(s): {', '.join(missing)}"
                ),
                CI_WORKFLOW_PATH,
            )
        )
    automatic_triggers = [
        trigger.strip()
        for trigger in CI_WORKFLOW_FORBIDDEN_TRIGGERS
        if trigger in text
    ]
    if automatic_triggers:
        findings.append(
            PackFinding(
                "pack_ci_workflow_automatic_trigger",
                (
                    f"{CI_WORKFLOW_PATH} must remain manual-only; remove automatic trigger(s): "
                    f"{', '.join(automatic_triggers)}"
                ),
                CI_WORKFLOW_PATH,
            )
        )


def _check_authority_skill_inventory(root: Path, findings: list[PackFinding]) -> None:
    path = root / AUTHORITY_SKILL_INVENTORY_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_authority_skill_inventory_missing",
                f"missing authority-routing skill inventory script: {AUTHORITY_SKILL_INVENTORY_PATH}",
                AUTHORITY_SKILL_INVENTORY_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in AUTHORITY_SKILL_INVENTORY_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_authority_skill_inventory_incomplete",
            (
                f"{AUTHORITY_SKILL_INVENTORY_PATH} must inventory authority-routing specialist skills "
                f"from design and implementation routing sources; missing phrase(s): {', '.join(missing)}"
            ),
            AUTHORITY_SKILL_INVENTORY_PATH,
        )
    )


def _check_authority_skill_repair_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in AUTHORITY_SKILL_REPAIR_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_authority_skill_repair_doc_missing",
                    f"{rel} must document authority skill repair command or behavior: {phrase}",
                    rel,
                )
            )


def _check_authority_skill_lock(root: Path, findings: list[PackFinding]) -> None:
    path = root / AUTHORITY_SKILL_LOCK_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_authority_skill_lock_missing",
                f"missing authority-routing skill source lock: {AUTHORITY_SKILL_LOCK_PATH}",
                AUTHORITY_SKILL_LOCK_PATH,
            )
        )
        return
    if validate_authority_skill_lock is None:
        findings.append(
            PackFinding(
                "pack_authority_skill_lock_validator_unavailable",
                "authority skill lock validator is unavailable: "
                f"{AUTHORITY_SKILL_LOCK_VALIDATOR_IMPORT_ERROR or 'unknown import error'}",
                AUTHORITY_SKILL_INVENTORY_PATH,
            )
        )
        return
    validation = validate_authority_skill_lock(path)
    locked_names = set(validation["skill_names"])
    missing = sorted(AUTHORITY_ROUTING_SPECIALIST_SKILLS - locked_names)
    stale = sorted(locked_names - AUTHORITY_ROUTING_SPECIALIST_SKILLS)
    errors = list(validation["errors"])
    if missing:
        errors.append(f"missing authority-routing skill entries: {', '.join(missing)}")
    if stale:
        errors.append(f"stale authority-routing skill entries: {', '.join(stale)}")
    if not errors and not validation["source_unregistered_skills"]:
        return
    if errors:
        findings.append(
            PackFinding(
                "pack_authority_skill_lock_invalid",
                f"{AUTHORITY_SKILL_LOCK_PATH} is invalid: {'; '.join(errors)}",
                AUTHORITY_SKILL_LOCK_PATH,
            )
        )
        return
    findings.append(
        PackFinding(
            "pack_authority_skill_lock_unregistered",
            (
                f"{AUTHORITY_SKILL_LOCK_PATH} must register an approved immutable source for every authority skill; "
                f"unregistered: {', '.join(validation['source_unregistered_skills'])}"
            ),
            AUTHORITY_SKILL_LOCK_PATH,
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


def _check_generated_root_agents_contract(root: Path, findings: list[PackFinding]) -> None:
    rel = BOOTSTRAP_TREE_PATH.as_posix()
    text = _read_utf8_text_or_none(root / BOOTSTRAP_TREE_PATH)
    if text is None:
        return
    missing = [phrase for phrase in GENERATED_ROOT_AGENTS_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_generated_root_agents_contract_incomplete",
            f"scripts/bootstrap_tree.py must generate the Agent workflow startup contract; missing phrase(s): "
            f"{', '.join(missing)}",
            rel,
        )
    )


def _check_generated_root_agents_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in GENERATED_ROOT_AGENTS_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_generated_root_agents_doc_missing",
                f"{rel} must document the generated Agent workflow startup contract; missing phrase(s): "
                f"{', '.join(missing)}",
                rel,
            )
        )


def _check_target_local_command_source(root: Path, findings: list[PackFinding]) -> None:
    rel = BOOTSTRAP_TREE_PATH.as_posix()
    path = root / BOOTSTRAP_TREE_PATH
    if not path.is_file():
        return
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return
    entries = _sequence_tuple_literals(_top_level_assignment_value(tree, "TARGET_LOCAL_COMMANDS"))
    if not entries:
        findings.append(
            PackFinding(
                "pack_target_local_command_source_missing",
                "scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS must contain command tuples",
                rel,
            )
        )
        return
    seen: set[str] = set()
    targets: list[str] = []
    for index, entry in enumerate(entries):
        if len(entry.elts) != 4:
            findings.append(
                PackFinding(
                    "pack_target_local_command_source_invalid",
                    f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS entry {index} must have target, recipe, description, writes_state",
                    rel,
                )
            )
            continue
        target = _ast_string_literal(entry.elts[0])
        recipe = _ast_string_literal(entry.elts[1])
        description = _ast_string_literal(entry.elts[2])
        writes_state = _ast_bool_literal(entry.elts[3])
        if not target or not re.fullmatch(r"[A-Za-z0-9_.-]+", target):
            findings.append(
                PackFinding(
                    "pack_target_local_command_source_invalid",
                    f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS entry {index} target must be a non-empty make target",
                    rel,
                )
            )
        elif target in seen:
            findings.append(
                PackFinding(
                    "pack_target_local_command_source_invalid",
                    f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS target must be unique: {target}",
                    rel,
                )
            )
        else:
            seen.add(target)
            targets.append(target)
        if not recipe:
            findings.append(
                PackFinding(
                    "pack_target_local_command_source_invalid",
                    f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS entry {index} recipe must be a non-empty string",
                    rel,
                )
            )
        if not description:
            findings.append(
                PackFinding(
                    "pack_target_local_command_source_invalid",
                    f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS entry {index} description must be a non-empty string",
                    rel,
                )
            )
        if writes_state is None:
            findings.append(
                PackFinding(
                    "pack_target_local_command_source_invalid",
                    f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS entry {index} writes_state must be boolean",
                    rel,
                )
            )
    missing = [target for target in TARGET_LOCAL_COMMAND_REQUIRED_TARGETS if target not in targets]
    if missing:
        findings.append(
            PackFinding(
                "pack_target_local_command_source_missing",
                f"scripts/bootstrap_tree.py TARGET_LOCAL_COMMANDS missing target(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_target_local_command_schema(root: Path, findings: list[PackFinding]) -> None:
    rel = BOOTSTRAP_TREE_PATH.as_posix()
    path = root / BOOTSTRAP_TREE_PATH
    if not path.is_file():
        return
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return

    payload_items = _return_list_dict_literals(_find_function_def(tree, "target_local_commands_payload"))
    if not payload_items:
        findings.append(
            PackFinding(
                "pack_target_local_command_schema_missing",
                "scripts/bootstrap_tree.py target_local_commands_payload() must return command dicts",
                rel,
            )
        )
        return
    _check_target_local_command_dicts_have_keys(payload_items, rel, findings)
    _check_target_local_command_make_contract(payload_items, rel, findings)


def _check_target_local_command_dicts_have_keys(
    actions: list[ast.Dict],
    rel: str,
    findings: list[PackFinding],
) -> None:
    for index, action in enumerate(actions):
        keys = _dict_literal_keys(action)
        missing = [key for key in TARGET_LOCAL_COMMAND_PAYLOAD_REQUIRED_KEYS if key not in keys]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_target_local_command_schema_missing",
                f"scripts/bootstrap_tree.py target_local_commands_payload() item {index} missing key(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_target_local_command_make_contract(
    actions: list[ast.Dict],
    rel: str,
    findings: list[PackFinding],
) -> None:
    for index, action in enumerate(actions):
        if _target_local_command_matches_make_target(action):
            continue
        findings.append(
            PackFinding(
                "pack_target_local_command_command_mismatch",
                f"scripts/bootstrap_tree.py target_local_commands_payload() item {index} command and argv must match make_target",
                rel,
            )
        )


def _target_local_command_matches_make_target(action: ast.Dict) -> bool:
    make_target = _ast_name_id(_dict_literal_value(action, "make_target"))
    command = _dict_literal_value(action, "command")
    argv = _dict_literal_value(action, "argv")
    if make_target is None or command is None or argv is None:
        return True
    if not _ast_make_command_matches(command, make_target):
        return False
    return _ast_make_argv_matches(argv, make_target)


def _check_workflow_action_schema(root: Path, findings: list[PackFinding]) -> None:
    rel = WORKFLOW_ACTIONS_PATH.as_posix()
    path = root / WORKFLOW_ACTIONS_PATH
    if not path.is_file():
        return
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return

    constants = _top_level_string_constants(tree)
    product_conversion = _top_level_assignment_value(tree, "PRODUCT_CONVERSION_ACTIONS")
    conversion_actions = _sequence_dict_literals(product_conversion)
    if not conversion_actions:
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                "scripts/workflow_actions.py PRODUCT_CONVERSION_ACTIONS must contain action dicts",
                rel,
            )
        )
    else:
        _check_action_dicts_have_keys(
            conversion_actions,
            WORKFLOW_ACTION_SOURCE_REQUIRED_KEYS,
            "PRODUCT_CONVERSION_ACTIONS",
            rel,
            findings,
        )
        _check_action_pair_contract(conversion_actions, "PRODUCT_CONVERSION_ACTIONS", rel, findings)
        _check_action_command_contract(conversion_actions, "PRODUCT_CONVERSION_ACTIONS", rel, findings)
        for action in conversion_actions:
            _check_workflow_action_metadata_alignment(root, action, constants, rel, findings)

    product_import = _top_level_assignment_value(tree, "PRODUCT_IMPORT_ACTIONS")
    product_actions = _sequence_dict_literals(product_import)
    if not product_actions:
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                "scripts/workflow_actions.py PRODUCT_IMPORT_ACTIONS must contain action dicts",
                rel,
            )
        )
    else:
        _check_action_dicts_have_keys(
            product_actions,
            WORKFLOW_ACTION_SOURCE_REQUIRED_KEYS,
            "PRODUCT_IMPORT_ACTIONS",
            rel,
            findings,
        )
        _check_action_pair_contract(product_actions, "PRODUCT_IMPORT_ACTIONS", rel, findings)
        _check_action_command_contract(product_actions, "PRODUCT_IMPORT_ACTIONS", rel, findings)
        for action in product_actions:
            _check_workflow_action_metadata_alignment(root, action, constants, rel, findings)

    phase_actions = _top_level_assignment_value(tree, "PHASE_ACTIONS")
    phase_metadata = _dict_literal_values(phase_actions)
    if not phase_metadata:
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                "scripts/workflow_actions.py PHASE_ACTIONS must contain phase metadata dicts",
                rel,
            )
        )
    else:
        _check_action_dicts_have_keys(
            phase_metadata,
            WORKFLOW_ACTION_PHASE_METADATA_REQUIRED_KEYS,
            "PHASE_ACTIONS",
            rel,
            findings,
        )
        for phase, metadata in _dict_literal_string_items(phase_actions):
            _check_workflow_phase_action_metadata_alignment(root, phase, metadata, constants, rel, findings)

    advance_actions = _return_list_dict_literals(_find_function_def(tree, "_advance_actions"))
    if not advance_actions:
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                "scripts/workflow_actions.py _advance_actions() must return preflight/apply action dicts",
                rel,
            )
        )
    else:
        _check_action_dicts_have_keys(
            advance_actions,
            WORKFLOW_ACTION_PAYLOAD_REQUIRED_KEYS,
            "_advance_actions() return",
            rel,
            findings,
        )
        _check_action_pair_contract(advance_actions, "_advance_actions() return", rel, findings)
        _check_action_command_contract(advance_actions, "_advance_actions() return", rel, findings)

    copy_actions = _find_function_def(tree, "_copy_actions")
    if copy_actions is None or not _function_assigns_subscript_key(copy_actions, "action", "cwd"):
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                "scripts/workflow_actions.py _copy_actions() must add cwd to copied product import actions",
                rel,
            )
        )


def _check_action_dicts_have_keys(
    actions: list[ast.Dict],
    required_keys: tuple[str, ...],
    label: str,
    rel: str,
    findings: list[PackFinding],
) -> None:
    for index, action in enumerate(actions):
        keys = _dict_literal_keys(action)
        missing = [key for key in required_keys if key not in keys]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                f"scripts/workflow_actions.py {label} action {index} missing key(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_action_pair_contract(
    actions: list[ast.Dict],
    label: str,
    rel: str,
    findings: list[PackFinding],
) -> None:
    if len(actions) < 2:
        findings.append(
            PackFinding(
                "pack_workflow_action_schema_missing",
                f"scripts/workflow_actions.py {label} must contain preflight and apply actions",
                rel,
            )
        )
        return
    expected = (
        (0, "preflight", False),
        (1, "apply", True),
    )
    for index, expected_kind, expected_writes_state in expected:
        action = actions[index]
        kind = _dict_literal_string_value(action, "kind")
        writes_state = _dict_literal_bool_value(action, "writes_state")
        sequence = _dict_literal_int_value(action, "sequence")
        success_condition = _dict_literal_string_value(action, "success_condition")
        if not (
            kind == expected_kind
            and writes_state is expected_writes_state
            and sequence == index + 1
            and success_condition == "ok:true"
        ):
            findings.append(
                PackFinding(
                    "pack_workflow_action_schema_missing",
                    (
                        f"scripts/workflow_actions.py {label} action {index} must be {expected_kind} "
                        f"with writes_state {expected_writes_state}, sequence {index + 1}, "
                        "and success_condition ok:true"
                    ),
                    rel,
                )
            )
        if expected_kind == "preflight" and "preflight_for" not in _dict_literal_keys(action):
            findings.append(
                PackFinding(
                    "pack_workflow_action_schema_missing",
                    f"scripts/workflow_actions.py {label} action {index} must include preflight_for",
                    rel,
                )
            )
        if expected_kind == "apply" and "requires_action" not in _dict_literal_keys(action):
            findings.append(
                PackFinding(
                    "pack_workflow_action_schema_missing",
                    f"scripts/workflow_actions.py {label} action {index} must include requires_action",
                    rel,
                )
            )


def _check_action_command_contract(
    actions: list[ast.Dict],
    label: str,
    rel: str,
    findings: list[PackFinding],
) -> None:
    for index, action in enumerate(actions):
        if _action_command_matches_argv(action):
            continue
        findings.append(
            PackFinding(
                "pack_workflow_action_command_mismatch",
                f"scripts/workflow_actions.py {label} action {index} command must match argv",
                rel,
            )
        )


def _action_command_matches_argv(action: ast.Dict) -> bool:
    command = _dict_literal_value(action, "command")
    argv = _dict_literal_value(action, "argv")
    if command is None or argv is None:
        return True

    command_text = _ast_static_string(command, {})
    argv_sequence = _ast_string_sequence(argv)
    if command_text is not None and argv_sequence is not None:
        return command_text == " ".join(argv_sequence)

    if not isinstance(command, ast.Call):
        return False
    if not isinstance(command.func, ast.Name) or command.func.id != "_command_text":
        return False
    if len(command.args) != 1:
        return False
    return _ast_name_id(command.args[0]) == _ast_name_id(argv)


def _check_workflow_action_metadata_alignment(
    root: Path,
    action: ast.Dict,
    constants: dict[str, str],
    rel: str,
    findings: list[PackFinding],
) -> None:
    phase = _dict_literal_string_value(action, "phase")
    if phase is None:
        return
    _check_workflow_action_alignment(root, phase, action, constants, rel, findings)


def _check_workflow_phase_action_metadata_alignment(
    root: Path,
    phase: str,
    metadata: ast.Dict,
    constants: dict[str, str],
    rel: str,
    findings: list[PackFinding],
) -> None:
    _check_workflow_action_alignment(root, phase, metadata, constants, rel, findings)


def _check_workflow_action_alignment(
    root: Path,
    phase: str,
    metadata: ast.Dict,
    constants: dict[str, str],
    rel: str,
    findings: list[PackFinding],
) -> None:
    expected_workflow = WORKFLOW_ACTION_PHASE_WORKFLOWS.get(phase)
    if expected_workflow is None:
        return
    workflow = _workflow_action_rel(_dict_literal_static_string_value(metadata, "workflow", constants), constants)
    if workflow != expected_workflow:
        findings.append(
            PackFinding(
                "pack_workflow_action_workflow_mismatch",
                f"scripts/workflow_actions.py action phase {phase} must reference {expected_workflow}",
                rel,
            )
        )

    expected_skills = _workflow_action_expected_skills(root, expected_workflow)
    if not expected_skills:
        return
    skills = _dict_literal_string_sequence_value(metadata, "skills")
    missing = [skill for skill in expected_skills if skill not in skills]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_workflow_action_skill_mismatch",
            f"scripts/workflow_actions.py action phase {phase} must include skill(s): {', '.join(missing)}",
            rel,
        )
    )


def _workflow_action_expected_skills(root: Path, expected_workflow: str) -> list[str]:
    try:
        overview_text = (root / "workflows/00-overview.md").read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    phase_map = _phase_map_primary_skills(_markdown_section(overview_text, "Phase Map") or "")
    phase_number = Path(expected_workflow).name.split("-", 1)[0]
    skills = list(phase_map.get(phase_number, []))
    for skill in WORKFLOW_ACTION_REQUIRED_SUPPORT_SKILLS:
        if skill not in skills:
            skills.append(skill)
    return skills


def _workflow_action_rel(value: str | None, constants: dict[str, str]) -> str:
    if value is None:
        return ""
    target_root = constants.get("TARGET_WORKFLOW_ROOT", "docs/agent-workflow/workflow-pack")
    prefix = f"{target_root}/"
    if value.startswith(prefix):
        return value[len(prefix) :]
    return value


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


def _top_level_assignment_value(tree: ast.AST, name: str) -> ast.AST | None:
    if not isinstance(tree, ast.Module):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return node.value
    return None


def _top_level_string_constants(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    if not isinstance(tree, ast.Module):
        return constants
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = _ast_string_literal(node.value)
            if value is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = _ast_string_literal(node.value)
            if value is not None:
                constants[node.target.id] = value
    return constants


def _sequence_dict_literals(node: ast.AST | None) -> list[ast.Dict]:
    if not isinstance(node, ast.Tuple | ast.List):
        return []
    return [element for element in node.elts if isinstance(element, ast.Dict)]


def _sequence_tuple_literals(node: ast.AST | None) -> list[ast.Tuple | ast.List]:
    if not isinstance(node, ast.Tuple | ast.List):
        return []
    return [element for element in node.elts if isinstance(element, ast.Tuple | ast.List)]


def _dict_literal_values(node: ast.AST | None) -> list[ast.Dict]:
    if not isinstance(node, ast.Dict):
        return []
    return [value for value in node.values if isinstance(value, ast.Dict)]


def _dict_literal_string_items(node: ast.AST | None) -> list[tuple[str, ast.Dict]]:
    if not isinstance(node, ast.Dict):
        return []
    items: list[tuple[str, ast.Dict]] = []
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(value, ast.Dict):
            items.append((key.value, value))
    return items


def _return_list_dict_literals(function: ast.FunctionDef | None) -> list[ast.Dict]:
    if function is None:
        return []
    for node in ast.walk(function):
        if not isinstance(node, ast.Return):
            continue
        if isinstance(node.value, ast.ListComp) and isinstance(node.value.elt, ast.Dict):
            return [node.value.elt]
        actions = _sequence_dict_literals(node.value)
        if actions:
            return actions
    return []


def _dict_literal_keys(node: ast.Dict) -> set[str]:
    return {key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}


def _dict_literal_value(node: ast.Dict, key_name: str) -> ast.AST | None:
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and key.value == key_name:
            return value
    return None


def _dict_literal_string_value(node: ast.Dict, key_name: str) -> str | None:
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or key.value != key_name:
            continue
        return _ast_string_literal(value)
    return None


def _dict_literal_static_string_value(
    node: ast.Dict,
    key_name: str,
    constants: dict[str, str],
) -> str | None:
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or key.value != key_name:
            continue
        return _ast_static_string(value, constants)
    return None


def _dict_literal_string_sequence_value(node: ast.Dict, key_name: str) -> tuple[str, ...]:
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or key.value != key_name:
            continue
        sequence = _ast_string_sequence(value)
        return sequence if sequence is not None else ()
    return ()


def _dict_literal_bool_value(node: ast.Dict, key_name: str) -> bool | None:
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or key.value != key_name:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, bool):
            return value.value
    return None


def _dict_literal_int_value(node: ast.Dict, key_name: str) -> int | None:
    for key, value in zip(node.keys, node.values):
        if not isinstance(key, ast.Constant) or key.value != key_name:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, int) and not isinstance(value.value, bool):
            return value.value
    return None


def _function_assigns_subscript_key(function: ast.FunctionDef, name: str, key_name: str) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Name) or target.value.id != name:
                continue
            if _ast_string_literal(target.slice) == key_name:
                return True
    return False


def _ast_name_id(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _ast_make_command_matches(node: ast.AST, target_name: str) -> bool:
    if not isinstance(node, ast.JoinedStr) or len(node.values) != 2:
        return False
    prefix, formatted = node.values
    if not isinstance(prefix, ast.Constant) or prefix.value != "make ":
        return False
    if not isinstance(formatted, ast.FormattedValue):
        return False
    return _ast_name_id(formatted.value) == target_name


def _ast_make_argv_matches(node: ast.AST, target_name: str) -> bool:
    if not isinstance(node, ast.List | ast.Tuple) or len(node.elts) != 2:
        return False
    command, target = node.elts
    if not isinstance(command, ast.Constant) or command.value != "make":
        return False
    return _ast_name_id(target) == target_name


def _ast_static_string(node: ast.AST, constants: dict[str, str]) -> str | None:
    literal = _ast_string_literal(node)
    if literal is not None:
        return literal
    if not isinstance(node, ast.JoinedStr):
        return None
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
            resolved = constants.get(value.value.id)
            if resolved is None:
                return None
            parts.append(resolved)
        else:
            return None
    return "".join(parts)


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


def _ast_bool_literal(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _check_runtime_executable_bits(root: Path, findings: list[PackFinding]) -> None:
    for rel_path in (*RUNTIME_EXECUTABLE_PATHS, Path(CONSUMER_BOOTSTRAP_WRAPPER_PATH)):
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


def _check_readme_artifact_consumer_quick_start(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if not readme.is_file():
        return
    text = _read_utf8_text_or_none(readme)
    if text is None:
        return
    section = _markdown_section(text, "Artifact Consumer Quick Start") or ""
    if not section:
        findings.append(
            PackFinding(
                "pack_artifact_consumer_quick_start_missing",
                "README.md must document Artifact Consumer Quick Start",
                "README.md",
            )
        )
        return
    for phrase in README_ARTIFACT_CONSUMER_QUICK_START_REQUIRED_PHRASES:
        haystack = text if phrase.startswith("## ") else section
        if phrase in haystack:
            continue
        findings.append(
            PackFinding(
                "pack_artifact_consumer_quick_start_missing",
                f"README.md Artifact Consumer Quick Start must document: {phrase}",
                "README.md",
            )
        )


def _check_dry_run_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in DRY_RUN_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_dry_run_doc_missing",
                    f"{rel} must document source-pack dry-run command or behavior: {phrase}",
                    rel,
                )
            )


def _check_stack_acceptance_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in STACK_ACCEPTANCE_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_stack_acceptance_doc_missing",
                    f"{rel} must document real stack acceptance command or behavior: {phrase}",
                    rel,
                )
            )


def _check_source_pack_export_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in SOURCE_PACK_EXPORT_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_source_pack_export_doc_missing",
                    f"{rel} must document source-pack export command or behavior: {phrase}",
                    rel,
                )
            )


def _check_pack_manifest_verify_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in PACK_MANIFEST_VERIFY_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_manifest_verify_doc_missing",
                    f"{rel} must document pack manifest verification command or behavior: {phrase}",
                    rel,
                )
            )


def _check_artifact_smoke_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in ARTIFACT_SMOKE_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_artifact_smoke_doc_missing",
                    f"{rel} must document artifact smoke command or behavior: {phrase}",
                    rel,
                )
            )


def _check_consumer_bootstrap_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in CONSUMER_BOOTSTRAP_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_consumer_bootstrap_doc_missing",
                    f"{rel} must document consumer bootstrap command or behavior: {phrase}",
                    rel,
                )
            )


def _check_release_readiness_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in RELEASE_READINESS_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        for phrase in required_phrases:
            if phrase in text:
                continue
            findings.append(
                PackFinding(
                    "pack_release_readiness_doc_missing",
                    f"{rel} must document release readiness command or behavior: {phrase}",
                    rel,
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


def _check_runtime_refresh_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in RUNTIME_REFRESH_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_runtime_refresh_doc_missing",
                f"{rel} must document runtime refresh phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_runtime_refresh_test_coverage(root: Path, findings: list[PackFinding]) -> None:
    path = root / RUNTIME_REFRESH_TEST_PATH
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in RUNTIME_REFRESH_TEST_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_runtime_refresh_test_missing",
            f"{RUNTIME_REFRESH_TEST_PATH} must cover runtime refresh continuation phrase(s): {', '.join(missing)}",
            RUNTIME_REFRESH_TEST_PATH,
        )
    )


def _check_product_conversion_source(root: Path, findings: list[PackFinding]) -> None:
    text = _read_utf8_text_or_none(root / PRODUCT_CONVERSION_SOURCE_PATH)
    if text is None:
        return
    missing = [
        phrase
        for phrase in PRODUCT_CONVERSION_SOURCE_REQUIRED_PHRASES
        if phrase not in text
    ]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_product_conversion_incomplete",
            f"{PRODUCT_CONVERSION_SOURCE_PATH} must preserve bounded conversion, evidence, and review gates; "
            f"missing phrase(s): {', '.join(missing)}",
            PRODUCT_CONVERSION_SOURCE_PATH,
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


def _check_product_disposition_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / PRODUCT_DISPOSITION_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_product_disposition_source_missing",
                f"missing product disposition source script: {PRODUCT_DISPOSITION_SOURCE_PATH}",
                PRODUCT_DISPOSITION_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in PRODUCT_DISPOSITION_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_product_disposition_source_incomplete",
                (
                    f"{PRODUCT_DISPOSITION_SOURCE_PATH} must preserve reviewed source-bound product decisions; "
                    f"missing phrase(s): {', '.join(missing)}"
                ),
                PRODUCT_DISPOSITION_SOURCE_PATH,
            )
        )


def _check_product_disposition_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, phrases in PRODUCT_DISPOSITION_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_product_disposition_doc_missing",
                    f"{rel} must document product disposition phrase(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_design_review_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / DESIGN_REVIEW_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_design_review_source_missing",
                f"missing design review source script: {DESIGN_REVIEW_SOURCE_PATH}",
                DESIGN_REVIEW_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in DESIGN_REVIEW_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_design_review_source_incomplete",
                (
                    f"{DESIGN_REVIEW_SOURCE_PATH} must preserve source-, evidence-, and authority-bound "
                    f"design review enforcement; missing phrase(s): {', '.join(missing)}"
                ),
                DESIGN_REVIEW_SOURCE_PATH,
            )
        )


def _check_design_review_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, phrases in DESIGN_REVIEW_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_design_review_doc_missing",
                    f"{rel} must document design review phrase(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_api_review_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / API_REVIEW_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_api_review_source_missing",
                f"missing API machine-review source script: {API_REVIEW_SOURCE_PATH}",
                API_REVIEW_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in API_REVIEW_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_api_review_source_incomplete",
                (
                    f"{API_REVIEW_SOURCE_PATH} must preserve authority-tool execution and hash-bound "
                    f"OpenAPI evidence; missing phrase(s): {', '.join(missing)}"
                ),
                API_REVIEW_SOURCE_PATH,
            )
        )


def _check_api_review_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, phrases in API_REVIEW_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_api_review_doc_missing",
                    f"{rel} must document API machine-review phrase(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_threat_review_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / THREAT_REVIEW_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_threat_review_source_missing",
                f"missing architecture threat-review source script: {THREAT_REVIEW_SOURCE_PATH}",
                THREAT_REVIEW_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in THREAT_REVIEW_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_threat_review_source_incomplete",
                (
                    f"{THREAT_REVIEW_SOURCE_PATH} must preserve authority-tool execution and hash-bound "
                    f"STRIDE/DREAD evidence; missing phrase(s): {', '.join(missing)}"
                ),
                THREAT_REVIEW_SOURCE_PATH,
            )
        )


def _check_threat_review_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, phrases in THREAT_REVIEW_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_threat_review_doc_missing",
                    f"{rel} must document architecture threat-review phrase(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_reliability_review_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / RELIABILITY_REVIEW_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_reliability_review_source_missing",
                f"missing backend reliability-review source script: {RELIABILITY_REVIEW_SOURCE_PATH}",
                RELIABILITY_REVIEW_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in RELIABILITY_REVIEW_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_reliability_review_source_incomplete",
                (
                    f"{RELIABILITY_REVIEW_SOURCE_PATH} must preserve authority-tool execution and hash-bound "
                    f"SLO/error-budget evidence; missing phrase(s): {', '.join(missing)}"
                ),
                RELIABILITY_REVIEW_SOURCE_PATH,
            )
        )


def _check_reliability_review_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, phrases in RELIABILITY_REVIEW_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_reliability_review_doc_missing",
                    f"{rel} must document backend reliability-review phrase(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_migration_review_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / MIGRATION_REVIEW_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_migration_review_source_missing",
                f"missing data-model migration-review source script: {MIGRATION_REVIEW_SOURCE_PATH}",
                MIGRATION_REVIEW_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in MIGRATION_REVIEW_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if missing:
        findings.append(
            PackFinding(
                "pack_migration_review_source_incomplete",
                (
                    f"{MIGRATION_REVIEW_SOURCE_PATH} must preserve authority-tool execution and hash-bound "
                    f"schema/migration evidence; missing phrase(s): {', '.join(missing)}"
                ),
                MIGRATION_REVIEW_SOURCE_PATH,
            )
        )


def _check_migration_review_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, phrases in MIGRATION_REVIEW_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in phrases if phrase not in text]
        if missing:
            findings.append(
                PackFinding(
                    "pack_migration_review_doc_missing",
                    f"{rel} must document data-model migration-review phrase(s): {', '.join(missing)}",
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


def _check_design_plan_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in DESIGN_PLAN_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in DESIGN_PLAN_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_design_plan_doc_missing",
                f"{rel} must document design plan phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_design_plan_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / DESIGN_PLAN_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_design_plan_source_missing",
                f"missing design plan source script: {DESIGN_PLAN_SOURCE_PATH}",
                DESIGN_PLAN_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in DESIGN_PLAN_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_design_plan_source_incomplete",
            (
                f"{DESIGN_PLAN_SOURCE_PATH} must preserve design track authority-skill routing "
                f"and stop-before-guessing missing policies; missing phrase(s): {', '.join(missing)}"
            ),
            DESIGN_PLAN_SOURCE_PATH,
        )
    )


def _check_project_environment_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / PROJECT_ENVIRONMENT_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_project_environment_source_missing",
                f"missing project environment contract source: {PROJECT_ENVIRONMENT_SOURCE_PATH}",
                PROJECT_ENVIRONMENT_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [
        phrase for phrase in PROJECT_ENVIRONMENT_SOURCE_REQUIRED_PHRASES if phrase not in text
    ]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_project_environment_source_incomplete",
            (
                f"{PROJECT_ENVIRONMENT_SOURCE_PATH} must preserve strict schema validation, safe version probes, "
                f"numeric version constraints, reviewed repair sources, and duplicate-key rejection; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            PROJECT_ENVIRONMENT_SOURCE_PATH,
        )
    )


def _check_bounded_process_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / BOUNDED_PROCESS_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_bounded_process_source_missing",
                f"missing shared bounded process source: {BOUNDED_PROCESS_SOURCE_PATH}",
                BOUNDED_PROCESS_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [
        phrase for phrase in BOUNDED_PROCESS_SOURCE_REQUIRED_PHRASES if phrase not in text
    ]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_bounded_process_source_incomplete",
            (
                f"{BOUNDED_PROCESS_SOURCE_PATH} must preserve no-shell bounded execution, "
                f"process-group timeout handling, output limits, and credential redaction; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            BOUNDED_PROCESS_SOURCE_PATH,
        )
    )


def _check_implementation_run_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / IMPLEMENTATION_RUN_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_implementation_run_source_missing",
                f"missing guarded implementation runner source: {IMPLEMENTATION_RUN_SOURCE_PATH}",
                IMPLEMENTATION_RUN_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in IMPLEMENTATION_RUN_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_implementation_run_source_incomplete",
            (
                f"{IMPLEMENTATION_RUN_SOURCE_PATH} must preserve snapshot-guarded claim/edit separation, "
                f"all-command preflight, bounded sequential execution, registered repair approval, locking, "
                f"and evidence-gated closeout; missing phrase(s): {', '.join(missing)}"
            ),
            IMPLEMENTATION_RUN_SOURCE_PATH,
        )
    )


def _check_implementation_run_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in IMPLEMENTATION_RUN_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_implementation_run_doc_missing",
                f"{rel} must document guarded implementation runner phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_implementation_review_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / IMPLEMENTATION_REVIEW_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_implementation_review_source_missing",
                f"missing implementation review evidence source: {IMPLEMENTATION_REVIEW_SOURCE_PATH}",
                IMPLEMENTATION_REVIEW_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [
        phrase for phrase in IMPLEMENTATION_REVIEW_SOURCE_REQUIRED_PHRASES if phrase not in text
    ]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_implementation_review_source_incomplete",
            (
                f"{IMPLEMENTATION_REVIEW_SOURCE_PATH} must preserve Git-backed task baselines, complete "
                "change-set hashing, authority provenance, structured reports, and stale-evidence checks; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            IMPLEMENTATION_REVIEW_SOURCE_PATH,
        )
    )


def _check_implementation_review_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in IMPLEMENTATION_REVIEW_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_implementation_review_doc_missing",
                f"{rel} must document implementation review phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_implementation_verify_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / IMPLEMENTATION_VERIFY_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_implementation_verify_source_missing",
                f"missing implementation verification source script: {IMPLEMENTATION_VERIFY_SOURCE_PATH}",
                IMPLEMENTATION_VERIFY_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in IMPLEMENTATION_VERIFY_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_implementation_verify_source_incomplete",
            (
                f"{IMPLEMENTATION_VERIFY_SOURCE_PATH} must preserve structured no-shell execution, approval and write "
                f"gates, executable environment preflight and non-guessing repair routing, bounded timeout evidence, "
                f"upserted summaries, and atomic post-write verification; "
                f"missing phrase(s): {', '.join(missing)}"
            ),
            IMPLEMENTATION_VERIFY_SOURCE_PATH,
        )
    )


def _check_implementation_verify_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in IMPLEMENTATION_VERIFY_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_implementation_verify_doc_missing",
                f"{rel} must document implementation verification phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_work_package_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / WORK_PACKAGE_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_work_package_source_missing",
                f"missing workflow work-package source script: {WORK_PACKAGE_SOURCE_PATH}",
                WORK_PACKAGE_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in WORK_PACKAGE_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_work_package_source_incomplete",
            (
                f"{WORK_PACKAGE_SOURCE_PATH} must preserve single-work-package routing, skill readiness, "
                f"scope, and continuation contracts; missing phrase(s): {', '.join(missing)}"
            ),
            WORK_PACKAGE_SOURCE_PATH,
        )
    )


def _check_work_package_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in WORK_PACKAGE_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_work_package_doc_missing",
                f"{rel} must document workflow work-package phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_workflow_resume_source(root: Path, findings: list[PackFinding]) -> None:
    path = root / WORKFLOW_RESUME_SOURCE_PATH
    if not path.is_file():
        findings.append(
            PackFinding(
                "pack_workflow_resume_source_missing",
                f"missing workflow resume source script: {WORKFLOW_RESUME_SOURCE_PATH}",
                WORKFLOW_RESUME_SOURCE_PATH,
            )
        )
        return
    text = _read_utf8_text_or_none(path)
    if text is None:
        return
    missing = [phrase for phrase in WORKFLOW_RESUME_SOURCE_REQUIRED_PHRASES if phrase not in text]
    if not missing:
        return
    findings.append(
        PackFinding(
            "pack_workflow_resume_source_incomplete",
            (
                f"{WORKFLOW_RESUME_SOURCE_PATH} must preserve single-action routing, stale-snapshot rejection, "
                f"declared-input evidence, and approval stop conditions; missing phrase(s): {', '.join(missing)}"
            ),
            WORKFLOW_RESUME_SOURCE_PATH,
        )
    )


def _check_workflow_resume_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel, required_phrases in WORKFLOW_RESUME_DOC_REQUIREMENTS.items():
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_workflow_resume_doc_missing",
                f"{rel} must document workflow resume phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_api_candidates_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in API_CANDIDATES_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in API_CANDIDATES_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_api_candidates_doc_missing",
                f"{rel} must document API candidate phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_api_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in API_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in API_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_api_authoring_doc_missing",
                f"{rel} must document API authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_architecture_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in ARCHITECTURE_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        required_phrases = (
            ARCHITECTURE_AUTHORING_SKILL_REQUIRED_PHRASES
            if rel == ARCHITECTURE_AUTHORING_SKILL_PATH
            else ARCHITECTURE_AUTHORING_REQUIRED_PHRASES
        )
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_architecture_authoring_doc_missing",
                f"{rel} must document architecture authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_backend_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in BACKEND_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        required_phrases = (
            BACKEND_AUTHORING_SKILL_REQUIRED_PHRASES
            if rel == BACKEND_AUTHORING_SKILL_PATH
            else BACKEND_AUTHORING_REQUIRED_PHRASES
        )
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_backend_authoring_doc_missing",
                f"{rel} must document backend authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_data_model_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in DATA_MODEL_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in DATA_MODEL_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_data_model_authoring_doc_missing",
                f"{rel} must document data model authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_ui_interaction_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in UI_INTERACTION_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in UI_INTERACTION_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_ui_interaction_authoring_doc_missing",
                f"{rel} must document UI interaction authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_frontend_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in FRONTEND_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in FRONTEND_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_frontend_authoring_doc_missing",
                f"{rel} must document frontend authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_test_strategy_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in TEST_STRATEGY_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in TEST_STRATEGY_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_test_strategy_authoring_doc_missing",
                f"{rel} must document test strategy authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_implementation_planning_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in IMPLEMENTATION_PLANNING_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in IMPLEMENTATION_PLANNING_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_implementation_planning_authoring_doc_missing",
                f"{rel} must document implementation planning authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_architecture_decisions_authoring_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in ARCHITECTURE_DECISIONS_AUTHORING_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in ARCHITECTURE_DECISIONS_AUTHORING_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_architecture_decisions_authoring_doc_missing",
                f"{rel} must document architecture decisions authoring phrase(s): {', '.join(missing)}",
                rel,
            )
        )


def _check_scaffold_continuation_docs(root: Path, findings: list[PackFinding]) -> None:
    for rel in SCAFFOLD_CONTINUATION_DOC_PATHS:
        text = _read_utf8_text_or_none(root / rel)
        if text is None:
            continue
        missing = [phrase for phrase in SCAFFOLD_CONTINUATION_REQUIRED_PHRASES if phrase not in text]
        if not missing:
            continue
        findings.append(
            PackFinding(
                "pack_scaffold_continuation_doc_missing",
                f"{rel} must document scaffold continuation phrase(s): {', '.join(missing)}",
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


def _check_initialization_reference_docs(root: Path, findings: list[PackFinding]) -> None:
    for reference, consumers in INITIALIZATION_REFERENCE_DOC_REQUIREMENTS:
        for rel in consumers:
            text = _read_utf8_text_or_none(root / rel)
            if text is None or reference in text:
                continue
            findings.append(
                PackFinding(
                    "pack_initialization_reference_doc_missing",
                    f"{rel} must route repository initialization through reference document: {reference}",
                    rel,
                )
            )


def _check_verification_reference_docs(root: Path, findings: list[PackFinding]) -> None:
    for reference, consumers in VERIFICATION_REFERENCE_DOC_REQUIREMENTS:
        for rel in consumers:
            text = _read_utf8_text_or_none(root / rel)
            if text is None or reference in text:
                continue
            findings.append(
                PackFinding(
                    "pack_verification_reference_doc_missing",
                    f"{rel} must route governance verification through reference document: {reference}",
                    rel,
                )
            )


def _check_implementation_reference_docs(root: Path, findings: list[PackFinding]) -> None:
    for reference, consumers in IMPLEMENTATION_REFERENCE_DOC_REQUIREMENTS:
        for rel in consumers:
            text = _read_utf8_text_or_none(root / rel)
            if text is None or reference in text:
                continue
            findings.append(
                PackFinding(
                    "pack_implementation_reference_doc_missing",
                    f"{rel} must route implementation execution through reference document: {reference}",
                    rel,
                )
            )


def _check_product_reference_docs(root: Path, findings: list[PackFinding]) -> None:
    for reference, consumers in PRODUCT_REFERENCE_DOC_REQUIREMENTS:
        for rel in consumers:
            text = _read_utf8_text_or_none(root / rel)
            if text is None or reference in text:
                continue
            findings.append(
                PackFinding(
                    "pack_product_reference_doc_missing",
                    f"{rel} must route product workflow through reference document: {reference}",
                    rel,
                )
            )


def _check_workflow_routing_reference_docs(root: Path, findings: list[PackFinding]) -> None:
    for reference, consumers in WORKFLOW_ROUTING_REFERENCE_DOC_REQUIREMENTS:
        for rel in consumers:
            text = _read_utf8_text_or_none(root / rel)
            if text is None or reference in text:
                continue
            findings.append(
                PackFinding(
                    "pack_workflow_routing_reference_doc_missing",
                    f"{rel} must route workflow selection and continuation through reference document: {reference}",
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
            if skill in skill_names or skill in AUTHORITY_ROUTING_SPECIALIST_SKILLS:
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


def _check_command_contract_template_defaults(root: Path, findings: list[PackFinding]) -> None:
    rel = "templates/docs/agent-workflow/command-contract.md"
    path = root / rel
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    section = _markdown_section(text, "Command Table")
    if section is None:
        return
    rows = _markdown_table_records(section)
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        name = row.get("Name", "").strip()
        if name:
            rows_by_name.setdefault(name, []).append(row)
    for target, recipe, description, writes_state in TARGET_LOCAL_COMMANDS:
        matching_rows = rows_by_name.get(target, [])
        if not matching_rows:
            findings.append(
                PackFinding(
                    "pack_command_contract_template_command_drift",
                    f"{rel} Command Table missing default command row: {target}",
                    rel,
                )
            )
            continue
        if len(matching_rows) > 1:
            findings.append(
                PackFinding(
                    "pack_command_contract_template_command_drift",
                    f"{rel} Command Table default command row must be unique: {target}",
                    rel,
                )
            )
        _check_command_contract_template_row(
            rel,
            target,
            matching_rows[0],
            recipe,
            description,
            writes_state,
            findings,
        )


def _check_command_contract_template_row(
    rel: str,
    target: str,
    row: dict[str, str],
    recipe: str,
    description: str,
    writes_state: bool,
    findings: list[PackFinding],
) -> None:
    expected_cells = {
        "Purpose": _sentence_case(description),
        "Cwd": "`.`",
        "Writes State": str(writes_state).lower(),
        "Approval Required": "false",
        "Evidence": _command_contract_evidence(target),
        "Environment": "core-governance",
    }
    for column, expected in expected_cells.items():
        actual = row.get(column, "").strip()
        if actual == expected:
            continue
        findings.append(
            PackFinding(
                "pack_command_contract_template_command_drift",
                f"{rel} Command Table row {target} has {column}={actual!r}; expected {expected!r}",
                rel,
            )
        )
    expected_argv = shlex.split(recipe)
    actual_argv_text = _strip_markdown_code_span(row.get("Argv", ""))
    try:
        actual_argv = json.loads(actual_argv_text)
    except json.JSONDecodeError:
        actual_argv = None
    if actual_argv != expected_argv:
        findings.append(
            PackFinding(
                "pack_command_contract_template_command_drift",
                f"{rel} Command Table row {target} has Argv={actual_argv_text!r}; expected {json.dumps(expected_argv)!r}",
                rel,
            )
        )


def _markdown_table_records(text: str) -> list[dict[str, str]]:
    table_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("|") and line.strip().endswith("|")
    ]
    if len(table_lines) < 2:
        return []
    header = _markdown_table_cells(table_lines[0])
    if not header:
        return []
    records: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = _markdown_table_cells(line)
        if len(cells) != len(header):
            continue
        records.append(dict(zip(header, cells, strict=True)))
    return records


def _markdown_table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _strip_markdown_code_span(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1].strip()
    return value


def _sentence_case(text: str) -> str:
    text = text.strip().rstrip(".")
    return f"{text[:1].upper()}{text[1:]}." if text else ""


def _command_contract_evidence(target: str) -> str:
    if target == "repair-env-check":
        return "`.governance/env-repair.md` when repair is written"
    return "`docs/development/03-verification-log.md`"


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
