import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "governance_cli.py"


def _append_index(readme: Path, filename: str) -> None:
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n- `{filename}` - generated for test\n", encoding="utf-8")


def _append_product_meta_chapter(root: Path, filename: str) -> None:
    meta = root / "docs/product/core/product-meta.md"
    meta.write_text(meta.read_text(encoding="utf-8") + f"\n- [{filename}](../{filename})\n", encoding="utf-8")


class GovernanceCliTest(unittest.TestCase):
    def test_env_repair_writes_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "env",
                    "--target",
                    str(target),
                    "--repair",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            repair_plan = target / ".governance/env-repair.md"
            self.assertTrue(repair_plan.exists())
            self.assertIn("Environment Repair Plan", repair_plan.read_text(encoding="utf-8"))

    def test_env_json_reports_tools_and_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "env",
                    "--target",
                    str(target),
                    "--repair",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(str(target), payload["target"])
            self.assertIn("tools", payload)
            self.assertIn("system", payload)
            self.assertIn("package_manager", payload)
            self.assertIn("git", payload)
            self.assertIn("install_plan", payload)
            self.assertIn("needs_escalation", payload)
            self.assertIn("repairs", payload)
            self.assertTrue(any(tool["name"] == "python3" for tool in payload["tools"]))
            self.assertEqual(str(target / ".governance/env-repair.md"), payload["repair_plan"])

    def test_init_check_json_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--check",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual([], payload["conflicts"])
            self.assertIn("README.md", payload["would_write"])
            self.assertIn("docs/agent-workflow/workflow-pack/manifest.json", payload["would_write"])
            self.assertIn("docs/agent-workflow/workflow-pack/skills/using-governance-workflow/SKILL.md", payload["would_write"])
            self.assertFalse(target.exists())

    def test_init_json_reports_conflicts_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            readme = target / "README.md"
            readme.write_text("# Existing\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn({"path": "README.md", "reason": "generated file already exists"}, payload["conflicts"])
            self.assertEqual("# Existing\n", readme.read_text(encoding="utf-8"))
            self.assertFalse((target / "docs/README.md").exists())

    def test_init_force_json_allows_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            target.mkdir()
            product = base / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            (target / "README.md").write_text("# Existing\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--project-name",
                    "Forced Demo",
                    "--force",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual("initialized", payload["state"]["phase"])
            self.assertEqual("docs/agent-workflow/workflow-pack/manifest.json", payload["state"]["workflow_pack_manifest"])
            self.assertIn("# Forced Demo", (target / "README.md").read_text(encoding="utf-8"))
            self.assertTrue((target / "docs/README.md").exists())

    def test_init_verify_and_status_update_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n\n## Goal\n\nShip governed projects.\n", encoding="utf-8")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--profile",
                    "web-app",
                    "--project-name",
                    "Governed Demo",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state_path = target / ".governance/state.json"
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("initialized", state["phase"])
            self.assertEqual("web-app", state["profile"])
            self.assertEqual("Governed Demo", state["project_name"])
            self.assertEqual("product.md", Path(state["product_source"]).name)

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertTrue(state["last_verification"]["ok"])

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_result.returncode, status_result.stderr)
            self.assertIn("phase: initialized", status_result.stdout)
            self.assertIn("profile: web-app", status_result.stdout)

    def test_init_verify_and_status_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--profile",
                    "service",
                    "--project-name",
                    "JSON Demo",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            init_payload = json.loads(init_result.stdout)
            self.assertTrue(init_payload["ok"])
            self.assertEqual(str(target), init_payload["target"])
            self.assertEqual("initialized", init_payload["state"]["phase"])

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, verify_result.returncode, verify_result.stderr)
            verify_payload = json.loads(verify_result.stdout)
            self.assertTrue(verify_payload["ok"])
            self.assertEqual([], verify_payload["errors"])
            self.assertEqual(str(target), verify_payload["target"])

            status_result = subprocess.run(
                [sys.executable, str(CLI), "status", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_result.returncode, status_result.stderr)
            status_payload = json.loads(status_result.stdout)
            self.assertTrue(status_payload["ok"])
            self.assertEqual("service", status_payload["state"]["profile"])

    def test_verify_json_reports_structured_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "init",
                    "--target",
                    str(target),
                    "--product",
                    str(product),
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n", encoding="utf-8")

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, verify_result.returncode)
            payload = json.loads(verify_result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("findings", payload)
            self.assertIn(
                {
                    "code": "docs_readme_unindexed_file",
                    "severity": "error",
                    "path": "docs/product/01-goals.md",
                    "message": "docs/product/01-goals.md is not indexed in docs/product/README.md",
                },
                payload["findings"],
            )

    def test_gate_product_structuring_allows_ready_markdown_product(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, gate_result.returncode, gate_result.stderr)
            payload = json.loads(gate_result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual("product-structuring", payload["gate"])
            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertTrue(requirements["product_import_ready"]["ok"])

    def test_advance_product_structuring_updates_phase_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            advance = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, advance.returncode, advance.stderr)
            payload = json.loads(advance.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["advanced"])
            self.assertEqual("product-structuring", payload["state"]["phase"])
            self.assertEqual("initialized", payload["state"]["phase_history"][0]["from_phase"])
            self.assertEqual("product-structuring", payload["state"]["phase_history"][0]["gate"])

    def test_advance_failed_gate_does_not_update_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            advance = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, advance.returncode)
            payload = json.loads(advance.stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["advanced"])
            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("initialized", state["phase"])
            self.assertNotIn("phase_history", state)

    def test_gate_product_structuring_uses_manifest_after_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.docx"
            product.write_bytes(b"fake docx bytes")

            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            state = json.loads((target / ".governance/state.json").read_text(encoding="utf-8"))
            self.assertEqual("conversion_required", state["product_import_status"])

            (target / "docs/product/core/PRD.md").write_text("# Converted Product\n", encoding="utf-8")
            manifest_path = target / "docs/product/core/source/source-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["import"]["status"] = "ready_for_structuring"
            manifest["import"]["conversion_method"] = "manual-reviewed-markdown"
            manifest["import"]["can_derive_design"] = True
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            gate_result = subprocess.run(
                [sys.executable, str(CLI), "gate", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, gate_result.returncode, gate_result.stderr)
            payload = json.loads(gate_result.stdout)
            requirements = {item["code"]: item for item in payload["requirements"]}
            self.assertTrue(requirements["product_import_ready"]["ok"])

    def test_gate_design_derivation_requires_product_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            blocked = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, blocked.returncode)
            blocked_payload = json.loads(blocked.stdout)
            blocked_requirements = {item["code"]: item for item in blocked_payload["requirements"]}
            self.assertFalse(blocked_requirements["product_chapters_present"]["ok"])

            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")

            missing_acceptance = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_acceptance.returncode)
            missing_acceptance_requirements = {item["code"]: item for item in json.loads(missing_acceptance.stdout)["requirements"]}
            self.assertFalse(missing_acceptance_requirements["product_acceptance_chapter_present"]["ok"])

            (target / "docs/product/08-acceptance-criteria.md").write_text(
                "# Acceptance Criteria\n\nSource: [PRD](core/PRD.md).\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            allowed = subprocess.run(
                [sys.executable, str(CLI), "gate", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)
            self.assertTrue(json.loads(allowed.stdout)["ok"])

    def test_advance_design_derivation_records_previous_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            first = subprocess.run(
                [sys.executable, str(CLI), "advance", "product-structuring", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, first.returncode, first.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                "# Acceptance Criteria\n\nSource: [PRD](core/PRD.md).\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            second = subprocess.run(
                [sys.executable, str(CLI), "advance", "design-derivation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, second.returncode, second.stderr)
            payload = json.loads(second.stdout)
            self.assertEqual("design-derivation", payload["state"]["phase"])
            history = payload["state"]["phase_history"]
            self.assertEqual(2, len(history))
            self.assertEqual("product-structuring", history[1]["from_phase"])
            self.assertEqual("design-derivation", history[1]["phase"])

    def test_gate_implementation_requires_design_and_delivery_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                "# Acceptance Criteria\n\nSource: [PRD](core/PRD.md).\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            blocked = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, blocked.returncode)
            blocked_requirements = {item["code"]: item for item in json.loads(blocked.stdout)["requirements"]}
            self.assertFalse(blocked_requirements["architecture_docs_present"]["ok"])

            for domain, filename in [
                ("architecture", "01-context.md"),
                ("api", "00-conventions.md"),
                ("backend", "01-modules.md"),
                ("tests", "01-strategy.md"),
                ("development", "01-roadmap.md"),
            ]:
                path = target / "docs" / domain / filename
                path.write_text(f"# {domain}\n", encoding="utf-8")
                _append_index(target / "docs" / domain / "README.md", filename)

            missing_task = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, missing_task.returncode)
            missing_task_requirements = {item["code"]: item for item in json.loads(missing_task.stdout)["requirements"]}
            self.assertFalse(missing_task_requirements["task_board_ready_task_present"]["ok"])

            task_board = target / "docs/development/02-task-board.md"
            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/missing.md | docs/tests/01-strategy.md | make test |\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/development/README.md", "02-task-board.md")

            blocked_trace = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, blocked_trace.returncode)
            blocked_trace_payload = json.loads(blocked_trace.stdout)
            blocked_trace_requirements = {item["code"]: item for item in blocked_trace_payload["requirements"]}
            self.assertFalse(blocked_trace_requirements["verification_passed"]["ok"])
            self.assertFalse(blocked_trace_requirements["task_board_ready_task_present"]["ok"])
            self.assertIn(
                {
                    "code": "task_board_trace_reference_missing",
                    "severity": "error",
                    "path": "docs/development/02-task-board.md",
                    "message": "task board row TASK-001 references missing API target: docs/api/missing.md",
                },
                blocked_trace_payload["verification"]["findings"],
            )

            task_board.write_text(
                "# Task Board\n\n"
                "| ID | Status | Task | Product | Design | API | Acceptance | Verification |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
                "| TASK-001 | Ready | Implement goal flow | docs/product/01-goals.md | docs/architecture/01-context.md | docs/api/00-conventions.md | docs/tests/01-strategy.md | make test |\n",
                encoding="utf-8",
            )

            allowed = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, allowed.returncode, allowed.stderr)
            self.assertTrue(json.loads(allowed.stdout)["ok"])

    def test_scaffold_design_requires_design_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)

            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(1, scaffold.returncode)
            payload = json.loads(scaffold.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("design-derivation gate failed", payload["errors"])
            self.assertFalse((target / "docs/architecture/01-system-context.md").exists())

    def test_scaffold_design_writes_indexed_placeholders_and_blocks_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            product = Path(tmp) / "product.md"
            product.write_text("# Product\n", encoding="utf-8")
            init_result = subprocess.run(
                [sys.executable, str(CLI), "init", "--target", str(target), "--product", str(product), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, init_result.returncode, init_result.stderr)
            (target / "docs/product/01-goals.md").write_text("# Goals\n\nSource: [PRD](core/PRD.md).\n", encoding="utf-8")
            _append_index(target / "docs/product/README.md", "01-goals.md")
            _append_product_meta_chapter(target, "01-goals.md")
            (target / "docs/product/08-acceptance-criteria.md").write_text(
                "# Acceptance Criteria\n\nSource: [PRD](core/PRD.md).\n",
                encoding="utf-8",
            )
            _append_index(target / "docs/product/README.md", "08-acceptance-criteria.md")
            _append_product_meta_chapter(target, "08-acceptance-criteria.md")

            scaffold = subprocess.run(
                [sys.executable, str(CLI), "scaffold", "design", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, scaffold.returncode, scaffold.stderr)
            payload = json.loads(scaffold.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("docs/architecture/01-system-context.md", payload["created"])
            self.assertIn("docs/api/endpoints/README.md", payload["created"])
            self.assertTrue((target / "docs/backend/02-data-model.md").exists())
            self.assertIn("01-system-context.md", (target / "docs/architecture/README.md").read_text(encoding="utf-8"))
            self.assertIn("00-conventions.md", (target / "docs/api/README.md").read_text(encoding="utf-8"))
            self.assertNotIn("README.md", (target / "docs/api/endpoints/README.md").read_text(encoding="utf-8"))

            verify_result = subprocess.run(
                [sys.executable, str(CLI), "verify", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, verify_result.returncode)
            verify_payload = json.loads(verify_result.stdout)
            finding_codes = {item["code"] for item in verify_payload["findings"]}
            self.assertIn("governance_scaffold_placeholder", finding_codes)
            self.assertNotIn("docs_readme_unindexed_file", finding_codes)

            gate = subprocess.run(
                [sys.executable, str(CLI), "gate", "implementation", str(target), "--json"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, gate.returncode)
            requirements = {item["code"]: item for item in json.loads(gate.stdout)["requirements"]}
            self.assertFalse(requirements["verification_passed"]["ok"])


if __name__ == "__main__":
    unittest.main()
