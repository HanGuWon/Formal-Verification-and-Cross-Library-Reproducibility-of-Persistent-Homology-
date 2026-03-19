from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ph_conformance.path_h0_formalization import (  # noqa: E402
    common_chain_encoding,
    diagram_distance_after_zero_removal,
    load_json,
    reference_path_h0_events,
    sha256_file,
    signal_to_values,
    zero_length_interval_count,
)


TASK_ID = "PH-FORMALIZATION-PATH-H0-002"
DEFAULT_SPEC_DIR = Path(__file__).resolve().parent / "spec"
ZERO_TOLERANCE = 1.0e-12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the finite-path H0 formalization specs against the saved lower-star artifacts.")
    parser.add_argument(
        "--spec-dir",
        type=Path,
        default=DEFAULT_SPEC_DIR,
        help="Directory containing the formalization spec JSON files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec_dir = args.spec_dir.resolve()
    index_path = spec_dir / "index.json"
    if not index_path.exists():
        raise SystemExit(f"Missing spec index: {index_path}")

    index_payload = load_json(index_path)
    spec_entries = index_payload["spec_entries"]
    theorem_example_dir = REPO_ROOT / "artifacts" / "lowerstar_h0" / "theorem_examples"
    theorem_example_stems = sorted(path.stem for path in theorem_example_dir.glob("*.json"))
    indexed_benchmarks = sorted(entry["benchmark_id"] for entry in spec_entries)
    expect(
        theorem_example_stems == indexed_benchmarks,
        "Spec index does not cover exactly the saved theorem examples.",
    )

    summary_rows = []
    for entry in spec_entries:
        spec_path = REPO_ROOT / entry["spec_path"]
        spec = load_json(spec_path)
        check_spec(spec)
        summary_rows.append(
            {
                "benchmark_id": spec["benchmark_id"],
                "family": spec["family"],
                "mode": spec["mode"],
                "zero_length_interval_count": spec["zero_length_interval_count"],
                "nonzero_interval_count": spec["nonzero_interval_count"],
            }
        )

    print(f"{TASK_ID}: checked {len(summary_rows)} spec entries.")
    for row in summary_rows:
        print(
            f"- {row['benchmark_id']}: zero_length={row['zero_length_interval_count']}, "
            f"nonzero={row['nonzero_interval_count']}"
        )
    return 0


def check_spec(spec: dict[str, Any]) -> None:
    benchmark_id = spec["benchmark_id"]
    source_artifacts = spec["source_artifacts"]

    resolved_paths = {}
    for name, entry in source_artifacts.items():
        path = REPO_ROOT / entry["path"]
        expect(path.exists(), f"{benchmark_id}: missing source artifact {name} at {path}")
        expect(sha256_file(path) == entry["sha256"], f"{benchmark_id}: hash mismatch for {name}")
        resolved_paths[name] = path

    signal_payload = load_json(resolved_paths["signal_json"])
    common_chain_saved = load_json(resolved_paths["common_chain"])
    theorem_saved = load_json(resolved_paths["theorem_example"])
    reference_saved = load_json(resolved_paths["reference_theorem_events"])
    case_payload = load_json(resolved_paths["case_payload"])
    betti_payload = load_json(resolved_paths["betti0_summary"])

    signal = signal_to_values(signal_payload)
    common_chain_ref = common_chain_encoding(signal)
    theorem_ref = reference_path_h0_events(signal)
    zero_metrics = diagram_distance_after_zero_removal(theorem_ref)

    expect(spec["task_id"] == TASK_ID, f"{benchmark_id}: wrong task id")
    expect(spec["signal"]["length"] == int(signal.size), f"{benchmark_id}: signal length mismatch")
    expect(spec["signal"]["values"] == signal_payload["values"], f"{benchmark_id}: signal value mismatch")
    expect(spec["reference_encoding"] == common_chain_ref, f"{benchmark_id}: spec encoding mismatch")
    expect(common_chain_saved == common_chain_ref, f"{benchmark_id}: saved common-chain encoding mismatch")
    expect(spec["reference_semantics"] == theorem_ref, f"{benchmark_id}: spec reference semantics mismatch")
    expect(theorem_saved == theorem_ref, f"{benchmark_id}: theorem-example artifact mismatch")
    expect(reference_saved == theorem_ref, f"{benchmark_id}: encoded theorem-events artifact mismatch")

    births_target = spec["theorem_targets"]["births_at_local_minima"]
    deaths_target = spec["theorem_targets"]["deaths_at_merge_heights"]
    zero_target = spec["theorem_targets"]["drop_zero_length_distance_zero"]
    expect(bool(theorem_ref["births_match_local_minima"]) and births_target["expected"], f"{benchmark_id}: births theorem failed")
    expect(
        bool(theorem_ref["finite_deaths_match_merge_heights"]) and deaths_target["expected"],
        f"{benchmark_id}: merge-height theorem failed",
    )
    expect(abs(float(zero_metrics["bottleneck_distance"])) <= ZERO_TOLERANCE, f"{benchmark_id}: bottleneck not zero")
    expect(abs(float(zero_metrics["wasserstein_distance_q2"])) <= ZERO_TOLERANCE, f"{benchmark_id}: wasserstein not zero")
    expect(
        abs(float(zero_target["verified_bottleneck_distance"])) <= ZERO_TOLERANCE,
        f"{benchmark_id}: stored bottleneck witness not zero",
    )
    expect(
        abs(float(zero_target["verified_wasserstein_q2_distance"])) <= ZERO_TOLERANCE,
        f"{benchmark_id}: stored wasserstein witness not zero",
    )

    expect(
        spec["zero_length_interval_count"] == zero_length_interval_count(theorem_ref["all_intervals"]),
        f"{benchmark_id}: zero-length interval count mismatch",
    )
    expect(
        spec["nonzero_interval_count"] == len(theorem_ref["nonzero_intervals"]),
        f"{benchmark_id}: nonzero interval count mismatch",
    )

    witness = spec["computational_witness"]
    expect(witness["theorem_example_summary"]["benchmark_id"] == benchmark_id, f"{benchmark_id}: summary witness mismatch")
    expect(witness["library_agreement"] == case_payload["results"]["agreement"], f"{benchmark_id}: library agreement mismatch")
    expect(witness["betti_summary"] == betti_payload, f"{benchmark_id}: betti summary mismatch")
    expect(spec["traceability"]["case_payload_benchmark_id"] == case_payload["benchmark"]["benchmark_id"], f"{benchmark_id}: traceability mismatch")


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
