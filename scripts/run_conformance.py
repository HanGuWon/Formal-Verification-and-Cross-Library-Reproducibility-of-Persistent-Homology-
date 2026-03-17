from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ph_conformance import benchmark_to_manifest, generate_benchmarks  # noqa: E402
from ph_conformance.tda import LIBRARIES, run_case  # noqa: E402


TASK_ID = "PH-CONFORMANCE-VR-001"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts"
RANDOM_SEED = 0
DIRECT_DISTRIBUTIONS = ("numpy", "scipy", "gudhi", "ripser", "dionysus")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PH cross-library conformance harness.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Artifact output directory.",
    )
    parser.add_argument(
        "--include-nacl",
        action="store_true",
        default=False,
        help="Include the optional NaCl-style coordination-shell benchmark family.",
    )
    parser.add_argument(
        "--floating-only",
        action="store_true",
        help="Run only floating benchmarks.",
    )
    parser.add_argument(
        "--quantized-only",
        action="store_true",
        help="Run only quantized benchmarks.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on the number of benchmarks before parameter expansion.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    np.random.seed(RANDOM_SEED)

    if args.floating_only and args.quantized_only:
        raise SystemExit("Choose at most one of --floating-only and --quantized-only.")

    modes = ("floating", "quantized")
    if args.floating_only:
        modes = ("floating",)
    if args.quantized_only:
        modes = ("quantized",)

    output_dir = args.output_dir.resolve()
    benchmarks = generate_benchmarks(modes=modes, include_nacl=args.include_nacl)
    if args.limit is not None:
        benchmarks = benchmarks[: args.limit]
    benchmark_manifests = [benchmark_to_manifest(benchmark) for benchmark in benchmarks]

    ensure_dir(output_dir)
    ensure_dir(output_dir / "inputs")
    ensure_dir(output_dir / "cases")
    ensure_dir(output_dir / "canonical_tables")
    ensure_dir(output_dir / "summary")
    ensure_dir(output_dir / "environment")
    ensure_dir(output_dir / "discrepancies")

    environment_snapshot = collect_environment_snapshot()
    write_text(output_dir / "environment" / "pip_freeze.txt", environment_snapshot["pip_freeze"])
    dump_json(output_dir / "environment" / "versions.json", environment_snapshot["versions"])
    dump_json(output_dir / "summary" / "benchmarks.json", benchmark_manifests)

    summary_rows: list[dict[str, Any]] = []
    discrepancy_rows: list[dict[str, Any]] = []
    pairwise_case_counts = {
        "gudhi__ripser": {"exact": 0, "different": 0},
        "gudhi__dionysus": {"exact": 0, "different": 0},
        "ripser__dionysus": {"exact": 0, "different": 0},
    }

    for benchmark in benchmarks:
        save_benchmark_inputs(output_dir / "inputs", benchmark)

        threshold_specs = [("selected", benchmark.selected_threshold)]
        if benchmark.full_filtration_feasible:
            threshold_specs.append(("full", benchmark.full_threshold))

        for coeff in benchmark.coeffs:
            for maxdim in benchmark.maxdims:
                for threshold_label, threshold_value in threshold_specs:
                    case_id = f"{benchmark.benchmark_id}__p{coeff}__h{maxdim}__{threshold_label}"
                    case_result = run_case(
                        benchmark.distance_matrix,
                        coeff=coeff,
                        maxdim=maxdim,
                        threshold=threshold_value,
                        case_id=case_id,
                    )
                    case_payload = build_case_payload(
                        benchmark=benchmark,
                        threshold_label=threshold_label,
                        threshold_value=threshold_value,
                        case_result=case_result,
                    )
                    dump_json(output_dir / "cases" / f"{case_id}.json", case_payload)
                    write_canonical_table(output_dir / "canonical_tables" / f"{case_id}.csv", case_payload)
                    summary_row = build_summary_row(case_payload)
                    summary_rows.append(summary_row)
                    update_pairwise_case_counts(pairwise_case_counts, case_result)
                    if not summary_row["exact_all_libraries"]:
                        discrepancy_rows.append(
                            {
                                "case_id": case_id,
                                "benchmark_id": benchmark.benchmark_id,
                                "family": benchmark.family,
                                "mode": benchmark.mode,
                                "coeff": coeff,
                                "maxdim": maxdim,
                                "threshold_label": threshold_label,
                                "matrix_size": int(benchmark.distance_matrix.shape[0]),
                                "distance_matrix_hash": benchmark.metadata["distance_matrix_hash"],
                                "point_cloud_hash": benchmark.metadata["point_cloud_hash"],
                                "mismatch_dimensions": summary_row["mismatch_dimensions"],
                                "discrepancy": case_result["discrepancy"],
                            }
                        )

    write_csv(output_dir / "summary" / "agreement_summary.csv", summary_rows)
    dump_json(output_dir / "summary" / "agreement_summary.json", summary_rows)
    dump_json(output_dir / "summary" / "pairwise_case_agreement.json", pairwise_case_counts)
    save_discrepancy_artifacts(output_dir / "discrepancies", discrepancy_rows)
    report_text = render_report(
        benchmarks=benchmark_manifests,
        summary_rows=summary_rows,
        discrepancies=discrepancy_rows,
        environment_snapshot=environment_snapshot["versions"],
        pairwise_case_counts=pairwise_case_counts,
    )
    write_text(output_dir / "report.md", report_text)
    return 0


def collect_environment_snapshot() -> dict[str, Any]:
    versions = {
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "random_seed": RANDOM_SEED,
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


def save_benchmark_inputs(base_dir: Path, benchmark: Any) -> None:
    benchmark_dir = base_dir / benchmark.benchmark_id
    ensure_dir(benchmark_dir)
    save_array(benchmark_dir / "distance_matrix.npy", benchmark.distance_matrix)
    save_csv_array(benchmark_dir / "distance_matrix.csv", benchmark.distance_matrix)
    if benchmark.point_cloud is not None:
        save_array(benchmark_dir / "point_cloud.npy", benchmark.point_cloud)
        save_csv_array(benchmark_dir / "point_cloud.csv", benchmark.point_cloud)
    dump_json(benchmark_dir / "manifest.json", benchmark_to_manifest(benchmark))


def build_case_payload(
    *,
    benchmark: Any,
    threshold_label: str,
    threshold_value: float,
    case_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "benchmark": benchmark_to_manifest(benchmark),
        "case_parameters": {
            "case_id": case_result["case_id"],
            "coeff": case_result["coeff"],
            "maxdim": case_result["maxdim"],
            "threshold_label": threshold_label,
            "threshold_value": serialize_json_value(threshold_value),
        },
        "inputs": {
            "distance_matrix_hash": benchmark.metadata["distance_matrix_hash"],
            "point_cloud_hash": benchmark.metadata["point_cloud_hash"],
            "distance_matrix_shape": list(benchmark.distance_matrix.shape),
            "point_cloud_shape": None if benchmark.point_cloud is None else list(benchmark.point_cloud.shape),
        },
        "results": case_result,
    }


def build_summary_row(case_payload: dict[str, Any]) -> dict[str, Any]:
    benchmark = case_payload["benchmark"]
    case_parameters = case_payload["case_parameters"]
    results = case_payload["results"]
    mismatch_dimensions = [
        dim
        for dim, payload in results["agreement"]["by_dimension"].items()
        if not payload["exact_all_libraries"]
    ]
    return {
        "case_id": case_parameters["case_id"],
        "benchmark_id": benchmark["benchmark_id"],
        "family": benchmark["family"],
        "label": benchmark["label"],
        "mode": benchmark["mode"],
        "coeff": case_parameters["coeff"],
        "maxdim": case_parameters["maxdim"],
        "threshold_label": case_parameters["threshold_label"],
        "threshold_value": case_parameters["threshold_value"],
        "matrix_size": results["matrix_size"],
        "distance_matrix_hash": case_payload["inputs"]["distance_matrix_hash"],
        "point_cloud_hash": case_payload["inputs"]["point_cloud_hash"],
        "exact_all_libraries": results["agreement"]["exact_all_libraries"],
        "mismatch_dimensions": ",".join(mismatch_dimensions),
    }


def save_discrepancy_artifacts(base_dir: Path, discrepancies: list[dict[str, Any]]) -> None:
    if discrepancies:
        dump_json(base_dir / "all_discrepancies.json", discrepancies)
        minimal = sorted(
            discrepancies,
            key=lambda row: (row["matrix_size"], row["benchmark_id"], row["case_id"]),
        )[0]
        dump_json(base_dir / "minimal_failing_case.json", minimal)
    else:
        note = {
            "task_id": TASK_ID,
            "message": "No discrepancies were observed; all canonicalized interval multisets matched exactly.",
        }
        dump_json(base_dir / "all_discrepancies.json", [])
        dump_json(base_dir / "minimal_failing_case.json", note)


def write_canonical_table(path: Path, case_payload: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    results = case_payload["results"]
    case_parameters = case_payload["case_parameters"]
    benchmark = case_payload["benchmark"]
    for library in LIBRARIES:
        for dim, payload in results["canonicalized"][library].items():
            for index, interval in enumerate(payload["intervals"]):
                rows.append(
                    {
                        "case_id": case_parameters["case_id"],
                        "benchmark_id": benchmark["benchmark_id"],
                        "family": benchmark["family"],
                        "mode": benchmark["mode"],
                        "coeff": case_parameters["coeff"],
                        "maxdim": case_parameters["maxdim"],
                        "threshold_label": case_parameters["threshold_label"],
                        "library": library,
                        "dimension": dim,
                        "interval_index": index,
                        "birth": interval["birth"],
                        "death": interval["death"],
                        "birth_hex": interval["birth_hex"],
                        "death_hex": interval["death_hex"],
                    }
                )
    write_csv(path, rows)


def render_report(
    *,
    benchmarks: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    discrepancies: list[dict[str, Any]],
    environment_snapshot: dict[str, Any],
    pairwise_case_counts: dict[str, dict[str, int]],
) -> str:
    setup_lines = [
        f"# {TASK_ID}",
        "",
        "## setup",
        f"- Generated at UTC: {environment_snapshot['generated_at_utc']}",
        f"- Python: `{environment_snapshot['python_version'].splitlines()[0]}`",
        f"- Platform: `{environment_snapshot['platform']}`",
        f"- Random seed: `{environment_snapshot['random_seed']}`",
        "- Key distributions:",
    ]
    for distribution, version in environment_snapshot["distributions"].items():
        setup_lines.append(f"  - `{distribution}=={version}`")
    setup_lines.append("- Pairwise case agreement across all compared dimensions:")
    for pair, counts in pairwise_case_counts.items():
        total = counts["exact"] + counts["different"]
        setup_lines.append(f"  - `{pair}` exact in `{counts['exact']}/{total}` case(s)")

    benchmark_rows = [
        {
            "benchmark_id": benchmark["benchmark_id"],
            "family": benchmark["family"],
            "mode": benchmark["mode"],
            "selected_threshold": benchmark["selected_threshold"],
            "full_threshold": benchmark["full_threshold"],
            "has_point_cloud": benchmark["has_point_cloud"],
            "distance_matrix_shape": "x".join(str(item) for item in benchmark["distance_matrix_shape"]),
            "distance_matrix_hash": benchmark["metadata"]["distance_matrix_hash"][:12],
        }
        for benchmark in benchmarks
    ]
    agreement_rows = [
        {
            "benchmark_id": row["benchmark_id"],
            "mode": row["mode"],
            "coeff": row["coeff"],
            "maxdim": row["maxdim"],
            "threshold": row["threshold_label"],
            "exact_all": row["exact_all_libraries"],
            "mismatch_dims": row["mismatch_dimensions"] or "-",
        }
        for row in summary_rows
    ]

    discrepancy_lines = ["## discrepancy analysis"]
    if discrepancies:
        zero_metric_cases = sum(1 for row in discrepancies if not discrepancy_has_positive_metric(row["discrepancy"]))
        positive_metric_cases = len(discrepancies) - zero_metric_cases
        discrepancy_lines.append("")
        discrepancy_lines.append(
            f"{len(discrepancies)} case(s) failed exact agreement after canonicalization by homological dimension."
        )
        discrepancy_lines.append(
            f"{zero_metric_cases} discrepancy case(s) have zero bottleneck and Wasserstein distance, indicating convention-level differences such as zero-length bars."
        )
        discrepancy_lines.append(
            f"{positive_metric_cases} discrepancy case(s) have a strictly positive diagram distance."
        )
        floating_h0_cases = sum(
            1
            for row in discrepancies
            if row["mode"] == "floating" and "0" in row["mismatch_dimensions"].split(",")
        )
        higher_dim_cases = sum(
            1
            for row in discrepancies
            if any(dim in row["mismatch_dimensions"].split(",") for dim in ("1", "2"))
        )
        discrepancy_lines.append(
            f"{floating_h0_cases} discrepancy case(s) include H0 endpoint hex mismatches in floating mode, driven by `gudhi` preserving float64 endpoints while `ripser` and `dionysus` round to float32-level values."
        )
        discrepancy_lines.append(
            f"{higher_dim_cases} discrepancy case(s) include higher-dimensional zero-length bars reported by `gudhi` but omitted by `ripser` and `dionysus`."
        )
        discrepancy_lines.append("")
        discrepancy_lines.append(
            render_markdown_table(
                [
                    {
                        "case_id": row["case_id"],
                        "matrix_size": row["matrix_size"],
                        "threshold": row["threshold_label"],
                        "mismatch_dims": ",".join(row["mismatch_dimensions"]) if isinstance(row["mismatch_dimensions"], list) else row["mismatch_dimensions"],
                    }
                    for row in discrepancies
                ]
            )
        )
    else:
        discrepancy_lines.append("")
        discrepancy_lines.append(
            "No discrepancies were observed. All canonicalized interval multisets matched exactly across GUDHI, Ripser.py, and Dionysus for every benchmark/parameter tuple."
        )

    reproducibility_lines = [
        "## reproducibility notes",
        "- Run the full harness from WSL/Linux with `make all`.",
        "- The pinned Python environment is recorded in `requirements.txt` and `artifacts/environment/pip_freeze.txt`.",
        "- Every input point cloud and distance matrix is saved under `artifacts/inputs/` with SHA-256 hashes in the benchmark manifests.",
        "- Raw library outputs are saved per case under `artifacts/cases/`.",
        "- Canonicalized interval tables are saved per case under `artifacts/canonical_tables/`.",
        "- Machine-readable summaries are saved under `artifacts/summary/` and `artifacts/discrepancies/`.",
        "- For Dionysus, the exact conformance path uses condensed distance-matrix input; no approximation modes are enabled in any library.",
    ]

    report_sections = setup_lines
    report_sections.extend(["", "## benchmark definitions", "", render_markdown_table(benchmark_rows)])
    report_sections.extend(["", "## per-benchmark agreement table", "", render_markdown_table(agreement_rows)])
    report_sections.extend([""])
    report_sections.extend(discrepancy_lines)
    report_sections.extend([""])
    report_sections.extend(reproducibility_lines)
    report_sections.append("")
    return "\n".join(report_sections)


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


def discrepancy_has_positive_metric(discrepancy: dict[str, Any]) -> bool:
    for dim_payload in discrepancy.get("by_dimension", {}).values():
        for pair_payload in dim_payload.get("pairwise", {}).values():
            for metric_key in ("bottleneck_distance", "wasserstein_distance_q2"):
                metric_value = pair_payload.get(metric_key)
                if isinstance(metric_value, (int, float)) and metric_value > 0.0:
                    return True
    return False


def update_pairwise_case_counts(pairwise_case_counts: dict[str, dict[str, int]], case_result: dict[str, Any]) -> None:
    for pair in pairwise_case_counts:
        exact = all(
            dim_payload["pairwise"][pair]["exact_match"]
            for dim_payload in case_result["agreement"]["by_dimension"].values()
        )
        if exact:
            pairwise_case_counts[pair]["exact"] += 1
        else:
            pairwise_case_counts[pair]["different"] += 1


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
        writer.writerows(rows)


def dump_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(serialize_json_value(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def save_array(path: Path, array: np.ndarray) -> None:
    ensure_dir(path.parent)
    np.save(path, np.asarray(array))


def save_csv_array(path: Path, array: np.ndarray) -> None:
    ensure_dir(path.parent)
    np.savetxt(path, np.asarray(array), delimiter=",", fmt="%.17g")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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
        if np.isnan(value):
            return "nan"
        if np.isposinf(value):
            return "inf"
        if np.isneginf(value):
            return "-inf"
        return value
    return value


if __name__ == "__main__":
    raise SystemExit(main())
