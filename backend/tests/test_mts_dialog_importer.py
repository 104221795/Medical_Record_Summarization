from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from backend.app.evaluation.datasets.mts_dialog_importer import (
    MTSDialogImportError,
    import_mts_dialog_dataset,
)


def test_mts_dialog_importer_writes_expected_splits(tmp_path: Path) -> None:
    input_dir = tmp_path / "MTS-Dialog" / "Main-Dataset"
    input_dir.mkdir(parents=True)
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-TrainingSet.csv", "train001")
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-ValidationSet.csv", "validation001")
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-TestSet-1-MEDIQA-Chat-2023.csv", "test001")
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-TestSet-2-MEDIQA-Sum-2023.csv", "test002")

    output_dir = tmp_path / "processed"
    imported = import_mts_dialog_dataset(input_dir=input_dir, output_dir=output_dir, limit=1)

    assert set(imported) == {"train", "validation", "test_1", "test_2"}
    assert (output_dir / "mts_dialog_train.jsonl").exists()
    assert (output_dir / "mts_dialog_validation.jsonl").exists()
    assert (output_dir / "mts_dialog_test_1.jsonl").exists()
    assert (output_dir / "mts_dialog_test_2.jsonl").exists()
    persisted = json.loads((output_dir / "mts_dialog_train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert persisted["dataset"] == "mts_dialog"
    assert persisted["split"] == "train"
    assert persisted["source_note"] == "Doctor: How are you feeling? Patient: I have chest pain."
    assert persisted["reference_summary"] == "Patient reports chest pain."
    assert persisted["validation_layer"].startswith("Layer C.2")
    assert persisted["metadata"]["original_record_id"] == "train001"


def test_mts_dialog_importer_requires_expected_columns(tmp_path: Path) -> None:
    input_dir = tmp_path / "MTS-Dialog" / "Main-Dataset"
    input_dir.mkdir(parents=True)
    bad_path = input_dir / "MTS-Dialog-TrainingSet.csv"
    with bad_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ID", "dialogue"])
        writer.writeheader()
        writer.writerow({"ID": "bad001", "dialogue": "Doctor: hello"})
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-ValidationSet.csv", "validation001")
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-TestSet-1-MEDIQA-Chat-2023.csv", "test001")
    _write_mts_dialog_csv(input_dir / "MTS-Dialog-TestSet-2-MEDIQA-Sum-2023.csv", "test002")

    with pytest.raises(MTSDialogImportError, match="missing required columns"):
        import_mts_dialog_dataset(input_dir=input_dir, output_dir=tmp_path / "processed")


def _write_mts_dialog_csv(path: Path, record_id: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ID", "section_header", "section_text", "dialogue"])
        writer.writeheader()
        writer.writerow(
            {
                "ID": record_id,
                "section_header": "Assessment",
                "section_text": "Patient reports chest pain.",
                "dialogue": "Doctor: How are you feeling? Patient: I have chest pain.",
            }
        )
