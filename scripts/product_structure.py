from __future__ import annotations

import argparse
import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .bootstrap_tree import target_local_commands_payload
    from .scaffold import PRODUCT_SCAFFOLD_BY_KEY
    from .state import StateFileError, load_state
    from .workflow_actions import next_actions_payload
except ImportError:  # pragma: no cover - direct script execution
    from bootstrap_tree import target_local_commands_payload
    from scaffold import PRODUCT_SCAFFOLD_BY_KEY
    from state import StateFileError, load_state
    from workflow_actions import next_actions_payload


PRD_REL = Path("docs/product/core/PRD.md")


@dataclass
class ProductStructureResult:
    target: str
    ok: bool
    check: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    would_update: list[str] = field(default_factory=list)
    chapters: list[dict[str, str]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target:
            raise ValueError("product structure result target must be a non-empty string")
        if not isinstance(self.ok, bool):
            raise ValueError("product structure result ok must be a boolean")
        if not isinstance(self.check, bool):
            raise ValueError("product structure result check must be a boolean")
        if not isinstance(self.errors, list) or not all(isinstance(item, str) for item in self.errors):
            raise ValueError("product structure result errors must be strings")
        if not isinstance(self.warnings, list) or not all(isinstance(item, str) for item in self.warnings):
            raise ValueError("product structure result warnings must be strings")
        _validate_path_list("updated", self.updated)
        _validate_path_list("would_update", self.would_update)
        if not isinstance(self.chapters, list) or not all(isinstance(item, dict) for item in self.chapters):
            raise ValueError("product structure result chapters must be objects")
        if not isinstance(self.state, dict):
            raise ValueError("product structure result state must be an object")
        if self.check and self.updated:
            raise ValueError("product structure result check mode cannot contain updated paths")
        if not self.check and self.would_update:
            raise ValueError("product structure result write mode cannot contain would_update paths")
        if self.ok and self.errors:
            raise ValueError("product structure result ok cannot include errors")
        if not self.ok and not self.errors:
            raise ValueError("product structure result failure requires errors")
        self.errors = list(self.errors)
        self.warnings = list(self.warnings)
        self.updated = list(self.updated)
        self.would_update = list(self.would_update)
        self.chapters = copy.deepcopy(self.chapters)
        self.state = copy.deepcopy(self.state)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "ok": self.ok,
            "check": self.check,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "updated": list(self.updated),
            "would_update": list(self.would_update),
            "chapters": copy.deepcopy(self.chapters),
            "state": copy.deepcopy(self.state),
        }


@dataclass(frozen=True)
class _ChapterPlan:
    key: str
    heading: str
    path: str
    title: str
    body: str
    rendered: str


@dataclass(frozen=True)
class _Snapshot:
    exists: bool
    content: bytes = b""


def check_structure_product(root: Path, chapters: list[str] | tuple[str, ...]) -> ProductStructureResult:
    plan = _build_structure_plan(root, chapters)
    if plan.errors:
        return ProductStructureResult(
            target=plan.target,
            ok=False,
            check=True,
            errors=plan.errors,
            warnings=plan.warnings,
            chapters=plan.chapter_dicts(),
            state=plan.state,
        )
    would_update = [
        chapter.path
        for chapter in plan.chapters
        if (Path(plan.target) / chapter.path).read_text(encoding="utf-8") != chapter.rendered
    ]
    would_update.extend(
        rel
        for rel, text in plan.extra_files.items()
        if (Path(plan.target) / rel).read_text(encoding="utf-8") != text
    )
    return ProductStructureResult(
        target=plan.target,
        ok=True,
        check=True,
        warnings=plan.warnings,
        would_update=would_update,
        chapters=plan.chapter_dicts(),
        state=plan.state,
    )


def structure_product(root: Path, chapters: list[str] | tuple[str, ...]) -> ProductStructureResult:
    plan = _build_structure_plan(root, chapters)
    if plan.errors:
        return ProductStructureResult(
            target=plan.target,
            ok=False,
            errors=plan.errors,
            warnings=plan.warnings,
            chapters=plan.chapter_dicts(),
            state=plan.state,
        )

    output_paths = [Path(chapter.path) for chapter in plan.chapters] + [Path(rel) for rel in plan.extra_files]
    snapshots = _snapshot_files(Path(plan.target), output_paths)
    updated: list[str] = []
    try:
        for chapter in plan.chapters:
            path = Path(plan.target) / chapter.path
            if path.read_text(encoding="utf-8") == chapter.rendered:
                continue
            _write_text_atomic(path, chapter.rendered)
            updated.append(chapter.path)
        for rel, text in plan.extra_files.items():
            path = Path(plan.target) / rel
            if path.read_text(encoding="utf-8") == text:
                continue
            _write_text_atomic(path, text)
            updated.append(rel)
    except OSError as error:
        _restore_snapshots(Path(plan.target), snapshots)
        return ProductStructureResult(
            target=plan.target,
            ok=False,
            errors=[f"product structure write failed: {_os_error_reason(error)}"],
            warnings=plan.warnings,
            chapters=plan.chapter_dicts(),
            state=plan.state,
        )

    return ProductStructureResult(
        target=plan.target,
        ok=True,
        warnings=plan.warnings,
        updated=updated,
        chapters=plan.chapter_dicts(),
        state=plan.state,
    )


