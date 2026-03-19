from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

import sys

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ph_conformance.path_h0_formalization import (  # noqa: E402
    common_chain_encoding,
    comparison_signature,
    diagram_distance_after_zero_removal,
    dump_json,
    event_list_signature,
    float_to_hex,
    load_json,
    reference_path_h0_events,
    serialize_json_value,
    sha256_file,
    signal_to_values,
    zero_length_interval_count,
)


TASK_ID = "PH-FORMALIZATION-PATH-H0-002"
DEFAULT_LOWERSTAR_DIR = REPO_ROOT / "artifacts" / "lowerstar_h0"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "formalization"
PROOF_OBLIGATIONS = [
    "Define the lower-star filtration on the finite path graph with vertex filtration f(i) and edge filtration max(f(i), f(i+1)).",
    "Prove that the reference elder-rule merge algorithm computes the H0 persistence multiset for this finite path filtration.",
    "Prove that nonzero births are exactly the strict local minima of the path signal.",
    "Prove that finite nonzero deaths are exactly the merge heights of components whose younger birth is strictly below the merge height.",
    "Prove that removing zero-length intervals preserves the persistence diagram up to zero bottleneck and Wasserstein distance by matching those intervals to the diagonal.",
]
THEOREM_TARGETS = {
    "births_at_local_minima": "For a finite path lower-star filtration in H0, the births of the nonzero persistence intervals occur exactly at strict local minima.",
    "deaths_at_merge_heights": "For a finite path lower-star filtration in H0, the finite deaths of the nonzero persistence intervals occur exactly at the elder-rule merge heights.",
    "drop_zero_length_distance_zero": "Removing zero-length intervals from the path-H0 interval multiset leaves bottleneck distance 0 and Wasserstein-q2 distance 0.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a formalization-ready finite-path H0 spec package from saved lower-star artifacts.")
    parser.add_argument(
        "--lowerstar-dir",
        type=Path,
        default=DEFAULT_LOWERSTAR_DIR,
        help="Directory containing PH-LOWERSTAR-H0-001 artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for the formalization package.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lowerstar_dir = args.lowerstar_dir.resolve()
    output_dir = args.output_dir.resolve()
    spec_dir = output_dir / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)

    theorem_example_summary = load_json(lowerstar_dir / "summary" / "theorem_examples.json")
    theorem_example_dir = lowerstar_dir / "theorem_examples"
    generated_entries = []

    for summary_row in theorem_example_summary:
        benchmark_id = str(summary_row["benchmark_id"])
        spec_payload = build_spec_for_benchmark(
            benchmark_id=benchmark_id,
            lowerstar_dir=lowerstar_dir,
            summary_row=summary_row,
        )
        dump_json(spec_dir / f"{benchmark_id}.json", spec_payload)
        generated_entries.append(
            {
                "benchmark_id": benchmark_id,
                "family": summary_row["family"],
                "mode": summary_row["mode"],
                "spec_path": f"formalization/spec/{benchmark_id}.json",
                "theorem_example_path": f"artifacts/lowerstar_h0/theorem_examples/{benchmark_id}.json",
            }
        )

    index_payload = {
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "package_scope": {
            "graph_type": "finite_path",
            "homology_dimension": 0,
            "filtration_rule": "lower_star_on_vertices_with_edge_filtration_max_endpoint",
            "claim_scope": "restricted_to_saved_path_graph_examples_only",
        },
        "tool_availability": {
            "lean": bool(which("lean")),
            "lake": bool(which("lake")),
            "coqc": bool(which("coqc")),
        },
        "theorem_targets": dict(THEOREM_TARGETS),
        "proof_obligations": list(PROOF_OBLIGATIONS),
        "spec_entries": generated_entries,
        "source_dirs": {
            "lowerstar_dir": str(lowerstar_dir.relative_to(REPO_ROOT)),
            "theorem_example_dir": str(theorem_example_dir.relative_to(REPO_ROOT)),
            "spec_dir": str(spec_dir.relative_to(REPO_ROOT)),
        },
    }
    dump_json(spec_dir / "index.json", index_payload)
    return 0


