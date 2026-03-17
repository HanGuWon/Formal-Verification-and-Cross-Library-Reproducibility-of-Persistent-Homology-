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
from scipy.sparse import save_npz

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ph_conformance.lower_star_h0 import (  # noqa: E402
    LOWER_STAR_LIBRARIES,
    benchmark_to_manifest,
    build_ripser_sparse_matrix,
    common_chain_filtration,
    expected_h0_events,
    generate_lower_star_h0_benchmarks,
    run_lower_star_h0_case,
    serialize_dionysus_filtration,
    serialize_gudhi_cubical_encoding,
    serialize_json_value,
    serialize_ripser_sparse_matrix,
)


TASK_ID = "PH-LOWERSTAR-H0-001"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "lowerstar_h0"
RANDOM_SEED = 0
DIRECT_DISTRIBUTIONS = ("numpy", "scipy", "gudhi", "ripser", "dionysus")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the lower-star H0 conformance benchmark.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Artifact output directory.",
    )
    parser.add_argument(
        "--no-aah",
        action="store_true",
        help="Skip the AAH-style intensity-profile benchmarks.",
    )
    parser.add_argument(
        "--floating-only",
        action="store_true",
        help="Run only floating-valued signals.",
    )
    parser.add_argument(
        "--quantized-only",
        action="store_true",
        help="Run only quantized signals.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit before mode expansion.",
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
    ensure_dir(output_dir)
    for child in (
        "signals",
        "encoded_filtrations",
        "diagrams",
        "betti_summaries",
        "theorem_examples",
        "cases",
        "summary",
        "environment",
    ):
        ensure_dir(output_dir / child)

    benchmarks = generate_lower_star_h0_benchmarks(modes=modes, include_aah=not args.no_aah)
    if args.limit is not None:
        benchmarks = benchmarks[: args.limit]

    environment_snapshot = collect_environment_snapshot()
    write_text(output_dir / "environment" / "pip_freeze.txt", environment_snapshot["pip_freeze"])
    dump_json(output_dir / "environment" / "versions.json", environment_snapshot["versions"])

    benchmark_manifests = [benchmark_to_manifest(benchmark) for benchmark in benchmarks]
    dump_json(output_dir / "summary" / "benchmarks.json", benchmark_manifests)

    case_payloads = []
    summary_rows = []
    theorem_examples = []

    for benchmark in benchmarks:
        save_signal_artifacts(output_dir / "signals", benchmark)
        save_encoded_filtration_artifacts(output_dir / "encoded_filtrations", benchmark)

        case_result = run_lower_star_h0_case(benchmark.signal)
        case_payload = {
            "task_id": TASK_ID,
            "benchmark": benchmark_to_manifest(benchmark),
            "results": case_result,
        }
        case_payloads.append(case_payload)
        dump_json(output_dir / "cases" / f"{benchmark.benchmark_id}.json", case_payload)

        save_diagram_artifacts(output_dir / "diagrams", benchmark.benchmark_id, case_result)
        save_betti_artifacts(output_dir / "betti_summaries", benchmark.benchmark_id, case_result)
        dump_json(output_dir / "theorem_examples" / f"{benchmark.benchmark_id}.json", case_result["theorem_events"])
        theorem_examples.append(
            {
                "benchmark_id": benchmark.benchmark_id,
                "family": benchmark.family,
                "mode": benchmark.mode,
                "births_match_local_minima": case_result["theorem_events"]["births_match_local_minima"],
                "finite_deaths_match_merge_heights": case_result["theorem_events"]["finite_deaths_match_merge_heights"],
                "local_minima_count": len(case_result["theorem_events"]["local_minima"]),
                "nonzero_interval_count": len(case_result["theorem_events"]["nonzero_intervals"]),
            }
        )
        summary_rows.append(build_summary_row(benchmark=benchmark, case_result=case_result))

    dump_json(output_dir / "summary" / "comparison_summary.json", summary_rows)
    write_csv(output_dir / "summary" / "comparison_summary.csv", summary_rows)
    dump_json(output_dir / "summary" / "theorem_examples.json", theorem_examples)

    report_text = render_report(
        benchmarks=benchmarks,
        summary_rows=summary_rows,
        theorem_examples=theorem_examples,
        environment_snapshot=environment_snapshot["versions"],
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


def save_signal_artifacts(base_dir: Path, benchmark: Any) -> None:
    benchmark_dir = base_dir / benchmark.benchmark_id
    ensure_dir(benchmark_dir)
    np.save(benchmark_dir / "signal.npy", np.asarray(benchmark.signal))
    np.savetxt(benchmark_dir / "signal.csv", np.asarray(benchmark.signal), delimiter=",", fmt="%.17g")
    dump_json(benchmark_dir / "signal.json", {"values": benchmark.signal.tolist()})
    dump_json(benchmark_dir / "manifest.json", benchmark_to_manifest(benchmark))


def save_encoded_filtration_artifacts(base_dir: Path, benchmark: Any) -> None:
    benchmark_dir = base_dir / benchmark.benchmark_id
    ensure_dir(benchmark_dir)
    dump_json(benchmark_dir / "common_chain.json", common_chain_filtration(benchmark.signal))
    dump_json(benchmark_dir / "gudhi_cubical_encoding.json", serialize_gudhi_cubical_encoding(benchmark.signal))
    dump_json(benchmark_dir / "ripser_sparse_matrix.json", serialize_ripser_sparse_matrix(benchmark.signal))
    save_npz(benchmark_dir / "ripser_sparse_matrix.npz", build_ripser_sparse_matrix(benchmark.signal))
    write_sparse_csv(benchmark_dir / "ripser_sparse_matrix.csv", serialize_ripser_sparse_matrix(benchmark.signal)["entries"])
    dump_json(benchmark_dir / "dionysus_freudenthal.json", serialize_dionysus_filtration(benchmark.signal))
    dump_json(benchmark_dir / "reference_theorem_events.json", expected_h0_events(benchmark.signal))


def save_diagram_artifacts(base_dir: Path, benchmark_id: str, case_result: dict[str, Any]) -> None:
    benchmark_dir = base_dir / benchmark_id
    ensure_dir(benchmark_dir)
    for library in LOWER_STAR_LIBRARIES:
        dump_json(benchmark_dir / f"{library}.json", case_result["raw_outputs"][library])


def save_betti_artifacts(base_dir: Path, benchmark_id: str, case_result: dict[str, Any]) -> None:
    benchmark_dir = base_dir / benchmark_id
    ensure_dir(benchmark_dir)
    dump_json(benchmark_dir / "betti0_summary.json", case_result["betti_summary"])
    write_csv(benchmark_dir / "betti0_summary.csv", case_result["betti_summary"]["rows"])
    write_csv(benchmark_dir / "betti0_float32_summary.csv", case_result["betti_summary"]["float32_rows"])


def build_summary_row(*, benchmark: Any, case_result: dict[str, Any]) -> dict[str, Any]:
    agreement = case_result["agreement"]
    theorem_events = case_result["theorem_events"]
    return {
        "benchmark_id": benchmark.benchmark_id,
        "family": benchmark.family,
        "label": benchmark.label,
        "mode": benchmark.mode,
        "signal_length": int(benchmark.signal.size),
        "signal_hash": benchmark.metadata["signal_hash"],
        "exact_interval_agreement": agreement["exact_all_libraries"],
        "float32_stable_interval_agreement": agreement["float32_stable_all_libraries"],
        "betti0_agreement": case_result["betti_summary"]["all_equal"],
        "betti0_float32_stable_agreement": case_result["betti_summary"]["float32_all_equal"],
        "births_match_local_minima": theorem_events["births_match_local_minima"],
        "finite_deaths_match_merge_heights": theorem_events["finite_deaths_match_merge_heights"],
        "gudhi__ripser_exact": agreement["pairwise"]["gudhi__ripser"]["exact_match"],
        "gudhi__dionysus_exact": agreement["pairwise"]["gudhi__dionysus"]["exact_match"],
        "ripser__dionysus_exact": agreement["pairwise"]["ripser__dionysus"]["exact_match"],
        "gudhi__ripser_float32": agreement["pairwise"]["gudhi__ripser"]["float32_match"],
        "gudhi__dionysus_float32": agreement["pairwise"]["gudhi__dionysus"]["float32_match"],
        "ripser__dionysus_float32": agreement["pairwise"]["ripser__dionysus"]["float32_match"],
        "gudhi__ripser_max_abs_diff": agreement["pairwise"]["gudhi__ripser"]["max_abs_finite_endpoint_diff"],
        "gudhi__dionysus_max_abs_diff": agreement["pairwise"]["gudhi__dionysus"]["max_abs_finite_endpoint_diff"],
        "ripser__dionysus_max_abs_diff": agreement["pairwise"]["ripser__dionysus"]["max_abs_finite_endpoint_diff"],
    }


def render_report(
    *,
    benchmarks: list[Any],
    summary_rows: list[dict[str, Any]],
    theorem_examples: list[dict[str, Any]],
    environment_snapshot: dict[str, Any],
) -> str:
    lines = [
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
        lines.append(f"  - `{distribution}=={version}`")

    family_order = []
    for benchmark in benchmarks:
        if benchmark.family not in family_order:
            family_order.append(benchmark.family)

    for family in family_order:
        rows = [row for row in summary_rows if row["family"] == family]
        exact_count = sum(1 for row in rows if row["exact_interval_agreement"])
        stable_count = sum(1 for row in rows if row["float32_stable_interval_agreement"])
        betti_count = sum(1 for row in rows if row["betti0_agreement"])
        betti_stable_count = sum(1 for row in rows if row["betti0_float32_stable_agreement"])
        theorem_count = sum(
            1
            for row in rows
            if row["births_match_local_minima"] and row["finite_deaths_match_merge_heights"]
        )
        lines.extend(
            [
                "",
                f"## {family} signals",
                f"- Interval-multiset exact agreement: `{exact_count}/{len(rows)}` benchmark(s).",
                f"- Float32-stable interval agreement: `{stable_count}/{len(rows)}` benchmark(s).",
                f"- Persistent Betti-0 exact agreement: `{betti_count}/{len(rows)}` benchmark(s).",
                f"- Persistent Betti-0 float32-stable agreement: `{betti_stable_count}/{len(rows)}` benchmark(s).",
                f"- Theorem-style minima/merge match: `{theorem_count}/{len(rows)}` benchmark(s).",
                "",
                render_markdown_table(
                    [
                        {
                            "benchmark_id": row["benchmark_id"],
                            "mode": row["mode"],
                            "signal_length": row["signal_length"],
                            "exact": row["exact_interval_agreement"],
                            "float32_stable": row["float32_stable_interval_agreement"],
                            "betti0_exact": row["betti0_agreement"],
                            "betti0_float32": row["betti0_float32_stable_agreement"],
                            "minima_births": row["births_match_local_minima"],
                            "merge_deaths": row["finite_deaths_match_merge_heights"],
                        }
                        for row in rows
                    ]
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## reproducibility",
            "- Run the benchmark from WSL/Linux with `PYTHONPATH=src python scripts/run_lowerstar_h0.py`.",
            "- Every signal is saved under `artifacts/lowerstar_h0/signals/` as `.npy`, `.csv`, and `.json`.",
            "- Every encoded filtration is saved under `artifacts/lowerstar_h0/encoded_filtrations/`.",
            "- Raw diagrams are saved under `artifacts/lowerstar_h0/diagrams/`.",
            "- Betti summaries are saved under `artifacts/lowerstar_h0/betti_summaries/`.",
            "- The theorem-supporting examples are saved under `artifacts/lowerstar_h0/theorem_examples/`.",
        ]
    )
    return "\n".join(lines) + "\n"


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


def write_sparse_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)
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


if __name__ == "__main__":
    raise SystemExit(main())
