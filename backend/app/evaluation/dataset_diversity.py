from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DIAGNOSIS_TERMS = re.compile(
    r"\b(diagnos\w*|condition|problem|assessment|impression|cancer|tumou?r|diabetes|"
    r"hypertension|infection|sepsis|failure|disease|injury|fracture|stroke|infarct)\b",
    re.I,
)
MEDICATION_TERMS = re.compile(
    r"\b(medication|medicine|drug|dose|dosage|mg|mcg|gtt|tablet|capsule|insulin|"
    r"antibiotic|metformin|aspirin|tamsulosin|vancomycin|ciprofloxacin|heparin|warfarin)\b",
    re.I,
)
TIMELINE_TERMS = re.compile(
    r"\b(day|week|month|year|hour|follow[- ]?up|discharg\w*|admission|admitted|"
    r"presented|after|before|prior|then|subsequent|post[- ]?op|pre[- ]?op|"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
    re.I,
)


@dataclass(frozen=True)
class RecordProfile:
    note_id: str
    dataset: str
    token_count: int
    length_bucket: str
    diagnosis_density: float
    medication_density: float
    timeline_complexity: float
    strata: list[str]


def load_jsonl_records(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))
            if limit is not None and len(records) >= limit:
                break
    return records


def profile_records(records: list[dict[str, Any]]) -> list[RecordProfile]:
    profiles = []
    for index, record in enumerate(records):
        text = str(record.get("source_note") or record.get("text") or "")
        tokens = re.findall(r"[A-Za-z0-9%./+-]+", text)
        token_count = len(tokens)
        diagnosis = len(DIAGNOSIS_TERMS.findall(text))
        medication = len(MEDICATION_TERMS.findall(text))
        timeline = len(TIMELINE_TERMS.findall(text))
        length_bucket = _length_bucket(token_count)
        dataset = str(record.get("dataset") or "unknown")
        strata = [length_bucket, f"dataset_{_safe_stratum(dataset)}"]
        if diagnosis >= 3:
            strata.append("diagnosis_heavy")
        if diagnosis >= 6:
            strata.append("diagnosis_dense_extreme")
        if medication >= 3:
            strata.append("medication_heavy")
        if medication >= 6:
            strata.append("medication_dense_extreme")
        if timeline >= 4:
            strata.append("timeline_heavy")
        if timeline >= 8:
            strata.append("timeline_complex_extreme")
        if _messy_formatting(text):
            strata.append("messy_formatting")
        if diagnosis >= 3 and medication >= 3:
            strata.append("diagnosis_medication_combo")
        if diagnosis >= 3 and timeline >= 4:
            strata.append("diagnosis_timeline_combo")
        profiles.append(
            RecordProfile(
                note_id=str(record.get("note_id") or record.get("id") or f"record_{index}"),
                dataset=dataset,
                token_count=token_count,
                length_bucket=length_bucket,
                diagnosis_density=round(diagnosis / max(1, token_count), 6),
                medication_density=round(medication / max(1, token_count), 6),
                timeline_complexity=round(timeline / max(1, token_count), 6),
                strata=strata,
            )
        )
    return profiles


def build_stratified_subsets(
    records: list[dict[str, Any]],
    profiles: list[RecordProfile],
    *,
    subset_size: int,
) -> dict[str, list[dict[str, Any]]]:
    by_note_id = {profile.note_id: record for profile, record in zip(profiles, records, strict=True)}
    buckets: dict[str, list[RecordProfile]] = {}
    for profile in profiles:
        for stratum in profile.strata:
            buckets.setdefault(stratum, []).append(profile)
    subsets: dict[str, list[dict[str, Any]]] = {}
    for stratum, stratum_profiles in buckets.items():
        ordered = sorted(
            stratum_profiles,
            key=lambda item: (-item.diagnosis_density, -item.medication_density, -item.timeline_complexity, item.note_id),
        )
        subsets[stratum] = [by_note_id[item.note_id] for item in ordered[:subset_size]]
    return subsets


def write_stratified_subsets(output_dir: Path, subsets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"subsets": {}}
    for name, records in sorted(subsets.items()):
        path = output_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        manifest["subsets"][name] = {
            "path": str(path),
            "record_count": len(records),
            "record_ids": [str(record.get("note_id") or record.get("id") or "") for record in records],
        }
    return manifest


