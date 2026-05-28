from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from src.data.dataset_loader import load_jsonl_dataset
from src.models import (
    BartSummarizer,
    BaseSummarizer,
    DeterministicSummarizer,
    PegasusSummarizer,
)


def run_baseline(
    records: list[dict[str, str]],
    providers: Iterable[BaseSummarizer],
    *,
    output_dir: str | Path = "results",
    include_bertscore: bool = False,
) -> dict[str, list[dict]]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    provider_outputs: dict[str, list[dict]] = {}
    comparison_rows: list[dict[str, str | int | float | None]] = []

    for provider in providers:
        outputs = [provider.generate(record).to_json_dict() for record in records]
        provider_outputs[provider.provider_name] = outputs
        _write_jsonl(output_path / f"{provider.provider_name}_outputs.jsonl", outputs)
        comparison_rows.append(_comparison_row(provider.provider_name, outputs, include_bertscore))

    _write_comparison_csv(output_path / "model_comparison.csv", comparison_rows)
    return provider_outputs


def compute_rouge_scores(prediction: str, reference: str) -> dict[str, float]:
    pred_tokens = _tokens(prediction)
    ref_tokens = _tokens(reference)
    return {
        "rouge1": _rouge_n(pred_tokens, ref_tokens, 1),
        "rouge2": _rouge_n(pred_tokens, ref_tokens, 2),
        "rougeL": _rouge_l(pred_tokens, ref_tokens),
    }


def maybe_compute_bertscore(predictions: list[str], references: list[str]) -> float | None:
    if not predictions or not references:
        return None
    try:
        from bert_score import score
    except Exception:
        return None
    _precision, _recall, f1 = score(predictions, references, lang="en", verbose=False)
    return float(f1.mean().item())


def build_providers(args: argparse.Namespace) -> list[BaseSummarizer]:
    requested = ["bart", "pegasus"] if args.provider == "all" else [args.provider]
    providers: list[BaseSummarizer] = []
    real_enabled = args.allow_model_downloads or os.environ.get("RUN_REAL_BASELINES") == "1"
    for provider in requested:
        if provider == "deterministic":
            providers.append(DeterministicSummarizer())
        elif provider == "bart":
            if not real_enabled:
                raise RuntimeError(
                    "BART execution is disabled by default. Pass --allow-model-downloads "
                    "or set RUN_REAL_BASELINES=1 to load Hugging Face models."
                )
            providers.append(BartSummarizer(model_name=args.bart_model, device=args.device))
        elif provider == "pegasus":
            if not real_enabled:
                raise RuntimeError(
                    "Pegasus execution is disabled by default. Pass --allow-model-downloads "
                    "or set RUN_REAL_BASELINES=1 to load Hugging Face models."
                )
            providers.append(PegasusSummarizer(model_name=args.pegasus_model, device=args.device))
        else:
            raise ValueError(f"Unsupported provider '{provider}'.")
    return providers


def main() -> None:
    args = _parse_args()
    records = load_jsonl_dataset(
        args.dataset_path,
        dataset="mock",
        split="test",
        require_reference=True,
        max_records=args.max_records,
    )
    providers = build_providers(args)
    run_baseline(
        records,
        providers,
        output_dir=args.output_dir,
        include_bertscore=args.include_bertscore,
    )
    print(f"Baseline outputs written to {args.output_dir}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run baseline summarization providers.")
    parser.add_argument("--dataset-path", default="data/evaluation/sample_ehr_notes.jsonl")
    parser.add_argument("--provider", choices=["deterministic", "bart", "pegasus", "all"], default="deterministic")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--bart-model", default="facebook/bart-large-cnn")
    parser.add_argument("--pegasus-model", default="google/pegasus-xsum")
    parser.add_argument("--device", type=int, default=-1)
    parser.add_argument("--allow-model-downloads", action="store_true")
    parser.add_argument("--include-bertscore", action="store_true")
    return parser.parse_args()


def _comparison_row(
    provider_name: str,
    outputs: list[dict],
    include_bertscore: bool,
) -> dict[str, str | int | float | None]:
    rouge_values = [
        compute_rouge_scores(item["generated_summary"], item["reference_summary"])
        for item in outputs
    ]
    predictions = [item["generated_summary"] for item in outputs]
    references = [item["reference_summary"] for item in outputs]
    return {
        "model_provider": provider_name,
        "record_count": len(outputs),
        "rouge1": _mean([item["rouge1"] for item in rouge_values]),
        "rouge2": _mean([item["rouge2"] for item in rouge_values]),
        "rougeL": _mean([item["rougeL"] for item in rouge_values]),
        "bertscore_f1": maybe_compute_bertscore(predictions, references) if include_bertscore else None,
        "average_latency_ms": _mean([item["latency_ms"] for item in outputs]),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_comparison_csv(path: Path, rows: list[dict[str, str | int | float | None]]) -> None:
    fieldnames = [
        "model_provider",
        "record_count",
        "rouge1",
        "rouge2",
        "rougeL",
        "bertscore_f1",
        "average_latency_ms",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9]+", text)]


def _rouge_n(pred_tokens: list[str], ref_tokens: list[str], n: int) -> float:
    pred_counts = Counter(_ngrams(pred_tokens, n))
    ref_counts = Counter(_ngrams(ref_tokens, n))
    if not pred_counts or not ref_counts:
        return 0.0
    overlap = sum(min(count, ref_counts[gram]) for gram, count in pred_counts.items())
    return _f1(overlap, sum(pred_counts.values()), sum(ref_counts.values()))


def _rouge_l(pred_tokens: list[str], ref_tokens: list[str]) -> float:
    if not pred_tokens or not ref_tokens:
        return 0.0
    overlap = _lcs_length(pred_tokens, ref_tokens)
    return _f1(overlap, len(pred_tokens), len(ref_tokens))


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[index : index + n]) for index in range(len(tokens) - n + 1)]


def _lcs_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _f1(overlap: int, predicted_total: int, reference_total: int) -> float:
    if overlap == 0 or predicted_total == 0 or reference_total == 0:
        return 0.0
    precision = overlap / predicted_total
    recall = overlap / reference_total
    return round((2 * precision * recall) / (precision + recall), 4)


def _mean(values: list[float | int]) -> float:
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 4)


if __name__ == "__main__":
    main()
