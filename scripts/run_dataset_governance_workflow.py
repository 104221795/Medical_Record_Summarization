from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from evaluation.data_governance.layers import HONESTY_WARNING
from src.data.dataset_loader import load_jsonl_dataset


OUTPUT_DIR = Path("D:/clin_summ_outputs/dataset_governance")
PROCESSED_GOVERNANCE_DIR = Path("data/processed/governance")
SUPPORTED_DATASETS = ("MultiClinSum", "MTS-Dialog", "MEDIQA-Sum", "Synthea", "SyntheticMass")
REQUIRED_FIELDS = ("note_id", "source_note", "reference_summary", "dataset", "split")


@dataclass(frozen=True)
class DatasetSource:
    name: str
    path: Path | None
    format: str
    summary_availability: str
    benchmark_suitability: str
    ingestion_suitability: str
    status: str
    notes: str


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)
    sources = discover_sources()
    records = load_supported_benchmark_records(sources)
    quality_rows, routed = score_and_route(records)

    benchmark_records = routed["benchmark"]
    warning_records = routed["warning"]
    rejected_records = routed["rejected"]
    manifest = build_manifest(sources, records, quality_rows, routed)

    write_inventory(OUTPUT_DIR / "dataset_inventory.md", sources)
    write_json(OUTPUT_DIR / "dataset_manifest.json", manifest)
    write_jsonl(OUTPUT_DIR / "record_quality.jsonl", quality_rows)
    write_jsonl(OUTPUT_DIR / "benchmark_manifest.jsonl", [manifest_row(record) for record in benchmark_records])
    write_jsonl(OUTPUT_DIR / "warning_manifest.jsonl", [manifest_row(record) for record in warning_records])
    write_jsonl(OUTPUT_DIR / "rejected_manifest.jsonl", [manifest_row(record) for record in rejected_records])
    write_jsonl(OUTPUT_DIR / "benchmark_set.jsonl", benchmark_records)
    write_jsonl(OUTPUT_DIR / "warning_set.jsonl", warning_records)
    write_jsonl(OUTPUT_DIR / "rejected_set.jsonl", rejected_records)
    write_jsonl(PROCESSED_GOVERNANCE_DIR / "benchmark_set.jsonl", benchmark_records)
    write_jsonl(PROCESSED_GOVERNANCE_DIR / "warning_set.jsonl", warning_records)
    write_jsonl(PROCESSED_GOVERNANCE_DIR / "rejected_set.jsonl", rejected_records)
    write_report(OUTPUT_DIR / "dataset_governance_report.md", sources, manifest)
    print(f"Dataset governance artifacts written to {OUTPUT_DIR}")
    print(f"Benchmark-ready records: {len(benchmark_records)}")


def discover_sources() -> list[DatasetSource]:
    multiclinsum_full = Path("data/processed/multiclinsum/multiclinsum_train_full.jsonl")
    multiclinsum_smoke = Path("data/processed/multiclinsum/multiclinsum_train_smoke.jsonl")
    mts_dir = Path("data/external/mts_dialog/MTS-Dialog/Main-Dataset")
    mediqa_candidates = [Path("data/processed/mediqa_sum"), Path("data/chq")]
    synthea_candidates = [Path("data/synthea"), Path("data/external/synthea")]
    syntheticmass_candidates = [Path("data/syntheticmass"), Path("data/external/syntheticmass")]

    sources: list[DatasetSource] = []
    sources.append(
        DatasetSource(
            name="MultiClinSum",
            path=multiclinsum_full if multiclinsum_full.exists() else multiclinsum_smoke if multiclinsum_smoke.exists() else None,
            format="processed JSONL" if (multiclinsum_full.exists() or multiclinsum_smoke.exists()) else "external zip expected",
            summary_availability="source/reference pairs available" if (multiclinsum_full.exists() or multiclinsum_smoke.exists()) else "not available",
            benchmark_suitability="primary benchmark-ready open proxy source-to-summary dataset" if multiclinsum_full.exists() else "smoke-only until full import exists",
            ingestion_suitability="medium; case-report prose, not FHIR/EHR ingestion",
            status="available" if (multiclinsum_full.exists() or multiclinsum_smoke.exists()) else "missing",
            notes="Full imported file preferred over smoke file.",
        )
    )
    sources.append(
        DatasetSource(
            name="MTS-Dialog",
            path=mts_dir if mts_dir.exists() else None,
            format="CSV source files" if mts_dir.exists() else "expected CSV files missing",
            summary_availability="dialogue plus section_text references" if mts_dir.exists() else "not available locally",
            benchmark_suitability="auxiliary dialogue-to-note proxy if CSVs are placed locally",
            ingestion_suitability="medium; dialogue normalization stress test",
            status="available" if mts_dir.exists() else "missing",
            notes="Importer is implemented, but local source CSVs were not found.",
        )
    )
    mediqa_path = next((path for path in mediqa_candidates if path.exists()), None)
    sources.append(
        DatasetSource(
            name="MEDIQA-Sum",
            path=mediqa_path,
            format="JSONL/XLSX related files" if mediqa_path else "expected MEDIQA-Sum files missing",
            summary_availability="CHQ/MeQSum-style question summaries available, official MEDIQA-Sum not confirmed" if mediqa_path else "not available locally",
            benchmark_suitability="warning only; not primary medical-record summarization unless official MEDIQA-Sum is normalized",
            ingestion_suitability="low for record summarization; useful for question summarization only",
            status="partial" if mediqa_path else "missing",
            notes="Local data/chq appears to be consumer health question summarization, not medical record summarization.",
        )
    )
    sources.append(
        DatasetSource(
            name="Synthea",
            path=next((path for path in synthea_candidates if path.exists()), None),
            format="synthetic FHIR/CSV expected",
            summary_availability="not expected by default",
            benchmark_suitability="not suitable for supervised summarization unless summaries are generated/curated",
            ingestion_suitability="high for synthetic FHIR ingestion if present",
            status="available" if any(path.exists() for path in synthea_candidates) else "missing",
            notes="No local Synthea folder found.",
        )
    )
    sources.append(
        DatasetSource(
            name="SyntheticMass",
            path=next((path for path in syntheticmass_candidates if path.exists()), None),
            format="synthetic FHIR/CSV expected",
            summary_availability="not expected by default",
            benchmark_suitability="not suitable for supervised summarization unless summaries are generated/curated",
            ingestion_suitability="high for synthetic FHIR ingestion if present",
            status="available" if any(path.exists() for path in syntheticmass_candidates) else "missing",
            notes="No local SyntheticMass folder found.",
        )
    )
    return sources


