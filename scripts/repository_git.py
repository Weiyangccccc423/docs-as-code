from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


GIT_TIMEOUT_SECONDS = 10
GIT_MAX_OUTPUT_CHARS = 65_536


@dataclass(frozen=True)
class RepositoryRequest:
    target: Path
    default_branch: str
    author_name: str
    author_email: str
    origin: str = ""
    reviewed: bool = False


@dataclass(frozen=True)
class RepositoryState:
    is_repository: bool = False
    repository_root: str = ""
    branch: str = ""
    local_author_name: str = ""
    local_author_email: str = ""
    origin: str = ""
    has_commits: bool = False


def plan_repository(request: RepositoryRequest) -> dict[str, object]:
    return _repository_result(request, check=True)


def configure_repository(request: RepositoryRequest) -> dict[str, object]:
    plan = _repository_result(request, check=False)
    if not plan["ok"]:
        return plan

    planned_actions = list(plan["planned_actions"])
    applied_actions, error = _apply_actions(request.target.resolve(), planned_actions)
    if error:
        return _apply_failure(plan, applied_actions, error)

    verified = _repository_result(request, check=False)
    if not verified["ok"] or verified["planned_actions"]:
        return _apply_failure(plan, applied_actions, "post-apply Git configuration verification failed")
    verified["status"] = "configured" if applied_actions else "already_configured"
    verified["planned_actions"] = planned_actions
    verified["applied_actions"] = applied_actions
    return verified


def _repository_result(request: RepositoryRequest, *, check: bool) -> dict[str, object]:
    request = RepositoryRequest(
        target=request.target.resolve(),
        default_branch=request.default_branch,
        author_name=request.author_name,
        author_email=request.author_email,
        origin=request.origin,
        reviewed=request.reviewed,
    )
    blockers = _input_blockers(request)
    git_installed = shutil.which("git") is not None
    if not git_installed:
        blockers.append(_blocker("git_unavailable", "Git is required before repository initialization."))

    state, inspection_blockers = _inspect_repository(request.target, git_installed=git_installed)
    blockers.extend(inspection_blockers)
    planned_actions: list[dict[str, object]] = []
    if not blockers:
        planned_actions, planning_blockers = _plan_actions(request, state)
        blockers.extend(planning_blockers)
    if blockers:
        planned_actions = []
    return _result_payload(
        request,
        state,
        git_installed=git_installed,
        check=check,
        blockers=blockers,
        planned_actions=planned_actions,
    )


def _inspect_repository(target: Path, *, git_installed: bool) -> tuple[RepositoryState, list[dict[str, str]]]:
    if not git_installed or not target.is_dir():
        return RepositoryState(), []
    root_result = _git(target, "rev-parse", "--show-toplevel")
    if root_result.returncode != 0 or not root_result.stdout.strip():
        return RepositoryState(), []

    repository_root = str(Path(root_result.stdout.strip()).resolve())
    if Path(repository_root) != target:
        return RepositoryState(is_repository=True, repository_root=repository_root), [
            _blocker(
                "target_inside_parent_repository",
                f"Target belongs to parent repository {repository_root}; choose the repository root explicitly.",
            )
        ]
    return RepositoryState(
        is_repository=True,
        repository_root=repository_root,
        branch=_git_output(target, "symbolic-ref", "--quiet", "--short", "HEAD"),
        local_author_name=_git_output(target, "config", "--local", "--get", "user.name"),
        local_author_email=_git_output(target, "config", "--local", "--get", "user.email"),
        origin=_git_output(target, "remote", "get-url", "origin"),
        has_commits=_git(target, "rev-parse", "--verify", "HEAD").returncode == 0,
    ), []


