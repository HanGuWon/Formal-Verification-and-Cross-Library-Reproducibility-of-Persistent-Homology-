# PH-NORMALIZED-CONFORMANCE-002

## setup
- Generated at UTC: 2026-03-19T13:07:33.638270+00:00
- Python: `3.12.3 (main, Mar  3 2026, 12:15:18) [GCC 13.3.0]`
- Platform: `Linux-5.15.167.4-microsoft-standard-WSL2-x86_64-with-glibc2.39`
- Key distributions:
  - `numpy==2.4.3`
  - `scipy==1.17.1`
  - `gudhi==3.11.0`
  - `ripser==0.6.12`
  - `dionysus==2.1.8`
- Exact command:
  - `PYTHONPATH=src python scripts/run_normalized_conformance.py --conformance-dir artifacts --audit-dir artifacts/audit --output-dir artifacts/normalized_conformance`

## input artifact hashes

| path | sha256 |
| --- | --- |
| artifacts/summary/benchmarks.json | cd635c29671dca690f4ccf5da94d080ce709e2577d5e8c676eaf6e6e2b2c732c |
| artifacts/audit/classification_table.json | f62e14c53d08776cfe8717aa114bf2b0fb4564ae1e5a798bcc6cff45804b9d1a |
| artifacts/audit/summary.json | 5b9e80191449139de1725514ae908631cd4cc0b01d206c8d881498819c5772cc |
| artifacts/cases/tfim_pbc_n4_g0p50__floating__p2__h1__selected.json | bdd12a01272bd58828cd6431749ed0fc3abe66cb15a62d7d01f40db245249f13 |
| artifacts/cases/triangular_patch_3x3__floating__p2__h1__selected.json | ed078b17225977526ff972869da6d8245f77a599e3dbdd458a6e911224b6e655 |

## pairwise agreement tables

| scope | comparison_mode | comparison_mode_label | pair | dimension | total_dimension_records | exact_count | different_count | exact_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_dimensions | distance_zero_semantic | distance_zero_semantic | gudhi__dionysus | all | 4 | 3 | 1 | 0.75 |
| all_dimensions | distance_zero_semantic | distance_zero_semantic | gudhi__ripser | all | 4 | 3 | 1 | 0.75 |
| all_dimensions | distance_zero_semantic | distance_zero_semantic | ripser__dionysus | all | 4 | 4 | 0 | 1.0 |
| all_dimensions | drop_zero_length_intervals | B. drop_zero_length_intervals | gudhi__dionysus | all | 4 | 0 | 4 | 0.0 |
| all_dimensions | drop_zero_length_intervals | B. drop_zero_length_intervals | gudhi__ripser | all | 4 | 0 | 4 | 0.0 |
| all_dimensions | drop_zero_length_intervals | B. drop_zero_length_intervals | ripser__dionysus | all | 4 | 4 | 0 | 1.0 |
| all_dimensions | drop_zero_length_intervals_plus_float32_roundtrip | C. drop_zero_length_intervals + float32_roundtrip | gudhi__dionysus | all | 4 | 3 | 1 | 0.75 |
| all_dimensions | drop_zero_length_intervals_plus_float32_roundtrip | C. drop_zero_length_intervals + float32_roundtrip | gudhi__ripser | all | 4 | 3 | 1 | 0.75 |
| all_dimensions | drop_zero_length_intervals_plus_float32_roundtrip | C. drop_zero_length_intervals + float32_roundtrip | ripser__dionysus | all | 4 | 4 | 0 | 1.0 |
| all_dimensions | raw_exact | A. raw_exact | gudhi__dionysus | all | 4 | 0 | 4 | 0.0 |
| all_dimensions | raw_exact | A. raw_exact | gudhi__ripser | all | 4 | 0 | 4 | 0.0 |
| all_dimensions | raw_exact | A. raw_exact | ripser__dionysus | all | 4 | 4 | 0 | 1.0 |
| all_dimensions | threshold_truncation_harmonized | D. threshold_truncation_harmonized | gudhi__dionysus | all | 4 | 4 | 0 | 1.0 |
| all_dimensions | threshold_truncation_harmonized | D. threshold_truncation_harmonized | gudhi__ripser | all | 4 | 4 | 0 | 1.0 |
| all_dimensions | threshold_truncation_harmonized | D. threshold_truncation_harmonized | ripser__dionysus | all | 4 | 4 | 0 | 1.0 |

## ablation table

| pair | raw_exact_count | distance_zero_semantic_count | mode_b_count | mode_c_count | mode_d_count | closed_by_mode_b_vs_raw | closed_by_mode_c_vs_mode_b | closed_by_mode_d_vs_mode_c | remaining_after_mode_d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gudhi__ripser | 0 | 3 | 0 | 3 | 4 | 0 | 3 | 1 | 0 |
| gudhi__dionysus | 0 | 3 | 0 | 3 | 4 | 0 | 3 | 1 | 0 |
| ripser__dionysus | 4 | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 |

## remaining failures

No pairwise disagreements remain after mode D (`threshold_truncation_harmonized`).

## reproducibility notes
- The normalization comparator reuses saved raw outputs from `artifacts/cases/` and audit labels from `artifacts/audit/`.
- Raw normalized interval tables are saved under `artifacts/normalized_conformance/normalized_tables/`.
- Machine-readable pairwise agreement and ablation tables are saved under `artifacts/normalized_conformance/summary/`.
- Input artifact hashes are saved under `artifacts/normalized_conformance/hashes/`.
