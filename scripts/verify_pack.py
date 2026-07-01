from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

try:
    from .verify_governance import (
        RUNTIME_EXECUTABLE_PATHS,
        RUNTIME_REQUIRED_PATHS,
        WORKFLOW_PACK_REQUIRED_PATHS,
    )
except ImportError:  # pragma: no cover - direct script execution
    from verify_governance import RUNTIME_EXECUTABLE_PATHS, RUNTIME_REQUIRED_PATHS, WORKFLOW_PACK_REQUIRED_PATHS


WORKFLOW_PACK_RESOURCE_PATHS = (
    "README.md",
    "workflows",
    "skills",
    "references",
    "templates",
)
PACK_LINK_CHECK_RESOURCE_PATHS = (
    "README.md",
    "AGENTS.md",
    "workflows",
    "skills",
    "references",
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
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKDOWN_REFERENCE_DEFINITION_RE = re.compile(r"^\s{0,3}\[[^\]]+]:\s*(\S+)", re.MULTILINE)
SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
PHASE_WORKFLOW_PATHS = (
    "workflows/01-empty-repo-initialization.md",
    "workflows/02-product-document-archiving.md",
    "workflows/03-product-structuring.md",
    "workflows/04-design-derivation.md",
    "workflows/05-verification-and-drift-control.md",
)
PHASE_WORKFLOW_REQUIRED_SECTIONS = (
    "Input",
    "Skills",
    "Procedure",
    "Output",
    "Verification",
    "Stop Conditions",
)


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
    _check_workflow_pack_file_encoding(root, findings)
    _check_runtime_executable_bits(root, findings)
    _check_phase_order_docs(root, findings)
    _check_phase_primary_skill_alignment(root, findings)
    _check_phase_workflow_sections(root, findings)
    _check_skill_frontmatter(root, findings)
    _check_skill_references(root, findings)
    _check_local_markdown_links(root, findings)
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


def _check_workflow_pack_file_encoding(root: Path, findings: list[PackFinding]) -> None:
    for rel_path in _iter_workflow_pack_files(root):
        rel = rel_path.as_posix()
        path = root / rel_path
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_file_invalid_encoding",
                    f"workflow-pack source file must be UTF-8: {rel}",
                    rel,
                )
            )
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_file_unreadable",
                    f"workflow-pack source file is unreadable: {rel}: {_os_error_reason(error)}",
                    rel,
                )
            )


def _check_runtime_executable_bits(root: Path, findings: list[PackFinding]) -> None:
    for rel_path in RUNTIME_EXECUTABLE_PATHS:
        rel = rel_path.as_posix()
        path = root / rel_path
        if not path.exists() or not path.is_file():
            continue
        if path.stat().st_mode & 0o111:
            continue
        findings.append(
            PackFinding(
                "pack_runtime_file_not_executable",
                f"runtime wrapper is not executable: {rel}",
                rel,
            )
            )


def _check_phase_order_docs(root: Path, findings: list[PackFinding]) -> None:
    readme = root / "README.md"
    if readme.is_file():
        try:
            text = readme.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        workflow_order = _ordered_numbered_backticked_values(_markdown_section(text, "Workflow Order") or "")
        expected = list(PHASE_WORKFLOW_PATHS)
        if workflow_order != expected:
            findings.append(
                PackFinding(
                    "pack_workflow_order_mismatch",
                    "README.md Workflow Order must match phase workflow files",
                    "README.md",
                )
            )

    overview = root / "workflows/00-overview.md"
    if overview.is_file():
        try:
            text = overview.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = ""
        phase_map = _phase_map_numbers(_markdown_section(text, "Phase Map") or "")
        expected_numbers = [Path(path).name.split("-", 1)[0] for path in PHASE_WORKFLOW_PATHS]
        if phase_map != expected_numbers:
            findings.append(
                PackFinding(
                    "pack_phase_map_mismatch",
                    "workflows/00-overview.md Phase Map must match phase workflow files",
                    "workflows/00-overview.md",
                )
            )