def _plan_actions(
    request: RepositoryRequest,
    state: RepositoryState,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    actions: list[dict[str, object]] = []
    blockers: list[dict[str, str]] = []
    if not state.is_repository:
        actions.append(
            _action(
                "initialize-repository",
                "Initialize the target as a local Git repository.",
                request.target,
                ["git", "init"],
            )
        )
    branch_actions, branch_blockers = _branch_plan(request, state)
    identity_actions, identity_blockers = _identity_plan(request, state)
    origin_actions, origin_blockers = _origin_plan(request, state)
    actions.extend(branch_actions + identity_actions + origin_actions)
    blockers.extend(branch_blockers + identity_blockers + origin_blockers)
    return actions, blockers


def _branch_plan(
    request: RepositoryRequest,
    state: RepositoryState,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    if state.is_repository and state.branch == request.default_branch:
        return [], []
    if state.is_repository and state.has_commits:
        return [], [
            _blocker(
                "default_branch_conflict",
                f"Existing branch {state.branch or '<detached>'} cannot be renamed automatically.",
            )
        ]
    return [
        _action(
            "set-default-branch",
            "Set the unborn default branch without creating a commit.",
            request.target,
            ["git", "symbolic-ref", "HEAD", f"refs/heads/{request.default_branch}"],
        )
    ], []


def _identity_plan(
    request: RepositoryRequest,
    state: RepositoryState,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    matches = state.local_author_name == request.author_name and state.local_author_email == request.author_email
    if matches:
        return [], []
    if state.is_repository and (state.local_author_name or state.local_author_email):
        return [], [
            _blocker(
                "local_author_conflict",
                "Existing repository-local author differs from the reviewed author; resolve it explicitly.",
            )
        ]
    return [
        _action(
            "set-local-author",
            "Set repository-local commit identity without changing global Git configuration.",
            request.target,
            ["git", "config", "--local", "user.name", request.author_name],
            ["git", "config", "--local", "user.email", request.author_email],
        )
    ], []


def _origin_plan(
    request: RepositoryRequest,
    state: RepositoryState,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    if not request.origin or state.origin == request.origin:
        return [], []
    if state.origin:
        return [], [
            _blocker(
                "origin_conflict",
                "Existing origin URL differs from the reviewed URL; resolve it explicitly.",
            )
        ]
    return [
        _action(
            "add-origin",
            "Add the reviewed origin URL without authenticating or pushing.",
            request.target,
            ["git", "remote", "add", "origin", request.origin],
        )
    ], []


def _apply_actions(target: Path, actions: list[object]) -> tuple[list[str], str]:
    applied_actions: list[str] = []
    for action in actions:
        if not isinstance(action, dict):
            return applied_actions, "invalid planned Git action"
        action_id = action.get("id")
        commands = action.get("commands")
        if not isinstance(action_id, str) or not isinstance(commands, list):
            return applied_actions, "invalid planned Git action"
        error = _apply_action(target, action_id, commands)
        if error:
            return applied_actions, error
        applied_actions.append(action_id)
    return applied_actions, ""


def _apply_action(target: Path, action_id: str, commands: list[object]) -> str:
    for command in commands:
        argv = command.get("argv") if isinstance(command, dict) else None
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            return "invalid planned Git command"
        result = _run(argv, cwd=target)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            return f"Git action {action_id} failed: {detail}"
    return ""


def _result_payload(
    request: RepositoryRequest,
    state: RepositoryState,
    *,
    git_installed: bool,
    check: bool,
    blockers: list[dict[str, str]],
    planned_actions: list[dict[str, object]],
) -> dict[str, object]:
    status = "blocked" if blockers else ("already_configured" if not planned_actions else "ready_to_apply")
    return {
        "ok": not blockers,
        "check": check,
        "target": str(request.target),
        "status": status,
        "git_installed": git_installed,
        "is_repository": state.is_repository,
        "repository_root": state.repository_root,
        "current": {
            "branch": state.branch,
            "local_author_name": state.local_author_name,
            "local_author_email": state.local_author_email,
            "origin": _display_origin(state.origin),
            "has_commits": state.has_commits,
        },
        "requested": {
            "default_branch": request.default_branch,
            "local_author_name": request.author_name,
            "local_author_email": request.author_email,
            "origin": _display_origin(request.origin),
            "reviewed": request.reviewed,
        },
        "blockers": blockers,
        "planned_actions": planned_actions,
        "applied_actions": [],
        "commit_created": False,
        "push_attempted": False,
        "remote_authentication_verified": False,
        "next": _next_step(status, request.origin),
    }


def _input_blockers(request: RepositoryRequest) -> list[dict[str, str]]:
    blockers = _target_blockers(request.target)
    if not request.reviewed:
        blockers.append(
            _blocker(
                "review_required",
                "Default branch, repository-local author, and optional origin must be explicitly reviewed.",
            )
        )
    if not _plain_value(request.author_name):
        blockers.append(_blocker("invalid_author_name", "Author name must be non-empty and contain no control characters."))
    if not _valid_email(request.author_email):
        blockers.append(_blocker("invalid_author_email", "Author email must be a non-empty email-like value."))
    if not _valid_branch(request.default_branch):
        blockers.append(_blocker("invalid_default_branch", "Default branch is not a valid Git branch name."))
    blockers.extend(_origin_blockers(request.origin))
    return blockers


def _target_blockers(target: Path) -> list[dict[str, str]]:
    if not target.exists():
        return [_blocker("target_missing", "Target directory must exist before Git initialization.")]
    if not target.is_dir():
        return [_blocker("target_not_directory", "Target path must be a directory.")]
    return []


def _origin_blockers(origin: str) -> list[dict[str, str]]:
    if not origin:
        return []
    if not _plain_value(origin):
        return [_blocker("invalid_origin", "Origin must contain no surrounding whitespace or control characters.")]
    if _origin_contains_credentials(origin):
        return [
            _blocker(
                "origin_contains_credentials",
                "HTTP origin URLs must not embed usernames, passwords, or access tokens.",
            )
        ]
    try:
        urlsplit(origin)
    except ValueError:
        return [_blocker("invalid_origin", "Origin URL syntax is invalid.")]
    return []


def _origin_contains_credentials(origin: str) -> bool:
    scheme, separator, remainder = origin.partition("://")
    if not separator or scheme.lower() not in {"http", "https"}:
        return False
    authority = remainder.split("/", 1)[0]
    return "@" in authority


def _display_origin(origin: str) -> str:
    return "<redacted-credential-url>" if _origin_contains_credentials(origin) else origin


def _valid_branch(value: str) -> bool:
    if not _plain_value(value) or value.startswith("-"):
        return False
    git = shutil.which("git")
    if git is None:
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value))
    return _run([git, "check-ref-format", "--branch", value], cwd=None).returncode == 0


def _valid_email(value: str) -> bool:
    if not _plain_value(value) or value.count("@") != 1:
        return False
    local, domain = value.split("@", 1)
    return bool(local and domain and not any(char.isspace() for char in value))


def _plain_value(value: str) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and not any(ord(char) < 32 for char in value)
    )


def _action(action_id: str, description: str, target: Path, *commands: list[str]) -> dict[str, object]:
    return {
        "id": action_id,
        "description": description,
        "cwd": str(target),
        "commands": [{"argv": command} for command in commands],
        "writes_state": True,
        "approval_required": False,
    }


def _blocker(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _git(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(target), *args], cwd=None)


def _git_output(target: Path, *args: str) -> str:
    result = _git(target, *args)
    return result.stdout.strip() if result.returncode == 0 else ""


def _run(argv: list[str], *, cwd: Path | None) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        return subprocess.CompletedProcess(
            result.args,
            result.returncode,
            result.stdout[:GIT_MAX_OUTPUT_CHARS],
            result.stderr[:GIT_MAX_OUTPUT_CHARS],
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(argv, 1, "", str(error)[:GIT_MAX_OUTPUT_CHARS])


def _apply_failure(plan: dict[str, object], applied_actions: list[str], error: str) -> dict[str, object]:
    return {
        **plan,
        "ok": False,
        "check": False,
        "status": "apply_failed",
        "applied_actions": applied_actions,
        "errors": [error[:GIT_MAX_OUTPUT_CHARS]],
        "next": "inspect partial Git state before retrying",
    }


def _next_step(status: str, origin: str) -> str:
    if status == "blocked":
        return "resolve blockers and rerun repository init --check"
    if status == "ready_to_apply":
        return "run the same reviewed repository init command without --check"
    if origin:
        return "review authentication separately before any explicit push"
    return "review staged files before creating the first commit"
