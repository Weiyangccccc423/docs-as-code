# Workflow Routing Checklist

Use this checklist when starting, resuming, or recovering a docs-as-code governance workflow from an empty, partially governed, or drifted repository.

Calibrate against explicit process modeling, machine-readable JSON contracts, schema discipline, and normative requirement language. The target-local governance CLI remains the executable authority for gates, actions, and verification findings.

## Entry Classification

- Is the target state classified from current files and governance state rather than from conversation memory?
- Is an empty or missing-governance target routed to `initializing-governance-repo`?
- Is an unarchived or conversion-required product source routed to `archiving-product-document`?
- For TXT/DOCX/HTML/PDF, does `workflow resume` select the guarded `product-convert` sequence until `product_conversion_status` becomes `pending_review`, then select `product-mark-ready` with the recorded `review_method`?
- If Pandoc is missing, does conversion preflight return the operation-scoped `--require-tool pandoc` repair route and stop before target writes when approval/manual repair is required?
- Does PDF route only through reviewed Poppler `pdftotext` extraction and remain stopped for source-fidelity review before product readiness?
- Is a reviewed PRD without sourced product chapters routed to `structuring-product-requirements`?
- Is structured product with acceptance criteria routed through design skills in the Phase Map order?
- Is a repository with a passing implementation gate and one selected `Ready` or `In Progress` `TASK-NNN` routed to `executing-implementation-task`?
- Is any claimed phase completion routed to `verifying-governance-docs` before downstream work starts?

Reference: `https://www.omg.org/spec/BPMN/2.0.2/`

## Machine-Readable Continuation

- Is `workflow resume --json` or `make workflow-resume` used as the primary start/resume controller instead of selecting an action from conversation memory?
- Is `snapshot.id` asserted through `assert_snapshot_command.argv` immediately before the selected action?
- Does `status: stale` cause the old `selected_action` to be discarded and `refresh_command.argv` to be run?
- Is work allowed only when `can_continue: true` and `stop_before_action: false`?
- Is exactly one `selected_action` executed before refreshing the controller payload?
- When using `dac next --apply --json`, does the executor re-run the snapshot assertion, reject approval or unsafe target-bound commands, preserve every step result, and refresh before reporting success?
- Does a refresh failure remain a stop state even when the selected write step already passed?
- When `selected_action.kind` is `guarded-sequence`, is preflight run first and apply run only after preflight succeeds?
- Are `blocked`, `approval_required`, and `failed` treated as stop states, and is `complete` required to have `action_count: 0`?
- Is the SHA-256 snapshot treated as a stale-context guard rather than a repository lock or substitute for implementation codebase mapping?
- For implementation, is `implementation run --check` used to select the task and issue the exact snapshot-guarded start, execute, and closeout actions?
- Does `--apply-start` stop with `status: implementation_required` so code edits occur before any verification execution?
- After edits, are all bound commands preflighted before execution, with approval/manual repair routes stopping instead of being guessed or silently applied?
- Does a stale runner snapshot, unavailable implementation lock, or first command failure preserve `In Progress` and force refresh or repair?
- Are `--json` payloads treated as structured JSON data, not display text?
- Are `local_commands[].argv` and `next_actions[].argv` executed from their reported `cwd`?
- Are `writes_state: false` commands preferred for inspection before state-changing actions?
- Are `approval_required: true` commands treated as stop-and-ask actions until explicit authorization is available?
- Are `next_actions` sorted by `sequence`, with `preflight_for`, `requires_action`, and `success_condition` used to pair preflight/apply commands instead of guessing from IDs?
- Are product `manual_authoring_tasks[]` sorted by `sequence`, with `required_evidence[].status` and `evidence_repair_actions[]` used before manual product authoring continues?
- Are design `authoring_tasks[]` sorted by `sequence`, with `execution.primary_skill`, `execution.primary_specialist_skill`, `execution.verify_step`, `execution.refresh_step`, and `execution.stop_condition` used instead of guessing from prose?
- Are design `skill_requirements[]` and `authority_skill_requirements[]` inspected for `type`, `available_in_workflow_pack`, `availability_scope`, and `missing_policy` before loading local or authority-routing skills?
- Is `workflow plan --json` `skill_summary` used to load local workflow skills and authority-routing skills before entering architecture, API, backend, data-model, security, or implementation-planning work?
- Is `workflow work-package --json` or `make work-package` used when one agent session needs a single evidence-selected task instead of every phase queue?
- When product `next_action.kind` is `decide-product-chapter`, is `product disposition --check` run before a reviewed apply, and is the returned `work_package_command` used to prove the stable work ID advanced?
- During design, is `work_stage` followed in authoring, integration, threat-review, machine-review, reliability-review, migration-review, review order so authority signoff cannot bypass deterministic checks?
- When `next_action.kind` is `run-threat-review`, are scope and mitigations authored from architecture sources and is `design threat-review --reviewed --check` run before write mode and architecture review?
- When `next_action.kind` is `run-api-review`, is `design api-review --reviewed --min-grade B --check` run before write mode and before `record-design-review`?
- When `next_action.kind` is `run-reliability-review`, is `design reliability-review --reviewed --check` run before write mode and before backend `record-design-review`?
- Does reliability routing preserve a source-backed `not-applicable` outcome instead of fabricating an SLO target for a project that does not operate a production service?
- When `next_action.kind` is `run-migration-review`, are all five migration inputs authored from repository sources and is `design migration-review --reviewed --check` run before write mode and before data-model `record-design-review`?
- Does migration routing require explicit owner, reason, mitigation, and repository evidence for every breaking or potentially breaking issue while rejecting orphaned acceptances?
- Does migration routing preserve a source-backed `not-applicable` outcome only when the project has no persistent datastore or schema lifecycle?
- When `next_action.kind` is `record-design-review`, is the primary authority skill loaded, is current `report_contract` used to write `.governance/design-review-reports/*.json` with exact decision coverage and no blocking findings, and is `design review --report <path> --check` run before writing report/source/evidence/skill hashes?
- Are missing, malformed, orphaned, or stale `docs/decisions/design-reviews.json` records treated as implementation blockers?
- If only an orphan review remains, does the work package route `record-design-review` for a current work item so apply can remove orphaned state atomically?
- Are `package_available`, `can_start`, `stop_before_work`, `skill_readiness`, `work_package.read_order`, `work_package.write_scope`, `next_action`, and `refresh_command` checked before edits?
- Are target-local `.agents/skills` and `.codex/skills`, or explicit `--skill-root` paths, included before declaring an authority-routing skill unavailable?
- Are `skill_loading_plan.steps[]` followed by `sequence`, loading local workflow skills before authority-routing skills and stopping on the declared `missing_policy` instead of guessing?
- Are `command` strings kept for human display while `argv` remains the automation contract?
- Is initialization `product.selection` used to distinguish `explicit`, `auto-discovered`, `none`, and `ambiguous` product input states before downstream product work starts?

