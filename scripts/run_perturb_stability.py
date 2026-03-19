from __future__ import annotations

import argparse
import os
import csv
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timezone
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
from ph_conformance.perturbation_stability import (  # noqa: E402
    COORDINATE_JITTER_MAGNITUDES,
    MATRIX_NOISE_MAGNITUDES,
    PAIRWISE_LIBRARY_PAIRS,
    QUANTIZATION_MAGNITUDES,
    RANDOM_SEEDS,
    SUMMARY_SCALAR_KEYS,
    VACANCY_COUNTS,
    betti_curve,
    betti_curve_distances,
    betti_grid_from_groups,
    build_persistence_image_config,
    build_perturbed_benchmarks,
    diagram_distance_metrics,
    diagram_pairs_from_case,
    diagram_scalar_summaries,
    hash_array,
    max_pairwise_spread,
    perturbed_benchmark_to_manifest,
    persistence_image_array,
    persistence_image_distance,
    scalar_summary_deltas,
    serialize_summary_value,
    summary_agreement,
)


TASK_ID = "PH-PERTURB-STABILITY-FULL-002"
DEFAULT_CONFORMANCE_DIR = REPO_ROOT / "artifacts"
DEFAULT_OUTPUT_DIR = DEFAULT_CONFORMANCE_DIR / "perturb_stability"
DIRECT_DISTRIBUTIONS = ("numpy", "scipy", "matplotlib", "persim", "gudhi", "ripser", "dionysus")
DIM_COLORS = {
    "0": "#1f77b4",
    "1": "#d62728",
    "2": "#2ca02c",
}
PERTURBATION_LABELS = {
    "coordinate_jitter": "Coordinate Jitter",
    "vacancy": "Vacancy",
    "matrix_entry_noise": "Matrix-Entry Noise",
    "quantization": "Quantization / Coarsening",
}
PERTURBATION_XLABELS = {
    "coordinate_jitter": "relative sigma",
    "vacancy": "deleted vertices",
    "matrix_entry_noise": "relative sigma",
    "quantization": "relative step",
}
PANEL_SPECS = (
    ("exact_agreement_rate", "Exact Agreement Rate"),
    ("bottleneck_to_baseline", "Bottleneck"),
    ("wasserstein_to_baseline", "Wasserstein q=2"),
    ("betti_l1_to_baseline", "Persistent Betti L1"),
    ("lifetime_l1_delta", "Lifetime L1 Delta"),
    ("lifetime_l2_delta", "Lifetime L2 Delta"),
    ("lifetime_linf_delta", "Lifetime L-inf Delta"),
    ("persistent_entropy_delta", "Entropy Delta"),
    ("persistence_image_l2_to_baseline", "Persistence Image L2"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the perturbation-stability sweep for the PH conformance harness.")
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
        help="Directory for PH-PERTURB-STABILITY-001 artifacts.",
    )
    parser.add_argument(
        "--benchmark-id",
        action="append",
        default=[],
        help="Optional source benchmark filter. May be specified multiple times.",
    )
    parser.add_argument(
        "--perturbation-family",
        action="append",
        default=[],
        choices=tuple(PERTURBATION_LABELS),
        help="Optional perturbation family filter. May be specified multiple times.",
    )
    parser.add_argument(
        "--limit-benchmarks",
        type=int,
        default=None,
        help="Optional limit after applying benchmark filters.",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip persistence-image summaries and plots.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(8, os.cpu_count() or 1)),
        help="Number of worker processes for case execution.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    conformance_dir = args.conformance_dir.resolve()
    output_dir = args.output_dir.resolve()
    family_filters = set(args.perturbation_family)
    benchmark_filters = set(args.benchmark_id)
    include_images = not args.skip_images

    ensure_dir(output_dir)
    ensure_dir(output_dir / "config")
    ensure_dir(output_dir / "environment")
    ensure_dir(output_dir / "inputs")
    ensure_dir(output_dir / "cases")
    ensure_dir(output_dir / "summary_objects")
    ensure_dir(output_dir / "summary")
    ensure_dir(output_dir / "plots")

    environment_snapshot = collect_environment_snapshot()
    write_text(output_dir / "environment" / "pip_freeze.txt", environment_snapshot["pip_freeze"])
    dump_json(output_dir / "environment" / "versions.json", environment_snapshot["versions"])

    baseline_catalog = load_baseline_catalog(conformance_dir)
    if benchmark_filters:
        baseline_catalog = [row for row in baseline_catalog if row["manifest"]["benchmark_id"] in benchmark_filters]
    if args.limit_benchmarks is not None:
        baseline_catalog = baseline_catalog[: args.limit_benchmarks]
    if not baseline_catalog:
        raise SystemExit("No baseline benchmarks matched the requested filters.")

    sweep_manifest = {
        "task_id": TASK_ID,
        "generated_at_utc": environment_snapshot["versions"]["generated_at_utc"],
        "conformance_dir": str(conformance_dir),
        "output_dir": str(output_dir),
        "random_seeds": list(RANDOM_SEEDS),
        "coordinate_jitter_magnitudes": list(COORDINATE_JITTER_MAGNITUDES),
        "vacancy_counts": list(VACANCY_COUNTS),
        "matrix_entry_noise_magnitudes": list(MATRIX_NOISE_MAGNITUDES),
        "quantization_magnitudes": list(QUANTIZATION_MAGNITUDES),
        "benchmark_filters": sorted(benchmark_filters),
        "perturbation_family_filters": sorted(family_filters),
        "include_persistence_images": include_images,
    }
    dump_json(output_dir / "config" / "sweep_manifest.json", sweep_manifest)

    baseline_case_payloads = load_case_payloads(conformance_dir / "cases")
    perturbed_benchmarks = []
    for baseline in baseline_catalog:
        benchmarks = build_perturbed_benchmarks(
            baseline["manifest"],
            baseline["distance_matrix"],
            baseline["point_cloud"],
        )
        if family_filters:
            benchmarks = [benchmark for benchmark in benchmarks if benchmark.perturbation["family"] in family_filters]
        for benchmark in benchmarks:
            save_perturbed_inputs(output_dir / "inputs", benchmark)
        perturbed_benchmarks.extend(benchmarks)

    perturbed_manifests = [perturbed_benchmark_to_manifest(benchmark) for benchmark in perturbed_benchmarks]
    dump_json(output_dir / "summary" / "perturbed_benchmarks.json", perturbed_manifests)

    case_index_rows: list[dict[str, Any]] = []
    case_specs: list[dict[str, Any]] = []
    for benchmark in perturbed_benchmarks:
        threshold_specs = [("selected", benchmark.selected_threshold), ("full", benchmark.full_threshold)]
        for coeff in benchmark.coeffs:
            for maxdim in benchmark.maxdims:
                for threshold_label, threshold_value in threshold_specs:
                    case_specs.append(
                        {
                            "benchmark": benchmark,
                            "coeff": coeff,
                            "maxdim": maxdim,
                            "threshold_label": threshold_label,
                            "threshold_value": threshold_value,
                        }
                    )

    if args.workers <= 1:
        executed_results = [execute_case_spec(spec) for spec in case_specs]
    else:
        executed_results = []
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_map = {executor.submit(execute_case_spec, spec): spec for spec in case_specs}
            for future in as_completed(future_map):
                executed_results.append(future.result())

    for executed in sorted(executed_results, key=lambda item: item["case_result"]["case_id"]):
        benchmark = executed["benchmark"]
        baseline_case_id = executed["baseline_case_id"]
        case_result = executed["case_result"]
        threshold_label = executed["threshold_label"]
        threshold_value = executed["threshold_value"]
        case_payload = build_case_payload(
            benchmark=benchmark,
            case_result=case_result,
            threshold_label=threshold_label,
            threshold_value=threshold_value,
            baseline_case_id=baseline_case_id,
        )
        dump_json(output_dir / "cases" / f"{case_result['case_id']}.json", case_payload)
        case_index_rows.append(build_case_index_row(case_payload))

    write_csv(output_dir / "summary" / "case_index.csv", case_index_rows)
    dump_json(output_dir / "summary" / "case_index.json", case_index_rows)

    perturbed_case_payloads = load_case_payloads(output_dir / "cases")
    group_configs = build_group_configs(
        perturbed_case_payloads=perturbed_case_payloads,
        baseline_case_payloads=baseline_case_payloads,
        include_images=include_images,
    )
    dump_json(output_dir / "summary" / "group_configs.json", group_configs)

    baseline_summary_cache = build_baseline_summary_cache(
        baseline_case_payloads=baseline_case_payloads,
        group_configs=group_configs,
        include_images=include_images,
    )

    summary_rows: list[dict[str, Any]] = []
    cross_library_rows: list[dict[str, Any]] = []
    highlight_rows: list[dict[str, Any]] = []

    for case_id in sorted(perturbed_case_payloads):
        case_payload = perturbed_case_payloads[case_id]
        case_summary, case_rows, cross_rows = summarize_case_from_saved_diagrams(
            case_payload=case_payload,
            baseline_case_payloads=baseline_case_payloads,
            baseline_summary_cache=baseline_summary_cache,
            group_configs=group_configs,
            include_images=include_images,
        )
        dump_json(output_dir / "summary_objects" / f"{case_id}.json", case_summary)
        summary_rows.extend(case_rows)
        cross_library_rows.extend(cross_rows)
        highlight_rows.extend(
            [row for row in cross_rows if (not row["exact_all_libraries"]) and row["agreeing_summary_keys"]]
        )

    write_csv(output_dir / "summary" / "diagram_summary_statistics.csv", summary_rows)
    dump_json(output_dir / "summary" / "diagram_summary_statistics.json", summary_rows)
    write_csv(output_dir / "summary" / "cross_library_summary_agreement.csv", cross_library_rows)
    dump_json(output_dir / "summary" / "cross_library_summary_agreement.json", cross_library_rows)
    write_csv(output_dir / "summary" / "exact_disagreement_summary_agreement.csv", highlight_rows)
    dump_json(output_dir / "summary" / "exact_disagreement_summary_agreement.json", highlight_rows)
    write_csv(output_dir / "diagram_summary_statistics.csv", summary_rows)
    dump_json(output_dir / "diagram_summary_statistics.json", summary_rows)
    write_csv(output_dir / "cross_library_summary_agreement.csv", cross_library_rows)
    dump_json(output_dir / "cross_library_summary_agreement.json", cross_library_rows)
    write_csv(output_dir / "exact_disagreement_summary_agreement.csv", highlight_rows)
    dump_json(output_dir / "exact_disagreement_summary_agreement.json", highlight_rows)

    aggregate_rows = build_aggregate_rows(
        baseline_case_payloads=baseline_case_payloads,
        baseline_catalog=baseline_catalog,
        case_index_rows=case_index_rows,
        summary_rows=summary_rows,
        cross_library_rows=cross_library_rows,
        family_filters=family_filters,
        include_images=include_images,
    )
    write_csv(output_dir / "summary" / "aggregate_curves.csv", aggregate_rows)
    dump_json(output_dir / "summary" / "aggregate_curves.json", aggregate_rows)
    write_csv(output_dir / "aggregate_curves.csv", aggregate_rows)
    dump_json(output_dir / "aggregate_curves.json", aggregate_rows)

    plot_rows = [row for row in aggregate_rows if include_images or row["statistic"] != "persistence_image_l2_to_baseline"]
    plot_paths = write_plots(
        aggregate_rows=plot_rows,
        baseline_catalog=baseline_catalog,
        output_dir=output_dir,
        include_images=include_images,
    )
    dump_json(output_dir / "summary" / "plot_index.json", plot_paths)
    dump_json(output_dir / "plot_index.json", plot_paths)

    overall_summary = build_overall_summary(
        baseline_catalog=baseline_catalog,
        case_index_rows=case_index_rows,
        cross_library_rows=cross_library_rows,
        highlight_rows=highlight_rows,
    )
    dump_json(output_dir / "summary" / "overall_summary.json", overall_summary)
    dump_json(output_dir / "overall_summary.json", overall_summary)

    report_text = render_report(
        environment_snapshot=environment_snapshot["versions"],
        sweep_manifest=sweep_manifest,
        baseline_catalog=baseline_catalog,
        overall_summary=overall_summary,
        cross_library_rows=cross_library_rows,
        highlight_rows=highlight_rows,
        aggregate_rows=plot_rows,
        plot_paths=plot_paths,
        include_images=include_images,
    )
    write_text(output_dir / "report.md", report_text)
    return 0


def collect_environment_snapshot() -> dict[str, Any]:
    versions = {
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "distributions": {
            distribution: importlib.metadata.version(distribution)
            for distribution in DIRECT_DISTRIBUTIONS
        },
    }
    pip_freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {"versions": versions, "pip_freeze": pip_freeze}


def load_baseline_catalog(conformance_dir: Path) -> list[dict[str, Any]]:
    manifests = load_json(conformance_dir / "summary" / "benchmarks.json")
    catalog = []
    for manifest in manifests:
        benchmark_id = manifest["benchmark_id"]
        input_dir = conformance_dir / "inputs" / benchmark_id
        distance_matrix = np.load(input_dir / "distance_matrix.npy")
        point_cloud_path = input_dir / "point_cloud.npy"
        point_cloud = np.load(point_cloud_path) if point_cloud_path.exists() else None
        if manifest["metadata"]["distance_matrix_hash"] != hash_array(distance_matrix):
            raise ValueError(f"Distance-matrix hash mismatch for {benchmark_id}")
        if point_cloud is not None and manifest["metadata"]["point_cloud_hash"] != hash_array(point_cloud):
            raise ValueError(f"Point-cloud hash mismatch for {benchmark_id}")
        catalog.append(
            {
                "manifest": manifest,
                "distance_matrix": distance_matrix,
                "point_cloud": point_cloud,
            }
        )
    return catalog


def save_perturbed_inputs(base_dir: Path, benchmark: Any) -> None:
    benchmark_dir = base_dir / benchmark.benchmark_id
    ensure_dir(benchmark_dir)
    np.save(benchmark_dir / "distance_matrix.npy", np.asarray(benchmark.distance_matrix, dtype=np.float64))
    np.savetxt(benchmark_dir / "distance_matrix.csv", np.asarray(benchmark.distance_matrix, dtype=np.float64), delimiter=",", fmt="%.17g")
    if benchmark.point_cloud is not None:
        np.save(benchmark_dir / "point_cloud.npy", np.asarray(benchmark.point_cloud, dtype=np.float64))
        np.savetxt(benchmark_dir / "point_cloud.csv", np.asarray(benchmark.point_cloud, dtype=np.float64), delimiter=",", fmt="%.17g")
    dump_json(benchmark_dir / "manifest.json", perturbed_benchmark_to_manifest(benchmark))


def build_case_payload(
    *,
    benchmark: Any,
    case_result: dict[str, Any],
    threshold_label: str,
    threshold_value: float,
    baseline_case_id: str,
) -> dict[str, Any]:
    benchmark_manifest = perturbed_benchmark_to_manifest(benchmark)
    return {
        "task_id": TASK_ID,
        "benchmark": benchmark_manifest,
        "case_parameters": {
            "case_id": case_result["case_id"],
            "coeff": case_result["coeff"],
            "maxdim": case_result["maxdim"],
            "threshold_label": threshold_label,
            "threshold_value": threshold_value,
            "baseline_case_id": baseline_case_id,
        },
        "inputs": {
            "distance_matrix_hash": benchmark.metadata["distance_matrix_hash"],
            "point_cloud_hash": benchmark.metadata["point_cloud_hash"],
            "source_distance_matrix_hash": benchmark.metadata["source_distance_matrix_hash"],
            "source_point_cloud_hash": benchmark.metadata["source_point_cloud_hash"],
            "distance_matrix_shape": list(benchmark.distance_matrix.shape),
            "point_cloud_shape": None if benchmark.point_cloud is None else list(benchmark.point_cloud.shape),
        },
        "results": case_result,
    }


def execute_case_spec(spec: dict[str, Any]) -> dict[str, Any]:
    benchmark = spec["benchmark"]
    coeff = int(spec["coeff"])
    maxdim = int(spec["maxdim"])
    threshold_label = str(spec["threshold_label"])
    threshold_value = float(spec["threshold_value"])
    case_id = f"{benchmark.benchmark_id}__p{coeff}__h{maxdim}__{threshold_label}"
    baseline_case_id = f"{benchmark.source_benchmark_id}__p{coeff}__h{maxdim}__{threshold_label}"
    case_result = run_case(
        benchmark.distance_matrix,
        coeff=coeff,
        maxdim=maxdim,
        threshold=threshold_value,
        case_id=case_id,
    )
    return {
        "benchmark": benchmark,
        "baseline_case_id": baseline_case_id,
        "threshold_label": threshold_label,
        "threshold_value": threshold_value,
        "case_result": case_result,
    }


def build_case_index_row(case_payload: dict[str, Any]) -> dict[str, Any]:
    benchmark = case_payload["benchmark"]
    parameters = case_payload["case_parameters"]
    perturbation = benchmark["perturbation"]
    return {
        "case_id": parameters["case_id"],
        "benchmark_id": benchmark["benchmark_id"],
        "source_benchmark_id": benchmark["source_benchmark_id"],
        "label": benchmark["label"],
        "mode": benchmark["mode"],
        "family": benchmark["family"],
        "perturbation_family": perturbation["family"],
        "perturbation_magnitude": perturbation["magnitude"],
        "perturbation_seed": perturbation.get("seed"),
        "coeff": parameters["coeff"],
        "maxdim": parameters["maxdim"],
        "threshold_label": parameters["threshold_label"],
        "threshold_value": parameters["threshold_value"],
        "baseline_case_id": parameters["baseline_case_id"],
    }


def load_case_payloads(case_dir: Path) -> dict[str, dict[str, Any]]:
    payloads = {}
    for path in sorted(case_dir.glob("*.json")):
        payloads[path.stem] = load_json(path)
    return payloads


def build_group_key(case_payload: dict[str, Any], dim: int) -> str:
    benchmark = case_payload["benchmark"]
    parameters = case_payload["case_parameters"]
    source_benchmark_id = benchmark.get("source_benchmark_id", benchmark["benchmark_id"])
    return "|".join(
        [
            source_benchmark_id,
            f"p{parameters['coeff']}",
            f"h{parameters['maxdim']}",
            parameters["threshold_label"],
            f"d{dim}",
        ]
    )


def build_group_configs(
    *,
    perturbed_case_payloads: dict[str, dict[str, Any]],
    baseline_case_payloads: dict[str, dict[str, Any]],
    include_images: bool,
) -> dict[str, dict[str, Any]]:
    grouped_pairs: dict[str, list[list[list[float]]]] = defaultdict(list)
    grouped_thresholds: dict[str, list[float]] = defaultdict(list)

    for case_payload in perturbed_case_payloads.values():
        baseline_case_id = case_payload["case_parameters"]["baseline_case_id"]
        baseline_case_payload = baseline_case_payloads[baseline_case_id]
        maxdim = int(case_payload["case_parameters"]["maxdim"])
        threshold_value = float(case_payload["case_parameters"]["threshold_value"])
        baseline_threshold = float(baseline_case_payload["case_parameters"]["threshold_value"])
        for dim in range(maxdim + 1):
            group_key = build_group_key(case_payload, dim)
            grouped_thresholds[group_key].extend([threshold_value, baseline_threshold])
            for payload in (baseline_case_payload, case_payload):
                for library in LIBRARIES:
                    grouped_pairs[group_key].append(diagram_pairs_from_case(payload, library, dim))

    configs: dict[str, dict[str, Any]] = {}
    for group_key, pairs_collection in grouped_pairs.items():
        betti_grid = betti_grid_from_groups(pairs_collection, grouped_thresholds[group_key])
        config: dict[str, Any] = {
            "betti_grid": betti_grid.tolist(),
            "betti_horizon": float(betti_grid[-1]),
        }
        if include_images:
            config["persistence_image"] = build_persistence_image_config(pairs_collection)
        configs[group_key] = config
    return configs


def build_baseline_summary_cache(
    *,
    baseline_case_payloads: dict[str, dict[str, Any]],
    group_configs: dict[str, dict[str, Any]],
    include_images: bool,
) -> dict[tuple[str, str, int], dict[str, Any]]:
    cache: dict[tuple[str, str, int], dict[str, Any]] = {}
    for case_id, case_payload in baseline_case_payloads.items():
        maxdim = int(case_payload["case_parameters"]["maxdim"])
        for library in LIBRARIES:
            for dim in range(maxdim + 1):
                group_key = build_group_key(case_payload, dim)
                config = group_configs.get(group_key)
                if config is None:
                    continue
                grid = np.asarray(config["betti_grid"], dtype=np.float64)
                pairs = diagram_pairs_from_case(case_payload, library, dim)
                scalar_summary = diagram_scalar_summaries(pairs)
                betti_values = betti_curve(pairs, grid)
                summary: dict[str, Any] = {
                    "scalar_summary": scalar_summary,
                    "betti_grid": grid,
                    "betti_curve": betti_values,
                }
                if include_images:
                    image_config = config["persistence_image"]
                    summary["persistence_image"] = persistence_image_array(pairs, image_config)
                cache[(case_id, library, dim)] = summary
    return cache


def summarize_case_from_saved_diagrams(
    *,
    case_payload: dict[str, Any],
    baseline_case_payloads: dict[str, dict[str, Any]],
    baseline_summary_cache: dict[tuple[str, str, int], dict[str, Any]],
    group_configs: dict[str, dict[str, Any]],
    include_images: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    benchmark = case_payload["benchmark"]
    parameters = case_payload["case_parameters"]
    perturbation = benchmark["perturbation"]
    mode = benchmark["mode"]
    baseline_case_id = parameters["baseline_case_id"]
    baseline_case_payload = baseline_case_payloads[baseline_case_id]
    maxdim = int(parameters["maxdim"])

    library_dimension_payloads: dict[str, dict[str, Any]] = {}
    summary_rows: list[dict[str, Any]] = []
    cross_library_rows: list[dict[str, Any]] = []

    for library in LIBRARIES:
        by_dimension: dict[str, Any] = {}
        for dim in range(maxdim + 1):
            group_key = build_group_key(case_payload, dim)
            config = group_configs[group_key]
            betti_grid = np.asarray(config["betti_grid"], dtype=np.float64)
            pairs = diagram_pairs_from_case(case_payload, library, dim)
            baseline_pairs = diagram_pairs_from_case(baseline_case_payload, library, dim)
            scalar_summary = diagram_scalar_summaries(pairs)
            baseline_summary = baseline_summary_cache[(baseline_case_id, library, dim)]
            distance_metrics = diagram_distance_metrics(baseline_pairs, pairs)
            betti_values = betti_curve(pairs, betti_grid)
            betti_distances = betti_curve_distances(betti_values, baseline_summary["betti_curve"], betti_grid)
            scalar_deltas = scalar_summary_deltas(scalar_summary, baseline_summary["scalar_summary"])
            persistence_image_l2_to_baseline = None
            persistence_image = None
            if include_images:
                image_config = config["persistence_image"]
                persistence_image = persistence_image_array(pairs, image_config)
                persistence_image_l2_to_baseline = persistence_image_distance(
                    persistence_image,
                    baseline_summary["persistence_image"],
                )
            dimension_payload = {
                "pairs": pairs,
                "scalar_summary": scalar_summary,
                "diagram_distances": distance_metrics,
                "betti_grid": betti_grid,
                "betti_curve": betti_values,
                "betti_distances": betti_distances,
                "scalar_deltas": scalar_deltas,
                "persistence_image_l2_to_baseline": persistence_image_l2_to_baseline,
            }
            if include_images:
                dimension_payload["persistence_image_shape"] = list(np.asarray(persistence_image).shape)
            by_dimension[str(dim)] = dimension_payload

            row = {
                "case_id": parameters["case_id"],
                "benchmark_id": benchmark["benchmark_id"],
                "source_benchmark_id": benchmark["source_benchmark_id"],
                "label": benchmark["label"],
                "mode": benchmark["mode"],
                "family": benchmark["family"],
                "perturbation_family": perturbation["family"],
                "perturbation_magnitude": perturbation["magnitude"],
                "perturbation_seed": perturbation.get("seed"),
                "coeff": parameters["coeff"],
                "maxdim": parameters["maxdim"],
                "threshold_label": parameters["threshold_label"],
                "threshold_value": parameters["threshold_value"],
                "baseline_case_id": baseline_case_id,
                "library": library,
                "dimension": dim,
                "bar_count": scalar_summary["bar_count"],
                "finite_bar_count": scalar_summary["finite_bar_count"],
                "essential_bar_count": scalar_summary["essential_bar_count"],
                "lifetime_l1": scalar_summary["lifetime_l1"],
                "lifetime_l2": scalar_summary["lifetime_l2"],
                "lifetime_linf": scalar_summary["lifetime_linf"],
                "persistent_entropy": scalar_summary["persistent_entropy"],
                "bottleneck_to_baseline": distance_metrics["bottleneck_to_baseline"],
                "wasserstein_to_baseline": distance_metrics["wasserstein_to_baseline"],
                "betti_l1_to_baseline": betti_distances["betti_l1_to_baseline"],
                "betti_linf_to_baseline": betti_distances["betti_linf_to_baseline"],
                "lifetime_l1_delta": scalar_deltas["lifetime_l1_delta"],
                "lifetime_l2_delta": scalar_deltas["lifetime_l2_delta"],
                "lifetime_linf_delta": scalar_deltas["lifetime_linf_delta"],
                "persistent_entropy_delta": scalar_deltas["persistent_entropy_delta"],
                "persistence_image_l2_to_baseline": persistence_image_l2_to_baseline,
                "betti_grid": betti_grid.tolist(),
                "betti_curve": betti_values.tolist(),
            }
            summary_rows.append(row)
        library_dimension_payloads[library] = by_dimension

    for dim in range(maxdim + 1):
        dim_key = str(dim)
        agreement_payload = case_payload["results"]["agreement"]["by_dimension"][dim_key]
        row: dict[str, Any] = {
            "case_id": parameters["case_id"],
            "benchmark_id": benchmark["benchmark_id"],
            "source_benchmark_id": benchmark["source_benchmark_id"],
            "label": benchmark["label"],
            "mode": benchmark["mode"],
            "family": benchmark["family"],
            "perturbation_family": perturbation["family"],
            "perturbation_magnitude": perturbation["magnitude"],
            "perturbation_seed": perturbation.get("seed"),
            "coeff": parameters["coeff"],
            "maxdim": parameters["maxdim"],
            "threshold_label": parameters["threshold_label"],
            "dimension": dim,
            "exact_all_libraries": agreement_payload["exact_all_libraries"],
        }
        agreeing_summary_keys = []
        for summary_key in SUMMARY_SCALAR_KEYS:
            values = {
                library: library_dimension_payloads[library][dim_key].get(summary_key)
                if summary_key in library_dimension_payloads[library][dim_key]
                else (
                    library_dimension_payloads[library][dim_key]["diagram_distances"].get(summary_key)
                    if summary_key in library_dimension_payloads[library][dim_key]["diagram_distances"]
                    else (
                        library_dimension_payloads[library][dim_key]["betti_distances"].get(summary_key)
                        if summary_key in library_dimension_payloads[library][dim_key]["betti_distances"]
                        else (
                            library_dimension_payloads[library][dim_key]["scalar_deltas"].get(summary_key)
                            if summary_key in library_dimension_payloads[library][dim_key]["scalar_deltas"]
                            else library_dimension_payloads[library][dim_key].get(summary_key)
                        )
                    )
                )
                for library in LIBRARIES
            }
            row[f"{summary_key}_spread"] = max_pairwise_spread(values)
            row[f"{summary_key}_all_libraries_agree"] = all(
                summary_agreement(values[left], values[right], mode=mode)
                for left, right in PAIRWISE_LIBRARY_PAIRS
            )
            if row[f"{summary_key}_all_libraries_agree"]:
                agreeing_summary_keys.append(summary_key)

        betti_curves = {library: library_dimension_payloads[library][dim_key]["betti_curve"] for library in LIBRARIES}
        row["betti_curve_exact_agreement"] = all(
            np.array_equal(betti_curves[left], betti_curves[right]) for left, right in PAIRWISE_LIBRARY_PAIRS
        )
        if row["betti_curve_exact_agreement"]:
            agreeing_summary_keys.append("betti_curve")
        row["agreeing_summary_keys"] = ",".join(agreeing_summary_keys)
        row["agreeing_summary_key_count"] = len(agreeing_summary_keys)
        cross_library_rows.append(row)

    case_summary = {
        "task_id": TASK_ID,
        "benchmark": benchmark,
        "case_parameters": parameters,
        "library_summaries": library_dimension_payloads,
        "cross_library_summary_agreement": cross_library_rows,
    }
    return serialize_summary_value(case_summary), serialize_summary_value(summary_rows), serialize_summary_value(cross_library_rows)


def build_aggregate_rows(
    *,
    baseline_case_payloads: dict[str, dict[str, Any]],
    baseline_catalog: list[dict[str, Any]],
    case_index_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    cross_library_rows: list[dict[str, Any]],
    family_filters: set[str],
    include_images: bool,
) -> list[dict[str, Any]]:
    applicable_families: dict[str, set[str]] = defaultdict(set)
    for row in case_index_rows:
        applicable_families[row["source_benchmark_id"]].add(row["perturbation_family"])

    rows: list[dict[str, Any]] = []
    grouped_exact: dict[tuple[str, str, int, float], list[dict[str, Any]]] = defaultdict(list)
    for row in cross_library_rows:
        key = (
            row["source_benchmark_id"],
            row["perturbation_family"],
            int(row["dimension"]),
            float(row["perturbation_magnitude"]),
        )
        grouped_exact[key].append(row)

    grouped_summary: dict[tuple[str, str, int, float, str], list[float]] = defaultdict(list)
    for row in summary_rows:
        for statistic in SUMMARY_SCALAR_KEYS:
            if not include_images and statistic == "persistence_image_l2_to_baseline":
                continue
            value = row.get(statistic)
            if value is None:
                continue
            key = (
                row["source_benchmark_id"],
                row["perturbation_family"],
                int(row["dimension"]),
                float(row["perturbation_magnitude"]),
                statistic,
            )
            grouped_summary[key].append(float(value))

    for (source_benchmark_id, perturbation_family, dimension, magnitude), exact_rows in grouped_exact.items():
        rows.append(
            {
                "source_benchmark_id": source_benchmark_id,
                "perturbation_family": perturbation_family,
                "dimension": dimension,
                "magnitude": magnitude,
                "statistic": "exact_agreement_rate",
                "value": float(np.mean([1.0 if row["exact_all_libraries"] else 0.0 for row in exact_rows])),
                "count": len(exact_rows),
            }
        )

    for key, values in grouped_summary.items():
        source_benchmark_id, perturbation_family, dimension, magnitude, statistic = key
        rows.append(
            {
                "source_benchmark_id": source_benchmark_id,
                "perturbation_family": perturbation_family,
                "dimension": dimension,
                "magnitude": magnitude,
                "statistic": statistic,
                "value": float(np.median(values)),
                "count": len(values),
            }
        )

    baseline_families = family_filters or set(PERTURBATION_LABELS)
    baseline_manifests = {row["manifest"]["benchmark_id"]: row["manifest"] for row in baseline_catalog}
    for benchmark_id, manifest in baseline_manifests.items():
        families = applicable_families.get(benchmark_id, set()) & baseline_families
        maxdims = tuple(int(value) for value in manifest["maxdims"])
        coeffs = tuple(int(value) for value in manifest["coeffs"])
        for perturbation_family in sorted(families):
            for dim in range(max(maxdims) + 1):
                exact_records = []
                for coeff in coeffs:
                    for maxdim in maxdims:
                        if dim > maxdim:
                            continue
                        for threshold_label in ("selected", "full"):
                            baseline_case_id = f"{benchmark_id}__p{coeff}__h{maxdim}__{threshold_label}"
                            baseline_case_payload = baseline_case_payloads[baseline_case_id]
                            exact_records.append(
                                1.0
                                if baseline_case_payload["results"]["agreement"]["by_dimension"][str(dim)]["exact_all_libraries"]
                                else 0.0
                            )
                if exact_records:
                    rows.append(
                        {
                            "source_benchmark_id": benchmark_id,
                            "perturbation_family": perturbation_family,
                            "dimension": dim,
                            "magnitude": 0.0,
                            "statistic": "exact_agreement_rate",
                            "value": float(np.mean(exact_records)),
                            "count": len(exact_records),
                        }
                    )
                for statistic in SUMMARY_SCALAR_KEYS:
                    if not include_images and statistic == "persistence_image_l2_to_baseline":
                        continue
                    rows.append(
                        {
                            "source_benchmark_id": benchmark_id,
                            "perturbation_family": perturbation_family,
                            "dimension": dim,
                            "magnitude": 0.0,
                            "statistic": statistic,
                            "value": 0.0,
                            "count": len(exact_records),
                        }
                    )

    rows.sort(key=lambda row: (row["source_benchmark_id"], row["perturbation_family"], row["statistic"], row["dimension"], row["magnitude"]))
    return rows


def write_plots(
    *,
    aggregate_rows: list[dict[str, Any]],
    baseline_catalog: list[dict[str, Any]],
    output_dir: Path,
    include_images: bool,
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in aggregate_rows:
        rows_by_key[(row["source_benchmark_id"], row["perturbation_family"])].append(row)

    benchmark_lookup = {row["manifest"]["benchmark_id"]: row["manifest"] for row in baseline_catalog}
    plot_index_rows: list[dict[str, Any]] = []
    panel_specs = PANEL_SPECS if include_images else tuple(spec for spec in PANEL_SPECS if spec[0] != "persistence_image_l2_to_baseline")

    for (source_benchmark_id, perturbation_family), rows in sorted(rows_by_key.items()):
        manifest = benchmark_lookup[source_benchmark_id]
        figure_path = output_dir / "plots" / source_benchmark_id / f"{perturbation_family}.png"
        ensure_dir(figure_path.parent)

        fig, axes = plt.subplots(3, 3, figsize=(14, 10), constrained_layout=True)
        axes_flat = axes.flatten()
        for axis in axes_flat:
            axis.set_visible(False)

        for axis, (statistic, title) in zip(axes_flat, panel_specs):
            axis.set_visible(True)
            statistic_rows = [row for row in rows if row["statistic"] == statistic]
            if not statistic_rows:
                axis.text(0.5, 0.5, "n/a", ha="center", va="center")
                axis.set_title(title)
                continue
            for dim in sorted({int(row["dimension"]) for row in statistic_rows}):
                dim_rows = sorted(
                    [row for row in statistic_rows if int(row["dimension"]) == dim],
                    key=lambda row: float(row["magnitude"]),
                )
                x = [float(row["magnitude"]) for row in dim_rows]
                y = [float(row["value"]) for row in dim_rows]
                axis.plot(x, y, marker="o", linewidth=1.8, color=DIM_COLORS[str(dim)], label=f"H{dim}")
            axis.set_title(title)
            axis.set_xlabel(PERTURBATION_XLABELS[perturbation_family])
            axis.grid(alpha=0.25)
            if statistic == "exact_agreement_rate":
                axis.set_ylim(-0.05, 1.05)

        visible_axes = [axis for axis in axes_flat if axis.get_visible()]
        if visible_axes:
            handles, labels = visible_axes[0].get_legend_handles_labels()
            if handles:
                fig.legend(handles, labels, loc="upper center", ncols=3, frameon=False)
        fig.suptitle(f"{manifest['label']} [{source_benchmark_id}] - {PERTURBATION_LABELS[perturbation_family]}", fontsize=12)
        fig.savefig(figure_path, dpi=160)
        plt.close(fig)

        plot_index_rows.append(
            {
                "source_benchmark_id": source_benchmark_id,
                "perturbation_family": perturbation_family,
                "plot_path": str(figure_path.relative_to(output_dir)),
            }
        )
    return plot_index_rows


def build_overall_summary(
    *,
    baseline_catalog: list[dict[str, Any]],
    case_index_rows: list[dict[str, Any]],
    cross_library_rows: list[dict[str, Any]],
    highlight_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    benchmark_count = len(baseline_catalog)
    perturbed_case_count = len(case_index_rows)
    exact_disagreement_count = sum(1 for row in cross_library_rows if not row["exact_all_libraries"])
    family_counts = defaultdict(int)
    family_highlights = defaultdict(int)
    summary_key_highlight_counts = defaultdict(int)

    for row in case_index_rows:
        family_counts[row["perturbation_family"]] += 1
    for row in highlight_rows:
        family_highlights[row["perturbation_family"]] += 1
        for key in row["agreeing_summary_keys"].split(","):
            if key:
                summary_key_highlight_counts[key] += 1

    return {
        "task_id": TASK_ID,
        "benchmark_count": benchmark_count,
        "perturbed_case_count": perturbed_case_count,
        "dimension_record_count": len(cross_library_rows),
        "exact_disagreement_dimension_records": exact_disagreement_count,
        "exact_disagreement_with_downstream_agreement_records": len(highlight_rows),
        "family_case_counts": dict(sorted(family_counts.items())),
        "family_highlight_counts": dict(sorted(family_highlights.items())),
        "summary_key_highlight_counts": dict(sorted(summary_key_highlight_counts.items())),
    }


def render_report(
    *,
    environment_snapshot: dict[str, Any],
    sweep_manifest: dict[str, Any],
    baseline_catalog: list[dict[str, Any]],
    overall_summary: dict[str, Any],
    cross_library_rows: list[dict[str, Any]],
    highlight_rows: list[dict[str, Any]],
    aggregate_rows: list[dict[str, Any]],
    plot_paths: list[dict[str, Any]],
    include_images: bool,
) -> str:
    lines = [
        f"# {TASK_ID}",
        "",
        "## setup",
        f"- Generated at UTC: {environment_snapshot['generated_at_utc']}",
        f"- Python: `{environment_snapshot['python_version'].splitlines()[0]}`",
        f"- Platform: `{environment_snapshot['platform']}`",
        f"- Baseline conformance directory: `{sweep_manifest['conformance_dir']}`",
        f"- Output directory: `{sweep_manifest['output_dir']}`",
        f"- Random seeds: `{', '.join(str(seed) for seed in sweep_manifest['random_seeds'])}`",
        f"- Coordinate-jitter grid: `{sweep_manifest['coordinate_jitter_magnitudes']}`",
        f"- Vacancy grid: `{sweep_manifest['vacancy_counts']}` deleted vertices",
        f"- Matrix-noise grid: `{sweep_manifest['matrix_entry_noise_magnitudes']}`",
        f"- Quantization grid: `{sweep_manifest['quantization_magnitudes']}`",
        f"- Persistence images included: `{sweep_manifest['include_persistence_images']}`",
        "- Approximation modes: `none`",
        "- Key distributions:",
    ]
    for distribution, version in environment_snapshot["distributions"].items():
        lines.append(f"  - `{distribution}=={version}`")

    lines.extend(
        [
            "",
            "## overall summary",
            f"- Benchmarks swept: `{overall_summary['benchmark_count']}`",
            f"- Perturbed case runs: `{overall_summary['perturbed_case_count']}`",
            f"- Dimension records analyzed: `{overall_summary['dimension_record_count']}`",
            f"- Exact disagreement dimension records: `{overall_summary['exact_disagreement_dimension_records']}`",
            f"- Exact disagreement records with at least one agreeing downstream summary: `{overall_summary['exact_disagreement_with_downstream_agreement_records']}`",
            "",
            render_markdown_table(
                [
                    {
                        "perturbation_family": family,
                        "case_runs": count,
                        "highlight_records": overall_summary["family_highlight_counts"].get(family, 0),
                    }
                    for family, count in overall_summary["family_case_counts"].items()
                ]
            ),
            "",
            "## downstream-summary highlights",
        ]
    )

    if highlight_rows:
        highlight_preview = [
            {
                "case_id": row["case_id"],
                "dimension": row["dimension"],
                "family": row["perturbation_family"],
                "magnitude": row["perturbation_magnitude"],
                "summary_keys": row["agreeing_summary_keys"],
            }
            for row in highlight_rows[:30]
        ]
        lines.append("")
        lines.append(render_markdown_table(highlight_preview))
    else:
        lines.append("")
        lines.append("No perturbed cases produced exact interval disagreements with downstream-summary agreement.")

    plot_lookup = {(row["source_benchmark_id"], row["perturbation_family"]): row["plot_path"] for row in plot_paths}
    aggregate_lookup: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in aggregate_rows:
        aggregate_lookup[(row["source_benchmark_id"], row["perturbation_family"])].append(row)

    lines.extend(["", "## benchmark-by-benchmark report"])
    for baseline in baseline_catalog:
        manifest = baseline["manifest"]
        benchmark_id = manifest["benchmark_id"]
        families = sorted({row["perturbation_family"] for row in cross_library_rows if row["source_benchmark_id"] == benchmark_id})
        lines.extend(
            [
                "",
                f"### {manifest['label']} [{benchmark_id}]",
                "",
            ]
        )
        if not families:
            lines.append("No perturbation families were run for this benchmark.")
            continue
        family_rows = []
        for family in families:
            family_records = [
                row
                for row in cross_library_rows
                if row["source_benchmark_id"] == benchmark_id and row["perturbation_family"] == family
            ]
            exact_rate_values = [
                row["value"]
                for row in aggregate_lookup[(benchmark_id, family)]
                if row["statistic"] == "exact_agreement_rate"
            ]
            family_rows.append(
                {
                    "perturbation_family": family,
                    "dimension_records": len(family_records),
                    "exact_rate_min": f"{min(exact_rate_values):.3f}" if exact_rate_values else "n/a",
                    "exact_rate_max": f"{max(exact_rate_values):.3f}" if exact_rate_values else "n/a",
                    "downstream_agreement_highlights": sum(
                        1 for row in highlight_rows if row["source_benchmark_id"] == benchmark_id and row["perturbation_family"] == family
                    ),
                }
            )
        lines.append(render_markdown_table(family_rows))
        for family in families:
            lines.extend(
                [
                    "",
                    f"#### {PERTURBATION_LABELS[family]}",
                    "",
                ]
            )
            plot_path = plot_lookup.get((benchmark_id, family))
            if plot_path is not None:
                lines.append(f"![{benchmark_id}-{family}]({plot_path})")
            else:
                lines.append("_No plot available._")

    lines.extend(
        [
            "",
            "## reproducibility notes",
            "- Recompute the saved baseline runs with `make run`.",
            "- Recompute this sweep with `make perturb-stability`.",
            "- The full sweep manifest is saved in `artifacts/perturb_stability/config/sweep_manifest.json`.",
            "- Raw perturbed inputs are saved under `artifacts/perturb_stability/inputs/`.",
            "- Raw diagrams and exact-agreement payloads are saved under `artifacts/perturb_stability/cases/`.",
            "- Summary statistics derived from saved diagrams are saved under `artifacts/perturb_stability/summary/` and `artifacts/perturb_stability/summary_objects/`.",
            "- Each perturbed case records its baseline case id, perturbation seed, and full parameter tuple.",
        ]
    )
    if include_images:
        lines.append("- Persistence-image summaries use fixed per-group image settings saved in `artifacts/perturb_stability/summary/group_configs.json`.")
    lines.append("")
    return "\n".join(lines)


def render_markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [escape_markdown(str(row.get(header, ""))) for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
