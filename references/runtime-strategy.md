# Runtime Strategy

The workflow pack separates mandatory governance runtime from optional project tooling.

## Core Runtime

Core governance commands must remain runnable with:

- POSIX `/bin/sh` for `bin/` wrappers; Bash is not required
- Python 3.10 or newer, using only the standard library for `scripts/`
- no package installation for normal checks and initialization
- no network access during normal checks or initialization; approved `env --repair` and authority-skill apply are separate explicit repair boundaries

Core runtime includes:

- repository bootstrap
- product source archiving
- governance structure verification
- environment inventory
- workflow state updates
- machine-readable status and verification output
- initialization preflight and conflict reporting

Generated target repositories receive their own copy of this core runtime under:

```text
bin/
scripts/
```

After initialization, prefer the target-local CLI:

```bash
bin/governance verify .
bin/governance env --repair --check --target . --json
bin/governance env --repair --target . --json
```

Generated targets also include stable Makefile entries for routine checks:

```bash
make verify-governance
make verify-check
make governance-status
make workflow-plan
make work-package
make workflow-resume
make product-plan
make design-plan
make implementation-plan
make implementation-run-check
make check-env
make repair-env-check
make project-env-plan
```

Target-local direct scripts under `scripts/` should mirror the same machine-readable continuation fields as the `bin/governance` wrapper when they can read workflow state.

When target-local runtime or workflow-pack integrity checks fail, run the refresh command from a trusted copy of this source workflow pack:

```bash
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

The refresh command overwrites only generated `bin/`, `scripts/`, `docs/agent-workflow/runtime-manifest.json`, and `docs/agent-workflow/workflow-pack/` snapshot files. It does not rewrite product, design, planning, or implementation documents.

For an unpacked source pack placed inside a new project folder with one product document, use the source-only consumer entry before target-local runtime exists:

```bash
./docs-as-code-workflow-pack/bin/governance-bootstrap --check --json
./docs-as-code-workflow-pack/bin/governance-bootstrap --json
```

The wrapper does not become part of generated target runtime. It enables safe `--auto-repair-env`, selects the current directory only when `--target` is absent, derives the default project name from that directory, and leaves profile as `unknown`; target-root product discovery still requires exactly one candidate. Check mode stays no-write, and write mode applies only repairs already classified as no-approval and non-manual. Inspect `input_resolution`. The workflow-pack root and its descendants are rejected as targets; the pack may be nested inside the target. TXT conversion uses Python standard-library UTF-8 handling. DOCX/HTML conversion elevates only `pandoc` with `--require-tool pandoc`; PDF conversion elevates only Poppler `pdftotext` with `--require-tool pdftotext`, so unrelated recommended tools do not become blockers. Conversion runs without a shell under fixed timeout/output limits and stops at `pending_review`.

Because this is the first executable entry, it probes Python 3.10 before any Python-based environment inspection. `DOCS_AS_CODE_PYTHON` may select an already installed compatible interpreter. JSON `bootstrap_python_unavailable` and `bootstrap_python_incompatible` failures set `writes_state: false`, stop the workflow, and return `manual-runtime-repair`; automatically installing the interpreter that the repair engine itself requires is outside the safe repair boundary. Keep the variable set for generated target commands: `bin/governance` repeats the compatibility guard, aliases delegate to that entry, `check_env.py` inventories the selected executable as the logical `python3` requirement, and `project-environment.json` declares the same `environment_override` for the `core-governance` probe. Target failures use `governance_python_unavailable` or `governance_python_incompatible` and remain no-write. A successful probe uses `exec` for direct signal and exit-code propagation.

Optional reviewed Git initialization is composed into that source-only entry with an existing target folder:

```bash
./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --check --json
./docs-as-code-workflow-pack/bin/governance-bootstrap --initialize-git --git-default-branch main --git-author-name "<name>" --git-author-email "<email>" --git-origin "<url>" --reviewed-git --json
```

Omit `--git-origin` when no remote is approved. Git options without `--initialize-git`, incomplete metadata, and missing review are blockers. Check mode leaves `.git` absent and reports `repository_git_check_ok`; apply uses the generated target-local runtime and reports `repository_git_initialized`. Neither path commits, authenticates, or pushes.

Use `runtime refresh --check --json` before repair when an agent needs a no-write preflight. It reports `would_refresh`, `would_remove`, and `version_transition` while leaving target files and `.governance/state.json` unchanged. Inspect the transition classification and version evidence; breaking upgrades, rollbacks, version replacements, and conflicting or invalid evidence require a reviewed `--approve-version-transition` write command. Unapproved high-risk transitions perform no writes.

After successful write-mode `runtime refresh --json`, JSON includes `local_commands` and `next_actions` when the refreshed target state is readable. Agents should run each returned `argv` from its `cwd` instead of reconstructing commands or rerunning `status`.

Append `--json` when an agent needs stable output for branching or repair planning. JSON payloads must include an `ok` field whose value matches the command's success semantics: missing required tools always make `ok: false`, named `required_tools` make `ok: false` only for the current operation, and other missing recommended tools make `ok: false` only under `--strict`. When supported packages can repair the environment, JSON includes `install_commands` as compatibility argv arrays, `install_command` as the equivalent human-readable command string, structured `repair_commands` with `cwd`, `argv`, `writes_state`, and `approval_required`, ordered `repair_actions`, `repair_execution` with `status`, `can_auto_apply`, `install_attempted`, `install_failed`, `post_repair_missing_required`, `post_repair_missing_recommended`, and `next_step`, and `repair_decision` with `decision`, `stop_before_workflow`, `runnable_action_ids`, `approval_action_ids`, and `manual_action_ids` so agents do not infer repair state from multiple fields. Missing tools in repair scope that cannot be covered by supported install commands are reported in `manual_repairs`.

Use `env --repair --check --json` before environment repair when an agent needs a no-write preflight. It reports `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, `repair_execution`, and `repair_decision` while leaving `.governance/env-repair.md` absent or unchanged and without executing package-manager commands. Agents should sort `repair_actions` by `sequence`, execute actions listed in `repair_decision.runnable_action_ids` only after `repair_decision.decision` is `run_repair_actions`, request approval for `repair_decision.approval_action_ids`, and treat `repair_decision.manual_action_ids` as user-facing repair instructions. If `repair_decision.stop_before_workflow` is true, do not continue to initialization, phase gates, or implementation work. If write-mode repair reports `repair_execution.status: applied_but_unresolved`, stop and inspect `post_repair_missing_required` and `post_repair_missing_recommended` before retrying package-manager repair.
When the target is an initialized governance repository and the env payload is `ok: true`, env JSON also includes `local_commands` and `next_actions` from the readable workflow state. `ok: false` remains a stop condition and does not advertise continuation commands.

## Authority Skill Supply Chain

Authority-routing skills live in the agent environment, outside the repository runtime. Inventory them offline before authority-dependent architecture, API, backend, data, security, CI, or implementation work:

```bash
python3 scripts/authority_skills.py --json
python3 scripts/authority_skills.py --repair --check --json
python3 scripts/authority_skills.py --repair --apply --approve-installs --strict-provenance --json
```

`references/authority-skills.lock.json` is the source contract. A registered entry must identify a GitHub `owner/repository`, normalized repository-relative skill path, full 40-character commit SHA, SHA-256 integrity scope and digest, license, reviewer, approval date, and review evidence. A source whose provenance has not been established must remain `unregistered`; never derive a repository or install command from the skill name.

The inventory reports `current`, `missing`, `drifted`, `unmanaged`, and `source-unregistered` status. `skill-tree` integrity hashes sorted repository-relative file records in the form `path\0file_sha256\n`; `.git`, `__pycache__`, `.DS_Store`, and `.pyc` cache files are excluded. Dependency directories such as `node_modules` remain inside the integrity boundary. Symbolic links and duplicate same-name installations fail provenance. Use the reported `observed_sha256` only after the source, revision, license, and contents have been reviewed; an observed local digest is not source approval.

