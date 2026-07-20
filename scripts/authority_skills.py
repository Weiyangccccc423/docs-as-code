from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    from .bounded_process import run_bounded_command
    from .design_plan import (
        AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
        AUTHORITY_ROUTING_SPECIALIST_SKILLS,
        DESIGN_TRACKS,
    )
    from .implementation_plan import BASE_SPECIALIST_SKILLS
    from .project_environment import PROJECT_ENVIRONMENT_SPECIALIST_SKILLS
except ImportError:  # pragma: no cover - direct script execution
    from bounded_process import run_bounded_command
    from design_plan import (
        AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
        AUTHORITY_ROUTING_SPECIALIST_SKILLS,
        DESIGN_TRACKS,
    )
    from implementation_plan import BASE_SPECIALIST_SKILLS
    from project_environment import PROJECT_ENVIRONMENT_SPECIALIST_SKILLS


AUTHORITY_SKILL_TYPE = "authority-routing"
AUTHORITY_SKILL_AVAILABILITY_SCOPE = "agent-environment"
AUTHORITY_SKILL_LOCK_SCHEMA_VERSION = 1
AUTHORITY_SKILL_LOCK_REL = Path("references/authority-skills.lock.json")
TARGET_AUTHORITY_SKILL_LOCK_REL = Path("docs/agent-workflow/workflow-pack") / AUTHORITY_SKILL_LOCK_REL
EXPECTED_AUTHORITY_ROUTING_SKILL_MISSING_POLICY = "load_from_agent_environment_or_stop_before_guessing"
IMPLEMENTATION_CONDITIONAL_SPECIALIST_SKILLS = (
    ("senior-backend", "docs/api/ or docs/backend/ references"),
    ("senior-frontend", "docs/frontend/ or docs/ui/ references"),
    ("api-design-reviewer", "docs/api/ references"),
)
LOCK_POLICY = {
    "install_execution": "explicit-approval-required",
    "integrity": "skill-tree-sha256-v1",
    "registered_source_kind": "github",
    "source_ref": "immutable-full-commit-sha",
    "unregistered_source": "manual-source-registration-required",
}
AUTHORITY_SKILL_STATUSES = ("current", "missing", "drifted", "unmanaged", "source-unregistered")
INTEGRITY_SCOPES = {"skill-tree"}
SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9_.-]+$")
IMMUTABLE_GITHUB_REF_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
APPROVAL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TREE_DIGEST_IGNORED_DIRS = {".git", "__pycache__"}
TREE_DIGEST_IGNORED_FILES = {".DS_Store"}
AUTHORITY_INSTALL_TIMEOUT_SECONDS = 120.0
AUTHORITY_INSTALL_MAX_OUTPUT_BYTES = 65_536


