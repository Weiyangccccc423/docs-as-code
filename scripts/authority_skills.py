from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from .design_plan import (
        AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
        AUTHORITY_ROUTING_SPECIALIST_SKILLS,
        DESIGN_TRACKS,
    )
    from .implementation_plan import BASE_SPECIALIST_SKILLS
except ImportError:  # pragma: no cover - direct script execution
    from design_plan import (
        AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
        AUTHORITY_ROUTING_SPECIALIST_SKILLS,
        DESIGN_TRACKS,
    )
    from implementation_plan import BASE_SPECIALIST_SKILLS


AUTHORITY_SKILL_TYPE = "authority-routing"
AUTHORITY_SKILL_AVAILABILITY_SCOPE = "agent-environment"
EXPECTED_AUTHORITY_ROUTING_SKILL_MISSING_POLICY = "load_from_agent_environment_or_stop_before_guessing"
IMPLEMENTATION_CONDITIONAL_SPECIALIST_SKILLS = (
    ("senior-backend", "docs/api/ or docs/backend/ references"),
    ("senior-frontend", "docs/frontend/ or docs/ui/ references"),
    ("api-design-reviewer", "docs/api/ references"),
)


def build_authority_skill_inventory(
    *,
    skill_roots: list[Path] | None = None,
    strict: bool = False,
    include_default_skill_roots: bool = True,
) -> dict[str, Any]:
    _validate_authority_missing_policy()
    roots = _resolve_skill_roots(skill_roots, include_default_skill_roots=include_default_skill_roots)
    installed_skills = _installed_skill_index(roots)
    requirements = _authority_skill_requirements()
    skills: list[dict[str, Any]] = []
    available_skills: list[str] = []
    missing_skills: list[str] = []

    for name in sorted(requirements):
        skill_path = installed_skills.get(name)
        available = skill_path is not None
        if available:
            available_skills.append(name)
        else:
            missing_skills.append(name)
        skills.append(
            {
                "name": name,
                "type": AUTHORITY_SKILL_TYPE,
                "availability_scope": AUTHORITY_SKILL_AVAILABILITY_SCOPE,
                "missing_policy": AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
                "available_in_agent_environment": available,
                "skill_path": str(skill_path) if skill_path is not None else "",
                "required_by": requirements[name],
            }
        )

    errors: list[str] = []
    if strict and missing_skills:
        errors.append(
            "authority-routing skills missing from agent environment under policy "
            f"{AUTHORITY_ROUTING_SKILL_MISSING_POLICY}: {', '.join(missing_skills)}"
        )

    return {
        "ok": not errors,
        "strict": strict,
        "type": AUTHORITY_SKILL_TYPE,
        "availability_scope": AUTHORITY_SKILL_AVAILABILITY_SCOPE,
        "missing_policy": AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
        "required_skill_count": len(skills),
        "available_skill_count": len(available_skills),
        "missing_skill_count": len(missing_skills),
        "available_skill_roots": [str(root) for root in roots],
        "available_skills": available_skills,
        "missing_skills": missing_skills,
        "skills": skills,
        "errors": errors,
    }


def _validate_authority_missing_policy() -> None:
    if AUTHORITY_ROUTING_SKILL_MISSING_POLICY != EXPECTED_AUTHORITY_ROUTING_SKILL_MISSING_POLICY:
        raise RuntimeError(
            "authority skill inventory missing policy drifted from design routing: "
            f"{AUTHORITY_ROUTING_SKILL_MISSING_POLICY}"
        )


