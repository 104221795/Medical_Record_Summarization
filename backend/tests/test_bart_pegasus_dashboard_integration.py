from __future__ import annotations

import inspect
import json
from pathlib import Path

from backend.app.persistence_schemas import SummaryGenerateRequest
from backend.app.services import evaluation_service
from backend.app.config import Settings
from backend.app.dependencies import _validated_header_context
from backend.app.evaluation.artifact_paths import (
    DEFAULT_EVALUATION_ARTIFACT_ROOT,
    benchmark_discovery_dirs,
    configured_evaluation_artifact_root,
)
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


def test_latest_rag_best_models_pointer_selects_completed_flow_2_1_run(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "rag_best_models_benchmark_50_no_gate"
    output_dir.mkdir()
    (output_dir / "model_comparison.csv").write_text(
        "\n".join(
            [
                "model_provider,model_name,status,record_count,completed_count,failed_count,skipped_count,rouge1,rouge2,rougeL",
                "deterministic,deterministic_context_baseline,completed,50,50,0,0,0.2973,0.1263,0.1737",
                "bart,facebook/bart-large-cnn,completed,50,50,0,0,0.0986,0.0127,0.0757",
                "pegasus,google/pegasus-cnn_dailymail,completed,50,50,0,0,0.1986,0.0748,0.1495",
                "qwen2.5,ollama/qwen2.5:3b,completed,50,50,0,0,0.3353,0.1429,0.2122",
                "llama3.2,ollama/llama3.2:3b,completed,50,50,0,0,0.3002,0.1281,0.1863",
            ]
        ),
        encoding="utf-8",
    )
    pointer = tmp_path / "latest_rag_best_models.json"
    pointer.write_text(
        json.dumps({"selected_output_dir": str(output_dir)}),
        encoding="utf-8",
    )
    selected = evaluation_service._latest_rag_best_models_output_dir(tmp_path)

    assert selected == output_dir


def test_relative_artifact_root_defaults_to_repository_location(monkeypatch) -> None:
    monkeypatch.delenv("RAG_EVALUATION_ARTIFACT_ROOT", raising=False)
    monkeypatch.delenv("EVALUATION_ARTIFACT_ROOT", raising=False)
    monkeypatch.delenv("BENCHMARK_SNAPSHOT_DIR", raising=False)

    assert configured_evaluation_artifact_root() == DEFAULT_EVALUATION_ARTIFACT_ROOT


def test_configured_artifact_root_is_preferred_for_flow_2_1(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "rag_best_models_benchmark_50_no_gate"
    output_dir.mkdir()
    (output_dir / "model_comparison.csv").write_text(
        "model_provider,status,record_count,completed_count,rougeL\n"
        "qwen2.5,completed,50,50,0.2122\n",
        encoding="utf-8",
    )

    candidates = benchmark_discovery_dirs(tmp_path)
    selected, discovered = evaluation_service._select_benchmark_output_dir(
        candidates,
        "rag_best_models",
    )

    assert selected == output_dir
    assert next(item for item in discovered if item["path"] == str(output_dir))["selected"] is True


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