def build_authority_skill_inventory(
    *,
    skill_roots: list[Path] | None = None,
    strict: bool = False,
    strict_provenance: bool = False,
    include_default_skill_roots: bool = True,
    manifest_path: Path | None = None,
    repair: bool = False,
    check: bool = False,
    skill_installer_path: Path | None = None,
) -> dict[str, Any]:
    if repair != check:
        raise ValueError("repair and check must be used together; authority skill repair is planning-only")
    _validate_authority_missing_policy()
    requirements = _authority_skill_requirements()
    roots = _resolve_skill_roots(skill_roots, include_default_skill_roots=include_default_skill_roots)
    installed_candidates = _installed_skill_candidates(roots)
    installed_skills = {name: candidates[0] for name, candidates in installed_candidates.items()}
    lock_path = _resolve_authority_skill_lock_path(manifest_path)
    manifest, locked_entries = _load_authority_skill_lock(lock_path)
    required_names = set(requirements)
    locked_names = set(manifest["skill_names"])
    unmanaged_names = sorted(required_names - locked_names)
    stale_names = sorted(locked_names - required_names)
    manifest["aligned_with_routing"] = not unmanaged_names and not stale_names
    manifest["unmanaged_required_skills"] = unmanaged_names
    manifest["stale_locked_skills"] = stale_names

    skills: list[dict[str, Any]] = []
    available_skills: list[str] = []
    missing_skills: list[str] = []
    source_unregistered_skills: list[str] = []
    registered_source_skills: list[str] = []
    status_lists = {status: [] for status in AUTHORITY_SKILL_STATUSES}

    for name in sorted(requirements):
        skill_path = installed_skills.get(name)
        installation_candidates = installed_candidates.get(name, [])
        installation_ambiguous = len(installation_candidates) > 1
        available = skill_path is not None
        entry = locked_entries.get(name)
        source = entry.get("source", {}) if entry is not None else {}
        trust = entry.get("trust", {}) if entry is not None else {}
        source_kind = source.get("kind", "") if isinstance(source, dict) else ""
        source_registered = source_kind == "github"
        if source_registered:
            registered_source_skills.append(name)
        elif source_kind == "unregistered":
            source_unregistered_skills.append(name)

        expected_scope = ""
        expected_sha256 = ""
        observed_sha256 = ""
        integrity_matches: bool | None = None
        integrity_errors: list[str] = []
        if installation_ambiguous:
            integrity_errors.append(
                "multiple installations found for one authority skill: "
                + ", ".join(str(path) for path in installation_candidates)
            )
        if entry is not None and source_registered:
            integrity = entry.get("integrity", {})
            if isinstance(integrity, dict):
                expected_scope = str(integrity.get("scope", ""))
                expected_sha256 = str(integrity.get("digest", ""))
        elif available:
            expected_scope = "skill-tree"

        if available and expected_scope:
            try:
                observed_sha256 = _skill_integrity_sha256(skill_path, expected_scope)
            except (OSError, ValueError) as error:
                integrity_errors.append(str(error))
            if expected_sha256:
                integrity_matches = bool(observed_sha256) and observed_sha256 == expected_sha256

        if entry is None:
            status = "unmanaged"
        elif not available:
            status = "missing"
        elif not source_registered:
            status = "source-unregistered"
        elif installation_ambiguous:
            status = "drifted"
        elif integrity_matches is True:
            status = "current"
        else:
            status = "drifted"

        if available:
            available_skills.append(name)
        else:
            missing_skills.append(name)
        status_lists[status].append(name)
        skills.append(
            {
                "name": name,
                "type": AUTHORITY_SKILL_TYPE,
                "availability_scope": AUTHORITY_SKILL_AVAILABILITY_SCOPE,
                "missing_policy": AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
                "status": status,
                "available_in_agent_environment": available,
                "skill_path": str(skill_path) if skill_path is not None else "",
                "installation_ambiguous": installation_ambiguous,
                "installation_candidates": [str(path) for path in installation_candidates],
                "source_registered": source_registered,
                "source_kind": source_kind or "unmanaged",
                "source": source if isinstance(source, dict) else {},
                "trust": trust if isinstance(trust, dict) else {},
                "integrity_scope": expected_scope,
                "expected_sha256": expected_sha256,
                "observed_sha256": observed_sha256,
                "integrity_matches": integrity_matches,
                "integrity_error": "; ".join(integrity_errors),
                "repair_action_ids": [],
                "required_by": requirements[name],
            }
        )

    installer = _resolve_skill_installer_path(skill_installer_path)
    repair_plan = _build_repair_plan(skills, requested=repair, check=check, skill_installer_path=installer)
    action_ids_by_skill: dict[str, list[str]] = {}
    for action in repair_plan["actions"]:
        action_ids_by_skill.setdefault(action["skill"], []).append(action["id"])
    for skill in skills:
        skill["repair_action_ids"] = action_ids_by_skill.get(skill["name"], [])

    errors = [f"authority skill lock: {error}" for error in manifest["errors"]]
    if unmanaged_names:
        errors.append(f"authority skill lock is missing routing skill entries: {', '.join(unmanaged_names)}")
    if stale_names:
        errors.append(f"authority skill lock contains stale routing skill entries: {', '.join(stale_names)}")
    if strict and missing_skills:
        errors.append(
            "authority-routing skills missing from agent environment under policy "
            f"{AUTHORITY_ROUTING_SKILL_MISSING_POLICY}: {', '.join(missing_skills)}"
        )
    provenance_issue_skills = sorted(skill["name"] for skill in skills if skill["status"] != "current")
    if strict_provenance and provenance_issue_skills:
        errors.append(
            "authority-routing skill provenance is not current; stop before authority-dependent work: "
            f"{', '.join(provenance_issue_skills)}"
        )

    return {
        "ok": not errors,
        "strict": strict,
        "strict_provenance": strict_provenance,
        "type": AUTHORITY_SKILL_TYPE,
        "availability_scope": AUTHORITY_SKILL_AVAILABILITY_SCOPE,
        "missing_policy": AUTHORITY_ROUTING_SKILL_MISSING_POLICY,
        "manifest": manifest,
        "required_skill_count": len(skills),
        "available_skill_count": len(available_skills),
        "missing_skill_count": len(missing_skills),
        "registered_source_skill_count": len(registered_source_skills),
        "source_unregistered_skill_count": len(source_unregistered_skills),
        "provenance_issue_count": len(provenance_issue_skills),
        "provenance_ready": not provenance_issue_skills and manifest["ok"] and manifest["aligned_with_routing"],
        "status_counts": {status: len(status_lists[status]) for status in AUTHORITY_SKILL_STATUSES},
        "available_skill_roots": [str(root) for root in roots],
        "available_skills": available_skills,
        "missing_skills": missing_skills,
        "current_skills": status_lists["current"],
        "drifted_skills": status_lists["drifted"],
        "unmanaged_skills": status_lists["unmanaged"],
        "source_unregistered_skills": source_unregistered_skills,
        "registered_source_skills": registered_source_skills,
        "provenance_issue_skills": provenance_issue_skills,
        "skills": skills,
        "repair_plan": repair_plan,
        "errors": errors,
    }


