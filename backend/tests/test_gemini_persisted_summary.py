from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, create_session_factory
from backend.app.main import create_app
from backend.app.models import AuditLog, ModelRun, Summary, SummaryStatus
from backend.app.services.rag import build_rag_service
from backend.tests.summary_test_utils import (
    HEADERS,
    api_client,
    fhir_like_payload,
    import_patient,
)


class FakeGeminiJsonClient:
    def __init__(self, mode: str = "valid"):
        self.mode = mode
        self.calls: list[dict[str, object]] = []

    def generate_json(
        self,
        *,
        system_instruction: str,
        user_text: str,
        output_schema: dict,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append(
            {
                "system_instruction": system_instruction,
                "user_text": user_text,
                "output_schema": output_schema,
                "temperature": temperature,
            }
        )
        if self.mode == "invalid_json":
            return "not-json"

        source_ids = re.findall(r'"source_id":\s*"([^"]+)"', user_text)

        def first(prefix: str) -> str:
            return next(source_id for source_id in source_ids if source_id.startswith(prefix))

        patient_id = first("patient:")
        condition_id = first("condition:")
        chunk_id = first("chunk:")
        medication_id = first("medication:")
        observation_id = first("observation:")
        report_id = first("diagnostic_report:")
        active_problem_citations = (
            ["condition:does-not-exist"] if self.mode == "bad_citation" else [condition_id]
        )
        return json.dumps(
            {
                "summary_type": "patient_snapshot",
                "language": "vi",
                "requires_clinician_review": True,
                "sections": [
                    {
                        "section_title": "Patient Snapshot",
                        "section_type": "patient_snapshot",
                        "section_order": 1,
                        "claims": [
                            {
                                "claim_text": "Gemini used the provided patient record for context.",
                                "claim_type": "general",
                                "support_status": "supported",
                                "citation_ids": [patient_id],
                                "clinical_risk_level": "low",
                                "confidence_score": 0.9,
                            }
                        ],
                    },
                    {
                        "section_title": "Active Problems",
                        "section_type": "active_problems",
                        "section_order": 2,
                        "claims": [
                            {
                                "claim_text": "Source records include one active problem.",
                                "claim_type": "diagnosis",
                                "support_status": "supported",
                                "citation_ids": active_problem_citations,
                                "clinical_risk_level": "high",
                                "confidence_score": 0.9,
                            }
                        ],
                    },
                    {
                        "section_title": "Recent Clinical Course",
                        "section_type": "recent_clinical_course",
                        "section_order": 3,
                        "claims": [
                            {
                                "claim_text": "A recent clinical note describes the visit course.",
                                "claim_type": "timeline_event",
                                "support_status": "supported",
                                "citation_ids": [chunk_id],
                                "clinical_risk_level": "medium",
                                "confidence_score": 0.88,
                            }
                        ],
                    },
                    {
                        "section_title": "Medications",
                        "section_type": "medications",
                        "section_order": 4,
                        "claims": [
                            {
                                "claim_text": "Medication data is present in the source record.",
                                "claim_type": "medication",
                                "support_status": "supported",
                                "citation_ids": [medication_id],
                                "clinical_risk_level": "critical",
                                "confidence_score": 0.9,
                            }
                        ],
                    },
                    {
                        "section_title": "Labs and Imaging Highlights",
                        "section_type": "labs_imaging",
                        "section_order": 5,
                        "claims": [
                            {
                                "claim_text": "A creatinine observation is present in the source record.",
                                "claim_type": "lab_result",
                                "support_status": "supported",
                                "citation_ids": [observation_id],
                                "clinical_risk_level": "high",
                                "confidence_score": 0.9,
                            },
                            {
                                "claim_text": "A diagnostic report conclusion is present.",
                                "claim_type": "imaging_finding",
                                "support_status": "supported",
                                "citation_ids": [report_id],
                                "clinical_risk_level": "high",
                                "confidence_score": 0.9,
                            },
                        ],
                    },
                    {
                        "section_title": "Needs Clinician Review",
                        "section_type": "needs_clinician_review",
                        "section_order": 6,
                        "claims": [
                            {
                                "claim_text": "Allergy information is not found in the current record.",
                                "claim_type": "missing_information",
                                "support_status": "insufficient_evidence",
                                "citation_ids": [],
                                "clinical_risk_level": "low",
                                "confidence_score": 0,
                            }
                        ],
                    },
                ],
                "safety_notes": [
                    "AI-generated draft requires doctor review before clinical use."
                ],
            }
        )


def _build_gemini_app(tmp_path: Path, fake_client: FakeGeminiJsonClient):
    settings = Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'gemini.db'}",
        qdrant_path=tmp_path / "qdrant",
        llm_provider="gemini",
        llm_external_enabled=True,
        llm_allow_phi_external=True,
        gemini_api_key="fake-key",
        gemini_model="gemini-test-model",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app(
        settings=settings,
        rag_service=build_rag_service(settings),
        db_session_factory=session_factory,
    )
    app.state.gemini_json_client = fake_client
    return app, session_factory, engine


