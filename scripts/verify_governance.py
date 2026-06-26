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

NON_BLOCKING_SCOPES = {"", "-", "none", "n/a", "na", "non-blocking", "non blocking", "resolved"}
SCAFFOLD_PLACEHOLDER = "governance:scaffold-placeholder"
WORKFLOW_PACK_SNAPSHOT_ROOT = "docs/agent-workflow/workflow-pack"


@dataclass
class VerificationFinding:
    code: str
    severity: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass
class VerificationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    findings: list[VerificationFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, code: str, message: str, path: str = "") -> None:
        self.errors.append(message)
        self.findings.append(VerificationFinding(code=code, severity="error", path=path, message=message))

    def add_warning(self, code: str, message: str, path: str = "") -> None:
        self.warnings.append(message)
        self.findings.append(VerificationFinding(code=code, severity="warning", path=path, message=message))


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
            report.add_error("missing_required_file", f"missing required file: {rel}", rel)

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
                report.add_error("docs_directory_unregistered", f"{rel} is not registered in docs/AGENTS.md", rel)
            if child.name in DOC_DIRS:
                for name in ("README.md", "AGENTS.md"):
                    if not (child / name).exists():
                        report.add_error("docs_directory_missing_governance_file", f"{rel} is missing {name}", f"{rel}/{name}")

    for path in [root / "README.md", docs_root / "README.md", docs_agents]:
        if path.exists():
            _check_reserved_markers(root, path, report)

    _check_product_source_manifest(root, report)
    _check_unresolved_items(root, report)
    _check_readme_indexes(root, report)
    _check_scaffold_placeholders(root, report)
    _check_workflow_pack_manifest(root, report)

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
                report.add_error("reserved_marker_stale", f"reserved marker references non-empty docs/{name}", f"docs/{name}")


def _check_product_source_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / "docs/product/core/source/source-manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.add_error(
            "product_source_manifest_invalid_json",
            f"invalid product source manifest: {error.msg}",
            "docs/product/core/source/source-manifest.json",
        )
        return

    source = manifest.get("source")
    archive = manifest.get("archive")
    imported = manifest.get("import")
    if not isinstance(source, dict) or not isinstance(archive, dict) or not isinstance(imported, dict):
        report.add_error(
            "product_source_manifest_invalid_schema",
            "invalid product source manifest: missing source/archive/import objects",
            "docs/product/core/source/source-manifest.json",
        )
        return

    status = imported.get("status")
    archived_rel = archive.get("path")
    if status == "no_source":
        report.add_error(
            "product_source_missing",
            "product source is missing; archive the original product document before design derivation",
            "docs/product/core/source/source-manifest.json",
        )
        return
    if not isinstance(archived_rel, str) or not archived_rel:
        report.add_error(
            "product_source_manifest_archive_path_missing",
            "invalid product source manifest: archive.path is missing",
            "docs/product/core/source/source-manifest.json",
        )
        return

    archived_path = root / archived_rel
    if not archived_path.exists():
        report.add_error("product_source_archive_missing", f"archived product source is missing: {archived_rel}", archived_rel)
        return

    expected_hash = archive.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        report.add_error(
            "product_source_manifest_archive_hash_missing",
            "invalid product source manifest: archive.sha256 is missing",
            "docs/product/core/source/source-manifest.json",
        )
    elif _sha256(archived_path) != expected_hash:
        report.add_error("product_source_hash_mismatch", f"archived product source hash mismatch: {archived_rel}", archived_rel)

    if imported.get("can_derive_design") is not True:
        report.add_error(
            "product_source_conversion_required",
            f"product source requires conversion before design derivation: {archived_rel}",
            archived_rel,
        )


