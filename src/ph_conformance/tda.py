from __future__ import annotations

import itertools
import math
from typing import Any

import dionysus
import gudhi
import numpy as np
from ripser import ripser
from scipy.spatial.distance import squareform


LIBRARIES = ("gudhi", "ripser", "dionysus")

def run_case(
    distance_matrix: np.ndarray | list[list[float]],
    coeff: int,
    maxdim: int,
    threshold: float,
    case_id: str,
) -> dict[str, Any]:
    matrix = prepare_distance_matrix(distance_matrix)
    threshold_value = normalize_threshold(threshold)

    raw_outputs = {
        "gudhi": run_gudhi(matrix, coeff=coeff, maxdim=maxdim, threshold=threshold_value),
        "ripser": run_ripser(matrix, coeff=coeff, maxdim=maxdim, threshold=threshold_value),
        "dionysus": run_dionysus(matrix, coeff=coeff, maxdim=maxdim, threshold=threshold_value),
    }

    canonicalized = {
        library: canonicalize_by_dimension(raw_outputs[library]["intervals_by_dimension"], maxdim=maxdim)
        for library in LIBRARIES
    }
    agreement = compare_canonical_multisets(canonicalized, maxdim=maxdim)
    discrepancy = build_discrepancy_payload(canonicalized, agreement, maxdim=maxdim)

    return {
        "case_id": case_id,
        "coeff": int(coeff),
        "maxdim": int(maxdim),
        "threshold": serialize_float(threshold_value),
        "threshold_hex": float_to_hex(threshold_value),
        "matrix_size": int(matrix.shape[0]),
        "raw_outputs": raw_outputs,
        "canonicalized": canonicalized,
        "agreement": agreement,
        "discrepancy": discrepancy,
    }


