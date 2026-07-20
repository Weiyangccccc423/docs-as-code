# Project Environment Contract

Use `docs/agent-workflow/project-environment.json` in generated targets to bind command-contract environment IDs to executable, version, and repair requirements.

## Contract Shape

- `schema_version` must be `1`.
- `environments` is a non-empty array with unique lowercase slug IDs.
- `allow_repository_executables` explicitly permits or denies relative executables resolved from command `Cwd`.
- `tools` lists every external executable required by the environment.
- Each tool has a unique ID, bare executable name, `version_probe`, `version_requirement`, and `repair` object.

The generated `core-governance` environment requires Python `>=3.10.0` and `<4.0.0`. `project-runtime` starts empty because the workflow must not guess the product project's stack.

## Command Coverage

`project-env plan` accepts `docs/agent-workflow/command-contract.md` only as a regular, non-symlink UTF-8 file no larger than 1 MiB, then reads every row whose `Environment` is `project-runtime`. Bare external executables map by exact executable name to one registered tool. Absolute external executables map by basename and probe the exact absolute path. Repository-relative executables must resolve from the command `Cwd`, remain inside the repository, be regular executable files rather than symlinks, and require `allow_repository_executables: true`.

The plan returns `required_commands`, per-command `command_coverage`, `missing_command_registrations`, registered `tool_readiness`, `unready_tool_ids`, and informational `unused_tool_ids`. `coverage_status` has these values:

- `not_required`: no command uses `project-runtime`; `configuration_complete` is true.
- `command_contract_invalid`: the command table cannot be parsed safely.
- `repair_evidence_pending`: an interrupted or unresolved reviewed repair record exists.
- `registration_required`: at least one external command executable has no reviewed tool registration.
- `repair_required`: registration exists, but a command path or required tool probe is not ready.
- `ready`: every project-runtime command is covered, every registered environment tool is ready, and `configuration_complete` is true.

The design-phase workflow appends a `project-runtime` queue after all design authoring and review queues. When incomplete, `workflow work-package` returns `kind: project-runtime-configuration` and routes command-contract repair, pending-evidence investigation, registration, or an exact `project-env repair --check` preflight without inventing tool IDs or install commands. Implementation gate requirement `project_runtime_ready` uses `configuration_complete`; direct gate invocation cannot bypass this queue.

## Version Probes

Version probes are executable metadata checks, not project verification commands. They run only after governance verification passes. The runtime permits only one of these argument arrays:

```json
["--version"]
["-V"]
["-version"]
["version"]
```

Select `stdout`, `stderr`, or `combined`, and provide the exact line prefix before the numeric dotted version. Probes run without a shell, with a five-second timeout and 4096-byte output limit. Arbitrary code flags, shell evaluation, network commands, and package-manager actions are invalid.

Version requirements may use one exact version or a range:

```json
{
  "minimum": "20.0.0",
  "maximum_exclusive": "23.0.0"
}
```

Only numeric versions with one to four components are accepted. Prerelease/channel policy requires a future schema revision rather than implicit semantic-version guessing.

## Repair Sources

Use `governance-env` only when the executable is already registered by `scripts/check_env.py`; its source must be the workflow-pack path `scripts/check_env.py`. This strategy returns the existing no-write repair preflight and preserves its approval and auto-apply boundaries.

Use `manual` when no deterministic project repair command has been accepted. Record a reviewed `official-url`, `repository-doc`, or `workflow-pack` source, a repository-local Markdown `review_evidence` path, and concrete instructions.

Use `reviewed-command` only when the accepted architecture or ADR evidence proves the exact repair `command.argv` and repository-local `command.cwd`. The command is stored as an argv array and is executed with `shell=False`; shell and privilege wrappers, inline interpreter code, placeholders, control characters, and secret-bearing arguments are rejected. Repository-relative repair executables must already exist, be executable, stay inside the repository, and not be symlinks. Registration automatically stores their SHA-256 in `command.executable_sha256`; any later digest drift blocks preview and execution. Bare repair executables must resolve from the effective `PATH` and their observed executable digest is bound into execution evidence. Official URLs must use HTTPS. Local source and review-evidence files must exist in the target repository. Undeclared tools, unregistered environment IDs, unknown fields, duplicate JSON keys, and inferred package names remain invalid.

`implementation verify` never installs tools. It reports ordered `repair_actions` and stops before the task command until every required tool is available and version-compatible. A failed `reviewed-command` tool routes to `project-env repair --check`; it never runs the repair from implementation preflight.

## Registration Workflow

After architecture and ADR review selects the implementation stack, load `configuring-project-runtime`, `tech-stack-evaluator`, `senior-architect`, and the owning specialist. Inspect the target with:

```bash
bin/governance project-env plan <target> --json
```

During `design-derivation` or `implementation`, use `project-env register --reviewed --check --json` with explicit tool ID, executable, version-probe style/output/prefix, exact or ranged numeric version requirement, source type/location, repository-local Markdown review evidence, and repair instructions. For `reviewed-command`, also repeat `--repair-command-arg` in exact argv order and set `--repair-command-cwd`; arguments beginning with `-` use the `--repair-command-arg=<value>` form. Repeat registration without `--check` only after reviewing `action`, `tool`, `environment`, and `would_update`. The apply is atomic and idempotent. A changed existing tool ID fails until `--replace` is explicitly supplied. Registration writes configuration only; it does not install, upgrade, or execute the registered tool.

After each registration or repair, rerun `project-env plan`. Do not advance to implementation until `configuration_complete` is true and the implementation gate reports `project_runtime_ready`.

## Reviewed Repair Workflow

Preview one registered repair without executing or writing evidence:

```bash
bin/governance project-env repair <target> --tool-id <tool-id> --check --json
```

Inspect `readiness_before`, `repair_action.command`, `repair_action.source`, `repair_ready`, `stop_before_workflow`, and `apply_command`. The apply action always has `approval_required: true`. After explicit approval, run its exact argv or:

```bash
bin/governance project-env repair <target> --tool-id <tool-id> --approved --json
```

Execution uses a bounded timeout, bounded stdout/stderr capture, process-group termination, and best-effort credential redaction. Before execution, the runtime atomically appends a `pending` record to `.governance/project-environment-repairs.json`; after execution it records a sanitized result and repeats the allowlisted version probe. Success requires command return code zero, a compatible observed version, and unchanged contract, review-evidence, local-source, and repair-executable SHA-256 inputs. Failed, timed-out, unavailable, integrity-drifted, or applied-but-unresolved commands keep `stop_before_workflow: true`. Pending evidence blocks governance verification and must be investigated rather than treated as successful repair. The evidence ledger stores exact non-secret argv, source and review-evidence identity, SHA-256 bindings for local evidence and repair executables, execution metadata without stdout/stderr text, and before/after readiness.

## Review Basis

The contract follows the preview-before-apply and provenance boundaries in `references/runtime-strategy.md`, NIST SP 800-218 SSDF environment protection, SLSA provenance principles, and OpenSSF Scorecard pinned-dependency guidance listed in `references/community-practices.md`.
