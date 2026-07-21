import json
import tempfile
import unittest
from pathlib import Path

from tests.test_governance_cli import (
    _implementation_ready_target,
    _install_test_authority_skills,
    _run_governance_json,
    _write_design_review_report,
)


class DesignReviewReportTest(unittest.TestCase):
    def _review_args(self, target: Path, report: Path | None = None) -> list[str]:
        args = [
            "design",
            "review",
            str(target),
            "--track",
            "ui-interaction",
            "--work",
            "UI-INTERACTION-AUTHOR-001",
            "--result",
            "approved",
            "--reason",
            "Senior frontend review resolved every interaction decision against repository evidence.",
            "--reviewed",
            "--check",
        ]
        if report is not None:
            args.extend(["--report", str(report)])
        return args

    def _target(self, tmp: str) -> Path:
        target = _implementation_ready_target(self, tmp, advance_implementation=False)
        _install_test_authority_skills(target, ("senior-frontend",))
        return target

    def test_report_is_required_and_contract_is_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            payload = _run_governance_json(
                self,
                self._review_args(target),
                expected_returncode=1,
            )

            self.assertIn("--report is required", payload["errors"])
            contract = payload["report_contract"]
            self.assertEqual(1, contract["schema_version"])
            self.assertEqual(
                ".governance/design-review-reports/*.json",
                contract["path_policy"],
            )
            self.assertEqual(
                list(contract["required_decision_ids"]),
                [item["id"] for item in contract["decision_templates"]],
            )

    def test_report_path_and_file_safety_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            escaped = _run_governance_json(
                self,
                self._review_args(target, outside),
                expected_returncode=1,
            )
            self.assertIn("must be under .governance/design-review-reports/", "\n".join(escaped["errors"]))

            report = _write_design_review_report(
                target,
                track="ui-interaction",
                work_id="UI-INTERACTION-AUTHOR-001",
            )
            real_report = report.with_name("real.json")
            report.rename(real_report)
            report.symlink_to(real_report.name)
            symlinked = _run_governance_json(
                self,
                self._review_args(target, report),
                expected_returncode=1,
            )
            self.assertIn("regular non-symlink file", "\n".join(symlinked["errors"]))
            report.unlink()

            report.write_text("not-json\n", encoding="utf-8")
            malformed = _run_governance_json(
                self,
                self._review_args(target, report),
                expected_returncode=1,
            )
            self.assertIn("invalid JSON", "\n".join(malformed["errors"]))

            report.write_text(" " * 262_145, encoding="utf-8")
            oversized = _run_governance_json(
                self,
                self._review_args(target, report),
                expected_returncode=1,
            )
            self.assertIn("exceeds 262144 bytes", "\n".join(oversized["errors"]))

    def test_report_identity_and_decision_registry_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            report = _write_design_review_report(
                target,
                track="ui-interaction",
                work_id="UI-INTERACTION-AUTHOR-001",
            )
            original = json.loads(report.read_text(encoding="utf-8"))

            cases = (
                ("track", "architecture", "track must be ui-interaction"),
                ("work_id", "UI-INTERACTION-AUTHOR-999", "work_id must be UI-INTERACTION-AUTHOR-001"),
                ("acceptance_id", "A-999", "acceptance_id must be A-001"),
            )
            for field, value, expected in cases:
                mutated = dict(original)
                mutated[field] = value
                report.write_text(json.dumps(mutated) + "\n", encoding="utf-8")
                payload = _run_governance_json(
                    self,
                    self._review_args(target, report),
                    expected_returncode=1,
                )
                self.assertIn(expected, "\n".join(payload["errors"]))

            missing = dict(original)
            missing["decisions"] = original["decisions"][:-1]
            report.write_text(json.dumps(missing) + "\n", encoding="utf-8")
            missing_payload = _run_governance_json(
                self,
                self._review_args(target, report),
                expected_returncode=1,
            )
            self.assertIn("missing decision", "\n".join(missing_payload["errors"]))

            duplicate = dict(original)
            duplicate["decisions"] = [*original["decisions"], original["decisions"][0]]
            report.write_text(json.dumps(duplicate) + "\n", encoding="utf-8")
            duplicate_payload = _run_governance_json(
                self,
                self._review_args(target, report),
                expected_returncode=1,
            )
            self.assertIn("duplicate design decision", "\n".join(duplicate_payload["errors"]))

            unknown = dict(original)
            unknown["decisions"] = [dict(item) for item in original["decisions"]]
            unknown["decisions"][0]["id"] = "invented_decision"
            report.write_text(json.dumps(unknown) + "\n", encoding="utf-8")
            unknown_payload = _run_governance_json(
                self,
                self._review_args(target, report),
                expected_returncode=1,
            )
            self.assertIn("unknown decision", "\n".join(unknown_payload["errors"]))

    def test_report_evidence_and_findings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            report = _write_design_review_report(
                target,
                track="ui-interaction",
                work_id="UI-INTERACTION-AUTHOR-001",
            )
            original = json.loads(report.read_text(encoding="utf-8"))

            for evidence, expected in (
                (["docs/missing.md"], "evidence path is not a file"),
                (["../outside.md"], "evidence path is invalid"),
            ):
                mutated = json.loads(json.dumps(original))
                mutated["decisions"][0]["evidence"] = evidence
                report.write_text(json.dumps(mutated) + "\n", encoding="utf-8")
                payload = _run_governance_json(
                    self,
                    self._review_args(target, report),
                    expected_returncode=1,
                )
                self.assertIn(expected, "\n".join(payload["errors"]))

            finding = {
                "id": "DRF-001",
                "severity": "medium",
                "status": "open",
                "evidence": ["docs/product/core/PRD.md"],
                "message": "Interaction recovery behavior is not fully specified.",
                "resolution": "Resolve before authority signoff.",
            }
            for status, severity, expected in (
                ("open", "medium", "finding remains open"),
                ("accepted-risk", "high", "critical or high design review finding cannot be accepted"),
            ):
                mutated = json.loads(json.dumps(original))
                mutated["verdict"] = "approved-with-suggestions"
                mutated["findings"] = [{**finding, "status": status, "severity": severity}]
                report.write_text(json.dumps(mutated) + "\n", encoding="utf-8")
                payload = _run_governance_json(
                    self,
                    self._review_args(target, report),
                    expected_returncode=1,
                )
                self.assertIn(expected, "\n".join(payload["errors"]))

    def test_report_content_and_digest_are_bound_to_review_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = self._target(tmp)
            report = _write_design_review_report(
                target,
                track="ui-interaction",
                work_id="UI-INTERACTION-AUTHOR-001",
            )
            args = [item for item in self._review_args(target, report) if item != "--check"]
            recorded = _run_governance_json(self, args)
            authority_report = recorded["review"]["authority_report"]
            self.assertEqual(report.relative_to(target).as_posix(), authority_report["path"])
            self.assertRegex(authority_report["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual("approved", authority_report["content"]["verdict"])

            content = json.loads(report.read_text(encoding="utf-8"))
            content["summary"] = "Changed after the recorded authority review."
            report.write_text(json.dumps(content) + "\n", encoding="utf-8")
            plan = _run_governance_json(
                self,
                ["design", "ui-interaction-authoring", str(target)],
            )
            stale = plan["authoring_tasks"][0]["stale_design_review"]
            self.assertIn(
                "authority review report changed after design review",
                stale["stale_reasons"],
            )


if __name__ == "__main__":
    unittest.main()
