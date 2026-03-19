from __future__ import annotations

import hashlib
import itertools
import math
from dataclasses import dataclass
from typing import Any, Iterable

import dionysus
import numpy as np
from persim import PersistenceImager
from scipy.spatial.distance import pdist, squareform

from .benchmarks import quantize_distance_matrix
from .tda import LIBRARIES, deserialize_float, prepare_distance_matrix, serialize_float

RANDOM_SEEDS = (0,)
COORDINATE_JITTER_MAGNITUDES = (0.01, 0.05)
VACANCY_COUNTS = (1, 2)
MATRIX_NOISE_MAGNITUDES = (1.0e-4, 1.0e-2)
QUANTIZATION_MAGNITUDES = (1.0e-3, 2.0e-2)
BETTI_GRID_SIZE = 65
PERSISTENCE_IMAGE_RESOLUTION = 16
SUMMARY_SCALAR_KEYS = (
    "bottleneck_to_baseline",
    "wasserstein_to_baseline",
    "betti_l1_to_baseline",
    "betti_linf_to_baseline",
    "lifetime_l1_delta",
    "lifetime_l2_delta",
    "lifetime_linf_delta",
    "persistent_entropy_delta",
    "persistence_image_l2_to_baseline",
)
PAIRWISE_LIBRARY_PAIRS = tuple(itertools.combinations(LIBRARIES, 2))


@dataclass(frozen=True)
class PerturbedBenchmark:
    benchmark_id: str
    source_benchmark_id: str
    family: str
    label: str
    mode: str
    distance_matrix: np.ndarray
    point_cloud: np.ndarray | None
    selected_threshold: float
    full_threshold: float
    coeffs: tuple[int, ...]
    maxdims: tuple[int, ...]
    metadata: dict[str, Any]
    notes: tuple[str, ...]
    perturbation: dict[str, Any]


def build_perturbed_benchmarks(
    benchmark_manifest: dict[str, Any],
    distance_matrix: np.ndarray,
    point_cloud: np.ndarray | None,
    *,
    random_seeds: tuple[int, ...] = RANDOM_SEEDS,
) -> list[PerturbedBenchmark]:
    matrix = prepare_distance_matrix(distance_matrix)
    points = None if point_cloud is None else np.asarray(point_cloud, dtype=np.float64)
    benchmarks: list[PerturbedBenchmark] = []

    if points is not None:
        for magnitude in COORDINATE_JITTER_MAGNITUDES:
            for seed in random_seeds:
                sigma_scale = reference_length_scale(benchmark_manifest, matrix)
                sigma = magnitude * sigma_scale
                rng = np.random.default_rng(seed)
                jitter = rng.normal(loc=0.0, scale=sigma, size=points.shape)
                jittered_points = np.asarray(points + jitter, dtype=np.float64)
                jittered_matrix = pairwise_distance_matrix(jittered_points)
                perturbation = {
                    "family": "coordinate_jitter",
                    "magnitude": magnitude,
                    "magnitude_unit": "relative_sigma",
                    "sigma_absolute": sigma,
                    "reference_length_scale": sigma_scale,
                    "seed": seed,
                }
                benchmarks.append(
                    build_perturbed_benchmark(
                        benchmark_manifest=benchmark_manifest,
                        distance_matrix=jittered_matrix,
                        point_cloud=jittered_points,
                        perturbation=perturbation,
                        magnitude_label=f"m{slug_float(magnitude)}",
                        seed=seed,
                    )
                )

    for delete_count in VACANCY_COUNTS:
        if delete_count >= matrix.shape[0]:
            continue
        for seed in random_seeds:
            keep_indices, removed_indices = vacancy_indices(matrix.shape[0], delete_count, seed)
            vacancy_matrix = matrix[np.ix_(keep_indices, keep_indices)]
            vacancy_points = None if points is None else points[keep_indices]
            perturbation = {
                "family": "vacancy",
                "magnitude": delete_count,
                "magnitude_unit": "deleted_vertices",
                "relative_magnitude": delete_count / float(matrix.shape[0]),
                "seed": seed,
                "deleted_count": delete_count,
                "kept_indices": keep_indices.tolist(),
                "removed_indices": removed_indices.tolist(),
            }
            benchmarks.append(
                build_perturbed_benchmark(
                    benchmark_manifest=benchmark_manifest,
                    distance_matrix=vacancy_matrix,
                    point_cloud=vacancy_points,
                    perturbation=perturbation,
                    magnitude_label=f"k{delete_count}",
                    seed=seed,
                )
            )

    for magnitude in MATRIX_NOISE_MAGNITUDES:
        for seed in random_seeds:
            scale = max_off_diagonal(matrix)
            sigma = magnitude * scale
            noisy_matrix = matrix_entry_noise(matrix, sigma=sigma, seed=seed)
            perturbation = {
                "family": "matrix_entry_noise",
                "magnitude": magnitude,
                "magnitude_unit": "relative_sigma",
                "sigma_absolute": sigma,
                "reference_distance_scale": scale,
                "seed": seed,
            }
            benchmarks.append(
                build_perturbed_benchmark(
                    benchmark_manifest=benchmark_manifest,
                    distance_matrix=noisy_matrix,
                    point_cloud=None,
                    perturbation=perturbation,
                    magnitude_label=f"m{slug_float(magnitude)}",
                    seed=seed,
                )
            )

    for magnitude in QUANTIZATION_MAGNITUDES:
        scale = max_off_diagonal(matrix)
        step = magnitude * scale
        quantized_matrix = quantize_distance_matrix(matrix, step=step)
        perturbation = {
            "family": "quantization",
            "magnitude": magnitude,
            "magnitude_unit": "relative_step",
            "step_absolute": step,
            "reference_distance_scale": scale,
            "seed": None,
        }
        benchmarks.append(
            build_perturbed_benchmark(
                benchmark_manifest=benchmark_manifest,
                distance_matrix=quantized_matrix,
                point_cloud=None,
                perturbation=perturbation,
                magnitude_label=f"m{slug_float(magnitude)}",
                seed=None,
            )
        )

    return benchmarks