def build_dataset_diversity_report(
    *,
    dataset_path: Path,
    records: list[dict[str, Any]],
    profiles: list[RecordProfile],
    inventory: dict[str, Any],
    subset_manifest: dict[str, Any],
) -> str:
    dataset_counts = Counter(profile.dataset for profile in profiles)
    stratum_counts = Counter(stratum for profile in profiles for stratum in profile.strata)
    lines = [
        "# Dataset Diversity and Stratification",
        "",
        "## Source Dataset",
        "",
        f"- Input path: `{dataset_path}`",
        f"- Loaded records: `{len(records)}`",
        "",
        "## Available Dataset Inventory",
        "",
        "| Dataset | Status | Local records | Notes |",
        "| --- | --- | ---: | --- |",
    ]
    for name, item in inventory.items():
        lines.append(f"| {name} | {item['status']} | {item['record_count']} | {item['notes']} |")
    lines.extend(["", "## Dataset Counts", ""])
    for name, count in dataset_counts.most_common():
        lines.append(f"- `{name}`: `{count}`")
    lines.extend(["", "## Stratification Counts", ""])
    for name, count in stratum_counts.most_common():
        lines.append(f"- `{name}`: `{count}`")
    lines.extend(["", "## Generated Subsets", ""])
    for name, item in sorted(subset_manifest.get("subsets", {}).items()):
        lines.append(f"- `{name}`: `{item['record_count']}` records -> `{item['path']}`")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- Use `short`, `medium`, and `long` subsets for length sensitivity.",
            "- Use `diagnosis_heavy`, `medication_heavy`, and `timeline_heavy` for clinical omission stress tests.",
            "- Add MTS-Dialog and MEDIQA-Sum as cross-dataset proxy benchmarks when local normalized files are available.",
            "- Keep synthetic structured EHR cases for deterministic end-to-end citation and workflow validation.",
        ]
    )
    return "\n".join(lines)


def inventory_available_datasets(root: Path) -> dict[str, Any]:
    candidates = {
        "MultiClinSum": [root / "data/processed/governance/benchmark_set.jsonl", root / "data/processed/multiclinsum/multiclinsum_train_smoke.jsonl"],
        "MTS-Dialog": [root / "data/processed/mts_dialog", root / "data/raw/mts_dialog"],
        "MEDIQA-Sum": [root / "data/processed/mediqa_sum", root / "data/raw/mediqa_sum"],
        "Synthea": [root / "data/processed/synthea", root / "data/raw/synthea"],
        "Synthetic structured EHR": [root / "data/demo/final_demo_cases.json", root / "data/demo/seed_clinical_cases.json"],
    }
    return {name: _inventory_candidate(paths) for name, paths in candidates.items()}


def _inventory_candidate(paths: list[Path]) -> dict[str, Any]:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return {"status": "not_available", "record_count": 0, "notes": "No local processed/raw source found."}
    count = sum(_count_records(path) for path in existing)
    return {"status": "available", "record_count": count, "notes": ", ".join(str(path) for path in existing)}


def _count_records(path: Path) -> int:
    if path.is_dir():
        return sum(_count_records(child) for child in path.rglob("*") if child.is_file())
    if path.suffix.lower() == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return 1
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            return len(next((value for value in payload.values() if isinstance(value, list)), [payload]))
    return 1


def _length_bucket(token_count: int) -> str:
    if token_count < 180:
        return "short"
    if token_count < 650:
        return "medium"
    if token_count < 1400:
        return "long"
    return "very_long"


def _messy_formatting(text: str) -> bool:
    if not text.strip():
        return True
    long_lines = sum(1 for line in text.splitlines() if len(line) > 220)
    dense_whitespace = bool(re.search(r"[ \t]{4,}", text))
    odd_headers = bool(re.search(r"\b[A-Z][A-Z_/ -]{8,}:{2,}", text))
    uppercase_ratio = sum(1 for char in text if char.isupper()) / max(1, sum(1 for char in text if char.isalpha()))
    return long_lines >= 2 or uppercase_ratio > 0.55 or dense_whitespace or odd_headers


def _safe_stratum(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_") or "unknown"
