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

Append `--json` when an agent needs stable output for branching or repair planning. JSON payloads must include an `ok` field whose value matches the command's success semantics: missing required tools always make `ok: false`, and missing recommended tools make `ok: false` only under `--strict`. When supported packages can repair the environment, JSON includes `install_commands` as compatibility argv arrays, `install_command` as the equivalent human-readable command string, structured `repair_commands` with `cwd`, `argv`, `writes_state`, and `approval_required`, ordered `repair_actions`, and `repair_execution` with `status`, `can_auto_apply`, `install_attempted`, `install_failed`, `post_repair_missing_required`, `post_repair_missing_recommended`, and `next_step` so agents do not infer repair state from multiple fields. Missing tools in repair scope that cannot be covered by supported install commands are reported in `manual_repairs`.

Use `env --repair --check --json` before environment repair when an agent needs a no-write preflight. It reports `would_repair`, `install_commands`, `repair_commands`, `repair_actions`, `manual_repairs`, `needs_escalation`, and `repair_execution` while leaving `.governance/env-repair.md` absent or unchanged and without executing package-manager commands. Agents should sort `repair_actions` by `sequence`, execute actions with `argv` only after `repair_execution.status` is `ready_to_apply` or explicit approval has been granted, and treat `manual-repair` actions as user-facing repair instructions. If write-mode repair reports `repair_execution.status: applied_but_unresolved`, stop and inspect `post_repair_missing_required` and `post_repair_missing_recommended` before retrying package-manager repair.
When the target is an initialized governance repository and the env payload is `ok: true`, env JSON also includes `local_commands` and `next_actions` from the readable workflow state. `ok: false` remains a stop condition and does not advertise continuation commands.

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

Repair scope follows strictness:

- non-strict repair plans only install supported missing required tools
- strict repair plans include supported missing recommended tools
- unsupported tools remain manual repair items