def load_supported_benchmark_records(sources: list[DatasetSource]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    multiclinsum = next(source for source in sources if source.name == "MultiClinSum")
    if multiclinsum.path and multiclinsum.path.exists():
        records.extend(load_jsonl_dataset(multiclinsum.path, dataset="multiclinsum", split="train", require_reference=True))
    return records


def score_and_route(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    routed: dict[str, list[dict[str, Any]]] = {"benchmark": [], "warning": [], "rejected": []}
    for record in records:
        fingerprint = fingerprint_record(record)
        duplicate = fingerprint in seen
        seen.add(fingerprint)
        scores = score_record(record, duplicate=duplicate)
        route = route_score(scores["quality_score"])
        enriched = {
            **record,
            **scores,
            "quality_route": route,
        }
        rows.append(
            {
                "note_id": record.get("note_id", ""),
                "dataset": record.get("dataset", ""),
                "split": record.get("split", ""),
                "route": route,
                **scores,
            }
        )
        routed[route].append(enriched)
    return rows, routed


def score_record(record: dict[str, Any], *, duplicate: bool) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if not str(record.get(field) or "").strip()]
    source = str(record.get("source_note") or "")
    reference = str(record.get("reference_summary") or "")
    completeness_score = 1.0 - len(missing) / len(REQUIRED_FIELDS)
    missing_field_score = completeness_score
    note_length_score = length_score(len(tokens(source)), minimum=40, target=180)
    summary_length_score = length_score(len(tokens(reference)), minimum=8, target=45)
    duplication_score = 0.0 if duplicate else 1.0
    formatting_score = formatting_score_for(source)
    quality_score = (
        0.26 * completeness_score
        + 0.18 * missing_field_score
        + 0.18 * note_length_score
        + 0.14 * summary_length_score
        + 0.12 * duplication_score
        + 0.12 * formatting_score
    )
    return {
        "completeness_score": round(completeness_score, 4),
        "missing_field_score": round(missing_field_score, 4),
        "note_length_score": round(note_length_score, 4),
        "summary_length_score": round(summary_length_score, 4),
        "duplication_score": round(duplication_score, 4),
        "formatting_score": round(formatting_score, 4),
        "quality_score": round(max(0.0, min(1.0, quality_score)), 4),
        "missing_fields": missing,
        "source_token_count": len(tokens(source)),
        "summary_token_count": len(tokens(reference)),
        "duplicate": duplicate,
    }


def route_score(score: float) -> str:
    if score >= 0.8:
        return "benchmark"
    if score >= 0.5:
        return "warning"
    return "rejected"


def length_score(length: int, *, minimum: int, target: int) -> float:
    if length <= 0:
        return 0.0
    if length < minimum:
        return length / minimum
    return min(1.0, length / target)


def formatting_score_for(text: str) -> float:
    if not text.strip():
        return 0.0
    if re.search(r"\b(assessment|plan|history|diagnosis|medications?|brief hospital course)\s*:", text, re.I):
        return 1.0
    noisy = sum(1 for char in text if not (char.isalnum() or char.isspace() or char in ".,;:/+-_%()[]#'\"!?"))
    noise_ratio = noisy / max(1, len(text))
    if len(tokens(text)) >= 80 and noise_ratio <= 0.03:
        return 0.75
    if len(tokens(text)) >= 40 and noise_ratio <= 0.06:
        return 0.6
    return 0.35


def build_manifest(
    sources: list[DatasetSource],
    records: list[dict[str, Any]],
    quality_rows: list[dict[str, Any]],
    routed: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    route_counts = {route: len(rows) for route, rows in routed.items()}
    largest = max(
        (source for source in sources if source.status in {"available", "partial"}),
        key=lambda source: inventory_count(source),
        default=None,
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "honesty_warning": HONESTY_WARNING,
        "supported_datasets": [source.name for source in sources],
        "inventory": [source_to_dict(source) | {"record_count": inventory_count(source)} for source in sources],
        "total_loaded_records": len(records),
        "route_counts": route_counts,
        "quality_score_distribution": distribution([row["quality_score"] for row in quality_rows]),
        "largest_available_benchmark_dataset": largest.name if largest else None,
        "next_medium_scale_dataset": "MultiClinSum Full" if route_counts["benchmark"] >= 500 else "not_available",
        "benchmark_set_path": str(PROCESSED_GOVERNANCE_DIR / "benchmark_set.jsonl"),
        "warning_set_path": str(PROCESSED_GOVERNANCE_DIR / "warning_set.jsonl"),
        "rejected_set_path": str(PROCESSED_GOVERNANCE_DIR / "rejected_set.jsonl"),
    }


def inventory_count(source: DatasetSource) -> int:
    if not source.path or not source.path.exists():
        return 0
    if source.path.is_dir():
        return sum(count_jsonl(path) for path in source.path.rglob("*.jsonl"))
    if source.path.suffix.lower() == ".jsonl":
        return count_jsonl(source.path)
    return 0


def count_jsonl(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for line in handle if line.strip())


def source_to_dict(source: DatasetSource) -> dict[str, Any]:
    return {
        "dataset": source.name,
        "path": str(source.path) if source.path else None,
        "format": source.format,
        "summary_availability": source.summary_availability,
        "benchmark_suitability": source.benchmark_suitability,
        "ingestion_suitability": source.ingestion_suitability,
        "status": source.status,
        "notes": source.notes,
    }


def manifest_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "note_id": record.get("note_id", ""),
        "dataset": record.get("dataset", ""),
        "split": record.get("split", ""),
        "quality_score": record.get("quality_score"),
        "quality_route": record.get("quality_route"),
        "source_token_count": record.get("source_token_count"),
        "summary_token_count": record.get("summary_token_count"),
        "missing_fields": record.get("missing_fields", []),
    }


def write_inventory(path: Path, sources: list[DatasetSource]) -> None:
    lines = [
        "# Dataset Inventory",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "| Dataset | Status | Records | Format | Summary availability | Benchmark suitability | Ingestion suitability |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for source in sources:
        lines.append(
            f"| {source.name} | {source.status} | {inventory_count(source)} | {source.format} | {source.summary_availability} | {source.benchmark_suitability} | {source.ingestion_suitability} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(path: Path, sources: list[DatasetSource], manifest: dict[str, Any]) -> None:
    counts = manifest["route_counts"]
    lines = [
        "# Dataset Governance Report",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Answers",
        "",
        f"- Benchmark-ready records: `{counts['benchmark']}`",
        f"- Warning records: `{counts['warning']}`",
        f"- Rejected records: `{counts['rejected']}`",
        f"- Largest available benchmark dataset: `{manifest['largest_available_benchmark_dataset']}`",
        f"- Next medium-scale evaluation dataset: `{manifest['next_medium_scale_dataset']}`",
        "",
        "## Benchmark Plan",
        "",
        "1. Stage 1: 50 records from `data/processed/governance/benchmark_set.jsonl`.",
        "2. Stage 2: 200 records from the same benchmark-ready set.",
        "3. Stage 3: 500+ records from MultiClinSum Full after spot-checking warning/rejected samples.",
        "4. Stage 4: Cross-dataset evaluation after MTS-Dialog and official MEDIQA-Sum are locally available and normalized.",
        "",
        "## Dataset Expansion Decision",
        "",
        "MultiClinSum Full is now the only large benchmark-ready local dataset. MTS-Dialog is supported by an importer but missing local CSVs. MEDIQA-Sum is not confirmed locally; CHQ/MeQSum-style files are present but are not medical-record summarization.",
        "",
        "## Artifact Paths",
        "",
        "- `dataset_inventory.md`",
        "- `dataset_manifest.json`",
        "- `benchmark_manifest.jsonl`",
        "- `warning_manifest.jsonl`",
        "- `rejected_manifest.jsonl`",
        "- `benchmark_set.jsonl`",
        "- `data/processed/governance/benchmark_set.jsonl`",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def distribution(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"min": None, "max": None, "mean": None}
    return {"min": min(values), "max": max(values), "mean": round(mean(values), 4)}


def fingerprint_record(record: dict[str, Any]) -> str:
    return f"{record.get('source_note', '')}\n{record.get('reference_summary', '')}"


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9%./+-]+", text.casefold())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
