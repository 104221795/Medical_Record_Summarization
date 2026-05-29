from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from backend.tests.summary_test_utils import (
    HEADERS,
    api_client,
    generate_patient_snapshot,
    import_patient,
)


def test_claim_citation_and_source_apis_return_same_patient_evidence(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, encounter_id = import_patient(client)
    generated = generate_patient_snapshot(client, patient_id, encounter_id)
    detail = client.get(
        f"/api/v1/summaries/{generated['summary_id']}", headers=HEADERS
    ).json()
    supported_claim = next(
        claim
        for section in detail["sections"]
        for claim in section["claims"]
        if claim["support_status"] == "supported" and claim["citation_count"] > 0
    )

    citations_response = client.get(
        f"/api/v1/claims/{supported_claim['claim_id']}/citations",
        headers=HEADERS,
    )
    assert citations_response.status_code == 200
    citations = citations_response.json()
    assert citations["claim_id"] == supported_claim["claim_id"]
    assert citations["citations"]

    citation_id = citations["citations"][0]["citation_id"]
    source_response = client.get(
        f"/api/v1/citations/{citation_id}/source",
        headers=HEADERS,
    )
    assert source_response.status_code == 200
    source = source_response.json()
    assert source["citation_id"] == citation_id
    assert source["claim_id"] == supported_claim["claim_id"]
    assert source["patient_id"] == patient_id
    assert source["highlighted_span"] is not None
    if source["surrounding_context"] and source["highlighted_span"]["text"]:
        assert source["highlighted_span"]["text"] in source["surrounding_context"]
    assert source["source_type"]


def test_citation_source_view_creates_audit_log(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, encounter_id = import_patient(client)
    generated = generate_patient_snapshot(client, patient_id, encounter_id)
    detail = client.get(
        f"/api/v1/summaries/{generated['summary_id']}", headers=HEADERS
    ).json()
    citation_id = next(
        claim["citations"][0]["citation_id"]
        for section in detail["sections"]
        for claim in section["claims"]
        if claim["citations"]
    )

    assert client.get(f"/api/v1/citations/{citation_id}/source", headers=HEADERS).status_code == 200
    audit = client.get("/api/v1/audit/logs?action=view_citation", headers=HEADERS)

    assert audit.status_code == 200
    assert audit.json()["pagination"]["total_items"] == 1
