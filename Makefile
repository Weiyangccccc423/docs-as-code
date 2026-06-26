.PHONY: test verify-pack check-env

test:
	python3 -m unittest discover -s tests

verify-pack: test
	python3 scripts/check_env.py

check-env:
	python3 scripts/check_env.py
