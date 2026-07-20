import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import implementation_run

from tests.test_governance_cli import (
    CLI,
    _append_project_command,
    _implementation_ready_target,
    _run_governance_json,
)


def _run(
    case: unittest.TestCase,
    target: Path,
    *args: str,
    expected_returncode: int = 0,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "implementation",
            "run",
            str(target),
            *args,
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    case.assertEqual(expected_returncode, result.returncode, result.stderr + result.stdout)
    return json.loads(result.stdout)


class ImplementationRunTest(unittest.TestCase):
    def test_governance_repair_is_not_applied_when_payload_reports_failure(self) -> None:
        preflights = [
            {
                "environment_readiness": {
                    "repair_actions": [
                        {
                            "id": "repair-python-runtime",
                            "strategy": "governance-env",
                            "repair_preflight_command": {
                                "cwd": ".",
                                "argv": [
                                    "bin/governance",
                                    "env",
                                    "--repair",
                                    "--check",
                                    "--target",
                                    ".",
                                    "--json",
                                ],
                            },
                        }
                    ]
                }
            }
        ]
        preview = {
            "ok": True,
            "payload": {
                "ok": False,
                "repair_decision": {
                    "can_auto_apply": True,
                    "requires_approval": False,
                    "manual_repair_required": False,
                },
            },
        }
        failed_apply = {"ok": True, "payload": {"ok": False}}

        with mock.patch.object(
            implementation_run,
            "_run_embedded_json_command",
            side_effect=[preview, failed_apply],
        ):
            outcomes = implementation_run._attempt_environment_repairs(
                Path("."),
                preflights,
                approve_repairs=False,
                timeout_seconds=30.0,
                max_output_bytes=4096,
            )

        self.assertEqual(1, len(outcomes))
        self.assertFalse(outcomes[0]["applied"])

    def test_start_write_failure_is_not_misreported_as_lock_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            preview = _run(self, target, "--task", "TASK-001", "--check")

            with mock.patch.object(
                implementation_run,
                "apply_implementation_start",
                side_effect=OSError("disk full"),
            ):
                payload = implementation_run.run_implementation_task(
                    target,
                    task_id="TASK-001",
                    apply_start=True,
                    expect_snapshot=str(preview["snapshot"]["id"]),
                )

            self.assertFalse(payload["ok"])
            self.assertEqual("operation_failed", payload["status"])
            self.assertIn("disk full", payload["errors"][0])

    def test_check_selects_ready_task_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            payload = _run(self, target, "--task", "TASK-001", "--check")

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["check"])
            self.assertEqual("ready_to_start", payload["status"])
            self.assertEqual("TASK-001", payload["task_id"])
            self.assertFalse(payload["writes_requested"])
            self.assertFalse(payload["executed"])
            self.assertFalse(payload["closeout_applied"])
            self.assertRegex(payload["snapshot"]["id"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                ["bin/governance", "implementation", "run", ".", "--task", "TASK-001", "--apply-start", "--expect-snapshot", payload["snapshot"]["id"], "--json"],
                payload["next_action"]["argv"],
            )
            self.assertIn(
                "| TASK-001 | Ready |",
                (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"),
            )

    def test_apply_start_claims_task_and_stops_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            preview = _run(self, target, "--task", "TASK-001", "--check")

            payload = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--apply-start",
                "--expect-snapshot",
                preview["snapshot"]["id"],
            )

            self.assertTrue(payload["ok"])
            self.assertEqual("implementation_required", payload["status"])
            self.assertTrue(payload["start_applied"])
            self.assertFalse(payload["executed"])
            self.assertEqual("edit_selected_task", payload["next_action"]["kind"])
            self.assertIn(
                "| TASK-001 | In Progress |",
                (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"),
            )

    def test_check_preflights_every_bound_command_for_in_progress_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run(self, target, "--task", "TASK-001", "--check")

            self.assertTrue(payload["ok"])
            self.assertEqual("verification_ready", payload["status"])
            self.assertEqual(["task-tests"], payload["verification_command_names"])
            self.assertEqual(1, payload["verification_summary"]["required_count"])
            self.assertEqual(1, payload["verification_summary"]["ready_count"])
            self.assertTrue(payload["verification_preflights"][0]["verification_ready"])
            self.assertFalse(payload["executed"])
            self.assertFalse((target / "docs/development/04-implementation-evidence.md").exists())

    def test_execute_records_all_evidence_without_marking_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "print('task passed')"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run(self, target, "--task", "TASK-001", "--execute")

            self.assertTrue(payload["ok"])
            self.assertEqual("closeout_ready", payload["status"])
            self.assertTrue(payload["executed"])
            self.assertEqual(1, payload["verification_summary"]["passed_count"])
            self.assertTrue(payload["verification_runs"][0]["command_passed"])
            self.assertTrue(payload["closeout_preview"]["closeout_ready"])
            self.assertFalse(payload["closeout_applied"])
            self.assertIn(
                "| TASK-001 | In Progress |",
                (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"),
            )

    def test_execute_and_closeout_completes_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "print('task passed')"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run(self, target, "--task", "TASK-001", "--execute", "--closeout")

            self.assertTrue(payload["ok"])
            self.assertEqual("complete", payload["status"])
            self.assertTrue(payload["executed"])
            self.assertTrue(payload["closeout_applied"])
            self.assertEqual("Done", payload["closeout_apply"]["task"]["status"])
            self.assertIn(
                "| TASK-001 | Done |",
                (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"),
            )

    def test_execute_stops_after_failing_command_and_preserves_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _append_project_command(
                target,
                name="task-tests",
                argv=["python3", "-c", "raise SystemExit(7)"],
            )
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--execute",
                "--closeout",
                expected_returncode=1,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual("verification_failed", payload["status"])
            self.assertTrue(payload["executed"])
            self.assertEqual(1, payload["verification_summary"]["failed_count"])
            self.assertFalse(payload["closeout_applied"])
            self.assertIn(
                "| TASK-001 | In Progress |",
                (target / "docs/development/02-task-board.md").read_text(encoding="utf-8"),
            )

    def test_expected_snapshot_rejects_stale_task_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            preview = _run(self, target, "--task", "TASK-001", "--check")
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            payload = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--execute",
                "--expect-snapshot",
                preview["snapshot"]["id"],
                expected_returncode=1,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual("stale", payload["status"])
            self.assertTrue(payload["stale"])
            self.assertFalse(payload["executed"])

    def test_apply_start_cannot_be_combined_with_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)

            payload = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--apply-start",
                "--execute",
                expected_returncode=1,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual("invalid_request", payload["status"])
            self.assertIn("--apply-start cannot be combined", payload["errors"][0])

    def test_snapshot_ignores_transient_lock_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            preview = _run(self, target, "--task", "TASK-001", "--check")
            (target / ".governance/transient.lock").touch()

            payload = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--check",
                "--expect-snapshot",
                preview["snapshot"]["id"],
            )

            self.assertTrue(payload["ok"])
            self.assertFalse(payload["stale"])
            self.assertEqual(preview["snapshot"]["id"], payload["snapshot"]["id"])

    def test_auto_repair_requires_explicit_approval_for_reviewed_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            installer = target / "tools/install-demo-runtime"
            installer.parent.mkdir(parents=True, exist_ok=True)
            installer.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                "mkdir -p tools-bin\n"
                "printf '%s\\n' '#!/bin/sh' 'printf \"Demo 2.1.0\\n\"' > tools-bin/demo-runtime\n"
                "chmod +x tools-bin/demo-runtime\n",
                encoding="utf-8",
            )
            installer.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = os.pathsep.join([str(target / "tools-bin"), env.get("PATH", "")])
            register = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "project-env",
                    "register",
                    str(target),
                    "--tool-id",
                    "demo-runtime",
                    "--executable",
                    "demo-runtime",
                    "--version-prefix",
                    "Demo ",
                    "--minimum-version",
                    "2.0.0",
                    "--maximum-exclusive-version",
                    "3.0.0",
                    "--repair-strategy",
                    "reviewed-command",
                    "--repair-source-type",
                    "official-url",
                    "--repair-source",
                    "https://example.com/demo-runtime",
                    "--review-evidence",
                    "docs/architecture/02-containers.md",
                    "--repair-instructions",
                    "Run the reviewed repository installer.",
                    "--repair-command-cwd",
                    ".",
                    "--repair-command-arg",
                    "tools/install-demo-runtime",
                    "--reviewed",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(0, register.returncode, register.stderr + register.stdout)
            _append_project_command(
                target,
                name="task-tests",
                argv=["demo-runtime"],
                environment="project-runtime",
            )

            blocked = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--execute",
                "--auto-repair",
                expected_returncode=1,
                env=env,
            )

            self.assertEqual("repair_required", blocked["status"])
            self.assertTrue(blocked["environment_repairs"][0]["approval_required"])
            self.assertFalse(blocked["environment_repairs"][0]["applied"])
            self.assertFalse((target / "tools-bin/demo-runtime").exists())

            repaired = _run(
                self,
                target,
                "--task",
                "TASK-001",
                "--execute",
                "--auto-repair",
                "--approve-repairs",
                env=env,
            )

            self.assertTrue(repaired["ok"])
            self.assertEqual("closeout_ready", repaired["status"])
            self.assertTrue(repaired["environment_repairs"][0]["applied"])
            self.assertTrue(repaired["verification_runs"][0]["command_passed"])
            self.assertTrue((target / ".governance/project-environment-repairs.json").is_file())

    def test_execute_refuses_when_implementation_run_lock_is_held(self) -> None:
        import fcntl

        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            lock_path = target / ".governance/implementation-run.lock"
            with lock_path.open("a+b") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                payload = _run(
                    self,
                    target,
                    "--task",
                    "TASK-001",
                    "--execute",
                    expected_returncode=1,
                )

            self.assertFalse(payload["ok"])
            self.assertEqual("lock_unavailable", payload["status"])
            self.assertFalse(payload["executed"])


if __name__ == "__main__":
    unittest.main()
