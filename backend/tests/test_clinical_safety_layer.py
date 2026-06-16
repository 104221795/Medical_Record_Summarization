from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models import (
    ClaimCitation,
    ClinicalDocument,
    Condition,
    DiagnosticReport,
    DocumentChunk,
    Encounter,
    Medication,
    Observation,
    Patient,
    Summary,
)
from backend.app.repositories import AuditRepository
from backend.app.services.audit_service import AuditService
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


def test_audit_metadata_is_phi_safe_and_exportable(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    with session_factory() as session:
        AuditService(AuditRepository(session)).record(
            action="unsafe_metadata_test",
            resource_type="clinical_safety_test",
            metadata={
                "raw_text": "SECRET RAW NOTE SHOULD NOT BE STORED",
                "approval_comment": "Free text may contain PHI.",
                "nested": {
                    "source_note": "SECRET NESTED NOTE SHOULD NOT BE STORED",
                    "safe_key": "safe value",
                },
                "long_value": "x" * 700,
                "safe_identifier": "case-001",
            },
        )
        session.commit()

    response = client.get(
        "/api/v1/audit/export?action=unsafe_metadata_test",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phi_safe"] is True
    assert body["row_count"] == 1
    metadata = body["items"][0]["metadata"]
    assert "raw_text" not in metadata
    assert "approval_comment" not in metadata
    assert metadata["nested"] == {"safe_key": "safe value"}
    assert metadata["long_value"] == "[redacted:long_text]"
    assert metadata["safe_identifier"] == "case-001"
    assert "SECRET" not in response.text


def test_doctor_role_cannot_export_audit_logs(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get("/api/v1/audit/export", headers=DOCTOR_HEADERS)

    assert response.status_code == 403


def test_approval_blocks_wrong_patient_citation_scope(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    patient_id, encounter_id = import_patient(client)
    generated = generate_patient_snapshot(client, patient_id, encounter_id)

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None
        other_patient = Patient(
            external_patient_id=f"OTHER-{uuid.uuid4()}",
            patient_hash=f"OTHER-HASH-{uuid.uuid4()}",
            gender="unknown",
            is_deidentified=True,
        )
        session.add(other_patient)
        session.flush()
        citation = _first_citation(summary)
        assert citation is not None
        assert _move_citation_source_to_patient(session, citation, other_patient)
        session.commit()

    response = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/approve",
        headers=DOCTOR_HEADERS,
        json={"approval_comment": "This should be blocked by citation scope validation."},
    )

    assert response.status_code == 409, response.text
    assert "citation source scope validation failed" in response.json()["detail"]

    safety = client.get("/api/v1/metrics/safety", headers=ADMIN_HEADERS)
    assert safety.status_code == 200, safety.text
    assert safety.json()["wrong_patient_retrieval_count"] >= 1


def _first_citation(summary: Summary) -> ClaimCitation | None:
    for claim in summary.claims:
        if claim.citations:
            return claim.citations[0]
    return None


def _move_citation_source_to_patient(
    session: Session,
    citation: ClaimCitation,
    patient: Patient,
) -> bool:
    if citation.source_chunk_id:
        source = session.get(DocumentChunk, citation.source_chunk_id)
        if source:
            source.patient_id = patient.patient_id
            return True
    if citation.source_document_id:
        source = session.get(ClinicalDocument, citation.source_document_id)
        if source:
            source.patient_id = patient.patient_id
            return True
    if citation.source_condition_id:
        source = session.get(Condition, citation.source_condition_id)
        if source:
            source.patient_id = patient.patient_id
            return True
    if citation.source_observation_id:
        source = session.get(Observation, citation.source_observation_id)
        if source:
            source.patient_id = patient.patient_id
            return True
    if citation.source_medication_id:
        source = session.get(Medication, citation.source_medication_id)
        if source:
            source.patient_id = patient.patient_id
            return True
    if citation.source_report_id:
        source = session.get(DiagnosticReport, citation.source_report_id)
        if source:
            source.patient_id = patient.patient_id
            return True
    if citation.source_record_type == "patient":
        citation.source_record_id = patient.patient_id
        return True
    if citation.source_record_type == "encounter":
        encounter = Encounter(
            patient_id=patient.patient_id,
            external_encounter_id=f"OTHER-VISIT-{uuid.uuid4()}",
            encounter_type="outpatient",
            status="finished",
        )
        session.add(encounter)
        session.flush()
        citation.source_record_id = encounter.encounter_id
        return True
    return False
