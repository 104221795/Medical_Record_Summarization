from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, create_session_factory
from backend.app.main import create_app
from backend.app.models import (
    AuditLog,
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    Observation,
    Patient,
)
from backend.app.services.rag import build_rag_service


HEADERS = {"X-Tenant-ID": "sandbox", "X-User-ID": "doctor-demo"}


@pytest.fixture()
def api_client(tmp_path: Path) -> tuple[TestClient, sessionmaker[Session]]:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'phase2.db'}",
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
    with TestClient(app) as client:
        yield client, session_factory
    engine.dispose()


def _fhir_like_payload() -> dict[str, object]:
    return {
        "source_system": "mock_emr",
        "ingestion_type": "fhir_like_json",
        "records": {
            "patients": [
                {
                    "resourceType": "Patient",
                    "id": "patient-001",
                    "identifier": [{"value": "MRN-DEMO-001"}],
                    "gender": "female",
                    "birthDate": "1980-01-02",
                    "is_deidentified": True,
                }
            ],
            "encounters": [
                {
                    "resourceType": "Encounter",
                    "id": "encounter-001",
                    "identifier": [{"value": "VISIT-DEMO-001"}],
                    "status": "finished",
                    "class": {"code": "AMB"},
                    "subject": {"reference": "Patient/patient-001"},
                    "period": {
                        "start": "2026-05-20T08:00:00Z",
                        "end": "2026-05-20T10:00:00Z",
                    },
                }
            ],
            "conditions": [
                {
                    "resourceType": "Condition",
                    "id": "condition-001",
                    "subject": {"reference": "Patient/patient-001"},
                    "encounter": {"reference": "Encounter/encounter-001"},
                    "code": {"text": "Source-recorded condition"},
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                }
            ],
            "observations": [
                {
                    "resourceType": "Observation",
                    "id": "observation-001",
                    "subject": {"reference": "Patient/patient-001"},
                    "encounter": {"reference": "Encounter/encounter-001"},
                    "code": {"text": "Blood pressure"},
                    "valueString": "128/78 mmHg",
                    "category": [{"coding": [{"code": "vital-signs"}]}],
                }
            ],
            "medications": [
                {
                    "resourceType": "MedicationStatement",
                    "id": "medication-001",
                    "subject": {"reference": "Patient/patient-001"},
                    "encounter": {"reference": "Encounter/encounter-001"},
                    "medicationCodeableConcept": {"text": "Source-recorded medication"},
                    "status": "active",
                }
            ],
            "diagnostic_reports": [
                {
                    "resourceType": "DiagnosticReport",
                    "id": "report-001",
                    "subject": {"reference": "Patient/patient-001"},
                    "encounter": {"reference": "Encounter/encounter-001"},
                    "status": "final",
                    "code": {"text": "Source diagnostic report"},
                    "conclusion": "Source-reported result without generated interpretation.",
                }
            ],
            "documents": [
                {
                    "resourceType": "DocumentReference",
                    "id": "document-001",
                    "identifier": [{"value": "NOTE-DEMO-001"}],
                    "subject": {"reference": "Patient/patient-001"},
                    "context": {
                        "encounter": [{"reference": "Encounter/encounter-001"}]
                    },
                    "type": {"text": "Progress Note"},
                    "date": "2026-05-20T09:00:00Z",
                    "raw_text": (
                        "ASSESSMENT:\nPatient reports fatigue.\n\n"
                        "VITALS:\nBlood pressure recorded as 128/78 mmHg."
                    ),
                }
            ],
        },
    }


