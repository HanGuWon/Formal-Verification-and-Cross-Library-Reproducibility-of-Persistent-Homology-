# PH-AUDIT-CONVENTIONS-001

Audited 276 disagreeing dimension records from 156 discrepancy cases.

Recompute everything from the repository root with:

```bash
make audit
```

The full audit command is `PYTHONPATH=src python scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit`.

| classification | count |
| --- | --- |
| convention mismatch | 196 |
| genuine coefficient dependence | 0 |
| boundary-condition dependence | 0 |
| floating-point artifact | 80 |
| unresolved | 0 |

## convention mismatch

196 disagreeing dimension record(s) fall in this class. These are disagreements attributable to library conventions around zero-length bars, near-cutoff ties, and truncated-filtration infinite bars.
`zero-length bar reporting`: 180 record(s).
`cutoff tie semantics`: 4 record(s).
`truncated-filtration infinite-bar handling`: 12 record(s).
`alpha vs 2alpha` candidates: 0 record(s); none survived inspection as a plausible global scaling convention.

Minimal reproducible example: `tfim_obc_n4_g0p50__floating__p2__h1__full` dimension `1`.
Saved input: `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/audit/minimal_repros/convention_mismatch/distance_matrix.npy`.
Exact command: `PYTHONPATH=src python scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit --case-id tfim_obc_n4_g0p50__floating__p2__h1__full`.
Before/after plot: `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/audit/minimal_repros/convention_mismatch/convention_mismatch_before_after.png`.

## genuine coefficient dependence

0 disagreeing dimension record(s) fall in this class.
Alternate-coefficient reruns changed the discrepancy class in 0 record(s); after inspection, none indicates genuine field dependence as the cause of a cross-library mismatch.
Both `coeff=2` and `coeff=3` show the same two root causes: floating endpoint rounding in `H0` and convention-level extra bars in higher dimensions.

| coeff | count |
| --- | --- |
| 2 | 0 |
| 3 | 0 |

## boundary-condition dependence

0 disagreeing dimension record(s) fall in this class.
TFIM open and periodic chains both exhibit the same classified mechanisms, so boundary conditions change where discrepancies appear but not why they appear.

| boundary | count |
| --- | --- |
| obc | 0 |
| pbc | 0 |
| none | 0 |

## floating-point artifact

80 disagreeing dimension record(s) fall in this class. In every such case the disagreement is confined to floating mode `H0`, and GUDHI matches Ripser.py/Dionysus after a float32 round-trip of the endpoints.
The exact-quantized reruns remove these disagreements, which separates them cleanly from the higher-dimensional convention mismatches.

Minimal reproducible example: `tfim_obc_n4_g0p50__floating__p2__h1__full` dimension `0`.
Saved input: `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/audit/minimal_repros/floating_point_artifact/distance_matrix.npy`.
Exact command: `PYTHONPATH=src python scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit --case-id tfim_obc_n4_g0p50__floating__p2__h1__full`.
Before/after plot: `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/audit/minimal_repros/floating_point_artifact/floating_point_artifact_before_after.png`.

## unresolved

0 disagreeing dimension record(s) fall in this class.
Diagnostics also found `diagonal_nonzero_count=0`, `approximation_flag_failure_count=0`, and `infinite_bar_mismatch_count=20`.
Diagonal handling and approximation flags stay at zero throughout the audit. Any nonzero infinite-bar mismatch count is fully classified under convention mismatch rather than left unresolved.

## Reproducibility

- Each classification row is saved in `classification_table.csv` and `classification_table.json`.
- Each case-specific rerun bundle is saved under `cases/` with fresh baseline, quantized/exact, jittered, threshold-scaled, and alternate-coefficient outputs.
- Minimal reproducible examples are saved under `minimal_repros/` and mirrored as JSON pointers under `reproducers/`.
- The full machine-readable summary is saved in `summary.json`.
- The source discrepancy input came from `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/discrepancies/all_discrepancies.json`.
