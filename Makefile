.PHONY: test dry-run verify-pack check-env

test:
	python3 -m unittest discover -s tests

dry-run:
	python3 scripts/dry_run_workflow.py --json

verify-pack: test
	python3 scripts/verify_pack.py
	python3 scripts/check_env.py

check-env:
	python3 scripts/check_env.py