def test_import_and_query_persisted_clinical_records(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client

    imported = client.post(
        "/api/v1/ingestion/import", headers=HEADERS, json=_fhir_like_payload()
    )

    assert imported.status_code == 201
    import_body = imported.json()
    assert import_body["status"] == "completed"
    assert import_body["total_records"] == 7
    assert import_body["accepted_records"] == 7
    assert import_body["failed_records"] == 0
    assert import_body["chunks_created"] >= 1
    uuid.UUID(import_body["ingestion_batch_id"])

    patients = client.get("/api/v1/patients", headers=HEADERS).json()
    assert patients["pagination"]["total_items"] == 1
    patient_id = patients["items"][0]["patient_id"]

    patient = client.get(f"/api/v1/patients/{patient_id}", headers=HEADERS)
    assert patient.status_code == 200
    assert patient.json()["fhir_patient_id"] == "patient-001"
    assert patient.json()["external_patient_id"] == "MRN-DEMO-001"

    encounters = client.get(
        f"/api/v1/patients/{patient_id}/encounters", headers=HEADERS
    ).json()
    assert len(encounters["items"]) == 1
    encounter_id = encounters["items"][0]["encounter_id"]
    encounter = client.get(f"/api/v1/encounters/{encounter_id}", headers=HEADERS)
    assert encounter.status_code == 200
    assert encounter.json()["fhir_encounter_id"] == "encounter-001"

    documents = client.get(
        f"/api/v1/patients/{patient_id}/documents", headers=HEADERS
    ).json()
    assert len(documents["items"]) == 1
    document_id = documents["items"][0]["document_id"]
    document = client.get(f"/api/v1/documents/{document_id}", headers=HEADERS)
    assert document.status_code == 200
    assert document.json()["fhir_document_reference_id"] == "document-001"
    assert "ASSESSMENT" in document.json()["raw_text"]

    chunks = client.get(
        f"/api/v1/documents/{document_id}/chunks", headers=HEADERS
    ).json()
    assert len(chunks["items"]) >= 1
    assert all(item["chunk_hash"] for item in chunks["items"])
    assert all(item["token_count"] > 0 for item in chunks["items"])

    audit = client.get(
        "/api/v1/audit/logs?action=import_data", headers=HEADERS
    ).json()
    assert audit["pagination"]["total_items"] == 1
    assert audit["items"][0]["action"] == "import_data"
    assert audit["items"][0]["metadata"]["source_system"] == "mock_emr"

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Condition)) == 1
        assert session.scalar(select(func.count()).select_from(Observation)) == 1
        assert session.scalar(select(func.count()).select_from(Medication)) == 1
        assert (
            session.scalar(select(func.count()).select_from(DiagnosticReport)) == 1
        )


def test_ingestion_is_idempotent_for_source_ids_and_document_hash(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client

    first = client.post(
        "/api/v1/ingestion/import", headers=HEADERS, json=_fhir_like_payload()
    )
    second = client.post(
        "/api/v1/ingestion/import", headers=HEADERS, json=_fhir_like_payload()
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["accepted_records"] == 0
    assert second.json()["skipped_duplicates"] == 7

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Patient)) == 1
        assert session.scalar(select(func.count()).select_from(Encounter)) == 1
        assert session.scalar(select(func.count()).select_from(ClinicalDocument)) == 1
        assert session.scalar(select(func.count()).select_from(DocumentChunk)) >= 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "import_data")
            )
            == 2
        )


def test_rejects_missing_patient_reference_without_partial_write(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    payload = {
        "source_system": "mock_emr",
        "documents": [
            {
                "resourceType": "Composition",
                "id": "unknown-patient-document",
                "subject": {"reference": "Patient/missing"},
                "document_type": "discharge_summary",
                "raw_text": "Imported source document.",
            }
        ],
    }

    response = client.post("/api/v1/ingestion/import", headers=HEADERS, json=payload)

    assert response.status_code == 422
    assert "Patient/missing" in response.json()["detail"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ClinicalDocument)) == 0
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_rejects_encounter_assigned_to_wrong_patient_atomically(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    assert (
        client.post(
            "/api/v1/ingestion/import", headers=HEADERS, json=_fhir_like_payload()
        ).status_code
        == 201
    )
    wrong_patient_payload = {
        "source_system": "mock_emr",
        "patients": [
            {
                "resourceType": "Patient",
                "id": "patient-002",
                "identifier": [{"value": "MRN-DEMO-002"}],
                "is_deidentified": True,
            }
        ],
        "documents": [
            {
                "resourceType": "DocumentReference",
                "id": "document-wrong-reference",
                "subject": {"reference": "Patient/patient-002"},
                "context": {
                    "encounter": [{"reference": "Encounter/encounter-001"}]
                },
                "type": {"text": "Progress Note"},
                "raw_text": "Should not persist.",
            }
        ],
    }

    response = client.post(
        "/api/v1/ingestion/import", headers=HEADERS, json=wrong_patient_payload
    )

    assert response.status_code == 422
    assert "different patient" in response.json()["detail"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Patient)) == 1
        assert session.scalar(select(func.count()).select_from(ClinicalDocument)) == 1


def test_rejects_import_payload_without_any_resources(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.post(
        "/api/v1/ingestion/import",
        headers=HEADERS,
        json={"source_system": "mock_emr", "records": {}},
    )

    assert response.status_code == 422
