from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import workflow_executor


SNAPSHOT = "a" * 64
OTHER_SNAPSHOT = "b" * 64


def _command(argv: list[str], cwd: Path, *, writes_state: bool = False) -> dict[str, object]:
    return {
        "argv": argv,
        "cwd": str(cwd),
        "writes_state": writes_state,
        "approval_required": False,
    }


def _resume_payload(target: Path, *, approval_required: bool = False) -> dict[str, object]:
    steps = [
        {
            "id": "advance-product-structuring-check",
            "kind": "preflight",
            "sequence": 1,
            "cwd": str(target),
            "argv": ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
            "writes_state": False,
            "approval_required": False,
            "success_condition": "ok:true",
        },
        {
            "id": "advance-product-structuring",
            "kind": "apply",
            "sequence": 2,
            "cwd": str(target),
            "argv": ["bin/governance", "advance", "product-structuring", ".", "--json"],
            "writes_state": True,
            "approval_required": approval_required,
            "success_condition": "ok:true",
        },
    ]
    action = {
        "id": "advance-product-structuring",
        "kind": "guarded-sequence",
        "valid": True,
        "writes_state": True,
        "approval_required": approval_required,
        "execution_policy": "run_preflight_then_apply_only_when_preflight_succeeds",
        "steps": steps,
    }
    return {
        "ok": True,
        "workflow": "workflow-resume",
        "phase": "initialized",
        "status": "approval_required" if approval_required else "action_ready",
        "can_continue": not approval_required,
        "stop_before_action": approval_required,
        "stale": False,
        "snapshot": {"id": SNAPSHOT},
        "action_count": 1,
        "selected_action": action,
        "assert_snapshot_command": _command(
            ["bin/governance", "workflow", "resume", ".", "--expect-snapshot", SNAPSHOT, "--json"],
            target,
        ),
        "refresh_command": _command(["bin/governance", "workflow", "resume", ".", "--json"], target),
        "errors": [],
    }


def _execution(argv: list[str], cwd: Path, payload: dict[str, object], returncode: int = 0) -> dict[str, object]:
    return {
        "started": True,
        "argv": argv,
        "cwd": str(cwd),
        "returncode": returncode,
        "result": "pass" if returncode == 0 else "fail",
        "timed_out": False,
        "stdout": json.dumps(payload),
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "output_redacted": False,
    }


