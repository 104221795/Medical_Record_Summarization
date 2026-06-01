from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import pytest

from backend.app.evaluation.datasets import multiclinsum_importer
from backend.app.evaluation.datasets.multiclinsum_importer import (
    MultiClinSumImportError,
    import_multiclinsum_dataset,
)


def test_multiclinsum_importer_normalizes_tiny_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "multiclinsum_large_scale_train.zip"
    _write_tiny_multiclinsum_zip(zip_path)

    output_path = tmp_path / "processed.jsonl"
    rows = import_multiclinsum_dataset(zip_path=zip_path, output_path=output_path, limit=5)

    assert output_path.exists()
    assert len(rows) == 1
    assert rows[0]["note_id"] == "case_001"
    assert rows[0]["dataset"] == "multiclinsum"
    assert rows[0]["source_note"].startswith("Patient has documented fever")
    assert rows[0]["reference_summary"] == "Fever documented; chest x-ray normal."
    persisted = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert persisted["metadata"]["source_file"] == "train.csv"
    assert persisted["validation_layer"].startswith("Layer C.1")


def test_multiclinsum_importer_accepts_large_scale_en_filename(tmp_path: Path) -> None:
    zip_path = tmp_path / "multiclinsum_large-scale_train_en.zip"
    _write_tiny_multiclinsum_zip(zip_path)

    rows = import_multiclinsum_dataset(zip_path=zip_path, output_path=tmp_path / "processed.jsonl", limit=5)

    assert len(rows) == 1
    assert rows[0]["note_id"] == "case_001"


def test_multiclinsum_auto_detects_single_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    zip_path = tmp_path / "multiclinsum_large-scale_train_en.zip"
    _write_tiny_multiclinsum_zip(zip_path)
    monkeypatch.setattr(multiclinsum_importer, "DEFAULT_ZIP_DIR", tmp_path)

    rows = import_multiclinsum_dataset(output_path=tmp_path / "processed.jsonl", limit=5)

    assert len(rows) == 1
    assert rows[0]["metadata"]["source_file"] == "train.csv"


def test_multiclinsum_auto_detect_fails_when_multiple_zips_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_tiny_multiclinsum_zip(tmp_path / "multiclinsum_large_scale_train.zip")
    _write_tiny_multiclinsum_zip(tmp_path / "multiclinsum_large-scale_train_en.zip")
    monkeypatch.setattr(multiclinsum_importer, "DEFAULT_ZIP_DIR", tmp_path)

    with pytest.raises(MultiClinSumImportError, match="Multiple MultiClinSum zip files"):
        import_multiclinsum_dataset(output_path=tmp_path / "processed.jsonl", limit=5)


def test_multiclinsum_missing_zip_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(MultiClinSumImportError, match="Place one of"):
        import_multiclinsum_dataset(zip_path=tmp_path / "missing.zip", output_path=tmp_path / "out.jsonl")


def _write_tiny_multiclinsum_zip(zip_path: Path) -> None:
    csv_path = zip_path.parent / "train.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "input_document", "summary"])
        writer.writeheader()
        writer.writerow(
            {
                "case_id": "case_001",
                "input_document": "Patient has documented fever. Chest x-ray is normal.",
                "summary": "Fever documented; chest x-ray normal.",
            }
        )
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(csv_path, "train.csv")
