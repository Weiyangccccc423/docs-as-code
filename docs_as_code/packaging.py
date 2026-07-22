from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


EMBEDDED_PACK_RESOURCE_PATHS = (
    ".github",
    "AGENTS.md",
    "CHANGELOG.md",
    "MANIFEST.in",
    "Makefile",
    "README.md",
    "README.zh-CN.md",
    "VERSION",
    "bin",
    "docs_as_code",
    "pyproject.toml",
    "references",
    "scripts",
    "setup.py",
    "skills",
    "templates",
    "tests",
    "workflows",
)
IGNORED_NAMES = {
    ".DS_Store",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".lycheecache",
    "__pycache__",
}
MANIFEST_NAME = "pack-manifest.json"


class EmbeddedPackError(ValueError):
    pass


def _ignored(path: Path) -> bool:
    return path.suffix == ".pyc" or any(part in IGNORED_NAMES for part in path.parts)


def embedded_pack_files(source_root: Path) -> tuple[Path, ...]:
    source_root = source_root.resolve()
    files: list[Path] = []
    for rel_text in EMBEDDED_PACK_RESOURCE_PATHS:
        source = source_root / rel_text
        if not source.exists():
            raise EmbeddedPackError(f"missing embedded workflow-pack resource: {rel_text}")
        if source.is_symlink():
            raise EmbeddedPackError(f"embedded workflow-pack resource must not be a symlink: {rel_text}")
        if source.is_file():
            files.append(source.relative_to(source_root))
            continue
        if not source.is_dir():
            raise EmbeddedPackError(f"embedded workflow-pack resource is not a file or directory: {rel_text}")
        for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source_root).as_posix()):
            if path.is_symlink():
                raise EmbeddedPackError(
                    f"embedded workflow-pack file must not be a symlink: {path.relative_to(source_root)}"
                )
            if path.is_file() and not _ignored(path):
                files.append(path.relative_to(source_root))
    return tuple(sorted(dict.fromkeys(files), key=lambda path: path.as_posix()))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_embedded_pack(source_root: Path, destination: Path) -> tuple[Path, ...]:
    source_root = source_root.resolve()
    destination = destination.resolve()
    files = embedded_pack_files(source_root)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for rel in files:
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / rel, target)

    version = (destination / "VERSION").read_text(encoding="utf-8").strip()
    manifest = {
        "schema_version": 1,
        "created_at": "1970-01-01T00:00:00Z",
        "source": "docs-as-code source workflow pack",
        "pack_version": version,
        "source_root": ".",
        "files": [
            {
                "path": rel.as_posix(),
                "size_bytes": (destination / rel).stat().st_size,
                "sha256": _sha256(destination / rel),
                "executable": bool((destination / rel).stat().st_mode & 0o111),
            }
            for rel in files
        ],
    }
    manifest_path = destination / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return tuple(destination / rel for rel in (*files, Path(MANIFEST_NAME)))