def build_perturbed_benchmark(
    *,
    benchmark_manifest: dict[str, Any],
    distance_matrix: np.ndarray,
    point_cloud: np.ndarray | None,
    perturbation: dict[str, Any],
    magnitude_label: str,
    seed: int | None,
) -> PerturbedBenchmark:
    matrix = prepare_distance_matrix(distance_matrix)
    points = None if point_cloud is None else np.asarray(point_cloud, dtype=np.float64)
    base_metadata = dict(benchmark_manifest.get("metadata", {}))
    selected_threshold = resolve_threshold(
        matrix,
        strategy=str(base_metadata["threshold_strategy"]),
        parameter=base_metadata["threshold_parameter"],
    )
    full_threshold = max_off_diagonal(matrix)
    family = str(benchmark_manifest["family"])
    source_benchmark_id = str(benchmark_manifest["benchmark_id"])
    family_slug = str(perturbation["family"])
    seed_suffix = "" if seed is None else f"__s{seed}"
    benchmark_id = f"{source_benchmark_id}__{family_slug}__{magnitude_label}{seed_suffix}"
    metadata = dict(base_metadata)
    metadata.update(
        {
            "distance_matrix_hash": hash_array(matrix),
            "point_cloud_hash": None if points is None else hash_array(points),
            "source_benchmark_id": source_benchmark_id,
            "source_distance_matrix_hash": benchmark_manifest["metadata"]["distance_matrix_hash"],
            "source_point_cloud_hash": benchmark_manifest["metadata"]["point_cloud_hash"],
            "perturbation_family": family_slug,
            "perturbation_magnitude": perturbation["magnitude"],
            "perturbation_seed": perturbation.get("seed"),
        }
    )
    notes = tuple(benchmark_manifest.get("notes", ())) + (
        f"Perturbation family: {family_slug}.",
        "Thresholds are recomputed from the perturbed input using the original benchmark threshold rule.",
    )
    return PerturbedBenchmark(
        benchmark_id=benchmark_id,
        source_benchmark_id=source_benchmark_id,
        family=family,
        label=str(benchmark_manifest["label"]),
        mode=str(benchmark_manifest["mode"]),
        distance_matrix=matrix,
        point_cloud=points,
        selected_threshold=selected_threshold,
        full_threshold=full_threshold,
        coeffs=tuple(int(value) for value in benchmark_manifest["coeffs"]),
        maxdims=tuple(int(value) for value in benchmark_manifest["maxdims"]),
        metadata=metadata,
        notes=notes,
        perturbation=dict(perturbation),
    )


