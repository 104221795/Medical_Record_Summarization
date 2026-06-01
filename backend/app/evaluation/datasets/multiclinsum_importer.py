from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any


DEFAULT_ZIP_DIR = Path("data/external/multiclinsum")
KNOWN_ZIP_FILENAMES = (
    "multiclinsum_large_scale_train.zip",
    "multiclinsum_large-scale_train_en.zip",
)
DEFAULT_ZIP_PATH = DEFAULT_ZIP_DIR / KNOWN_ZIP_FILENAMES[0]
DEFAULT_OUTPUT_PATH = Path("data/processed/multiclinsum/multiclinsum_train.jsonl")


class MultiClinSumImportError(ValueError):
    pass


def import_multiclinsum_dataset(
    *,
    zip_path: str | Path | None = None,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    limit: int | None = 500,
) -> list[dict[str, Any]]:
    archive = resolve_multiclinsum_zip_path(zip_path)

    rows = _read_supported_rows_from_zip(archive)
    normalized: list[dict[str, Any]] = []
    inspected_files = sorted({row["_source_file"] for row in rows})

    for index, row in enumerate(rows, start=1):
        source_text = _first_text(row, *_SOURCE_FIELDS)
        reference = _first_text(row, *_REFERENCE_FIELDS)
        if not source_text or not reference:
            continue
        normalized.append(
            {
                "note_id": _first_text(row, *_ID_FIELDS) or f"multiclinsum_{index:06d}",
                "patient_id": f"multiclinsum_patient_{index:06d}",
                "encounter_id": f"multiclinsum_encounter_{index:06d}",
                "source_note": source_text,
                "reference_summary": reference,
                "dataset": "multiclinsum",
                "split": str(row.get("split") or "train"),
                "source_dataset": "MultiClinSum",
                "validation_layer": "Layer C.1 - Primary Open Clinical Summarization Benchmark",
                "metadata": {
                    "source_file": row["_source_file"],
                    "original_id": _first_text(row, *_ID_FIELDS),
                    "language": _first_text(row, "language", "lang"),
                },
            }
        )
        if limit and len(normalized) >= limit:
            break

    if not normalized:
        raise MultiClinSumImportError(
            "Could not find source/reference summary pairs in MultiClinSum archive. "
            f"Inspected files: {', '.join(inspected_files) or 'none'}. "
            "Expected source fields like input_document/document/source_text and "
            "reference fields like reference_summary/summary/target."
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output, normalized)
    return normalized


def resolve_multiclinsum_zip_path(zip_path: str | Path | None = None) -> Path:
    if zip_path is not None:
        archive = Path(zip_path)
        if archive.exists():
            return archive
        raise MultiClinSumImportError(
            "MultiClinSum zip not found at "
            f"{archive}. Place one of {', '.join(KNOWN_ZIP_FILENAMES)} under "
            f"{DEFAULT_ZIP_DIR.as_posix()}/ or pass --zip with the exact file path."
        )

    if not DEFAULT_ZIP_DIR.exists():
        raise MultiClinSumImportError(
            f"MultiClinSum directory does not exist: {DEFAULT_ZIP_DIR.as_posix()}. "
            f"Create it and place one of {', '.join(KNOWN_ZIP_FILENAMES)} there, "
            "or pass --zip with the exact file path."
        )

    detected_zips = sorted(DEFAULT_ZIP_DIR.glob("*.zip"))
    known_zips = [DEFAULT_ZIP_DIR / filename for filename in KNOWN_ZIP_FILENAMES if (DEFAULT_ZIP_DIR / filename).exists()]
    if len(detected_zips) == 1:
        return detected_zips[0]
    if not detected_zips:
        raise MultiClinSumImportError(
            f"No MultiClinSum zip found under {DEFAULT_ZIP_DIR.as_posix()}. "
            f"Expected one of: {', '.join(KNOWN_ZIP_FILENAMES)}."
        )
    if len(known_zips) == 1 and len(detected_zips) == 1:
        return known_zips[0]
    raise MultiClinSumImportError(
        "Multiple MultiClinSum zip files were detected. Pass --zip with the exact file to import. "
        f"Detected: {', '.join(path.name for path in detected_zips)}"
    )


