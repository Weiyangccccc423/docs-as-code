from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import smoke_installable_cli


ROOT = Path(__file__).resolve().parents[1]


def _execution(argv: list[str], **overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "started": True,
        "argv": argv,
        "cwd": str(ROOT),
        "started_at": "2026-07-22T00:00:00.000000Z",
        "finished_at": "2026-07-22T00:00:00.010000Z",
        "duration_seconds": 0.01,
        "returncode": 0,
        "result": "pass",
        "timed_out": False,
        "timeout_seconds": 300.0,
        "stdout": "",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "output_redacted": False,
        "stdout_redaction_count": 0,
        "stderr_redaction_count": 0,
        "max_output_bytes_per_stream": 16 * 1024 * 1024,
        "output_safe": True,
    }
    result.update(overrides)
    return result


class InstallableCliSmokeTest(unittest.TestCase):
    def test_check_mode_reports_read_only_plan(self) -> None:
        execution = _execution(["/opt/uv", "--version"], stdout="uv 0.9.30\n")

        with mock.patch.object(
            smoke_installable_cli,
            "run_source_command",
            return_value=execution,
        ) as run:
            payload = smoke_installable_cli.run_installable_cli_smoke(
                check=True,
                uv_executable=Path("/opt/uv"),
            )

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["check"])
        self.assertFalse(payload["writes_state"])
        self.assertEqual("/opt/uv", payload["builder"]["executable"])
        self.assertEqual("uv 0.9.30", payload["builder"]["version"])
        self.assertEqual(
            [
                "build-wheel",
                "create-isolated-environment",
                "install-wheel",
                "verify-entry-points",
                "initialize-fresh-project",
                "verify-generated-target",
            ],
            [step["id"] for step in payload["planned_steps"]],
        )
        self.assertTrue(all(step["writes_state"] for step in payload["planned_steps"][:3]))
        run.assert_called_once()

    def test_missing_uv_returns_structured_no_write_repair_route(self) -> None:
        with mock.patch.object(smoke_installable_cli.shutil, "which", return_value=None), mock.patch.object(
            smoke_installable_cli,
            "run_source_command",
        ) as run:
            payload = smoke_installable_cli.run_installable_cli_smoke(check=True)

        self.assertFalse(payload["ok"])
        self.assertEqual("install_smoke_uv_unavailable", payload["error_code"])
        self.assertFalse(payload["writes_state"])
        self.assertEqual("manual-tool-install", payload["repair"]["kind"])
        self.assertIn("uv", payload["repair"]["tool"])
        self.assertIn("uv tool install", payload["repair"]["consumer_alternatives"][0])
        run.assert_not_called()

    def test_run_step_rejects_unsafe_or_invalid_json_output(self) -> None:
        unsafe = _execution(
            ["unsafe"],
            stdout='{"ok": true}',
            output_safe=False,
            stdout_truncated=True,
        )
        with mock.patch.object(smoke_installable_cli, "run_source_command", return_value=unsafe):
            with self.assertRaises(smoke_installable_cli.InstallSmokeError) as raised:
                smoke_installable_cli._run_step(
                    [],
                    "unsafe",
                    ["unsafe"],
                    cwd=ROOT,
                    env={},
                    parse_json=True,
                )
        self.assertEqual("unsafe", raised.exception.step["id"])
        self.assertFalse(raised.exception.step["output_safe"])

        invalid = _execution(["invalid"], stdout="not-json\n")
        with mock.patch.object(smoke_installable_cli, "run_source_command", return_value=invalid):
            with self.assertRaises(smoke_installable_cli.InstallSmokeError):
                smoke_installable_cli._run_step(
                    [],
                    "invalid",
                    ["invalid"],
                    cwd=ROOT,
                    env={},
                    parse_json=True,
                )

    def test_success_contract_requires_installed_and_generated_cli_evidence(self) -> None:
        evidence = {
            "version": "2.0.0",
            "help": True,
            "no_args_help": True,
            "help_command": True,
            "help_init": True,
            "alias": True,
            "init_check": True,
            "init_check_read_only": True,
            "init": True,
            "status": True,
            "status_from_nested": True,
            "directory_after_command": True,
            "next": True,
            "verify": True,
            "target_help": True,
            "target_help_command": True,
            "target_help_status": True,
            "target_status": True,
            "target_status_from_nested": True,
        }

        self.assertTrue(smoke_installable_cli._evidence_ok(evidence))
        for field in evidence:
            with self.subTest(field=field):
                incomplete = dict(evidence)
                incomplete[field] = False if field != "version" else ""
                self.assertFalse(smoke_installable_cli._evidence_ok(incomplete))

    def test_source_version_match_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("2.0.0\n", encoding="utf-8")

            self.assertTrue(smoke_installable_cli._version_matches_source("2.0.0", root=root))
            self.assertFalse(smoke_installable_cli._version_matches_source("2.0.1", root=root))

    def test_compacted_json_steps_keep_summary_and_digest(self) -> None:
        step: dict[str, object] = {
            "id": "json-step",
            "stdout": '{"ok": true}\n',
            "payload": {"ok": True, "check": True, "details": ["large"]},
        }

        smoke_installable_cli._compact_payloads([step])

        self.assertNotIn("payload", step)
        self.assertEqual({"ok": True, "check": True}, step["payload_summary"])
        self.assertEqual("", step["stdout"])
        self.assertTrue(step["stdout_compacted"])
        self.assertIn("payload_sha256", step)

    def test_uv_cache_defaults_to_writable_temporary_storage(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            cache = smoke_installable_cli._resolve_uv_cache_dir(None)
        self.assertEqual(Path(tempfile.gettempdir()) / "docs-as-code-uv-cache", cache)

        with mock.patch.dict(os.environ, {"UV_CACHE_DIR": "/env/uv-cache"}, clear=True):
            self.assertEqual(
                Path("/env/uv-cache"),
                smoke_installable_cli._resolve_uv_cache_dir(None),
            )
            self.assertEqual(
                Path("/explicit/uv-cache"),
                smoke_installable_cli._resolve_uv_cache_dir(Path("/explicit/uv-cache")),
            )

    def test_offline_build_dependency_failure_returns_approval_bound_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            context = smoke_installable_cli.InstallSmokeContext(
                uv=Path("/opt/uv"),
                uv_cache_dir=Path(tmp) / "uv-cache",
                env={},
                steps=[],
                check=False,
                keep=False,
                allow_network=False,
                workspace=workspace,
            )
            step = {
                "id": "build-wheel",
                "stderr": "dependency resolution failed because network was disabled",
            }
            error = smoke_installable_cli.InstallSmokeError("step failed: build-wheel", step=step)

            payload = smoke_installable_cli._failure_payload(context, error)

        self.assertFalse(payload["ok"])
        self.assertEqual("install_smoke_build_dependencies_unavailable", payload["error_code"])
        self.assertTrue(payload["writes_state"])
        self.assertEqual("approved-cache-prime", payload["repair"]["kind"])
        self.assertTrue(payload["repair"]["approval_required"])
        self.assertEqual(
            [
                sys.executable,
                "scripts/smoke_installable_cli.py",
                "--allow-network",
                "--uv-cache-dir",
                str(Path(tmp) / "uv-cache"),
                "--json",
            ],
            payload["repair"]["argv"],
        )

    def test_cli_json_failure_is_machine_readable(self) -> None:
        with mock.patch.object(smoke_installable_cli.shutil, "which", return_value=None):
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "result.json"
                returncode = smoke_installable_cli.main(["--check", "--json", "--output", str(output)])

                payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(1, returncode)
        self.assertFalse(payload["ok"])
        self.assertEqual("install_smoke_uv_unavailable", payload["error_code"])


if __name__ == "__main__":
    unittest.main()
