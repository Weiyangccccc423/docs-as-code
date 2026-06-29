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


def state_path(root: Path) -> Path:
    return root / STATE_REL


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return {}
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_state(root: Path, **updates: Any) -> dict[str, Any]:
    state = load_state(root)
    state.update(updates)
    state["updated_at"] = utc_now()
    save_state(root, state)
    return state