`--repair --check` is planning-only: it performs no network access and no filesystem writes. A registered missing skill may produce exact Codex system `skill-installer` argv, but the action remains approval-required because it uses the network and writes outside the repository. `--repair --apply` still executes nothing until `--approve-installs` is present. Approved apply accepts only `missing` actions from the valid immutable lock through an available non-symlink system installer, executes argv without a shell, limits every action to 120 seconds and 65,536 bytes per output stream, and immediately verifies the complete installed tree digest. It stops after the first command failure or digest mismatch and reports `partial_write_observed` plus `manual_cleanup_required`. Drift replacement, duplicate installations, unavailable installers, unmanaged skills, and source-registration work remain manual and block the whole batch before execution.

Use `--strict` to require availability. Use `--strict-provenance` to require every routing skill to be installed, source-approved, and digest-current. The checked-in lock registers the reviewed baseline, but a recipient Agent environment may still be missing or drifted; authority-dependent work should use provenance strictness.

This contract is calibrated against SLSA provenance, NIST SP 800-218 SSDF, and OpenSSF Scorecard pinned-dependency guidance listed in `references/community-practices.md`.

## Node.js Layer

Use Node.js for ecosystem-specific enhancement after the target stack is known:

- markdown formatting and linting
- OpenAPI linting
- frontend workspace checks
- docs site builds
- package manager health checks

Do not make Node.js required for `governance init`, `governance verify`, or `governance env`.

## Rust Layer

Use Rust only for optional stable accelerators or single-binary distribution after rules have stabilized:

- large-repository scans
- high-frequency link or index checks
- packaged offline verification binaries

The Python standard-library implementation remains the reference behavior.

## Repair Policy

Environment repair may create local governance directories and write repair plans. It may execute supported apt installs only when the process already has root privileges. Under `--check`, it must not write repair plans or execute package-manager commands. It must not call `sudo`, change global Git configuration, or install project dependencies.

Authority skill repair is a separate trust domain. Planning remains offline and no-write. Apply may download code and modify `CODEX_HOME` only with `--repair --apply --approve-installs`, only for eligible locked missing skills, and only under bounded execution plus immediate digest verification. It never removes or replaces an existing skill automatically.

Project-command verification is a separate scope governed by `docs/agent-workflow/project-environment.json`. Each command-contract `Environment` cell references an environment ID. After governance verification passes, `implementation verify --check` resolves `Argv[0]`, confines repository-relative executables, and runs each declared tool's version probe without a shell, with a five-second timeout and bounded output. Version probes accept only the parser's fixed read-only argument forms; parsed numeric versions must satisfy `exact`, `minimum`, and/or `maximum_exclusive` constraints. `environment_readiness`, `required_tools[]`, and `environment_probe_executed` make that evidence explicit. Missing or incompatible tools route only through the declared repair strategy: `governance-env` delegates to `env --repair --check --strict`, `manual` returns reviewed instructions, and `reviewed-command` delegates to `project-env repair --check`. Undeclared tools stop for registration. No package name, source, or install command is inferred. The registered task command and reviewed repair command are never executed by implementation preflight.

Project runtime registration is also separate from installation. After stack review, run `project-env plan`, then `project-env register --reviewed --check` and apply with explicit tool, version, probe, source, evidence, and instruction fields. The command accepts writes only during `design-derivation` or `implementation`, atomically updates only `project-environment.json`, is idempotent for an unchanged tool, and requires `--replace` for a reviewed conflicting tool ID.

Project runtime repair is a third trust boundary. `project-env repair --check` resolves the exact registered command, verifies the registered repository-executable digest, and returns an approval-required apply action without executing or writing. `project-env repair --approved` executes only a `reviewed-command` argv with no shell, bounded timeout/output, redaction, and repository confinement. It writes pending evidence before execution, repeats the version probe afterward, verifies all integrity inputs stayed unchanged, and records sanitized evidence in `.governance/project-environment-repairs.json`. Manual repairs remain manual, governance repairs remain delegated, and pending evidence stops workflow progress.

Repair scope follows strictness:

- non-strict repair plans only install supported missing required tools
- strict repair plans include supported missing recommended tools
- unsupported tools remain manual repair items
