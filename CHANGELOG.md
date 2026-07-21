# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
