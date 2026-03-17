from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import dionysus
import gudhi
import numpy as np
from ripser import ripser
from scipy import sparse
from scipy.sparse import csr_matrix, spmatrix


LOWER_STAR_LIBRARIES = ("gudhi", "ripser", "dionysus")
DEFAULT_SIGNAL_MODES = ("floating", "quantized")
DEFAULT_SIGNAL_QUANTIZATION_STEP = 2.0**-10
GOLDEN_RATIO = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass(frozen=True)
class LowerStarH0Benchmark:
    benchmark_id: str
    family: str
    label: str
    mode: str
    signal: np.ndarray
    metadata: dict[str, Any]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class _BaseSignalBenchmark:
    benchmark_id: str
    family: str
    label: str
    signal: np.ndarray
    metadata: dict[str, Any]
    notes: tuple[str, ...]


def generate_lower_star_h0_benchmarks(
    *,
    modes: tuple[str, ...] = DEFAULT_SIGNAL_MODES,
    quantization_step: float = DEFAULT_SIGNAL_QUANTIZATION_STEP,
    include_aah: bool = True,
) -> list[LowerStarH0Benchmark]:
    benchmarks: list[LowerStarH0Benchmark] = []
    for base in _base_signal_benchmarks(include_aah=include_aah):
        for mode in modes:
            signal = _materialize_signal_mode(base.signal, mode=mode, quantization_step=quantization_step)
            metadata = dict(base.metadata)
            metadata.update(
                {
                    "benchmark_id": base.benchmark_id,
                    "mode": mode,
                    "signal_hash": _hash_array(signal),
                    "signal_length": int(signal.size),
                    "quantization_step": None if mode == "floating" else quantization_step,
                }
            )
            notes = base.notes
            if mode == "quantized":
                notes = notes + (f"Signal values quantized to a power-of-two step of {quantization_step}.",)
            benchmarks.append(
                LowerStarH0Benchmark(
                    benchmark_id=f"{base.benchmark_id}__{mode}",
                    family=base.family,
                    label=base.label,
                    mode=mode,
                    signal=signal,
                    metadata=metadata,
                    notes=notes,
                )
            )
    return benchmarks


def benchmark_to_manifest(benchmark: LowerStarH0Benchmark) -> dict[str, Any]:
    return {
        "benchmark_id": benchmark.benchmark_id,
        "family": benchmark.family,
        "label": benchmark.label,
        "mode": benchmark.mode,
        "signal_length": int(benchmark.signal.size),
        "metadata": benchmark.metadata,
        "notes": list(benchmark.notes),
    }


def quantize_signal(signal: np.ndarray | list[float], *, step: float = DEFAULT_SIGNAL_QUANTIZATION_STEP) -> np.ndarray:
    array = np.asarray(signal, dtype=np.float64)
    return np.round(array / step) * step


def common_chain_filtration(signal: np.ndarray | list[float]) -> dict[str, Any]:
    values = np.asarray(signal, dtype=np.float64)
    vertices = [
        {
            "index": int(index),
            "filtration": serialize_float(height),
            "filtration_hex": float_to_hex(height),
        }
        for index, height in enumerate(values)
    ]
    edges = [
        {
            "vertices": [int(index), int(index + 1)],
            "filtration": serialize_float(max(values[index], values[index + 1])),
            "filtration_hex": float_to_hex(max(values[index], values[index + 1])),
        }
        for index in range(values.size - 1)
    ]
    critical_values = sorted(
        {
            float(values[index])
            for index in range(values.size)
        }.union(
            {
                float(max(values[index], values[index + 1]))
                for index in range(values.size - 1)
            }
        )
    )
    return {
        "signal": [serialize_float(value) for value in values],
        "vertices": vertices,
        "edges": edges,
        "critical_values": [
            {"value": serialize_float(value), "value_hex": float_to_hex(value)} for value in critical_values
        ],
    }


