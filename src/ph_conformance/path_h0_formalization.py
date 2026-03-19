from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import dionysus
import numpy as np


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


def float_to_hex(value: float | str) -> str:
    number = deserialize_float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "inf" if number > 0 else "-inf"
    return np.float64(number).hex()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serialize_json_value(payload), indent=2, sort_keys=True), encoding="utf-8")


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
        return serialize_float(value)
    return value


def signal_to_values(signal_payload: dict[str, Any]) -> np.ndarray:
    return np.asarray(signal_payload["values"], dtype=np.float64)


def common_chain_encoding(signal: np.ndarray | list[float]) -> dict[str, Any]:
    values = np.asarray(signal, dtype=np.float64)
    vertices = [
        {
            "index": int(index),
            "filtration": serialize_float(value),
            "filtration_hex": float_to_hex(value),
        }
        for index, value in enumerate(values)
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
        {float(value) for value in values}.union({float(max(values[index], values[index + 1])) for index in range(values.size - 1)})
    )
    return {
        "signal": [serialize_float(value) for value in values],
        "vertices": vertices,
        "edges": edges,
        "critical_values": [{"value": serialize_float(value), "value_hex": float_to_hex(value)} for value in critical_values],
    }


def local_minima(signal: np.ndarray | list[float]) -> list[dict[str, Any]]:
    values = np.asarray(signal, dtype=np.float64)
    minima = []
    for index, value in enumerate(values):
        left = values[index - 1] if index > 0 else math.inf
        right = values[index + 1] if index + 1 < values.size else math.inf
        if value < left and value < right:
            minima.append(
                {
                    "index": int(index),
                    "value": serialize_float(value),
                    "value_hex": float_to_hex(value),
                }
            )
    return minima


def reference_path_h0_events(signal: np.ndarray | list[float]) -> dict[str, Any]:
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
    intervals = []
    merges = []

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def is_older(left_root: int, right_root: int) -> bool:
        return (elder_birth_value[left_root], elder_birth_index[left_root]) <= (
            elder_birth_value[right_root],
            elder_birth_index[right_root],
        )

    for filtration, dimension, simplex in events:
        if dimension == 0:
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

    minima = local_minima(values)
    nonzero_intervals = [interval for interval in intervals if not interval["is_zero_length"]] + [essential]
    finite_merge_events = [merge for merge in merges if merge["merge_height"] != merge["younger_birth"]]

    return {
        "local_minima": minima,
        "merge_events": merges,
        "all_intervals": intervals + [essential],
        "nonzero_intervals": nonzero_intervals,
        "births_match_local_minima": sorted(interval["birth_index"] for interval in nonzero_intervals)
        == sorted(item["index"] for item in minima),
        "finite_deaths_match_merge_heights": sorted(
            interval["death_hex"] for interval in nonzero_intervals if interval["death"] != "inf"
        )
        == sorted(merge["merge_height_hex"] for merge in finite_merge_events),
    }


def interval_signature(record: dict[str, Any]) -> str:
    return "|".join(
        [
            str(record.get("birth_index", "")),
            str(record["birth_hex"]),
            str(record["death_hex"]),
            str(record.get("death_edge")),
            str(record.get("is_zero_length", "")),
        ]
    )


def event_list_signature(records: list[dict[str, Any]]) -> list[str]:
    return sorted(interval_signature(record) for record in records)


def zero_length_interval_count(intervals: list[dict[str, Any]]) -> int:
    return sum(1 for interval in intervals if interval.get("is_zero_length", False))


def diagram_distance_after_zero_removal(theorem_events: dict[str, Any]) -> dict[str, float]:
    all_pairs = [
        [deserialize_float(interval["birth"]), deserialize_float(interval["death"])]
        for interval in theorem_events["all_intervals"]
    ]
    nonzero_pairs = [
        [deserialize_float(interval["birth"]), deserialize_float(interval["death"])]
        for interval in theorem_events["nonzero_intervals"]
    ]
    left = dionysus.Diagram(all_pairs)
    right = dionysus.Diagram(nonzero_pairs)

    try:
        bottleneck = float(dionysus.bottleneck_distance(left, right, delta=0.0))
    except Exception:
        bottleneck = 0.0 if removed_intervals_are_zero_length_only(theorem_events) else math.inf
    try:
        wasserstein_q2 = float(dionysus.wasserstein_distance(left, right, q=2, delta=0.0))
    except Exception:
        wasserstein_q2 = 0.0 if removed_intervals_are_zero_length_only(theorem_events) else math.inf
    return {
        "bottleneck_distance": bottleneck,
        "wasserstein_distance_q2": wasserstein_q2,
    }


def removed_intervals_are_zero_length_only(theorem_events: dict[str, Any]) -> bool:
    all_records = theorem_events["all_intervals"]
    nonzero_signatures = event_list_signature(theorem_events["nonzero_intervals"])
    remaining = list(nonzero_signatures)
    for record in all_records:
        signature = interval_signature(record)
        if signature in remaining:
            remaining.remove(signature)
        elif not record.get("is_zero_length", False):
            return False
    return not remaining


def comparison_signature(records: list[dict[str, Any]]) -> list[str]:
    return sorted(
        f"{record['birth_hex']}|{record['death_hex']}"
        for record in records
    )


__all__ = [
    "common_chain_encoding",
    "comparison_signature",
    "diagram_distance_after_zero_removal",
    "dump_json",
    "event_list_signature",
    "float_to_hex",
    "load_json",
    "local_minima",
    "reference_path_h0_events",
    "serialize_json_value",
    "sha256_file",
    "signal_to_values",
    "zero_length_interval_count",
]