def validate_authority_skill_lock(path: Path) -> dict[str, Any]:
    manifest, _entries = _load_authority_skill_lock(_absolute_path_preserving_symlinks(path))
    return manifest


def apply_authority_skill_repairs(
    *,
    approved: bool,
    skill_roots: list[Path] | None = None,
    strict: bool = False,
    strict_provenance: bool = False,
    include_default_skill_roots: bool = True,
    manifest_path: Path | None = None,
    skill_installer_path: Path | None = None,
) -> dict[str, Any]:
    initial = build_authority_skill_inventory(
        skill_roots=skill_roots,
        include_default_skill_roots=include_default_skill_roots,
        manifest_path=manifest_path,
        repair=True,
        check=True,
        skill_installer_path=skill_installer_path,
    )
    plan = initial["repair_plan"]
    actions = plan.get("actions", []) if isinstance(plan, dict) else []
    execution = _authority_repair_execution_payload(approved=approved, action_count=len(actions))

    if not initial["ok"]:
        execution.update(
            {
                "status": "blocked_invalid_inventory",
                "stop_reason": "authority skill lock or routing inventory is invalid",
            }
        )
        return _authority_repair_result(
            initial,
            initial,
            execution,
            strict=strict,
            strict_provenance=strict_provenance,
        )

    installer_path = _resolve_skill_installer_path(skill_installer_path)
    skills_by_name = {str(skill["name"]): skill for skill in initial["skills"]}
    unsupported_actions = [
        action
        for action in actions
        if not _authority_install_action_is_executable(
            action,
            skill=skills_by_name.get(str(action.get("skill", "")), {}),
            installer_path=installer_path,
        )
    ]
    if unsupported_actions:
        execution.update(
            {
                "status": "blocked_unsupported_actions",
                "stop_reason": "authority repair contains drift, source review, ambiguity, or unavailable-installer actions",
                "blocked_action_ids": [str(action.get("id", "")) for action in unsupported_actions],
            }
        )
        return _authority_repair_result(
            initial,
            initial,
            execution,
            strict=strict,
            strict_provenance=strict_provenance,
        )

    if not actions:
        final = build_authority_skill_inventory(
            skill_roots=skill_roots,
            strict=strict,
            strict_provenance=strict_provenance,
            include_default_skill_roots=include_default_skill_roots,
            manifest_path=manifest_path,
            skill_installer_path=skill_installer_path,
        )
        execution.update(
            {
                "ok": final["ok"] and final["provenance_ready"],
                "status": "no_action_required",
                "can_continue": final["ok"] and final["provenance_ready"],
            }
        )
        return _authority_repair_result(
            initial,
            final,
            execution,
            strict=strict,
            strict_provenance=strict_provenance,
        )

    if not approved:
        execution.update(
            {
                "status": "approval_required",
                "stop_reason": "network access and Agent-environment writes require explicit --approve-installs",
                "blocked_action_ids": [str(action.get("id", "")) for action in actions],
            }
        )
        return _authority_repair_result(
            initial,
            initial,
            execution,
            strict=strict,
            strict_provenance=strict_provenance,
        )

    lock_path = _resolve_authority_skill_lock_path(manifest_path)
    for action in actions:
        action_id = str(action["id"])
        skill_name = str(action["skill"])
        if not _authority_install_action_is_executable(
            action,
            skill=skills_by_name.get(skill_name, {}),
            installer_path=installer_path,
        ):
            execution.update(
                {
                    "status": "blocked_unsupported_actions",
                    "stop_reason": "authority install action or installer changed after repair planning",
                    "blocked_action_ids": [action_id],
                    "partial_write_observed": execution["verified_count"] > 0,
                }
            )
            break
        argv = [str(value) for value in action["argv"]]
        command_result = run_bounded_command(
            argv,
            cwd=lock_path.parent.parent,
            timeout_seconds=AUTHORITY_INSTALL_TIMEOUT_SECONDS,
            max_output_bytes=AUTHORITY_INSTALL_MAX_OUTPUT_BYTES,
        )
        execution["attempted_count"] += 1
        post_action = build_authority_skill_inventory(
            skill_roots=skill_roots,
            include_default_skill_roots=include_default_skill_roots,
            manifest_path=manifest_path,
            skill_installer_path=skill_installer_path,
        )
        skill = next((item for item in post_action["skills"] if item["name"] == skill_name), {})
        command_succeeded = command_result.get("result") == "pass"
        integrity_verified = skill.get("status") == "current" and skill.get("integrity_matches") is True
        verified = command_succeeded and integrity_verified
        action_result = {
            "id": action_id,
            "skill": skill_name,
            "argv": argv,
            "execution": command_result,
            "command_succeeded": command_succeeded,
            "post_status": skill.get("status", "unavailable"),
            "post_integrity_matches": skill.get("integrity_matches"),
            "integrity_verified": integrity_verified,
            "verified": verified,
        }
        execution["actions"].append(action_result)
        if verified:
            execution["verified_count"] += 1
            continue

        execution["failed_action_id"] = action_id
        execution["failed_skill"] = skill_name
        execution["partial_write_observed"] = (
            execution["verified_count"] > 0 or skill.get("available_in_agent_environment") is True
        )
        execution["manual_cleanup_required"] = skill.get("available_in_agent_environment") is True
        if command_succeeded:
            execution["status"] = "integrity_failed"
            execution["stop_reason"] = "installer returned success but the installed skill tree did not match the lock"
        else:
            execution["status"] = "failed"
            execution["stop_reason"] = "authority skill installer command failed"
        break

    final = build_authority_skill_inventory(
        skill_roots=skill_roots,
        strict=strict,
        strict_provenance=strict_provenance,
        include_default_skill_roots=include_default_skill_roots,
        manifest_path=manifest_path,
        skill_installer_path=skill_installer_path,
    )
    if not execution["failed_action_id"] and not execution["blocked_action_ids"]:
        execution["partial_write_observed"] = False
        execution["status"] = "completed"
        execution["ok"] = final["ok"] and final["provenance_ready"]
        execution["can_continue"] = execution["ok"]
        if not execution["ok"]:
            execution["status"] = "post_verification_failed"
            execution["stop_reason"] = "post-install authority provenance verification did not pass"
    return _authority_repair_result(
        initial,
        final,
        execution,
        strict=strict,
        strict_provenance=strict_provenance,
    )


