from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, create_session_factory
from backend.app.main import create_app
from backend.app.models import AuditLog, ModelRun, Summary, SummaryStatus
from backend.app.services.rag import build_rag_service
from backend.app.services.summary_providers import ProviderOutput, SummaryProvider
from backend.tests.summary_test_utils import HEADERS, api_client, import_patient


class FakePersistedProvider(SummaryProvider):
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.model_name = f"mock-{provider_name}"
        self.model_version = "test-1.0"
        self.calls: list[dict[str, Any]] = []

    def generate_summary(
        self,
        *,
        patient,
        encounter,
        context,
        evidence_pack,
        summary_type,
        language,
        options,
    ) -> ProviderOutput:
        self.calls.append(
            {
                "patient_id": str(patient.patient_id),
                "encounter_id": str(encounter.encounter_id) if encounter else None,
                "evidence_count": len(evidence_pack["evidence"]),
                "summary_type": summary_type,
                "language": language,
                "options": dict(options),
            }
        )
        return ProviderOutput(
            provider=self.provider_name,
            model_name=self.model_name,
            model_version=self.model_version,
            summary_text=(
                "Patient reports fatigue during the visit. "
                "The patient should start aspirin."
            ),
            latency_ms=17,
            raw_output={"mocked": True},
        )


def _build_provider_app(tmp_path: Path, provider: SummaryProvider | None = None):
    settings = Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'providers.db'}",
        qdrant_path=tmp_path / "qdrant",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app(
        settings=settings,
        rag_service=build_rag_service(settings),
        db_session_factory=session_factory,
    )
    if provider is not None:
        app.state.summary_model_providers = {provider.provider_name: provider}
    return app, session_factory, engine


@pytest.mark.parametrize("provider_name", ["bart", "pegasus"])
def test_bart_and_pegasus_generate_persisted_draft_with_citations_and_safety(
    tmp_path: Path,
    provider_name: str,
) -> None:
    provider = FakePersistedProvider(provider_name)
    app, session_factory, engine = _build_provider_app(tmp_path, provider)
    try:
        with TestClient(app) as client:
            patient_id, encounter_id = import_patient(client)
            response = client.post(
                f"/api/v1/patients/{patient_id}/summaries/generate",
                headers=HEADERS,
                json={
                    "encounter_id": encounter_id,
                    "summary_type": "patient_snapshot",
                    "language": "vi",
                    "model_provider": provider_name,
                    "options": {"require_citations": True, "include_safety_check": True},
                },
            )

            assert response.status_code == 201, response.text
            generated = response.json()
            assert generated["status"] == "draft"
            assert generated["model_provider"] == provider_name
            assert generated["model_name"] == f"mock-{provider_name}"
            assert generated["latency_ms"] == 17
            assert generated["unsupported_claim_count"] >= 1
            assert provider.calls and provider.calls[0]["evidence_count"] > 0

            detail_response = client.get(
                f"/api/v1/summaries/{generated['summary_id']}",
                headers=HEADERS,
            )
            assert detail_response.status_code == 200
            detail = detail_response.json()
            assert detail["model_provider"] == provider_name
            assert detail["model_name"] == f"mock-{provider_name}"
            assert "Generated Summary" in [section["section_title"] for section in detail["sections"]]
            claims = [
                claim
                for section in detail["sections"]
                for claim in section["claims"]
            ]
            supported = [claim for claim in claims if claim["support_status"] == "supported"]
            unsupported = [
                claim
                for claim in claims
                if claim["support_status"] in {"unsupported", "insufficient_evidence"}
            ]
            assert supported
            assert all(claim["citation_count"] >= 1 for claim in supported)
            assert any("should start aspirin" in claim["claim_text"] for claim in unsupported)

            citation_id = supported[0]["citations"][0]["citation_id"]
            source_response = client.get(
                f"/api/v1/citations/{citation_id}/source",
                headers=HEADERS,
            )
            assert source_response.status_code == 200
            assert source_response.json()["patient_id"] == patient_id

        with session_factory() as session:
            summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
            assert summary is not None
            assert summary.status == SummaryStatus.DRAFT
            assert summary.approved_at is None
            model_run = session.get(ModelRun, summary.model_run_id)
            assert model_run is not None
            assert model_run.provider == provider_name
            assert model_run.model_name == f"mock-{provider_name}"
            assert model_run.prompt_template_id == f"{provider_name}_text_normalizer"
            audit = session.scalar(
                select(AuditLog).where(AuditLog.action == "generate_summary")
            )
            assert audit is not None
            assert audit.metadata_json["provider"] == provider_name
    finally:
        engine.dispose()


def test_deterministic_model_provider_remains_safe_default(api_client) -> None:
    client, session_factory = api_client
    patient_id, encounter_id = import_patient(client)

    response = client.post(
        f"/api/v1/patients/{patient_id}/summaries/generate",
        headers=HEADERS,
        json={
            "encounter_id": encounter_id,
            "summary_type": "patient_snapshot",
            "language": "vi",
            "model_provider": "deterministic",
        },
    )

    assert response.status_code == 201, response.text
    generated = response.json()
    assert generated["status"] == "draft"
    assert generated["model_provider"] == "deterministic"

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None
        model_run = session.get(ModelRun, summary.model_run_id)
        assert model_run is not None
        assert model_run.provider == "local"


def test_real_bart_provider_is_disabled_without_explicit_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RUN_REAL_BASELINES", raising=False)
    monkeypatch.delenv("RAG_RUN_REAL_BASELINES", raising=False)
    app, _session_factory, engine = _build_provider_app(tmp_path)
    try:
        with TestClient(app) as client:
            patient_id, encounter_id = import_patient(client)
            response = client.post(
                f"/api/v1/patients/{patient_id}/summaries/generate",
                headers=HEADERS,
                json={
                    "encounter_id": encounter_id,
                    "summary_type": "patient_snapshot",
                    "language": "vi",
                    "model_provider": "bart",
                },
            )

            assert response.status_code == 422
            assert "RUN_REAL_BASELINES=1" in response.json()["detail"]
    finally:
        engine.dispose()


def test_invalid_model_provider_returns_validation_error(api_client) -> None:
    client, _session_factory = api_client
    patient_id, encounter_id = import_patient(client)

    response = client.post(
        f"/api/v1/patients/{patient_id}/summaries/generate",
        headers=HEADERS,
        json={
            "encounter_id": encounter_id,
            "summary_type": "patient_snapshot",
            "language": "vi",
            "model_provider": "llama",
        },
    )

    assert response.status_code == 422
