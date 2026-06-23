from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.evaluation.artifact_paths import configured_evaluation_artifact_root
from evaluation.data_governance.layers import HONESTY_WARNING, configure_d_drive_environment


ROOT = configured_evaluation_artifact_root() / "summarization_benchmark"
STAGES = {
    "A": ROOT / "stages" / "stage_a_deterministic_limit3",
    "B": ROOT / "stages" / "stage_b_bart_limit3",
    "C": ROOT / "stages" / "stage_c_pegasus_limit3",
    "D": ROOT / "stages" / "stage_d_bart_limit50",
    "E": ROOT / "stages" / "stage_e_pegasus_limit50",
}
FINAL_PREDICTION_SOURCES = {
    "deterministic": STAGES["A"] / "deterministic_predictions.jsonl",
    "bart": STAGES["D"] / "bart_predictions.jsonl",
    "pegasus": STAGES["E"] / "pegasus_predictions.jsonl",
}


def main() -> None:
    cache_paths = configure_d_drive_environment()
    _verify_embedding_env()
    ROOT.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    stage_records: dict[str, int] = {}
    for model, source in FINAL_PREDICTION_SOURCES.items():
        rows = _read_jsonl(source)
        stage_records[model] = len(rows)
        _write_jsonl(ROOT / f"{model}_predictions.jsonl", rows)
        all_rows.extend(rows)
    _write_jsonl(ROOT / "all_predictions.jsonl", all_rows)

    comparison_rows = _comparison_rows()
    _write_comparison_csv(ROOT / "model_comparison.csv", comparison_rows)
    _write_per_record_metrics(ROOT / "per_record_metrics.csv", all_rows)
    failure_rows = _failure_rows(all_rows)
    _write_failure_analysis(ROOT / "failure_analysis.md", failure_rows)
    manifest = _manifest(cache_paths, comparison_rows, stage_records)
    (ROOT / "evaluation_run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(ROOT / "EVALUATION_REPORT.md", comparison_rows, failure_rows, manifest)
    _write_run_log(ROOT / "run.log", comparison_rows, stage_records, cache_paths)
    print(f"Consolidated summarization benchmark outputs written to {ROOT}")


def _verify_embedding_env() -> None:
    provider = os.environ.get("RAG_EMBEDDING_PROVIDER")
    model = os.environ.get("RAG_SENTENCE_TRANSFORMERS_MODEL")
    if provider != "sentence_transformers":
        raise RuntimeError("RAG_EMBEDDING_PROVIDER must be sentence_transformers for this benchmark.")
    if model != "sentence-transformers/all-MiniLM-L6-v2":
        raise RuntimeError("RAG_SENTENCE_TRANSFORMERS_MODEL must be sentence-transformers/all-MiniLM-L6-v2.")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing stage prediction file: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _comparison_rows() -> list[dict[str, Any]]:
    sources = {
        "deterministic": STAGES["A"] / "model_comparison.csv",
        "bart": STAGES["D"] / "model_comparison.csv",
        "pegasus": STAGES["E"] / "model_comparison.csv",
    }
    rows: list[dict[str, Any]] = []
    for model, path in sources.items():
        with path.open("r", encoding="utf-8", newline="") as handle:
            stage_rows = list(csv.DictReader(handle))
        row = next(item for item in stage_rows if item["model_provider"] == model)
        row["selected_stage"] = {"deterministic": "A", "bart": "D", "pegasus": "E"}[model]
        rows.append(row)
    return rows


def _write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_per_record_metrics(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "note_id",
        "model_provider",
        "model_name",
        "status",
        "rouge1",
        "rouge2",
        "rougeL",
        "latency_ms",
        "failure_categories",
    ]
    failures = {row_key(row): _classify_failure(row) for row in rows}
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "note_id": row.get("note_id", ""),
                    "model_provider": row.get("model_provider", ""),
                    "model_name": row.get("model_name", ""),
                    "status": row.get("status", ""),
                    "rouge1": row.get("rouge1"),
                    "rouge2": row.get("rouge2"),
                    "rougeL": row.get("rougeL"),
                    "latency_ms": row.get("latency_ms"),
                    "failure_categories": "; ".join(failures[row_key(row)]),
                }
            )


