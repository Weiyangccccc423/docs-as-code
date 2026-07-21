# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Weiyangccccc423/docs-as-code/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Weiyangccccc423/docs-as-code/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Weiyangccccc423/docs-as-code/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Weiyangccccc423/docs-as-code/releases/tag/v0.1.0