def _authority_install_action_is_executable(
    action: object,
    *,
    skill: object,
    installer_path: Path,
) -> bool:
    if not isinstance(action, dict) or not isinstance(skill, dict):
        return False
    name = skill.get("name")
    source = skill.get("source")
    trust = skill.get("trust")
    if not isinstance(name, str) or not isinstance(source, dict) or not isinstance(trust, dict):
        return False
    repo = source.get("repo")
    source_path = source.get("path")
    source_ref = source.get("ref")
    if not all(isinstance(value, str) and value for value in (repo, source_path, source_ref)):
        return False
    expected_argv = [
        sys.executable,
        str(installer_path),
        "--repo",
        repo,
        "--path",
        source_path,
        "--ref",
        source_ref,
        "--name",
        name,
    ]
    argv = action.get("argv")
    return bool(
        installer_path.is_file()
        and not installer_path.is_symlink()
        and skill.get("status") == "missing"
        and skill.get("source_registered") is True
        and source.get("kind") == "github"
        and trust.get("status") == "approved"
        and SHA256_RE.fullmatch(str(skill.get("expected_sha256", ""))) is not None
        and action.get("id") == f"authority-skill-install-{name}"
        and action.get("skill") == name
        and action.get("kind") == "install-authority-skill-from-registered-source"
        and action.get("status") == "missing"
        and action.get("approval_required") is True
        and action.get("network_required") is True
        and action.get("writes_outside_repository") is True
        and action.get("manual_required") is False
        and argv == expected_argv
    )


