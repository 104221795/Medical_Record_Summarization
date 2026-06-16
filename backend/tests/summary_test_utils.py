from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, create_session_factory
from backend.app.main import create_app
from backend.app.services.rag import build_rag_service


HEADERS = {"X-Tenant-ID": "sandbox", "X-User-ID": "doctor-demo"}


@pytest.fixture()
def api_client(tmp_path: Path) -> tuple[TestClient, sessionmaker[Session]]:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'phase3.db'}",
        qdrant_path=tmp_path / "qdrant",
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
        yield client, session_factory
    engine.dispose()


def fhir_like_payload(
    *,
    include_conditions: bool = True,
    include_medications: bool = True,
    include_reports: bool = True,
    observation_count: int = 1,
    document_text: str | None = None,
) -> dict[str, object]:
    observations = [
        {
            "resourceType": "Observation",
            "id": f"observation-{index + 1:03d}",
            "subject": {"reference": "Patient/patient-001"},
            "encounter": {"reference": "Encounter/encounter-001"},
            "code": {"text": "Creatinine"},
            "valueQuantity": {"value": 1.2 + index, "unit": "mg/dL"},
            "category": [{"coding": [{"code": "laboratory"}]}],
            "effectiveDateTime": f"2026-05-2{index}T08:00:00Z",
        }
        for index in range(observation_count)
    ]
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
                    "period": {"start": "2026-05-20T08:00:00Z"},
                    "reasonCode": {"text": "Source-recorded visit reason"},
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
            ]
            if include_conditions
            else [],
            "observations": observations,
            "medications": [
                {
                    "resourceType": "MedicationStatement",
                    "id": "medication-001",
                    "subject": {"reference": "Patient/patient-001"},
                    "encounter": {"reference": "Encounter/encounter-001"},
                    "medicationCodeableConcept": {"text": "Source-recorded medication"},
                    "dosageInstruction": [{"text": "source-recorded dosage"}],
                    "status": "active",
                }
            ]
            if include_medications
            else [],
            "diagnostic_reports": [
                {
                    "resourceType": "DiagnosticReport",
                    "id": "report-001",
                    "subject": {"reference": "Patient/patient-001"},
                    "encounter": {"reference": "Encounter/encounter-001"},
                    "status": "final",
                    "code": {"text": "Source diagnostic report"},
                    "conclusion": "Source report conclusion.",
                }
            ]
            if include_reports
            else [],
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
                    "raw_text": document_text
                    or (
                        "COURSE:\nPatient reports fatigue during the visit.\n\n"
                        "VITALS:\nBlood pressure was recorded by source staff."
                    ),
                }
            ],
        },
    }


def import_patient(client: TestClient, payload: dict[str, object] | None = None) -> tuple[str, str]:
    response = client.post(
        "/api/v1/ingestion/import",
        headers=HEADERS,
        json=payload or fhir_like_payload(),
    )
    assert response.status_code == 201, response.text
    patients = client.get("/api/v1/patients", headers=HEADERS)
    assert patients.status_code == 200
    patient_id = patients.json()["items"][0]["patient_id"]
    encounters = client.get(f"/api/v1/patients/{patient_id}/encounters", headers=HEADERS)
    assert encounters.status_code == 200
    encounter_id = encounters.json()["items"][0]["encounter_id"]
    return patient_id, encounter_id


def generate_patient_snapshot(client: TestClient, patient_id: str, encounter_id: str | None = None) -> dict:
    response = client.post(
        f"/api/v1/patients/{patient_id}/summaries/generate",
        headers=HEADERS,
        json={
            "encounter_id": encounter_id,
            "summary_type": "patient_snapshot",
            "language": "vi",
            "options": {"require_citations": True, "include_safety_check": True},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
