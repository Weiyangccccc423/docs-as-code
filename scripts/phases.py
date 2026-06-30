from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .gates import GATE_NAMES, evaluate_gate
    from .state import STATE_REL, StateFileError, load_state, save_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from gates import GATE_NAMES, evaluate_gate
    from state import STATE_REL, StateFileError, load_state, save_state, utc_now


PHASE_NAMES = GATE_NAMES


@dataclass
class AdvanceResult:
    phase: str
    target: str
    ok: bool
    advanced: bool
    gate: dict[str, Any]
    check: bool = False
    would_advance: bool = False
    would_state: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "target": self.target,
            "ok": self.ok,
            "advanced": self.advanced,
            "check": self.check,
            "would_advance": self.would_advance,
            "would_state": self.would_state,
            "errors": self.errors,
            "gate": self.gate,
            "state": self.state,
        }


def check_advance_phase(root: Path, phase: str) -> AdvanceResult:
    if phase not in PHASE_NAMES:
        raise ValueError(f"unknown phase: {phase}")
    root = root.resolve()
    plan = _build_advance_plan(root, phase)
    if plan is not None:
        plan.check = True
        return plan
    gate = evaluate_gate(root, phase)
    state = load_state(root)
    planned_state = _planned_advance_state(state, phase, gate.ok)
    return AdvanceResult(
        phase=phase,
        target=str(root),
        ok=True,
        advanced=False,
        check=True,
        would_advance=True,
        gate=gate.to_dict(),
        state=state,
        would_state=planned_state,
    )


def advance_phase(root: Path, phase: str) -> AdvanceResult:
    if phase not in PHASE_NAMES:
        raise ValueError(f"unknown phase: {phase}")
    root = root.resolve()
    plan_error = _build_advance_plan(root, phase)
    if plan_error is not None:
        return plan_error

    gate = evaluate_gate(root, phase)
    state = load_state(root)
    planned_state = _planned_advance_state(state, phase, gate.ok)
    try:
        save_state(root, planned_state)
    except StateFileError as error:
        return AdvanceResult(
            phase=phase,
            target=str(root),
            ok=False,
            advanced=False,
            errors=[f"failed to advance phase: {error}"],
            gate=gate.to_dict(),
            state=state,
            would_state=planned_state,
        )
    return AdvanceResult(
        phase=phase,
        target=str(root),
        ok=True,
        advanced=True,
        gate=gate.to_dict(),
        state=planned_state,
    )


def _build_advance_plan(root: Path, phase: str) -> AdvanceResult | None:
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
    state_output_error = _state_output_error(root)
    if state_output_error is not None:
        return AdvanceResult(
            phase=phase,
            target=str(root),
            ok=False,
            advanced=False,
            errors=[f"failed to advance phase: {state_output_error}"],
            gate=gate.to_dict(),
            state=state,
        )
    return None


def _state_output_error(root: Path) -> StateFileError | None:
    path = root / STATE_REL
    if path.parent.exists() and not path.parent.is_dir():
        rel_parent = path.parent.relative_to(root).as_posix()
        return StateFileError(path, f"unwritable: {rel_parent} is not a directory")
    temp = path.with_name(f".{path.name}.tmp")
    if temp.exists() and not temp.is_file():
        rel_temp = temp.relative_to(root).as_posix()
        return StateFileError(path, f"unwritable: {rel_temp} is not a file")
    return None


def _planned_advance_state(state: dict[str, Any], phase: str, gate_ok: bool) -> dict[str, Any]:
    planned = copy.deepcopy(state)
    previous_phase = planned.get("phase")
    advanced_at = utc_now()
    history = planned.get("phase_history")
    if not isinstance(history, list):
        history = []
    else:
        history = copy.deepcopy(history)
    history.append(
        {
            "phase": phase,
            "from_phase": previous_phase,
            "gate": phase,
            "advanced_at": advanced_at,
        }
    )
    planned.update(
        {
            "phase": phase,
            "phase_history": history,
            "last_gate": {
                "name": phase,
                "ok": gate_ok,
                "checked_at": advanced_at,
            },
            "updated_at": advanced_at,
        }
    )
    return planned


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance docs-as-code workflow phases after gates pass.")
    parser.add_argument("phase", choices=PHASE_NAMES, help="Phase to advance to.")
    parser.add_argument("target", nargs="?", default=".", help="Repository root to update.")
    parser.add_argument("--check", action="store_true", help="Run phase advance preflight without writing state.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable advance result.")
    args = parser.parse_args()
    if args.check:
        result = check_advance_phase(Path(args.target), args.phase)
    else:
        result = advance_phase(Path(args.target), args.phase)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.ok else 1
    if args.check and result.ok:
        print(f"Advance preflight passed: {args.phase}")
        return 0
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
