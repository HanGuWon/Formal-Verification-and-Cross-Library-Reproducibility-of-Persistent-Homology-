from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np

from .tda import deserialize_float, float_to_hex, serialize_float

NORMALIZATION_MODES = (
    "raw_exact",
    "drop_zero_length_intervals",
    "drop_zero_length_intervals_plus_float32_roundtrip",
    "threshold_truncation_harmonized",
)
PAIR_KEYS = ("gudhi__ripser", "gudhi__dionysus", "ripser__dionysus")
TRUNCATED_DEATH_SENTINEL = "trunc_inf"


def normalize_interval_records(
    records: list[dict[str, Any]],
    *,
    normalization_mode: str,
    case_mode: str,
    threshold_value: float,
    full_threshold: float,
) -> list[dict[str, Any]]:
    if normalization_mode not in NORMALIZATION_MODES:
        raise ValueError(f"Unknown normalization mode: {normalization_mode}")

    apply_zero_drop = normalization_mode != "raw_exact"
    apply_float32 = normalization_mode in {
        "drop_zero_length_intervals_plus_float32_roundtrip",
        "threshold_truncation_harmonized",
    } and case_mode == "floating"
    apply_truncation_rule = normalization_mode == "threshold_truncation_harmonized"

    normalized_threshold = roundtrip_float32(threshold_value) if apply_float32 else float(threshold_value)
    truncation_tolerance = threshold_based_tolerance(normalized_threshold)
    truncated_filtration = bool(float(full_threshold) > float(threshold_value) + truncation_tolerance)

    normalized_records = []
    for record in records:
        birth = deserialize_float(record["birth"])
        death = deserialize_float(record["death"])

        if apply_float32 and math.isfinite(birth):
            birth = roundtrip_float32(birth)
        if apply_float32 and math.isfinite(death):
            death = roundtrip_float32(death)

        if apply_zero_drop and math.isfinite(death) and death == birth:
            continue

        if apply_truncation_rule and truncated_filtration:
            death_touches_threshold = math.isfinite(death) and value_touches_threshold(
                death,
                threshold=normalized_threshold,
                tolerance=truncation_tolerance,
            )
            survives_to_threshold = math.isinf(death) or death_touches_threshold
            if survives_to_threshold:
                death = TRUNCATED_DEATH_SENTINEL
            if death == TRUNCATED_DEATH_SENTINEL and value_touches_threshold(
                birth,
                threshold=normalized_threshold,
                tolerance=truncation_tolerance,
            ):
                continue

        normalized_records.append(record_from_values(birth, death))

    normalized_records.sort(key=lambda item: (item["birth_hex"], item["death_hex"]))
    return normalized_records


def record_from_values(birth: float, death: float | str) -> dict[str, Any]:
    if isinstance(death, str):
        if death != TRUNCATED_DEATH_SENTINEL:
            raise ValueError(f"Unsupported death sentinel: {death}")
        death_value: float | str = death
        death_hex = death
    else:
        death_value = serialize_float(death)
        death_hex = float_to_hex(death)
    return {
        "birth": serialize_float(birth),
        "death": death_value,
        "birth_hex": float_to_hex(birth),
        "death_hex": death_hex,
    }


def signature_of_records(records: list[dict[str, Any]]) -> list[str]:
    return [f"{record['birth_hex']}|{record['death_hex']}" for record in records]


def pairwise_semantic_agreement(case_payload: dict[str, Any], *, pair_key: str, dim_key: str) -> bool:
    pairwise = case_payload["results"]["agreement"]["by_dimension"][dim_key]["pairwise"][pair_key]
    if pairwise["exact_match"]:
        return True
    discrepancy = case_payload["results"]["discrepancy"]["by_dimension"].get(dim_key)
    if discrepancy is None:
        return False
    metrics = discrepancy["pairwise"].get(pair_key)
    if metrics is None:
        return False
    for metric_key in ("bottleneck_distance", "wasserstein_distance_q2"):
        metric_value = metrics.get(metric_key)
        if metric_value is None:
            return False
        if deserialize_float(metric_value) != 0.0:
            return False
    return True


def roundtrip_float32(value: float) -> float:
    if math.isinf(value) or math.isnan(value):
        return value
    return float(np.float32(value))


def threshold_based_tolerance(threshold: float) -> float:
    scale = max(abs(float(threshold)), 1.0)
    return max(math.ulp(scale) * 32.0, scale * 1.0e-12)


def value_touches_threshold(value: float, *, threshold: float, tolerance: float) -> bool:
    if not math.isfinite(value):
        return False
    if abs(value - threshold) <= tolerance:
        return True
    return float_to_hex(roundtrip_float32(value)) == float_to_hex(roundtrip_float32(threshold))


def sha256_path(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "NORMALIZATION_MODES",
    "PAIR_KEYS",
    "TRUNCATED_DEATH_SENTINEL",
    "normalize_interval_records",
    "pairwise_semantic_agreement",
    "record_from_values",
    "roundtrip_float32",
    "sha256_path",
    "signature_of_records",
    "threshold_based_tolerance",
    "value_touches_threshold",
]
