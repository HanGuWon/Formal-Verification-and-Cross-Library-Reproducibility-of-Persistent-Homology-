# PH-LOWERSTAR-H0-001

## setup
- Generated at UTC: 2026-03-17T17:05:36.626348+00:00
- Python: `3.12.3 (main, Mar  3 2026, 12:15:18) [GCC 13.3.0]`
- Platform: `Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- Random seed: `0`
- Key distributions:
  - `numpy==2.4.3`
  - `scipy==1.17.1`
  - `gudhi==3.11.0`
  - `ripser==0.6.12`
  - `dionysus==2.1.8`

## synthetic signals
- Interval-multiset exact agreement: `2/2` benchmark(s).
- Float32-stable interval agreement: `2/2` benchmark(s).
- Persistent Betti-0 agreement: `2/2` benchmark(s).
- Theorem-style minima/merge match: `2/2` benchmark(s).

| benchmark_id | mode | signal_length | exact | float32_stable | betti0 | minima_births | merge_deaths |
| --- | --- | --- | --- | --- | --- | --- | --- |
| synthetic_single_basin_3__floating | floating | 3 | True | True | True | True | True |
| synthetic_single_basin_3__quantized | quantized | 3 | True | True | True | True | True |

## reproducibility
- Run the benchmark from WSL/Linux with `PYTHONPATH=src python scripts/run_lowerstar_h0.py`.
- Every signal is saved under `artifacts/lowerstar_h0/signals/` as `.npy`, `.csv`, and `.json`.
- Every encoded filtration is saved under `artifacts/lowerstar_h0/encoded_filtrations/`.
- Raw diagrams are saved under `artifacts/lowerstar_h0/diagrams/`.
- Betti summaries are saved under `artifacts/lowerstar_h0/betti_summaries/`.
- The theorem-supporting examples are saved under `artifacts/lowerstar_h0/theorem_examples/`.