def _check_phase_primary_skill_alignment(root: Path, findings: list[PackFinding]) -> None:
    overview = root / "workflows/00-overview.md"
    if not overview.is_file():
        return
    try:
        overview_text = overview.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    phase_map = _phase_map_primary_skills(_markdown_section(overview_text, "Phase Map") or "")
    if not phase_map:
        return

    for rel in PHASE_WORKFLOW_PATHS:
        phase = Path(rel).name.split("-", 1)[0]
        expected_skills = phase_map.get(phase, [])
        if not expected_skills:
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        workflow_skills = set(_extract_skill_tokens(_markdown_section(text, "Skills") or ""))
        missing = [skill for skill in expected_skills if skill not in workflow_skills]
        if missing:
            findings.append(
                PackFinding(
                    "pack_phase_primary_skill_missing",
                    f"{rel} Skills section is missing overview primary skill(s): {', '.join(missing)}",
                    rel,
                )
            )


def _check_phase_workflow_sections(root: Path, findings: list[PackFinding]) -> None:
    for rel in PHASE_WORKFLOW_PATHS:
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_workflow_invalid_encoding",
                    f"workflow file must be UTF-8 Markdown: {rel}",
                    rel,
                )
            )
            continue
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_workflow_unreadable",
                    f"workflow file is unreadable: {rel}: {_os_error_reason(error)}",
                    rel,
                )
            )
            continue
        ordered_sections = [_normalize_heading(match) for match in re.findall(r"(?m)^##\s+(.+?)\s*$", text)]
        sections = set(ordered_sections)
        for section in PHASE_WORKFLOW_REQUIRED_SECTIONS:
            if _normalize_heading(section) not in sections:
                findings.append(
                    PackFinding(
                        "pack_workflow_section_missing",
                        f"workflow phase missing section '{section}': {rel}",
                        rel,
                    )
            )
        if all(_normalize_heading(section) in sections for section in PHASE_WORKFLOW_REQUIRED_SECTIONS):
            required_positions = [
                ordered_sections.index(_normalize_heading(section))
                for section in PHASE_WORKFLOW_REQUIRED_SECTIONS
            ]
            if required_positions != sorted(required_positions):
                findings.append(
                    PackFinding(
                        "pack_workflow_section_order_mismatch",
                        "workflow phase sections must appear in operating-model order: "
                        + ", ".join(PHASE_WORKFLOW_REQUIRED_SECTIONS),
                        rel,
                    )
                )


def _check_skill_references(root: Path, findings: list[PackFinding]) -> None:
    skill_names = _available_skill_names(root)
    references: dict[str, set[str]] = {}
    for rel, section in _skill_reference_sections():
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        section_text = _markdown_section(text, section)
        if section_text is None:
            continue
        for skill in _extract_skill_tokens(section_text):
            references.setdefault(skill, set()).add(rel)
            if skill in skill_names:
                continue
            findings.append(
                PackFinding(
                    "pack_skill_reference_missing",
                    f"{rel} references missing skill: {skill}",
                    rel,
                )
            )
    for skill in sorted(skill_names - set(references)):
        findings.append(
            PackFinding(
                "pack_skill_unreferenced",
                f"skill is not referenced by workflow routing: {skill}",
                f"skills/{skill}/SKILL.md",
            )
        )


