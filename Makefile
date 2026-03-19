VENV ?= .venv-wsl
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip

.PHONY: all setup run audit lowerstar-h0 perturb-stability normalized-conformance formalization-path-h0 report clean

all: setup run audit

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

run:
	PYTHONPATH=src $(PYTHON) scripts/run_conformance.py --include-nacl

audit: run
	PYTHONPATH=src $(PYTHON) scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit

lowerstar-h0: setup
	PYTHONPATH=src $(PYTHON) scripts/run_lowerstar_h0.py --output-dir artifacts/lowerstar_h0

perturb-stability: run
	PYTHONPATH=src $(PYTHON) scripts/run_perturb_stability.py --conformance-dir artifacts --output-dir artifacts/perturb_stability

normalized-conformance: audit
	PYTHONPATH=src $(PYTHON) scripts/run_normalized_conformance.py --conformance-dir artifacts --audit-dir artifacts/audit --output-dir artifacts/normalized_conformance

formalization-path-h0:
	PYTHONPATH=src $(PYTHON) scripts/generate_path_h0_formalization.py --lowerstar-dir artifacts/lowerstar_h0 --output-dir formalization
	PYTHONPATH=src $(PYTHON) formalization/reference_checker.py

report: run

clean:
	rm -rf artifacts