def expected_h0_events(signal: np.ndarray | list[float]) -> dict[str, Any]:
    values = np.asarray(signal, dtype=np.float64)
    num_vertices = int(values.size)

    events: list[tuple[float, int, tuple[int, ...]]] = []
    for index, value in enumerate(values):
        events.append((float(value), 0, (int(index),)))
    for index in range(values.size - 1):
        events.append((float(max(values[index], values[index + 1])), 1, (int(index), int(index + 1))))
    events.sort(key=lambda item: (item[0], item[1], item[2]))

    parent = list(range(num_vertices))
    elder_birth_value = [float(value) for value in values]
    elder_birth_index = list(range(num_vertices))
    present = [False] * num_vertices
    intervals = []
    merges = []

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def is_older(left_root: int, right_root: int) -> bool:
        left_key = (elder_birth_value[left_root], elder_birth_index[left_root])
        right_key = (elder_birth_value[right_root], elder_birth_index[right_root])
        return left_key <= right_key

    for filtration, dimension, simplex in events:
        if dimension == 0:
            present[simplex[0]] = True
            continue

        left_root = find(simplex[0])
        right_root = find(simplex[1])
        if left_root == right_root:
            continue
        older_root, younger_root = (left_root, right_root) if is_older(left_root, right_root) else (right_root, left_root)
        intervals.append(
            {
                "birth_index": int(elder_birth_index[younger_root]),
                "birth": serialize_float(elder_birth_value[younger_root]),
                "birth_hex": float_to_hex(elder_birth_value[younger_root]),
                "death": serialize_float(filtration),
                "death_hex": float_to_hex(filtration),
                "death_edge": list(simplex),
                "is_zero_length": bool(elder_birth_value[younger_root] == filtration),
            }
        )
        merges.append(
            {
                "edge": list(simplex),
                "merge_height": serialize_float(filtration),
                "merge_height_hex": float_to_hex(filtration),
                "elder_birth_index": int(elder_birth_index[older_root]),
                "elder_birth": serialize_float(elder_birth_value[older_root]),
                "younger_birth_index": int(elder_birth_index[younger_root]),
                "younger_birth": serialize_float(elder_birth_value[younger_root]),
            }
        )
        parent[younger_root] = older_root

    roots = sorted({find(index) for index in range(num_vertices)}, key=lambda root: (elder_birth_value[root], elder_birth_index[root]))
    surviving_root = roots[0]
    essential = {
        "birth_index": int(elder_birth_index[surviving_root]),
        "birth": serialize_float(elder_birth_value[surviving_root]),
        "birth_hex": float_to_hex(elder_birth_value[surviving_root]),
        "death": "inf",
        "death_hex": "inf",
        "death_edge": None,
        "is_zero_length": False,
    }

    local_minima = _local_minima(values)
    nonzero_intervals = [interval for interval in intervals if interval["death"] != interval["birth"]] + [essential]

    return {
        "local_minima": local_minima,
        "merge_events": merges,
        "all_intervals": intervals + [essential],
        "nonzero_intervals": nonzero_intervals,
        "births_match_local_minima": sorted(interval["birth_index"] for interval in nonzero_intervals)
        == sorted(item["index"] for item in local_minima),
        "finite_deaths_match_merge_heights": sorted(
            interval["death_hex"] for interval in nonzero_intervals if interval["death"] != "inf"
        )
        == sorted(merge["merge_height_hex"] for merge in merges if merge["merge_height"] != merge["younger_birth"]),
    }


def build_ripser_sparse_matrix(signal: np.ndarray | list[float]) -> csr_matrix:
    values = np.asarray(signal, dtype=np.float64)
    rows = list(range(values.size))
    cols = list(range(values.size))
    data = [float(value) for value in values]
    for index in range(values.size - 1):
        filtration = float(max(values[index], values[index + 1]))
        rows.extend([index, index + 1])
        cols.extend([index + 1, index])
        data.extend([filtration, filtration])
    return sparse.csr_matrix((data, (rows, cols)), shape=(values.size, values.size))


def serialize_ripser_sparse_matrix(signal: np.ndarray | list[float]) -> dict[str, Any]:
    matrix = build_ripser_sparse_matrix(signal).tocoo()
    entries = [
        {
            "row": int(row),
            "col": int(col),
            "value": serialize_float(value),
            "value_hex": float_to_hex(value),
        }
        for row, col, value in zip(matrix.row.tolist(), matrix.col.tolist(), matrix.data.tolist(), strict=False)
    ]
    return {
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "nnz": int(matrix.nnz),
        "entries": sorted(entries, key=lambda entry: (entry["row"], entry["col"], entry["value_hex"])),
    }


def serialize_dionysus_filtration(signal: np.ndarray | list[float]) -> list[dict[str, Any]]:
    filtration = dionysus.fill_freudenthal(np.asarray(signal, dtype=np.float64))
    return [
        {
            "vertices": [int(vertex) for vertex in simplex],
            "dimension": int(simplex.dimension()),
            "filtration": serialize_float(simplex.data),
            "filtration_hex": float_to_hex(simplex.data),
        }
        for simplex in filtration
    ]


