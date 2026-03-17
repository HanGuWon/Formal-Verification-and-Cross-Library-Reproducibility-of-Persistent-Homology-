from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
from scipy.linalg import eigh
from scipy.spatial.distance import pdist, squareform

DEFAULT_COEFFS = (2, 3)
DEFAULT_MAXDIMS = (1, 2)
DEFAULT_QUANTIZATION_STEP = 2.0**-10
DEFAULT_MODES = ("floating", "quantized")
TFIM_J = 1.0
TFIM_MI_FLOOR = 1.0e-12
ENTROPY_EPS = 1.0e-14


@dataclass(frozen=True)
class BenchmarkDefinition:
    benchmark_id: str
    family: str
    label: str
    mode: str
    distance_matrix: np.ndarray
    point_cloud: np.ndarray | None
    selected_threshold: float
    full_threshold: float
    full_filtration_feasible: bool
    coeffs: tuple[int, ...] = DEFAULT_COEFFS
    maxdims: tuple[int, ...] = DEFAULT_MAXDIMS
    metadata: dict[str, Any] | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _BaseBenchmark:
    benchmark_id: str
    family: str
    label: str
    distance_matrix: np.ndarray
    point_cloud: np.ndarray | None
    threshold_strategy: str
    threshold_parameter: float | None
    metadata: dict[str, Any]
    notes: tuple[str, ...]


def generate_benchmarks(
    *,
    modes: tuple[str, ...] = DEFAULT_MODES,
    quantization_step: float = DEFAULT_QUANTIZATION_STEP,
    include_nacl: bool = True,
) -> list[BenchmarkDefinition]:
    base_benchmarks = _generate_base_benchmarks(include_nacl=include_nacl)
    benchmarks: list[BenchmarkDefinition] = []
    for base in base_benchmarks:
        for mode in modes:
            matrix = _materialize_mode_matrix(
                base.distance_matrix,
                mode=mode,
                quantization_step=quantization_step,
            )
            point_cloud = None if base.point_cloud is None else np.array(base.point_cloud, copy=True)
            selected_threshold = _resolve_threshold(
                matrix,
                strategy=base.threshold_strategy,
                parameter=base.threshold_parameter,
            )
            full_threshold = _full_threshold(matrix)
            metadata = dict(base.metadata)
            metadata.update(
                {
                    "benchmark_id": base.benchmark_id,
                    "mode": mode,
                    "distance_matrix_hash": _hash_array(matrix),
                    "point_cloud_hash": None if point_cloud is None else _hash_array(point_cloud),
                    "quantization_step": None if mode == "floating" else quantization_step,
                    "threshold_strategy": base.threshold_strategy,
                    "threshold_parameter": base.threshold_parameter,
                    "has_point_cloud": point_cloud is not None,
                }
            )
            notes = base.notes
            if mode == "quantized":
                notes = notes + (
                    f"Distance matrix quantized to a power-of-two step of {quantization_step}.",
                )
            benchmarks.append(
                BenchmarkDefinition(
                    benchmark_id=f"{base.benchmark_id}__{mode}",
                    family=base.family,
                    label=base.label,
                    mode=mode,
                    distance_matrix=matrix,
                    point_cloud=point_cloud,
                    selected_threshold=selected_threshold,
                    full_threshold=full_threshold,
                    full_filtration_feasible=bool(np.isfinite(full_threshold)),
                    metadata=metadata,
                    notes=notes,
                )
            )
    return benchmarks


def benchmark_to_manifest(benchmark: BenchmarkDefinition) -> dict[str, Any]:
    return {
        "benchmark_id": benchmark.benchmark_id,
        "family": benchmark.family,
        "label": benchmark.label,
        "mode": benchmark.mode,
        "selected_threshold": benchmark.selected_threshold,
        "full_threshold": benchmark.full_threshold,
        "full_filtration_feasible": benchmark.full_filtration_feasible,
        "coeffs": list(benchmark.coeffs),
        "maxdims": list(benchmark.maxdims),
        "has_point_cloud": benchmark.point_cloud is not None,
        "metadata": benchmark.metadata or {},
        "notes": list(benchmark.notes),
        "distance_matrix_shape": list(benchmark.distance_matrix.shape),
        "point_cloud_shape": None if benchmark.point_cloud is None else list(benchmark.point_cloud.shape),
    }


