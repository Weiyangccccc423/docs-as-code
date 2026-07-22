from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from docs_as_code import cli
from docs_as_code.packaging import build_embedded_pack
from scripts.verify_pack import verify_pack
from scripts.verify_pack_manifest import verify_pack_manifest


ROOT = Path(__file__).resolve().parents[1]
main = cli.main


class DistributionCliTest(unittest.TestCase):
    def test_embedded_pack_has_verified_content_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            build_embedded_pack(ROOT, pack)

            manifest_report = verify_pack_manifest(pack)
            pack_report = verify_pack(pack)
            self.assertTrue(manifest_report.ok, manifest_report.errors)
            self.assertTrue(pack_report.ok, pack_report.errors)
            self.assertTrue((pack / "README.zh-CN.md").is_file())
            self.assertTrue((pack / "pyproject.toml").is_file())

    def test_source_checkout_prepares_verified_pack_without_writing_manifest(self) -> None:
        source_manifest = ROOT / "pack-manifest.json"
        self.assertFalse(source_manifest.exists())

        with cli._prepared_pack_root() as pack:
            self.assertNotEqual(ROOT, pack)
            self.assertTrue(verify_pack_manifest(pack).ok)
            self.assertTrue(verify_pack(pack).ok)

        self.assertFalse(source_manifest.exists())

    def test_non_source_pack_without_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            for marker in cli.PACK_MARKERS:
                path = pack / marker
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder\n", encoding="utf-8")

            with mock.patch.dict("os.environ", {"DOCS_AS_CODE_PACK_ROOT": str(pack)}):
                with self.assertRaisesRegex(RuntimeError, "workflow manifest is missing"):
                    with cli._prepared_pack_root():
                        self.fail("unmanifested non-source pack must not be accepted")

    def test_no_arguments_prints_top_level_help(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            returncode = main([])

        output = stdout.getvalue()
        self.assertEqual(0, returncode)
        self.assertIn("usage: dac", output)
        self.assertIn("init", output)
        self.assertIn("doctor", output)
        self.assertIn("status", output)
        self.assertIn("next", output)
        self.assertIn("verify", output)
        self.assertIn("upgrade", output)
        self.assertIn("dac help <command>", output)

    def test_help_command_prints_guided_quick_start(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            returncode = main(["help"])

        output = stdout.getvalue()
        self.assertEqual(0, returncode)
        self.assertIn("getting started:", output)
        self.assertIn("Put exactly one product document in the project root", output)
        self.assertIn("dac init --check", output)
        self.assertIn("read-only", output)
        self.assertIn("dac COMMAND --help", output)

    def test_help_init_explains_product_document_discovery(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            returncode = main(["help", "init"])

        output = stdout.getvalue()
        self.assertEqual(0, returncode)
        self.assertIn("usage: dac init", output)
        self.assertIn("project root", output)
        self.assertIn(".md", output)
        self.assertIn(".docx", output)
        self.assertIn(".pdf", output)
        self.assertIn("dac init /path/to/product.pdf", output)

    def test_every_operational_command_has_examples(self) -> None:
        for command in ("init", "doctor", "status", "next", "verify", "upgrade"):
            with self.subTest(command=command):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    returncode = main(["help", command])
                output = stdout.getvalue()
                self.assertEqual(0, returncode)
                self.assertIn(f"usage: dac {command}", output)
                self.assertIn("examples:", output)
                self.assertIn(f"dac {command}", output)

    def test_next_help_documents_explicit_apply_mode(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            returncode = main(["help", "next"])

        self.assertEqual(0, returncode)
        self.assertIn("--apply", stdout.getvalue())
        self.assertIn("without executing", stdout.getvalue())

    def test_init_dispatches_to_safe_consumer_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            product = target / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            preflight = cli.CommandResult(
                0,
                {
                    "ok": True,
                    "init_check": {
                        "product": {
                            "path": str(product),
                            "selection": "explicit",
                        }
                    },
                },
                "",
                "",
            )
            stdout = io.StringIO()
            with mock.patch("docs_as_code.cli._run_pack_json", return_value=preflight) as run, contextlib.redirect_stdout(
                stdout
            ):
                returncode = main(["-C", str(target), "init", "product.md", "--check", "--json"])

        self.assertEqual(0, returncode)
        argv = run.call_args.args[0]
        self.assertEqual("scripts/bootstrap_consumer_project.py", argv[0])
        self.assertIn("--auto-repair-env", argv)
        self.assertIn("--target", argv)
        self.assertIn(str(target.resolve()), argv)
        self.assertIn("--product", argv)
        self.assertIn(str(product.resolve()), argv)
        self.assertIn("--check", argv)
        self.assertIn("--json", argv)

    def test_human_init_output_reports_product_phase_and_next_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            product = target / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            payload = {
                "ok": True,
                "target": str(target),
                "check": False,
                "init": {
                    "product": {
                        "path": str(product),
                        "selection": "auto-discovered",
                    },
                    "state": {
                        "phase": "initialized",
                        "archived_product": "docs/product/core/source/product.md",
                    },
                },
            }
            stdout = io.StringIO()
            with mock.patch(
                "docs_as_code.cli._run_pack_json",
                side_effect=(
                    cli.CommandResult(
                        0,
                        {
                            "ok": True,
                            "init_check": {
                                "product": {
                                    "path": str(product),
                                    "selection": "auto-discovered",
                                }
                            },
                        },
                        "",
                        "",
                    ),
                    cli.CommandResult(0, payload, "", ""),
                ),
            ), contextlib.redirect_stdout(stdout):
                returncode = main(["-C", str(target), "init"])

        output = stdout.getvalue()
        self.assertEqual(0, returncode)
        self.assertIn(f"Initialized: {target}", output)
        self.assertIn("Product: product.md (auto-discovered)", output)
        self.assertIn("Phase: initialized", output)
        self.assertIn("Next: dac next", output)

    def test_init_without_product_stops_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            preflight = cli.CommandResult(
                0,
                {
                    "ok": True,
                    "target": str(target),
                    "check": True,
                    "init_check": {
                        "product": {
                            "path": "",
                            "selection": "none",
                            "candidates": [],
                        }
                    },
                },
                "",
                "",
            )
            stderr = io.StringIO()
            with mock.patch("docs_as_code.cli._run_pack_json", return_value=preflight) as run_json, mock.patch(
                "docs_as_code.cli._run_pack_command"
            ) as run_write, contextlib.redirect_stderr(stderr):
                returncode = main(["-C", str(target), "init"])

        self.assertEqual(1, returncode)
        self.assertEqual(1, run_json.call_count)
        run_write.assert_not_called()
        self.assertIn("exactly one product document", stderr.getvalue())
        self.assertIn("dac init PRODUCT", stderr.getvalue())

    def test_init_write_pins_preflight_product_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            product = target / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            preflight_payload = {
                "ok": True,
                "target": str(target),
                "init_check": {
                    "product": {
                        "path": str(product),
                        "selection": "auto-discovered",
                    }
                },
            }
            apply_payload = {
                "ok": True,
                "target": str(target),
                "init": {
                    "product": {
                        "path": str(product),
                        "selection": "explicit",
                    },
                    "state": {"phase": "initialized"},
                },
            }
            stdout = io.StringIO()
            with mock.patch(
                "docs_as_code.cli._run_pack_json",
                side_effect=(
                    cli.CommandResult(0, preflight_payload, "", ""),
                    cli.CommandResult(0, apply_payload, "", ""),
                ),
            ) as run, contextlib.redirect_stdout(stdout):
                returncode = main(["-C", str(target), "init", "--json"])

        self.assertEqual(0, returncode)
        self.assertEqual(2, run.call_count)
        apply_argv = run.call_args_list[1].args[0]
        self.assertIn("--product", apply_argv)
        self.assertIn(str(product.resolve()), apply_argv)
        output = json.loads(stdout.getvalue())
        self.assertEqual("auto-discovered", output["cli_preflight"]["product"]["selection"])
        self.assertEqual(str(product.resolve()), output["cli_preflight"]["product"]["path"])

    def test_human_status_and_next_outputs_are_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            runtime = target / "scripts/governance_cli.py"
            runtime.parent.mkdir()
            runtime.write_text("", encoding="utf-8")
            status_payload = {
                "ok": True,
                "state": {
                    "project_name": "Example",
                    "phase": "initialized",
                    "product_source": str(target / "product.md"),
                    "product_import_status": "ready_for_structuring",
                },
            }
            next_payload = {
                "ok": True,
                "phase": "initialized",
                "status": "action_ready",
                "selected_action": {
                    "id": "advance-product-structuring",
                    "description": "Enter product structuring.",
                    "writes_state": True,
                    "steps": [
                        {
                            "skills": [
                                "structuring-product-requirements",
                                "verifying-governance-docs",
                            ]
                        }
                    ],
                },
            }
            stdout = io.StringIO()
            with mock.patch(
                "docs_as_code.cli._run_python_json",
                side_effect=(
                    cli.CommandResult(0, status_payload, "", ""),
                    cli.CommandResult(0, next_payload, "", ""),
                ),
            ), contextlib.redirect_stdout(stdout):
                status_returncode = main(["-C", str(target), "status"])
                next_returncode = main(["-C", str(target), "next"])

        output = stdout.getvalue()
        self.assertEqual(0, status_returncode)
        self.assertEqual(0, next_returncode)
        self.assertIn("Project: Example", output)
        self.assertIn("Phase: initialized", output)
        self.assertIn("Next action: advance-product-structuring", output)
        self.assertIn("Enter product structuring.", output)
        self.assertIn("Skills: structuring-product-requirements, verifying-governance-docs", output)
        self.assertIn("Agent details: dac next --json", output)

    def test_next_apply_dispatches_to_snapshot_bound_executor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            runtime = target / "scripts/governance_cli.py"
            runtime.parent.mkdir()
            runtime.write_text("", encoding="utf-8")
            payload = {
                "ok": True,
                "status": "completed",
                "phase": "initialized",
                "selected_action": {"id": "advance-product-structuring", "writes_state": True},
                "snapshot_id": "a" * 64,
                "writes_state": True,
                "step_results": [{"passed": True}, {"passed": True}],
                "refresh": {"passed": True},
            }
            stdout = io.StringIO()
            with mock.patch(
                "docs_as_code.cli._run_pack_json",
                return_value=cli.CommandResult(0, payload, "", ""),
            ) as run, contextlib.redirect_stdout(stdout):
                returncode = main(["-C", str(target), "next", "--apply"])

        self.assertEqual(0, returncode)
        executor_argv = run.call_args.args[0]
        self.assertEqual("scripts/workflow_executor.py", executor_argv[0])
        self.assertIn("--target", executor_argv)
        self.assertIn(str(target.resolve()), executor_argv)
        self.assertIn("Workflow action applied.", stdout.getvalue())
        self.assertIn("Next: Run dac next", stdout.getvalue())

    def test_human_upgrade_output_summarizes_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            runtime = target / "scripts/governance_cli.py"
            runtime.parent.mkdir()
            runtime.write_text("", encoding="utf-8")
            payload = {
                "ok": True,
                "check": True,
                "target": str(target),
                "would_refresh": [f"scripts/file-{index}.py" for index in range(128)],
                "would_remove": ["scripts/obsolete.py"],
                "version_transition": {
                    "from_version": "2.0.0",
                    "to_version": "2.0.0",
                    "classification": "same",
                },
            }
            stdout = io.StringIO()
            with mock.patch(
                "docs_as_code.cli._run_pack_json",
                return_value=cli.CommandResult(0, payload, "", ""),
            ), contextlib.redirect_stdout(stdout):
                returncode = main(["-C", str(target), "upgrade", "--check"])

        output = stdout.getvalue()
        self.assertEqual(0, returncode)
        self.assertIn("Runtime upgrade check passed.", output)
        self.assertIn("Version: 2.0.0 -> 2.0.0 (same)", output)
        self.assertIn("Files to refresh: 128", output)
        self.assertIn("Files to remove: 1", output)
        self.assertIn("Run: dac upgrade", output)
        self.assertNotIn("scripts/file-0.py", output)

    def test_project_commands_use_target_local_governance_runtime(self) -> None:
        cases = {
            "status": ["status", "."],
            "next": ["workflow", "resume", "."],
            "verify": ["verify", "."],
        }
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            runtime = target / "scripts/governance_cli.py"
            runtime.parent.mkdir()
            runtime.write_text("", encoding="utf-8")
            for command, expected in cases.items():
                with self.subTest(command=command), mock.patch(
                    "docs_as_code.cli._run_python_script",
                    return_value=0,
                ) as run:
                    returncode = main(["-C", str(target), command, "--json"])
                    self.assertEqual(0, returncode)
                    self.assertEqual(runtime, run.call_args.args[0])
                    self.assertEqual([*expected, "--json"], run.call_args.args[1])
                    self.assertEqual(target.resolve(), run.call_args.kwargs["cwd"])

    def test_uninitialized_project_command_reports_recovery(self) -> None:
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(stderr):
            returncode = main(["-C", tmp, "next"])

        self.assertEqual(2, returncode)
        self.assertIn("not initialized", stderr.getvalue())
        self.assertIn("dac init", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
