import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.source_process import run_source_command


class SourceProcessTest(unittest.TestCase):
    def test_passes_explicit_environment_to_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            environment = os.environ.copy()
            environment["SOURCE_PROCESS_TEST_VALUE"] = "expected-value"

            result = run_source_command(
                [
                    sys.executable,
                    "-c",
                    "import os; print(os.environ['SOURCE_PROCESS_TEST_VALUE'])",
                ],
                cwd=Path(tmp),
                env=environment,
                timeout_seconds=5,
            )

        self.assertEqual("pass", result["result"])
        self.assertEqual("expected-value\n", result["stdout"])
        self.assertTrue(result["output_safe"])

    def test_bounds_and_redacts_captured_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_source_command(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; "
                        "print('api_key=super-secret-value'); "
                        "print('x' * 2048, file=sys.stderr)"
                    ),
                ],
                cwd=Path(tmp),
                env=os.environ.copy(),
                timeout_seconds=5,
                max_output_bytes=128,
            )

        self.assertEqual("pass", result["result"])
        self.assertTrue(result["output_redacted"])
        self.assertIn("api_key=[REDACTED]", result["stdout"])
        self.assertTrue(result["stderr_truncated"])
        self.assertFalse(result["output_safe"])

    @unittest.skipUnless(os.name == "posix", "process-group verification requires POSIX")
    def test_timeout_terminates_the_spawned_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_source_command(
                [
                    sys.executable,
                    "-c",
                    (
                        "import subprocess, sys, time; "
                        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                        "print(child.pid, flush=True); "
                        "time.sleep(30)"
                    ),
                ],
                cwd=Path(tmp),
                env=os.environ.copy(),
                timeout_seconds=0.1,
                max_output_bytes=4096,
            )

        self.assertEqual("fail", result["result"])
        self.assertTrue(result["timed_out"])
        child_pid = int(str(result["stdout"]).strip())
        process_stat = Path(f"/proc/{child_pid}/stat")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if not process_stat.exists():
                break
            try:
                state = process_stat.read_text(encoding="utf-8").split()[2]
            except (OSError, IndexError):
                break
            if state == "Z":
                break
            time.sleep(0.02)
        else:
            self.fail(f"spawned child process {child_pid} survived source-command timeout")


if __name__ == "__main__":
    unittest.main()
