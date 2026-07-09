import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.authority_skills import build_authority_skill_inventory


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/authority_skills.py"


class AuthoritySkillsTest(unittest.TestCase):
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
