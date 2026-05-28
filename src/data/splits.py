from __future__ import annotations

import hashlib
from collections.abc import Iterable


def assign_split(
    stable_id: str,
    *,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
) -> str:
    """Assign a deterministic split using a stable record or patient ID."""

    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1.")
    if not 0 <= validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1.")
    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be less than 1.")
    digest = hashlib.sha256(stable_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + validation_ratio:
        return "validation"
    return "test"


def split_records(
    records: Iterable[dict[str, str]],
    *,
    split_by: str = "patient_id",
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
) -> list[dict[str, str]]:
    """Return records with deterministic split assignments."""

    output: list[dict[str, str]] = []
    for record in records:
        stable_id = record.get(split_by) or record.get("note_id") or ""
        if not stable_id:
            raise ValueError(f"Record is missing split key '{split_by}'.")
        copy = dict(record)
        copy["split"] = assign_split(
            stable_id,
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
        )
        output.append(copy)
    return output
