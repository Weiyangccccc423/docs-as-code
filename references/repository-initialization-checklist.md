# Repository Initialization Checklist

Use this checklist before treating an empty or near-empty target folder as a governed docs-as-code repository.

Calibrate against Git repository initialization, repository entry-point documentation, lightweight security posture, and editor/tooling consistency practices. The workflow pack remains the source of truth for generated file names and command contracts.

## Target Safety

- For the standard installed-CLI path, was exactly one supported product document placed in the target root, and did `dac init --check --json` pass before `dac init --json`?
- Do zero or multiple product candidates stop at the CLI preflight with `writes_state: false` and no generated target files?
- If product auto-discovery was ambiguous, was a reviewed source selected explicitly with `dac init <product-document>` instead of guessing?
- When operating outside the target, was the reviewed target selected with `dac -C <target> ...`?
- If pip installation was unavailable, did the offline artifact entry `./docs-as-code-workflow-pack/bin/governance-bootstrap --check --json` pass before `./docs-as-code-workflow-pack/bin/governance-bootstrap --json`?
- When Git initialization is requested, did `./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --check --json` pass before `./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --json`?
- Does `input_resolution` prove current-directory target selection, target-directory-name project naming, and reviewed product/profile inputs, and, for the offline artifact path, are the workflow-pack root and its descendants excluded as targets?
- Did wrapper-driven `--auto-repair-env` remain no-write in check mode and apply only no-approval, non-manual repairs in write mode?
- Is the target folder empty or near-empty enough that generated governance files can be created without hiding user work?
- Does `bin/governance init --check --target <target> --json` auto-discover exactly one root product document when `--product` is omitted?
- Does `bin/governance init --check --target <target> --product <product-doc> --json` report conflicts before write mode is used when the source is outside the target or multiple candidates exist?
- Are existing governance files reviewed with the user before `--force` is used?
- Is the selected product document path readable before initialization writes target files?
- Are multiple product document candidates treated as a stop condition instead of guessed from file names?

Reference: `https://git-scm.com/book/en/v2/Git-Basics-Getting-a-Git-Repository`

## Environment and Repair

- Does the one-command wrapper require Python 3.10 before any pack or target checks, honor `DOCS_AS_CODE_PYTHON` for an already installed interpreter, and return no-write `bootstrap_python_unavailable` or `bootstrap_python_incompatible` plus `manual-runtime-repair` when bootstrap cannot start safely? Does the same variable reach target-local wrappers, environment inventory, and the `core-governance` `environment_override`, with no-write `governance_python_unavailable` or `governance_python_incompatible` failures? Does it run with POSIX `/bin/sh`, so Bash is not required?
- Does `bin/governance env --repair --check --target <target> --json` pass or produce actionable `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, and `needs_escalation` fields?
- Are `repair_actions` sorted by `sequence` before any environment repair action is executed?
- Are package-manager repair commands treated as approval-requiring actions when `needs_escalation` is true?
- Can initialization proceed with POSIX shell plus Python standard-library runtime and no project package install?
- For DOCX/HTML input, does `--require-tool pandoc` elevate only Pandoc, and for PDF input does `--require-tool pdftotext` elevate only Poppler text extraction, leaving unrelated recommended tools non-blocking?
- Are target-local continuation commands used from returned `cwd` and `argv` instead of reparsing display text?

## Authority Skill Readiness

- Does `python3 scripts/authority_skills.py --repair --check --json` validate `references/authority-skills.lock.json` without network access or writes?
- If missing locked skills are required, was `python3 scripts/authority_skills.py --repair --apply --approve-installs --strict-provenance --json` explicitly approved and run before environment checks or target writes?
- Did authority apply accept only `missing` installs, stop on the first command/integrity failure, and leave drifted, duplicated, unmanaged, source-unregistered, or unavailable-installer actions untouched?
- Were `repair_execution.partial_write_observed` and `manual_cleanup_required` checked before retrying a failed authority repair?
- Are `source-unregistered` and `unmanaged` skills routed to source and license review instead of guessed installs?
- Are exact install argv emitted only for approved GitHub sources pinned to immutable commits and expected digests?
- Is `--strict-authority-provenance` used before target writes when policy requires every authority skill to be source-approved and current?
- When consumer bootstrap performs the repair, is `--approve-authority-installs --strict-authority-provenance` used only in write mode, and is `authority_skill_auto_repair.can_continue` true before initialization?

## Governance Entry Points

- Are root `README.md`, `AGENTS.md`, `SPEC.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `SECURITY.md`, and `Makefile` generated or intentionally preserved?
- Do root docs explain repository purpose, source-of-truth order, verification commands, contribution rules, and security reporting enough for agents and humans to start safely?
- Does root `AGENTS.md` require `make workflow-resume`, snapshot assertion, work-package read order, ordered local/authority skill loading, one selected action, and refresh before the next action?
- Are same-directory `README.md` and `AGENTS.md` files present for non-empty documentation domains?