def _read_supported_rows_from_zip(archive: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(archive) as zipped:
        txt_pairs = _read_txt_pairs_from_zip(zipped)
        if txt_pairs:
            return txt_pairs
        rows: list[dict[str, Any]] = []
        members = [
            member
            for member in zipped.namelist()
            if not member.endswith("/")
            and Path(member).suffix.lower() in {".jsonl", ".json", ".csv", ".tsv"}
        ]
        for member in members:
            with zipped.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace").read()
            rows.extend(_read_member_rows(member, text))
    return rows


def _read_txt_pairs_from_zip(zipped: zipfile.ZipFile) -> list[dict[str, Any]]:
    members = [
        member
        for member in zipped.namelist()
        if not member.endswith("/") and Path(member).suffix.lower() == ".txt"
    ]
    fulltext_by_stem = {
        _pair_stem(member): member
        for member in members
        if "/fulltext/" in member.replace("\\", "/").lower()
    }
    summary_by_stem = {
        _pair_stem(member): member
        for member in members
        if "/summaries/" in member.replace("\\", "/").lower()
    }
    shared_stems = sorted(set(fulltext_by_stem) & set(summary_by_stem))
    rows: list[dict[str, Any]] = []
    for stem in shared_stems:
        with zipped.open(fulltext_by_stem[stem]) as raw:
            source_text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace").read().strip()
        with zipped.open(summary_by_stem[stem]) as raw:
            reference = io.TextIOWrapper(raw, encoding="utf-8", errors="replace").read().strip()
        rows.append(
            {
                "case_id": stem,
                "input_document": source_text,
                "summary": reference,
                "_source_file": fulltext_by_stem[stem],
            }
        )
    return rows


def _pair_stem(member: str) -> str:
    stem = Path(member).stem
    return stem.removesuffix("_sum").removesuffix("_summary")


def _read_member_rows(member: str, text: str) -> list[dict[str, Any]]:
    suffix = Path(member).suffix.lower()
    if suffix == ".jsonl":
        return [_with_source_file(row, member) for row in _read_jsonl(text)]
    if suffix == ".json":
        return [_with_source_file(row, member) for row in _read_json_payload(text)]
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        return [_with_source_file(dict(row), member) for row in reader]
    return []


def _read_jsonl(text: str) -> Iterable[dict[str, Any]]:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MultiClinSumImportError(f"Invalid JSONL row at line {line_number}.") from exc
        if isinstance(payload, dict):
            yield payload


def _read_json_payload(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MultiClinSumImportError("Invalid JSON file inside MultiClinSum archive.") from exc
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records", "examples", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _with_source_file(row: dict[str, Any], member: str) -> dict[str, Any]:
    row["_source_file"] = member
    return row


def _first_text(row: dict[str, Any], *keys: str) -> str:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = row.get(key)
        if value is None:
            value = lowered.get(key.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


_ID_FIELDS = (
    "note_id",
    "case_id",
    "id",
    "article_id",
    "sample_id",
    "document_id",
)
_SOURCE_FIELDS = (
    "source_note",
    "input_document",
    "document",
    "source",
    "source_text",
    "article",
    "text",
    "case_report",
    "clinical_document",
    "inputs",
    "input",
)
_REFERENCE_FIELDS = (
    "reference_summary",
    "summary",
    "target",
    "abstract",
    "output",
    "reference",
    "gold_summary",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MultiClinSum into the internal evaluation JSONL schema.")
    parser.add_argument("--zip", dest="zip_path", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    rows = import_multiclinsum_dataset(
        zip_path=args.zip_path,
        output_path=args.output,
        limit=args.limit,
    )
    print(f"Wrote {len(rows)} MultiClinSum rows to {args.output}")


if __name__ == "__main__":
    main()