@dataclass
class _StructurePlan:
    target: str
    errors: list[str]
    warnings: list[str]
    chapters: list[_ChapterPlan]
    extra_files: dict[str, str]
    state: dict[str, Any]

    def chapter_dicts(self) -> list[dict[str, str]]:
        return [
            {
                "key": chapter.key,
                "heading": chapter.heading,
                "path": chapter.path,
                "title": chapter.title,
            }
            for chapter in self.chapters
        ]


def _build_structure_plan(root: Path, chapters: list[str] | tuple[str, ...]) -> _StructurePlan:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    state: dict[str, Any] = {}
    if not chapters:
        errors.append("at least one product chapter mapping must be provided")
    try:
        state = load_state(root)
    except StateFileError as error:
        errors.append(f"target governance state is invalid: {error}")

    prd_path = root / PRD_REL
    prd_text = _read_required_text(prd_path, PRD_REL.as_posix(), errors)
    mappings = _parse_chapter_mappings(chapters, errors)
    plans: list[_ChapterPlan] = []
    for key, heading in mappings:
        spec = PRODUCT_SCAFFOLD_BY_KEY[key]
        path = root / spec.path
        existing = _read_required_text(path, spec.path, errors)
        section = _extract_markdown_section(prd_text, heading)
        if section is None:
            errors.append(f"PRD section heading not found for {key}: {heading}")
            continue
        if existing == "":
            continue
        if key == "acceptance-criteria":
            rendered = _render_acceptance_chapter(spec.title, section)
        else:
            rendered = _render_product_chapter(spec.title, heading, section)
        plans.append(
            _ChapterPlan(
                key=key,
                heading=heading,
                path=spec.path,
                title=spec.title,
                body=section,
                rendered=rendered,
            )
        )
    extra_files = _product_readme_updates(root, plans, errors)
    return _StructurePlan(str(root), errors, warnings, plans, extra_files, state)


def _product_readme_updates(root: Path, chapters: list[_ChapterPlan], errors: list[str]) -> dict[str, str]:
    acceptance = next((chapter for chapter in chapters if chapter.key == "acceptance-criteria"), None)
    if acceptance is None:
        return {}
    readme_rel = "docs/product/README.md"
    readme = _read_required_text(root / readme_rel, readme_rel, errors)
    if not readme or "A-NNN" not in readme:
        return {}
    criteria_count = len(_acceptance_criteria(acceptance.body))
    id_label = "A-001" if criteria_count <= 1 else f"A-001 through A-{criteria_count:03d}"
    return {readme_rel: readme.replace("A-NNN", id_label)}


def _parse_chapter_mappings(raw: list[str] | tuple[str, ...], errors: list[str]) -> list[tuple[str, str]]:
    mappings: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if "=" not in item:
            errors.append(f"chapter mapping must use key=PRD Heading: {item}")
            continue
        key, heading = item.split("=", 1)
        key = key.strip()
        heading = heading.strip()
        if key not in PRODUCT_SCAFFOLD_BY_KEY:
            errors.append(f"unknown product chapter: {key}")
            continue
        if not heading:
            errors.append(f"chapter mapping heading is empty for {key}")
            continue
        if key in seen:
            errors.append(f"duplicate product chapter mapping: {key}")
            continue
        seen.add(key)
        mappings.append((key, heading))
    return mappings


