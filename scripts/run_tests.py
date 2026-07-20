from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO


MAX_WORKERS = 64
DEFAULT_MODULE_TIMEOUT_SECONDS = 900.0
MAX_MODULE_TIMEOUT_SECONDS = 86400.0
TIMEOUT_RETURN_CODE = 124
TEST_FILE_PATTERN = re.compile(r"^test_[A-Za-z0-9][A-Za-z0-9_]*\.py$")
TEST_MODULE_PATTERN = re.compile(r"^tests\.test_[A-Za-z0-9][A-Za-z0-9_]*$")
TEST_COUNT_PATTERN = re.compile(r"^Ran (?P<count>\d+) tests? in ", re.MULTILINE)


@dataclass(frozen=True)
class TestModuleResult:
    module: str
    returncode: int
    test_count: int
    elapsed_seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "module": self.module,
            "returncode": self.returncode,
            "test_count": self.test_count,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
        }


def default_worker_count() -> int:
    return max(1, min(4, os.cpu_count() or 1))


def discover_test_modules(root: Path) -> tuple[str, ...]:
    tests_dir = root.resolve() / "tests"
    if not tests_dir.is_dir():
        return ()
    return tuple(
        f"tests.{path.stem}"
        for path in sorted(tests_dir.iterdir(), key=lambda entry: entry.name)
        if path.is_file() and not path.is_symlink() and TEST_FILE_PATTERN.fullmatch(path.name)
    )


def _validate_worker_count(workers: int) -> None:
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")


def _validate_timeout_seconds(timeout_seconds: float) -> None:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0 < timeout_seconds <= MAX_MODULE_TIMEOUT_SECONDS
    ):
        raise ValueError(
            f"timeout_seconds must be between 0 and {MAX_MODULE_TIMEOUT_SECONDS:g}"
        )


def _validate_test_modules(root: Path, modules: Sequence[str]) -> None:
    if not root.is_dir():
        raise ValueError(f"test root must be an existing directory: {root}")
    if len(set(modules)) != len(modules):
        raise ValueError("test modules must not contain duplicates")

    discovered = set(discover_test_modules(root))
    for module in modules:
        if not isinstance(module, str) or TEST_MODULE_PATTERN.fullmatch(module) is None:
            raise ValueError(f"invalid test module: {module!r}")
        if module not in discovered:
            raise ValueError(f"test module is not discoverable under tests/: {module}")


def _validate_run_request(
    root: Path,
    modules: Sequence[str],
    workers: int,
    timeout_seconds: float,
) -> None:
    _validate_worker_count(workers)
    _validate_timeout_seconds(timeout_seconds)
    _validate_test_modules(root, modules)


def _test_count(stdout: str, stderr: str) -> int:
    matches = TEST_COUNT_PATTERN.findall(f"{stdout}\n{stderr}")
    return int(matches[-1]) if matches else 0


def _output_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _run_test_module(
    root: Path,
    module: str,
    timeout_seconds: float,
) -> TestModuleResult:
    environment = os.environ.copy()
    environment.pop("MAKEFLAGS", None)
    environment.pop("MAKELEVEL", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", module],
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.monotonic() - started
        stdout = _output_text(error.stdout)
        stderr = _output_text(error.stderr)
        if stderr and not stderr.endswith("\n"):
            stderr += "\n"
        stderr += f"test module exceeded {timeout_seconds:g} seconds\n"
        return TestModuleResult(
            module,
            TIMEOUT_RETURN_CODE,
            0,
            elapsed,
            stdout,
            stderr,
            timed_out=True,
        )
    except OSError as error:
        elapsed = time.monotonic() - started
        return TestModuleResult(module, 2, 0, elapsed, "", f"failed to start test module: {error}\n")

    elapsed = time.monotonic() - started
    return TestModuleResult(
        module=module,
        returncode=completed.returncode,
        test_count=_test_count(completed.stdout, completed.stderr),
        elapsed_seconds=elapsed,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_test_modules(
    root: Path,
    modules: Sequence[str],
    workers: int,
    timeout_seconds: float = DEFAULT_MODULE_TIMEOUT_SECONDS,
) -> list[TestModuleResult]:
    root = root.resolve()
    modules = tuple(modules)
    _validate_run_request(root, modules, workers, timeout_seconds)
    if not modules:
        return []

    with ThreadPoolExecutor(max_workers=min(workers, len(modules))) as executor:
        return list(
            executor.map(
                lambda module: _run_test_module(root, module, timeout_seconds),
                modules,
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run each source-pack unittest module in an isolated local subprocess."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=default_worker_count(),
        help="Maximum parallel test modules (default: min(4, CPU count)).",
    )
    parser.add_argument(
        "--module",
        action="append",
        dest="modules",
        help="Run one discovered tests.test_* module; repeat to select multiple modules.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_MODULE_TIMEOUT_SECONDS,
        help=(
            "Maximum seconds for each test module "
            f"(default: {DEFAULT_MODULE_TIMEOUT_SECONDS:g})."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable results.")
    return parser


def _write_preserved_output(stream: TextIO, output: str) -> None:
    if not output:
        return
    stream.write(output)
    if not output.endswith("\n"):
        stream.write("\n")


def _print_human(results: Sequence[TestModuleResult], elapsed_seconds: float) -> None:
    for result in results:
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(
            f"{status} {result.module} "
            f"({result.test_count} tests, {result.elapsed_seconds:.3f}s)"
        )
    for result in results:
        if result.returncode == 0:
            continue
        print(f"\n--- {result.module} stdout ---")
        _write_preserved_output(sys.stdout, result.stdout)
        print(f"--- {result.module} stderr ---", file=sys.stderr)
        _write_preserved_output(sys.stderr, result.stderr)
    print(
        f"Ran {sum(result.test_count for result in results)} tests "
        f"across {len(results)} modules in {elapsed_seconds:.3f}s"
    )


def _result_payload(
    root: Path,
    workers: int,
    timeout_seconds: float,
    results: Sequence[TestModuleResult],
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "ok": all(result.returncode == 0 for result in results),
        "root": str(root),
        "workers": workers,
        "module_timeout_seconds": timeout_seconds,
        "module_count": len(results),
        "test_count": sum(result.test_count for result in results),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "failed_modules": [
            result.module for result in results if result.returncode != 0
        ],
        "results": [result.to_dict() for result in results],
    }


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    modules = tuple(args.modules) if args.modules else discover_test_modules(root)
    if not modules:
        print("no tests/test_*.py modules were discovered", file=sys.stderr)
        return 2

    started = time.monotonic()
    try:
        results = run_test_modules(
            root,
            modules,
            args.workers,
            timeout_seconds=args.timeout,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    elapsed = time.monotonic() - started
    payload = _result_payload(root, args.workers, args.timeout, results, elapsed)

    if args.json:
        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_human(results, elapsed)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
