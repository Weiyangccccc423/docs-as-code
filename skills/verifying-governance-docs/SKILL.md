---
name: verifying-governance-docs
description: Use when checking whether generated or edited governance documents are complete, indexed, consistent, and ready for implementation handoff.
---

# Verifying Governance Docs

Prefer deterministic checks before manual review.

## Commands

```bash
bin/governance verify <target>
bin/governance env --strict --repair --target <target>
```

For agent automation, use JSON and branch on `ok`:

```bash
bin/governance verify <target> --json
bin/governance env --strict --repair --target <target> --json
```

Treat `ok: false` as blocking. Treat `needs_escalation: true` as requiring explicit approval before running the reported package-manager command.

When already inside an initialized target repository, prefer target-local checks:

```bash
bin/governance verify .
make verify-governance
make ci
```

## Manual Checks

- no unregistered `docs/` directories
- no stale reserved markers
- non-empty docs directories have `README.md` and `AGENTS.md`
- non-template Markdown files are indexed in the README in the same directory
- unresolved items use `none`, `-`, `n/a`, `non-blocking`, or `resolved` for non-blocking scope; any other `Blocking Scope` fails verification
- roadmap and task board status agree
- implementation tasks link to product, design, API, and acceptance sources

## Red Lines

- Do not declare governance complete while verification fails.
- Do not ignore unresolved items that affect implementation.
- Do not treat generated indexes as optional.
