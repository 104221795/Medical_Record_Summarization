from __future__ import annotations

import inspect
import json
from pathlib import Path

from backend.app.persistence_schemas import SummaryGenerateRequest
from backend.app.services import evaluation_service
from backend.app.config import Settings
from backend.app.dependencies import _validated_header_context
from backend.app.main import create_app
from backend.app.routers.auth import _hash_password, _verify_password, logout
from backend.app.persistence_schemas import AuthGoogleLoginRequest, AuthSignupRequest
from backend.app.services.rag import build_rag_service
from backend.app.services.llm_gateway import SummaryProviderGateway
from src.models.bart_summarizer import BartSummarizer
from src.models.pegasus_summarizer import PegasusSummarizer


def test_bart_and_pegasus_summarizers_do_not_use_pipeline() -> None:
    assert 'pipeline("summarization"' not in inspect.getsource(BartSummarizer)
    assert 'pipeline("summarization"' not in inspect.getsource(PegasusSummarizer)


def test_new_provider_names_are_accepted() -> None:
    for provider in ("bart", "pegasus", "pegasus_pubmed", "pegasus_cnn_dailymail", "pegasus_xsum"):
        payload = SummaryGenerateRequest.model_validate({"model_provider": provider})
        assert payload.model_provider == provider


def test_provider_gateway_lists_required_providers() -> None:
    response = SummaryProviderGateway(Settings()).list_providers()
    names = {provider.provider_name for provider in response.providers}
    assert {
        "deterministic",
        "gemini2.5_flash_lite",
        "bart",
        "pegasus_pubmed",
        "pegasus_cnn_dailymail",
        "pegasus_xsum",
    } <= names
    assert next(provider for provider in response.providers if provider.provider_name == "pegasus_pubmed").domain_fit


def test_auth_password_hash_and_signup_validation() -> None:
    password_hash = _hash_password("Demo-password7!")
    assert _verify_password("Demo-password7!", password_hash)
    payload = AuthSignupRequest(
        full_name="Doctor Demo",
        email="doctor@example.test",
        password="Demo-password7!",
        confirm_password="Demo-password7!",
        role="doctor",
    )
    assert payload.email == "doctor@example.test"
    assert logout().authenticated is False


def test_google_login_payload_validation() -> None:
    payload = AuthGoogleLoginRequest(
        credential="header.payload.signature-for-google-id-token",
        role="doctor",
        tenant_id="sandbox",
    )
    assert payload.role == "doctor"
    assert payload.tenant_id == "sandbox"


def test_google_auth_route_is_registered() -> None:
    settings = Settings(database_url="sqlite:///:memory:", embedding_provider="hashing")
    app = create_app(settings=settings, rag_service=build_rag_service(settings))
    paths = {route.path for route in app.routes}
    assert "/api/v1/auth/google" in paths


def test_database_url_accepts_unprefixed_alias(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("RAG_DATABASE_URL", raising=False)
    assert Settings().database_url == "sqlite:///:memory:"


def test_request_context_accepts_email_user_header() -> None:
    context = _validated_header_context("sandbox", "doctor.demo@example.org", "doctor")
    assert context.user_id == "doctor.demo@example.org"


def test_benchmark_csv_reader_parses_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "model_comparison.csv"
    csv_path.write_text(
        "\n".join(
            [
                "model_provider,model_name,status,record_count,completed_count,failed_count,skipped_count,rouge1,rouge2,rougeL,bertscore_status,average_latency_ms,notes,error_message",
                "bart,facebook/bart-large-cnn,completed,200,200,0,0,0.3,0.1,0.2,not_requested,10,,",
            ]
        ),
        encoding="utf-8",
    )
    rows = evaluation_service._read_model_comparison(csv_path)
    assert rows[0].model_provider == "bart"
    assert rows[0].rougeL == 0.2


def test_benchmark_results_merge_pegasus_pubmed_prediction_rows(tmp_path: Path) -> None:
    prediction_path = tmp_path / "pegasus_pubmed_predictions.jsonl"
    records = [
        {
            "stage": "stage_pegasus_pegasus_pubmed_limit200",
            "model_provider": "pegasus_pubmed",
            "model_name": "google/pegasus-pubmed",
            "status": "completed",
            "rouge1": 0.4,
            "rouge2": 0.2,
            "rougeL": 0.3,
            "latency_ms": 1200,
            "failure_categories": ["source data limitation"],
        },
        {
            "stage": "stage_pegasus_pegasus_pubmed_limit200",
            "model_provider": "pegasus_pubmed",
            "model_name": "google/pegasus-pubmed",
            "status": "completed",
            "rouge1": 0.2,
            "rouge2": 0.1,
            "rougeL": 0.15,
            "latency_ms": 1800,
            "failure_categories": ["missing medication"],
        },
    ]
    prediction_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )

    rows = evaluation_service._merge_prediction_rows(tmp_path, [])
    pubmed = next(row for row in rows if row.model_provider == "pegasus_pubmed")

    assert pubmed.model_name == "google/pegasus-pubmed"
    assert pubmed.stage_name == "stage_pegasus_pegasus_pubmed_limit200"
    assert pubmed.completed_count == 2
    assert pubmed.rougeL == 0.225
    assert pubmed.average_latency_ms == 1500
    assert pubmed.domain_fit == "Medical/scientific"


def test_evaluation_ui_can_render_benchmark_rows() -> None:
    app_js = Path("backend/ui/evaluation/app.js").read_text(encoding="utf-8")
    assert "renderBenchmarkDashboard" in app_js
    assert "benchmarkRow" in app_js
    assert "/evaluation/benchmark/results" in app_js
