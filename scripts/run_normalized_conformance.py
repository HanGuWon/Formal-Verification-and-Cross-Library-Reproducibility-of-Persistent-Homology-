from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ph_conformance.normalized_conformance import (  # noqa: E402
    NORMALIZATION_MODES,
    PAIR_KEYS,
    normalize_interval_records,
    pairwise_semantic_agreement,
    sha256_path,
    signature_of_records,
)


TASK_ID = "PH-NORMALIZED-CONFORMANCE-002"
DEFAULT_CONFORMANCE_DIR = REPO_ROOT / "artifacts"
DEFAULT_AUDIT_DIR = DEFAULT_CONFORMANCE_DIR / "audit"
DEFAULT_OUTPUT_DIR = DEFAULT_CONFORMANCE_DIR / "normalized_conformance"
DIRECT_DISTRIBUTIONS = ("numpy", "scipy", "gudhi", "ripser", "dionysus")
MODE_LABELS = {
    "raw_exact": "A. raw_exact",
    "drop_zero_length_intervals": "B. drop_zero_length_intervals",
    "drop_zero_length_intervals_plus_float32_roundtrip": "C. drop_zero_length_intervals + float32_roundtrip",
    "threshold_truncation_harmonized": "D. threshold_truncation_harmonized",
    "distance_zero_semantic": "distance_zero_semantic",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute normalization-tier pairwise agreement tables from saved PH artifacts.")
    parser.add_argument(
        "--conformance-dir",
        type=Path,
        default=DEFAULT_CONFORMANCE_DIR,
        help="Directory containing PH-CONFORMANCE-VR-001 artifacts.",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=DEFAULT_AUDIT_DIR,
        help="Directory containing PH-AUDIT-CONVENTIONS-001 artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for PH-NORMALIZED-CONFORMANCE-002 artifacts.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case-id filter. May be specified multiple times.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    conformance_dir = args.conformance_dir.resolve()
    audit_dir = args.audit_dir.resolve()
    output_dir = args.output_dir.resolve()
    case_filters = set(args.case_id)

    ensure_dir(output_dir)
    ensure_dir(output_dir / "environment")
    ensure_dir(output_dir / "hashes")
    ensure_dir(output_dir / "normalized_tables")
    ensure_dir(output_dir / "summary")
    ensure_dir(output_dir / "minimal_repros")

    environment_snapshot = collect_environment_snapshot()
    write_text(output_dir / "environment" / "pip_freeze.txt", environment_snapshot["pip_freeze"])
    dump_json(output_dir / "environment" / "versions.json", environment_snapshot["versions"])

    case_payloads = load_case_payloads(conformance_dir / "cases")
    if case_filters:
        case_payloads = {case_id: payload for case_id, payload in case_payloads.items() if case_id in case_filters}
        if not case_payloads:
            raise SystemExit("No saved conformance cases matched the provided --case-id filter.")

    audit_rows = load_json(audit_dir / "classification_table.json")
    audit_lookup = {(row["case_id"], str(row["dimension"])): row for row in audit_rows}

    input_hash_rows = build_input_hash_rows(
        conformance_dir=conformance_dir,
        audit_dir=audit_dir,
        case_ids=sorted(case_payloads),
    )
    write_csv(output_dir / "hashes" / "input_artifact_hashes.csv", input_hash_rows)
    dump_json(output_dir / "hashes" / "input_artifact_hashes.json", input_hash_rows)

    normalized_interval_rows: list[dict[str, Any]] = []
    normalized_signature_rows: list[dict[str, Any]] = []
    pairwise_case_rows: list[dict[str, Any]] = []

    for case_id in sorted(case_payloads):
        case_payload = case_payloads[case_id]
        benchmark = case_payload["benchmark"]
        parameters = case_payload["case_parameters"]
        mode = benchmark["mode"]
        threshold_value = float(parameters["threshold_value"])
        full_threshold = float(benchmark["full_threshold"])
        maxdim = int(parameters["maxdim"])

        normalized_signatures_for_case: dict[tuple[str, str], list[str]] = {}
        for dim in range(maxdim + 1):
            dim_key = str(dim)
            for normalization_mode in NORMALIZATION_MODES:
                for library in ("gudhi", "ripser", "dionysus"):
                    raw_records = case_payload["results"]["raw_outputs"][library]["intervals_by_dimension"].get(dim_key, [])
                    normalized_records = normalize_interval_records(
                        raw_records,
                        normalization_mode=normalization_mode,
                        case_mode=mode,
                        threshold_value=threshold_value,
                        full_threshold=full_threshold,
                    )
                    signature = signature_of_records(normalized_records)
                    normalized_signatures_for_case[(normalization_mode, f"{library}:{dim_key}")] = signature
                    normalized_signature_rows.append(
                        {
                            "case_id": case_id,
                            "benchmark_id": benchmark["benchmark_id"],
                            "mode": mode,
                            "coeff": parameters["coeff"],
                            "maxdim": parameters["maxdim"],
                            "threshold_label": parameters["threshold_label"],
                            "dimension": dim,
                            "normalization_mode": normalization_mode,
                            "library": library,
                            "interval_count": len(normalized_records),
                            "signature": "::".join(signature),
                        }
                    )
                    for interval_index, record in enumerate(normalized_records):
                        normalized_interval_rows.append(
                            {
                                "case_id": case_id,
                                "benchmark_id": benchmark["benchmark_id"],
                                "mode": mode,
                                "coeff": parameters["coeff"],
                                "maxdim": parameters["maxdim"],
                                "threshold_label": parameters["threshold_label"],
                                "dimension": dim,
                                "normalization_mode": normalization_mode,
                                "library": library,
                                "interval_index": interval_index,
                                "birth": record["birth"],
                                "death": record["death"],
                                "birth_hex": record["birth_hex"],
                                "death_hex": record["death_hex"],
                            }
                        )

            audit_row = audit_lookup.get((case_id, dim_key), {})
            for normalization_mode in NORMALIZATION_MODES:
                for pair_key in PAIR_KEYS:
                    left_library, right_library = pair_key.split("__")
                    left_signature = normalized_signatures_for_case[(normalization_mode, f"{left_library}:{dim_key}")]
                    right_signature = normalized_signatures_for_case[(normalization_mode, f"{right_library}:{dim_key}")]
                    pairwise_case_rows.append(
                        {
                            "case_id": case_id,
                            "benchmark_id": benchmark["benchmark_id"],
                            "label": benchmark["label"],
                            "family": benchmark["family"],
                            "mode": mode,
                            "coeff": parameters["coeff"],
                            "maxdim": parameters["maxdim"],
                            "threshold_label": parameters["threshold_label"],
                            "threshold_value": parameters["threshold_value"],
                            "dimension": dim,
                            "pair": pair_key,
                            "comparison_mode": normalization_mode,
                            "exact_match": left_signature == right_signature,
                            "audit_classification": audit_row.get("classification", ""),
                            "audit_mechanism": audit_row.get("mechanism", ""),
                        }
                    )
            for pair_key in PAIR_KEYS:
                pairwise_case_rows.append(
                    {
                        "case_id": case_id,
                        "benchmark_id": benchmark["benchmark_id"],
                        "label": benchmark["label"],
                        "family": benchmark["family"],
                        "mode": mode,
                        "coeff": parameters["coeff"],
                        "maxdim": parameters["maxdim"],
                        "threshold_label": parameters["threshold_label"],
                        "threshold_value": parameters["threshold_value"],
                        "dimension": dim,
                        "pair": pair_key,
                        "comparison_mode": "distance_zero_semantic",
                        "exact_match": pairwise_semantic_agreement(case_payload, pair_key=pair_key, dim_key=dim_key),
                        "audit_classification": audit_row.get("classification", ""),
                        "audit_mechanism": audit_row.get("mechanism", ""),
                    }
                )

    write_csv(output_dir / "normalized_tables" / "normalized_interval_records.csv", normalized_interval_rows)
    dump_json(output_dir / "normalized_tables" / "normalized_interval_records.json", normalized_interval_rows)
    write_csv(output_dir / "normalized_tables" / "normalized_signatures.csv", normalized_signature_rows)
    dump_json(output_dir / "normalized_tables" / "normalized_signatures.json", normalized_signature_rows)
    write_csv(output_dir / "summary" / "pairwise_case_dimension_agreement.csv", pairwise_case_rows)
    dump_json(output_dir / "summary" / "pairwise_case_dimension_agreement.json", pairwise_case_rows)

    pairwise_agreement_rows = build_pairwise_agreement_rows(pairwise_case_rows)
    write_csv(output_dir / "summary" / "pairwise_agreement.csv", pairwise_agreement_rows)
    dump_json(output_dir / "summary" / "pairwise_agreement.json", pairwise_agreement_rows)

    ablation_rows = build_ablation_rows(pairwise_case_rows)
    write_csv(output_dir / "summary" / "ablation_table.csv", ablation_rows)
    dump_json(output_dir / "summary" / "ablation_table.json", ablation_rows)

    remaining_failure_rows = [
        row
        for row in pairwise_case_rows
        if row["comparison_mode"] == "threshold_truncation_harmonized" and not row["exact_match"]
    ]
    write_csv(output_dir / "summary" / "remaining_failures.csv", remaining_failure_rows)
    dump_json(output_dir / "summary" / "remaining_failures.json", remaining_failure_rows)

    reproducer_payload = write_remaining_failure_reproducers(
        remaining_failure_rows=remaining_failure_rows,
        case_payloads=case_payloads,
        conformance_dir=conformance_dir,
        output_dir=output_dir,
    )
    dump_json(output_dir / "minimal_repros" / "index.json", reproducer_payload)

    report_text = render_report(
        environment_snapshot=environment_snapshot["versions"],
        input_hash_rows=input_hash_rows,
        pairwise_agreement_rows=pairwise_agreement_rows,
        ablation_rows=ablation_rows,
        remaining_failure_rows=remaining_failure_rows,
        reproducer_payload=reproducer_payload,
    )
    write_text(output_dir / "report.md", report_text)
    return 0


def collect_environment_snapshot() -> dict[str, Any]:
    versions = {
        "task_id": TASK_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
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


def load_case_payloads(case_dir: Path) -> dict[str, dict[str, Any]]:
    payloads = {}
    for path in sorted(case_dir.glob("*.json")):
        payloads[path.stem] = load_json(path)
    return payloads


def build_input_hash_rows(
    *,
    conformance_dir: Path,
    audit_dir: Path,
    case_ids: list[str],
) -> list[dict[str, Any]]:
    rows = []
    fixed_paths = [
        conformance_dir / "summary" / "benchmarks.json",
        audit_dir / "classification_table.json",
        audit_dir / "summary.json",
    ]
    for path in fixed_paths:
        rows.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(str(path)),
            }
        )
    for case_id in case_ids:
        path = conformance_dir / "cases" / f"{case_id}.json"
        rows.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "sha256": sha256_path(str(path)),
            }
        )
    return rows


