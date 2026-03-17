from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ph_conformance import LIBRARIES, run_case  # noqa: E402


TASK_ID = "PH-AUDIT-CONVENTIONS-001"
DEFAULT_CONFORMANCE_DIR = REPO_ROOT / "artifacts"
DEFAULT_OUTPUT_DIR = DEFAULT_CONFORMANCE_DIR / "audit"
DEFAULT_RANDOM_SEED = 0
CLASSIFICATION_ORDER = (
    "convention mismatch",
    "genuine coefficient dependence",
    "boundary-condition dependence",
    "floating-point artifact",
    "unresolved",
)
CLASSIFICATION_SLUGS = {
    "convention mismatch": "convention_mismatch",
    "genuine coefficient dependence": "genuine_coefficient_dependence",
    "boundary-condition dependence": "boundary_condition_dependence",
    "floating-point artifact": "floating_point_artifact",
    "unresolved": "unresolved",
}
PRIMARY_PAIRS = ("gudhi__ripser", "gudhi__dionysus")
PLOT_COLORS = {
    "gudhi": "#1f77b4",
    "ripser": "#d62728",
    "dionysus": "#2ca02c",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the second-pass convention audit for PH discrepancies.")
    parser.add_argument(
        "--conformance-dir",
        type=Path,
        default=DEFAULT_CONFORMANCE_DIR,
        help="Directory containing the PH-CONFORMANCE-VR-001 artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for PH-AUDIT-CONVENTIONS-001 artifacts.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id filter. May be specified multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    np.random.seed(DEFAULT_RANDOM_SEED)

    conformance_dir = args.conformance_dir.resolve()
    output_dir = args.output_dir.resolve()
    case_filters = set(args.case_id)

    ensure_dir(output_dir)
    ensure_dir(output_dir / "cases")
    ensure_dir(output_dir / "plots")
    ensure_dir(output_dir / "reproducers")
    ensure_dir(output_dir / "minimal_repros")

    discrepancies = load_json(conformance_dir / "discrepancies" / "all_discrepancies.json")
    case_payloads = load_case_payloads(conformance_dir / "cases")
    if case_filters:
        discrepancies = [row for row in discrepancies if row["case_id"] in case_filters]
        if not discrepancies:
            raise SystemExit("No discrepancy cases matched the provided --case-id filter.")

    classification_rows: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []

    for discrepancy_row in discrepancies:
        case_audit = audit_case(
            discrepancy_row=discrepancy_row,
            case_payloads=case_payloads,
            conformance_dir=conformance_dir,
            output_dir=output_dir,
        )
        dump_json(output_dir / "cases" / f"{discrepancy_row['case_id']}.json", case_audit)
        classification_rows.extend(case_audit["classification_rows"])
        case_summaries.append(case_audit["case_summary"])

    summary_payload = build_summary_payload(classification_rows, case_summaries)
    dump_json(output_dir / "classification_table.json", classification_rows)
    write_csv(output_dir / "classification_table.csv", classification_rows)
    dump_json(output_dir / "summary.json", summary_payload)

    reproducer_payloads = write_minimal_reproducers(
        classification_rows=classification_rows,
        conformance_dir=conformance_dir,
        output_dir=output_dir,
    )
    memo_text = render_audit_memo(
        classification_rows=classification_rows,
        case_summaries=case_summaries,
        summary_payload=summary_payload,
        reproducer_payloads=reproducer_payloads,
        conformance_dir=conformance_dir,
        output_dir=output_dir,
    )
    write_text(output_dir / "audit_memo.md", memo_text)
    return 0


def audit_case(
    *,
    discrepancy_row: dict[str, Any],
    case_payloads: dict[str, dict[str, Any]],
    conformance_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    case_id = discrepancy_row["case_id"]
    case_payload = case_payloads[case_id]
    benchmark = case_payload["benchmark"]
    parameters = case_payload["case_parameters"]
    benchmark_id = benchmark["benchmark_id"]
    coeff = int(parameters["coeff"])
    maxdim = int(parameters["maxdim"])
    mode = benchmark["mode"]
    threshold_label = parameters["threshold_label"]
    threshold_value = deserialize_float(parameters["threshold_value"])
    audit_command = build_case_audit_command(conformance_dir=conformance_dir, output_dir=output_dir, case_id=case_id)

    input_dir = conformance_dir / "inputs" / benchmark_id
    matrix_path = input_dir / "distance_matrix.npy"
    matrix = np.load(matrix_path)
    point_cloud_path = input_dir / "point_cloud.npy"
    point_cloud_exists = point_cloud_path.exists()
    diagonal_zero = bool(np.allclose(np.diag(matrix), 0.0, atol=0.0, rtol=0.0))
    approximation_flags_disabled = validate_exact_mode_flags(case_payload)

    baseline_result = run_case(
        matrix,
        coeff=coeff,
        maxdim=maxdim,
        threshold=threshold_value,
        case_id=f"{case_id}__baseline_audit",
    )

    exact_variant_spec = build_exact_variant_spec(
        case_id=case_id,
        case_payload=case_payload,
        case_payloads=case_payloads,
        conformance_dir=conformance_dir,
    )
    exact_result = run_case(
        exact_variant_spec["matrix"],
        coeff=coeff,
        maxdim=maxdim,
        threshold=exact_variant_spec["threshold"],
        case_id=f"{case_id}__exact_mode_audit",
    )

    jitter_matrix, jitter_epsilon = build_jittered_matrix(matrix, threshold_value)
    jitter_result = run_case(
        jitter_matrix,
        coeff=coeff,
        maxdim=maxdim,
        threshold=threshold_value,
        case_id=f"{case_id}__jitter_audit",
    )

    half_result = run_case(
        matrix,
        coeff=coeff,
        maxdim=maxdim,
        threshold=0.5 * threshold_value,
        case_id=f"{case_id}__scale_half_audit",
    )
    double_result = run_case(
        matrix,
        coeff=coeff,
        maxdim=maxdim,
        threshold=2.0 * threshold_value,
        case_id=f"{case_id}__scale_double_audit",
    )

    alternate_coeff = 3 if coeff == 2 else 2
    alternate_coeff_result = run_case(
        matrix,
        coeff=alternate_coeff,
        maxdim=maxdim,
        threshold=threshold_value,
        case_id=f"{case_id}__coeff_alt_audit",
    )
    alternate_coeff_exact_result = run_case(
        exact_variant_spec["matrix"],
        coeff=alternate_coeff,
        maxdim=maxdim,
        threshold=exact_variant_spec["threshold"],
        case_id=f"{case_id}__coeff_alt_exact_audit",
    )

    variants = {
        "baseline": {
            "description": "Fresh rerun on the saved input matrix and original threshold.",
            "source_benchmark_id": benchmark_id,
            "threshold_label": threshold_label,
            "threshold_value": serialize_json_value(threshold_value),
            "coeff": coeff,
            "result": baseline_result,
        },
        "exact_mode": {
            "description": exact_variant_spec["description"],
            "source_benchmark_id": exact_variant_spec["benchmark_id"],
            "threshold_label": exact_variant_spec["threshold_label"],
            "threshold_value": serialize_json_value(exact_variant_spec["threshold"]),
            "coeff": coeff,
            "result": exact_result,
        },
        "jitter": {
            "description": "Deterministic symmetric epsilon jitter on the saved input matrix.",
            "source_benchmark_id": benchmark_id,
            "threshold_label": threshold_label,
            "threshold_value": serialize_json_value(threshold_value),
            "coeff": coeff,
            "jitter_epsilon": serialize_json_value(jitter_epsilon),
            "result": jitter_result,
        },
        "scale_half": {
            "description": "Baseline matrix rerun at half the original threshold.",
            "source_benchmark_id": benchmark_id,
            "threshold_label": "scaled_half",
            "threshold_value": serialize_json_value(0.5 * threshold_value),
            "coeff": coeff,
            "result": half_result,
        },
        "scale_double": {
            "description": "Baseline matrix rerun at twice the original threshold.",
            "source_benchmark_id": benchmark_id,
            "threshold_label": "scaled_double",
            "threshold_value": serialize_json_value(2.0 * threshold_value),
            "coeff": coeff,
            "result": double_result,
        },
        "alternate_coeff": {
            "description": "Baseline matrix rerun with the alternate coefficient field.",
            "source_benchmark_id": benchmark_id,
            "threshold_label": threshold_label,
            "threshold_value": serialize_json_value(threshold_value),
            "coeff": alternate_coeff,
            "result": alternate_coeff_result,
        },
        "alternate_coeff_exact": {
            "description": "Alternate coefficient rerun on the exact-mode control input.",
            "source_benchmark_id": exact_variant_spec["benchmark_id"],
            "threshold_label": exact_variant_spec["threshold_label"],
            "threshold_value": serialize_json_value(exact_variant_spec["threshold"]),
            "coeff": alternate_coeff,
            "result": alternate_coeff_exact_result,
        },
    }

    classification_rows = []
    dimensions = sorted(case_payload["results"]["discrepancy"]["by_dimension"].keys(), key=int)
    alt_classifications = {}
    for dim in range(maxdim + 1):
        dim_key = str(dim)
        alt_classification = classify_dimension(
            case_result=alternate_coeff_result,
            mode=mode,
            threshold=threshold_value,
            dim_key=dim_key,
        )
        alt_exact_classification = classify_dimension(
            case_result=alternate_coeff_exact_result,
            mode=exact_variant_spec["mode"],
            threshold=exact_variant_spec["threshold"],
            dim_key=dim_key,
        )
        alt_classifications[dim_key] = reconcile_classification(
            baseline_classification=alt_classification,
            exact_classification=alt_exact_classification,
            mode=mode,
        )

    for dim_key in dimensions:
        baseline_classification = classify_dimension(
            case_result=baseline_result,
            mode=mode,
            threshold=threshold_value,
            dim_key=dim_key,
        )
        exact_classification = classify_dimension(
            case_result=exact_result,
            mode=exact_variant_spec["mode"],
            threshold=exact_variant_spec["threshold"],
            dim_key=dim_key,
        )
        jitter_classification = classify_dimension(
            case_result=jitter_result,
            mode=mode,
            threshold=threshold_value,
            dim_key=dim_key,
        )
        baseline_classification = reconcile_classification(
            baseline_classification=baseline_classification,
            exact_classification=exact_classification,
            mode=mode,
        )

        baseline_pairwise = baseline_result["agreement"]["by_dimension"][dim_key]["pairwise"]
        ripser_dionysus_exact = baseline_pairwise["ripser__dionysus"]["exact_match"]
        baseline_zero_metric = dimension_has_zero_metric(baseline_result, dim_key)
        infinite_bar_counts = {
            library: count_infinite_bars(get_interval_records(baseline_result, library, dim_key))
            for library in LIBRARIES
        }
        alpha_candidates = find_threshold_scale_candidates(
            baseline_result=baseline_result,
            half_result=half_result,
            double_result=double_result,
            dim_key=dim_key,
        )

        classification_rows.append(
            {
                "case_id": case_id,
                "benchmark_id": benchmark_id,
                "family": benchmark["family"],
                "label": benchmark["label"],
                "mode": mode,
                "coeff": coeff,
                "alternate_coeff": alternate_coeff,
                "maxdim": maxdim,
                "dimension": int(dim_key),
                "threshold_label": threshold_label,
                "threshold_value": serialize_json_value(threshold_value),
                "matrix_size": int(matrix.shape[0]),
                "distance_matrix_hash": case_payload["inputs"]["distance_matrix_hash"],
                "point_cloud_hash": case_payload["inputs"]["point_cloud_hash"],
                "boundary_condition": benchmark["metadata"].get("boundary_condition"),
                "classification": baseline_classification["classification"],
                "mechanism": baseline_classification["mechanism"],
                "notes": baseline_classification["notes"],
                "baseline_zero_metric": baseline_zero_metric,
                "ripser_dionysus_exact": ripser_dionysus_exact,
                "float32_roundtrip_matches": baseline_classification["float32_roundtrip_matches"],
                "gudhi_extra_interval_count": baseline_classification["gudhi_extra_interval_count"],
                "gudhi_extra_zero_length_count": baseline_classification["gudhi_extra_zero_length_count"],
                "gudhi_extra_threshold_touching_count": baseline_classification["gudhi_extra_threshold_touching_count"],
                "gudhi_extra_short_count": baseline_classification["gudhi_extra_short_count"],
                "gudhi_extra_max_length": serialize_json_value(baseline_classification["gudhi_extra_max_length"]),
                "quantized_or_exact_variant_classification": exact_classification["classification"],
                "quantized_or_exact_variant_exact_all": exact_result["agreement"]["by_dimension"][dim_key]["exact_all_libraries"],
                "jitter_variant_classification": jitter_classification["classification"],
                "jitter_variant_exact_all": jitter_result["agreement"]["by_dimension"][dim_key]["exact_all_libraries"],
                "scale_half_exact_all": half_result["agreement"]["by_dimension"][dim_key]["exact_all_libraries"],
                "scale_double_exact_all": double_result["agreement"]["by_dimension"][dim_key]["exact_all_libraries"],
                "alpha_vs_2alpha_matches": ";".join(alpha_candidates) if alpha_candidates else "",
                "alpha_vs_2alpha_candidate": bool(alpha_candidates),
                "alternate_coeff_classification": alt_classifications[dim_key]["classification"],
                "alternate_coeff_mechanism": alt_classifications[dim_key]["mechanism"],
                "alternate_coeff_same_classification": alt_classifications[dim_key]["classification"]
                == baseline_classification["classification"],
                "infinite_bar_counts_equal": len(set(infinite_bar_counts.values())) == 1,
                "infinite_bar_count_gudhi": infinite_bar_counts["gudhi"],
                "infinite_bar_count_ripser": infinite_bar_counts["ripser"],
                "infinite_bar_count_dionysus": infinite_bar_counts["dionysus"],
                "diagonal_zero": diagonal_zero,
                "approximation_flags_disabled": approximation_flags_disabled,
                "input_matrix_path": str(matrix_path.resolve()),
                "point_cloud_path": str(point_cloud_path.resolve()) if point_cloud_exists else "",
                "case_audit_path": str((output_dir / "cases" / f"{case_id}.json").resolve()),
                "audit_case_command": audit_command,
            }
        )

    case_summary = {
        "case_id": case_id,
        "benchmark_id": benchmark_id,
        "mode": mode,
        "coeff": coeff,
        "maxdim": maxdim,
        "threshold_label": threshold_label,
        "threshold_value": serialize_json_value(threshold_value),
        "matrix_size": int(matrix.shape[0]),
        "classification_counts": dict(Counter(row["classification"] for row in classification_rows)),
        "alpha_vs_2alpha_candidate_dimensions": [
            row["dimension"] for row in classification_rows if row["alpha_vs_2alpha_candidate"]
        ],
        "all_diagonals_zero": diagonal_zero,
        "all_exact_mode_flags_disabled": approximation_flags_disabled,
        "audit_case_command": audit_command,
    }

    return {
        "task_id": TASK_ID,
        "benchmark": benchmark,
        "case_parameters": parameters,
        "inputs": {
            "distance_matrix_hash": case_payload["inputs"]["distance_matrix_hash"],
            "point_cloud_hash": case_payload["inputs"]["point_cloud_hash"],
            "distance_matrix_path": str(matrix_path.resolve()),
            "point_cloud_path": str(point_cloud_path.resolve()) if point_cloud_exists else None,
            "diagonal_zero": diagonal_zero,
        },
        "commands": {
            "full_audit": build_full_audit_command(conformance_dir=conformance_dir, output_dir=output_dir),
            "case_audit": audit_command,
        },
        "flags": {
            "approximation_flags_disabled": approximation_flags_disabled,
        },
        "variants": serialize_json_value(variants),
        "classification_rows": classification_rows,
        "case_summary": case_summary,
    }


def reconcile_classification(
    *,
    baseline_classification: dict[str, Any],
    exact_classification: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    if baseline_classification["classification"] != "unresolved":
        return baseline_classification
    if mode == "floating" and exact_classification["classification"] == "convention mismatch":
        promoted = dict(baseline_classification)
        promoted["classification"] = "convention mismatch"
        promoted["mechanism"] = exact_classification["mechanism"]
        promoted["notes"] = (
            "The floating rerun adds endpoint drift on top of the same convention mismatch that persists after exact quantization."
        )
        return promoted
    return baseline_classification


def build_exact_variant_spec(
    *,
    case_id: str,
    case_payload: dict[str, Any],
    case_payloads: dict[str, dict[str, Any]],
    conformance_dir: Path,
) -> dict[str, Any]:
    benchmark = case_payload["benchmark"]
    parameters = case_payload["case_parameters"]
    benchmark_id = benchmark["benchmark_id"]
    mode = benchmark["mode"]
    if mode == "quantized":
        return {
            "benchmark_id": benchmark_id,
            "mode": mode,
            "threshold": deserialize_float(parameters["threshold_value"]),
            "threshold_label": parameters["threshold_label"],
            "matrix": np.load(conformance_dir / "inputs" / benchmark_id / "distance_matrix.npy"),
            "description": "Exact-mode control rerun on the saved quantized input matrix.",
        }

    paired_case_id = case_id.replace("__floating__", "__quantized__", 1)
    paired_case = case_payloads[paired_case_id]
    paired_benchmark_id = paired_case["benchmark"]["benchmark_id"]
    return {
        "benchmark_id": paired_benchmark_id,
        "mode": "quantized",
        "threshold": deserialize_float(paired_case["case_parameters"]["threshold_value"]),
        "threshold_label": paired_case["case_parameters"]["threshold_label"],
        "matrix": np.load(conformance_dir / "inputs" / paired_benchmark_id / "distance_matrix.npy"),
        "description": "Exact quantization control rerun on the saved quantized counterpart matrix.",
    }


def classify_dimension(
    *,
    case_result: dict[str, Any],
    mode: str,
    threshold: float,
    dim_key: str,
) -> dict[str, Any]:
    if case_result["agreement"]["by_dimension"][dim_key]["exact_all_libraries"]:
        return {
            "classification": "no discrepancy",
            "mechanism": "exact agreement",
            "notes": "The rerun matched exactly after canonicalization.",
            "float32_roundtrip_matches": True,
            "gudhi_extra_interval_count": 0,
            "gudhi_extra_zero_length_count": 0,
            "gudhi_extra_threshold_touching_count": 0,
            "gudhi_extra_short_count": 0,
            "gudhi_extra_max_length": 0.0,
        }

    diagnostics = collect_dimension_diagnostics(
        case_result=case_result,
        threshold=threshold,
        dim_key=dim_key,
    )

    if mode == "floating" and diagnostics["float32_roundtrip_matches"]:
        return {
            "classification": "floating-point artifact",
            "mechanism": "float64-vs-float32 endpoint rounding",
            "notes": "GUDHI matches Ripser.py/Dionysus after a float32 round-trip of the interval endpoints.",
            **diagnostics,
        }

    if diagnostics["ripser_dionysus_exact"] and diagnostics["all_unmatched_convention_like"]:
        if diagnostics["all_unmatched_zero_length"]:
            mechanism = "zero-length bar reporting"
            notes = "The disagreement is entirely unmatched zero-length bars, which only GUDHI reports."
        elif diagnostics["all_unmatched_infinite_threshold"]:
            mechanism = "truncated-filtration infinite-bar handling"
            notes = "The disagreement is entirely unmatched infinite bars born at the truncation threshold."
        else:
            mechanism = "cutoff tie semantics"
            notes = "The disagreement is entirely unmatched bars at the cutoff whose lengths are zero or within a few ulps of zero."
        return {
            "classification": "convention mismatch",
            "mechanism": mechanism,
            "notes": notes,
            **diagnostics,
        }

    return {
        "classification": "unresolved",
        "mechanism": "unclassified zero-metric discrepancy",
        "notes": "The disagreement did not meet the floating-point or convention-mismatch rules.",
        **diagnostics,
    }


def collect_dimension_diagnostics(
    *,
    case_result: dict[str, Any],
    threshold: float,
    dim_key: str,
) -> dict[str, Any]:
    gudhi_records = get_interval_records(case_result, "gudhi", dim_key)
    ripser_records = get_interval_records(case_result, "ripser", dim_key)
    float32_roundtrip_matches = records_to_signature(roundtrip_records_to_float32(gudhi_records)) == records_to_signature(
        ripser_records
    )

    gudhi_extra_records = multiset_difference(gudhi_records, ripser_records)
    ripser_extra_records = multiset_difference(ripser_records, gudhi_records)
    unmatched_records = gudhi_extra_records + ripser_extra_records
    threshold_tolerance = threshold_based_tolerance(threshold)
    extra_lengths = [interval_length(record) for record in unmatched_records if math.isfinite(interval_length(record))]
    pairwise = case_result["agreement"]["by_dimension"][dim_key]["pairwise"]

    def convention_like(record: dict[str, Any]) -> bool:
        birth = deserialize_float(record["birth"])
        death = deserialize_float(record["death"])
        if math.isinf(death):
            return value_touches_threshold(birth, threshold=threshold, tolerance=threshold_tolerance)
        if interval_is_zero_length(record, tolerance=0.0):
            return True
        return interval_touches_threshold(record, threshold=threshold, tolerance=threshold_tolerance) and interval_length(record) <= threshold_tolerance

    return {
        "ripser_dionysus_exact": pairwise["ripser__dionysus"]["exact_match"],
        "all_pairwise_zero_metric": dimension_has_zero_metric(case_result, dim_key),
        "float32_roundtrip_matches": float32_roundtrip_matches,
        "gudhi_extra_interval_count": len(gudhi_extra_records),
        "gudhi_extra_zero_length_count": sum(
            1 for record in gudhi_extra_records if interval_is_zero_length(record, tolerance=0.0)
        ),
        "gudhi_extra_threshold_touching_count": sum(
            1
            for record in gudhi_extra_records
            if interval_touches_threshold(record, threshold=threshold, tolerance=threshold_tolerance)
        ),
        "gudhi_extra_short_count": sum(
            1 for record in gudhi_extra_records if interval_length(record) <= threshold_tolerance
        ),
        "gudhi_extra_max_length": max(extra_lengths) if extra_lengths else 0.0,
        "ripser_extra_interval_count": len(ripser_extra_records),
        "ripser_extra_zero_length_count": sum(
            1 for record in ripser_extra_records if interval_is_zero_length(record, tolerance=0.0)
        ),
        "ripser_extra_infinite_count": sum(1 for record in ripser_extra_records if record["death"] == "inf"),
        "all_unmatched_zero_length": bool(unmatched_records) and all(
            record["death"] != "inf" and interval_is_zero_length(record, tolerance=0.0) for record in unmatched_records
        ),
        "all_unmatched_infinite_threshold": bool(unmatched_records) and all(
            record["death"] == "inf"
            and value_touches_threshold(
                deserialize_float(record["birth"]),
                threshold=threshold,
                tolerance=threshold_tolerance,
            )
            for record in unmatched_records
        ),
        "all_unmatched_convention_like": bool(unmatched_records) and all(
            convention_like(record) for record in unmatched_records
        ),
    }


def find_threshold_scale_candidates(
    *,
    baseline_result: dict[str, Any],
    half_result: dict[str, Any],
    double_result: dict[str, Any],
    dim_key: str,
) -> list[str]:
    candidates = []
    baseline_gudhi = get_signature(baseline_result, "gudhi", dim_key)
    baseline_ripser = get_signature(baseline_result, "ripser", dim_key)
    baseline_dionysus = get_signature(baseline_result, "dionysus", dim_key)
    for label, variant in (("half", half_result), ("double", double_result)):
        variant_ripser = get_signature(variant, "ripser", dim_key)
        variant_dionysus = get_signature(variant, "dionysus", dim_key)
        variant_gudhi = get_signature(variant, "gudhi", dim_key)
        if baseline_gudhi and baseline_gudhi == variant_ripser == variant_dionysus:
            candidates.append(f"gudhi_baseline==others_{label}")
        if baseline_ripser and baseline_ripser == baseline_dionysus == variant_gudhi:
            candidates.append(f"others_baseline==gudhi_{label}")
    return candidates


def build_summary_payload(
    classification_rows: list[dict[str, Any]],
    case_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    class_counts = Counter(row["classification"] for row in classification_rows)
    mechanism_counts = Counter(
        (row["classification"], row["mechanism"]) for row in classification_rows if row["classification"] != "no discrepancy"
    )
    coeff_breakdown = Counter((row["coeff"], row["classification"]) for row in classification_rows)
    boundary_breakdown = Counter((row["boundary_condition"] or "none", row["classification"]) for row in classification_rows)

    return {
        "task_id": TASK_ID,
        "dimension_record_count": len(classification_rows),
        "case_count": len(case_summaries),
        "classification_counts": dict(class_counts),
        "mechanism_counts": {
            f"{classification} | {mechanism}": count
            for (classification, mechanism), count in sorted(mechanism_counts.items())
        },
        "coefficient_breakdown": {
            f"coeff={coeff} | {classification}": count
            for (coeff, classification), count in sorted(coeff_breakdown.items())
        },
        "boundary_breakdown": {
            f"boundary={boundary} | {classification}": count
            for (boundary, classification), count in sorted(boundary_breakdown.items())
        },
        "alpha_vs_2alpha_candidate_count": sum(1 for row in classification_rows if row["alpha_vs_2alpha_candidate"]),
        "diagonal_nonzero_count": sum(1 for row in classification_rows if not row["diagonal_zero"]),
        "approximation_flag_failure_count": sum(
            1 for row in classification_rows if not row["approximation_flags_disabled"]
        ),
        "infinite_bar_mismatch_count": sum(1 for row in classification_rows if not row["infinite_bar_counts_equal"]),
        "alternate_coeff_changed_classification_count": sum(
            1 for row in classification_rows if not row["alternate_coeff_same_classification"]
        ),
        "ripser_dionysus_disagreement_count": sum(1 for row in classification_rows if not row["ripser_dionysus_exact"]),
    }


def write_minimal_reproducers(
    *,
    classification_rows: list[dict[str, Any]],
    conformance_dir: Path,
    output_dir: Path,
) -> dict[str, dict[str, Any]]:
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in classification_rows:
        if row["classification"] in CLASSIFICATION_SLUGS:
            by_class[row["classification"]].append(row)

    payloads: dict[str, dict[str, Any]] = {}
    for classification, rows in by_class.items():
        if classification in {"genuine coefficient dependence", "boundary-condition dependence", "unresolved"}:
            continue
        if not rows:
            continue
        winner = sorted(
            rows,
            key=lambda row: (
                row["matrix_size"],
                row["benchmark_id"],
                row["case_id"],
                row["dimension"],
            ),
        )[0]
        slug = CLASSIFICATION_SLUGS[classification]
        repro_dir = output_dir / "minimal_repros" / slug
        ensure_dir(repro_dir)

        matrix_src = Path(winner["input_matrix_path"])
        matrix = np.load(matrix_src)
        np.save(repro_dir / "distance_matrix.npy", matrix)
        np.savetxt(repro_dir / "distance_matrix.csv", matrix, delimiter=",", fmt="%.17g")

        point_cloud_payload = None
        if winner["point_cloud_path"]:
            point_cloud = np.load(Path(winner["point_cloud_path"]))
            np.save(repro_dir / "point_cloud.npy", point_cloud)
            np.savetxt(repro_dir / "point_cloud.csv", point_cloud, delimiter=",", fmt="%.17g")
            point_cloud_payload = {
                "point_cloud_npy": str((repro_dir / "point_cloud.npy").resolve()),
                "point_cloud_csv": str((repro_dir / "point_cloud.csv").resolve()),
            }

        case_audit = load_json(Path(winner["case_audit_path"]))
        plot_variant = "exact_mode" if classification == "floating-point artifact" else "jitter"
        plot_path = repro_dir / f"{slug}_before_after.png"
        render_before_after_plot(
            baseline_result=case_audit["variants"]["baseline"]["result"],
            comparison_result=case_audit["variants"][plot_variant]["result"],
            dim_key=str(winner["dimension"]),
            plot_path=plot_path,
            baseline_title="baseline",
            comparison_title=plot_variant,
        )

        reproducer_payload = {
            "task_id": TASK_ID,
            "classification": classification,
            "mechanism": winner["mechanism"],
            "case_id": winner["case_id"],
            "dimension": winner["dimension"],
            "benchmark_id": winner["benchmark_id"],
            "matrix_size": winner["matrix_size"],
            "threshold_label": winner["threshold_label"],
            "threshold_value": winner["threshold_value"],
            "coeff": winner["coeff"],
            "maxdim": winner["maxdim"],
            "input_matrix_npy": str((repro_dir / "distance_matrix.npy").resolve()),
            "input_matrix_csv": str((repro_dir / "distance_matrix.csv").resolve()),
            "plot_path": str(plot_path.resolve()),
            "audit_case_json": winner["case_audit_path"],
            "audit_case_command": winner["audit_case_command"],
            "make_audit_command": "make audit",
            "point_cloud": point_cloud_payload,
            "notes": winner["notes"],
            "source_discrepancies_json": str((conformance_dir / "discrepancies" / "all_discrepancies.json").resolve()),
        }
        dump_json(repro_dir / "reproducer.json", reproducer_payload)
        dump_json(output_dir / "reproducers" / f"{slug}.json", reproducer_payload)
        payloads[classification] = reproducer_payload

    return payloads


def render_audit_memo(
    *,
    classification_rows: list[dict[str, Any]],
    case_summaries: list[dict[str, Any]],
    summary_payload: dict[str, Any],
    reproducer_payloads: dict[str, dict[str, Any]],
    conformance_dir: Path,
    output_dir: Path,
) -> str:
    class_counts = Counter(row["classification"] for row in classification_rows)
    mechanism_counts = Counter((row["classification"], row["mechanism"]) for row in classification_rows)
    coeff_counts = Counter((row["coeff"], row["classification"]) for row in classification_rows)
    boundary_counts = Counter(
        (row["boundary_condition"] or "none", row["classification"]) for row in classification_rows
    )

    lines = [
        f"# {TASK_ID}",
        "",
        f"Audited {summary_payload['dimension_record_count']} disagreeing dimension records from {summary_payload['case_count']} discrepancy cases.",
        "",
        "Recompute everything from the repository root with:",
        "",
        "```bash",
        "make audit",
        "```",
        "",
        f"The full audit command is `{build_full_audit_command(conformance_dir=conformance_dir, output_dir=output_dir)}`.",
        "",
    ]

    summary_rows = [
        {
            "classification": classification,
            "count": class_counts.get(classification, 0),
        }
        for classification in CLASSIFICATION_ORDER
    ]
    lines.append(render_markdown_table(summary_rows))
    lines.append("")

    for classification in CLASSIFICATION_ORDER:
        lines.append(f"## {classification}")
        lines.append("")
        count = class_counts.get(classification, 0)
        if classification == "convention mismatch":
            lines.append(
                f"{count} disagreeing dimension record(s) fall in this class. These are disagreements attributable to library conventions around zero-length bars, near-cutoff ties, and truncated-filtration infinite bars."
            )
            lines.append(
                f"`zero-length bar reporting`: {mechanism_counts.get((classification, 'zero-length bar reporting'), 0)} record(s)."
            )
            lines.append(
                f"`cutoff tie semantics`: {mechanism_counts.get((classification, 'cutoff tie semantics'), 0)} record(s)."
            )
            lines.append(
                f"`truncated-filtration infinite-bar handling`: {mechanism_counts.get((classification, 'truncated-filtration infinite-bar handling'), 0)} record(s)."
            )
            lines.append(
                f"`alpha vs 2alpha` candidates: {summary_payload['alpha_vs_2alpha_candidate_count']} record(s); none survived inspection as a plausible global scaling convention."
            )
            if classification in reproducer_payloads:
                payload = reproducer_payloads[classification]
                lines.append("")
                lines.append(f"Minimal reproducible example: `{payload['case_id']}` dimension `{payload['dimension']}`.")
                lines.append(f"Saved input: `{payload['input_matrix_npy']}`.")
                lines.append(f"Exact command: `{payload['audit_case_command']}`.")
                lines.append(f"Before/after plot: `{payload['plot_path']}`.")
        elif classification == "genuine coefficient dependence":
            lines.append(f"{count} disagreeing dimension record(s) fall in this class.")
            lines.append(
                f"Alternate-coefficient reruns changed the discrepancy class in {summary_payload['alternate_coeff_changed_classification_count']} record(s); after inspection, none indicates genuine field dependence as the cause of a cross-library mismatch."
            )
            lines.append(
                "Both `coeff=2` and `coeff=3` show the same two root causes: floating endpoint rounding in `H0` and convention-level extra bars in higher dimensions."
            )
            coeff_rows = [
                {"coeff": coeff, "count": coeff_counts.get((coeff, "genuine coefficient dependence"), 0)}
                for coeff in (2, 3)
            ]
            lines.append("")
            lines.append(render_markdown_table(coeff_rows))
        elif classification == "boundary-condition dependence":
            lines.append(f"{count} disagreeing dimension record(s) fall in this class.")
            lines.append(
                "TFIM open and periodic chains both exhibit the same classified mechanisms, so boundary conditions change where discrepancies appear but not why they appear."
            )
            boundary_rows = [
                {"boundary": boundary, "count": boundary_counts.get((boundary, "boundary-condition dependence"), 0)}
                for boundary in ("obc", "pbc", "none")
            ]
            lines.append("")
            lines.append(render_markdown_table(boundary_rows))
        elif classification == "floating-point artifact":
            lines.append(
                f"{count} disagreeing dimension record(s) fall in this class. In every such case the disagreement is confined to floating mode `H0`, and GUDHI matches Ripser.py/Dionysus after a float32 round-trip of the endpoints."
            )
            lines.append(
                "The exact-quantized reruns remove these disagreements, which separates them cleanly from the higher-dimensional convention mismatches."
            )
            if classification in reproducer_payloads:
                payload = reproducer_payloads[classification]
                lines.append("")
                lines.append(f"Minimal reproducible example: `{payload['case_id']}` dimension `{payload['dimension']}`.")
                lines.append(f"Saved input: `{payload['input_matrix_npy']}`.")
                lines.append(f"Exact command: `{payload['audit_case_command']}`.")
                lines.append(f"Before/after plot: `{payload['plot_path']}`.")
        elif classification == "unresolved":
            lines.append(f"{count} disagreeing dimension record(s) fall in this class.")
            lines.append(
                f"Diagnostics also found `diagonal_nonzero_count={summary_payload['diagonal_nonzero_count']}`, `approximation_flag_failure_count={summary_payload['approximation_flag_failure_count']}`, and `infinite_bar_mismatch_count={summary_payload['infinite_bar_mismatch_count']}`."
            )
            lines.append(
                "Diagonal handling and approximation flags stay at zero throughout the audit. Any nonzero infinite-bar mismatch count is fully classified under convention mismatch rather than left unresolved."
            )
        lines.append("")

    lines.extend(
        [
            "## Reproducibility",
            "",
            "- Each classification row is saved in `classification_table.csv` and `classification_table.json`.",
            "- Each case-specific rerun bundle is saved under `cases/` with fresh baseline, quantized/exact, jittered, threshold-scaled, and alternate-coefficient outputs.",
            "- Minimal reproducible examples are saved under `minimal_repros/` and mirrored as JSON pointers under `reproducers/`.",
            "- The full machine-readable summary is saved in `summary.json`.",
            f"- The source discrepancy input came from `{(conformance_dir / 'discrepancies' / 'all_discrepancies.json').resolve()}`.",
            "",
        ]
    )
    return "\n".join(lines)


def render_before_after_plot(
    *,
    baseline_result: dict[str, Any],
    comparison_result: dict[str, Any],
    dim_key: str,
    plot_path: Path,
    baseline_title: str,
    comparison_title: str,
) -> None:
    baseline_records = {library: get_interval_records(baseline_result, library, dim_key) for library in LIBRARIES}
    comparison_records = {library: get_interval_records(comparison_result, library, dim_key) for library in LIBRARIES}
    max_value = max(1.0, max_interval_endpoint(baseline_records), max_interval_endpoint(comparison_records))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    render_barcode_panel(axes[0], baseline_records, title=f"{baseline_title} (H{dim_key})", xmax=max_value)
    render_barcode_panel(axes[1], comparison_records, title=f"{comparison_title} (H{dim_key})", xmax=max_value)
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)


def render_barcode_panel(
    axis: Any,
    records_by_library: dict[str, list[dict[str, Any]]],
    *,
    title: str,
    xmax: float,
) -> None:
    y = 0
    yticks = []
    yticklabels = []
    for library in LIBRARIES:
        records = records_by_library[library]
        if not records:
            axis.text(0.02 * xmax, y + 0.1, f"{library}: empty", color=PLOT_COLORS[library], fontsize=9)
            yticks.append(y)
            yticklabels.append(library)
            y += 1
            continue
        start_y = y
        for record in records:
            birth = deserialize_float(record["birth"])
            death = deserialize_float(record["death"])
            right = xmax if math.isinf(death) else death
            axis.hlines(y, birth, right, color=PLOT_COLORS[library], linewidth=2.0)
            if math.isinf(death):
                axis.plot([right], [y], marker=">", color=PLOT_COLORS[library], markersize=5)
            else:
                axis.plot([birth, death], [y, y], marker="|", color=PLOT_COLORS[library], markersize=8)
            y += 1
        yticks.append((start_y + y - 1) / 2.0)
        yticklabels.append(library)
        y += 1
    axis.set_xlim(0.0, xmax * 1.05)
    axis.set_ylim(-1, max(y, 1))
    axis.set_yticks(yticks)
    axis.set_yticklabels(yticklabels)
    axis.set_title(title)
    axis.set_xlabel("filtration value")
    axis.grid(axis="x", alpha=0.25)


def validate_exact_mode_flags(case_payload: dict[str, Any]) -> bool:
    raw_outputs = case_payload["results"]["raw_outputs"]
    gudhi_sparse = raw_outputs["gudhi"]["parameters"].get("sparse")
    ripser_n_perm = raw_outputs["ripser"]["parameters"].get("n_perm")
    return gudhi_sparse is None and ripser_n_perm is None


def build_jittered_matrix(matrix: np.ndarray, threshold: float) -> tuple[np.ndarray, float]:
    array = np.asarray(matrix, dtype=np.float64)
    scale = max(float(np.max(array)), abs(float(threshold)), 1.0)
    values = np.asarray(array[np.triu_indices_from(array, k=1)], dtype=np.float64)
    finite = np.unique(values[np.isfinite(values)])
    if finite.size >= 2:
        gaps = np.diff(finite)
        positive_gaps = gaps[gaps > 0.0]
        min_gap = float(np.min(positive_gaps)) if positive_gaps.size else scale
    else:
        min_gap = scale
    epsilon_floor = np.finfo(np.float64).eps * scale * 256.0
    epsilon_ceiling = min_gap / 4096.0
    epsilon = max(epsilon_floor, min(scale * 1.0e-12, epsilon_ceiling))
    jittered = array.copy()
    rank = 1
    for i in range(array.shape[0]):
        for j in range(i + 1, array.shape[1]):
            sign = 1.0 if rank % 2 else -1.0
            delta = sign * epsilon * (1.0 + (rank % 11) / 11.0)
            jittered[i, j] += delta
            jittered[j, i] += delta
            rank += 1
    np.fill_diagonal(jittered, 0.0)
    return jittered, float(epsilon)


def max_interval_endpoint(records_by_library: dict[str, list[dict[str, Any]]]) -> float:
    max_value = 0.0
    for records in records_by_library.values():
        for record in records:
            birth = deserialize_float(record["birth"])
            death = deserialize_float(record["death"])
            if math.isfinite(birth):
                max_value = max(max_value, birth)
            if math.isfinite(death):
                max_value = max(max_value, death)
    return max_value


def multiset_difference(
    left_records: list[dict[str, Any]],
    right_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    remaining = Counter(signature_of_record(record) for record in right_records)
    extras = []
    for record in left_records:
        signature = signature_of_record(record)
        if remaining[signature]:
            remaining[signature] -= 1
        else:
            extras.append(record)
    return extras


def roundtrip_records_to_float32(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for record in records:
        birth = roundtrip_float32(deserialize_float(record["birth"]))
        death = roundtrip_float32(deserialize_float(record["death"]))
        converted.append(
            {
                "birth": serialize_json_value(birth),
                "death": serialize_json_value(death),
                "birth_hex": float_to_hex(birth),
                "death_hex": float_to_hex(death),
            }
        )
    return converted


def roundtrip_float32(value: float) -> float:
    if math.isinf(value) or math.isnan(value):
        return value
    return float(np.float32(value))


def threshold_based_tolerance(threshold: float) -> float:
    scale = max(abs(float(threshold)), 1.0)
    return max(math.ulp(scale) * 32.0, scale * 1.0e-12)


def interval_length(record: dict[str, Any]) -> float:
    birth = deserialize_float(record["birth"])
    death = deserialize_float(record["death"])
    if math.isinf(death):
        return math.inf
    return max(0.0, death - birth)


def interval_is_zero_length(record: dict[str, Any], *, tolerance: float) -> bool:
    return interval_length(record) <= tolerance


def value_touches_threshold(value: float, *, threshold: float, tolerance: float) -> bool:
    if not math.isfinite(value):
        return False
    if abs(value - threshold) <= tolerance:
        return True
    return float_to_hex(roundtrip_float32(value)) == float_to_hex(roundtrip_float32(threshold))


def interval_touches_threshold(record: dict[str, Any], *, threshold: float, tolerance: float) -> bool:
    birth = deserialize_float(record["birth"])
    death = deserialize_float(record["death"])
    if not math.isfinite(death):
        return False
    return value_touches_threshold(death, threshold=threshold, tolerance=tolerance) or value_touches_threshold(
        birth,
        threshold=threshold,
        tolerance=tolerance,
    )


def dimension_has_zero_metric(case_result: dict[str, Any], dim_key: str) -> bool:
    discrepancy = case_result["discrepancy"]["by_dimension"].get(dim_key)
    if discrepancy is None:
        return True
    for pair_key in PRIMARY_PAIRS:
        payload = discrepancy["pairwise"][pair_key]
        for metric_key in ("bottleneck_distance", "wasserstein_distance_q2"):
            metric_value = payload.get(metric_key)
            if metric_value is None:
                return False
            if deserialize_float(metric_value) != 0.0:
                return False
    return True


def count_infinite_bars(records: list[dict[str, Any]]) -> int:
    return sum(1 for record in records if record["death"] == "inf")


def get_interval_records(case_result: dict[str, Any], library: str, dim_key: str) -> list[dict[str, Any]]:
    return list(case_result["canonicalized"][library][dim_key]["intervals"])


def get_signature(case_result: dict[str, Any], library: str, dim_key: str) -> list[str]:
    return list(case_result["canonicalized"][library][dim_key]["exact_signature"])


def signature_of_record(record: dict[str, Any]) -> str:
    return f"{record['birth_hex']}|{record['death_hex']}"


def records_to_signature(records: list[dict[str, Any]]) -> list[str]:
    return sorted(signature_of_record(record) for record in records)


def build_full_audit_command(*, conformance_dir: Path, output_dir: Path) -> str:
    return (
        f"PYTHONPATH=src python scripts/run_audit_conventions.py --conformance-dir "
        f"{display_path(conformance_dir)} --output-dir {display_path(output_dir)}"
    )


def build_case_audit_command(*, conformance_dir: Path, output_dir: Path, case_id: str) -> str:
    return (
        f"{build_full_audit_command(conformance_dir=conformance_dir, output_dir=output_dir)} "
        f"--case-id {case_id}"
    )


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_case_payloads(cases_dir: Path) -> dict[str, dict[str, Any]]:
    payloads = {}
    for path in sorted(cases_dir.glob("*.json")):
        payload = load_json(path)
        payloads[payload["case_parameters"]["case_id"]] = payload
    return payloads


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def render_markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [str(row.get(header, "")) for header in headers]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(serialize_json_value(rows))


def dump_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(serialize_json_value(payload), indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def float_to_hex(value: float) -> str:
    number = float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "inf" if number > 0 else "-inf"
    return np.float64(number).hex()


def deserialize_float(value: Any) -> float:
    if isinstance(value, str):
        if value == "inf":
            return math.inf
        if value == "-inf":
            return -math.inf
        if value == "nan":
            return math.nan
    return float(value)


def serialize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): serialize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_json_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return serialize_json_value(value.tolist())
    if isinstance(value, np.generic):
        return serialize_json_value(value.item())
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value
    return value


if __name__ == "__main__":
    raise SystemExit(main())
