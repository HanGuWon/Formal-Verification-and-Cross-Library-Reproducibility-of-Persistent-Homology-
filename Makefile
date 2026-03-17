VENV ?= .venv-wsl
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip

.PHONY: all setup run audit report clean

all: setup run audit

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

run:
	PYTHONPATH=src $(PYTHON) scripts/run_conformance.py --include-nacl

audit: run
	PYTHONPATH=src $(PYTHON) scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit

report: run

clean:
	rm -rf artifacts