def _authority_skill_requirements() -> dict[str, list[dict[str, str]]]:
    required_by: dict[str, list[dict[str, str]]] = {skill: [] for skill in AUTHORITY_ROUTING_SPECIALIST_SKILLS}
    for track in DESIGN_TRACKS:
        for skill in track.specialist_skills:
            _append_requirement(
                required_by,
                skill,
                {
                    "phase": "design-derivation",
                    "track": track.id,
                    "title": track.title,
                    "source": "DESIGN_TRACKS",
                },
            )
    for skill in BASE_SPECIALIST_SKILLS:
        _append_requirement(
            required_by,
            skill,
            {
                "phase": "implementation",
                "track": "base",
                "title": "Implementation base routing",
                "source": "BASE_SPECIALIST_SKILLS",
            },
        )
    for skill, trigger in IMPLEMENTATION_CONDITIONAL_SPECIALIST_SKILLS:
        _append_requirement(
            required_by,
            skill,
            {
                "phase": "implementation",
                "track": "conditional",
                "title": trigger,
                "source": "_task_specialist_skills",
            },
        )
    return {skill: entries for skill, entries in sorted(required_by.items()) if entries}


def _append_requirement(required_by: dict[str, list[dict[str, str]]], skill: str, entry: dict[str, str]) -> None:
    if skill not in AUTHORITY_ROUTING_SPECIALIST_SKILLS:
        return
    entries = required_by.setdefault(skill, [])
    if entry not in entries:
        entries.append(entry)


def _resolve_skill_roots(
    skill_roots: list[Path] | None,
    *,
    include_default_skill_roots: bool,
) -> list[Path]:
    roots: list[Path] = []
    if include_default_skill_roots:
        codex_home = os.environ.get("CODEX_HOME", "").strip()
        if codex_home:
            roots.append(Path(codex_home) / "skills")
        roots.append(Path.home() / ".codex" / "skills")
    if skill_roots:
        roots.extend(skill_roots)

    resolved: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        expanded = root.expanduser().resolve()
        key = str(expanded)
        if key in seen or not expanded.is_dir():
            continue
        seen.add(key)
        resolved.append(expanded)
    return resolved


def _find_skill_path(name: str, roots: list[Path]) -> Path | None:
    installed_skills = _installed_skill_index(roots)
    return installed_skills.get(name)


def _installed_skill_index(roots: list[Path]) -> dict[str, Path]:
    installed: dict[str, Path] = {}
    for root in roots:
        for candidate in sorted(root.glob("*/SKILL.md")):
            if not candidate.is_file():
                continue
            names = [candidate.parent.name]
            frontmatter_name = _skill_frontmatter_name(candidate)
            if frontmatter_name:
                names.insert(0, frontmatter_name)
            for name in names:
                installed.setdefault(name, candidate.resolve())
    return installed


def _skill_frontmatter_name(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    if not lines or lines[0].strip() != "---":
        return ""
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return ""
        if not stripped.startswith("name:"):
            continue
        value = stripped.split(":", 1)[1].strip()
        return value.strip("'\"")
    return ""


def _text_summary(payload: dict[str, Any]) -> str:
    lines = [
        (
            "Authority routing skills: "
            f"{payload['available_skill_count']} available, {payload['missing_skill_count']} missing, "
            f"{payload['required_skill_count']} required"
        )
    ]
    if payload["available_skill_roots"]:
        lines.append("Skill roots:")
        lines.extend(f"- {root}" for root in payload["available_skill_roots"])
    if payload["missing_skills"]:
        lines.append("Missing skills:")
        lines.extend(f"- {skill}" for skill in payload["missing_skills"])
    if payload["errors"]:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory authority-routing specialist skills required by this workflow pack."
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when any required authority-routing skill is unavailable in the agent environment.",
    )
    parser.add_argument(
        "--skill-root",
        action="append",
        type=Path,
        default=[],
        help="Additional skill root to scan for installed SKILL.md files.",
    )
    parser.add_argument(
        "--no-default-skill-roots",
        action="store_true",
        help="Do not scan CODEX_HOME/skills or ~/.codex/skills.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = build_authority_skill_inventory(
        skill_roots=list(args.skill_root),
        strict=args.strict,
        include_default_skill_roots=not args.no_default_skill_roots,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_text_summary(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