def _generate_base_benchmarks(*, include_nacl: bool) -> list[_BaseBenchmark]:
    return _generate_tfim_base_benchmarks() + _generate_point_cloud_base_benchmarks(include_nacl=include_nacl)


def _generate_tfim_base_benchmarks() -> list[_BaseBenchmark]:
    specs = [
        ("obc", 4, 0.50),
        ("obc", 4, 1.00),
        ("obc", 6, 0.50),
        ("obc", 6, 1.00),
        ("pbc", 4, 0.50),
        ("pbc", 4, 1.00),
        ("pbc", 6, 0.50),
        ("pbc", 6, 1.00),
    ]
    benchmarks: list[_BaseBenchmark] = []
    for boundary, n_sites, transverse_field in specs:
        distance_matrix = _tfim_inverse_mutual_information_distance_matrix(
            n_sites=n_sites,
            transverse_field=transverse_field,
            periodic=(boundary == "pbc"),
        )
        benchmark_id = f"tfim_{boundary}_n{n_sites}_g{_slug_float(transverse_field)}"
        label = f"TFIM {boundary.upper()} N={n_sites}, g={transverse_field:.2f}"
        metadata = {
            "family": "entanglement_distance_matrix",
            "generator": "tfim_inverse_mutual_information",
            "boundary_condition": boundary,
            "n_sites": n_sites,
            "transverse_field": transverse_field,
            "exchange_coupling": TFIM_J,
            "mutual_information_floor": TFIM_MI_FLOOR,
            "state_solver": "dense_exact_diagonalization",
        }
        notes = (
            "Distance is defined as the inverse pairwise mutual information from the TFIM ground state.",
            "Mutual information uses base-2 von Neumann entropy with a small numerical floor.",
        )
        benchmarks.append(
            _BaseBenchmark(
                benchmark_id=benchmark_id,
                family="A",
                label=label,
                distance_matrix=distance_matrix,
                point_cloud=None,
                threshold_strategy="matrix_quantile",
                threshold_parameter=0.40,
                metadata=metadata,
                notes=notes,
            )
        )
    return benchmarks


def _generate_point_cloud_base_benchmarks(*, include_nacl: bool) -> list[_BaseBenchmark]:
    point_clouds = [
        (
            "square_patch_3x3",
            "Square lattice patch 3x3",
            _square_lattice_patch(3, 3, spacing=1.0),
            ("Regular square patch with unit nearest-neighbor spacing.",),
        ),
        (
            "triangular_patch_3x3",
            "Triangular lattice patch 3x3",
            _triangular_lattice_patch(3, 3, spacing=1.0),
            ("Triangular lattice patch built from a unit-spacing oblique basis.",),
        ),
        (
            "honeycomb_patch_2x2",
            "Honeycomb patch 2x2 cells",
            _honeycomb_patch(2, 2, bond_length=1.0),
            ("Graphene-like honeycomb patch using a two-point basis.",),
        ),
    ]
    if include_nacl:
        point_clouds.append(
            (
                "nacl_coordination_shell",
                "NaCl-style coordination shell",
                _nacl_coordination_shell(nearest_neighbor=1.0),
                ("Central atom with six axis-aligned nearest neighbors.",),
            )
        )

    benchmarks: list[_BaseBenchmark] = []
    for benchmark_id, label, point_cloud, notes in point_clouds:
        distance_matrix = _pairwise_distance_matrix(point_cloud)
        metadata = {
            "family": "crystalline_point_cloud",
            "generator": benchmark_id,
            "ambient_dimension": int(point_cloud.shape[1]),
            "num_points": int(point_cloud.shape[0]),
            "nearest_neighbor_distance": 1.0,
        }
        benchmarks.append(
            _BaseBenchmark(
                benchmark_id=benchmark_id,
                family="B",
                label=label,
                distance_matrix=distance_matrix,
                point_cloud=point_cloud,
                threshold_strategy="nearest_neighbor",
                threshold_parameter=1.0,
                metadata=metadata,
                notes=notes,
            )
        )
    return benchmarks