Reference: `https://www.rfc-editor.org/rfc/rfc8259.html`

## Gate and Advance Discipline

- Are `gate` commands used for repeated checks and audits without changing phase?
- Are `advance --check --json` commands used before each state-writing `advance --json`?
- Are adjacent workflow phase transitions preserved without skipping phases?
- Is `requirements[].code` used to route repair work to the relevant phase skill?

## Scaffold Continuation

- Is `scaffold_phase.matches` inspected before treating scaffold output as current-phase work?
- Are returned `next_actions` followed to advance recorded phases when `scaffold_phase.matches` is false?
- Are `next_actions_blocked_by` blockers resolved before downstream state-writing actions run?
- Are `governance:scaffold-placeholder` markers replaced with sourced content before verification or handoff claims?

## Repair Routing

- Are product import blockers repaired with product archiving before product structuring?
- Are product acceptance blockers repaired with product structuring before design derivation?
- Are design, API, UI, backend, frontend, test, ADR, and implementation-readiness blockers routed to their owning design skills?
- Are runtime or workflow-pack drift findings routed to `runtime refresh --check --json` from a trusted source workflow-pack checkout?
- Are implementation environment blockers routed only through registered governance-env, reviewed-command, or manual repair contracts, with explicit approval where required?

## Schema and Payload Expectations

- Are required continuation fields (`cwd`, `command`, `argv`, `writes_state`, and `approval_required`) present before agents execute returned commands?
- Are action sequencing fields (`sequence`, `preflight_for`, `requires_action`, and `success_condition`) present before agents execute returned `next_actions`?
- Are action objects distinguished by `kind` such as preflight, apply, or local inspection when present?
- Are missing or malformed payload fields treated as a stop condition instead of guessed from prose?

Reference: `https://json-schema.org/draft/2020-12/json-schema-core`

## Source-of-Truth Priority

- Are target-local workflow-pack snapshots used when the source pack repository is not open?
- Are local target files, manifest state, and verification output treated as stronger evidence than prior chat context?
- Are workflow decisions updated after every command result instead of following stale planned actions?
- Are explicit stop conditions escalated to the user rather than bypassed by generating placeholder governance text?

## Normative Language

- Are hard requirements expressed with clear mandatory language in workflow, skill, and reference files?
- Are optional recommendations distinguishable from blocking checks and phase gates?
- Are stop conditions and escalation requirements stated concretely enough for another agent to enforce?

Reference: `https://www.rfc-editor.org/rfc/rfc2119.html`
