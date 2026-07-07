.PHONY: test dry-run package verify-pack check-env

test:
	python3 -m unittest discover -s tests

dry-run:
	python3 scripts/dry_run_workflow.py --json

package:
	python3 scripts/export_workflow_pack.py --output dist/docs-as-code-workflow-pack --archive dist/docs-as-code-workflow-pack.tar.gz --force --json

verify-pack: test
	python3 scripts/verify_pack.py
	python3 scripts/check_env.py

check-env:
	python3 scripts/check_env.py
