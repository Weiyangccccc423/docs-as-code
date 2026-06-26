# Runtime Strategy

The workflow pack separates mandatory governance runtime from optional project tooling.

## Core Runtime

Core governance commands must remain runnable with:

- POSIX shell for `bin/` wrappers
- `python3` standard library for `scripts/`
- no package installation
- no network access

Core runtime includes:

- repository bootstrap
- product source archiving
- governance structure verification
- environment inventory
- workflow state updates
- machine-readable status and verification output

Generated target repositories receive their own copy of this core runtime under:

```text
bin/
scripts/
```

After initialization, prefer the target-local CLI:

```bash
bin/governance verify .
bin/governance env --repair --target .
```

Append `--json` when an agent needs stable output for branching or repair planning. JSON payloads must include an `ok` field whose value matches the command's success semantics.

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

Environment repair may create local governance directories and write repair plans. It must not install system packages or project dependencies without an explicit user decision.