def perturbed_benchmark_to_manifest(benchmark: PerturbedBenchmark) -> dict[str, Any]:
    return {
        "benchmark_id": benchmark.benchmark_id,
        "source_benchmark_id": benchmark.source_benchmark_id,
        "family": benchmark.family,
        "label": benchmark.label,
        "mode": benchmark.mode,
        "selected_threshold": benchmark.selected_threshold,
        "full_threshold": benchmark.full_threshold,
        "full_filtration_feasible": True,
        "coeffs": list(benchmark.coeffs),
        "maxdims": list(benchmark.maxdims),
        "has_point_cloud": benchmark.point_cloud is not None,
        "metadata": dict(benchmark.metadata),
        "notes": list(benchmark.notes),
        "distance_matrix_shape": list(benchmark.distance_matrix.shape),
        "point_cloud_shape": None if benchmark.point_cloud is None else list(benchmark.point_cloud.shape),
        "perturbation": dict(benchmark.perturbation),
    }


def pairwise_distance_matrix(point_cloud: np.ndarray) -> np.ndarray:
    return canonical_distance_matrix(squareform(pdist(np.asarray(point_cloud, dtype=np.float64), metric="euclidean")))


def canonical_distance_matrix(matrix: np.ndarray) -> np.ndarray:
    array = np.asarray(matrix, dtype=np.float64)
    symmetrized = 0.5 * (array + array.T)
    symmetrized = np.maximum(symmetrized, 0.0)
    np.fill_diagonal(symmetrized, 0.0)
    return symmetrized


def max_off_diagonal(matrix: np.ndarray) -> float:
    values = off_diagonal_values(matrix)
    return float(np.max(values))


def min_positive_off_diagonal(matrix: np.ndarray) -> float:
    values = off_diagonal_values(matrix)
    positive = values[values > 0.0]
    if positive.size == 0:
        return 1.0
    return float(np.min(positive))