def _authority_repair_execution_payload(*, approved: bool, action_count: int) -> dict[str, Any]:
    return {
        "ok": False,
        "requested": True,
        "approved": approved,
        "writes_state": True,
        "writes_outside_repository": True,
        "network_required": action_count > 0,
        "status": "pending",
        "can_continue": False,
        "action_count": action_count,
        "attempted_count": 0,
        "verified_count": 0,
        "failed_action_id": "",
        "failed_skill": "",
        "blocked_action_ids": [],
        "partial_write_observed": False,
        "manual_cleanup_required": False,
        "stop_reason": "",
        "timeout_seconds_per_action": AUTHORITY_INSTALL_TIMEOUT_SECONDS,
        "max_output_bytes_per_stream": AUTHORITY_INSTALL_MAX_OUTPUT_BYTES,
        "actions": [],
    }


def _authority_repair_result(
    initial: dict[str, Any],
    final: dict[str, Any],
    execution: dict[str, Any],
    *,
    strict: bool,
    strict_provenance: bool,
) -> dict[str, Any]:
    payload = dict(final)
    payload["strict"] = strict
    payload["strict_provenance"] = strict_provenance
    payload["ok"] = bool(final.get("ok") is True and execution.get("ok") is True)
    payload["repair_plan"] = initial["repair_plan"]
    payload["repair_execution"] = execution
    payload["pre_repair_summary"] = _authority_inventory_summary(initial)
    payload["post_repair_summary"] = _authority_inventory_summary(final)
    if not payload["ok"] and execution.get("stop_reason"):
        errors = list(payload.get("errors", []))
        errors.append(str(execution["stop_reason"]))
        payload["errors"] = errors
    return payload


def _authority_inventory_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok") is True,
        "required_skill_count": payload.get("required_skill_count", 0),
        "available_skill_count": payload.get("available_skill_count", 0),
        "missing_skill_count": payload.get("missing_skill_count", 0),
        "provenance_issue_count": payload.get("provenance_issue_count", 0),
        "provenance_ready": payload.get("provenance_ready") is True,
        "status_counts": payload.get("status_counts", {}),
    }


