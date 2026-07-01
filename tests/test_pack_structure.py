import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_tree import _iter_workflow_pack_files
from scripts.verify_pack import verify_pack
from scripts.verify_governance import WORKFLOW_PACK_REQUIRED_PATHS


ROOT = Path(__file__).resolve().parents[1]


class PackStructureTest(unittest.TestCase):
    def test_verify_pack_script_json_reports_ok(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/verify_pack.py"), "--json"],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(str(ROOT.resolve()), payload["target"])
        self.assertEqual([], payload["errors"])
        self.assertEqual([], payload["findings"])

    def test_verify_pack_script_json_reports_missing_required_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            target.mkdir()

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/verify_pack.py"), str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(str(target.resolve()), payload["target"])
            self.assertIn("missing required pack file: README.md", payload["errors"])
            self.assertTrue(
                any(
                    finding["code"] == "pack_required_file_missing"
                    and finding["path"] == "README.md"
                    for finding in payload["findings"]
                )
            )

    def test_verify_pack_reports_missing_makefile_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\nverify-pack: test\n\tpython3 scripts/verify_pack.py\n\tpython3 scripts/check_env.py\n",
                    "\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_missing"
                    and finding.path == "Makefile"
                    and "verify-pack" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_makefile_target_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            makefile = target / "Makefile"
            makefile.write_text(
                makefile.read_text(encoding="utf-8").replace(
                    "\tpython3 scripts/check_env.py\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_makefile_target_recipe_missing"
                    and finding.path == "Makefile"
                    and "verify-pack" in finding.message
                    and "python3 scripts/check_env.py" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_readme_quick_start_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "bin/governance status /path/to/new-project\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_readme_quick_start_command_missing"
                    and finding.path == "README.md"
                    and "bin/governance status" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_readme_agent_automation_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "bin/governance verify /path/to/new-project --check --json\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_readme_agent_automation_command_missing"
                    and finding.path == "README.md"
                    and "verify /path/to/new-project --check --json" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_documented_verification_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "make verify-pack\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_verification_command_missing"
                    and finding.path == "AGENTS.md"
                    and "make verify-pack" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_purpose_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    " Do not treat it as a generated target project.",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_purpose_guardrail_missing"
                    and finding.path == "AGENTS.md"
                    and "generated target project" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_baseline_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    " Commit after each coherent change to scripts, skills, workflows, or templates so future workflow behavior is traceable.",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_baseline_guardrail_missing"
                    and finding.path == "AGENTS.md"
                    and "commit after each coherent change" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_editing_rule_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "- Put deterministic behavior in `scripts/`.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_editing_rule_missing"
                    and finding.path == "AGENTS.md"
                    and "deterministic behavior" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_required_reading_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "1. `workflows/00-overview.md`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_required_reading_missing"
                    and finding.path == "AGENTS.md"
                    and "workflows/00-overview.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_agents_verification_report_guardrail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            agents = target / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "Before claiming completion, report the verification commands and results.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_agents_verification_guardrail_missing"
                    and finding.path == "AGENTS.md"
                    and "verification commands and results" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_phase_workflow_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/01-empty-repo-initialization.md"
            text = workflow.read_text(encoding="utf-8")
            self.assertIn("## Verification", text)
            workflow.write_text(
                re.sub(r"\n## Verification\n.*?(?=\n## Stop Conditions\n)", "\n", text, flags=re.S),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_section_missing"
                    and finding.path == "workflows/01-empty-repo-initialization.md"
                    and "Verification" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_workflow_heading_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "# Phase 03: Product Structuring",
                    "# Phase 04: Product Structuring",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_phase_heading_mismatch"
                    and finding.path == "workflows/03-product-structuring.md"
                    and "Phase 03" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_workflow_title_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "# Phase 04: Design Derivation",
                    "# Phase 04: Backend Design",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_phase_title_mismatch"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "Design Derivation" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_workflow_section_order_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                "\n".join(
                    [
                        "# Phase 03: Product Structuring",
                        "",
                        "## Input",
                        "",
                        "## Skills",
                        "",
                        "- `structuring-product-requirements`",
                        "",
                        "## Procedure",
                        "",
                        "## Verification",
                        "",
                        "## Output",
                        "",
                        "## Stop Conditions",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_section_order_mismatch"
                    and finding.path == "workflows/03-product-structuring.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_empty_phase_workflow_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/03-product-structuring.md"
            workflow.write_text(
                "\n".join(
                    [
                        "# Phase 03: Product Structuring",
                        "",
                        "## Input",
                        "",
                        "- `docs/product/core/PRD.md`",
                        "",
                        "## Skills",
                        "",
                        "- `structuring-product-requirements`",
                        "",
                        "## Procedure",
                        "",
                        "1. Structure product requirements.",
                        "",
                        "## Output",
                        "",
                        "## Verification",
                        "",
                        "- Run governance verification.",
                        "",
                        "## Stop Conditions",
                        "",
                        "- Stop on product ambiguity.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_section_empty"
                    and finding.path == "workflows/03-product-structuring.md"
                    and "Output" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_local_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/00-overview.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8")
                + "\nBroken source-pack link: [Missing](missing-reference.md)\n",
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_local_markdown_link_missing"
                    and finding.path == "workflows/00-overview.md"
                    and "workflows/missing-reference.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_unknown_skill_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "`designing-api-contracts`",
                    "`missing-api-skill`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_skill_reference_missing"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "missing-api-skill" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_non_executable_runtime_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance"
            wrapper.chmod(0o644)

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_file_not_executable"
                    and finding.path == "bin/governance"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_wrapper_command_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance-verify"
            wrapper.write_text(
                wrapper.read_text(encoding="utf-8").replace(
                    'python3 "$ROOT_DIR/scripts/governance_cli.py" verify "$@"',
                    'python3 "$ROOT_DIR/scripts/governance_cli.py" status "$@"',
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_wrapper_command_mismatch"
                    and finding.path == "bin/governance-verify"
                    and "governance_cli.py\" verify" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_wrapper_missing_shell_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance"
            wrapper.write_text(
                wrapper.read_text(encoding="utf-8").replace("set -euo pipefail\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_wrapper_guard_missing"
                    and finding.path == "bin/governance"
                    and "set -euo pipefail" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_wrapper_missing_root_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            wrapper = target / "bin/governance"
            wrapper.write_text(
                wrapper.read_text(encoding="utf-8").replace(
                    'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n',
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_wrapper_root_missing"
                    and finding.path == "bin/governance"
                    and "ROOT_DIR" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_invalid_workflow_pack_file_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/product/core/PRD.md"
            template.write_bytes(b"\xff")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_file_invalid_encoding"
                    and finding.path == "templates/docs/product/core/PRD.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_runtime_python_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            script.write_text("def broken(:\n    pass\n", encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_runtime_python_syntax_invalid"
                    and finding.path == "scripts/governance_cli.py"
                    and "invalid Python syntax" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_governance_cli_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            original = 'status = sub.add_parser("status", help="Show target governance workflow state.")'
            replacement = 'status = sub.add_parser("state", help="Show target governance workflow state.")'
            text = script.read_text(encoding="utf-8")
            self.assertIn(original, text)
            script.write_text(text.replace(original, replacement, 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_governance_cli_command_missing"
                    and finding.path == "scripts/governance_cli.py"
                    and "status" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_missing_governance_cli_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            script = target / "scripts/governance_cli.py"
            original = 'runtime_refresh = runtime_sub.add_parser(\n        "refresh",'
            replacement = 'runtime_refresh = runtime_sub.add_parser(\n        "repair",'
            text = script.read_text(encoding="utf-8")
            self.assertIn(original, text)
            script.write_text(text.replace(original, replacement, 1), encoding="utf-8")

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_governance_cli_subcommand_missing"
                    and finding.path == "scripts/governance_cli.py"
                    and "runtime" in finding.message
                    and "refresh" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_workflow_order_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "3. `workflows/03-product-structuring.md`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_workflow_order_mismatch"
                    and finding.path == "README.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_package_layout_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "├── references/   # supporting methods and practice references\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_package_layout_missing_directory"
                    and finding.path == "README.md"
                    and "references/" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_package_layout_stale_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "├── skills/       # agent skills used by the workflow\n",
                    "├── skills/       # agent skills used by the workflow\n├── plugins/      # stale plugin experiments\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_package_layout_stale_directory"
                    and finding.path == "README.md"
                    and "plugins/" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_overview_phase_map_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "| 03 | Product structuring | `structuring-product-requirements` |\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_map_mismatch"
                    and finding.path == "workflows/00-overview.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_overview_phase_map_title_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "| 04 | Design derivation | `designing-system-architecture`, `designing-api-contracts` |\n",
                    "| 04 | Backend design | `designing-system-architecture`, `designing-api-contracts` |\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_map_title_mismatch"
                    and finding.path == "workflows/00-overview.md"
                    and "04" in finding.message
                    and "Design Derivation" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_primary_skill_missing_from_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            workflow = target / "workflows/04-design-derivation.md"
            workflow.write_text(
                workflow.read_text(encoding="utf-8").replace(
                    "- API contract: `designing-api-contracts`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_primary_skill_missing"
                    and finding.path == "workflows/04-design-derivation.md"
                    and "designing-api-contracts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_phase_map_missing_primary_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "| 03 | Product structuring | `structuring-product-requirements` |\n",
                    "| 03 | Product structuring | |\n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_phase_map_primary_skill_missing"
                    and finding.path == "workflows/00-overview.md"
                    and "03" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_router_missing_phase_primary_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            router = target / "skills/using-governance-workflow/SKILL.md"
            router.write_text(
                router.read_text(encoding="utf-8").replace(
                    "`designing-system-architecture`, then `designing-api-contracts`",
                    "`designing-system-architecture`",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_router_primary_skill_missing"
                    and finding.path == "skills/using-governance-workflow/SKILL.md"
                    and "designing-api-contracts" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_unrouted_reference_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            overview = target / "workflows/00-overview.md"
            overview.write_text(
                overview.read_text(encoding="utf-8").replace(
                    "Use `references/community-practices.md` to calibrate this workflow against recognized docs-as-code, architecture, API, ADR, quality, and security practices without treating any single framework as a rigid template.\n\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `references/community-practices.md`: external practice calibration.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_reference_unrouted"
                    and finding.path == "references/community-practices.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_reference_index_missing_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `references/backend-design-checklist.md`: backend and data-design completion checklist.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_reference_index_missing"
                    and finding.path == "README.md"
                    and "references/backend-design-checklist.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_skill_index_missing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `skills/designing-data-models/SKILL.md`: persistence and lifecycle design.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_skill_index_missing"
                    and finding.path == "README.md"
                    and "skills/designing-data-models/SKILL.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_readme_index_entry_missing_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `skills/designing-data-models/SKILL.md`: persistence and lifecycle design.\n",
                    "- `skills/designing-data-models/SKILL.md`:   \n",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_index_entry_description_missing"
                    and finding.path == "README.md"
                    and "Skill Files" in finding.message
                    and "skills/designing-data-models/SKILL.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_unrouted_template_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `templates/docs/decisions/ADR-template.md`: ADR shape for architecture decisions.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_unrouted"
                    and finding.path == "templates/docs/decisions/ADR-template.md"
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_template_index_missing_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            readme = target / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "- `templates/root/README.md`: generated target root README shape.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_index_missing"
                    and finding.path == "README.md"
                    and "templates/root/README.md" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/decisions/ADR-template.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace("- Related modules: TBD\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/decisions/ADR-template.md"
                    and "- Related modules: TBD" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_template_section_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/decisions/ADR-template.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace("## References\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_section_missing"
                    and finding.path == "templates/docs/decisions/ADR-template.md"
                    and "References" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_task_handoff_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/agent-workflow/task-handoff.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Verification commands pass and output is recorded.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/agent-workflow/task-handoff.md"
                    and "Verification commands pass" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_verification_log_template_section_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/development/03-verification-log.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace("## Verification Runs\n", "", 1),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_section_missing"
                    and finding.path == "templates/docs/development/03-verification-log.md"
                    and "Verification Runs" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_task_board_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/development/02-task-board.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "Done tasks must link Verification to local Markdown evidence.",
                    "Done tasks can use any verification note.",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/development/02-task-board.md"
                    and "Done tasks must link Verification" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_acceptance_matrix_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/tests/02-acceptance-matrix.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| Acceptance | Design | API | Test |",
                    "| Acceptance | Design | Test |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/tests/02-acceptance-matrix.md"
                    and "| Acceptance | Design | API | Test |" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_roadmap_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/development/01-roadmap.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "| ID | Status | Milestone |",
                    "| ID | Status |",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/development/01-roadmap.md"
                    and "| ID | Status | Milestone |" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_test_strategy_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/tests/01-strategy.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Integration tests cover API contract and persistence behavior.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/tests/01-strategy.md"
                    and "Integration tests cover API contract" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_system_context_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/architecture/01-system-context.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- External system, service, or explicit `none`\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/architecture/01-system-context.md"
                    and "External system" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_containers_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/architecture/02-containers.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "Map each container to owned data, shared data, and integration boundaries.",
                    "List data notes.",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/architecture/02-containers.md"
                    and "Map each container" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_quality_attributes_template_guardrail_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            template = target / "templates/docs/architecture/03-quality-attributes.md"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "- Logs, metrics, traces, audit events, and alerting expectations\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_template_guardrail_missing"
                    and finding.path == "templates/docs/architecture/03-quality-attributes.md"
                    and "Logs, metrics, traces" in finding.message
                    for finding in report.findings
                )
            )

    def test_verify_pack_reports_skill_heading_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            shutil.copytree(
                ROOT,
                target,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            skill = target / "skills/designing-api-contracts/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace(
                    "# Designing API Contracts",
                    "# Designing Backend Modules",
                    1,
                ),
                encoding="utf-8",
            )

            report = verify_pack(target)

            self.assertFalse(report.ok)
            self.assertTrue(
                any(
                    finding.code == "pack_skill_heading_mismatch"
                    and finding.path == "skills/designing-api-contracts/SKILL.md"
                    for finding in report.findings
                )
            )

    def test_makefile_verify_pack_runs_pack_verifier(self) -> None:
        text = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^\tpython3 scripts/verify_pack\.py$")

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
            "templates/docs/agent-workflow/task-handoff.md",
            "templates/docs/architecture/01-system-context.md",
            "templates/docs/architecture/02-containers.md",
            "templates/docs/architecture/03-quality-attributes.md",
            "templates/docs/decisions/ADR-template.md",
            "templates/docs/development/01-roadmap.md",
            "templates/docs/development/02-task-board.md",
            "templates/docs/development/03-verification-log.md",
            "templates/docs/tests/01-strategy.md",
            "templates/docs/tests/02-acceptance-matrix.md",
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

    def test_verifying_skill_prioritizes_structural_markdown_repairs(self) -> None:
        text = (ROOT / "skills/verifying-governance-docs/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Repair Order", text)
        self.assertIn("Fix document-integrity findings first", text)
        self.assertIn("markdown_not_file", text)
        self.assertIn("markdown_invalid_encoding", text)
        self.assertIn("rerun verification before interpreting downstream traceability findings", text)

    def test_verifier_workflow_pack_required_paths_match_bootstrap_snapshot(self) -> None:
        copied = [path.as_posix() for path in _iter_workflow_pack_files()]
        self.assertEqual(copied, list(WORKFLOW_PACK_REQUIRED_PATHS))


if __name__ == "__main__":
    unittest.main()