def serialize_gudhi_cubical_encoding(signal: np.ndarray | list[float]) -> dict[str, Any]:
    cubical = gudhi.CubicalComplex(vertices=np.asarray(signal, dtype=np.float64))
    return {
        "vertices": [serialize_float(value) for value in cubical.vertices()],
        "vertices_hex": [float_to_hex(value) for value in cubical.vertices()],
        "top_dimensional_cells": [serialize_float(value) for value in cubical.top_dimensional_cells()],
        "top_dimensional_cells_hex": [float_to_hex(value) for value in cubical.top_dimensional_cells()],
        "all_cells": [serialize_float(value) for value in cubical.all_cells()],
        "all_cells_hex": [float_to_hex(value) for value in cubical.all_cells()],
    }


def run_lower_star_h0_case(signal: np.ndarray | list[float]) -> dict[str, Any]:
    values = np.asarray(signal, dtype=np.float64)
    raw_outputs = {
        "gudhi": run_gudhi_lower_star_h0(values),
        "ripser": run_ripser_lower_star_h0(values),
        "dionysus": run_dionysus_lower_star_h0(values),
    }
    canonicalized = {
        library: canonicalize_intervals(raw_outputs[library]["intervals"])
        for library in LOWER_STAR_LIBRARIES
    }
    agreement = compare_h0_canonicalized(canonicalized)
    betti_summary = build_betti0_summary(values, canonicalized)
    theorem_events = expected_h0_events(values)
    return {
        "signal_length": int(values.size),
        "raw_outputs": raw_outputs,
        "canonicalized": canonicalized,
        "agreement": agreement,
        "betti_summary": betti_summary,
        "theorem_events": theorem_events,
    }


def run_gudhi_lower_star_h0(signal: np.ndarray) -> dict[str, Any]:
    cubical = gudhi.CubicalComplex(vertices=np.asarray(signal, dtype=np.float64))
    persistence_pairs = cubical.persistence(homology_coeff_field=2, min_persistence=0.0)
    intervals = np.asarray(cubical.persistence_intervals_in_dimension(0), dtype=np.float64).reshape(-1, 2)
    return {
        "library": "gudhi",
        "parameters": {
            "constructor": "CubicalComplex(vertices=signal)",
            "homology_coeff_field": 2,
            "min_persistence": 0.0,
        },
        "raw_persistence_pairs": [
            {
                "dimension": int(dimension),
                "birth": serialize_float(interval[0]),
                "death": serialize_float(interval[1]),
                "birth_hex": float_to_hex(interval[0]),
                "death_hex": float_to_hex(interval[1]),
            }
            for dimension, interval in persistence_pairs
        ],
        "intervals": interval_array_to_records(intervals),
    }


def run_ripser_lower_star_h0(signal: np.ndarray) -> dict[str, Any]:
    matrix = build_ripser_sparse_matrix(signal)
    result = ripser(
        matrix,
        distance_matrix=True,
        maxdim=0,
        coeff=2,
        do_cocycles=False,
        n_perm=None,
    )
    intervals = np.asarray(result["dgms"][0], dtype=np.float64).reshape(-1, 2)
    return {
        "library": "ripser",
        "parameters": {
            "encoding": "sparse_distance_matrix_with_diagonal_vertex_births",
            "distance_matrix": True,
            "maxdim": 0,
            "coeff": 2,
            "n_perm": None,
        },
        "result_metadata": {
            key: serialize_json_value(value)
            for key, value in result.items()
            if key != "dgms"
        },
        "intervals": interval_array_to_records(intervals),
    }


def run_dionysus_lower_star_h0(signal: np.ndarray) -> dict[str, Any]:
    filtration = dionysus.fill_freudenthal(np.asarray(signal, dtype=np.float64))
    reduced_matrix = dionysus.homology_persistence(filtration, prime=2)
    diagrams = dionysus.init_diagrams(reduced_matrix, filtration)
    intervals = diagram_to_records(diagrams[0] if diagrams else [])
    return {
        "library": "dionysus",
        "parameters": {
            "constructor": "fill_freudenthal(signal)",
            "prime": 2,
        },
        "filtration_size": int(len(filtration)),
        "diagram_count": int(len(diagrams)),
        "intervals": intervals,
    }


