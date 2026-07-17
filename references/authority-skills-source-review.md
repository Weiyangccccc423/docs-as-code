# Authority Skill Source Review

## Decision

The workflow pack accepts the 19 authority-routing skills in `references/authority-skills.lock.json` from the community-maintained `alirezarezvani/claude-skills` repository under the controls below.

This approval means the pinned skill trees are allowed as reviewed Agent guidance and deterministic review tooling. It does not make the skills official OpenAI, Anthropic, standards-body, or vendor guidance. Architecture, backend, security, API, data, reliability, and test decisions must still cite primary standards and project evidence, pass the workflow's deterministic checks, and receive the required human or authority review.

## Reviewed Source

| Field | Value |
| --- | --- |
| Repository | `https://github.com/alirezarezvani/claude-skills` |
| Immutable revision | `b2aa395350c5a96d094c0fea116636bfa25ad1d0` |
| Review date | `2026-07-17` |
| License | MIT, copyright Alireza Rezvani |
| Upstream controls observed | `SECURITY.md`, `CONTRIBUTING.md`, source-visible skills and scripts |
| Integrity scope | Complete selected skill tree, SHA-256 over relative path and file SHA-256 |

## Review Evidence

- Resolved upstream `HEAD` with `git ls-remote`, then cloned the exact revision for inspection.
- Compared every selected upstream skill directory to the installed Agent-environment copy with recursive file comparison; all 19 trees matched.
- Confirmed the selected 259 files contain no symbolic links.
- Recomputed every complete skill-tree digest with the same `skill-tree-sha256-v1` algorithm used by `scripts/authority_skills.py`.
- Confirmed the repository root MIT license and reviewed upstream security and contribution policies.
- Scanned selected scripts for subprocess, shell execution, network, dynamic evaluation, destructive filesystem, and write patterns. The reviewed trees include explicit output-file writers and a backend load-test client; these capabilities must run only through task-specific reviewed commands and workflow approval boundaries.
- The pinned commit carries a Git signature, but its public key was not available in the review environment. The immutable commit SHA plus independently recorded tree digests are therefore the enforced integrity controls.

## Accepted Paths

| Skill | Repository path |
| --- | --- |
| `a11y-audit` | `engineering-team/a11y-audit/skills/a11y-audit` |
| `api-design-reviewer` | `engineering/skills/api-design-reviewer` |
| `ci-cd-pipeline-builder` | `engineering/skills/ci-cd-pipeline-builder` |
| `database-designer` | `engineering/skills/database-designer` |
| `database-schema-designer` | `engineering/skills/database-schema-designer` |
| `migration-architect` | `engineering/skills/migration-architect` |
| `observability-designer` | `engineering/skills/observability-designer` |
| `performance-profiler` | `engineering/skills/performance-profiler` |
| `playwright-pro` | `engineering-team/playwright-pro/skills/pw` |
| `security-pen-testing` | `engineering-team/skills/security-pen-testing` |
| `senior-architect` | `engineering-team/skills/senior-architect` |
| `senior-backend` | `engineering-team/skills/senior-backend` |
| `senior-frontend` | `engineering-team/skills/senior-frontend` |
| `senior-fullstack` | `engineering-team/skills/senior-fullstack` |
| `senior-qa` | `engineering-team/skills/senior-qa` |
| `senior-security` | `engineering-team/skills/senior-security` |
| `slo-architect` | `engineering/skills/slo-architect` |
| `tech-debt-tracker` | `engineering/skills/tech-debt-tracker` |
| `tech-stack-evaluator` | `engineering-team/skills/tech-stack-evaluator` |

## Runtime Controls

- Installation always requires explicit approval because it uses network access and writes to the Agent environment.
- Install only the exact repository path at the exact 40-character revision in the lock.
- Stop authority-dependent work when a skill is missing, duplicated, source-unregistered, or does not match its complete tree digest.
- Do not execute a skill's scripts merely because the skill is approved. Inspect the work package, script arguments, target paths, network effects, and write behavior for the current task.
- Treat generated recommendations as review input. Product sources, repository evidence, primary standards, and deterministic gates remain controlling.

## Upgrade Procedure

1. Resolve a proposed immutable upstream commit and review the diff from the currently locked revision.
2. Recheck license, source ownership, security policy, selected paths, symlinks, executable behavior, network access, and filesystem writes.
3. Run each selected skill's relevant tests or deterministic tools in an isolated workspace.
4. Recompute complete skill-tree digests and update the lock, review date, and review evidence in one commit.
5. Run `python3 scripts/authority_skills.py --strict-provenance --json`, `make test`, and `make verify-pack` before release.

Do not follow a mutable branch, tag, marketplace alias, or latest-version pointer in the authority skill lock.
