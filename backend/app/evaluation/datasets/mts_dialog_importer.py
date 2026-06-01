from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("data/external/mts_dialog/MTS-Dialog/Main-Dataset")
DEFAULT_OUTPUT_DIR = Path("data/processed/mts_dialog")
REQUIRED_COLUMNS = ("ID", "section_header", "section_text", "dialogue")
SPLIT_FILES = {
    "train": "MTS-Dialog-TrainingSet.csv",
    "validation": "MTS-Dialog-ValidationSet.csv",
    "test_1": "MTS-Dialog-TestSet-1-MEDIQA-Chat-2023.csv",
    "test_2": "MTS-Dialog-TestSet-2-MEDIQA-Sum-2023.csv",
}
OUTPUT_FILES = {
    "train": "mts_dialog_train.jsonl",
    "validation": "mts_dialog_validation.jsonl",
    "test_1": "mts_dialog_test_1.jsonl",
    "test_2": "mts_dialog_test_2.jsonl",
}


class MTSDialogImportError(ValueError):
    pass


def import_mts_dialog_dataset(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    source_dir = Path(input_dir)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    imported: dict[str, list[dict[str, Any]]] = {}
    for split, filename in SPLIT_FILES.items():
        source_path = source_dir / filename
        rows = _read_split(source_path, split=split, limit=limit)
        output_path = target_dir / OUTPUT_FILES[split]
        _write_jsonl(output_path, rows)
        imported[split] = rows
    return imported


def _read_split(path: Path, *, split: str, limit: int | None) -> list[dict[str, Any]]:
    if not path.exists():
        raise MTSDialogImportError(
            f"Missing MTS-Dialog file: {path}. Expected the Main-Dataset CSV export under "
            f"{DEFAULT_INPUT_DIR.as_posix()}."
        )

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_columns(path, reader.fieldnames or [])
        for index, row in enumerate(reader, start=1):
            source_note = _required_text(row, "dialogue", path=path, row_number=index)
            reference_summary = _required_text(row, "section_text", path=path, row_number=index)
            original_id = _required_text(row, "ID", path=path, row_number=index)
            section_header = _required_text(row, "section_header", path=path, row_number=index)
            rows.append(
                {
                    "note_id": f"mts_dialog_{split}_{_safe_identifier(original_id)}",
                    "source_note": source_note,
                    "reference_summary": reference_summary,
                    "dataset": "mts_dialog",
                    "split": split,
                    "source_dataset": "MTS-Dialog",
                    "validation_layer": "Layer C.2 - Auxiliary Dialogue-to-Note Proxy Evaluation",
                    "task_type": "clinical_dialogue_to_note_section",
                    "section_header": section_header,
                    "metadata": {
                        "original_record_id": original_id,
                    },
                }
            )
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _validate_columns(path: Path, columns: list[str]) -> None:
    available = {column.strip() for column in columns}
    missing = [column for column in REQUIRED_COLUMNS if column not in available]
    if missing:
        raise MTSDialogImportError(
            f"{path} is missing required columns: {', '.join(missing)}. "
            f"Required columns are: {', '.join(REQUIRED_COLUMNS)}."
        )


def _required_text(row: dict[str, Any], key: str, *, path: Path, row_number: int) -> str:
    value = row.get(key)
    if value is None or not str(value).strip():
        raise MTSDialogImportError(f"{path}:{row_number} has empty required column '{key}'.")
    return str(value).strip()


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()) or "unknown"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MTS-Dialog into the internal evaluation JSONL schema.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    imported = import_mts_dialog_dataset(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        limit=args.limit,
    )
    counts = ", ".join(f"{split}={len(rows)}" for split, rows in imported.items())
    print(f"Wrote MTS-Dialog rows to {args.output_dir}: {counts}")


if __name__ == "__main__":
    main()
