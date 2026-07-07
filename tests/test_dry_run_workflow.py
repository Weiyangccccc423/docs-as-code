import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRY_RUN = ROOT / "scripts" / "dry_run_workflow.py"


class DryRunWorkflowTest(unittest.TestCase):
    def test_dry_run_reaches_design_authoring_queues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "dry-target"
            result = subprocess.run(
                [
                    sys.executable,
                    str(DRY_RUN),
                    "--target",
                    str(target),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("", result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["target_retained"])
            self.assertEqual("design-derivation", payload["final_phase"])
            self.assertEqual("fresh-target-governance-dry-run", payload["workflow"])
            self.assertEqual(1, payload["api_candidate_count"])
            self.assertEqual(
                {
                    "api-authoring": 1,
                    "backend-authoring": 1,
                    "frontend-authoring": 1,
                    "test-strategy-authoring": 1,
                    "implementation-planning-authoring": 1,
                    "architecture-decisions-authoring": 1,
                },
                payload["authoring_task_counts"],
            )
            self.assertFalse(payload["implementation_gate"]["ok"])
            self.assertTrue(payload["implementation_gate"]["expected_blocked"])
            step_ids = {step["id"] for step in payload["steps"]}
            self.assertIn("product_structure", step_ids)
            self.assertIn("design_plan", step_ids)
            self.assertIn("implementation_advance_check", step_ids)
            self.assertTrue((target / "bin/governance").is_file())
            self.assertTrue((target / "docs/api/endpoints/01-endpoint-contract.md").is_file())


if __name__ == "__main__":
    unittest.main()
