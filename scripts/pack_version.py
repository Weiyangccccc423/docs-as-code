from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


VERSION_FILE_NAME = "VERSION"
MAX_VERSION_FILE_BYTES = 256
CHANGELOG_FILE_NAME = "CHANGELOG.md"
MAX_CHANGELOG_FILE_BYTES = 1024 * 1024
CHANGELOG_RELEASE_RE = re.compile(r"^## \[([^]]+)] - ([0-9]{4}-[0-9]{2}-[0-9]{2})$")
CHANGELOG_SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class PackVersionError(ValueError):
    def __init__(self, message: str, *, path: Path | None = None) -> None:
        self.message = message
        self.path = path
        super().__init__(message)


class PackChangelogError(ValueError):
    def __init__(self, message: str, *, path: Path | None = None) -> None:
        self.message = message
        self.path = path
        super().__init__(message)


@dataclass(frozen=True)
class PackChangelog:
    current_version: str
    current_release_date: str
    current_sections: tuple[str, ...]
    release_versions: tuple[str, ...]


def parse_pack_version(value: object) -> str:
    if not isinstance(value, str) or SEMVER_RE.fullmatch(value) is None:
        raise PackVersionError("workflow-pack version must be a strict SemVer 2.0 value")
    return value


def compare_pack_versions(left: str, right: str) -> int:
    """Compare two SemVer values by precedence, ignoring build metadata."""
    left = parse_pack_version(left)
    right = parse_pack_version(right)
    left_match = SEMVER_RE.fullmatch(left)
    right_match = SEMVER_RE.fullmatch(right)
    assert left_match is not None
    assert right_match is not None

    left_core = tuple(int(left_match.group(index)) for index in range(1, 4))
    right_core = tuple(int(right_match.group(index)) for index in range(1, 4))
    if left_core < right_core:
        return -1
    if left_core > right_core:
        return 1

    left_prerelease = _prerelease_identifiers(left_match.group(4))
    right_prerelease = _prerelease_identifiers(right_match.group(4))
    if not left_prerelease and not right_prerelease:
        return 0
    if not left_prerelease:
        return 1
    if not right_prerelease:
        return -1
    for left_identifier, right_identifier in zip(left_prerelease, right_prerelease):
        if left_identifier == right_identifier:
            continue
        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_identifier) < int(right_identifier) else 1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_identifier < right_identifier else 1
    if len(left_prerelease) < len(right_prerelease):
        return -1
    if len(left_prerelease) > len(right_prerelease):
        return 1
    return 0


def classify_pack_version_transition(current: str | None, target: str) -> str:
    """Classify a target refresh from an installed version to a source version."""
    target = parse_pack_version(target)
    if current is None:
        return "legacy_install"
    current = parse_pack_version(current)
    if current == target:
        return "same"
    precedence = compare_pack_versions(current, target)
    if precedence < 0:
        current_major = int(current.split(".", 1)[0])
        target_major = int(target.split(".", 1)[0])
        return "breaking_upgrade" if target_major > current_major else "compatible_upgrade"
    if precedence > 0:
        return "rollback"
    return "version_replacement"


def _prerelease_identifiers(value: str | None) -> tuple[str, ...]:
    return tuple(value.split(".")) if value else ()


