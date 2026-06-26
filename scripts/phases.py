from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from .gates import GATE_NAMES, evaluate_gate
    from .state import load_state, save_state, utc_now
except ImportError:  # pragma: no cover - direct script execution
    from gates import GATE_NAMES, evaluate_gate
    from state import load_state, save_state, utc_now


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
    gate = evaluate_gate(root, phase)
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

    state = load_state(root)
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
    save_state(root, state)
    return AdvanceResult(
        phase=phase,
        target=str(root),
        ok=True,
        advanced=True,
        gate=gate.to_dict(),
        state=state,
    )
