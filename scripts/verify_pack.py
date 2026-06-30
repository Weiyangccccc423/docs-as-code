from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from .verify_governance import RUNTIME_REQUIRED_PATHS, WORKFLOW_PACK_REQUIRED_PATHS
except ImportError:  # pragma: no cover - direct script execution
    from verify_governance import RUNTIME_REQUIRED_PATHS, WORKFLOW_PACK_REQUIRED_PATHS


WORKFLOW_PACK_RESOURCE_PATHS = (
    "README.md",
    "workflows",
    "skills",
    "references",
    "templates",
)
SOURCE_PACK_REQUIRED_PATHS = tuple(
    dict.fromkeys(
        (
            "README.md",
            "AGENTS.md",
            "Makefile",
            "scripts/verify_pack.py",
            *(path.as_posix() for path in RUNTIME_REQUIRED_PATHS),
            *WORKFLOW_PACK_REQUIRED_PATHS,
        )
    )
)
IGNORED_PACK_FILE_NAMES = {".DS_Store", "manifest.json"}


@dataclass(frozen=True)
class PackFinding:
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
class PackReport:
    target: str
    findings: list[PackFinding]

    @property
    def errors(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[str]:
        return [finding.message for finding in self.findings if finding.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "target": self.target,
            "errors": self.errors,
            "warnings": self.warnings,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def verify_pack(root: Path) -> PackReport:
    root = root.resolve()
    findings: list[PackFinding] = []
    if not root.exists():
        findings.append(
            PackFinding(
                "pack_target_missing",
                f"pack target does not exist: {root}",
                ".",
            )
        )
        return PackReport(str(root), findings)
    if not root.is_dir():
        findings.append(
            PackFinding(
                "pack_target_not_directory",
                f"pack target is not a directory: {root}",
                ".",
            )
        )
        return PackReport(str(root), findings)

    _check_required_files(root, findings)
    _check_skill_frontmatter(root, findings)
    _check_workflow_pack_file_list(root, findings)
    return PackReport(str(root), findings)


def _check_required_files(root: Path, findings: list[PackFinding]) -> None:
    for rel in SOURCE_PACK_REQUIRED_PATHS:
        path = root / rel
        if not path.exists():
            findings.append(
                PackFinding(
                    "pack_required_file_missing",
                    f"missing required pack file: {rel}",
                    rel,
                )
            )
        elif not path.is_file():
            findings.append(
                PackFinding(
                    "pack_required_file_not_file",
                    f"required pack path is not a file: {rel}",
                    rel,
                )
            )


def _check_skill_frontmatter(root: Path, findings: list[PackFinding]) -> None:
    skills_root = root / "skills"
    if not skills_root.exists() or not skills_root.is_dir():
        return
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        rel = Path("skills") / skill_dir.name / "SKILL.md"
        skill_file = root / rel
        if not skill_file.exists():
            findings.append(
                PackFinding(
                    "pack_skill_missing_file",
                    f"missing skill file: {rel.as_posix()}",
                    rel.as_posix(),
                )
            )
            continue
        if not skill_file.is_file():
            findings.append(
                PackFinding(
                    "pack_skill_file_not_file",
                    f"skill path is not a file: {rel.as_posix()}",
                    rel.as_posix(),
                )
            )
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_skill_invalid_encoding",
                    f"skill file must be UTF-8 Markdown: {rel.as_posix()}",
                    rel.as_posix(),
                )
            )
            continue
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_skill_unreadable",
                    f"skill file is unreadable: {rel.as_posix()}: {_os_error_reason(error)}",
                    rel.as_posix(),
                )
            )
            continue
        _check_single_skill_frontmatter(skill_dir.name, rel.as_posix(), text, findings)


def _check_single_skill_frontmatter(
    skill_name: str,
    rel: str,
    text: str,
    findings: list[PackFinding],
) -> None:
    if not text.startswith("---\n"):
        findings.append(
            PackFinding(
                "pack_skill_frontmatter_missing",
                f"skill file missing frontmatter: {rel}",
                rel,
            )
        )
        return
    parts = text.split("---", 2)
    if len(parts) < 3:
        findings.append(
            PackFinding(
                "pack_skill_frontmatter_unclosed",
                f"skill file frontmatter is not closed: {rel}",
                rel,
            )
        )
        return
    frontmatter = parts[1].strip()
    if not re.search(rf"(?m)^name:\s*{re.escape(skill_name)}$", frontmatter):
        findings.append(
            PackFinding(
                "pack_skill_name_mismatch",
                f"skill frontmatter name must match directory: {rel}",
                rel,
            )
        )
    if not re.search(r"(?m)^description:\s*Use when .+", frontmatter):
        findings.append(
            PackFinding(
                "pack_skill_description_invalid",
                f"skill frontmatter description must start with 'Use when': {rel}",
                rel,
            )
        )


def _check_workflow_pack_file_list(root: Path, findings: list[PackFinding]) -> None:
    copied = [path.as_posix() for path in _iter_workflow_pack_files(root)]
    required = list(WORKFLOW_PACK_REQUIRED_PATHS)
    copied_set = set(copied)
    required_set = set(required)
    for rel in sorted(required_set - copied_set):
        findings.append(
            PackFinding(
                "pack_snapshot_required_file_missing",
                f"workflow-pack snapshot source file is missing: {rel}",
                rel,
            )
        )
    for rel in sorted(copied_set - required_set):
        findings.append(
            PackFinding(
                "pack_snapshot_unverified_file",
                f"workflow-pack source file is not listed in verifier required paths: {rel}",
                rel,
            )
        )
    if copied != required and copied_set == required_set:
        findings.append(
            PackFinding(
                "pack_snapshot_order_mismatch",
                "workflow-pack snapshot file order differs from verifier required paths",
                "docs/agent-workflow/workflow-pack/manifest.json",
            )
        )


def _iter_workflow_pack_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in WORKFLOW_PACK_RESOURCE_PATHS:
        source = root / rel
        if not source.exists():
            continue
        if source.is_file():
            if not _is_ignored_pack_file(source):
                files.append(Path(rel))
            continue
        for path in sorted(source.rglob("*")):
            if path.is_file() and not _is_ignored_pack_file(path):
                files.append(path.relative_to(root))
    return sorted(files, key=lambda path: path.as_posix())


def _is_ignored_pack_file(path: Path) -> bool:
    parts = set(path.parts)
    return (
        "__pycache__" in parts
        or ".git" in parts
        or path.suffix == ".pyc"
        or path.name in IGNORED_PACK_FILE_NAMES
    )


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify workflow-pack source structure.")
    parser.add_argument("target", nargs="?", default=".", help="Workflow-pack repository root.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable pack report.")
    args = parser.parse_args()

    report = verify_pack(Path(args.target))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if report.ok else 1
    if report.ok:
        print("Workflow pack verification passed.")
        return 0
    print("Workflow pack verification failed:")
    for error in report.errors:
        print(f"- ERROR: {error}")
    for warning in report.warnings:
        print(f"- WARN: {warning}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
