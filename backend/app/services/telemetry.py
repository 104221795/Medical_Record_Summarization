import json
import logging
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import tiktoken

from ..config import Settings
from ..schemas import CandidateSummary, EvidenceChunk, GuardrailReport, SummaryRequest


LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class SummaryTelemetryEvent:
    workflow: str
    generator_provider: str
    embedding_provider: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    retrieved_chunks: int
    status: str
    guardrail: GuardrailReport


class SummaryTelemetry(ABC):
    @abstractmethod
    def record(self, event: SummaryTelemetryEvent) -> None:
        raise NotImplementedError


class DisabledTelemetry(SummaryTelemetry):
    def record(self, event: SummaryTelemetryEvent) -> None:
        del event


class TokenEstimator:
    def __init__(self) -> None:
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def input_tokens(self, request: SummaryRequest, evidence: list[EvidenceChunk]) -> int:
        source = "\n".join(item.text for item in evidence)
        return len(self._encoding.encode(f"{request.clinical_question}\n{source}"))

    def output_tokens(self, candidate: CandidateSummary) -> int:
        text = "\n".join(item.text for item in candidate.claims)
        return len(self._encoding.encode(text))


class MlflowTelemetry(SummaryTelemetry):
    """Logs operational metrics without storing patient text or generated claims."""

    def __init__(self, settings: Settings):
        try:
            import mlflow
        except ImportError as exc:
            raise RuntimeError(
                "MLflow tracking is enabled but mlflow is not installed. "
                "Install requirements.txt."
            ) from exc
        self.mlflow = mlflow
        self.log_redacted_artifacts = settings.mlflow_log_redacted_safety_artifacts
        self.experiment_name = settings.mlflow_experiment_name
        if settings.mlflow_tracking_uri.startswith("sqlite:///./"):
            database_path = Path(settings.mlflow_tracking_uri.removeprefix("sqlite:///"))
            database_path.parent.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    def record(self, event: SummaryTelemetryEvent) -> None:
        event_id = str(uuid.uuid4())
        suspicious = int(not event.guardrail.approved or bool(event.guardrail.issues))
        self.mlflow.set_experiment(self.experiment_name)
        with self.mlflow.start_run(run_name=f"summary-{event_id[:8]}"):
            self.mlflow.set_tags(
                {
                    "event_id": event_id,
                    "workflow": event.workflow,
                    "generator_provider": event.generator_provider,
                    "embedding_provider": event.embedding_provider,
                    "summary_status": event.status,
                    "contains_phi": "not_logged",
                }
            )
            self.mlflow.log_metrics(
                {
                    "latency_ms": event.latency_ms,
                    "input_tokens_estimated": float(event.input_tokens),
                    "output_tokens_estimated": float(event.output_tokens),
                    "retrieved_chunks": float(event.retrieved_chunks),
                    "citation_coverage_pct": event.guardrail.citation_coverage,
                    "suspected_hallucination": float(suspicious),
                    "guardrail_issue_count": float(len(event.guardrail.issues)),
                }
            )
            if suspicious and self.log_redacted_artifacts:
                self._log_redacted_safety_event(event_id, event.guardrail)

    def _log_redacted_safety_event(self, event_id: str, report: GuardrailReport) -> None:
        artifact = {
            "event_id": event_id,
            "approved": report.approved,
            "citation_coverage_pct": report.citation_coverage,
            "issue_codes": [issue.code for issue in report.issues],
            "issue_count": len(report.issues),
            "redaction_notice": "No patient text, claim text, source evidence, or identifiers logged.",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "suspected_hallucination_event.json"
            path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
            self.mlflow.log_artifact(str(path), artifact_path="safety_events")


class ResilientTelemetry(SummaryTelemetry):
    """Prevents observability failure from failing a clinical API response."""

    def __init__(self, delegate: SummaryTelemetry):
        self.delegate = delegate

    def record(self, event: SummaryTelemetryEvent) -> None:
        try:
            self.delegate.record(event)
        except Exception:
            LOGGER.exception("Summary telemetry write failed; request result is preserved.")


def build_telemetry(settings: Settings) -> SummaryTelemetry:
    if not settings.mlflow_enabled:
        return DisabledTelemetry()
    return ResilientTelemetry(MlflowTelemetry(settings))
