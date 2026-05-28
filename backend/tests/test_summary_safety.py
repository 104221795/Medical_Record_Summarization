from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from backend.tests.summary_test_utils import (
    HEADERS,
    api_client,
    fhir_like_payload,
    generate_patient_snapshot,
    import_patient,
)


def test_missing_diagnosis_and_medication_are_not_invented_and_single_lab_has_no_trend(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, encounter_id = import_patient(
        client,
        fhir_like_payload(
            include_conditions=False,
            include_medications=False,
            include_reports=False,
            observation_count=1,
            document_text="COURSE:\nPatient reports fatigue. No diagnosis or medication is listed.",
        ),
    )

    generated = generate_patient_snapshot(client, patient_id, encounter_id)
    detail = client.get(
        f"/api/v1/summaries/{generated['summary_id']}", headers=HEADERS
    ).json()
    claims = [
        claim
        for section in detail["sections"]
        for claim in section["claims"]
    ]

    assert not [
        claim
        for claim in claims
        if claim["claim_type"] == "diagnosis" and claim["support_status"] == "supported"
    ]
    assert not [
        claim
        for claim in claims
        if claim["claim_type"] == "medication" and claim["support_status"] == "supported"
    ]
    claim_text = " ".join(claim["claim_text"].casefold() for claim in claims)
    forbidden_trend_words = ["trend", "increased", "decreased", "xu hướng", "tăng", "giảm"]
    assert all(word not in claim_text for word in forbidden_trend_words)
    unsupported = [
        claim
        for claim in claims
        if claim["support_status"] in {"unsupported", "insufficient_evidence"}
    ]
    assert unsupported
    assert all(claim["citation_count"] == 0 for claim in unsupported)
    assert detail["status"] == "draft"
    assert detail["generated_at"]


def test_summary_is_never_auto_approved(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, encounter_id = import_patient(client)

    generated = generate_patient_snapshot(client, patient_id, encounter_id)
    detail = client.get(
        f"/api/v1/summaries/{generated['summary_id']}", headers=HEADERS
    ).json()

    assert generated["status"] == "draft"
    assert detail["status"] == "draft"
    assert detail["safety_summary"]["conflict_count"] == 0
