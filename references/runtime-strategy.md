# Runtime Strategy

The workflow pack separates mandatory governance runtime from optional project tooling.

## Core Runtime

Core governance commands must remain runnable with:

- POSIX shell for `bin/` wrappers
- `python3` standard library for `scripts/`
- no package installation for normal checks and initialization
- no network access except approved `env --repair` system package installation

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
make product-plan
make design-plan
make implementation-plan
make check-env
make repair-env-check
```

Target-local direct scripts under `scripts/` should mirror the same machine-readable continuation fields as the `bin/governance` wrapper when they can read workflow state.

When target-local runtime or workflow-pack integrity checks fail, run the refresh command from a trusted copy of this source workflow pack:

```bash
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

The refresh command overwrites only generated `bin/`, `scripts/`, `docs/agent-workflow/runtime-manifest.json`, and `docs/agent-workflow/workflow-pack/` snapshot files. It does not rewrite product, design, planning, or implementation documents.

Use `runtime refresh --check --json` before repair when an agent needs a no-write preflight. It reports `would_refresh` and `would_remove` paths while leaving target files and `.governance/state.json` unchanged.

After successful write-mode `runtime refresh --json`, JSON includes `local_commands` and `next_actions` when the refreshed target state is readable. Agents should run each returned `argv` from its `cwd` instead of reconstructing commands or rerunning `status`.

Append `--json` when an agent needs stable output for branching or repair planning. JSON payloads must include an `ok` field whose value matches the command's success semantics: missing required tools always make `ok: false`, and missing recommended tools make `ok: false` only under `--strict`. When supported packages can repair the environment, JSON includes `install_commands` as compatibility argv arrays, `install_command` as the equivalent human-readable command string, structured `repair_commands` with `cwd`, `argv`, `writes_state`, and `approval_required`, ordered `repair_actions`, `repair_execution` with `status`, `can_auto_apply`, `install_attempted`, `install_failed`, `post_repair_missing_required`, `post_repair_missing_recommended`, and `next_step`, and `repair_decision` with `decision`, `stop_before_workflow`, `runnable_action_ids`, `approval_action_ids`, and `manual_action_ids` so agents do not infer repair state from multiple fields. Missing tools in repair scope that cannot be covered by supported install commands are reported in `manual_repairs`.

Use `env --repair --check --json` before environment repair when an agent needs a no-write preflight. It reports `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, `repair_execution`, and `repair_decision` while leaving `.governance/env-repair.md` absent or unchanged and without executing package-manager commands. Agents should sort `repair_actions` by `sequence`, execute actions listed in `repair_decision.runnable_action_ids` only after `repair_decision.decision` is `run_repair_actions`, request approval for `repair_decision.approval_action_ids`, and treat `repair_decision.manual_action_ids` as user-facing repair instructions. If `repair_decision.stop_before_workflow` is true, do not continue to initialization, phase gates, or implementation work. If write-mode repair reports `repair_execution.status: applied_but_unresolved`, stop and inspect `post_repair_missing_required` and `post_repair_missing_recommended` before retrying package-manager repair.
When the target is an initialized governance repository and the env payload is `ok: true`, env JSON also includes `local_commands` and `next_actions` from the readable workflow state. `ok: false` remains a stop condition and does not advertise continuation commands.

## Authority Skill Supply Chain

Authority-routing skills live in the agent environment, outside the repository runtime. Inventory them offline before authority-dependent architecture, API, backend, data, security, CI, or implementation work:

```bash
python3 scripts/authority_skills.py --json
python3 scripts/authority_skills.py --repair --check --json
```

`references/authority-skills.lock.json` is the source contract. A registered entry must identify a GitHub `owner/repository`, normalized repository-relative skill path, full 40-character commit SHA, SHA-256 integrity scope and digest, license, reviewer, approval date, and review evidence. A source whose provenance has not been established must remain `unregistered`; never derive a repository or install command from the skill name.

The inventory reports `current`, `missing`, `drifted`, `unmanaged`, and `source-unregistered` status. `skill-tree` integrity hashes sorted repository-relative file records in the form `path\0file_sha256\n`; `.git`, `__pycache__`, `.DS_Store`, and `.pyc` cache files are excluded. Dependency directories such as `node_modules` remain inside the integrity boundary. Symbolic links and duplicate same-name installations fail provenance. Use the reported `observed_sha256` only after the source, revision, license, and contents have been reviewed; an observed local digest is not source approval.

`--repair --check` is planning-only: it performs no network access and no filesystem writes. A registered missing skill may produce exact Codex system `skill-installer` argv, but the action remains approval-required because it uses the network and writes outside the repository. Drift replacement remains manual because the installer refuses to overwrite an existing destination. Unregistered or unmanaged skills produce source-registration actions without guessed argv.

Use `--strict` to require availability. Use `--strict-provenance` to require every routing skill to be installed, source-approved, and digest-current. The checked-in baseline may remain portable with acknowledged unregistered sources, but authority-dependent work should use provenance strictness once the organization has completed source review.

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

Authority skill repair is a separate trust domain. It is always planning-only in this pack; it must not download code or modify `CODEX_HOME` without explicit approval.

Project-command verification is a separate scope governed by `docs/agent-workflow/project-environment.json`. Each command-contract `Environment` cell references an environment ID. After governance verification passes, `implementation verify --check` resolves `Argv[0]`, confines repository-relative executables, and runs each declared tool's version probe without a shell, with a five-second timeout and bounded output. Version probes accept only the parser's fixed read-only argument forms; parsed numeric versions must satisfy `exact`, `minimum`, and/or `maximum_exclusive` constraints. `environment_readiness`, `required_tools[]`, and `environment_probe_executed` make that evidence explicit. Missing or incompatible tools route only through the declared repair strategy: `governance-env` delegates to `env --repair --check --strict`, while `manual` returns a reviewed source, local review evidence, and instructions. Undeclared tools stop for registration. No package name, source, or install command is inferred. The registered task command itself is never executed by preflight.

Repair scope follows strictness:

- non-strict repair plans only install supported missing required tools
- strict repair plans include supported missing recommended tools
- unsupported tools remain manual repair items
