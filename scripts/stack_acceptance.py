from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .dry_run_workflow import run_dry_run
except ImportError:  # pragma: no cover - direct script execution
    from dry_run_workflow import run_dry_run


REQUIRED_STACKS = ("python", "node")
OPTIONAL_STACKS = ("rust",)


def _stack_status(stacks: dict[str, object], name: str) -> str:
    entry = stacks.get(name)
    return str(entry.get("status", "")) if isinstance(entry, dict) else ""


def _stack_blocker(name: str) -> dict[str, str]:
    return {
        "code": f"{name}_stack_not_passed",
        "message": f"{name} stack acceptance must report status passed",
    }


def run_stack_acceptance(
    *,
    target: Path | None = None,
    product: Path | None = None,
    keep: bool = False,
    strict_rust: bool = False,
) -> dict[str, object]:
    dry_run = run_dry_run(target=target, product=product, keep=keep)
    dry_run_ok = dry_run.get("ok") is True
    summary = dry_run.get("stack_acceptance")
    summary_map = summary if isinstance(summary, dict) else {}
    raw_stacks = summary_map.get("stacks")
    stacks = dict(raw_stacks) if isinstance(raw_stacks, dict) else {}
    blockers: list[dict[str, str]] = []

    if not dry_run_ok:
        blockers.append(
            {
                "code": "dry_run_failed",
                "message": str(dry_run.get("error", "governance dry run failed")),
            }
        )
    elif not summary_map:
        blockers.append(
            {
                "code": "stack_acceptance_missing",
                "message": "governance dry run did not return a stack acceptance matrix",
            }
        )
    else:
        blockers.extend(
            _stack_blocker(name)
            for name in REQUIRED_STACKS
            if _stack_status(stacks, name) != "passed"
        )
        if strict_rust and _stack_status(stacks, "rust") != "passed":
            blockers.append(_stack_blocker("rust"))

    all_required_passed = all(_stack_status(stacks, name) == "passed" for name in REQUIRED_STACKS)
    available_entries = [
        entry
        for entry in stacks.values()
        if isinstance(entry, dict) and entry.get("runtime_available") is True
    ]
    all_available_passed = bool(available_entries) and all(
        entry.get("status") == "passed" for entry in available_entries
    )
    strict_rust_passed = _stack_status(stacks, "rust") == "passed"
    return {
        "ok": dry_run_ok and not blockers,
        "workflow": "real-stack-acceptance",
        "policy": str(summary_map.get("policy", "")),
        "strict_rust": strict_rust,
        "dry_run_ok": dry_run_ok,
        "dry_run_error": str(dry_run.get("error", "")),
        "required_stacks": list(REQUIRED_STACKS),
        "optional_stacks": list(OPTIONAL_STACKS),
        "all_required_passed": all_required_passed,
        "all_available_passed": all_available_passed,
        "strict_rust_passed": strict_rust_passed,
        "stacks": stacks,
        "blockers": blockers,
        "final_phase": dry_run.get("final_phase", ""),
        "workspace": dry_run.get("workspace", ""),
        "target": dry_run.get("target", ""),
        "product": dry_run.get("product", ""),
        "target_retained": dry_run.get("target_retained", False),
        "failed_step": dry_run.get("failed_step"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run real Python, Node.js, and optional Rust workflow acceptance.")
    parser.add_argument("--target", type=Path, help="Optional explicit target directory. The target is retained.")
    parser.add_argument("--product", type=Path, help="Optional product document. Defaults to a generated sample PRD.")
    parser.add_argument("--keep", action="store_true", help="Retain the generated temporary target on success.")
    parser.add_argument(
        "--strict-rust",
        action="store_true",
        help="Require the Rust runtime and offline Cargo tests to pass.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    status = "passed" if payload.get("ok") else "blocked"
    print(f"Stack acceptance {status}")
    stacks = payload.get("stacks")
    if isinstance(stacks, dict):
        for name in (*REQUIRED_STACKS, *OPTIONAL_STACKS):
            print(f"{name}: {_stack_status(stacks, name) or 'missing'}")
    blockers = payload.get("blockers")
    if isinstance(blockers, list):
        for blocker in blockers:
            if isinstance(blocker, dict):
                print(f"Blocker: {blocker.get('code')}: {blocker.get('message')}")


def main() -> int:
    args = build_parser().parse_args()
    payload = run_stack_acceptance(
        target=args.target,
        product=args.product,
        keep=args.keep,
        strict_rust=args.strict_rust,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
