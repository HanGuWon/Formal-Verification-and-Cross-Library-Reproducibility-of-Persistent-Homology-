# Finite-Path Lower-Star H0 Formalization Package

This package is the theorem-sized core extracted from `PH-LOWERSTAR-H0-001`. It is restricted to:

- finite path graphs on vertices `0, 1, ..., n-1`
- `H0` only
- vertex filtration values given by a 1D signal `f(i)`
- edge filtration values `max(f(i), f(i+1))`
- the elder-rule tie break used by the saved reference events:
  smaller birth value first, then smaller birth index

It does **not** claim anything about unrestricted cubical complexes, higher homology, or general graphs.

## Theorem Target

For the saved path-H0 examples:

1. births of the nonzero intervals occur exactly at strict local minima
2. finite deaths of the nonzero intervals occur exactly at elder-rule merge heights
3. removing zero-length intervals leaves diagram distance zero

The formalization-oriented data lives in `formalization/spec/`, with one JSON spec per saved theorem example and an index at `formalization/spec/index.json`.

## Artifact Layout

- `formalization/spec/index.json`
  package metadata, theorem statements, proof obligations, and the list of example specs
- `formalization/spec/<benchmark_id>.json`
  one formalization spec per saved theorem example
- `formalization/reference_checker.py`
  re-derives the path-H0 reference semantics from the saved signals and checks the three theorem targets

Each spec entry traces back to the saved computational artifacts under `artifacts/lowerstar_h0/`:

- `signals/<benchmark_id>/signal.json`
- `signals/<benchmark_id>/manifest.json`
- `encoded_filtrations/<benchmark_id>/common_chain.json`
- `encoded_filtrations/<benchmark_id>/gudhi_cubical_encoding.json`
- `encoded_filtrations/<benchmark_id>/ripser_sparse_matrix.json`
- `encoded_filtrations/<benchmark_id>/dionysus_freudenthal.json`
- `encoded_filtrations/<benchmark_id>/reference_theorem_events.json`
- `theorem_examples/<benchmark_id>.json`
- `cases/<benchmark_id>.json`
- `betti_summaries/<benchmark_id>/betti0_summary.json`

All traced source artifacts are stored with relative paths and SHA-256 hashes in the spec JSON.

## Proof Obligations

The package is prepared for Lean or Coq, but neither toolchain is installed in this environment, so this repository only includes theorem statements and proof obligations:

1. Define the lower-star filtration on a finite path graph with vertex weights `f(i)` and edge weights `max(f(i), f(i+1))`.
2. Prove that the reference elder-rule merge algorithm computes the `H0` persistence multiset for that filtration.
3. Prove that nonzero births are exactly the strict local minima.
4. Prove that finite nonzero deaths are exactly the elder-rule merge heights with strictly younger birth.
5. Prove that zero-length intervals contribute zero bottleneck and Wasserstein cost because they match to the diagonal.

## Commands

Regenerate the spec package from the saved lower-star artifacts:

```bash
PYTHONPATH=src python scripts/generate_path_h0_formalization.py --lowerstar-dir artifacts/lowerstar_h0 --output-dir formalization
```

Run the reference checker from a single command:

```bash
PYTHONPATH=src python formalization/reference_checker.py
```

In the current workspace that means:

```bash
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology- && source .venv-wsl/bin/activate && PYTHONPATH=src python formalization/reference_checker.py"
```
