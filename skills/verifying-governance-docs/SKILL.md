---
name: verifying-governance-docs
description: Use when checking whether generated or edited governance documents are complete, indexed, consistent, and ready for implementation handoff.
---

# Verifying Governance Docs

Prefer deterministic checks before manual review.

## Commands

```bash
python3 scripts/verify_governance.py <target>
python3 scripts/check_env.py --strict
```

Run target project checks when available:

```bash
make verify-governance
make ci
```

## Manual Checks

- no unregistered `docs/` directories
- no stale reserved markers
- non-empty docs directories have `README.md` and `AGENTS.md`
- unresolved items are either empty or explicitly blocking
- roadmap and task board status agree
- implementation tasks link to product, design, API, and acceptance sources

## Red Lines

- Do not declare governance complete while verification fails.
- Do not ignore unresolved items that affect implementation.
- Do not treat generated indexes as optional.