def _read_required_text(path: Path, label: str, errors: list[str]) -> str:
    if not path.exists():
        errors.append(f"required product structure file is missing: {label}")
        return ""
    if not path.is_file():
        errors.append(f"required product structure path is not a file: {label}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"required product structure file must be UTF-8 Markdown: {label}")
    except OSError as error:
        errors.append(f"required product structure file is unreadable: {label}: {_os_error_reason(error)}")
    return ""


def _extract_markdown_section(text: str, heading: str) -> str | None:
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
    lines = text.splitlines()
    start_index = -1
    start_level = 0
    for index, line in enumerate(lines):
        match = heading_re.match(line)
        if not match:
            continue
        title = match.group(2).strip()
        if title.casefold() != heading.casefold():
            continue
        start_index = index + 1
        start_level = len(match.group(1))
        break
    if start_index < 0:
        return None
    end_index = len(lines)
    for index in range(start_index, len(lines)):
        match = heading_re.match(lines[index])
        if match and len(match.group(1)) <= start_level:
            end_index = index
            break
    section = "\n".join(lines[start_index:end_index]).strip()
    return section if section else None


def _render_product_chapter(title: str, source_heading: str, section: str) -> str:
    return (
        f"# {title}\n\n"
        "Source: [PRD](core/PRD.md).\n\n"
        f"## {source_heading}\n\n"
        f"{section.strip()}\n"
    )


def _render_acceptance_chapter(title: str, section: str) -> str:
    criteria = _acceptance_criteria(section)
    body = "\n\n".join(
        f"## A-{index:03d} {_criterion_title(criterion)}\n\n- {criterion}"
        for index, criterion in enumerate(criteria, start=1)
    )
    return f"# {title}\n\nSource: [PRD](core/PRD.md).\n\n{body}\n"


def _acceptance_criteria(section: str) -> list[str]:
    criteria: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        match = re.match(r"^(?:[-*]|\d+[.)])\s+(.+)$", stripped)
        if match:
            criteria.append(match.group(1).strip().rstrip("."))
    if criteria:
        return criteria
    text = " ".join(line.strip() for line in section.splitlines() if line.strip())
    return [text.rstrip(".")] if text else []


def _criterion_title(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", text).strip()
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    words = []
    for word in cleaned.split():
        words.append(word if word.isupper() else word[:1].upper() + word[1:].lower())
    return " ".join(words) or "Acceptance Criterion"


def _snapshot_files(root: Path, paths: list[Path]) -> dict[Path, _Snapshot]:
    snapshots: dict[Path, _Snapshot] = {}
    for rel in paths:
        path = root / rel
        snapshots[rel] = _Snapshot(path.exists(), path.read_bytes() if path.is_file() else b"")
    return snapshots


def _restore_snapshots(root: Path, snapshots: dict[Path, _Snapshot]) -> None:
    for rel, snapshot in snapshots.items():
        path = root / rel
        if snapshot.exists:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(snapshot.content)
        elif path.exists() and path.is_file():
            path.unlink()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    if temp.exists() and not temp.is_file():
        raise OSError(f"temp path is not a file: {temp}")
    temp.write_text(text, encoding="utf-8")
    try:
        temp.replace(path)
    finally:
        if temp.exists() and temp.is_file():
            temp.unlink()


def _validate_path_list(field_name: str, paths: object) -> None:
    if not isinstance(paths, list):
        raise ValueError(f"product structure result {field_name} must be a list")
    if not all(isinstance(path, str) for path in paths):
        raise ValueError(f"product structure result {field_name} paths must be strings")
    if len(paths) != len(set(paths)):
        raise ValueError(f"product structure result {field_name} paths must be unique")
    for path in paths:
        posix_path = PurePosixPath(path)
        windows_path = PureWindowsPath(path)
        normalized_path = posix_path.as_posix()
        if (
            not path
            or path == "."
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError(f"product structure result {field_name} paths must be repository-relative")
        if "\\" in path or path != normalized_path:
            raise ValueError(f"product structure result {field_name} paths must use normalized POSIX form")


def _os_error_reason(error: OSError) -> str:
    return error.strerror or str(error)


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _payload_with_continuation(result: ProductStructureResult) -> dict[str, object]:
    payload = result.to_dict()
    if result.ok and not result.check and result.state:
        payload["local_commands"] = target_local_commands_payload(cwd=result.target)
        payload["next_actions"] = next_actions_payload(result.state, cwd=result.target)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill scaffolded product chapters from explicit PRD sections.")
    parser.add_argument("target", nargs="?", default=".")
    parser.add_argument(
        "--chapter",
        action="append",
        default=[],
        help="Chapter mapping as product-chapter-key=PRD heading. Repeat for multiple chapters.",
    )
    parser.add_argument("--check", action="store_true", help="Preview chapter updates without writing files.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = check_structure_product(Path(args.target), args.chapter) if args.check else structure_product(Path(args.target), args.chapter)
    payload = _payload_with_continuation(result)
    if args.json:
        _print_json(payload)
        return 0 if result.ok else 1
    if result.ok and result.check:
        print("Product structure preflight passed.")
        for path in result.would_update:
            print(f"- WOULD UPDATE: {path}")
        return 0
    if result.ok:
        print("Product structure updated.")
        for path in result.updated:
            print(f"- UPDATED: {path}")
        return 0
    print("Product structure failed:")
    for error in result.errors:
        print(f"- ERROR: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