def canonicalize_intervals(intervals: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        {
            "birth": serialize_float(deserialize_float(record["birth"])),
            "death": serialize_float(deserialize_float(record["death"])),
            "birth_hex": record.get("birth_hex", float_to_hex(record["birth"])),
            "death_hex": record.get("death_hex", float_to_hex(record["death"])),
        }
        for record in intervals
    ]
    records.sort(key=lambda item: (item["birth_hex"], item["death_hex"]))
    float32_records = roundtrip_records_to_float32(records)
    float32_records.sort(key=lambda item: (item["birth_hex"], item["death_hex"]))
    return {
        "count": len(records),
        "intervals": records,
        "float32_intervals": float32_records,
        "exact_signature": [signature_of_record(record) for record in records],
        "float32_signature": [signature_of_record(record) for record in float32_records],
    }


def compare_h0_canonicalized(canonicalized: dict[str, dict[str, Any]]) -> dict[str, Any]:
    exact_all = len({tuple(canonicalized[library]["exact_signature"]) for library in LOWER_STAR_LIBRARIES}) == 1
    float32_all = len({tuple(canonicalized[library]["float32_signature"]) for library in LOWER_STAR_LIBRARIES}) == 1
    pairwise = {}
    for left, right in (("gudhi", "ripser"), ("gudhi", "dionysus"), ("ripser", "dionysus")):
        pair_key = f"{left}__{right}"
        pairwise[pair_key] = {
            "exact_match": canonicalized[left]["exact_signature"] == canonicalized[right]["exact_signature"],
            "float32_match": canonicalized[left]["float32_signature"] == canonicalized[right]["float32_signature"],
            "max_abs_finite_endpoint_diff": serialize_float(
                max_abs_finite_endpoint_diff(canonicalized[left]["intervals"], canonicalized[right]["intervals"])
            ),
        }
    return {
        "exact_all_libraries": exact_all,
        "float32_stable_all_libraries": float32_all,
        "pairwise": pairwise,
    }


def build_betti0_summary(signal: np.ndarray, canonicalized: dict[str, dict[str, Any]]) -> dict[str, Any]:
    common = common_chain_filtration(signal)
    finite_values = [deserialize_float(item["value"]) for item in common["critical_values"]]
    rows = _betti_rows_from_values(finite_values, canonicalized, interval_key="intervals")
    float32_values = sorted({roundtrip_float32(value) for value in finite_values})
    float32_rows = _betti_rows_from_values(float32_values, canonicalized, interval_key="float32_intervals")
    return {
        "rows": rows,
        "all_equal": all(row["all_equal"] for row in rows),
        "float32_rows": float32_rows,
        "float32_all_equal": all(row["all_equal"] for row in float32_rows),
    }


def _betti_rows_from_values(
    finite_values: list[float],
    canonicalized: dict[str, dict[str, Any]],
    *,
    interval_key: str,
) -> list[dict[str, Any]]:
    if finite_values:
        lower_probe = math.nextafter(min(finite_values), -math.inf)
    else:
        lower_probe = -math.inf
    probes = [
        {
            "label": "below_min",
            "probe_value": serialize_float(lower_probe),
            "probe_value_hex": float_to_hex(lower_probe),
        }
    ]
    for value in finite_values:
        probe = math.nextafter(value, math.inf)
        probes.append(
            {
                "label": f"after_{float_to_hex(value)}",
                "critical_value": serialize_float(value),
                "critical_value_hex": float_to_hex(value),
                "probe_value": serialize_float(probe),
                "probe_value_hex": float_to_hex(probe),
            }
        )

    rows = []
    for probe in probes:
        probe_value = deserialize_float(probe["probe_value"])
        row = dict(probe)
        counts = {}
        for library in LOWER_STAR_LIBRARIES:
            counts[library] = count_betti0_at_probe(canonicalized[library][interval_key], probe_value)
            row[library] = counts[library]
        row["all_equal"] = len(set(counts.values())) == 1
        rows.append(row)
    return rows


def count_betti0_at_probe(intervals: list[dict[str, Any]], probe: float) -> int:
    count = 0
    for record in intervals:
        birth = deserialize_float(record["birth"])
        death = deserialize_float(record["death"])
        if birth <= probe and (death == "inf" or probe < death):
            count += 1
    return count


