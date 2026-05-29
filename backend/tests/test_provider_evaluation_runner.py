from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pytest

from scripts.run_provider_evaluation import (
    EvaluationProvider,
    GeminiEvaluationSummarizer,
    build_evaluation_providers,
    run_provider_evaluation,
)
from src.data.dataset_loader import load_jsonl_dataset
from src.models import DeterministicSummarizer


SAMPLE_DATASET = Path("data/evaluation/sample_ehr_notes.jsonl")


class FakeGeminiClient:
    def __init__(self, raw_response: str):
        self.raw_response = raw_response

    def generate_json(self, **kwargs):
        return self.raw_response


def test_unified_provider_evaluation_writes_proxy_outputs(tmp_path: Path) -> None:
    records = load_jsonl_dataset(SAMPLE_DATASET, dataset="mock", max_records=2)
    provider = EvaluationProvider(
        name="deterministic",
        model_name="deterministic_sentence_baseline",
        summarizer=DeterministicSummarizer(max_sentences=2),
    )

    result = run_provider_evaluation(
        records,
        [provider],
        output_dir=tmp_path,
        dataset_path=SAMPLE_DATASET,
    )

    assert result["output_dir"] == str(tmp_path)
    provider_jsonl = tmp_path / "provider_outputs.jsonl"
    deterministic_jsonl = tmp_path / "deterministic_outputs.jsonl"
    comparison_csv = tmp_path / "provider_model_comparison.csv"
    markdown_summary = tmp_path / "EVALUATION_SUMMARY.md"
    assert provider_jsonl.exists()
    assert deterministic_jsonl.exists()
    assert comparison_csv.exists()
    assert markdown_summary.exists()

    rows = [json.loads(line) for line in provider_jsonl.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["model_provider"] for row in rows} == {"deterministic"}
    assert all(row["status"] == "completed" for row in rows)
    assert all(row["proxy_evaluation"] is True for row in rows)
    assert all(row["evaluation_type"] == "proxy_deidentified_demo_evaluation" for row in rows)
    assert all(row["generated_summary"] for row in rows)
    assert all(row["rouge1"] is not None for row in rows)

    with comparison_csv.open("r", encoding="utf-8", newline="") as handle:
        comparison_rows = list(csv.DictReader(handle))
    assert comparison_rows[0]["model_provider"] == "deterministic"
    assert comparison_rows[0]["status"] == "completed"
    assert comparison_rows[0]["completed_count"] == "2"

    summary_text = markdown_summary.read_text(encoding="utf-8")
    assert "Proxy evaluation only" in summary_text
    assert "Real EHR benchmark status: pending" in summary_text


def test_disabled_external_providers_are_skipped_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in [
        "RUN_REAL_BASELINES",
        "RAG_RUN_REAL_BASELINES",
        "RUN_GEMINI_EVALUATION",
        "RAG_LLM_PROVIDER",
        "RAG_LLM_EXTERNAL_ENABLED",
        "RAG_LLM_ALLOW_PHI_EXTERNAL",
        "RAG_GEMINI_API_KEY",
        "GEMINI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    args = argparse.Namespace(
        providers="bart,pegasus,gemini",
        allow_model_downloads=False,
        allow_gemini=False,
        bart_model="facebook/bart-large-cnn",
        pegasus_model="google/pegasus-xsum",
        gemini_model="gemini-2.5-flash-lite",
        device=-1,
        deterministic_sentences=3,
    )
    providers = build_evaluation_providers(args)
    records = load_jsonl_dataset(SAMPLE_DATASET, dataset="mock", max_records=1)

    result = run_provider_evaluation(
        records,
        providers,
        output_dir=tmp_path,
        dataset_path=SAMPLE_DATASET,
    )

    statuses = {(row["model_provider"], row["status"]) for row in result["rows"]}
    assert statuses == {("bart", "skipped"), ("pegasus", "skipped"), ("gemini", "skipped")}
    assert all(row["generated_summary"] == "" for row in result["rows"])
    assert all("disabled" in row["error_message"].lower() for row in result["rows"])


def test_gemini_evaluation_summarizer_uses_strict_json_without_network() -> None:
    summarizer = GeminiEvaluationSummarizer(api_key="test-key", model_name="test-gemini")
    summarizer.client = FakeGeminiClient(
        '{"generated_summary":"Mock Gemini summary.","safety_note":"demo only"}'
    )

    output = summarizer.generate(
        {
            "note_id": "note_gemini",
            "source_note": "De-identified source note.",
            "reference_summary": "Reference.",
        }
    )

    assert output.model_provider == "gemini"
    assert output.generated_summary == "Mock Gemini summary."

    summarizer.client = FakeGeminiClient("not-json")
    with pytest.raises(Exception, match="invalid JSON"):
        summarizer.generate(
            {
                "note_id": "note_gemini",
                "source_note": "De-identified source note.",
                "reference_summary": "Reference.",
            }
        )
