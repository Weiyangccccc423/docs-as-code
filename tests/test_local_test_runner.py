import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run_tests import (
    _parse_mem_available_bytes,
    default_worker_count,
    discover_test_modules,
    run_test_modules,
)


ROOT = Path(__file__).resolve().parents[1]


class LocalTestRunnerTest(unittest.TestCase):
    def test_parses_linux_available_memory(self) -> None:
        self.assertEqual(
            2 * 1024**3,
            _parse_mem_available_bytes(
                "MemTotal:       8192000 kB\nMemAvailable:   2097152 kB\n"
            ),
        )
        self.assertIsNone(_parse_mem_available_bytes("MemTotal: 8192000 kB\n"))
        self.assertIsNone(_parse_mem_available_bytes("MemAvailable: many kB\n"))

    def test_auto_worker_count_is_bounded_by_cpu_and_available_memory(self) -> None:
        gibibyte = 1024**3
        cases = (
            (16, 10 * gibibyte, 8),
            (16, 2 * gibibyte, 2),
            (2, 10 * gibibyte, 2),
            (None, 10 * gibibyte, 1),
        )
        for cpu_count, available_memory, expected in cases:
            with self.subTest(cpu_count=cpu_count, available_memory=available_memory):
                with (
                    mock.patch("scripts.run_tests.os.cpu_count", return_value=cpu_count),
                    mock.patch(
                        "scripts.run_tests._available_memory_bytes",
                        return_value=available_memory,
                    ),
                ):
                    self.assertEqual(expected, default_worker_count())

    def test_auto_worker_count_uses_conservative_fallback_without_memory_signal(self) -> None:
        with (
            mock.patch("scripts.run_tests.os.cpu_count", return_value=16),
            mock.patch("scripts.run_tests._available_memory_bytes", return_value=None),
        ):
            self.assertEqual(4, default_worker_count())

    def test_discovers_sorted_test_modules_and_ignores_non_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_zeta.py").write_text("", encoding="utf-8")
            (tests_dir / "test_alpha.py").write_text("", encoding="utf-8")
            (tests_dir / "helper.py").write_text("", encoding="utf-8")
            (tests_dir / "test_nested").mkdir()

            modules = discover_test_modules(root)

        self.assertEqual(("tests.test_alpha", "tests.test_zeta"), modules)

    def test_runs_modules_in_isolated_subprocesses_and_preserves_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tests_dir / "test_pass.py").write_text(
                "import unittest\n\n"
                "class PassingTest(unittest.TestCase):\n"
                "    def test_one(self):\n"
                "        self.assertTrue(True)\n\n"
                "    def test_two(self):\n"
                "        self.assertEqual(2, 1 + 1)\n",
                encoding="utf-8",
            )
            (tests_dir / "test_fail.py").write_text(
                "import unittest\n\n"
                "class FailingTest(unittest.TestCase):\n"
                "    def test_failure_is_reported(self):\n"
                "        self.assertEqual('expected', 'actual')\n",
                encoding="utf-8",
            )

            results = run_test_modules(
                root,
                ("tests.test_pass", "tests.test_fail"),
                workers=2,
            )

        self.assertEqual(
            ["tests.test_pass", "tests.test_fail"],
            [result.module for result in results],
        )
        by_module = {result.module: result for result in results}
        self.assertEqual(0, by_module["tests.test_pass"].returncode)
        self.assertEqual(2, by_module["tests.test_pass"].test_count)
        self.assertEqual(1, by_module["tests.test_fail"].returncode)
        self.assertEqual(1, by_module["tests.test_fail"].test_count)
        self.assertIn("FAIL: test_failure_is_reported", by_module["tests.test_fail"].stderr)

    def test_clears_make_environment_and_disables_bytecode_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tests_dir / "test_environment.py").write_text(
                "import os\n"
                "import unittest\n\n"
                "class EnvironmentTest(unittest.TestCase):\n"
                "    def test_runner_environment(self):\n"
                "        self.assertNotIn('MAKEFLAGS', os.environ)\n"
                "        self.assertNotIn('MAKELEVEL', os.environ)\n"
                "        self.assertEqual('1', os.environ.get('PYTHONDONTWRITEBYTECODE'))\n",
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {"MAKEFLAGS": "--jobserver-auth=3,4", "MAKELEVEL": "1"},
            ):
                results = run_test_modules(root, ("tests.test_environment",), workers=1)

        self.assertEqual(0, results[0].returncode, results[0].stderr)
        self.assertFalse((tests_dir / "__pycache__").exists())

    def test_times_out_a_stalled_test_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "__init__.py").write_text("", encoding="utf-8")
            (tests_dir / "test_stalled.py").write_text(
                "import time\n"
                "import unittest\n\n"
                "class StalledTest(unittest.TestCase):\n"
                "    def test_stalls(self):\n"
                "        time.sleep(2)\n",
                encoding="utf-8",
            )

            results = run_test_modules(
                root,
                ("tests.test_stalled",),
                workers=1,
                timeout_seconds=0.05,
            )

        self.assertEqual(124, results[0].returncode)
        self.assertTrue(results[0].timed_out)
        self.assertIn("exceeded 0.05 seconds", results[0].stderr)

    def test_rejects_unlisted_or_invalid_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()

            with self.assertRaisesRegex(ValueError, "invalid test module"):
                run_test_modules(root, ("os",), workers=1)

            with self.assertRaisesRegex(ValueError, "workers must be between"):
                run_test_modules(root, ("tests.test_safe",), workers=0)

            with self.assertRaisesRegex(ValueError, "timeout_seconds must be between"):
                run_test_modules(
                    root,
                    ("tests.test_safe",),
                    workers=1,
                    timeout_seconds=0,
                )

    def test_cli_rejects_invalid_module_without_executing_it(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_tests.py"),
                "--module",
                "os",
                "--workers",
                "1",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("invalid test module", result.stderr)


if __name__ == "__main__":
    unittest.main()