def _check_local_markdown_links(root: Path, findings: list[PackFinding]) -> None:
    for path in _iter_pack_link_check_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(
                PackFinding(
                    "pack_markdown_invalid_encoding",
                    f"pack Markdown file must be UTF-8: {rel}",
                    rel,
                )
            )
            continue
        except OSError as error:
            findings.append(
                PackFinding(
                    "pack_markdown_unreadable",
                    f"pack Markdown file is unreadable: {rel}: {_os_error_reason(error)}",
                    rel,
                )
            )
            continue
        for target in _extract_local_markdown_link_targets(text):
            reference = _resolve_local_markdown_link(root, path, target)
            if reference is None:
                continue
            reference_rel, exists = reference
            if exists:
                continue
            findings.append(
                PackFinding(
                    "pack_local_markdown_link_missing",
                    f"{rel} links to missing local Markdown target: {reference_rel}",
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


def _normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _available_skill_names(root: Path) -> set[str]:
    skills_root = root / "skills"
    if not skills_root.exists() or not skills_root.is_dir():
        return set()
    return {
        path.name
        for path in skills_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }


def _skill_reference_sections() -> list[tuple[str, str]]:
    sections = [("workflows/00-overview.md", "Phase Map")]
    sections.extend((rel, "Skills") for rel in PHASE_WORKFLOW_PATHS)
    sections.append(("skills/using-governance-workflow/SKILL.md", "Route"))
    return sections


def _markdown_section(text: str, heading: str) -> str | None:
    pattern = re.compile(r"(?m)^##\s+(.+?)\s*$")
    matches = list(pattern.finditer(text))
    wanted = _normalize_heading(heading)
    for index, match in enumerate(matches):
        if _normalize_heading(match.group(1)) != wanted:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[start:end]
    return None


def _ordered_numbered_backticked_values(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        if not re.match(r"^\s*[0-9]+\.\s+", line):
            continue
        match = re.search(r"`([^`\n]+)`", line)
        if match:
            values.append(match.group(1).strip())
    return values


def _phase_map_numbers(text: str) -> list[str]:
    numbers: list[str] = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[0-9]{2}", cells[0]):
            continue
        numbers.append(cells[0])
    return numbers


def _phase_map_primary_skills(text: str) -> dict[str, list[str]]:
    skills_by_phase: dict[str, list[str]] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[0-9]{2}", cells[0]):
            continue
        skills_by_phase[cells[0]] = _extract_skill_tokens(cells[2])
    return skills_by_phase


def _extract_skill_tokens(text: str) -> list[str]:
    text = _strip_fenced_markdown_code(text)
    tokens = []
    for token in re.findall(r"`([^`\n]+)`", text):
        token = token.strip()
        if SKILL_NAME_RE.fullmatch(token):
            tokens.append(token)
    return tokens


def _iter_pack_link_check_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in PACK_LINK_CHECK_RESOURCE_PATHS:
        source = root / rel
        if not source.exists():
            continue
        if source.is_file():
            if source.suffix == ".md" and not _is_ignored_pack_file(source):
                files.append(source)
            continue
        for path in sorted(source.rglob("*.md")):
            if path.is_file() and not _is_ignored_pack_file(path):
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _extract_local_markdown_link_targets(text: str) -> list[str]:
    text = _strip_markdown_code(text)
    targets = [match.group(1) for match in MARKDOWN_LINK_RE.finditer(text)]
    targets.extend(match.group(1) for match in MARKDOWN_REFERENCE_DEFINITION_RE.finditer(text))
    return targets


def _resolve_local_markdown_link(root: Path, source_path: Path, target: str) -> tuple[str, bool] | None:
    raw = target.strip()
    target = raw.strip("`").strip("<>").strip().rstrip(".,;")
    if not target or target.startswith("#") or _is_external_reference_target(target):
        return None
    target = target.replace("\\", "/").split("#", 1)[0].split("?", 1)[0]
    if target.startswith("/"):
        target = target.lstrip("/")
        base = root
    else:
        base = source_path.parent
    if not target.endswith(".md"):
        return None
    candidate = (base / Path(target)).resolve()
    try:
        rel = candidate.relative_to(root.resolve()).as_posix()
    except ValueError:
        return (target, False)
    return (rel, candidate.is_file())


def _is_external_reference_target(target: str) -> bool:
    lowered = target.lower()
    return (
        "://" in lowered
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
        or lowered.startswith("urn:")
    )


def _strip_markdown_code(text: str) -> str:
    text = _strip_fenced_markdown_code(text)
    return re.sub(r"`[^`\n]*`", "", text)


def _strip_fenced_markdown_code(text: str) -> str:
    text = re.sub(r"(?s)```.*?```", "", text)
    return re.sub(r"(?s)~~~.*?~~~", "", text)


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
