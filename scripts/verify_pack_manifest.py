from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


MANIFEST_NAME = "pack-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_SOURCE = "docs-as-code source workflow pack"
IGNORED_FILE_NAMES = {
    ".DS_Store",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}


@dataclass(frozen=True)
class ManifestFinding:
    code: str
    message: str
    path: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class ManifestReport:
    target: str
    manifest: str
    file_count: int
    findings: list[ManifestFinding]

    @property
    def ok(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)

    @property
    def errors(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "error"]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "target": self.target,
            "manifest": self.manifest,
            "file_count": self.file_count,
            "errors": list(self.errors),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pack_manifest(target: Path) -> ManifestReport:
    root = target.resolve()
    manifest_path = root / MANIFEST_NAME
    findings: list[ManifestFinding] = []
    listed_paths: set[str] = set()

    if not root.exists():
        findings.append(ManifestFinding("pack_manifest_target_missing", f"pack target does not exist: {root}", "."))
        return _report(root, manifest_path, listed_paths, findings)
    if not root.is_dir():
        findings.append(
            ManifestFinding("pack_manifest_target_not_directory", f"pack target is not a directory: {root}", ".")
        )
        return _report(root, manifest_path, listed_paths, findings)
    if not manifest_path.exists():
        findings.append(
            ManifestFinding("pack_manifest_missing", f"missing pack manifest: {MANIFEST_NAME}", MANIFEST_NAME)
        )
        return _report(root, manifest_path, listed_paths, findings)
    if not manifest_path.is_file():
        findings.append(
            ManifestFinding("pack_manifest_not_file", f"pack manifest is not a file: {MANIFEST_NAME}", MANIFEST_NAME)
        )
        return _report(root, manifest_path, listed_paths, findings)

    manifest = _load_manifest(manifest_path, findings)
    if manifest is None:
        return _report(root, manifest_path, listed_paths, findings)

    _check_manifest_identity(manifest, findings)
    files = manifest.get("files")
    if not isinstance(files, list):
        findings.append(
            ManifestFinding(
                "pack_manifest_invalid_schema",
                "invalid pack manifest: files must be a list",
                MANIFEST_NAME,
            )
        )
        return _report(root, manifest_path, listed_paths, findings)

    for item in files:
        _check_manifest_entry(root, item, listed_paths, findings)

    _check_unmanifested_files(root, listed_paths, findings)
    return _report(root, manifest_path, listed_paths, findings)


def _report(
    root: Path,
    manifest_path: Path,
    listed_paths: set[str],
    findings: list[ManifestFinding],
) -> ManifestReport:
    return ManifestReport(str(root), str(manifest_path), len(listed_paths), list(findings))


def _load_manifest(manifest_path: Path, findings: list[ManifestFinding]) -> dict[str, Any] | None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        findings.append(
            ManifestFinding(
                "pack_manifest_invalid_encoding",
                "invalid pack manifest encoding: expected UTF-8",
                MANIFEST_NAME,
            )
        )
        return None
    except json.JSONDecodeError as error:
        findings.append(
            ManifestFinding("pack_manifest_invalid_json", f"invalid pack manifest: {error.msg}", MANIFEST_NAME)
        )
        return None
    if not isinstance(manifest, dict):
        findings.append(
            ManifestFinding(
                "pack_manifest_invalid_schema",
                "invalid pack manifest: root must be an object",
                MANIFEST_NAME,
            )
        )
        return None
    return manifest


def _check_manifest_identity(manifest: dict[str, Any], findings: list[ManifestFinding]) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        findings.append(
            ManifestFinding(
                "pack_manifest_schema_version_invalid",
                f"pack manifest schema_version must be {MANIFEST_SCHEMA_VERSION}",
                MANIFEST_NAME,
            )
        )
    if manifest.get("source") != MANIFEST_SOURCE:
        findings.append(
            ManifestFinding(
                "pack_manifest_source_invalid",
                f"pack manifest source must be {MANIFEST_SOURCE}",
                MANIFEST_NAME,
            )
        )


