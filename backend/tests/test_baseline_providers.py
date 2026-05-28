from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.run_baseline_summarization import (
    build_providers,
    compute_rouge_scores,
    run_baseline,
)
from src.data.dataset_loader import load_jsonl_dataset
from src.models import BartSummarizer, DeterministicSummarizer, PegasusSummarizer


SAMPLE_DATASET = Path("data/evaluation/sample_ehr_notes.jsonl")


class FakeGenerator:
    def __init__(self, summary: str):
        self.summary = summary
        self.calls = []

    def __call__(self, source_note: str, **kwargs):
        self.calls.append({"source_note": source_note, **kwargs})
        return [{"summary_text": self.summary}]


def test_provider_interface_with_deterministic_summarizer() -> None:
    provider = DeterministicSummarizer(max_sentences=1)
    record = {
        "note_id": "note_001",
        "source_note": "First sentence. Second sentence.",
        "reference_summary": "Reference.",
    }

    result = provider.generate(record)

    assert result.note_id == "note_001"
    assert result.model_provider == "deterministic"
    assert result.generated_summary == "First sentence."
    assert result.latency_ms >= 0
    assert set(result.to_json_dict()) == {
        "note_id",
        "model_provider",
        "source_note",
        "reference_summary",
        "generated_summary",
        "latency_ms",
    }


def test_mocked_bart_generation_does_not_download_model() -> None:
    fake = FakeGenerator("Mock BART summary.")
    provider = BartSummarizer(generator=fake, model_name="mock-bart")

    result = provider.generate(
        {
            "note_id": "note_bart",
            "source_note": "Source note for BART.",
            "reference_summary": "Reference.",
        }
    )

    assert result.model_provider == "bart"
    assert result.generated_summary == "Mock BART summary."
    assert fake.calls[0]["do_sample"] is False
    assert fake.calls[0]["truncation"] is True


def test_mocked_pegasus_generation_does_not_download_model() -> None:
    fake = FakeGenerator("Mock Pegasus summary.")
    provider = PegasusSummarizer(generator=fake, model_name="mock-pegasus")

    result = provider.generate(
        {
            "note_id": "note_pegasus",
            "source_note": "Source note for Pegasus.",
            "reference_summary": "Reference.",
        }
    )

    assert result.model_provider == "pegasus"
    assert result.generated_summary == "Mock Pegasus summary."
    assert fake.calls[0]["do_sample"] is False
    assert fake.calls[0]["truncation"] is True


def test_baseline_script_runner_on_sample_dataset_with_mocked_providers(tmp_path: Path) -> None:
    records = load_jsonl_dataset(SAMPLE_DATASET, dataset="mock")
    providers = [
        BartSummarizer(generator=FakeGenerator("Mock BART summary."), model_name="mock-bart"),
        PegasusSummarizer(generator=FakeGenerator("Mock Pegasus summary."), model_name="mock-pegasus"),
    ]

    outputs = run_baseline(records, providers, output_dir=tmp_path)

    assert set(outputs) == {"bart", "pegasus"}
    bart_path = tmp_path / "bart_outputs.jsonl"
    pegasus_path = tmp_path / "pegasus_outputs.jsonl"
    comparison_path = tmp_path / "model_comparison.csv"
    assert bart_path.exists()
    assert pegasus_path.exists()
    assert comparison_path.exists()

    first_output = json.loads(bart_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_output["model_provider"] == "bart"
    assert first_output["note_id"]
    assert first_output["source_note"]
    assert first_output["reference_summary"]
    assert first_output["generated_summary"] == "Mock BART summary."
    assert first_output["latency_ms"] >= 0

    with comparison_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["model_provider"] for row in rows} == {"bart", "pegasus"}
    assert all(row["rouge1"] for row in rows)
    assert all(row["rouge2"] for row in rows)
    assert all(row["rougeL"] for row in rows)


def test_rouge_metrics_exact_match() -> None:
    scores = compute_rouge_scores(
        "patient has documented diabetes",
        "patient has documented diabetes",
    )

    assert scores == {"rouge1": 1.0, "rouge2": 1.0, "rougeL": 1.0}


def test_real_bart_and_pegasus_disabled_by_default() -> None:
    class Args:
        provider = "bart"
        allow_model_downloads = False
        bart_model = "facebook/bart-large-cnn"
        pegasus_model = "google/pegasus-xsum"
        device = -1

    with pytest.raises(RuntimeError, match="disabled by default"):
        build_providers(Args())