def _generate_with_gemini(client: TestClient, patient_id: str, encounter_id: str) -> dict:
    response = client.post(
        f"/api/v1/patients/{patient_id}/summaries/generate",
        headers=HEADERS,
        json={
            "encounter_id": encounter_id,
            "summary_type": "patient_snapshot",
            "language": "vi",
            "provider": "gemini",
            "options": {"require_citations": True, "include_safety_check": True},
        },
    )
    return {"status_code": response.status_code, "body": response.json()}


def test_gemini_requires_explicit_external_governance_flags(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="RAG_LLM_EXTERNAL_ENABLED=true"):
        Settings(
            environment="test",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'blocked.db'}",
            qdrant_path=tmp_path / "qdrant",
            llm_provider="gemini",
            gemini_api_key="fake-key",
        )


def test_endpoint_rejects_gemini_when_provider_is_not_enabled(api_client) -> None:
    client, _session_factory = api_client
    patient_id, encounter_id = import_patient(client)

    response = client.post(
        f"/api/v1/patients/{patient_id}/summaries/generate",
        headers=HEADERS,
        json={
            "encounter_id": encounter_id,
            "summary_type": "patient_snapshot",
            "language": "vi",
            "provider": "gemini",
        },
    )

    assert response.status_code == 422
    assert "RAG_LLM_PROVIDER=gemini" in response.json()["detail"]


def test_gemini_generation_persists_draft_claims_citations_model_run_and_audit(
    tmp_path: Path,
) -> None:
    fake_client = FakeGeminiJsonClient()
    app, session_factory, engine = _build_gemini_app(tmp_path, fake_client)
    try:
        with TestClient(app) as client:
            patient_id, encounter_id = import_patient(client)
            generated = _generate_with_gemini(client, patient_id, encounter_id)

            assert generated["status_code"] == 201, generated["body"]
            body = generated["body"]
            assert body["status"] == "draft"
            assert body["unsupported_claim_count"] >= 1
            assert fake_client.calls
            assert "Evidence pack JSON" in fake_client.calls[0]["user_text"]

            detail_response = client.get(
                f"/api/v1/summaries/{body['summary_id']}",
                headers=HEADERS,
            )
            assert detail_response.status_code == 200
            claims = [
                claim
                for section in detail_response.json()["sections"]
                for claim in section["claims"]
            ]
            supported_claims = [
                claim for claim in claims if claim["support_status"] == "supported"
            ]
            assert supported_claims
            assert all(claim["citation_count"] >= 1 for claim in supported_claims)

        with session_factory() as session:
            summary = session.get(Summary, uuid.UUID(body["summary_id"]))
            assert summary is not None
            assert summary.status == SummaryStatus.DRAFT
            assert summary.approved_at is None
            model_run = session.get(ModelRun, summary.model_run_id)
            assert model_run is not None
            assert model_run.provider == "gemini"
            assert model_run.model_name == "gemini-test-model"
            assert model_run.prompt_template_id == "patient_snapshot_vi"
            assert model_run.prompt_version == "1.0.0"
            assert model_run.context_hash
            assert model_run.output_hash
            assert model_run.run_metadata["requires_deidentified_or_governed_data"] is True
            audit = session.scalar(
                select(AuditLog).where(AuditLog.action == "generate_summary")
            )
            assert audit is not None
            assert audit.metadata_json["provider"] == "gemini"
    finally:
        engine.dispose()


def test_invalid_gemini_json_fails_safely_without_summary(tmp_path: Path) -> None:
    fake_client = FakeGeminiJsonClient(mode="invalid_json")
    app, session_factory, engine = _build_gemini_app(tmp_path, fake_client)
    try:
        with TestClient(app) as client:
            patient_id, encounter_id = import_patient(client)
            generated = _generate_with_gemini(client, patient_id, encounter_id)

            assert generated["status_code"] == 422
            assert "invalid structured JSON" in generated["body"]["detail"]

        with session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Summary)) == 0
    finally:
        engine.dispose()


def test_gemini_supported_claim_with_unknown_citation_is_downgraded(
    tmp_path: Path,
) -> None:
    fake_client = FakeGeminiJsonClient(mode="bad_citation")
    app, _session_factory, engine = _build_gemini_app(tmp_path, fake_client)
    try:
        with TestClient(app) as client:
            patient_id, encounter_id = import_patient(client, fhir_like_payload())
            generated = _generate_with_gemini(client, patient_id, encounter_id)

            assert generated["status_code"] == 201, generated["body"]
            detail = client.get(
                f"/api/v1/summaries/{generated['body']['summary_id']}",
                headers=HEADERS,
            ).json()
            needs_review = next(
                section
                for section in detail["sections"]
                if section["section_type"] == "needs_clinician_review"
            )
            downgraded_claim = next(
                claim
                for claim in needs_review["claims"]
                if claim["claim_text"] == "Source records include one active problem."
            )
            assert downgraded_claim["support_status"] == "insufficient_evidence"
            assert downgraded_claim["citation_count"] == 0
    finally:
        engine.dispose()
