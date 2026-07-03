# Repository Initialization Checklist

Use this checklist before treating an empty or near-empty target folder as a governed docs-as-code repository.

Calibrate against Git repository initialization, repository entry-point documentation, lightweight security posture, and editor/tooling consistency practices. The workflow pack remains the source of truth for generated file names and command contracts.

## Target Safety

- Is the target folder empty or near-empty enough that generated governance files can be created without hiding user work?
- Does `bin/governance init --check --target <target> --product <product-doc> --json` report conflicts before write mode is used?
- Are existing governance files reviewed with the user before `--force` is used?
- Is the product document path readable before initialization writes target files?

Reference: `https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository`

## Environment and Repair

- Does `bin/governance env --repair --check --target <target> --json` pass or produce actionable `would_repair`, `install_commands`, `manual_repairs`, and `needs_escalation` fields?
- Are package-manager repair commands treated as approval-requiring actions when `needs_escalation` is true?
- Can initialization proceed with POSIX shell plus Python standard-library runtime and no project package install?
- Are target-local continuation commands used from returned `cwd` and `argv` instead of reparsing display text?

## Governance Entry Points

- Are root `README.md`, `AGENTS.md`, `SPEC.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, and `Makefile` generated or intentionally preserved?
- Do root docs explain repository purpose, source-of-truth order, verification commands, contribution rules, and security reporting enough for agents and humans to start safely?
- Are same-directory `README.md` and `AGENTS.md` files present for non-empty documentation domains?

Reference: `https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes`

## Runtime and Snapshot Integrity

- Are target-local `bin/` and `scripts/` files generated with executable runtime entry points?
- Does `docs/agent-workflow/runtime-manifest.json` cover target-local runtime files?
- Does `docs/agent-workflow/workflow-pack/manifest.json` cover the copied workflow-pack snapshot?
- Are `make verify-governance`, `make verify-check`, `make governance-status`, `make check-env`, and `make repair-env-check` available after initialization?

## Product Seed

- Are `docs/product/core/PRD.md`, `docs/product/core/product-meta.md`, `docs/product/core/source/source-manifest.json`, `docs/unresolved.md`, and `docs/glossary.md` initialized?
- Is the original product source archived or represented as conversion-required before product structuring begins?
- Does `.governance/state.json` record phase, profile, product source, archive path, and product import readiness consistently?

## Git Readiness

- If the target is under Git, is the repository initialized deliberately and ready for small traceable commits?
- Are generated runtime, workflow-pack snapshot, templates, and governance docs intended to be versioned?
- Are local caches, secrets, credentials, environment files, and build outputs excluded before the first commit?
- Is the default branch, remote, and author identity a user decision rather than a workflow-pack assumption?

Reference: `https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository`

## Baseline Security Posture

- Are `SECURITY.md` and governance docs present before implementation work begins?
- Are secret handling, dependency update expectations, and verification commands visible from generated entry points?
- Are repository hardening items that depend on the hosting provider, such as branch protection or code scanning, tracked as follow-up work instead of silently assumed?

Reference: `https://scorecard.dev/`

## Editor and Tooling Consistency

- Are formatting, line ending, and editor expectations either generated or deferred explicitly for the target stack?
- Are stack-specific Node.js, Rust, Python, Go, or frontend tooling choices deferred until product/design evidence requires them?
- Are optional tooling gaps recorded by `check-env` rather than hidden during initialization?

Reference: `https://editorconfig.org/`

## Handoff Readiness

- Does `bin/governance verify <target> --check --json` pass before recorded verification?
- Does `bin/governance verify <target>` or `bin/governance verify <target> --json` establish the initial verification baseline?
- Does `bin/governance status <target>` report readable phase and product-import state?
- Does `bin/governance advance product-structuring <target> --check --json` provide the next safe transition result?
