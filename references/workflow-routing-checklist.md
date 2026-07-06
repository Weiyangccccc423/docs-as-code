# Workflow Routing Checklist

Use this checklist when starting, resuming, or recovering a docs-as-code governance workflow from an empty, partially governed, or drifted repository.

Calibrate against explicit process modeling, machine-readable JSON contracts, schema discipline, and normative requirement language. The target-local governance CLI remains the executable authority for gates, actions, and verification findings.

## Entry Classification

- Is the target state classified from current files and governance state rather than from conversation memory?
- Is an empty or missing-governance target routed to `initializing-governance-repo`?
- Is an unarchived or conversion-required product source routed to `archiving-product-document`?
- Is a reviewed PRD without sourced product chapters routed to `structuring-product-requirements`?
- Is structured product with acceptance criteria routed through design skills in the Phase Map order?
- Is any claimed phase completion routed to `verifying-governance-docs` before downstream work starts?

Reference: `https://www.omg.org/spec/BPMN/2.0.2/`

## Machine-Readable Continuation

- Are `--json` payloads treated as structured JSON data, not display text?
- Are `local_commands[].argv` and `next_actions[].argv` executed from their reported `cwd`?
- Are `writes_state: false` commands preferred for inspection before state-changing actions?
- Are `command` strings kept for human display while `argv` remains the automation contract?

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

## Schema and Payload Expectations

- Are required continuation fields (`cwd`, `command`, `argv`, and `writes_state`) present before agents execute returned commands?
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
