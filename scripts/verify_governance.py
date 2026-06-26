from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


DOC_DIRS = {
    "product",
    "architecture",
    "ui",
    "api",
    "backend",
    "frontend",
    "tests",
    "decisions",
    "development",
    "agent-workflow",
}


@dataclass
class VerificationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def verify(root: Path) -> VerificationReport:
    root = root.resolve()
    report = VerificationReport()

    required_files = [
        "README.md",
        "AGENTS.md",
        "SPEC.md",
        "docs/README.md",
        "docs/AGENTS.md",
        "docs/unresolved.md",
        "docs/glossary.md",
        "docs/product/core/PRD.md",
        "docs/product/core/product-meta.md",
        "docs/product/core/source/source-manifest.json",
    ]
    for rel in required_files:
        if not (root / rel).exists():
            report.errors.append(f"missing required file: {rel}")

    docs_root = root / "docs"
    docs_agents = docs_root / "AGENTS.md"
    docs_agents_text = docs_agents.read_text(encoding="utf-8") if docs_agents.exists() else ""

    if docs_root.exists():
        for child in sorted(docs_root.iterdir()):
            if not child.is_dir():
                continue
            rel = f"docs/{child.name}"
            if _is_effectively_empty(child):
                continue
            if child.name not in DOC_DIRS and f"`{rel}/`" not in docs_agents_text:
                report.errors.append(f"{rel} is not registered in docs/AGENTS.md")
            if child.name in DOC_DIRS:
                for name in ("README.md", "AGENTS.md"):
                    if not (child / name).exists():
                        report.errors.append(f"{rel} is missing {name}")

    for path in [root / "README.md", docs_root / "README.md", docs_agents]:
        if path.exists():
            _check_reserved_markers(root, path, report)

    _check_product_source_manifest(root, report)

    return report


def _is_effectively_empty(path: Path) -> bool:
    return not any(child.name != ".gitkeep" for child in path.iterdir())


def _check_reserved_markers(root: Path, path: Path, report: VerificationReport) -> None:
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "预留" not in line and "[reserved]" not in line.lower():
            continue
        for match in re.finditer(r"docs/([a-z0-9-]+)", line):
            name = match.group(1)
            target = root / "docs" / name
            if target.exists() and target.is_dir() and not _is_effectively_empty(target):
                report.errors.append(f"reserved marker references non-empty docs/{name}")


def _check_product_source_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / "docs/product/core/source/source-manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.errors.append(f"invalid product source manifest: {error.msg}")
        return

    source = manifest.get("source")
    archive = manifest.get("archive")
    imported = manifest.get("import")
    if not isinstance(source, dict) or not isinstance(archive, dict) or not isinstance(imported, dict):
        report.errors.append("invalid product source manifest: missing source/archive/import objects")
        return

    status = imported.get("status")
    archived_rel = archive.get("path")
    if status == "no_source":
        report.errors.append("product source is missing; archive the original product document before design derivation")
        return
    if not isinstance(archived_rel, str) or not archived_rel:
        report.errors.append("invalid product source manifest: archive.path is missing")
        return

    archived_path = root / archived_rel
    if not archived_path.exists():
        report.errors.append(f"archived product source is missing: {archived_rel}")
        return

    expected_hash = archive.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        report.errors.append("invalid product source manifest: archive.sha256 is missing")
    elif _sha256(archived_path) != expected_hash:
        report.errors.append(f"archived product source hash mismatch: {archived_rel}")

    if imported.get("can_derive_design") is not True:
        report.errors.append(f"product source requires conversion before design derivation: {archived_rel}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify docs-as-code governance consistency.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to verify.")
    args = parser.parse_args()
    report = verify(Path(args.target))
    if report.errors:
        print("Governance verification failed:")
        for error in report.errors:
            print(f"- ERROR: {error}")
    if report.warnings:
        print("Governance warnings:")
        for warning in report.warnings:
            print(f"- WARN: {warning}")
    if report.ok:
        print("Governance verification passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
