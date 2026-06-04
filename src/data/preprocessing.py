from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


INTERNAL_SCHEMA_FIELDS = (
    "note_id",
    "patient_id",
    "encounter_id",
    "source_note",
    "reference_summary",
    "dataset",
    "split",
)
SUPPORTED_DATASETS = {
    "mock",
    "multiclinsum",
    "mts_dialog",
    "mediqa_sum",
    "aci_bench",
    "mtsamples_clean",
    "mimic_iv_note",
    "mimic_iv_ext_bhc",
}
SUPPORTED_SPLITS = {"train", "validation", "test", "test_1", "test_2"}


class DatasetValidationError(ValueError):
    """Raised when a dataset row cannot be used for summarization evaluation."""


def normalize_to_internal_schema(
    row: Mapping[str, Any],
    *,
    dataset: str = "mock",
    split: str = "test",
    require_reference: bool = True,
) -> dict[str, str]:
    """Normalize common EHR summarization row shapes into the MVP schema."""

    dataset = _clean_dataset(dataset or str(row.get("dataset") or "mock"))
    split = _clean_split(split or str(row.get("split") or "test"))
    source_note = _first_text(
        row,
        "source_note",
        "source",
        "text",
        "note_text",
        "discharge_summary",
        "inputs",
        "input",
    )
    reference_summary = _first_text(
        row,
        "reference_summary",
        "target",
        "summary",
        "brief_hospital_course",
        "bhc",
        "output",
    )
    normalized = {
        "note_id": _first_identifier(row, "note_id", "id", "idx", default_prefix="note"),
        "patient_id": _first_identifier(row, "patient_id", "subject_id", default_prefix="patient"),
        "encounter_id": _first_identifier(row, "encounter_id", "hadm_id", "visit_id", default_prefix="enc"),
        "source_note": source_note,
        "reference_summary": reference_summary,
        "dataset": dataset,
        "split": split,
    }
    validate_no_empty_source_or_target(normalized, require_reference=require_reference)
    return normalized


def validate_no_empty_source_or_target(
    record: Mapping[str, Any],
    *,
    require_reference: bool = True,
) -> None:
    if not str(record.get("source_note") or "").strip():
        raise DatasetValidationError("Dataset row has an empty source_note.")
    if require_reference and not str(record.get("reference_summary") or "").strip():
        raise DatasetValidationError(
            "Dataset row is missing reference_summary required for training/evaluation."
        )


def deidentification_warnings(text: str) -> list[str]:
    """Return conservative warnings for obvious PHI-like patterns.

    MIMIC data is credentialed and de-identified, but local custom datasets still
    need a quick tripwire before entering model/evaluation flows.
    """

    warnings: list[str] = []
    checks = {
        "possible_email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "possible_phone": r"\b(?:\+?\d[\s.-]?){9,}\b",
        "possible_ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "possible_mrn_label": r"\b(?:MRN|Medical Record Number)\s*[:#]?\s*\d{4,}\b",
    }
    for label, pattern in checks.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            warnings.append(label)
    if re.search(r"\b[A-Z][a-z]+,\s+[A-Z][a-z]+\b", text):
        warnings.append("possible_person_name")
    return warnings


def extract_brief_hospital_course(note_text: str) -> str | None:
    """Best-effort section extraction for MIMIC-IV-Note discharge summaries."""

    pattern = re.compile(
        r"(?:brief hospital course|hospital course)\s*:?\s*(.*?)(?=\n\s*[A-Z][A-Za-z /_-]{2,40}\s*:|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(note_text)
    if not match:
        return None
    return _compact_text(match.group(1))


def _clean_dataset(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "mimicivnote": "mimic_iv_note",
        "mimic_iv_notes": "mimic_iv_note",
        "mimic_iv_ext_bhc": "mimic_iv_ext_bhc",
        "mimicivextbhc": "mimic_iv_ext_bhc",
        "multi_clin_sum": "multiclinsum",
        "multi_clinsum": "multiclinsum",
        "multi_clinical_summarization": "multiclinsum",
        "mtsdialog": "mts_dialog",
        "mts_dialogue": "mts_dialog",
        "mediqasum": "mediqa_sum",
        "mediqa_sum": "mediqa_sum",
        "mediqa-sum": "mediqa_sum",
        "aci": "aci_bench",
        "acibench": "aci_bench",
        "aci-bench": "aci_bench",
        "biomednlp_mtsamples_clean": "mtsamples_clean",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_DATASETS:
        raise DatasetValidationError(f"Unsupported dataset '{value}'.")
    return normalized


def _clean_split(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {"val": "validation", "valid": "validation", "dev": "validation"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in SUPPORTED_SPLITS:
        raise DatasetValidationError(f"Unsupported split '{value}'.")
    return normalized


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return _compact_text(str(value))
    return ""


def _first_identifier(
    row: Mapping[str, Any],
    *keys: str,
    default_prefix: str,
) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return _safe_identifier(str(value))
    return f"{default_prefix}_unknown"


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
