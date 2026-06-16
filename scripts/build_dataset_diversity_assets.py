from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.evaluation.dataset_diversity import (
    build_dataset_diversity_report,
    build_stratified_subsets,
    load_jsonl_records,
    profile_records,
    write_stratified_subsets,
)
from backend.app.evaluation.datasets.mts_dialog_importer import (
    DEFAULT_INPUT_DIR as DEFAULT_MTS_DIALOG_INPUT_DIR,
    DEFAULT_OUTPUT_DIR as DEFAULT_MTS_DIALOG_OUTPUT_DIR,
    MTSDialogImportError,
    import_mts_dialog_dataset,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY = Path("data/processed/governance/benchmark_set.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/processed/diversity")
DEFAULT_REPORT_DIR = Path("outputs/evaluation/dataset_diversity")
DEFAULT_SYNTHETIC_SOURCES = (
    Path("data/demo/seed_clinical_cases.json"),
    Path("data/demo/final_demo_cases.json"),
)
PROXY_WARNING = (
    "Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, "
    "or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as "
    "MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes."
)


@dataclass(frozen=True)
class DatasetSourceResult:
    name: str
    status: str
    record_count: int
    benchmark_role: str
    local_paths: list[str]
    notes: str


def main() -> None:
    args = parse_args()
    manifest = build_dataset_diversity_assets(args)
    print(f"Dataset diversity assets written to {manifest['output_dir']}")
    print(f"Combined records: {manifest['combined_record_count']}")
    print(f"Report: {manifest['report_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Priority 4 dataset diversity assets and stratified benchmark subsets."
    )
    parser.add_argument("--primary", default=str(DEFAULT_PRIMARY))
    parser.add_argument("--primary-limit", type=int, default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--subset-size", type=int, default=50)
    parser.add_argument("--mts-dialog-input-dir", default=str(DEFAULT_MTS_DIALOG_INPUT_DIR))
    parser.add_argument("--mts-dialog-output-dir", default=str(DEFAULT_MTS_DIALOG_OUTPUT_DIR))
    parser.add_argument("--mts-dialog-limit", type=int, default=None)
    parser.add_argument("--mediqa-sum-dir", default="data/processed/mediqa_sum")
    parser.add_argument("--messy-cases", type=int, default=40)
    parser.add_argument("--synthetic-limit", type=int, default=None)
    parser.add_argument(
        "--skip-mts-dialog-import",
        action="store_true",
        help="Only inspect existing processed MTS-Dialog JSONL files.",
    )
    return parser.parse_args()


def build_dataset_diversity_assets(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    primary_path = Path(args.primary)
    primary_records = _normalize_records(
        load_jsonl_records(primary_path, limit=args.primary_limit),
        dataset="multiclinsum",
        source_dataset="MultiClinSum",
        validation_layer="Layer C.1 - Primary Open Clinical Summarization Proxy",
        benchmark_role="primary_open_proxy",
    )
    source_results: list[DatasetSourceResult] = [
        DatasetSourceResult(
            name="MultiClinSum",
            status="available" if primary_records else "not_available",
            record_count=len(primary_records),
            benchmark_role="Primary source-note to summary proxy benchmark.",
            local_paths=[str(primary_path)],
            notes=(
                "Used as the main large open/proxy benchmark. Does not demonstrate real EHR performance."
                if primary_records
                else "Primary governance benchmark file is missing or empty."
            ),
        )
    ]

    mts_records, mts_result = _load_mts_dialog_records(
        input_dir=Path(args.mts_dialog_input_dir),
        output_dir=Path(args.mts_dialog_output_dir),
        limit=args.mts_dialog_limit,
        skip_import=args.skip_mts_dialog_import,
    )
    source_results.append(mts_result)

    mediqa_records, mediqa_result = _load_mediqa_sum_records(Path(args.mediqa_sum_dir))
    source_results.append(mediqa_result)

    synthetic_records, synthetic_result = _load_synthetic_structured_records(
        DEFAULT_SYNTHETIC_SOURCES,
        limit=args.synthetic_limit,
    )
    source_results.append(synthetic_result)

    messy_records = _build_messy_cases(
        [*synthetic_records, *primary_records[: max(0, args.messy_cases)]],
        limit=max(0, args.messy_cases),
    )
    messy_result = DatasetSourceResult(
        name="Messy formatting stress cases",
        status="available" if messy_records else "not_available",
        record_count=len(messy_records),
        benchmark_role="Formatting robustness and normalization stress test.",
        local_paths=[str(output_dir / "messy_formatting_cases.jsonl")],
        notes="Deterministic messy variants generated from de-identified proxy/demo records.",
    )
    source_results.append(messy_result)

    combined_records = _dedupe_records(
        [
            *primary_records,
            *mts_records,
            *mediqa_records,
            *synthetic_records,
            *messy_records,
        ]
    )
    profiles = profile_records(combined_records)
    subsets = build_stratified_subsets(combined_records, profiles, subset_size=args.subset_size)
    subset_manifest = write_stratified_subsets(output_dir / "stratified_subsets", subsets)

    _write_jsonl(output_dir / "diversity_benchmark_set.jsonl", combined_records)
    _write_jsonl(output_dir / "synthetic_structured_ehr.jsonl", synthetic_records)
    _write_jsonl(output_dir / "messy_formatting_cases.jsonl", messy_records)
    _write_profiles_csv(output_dir / "dataset_profiles.csv", profiles)

    inventory = {
        result.name: {
            "status": result.status,
            "record_count": result.record_count,
            "notes": result.notes,
            "benchmark_role": result.benchmark_role,
            "local_paths": result.local_paths,
        }
        for result in source_results
    }
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "proxy_warning": PROXY_WARNING,
        "output_dir": str(output_dir),
        "report_dir": str(report_dir),
        "primary_dataset_path": str(primary_path),
        "combined_record_count": len(combined_records),
        "source_inventory": inventory,
        "stratified_subsets": subset_manifest,
        "recommended_next_runs": {
            "stage_1_diversity_smoke": "Run 20-50 records across mixed dataset/source strata.",
            "stage_2_strata_probe": "Run each generated stratum subset with Qwen/Llama/Gemini Flash Lite.",
            "stage_3_cross_dataset": "Run separate MultiClinSum, MTS-Dialog, synthetic, and messy cohorts.",
            "stage_4_real_ehr_pending": "Only after credentialed MIMIC-IV-Note/BHC governance approval.",
        },
        "limitations": [
            "MTS-Dialog is auxiliary dialogue-to-note section evaluation, not full medical-record summarization.",
            "MEDIQA-Sum is included only when official local normalized files exist.",
            "Synthetic and messy cases validate workflow robustness, not real clinical performance.",
            "Real EHR benchmarking remains pending credentialed access and governance approval.",
        ],
    }
    manifest_path = output_dir / "dataset_diversity_manifest.json"
    _write_json(manifest_path, manifest)

    report = build_dataset_diversity_report(
        dataset_path=primary_path,
        records=combined_records,
        profiles=profiles,
        inventory=inventory,
        subset_manifest=subset_manifest,
    )
    priority_report = _build_priority4_report(
        manifest=manifest,
        source_results=source_results,
        profile_count=len(profiles),
    )
    report_path = report_dir / "DATASET_DIVERSITY_PRIORITY4_REPORT.md"
    inventory_path = report_dir / "dataset_inventory.md"
    report_path.write_text(priority_report + "\n\n" + report + "\n", encoding="utf-8")
    inventory_path.write_text(_build_inventory_report(source_results), encoding="utf-8")
    (report_dir / "dataset_diversity_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (report_dir / "dataset_strata_manifest.json").write_text(
        json.dumps(subset_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest["report_path"] = str(report_path)
    _write_json(manifest_path, manifest)
    return manifest


def _load_mts_dialog_records(
    *,
    input_dir: Path,
    output_dir: Path,
    limit: int | None,
    skip_import: bool,
) -> tuple[list[dict[str, Any]], DatasetSourceResult]:
    rows_by_split: dict[str, list[dict[str, Any]]] = {}
    status = "not_available"
    notes = "Expected MTS-Dialog CSVs are not present locally."
    if not skip_import:
        try:
            rows_by_split = import_mts_dialog_dataset(
                input_dir=input_dir,
                output_dir=output_dir,
                limit=limit,
            )
            status = "available"
            notes = "Imported from local MTS-Dialog CSV files."
        except MTSDialogImportError as exc:
            notes = str(exc)
    if not rows_by_split:
        rows_by_split = _read_processed_jsonl_dir(output_dir)
        if rows_by_split:
            status = "available"
            notes = "Loaded existing processed MTS-Dialog JSONL files."
    records = _normalize_records(
        [row for rows in rows_by_split.values() for row in rows],
        dataset="mts_dialog",
        source_dataset="MTS-Dialog",
        validation_layer="Layer C.2 - Auxiliary Dialogue-to-Note Proxy Evaluation",
        benchmark_role="auxiliary_dialogue_to_note",
    )
    return records, DatasetSourceResult(
        name="MTS-Dialog",
        status=status,
        record_count=len(records),
        benchmark_role="Auxiliary dialogue-to-note section benchmark.",
        local_paths=[str(input_dir), str(output_dir)],
        notes=notes,
    )


def _load_mediqa_sum_records(path: Path) -> tuple[list[dict[str, Any]], DatasetSourceResult]:
    rows_by_file = _read_processed_jsonl_dir(path)
    records = _normalize_records(
        [row for rows in rows_by_file.values() for row in rows],
        dataset="mediqa_sum",
        source_dataset="MEDIQA-Sum",
        validation_layer="Layer C.3 - MEDIQA-Sum Proxy Evaluation",
        benchmark_role="cross_dataset_proxy",
    )
    if records:
        status = "available"
        notes = "Loaded local normalized MEDIQA-Sum JSONL files."
    else:
        status = "not_available"
        notes = (
            "No official normalized MEDIQA-Sum JSONL files found. Local CHQ/MeQSum-style files are "
            "question summarization resources and are not counted as medical-record summarization."
        )
    return records, DatasetSourceResult(
        name="MEDIQA-Sum",
        status=status,
        record_count=len(records),
        benchmark_role="Cross-dataset summarization proxy when official local files exist.",
        local_paths=[str(path)],
        notes=notes,
    )


def _load_synthetic_structured_records(
    paths: tuple[Path, ...],
    *,
    limit: int | None,
) -> tuple[list[dict[str, Any]], DatasetSourceResult]:
    records: list[dict[str, Any]] = []
    existing: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        existing.append(str(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            continue
        for case in payload:
            converted = _synthetic_case_to_record(case)
            if converted:
                records.append(converted)
                if limit is not None and len(records) >= limit:
                    break
        if limit is not None and len(records) >= limit:
            break
    return records, DatasetSourceResult(
        name="Synthetic structured EHR cases",
        status="available" if records else "not_available",
        record_count=len(records),
        benchmark_role="End-to-end workflow, citation, missing-evidence, and safety scenario validation.",
        local_paths=existing or [str(path) for path in paths],
        notes=(
            "Converted local de-identified demo/FHIR-like cases into benchmark-style JSONL."
            if records
            else "No local synthetic structured EHR case file found."
        ),
    )


def _synthetic_case_to_record(case: dict[str, Any]) -> dict[str, Any] | None:
    case_id = str(case.get("case_id") or case.get("id") or "").strip()
    if not case_id:
        return None
    if "fhir_like_import" in case:
        return _fhir_demo_case_to_record(case)
    documents = case.get("documents") if isinstance(case.get("documents"), list) else []
    conditions = case.get("conditions") if isinstance(case.get("conditions"), list) else []
    medications = case.get("medications") if isinstance(case.get("medications"), list) else []
    observations = case.get("observations") if isinstance(case.get("observations"), list) else []
    reports = case.get("reports") if isinstance(case.get("reports"), list) else []
    source_note = "\n\n".join(
        part
        for part in (
            f"PATIENT: {case.get('gender', 'unknown')} de-identified patient.",
            _section("ENCOUNTER", [str((case.get("encounter") or {}).get("reason_for_visit") or "")]),
            _section("DIAGNOSIS", [_item_name(item) for item in conditions]),
            _section("MEDICATIONS", [_medication_text(item) for item in medications]),
            _section("LABS_AND_DIAGNOSTICS", [_observation_text(item) for item in observations] + [_report_text(item) for item in reports]),
            _section("SOURCE_NOTES", [str(document.get("text") or "") for document in documents if isinstance(document, dict)]),
        )
        if part.strip()
    )
    return _benchmark_record(
        note_id=f"synthetic_structured_{case_id}",
        patient_id=str(case.get("external_patient_id") or case.get("fhir_patient_id") or f"synthetic_patient_{case_id}"),
        encounter_id=str((case.get("encounter") or {}).get("external_encounter_id") or f"synthetic_encounter_{case_id}"),
        source_note=source_note,
        reference_summary=_synthetic_reference_summary(case),
        dataset="synthetic_structured_ehr",
        source_dataset="Synthetic structured EHR",
        split="demo",
        validation_layer="Layer A/B - Workflow and Citation Validation",
        benchmark_role="synthetic_structured_ehr",
        metadata={"title": case.get("title"), "demo_focus": case.get("demo_focus")},
    )


def _fhir_demo_case_to_record(case: dict[str, Any]) -> dict[str, Any] | None:
    payload = case.get("fhir_like_import") or {}
    records = payload.get("records") if isinstance(payload.get("records"), dict) else {}
    patients = records.get("patients") or []
    encounters = records.get("encounters") or []
    documents = records.get("documents") or []
    patient = patients[0] if patients else {}
    encounter = encounters[0] if encounters else {}
    source_note = "\n\n".join(
        part
        for part in (
            f"PATIENT: {patient.get('gender', 'unknown')} de-identified patient.",
            _section("ENCOUNTER", [str((encounter.get("reasonCode") or {}).get("text") or "")]),
            _section("DIAGNOSIS", [_fhir_code_text(item) for item in records.get("conditions") or []]),
            _section("MEDICATIONS", [_fhir_medication_text(item) for item in records.get("medications") or []]),
            _section("LABS_AND_DIAGNOSTICS", [_fhir_observation_text(item) for item in records.get("observations") or []]),
            _section("SOURCE_NOTES", [str(document.get("raw_text") or "") for document in documents if isinstance(document, dict)]),
        )
        if part.strip()
    )
    case_id = str(case.get("case_id") or "fhir_demo").strip()
    return _benchmark_record(
        note_id=f"synthetic_structured_{case_id}",
        patient_id=str(patient.get("id") or f"synthetic_patient_{case_id}"),
        encounter_id=str(encounter.get("id") or f"synthetic_encounter_{case_id}"),
        source_note=source_note,
        reference_summary=_synthetic_reference_summary(case),
        dataset="synthetic_structured_ehr",
        source_dataset="Synthetic structured EHR",
        split="demo",
        validation_layer="Layer A/B - Workflow and Citation Validation",
        benchmark_role="synthetic_structured_ehr",
        metadata={"title": case.get("title"), "demo_focus": case.get("demo_focus")},
    )


def _build_messy_cases(records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    messy: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if len(messy) >= limit:
            break
        source_note = str(record.get("source_note") or "")
        if not source_note.strip():
            continue
        messy_record = dict(record)
        messy_record["note_id"] = f"messy_{record.get('note_id') or index}"
        messy_record["dataset"] = "messy_formatting"
        messy_record["source_dataset"] = "Deterministic messy formatting stress case"
        messy_record["validation_layer"] = "Layer B - Input Normalization and Formatting Stress Test"
        messy_record["split"] = "stress"
        messy_record["source_note"] = _messy_format_text(source_note)
        metadata = dict(record.get("metadata") or {})
        metadata.update(
            {
                "base_note_id": record.get("note_id"),
                "stress_tags": ["messy_formatting", "irregular_spacing", "uppercase_headers", "line_break_noise"],
            }
        )
        messy_record["metadata"] = metadata
        messy.append(messy_record)
    return messy


def _messy_format_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    chunks = []
    for index, sentence in enumerate(sentences[:24]):
        if not sentence:
            continue
        prefix = ""
        if index % 5 == 0:
            prefix = "\n\nASSESSMENT/PLAN::: "
        elif index % 3 == 0:
            prefix = "\n-- "
        elif index % 2 == 0:
            prefix = "   "
        chunks.append(prefix + sentence)
    messy = " ".join(chunks)
    messy = messy.replace(" and ", "  and   ")
    messy = messy.replace(" mg", "mg")
    return messy[:14000]


def _normalize_records(
    records: list[dict[str, Any]],
    *,
    dataset: str,
    source_dataset: str,
    validation_layer: str,
    benchmark_role: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        source_note = str(record.get("source_note") or record.get("text") or record.get("dialogue") or "")
        reference_summary = str(record.get("reference_summary") or record.get("target") or record.get("section_text") or "")
        if not source_note.strip() or not reference_summary.strip():
            continue
        metadata = dict(record.get("metadata") or {})
        metadata.setdefault("benchmark_role", benchmark_role)
        normalized.append(
            _benchmark_record(
                note_id=str(record.get("note_id") or record.get("id") or f"{dataset}_{index:06d}"),
                patient_id=str(record.get("patient_id") or f"{dataset}_patient_{index:06d}"),
                encounter_id=str(record.get("encounter_id") or f"{dataset}_encounter_{index:06d}"),
                source_note=source_note,
                reference_summary=reference_summary,
                dataset=str(record.get("dataset") or dataset),
                source_dataset=str(record.get("source_dataset") or source_dataset),
                split=str(record.get("split") or "unknown"),
                validation_layer=str(record.get("validation_layer") or validation_layer),
                benchmark_role=benchmark_role,
                metadata=metadata,
                extra=record,
            )
        )
    return normalized


def _benchmark_record(
    *,
    note_id: str,
    patient_id: str,
    encounter_id: str,
    source_note: str,
    reference_summary: str,
    dataset: str,
    source_dataset: str,
    split: str,
    validation_layer: str,
    benchmark_role: str,
    metadata: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = {
        "note_id": note_id,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "source_note": source_note.strip(),
        "reference_summary": reference_summary.strip(),
        "dataset": dataset,
        "split": split,
        "source_dataset": source_dataset,
        "validation_layer": validation_layer,
        "benchmark_role": benchmark_role,
        "metadata": metadata or {},
    }
    for key in ("quality_score", "quality_route", "source_token_count", "summary_token_count"):
        if extra and key in extra:
            base[key] = extra[key]
    return base


def _read_processed_jsonl_dir(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    files = [path] if path.is_file() else sorted(path.glob("*.jsonl"))
    rows: dict[str, list[dict[str, Any]]] = {}
    for file_path in files:
        rows[file_path.stem] = load_jsonl_records(file_path)
    return rows


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("note_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def _section(title: str, values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return ""
    return f"{title}:\n" + "\n".join(f"- {value}" for value in cleaned)


def _item_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("code") or item.get("text") or "").strip()


def _medication_text(item: dict[str, Any]) -> str:
    return " ".join(
        value
        for value in (
            str(item.get("name") or "").strip(),
            str(item.get("dosage_text") or "").strip(),
            str(item.get("route") or "").strip(),
            str(item.get("frequency") or "").strip(),
        )
        if value
    )


def _observation_text(item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    value = str(item.get("value") or "").strip()
    unit = str(item.get("unit") or "").strip()
    return " ".join(part for part in (name, value, unit) if part)


def _report_text(item: dict[str, Any]) -> str:
    return str(item.get("conclusion") or item.get("text") or item.get("title") or "").strip()


def _fhir_code_text(item: dict[str, Any]) -> str:
    code = item.get("code") if isinstance(item.get("code"), dict) else {}
    return str(code.get("text") or item.get("id") or "").strip()


def _fhir_medication_text(item: dict[str, Any]) -> str:
    medication = item.get("medicationCodeableConcept") if isinstance(item.get("medicationCodeableConcept"), dict) else {}
    dosage = item.get("dosageInstruction") if isinstance(item.get("dosageInstruction"), list) else []
    dosage_text = "; ".join(str(row.get("text") or "") for row in dosage if isinstance(row, dict))
    return " ".join(part for part in (str(medication.get("text") or ""), dosage_text, str(item.get("status") or "")) if part)


def _fhir_observation_text(item: dict[str, Any]) -> str:
    code = item.get("code") if isinstance(item.get("code"), dict) else {}
    quantity = item.get("valueQuantity") if isinstance(item.get("valueQuantity"), dict) else {}
    return " ".join(
        part
        for part in (
            str(code.get("text") or item.get("id") or ""),
            str(quantity.get("value") or ""),
            str(quantity.get("unit") or ""),
        )
        if part
    )


def _synthetic_reference_summary(case: dict[str, Any]) -> str:
    title = str(case.get("title") or "Synthetic structured EHR case").strip()
    focus = str(case.get("demo_focus") or "").strip()
    expected = case.get("expected_behavior")
    if isinstance(expected, list) and expected:
        return f"{title}. Expected review focus: {expected[0]}"
    if focus:
        return f"{title}. {focus}"
    return title


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_profiles_csv(path: Path, profiles: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(profiles[0]).keys()) if profiles else [
        "note_id",
        "dataset",
        "token_count",
        "length_bucket",
        "diagnosis_density",
        "medication_density",
        "timeline_complexity",
        "strata",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for profile in profiles:
            row = asdict(profile)
            row["strata"] = "|".join(row["strata"])
            writer.writerow(row)


def _build_inventory_report(results: list[DatasetSourceResult]) -> str:
    lines = [
        "# Dataset Inventory",
        "",
        PROXY_WARNING,
        "",
        "| Dataset | Status | Records | Role | Notes |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.name} | {result.status} | {result.record_count} | "
            f"{result.benchmark_role} | {result.notes} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- MultiClinSum remains the primary large open/proxy summarization dataset.",
            "- MTS-Dialog should be used as an auxiliary dialogue-to-note dataset when local CSVs are placed under `data/external/mts_dialog/MTS-Dialog/Main-Dataset/`.",
            "- MEDIQA-Sum should be added only from official normalized files; CHQ/MeQSum question summarization is not counted as medical-record summarization.",
            "- Synthetic and messy cases test product robustness, citation traceability, and normalization behavior.",
        ]
    )
    return "\n".join(lines)


def _build_priority4_report(
    *,
    manifest: dict[str, Any],
    source_results: list[DatasetSourceResult],
    profile_count: int,
) -> str:
    available = [result for result in source_results if result.status == "available"]
    pending = [result for result in source_results if result.status != "available"]
    lines = [
        "# Priority 4 - Dataset Diversity Expansion",
        "",
        PROXY_WARNING,
        "",
        "## What Changed",
        "",
        "- Built a combined diversity benchmark set across available open/proxy and synthetic sources.",
        "- Added deterministic synthetic structured EHR cases for workflow and citation validation.",
        "- Added messy formatting stress cases to test input normalization and RAG robustness.",
        "- Generated stratified subsets by note length, diagnosis density, medication density, timeline complexity, and formatting difficulty.",
        "- Kept MTS-Dialog and MEDIQA-Sum honest: included when local files exist, otherwise marked pending instead of overclaiming.",
        "",
        "## Current Coverage",
        "",
        f"- Combined records: `{manifest['combined_record_count']}`",
        f"- Profiled records: `{profile_count}`",
        f"- Available source groups: `{len(available)}`",
        f"- Pending source groups: `{len(pending)}`",
        "",
        "## Source Status",
        "",
    ]
    for result in source_results:
        lines.append(f"- `{result.name}`: {result.status}, {result.record_count} records. {result.notes}")
    lines.extend(
        [
            "",
            "## Recommended Benchmark Use",
            "",
            "1. Run a 20-50 record smoke on `diversity_benchmark_set.jsonl` using Qwen/Llama/Gemini Flash Lite.",
            "2. Run one subset at a time from `stratified_subsets/` to find failure modes by clinical difficulty.",
            "3. Compare raw, clinical-context, and RAG flows on the same subset before scaling.",
            "4. Add official MTS-Dialog and MEDIQA-Sum local files, then rerun this script to activate cross-dataset rows.",
            "",
            "## Why This Matters",
            "",
            "A model can look good on the average MultiClinSum record while still failing long notes, medication-heavy notes, timeline-heavy notes, or messy input. These assets make those failure modes visible before any medium-scale benchmark claim.",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