def _tfim_inverse_mutual_information_distance_matrix(
    *,
    n_sites: int,
    transverse_field: float,
    periodic: bool,
) -> np.ndarray:
    hamiltonian = _tfim_hamiltonian(
        n_sites=n_sites,
        transverse_field=transverse_field,
        periodic=periodic,
    )
    eigenvalues, eigenvectors = eigh(hamiltonian)
    ground_state = eigenvectors[:, np.argmin(eigenvalues)]
    single_site_entropies = {
        (site,): _von_neumann_entropy(_reduced_density_matrix(ground_state, n_sites, (site,)))
        for site in range(n_sites)
    }
    matrix = np.zeros((n_sites, n_sites), dtype=np.float64)
    for i, j in combinations(range(n_sites), 2):
        rho_ij = _reduced_density_matrix(ground_state, n_sites, (i, j))
        entropy_ij = _von_neumann_entropy(rho_ij)
        mutual_information = single_site_entropies[(i,)] + single_site_entropies[(j,)] - entropy_ij
        mutual_information = max(float(np.real_if_close(mutual_information)), TFIM_MI_FLOOR)
        distance = 1.0 / mutual_information
        matrix[i, j] = distance
        matrix[j, i] = distance
    return _canonical_distance_matrix(matrix)


def _tfim_hamiltonian(*, n_sites: int, transverse_field: float, periodic: bool) -> np.ndarray:
    dimension = 1 << n_sites
    hamiltonian = np.zeros((dimension, dimension), dtype=np.float64)
    zz_pairs = [(site, site + 1) for site in range(n_sites - 1)]
    if periodic and n_sites > 2:
        zz_pairs.append((n_sites - 1, 0))

    for basis_state in range(dimension):
        diagonal_term = 0.0
        for i, j in zz_pairs:
            zi = 1.0 if ((basis_state >> i) & 1) == 0 else -1.0
            zj = 1.0 if ((basis_state >> j) & 1) == 0 else -1.0
            diagonal_term -= TFIM_J * zi * zj
        hamiltonian[basis_state, basis_state] += diagonal_term
        for site in range(n_sites):
            flipped_state = basis_state ^ (1 << site)
            hamiltonian[basis_state, flipped_state] -= transverse_field
    return hamiltonian


def _reduced_density_matrix(
    statevector: np.ndarray,
    n_sites: int,
    keep_sites: tuple[int, ...],
) -> np.ndarray:
    keep_sites = tuple(sorted(keep_sites))
    traced_sites = tuple(site for site in range(n_sites) if site not in keep_sites)
    psi = np.asarray(statevector, dtype=np.complex128).reshape((2,) * n_sites)
    permuted = np.transpose(psi, keep_sites + traced_sites)
    kept_dim = 1 << len(keep_sites)
    traced_dim = 1 << len(traced_sites)
    reshaped = permuted.reshape(kept_dim, traced_dim)
    return reshaped @ reshaped.conj().T


