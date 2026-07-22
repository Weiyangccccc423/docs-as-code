from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from docs_as_code.cli import main
from docs_as_code.packaging import build_embedded_pack
from scripts.verify_pack import verify_pack
from scripts.verify_pack_manifest import verify_pack_manifest


ROOT = Path(__file__).resolve().parents[1]


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

    def test_init_dispatches_to_safe_consumer_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            product = target / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            with mock.patch("docs_as_code.cli._run_pack_command", return_value=0) as run:
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
