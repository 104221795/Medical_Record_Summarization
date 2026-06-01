from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics
from src.data.dataset_loader import load_jsonl_dataset
from src.models import BartSummarizer, BaseSummarizer, DeterministicSummarizer, PegasusSummarizer


DEFAULT_OUTPUT_DIR = Path("outputs/evaluation")


class BaselineRunnerError(ValueError):
    pass


def run_baseline_evaluation(
    *,
    dataset: str,
    input_path: str | Path,
    model: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
    dry_run: bool = False,
    allow_model_downloads: bool = False,
    include_bertscore: bool = False,
    device: int = -1,
    bart_model_name: str = "facebook/bart-large-cnn",
    pegasus_model_name: str = "google/pegasus-xsum",
) -> dict[str, Any]:
    dataset = _normalize_dataset(dataset)
    records = _load_records(input_path, dataset=dataset, limit=limit)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if dry_run:
        result = _dry_run_result(dataset, input_path, model, records)
        _write_json(output_path / f"{dataset}_{model}_readiness.json", result)
        _write_markdown_summary(output_path / f"{dataset}_{model}_summary.md", result)
        return result

    provider = _build_provider(
        model=model,
        allow_model_downloads=allow_model_downloads,
        device=device,
        bart_model_name=bart_model_name,
        pegasus_model_name=pegasus_model_name,
    )
    rows = []
    predictions: list[str] = []
    references: list[str] = []
    latencies: list[int] = []
    failures = 0
    evaluation_layer = _evaluation_layer(dataset)
    for record in records:
        try:
            output = provider.generate(record)
            predictions.append(output.generated_summary)
            references.append(output.reference_summary)
            latencies.append(output.latency_ms)
            rows.append(
                {
                    **record,
                    "model_provider": provider.provider_name,
                    "model_name": provider.model_name,
                    "generated_summary": output.generated_summary,
                    "latency_ms": output.latency_ms,
                    "status": "completed",
                    "error_message": None,
                    "proxy_evaluation": True,
                    "evaluation_layer": evaluation_layer,
                }
            )
        except Exception as exc:
            failures += 1
            rows.append(
                {
                    **record,
                    "model_provider": model,
                    "model_name": model,
                    "generated_summary": "",
                    "latency_ms": None,
                    "status": "failed",
                    "error_message": str(exc),
                    "proxy_evaluation": True,
                    "evaluation_layer": evaluation_layer,
                }
            )

    metrics = compute_pairwise_metrics(predictions, references, include_bertscore=include_bertscore)
    metrics.update(
        {
            "dataset": dataset,
            "input_path": str(input_path),
            "model_provider": provider.provider_name,
            "model_name": provider.model_name,
            "evaluation_layer": evaluation_layer,
            "status": "completed" if predictions and failures == 0 else "partial" if predictions else "failed",
            "success_count": len(predictions),
            "failure_count": failures,
            "success_rate": round(len(predictions) / len(records), 4) if records else 0.0,
            "average_latency_ms": _mean(latencies),
            "average_input_length": _mean([len(str(record.get("source_note", "")).split()) for record in records]),
            "average_output_length": _mean([len(text.split()) for text in predictions]),
            "proxy_warning": _PROXY_WARNING,
        }
    )

    prefix = output_path / f"{dataset}_{model}"
    _write_jsonl(prefix.with_name(f"{prefix.name}_predictions.jsonl"), rows)
    _write_json(prefix.with_name(f"{prefix.name}_metrics.json"), metrics)
    _write_metrics_csv(prefix.with_name(f"{prefix.name}_metrics.csv"), metrics)
    _write_markdown_summary(prefix.with_name(f"{prefix.name}_summary.md"), metrics)
    return metrics


def _load_records(input_path: str | Path, *, dataset: str, limit: int | None) -> list[dict[str, str]]:
    path = Path(input_path)
    if not path.exists():
        raise BaselineRunnerError(f"Evaluation input file does not exist: {path}")
    records = load_jsonl_dataset(
        path,
        dataset=dataset,
        split="test",
        require_reference=True,
        max_records=limit,
    )
    if not records:
        raise BaselineRunnerError("Evaluation input contains no usable records.")
    return records


def _build_provider(
    *,
    model: str,
    allow_model_downloads: bool,
    device: int,
    bart_model_name: str,
    pegasus_model_name: str,
) -> BaseSummarizer:
    if model == "deterministic":
        return DeterministicSummarizer(max_sentences=3)
    real_enabled = allow_model_downloads or os.environ.get("RUN_REAL_BASELINES") == "1"
    if model == "bart":
        if not real_enabled:
            raise BaselineRunnerError(
                "BART execution is disabled by default. Pass --allow-model-downloads "
                "or set RUN_REAL_BASELINES=1 to load Hugging Face models."
            )
        return BartSummarizer(model_name=bart_model_name, device=device)
    if model == "pegasus":
        if not real_enabled:
            raise BaselineRunnerError(
                "Pegasus execution is disabled by default. Pass --allow-model-downloads "
                "or set RUN_REAL_BASELINES=1 to load Hugging Face models."
            )
        return PegasusSummarizer(model_name=pegasus_model_name, device=device)
    raise BaselineRunnerError(f"Unsupported model '{model}'. Use deterministic, bart, or pegasus.")


