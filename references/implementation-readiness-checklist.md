# Implementation Readiness Checklist

Use this checklist before tasks are marked `Ready`, handed to an implementation agent, or accepted as `Done`.

Calibrate implementation readiness against the Scrum Guide's transparency and Definition of Done guidance, DORA technical capabilities, and SLSA supply-chain expectations. Keep the checklist local and traceable: every item should point back to repository Markdown, commands, or evidence.

## Ready Task Contract

- Does each `Ready` task have a stable `TASK-NNN` ID, concise goal, owner or agent role, and expected code/documentation surface?
- Do Product, Design, API, Acceptance, and Verification cells link existing local Markdown sources?
- Are dependencies, sequencing, blocked questions, and out-of-scope work explicit enough that an agent can start without inventing requirements?
- Do the linked design paths provide enough machine-readable scope for `implementation plan` to route the required architecture, backend, data, reliability, frontend, test, and delivery authority skills without task-title guessing?

Reference: `https://scrumguides.org/scrum-guide.html`

## Definition of Done

- Does Done require working code, synchronized docs, passing verification commands, and local Markdown evidence?
- Are acceptance criteria, tests, migrations, security checks, operational notes, and compatibility notes included when the task scope needs them?
- Is work that fails the repository Definition of Done returned to Backlog or Blocked instead of being presented as complete?

Reference: `https://scrumguides.org/scrum-guide.html`

## Verification Plan

- Does each task name the exact commands, test layers, expected evidence target, and fallback when a command cannot run?
- Are unit, integration, contract, end-to-end, accessibility, performance, security, or manual-review checks selected from product acceptance and design risk?
- Are flaky, skipped, unavailable, or environment-dependent checks recorded as evidence with follow-up ownership?

Reference: `https://dora.dev/capabilities/test-automation/`

## Change Integration

- Are tasks small enough to review, integrate, and verify independently without long-lived divergence?
- Are branch, merge, generated-code, migration, and compatibility expectations documented when they affect implementation flow?
- Are cross-task dependencies represented in roadmap sequencing instead of hidden in task prose?

Reference: `https://dora.dev/capabilities/trunk-based-development/`

## Agent Handoff

- Does the handoff include task goal, related specs, constraints, allowed files or modules, verification commands, and Definition of Done?
- Are assumptions, unresolved questions, and user decisions captured in `docs/unresolved.md` or the task handoff before implementation starts?
- Are implementation agents told to use target-local `local_commands[].argv`, inspect `approval_required`, and avoid reparsing command strings when JSON payloads provide structured commands?

## Supply Chain Evidence

- Are generated artifacts, dependency changes, build outputs, and release evidence traceable when the task produces deliverables beyond source code?
- Are provenance, integrity, and dependency update expectations documented for build/release work?
- Are secrets, credentials, generated clients, and package-publishing actions treated as explicit high-risk scope?

Reference: `https://slsa.dev/spec/v1.1/about`