def read_pack_version(root: Path) -> str:
    path = root / VERSION_FILE_NAME
    if path.is_symlink() or not path.is_file():
        raise PackVersionError(f"{VERSION_FILE_NAME} must be a regular file", path=path)
    try:
        size = path.stat().st_size
        if size > MAX_VERSION_FILE_BYTES:
            raise PackVersionError(
                f"{VERSION_FILE_NAME} must not exceed {MAX_VERSION_FILE_BYTES} bytes",
                path=path,
            )
        raw = path.read_bytes()
    except OSError as error:
        reason = error.strerror or str(error)
        raise PackVersionError(f"{VERSION_FILE_NAME} is unreadable: {reason}", path=path) from error
    if len(raw) > MAX_VERSION_FILE_BYTES:
        raise PackVersionError(
            f"{VERSION_FILE_NAME} must not exceed {MAX_VERSION_FILE_BYTES} bytes",
            path=path,
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PackVersionError(f"{VERSION_FILE_NAME} must be valid UTF-8", path=path) from error
    value = text[:-1] if text.endswith("\n") else text
    if "\n" in value or "\r" in value:
        raise PackVersionError(f"{VERSION_FILE_NAME} must contain exactly one line", path=path)
    try:
        return parse_pack_version(value)
    except PackVersionError as error:
        raise PackVersionError(error.message, path=path) from error


def read_pack_changelog(root: Path) -> PackChangelog:
    path = root / CHANGELOG_FILE_NAME
    if path.is_symlink() or not path.is_file():
        raise PackChangelogError(f"{CHANGELOG_FILE_NAME} must be a regular file", path=path)
    try:
        size = path.stat().st_size
        if size > MAX_CHANGELOG_FILE_BYTES:
            raise PackChangelogError(
                f"{CHANGELOG_FILE_NAME} must not exceed {MAX_CHANGELOG_FILE_BYTES} bytes",
                path=path,
            )
        raw = path.read_bytes()
    except OSError as error:
        reason = error.strerror or str(error)
        raise PackChangelogError(f"{CHANGELOG_FILE_NAME} is unreadable: {reason}", path=path) from error
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PackChangelogError(f"{CHANGELOG_FILE_NAME} must be valid UTF-8", path=path) from error
    return _parse_pack_changelog(text, read_pack_version(root), path)


def _parse_pack_changelog(text: str, current_version: str, path: Path) -> PackChangelog:
    lines = text.splitlines()
    if not lines or lines[0] != "# Changelog":
        raise PackChangelogError(f"{CHANGELOG_FILE_NAME} must start with '# Changelog'", path=path)
    for phrase in ("Keep a Changelog", "Semantic Versioning"):
        if phrase not in text:
            raise PackChangelogError(f"{CHANGELOG_FILE_NAME} must reference {phrase}", path=path)

    unreleased = [index for index, line in enumerate(lines) if line == "## [Unreleased]"]
    if len(unreleased) != 1:
        raise PackChangelogError(
            f"{CHANGELOG_FILE_NAME} must contain exactly one '## [Unreleased]' heading",
            path=path,
        )

    releases: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        match = CHANGELOG_RELEASE_RE.fullmatch(line)
        if match is not None:
            version, released_on = match.groups()
            try:
                version = parse_pack_version(version)
            except PackVersionError as error:
                raise PackChangelogError(
                    f"invalid changelog release version '{version}': {error.message}",
                    path=path,
                ) from error
            try:
                date.fromisoformat(released_on)
            except ValueError as error:
                raise PackChangelogError(
                    f"invalid changelog release date for {version}: {released_on}",
                    path=path,
                ) from error
            releases.append((index, version, released_on))
        elif line.startswith("## [") and line != "## [Unreleased]":
            raise PackChangelogError(f"invalid changelog release heading: {line}", path=path)

    if not releases:
        raise PackChangelogError(f"{CHANGELOG_FILE_NAME} must contain at least one release", path=path)
    if unreleased[0] > releases[0][0]:
        raise PackChangelogError("the Unreleased section must precede release entries", path=path)

    release_versions = tuple(version for _index, version, _released_on in releases)
    if len(release_versions) != len(set(release_versions)):
        raise PackChangelogError("changelog release versions must be unique", path=path)
    if release_versions[0] != current_version:
        raise PackChangelogError(
            f"current VERSION {current_version} must match the first changelog release {release_versions[0]}",
            path=path,
        )
    for newer, older in zip(release_versions, release_versions[1:]):
        if compare_pack_versions(newer, older) <= 0:
            raise PackChangelogError(
                f"changelog releases must be newest first: {newer} must precede {older}",
                path=path,
            )

    release_sections: list[tuple[str, ...]] = []
    for release_index, (start, version, _released_on) in enumerate(releases):
        end = releases[release_index + 1][0] if release_index + 1 < len(releases) else len(lines)
        sections = _release_sections_with_entries(lines[start + 1 : end])
        if not sections:
            raise PackChangelogError(
                f"changelog release {version} must contain a recognized section with at least one bullet",
                path=path,
            )
        release_sections.append(sections)

    return PackChangelog(
        current_version=current_version,
        current_release_date=releases[0][2],
        current_sections=release_sections[0],
        release_versions=release_versions,
    )


def _release_sections_with_entries(lines: list[str]) -> tuple[str, ...]:
    sections: list[str] = []
    active_section: str | None = None
    active_has_entry = False
    for line in lines:
        if line.startswith("### "):
            if active_section is not None and active_has_entry:
                sections.append(active_section)
            candidate = line[4:]
            active_section = candidate if candidate in CHANGELOG_SECTIONS else None
            active_has_entry = False
            continue
        if active_section is not None and re.match(r"^-\s+\S", line):
            active_has_entry = True
    if active_section is not None and active_has_entry:
        sections.append(active_section)
    return tuple(dict.fromkeys(sections))