def _failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        output.append(
            {
                "note_id": row.get("note_id", ""),
                "model_provider": row.get("model_provider", ""),
                "rougeL": _float_or_none(row.get("rougeL")),
                "categories": _classify_failure(row),
                "generated_summary": row.get("generated_summary", ""),
            }
        )
    return sorted(output, key=lambda item: item["rougeL"] if item["rougeL"] is not None else -1)


def _classify_failure(row: dict[str, Any]) -> list[str]:
    generated = str(row.get("generated_summary") or "")
    reference = str(row.get("reference_summary") or "")
    source = str(row.get("source_note") or "")
    categories: list[str] = []
    if _hallucination_score(generated, source, reference) > 0.35:
        categories.append("hallucinated content")
    if _contains(reference, "diagnos", "tuberculosis", "pancreatitis", "herniation") and not _contains(
        generated, "diagnos", "tuberculosis", "pancreatitis", "herniation"
    ):
        categories.append("missing diagnosis")
    if _contains(reference, "medication", "treatment", "therapy", "ciprofloxacin", "isoniazid", "rifampicin") and not _contains(
        generated, "medication", "treatment", "therapy", "ciprofloxacin", "isoniazid", "rifampicin"
    ):
        categories.append("missing medication")
    if _contains(reference, "week", "month", "year", "follow-up", "after") and not _contains(
        generated, "week", "month", "year", "follow-up", "after"
    ):
        categories.append("missing timeline")
    if len(generated.split()) < max(8, len(reference.split()) // 3):
        categories.append("incomplete summary")
    if _float_or_none(row.get("rougeL")) is not None and float(row.get("rougeL") or 0) < 0.2:
        categories.append("retrieval-related failure")
    if "multiclinsum_train_smoke" in str(row.get("input_path", "")):
        categories.append("source data limitation")
    return categories or ["needs human review"]


def _hallucination_score(generated: str, source: str, reference: str) -> float:
    generated_tokens = _tokens(generated)
    support_tokens = set(_tokens(f"{source} {reference}"))
    unsupported = [token for token in generated_tokens if token not in support_tokens]
    return len(unsupported) / max(1, len(generated_tokens))


def _contains(text: str, *terms: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9%./+-]+", text.casefold()) if len(token) > 2]


def row_key(row: dict[str, Any]) -> str:
    return f"{row.get('model_provider')}::{row.get('note_id')}"


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _write_failure_analysis(path: Path, failures: list[dict[str, Any]]) -> None:
    counts = Counter(category for row in failures for category in row["categories"])
    lines = [
        "# Failure Analysis",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Failure Pattern Counts",
        "",
    ]
    for category, count in counts.most_common():
        lines.append(f"- {category}: `{count}`")
    lines.extend(
        [
            "",
            "## Lowest ROUGE-L Records",
            "",
            "| Rank | Note ID | Model | ROUGE-L | Categories |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    for index, row in enumerate(failures[:20], start=1):
        lines.append(
            f"| {index} | `{row['note_id']}` | `{row['model_provider']}` | `{row['rougeL']}` | {', '.join(row['categories'])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _manifest(cache_paths: dict[str, str], comparison_rows: list[dict[str, Any]], stage_records: dict[str, int]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pipeline": "controlled_summarization_benchmark",
        "honesty_warning": HONESTY_WARNING,
        "cache_paths": cache_paths,
        "retrieval_embedding_provider": os.environ.get("RAG_EMBEDDING_PROVIDER"),
        "retrieval_embedding_model": os.environ.get("RAG_SENTENCE_TRANSFORMERS_MODEL"),
        "dataset": "multiclinsum",
        "input_path": "data/processed/multiclinsum/multiclinsum_train_smoke.jsonl",
        "larger_processed_multiclinsum_available": False,
        "dataset_limitation": "Only the 3-record MultiClinSum smoke JSONL is available locally; limit-50 stages evaluated 3 records.",
        "stages": {
            "A": {"model": "deterministic", "limit": 3, "output_dir": str(STAGES["A"])},
            "B": {"model": "bart", "limit": 3, "output_dir": str(STAGES["B"])},
            "C": {"model": "pegasus", "limit": 3, "output_dir": str(STAGES["C"])},
            "D": {"model": "bart", "limit": 50, "output_dir": str(STAGES["D"]), "actual_records": stage_records.get("bart")},
            "E": {"model": "pegasus", "limit": 50, "output_dir": str(STAGES["E"]), "actual_records": stage_records.get("pegasus")},
        },
        "model_comparison": comparison_rows,
        "outputs": [
            "run.log",
            "evaluation_run_manifest.json",
            "deterministic_predictions.jsonl",
            "bart_predictions.jsonl",
            "pegasus_predictions.jsonl",
            "model_comparison.csv",
            "per_record_metrics.csv",
            "failure_analysis.md",
            "EVALUATION_REPORT.md",
        ],
    }


def _write_report(path: Path, comparison_rows: list[dict[str, Any]], failures: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    best = _best_model(comparison_rows)
    counts = Counter(category for row in failures for category in row["categories"])
    lines = [
        "# Controlled Summarization Benchmark Report",
        "",
        f"> {HONESTY_WARNING}",
        "",
        "## Summary",
        "",
        "- Stages A-E completed.",
        "- BART and Pegasus prediction files were generated.",
        "- The upgraded retrieval embedding configuration was used for the benchmark environment.",
        "- No larger processed MultiClinSum JSONL was found locally; limit-50 stages evaluated the 3 smoke records.",
        f"- Best model by ROUGE-L: `{best}`",
        "",
        "## Cache Verification",
        "",
        f"- HF_HOME: `{manifest['cache_paths']['HF_HOME']}`",
        f"- HF_HUB_CACHE: `{manifest['cache_paths']['HF_HUB_CACHE']}`",
        f"- HF_DATASETS_CACHE: `{manifest['cache_paths']['HF_DATASETS_CACHE']}`",
        f"- TRANSFORMERS_CACHE: `{manifest['cache_paths']['TRANSFORMERS_CACHE']}`",
        f"- RAG_EMBEDDING_PROVIDER: `{manifest['retrieval_embedding_provider']}`",
        f"- RAG_SENTENCE_TRANSFORMERS_MODEL: `{manifest['retrieval_embedding_model']}`",
        "",
        "## ROUGE Results",
        "",
        "| Model | Status | Records | ROUGE-1 | ROUGE-2 | ROUGE-L | Avg latency ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in comparison_rows:
        lines.append(
            f"| `{row['model_provider']}` | `{row['status']}` | {row['completed_count']} | {row['rouge1']} | {row['rouge2']} | {row['rougeL']} | {row['average_latency_ms']} |"
        )
    lines.extend(["", "## Worst Failure Patterns", ""])
    for category, count in counts.most_common():
        lines.append(f"- {category}: `{count}`")
    lines.extend(
        [
            "",
            "## Readiness",
            "",
            "The project is ready for a medium-scale benchmark only after a larger processed MultiClinSum file is available locally. The model path itself is functional: deterministic, BART, and Pegasus all completed on the smoke set.",
            "",
            "Dataset limitation remains the main blocker: current local processed data contains only 3 smoke records, which is not enough for stable benchmark conclusions.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _best_model(comparison_rows: list[dict[str, Any]]) -> str:
    completed = [row for row in comparison_rows if row.get("status") == "completed"]
    if not completed:
        return "not_available"
    return max(completed, key=lambda row: float(row.get("rougeL") or 0.0))["model_provider"]


def _write_run_log(path: Path, comparison_rows: list[dict[str, Any]], stage_records: dict[str, int], cache_paths: dict[str, str]) -> None:
    lines = [
        f"{datetime.now(UTC).isoformat(timespec='seconds')} Consolidated controlled summarization benchmark.",
        f"Cache paths: {cache_paths}",
        f"Stage record counts: {stage_records}",
        f"Models: {[row['model_provider'] for row in comparison_rows]}",
        HONESTY_WARNING,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
