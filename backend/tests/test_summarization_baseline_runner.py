from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.evaluation.summarization_baseline_runner import (
    BaselineRunnerError,
    run_baseline_evaluation,
)


def test_baseline_runner_dry_run_writes_readiness_report(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)

    result = run_baseline_evaluation(
        dataset="multiclinsum",
        input_path=input_path,
        model="pegasus",
        output_dir=tmp_path / "outputs",
        dry_run=True,
        limit=1,
    )

    readiness_path = tmp_path / "outputs" / "multiclinsum_pegasus_readiness.json"
    assert readiness_path.exists()
    assert result["status"] == "ready"
    assert result["dry_run"] is True
    assert result["record_count"] == 1
    assert result["evaluation_layer"].startswith("Layer C.1")
    assert result["average_input_length"] > 0
    assert result["average_latency_ms"] == 0.0
    persisted = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert persisted["model_provider"] == "pegasus"


def test_baseline_runner_deterministic_smoke_writes_metrics(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)

    result = run_baseline_evaluation(
        dataset="multiclinsum",
        input_path=input_path,
        model="deterministic",
        output_dir=tmp_path / "outputs",
        limit=1,
    )

    assert result["status"] == "completed"
    assert result["success_count"] == 1
    assert result["evaluation_layer"].startswith("Layer C.1")
    assert result["average_latency_ms"] >= 0
    assert result["average_input_length"] > 0
    assert result["average_output_length"] > 0
    assert (tmp_path / "outputs" / "multiclinsum_deterministic_predictions.jsonl").exists()
    assert (tmp_path / "outputs" / "multiclinsum_deterministic_metrics.csv").exists()
    assert (tmp_path / "outputs" / "multiclinsum_deterministic_summary.md").exists()
    summary = (tmp_path / "outputs" / "multiclinsum_deterministic_summary.md").read_text(encoding="utf-8")
    assert "BERTScore status" in summary


def test_baseline_runner_supports_mts_dialog_layer(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path, dataset="mts_dialog", split="test_1")

    result = run_baseline_evaluation(
        dataset="mts_dialog",
        input_path=input_path,
        model="deterministic",
        output_dir=tmp_path / "outputs",
        limit=1,
    )

    assert result["status"] == "completed"
    assert result["evaluation_layer"].startswith("Layer C.2")


def test_baseline_runner_blocks_real_pegasus_by_default(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)

    with pytest.raises(BaselineRunnerError, match="Pegasus execution is disabled"):
        run_baseline_evaluation(
            dataset="multiclinsum",
            input_path=input_path,
            model="pegasus",
            output_dir=tmp_path / "outputs",
            limit=1,
        )


def test_baseline_runner_rejects_unknown_dataset(tmp_path: Path) -> None:
    input_path = _write_dataset(tmp_path)

    with pytest.raises(BaselineRunnerError, match="Unsupported dataset"):
        run_baseline_evaluation(
            dataset="unknown",
            input_path=input_path,
            model="deterministic",
            output_dir=tmp_path / "outputs",
            limit=1,
        )


def _write_dataset(tmp_path: Path, *, dataset: str = "multiclinsum", split: str = "test") -> Path:
    input_path = tmp_path / "records.jsonl"
    row = {
        "note_id": "note_001",
        "patient_id": "patient_001",
        "encounter_id": "enc_001",
        "source_note": "Patient has documented fever. Chest x-ray is normal.",
        "reference_summary": "Fever documented; chest x-ray normal.",
        "dataset": dataset,
        "split": split,
    }
    input_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return input_path
