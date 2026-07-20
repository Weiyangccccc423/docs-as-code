import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_governance_cli import (
    CLI,
    _implementation_ready_target,
    _run_governance_json,
)


def _initialize_git(case: unittest.TestCase, target: Path) -> None:
    if (target / ".git").exists():
        return
    result = subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=target,
        text=True,
        capture_output=True,
        check=False,
    )
    case.assertEqual(0, result.returncode, result.stderr)


def _write_review_report(
    target: Path,
    task_id: str = "TASK-001",
    *,
    findings: list[dict[str, str]] | None = None,
) -> Path:
    path = target / ".governance/code-review-reports" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": task_id,
                "reviewer": {
                    "kind": "agent",
                    "id": "independent-code-review-pass",
                },
                "verdict": "approved",
                "summary": "Reviewed the complete task change set against linked requirements and tests.",
                "findings": findings or [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class ImplementationReviewTest(unittest.TestCase):
    def _start_with_change(self, target: Path) -> Path:
        _initialize_git(self, target)
        _run_governance_json(
            self,
            ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
        )
        changed_path = target / "src/goal_flow.py"
        changed_path.parent.mkdir(parents=True)
        changed_path.write_text("def goal_flow():\n    return 'ready'\n", encoding="utf-8")
        return changed_path

    def _verify_task(self, target: Path) -> dict[str, object]:
        return _run_governance_json(
            self,
            [
                "implementation",
                "verify",
                str(target),
                "--task",
                "TASK-001",
                "--command",
                "task-tests",
            ],
        )

    def test_review_evidence_binds_task_change_set_and_becomes_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _initialize_git(self, target)
            started = _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )

            self.assertTrue(started["baseline_capture"]["captured"])
            self.assertNotIn("inventory", started["baseline_capture"]["baseline"])
            self.assertGreater(started["baseline_capture"]["baseline"]["file_count"], 0)
            self.assertTrue((target / ".governance/implementation-change-baselines.json").is_file())

            changed_path = target / "src/goal_flow.py"
            changed_path.parent.mkdir(parents=True)
            changed_path.write_text("def goal_flow():\n    return 'ready'\n", encoding="utf-8")
            verification = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                ],
            )
            self.assertTrue(verification["command_passed"])

            plan = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
            )
            self.assertEqual("review_required", plan["status"])
            self.assertEqual(["src/goal_flow.py"], plan["change_set"]["changed_paths"])
            self.assertEqual("code-reviewer", plan["authority_skill"]["name"])
            self.assertTrue(plan["authority_skill"]["provenance_ready"])

            report = _write_review_report(target)
            preview = _run_governance_json(
                self,
                [
                    "implementation",
                    "review",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--report",
                    str(report),
                    "--reviewed",
                    "--check",
                ],
            )
            self.assertTrue(preview["review_ready"])
            self.assertEqual(["docs/development/05-code-review-evidence.json"], preview["would_update"])

            recorded = _run_governance_json(
                self,
                [
                    "implementation",
                    "review",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--report",
                    str(report),
                    "--reviewed",
                ],
            )
            self.assertEqual("current", recorded["status"])
            self.assertTrue(recorded["evidence_current"])
            self.assertTrue((target / "docs/development/05-code-review-evidence.json").is_file())

            changed_path.write_text("def goal_flow():\n    return 'changed-after-review'\n", encoding="utf-8")
            stale = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
            )
            self.assertEqual("stale", stale["status"])
            self.assertFalse(stale["evidence_current"])
            self.assertIn("implementation change set changed after code review", stale["stale_reasons"])

    def test_closeout_requires_current_code_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            _initialize_git(self, target)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            source = target / "src/goal_flow.py"
            source.parent.mkdir(parents=True)
            source.write_text("def goal_flow():\n    return 'ready'\n", encoding="utf-8")
            verification = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                ],
            )
            self.assertTrue(verification["command_passed"])

            blocked = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )
            blocking_codes = {item["code"] for item in blocked["blocking_requirements"]}
            self.assertIn("code_review_evidence_current", blocking_codes)
            self.assertFalse(blocked["closeout_ready"])
            self.assertEqual(
                ["bin/governance", "implementation", "review", ".", "--task", "TASK-001", "--json"],
                blocked["code_review_command"]["argv"],
            )

            report = _write_review_report(target)
            _run_governance_json(
                self,
                [
                    "implementation",
                    "review",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--report",
                    str(report),
                    "--reviewed",
                ],
            )
            ready = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )
            self.assertTrue(ready["closeout_ready"])
            self.assertTrue(ready["evidence_summary"]["code_review_evidence_current"])

            rerun = _run_governance_json(
                self,
                [
                    "implementation",
                    "verify",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--command",
                    "task-tests",
                ],
            )
            self.assertTrue(rerun["command_passed"])
            stale = _run_governance_json(
                self,
                ["implementation", "closeout", str(target), "--task", "TASK-001"],
            )
            self.assertFalse(stale["closeout_ready"])
            self.assertFalse(stale["evidence_summary"]["code_review_evidence_current"])
            self.assertIn(
                "implementation verification evidence changed after code review",
                stale["code_review"]["stale_reasons"],
            )

    def test_review_rejects_tampered_baseline_content_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            self._start_with_change(target)
            self.assertTrue(self._verify_task(target)["command_passed"])
            baseline_path = target / ".governance/implementation-change-baselines.json"
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline["baselines"][0]["captured_at"] = "2026-07-20T00:00:00+00:00"
            baseline["baselines"][0]["inventory"]["files"][0]["size"] += 1
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

            blocked = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
                expected_returncode=1,
            )

            self.assertFalse(blocked["evidence_current"])
            self.assertTrue(
                any("implementation baseline" in error and "mismatch" in error for error in blocked["errors"])
            )

    def test_review_rejects_tampered_recorded_report_content_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            self._start_with_change(target)
            self.assertTrue(self._verify_task(target)["command_passed"])
            report = _write_review_report(target)
            recorded = _run_governance_json(
                self,
                [
                    "implementation",
                    "review",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--report",
                    str(report),
                    "--reviewed",
                ],
            )
            self.assertTrue(recorded["evidence_current"])
            evidence_path = target / "docs/development/05-code-review-evidence.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["reviews"][0]["report"]["summary"] = "Tampered after recording."
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

            blocked = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
                expected_returncode=1,
            )

            self.assertFalse(blocked["evidence_current"])
            self.assertTrue(
                any("code review evidence content ID mismatch" in error for error in blocked["errors"])
            )

    def test_review_report_finding_must_target_current_change_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            self._start_with_change(target)
            self.assertTrue(self._verify_task(target)["command_passed"])
            report = _write_review_report(
                target,
                findings=[
                    {
                        "id": "CR-001",
                        "severity": "low",
                        "status": "resolved",
                        "path": "src/unrelated.py",
                        "message": "The finding is outside this task's change set.",
                        "resolution": "No task-scoped resolution exists.",
                    }
                ],
            )

            blocked = _run_governance_json(
                self,
                [
                    "implementation",
                    "review",
                    str(target),
                    "--task",
                    "TASK-001",
                    "--report",
                    str(report),
                    "--reviewed",
                    "--check",
                ],
                expected_returncode=1,
            )

            self.assertFalse(blocked["review_ready"])
            self.assertIn(
                "code review finding path is outside the current task change set: src/unrelated.py",
                blocked["errors"],
            )

    def test_review_change_set_includes_deleted_tracked_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            obsolete = target / "src/obsolete.py"
            obsolete.parent.mkdir(parents=True)
            obsolete.write_text("OBSOLETE = True\n", encoding="utf-8")
            git_add = subprocess.run(
                ["git", "add", "src/obsolete.py"],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, git_add.returncode, git_add.stderr)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            obsolete.unlink()
            self.assertTrue(self._verify_task(target)["command_passed"])

            plan = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
            )

            self.assertEqual("review_required", plan["status"])
            deleted = next(
                change
                for change in plan["change_set"]["changes"]
                if change["path"] == "src/obsolete.py"
            )
            self.assertEqual("deleted", deleted["status"])

    def test_review_change_set_binds_executable_mode_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            script = target / "scripts/run-task"
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            script.chmod(0o644)
            _run_governance_json(
                self,
                ["implementation", "start", str(target), "--task", "TASK-001", "--apply"],
            )
            script.chmod(0o755)
            self.assertTrue(self._verify_task(target)["command_passed"])

            plan = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
            )

            changed = next(
                change
                for change in plan["change_set"]["changes"]
                if change["path"] == "scripts/run-task"
            )
            self.assertEqual("100644", changed["before_mode"])
            self.assertEqual("100755", changed["after_mode"])

    def test_review_requires_present_and_passing_verification_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = _implementation_ready_target(self, tmp)
            self._start_with_change(target)

            missing = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
                expected_returncode=1,
            )
            self.assertIn("implementation review requires current verification evidence", missing["errors"])

            verification_log = target / "docs/development/03-verification-log.md"
            verification_log.write_text(
                verification_log.read_text(encoding="utf-8").replace(
                    "| --- | --- | --- | --- | --- |\n",
                    "| --- | --- | --- | --- | --- |\n"
                    "| TASK-001 | task-tests | fail | 2026-07-20 | Local test failed. |\n",
                    1,
                ),
                encoding="utf-8",
            )
            failing = _run_governance_json(
                self,
                ["implementation", "review", str(target), "--task", "TASK-001"],
                expected_returncode=1,
            )
            self.assertIn(
                "implementation review requires every current verification result to pass",
                failing["errors"],
            )


if __name__ == "__main__":
    unittest.main()
