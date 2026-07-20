import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_tree import bootstrap
from scripts.repository_git import (
    GIT_MAX_OUTPUT_CHARS,
    RepositoryRequest,
    _run,
    configure_repository,
    plan_repository,
)


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "governance_cli.py"


def _git(target: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(target), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


def _request(
    target: Path,
    *,
    default_branch: str = "main",
    author_name: str = "Project Author",
    author_email: str = "author@example.com",
    origin: str = "",
    reviewed: bool = True,
) -> RepositoryRequest:
    return RepositoryRequest(
        target=target,
        default_branch=default_branch,
        author_name=author_name,
        author_email=author_email,
        origin=origin,
        reviewed=reviewed,
    )


class RepositoryGitTest(unittest.TestCase):
    def test_check_plans_new_repository_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()

            result = plan_repository(_request(
                target,
                origin="https://github.com/example/project.git",
            ))

            self.assertTrue(result["ok"])
            self.assertTrue(result["check"])
            self.assertEqual("ready_to_apply", result["status"])
            self.assertEqual(
                ["initialize-repository", "set-default-branch", "set-local-author", "add-origin"],
                [action["id"] for action in result["planned_actions"]],
            )
            self.assertFalse((target / ".git").exists())
            self.assertFalse(result["commit_created"])
            self.assertFalse(result["push_attempted"])

    def test_apply_requires_reviewed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()

            result = configure_repository(_request(
                target,
                reviewed=False,
            ))

            self.assertFalse(result["ok"])
            self.assertEqual("blocked", result["status"])
            self.assertIn("review_required", [item["code"] for item in result["blockers"]])
            self.assertFalse((target / ".git").exists())

    def test_apply_initializes_repo_with_local_identity_and_no_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            (target / "README.md").write_text("# Project\n", encoding="utf-8")

            result = configure_repository(_request(
                target,
                origin="https://github.com/example/project.git",
            ))

            self.assertTrue(result["ok"])
            self.assertEqual("configured", result["status"])
            self.assertEqual("main", _git(target, "branch", "--show-current"))
            self.assertEqual("Project Author", _git(target, "config", "--local", "--get", "user.name"))
            self.assertEqual("author@example.com", _git(target, "config", "--local", "--get", "user.email"))
            self.assertEqual(
                "https://github.com/example/project.git",
                _git(target, "remote", "get-url", "origin"),
            )
            head = subprocess.run(
                ["git", "-C", str(target), "rev-parse", "--verify", "HEAD"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(0, head.returncode)
            self.assertFalse(result["commit_created"])
            self.assertFalse(result["push_attempted"])

    def test_apply_is_idempotent_when_configuration_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            request = _request(target)
            first = configure_repository(request)

            second = configure_repository(request)

            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertEqual("already_configured", second["status"])
            self.assertEqual([], second["applied_actions"])

    def test_existing_local_identity_conflict_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            _git(target, "init")
            _git(target, "config", "--local", "user.name", "Existing Author")
            _git(target, "config", "--local", "user.email", "existing@example.com")

            result = plan_repository(_request(
                target,
                author_name="Different Author",
                author_email="different@example.com",
            ))

            self.assertFalse(result["ok"])
            self.assertIn("local_author_conflict", [item["code"] for item in result["blockers"]])
            self.assertEqual("Existing Author", _git(target, "config", "--local", "--get", "user.name"))

    def test_target_inside_parent_repository_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "parent"
            target = parent / "child"
            target.mkdir(parents=True)
            _git(parent, "init")

            result = plan_repository(_request(target))

            self.assertFalse(result["ok"])
            self.assertIn("target_inside_parent_repository", [item["code"] for item in result["blockers"]])

    def test_invalid_inputs_are_blocked_before_git_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()

            result = configure_repository(_request(
                target,
                default_branch="bad branch",
                author_name="Project\nAuthor",
                author_email="not-an-email",
            ))

            codes = {item["code"] for item in result["blockers"]}
            self.assertFalse(result["ok"])
            self.assertTrue({"invalid_default_branch", "invalid_author_name", "invalid_author_email"} <= codes)
            self.assertFalse((target / ".git").exists())

    def test_http_origin_with_embedded_credentials_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()

            result = plan_repository(_request(
                target,
                origin="https://token@github.com/example/project.git",
            ))

            self.assertFalse(result["ok"])
            self.assertIn("origin_contains_credentials", [item["code"] for item in result["blockers"]])
            self.assertNotIn("token@github.com", json.dumps(result))

    def test_existing_origin_credentials_are_redacted_from_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            _git(target, "init")
            _git(target, "symbolic-ref", "HEAD", "refs/heads/main")
            _git(target, "config", "--local", "user.name", "Project Author")
            _git(target, "config", "--local", "user.email", "author@example.com")
            _git(target, "remote", "add", "origin", "https://token@github.com/example/project.git")

            result = plan_repository(_request(target))

            self.assertTrue(result["ok"])
            self.assertEqual("<redacted-credential-url>", result["current"]["origin"])
            self.assertNotIn("token@github.com", json.dumps(result))

    def test_malformed_origin_is_blocked_without_parser_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()

            result = plan_repository(_request(target, origin="https://["))

            self.assertFalse(result["ok"])
            self.assertIn("invalid_origin", [item["code"] for item in result["blockers"]])

    def test_process_output_is_bounded(self) -> None:
        result = _run(
            [sys.executable, "-c", "import sys; print('o' * 70000); print('e' * 70000, file=sys.stderr)"],
            cwd=None,
        )

        self.assertEqual(0, result.returncode)
        self.assertLessEqual(len(result.stdout), GIT_MAX_OUTPUT_CHARS)
        self.assertLessEqual(len(result.stderr), GIT_MAX_OUTPUT_CHARS)

    def test_cli_exposes_repository_init_check_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            common = [
                sys.executable,
                str(CLI),
                "repository",
                "init",
                str(target),
                "--default-branch",
                "main",
                "--author-name",
                "Project Author",
                "--author-email",
                "author@example.com",
                "--reviewed",
                "--json",
            ]

            check = subprocess.run(
                [*common, "--check"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, check.returncode, check.stderr)
            self.assertEqual("ready_to_apply", json.loads(check.stdout)["status"])
            self.assertFalse((target / ".git").exists())

            apply = subprocess.run(common, text=True, capture_output=True, check=False)
            self.assertEqual(0, apply.returncode, apply.stderr)
            self.assertEqual("configured", json.loads(apply.stdout)["status"])
            self.assertEqual("Project Author", _git(target, "config", "--local", "--get", "user.name"))

    def test_generated_target_runtime_exposes_repository_init(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            bootstrap(target, product)

            result = subprocess.run(
                [
                    str(target / "bin/governance"),
                    "repository",
                    "init",
                    str(target),
                    "--default-branch",
                    "main",
                    "--author-name",
                    "Project Author",
                    "--author-email",
                    "author@example.com",
                    "--reviewed",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("configured", json.loads(result.stdout)["status"])
            self.assertTrue((target / "scripts/repository_git.py").is_file())
            self.assertEqual("Project Author", _git(target, "config", "--local", "--get", "user.name"))
            self.assertIn(
                "/docs-as-code-workflow-pack/",
                (target / ".gitignore").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
