from __future__ import annotations

import csv
import gzip
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .preprocessing import (
    DatasetValidationError,
    deidentification_warnings,
    extract_brief_hospital_course,
    normalize_to_internal_schema,
)
from .splits import split_records


def load_jsonl_dataset(
    path: str | Path,
    *,
    dataset: str = "mock",
    split: str = "test",
    require_reference: bool = True,
    max_records: int | None = None,
) -> list[dict[str, str]]:
    """Load the local JSONL sample or legacy `{inputs,target}` JSONL format."""

    records = []
    for row in _read_jsonl(Path(path)):
        normalized = normalize_to_internal_schema(
            row,
            dataset=dataset,
            split=str(row.get("split") or split),
            require_reference=require_reference,
        )
        _warn_if_phi_like(normalized)
        records.append(normalized)
        if max_records and len(records) >= max_records:
            break
    return records


def load_mimic_iv_note_dataset(
    path: str | Path,
    *,
    split: str = "test",
    reference_column: str | None = None,
    derive_bhc_reference: bool = True,
    require_reference: bool = True,
    max_records: int | None = None,
) -> list[dict[str, str]]:
    """Load MIMIC-IV-Note-style discharge summaries from CSV/CSV.GZ/JSONL.

    Expected columns are flexible. Common MIMIC-IV-Note fields such as
    `note_id`, `subject_id`, `hadm_id`, and `text` are mapped automatically.
    If `reference_column` is not supplied, the loader can derive a reference
    from the Brief Hospital Course section for evaluation experiments.
    """

    rows = _read_tabular(Path(path))
    records: list[dict[str, str]] = []
    for row in rows:
        mutable = dict(row)
        if reference_column and row.get(reference_column):
            mutable["reference_summary"] = row[reference_column]
        elif derive_bhc_reference and not _has_reference(mutable):
            reference = extract_brief_hospital_course(str(row.get("text") or ""))
            if reference:
                mutable["reference_summary"] = reference
        normalized = normalize_to_internal_schema(
            mutable,
            dataset="mimic_iv_note",
            split=str(row.get("split") or split),
            require_reference=require_reference,
        )
        _warn_if_phi_like(normalized)
        records.append(normalized)
        if max_records and len(records) >= max_records:
            break
    return records


def load_bhc_dataset(
    path: str | Path,
    *,
    split: str = "test",
    source_column: str | None = None,
    reference_column: str | None = None,
    require_reference: bool = True,
    max_records: int | None = None,
) -> list[dict[str, str]]:
    """Load MIMIC-IV-Ext-BHC-style hospital course summarization rows."""

    rows = _read_tabular(Path(path))
    records: list[dict[str, str]] = []
    for row in rows:
        mutable = dict(row)
        if source_column and row.get(source_column):
            mutable["source_note"] = row[source_column]
        elif not _has_source(mutable):
            mutable["source_note"] = _first_existing(
                row,
                "discharge_summary",
                "full_discharge_summary",
                "source",
                "input",
                "inputs",
                "text",
            )
        if reference_column and row.get(reference_column):
            mutable["reference_summary"] = row[reference_column]
        elif not _has_reference(mutable):
            mutable["reference_summary"] = _first_existing(
                row,
                "brief_hospital_course",
                "bhc",
                "target",
                "summary",
                "reference",
            )
        normalized = normalize_to_internal_schema(
            mutable,
            dataset="mimic_iv_ext_bhc",
            split=str(row.get("split") or split),
            require_reference=require_reference,
        )
        _warn_if_phi_like(normalized)
        records.append(normalized)
        if max_records and len(records) >= max_records:
            break
    return records


def create_small_demo_subset(
    records: Iterable[dict[str, str]],
    *,
    max_records: int = 10,
    split_by: str = "patient_id",
) -> list[dict[str, str]]:
    """Create a deterministic tiny subset for smoke tests or demos."""

    subset = list(records)[:max_records]
    return split_records(subset, split_by=split_by) if subset else []


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetValidationError(
                    f"Invalid JSONL at {path}:{line_number}."
                ) from exc


def _read_tabular(path: Path) -> list[dict[str, Any]]:
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".jsonl"):
        return list(_read_jsonl(path))
    if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
        opener = gzip.open if suffixes.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    raise DatasetValidationError(
        f"Unsupported dataset file extension for '{path}'. Use .jsonl, .csv, or .csv.gz."
    )


def _warn_if_phi_like(record: dict[str, str]) -> None:
    warnings = deidentification_warnings(record["source_note"])
    if warnings:
        record["deidentification_warnings"] = ",".join(warnings)


def _has_source(row: dict[str, Any]) -> bool:
    return bool(_first_existing(row, "source_note", "source", "text", "inputs", "input"))


def _has_reference(row: dict[str, Any]) -> bool:
    return bool(
        _first_existing(
            row,
            "reference_summary",
            "target",
            "summary",
            "brief_hospital_course",
            "bhc",
            "output",
        )
    )


def _first_existing(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""
