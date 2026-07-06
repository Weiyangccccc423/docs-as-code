# Governance Verification Checklist

Use this checklist before declaring a generated docs-as-code repository ready for the next workflow phase or for implementation handoff.

Calibrate against automated verification, secure development, supply-chain integrity, and security-health measurement practices. Deterministic local governance checks remain the first authority; external frameworks are calibration references, not replacement gates.

## Command Discipline

- Is every state-writing verification or phase transition preceded by its matching `--check --json` preflight?
- Are agents branching on `ok`, `findings[].code`, `findings[].path`, and `requirements[].code` instead of scraping prose?
- Are `local_commands[].argv` and `next_actions[].argv` executed from their reported `cwd` rather than reconstructed from display strings?
- Are returned commands with `approval_required: true` blocked until explicit authorization is available?
- Are `errors` and `warnings` treated as human summaries, with structured findings used for repair routing?

Reference: `https://dora.dev/capabilities/test-automation/`

## Environment Repair Control

- Does strict environment verification use `bin/governance env --strict --repair --check --target <target> --json` before any repair write?
- Are `would_repair`, `install_commands`, `manual_repairs`, and `needs_escalation` inspected before running repair mode?
- Are package-manager commands blocked until explicit approval when `needs_escalation` is true?
- Are missing recommended tools reported without hiding required-tool failures?

## Drift and Refresh

- Are `runtime_manifest_*`, `runtime_file_*`, `workflow_pack_manifest_*`, and `workflow_pack_file_*` findings treated as runtime or workflow-pack integrity blockers?
- Is `bin/governance runtime refresh <target> --check --json` used as a no-write plan from a trusted source workflow-pack checkout?
- Does write-mode runtime refresh avoid rewriting product, design, planning, or implementation documents?
- Are target-local checks rerun from returned `local_commands[].argv` after refresh succeeds?

Reference: `https://slsa.dev/spec/v1.2/about`

## Phase Gates and State

- Are `gate` commands used for repeated checks and `advance` commands used only when recording adjacent phase transitions?
- Does every `advance --json` follow a passing `advance --check --json` for the same target and phase?
- Are `.governance/state.json` phase, phase history, product import cache, and `last_verification` repaired before downstream work continues?
- Are `next_actions` preserved but not executed while placeholder or unresolved blockers remain?

## Repair Ordering

- Are document-integrity findings repaired before traceability, task, or gate findings derived from unreadable files?
- Are missing acceptance IDs, unresolved IDs, links, and evidence restored from source documents instead of invented to satisfy a secondary finding?
- Is verification rerun after each structural repair before interpreting downstream findings in the same area?
- Are unresolved blocking rows treated as phase blockers until they are resolved or explicitly marked non-blocking by approved workflow values?

## Traceability and Evidence

- Does verification confirm product, design, API, test, and task-board links point to existing local Markdown sources?
- Does every `Done` task link to existing verification evidence, and does `docs/development/03-verification-log.md` contain matching `TASK-NNN` run rows when cited?
- Does the acceptance matrix map every product-defined `A-NNN` or list it under Uncovered Criteria with product-defined IDs only?
- Are verification commands and results reported before claiming completion?

## Security and Supply Chain Sanity

- Are `SECURITY.md`, dependency trust expectations, and security-sensitive design verification paths visible before implementation starts?
- Are supply-chain integrity concerns, provenance expectations, and dependency update assumptions documented before they affect implementation tasks?
- Are repository security-health checks treated as signals to review, not as a single absolute pass/fail score?

Reference: `https://csrc.nist.gov/pubs/sp/800/218/final`

Reference: `https://github.com/ossf/scorecard`

## Completion Gate

- Does `bin/governance verify <target> --check --json` pass before recorded verification?
- Does `bin/governance verify <target> --json` record the current successful baseline when state should be updated?
- Does `bin/governance advance implementation <target> --check --json` pass before implementation work starts?
- Is at least one task board item `Ready`, with product, design, API, acceptance, and verification links satisfied?
