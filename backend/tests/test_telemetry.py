import json
from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.schemas import GuardrailIssue, GuardrailReport
from backend.app.services.telemetry import MlflowTelemetry, SummaryTelemetryEvent


@pytest.mark.filterwarnings("ignore:The filesystem tracking backend.*:FutureWarning")
def test_mlflow_logs_metrics_and_redacted_safety_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        environment="test",
        mlflow_enabled=True,
        mlflow_tracking_uri=tmp_path.as_uri(),
        mlflow_experiment_name="telemetry-test",
    )
    telemetry = MlflowTelemetry(settings)
    event = SummaryTelemetryEvent(
        workflow="diagnostic_report",
        generator_provider="test-generator",
        embedding_provider="test-embedder",
        latency_ms=24.6,
        input_tokens=91,
        output_tokens=12,
        retrieved_chunks=2,
        status="blocked",
        guardrail=GuardrailReport(
            approved=False,
            checks_applied=["fail_closed_output_gate"],
            citation_coverage=0.0,
            issues=[
                GuardrailIssue(
                    claim="Sensitive patient diagnosis must not be stored in MLflow.",
                    code="POSSIBLE_CONTRADICTION",
                    detail="Sensitive evidence detail must not be stored either.",
                )
            ],
            disposition="Blocked",
        ),
    )

    telemetry.record(event)

    artifacts = list(tmp_path.rglob("suspected_hallucination_event.json"))
    assert len(artifacts) == 1
    safety_event = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert safety_event["issue_codes"] == ["POSSIBLE_CONTRADICTION"]
    assert "claim" not in safety_event
    assert "Sensitive" not in artifacts[0].read_text(encoding="utf-8")
