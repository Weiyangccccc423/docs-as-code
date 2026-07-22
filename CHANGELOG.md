# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added an installable Python wheel that embeds and integrity-manifests the complete workflow pack.
- Added the short `dac` CLI with `init`, `doctor`, `status`, `next`, `verify`, `upgrade`, and command-specific help; retained `docs-as-code` as a compatibility alias.
- Added product-document auto-discovery from the project root plus explicit `PRODUCT`, `-C`, read-only `--check`, and machine-readable `--json` interfaces.
- Added bounded human-readable summaries for all `dac` operations and command-specific examples for every operational subcommand.
- Added explicit `dac next --apply` execution with snapshot re-assertion, target-bound command validation, bounded step evidence, and mandatory workflow refresh.
- Added bounded `dac next` route modes so executable actions, manual work, approvals, blockers, terminal completion, and failed-action recovery are distinguishable without parsing JSON.
- Added a guided `dac help` page covering product placement, first-run steps, read-only previews, and command-specific help.
- Added a manifest-checked POSIX `bin/dac` wrapper so exported workflow packs expose the same short CLI and help without package installation.
- Added manifest-checked source-checkout and editable-install execution without writing generated trust evidence into the checkout.

### Changed

- Reworked the GitHub README into a concise project overview with the complete operational reference kept in a collapsible section.
- Added a concise Chinese GitHub README with links between the Chinese and English project introductions.
- Made installation, product-document placement, `dac init`, and `dac --help` the primary consumer path while retaining unpacked source-pack commands for offline and advanced operation.
- `dac init` now requires exactly one selected product document, pins that preflight path into apply, and stops before target writes when discovery returns zero or multiple candidates.

## [2.0.0] - 2026-07-21

### Added

- Added `source_identity.artifact_verification` evidence with manifest presence, verification status, manifest SHA-256, and finding codes.
- Added high-risk refresh coverage for missing, tampered, valid, and drifted workflow-pack artifacts.

### Changed

- Breaking upgrades, rollbacks, version replacements, and invalid or conflicting installed-version repairs now require an exported workflow-pack artifact whose `pack-manifest.json` verifies successfully.
- Same-version, compatible-upgrade, and clean legacy-install refreshes remain usable from a source checkout.

### Security

- Version-transition approval and a matching migration plan can no longer override missing or failed workflow-pack artifact integrity evidence.

## [1.0.0] - 2026-07-21

### Added

- Added deterministic runtime migration plan IDs bound to source content, target governance evidence, transition identity, target path, and managed scope.
- Added `--expect-migration-plan` so reviewed high-risk migration approvals cannot be reused after source or target drift.

### Changed

- High-risk runtime refresh now requires both `--approve-version-transition` and the exact reviewed migration `plan_id` before any target write.

## [0.3.0] - 2026-07-21

### Added

- Added structured runtime migration plans with exact preflight, apply, verification, and workflow-resume argv for every refresh.
- Added explicit preserved project-document roots and trusted-artifact rollback requirements to runtime refresh evidence.

### Changed

- High-risk workflow-pack transitions now expose ordered, approval-guarded migration steps and keep target files unchanged until approval.

## [0.2.0] - 2026-07-21

### Added

- Added strict SemVer precedence and installed-version evidence to target runtime refresh plans.
- Added explicit transition classifications for compatible upgrades, breaking upgrades, rollbacks, build-metadata replacements, and legacy installations.

### Changed

- Breaking upgrades, rollbacks, version replacements, and conflicting or invalid installed-version evidence now require `--approve-version-transition` after a reviewed check.
- Same-version refreshes, compatible upgrades, and clean legacy installations remain automatic and preserve product, design, planning, and implementation documents.

## [0.1.0] - 2026-07-21

### Added

- Added the reusable empty-folder-to-governed-repository workflow covering product archival, conversion, structuring, design derivation, implementation planning, execution, and verification.
- Added target-local governance commands, environment inventory and reviewed repair, authority-skill provenance locks, structured design and implementation review evidence, and snapshot-guarded resume behavior.
- Added deterministic source-pack export, integrity manifests, artifact smoke tests, real-stack acceptance fixtures, and a local-first release gate.

[Unreleased]: https://github.com/Weiyangccccc423/docs-as-code/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/Weiyangccccc423/docs-as-code/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/Weiyangccccc423/docs-as-code/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/Weiyangccccc423/docs-as-code/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Weiyangccccc423/docs-as-code/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Weiyangccccc423/docs-as-code/releases/tag/v0.1.0
