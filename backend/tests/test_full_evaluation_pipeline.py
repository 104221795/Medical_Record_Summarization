from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts import run_full_evaluation_pipeline as pipeline
from scripts.run_full_evaluation_pipeline import PipelineConfig, ProviderPlan, run_full_evaluation_pipeline
from src.models import BaseSummarizer


def test_full_pipeline_dry_run_writes_outputs_without_model_downloads(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)
    output_dir = tmp_path / "outputs"

    result = run_full_evaluation_pipeline(
        PipelineConfig(
            input_path=input_path,
            dataset="multiclinsum",
            models=("deterministic", "bart", "pegasus"),
            limit=1,
            output_dir=output_dir,
            dry_run=True,
        )
    )

    assert result["output_dir"] == str(output_dir)
    _assert_common_outputs(output_dir)
    assert (output_dir / "deterministic_predictions.jsonl").exists()
    assert (output_dir / "bart_predictions.jsonl").exists()
    assert (output_dir / "pegasus_predictions.jsonl").exists()

    rows = _read_jsonl(output_dir / "all_predictions.jsonl")
    statuses = {(row["model_provider"], row["status"]) for row in rows}
    assert statuses == {
        ("deterministic", "ready"),
        ("bart", "skipped"),
        ("pegasus", "skipped"),
    }
    assert all(row["generated_summary"] == "" for row in rows)

    report = (output_dir / "EVALUATION_REPORT.md").read_text(encoding="utf-8")
    assert "Proxy evaluation only. Do not claim real EHR benchmark or clinical performance" in report
    assert "These results do not demonstrate clinical safety, clinical effectiveness" in report
    assert "MultiClinSum/MTS-Dialog/MEDIQA-Sum are proxy/open benchmark datasets" in report
    assert "Medical record summarization datasets are limited" in report


