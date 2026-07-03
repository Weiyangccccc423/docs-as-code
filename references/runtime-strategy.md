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
make check-env
make repair-env-check
```

When target-local runtime or workflow-pack integrity checks fail, run the refresh command from a trusted copy of this source workflow pack:

```bash
bin/governance runtime refresh <target> --check --json
bin/governance runtime refresh <target> --json
```

The refresh command overwrites only generated `bin/`, `scripts/`, `docs/agent-workflow/runtime-manifest.json`, and `docs/agent-workflow/workflow-pack/` snapshot files. It does not rewrite product, design, planning, or implementation documents.

Use `runtime refresh --check --json` before repair when an agent needs a no-write preflight. It reports `would_refresh` and `would_remove` paths while leaving target files and `.governance/state.json` unchanged.

After successful write-mode `runtime refresh --json`, JSON includes `local_commands` and `next_actions` when the refreshed target state is readable. Agents should run each returned `argv` from its `cwd` instead of reconstructing commands or rerunning `status`.

Append `--json` when an agent needs stable output for branching or repair planning. JSON payloads must include an `ok` field whose value matches the command's success semantics: missing required tools always make `ok: false`, and missing recommended tools make `ok: false` only under `--strict`. When supported packages can repair the environment, JSON includes `install_commands` as argv arrays and `install_command` as the equivalent human-readable command string.

Use `env --repair --check --json` before environment repair when an agent needs a no-write preflight. It reports `would_repair`, `install_commands`, and `needs_escalation` while leaving `.governance/env-repair.md` absent or unchanged and without executing package-manager commands.
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
