import re
import unittest
from pathlib import Path

from scripts.bootstrap_tree import _iter_workflow_pack_files
from scripts.verify_governance import WORKFLOW_PACK_REQUIRED_PATHS


ROOT = Path(__file__).resolve().parents[1]


class PackStructureTest(unittest.TestCase):
    def test_required_workflow_pack_files_exist(self) -> None:
        required = [
            "README.md",
            "AGENTS.md",
            "Makefile",
            "workflows/00-overview.md",
            "workflows/01-empty-repo-initialization.md",
            "workflows/02-product-document-archiving.md",
            "workflows/03-product-structuring.md",
            "workflows/04-design-derivation.md",
            "workflows/05-verification-and-drift-control.md",
            "references/architecture-methods.md",
            "references/backend-design-checklist.md",
            "references/runtime-strategy.md",
            "templates/root/README.md",
            "templates/docs/product/core/PRD.md",
            "templates/docs/decisions/ADR-template.md",
        ]
        missing = [path for path in required if not (ROOT / path).exists()]
        self.assertEqual([], missing)

    def test_skills_have_valid_frontmatter(self) -> None:
        skill_dirs = [
            "using-governance-workflow",
            "initializing-governance-repo",
            "archiving-product-document",
            "structuring-product-requirements",
            "designing-system-architecture",
            "designing-api-contracts",
            "designing-backend-modules",
            "designing-data-models",
            "capturing-architecture-decisions",
            "verifying-governance-docs",
        ]
        for skill in skill_dirs:
            skill_file = ROOT / "skills" / skill / "SKILL.md"
            self.assertTrue(skill_file.exists(), skill)
            text = skill_file.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), skill)
            frontmatter = text.split("---", 2)[1].strip()
            self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(skill)}$", skill)
            self.assertRegex(frontmatter, r"(?m)^description:\s*Use when .+", skill)

    def test_verifier_workflow_pack_required_paths_match_bootstrap_snapshot(self) -> None:
        copied = [path.as_posix() for path in _iter_workflow_pack_files()]
        self.assertEqual(copied, list(WORKFLOW_PACK_REQUIRED_PATHS))


if __name__ == "__main__":
    unittest.main()