def _check_manifest_entry(
    root: Path,
    item: object,
    listed_paths: set[str],
    findings: list[ManifestFinding],
) -> None:
    if not isinstance(item, dict):
        findings.append(
            ManifestFinding("pack_manifest_invalid_schema", "invalid pack manifest: file entry must be an object", MANIFEST_NAME)
        )
        return

    rel = item.get("path")
    if rel == MANIFEST_NAME:
        findings.append(
            ManifestFinding(
                "pack_manifest_reserved_path",
                f"pack manifest must not list itself: {MANIFEST_NAME}",
                MANIFEST_NAME,
            )
        )
        return
    if not _is_valid_manifest_relative_path(rel):
        findings.append(
            ManifestFinding(
                "pack_manifest_invalid_path",
                f"invalid pack manifest file path: {rel}",
                MANIFEST_NAME,
            )
        )
        return
    if rel in listed_paths:
        findings.append(
            ManifestFinding(
                "pack_manifest_duplicate_path",
                f"duplicate pack manifest path: {rel}",
                MANIFEST_NAME,
            )
        )
        return
    listed_paths.add(rel)

    expected_size = item.get("size_bytes")
    expected_hash = item.get("sha256")
    expected_executable = item.get("executable")
    if not _is_valid_manifest_size(expected_size):
        findings.append(
            ManifestFinding(
                "pack_manifest_size_missing",
                f"pack manifest file size is missing or invalid: {rel}",
                MANIFEST_NAME,
            )
        )
    if not _is_valid_sha256_digest(expected_hash):
        findings.append(
            ManifestFinding(
                "pack_manifest_hash_invalid",
                f"pack manifest file hash is missing or invalid: {rel}",
                MANIFEST_NAME,
            )
        )
    if not isinstance(expected_executable, bool):
        findings.append(
            ManifestFinding(
                "pack_manifest_executable_invalid",
                f"pack manifest executable flag is missing or invalid: {rel}",
                MANIFEST_NAME,
            )
        )

    path = root / rel
    if not path.exists():
        findings.append(ManifestFinding("pack_manifest_file_missing", f"pack manifest file is missing: {rel}", rel))
        return
    if not path.is_file() or path.is_symlink():
        findings.append(ManifestFinding("pack_manifest_file_not_file", f"pack manifest path is not a regular file: {rel}", rel))
        return

    if _is_valid_manifest_size(expected_size) and path.stat().st_size != expected_size:
        findings.append(ManifestFinding("pack_manifest_file_size_mismatch", f"pack manifest file size mismatch: {rel}", rel))
    if _is_valid_sha256_digest(expected_hash) and sha256_file(path) != expected_hash:
        findings.append(ManifestFinding("pack_manifest_file_hash_mismatch", f"pack manifest file hash mismatch: {rel}", rel))
    if isinstance(expected_executable, bool):
        actual_executable = bool(path.stat().st_mode & 0o111)
        if actual_executable != expected_executable:
            findings.append(
                ManifestFinding(
                    "pack_manifest_file_executable_mismatch",
                    f"pack manifest executable flag mismatch: {rel}",
                    rel,
                )
            )


def _check_unmanifested_files(root: Path, listed_paths: set[str], findings: list[ManifestFinding]) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if rel == MANIFEST_NAME or _is_ignored_file(path.relative_to(root)):
            continue
        if rel not in listed_paths:
            findings.append(
                ManifestFinding(
                    "pack_manifest_file_unmanifested",
                    f"pack file is not listed in manifest: {rel}",
                    rel,
                )
            )


def _is_ignored_file(rel: Path) -> bool:
    return rel.suffix == ".pyc" or any(part in IGNORED_FILE_NAMES for part in rel.parts)


def _is_valid_manifest_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_valid_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _is_valid_manifest_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("~"):
        return False
    windows = PureWindowsPath(value)
    if windows.is_absolute() or windows.drive:
        return False
    posix = PurePosixPath(value)
    if posix.is_absolute() or posix.as_posix() != value:
        return False
    return bool(posix.parts) and all(part not in {"", ".", ".."} for part in posix.parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an exported docs-as-code workflow-pack manifest.")
    parser.add_argument("target", nargs="?", type=Path, default=Path("."), help="Exported workflow-pack directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(report: ManifestReport) -> None:
    if report.ok:
        print(f"Pack manifest verification passed: {report.target}")
        return
    print(f"Pack manifest verification failed: {report.target}")
    for error in report.errors:
        print(f"- {error}")


def main() -> int:
    args = build_parser().parse_args()
    report = verify_pack_manifest(args.target)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