def build_pairwise_agreement_rows(pairwise_case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    grouped_by_dim: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in pairwise_case_rows:
        grouped[(row["comparison_mode"], row["pair"])].append(row)
        grouped_by_dim[(row["comparison_mode"], row["pair"], int(row["dimension"]))].append(row)

    rows = []
    for (comparison_mode, pair), items in sorted(grouped.items()):
        exact_count = sum(1 for item in items if item["exact_match"])
        rows.append(
            {
                "scope": "all_dimensions",
                "comparison_mode": comparison_mode,
                "comparison_mode_label": MODE_LABELS[comparison_mode],
                "pair": pair,
                "dimension": "all",
                "total_dimension_records": len(items),
                "exact_count": exact_count,
                "different_count": len(items) - exact_count,
                "exact_rate": exact_count / float(len(items)),
            }
        )
    for (comparison_mode, pair, dimension), items in sorted(grouped_by_dim.items()):
        exact_count = sum(1 for item in items if item["exact_match"])
        rows.append(
            {
                "scope": "per_dimension",
                "comparison_mode": comparison_mode,
                "comparison_mode_label": MODE_LABELS[comparison_mode],
                "pair": pair,
                "dimension": dimension,
                "total_dimension_records": len(items),
                "exact_count": exact_count,
                "different_count": len(items) - exact_count,
                "exact_rate": exact_count / float(len(items)),
            }
        )
    return rows


def build_ablation_rows(pairwise_case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for row in pairwise_case_rows:
        if row["comparison_mode"] == "raw_exact":
            totals[row["pair"]] += 1
        if row["exact_match"]:
            counts[(row["pair"], row["comparison_mode"])] += 1

    rows = []
    for pair in PAIR_KEYS:
        raw_exact = counts[(pair, "raw_exact")]
        semantic = counts[(pair, "distance_zero_semantic")]
        mode_b = counts[(pair, "drop_zero_length_intervals")]
        mode_c = counts[(pair, "drop_zero_length_intervals_plus_float32_roundtrip")]
        mode_d = counts[(pair, "threshold_truncation_harmonized")]
        rows.append(
            {
                "pair": pair,
                "raw_exact_count": raw_exact,
                "distance_zero_semantic_count": semantic,
                "mode_b_count": mode_b,
                "mode_c_count": mode_c,
                "mode_d_count": mode_d,
                "closed_by_mode_b_vs_raw": mode_b - raw_exact,
                "closed_by_mode_c_vs_mode_b": mode_c - mode_b,
                "closed_by_mode_d_vs_mode_c": mode_d - mode_c,
                "remaining_after_mode_d": totals[pair] - mode_d,
            }
        )
    return rows


def write_remaining_failure_reproducers(
    *,
    remaining_failure_rows: list[dict[str, Any]],
    case_payloads: dict[str, dict[str, Any]],
    conformance_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if not remaining_failure_rows:
        note = {
            "task_id": TASK_ID,
            "message": "No remaining failures after threshold-truncation harmonization.",
        }
        return note

    remaining_failure_rows = sorted(
        remaining_failure_rows,
        key=lambda row: (
            case_payloads[row["case_id"]]["results"]["matrix_size"],
            row["case_id"],
            row["pair"],
            row["dimension"],
        ),
    )
    minimal = remaining_failure_rows[0]
    case_id = minimal["case_id"]
    case_payload = case_payloads[case_id]
    benchmark_id = case_payload["benchmark"]["benchmark_id"]
    payload = {
        "task_id": TASK_ID,
        "case_id": case_id,
        "pair": minimal["pair"],
        "dimension": minimal["dimension"],
        "case_payload_path": str((conformance_dir / "cases" / f"{case_id}.json").resolve()),
        "distance_matrix_path": str((conformance_dir / "inputs" / benchmark_id / "distance_matrix.npy").resolve()),
        "point_cloud_path": str((conformance_dir / "inputs" / benchmark_id / "point_cloud.npy").resolve()),
        "exact_command": (
            "PYTHONPATH=src python scripts/run_normalized_conformance.py "
            f"--conformance-dir {conformance_dir.relative_to(REPO_ROOT)} "
            f"--audit-dir {(conformance_dir / 'audit').relative_to(REPO_ROOT)} "
            f"--output-dir {output_dir.relative_to(REPO_ROOT)} --case-id {case_id}"
        ),
        "explanation": "The strongest documented normalization still leaves this pairwise interval multiset unequal.",
    }
    dump_json(output_dir / "minimal_repros" / "minimal_remaining_failure.json", payload)
    return payload


def render_report(
    *,
    environment_snapshot: dict[str, Any],
    input_hash_rows: list[dict[str, Any]],
    pairwise_agreement_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    remaining_failure_rows: list[dict[str, Any]],
    reproducer_payload: dict[str, Any],
) -> str:
    overall_rows = [row for row in pairwise_agreement_rows if row["scope"] == "all_dimensions"]
    lines = [
        f"# {TASK_ID}",
        "",
        "## setup",
        f"- Generated at UTC: {environment_snapshot['generated_at_utc']}",
        f"- Python: `{environment_snapshot['python_version'].splitlines()[0]}`",
        f"- Platform: `{environment_snapshot['platform']}`",
        "- Key distributions:",
    ]
    for distribution, version in environment_snapshot["distributions"].items():
        lines.append(f"  - `{distribution}=={version}`")
    lines.extend(
        [
            "- Exact command:",
            "  - `PYTHONPATH=src python scripts/run_normalized_conformance.py --conformance-dir artifacts --audit-dir artifacts/audit --output-dir artifacts/normalized_conformance`",
            "",
            "## input artifact hashes",
            "",
            render_markdown_table(input_hash_rows[:12] + ([{"path": "...", "sha256": "..."}] if len(input_hash_rows) > 12 else [])),
            "",
            "## pairwise agreement tables",
            "",
            render_markdown_table(overall_rows),
            "",
            "## ablation table",
            "",
            render_markdown_table(ablation_rows),
            "",
            "## remaining failures",
        ]
    )
    if remaining_failure_rows:
        lines.extend(
            [
                "",
                render_markdown_table(remaining_failure_rows[:20]),
                "",
                f"Minimal reproducer: `{reproducer_payload.get('case_id', '')}`",
                f"Exact command: `{reproducer_payload.get('exact_command', '')}`",
                f"Explanation: {reproducer_payload.get('explanation', '')}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "No pairwise disagreements remain after mode D (`threshold_truncation_harmonized`).",
            ]
        )
    lines.extend(
        [
            "",
            "## reproducibility notes",
            "- The normalization comparator reuses saved raw outputs from `artifacts/cases/` and audit labels from `artifacts/audit/`.",
            "- Raw normalized interval tables are saved under `artifacts/normalized_conformance/normalized_tables/`.",
            "- Machine-readable pairwise agreement and ablation tables are saved under `artifacts/normalized_conformance/summary/`.",
            "- Input artifact hashes are saved under `artifacts/normalized_conformance/hashes/`.",
        ]
    )
    lines.append("")
    return "\n".join(lines)


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
        writer.writerows(serialize_json_value(rows))


def dump_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(serialize_json_value(payload), indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
