from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from ...config import Settings
from ...services.document_difficulty import detect_document_difficulty
from ...services.generators import GeminiJsonClient
from ...services.input_normalization import normalize_clinical_document


class DatasetImportError(ValueError):
    pass


def import_mtsamples_clean(
    *,
    split: str = "train",
    limit: int = 500,
    output_path: str | Path = "data/processed/mtsamples_clean/mtsamples_clean_train.jsonl",
    loader: Callable[[str], Iterable[dict[str, Any]]] | None = None,
    allow_llm_normalization: bool = False,
    max_llm_cases: int = 5,
    settings: Settings | None = None,
    gemini_client: GeminiJsonClient | None = None,
) -> list[dict[str, Any]]:
    rows = list(_load_rows(split, loader=loader))
    output_rows: list[dict[str, Any]] = []
    llm_attempt_count = 0
    max_llm_cases = max(0, max_llm_cases)
    for index, row in enumerate(rows[:limit], start=1):
        raw_text = _first_text(row, "transcription", "text", "raw_text", "source_note")
        if not raw_text:
            continue
        difficulty = detect_document_difficulty(raw_text)
        llm_allowed_for_row = (
            allow_llm_normalization
            and difficulty.should_use_llm_normalization
            and llm_attempt_count < max_llm_cases
        )
        cap_warning = None
        if allow_llm_normalization and difficulty.should_use_llm_normalization and not llm_allowed_for_row:
            cap_warning = "llm_normalization_skipped: max_llm_cases reached"
        normalization = normalize_clinical_document(
            raw_text,
            document_type=str(row.get("sample_name") or row.get("document_type") or "medical_transcription"),
            language="en",
            settings=settings,
            gemini_client=gemini_client,
            allow_llm=llm_allowed_for_row,
        )
        if llm_allowed_for_row:
            llm_attempt_count += 1
        warnings = list(normalization.warnings)
        if cap_warning:
            warnings.append(cap_warning)
        llm_failed = _first_warning(warnings, "llm_normalization_failed")
        needs_review_count = sum(1 for section in normalization.sections if section.needs_review)
        output_rows.append(
            {
                "record_id": str(row.get("id") or row.get("idx") or f"mtsamples_{index:05d}"),
                "source_dataset": "BIOMEDNLP/mtsamples_clean",
                "validation_layer": "Normalization stress test",
                "document_type": str(row.get("sample_name") or "medical_transcription"),
                "specialty": str(row.get("medical_specialty") or row.get("category") or ""),
                "raw_text": raw_text,
                "proxy_patient_id": f"mtsamples_patient_{index:05d}",
                "proxy_encounter_id": f"mtsamples_encounter_{index:05d}",
                "normalization": normalization.to_json_dict(),
                "normalization_method": normalization.normalization_method,
                "difficulty_score": normalization.difficulty.difficulty_score,
                "difficulty_reasons": normalization.difficulty.reasons,
                "needs_review_count": needs_review_count,
                "llm_attempted": llm_allowed_for_row,
                "llm_failed": llm_failed,
                "normalization_warnings": warnings,
                "benchmark_note": (
                    "Used for messy input normalization stress testing, not as the main "
                    "supervised summarization benchmark unless reliable references exist."
                ),
            }
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output, output_rows)
    return output_rows


def _load_rows(
    split: str,
    *,
    loader: Callable[[str], Iterable[dict[str, Any]]] | None,
) -> Iterable[dict[str, Any]]:
    if loader is not None:
        return loader(split)
    try:
        from datasets import load_dataset
    except Exception as exc:
        raise DatasetImportError(
            "Importing BIOMEDNLP/mtsamples_clean requires the optional 'datasets' package. "
            "Install it locally before running this importer."
        ) from exc
    dataset = load_dataset("BIOMEDNLP/mtsamples_clean", split=split)
    return (dict(row) for row in dataset)


def _first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_warning(warnings: list[str], prefix: str) -> str | None:
    for warning in warnings:
        if warning.startswith(prefix):
            return warning
    return None


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import BIOMEDNLP/mtsamples_clean for normalization stress tests.")
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", default="data/processed/mtsamples_clean/mtsamples_clean_train.jsonl")
    parser.add_argument("--allow-llm-normalization", action="store_true")
    parser.add_argument("--max-llm-cases", type=int, default=5)
    args = parser.parse_args()
    rows = import_mtsamples_clean(
        split=args.split,
        limit=args.limit,
        output_path=args.output,
        allow_llm_normalization=args.allow_llm_normalization,
        max_llm_cases=args.max_llm_cases,
    )
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