def max_abs_finite_endpoint_diff(
    left_intervals: list[dict[str, Any]],
    right_intervals: list[dict[str, Any]],
) -> float:
    left_pairs = sorted(
        (
            deserialize_float(record["birth"]),
            deserialize_float(record["death"]),
        )
        for record in left_intervals
    )
    right_pairs = sorted(
        (
            deserialize_float(record["birth"]),
            deserialize_float(record["death"]),
        )
        for record in right_intervals
    )
    if len(left_pairs) != len(right_pairs):
        return math.inf
    diffs = []
    for (left_birth, left_death), (right_birth, right_death) in zip(left_pairs, right_pairs, strict=False):
        if math.isfinite(left_birth) and math.isfinite(right_birth):
            diffs.append(abs(left_birth - right_birth))
        if math.isfinite(left_death) and math.isfinite(right_death):
            diffs.append(abs(left_death - right_death))
    return max(diffs, default=0.0)


def interval_array_to_records(intervals: np.ndarray) -> list[dict[str, Any]]:
    array = np.asarray(intervals, dtype=np.float64).reshape(-1, 2)
    return [
        {
            "birth": serialize_float(birth),
            "death": serialize_float(death),
            "birth_hex": float_to_hex(birth),
            "death_hex": float_to_hex(death),
        }
        for birth, death in array
    ]


def diagram_to_records(diagram: Any) -> list[dict[str, Any]]:
    return [
        {
            "birth": serialize_float(float(point.birth)),
            "death": serialize_float(float(point.death)),
            "birth_hex": float_to_hex(float(point.birth)),
            "death_hex": float_to_hex(float(point.death)),
        }
        for point in diagram
    ]


