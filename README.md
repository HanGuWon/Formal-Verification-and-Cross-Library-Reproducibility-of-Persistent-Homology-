# Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-

Cross-library Vietoris-Rips conformance harness for GUDHI, Ripser.py, and Dionysus on condensed-matter distance matrices and deterministic crystalline point clouds.

## Reproduce

Run from WSL/Linux:

```bash
make all
```

The main entrypoint is:

```bash
PYTHONPATH=src .venv-wsl/bin/python scripts/run_conformance.py --include-nacl
```

Artifacts are written to `artifacts/`:

- `artifacts/inputs/`: raw point clouds and distance matrices
- `artifacts/cases/`: raw per-library outputs and comparison payloads
- `artifacts/canonical_tables/`: canonicalized interval tables
- `artifacts/summary/`: machine-readable summaries
- `artifacts/discrepancies/`: discrepancy reports and minimal failing case
- `artifacts/report.md`: top-level Markdown report