def off_diagonal_values(matrix: np.ndarray) -> np.ndarray:
    indices = np.triu_indices_from(matrix, k=1)
    values = np.asarray(matrix[indices], dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("Matrix has no finite off-diagonal entries")
    return finite


def resolve_threshold(matrix: np.ndarray, *, strategy: str, parameter: Any) -> float:
    if strategy == "nearest_neighbor":
        if parameter is None:
            raise ValueError("nearest_neighbor threshold requires a parameter")
        return float(parameter)
    if strategy == "matrix_quantile":
        if parameter is None:
            raise ValueError("matrix_quantile threshold requires a parameter")
        values = off_diagonal_values(matrix)
        return float(np.quantile(values, float(parameter), method="nearest"))
    raise ValueError(f"Unknown threshold strategy: {strategy}")


def reference_length_scale(benchmark_manifest: dict[str, Any], distance_matrix: np.ndarray) -> float:
    metadata = benchmark_manifest.get("metadata", {})
    if metadata.get("nearest_neighbor_distance") is not None:
        return float(metadata["nearest_neighbor_distance"])
    return min_positive_off_diagonal(distance_matrix)


def vacancy_indices(size: int, delete_count: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    if delete_count <= 0 or delete_count >= size:
        raise ValueError("delete_count must lie strictly between 0 and the matrix size")
    rng = np.random.default_rng(seed)
    removed = np.sort(rng.choice(size, size=delete_count, replace=False))
    keep_mask = np.ones(size, dtype=bool)
    keep_mask[removed] = False
    keep = np.flatnonzero(keep_mask)
    return keep, removed


def matrix_entry_noise(matrix: np.ndarray, *, sigma: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.normal(loc=0.0, scale=sigma, size=matrix.shape)
    upper = np.triu(noise, k=1)
    symmetric_noise = upper + upper.T
    return canonical_distance_matrix(np.asarray(matrix, dtype=np.float64) + symmetric_noise)


def hash_array(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(repr(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def slug_float(value: float) -> str:
    return f"{float(value):.6g}".replace("-", "m").replace(".", "p")


def interval_records_to_pairs(records: list[dict[str, Any]]) -> list[list[float]]:
    pairs: list[list[float]] = []
    for record in records:
        birth = deserialize_float(record["birth"])
        death = deserialize_float(record["death"])
        pairs.append([float(birth), float(death)])
    return pairs


def diagram_pairs_from_case(case_payload: dict[str, Any], library: str, dim: int) -> list[list[float]]:
    records = case_payload["results"]["raw_outputs"][library]["intervals_by_dimension"].get(str(dim), [])
    return interval_records_to_pairs(records)


def finite_lifetimes(pairs: Iterable[Iterable[float]]) -> np.ndarray:
    values = []
    for birth, death in pairs:
        birth_value = float(birth)
        death_value = float(death)
        if math.isinf(death_value):
            continue
        values.append(max(0.0, death_value - birth_value))
    if not values:
        return np.empty((0,), dtype=np.float64)
    return np.asarray(values, dtype=np.float64)


def diagram_scalar_summaries(pairs: list[list[float]]) -> dict[str, float | int]:
    lifetimes = finite_lifetimes(pairs)
    positive_lifetimes = lifetimes[lifetimes > 0.0]
    if positive_lifetimes.size == 0:
        persistent_entropy = 0.0
    else:
        weights = positive_lifetimes / np.sum(positive_lifetimes)
        persistent_entropy = float(-np.sum(weights * np.log2(weights)))
    essential_count = sum(1 for _, death in pairs if math.isinf(float(death)))
    return {
        "bar_count": int(len(pairs)),
        "finite_bar_count": int(lifetimes.size),
        "essential_bar_count": int(essential_count),
        "lifetime_l1": float(np.sum(lifetimes)) if lifetimes.size else 0.0,
        "lifetime_l2": float(np.linalg.norm(lifetimes, ord=2)) if lifetimes.size else 0.0,
        "lifetime_linf": float(np.max(lifetimes)) if lifetimes.size else 0.0,
        "persistent_entropy": persistent_entropy,
    }


def betti_grid_from_groups(pairs_collection: Iterable[list[list[float]]], threshold_values: Iterable[float]) -> np.ndarray:
    horizon = 0.0
    for threshold in threshold_values:
        horizon = max(horizon, float(threshold))
    for pairs in pairs_collection:
        for birth, death in pairs:
            horizon = max(horizon, float(birth))
            if not math.isinf(float(death)):
                horizon = max(horizon, float(death))
    if horizon <= 0.0:
        horizon = 1.0
    return np.linspace(0.0, horizon, BETTI_GRID_SIZE, dtype=np.float64)


def betti_curve(pairs: list[list[float]], grid: np.ndarray) -> np.ndarray:
    counts = np.zeros_like(grid, dtype=np.int64)
    for index, value in enumerate(grid):
        count = 0
        for birth, death in pairs:
            birth_value = float(birth)
            death_value = float(death)
            if value < birth_value:
                continue
            if math.isinf(death_value) or value < death_value:
                count += 1
        counts[index] = count
    return counts


def betti_curve_distances(curve: np.ndarray, baseline_curve: np.ndarray, grid: np.ndarray) -> dict[str, float]:
    delta = np.abs(np.asarray(curve, dtype=np.float64) - np.asarray(baseline_curve, dtype=np.float64))
    l1 = float(np.trapezoid(delta, x=np.asarray(grid, dtype=np.float64)))
    linf = float(np.max(delta)) if delta.size else 0.0
    return {
        "betti_l1_to_baseline": l1,
        "betti_linf_to_baseline": linf,
    }


def diagram_distance_metrics(left_pairs: list[list[float]], right_pairs: list[list[float]]) -> dict[str, float | None]:
    left = dionysus.Diagram(left_pairs)
    right = dionysus.Diagram(right_pairs)
    metrics: dict[str, float | None] = {
        "bottleneck_to_baseline": None,
        "wasserstein_to_baseline": None,
    }
    try:
        metrics["bottleneck_to_baseline"] = float(dionysus.bottleneck_distance(left, right, delta=0.0))
    except Exception:  # pragma: no cover - library dependent
        metrics["bottleneck_to_baseline"] = None
    try:
        metrics["wasserstein_to_baseline"] = float(dionysus.wasserstein_distance(left, right, q=2, delta=0.0))
    except Exception:  # pragma: no cover - library dependent
        metrics["wasserstein_to_baseline"] = None
    return metrics


def finite_birth_persistence_points(pairs: list[list[float]]) -> np.ndarray:
    points = []
    for birth, death in pairs:
        birth_value = float(birth)
        death_value = float(death)
        if math.isinf(death_value):
            continue
        persistence = max(0.0, death_value - birth_value)
        if persistence <= 0.0:
            continue
        points.append([birth_value, persistence])
    if not points:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(points, dtype=np.float64)


def build_persistence_image_config(pairs_collection: Iterable[list[list[float]]]) -> dict[str, float]:
    births = [0.0]
    persistences = [0.0]
    for pairs in pairs_collection:
        points = finite_birth_persistence_points(pairs)
        if points.size == 0:
            continue
        births.extend(points[:, 0].tolist())
        persistences.extend(points[:, 1].tolist())
    max_birth = max(births)
    max_persistence = max(persistences)
    birth_upper = max(1.0, 1.05 * max_birth if max_birth > 0.0 else 1.0)
    persistence_upper = max(1.0, 1.05 * max_persistence if max_persistence > 0.0 else 1.0)
    pixel_size = max(birth_upper, persistence_upper) / float(PERSISTENCE_IMAGE_RESOLUTION)
    return {
        "birth_min": 0.0,
        "birth_max": birth_upper,
        "pers_min": 0.0,
        "pers_max": persistence_upper,
        "pixel_size": pixel_size,
    }


def empty_persistence_image(config: dict[str, float]) -> np.ndarray:
    height = max(1, int(math.ceil((config["pers_max"] - config["pers_min"]) / config["pixel_size"])))
    width = max(1, int(math.ceil((config["birth_max"] - config["birth_min"]) / config["pixel_size"])))
    return np.zeros((height, width), dtype=np.float64)


def persistence_image_array(pairs: list[list[float]], config: dict[str, float]) -> np.ndarray:
    points = finite_birth_persistence_points(pairs)
    if points.size == 0:
        return empty_persistence_image(config)
    imager = PersistenceImager(
        birth_range=(config["birth_min"], config["birth_max"]),
        pers_range=(config["pers_min"], config["pers_max"]),
        pixel_size=config["pixel_size"],
    )
    image = imager.transform(points)
    return np.asarray(image, dtype=np.float64)


def persistence_image_distance(left_image: np.ndarray, right_image: np.ndarray) -> float:
    left = np.asarray(left_image, dtype=np.float64)
    right = np.asarray(right_image, dtype=np.float64)
    return float(np.linalg.norm(left - right))


def summary_agreement(left: Any, right: Any, *, mode: str) -> bool:
    if left is None or right is None:
        return False
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return np.array_equal(np.asarray(left), np.asarray(right))
    left_value = float(left)
    right_value = float(right)
    if mode == "quantized":
        return abs(left_value - right_value) <= 1.0e-12 * max(abs(left_value), abs(right_value), 1.0)
    return abs(left_value - right_value) <= 1.0e-8 + 1.0e-7 * max(abs(left_value), abs(right_value), 1.0)


def max_pairwise_spread(values_by_library: dict[str, float | None]) -> float | None:
    numeric = [float(value) for value in values_by_library.values() if value is not None]
    if not numeric:
        return None
    return float(max(numeric) - min(numeric))


def scalar_summary_deltas(
    current_summary: dict[str, float | int],
    baseline_summary: dict[str, float | int],
) -> dict[str, float]:
    return {
        "lifetime_l1_delta": float(abs(float(current_summary["lifetime_l1"]) - float(baseline_summary["lifetime_l1"]))),
        "lifetime_l2_delta": float(abs(float(current_summary["lifetime_l2"]) - float(baseline_summary["lifetime_l2"]))),
        "lifetime_linf_delta": float(abs(float(current_summary["lifetime_linf"]) - float(baseline_summary["lifetime_linf"]))),
        "persistent_entropy_delta": float(
            abs(float(current_summary["persistent_entropy"]) - float(baseline_summary["persistent_entropy"]))
        ),
    }


def serialize_summary_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return serialize_summary_value(value.tolist())
    if isinstance(value, (list, tuple)):
        return [serialize_summary_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_summary_value(item) for key, item in value.items()}
    if isinstance(value, np.generic):
        return serialize_summary_value(value.item())
    if isinstance(value, float):
        return serialize_float(value)
    return value


__all__ = [
    "BETTI_GRID_SIZE",
    "COORDINATE_JITTER_MAGNITUDES",
    "MATRIX_NOISE_MAGNITUDES",
    "PAIRWISE_LIBRARY_PAIRS",
    "PERSISTENCE_IMAGE_RESOLUTION",
    "PerturbedBenchmark",
    "QUANTIZATION_MAGNITUDES",
    "RANDOM_SEEDS",
    "SUMMARY_SCALAR_KEYS",
    "VACANCY_COUNTS",
    "betti_curve",
    "betti_curve_distances",
    "betti_grid_from_groups",
    "build_perturbed_benchmarks",
    "build_persistence_image_config",
    "canonical_distance_matrix",
    "diagram_distance_metrics",
    "diagram_pairs_from_case",
    "diagram_scalar_summaries",
    "empty_persistence_image",
    "finite_birth_persistence_points",
    "hash_array",
    "interval_records_to_pairs",
    "max_pairwise_spread",
    "pairwise_distance_matrix",
    "perturbed_benchmark_to_manifest",
    "persistence_image_array",
    "persistence_image_distance",
    "scalar_summary_deltas",
    "serialize_summary_value",
    "slug_float",
    "summary_agreement",
]
