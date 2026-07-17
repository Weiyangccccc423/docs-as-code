import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.authority_skills import (
    _authority_install_action_is_executable,
    build_authority_skill_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/authority_skills.py"
DEFAULT_LOCK = ROOT / "references/authority-skills.lock.json"


def _tree_digest(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(skill_dir.rglob("*"), key=lambda item: item.relative_to(skill_dir).as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir).as_posix()
        file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(f"{rel}\0{file_digest}\n".encode("utf-8"))
    return digest.hexdigest()


def _lock_payload() -> dict[str, object]:
    return json.loads(DEFAULT_LOCK.read_text(encoding="utf-8"))


def _registered_skill(name: str, digest: str) -> dict[str, object]:
    return {
        "name": name,
        "source": {
            "kind": "github",
            "repo": "example/authority-skills",
            "path": f"skills/{name}",
            "ref": "0123456789abcdef0123456789abcdef01234567",
        },
        "integrity": {
            "algorithm": "sha256",
            "scope": "skill-tree",
            "digest": digest,
        },
        "trust": {
            "status": "approved",
            "approved_by": "workflow-pack-test",
            "approved_at": "2026-07-13",
            "license": "MIT",
            "review_evidence": "https://example.invalid/authority-skill-review",
        },
    }


def _unregistered_skill(name: str) -> dict[str, object]:
    return {
        "name": name,
        "source": {
            "kind": "unregistered",
            "reason": "Test fixture intentionally leaves source registration pending.",
        },
        "trust": {
            "status": "pending-source-review",
            "approved_by": "",
            "approved_at": "",
            "license": "",
            "review_evidence": "",
        },
    }


def _write_lock(path: Path, replacement: dict[str, object] | None = None) -> None:
    payload = _lock_payload()
    if replacement is not None:
        skills = payload["skills"]
        assert isinstance(skills, list)
        payload["skills"] = [replacement if item.get("name") == replacement["name"] else item for item in skills]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_fixture_lock(path: Path, source_root: Path) -> list[str]:
    payload = _lock_payload()
    names: list[str] = []
    for entry in payload["skills"]:
        name = entry["name"]
        names.append(name)
        skill_dir = source_root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Fixture authority skill\n---\n",
            encoding="utf-8",
        )
        entry["source"] = {
            "kind": "github",
            "repo": "example/authority-skills",
            "path": f"skills/{name}",
            "ref": "0123456789abcdef0123456789abcdef01234567",
        }
        entry["integrity"]["digest"] = _tree_digest(skill_dir)
        entry["trust"] = {
            "status": "approved",
            "approved_by": "workflow-pack-test",
            "approved_at": "2026-07-17",
            "license": "MIT",
            "review_evidence": "references/authority-skills-source-review.md",
        }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return names


def _write_fixture_installer(codex_home: Path) -> Path:
    installer = codex_home / "skills/.system/skill-installer/scripts/install-skill-from-github.py"
    installer.parent.mkdir(parents=True)
    installer.write_text(
        "import argparse\n"
        "import os\n"
        "import shutil\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--repo')\n"
        "parser.add_argument('--path')\n"
        "parser.add_argument('--ref')\n"
        "parser.add_argument('--name', required=True)\n"
        "args = parser.parse_args()\n"
        "source = Path(os.environ['AUTHORITY_FIXTURE_SOURCE']) / args.name\n"
        "destination = Path(os.environ['CODEX_HOME']) / 'skills' / args.name\n"
        "if args.name == os.environ.get('AUTHORITY_FIXTURE_FAIL_NAME'):\n"
        "    raise SystemExit(7)\n"
        "shutil.copytree(source, destination)\n"
        "if args.name == os.environ.get('AUTHORITY_FIXTURE_FAIL_AFTER_COPY_NAME'):\n"
        "    raise SystemExit(8)\n"
        "if args.name == os.environ.get('AUTHORITY_FIXTURE_DRIFT_NAME'):\n"
        "    (destination / 'SKILL.md').write_text('drifted\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return installer


def _authority_fixture_env(codex_home: Path, source_root: Path, **overrides: str) -> dict[str, str]:
    return {
        **os.environ,
        "CODEX_HOME": str(codex_home),
        "HOME": str(codex_home.parent / "home"),
        "AUTHORITY_FIXTURE_SOURCE": str(source_root),
        **overrides,
    }


class AuthoritySkillsTest(unittest.TestCase):
    def test_default_lock_registers_every_required_authority_skill_source(self) -> None:
        payload = build_authority_skill_inventory(skill_roots=[], include_default_skill_roots=False)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["required_skill_count"], payload["registered_source_skill_count"])
        self.assertEqual(0, payload["source_unregistered_skill_count"])
        self.assertEqual([], payload["source_unregistered_skills"])
        for entry in _lock_payload()["skills"]:
            self.assertEqual("github", entry["source"]["kind"])
            self.assertEqual("alirezarezvani/claude-skills", entry["source"]["repo"])
            self.assertRegex(entry["source"]["ref"], r"^[0-9a-f]{40}$")
            self.assertEqual("skill-tree", entry["integrity"]["scope"])
            self.assertRegex(entry["integrity"]["digest"], r"^[0-9a-f]{64}$")
            self.assertEqual("approved", entry["trust"]["status"])
            self.assertEqual("MIT", entry["trust"]["license"])
            self.assertEqual(
                "references/authority-skills-source-review.md",
                entry["trust"]["review_evidence"],
            )

    def test_inventory_collects_design_and_implementation_authority_skills(self) -> None:
        payload = build_authority_skill_inventory(skill_roots=[], include_default_skill_roots=False)

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["strict"])
        self.assertEqual("load_from_agent_environment_or_stop_before_guessing", payload["missing_policy"])
        self.assertEqual("agent-environment", payload["availability_scope"])
        self.assertGreaterEqual(payload["required_skill_count"], 19)
        self.assertEqual([], payload["available_skill_roots"])
        self.assertEqual(payload["required_skill_count"], payload["missing_skill_count"])
        self.assertEqual([], payload["available_skills"])
        self.assertTrue(payload["manifest"]["ok"])
        self.assertTrue(payload["manifest"]["aligned_with_routing"])
        self.assertEqual(str(DEFAULT_LOCK.resolve()), payload["manifest"]["path"])
        self.assertEqual(payload["required_skill_count"], payload["status_counts"]["missing"])

        skills = {skill["name"]: skill for skill in payload["skills"]}
        for name in (
            "senior-architect",
            "api-design-reviewer",
            "senior-backend",
            "database-designer",
            "database-schema-designer",
            "migration-architect",
            "senior-security",
            "ci-cd-pipeline-builder",
        ):
            self.assertIn(name, skills)
            self.assertEqual("authority-routing", skills[name]["type"])
            self.assertEqual("agent-environment", skills[name]["availability_scope"])
            self.assertEqual(
                "load_from_agent_environment_or_stop_before_guessing",
                skills[name]["missing_policy"],
            )
            self.assertFalse(skills[name]["available_in_agent_environment"])

        architect_sources = {
            (entry["phase"], entry.get("track"), entry["source"])
            for entry in skills["senior-architect"]["required_by"]
        }
        self.assertIn(("design-derivation", "architecture", "DESIGN_TRACKS"), architect_sources)

        fullstack_sources = {
            (entry["phase"], entry.get("track"), entry["source"])
            for entry in skills["senior-fullstack"]["required_by"]
        }
        self.assertIn(("implementation", "base", "BASE_SPECIALIST_SKILLS"), fullstack_sources)

        backend_sources = {
            (entry["phase"], entry.get("track"), entry["source"])
            for entry in skills["senior-backend"]["required_by"]
        }
        self.assertIn(("implementation", "conditional", "_task_specialist_skills"), backend_sources)

    def test_registered_skill_tree_is_current_then_drifted_when_bundled_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_dir = skill_root / "senior-architect"
            reference = skill_dir / "references" / "architecture.md"
            reference.parent.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: senior-architect\ndescription: Architecture review\n---\n",
                encoding="utf-8",
            )
            reference.write_text("approved architecture method\n", encoding="utf-8")
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _registered_skill("senior-architect", _tree_digest(skill_dir)))

            current = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
            )
            reference.write_text("locally modified architecture method\n", encoding="utf-8")
            drifted = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
            )

        current_skill = {skill["name"]: skill for skill in current["skills"]}["senior-architect"]
        drifted_skill = {skill["name"]: skill for skill in drifted["skills"]}["senior-architect"]
        self.assertEqual("current", current_skill["status"])
        self.assertTrue(current_skill["integrity_matches"])
        self.assertEqual("skill-tree", current_skill["integrity_scope"])
        self.assertEqual("drifted", drifted_skill["status"])
        self.assertFalse(drifted_skill["integrity_matches"])
        self.assertNotEqual(drifted_skill["expected_sha256"], drifted_skill["observed_sha256"])
        self.assertIn("senior-architect", drifted["drifted_skills"])

    def test_registered_skill_tree_includes_node_modules_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_dir = skill_root / "senior-architect"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: senior-architect\ndescription: Architecture review\n---\n",
                encoding="utf-8",
            )
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _registered_skill("senior-architect", _tree_digest(skill_dir)))
            dependency = skill_dir / "node_modules" / "dependency" / "index.js"
            dependency.parent.mkdir(parents=True)
            dependency.write_text("module.exports = 'unreviewed';\n", encoding="utf-8")

            payload = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
            )

        skill = {item["name"]: item for item in payload["skills"]}["senior-architect"]
        self.assertEqual("drifted", skill["status"])
        self.assertFalse(skill["integrity_matches"])

    def test_installed_skill_without_registered_source_is_source_unregistered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_dir = skill_root / "senior-architect"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: senior-architect\ndescription: Architecture review\n---\n",
                encoding="utf-8",
            )
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _unregistered_skill("senior-architect"))

            payload = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
                repair=True,
                check=True,
            )

        skill = {item["name"]: item for item in payload["skills"]}["senior-architect"]
        action = next(
            item for item in payload["repair_plan"]["actions"] if item["skill"] == "senior-architect"
        )
        self.assertTrue(payload["ok"])
        self.assertEqual("source-unregistered", skill["status"])
        self.assertFalse(skill["source_registered"])
        self.assertEqual("register-authority-skill-source", action["kind"])
        self.assertTrue(action["manual_required"])
        self.assertEqual([], action["argv"])

    def test_repair_check_plans_exact_registered_install_without_executing_installer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_root.mkdir()
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _registered_skill("senior-architect", "a" * 64))
            marker = base / "installer-ran"
            installer = base / "install-skill-from-github.py"
            installer.write_text(
                "from pathlib import Path\nPath(%r).write_text('ran', encoding='utf-8')\n" % str(marker),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--skill-installer",
                    str(installer),
                    "--skill-root",
                    str(skill_root),
                    "--no-default-skill-roots",
                    "--repair",
                    "--check",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", result.stderr)
        self.assertFalse(marker.exists())
        payload = json.loads(result.stdout)
        action = next(
            item for item in payload["repair_plan"]["actions"] if item["skill"] == "senior-architect"
        )
        self.assertTrue(payload["repair_plan"]["requested"])
        self.assertTrue(payload["repair_plan"]["check"])
        self.assertFalse(payload["repair_plan"]["writes_state"])
        self.assertFalse(payload["repair_plan"]["applied"])
        self.assertTrue(action["approval_required"])
        self.assertTrue(action["network_required"])
        self.assertTrue(action["writes_outside_repository"])
        self.assertEqual(
            [
                sys.executable,
                str(installer.resolve()),
                "--repo",
                "example/authority-skills",
                "--path",
                "skills/senior-architect",
                "--ref",
                "0123456789abcdef0123456789abcdef01234567",
                "--name",
                "senior-architect",
            ],
            action["argv"],
        )

    def test_repair_check_rejects_symbolic_link_skill_installer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_root.mkdir()
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _registered_skill("senior-architect", "a" * 64))
            installer = base / "real-installer.py"
            installer.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
            installer_link = base / "install-skill-from-github.py"
            installer_link.symlink_to(installer)

            payload = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
                repair=True,
                check=True,
                skill_installer_path=installer_link,
            )

        action = next(
            item for item in payload["repair_plan"]["actions"] if item["skill"] == "senior-architect"
        )
        self.assertFalse(payload["repair_plan"]["skill_installer_available"])
        self.assertTrue(action["manual_required"])
        self.assertEqual([], action["argv"])

    def test_repair_apply_installs_and_verifies_every_missing_registered_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / "codex"
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            names = _write_fixture_lock(lock, source_root)
            _write_fixture_installer(codex_home)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--repair",
                    "--apply",
                    "--approve-installs",
                    "--strict-provenance",
                    "--json",
                ],
                cwd=ROOT,
                env=_authority_fixture_env(codex_home, source_root),
                text=True,
                capture_output=True,
                check=False,
            )

            installed = sorted(path.name for path in (codex_home / "skills").iterdir() if path.name != ".system")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", result.stderr)
        payload = json.loads(result.stdout)
        execution = payload["repair_execution"]
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["provenance_ready"])
        self.assertEqual("completed", execution["status"])
        self.assertEqual(len(names), execution["attempted_count"])
        self.assertEqual(len(names), execution["verified_count"])
        self.assertEqual("", execution["failed_action_id"])
        self.assertFalse(execution["partial_write_observed"])
        self.assertEqual(sorted(names), installed)
        self.assertEqual([], payload["missing_skills"])
        self.assertEqual([], payload["drifted_skills"])

    def test_repair_apply_without_approval_executes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / "codex"
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            _write_fixture_lock(lock, source_root)
            _write_fixture_installer(codex_home)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--repair",
                    "--apply",
                    "--strict-provenance",
                    "--json",
                ],
                cwd=ROOT,
                env=_authority_fixture_env(codex_home, source_root),
                text=True,
                capture_output=True,
                check=False,
            )

            installed = [path for path in (codex_home / "skills").iterdir() if path.name != ".system"]

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual("", result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["strict_provenance"])
        self.assertEqual("approval_required", payload["repair_execution"]["status"])
        self.assertEqual(0, payload["repair_execution"]["attempted_count"])
        self.assertEqual([], installed)

    def test_repair_apply_stops_after_installer_failure_and_reports_partial_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / "codex"
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            names = _write_fixture_lock(lock, source_root)
            _write_fixture_installer(codex_home)
            fail_name = sorted(names)[1]

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--repair",
                    "--apply",
                    "--approve-installs",
                    "--json",
                ],
                cwd=ROOT,
                env=_authority_fixture_env(
                    codex_home,
                    source_root,
                    AUTHORITY_FIXTURE_FAIL_NAME=fail_name,
                ),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        execution = payload["repair_execution"]
        self.assertFalse(payload["ok"])
        self.assertEqual("failed", execution["status"])
        self.assertEqual(2, execution["attempted_count"])
        self.assertEqual(1, execution["verified_count"])
        self.assertEqual(f"authority-skill-install-{fail_name}", execution["failed_action_id"])
        self.assertTrue(execution["partial_write_observed"])
        self.assertFalse((codex_home / "skills" / sorted(names)[2]).exists())

    def test_repair_apply_stops_when_failed_installer_left_a_matching_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / "codex"
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            names = _write_fixture_lock(lock, source_root)
            _write_fixture_installer(codex_home)
            fail_name = sorted(names)[0]

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--repair",
                    "--apply",
                    "--approve-installs",
                    "--json",
                ],
                cwd=ROOT,
                env=_authority_fixture_env(
                    codex_home,
                    source_root,
                    AUTHORITY_FIXTURE_FAIL_AFTER_COPY_NAME=fail_name,
                ),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        execution = payload["repair_execution"]
        self.assertEqual("failed", execution["status"])
        self.assertEqual(1, execution["attempted_count"])
        self.assertEqual(0, execution["verified_count"])
        self.assertEqual(f"authority-skill-install-{fail_name}", execution["failed_action_id"])
        self.assertTrue(execution["partial_write_observed"])
        self.assertTrue(execution["manual_cleanup_required"])
        self.assertFalse(execution["actions"][0]["verified"])
        self.assertTrue(execution["actions"][0]["post_integrity_matches"])
        self.assertFalse((codex_home / "skills" / sorted(names)[1]).exists())

    def test_install_action_must_exactly_match_locked_source_and_installer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            installer = _write_fixture_installer(base / "codex")
            names = _write_fixture_lock(lock, source_root)
            payload = build_authority_skill_inventory(
                skill_roots=[],
                include_default_skill_roots=False,
                manifest_path=lock,
                repair=True,
                check=True,
                skill_installer_path=installer,
            )
            skill_name = sorted(names)[0]
            skill = next(item for item in payload["skills"] if item["name"] == skill_name)
            action = next(item for item in payload["repair_plan"]["actions"] if item["skill"] == skill_name)

            self.assertTrue(
                _authority_install_action_is_executable(
                    action,
                    skill=skill,
                    installer_path=installer,
                )
            )
            tampered_action = json.loads(json.dumps(action))
            tampered_action["argv"][-1] = "different-skill"
            self.assertFalse(
                _authority_install_action_is_executable(
                    tampered_action,
                    skill=skill,
                    installer_path=installer,
                )
            )

    def test_repair_apply_stops_when_installed_tree_does_not_match_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / "codex"
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            names = _write_fixture_lock(lock, source_root)
            _write_fixture_installer(codex_home)
            drift_name = sorted(names)[0]

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--repair",
                    "--apply",
                    "--approve-installs",
                    "--json",
                ],
                cwd=ROOT,
                env=_authority_fixture_env(
                    codex_home,
                    source_root,
                    AUTHORITY_FIXTURE_DRIFT_NAME=drift_name,
                ),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        execution = payload["repair_execution"]
        self.assertEqual("integrity_failed", execution["status"])
        self.assertEqual(1, execution["attempted_count"])
        self.assertEqual(0, execution["verified_count"])
        self.assertEqual(f"authority-skill-install-{drift_name}", execution["failed_action_id"])
        self.assertTrue(execution["manual_cleanup_required"])
        self.assertIn(drift_name, payload["drifted_skills"])
        self.assertFalse((codex_home / "skills" / sorted(names)[1]).exists())

    def test_repair_apply_refuses_all_actions_when_preexisting_skill_is_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex_home = base / "codex"
            source_root = base / "source"
            lock = base / "authority-skills.lock.json"
            names = _write_fixture_lock(lock, source_root)
            _write_fixture_installer(codex_home)
            drift_name = sorted(names)[0]
            drift_dir = codex_home / "skills" / drift_name
            drift_dir.mkdir()
            (drift_dir / "SKILL.md").write_text("preexisting drift\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--manifest",
                    str(lock),
                    "--repair",
                    "--apply",
                    "--approve-installs",
                    "--json",
                ],
                cwd=ROOT,
                env=_authority_fixture_env(codex_home, source_root),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        execution = payload["repair_execution"]
        self.assertEqual("blocked_unsupported_actions", execution["status"])
        self.assertEqual(0, execution["attempted_count"])
        self.assertIn(f"authority-skill-replace-{drift_name}", execution["blocked_action_ids"])
        self.assertFalse((codex_home / "skills" / sorted(names)[1]).exists())

    def test_repair_and_check_flags_must_be_paired_in_library_api(self) -> None:
        with self.assertRaisesRegex(ValueError, "repair and check must be used together"):
            build_authority_skill_inventory(
                skill_roots=[],
                include_default_skill_roots=False,
                manifest_path=DEFAULT_LOCK,
                repair=True,
                check=False,
            )

    def test_manifest_rejects_mutable_github_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "authority-skills.lock.json"
            registered = _registered_skill("senior-architect", "a" * 64)
            registered["source"]["ref"] = "main"
            _write_lock(lock, registered)

            payload = build_authority_skill_inventory(
                skill_roots=[],
                include_default_skill_roots=False,
                manifest_path=lock,
            )

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["manifest"]["ok"])
        self.assertTrue(any("immutable 40-character commit" in error for error in payload["manifest"]["errors"]))

    def test_manifest_rejects_skill_md_only_integrity_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "authority-skills.lock.json"
            registered = _registered_skill("senior-architect", "a" * 64)
            registered["integrity"]["scope"] = "skill-md"
            _write_lock(lock, registered)

            payload = build_authority_skill_inventory(
                skill_roots=[],
                include_default_skill_roots=False,
                manifest_path=lock,
            )

        self.assertFalse(payload["ok"])
        self.assertTrue(any("integrity.scope" in error for error in payload["manifest"]["errors"]))

    def test_manifest_rejects_symbolic_link_lock_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            lock = base / "authority-skills.lock.json"
            _write_lock(lock)
            lock_link = base / "linked-lock.json"
            lock_link.symlink_to(lock)

            payload = build_authority_skill_inventory(
                skill_roots=[],
                include_default_skill_roots=False,
                manifest_path=lock_link,
            )

        self.assertFalse(payload["ok"])
        self.assertTrue(any("symbolic link" in error for error in payload["manifest"]["errors"]))

    def test_manifest_rejects_unsafe_source_path_and_impossible_approval_date(self) -> None:
        cases = (
            ("source.path", lambda entry: entry["source"].__setitem__("path", "../skills/senior-architect")),
            ("trust.approved_at", lambda entry: entry["trust"].__setitem__("approved_at", "2026-02-31")),
        )
        for expected_error, mutate in cases:
            with self.subTest(expected_error=expected_error), tempfile.TemporaryDirectory() as tmp:
                lock = Path(tmp) / "authority-skills.lock.json"
                registered = _registered_skill("senior-architect", "a" * 64)
                mutate(registered)
                _write_lock(lock, registered)

                payload = build_authority_skill_inventory(
                    skill_roots=[],
                    include_default_skill_roots=False,
                    manifest_path=lock,
                )

            self.assertFalse(payload["ok"])
            self.assertTrue(any(expected_error in error for error in payload["manifest"]["errors"]))

    def test_registered_skill_tree_with_symbolic_link_is_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_dir = skill_root / "senior-architect"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: senior-architect\ndescription: Architecture review\n---\n",
                encoding="utf-8",
            )
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _registered_skill("senior-architect", _tree_digest(skill_dir)))
            outside = base / "outside.md"
            outside.write_text("untrusted content\n", encoding="utf-8")
            (skill_dir / "linked.md").symlink_to(outside)

            payload = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
            )

        skill = {item["name"]: item for item in payload["skills"]}["senior-architect"]
        self.assertEqual("drifted", skill["status"])
        self.assertIn("symbolic link", skill["integrity_error"])

    def test_duplicate_registered_skill_installations_are_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            roots = [base / "skills-one", base / "skills-two"]
            for root in roots:
                skill_dir = root / "senior-architect"
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(
                    "---\nname: senior-architect\ndescription: Architecture review\n---\n",
                    encoding="utf-8",
                )
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _registered_skill("senior-architect", _tree_digest(roots[0] / "senior-architect")))

            payload = build_authority_skill_inventory(
                skill_roots=roots,
                include_default_skill_roots=False,
                manifest_path=lock,
            )

        skill = {item["name"]: item for item in payload["skills"]}["senior-architect"]
        self.assertEqual("drifted", skill["status"])
        self.assertTrue(skill["installation_ambiguous"])
        self.assertEqual(2, len(skill["installation_candidates"]))
        self.assertIn("multiple installations", skill["integrity_error"])

    def test_provenance_strict_fails_for_unregistered_sources_even_when_skill_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            skill_root = base / "skills"
            skill_dir = skill_root / "senior-architect"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: senior-architect\ndescription: Architecture review\n---\n",
                encoding="utf-8",
            )
            lock = base / "authority-skills.lock.json"
            _write_lock(lock, _unregistered_skill("senior-architect"))

            payload = build_authority_skill_inventory(
                skill_roots=[skill_root],
                include_default_skill_roots=False,
                manifest_path=lock,
                strict_provenance=True,
            )

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["strict_provenance"])
        self.assertIn("senior-architect", payload["source_unregistered_skills"])
        self.assertTrue(any("provenance is not current" in error for error in payload["errors"]))

    def test_inventory_reports_available_skills_from_explicit_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "senior-architect"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: senior-architect\n---\n", encoding="utf-8")

            payload = build_authority_skill_inventory(skill_roots=[root], include_default_skill_roots=False)

        skills = {skill["name"]: skill for skill in payload["skills"]}
        self.assertTrue(payload["ok"])
        self.assertIn("senior-architect", payload["available_skills"])
        self.assertTrue(skills["senior-architect"]["available_in_agent_environment"])
        self.assertEqual(str(skill_dir.resolve() / "SKILL.md"), skills["senior-architect"]["skill_path"])
        self.assertIn(str(root.resolve()), payload["available_skill_roots"])

    def test_inventory_uses_skill_frontmatter_name_when_directory_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "pw"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                '---\nname: "playwright-pro"\ndescription: Playwright toolkit\n---\n',
                encoding="utf-8",
            )

            payload = build_authority_skill_inventory(skill_roots=[root], include_default_skill_roots=False)

        skills = {skill["name"]: skill for skill in payload["skills"]}
        self.assertTrue(payload["ok"])
        self.assertIn("playwright-pro", payload["available_skills"])
        self.assertTrue(skills["playwright-pro"]["available_in_agent_environment"])
        self.assertEqual(str(skill_dir.resolve() / "SKILL.md"), skills["playwright-pro"]["skill_path"])

    def test_strict_mode_fails_when_explicit_skill_root_is_missing_required_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--skill-root",
                    tmp,
                    "--no-default-skill-roots",
                    "--strict",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["strict"])
        self.assertIn("senior-architect", payload["missing_skills"])
        self.assertIn("load_from_agent_environment_or_stop_before_guessing", payload["errors"][0])

    def test_cli_json_default_is_non_strict_and_machine_readable(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json", "--no-default-skill-roots"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["strict"])
        self.assertEqual([], payload["errors"])
        self.assertIn("skills", payload)


if __name__ == "__main__":
    unittest.main()
