from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.data.dataset_loader import (
    DatasetValidationError,
    create_small_demo_subset,
    load_bhc_dataset,
    load_jsonl_dataset,
    load_mimic_iv_note_dataset,
)
from src.data.preprocessing import normalize_to_internal_schema


SAMPLE_DATASET = Path("data/evaluation/sample_ehr_notes.jsonl")


def test_load_mock_dataset() -> None:
    records = load_jsonl_dataset(SAMPLE_DATASET, dataset="mock")

    assert len(records) == 3
    assert records[0]["dataset"] == "mock"
    assert records[0]["split"] == "train"
    assert records[0]["source_note"]
    assert records[0]["reference_summary"]


def test_normalize_dataset_preserves_ids() -> None:
    normalized = normalize_to_internal_schema(
        {
            "note_id": "note_custom",
            "patient_id": "patient_custom",
            "encounter_id": "enc_custom",
            "source_note": "Clinical note text.",
            "reference_summary": "Reference summary.",
        },
        dataset="mock",
        split="validation",
    )

    assert normalized["note_id"] == "note_custom"
    assert normalized["patient_id"] == "patient_custom"
    assert normalized["encounter_id"] == "enc_custom"
    assert normalized["split"] == "validation"


def test_normalize_legacy_jsonl_shape() -> None:
    normalized = normalize_to_internal_schema(
        {
            "idx": 42,
            "inputs": "Legacy source note.",
            "target": "Legacy reference summary.",
        },
        dataset="mock",
        split="test",
    )

    assert normalized["note_id"] == "42"
    assert normalized["patient_id"] == "patient_unknown"
    assert normalized["encounter_id"] == "enc_unknown"
    assert normalized["source_note"] == "Legacy source note."
    assert normalized["reference_summary"] == "Legacy reference summary."


def test_reject_empty_source_note() -> None:
    with pytest.raises(DatasetValidationError, match="empty source_note"):
        normalize_to_internal_schema(
            {
                "note_id": "note_empty",
                "patient_id": "patient_001",
                "encounter_id": "enc_001",
                "source_note": " ",
                "reference_summary": "Reference summary.",
            },
            dataset="mock",
            split="test",
        )


def test_reject_missing_reference_summary_for_training_or_evaluation() -> None:
    with pytest.raises(DatasetValidationError, match="reference_summary"):
        normalize_to_internal_schema(
            {
                "note_id": "note_missing_target",
                "patient_id": "patient_001",
                "encounter_id": "enc_001",
                "source_note": "Source note.",
            },
            dataset="mock",
            split="train",
            require_reference=True,
        )


def test_load_mimic_iv_note_style_without_real_mimic_files(tmp_path: Path) -> None:
    path = tmp_path / "discharge.csv"
    _write_csv(
        path,
        [
            {
                "note_id": "mimic-note-001",
                "subject_id": "10000001",
                "hadm_id": "20000001",
                "text": (
                    "DISCHARGE SUMMARY:\n"
                    "Brief Hospital Course: De-identified course text for evaluation.\n"
                    "DISCHARGE MEDICATIONS: Listed in source."
                ),
            }
        ],
    )

    records = load_mimic_iv_note_dataset(path, split="test")

    assert len(records) == 1
    assert records[0]["dataset"] == "mimic_iv_note"
    assert records[0]["note_id"] == "mimic-note-001"
    assert records[0]["patient_id"] == "10000001"
    assert records[0]["encounter_id"] == "20000001"
    assert records[0]["reference_summary"] == "De-identified course text for evaluation."


def test_load_bhc_style_without_real_mimic_files(tmp_path: Path) -> None:
    path = tmp_path / "bhc.csv"
    _write_csv(
        path,
        [
            {
                "note_id": "bhc-001",
                "subject_id": "10000002",
                "hadm_id": "20000002",
                "discharge_summary": "Full de-identified discharge summary text.",
                "brief_hospital_course": "Brief hospital course target.",
                "split": "validation",
            }
        ],
    )

    records = load_bhc_dataset(path)

    assert len(records) == 1
    assert records[0]["dataset"] == "mimic_iv_ext_bhc"
    assert records[0]["split"] == "validation"
    assert records[0]["source_note"] == "Full de-identified discharge summary text."
    assert records[0]["reference_summary"] == "Brief hospital course target."


def test_create_small_demo_subset_assigns_splits() -> None:
    records = load_jsonl_dataset(SAMPLE_DATASET, dataset="mock")

    subset = create_small_demo_subset(records, max_records=2)

    assert len(subset) == 2
    assert {record["split"] for record in subset}.issubset({"train", "validation", "test"})


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
