from __future__ import annotations

import os
from typing import Any

from scripts.run_baseline_summarization import compute_rouge_scores


def compute_pairwise_metrics(
    predictions: list[str],
    references: list[str],
    *,
    include_bertscore: bool = False,
) -> dict[str, Any]:
    if len(predictions) != len(references):
        raise ValueError("predictions and references must have the same length.")
    rouge_rows = [
        compute_rouge_scores(prediction, reference)
        for prediction, reference in zip(predictions, references, strict=True)
    ]
    metrics: dict[str, Any] = {
        "record_count": len(predictions),
        "rouge1": _mean([row["rouge1"] for row in rouge_rows]),
        "rouge2": _mean([row["rouge2"] for row in rouge_rows]),
        "rougeL": _mean([row["rougeL"] for row in rouge_rows]),
        "average_prediction_length": _mean([len(text.split()) for text in predictions]),
        "average_reference_length": _mean([len(text.split()) for text in references]),
    }
    if include_bertscore:
        metrics.update(compute_bertscore_metrics(predictions, references))
    return metrics


def compute_bertscore_metrics(predictions: list[str], references: list[str]) -> dict[str, Any]:
    if not predictions or not references:
        return {
            "bertscore_precision": None,
            "bertscore_recall": None,
            "bertscore_f1": None,
            "bertscore_status": "not_available",
            "bertscore_message": "BERTScore was not computed because there are no prediction/reference pairs.",
        }
    try:
        from bert_score import score
    except Exception:
        return {
            "bertscore_precision": None,
            "bertscore_recall": None,
            "bertscore_f1": None,
            "bertscore_status": "skipped_dependency_unavailable",
            "bertscore_message": "BERTScore skipped: optional package 'bert-score' is not installed.",
        }
    try:
        score_kwargs: dict[str, Any] = {"lang": "en", "verbose": False}
        model_type = os.environ.get("RAG_BERTSCORE_MODEL_TYPE", "").strip()
        device = os.environ.get("RAG_BERTSCORE_DEVICE", "").strip()
        batch_size = os.environ.get("RAG_BERTSCORE_BATCH_SIZE", "").strip()
        if model_type:
            score_kwargs["model_type"] = model_type
        if device:
            score_kwargs["device"] = device
        if batch_size:
            score_kwargs["batch_size"] = int(batch_size)
        precision, recall, f1 = score(predictions, references, **score_kwargs)
    except Exception as exc:
        return {
            "bertscore_precision": None,
            "bertscore_recall": None,
            "bertscore_f1": None,
            "bertscore_status": "skipped_model_unavailable",
            "bertscore_message": f"BERTScore skipped: dependency/model unavailable ({exc}).",
        }
    return {
        "bertscore_precision": round(float(precision.mean().item()), 4),
        "bertscore_recall": round(float(recall.mean().item()), 4),
        "bertscore_f1": round(float(f1.mean().item()), 4),
        "bertscore_status": "computed",
        "bertscore_model_type": os.environ.get("RAG_BERTSCORE_MODEL_TYPE", "").strip() or "bert-score-default-en",
        "bertscore_message": "BERTScore computed successfully.",
    }


def _mean(values: list[float | int]) -> float:
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 4)
