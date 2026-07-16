import unittest
from pathlib import Path
from unittest import mock

from scripts import stack_acceptance


class StackAcceptanceTest(unittest.TestCase):
    def test_default_policy_requires_python_and_node_but_not_rust(self) -> None:
        dry_run_payload = _dry_run_payload(rust_status="unavailable")

        with mock.patch.object(stack_acceptance, "run_dry_run", return_value=dry_run_payload) as run_dry_run:
            payload = stack_acceptance.run_stack_acceptance(
                target=Path("target"),
                product=Path("product.md"),
                keep=True,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual([], payload["blockers"])
        self.assertEqual(["python", "node"], payload["required_stacks"])
        self.assertEqual(["rust"], payload["optional_stacks"])
        self.assertTrue(payload["all_required_passed"])
        self.assertFalse(payload["strict_rust"])
        self.assertFalse(payload["strict_rust_passed"])
        self.assertEqual("unavailable", payload["stacks"]["rust"]["status"])
        run_dry_run.assert_called_once_with(
            target=Path("target"),
            product=Path("product.md"),
            keep=True,
        )

    def test_strict_rust_blocks_when_rust_did_not_pass(self) -> None:
        with mock.patch.object(
            stack_acceptance,
            "run_dry_run",
            return_value=_dry_run_payload(rust_status="unavailable"),
        ):
            payload = stack_acceptance.run_stack_acceptance(strict_rust=True)

        self.assertFalse(payload["ok"])
        self.assertTrue(payload["strict_rust"])
        self.assertEqual(["rust_stack_not_passed"], [item["code"] for item in payload["blockers"]])

    def test_required_stack_failure_is_derived_from_stack_status(self) -> None:
        dry_run_payload = _dry_run_payload(rust_status="passed")
        dry_run_payload["stack_acceptance"]["stacks"]["node"]["status"] = "failed"
        dry_run_payload["stack_acceptance"]["all_required_passed"] = True

        with mock.patch.object(stack_acceptance, "run_dry_run", return_value=dry_run_payload):
            payload = stack_acceptance.run_stack_acceptance()

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["all_required_passed"])
        self.assertEqual(["node_stack_not_passed"], [item["code"] for item in payload["blockers"]])

    def test_dry_run_failure_is_preserved_as_a_blocker(self) -> None:
        dry_run_payload = {
            "ok": False,
            "error": "environment repair check failed",
            "target": "/tmp/target",
            "target_retained": True,
            "failed_step": {"id": "env_repair_check"},
        }

        with mock.patch.object(stack_acceptance, "run_dry_run", return_value=dry_run_payload):
            payload = stack_acceptance.run_stack_acceptance()

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["all_available_passed"])
        self.assertEqual("environment repair check failed", payload["dry_run_error"])
        self.assertEqual({"id": "env_repair_check"}, payload["failed_step"])
        self.assertEqual("dry_run_failed", payload["blockers"][0]["code"])


def _dry_run_payload(*, rust_status: str) -> dict[str, object]:
    rust_passed = rust_status == "passed"
    return {
        "ok": True,
        "final_phase": "implementation",
        "target": "/tmp/target",
        "product": "/tmp/product.md",
        "workspace": "/tmp",
        "target_retained": False,
        "stack_acceptance": {
            "policy": "real_runtime_no_network_no_third_party_dependencies",
            "required_stacks": ["python", "node"],
            "optional_stacks": ["rust"],
            "all_required_passed": True,
            "all_available_passed": True,
            "strict_rust_passed": rust_passed,
            "stacks": {
                "python": {"status": "passed", "runtime_available": True},
                "node": {"status": "passed", "runtime_available": True},
                "rust": {"status": rust_status, "runtime_available": rust_passed},
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
