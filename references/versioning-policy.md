# Workflow-Pack Versioning Policy

This workflow pack follows Semantic Versioning 2.0.0. The top-level `VERSION` is the sole version source; manifests and target state contain evidence copies, not independent version sources.

`CHANGELOG.md` is the reviewed consumer-facing release history. It is not a version source: its newest release heading must match `VERSION`, use an ISO date, contain at least one Keep a Changelog category with a concrete entry, and preserve strict newest-first SemVer order.

## Version Changes

- **Major:** increment for an incompatible workflow, command, generated-document, manifest, or state contract change that requires consumer migration.
- **Minor:** increment for a backward-compatible workflow capability, generated artifact, command, or verification rule.
- **Patch:** increment for a backward-compatible correction that does not add a governed capability or require consumer migration.
- Pre-release and build identifiers may be used only when their lifecycle and distribution purpose are documented in the release evidence.

The proposed version and its Major, Minor, or Patch classification must be reviewed before export or tagging. A release change updates `VERSION` and adds the matching reviewed `CHANGELOG.md` entry in one coherent change; exporters, runtime bootstrap, and verifiers copy or compare that value. Do not edit `pack-manifest.json`, runtime manifests, workflow-pack snapshot manifests, or `.governance/state.json` as version sources.

## Release Boundary

Run local source-pack tests, source verification, changelog validation, deterministic export, manifest verification, and artifact smoke validation before a release is accepted. The workflow does not tag or publish automatically. Tagging, distribution, and remote publication remain separately reviewed operations.

The exported `pack-manifest.json` and every generated target's runtime manifest, workflow-pack snapshot manifest, and governance state must match the packaged `VERSION`. A missing, invalid, or mismatched value blocks verification.

## Upgrade And Rollback

Use target `runtime refresh --check --json` from a trusted source workflow-pack checkout before applying an upgrade. Inspect `version_transition.from_version`, `to_version`, `classification`, `evidence_status`, `candidate_versions`, `approval_required`, and `can_apply`, then follow the returned `migration_plan` steps and scope. The deterministic classifications are `same`, `compatible_upgrade`, `breaking_upgrade`, `rollback`, `version_replacement`, and `legacy_install`; SemVer precedence ignores build metadata, so changing only build metadata is a `version_replacement` rather than an upgrade.

Write mode may apply `same`, `compatible_upgrade`, and clean `legacy_install` transitions without extra approval. A breaking upgrade, rollback, build-metadata replacement, invalid version evidence, or disagreement between snapshot `VERSION` and state `workflow_pack_version` requires a reviewed check result plus `--approve-version-transition`. Without that flag, write mode fails before changing any target file. Approval authorizes only the exact source checkout used by that command; it does not waive post-refresh verification or migration work required by a Major release.

Successful write-mode runtime refresh records the new workflow-pack version while replacing only governed runtime and snapshot files; it must not rewrite product, design, planning, or implementation documents.

Rollback uses a previously verified artifact and the same check-then-apply procedure, followed by the explicit version-transition approval. The migration plan marks `requires_trusted_artifact: true` for rollback and other high-risk transitions. Do not reconstruct an earlier version by editing generated manifests or state. Re-run target-local verification after either upgrade or rollback.

## References

- Semantic Versioning 2.0.0: `https://semver.org/spec/v2.0.0.html`
- Keep a Changelog: `https://keepachangelog.com/en/1.1.0/`
- SLSA provenance model: `https://slsa.dev/spec/v1.2/provenance`
