from __future__ import annotations

import json

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, create_session_factory
from backend.app.main import create_app
from backend.app.services import llm_gateway as llm_gateway_module
from backend.app.services.llm_gateway import SummaryProviderGateway
from backend.app.services.rag import build_rag_service
from backend.tests.summary_test_utils import (
    HEADERS,
    api_client,
    generate_patient_snapshot,
    import_patient,
)


ADMIN_HEADERS = {
    **HEADERS,
    "X-Role-Code": "clinical_admin",
    "X-User-ID": "clinical-admin-demo",
}
DOCTOR_HEADERS = {**HEADERS, "X-Role-Code": "doctor"}


def test_operations_health_and_readiness(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"
    assert ready.status_code in {200, 503}, ready.text
    body = ready.json()
    assert body["clinical_use"] == "staging_demo_only"
    assert "database" in body["checks"]
    assert body["checks"]["database"]["status"] == "pass"


def test_doctor_golden_path_smoke(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, encounter_id = import_patient(client)

    patients = client.get("/api/v1/patients", headers=DOCTOR_HEADERS)
    generated = generate_patient_snapshot(client, patient_id, encounter_id)
    review = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/review/start",
        headers=DOCTOR_HEADERS,
    )

    assert patients.status_code == 200, patients.text
    assert patients.json()["items"]
    assert generated["status"] == "draft"
    assert generated["citation_coverage"] is not None
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "under_review"


def test_admin_artifact_and_audit_endpoints_are_graceful(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    benchmark = client.get("/api/v1/evaluation/benchmark/status", headers=ADMIN_HEADERS)
    audit_export = client.get("/api/v1/audit/export", headers=ADMIN_HEADERS)

    assert benchmark.status_code == 200, benchmark.text
    assert "status" in benchmark.json()
    assert audit_export.status_code == 200, audit_export.text
    assert audit_export.json()["phi_safe"] is True


def test_railway_provider_selectability_is_deployment_aware() -> None:
    settings = Settings(
        environment="staging",
        deployment_mode="railway",
        auth_secret_key=SecretStr("staging-test-secret-with-sufficient-entropy"),
        cors_origins="https://example-staging.up.railway.app",
        job_backend="rq",
        redis_required=True,
        primary_provider="gemini2.5_flash_lite",
        local_ollama_enabled=False,
    ).model_copy(update={"gemini_api_key": None})

    providers = {
        item.provider_name: item
        for item in SummaryProviderGateway(settings).list_providers().providers
    }

    assert providers["deterministic"].selectable is True
    assert providers["deterministic"].deployment_role == "smoke_fallback"
    assert providers["gemini2.5_flash_lite"].selectable is False
    assert providers["gemini2.5_flash_lite"].status == "configuration_required"
    assert providers["qwen2.5"].selectable is False
    assert providers["qwen2.5"].status == "local_only"


def test_railway_gemini_is_selectable_when_server_secret_is_configured() -> None:
    settings = Settings(
        environment="staging",
        deployment_mode="railway",
        auth_secret_key=SecretStr("staging-test-secret-with-sufficient-entropy"),
        cors_origins="https://example-staging.up.railway.app",
        job_backend="rq",
        redis_required=True,
        primary_provider="gemini2.5_flash_lite",
        gemini_api_key=SecretStr("test-gemini-key-placeholder"),
    )

    gemini = next(
        item
        for item in SummaryProviderGateway(settings).list_providers().providers
        if item.provider_name == "gemini2.5_flash_lite"
    )

    assert gemini.selectable is True
    assert gemini.status == "ready"
    assert gemini.deployment_role == "deployment_primary"


class _FakeOllamaResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_local_ollama_readiness_uses_default_url_and_qwen_model(monkeypatch) -> None:
    requested_urls: list[str] = []

    def fake_urlopen(url: str, timeout: float):
        requested_urls.append(url)
        return _FakeOllamaResponse({"models": [{"name": "qwen2.5:3b"}]})

    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr(llm_gateway_module.urlrequest, "urlopen", fake_urlopen)

    settings = Settings(environment="test", local_ollama_enabled=True)
    providers = {
        item.provider_name: item
        for item in SummaryProviderGateway(settings).list_providers().providers
    }

    assert requested_urls[0] == "http://127.0.0.1:11434/api/tags"
    assert providers["qwen2.5"].status == "ready"
    assert providers["qwen2.5"].selectable is True


def test_local_ollama_readiness_honors_qwen_model_override(monkeypatch) -> None:
    def fake_urlopen(url: str, timeout: float):
        assert url == "http://localhost:11434/api/tags"
        return _FakeOllamaResponse({"models": [{"name": "qwen2.5:7b"}]})

    monkeypatch.setenv("LLM_GATEWAY_QWEN2_5_MODEL", "ollama/qwen2.5:7b")
    monkeypatch.setattr(llm_gateway_module.urlrequest, "urlopen", fake_urlopen)

    settings = Settings(
        environment="test",
        local_ollama_enabled=True,
        ollama_base_url="localhost:11434/api",
    )
    qwen = next(
        item
        for item in SummaryProviderGateway(settings).list_providers().providers
        if item.provider_name == "qwen2.5"
    )

    assert qwen.model_name == "ollama/qwen2.5:7b"
    assert qwen.status == "ready"
    assert qwen.selectable is True


def test_local_ollama_readiness_reports_actionable_url_error(monkeypatch) -> None:
    def fake_urlopen(url: str, timeout: float):
        raise OSError("connection refused")

    monkeypatch.setattr(llm_gateway_module.urlrequest, "urlopen", fake_urlopen)

    settings = Settings(environment="test", local_ollama_enabled=True)
    qwen = next(
        item
        for item in SummaryProviderGateway(settings).list_providers().providers
        if item.provider_name == "qwen2.5"
    )

    assert qwen.status == "unavailable"
    assert "http://127.0.0.1:11434/api/tags" in (qwen.disabled_reason or "")
    assert "ollama pull qwen2.5:3b" in (qwen.disabled_reason or "")


def test_compose_mode_enforces_strict_rq_topology() -> None:
    settings = Settings(
        environment="staging",
        deployment_mode="compose",
        auth_secret_key=SecretStr("staging-test-secret-with-sufficient-entropy"),
        cors_origins="http://127.0.0.1:8080,http://localhost:8080",
        job_backend="rq",
        redis_required=True,
        embedding_provider="hashing",
    )

    assert settings.deployment_mode == "compose"
    assert settings.job_backend == "rq"
    assert settings.redis_required is True


def test_staging_rejects_role_header_impersonation_and_admin_signup(tmp_path) -> None:
    settings = Settings(
        environment="staging",
        deployment_mode="railway",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'staging-auth.db'}",
        auth_secret_key=SecretStr("staging-test-secret-with-sufficient-entropy"),
        cors_origins="https://example-staging.up.railway.app",
        job_backend="rq",
        redis_required=True,
        embedding_provider="hashing",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app(
        settings=settings,
        rag_service=build_rag_service(settings),
        db_session_factory=session_factory,
    )

    with TestClient(app) as client:
        impersonation = client.get(
            "/api/v1/audit/export",
            headers={
                "X-Tenant-ID": "sandbox",
                "X-User-ID": "attacker",
                "X-Role-Code": "clinical_admin",
            },
        )
        signup = client.post(
            "/api/v1/auth/signup",
            json={
                "full_name": "Unauthorized Admin",
                "email": "unauthorized-admin@example.com",
                "password": "StrongPass!123",
                "confirm_password": "StrongPass!123",
                "role": "admin",
                "tenant_id": "sandbox",
            },
        )

    assert impersonation.status_code == 401
    assert signup.status_code == 403
    engine.dispose()
