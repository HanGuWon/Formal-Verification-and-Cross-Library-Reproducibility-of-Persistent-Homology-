VENV ?= .venv-wsl
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip

.PHONY: all setup run report clean

all: setup run

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

run:
	PYTHONPATH=src $(PYTHON) scripts/run_conformance.py --include-nacl

report: run

clean:
	rm -rf artifacts
