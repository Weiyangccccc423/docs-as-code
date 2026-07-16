.PHONY: test dry-run dry-run-golden stack-acceptance package artifact-smoke release-check authority-skills verify-pack check-env ci

test:
	python3 -m unittest discover -s tests

dry-run:
	python3 scripts/dry_run_workflow.py --json

dry-run-golden:
	python3 scripts/dry_run_workflow.py --product tests/fixtures/product-docs/field-service-ops.md --json

stack-acceptance:
	python3 scripts/stack_acceptance.py --json

package:
	python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json

artifact-smoke:
	python3 scripts/smoke_workflow_pack_artifact.py --json

release-check:
	python3 scripts/release_readiness.py --json

authority-skills:
	python3 scripts/authority_skills.py --json

verify-pack:
	python3 scripts/verify_pack.py
	python3 scripts/check_env.py

check-env:
	python3 scripts/check_env.py

ci: test verify-pack