class WorkflowExecutorTest(unittest.TestCase):
    def _target(self, tmp: str) -> Path:
        target = Path(tmp) / "target"
        (target / "bin").mkdir(parents=True)
        (target / "bin/governance").write_text("#!/bin/sh\n", encoding="utf-8")
        (target / "bin/governance").chmod(0o755)
        return target

    def test_executes_exact_snapshot_bound_steps_in_order_then_refreshes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                if argv[1:3] == ["workflow", "resume"]:
                    return _execution(argv, cwd, resume)
                return _execution(argv, cwd, {"ok": True})

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertTrue(result["ok"])
        self.assertEqual("completed", result["status"])
        self.assertEqual(
            [
                ["bin/governance", "workflow", "resume", ".", "--json"],
                ["bin/governance", "workflow", "resume", ".", "--expect-snapshot", SNAPSHOT, "--json"],
                ["bin/governance", "advance", "product-structuring", ".", "--check", "--json"],
                ["bin/governance", "advance", "product-structuring", ".", "--json"],
                ["bin/governance", "workflow", "resume", ".", "--json"],
            ],
            calls,
        )
        self.assertEqual(2, len(result["step_results"]))
        self.assertTrue(result["refresh"]["payload"]["ok"])

    def test_approval_required_stops_before_assert_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target, approval_required=True)
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                return _execution(argv, cwd, resume)

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("approval_required", result["status"])
        self.assertEqual(["bin/governance", "workflow", "resume", ".", "--json"], calls[0])
        self.assertEqual(1, len(calls))
        self.assertIn("approval", " ".join(result["stop_reasons"]))

    def test_nested_step_approval_cannot_be_hidden_by_action_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            resume["selected_action"]["approval_required"] = False
            resume["selected_action"]["steps"][0]["approval_required"] = True
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                return _execution(argv, cwd, resume)

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("approval_required", result["status"])
        self.assertEqual(1, len(calls))

    def test_blocked_route_without_action_is_not_reported_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            resume.update(
                {
                    "status": "blocked",
                    "can_continue": False,
                    "stop_before_action": True,
                    "action_count": 0,
                    "selected_action": {},
                    "stop_reasons": ["no_resumable_action"],
                }
            )

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                return _execution(argv, cwd, resume)

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("blocked", result["status"])

    def test_complete_route_without_action_is_successful_terminal_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            resume.update(
                {
                    "status": "complete",
                    "can_continue": False,
                    "stop_before_action": True,
                    "action_count": 0,
                    "selected_action": {},
                }
            )

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                return _execution(argv, cwd, resume)

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertTrue(result["ok"])
        self.assertEqual("complete", result["status"])

    def test_snapshot_drift_stops_before_selected_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                if "--expect-snapshot" in argv:
                    return _execution(
                        argv,
                        cwd,
                        {"ok": False, "status": "stale", "stale": True, "snapshot": {"id": OTHER_SNAPSHOT}},
                        returncode=1,
                    )
                return _execution(argv, cwd, resume)

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("stale", result["status"])
        self.assertEqual(2, len(calls))
        self.assertEqual([], result["step_results"])

    def test_unsafe_snapshot_assertion_is_rejected_before_execution(self) -> None:
        for unsafe_field in ("writes_state", "approval_required"):
            with self.subTest(unsafe_field=unsafe_field), tempfile.TemporaryDirectory() as tmp:
                target = self._target(tmp)
                resume = _resume_payload(target)
                resume["assert_snapshot_command"][unsafe_field] = True
                calls: list[list[str]] = []

                def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                    calls.append(argv)
                    return _execution(argv, cwd, resume)

                with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                    result = workflow_executor.execute_workflow_action(target)

                self.assertFalse(result["ok"])
                self.assertEqual("blocked", result["status"])
                self.assertEqual(["assert_snapshot_command_unsafe"], result["stop_reasons"])
                self.assertEqual(1, len(calls))

    def test_cwd_escape_is_rejected_before_snapshot_assertion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            resume["selected_action"] = copy.deepcopy(resume["selected_action"])
            resume["selected_action"]["steps"][0]["cwd"] = str(target.parent)
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                return _execution(argv, cwd, resume)

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("blocked", result["status"])
        self.assertIn("action_command_cwd_outside_target", result["stop_reasons"])
        self.assertEqual(1, len(calls))

    def test_step_failure_stops_and_preserves_prior_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                if argv[1:3] == ["workflow", "resume"]:
                    return _execution(argv, cwd, resume)
                if "--check" not in argv:
                    return _execution(argv, cwd, {"ok": False, "error": "gate failed"}, returncode=1)
                return _execution(argv, cwd, {"ok": True})

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("step_failed", result["status"])
        self.assertEqual(2, len(result["step_results"]))
        self.assertTrue(result["writes_state"])
        self.assertEqual(4, len(calls))
        self.assertEqual({}, result["refresh"])

    def test_refresh_failure_returns_recovery_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            resume = _resume_payload(target)
            calls: list[list[str]] = []

            def run(argv: list[str], *, cwd: Path, **_: object) -> dict[str, object]:
                calls.append(argv)
                if argv[1:3] == ["workflow", "resume"] and len(calls) == 5:
                    return _execution(argv, cwd, {"ok": False, "error": "refresh failed"}, returncode=1)
                if argv[1:3] == ["workflow", "resume"]:
                    return _execution(argv, cwd, resume)
                return _execution(argv, cwd, {"ok": True})

            with mock.patch.object(workflow_executor, "run_bounded_command", side_effect=run):
                result = workflow_executor.execute_workflow_action(target)

        self.assertFalse(result["ok"])
        self.assertEqual("refresh_failed", result["status"])
        self.assertIn("dac next --json", result["recovery"])
        self.assertEqual(5, len(calls))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
