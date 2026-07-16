from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_REL = Path(".governance/state.json")


class StateFileError(RuntimeError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"invalid governance state file: {path}: {reason}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def next_state_timestamp(state: dict[str, Any], candidate: str) -> str:
    current = state.get("updated_at")
    if not isinstance(current, str):
        return candidate
    try:
        current_time = datetime.fromisoformat(current)
        candidate_time = datetime.fromisoformat(candidate)
    except ValueError:
        return candidate
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        return candidate
    if candidate_time.tzinfo is None or candidate_time.utcoffset() is None:
        return candidate
    return current if current_time > candidate_time else candidate


def state_path(root: Path) -> Path:
    return root / STATE_REL


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return {}
    if not path.is_file():
        raise StateFileError(path, "not a file")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StateFileError(path, f"invalid JSON: {error.msg}") from error
    except UnicodeDecodeError as error:
        raise StateFileError(path, f"invalid UTF-8: {error.reason}") from error
    except OSError as error:
        reason = error.strerror or str(error)
        raise StateFileError(path, f"unreadable: {reason}") from error
    if not isinstance(state, dict):
        raise StateFileError(path, "root must be an object")
    return state


def save_state(root: Path, state: dict[str, Any]) -> None:
    path = state_path(root)
    if not isinstance(state, dict):
        raise StateFileError(path, "root must be an object")
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.replace(path)
    except OSError as error:
        if tmp_path.exists() and tmp_path.is_file():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        reason = error.strerror or str(error)
        raise StateFileError(path, f"unwritable: {reason}") from error


def merge_state(root: Path, *, updated_at: str | None = None, **updates: Any) -> dict[str, Any]:
    state = load_state(root)
    timestamp = next_state_timestamp(state, updated_at if updated_at is not None else utc_now())
    state.update(updates)
    state["updated_at"] = timestamp
    save_state(root, state)
    return state