def _load_authority_skill_lock(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    invalid_skills: set[str] = set()
    entries: dict[str, dict[str, Any]] = {}
    skill_names: set[str] = set()
    schema_version: int | None = None

    if path.is_symlink():
        errors.append("lock path must not be a symbolic link")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append("lock file is missing")
        return _manifest_payload(path, schema_version, skill_names, invalid_skills, errors), entries
    except (OSError, UnicodeDecodeError) as error:
        errors.append(f"lock file is unreadable UTF-8 JSON: {error}")
        return _manifest_payload(path, schema_version, skill_names, invalid_skills, errors), entries
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        errors.append(f"lock file is invalid JSON: {error.msg} at line {error.lineno} column {error.colno}")
        return _manifest_payload(path, schema_version, skill_names, invalid_skills, errors), entries
    if not isinstance(payload, dict):
        errors.append("lock root must be a JSON object")
        return _manifest_payload(path, schema_version, skill_names, invalid_skills, errors), entries

    raw_schema = payload.get("schema_version")
    if isinstance(raw_schema, int) and not isinstance(raw_schema, bool):
        schema_version = raw_schema
    if schema_version != AUTHORITY_SKILL_LOCK_SCHEMA_VERSION:
        errors.append(f"schema_version must equal {AUTHORITY_SKILL_LOCK_SCHEMA_VERSION}")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        for key, expected in LOCK_POLICY.items():
            if policy.get(key) != expected:
                errors.append(f"policy.{key} must equal {expected!r}")

    raw_skills = payload.get("skills")
    if not isinstance(raw_skills, list):
        errors.append("skills must be an array")
        return _manifest_payload(path, schema_version, skill_names, invalid_skills, errors), entries

    for index, raw_entry in enumerate(raw_skills):
        prefix = f"skills[{index}]"
        if not isinstance(raw_entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = raw_entry.get("name")
        if not isinstance(name, str) or SKILL_NAME_RE.fullmatch(name) is None:
            errors.append(f"{prefix}.name must be a normalized hyphenated skill name")
            continue
        if name in skill_names:
            errors.append(f"{prefix}.name duplicates authority skill {name}")
            invalid_skills.add(name)
            entries.pop(name, None)
            continue
        skill_names.add(name)
        entry_errors = _validate_lock_entry(raw_entry, prefix)
        if entry_errors:
            errors.extend(entry_errors)
            invalid_skills.add(name)
            continue
        entries[name] = raw_entry

    return _manifest_payload(path, schema_version, skill_names, invalid_skills, errors, entries), entries


def _validate_lock_entry(entry: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    source = entry.get("source")
    trust = entry.get("trust")
    if not isinstance(source, dict):
        return [f"{prefix}.source must be an object"]
    if not isinstance(trust, dict):
        return [f"{prefix}.trust must be an object"]
    source_kind = source.get("kind")
    if source_kind == "unregistered":
        if not _non_empty_string(source.get("reason")):
            errors.append(f"{prefix}.source.reason must explain why source registration is pending")
        if "integrity" in entry:
            errors.append(f"{prefix}.integrity must be omitted until a source is registered")
        if trust.get("status") != "pending-source-review":
            errors.append(f"{prefix}.trust.status must equal 'pending-source-review' for unregistered sources")
        return errors
    if source_kind != "github":
        errors.append(f"{prefix}.source.kind must be 'github' or 'unregistered'")
        return errors

    repo = source.get("repo")
    if not isinstance(repo, str) or GITHUB_REPO_RE.fullmatch(repo) is None:
        errors.append(f"{prefix}.source.repo must use the GitHub owner/repository form")
    source_path = source.get("path")
    if not isinstance(source_path, str) or not _normalized_relative_path(source_path):
        errors.append(f"{prefix}.source.path must be a normalized repository-relative POSIX path")
    ref = source.get("ref")
    if not isinstance(ref, str) or IMMUTABLE_GITHUB_REF_RE.fullmatch(ref) is None:
        errors.append(f"{prefix}.source.ref must be an immutable 40-character commit SHA")

    integrity = entry.get("integrity")
    if not isinstance(integrity, dict):
        errors.append(f"{prefix}.integrity must be an object for registered sources")
    else:
        if integrity.get("algorithm") != "sha256":
            errors.append(f"{prefix}.integrity.algorithm must equal 'sha256'")
        if integrity.get("scope") not in INTEGRITY_SCOPES:
            errors.append(f"{prefix}.integrity.scope must be one of: {', '.join(sorted(INTEGRITY_SCOPES))}")
        digest = integrity.get("digest")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            errors.append(f"{prefix}.integrity.digest must be a lowercase SHA-256 value")

    if trust.get("status") != "approved":
        errors.append(f"{prefix}.trust.status must equal 'approved' for registered sources")
    for field in ("approved_by", "license", "review_evidence"):
        if not _non_empty_string(trust.get(field)):
            errors.append(f"{prefix}.trust.{field} must be non-empty for registered sources")
    approved_at = trust.get("approved_at")
    if not _valid_approval_date(approved_at):
        errors.append(f"{prefix}.trust.approved_at must use YYYY-MM-DD")
    return errors


def _manifest_payload(
    path: Path,
    schema_version: int | None,
    skill_names: set[str],
    invalid_skills: set[str],
    errors: list[str],
    entries: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    valid_entries = entries or {}
    registered_source_skills = sorted(
        name for name, entry in valid_entries.items() if entry.get("source", {}).get("kind") == "github"
    )
    source_unregistered_skills = sorted(
        name for name, entry in valid_entries.items() if entry.get("source", {}).get("kind") == "unregistered"
    )
    return {
        "ok": not errors,
        "path": str(path),
        "schema_version": schema_version,
        "skill_count": len(skill_names),
        "skill_names": sorted(skill_names),
        "invalid_skills": sorted(invalid_skills),
        "registered_source_skills": registered_source_skills,
        "source_unregistered_skills": source_unregistered_skills,
        "aligned_with_routing": False,
        "unmanaged_required_skills": [],
        "stale_locked_skills": [],
        "errors": errors,
    }


def _build_repair_plan(
    skills: list[dict[str, Any]],
    *,
    requested: bool,
    check: bool,
    skill_installer_path: Path,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    installer_available = skill_installer_path.is_file() and not skill_installer_path.is_symlink()
    if requested:
        for skill in skills:
            action = _repair_action_for_skill(skill, skill_installer_path, installer_available)
            if action is not None:
                actions.append(action)
    approval_action_ids = [action["id"] for action in actions if action["approval_required"]]
    manual_action_ids = [action["id"] for action in actions if action["manual_required"]]
    if not requested:
        status = "not-requested"
        decision = "inventory-only"
    elif not actions:
        status = "no-action-required"
        decision = "continue-workflow"
    else:
        status = "blocked-pending-approval-or-manual-action"
        decision = "stop-before-authority-dependent-work"
    return {
        "requested": requested,
        "check": check,
        "writes_state": False,
        "applied": False,
        "status": status,
        "decision": decision,
        "skill_installer": str(skill_installer_path),
        "skill_installer_available": installer_available,
        "action_count": len(actions),
        "can_auto_apply": False,
        "requires_approval": bool(approval_action_ids),
        "manual_repair_required": bool(manual_action_ids),
        "runnable_action_ids": [],
        "approval_action_ids": approval_action_ids,
        "manual_action_ids": manual_action_ids,
        "actions": actions,
    }


def _repair_action_for_skill(
    skill: dict[str, Any],
    installer_path: Path,
    installer_available: bool,
) -> dict[str, Any] | None:
    status = skill["status"]
    name = skill["name"]
    if status == "current":
        return None
    common = {
        "skill": name,
        "status": status,
        "approval_required": True,
        "network_required": False,
        "writes_outside_repository": False,
        "manual_required": True,
        "argv": [],
    }
    if not skill["source_registered"]:
        return {
            **common,
            "id": f"authority-skill-source-register-{name}",
            "kind": "register-authority-skill-source",
            "reason": (
                "Review license and source ownership, then record an exact GitHub repository, path, immutable "
                "commit, tree digest, and trust approval in the authority skill lock."
            ),
        }

    source = skill["source"]
    install_argv = [
        sys.executable,
        str(installer_path),
        "--repo",
        source["repo"],
        "--path",
        source["path"],
        "--ref",
        source["ref"],
        "--name",
        name,
    ]
    if status == "missing" and installer_available:
        return {
            **common,
            "id": f"authority-skill-install-{name}",
            "kind": "install-authority-skill-from-registered-source",
            "reason": "The registered authority skill is missing from the agent environment.",
            "network_required": True,
            "writes_outside_repository": True,
            "manual_required": False,
            "argv": install_argv,
        }
    if status == "missing":
        return {
            **common,
            "id": f"authority-skill-install-{name}",
            "kind": "install-authority-skill-from-registered-source",
            "reason": "The registered authority skill is missing and the system skill-installer is unavailable.",
            "network_required": True,
            "writes_outside_repository": True,
        }
    return {
        **common,
        "id": f"authority-skill-replace-{name}",
        "kind": "replace-drifted-authority-skill",
        "reason": (
            "The installed skill does not match the locked digest; the installer refuses to overwrite an existing "
            "destination, so review and replace it manually."
        ),
        "network_required": True,
        "writes_outside_repository": True,
        "install_argv_after_existing_destination_is_removed": install_argv if installer_available else [],
    }


def _skill_integrity_sha256(skill_path: Path, scope: str) -> str:
    if skill_path.is_symlink() or skill_path.parent.is_symlink():
        raise ValueError(f"authority skill path must not be a symbolic link: {skill_path}")
    if scope != "skill-tree":
        raise ValueError(f"unsupported authority skill integrity scope: {scope}")
    skill_dir = skill_path.parent
    digest = hashlib.sha256()
    for path in sorted(skill_dir.rglob("*"), key=lambda item: item.relative_to(skill_dir).as_posix()):
        rel = path.relative_to(skill_dir)
        if _tree_digest_ignored(rel):
            continue
        if path.is_symlink():
            raise ValueError(f"authority skill tree contains symbolic link: {rel.as_posix()}")
        if not path.is_file():
            continue
        digest.update(f"{rel.as_posix()}\0{_sha256_file(path)}\n".encode("utf-8"))
    return digest.hexdigest()


def _tree_digest_ignored(path: Path) -> bool:
    return (
        any(part in TREE_DIGEST_IGNORED_DIRS for part in path.parts)
        or path.name in TREE_DIGEST_IGNORED_FILES
        or path.suffix == ".pyc"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    for skill in PROJECT_ENVIRONMENT_SPECIALIST_SKILLS:
        _append_requirement(
            required_by,
            skill,
            {
                "phase": "design-derivation",
                "track": "project-runtime",
                "title": "Project runtime configuration",
                "source": "PROJECT_ENVIRONMENT_SPECIALIST_SKILLS",
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


def _resolve_authority_skill_lock_path(manifest_path: Path | None) -> Path:
    if manifest_path is not None:
        return _absolute_path_preserving_symlinks(manifest_path)
    root = Path(__file__).resolve().parents[1]
    candidates = (root / AUTHORITY_SKILL_LOCK_REL, root / TARGET_AUTHORITY_SKILL_LOCK_REL)
    return next(
        (_absolute_path_preserving_symlinks(candidate) for candidate in candidates if candidate.is_file()),
        _absolute_path_preserving_symlinks(candidates[0]),
    )


def _resolve_skill_installer_path(skill_installer_path: Path | None) -> Path:
    if skill_installer_path is not None:
        return _absolute_path_preserving_symlinks(skill_installer_path)
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    home = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return _absolute_path_preserving_symlinks(
        home / "skills/.system/skill-installer/scripts/install-skill-from-github.py"
    )


def _find_skill_path(name: str, roots: list[Path]) -> Path | None:
    installed_skills = _installed_skill_index(roots)
    return installed_skills.get(name)


def _installed_skill_index(roots: list[Path]) -> dict[str, Path]:
    return {name: candidates[0] for name, candidates in _installed_skill_candidates(roots).items()}


def _installed_skill_candidates(roots: list[Path]) -> dict[str, list[Path]]:
    installed: dict[str, list[Path]] = {}
    for root in roots:
        for candidate in sorted(root.glob("*/SKILL.md")):
            if not candidate.is_file():
                continue
            candidate_path = candidate.absolute()
            names = [candidate.parent.name]
            frontmatter_name = _skill_frontmatter_name(candidate)
            if frontmatter_name:
                names.insert(0, frontmatter_name)
            for name in names:
                paths = installed.setdefault(name, [])
                if candidate_path not in paths:
                    paths.append(candidate_path)
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


def _normalized_relative_path(value: str) -> bool:
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return bool(
        value
        and value != "."
        and "\\" not in value
        and not posix.is_absolute()
        and not windows.is_absolute()
        and ".." not in posix.parts
        and "." not in posix.parts
        and value == posix.as_posix()
    )


def _absolute_path_preserving_symlinks(path: Path) -> Path:
    return Path(os.path.abspath(str(path.expanduser())))


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_approval_date(value: object) -> bool:
    if not isinstance(value, str) or APPROVAL_DATE_RE.fullmatch(value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _text_summary(payload: dict[str, Any]) -> str:
    lines = [
        (
            "Authority routing skills: "
            f"{payload['available_skill_count']} available, {payload['missing_skill_count']} missing, "
            f"{payload['required_skill_count']} required"
        ),
        (
            "Provenance: "
            f"{payload['status_counts']['current']} current, {payload['status_counts']['drifted']} drifted, "
            f"{payload['status_counts']['source-unregistered']} source-unregistered, "
            f"{payload['status_counts']['unmanaged']} unmanaged"
        ),
        f"Authority skill lock: {payload['manifest']['path']}",
    ]
    if payload["available_skill_roots"]:
        lines.append("Skill roots:")
        lines.extend(f"- {root}" for root in payload["available_skill_roots"])
    if payload["missing_skills"]:
        lines.append("Missing skills:")
        lines.extend(f"- {skill}" for skill in payload["missing_skills"])
    if payload["repair_plan"]["actions"]:
        lines.append("Repair actions:")
        lines.extend(f"- {action['id']}: {action['kind']}" for action in payload["repair_plan"]["actions"])
    if payload["errors"]:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory and verify authority-routing specialist skills required by this workflow pack."
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when any required authority-routing skill is unavailable in the agent environment.",
    )
    parser.add_argument(
        "--strict-provenance",
        action="store_true",
        help="Fail unless every required authority-routing skill matches an approved locked source and digest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Authority skill source lock; defaults to references/authority-skills.lock.json.",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Build fail-closed source registration, installation, or drift-replacement actions.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="With --repair, plan actions without network access or filesystem writes.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="With --repair, execute only approved missing-skill installs and verify every locked tree digest.",
    )
    parser.add_argument(
        "--approve-installs",
        action="store_true",
        help="Explicitly approve network access and Agent-environment writes for --repair --apply.",
    )
    parser.add_argument(
        "--skill-installer",
        type=Path,
        help="Explicit Codex system skill-installer helper used to plan and execute approved install argv.",
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
    if args.check and args.apply:
        parser.error("--check and --apply are mutually exclusive")
    if args.repair and not (args.check or args.apply):
        parser.error("--repair requires exactly one of --check or --apply")
    if not args.repair and (args.check or args.apply):
        parser.error("--check and --apply require --repair")
    if args.approve_installs and not args.apply:
        parser.error("--approve-installs requires --repair --apply")
    common = {
        "skill_roots": list(args.skill_root),
        "strict": args.strict,
        "strict_provenance": args.strict_provenance,
        "include_default_skill_roots": not args.no_default_skill_roots,
        "manifest_path": args.manifest,
        "skill_installer_path": args.skill_installer,
    }
    if args.apply:
        payload = apply_authority_skill_repairs(
            approved=args.approve_installs,
            **common,
        )
    else:
        payload = build_authority_skill_inventory(
            repair=args.repair,
            check=args.check,
            **common,
        )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_text_summary(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
