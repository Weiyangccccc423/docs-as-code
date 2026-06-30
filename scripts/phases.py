from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .gates import GATE_NAMES, evaluate_gate
    from .state import StateFileError, load_state, save_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from gates import GATE_NAMES, evaluate_gate
    from state import StateFileError, load_state, save_state, utc_now


PHASE_NAMES = GATE_NAMES


@dataclass
class AdvanceResult:
    phase: str
    target: str
    ok: bool
    advanced: bool
    gate: dict[str, Any]
    state: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "target": self.target,
            "ok": self.ok,
            "advanced": self.advanced,
            "errors": self.errors,
            "gate": self.gate,
            "state": self.state,
        }


def advance_phase(root: Path, phase: str) -> AdvanceResult:
    if phase not in PHASE_NAMES:
        raise ValueError(f"unknown phase: {phase}")
    root = root.resolve()
    try:
        gate = evaluate_gate(root, phase)
    except StateFileError as error:
        return AdvanceResult(
            phase=phase,
            target=str(root),
            ok=False,
            advanced=False,
            errors=[f"failed to advance phase: {error}"],
            gate={},
        )
    if not gate.ok:
        return AdvanceResult(
            phase=phase,
            target=str(root),
            ok=False,
            advanced=False,
            errors=[f"{phase} gate failed"],
            gate=gate.to_dict(),
            state=gate.state,
        )

    try:
        state = load_state(root)
    except StateFileError as error:
        return AdvanceResult(
            phase=phase,
            target=str(root),
            ok=False,
            advanced=False,
            errors=[f"failed to advance phase: {error}"],
            gate=gate.to_dict(),
            state=gate.state,
        )
    original_state = copy.deepcopy(state)
    previous_phase = state.get("phase")
    advanced_at = utc_now()
    history = state.get("phase_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "phase": phase,
            "from_phase": previous_phase,
            "gate": phase,
            "advanced_at": advanced_at,
        }
    )
    state.update(
        {
            "phase": phase,
            "phase_history": history,
            "last_gate": {
                "name": phase,
                "ok": gate.ok,
                "checked_at": advanced_at,
            },
            "updated_at": advanced_at,
        }
    )
    try:
        save_state(root, state)
    except StateFileError as error:
        return AdvanceResult(
            phase=phase,
            target=str(root),
            ok=False,
            advanced=False,
            errors=[f"failed to advance phase: {error}"],
            gate=gate.to_dict(),
            state=original_state,
        )
    return AdvanceResult(
        phase=phase,
        target=str(root),
        ok=True,
        advanced=True,
        gate=gate.to_dict(),
        state=state,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance docs-as-code workflow phases after gates pass.")
    parser.add_argument("phase", choices=PHASE_NAMES, help="Phase to advance to.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to update.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable advance result.")
    args = parser.parse_args()
    result = advance_phase(Path(args.target), args.phase)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.ok else 1
    if result.ok:
        print(f"Advanced phase: {args.phase}")
        return 0
    print(f"Advance failed: {args.phase}")
    for error in result.errors:
        print(f"- ERROR: {error}")
    for requirement in result.gate.get("requirements", []):
        if isinstance(requirement, dict) and not requirement.get("ok"):
            path = requirement.get("path")
            suffix = f" ({path})" if path else ""
            print(f"- {requirement.get('code')}: {requirement.get('message')}{suffix}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