def build_spec_for_benchmark(
    *,
    benchmark_id: str,
    lowerstar_dir: Path,
    summary_row: dict[str, Any],
) -> dict[str, Any]:
    signal_dir = lowerstar_dir / "signals" / benchmark_id
    encoded_dir = lowerstar_dir / "encoded_filtrations" / benchmark_id
    theorem_example_path = lowerstar_dir / "theorem_examples" / f"{benchmark_id}.json"
    case_path = lowerstar_dir / "cases" / f"{benchmark_id}.json"
    betti_path = lowerstar_dir / "betti_summaries" / benchmark_id / "betti0_summary.json"

    signal_payload = load_json(signal_dir / "signal.json")
    signal_manifest = load_json(signal_dir / "manifest.json")
    common_chain_saved = load_json(encoded_dir / "common_chain.json")
    theorem_saved = load_json(theorem_example_path)
    reference_saved = load_json(encoded_dir / "reference_theorem_events.json")
    case_payload = load_json(case_path)
    betti_payload = load_json(betti_path)

    signal = signal_to_values(signal_payload)
    common_chain_ref = common_chain_encoding(signal)
    theorem_ref = reference_path_h0_events(signal)
    zero_length_distances = diagram_distance_after_zero_removal(theorem_ref)

    common_chain_matches_saved = serialize_json_value(common_chain_ref) == serialize_json_value(common_chain_saved)
    theorem_saved_matches_reference = serialize_json_value(theorem_saved) == serialize_json_value(theorem_ref)
    encoded_reference_matches_reference = serialize_json_value(reference_saved) == serialize_json_value(theorem_ref)

    if not common_chain_matches_saved:
        raise ValueError(f"Saved common-chain encoding diverged for {benchmark_id}")
    if not theorem_saved_matches_reference:
        raise ValueError(f"Saved theorem example diverged for {benchmark_id}")
    if not encoded_reference_matches_reference:
        raise ValueError(f"Saved reference theorem events diverged for {benchmark_id}")

    source_artifacts = {
        "signal_json": artifact_entry(signal_dir / "signal.json"),
        "signal_manifest": artifact_entry(signal_dir / "manifest.json"),
        "common_chain": artifact_entry(encoded_dir / "common_chain.json"),
        "gudhi_cubical_encoding": artifact_entry(encoded_dir / "gudhi_cubical_encoding.json"),
        "ripser_sparse_matrix": artifact_entry(encoded_dir / "ripser_sparse_matrix.json"),
        "dionysus_freudenthal": artifact_entry(encoded_dir / "dionysus_freudenthal.json"),
        "reference_theorem_events": artifact_entry(encoded_dir / "reference_theorem_events.json"),
        "theorem_example": artifact_entry(theorem_example_path),
        "case_payload": artifact_entry(case_path),
        "betti0_summary": artifact_entry(betti_path),
    }

    path_graph = {
        "vertex_count": int(signal.size),
        "vertices": list(range(int(signal.size))),
        "edges": [[index, index + 1] for index in range(int(signal.size) - 1)],
    }

    computational_witness = {
        "theorem_example_summary": dict(summary_row),
        "library_agreement": case_payload["results"]["agreement"],
        "betti_summary": betti_payload,
        "reference_consistency": {
            "common_chain_matches_saved": common_chain_matches_saved,
            "theorem_example_matches_saved": theorem_saved_matches_reference,
            "encoded_reference_matches_saved": encoded_reference_matches_reference,
        },
    }

    theorem_targets = {
        "births_at_local_minima": {
            "statement": THEOREM_TARGETS["births_at_local_minima"],
            "expected": True,
            "verified_by_reference": bool(theorem_ref["births_match_local_minima"]),
        },
        "deaths_at_merge_heights": {
            "statement": THEOREM_TARGETS["deaths_at_merge_heights"],
            "expected": True,
            "verified_by_reference": bool(theorem_ref["finite_deaths_match_merge_heights"]),
        },
        "drop_zero_length_distance_zero": {
            "statement": THEOREM_TARGETS["drop_zero_length_distance_zero"],
            "expected_bottleneck_distance": 0.0,
            "expected_wasserstein_q2_distance": 0.0,
            "verified_bottleneck_distance": zero_length_distances["bottleneck_distance"],
            "verified_wasserstein_q2_distance": zero_length_distances["wasserstein_distance_q2"],
        },
    }

    return {
        "task_id": TASK_ID,
        "spec_version": 1,
        "benchmark_id": benchmark_id,
        "family": signal_manifest["family"],
        "label": signal_manifest["label"],
        "mode": signal_manifest["mode"],
        "restricted_setting": {
            "graph_type": "finite_path",
            "homology_dimension": 0,
            "signal_encoding": "vertex_filtration_on_path_graph",
            "edge_filtration_rule": "max(endpoint_heights)",
            "lower_star_encodings": {
                "gudhi": "CubicalComplex(vertices=signal)",
                "ripser": "sparse distance matrix with diagonal births and edge weights=max endpoint heights",
                "dionysus": "fill_freudenthal(signal)",
            },
            "elder_rule_tie_break": "older=(smaller birth value, then smaller birth index)",
        },
        "source_artifacts": source_artifacts,
        "signal": {
            "length": int(signal.size),
            "values": [float(value) for value in signal.tolist()],
            "values_hex": [float_to_hex(value) for value in signal.tolist()],
            "signal_hash": signal_manifest["metadata"]["signal_hash"],
        },
        "path_graph": path_graph,
        "reference_encoding": common_chain_ref,
        "reference_semantics": theorem_ref,
        "zero_length_interval_count": zero_length_interval_count(theorem_ref["all_intervals"]),
        "nonzero_interval_count": len(theorem_ref["nonzero_intervals"]),
        "theorem_targets": theorem_targets,
        "computational_witness": computational_witness,
        "proof_obligations": list(PROOF_OBLIGATIONS),
        "traceability": {
            "signal_manifest_benchmark_id": signal_manifest["benchmark_id"],
            "case_payload_benchmark_id": case_payload["benchmark"]["benchmark_id"],
            "theorem_example_benchmark_id": benchmark_id,
        },
    }


def artifact_entry(path: Path) -> dict[str, Any]:
    entry = {
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": sha256_file(path),
    }
    if path.suffix == ".json":
        payload = load_json(path)
        if isinstance(payload, dict) and "benchmark_id" in payload:
            entry["benchmark_id"] = payload["benchmark_id"]
    return entry


if __name__ == "__main__":
    raise SystemExit(main())