def _von_neumann_entropy(rho: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(np.asarray(rho, dtype=np.complex128))
    eigenvalues = np.real_if_close(eigenvalues)
    eigenvalues = np.clip(np.asarray(eigenvalues, dtype=np.float64), 0.0, 1.0)
    mask = eigenvalues > ENTROPY_EPS
    if not np.any(mask):
        return 0.0
    vals = eigenvalues[mask]
    return float(-np.sum(vals * np.log2(vals)))


def _square_lattice_patch(nx: int, ny: int, *, spacing: float) -> np.ndarray:
    return np.array(
        [[spacing * x, spacing * y] for y in range(ny) for x in range(nx)],
        dtype=np.float64,
    )


def _triangular_lattice_patch(nx: int, ny: int, *, spacing: float) -> np.ndarray:
    vertical = spacing * math.sqrt(3.0) / 2.0
    return np.array(
        [
            [spacing * (x + 0.5 * (y % 2)), vertical * y]
            for y in range(ny)
            for x in range(nx)
        ],
        dtype=np.float64,
    )


def _honeycomb_patch(nx: int, ny: int, *, bond_length: float) -> np.ndarray:
    a1 = np.array([1.5 * bond_length, math.sqrt(3.0) * bond_length / 2.0], dtype=np.float64)
    a2 = np.array([1.5 * bond_length, -math.sqrt(3.0) * bond_length / 2.0], dtype=np.float64)
    basis = (
        np.array([0.0, 0.0], dtype=np.float64),
        np.array([bond_length, 0.0], dtype=np.float64),
    )
    points = []
    for ix in range(nx):
        for iy in range(ny):
            origin = ix * a1 + iy * a2
            for site in basis:
                points.append(origin + site)
    return np.array(points, dtype=np.float64)


def _nacl_coordination_shell(*, nearest_neighbor: float) -> np.ndarray:
    offsets = [
        (0.0, 0.0, 0.0),
        (nearest_neighbor, 0.0, 0.0),
        (-nearest_neighbor, 0.0, 0.0),
        (0.0, nearest_neighbor, 0.0),
        (0.0, -nearest_neighbor, 0.0),
        (0.0, 0.0, nearest_neighbor),
        (0.0, 0.0, -nearest_neighbor),
    ]
    return np.array(offsets, dtype=np.float64)


def _pairwise_distance_matrix(point_cloud: np.ndarray) -> np.ndarray:
    return _canonical_distance_matrix(squareform(pdist(point_cloud, metric="euclidean")))


def _canonical_distance_matrix(matrix: np.ndarray) -> np.ndarray:
    array = np.asarray(matrix, dtype=np.float64)
    symmetrized = 0.5 * (array + array.T)
    np.fill_diagonal(symmetrized, 0.0)
    return symmetrized


def _materialize_mode_matrix(
    distance_matrix: np.ndarray,
    *,
    mode: str,
    quantization_step: float,
) -> np.ndarray:
    if mode == "floating":
        return _canonical_distance_matrix(distance_matrix)
    if mode == "quantized":
        return quantize_distance_matrix(distance_matrix, step=quantization_step)
    raise ValueError(f"Unknown benchmark mode: {mode}")


def quantize_distance_matrix(distance_matrix: np.ndarray, *, step: float = DEFAULT_QUANTIZATION_STEP) -> np.ndarray:
    array = _canonical_distance_matrix(distance_matrix)
    quantized = np.round(array / step) * step
    np.fill_diagonal(quantized, 0.0)
    return _canonical_distance_matrix(quantized)


def _resolve_threshold(matrix: np.ndarray, *, strategy: str, parameter: float | None) -> float:
    if strategy == "nearest_neighbor":
        if parameter is None:
            raise ValueError("nearest_neighbor threshold strategy requires a parameter")
        return float(parameter)
    if strategy == "matrix_quantile":
        if parameter is None:
            raise ValueError("matrix_quantile threshold strategy requires a parameter")
        values = _off_diagonal_values(matrix)
        return float(np.quantile(values, parameter, method="nearest"))
    raise ValueError(f"Unknown threshold strategy: {strategy}")


def _full_threshold(matrix: np.ndarray) -> float:
    values = _off_diagonal_values(matrix)
    return float(np.max(values))


def _off_diagonal_values(matrix: np.ndarray) -> np.ndarray:
    indices = np.triu_indices_from(matrix, k=1)
    values = np.asarray(matrix[indices], dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("Distance matrix has no finite off-diagonal entries")
    return finite


def _hash_array(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(repr(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _slug_float(value: float) -> str:
    return f"{value:.2f}".replace(".", "p")
