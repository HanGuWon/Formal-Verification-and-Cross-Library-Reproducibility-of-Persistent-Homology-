# PH-AUDIT-CONVENTIONS-001

Audited 1 disagreeing dimension records from 1 discrepancy cases.

Recompute everything from the repository root with:

```bash
make audit
```

The full audit command is `PYTHONPATH=src python scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit-dev-convention`.

| classification | count |
| --- | --- |
| convention mismatch | 1 |
| genuine coefficient dependence | 0 |
| boundary-condition dependence | 0 |
| floating-point artifact | 0 |
| unresolved | 0 |

## convention mismatch

1 disagreeing dimension record(s) fall in this class. These are zero-metric disagreements where GUDHI emits extra cutoff-touching bars that Ripser.py and Dionysus omit.
`zero-length bar reporting`: 1 record(s).
`cutoff tie semantics`: 0 record(s).
`alpha vs 2alpha` candidates: 0 record(s); none survived inspection as a plausible global scaling convention.

Minimal reproducible example: `tfim_pbc_n4_g0p50__quantized__p2__h1__full` dimension `1`.
Saved input: `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/audit-dev-convention/minimal_repros/convention_mismatch/distance_matrix.npy`.
Exact command: `PYTHONPATH=src python scripts/run_audit_conventions.py --conformance-dir artifacts --output-dir artifacts/audit-dev-convention --case-id tfim_pbc_n4_g0p50__quantized__p2__h1__full`.
Before/after plot: `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/audit-dev-convention/minimal_repros/convention_mismatch/convention_mismatch_before_after.png`.

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

0 disagreeing dimension record(s) fall in this class. In every such case the disagreement is confined to floating mode `H0`, and GUDHI matches Ripser.py/Dionysus after a float32 round-trip of the endpoints.
The exact-quantized reruns remove these disagreements, which separates them cleanly from the higher-dimensional convention mismatches.

## unresolved

0 disagreeing dimension record(s) fall in this class.
Diagnostics also found `diagonal_nonzero_count=0`, `approximation_flag_failure_count=0`, and `infinite_bar_mismatch_count=0`.
All three are zero in this audit, so there are no unresolved cases attributable to diagonal handling, approximation flags, or infinite-bar semantics.

## Reproducibility

- Each classification row is saved in `classification_table.csv` and `classification_table.json`.
- Each case-specific rerun bundle is saved under `cases/` with fresh baseline, quantized/exact, jittered, threshold-scaled, and alternate-coefficient outputs.
- Minimal reproducible examples are saved under `minimal_repros/` and mirrored as JSON pointers under `reproducers/`.
- The full machine-readable summary is saved in `summary.json`.
- The source discrepancy input came from `/mnt/c/Users/한구원/Desktop/Formal-Verification-and-Cross-Library-Reproducibility-of-Persistent-Homology-/artifacts/discrepancies/all_discrepancies.json`.