Reference: `https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes`

## Runtime and Snapshot Integrity

- Are target-local `bin/` and `scripts/` files generated with executable runtime entry points?
- Does `docs/agent-workflow/runtime-manifest.json` cover target-local runtime files?
- Does `docs/agent-workflow/workflow-pack/manifest.json` cover the copied workflow-pack snapshot?
- Does `docs/agent-workflow/project-environment.json` validate, provide a usable `core-governance` version contract, and leave project-specific tools unguessed until stack selection?
- Does the target runtime include the shared bounded process runner used by implementation verification and approved project environment repair?
- Does the snapshot contain `references/authority-skills.lock.json` and does its manifest bind the file hash?
- Are `make verify-governance`, `make verify-check`, `make governance-status`, `make workflow-plan`, `make product-plan`, `make design-plan`, `make check-env`, `make repair-env-check`, and `make project-env-plan` available after initialization?

## Product Seed

- Are `docs/product/core/PRD.md`, `docs/product/core/product-meta.md`, `docs/product/core/source/source-manifest.json`, `docs/unresolved.md`, and `docs/glossary.md` initialized?
- Is the original product source archived or represented as conversion-required before product structuring begins?
- For TXT/DOCX/HTML/PDF, does initialization create `docs/product/core/source/conversion-report.json`, record generated output SHA-256, remain `pending_review`, and route to guarded `product-mark-ready`?
- Does PDF extraction use fixed bounded `pdftotext` arguments and require source comparison for tables, diagrams, columns, and layout-dependent meaning?
- Does initialization JSON record product selection as `explicit`, `auto-discovered`, `none`, or `ambiguous` so agents can branch deterministically?
- Does `.governance/state.json` record phase, profile, product source, archive path, and product import readiness consistently?

## Git Readiness

- If the target is under Git, is the repository initialized deliberately and ready for small traceable commits?
- Does consumer bootstrap report `repository_git_check_ok: true` before apply and `repository_git_initialized: true` afterward, while check mode leaves `.git` absent?
- Was `bin/governance repository init <target> ... --reviewed --check --json` run before its write-mode equivalent?
- Are `user.name` and `user.email` set with repository-local scope from explicit reviewed values rather than silently inherited from global Git configuration?
- Did initialization refuse to mutate a parent repository or overwrite conflicting branch, author, or origin metadata?
- Is it explicit that repository initialization does not create a commit, authenticate, or push, and that hosting-account identity must be checked separately before a push?
- Are generated runtime, workflow-pack snapshot, templates, and governance docs intended to be versioned?
- Is the unpacked source workflow pack excluded while its generated manifest-bound snapshot remains versioned?
- Do generated snapshot `VERSION`, runtime/snapshot `pack_version`, and state `workflow_pack_version` match the reviewed source pack?
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