def test_full_pipeline_deterministic_model_completes(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)
    output_dir = tmp_path / "outputs"

    result = run_full_evaluation_pipeline(
        PipelineConfig(
            input_path=input_path,
            dataset="multiclinsum",
            models=("deterministic",),
            limit=1,
            output_dir=output_dir,
        )
    )

    _assert_common_outputs(output_dir)
    predictions = _read_jsonl(output_dir / "deterministic_predictions.jsonl")
    assert len(predictions) == 1
    assert predictions[0]["status"] == "completed"
    assert predictions[0]["generated_summary"]
    assert predictions[0]["proxy_evaluation"] is True
    assert "factuality_proxy_score" in predictions[0]
    assert "failure_categories" in predictions[0]

    comparison = result["comparison_rows"][0]
    assert comparison["model_provider"] == "deterministic"
    assert comparison["status"] == "completed"
    assert comparison["completed_count"] == 1
    assert comparison["rouge1"] is not None
    assert "citation_coverage" in comparison
    assert "latency_p95_ms" in comparison

    with (output_dir / "model_comparison.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["model_provider"] == "deterministic"
    assert rows[0]["status"] == "completed"
    assert "factuality_proxy_score" in rows[0]

    failure_examples = _read_jsonl(output_dir / "per_record_failure_analysis.jsonl")
    assert failure_examples[0]["input_note"]
    assert failure_examples[0]["generated_summary"]
    assert failure_examples[0]["reference_summary"]


def test_full_pipeline_blocks_bart_and_pegasus_unless_downloads_allowed(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)

    result = run_full_evaluation_pipeline(
        PipelineConfig(
            input_path=input_path,
            dataset="multiclinsum",
            models=("bart", "pegasus"),
            output_dir=tmp_path / "outputs",
            allow_model_downloads=False,
        )
    )

    statuses = {(row["model_provider"], row["status"]) for row in result["prediction_rows"]}
    assert statuses == {("bart", "skipped"), ("pegasus", "skipped")}
    assert all("disabled by default" in row["error_message"] for row in result["prediction_rows"])


def test_full_pipeline_failed_provider_does_not_crash_without_fail_fast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_dataset(tmp_path)

    def fake_build_provider_plan(model: str, config: PipelineConfig) -> ProviderPlan:
        return ProviderPlan(name="deterministic", model_name="failing", summarizer=FailingSummarizer())

    monkeypatch.setattr(pipeline, "_build_provider_plan", fake_build_provider_plan)

    result = run_full_evaluation_pipeline(
        PipelineConfig(
            input_path=input_path,
            dataset="multiclinsum",
            models=("deterministic",),
            output_dir=tmp_path / "outputs",
            fail_fast=False,
        )
    )

    assert result["comparison_rows"][0]["status"] == "failed"
    rows = _read_jsonl(tmp_path / "outputs" / "all_predictions.jsonl")
    assert rows[0]["status"] == "failed"
    assert "synthetic provider failure" in rows[0]["error_message"]


def test_full_pipeline_fail_fast_raises_on_provider_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_dataset(tmp_path)

    def fake_build_provider_plan(model: str, config: PipelineConfig) -> ProviderPlan:
        return ProviderPlan(name="deterministic", model_name="failing", summarizer=FailingSummarizer())

    monkeypatch.setattr(pipeline, "_build_provider_plan", fake_build_provider_plan)

    with pytest.raises(RuntimeError, match="synthetic provider failure"):
        run_full_evaluation_pipeline(
            PipelineConfig(
                input_path=input_path,
                dataset="multiclinsum",
                models=("deterministic",),
                output_dir=tmp_path / "outputs",
                fail_fast=True,
            )
        )


class FailingSummarizer(BaseSummarizer):
    provider_name = "deterministic"
    model_name = "failing_summarizer"
    model_version = "test"

    def _generate_text(self, source_note: str) -> str:
        raise RuntimeError("synthetic provider failure")


def _write_dataset(tmp_path: Path) -> Path:
    input_path = tmp_path / "records.jsonl"
    row = {
        "note_id": "note_001",
        "patient_id": "patient_001",
        "encounter_id": "encounter_001",
        "source_note": (
            "History:\n"
            "Patient has documented fever, cough, and fatigue for three days. "
            "The patient denies chest pain and reports adequate oral intake. "
            "Past history includes mild asthma without recent exacerbation. "
            "Medications:\n"
            "Patient uses an albuterol inhaler as needed and takes acetaminophen for fever. "
            "Assessment:\n"
            "Clinical documentation supports an acute febrile respiratory illness with stable respiratory status. "
            "Plan:\n"
            "Continue supportive care, monitor symptoms, and arrange follow up if symptoms worsen."
        ),
        "reference_summary": (
            "Patient has fever, cough, and fatigue for three days with stable respiratory status. "
            "Uses albuterol as needed and acetaminophen for fever. Supportive care and follow up were arranged."
        ),
        "dataset": "multiclinsum",
        "split": "test",
    }
    input_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return input_path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_common_outputs(output_dir: Path) -> None:
    assert (output_dir / "evaluation_run_manifest.json").exists()
    assert (output_dir / "run_manifest.json").exists()
    assert (output_dir / "dataset_profile.json").exists()
    assert (output_dir / "quality_metrics.json").exists()
    assert (output_dir / "retrieval_metrics.json").exists()
    assert (output_dir / "model_manifest.json").exists()
    assert (output_dir / "model_comparison.csv").exists()
    assert (output_dir / "all_predictions.jsonl").exists()
    assert (output_dir / "per_record_failure_analysis.jsonl").exists()
    assert (output_dir / "human_review_template.csv").exists()
    assert (output_dir / "failure_analysis.md").exists()
    assert (output_dir / "EVALUATION_REPORT.md").exists()
    assert (output_dir / "run.log").exists()
    assert (output_dir / "data_governance" / "dataset_manifest.json").exists()
    assert (output_dir / "data_governance" / "benchmark_manifest.jsonl").exists()
    assert (output_dir / "data_governance" / "chunking_report.md").exists()
