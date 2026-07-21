from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path
from typing import Any

try:
    from .pack_version import PackVersionError, read_pack_version
    from .verify_pack import verify_pack
    from .verify_pack_manifest import verify_pack_manifest
except ImportError:  # pragma: no cover - direct script execution
    from pack_version import PackVersionError, read_pack_version
    from verify_pack import verify_pack
    from verify_pack_manifest import verify_pack_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "pack-manifest.json"
DEFAULT_OUTPUT = ROOT / "dist" / "docs-as-code-workflow-pack"
DEFAULT_ARCHIVE = ROOT / "dist" / "docs-as-code-workflow-pack.tar.gz"
REPRODUCIBLE_CREATED_AT = "1970-01-01T00:00:00Z"
ARCHIVE_ROOT_NAME = "docs-as-code-workflow-pack"
EXPORT_RESOURCE_PATHS = (
    ".github",
    ".gitignore",
    "AGENTS.md",
    "Makefile",
    "README.md",
    "VERSION",
    "bin",
    "references",
    "scripts",
    "skills",
    "templates",
    "tests",
    "workflows",
)
IGNORED_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".lycheecache",
    "__pycache__",
    "dist",
    "node_modules",
    ".venv",
}


class ExportError(Exception):
    def __init__(self, message: str, *, path: Path | None = None, code: str = "export_error") -> None:
        super().__init__(message)
        self.message = message
        self.path = path
        self.code = code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_files(root: Path = ROOT) -> list[Path]:
    files: list[Path] = []
    for rel_text in EXPORT_RESOURCE_PATHS:
        source = root / rel_text
        if not source.exists():
            raise ExportError(f"missing export resource: {rel_text}", path=source)
        if source.is_file():
            if not _is_ignored(source):
                files.append(source.relative_to(root))
            continue
        if not source.is_dir():
            raise ExportError(f"export resource is neither file nor directory: {rel_text}", path=source)
        for path in source.rglob("*"):
            if path.is_file() and not _is_ignored(path):
                files.append(path.relative_to(root))
    return sorted(dict.fromkeys(files), key=lambda item: item.as_posix())


def run_export(
    *,
    output: Path = DEFAULT_OUTPUT,
    archive: Path | None = DEFAULT_ARCHIVE,
    force: bool = False,
    check: bool = False,
    root: Path = ROOT,
) -> dict[str, object]:
    root = root.resolve()
    output = output.resolve()
    archive = archive.resolve() if archive is not None else None
    try:
        _reject_unsafe_destination(root, output)
        if archive is not None:
            _reject_unsafe_archive(root, output, archive)
        try:
            pack_version = read_pack_version(root)
        except PackVersionError as error:
            raise ExportError(
                error.message,
                path=error.path or root / "VERSION",
                code="pack_version_invalid",
            ) from error
        files = export_files(root)
        payload: dict[str, object] = {
            "ok": True,
            "check": check,
            "pack_version": pack_version,
            "source": str(root),
            "output": str(output),
            "archive": str(archive) if archive is not None else None,
            "file_count": len(files),
            "files": [rel.as_posix() for rel in files],
        }
        if check:
            payload["would_write"] = [*(rel.as_posix() for rel in files), MANIFEST_NAME]
            if archive is not None:
                payload["would_archive"] = str(archive)
            return payload
        if output.exists():
            if not force:
                raise ExportError(f"output already exists; pass --force to replace it: {output}", path=output)
            if not output.is_dir():
                raise ExportError(f"output exists and is not a directory: {output}", path=output)
            shutil.rmtree(output)
        _copy_files(root, output, files)
        manifest = _write_manifest(root, output, files, pack_version)
        manifest_verification = verify_pack_manifest(output)
        payload["manifest_verification"] = manifest_verification.to_dict()
        if not manifest_verification.ok:
            payload["ok"] = False
            payload["errors"] = ["exported pack failed verify_pack_manifest"]
            return payload
        verification = verify_pack(output)
        payload["manifest"] = str((output / MANIFEST_NAME).resolve())
        payload["manifest_sha256"] = sha256_file(output / MANIFEST_NAME)
        payload["verification"] = verification.to_dict()
        if not verification.ok:
            payload["ok"] = False
            payload["errors"] = ["exported pack failed verify_pack"]
            return payload
        if archive is not None:
            archive.parent.mkdir(parents=True, exist_ok=True)
            if archive.exists():
                if not force:
                    raise ExportError(f"archive already exists; pass --force to replace it: {archive}", path=archive)
                archive.unlink()
            _write_archive(output, archive)
            payload["archive_sha256"] = sha256_file(archive)
            payload["archive_size_bytes"] = archive.stat().st_size
        payload["manifest_file_count"] = len(manifest["files"])
        return payload
    except ExportError as error:
        return {
            "ok": False,
            "check": check,
            "source": str(root),
            "output": str(output),
            "archive": str(archive) if archive is not None else None,
            "code": error.code,
            "error": error.message,
            "path": str(error.path) if error.path is not None else "",
            "errors": [error.message],
        }
    except OSError as error:
        message = error.strerror or str(error)
        return {
            "ok": False,
            "check": check,
            "source": str(root),
            "output": str(output),
            "archive": str(archive) if archive is not None else None,
            "error": message,
            "path": str(error.filename) if error.filename else "",
            "errors": [message],
        }


