# PH-NORMALIZED-CONFORMANCE-002

## setup
- Generated at UTC: 2026-03-19T13:12:05.689605+00:00
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
| artifacts/cases/honeycomb_patch_2x2__floating__p2__h1__full.json | 45d9e33ca0c2ae00ed54aea98cf8b97dc0dc3392010e7d43ce80967e4f1a5baa |
| artifacts/cases/honeycomb_patch_2x2__floating__p2__h1__selected.json | b07ad29d6a2db5cc73be22427e671f53fc0e0cc5347112719ce6f46658b3ca0a |
| artifacts/cases/honeycomb_patch_2x2__floating__p2__h2__full.json | 652d6471a163b9fee918b27e293e52eb5502302c9b255684999bef8ad724ebee |
| artifacts/cases/honeycomb_patch_2x2__floating__p2__h2__selected.json | f2a49098d1b3b473d2fa2b61936c8c1892a4e483ee4022f8f2324d106c5130a1 |
| artifacts/cases/honeycomb_patch_2x2__floating__p3__h1__full.json | ef24b49c7560797ab7dfa9da7db7a32373e1885448850cb044a31a3dc828e1fc |
| artifacts/cases/honeycomb_patch_2x2__floating__p3__h1__selected.json | e3c56af98e096881aedaa2b97041e3684796f1ea62da637efbb82645ab1856e8 |
| artifacts/cases/honeycomb_patch_2x2__floating__p3__h2__full.json | d0d1e084c4793d9325f334eb9e4a9e345a4e17c99a62036223ee42f6c98ce536 |
| artifacts/cases/honeycomb_patch_2x2__floating__p3__h2__selected.json | 79318783bcd5bfb09c3dde2a92c8955c7ee58ce302b73583f865aca67db31ad8 |
| artifacts/cases/honeycomb_patch_2x2__quantized__p2__h1__full.json | 22320bf88485b695a3008997bec8cb4cf35ec610e56fe6717a85f1dbf2e6ade0 |
| ... | ... |

## pairwise agreement tables

| scope | comparison_mode | comparison_mode_label | pair | dimension | total_dimension_records | exact_count | different_count | exact_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_dimensions | distance_zero_semantic | distance_zero_semantic | gudhi__dionysus | all | 480 | 460 | 20 | 0.9583333333333334 |
| all_dimensions | distance_zero_semantic | distance_zero_semantic | gudhi__ripser | all | 480 | 460 | 20 | 0.9583333333333334 |
| all_dimensions | distance_zero_semantic | distance_zero_semantic | ripser__dionysus | all | 480 | 480 | 0 | 1.0 |
| all_dimensions | drop_zero_length_intervals | B. drop_zero_length_intervals | gudhi__dionysus | all | 480 | 342 | 138 | 0.7125 |
| all_dimensions | drop_zero_length_intervals | B. drop_zero_length_intervals | gudhi__ripser | all | 480 | 342 | 138 | 0.7125 |
| all_dimensions | drop_zero_length_intervals | B. drop_zero_length_intervals | ripser__dionysus | all | 480 | 480 | 0 | 1.0 |
| all_dimensions | drop_zero_length_intervals_plus_float32_roundtrip | C. drop_zero_length_intervals + float32_roundtrip | gudhi__dionysus | all | 480 | 460 | 20 | 0.9583333333333334 |
| all_dimensions | drop_zero_length_intervals_plus_float32_roundtrip | C. drop_zero_length_intervals + float32_roundtrip | gudhi__ripser | all | 480 | 460 | 20 | 0.9583333333333334 |
| all_dimensions | drop_zero_length_intervals_plus_float32_roundtrip | C. drop_zero_length_intervals + float32_roundtrip | ripser__dionysus | all | 480 | 480 | 0 | 1.0 |
| all_dimensions | raw_exact | A. raw_exact | gudhi__dionysus | all | 480 | 204 | 276 | 0.425 |
| all_dimensions | raw_exact | A. raw_exact | gudhi__ripser | all | 480 | 204 | 276 | 0.425 |
| all_dimensions | raw_exact | A. raw_exact | ripser__dionysus | all | 480 | 480 | 0 | 1.0 |
| all_dimensions | threshold_truncation_harmonized | D. threshold_truncation_harmonized | gudhi__dionysus | all | 480 | 480 | 0 | 1.0 |
| all_dimensions | threshold_truncation_harmonized | D. threshold_truncation_harmonized | gudhi__ripser | all | 480 | 480 | 0 | 1.0 |
| all_dimensions | threshold_truncation_harmonized | D. threshold_truncation_harmonized | ripser__dionysus | all | 480 | 480 | 0 | 1.0 |

## ablation table

| pair | raw_exact_count | distance_zero_semantic_count | mode_b_count | mode_c_count | mode_d_count | closed_by_mode_b_vs_raw | closed_by_mode_c_vs_mode_b | closed_by_mode_d_vs_mode_c | remaining_after_mode_d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gudhi__ripser | 204 | 460 | 342 | 460 | 480 | 138 | 118 | 20 | 0 |
| gudhi__dionysus | 204 | 460 | 342 | 460 | 480 | 138 | 118 | 20 | 0 |
| ripser__dionysus | 480 | 480 | 480 | 480 | 480 | 0 | 0 | 0 | 0 |

## remaining failures

No pairwise disagreements remain after mode D (`threshold_truncation_harmonized`).

## reproducibility notes
- The normalization comparator reuses saved raw outputs from `artifacts/cases/` and audit labels from `artifacts/audit/`.
- Raw normalized interval tables are saved under `artifacts/normalized_conformance/normalized_tables/`.
- Machine-readable pairwise agreement and ablation tables are saved under `artifacts/normalized_conformance/summary/`.
- Input artifact hashes are saved under `artifacts/normalized_conformance/hashes/`.
