from __future__ import annotations

import builtins

from backend.app.evaluation.semantic_metrics import compute_pairwise_metrics


def test_semantic_metrics_exact_match_without_optional_bertscore() -> None:
    metrics = compute_pairwise_metrics(
        ["patient has documented fever"],
        ["patient has documented fever"],
    )

    assert metrics["record_count"] == 1
    assert metrics["rouge1"] == 1.0
    assert metrics["rouge2"] == 1.0
    assert metrics["rougeL"] == 1.0


def test_semantic_metrics_rejects_mismatched_lengths() -> None:
    try:
        compute_pairwise_metrics(["one"], ["one", "two"])
    except ValueError as exc:
        assert "same length" in str(exc)
    else:
        raise AssertionError("Expected ValueError for mismatched metric inputs.")


def test_semantic_metrics_reports_when_bertscore_dependency_missing(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "bert_score":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    metrics = compute_pairwise_metrics(
        ["patient has documented fever"],
        ["patient has documented fever"],
        include_bertscore=True,
    )

    assert metrics["bertscore_precision"] is None
    assert metrics["bertscore_status"] == "skipped_dependency_unavailable"
    assert "BERTScore skipped" in metrics["bertscore_message"]