def _check_unresolved_items(root: Path, report: VerificationReport) -> None:
    path = root / "docs/unresolved.md"
    if not path.exists():
        return
    rows = _markdown_table(path.read_text(encoding="utf-8"))
    if not rows:
        return
    header = [_normalize_cell(cell) for cell in rows[0]]
    required = ["id", "domain", "description", "blocking scope"]
    missing = [name for name in required if name not in header]
    if missing:
        report.add_error(
            "unresolved_table_missing_columns",
            f"docs/unresolved.md table is missing required columns: {', '.join(missing)}",
            "docs/unresolved.md",
        )
        return
    id_index = header.index("id")
    scope_index = header.index("blocking scope")
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        if len(row) <= max(id_index, scope_index):
            continue
        item_id = row[id_index].strip() or "(missing id)"
        blocking_scope = row[scope_index].strip()
        if _normalize_cell(blocking_scope) in NON_BLOCKING_SCOPES:
            continue
        report.add_error(
            "unresolved_blocking_item",
            f"blocking unresolved item {item_id} affects {blocking_scope}",
            "docs/unresolved.md",
        )


def _check_readme_indexes(root: Path, report: VerificationReport) -> None:
    docs_root = root / "docs"
    if not docs_root.exists():
        return
    for readme in sorted(docs_root.rglob("README.md")):
        directory = readme.parent
        readme_text = readme.read_text(encoding="utf-8")
        for child in sorted(directory.glob("*.md")):
            if child.name in {"README.md", "AGENTS.md"} or child.name.startswith("_"):
                continue
            if child.name in readme_text:
                continue
            rel_child = child.relative_to(root).as_posix()
            rel_readme = readme.relative_to(root).as_posix()
            report.add_error("docs_readme_unindexed_file", f"{rel_child} is not indexed in {rel_readme}", rel_child)


def _check_scaffold_placeholders(root: Path, report: VerificationReport) -> None:
    docs_root = root / "docs"
    if not docs_root.exists():
        return
    for path in sorted(docs_root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SCAFFOLD_PLACEHOLDER not in text:
            continue
        report.add_error(
            "governance_scaffold_placeholder",
            f"{rel} still contains a governance scaffold placeholder",
            rel,
        )


def _check_workflow_pack_manifest(root: Path, report: VerificationReport) -> None:
    manifest_path = root / WORKFLOW_PACK_SNAPSHOT_ROOT / "manifest.json"
    manifest_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/manifest.json"
    if not manifest_path.exists():
        report.add_error("workflow_pack_manifest_missing", f"missing workflow pack manifest: {manifest_rel}", manifest_rel)
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.add_error("workflow_pack_manifest_invalid_json", f"invalid workflow pack manifest: {error.msg}", manifest_rel)
        return
    files = manifest.get("files")
    if not isinstance(files, list):
        report.add_error("workflow_pack_manifest_invalid_schema", "invalid workflow pack manifest: files must be a list", manifest_rel)
        return
    snapshot_root = root / WORKFLOW_PACK_SNAPSHOT_ROOT
    for item in files:
        if not isinstance(item, dict):
            report.add_error("workflow_pack_manifest_invalid_schema", "invalid workflow pack manifest: file entry must be an object", manifest_rel)
            continue
        rel = item.get("path")
        expected_hash = item.get("sha256")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            report.add_error("workflow_pack_manifest_invalid_path", f"invalid workflow pack file path: {rel}", manifest_rel)
            continue
        path = snapshot_root / rel
        file_rel = f"{WORKFLOW_PACK_SNAPSHOT_ROOT}/{rel}"
        if not path.exists():
            report.add_error("workflow_pack_file_missing", f"workflow pack file is missing: {file_rel}", file_rel)
            continue
        if not isinstance(expected_hash, str) or not expected_hash:
            report.add_error("workflow_pack_manifest_hash_missing", f"workflow pack file hash is missing: {file_rel}", manifest_rel)
            continue
        if _sha256(path) != expected_hash:
            report.add_error("workflow_pack_file_hash_mismatch", f"workflow pack file hash mismatch: {file_rel}", file_rel)


def _markdown_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows


def _normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_separator_row(row: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row)


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