def _copy_files(root: Path, output: Path, files: list[Path]) -> None:
    for rel in files:
        source = root / rel
        target = output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _write_manifest(root: Path, output: Path, files: list[Path], pack_version: str) -> dict[str, object]:
    entries = []
    for rel in files:
        path = output / rel
        entries.append(
            {
                "path": rel.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "executable": bool(path.stat().st_mode & 0o111),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "created_at": REPRODUCIBLE_CREATED_AT,
        "source": "docs-as-code source workflow pack",
        "pack_version": pack_version,
        "source_root": ".",
        "files": entries,
    }
    _write_json(output / MANIFEST_NAME, manifest)
    return manifest


def _write_archive(output: Path, archive: Path) -> None:
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for path in sorted(output.rglob("*"), key=lambda item: item.relative_to(output).as_posix()):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(output)
                    info = tar.gettarinfo(str(path), arcname=f"{ARCHIVE_ROOT_NAME}/{rel.as_posix()}")
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with path.open("rb") as handle:
                        tar.addfile(info, handle)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _reject_unsafe_destination(root: Path, output: Path) -> None:
    if output == root:
        raise ExportError("output must not be the source workflow-pack root", path=output)
    try:
        rel = output.relative_to(root)
    except ValueError:
        return
    if rel.parts and rel.parts[0] == "dist":
        return
    if rel.parts and rel.parts[0] in EXPORT_RESOURCE_PATHS:
        raise ExportError("output must not be inside an exported source resource", path=output)


def _reject_unsafe_archive(root: Path, output: Path, archive: Path) -> None:
    if archive == output or _is_relative_to(archive, output):
        raise ExportError("archive must not be written inside the exported pack directory", path=archive)
    try:
        rel = archive.relative_to(root)
    except ValueError:
        return
    if rel.parts and rel.parts[0] == "dist":
        return
    if rel.parts and rel.parts[0] in EXPORT_RESOURCE_PATHS:
        raise ExportError("archive must not be inside an exported source resource", path=archive)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _is_ignored(path: Path) -> bool:
    if path.name in IGNORED_NAMES or path.suffix == ".pyc":
        return True
    return any(part in IGNORED_NAMES for part in path.parts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the source docs-as-code workflow pack.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Directory to write the exported pack.")
    parser.add_argument(
        "--archive",
        type=Path,
        nargs="?",
        const=DEFAULT_ARCHIVE,
        default=DEFAULT_ARCHIVE,
        help="Optional tar.gz archive path. Defaults to dist/docs-as-code-workflow-pack.tar.gz.",
    )
    parser.add_argument("--no-archive", action="store_true", help="Export only the directory, without tar.gz.")
    parser.add_argument("--force", action="store_true", help="Replace an existing output directory or archive.")
    parser.add_argument("--check", action="store_true", help="Preview export inputs and outputs without writing files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    if payload.get("ok"):
        if payload.get("check"):
            print(f"Workflow pack export preflight passed: {payload.get('file_count')} files")
            print(f"Output: {payload.get('output')}")
            print(f"Archive: {payload.get('archive')}")
            return
        print(f"Workflow pack exported: {payload.get('output')}")
        if payload.get("archive"):
            print(f"Archive: {payload.get('archive')}")
        print(f"Files: {payload.get('file_count')}")
        return
    print(f"Workflow pack export failed: {payload.get('error')}")


def main() -> int:
    args = build_parser().parse_args()
    archive = None if args.no_archive else args.archive
    payload = run_export(output=args.output, archive=archive, force=args.force, check=args.check)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