def _dry_run_result(
    dataset: str,
    input_path: str | Path,
    model: str,
    records: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "status": "ready",
        "dry_run": True,
        "dataset": dataset,
        "input_path": str(input_path),
        "model_provider": model,
        "evaluation_layer": _evaluation_layer(dataset),
        "record_count": len(records),
        "first_note_id": records[0].get("note_id", "") if records else "",
        "has_source_note": all(bool(record.get("source_note")) for record in records),
        "has_reference_summary": all(bool(record.get("reference_summary")) for record in records),
        "average_input_length": _mean([len(str(record.get("source_note", "")).split()) for record in records]),
        "average_reference_length": _mean([len(str(record.get("reference_summary", "")).split()) for record in records]),
        "average_output_length": 0.0,
        "average_latency_ms": 0.0,
        "proxy_warning": _PROXY_WARNING,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_metrics_csv(path: Path, metrics: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)


def _write_markdown_summary(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Baseline Evaluation Smoke Summary",
        "",
        f"> {_PROXY_WARNING}",
        "",
        f"- Status: `{result.get('status')}`",
        f"- Dataset: `{result.get('dataset')}`",
        f"- Evaluation layer: `{result.get('evaluation_layer')}`",
        f"- Input: `{result.get('input_path')}`",
        f"- Provider: `{result.get('model_provider')}`",
        f"- Records: `{result.get('record_count', result.get('success_count', 0))}`",
        f"- ROUGE-1: `{_display(result.get('rouge1'))}`",
        f"- ROUGE-2: `{_display(result.get('rouge2'))}`",
        f"- ROUGE-L: `{_display(result.get('rougeL'))}`",
        f"- BERTScore precision: `{_display(result.get('bertscore_precision'))}`",
        f"- BERTScore recall: `{_display(result.get('bertscore_recall'))}`",
        f"- BERTScore F1: `{_display(result.get('bertscore_f1'))}`",
        f"- BERTScore status: `{_display(result.get('bertscore_status'))}`",
        f"- Average latency ms: `{_display(result.get('average_latency_ms'))}`",
        f"- Average input length: `{_display(result.get('average_input_length'))}`",
        f"- Average output length: `{_display(result.get('average_output_length'))}`",
        "",
        "Real EHR benchmark metrics remain pending until credentialed, governed EHR data is available.",
    ]
    if result.get("bertscore_message"):
        lines.insert(-2, f"- BERTScore message: `{result.get('bertscore_message')}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def _display(value: Any) -> str:
    return "not_available" if value is None or value == "" else str(value)


def _normalize_dataset(dataset: str) -> str:
    normalized = dataset.strip().lower().replace("-", "_")
    aliases = {
        "multi_clinsum": "multiclinsum",
        "multi_clin_sum": "multiclinsum",
        "mtsdialog": "mts_dialog",
        "mts_dialogue": "mts_dialog",
        "acibench": "aci_bench",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in _EVALUATION_LAYER_BY_DATASET:
        supported = ", ".join(sorted(_EVALUATION_LAYER_BY_DATASET))
        raise BaselineRunnerError(f"Unsupported dataset '{dataset}'. Supported values: {supported}.")
    return normalized


def _evaluation_layer(dataset: str) -> str:
    return _EVALUATION_LAYER_BY_DATASET[_normalize_dataset(dataset)]


def _mean(values: list[int | float]) -> float:
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 4)


def main() -> None:
    args = _parse_args()
    result = run_baseline_evaluation(
        dataset=args.dataset,
        input_path=args.input,
        model=args.model,
        output_dir=args.output_dir,
        limit=args.limit,
        dry_run=args.dry_run,
        allow_model_downloads=args.allow_model_downloads,
        include_bertscore=args.include_bertscore,
        device=args.device,
        bart_model_name=args.bart_model,
        pegasus_model_name=args.pegasus_model,
    )
    print(_PROXY_WARNING)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Layer C baseline evaluation smoke tests.")
    parser.add_argument("--dataset", choices=sorted(_EVALUATION_LAYER_BY_DATASET), default="multiclinsum")
    parser.add_argument("--input", required=True)
    parser.add_argument("--model", choices=["deterministic", "bart", "pegasus"], default="deterministic")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-model-downloads", action="store_true")
    parser.add_argument("--include-bertscore", action="store_true")
    parser.add_argument("--device", type=int, default=-1)
    parser.add_argument("--bart-model", default=os.environ.get("BART_MODEL_NAME", "facebook/bart-large-cnn"))
    parser.add_argument("--pegasus-model", default=os.environ.get("PEGASUS_MODEL_NAME", "google/pegasus-xsum"))
    return parser.parse_args()


_PROXY_WARNING = (
    "Proxy evaluation only: use de-identified/demo/open benchmark data. "
    "Do not claim real EHR benchmark or clinical performance from these outputs."
)

_EVALUATION_LAYER_BY_DATASET = {
    "multiclinsum": "Layer C.1 - Primary Open Clinical Summarization Benchmark",
    "mts_dialog": "Layer C.2 - Auxiliary Dialogue-to-Note Proxy Evaluation",
    "aci_bench": "Layer C.3 - Optional Full-Visit Dialogue-to-Note Proxy Evaluation",
}


if __name__ == "__main__":
    main()
