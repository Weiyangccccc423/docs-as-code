# Project Environment Contract

Use `docs/agent-workflow/project-environment.json` in generated targets to bind command-contract environment IDs to executable, version, and repair requirements.

## Contract Shape

- `schema_version` must be `1`.
- `environments` is a non-empty array with unique lowercase slug IDs.
- `allow_repository_executables` explicitly permits or denies relative executables resolved from command `Cwd`.
- `tools` lists every external executable required by the environment.
- Each tool has a unique ID, bare executable name, `version_probe`, `version_requirement`, and `repair` object.

The generated `core-governance` environment requires Python `>=3.10.0` and `<4.0.0`. `project-runtime` starts empty because the workflow must not guess the product project's stack.

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

Use `manual` for project-specific tools. Record a reviewed `official-url`, `repository-doc`, or `workflow-pack` source, a repository-local Markdown `review_evidence` path, and concrete instructions. Official URLs must use HTTPS. Local source and review-evidence files must exist in the target repository. Placeholders, undeclared tools, unregistered environment IDs, unknown fields, duplicate JSON keys, and inferred package names are invalid.

`implementation verify` never installs tools. It reports ordered `repair_actions` and stops before the task command until every required tool is available and version-compatible.

## Registration Workflow

After architecture and ADR review selects the implementation stack, load `configuring-project-runtime`, `tech-stack-evaluator`, `senior-architect`, and the owning specialist. Inspect the target with:

```bash
bin/governance project-env plan <target> --json
```

During `design-derivation` or `implementation`, use `project-env register --reviewed --check --json` with explicit tool ID, executable, version-probe style/output/prefix, exact or ranged numeric version requirement, source type/location, repository-local Markdown review evidence, and repair instructions. Repeat without `--check` only after reviewing `action`, `tool`, `environment`, and `would_update`. The apply is atomic and idempotent. A changed existing tool ID fails until `--replace` is explicitly supplied. Registration writes configuration only; it does not install, upgrade, or execute the registered tool.

## Review Basis

The contract follows the preview-before-apply and provenance boundaries in `references/runtime-strategy.md`, NIST SP 800-218 SSDF environment protection, SLSA provenance principles, and OpenSSF Scorecard pinned-dependency guidance listed in `references/community-practices.md`.
