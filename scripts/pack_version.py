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