def prepare_distance_matrix(distance_matrix: np.ndarray | list[list[float]]) -> np.ndarray:
    matrix = np.asarray(distance_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("distance_matrix must be a square 2D array")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("distance_matrix must contain only finite values")
    if not np.allclose(matrix, matrix.T, atol=0.0, rtol=0.0):
        raise ValueError("distance_matrix must be exactly symmetric")
    matrix = matrix.copy()
    np.fill_diagonal(matrix, 0.0)
    return matrix


def normalize_threshold(threshold: float) -> float:
    value = float(threshold)
    if math.isnan(value):
        raise ValueError("threshold must not be NaN")
    return value


def run_gudhi(
    distance_matrix: np.ndarray,
    *,
    coeff: int,
    maxdim: int,
    threshold: float,
) -> dict[str, Any]:
    rips_complex = gudhi.RipsComplex(
        distance_matrix=distance_matrix,
        max_edge_length=threshold,
    )
    simplex_tree = rips_complex.create_simplex_tree(max_dimension=maxdim + 1)
    persistence_pairs = simplex_tree.persistence(
        homology_coeff_field=coeff,
        min_persistence=-1.0,
        persistence_dim_max=True,
    )

    intervals_by_dimension = {
        dim: np.asarray(simplex_tree.persistence_intervals_in_dimension(dim), dtype=np.float64).reshape(-1, 2)
        for dim in range(maxdim + 1)
    }

    return {
        "library": "gudhi",
        "parameters": {
            "homology_coeff_field": int(coeff),
            "max_dimension": int(maxdim + 1),
            "max_edge_length": serialize_float(threshold),
            "sparse": None,
        },
        "raw_persistence_pairs": [
            {
                "dimension": int(dim),
                "birth": serialize_float(interval[0]),
                "death": serialize_float(interval[1]),
                "birth_hex": float_to_hex(interval[0]),
                "death_hex": float_to_hex(interval[1]),
            }
            for dim, interval in persistence_pairs
        ],
        "intervals_by_dimension": serialize_intervals_by_dimension(intervals_by_dimension, maxdim=maxdim),
    }


def run_ripser(
    distance_matrix: np.ndarray,
    *,
    coeff: int,
    maxdim: int,
    threshold: float,
) -> dict[str, Any]:
    result = ripser(
        distance_matrix,
        distance_matrix=True,
        maxdim=maxdim,
        thresh=threshold,
        coeff=coeff,
        n_perm=None,
        do_cocycles=False,
    )
    dgms = result["dgms"]
    intervals_by_dimension = {
        dim: np.asarray(dgms[dim], dtype=np.float64).reshape(-1, 2)
        for dim in range(maxdim + 1)
    }

    return {
        "library": "ripser",
        "parameters": {
            "distance_matrix": True,
            "maxdim": int(maxdim),
            "thresh": serialize_float(threshold),
            "coeff": int(coeff),
            "n_perm": None,
            "do_cocycles": False,
        },
        "result_metadata": {
            key: serialize_value(value)
            for key, value in result.items()
            if key != "dgms"
        },
        "intervals_by_dimension": serialize_intervals_by_dimension(intervals_by_dimension, maxdim=maxdim),
    }


def run_dionysus(
    distance_matrix: np.ndarray,
    *,
    coeff: int,
    maxdim: int,
    threshold: float,
) -> dict[str, Any]:
    condensed = squareform(distance_matrix, force="tovector", checks=False)
    filtration = dionysus.fill_rips(condensed, maxdim + 1, threshold)
    reduced_matrix = dionysus.homology_persistence(filtration, prime=coeff)
    diagrams = dionysus.init_diagrams(reduced_matrix, filtration)

    intervals_by_dimension = {
        dim: diagram_to_array(diagrams[dim]) if dim < len(diagrams) else np.empty((0, 2), dtype=np.float64)
        for dim in range(maxdim + 1)
    }

    return {
        "library": "dionysus",
        "parameters": {
            "prime": int(coeff),
            "skeleton_dimension": int(maxdim + 1),
            "threshold": serialize_float(threshold),
            "input_format": "condensed_distance_matrix",
        },
        "filtration_size": int(len(filtration)),
        "diagram_count": int(len(diagrams)),
        "intervals_by_dimension": serialize_intervals_by_dimension(intervals_by_dimension, maxdim=maxdim),
    }


def diagram_to_array(diagram: Any) -> np.ndarray:
    if len(diagram) == 0:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray([[float(point.birth), float(point.death)] for point in diagram], dtype=np.float64)


def serialize_intervals_by_dimension(
    intervals_by_dimension: dict[int, np.ndarray],
    *,
    maxdim: int,
) -> dict[str, list[dict[str, Any]]]:
    return {
        str(dim): interval_array_to_records(intervals_by_dimension.get(dim, np.empty((0, 2), dtype=np.float64)))
        for dim in range(maxdim + 1)
    }


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


def canonicalize_by_dimension(
    serialized_intervals_by_dimension: dict[str, list[dict[str, Any]]],
    *,
    maxdim: int,
) -> dict[str, dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for dim in range(maxdim + 1):
        raw_records = serialized_intervals_by_dimension.get(str(dim), [])
        typed_records = []
        numeric_pairs = []
        for record in raw_records:
            birth = deserialize_float(record["birth"])
            death = deserialize_float(record["death"])
            birth_hex = record.get("birth_hex") or float_to_hex(birth)
            death_hex = record.get("death_hex") or float_to_hex(death)
            typed_records.append(
                {
                    "birth": serialize_float(birth),
                    "death": serialize_float(death),
                    "birth_hex": birth_hex,
                    "death_hex": death_hex,
                }
            )
            numeric_pairs.append([birth, death])

        typed_records.sort(key=lambda item: (item["birth_hex"], item["death_hex"]))
        numeric_pairs.sort(key=lambda pair: (float_to_hex(pair[0]), float_to_hex(pair[1])))
        exact_signature = [f"{item['birth_hex']}|{item['death_hex']}" for item in typed_records]
        canonical[str(dim)] = {
            "count": len(typed_records),
            "intervals": typed_records,
            "exact_signature": exact_signature,
            "numeric_pairs": numeric_pairs,
        }
    return canonical


def compare_canonical_multisets(
    canonicalized: dict[str, dict[str, dict[str, Any]]],
    *,
    maxdim: int,
) -> dict[str, Any]:
    by_dimension: dict[str, Any] = {}
    all_exact = True

    for dim in range(maxdim + 1):
        dim_key = str(dim)
        signatures = {
            library: canonicalized[library][dim_key]["exact_signature"]
            for library in LIBRARIES
        }
        pairwise = {}
        dim_exact = True
        for left, right in itertools.combinations(LIBRARIES, 2):
            exact_match = signatures[left] == signatures[right]
            pairwise[f"{left}__{right}"] = {
                "exact_match": exact_match,
                "left_count": canonicalized[left][dim_key]["count"],
                "right_count": canonicalized[right][dim_key]["count"],
            }
            dim_exact = dim_exact and exact_match

        by_dimension[dim_key] = {
            "exact_all_libraries": dim_exact,
            "signatures": signatures,
            "pairwise": pairwise,
        }
        all_exact = all_exact and dim_exact

    return {
        "exact_all_libraries": all_exact,
        "by_dimension": by_dimension,
    }


def build_discrepancy_payload(
    canonicalized: dict[str, dict[str, dict[str, Any]]],
    agreement: dict[str, Any],
    *,
    maxdim: int,
) -> dict[str, Any]:
    payload = {
        "has_discrepancy": not agreement["exact_all_libraries"],
        "by_dimension": {},
    }

    if agreement["exact_all_libraries"]:
        return payload

    for dim in range(maxdim + 1):
        dim_key = str(dim)
        dim_agreement = agreement["by_dimension"][dim_key]
        if dim_agreement["exact_all_libraries"]:
            continue

        pairwise_metrics = {}
        for left, right in itertools.combinations(LIBRARIES, 2):
            pair_key = f"{left}__{right}"
            exact_match = dim_agreement["pairwise"][pair_key]["exact_match"]
            left_numeric = canonicalized[left][dim_key]["numeric_pairs"]
            right_numeric = canonicalized[right][dim_key]["numeric_pairs"]
            metrics = {
                "exact_match": exact_match,
                "left_signature": canonicalized[left][dim_key]["exact_signature"],
                "right_signature": canonicalized[right][dim_key]["exact_signature"],
            }
            if not exact_match:
                metrics.update(compute_pairwise_metrics(left_numeric, right_numeric))
            pairwise_metrics[pair_key] = metrics

        payload["by_dimension"][dim_key] = {
            "signatures": dim_agreement["signatures"],
            "pairwise": pairwise_metrics,
        }

    return payload


def compute_pairwise_metrics(
    left_numeric_pairs: list[list[float]],
    right_numeric_pairs: list[list[float]],
) -> dict[str, Any]:
    left_diagram = dionysus.Diagram(left_numeric_pairs)
    right_diagram = dionysus.Diagram(right_numeric_pairs)

    metrics: dict[str, Any] = {}
    for name, fn in (
        ("bottleneck_distance", lambda: dionysus.bottleneck_distance(left_diagram, right_diagram, delta=0.0)),
        (
            "wasserstein_distance_q2",
            lambda: dionysus.wasserstein_distance(left_diagram, right_diagram, q=2, delta=0.0),
        ),
    ):
        try:
            value = fn()
            metrics[name] = serialize_float(value)
            metrics[f"{name}_hex"] = float_to_hex(value)
        except Exception as exc:  # pragma: no cover - library-dependent failure mode
            metrics[name] = None
            metrics[f"{name}_error"] = f"{type(exc).__name__}: {exc}"
    return metrics


def float_to_hex(value: float) -> str:
    number = float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "inf" if number > 0 else "-inf"
    return np.float64(number).hex()


def serialize_float(value: float) -> float | str:
    number = float(value)
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
    return float(value)


def serialize_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [serialize_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return serialize_value(value.item())
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if isinstance(value, float):
        return serialize_float(value)
    return value


__all__ = [
    "LIBRARIES",
    "canonicalize_by_dimension",
    "compare_canonical_multisets",
    "prepare_distance_matrix",
    "run_case",
    "run_dionysus",
    "run_gudhi",
    "run_ripser",
]