def roundtrip_records_to_float32(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rounded = []
    for record in records:
        birth = roundtrip_float32(deserialize_float(record["birth"]))
        death = roundtrip_float32(deserialize_float(record["death"]))
        rounded.append(
            {
                "birth": serialize_float(birth),
                "death": serialize_float(death),
                "birth_hex": float_to_hex(birth),
                "death_hex": float_to_hex(death),
            }
        )
    return rounded


def roundtrip_float32(value: float) -> float:
    if math.isinf(value) or math.isnan(value):
        return value
    return float(np.float32(value))


def signature_of_record(record: dict[str, Any]) -> str:
    return f"{record['birth_hex']}|{record['death_hex']}"


def float_to_hex(value: float | str) -> str:
    number = deserialize_float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "inf" if number > 0 else "-inf"
    return np.float64(number).hex()


def serialize_float(value: float | str) -> float | str:
    number = deserialize_float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "inf" if number > 0 else "-inf"
    return number


def deserialize_float(value: float | str) -> float:
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
    if isinstance(value, spmatrix):
        matrix = value.tocoo()
        return {
            "format": value.getformat(),
            "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
            "entries": [
                {
                    "row": int(row),
                    "col": int(col),
                    "value": serialize_float(entry),
                    "value_hex": float_to_hex(entry),
                }
                for row, col, entry in zip(matrix.row.tolist(), matrix.col.tolist(), matrix.data.tolist(), strict=False)
            ],
        }
    if isinstance(value, np.ndarray):
        return serialize_json_value(value.tolist())
    if isinstance(value, np.generic):
        return serialize_json_value(value.item())
    if isinstance(value, float):
        return serialize_float(value)
    return value


def _base_signal_benchmarks(*, include_aah: bool) -> list[_BaseSignalBenchmark]:
    synthetic = [
        _BaseSignalBenchmark(
            benchmark_id="synthetic_single_basin_3",
            family="synthetic",
            label="Synthetic single basin (n=3)",
            signal=np.array([0.75, 0.125, 0.875], dtype=np.float64),
            metadata={
                "generator": "handcrafted_signal",
                "signal_kind": "synthetic",
            },
            notes=(
                "Distinct dyadic heights with one strict interior minimum.",
            ),
        ),
        _BaseSignalBenchmark(
            benchmark_id="synthetic_double_well_5",
            family="synthetic",
            label="Synthetic double well (n=5)",
            signal=np.array([0.625, 0.125, 0.75, 0.25, 0.5], dtype=np.float64),
            metadata={
                "generator": "handcrafted_signal",
                "signal_kind": "synthetic",
            },
            notes=(
                "Two strict local minima with a single finite merge height.",
            ),
        ),
        _BaseSignalBenchmark(
            benchmark_id="synthetic_three_minima_7",
            family="synthetic",
            label="Synthetic three minima (n=7)",
            signal=np.array([0.875, 0.25, 0.75, 0.125, 0.625, 0.375, 1.0], dtype=np.float64),
            metadata={
                "generator": "handcrafted_signal",
                "signal_kind": "synthetic",
            },
            notes=(
                "Three strict minima with nested merges on a length-7 chain.",
            ),
        ),
        _BaseSignalBenchmark(
            benchmark_id="synthetic_staggered_valleys_6",
            family="synthetic",
            label="Synthetic staggered valleys (n=6)",
            signal=np.array([0.5, 0.0, 0.75, 0.125, 0.625, 0.25], dtype=np.float64),
            metadata={
                "generator": "handcrafted_signal",
                "signal_kind": "synthetic",
            },
            notes=(
                "Endpoint-adjacent minimum plus two interior minima.",
            ),
        ),
    ]
    if not include_aah:
        return synthetic

    aah_specs = [
        ("aah_n8_l1p50_phi0p10_s0", "AAH profile n=8, lambda=1.50, phase=0.10, state=0", 8, 1.50, 0.10, 0),
        ("aah_n8_l2p00_phi0p30_s3", "AAH profile n=8, lambda=2.00, phase=0.30, state=3", 8, 2.00, 0.30, 3),
        ("aah_n13_l1p00_phi0p20_s6", "AAH profile n=13, lambda=1.00, phase=0.20, state=6", 13, 1.00, 0.20, 6),
    ]
    benchmarks = list(synthetic)
    for benchmark_id, label, n_sites, lam, phase, state_index in aah_specs:
        signal = generate_aah_intensity_profile(
            n_sites=n_sites,
            lambda_strength=lam,
            phase=phase,
            state_index=state_index,
        )
        benchmarks.append(
            _BaseSignalBenchmark(
                benchmark_id=benchmark_id,
                family="aah",
                label=label,
                signal=signal,
                metadata={
                    "generator": "generalized_aah_intensity_profile",
                    "signal_kind": "aah",
                    "n_sites": n_sites,
                    "lambda_strength": lam,
                    "phase": phase,
                    "state_index": state_index,
                    "boundary_condition": "open",
                    "hopping": 1.0,
                    "irrational_frequency": 1.0 / GOLDEN_RATIO,
                },
                notes=(
                    "Intensity profile from an Aubry-Andre-Harper tight-binding eigenstate.",
                    "The profile is normalized to sum to 1.",
                ),
            )
        )
    return benchmarks


def generate_aah_intensity_profile(
    *,
    n_sites: int,
    lambda_strength: float,
    phase: float,
    state_index: int,
) -> np.ndarray:
    indices = np.arange(n_sites, dtype=np.float64)
    onsite = lambda_strength * np.cos(2.0 * math.pi * indices / GOLDEN_RATIO + phase)
    hamiltonian = np.diag(onsite)
    for index in range(n_sites - 1):
        hamiltonian[index, index + 1] = -1.0
        hamiltonian[index + 1, index] = -1.0
    _, eigenvectors = np.linalg.eigh(hamiltonian)
    state = eigenvectors[:, state_index]
    intensities = np.abs(state) ** 2
    return np.asarray(intensities / intensities.sum(), dtype=np.float64)


def _materialize_signal_mode(signal: np.ndarray, *, mode: str, quantization_step: float) -> np.ndarray:
    if mode == "floating":
        return np.asarray(signal, dtype=np.float64)
    if mode == "quantized":
        return quantize_signal(signal, step=quantization_step)
    raise ValueError(f"Unknown signal mode: {mode}")


def _local_minima(signal: np.ndarray) -> list[dict[str, Any]]:
    minima = []
    for index, value in enumerate(signal):
        left = signal[index - 1] if index > 0 else math.inf
        right = signal[index + 1] if index + 1 < signal.size else math.inf
        if value < left and value < right:
            minima.append(
                {
                    "index": int(index),
                    "value": serialize_float(value),
                    "value_hex": float_to_hex(value),
                }
            )
    return minima


def _hash_array(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(np.asarray(array))
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(repr(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


__all__ = [
    "DEFAULT_SIGNAL_MODES",
    "DEFAULT_SIGNAL_QUANTIZATION_STEP",
    "LOWER_STAR_LIBRARIES",
    "LowerStarH0Benchmark",
    "benchmark_to_manifest",
    "build_ripser_sparse_matrix",
    "common_chain_filtration",
    "expected_h0_events",
    "generate_aah_intensity_profile",
    "generate_lower_star_h0_benchmarks",
    "quantize_signal",
    "run_lower_star_h0_case",
    "serialize_dionysus_filtration",
    "serialize_gudhi_cubical_encoding",
    "serialize_json_value",
    "serialize_ripser_sparse_matrix",
]
