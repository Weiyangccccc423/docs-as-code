from __future__ import annotations

import re
from pathlib import Path


VERSION_FILE_NAME = "VERSION"
MAX_VERSION_FILE_BYTES = 256
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
