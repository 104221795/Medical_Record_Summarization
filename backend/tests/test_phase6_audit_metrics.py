from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models import AuditLog
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
NURSE_HEADERS = {**HEADERS, "X-Role-Code": "nurse", "X-User-ID": "nurse-demo"}


def _create_reviewed_summaries(client: TestClient) -> tuple[str, str, str, str]:
    patient_id, encounter_id = import_patient(client)
    approved = generate_patient_snapshot(client, patient_id, encounter_id)
    rejected = generate_patient_snapshot(client, patient_id, encounter_id)

    edit_response = client.patch(
        f"/api/v1/summaries/{approved['summary_id']}/edit",
        headers=DOCTOR_HEADERS,
        json={
            "edited_summary_text": "Clinician edited text for metric calculation.",
            "edit_comment": "Metric edit.",
        },
    )
    assert edit_response.status_code == 200, edit_response.text
    approval_response = client.post(
        f"/api/v1/summaries/{approved['summary_id']}/approve",
        headers=DOCTOR_HEADERS,
        json={"approval_comment": "Reviewed and approved."},
    )
    assert approval_response.status_code == 200, approval_response.text

    rejection_response = client.post(
        f"/api/v1/summaries/{rejected['summary_id']}/reject",
        headers=DOCTOR_HEADERS,
        json={
            "rejection_reason": "wrong_citation",
            "rejection_comment": "Citation requires correction.",
        },
    )
    assert rejection_response.status_code == 200, rejection_response.text
    return patient_id, encounter_id, approved["summary_id"], rejected["summary_id"]


def test_clinical_admin_summary_quality_metrics_counts_rates_and_average(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    _create_reviewed_summaries(client)

    response = client.get("/api/v1/metrics/summary-quality", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_summaries"] == 2
    assert body["approved_count"] == 1
    assert body["rejected_count"] == 1
    assert body["approval_rate"] == 0.5
    assert body["rejection_rate"] == 0.5
    assert body["average_citation_coverage"] is not None
    assert body["average_edit_distance"] is not None
    assert body["top_rejection_reasons"] == [{"key": "wrong_citation", "count": 1}]


def test_nurse_cannot_fetch_global_metrics(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get("/api/v1/metrics/usage", headers=NURSE_HEADERS)

    assert response.status_code == 403
    assert "cannot view global metrics" in response.json()["detail"]


def test_audit_logs_filter_by_action_patient_and_detail(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, _ = import_patient(client)

    response = client.get(
        f"/api/v1/audit/logs?action=import_data&patient_id={patient_id}",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pagination"]["total_items"] == 1
    item = body["items"][0]
    assert item["action"] == "import_data"
    assert item["patient_id"] == patient_id
    assert item["created_at"]
    assert item["action_metadata"]["source_system"] == "mock_emr"

    detail = client.get(f"/api/v1/audit/logs/{item['audit_id']}", headers=ADMIN_HEADERS)
    assert detail.status_code == 200, detail.text
    assert detail.json()["audit_id"] == item["audit_id"]


def test_usage_safety_and_review_metrics_from_seeded_workflow(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    _create_reviewed_summaries(client)

    usage = client.get("/api/v1/metrics/usage", headers=ADMIN_HEADERS)
    safety = client.get("/api/v1/metrics/safety", headers=ADMIN_HEADERS)
    review = client.get("/api/v1/metrics/review", headers=ADMIN_HEADERS)

    assert usage.status_code == 200, usage.text
    assert usage.json()["total_patients"] == 1
    assert usage.json()["total_documents"] == 1
    assert usage.json()["total_document_chunks"] >= 1
    assert usage.json()["total_summaries_generated"] == 2
    assert usage.json()["model_run_count"] == 2

    assert safety.status_code == 200, safety.text
    safety_body = safety.json()
    assert safety_body["citation_coverage_average"] is not None
    assert safety_body["unsupported_claim_total"] >= 1
    assert safety_body["wrong_patient_retrieval_count"] == 0
    gate_names = {
        gate["name"]: gate
        for gate in safety_body["safety_gate_status"]["gates"]
    }
    assert gate_names["citation_coverage"]["threshold"] == 0.9
    assert gate_names["wrong_patient_retrieval"]["status"] == "pass"
    assert gate_names["encounter_scope_enforcement"]["status"] == "pass"
    assert gate_names["no_summary_auto_approval"]["status"] == "pass"

    assert review.status_code == 200, review.text
    review_body = review.json()
    assert review_body["approvals"] == 1
    assert review_body["rejections"] == 1
    assert review_body["edits"] == 1
    assert review_body["rejection_reasons_distribution"] == [
        {"key": "wrong_citation", "count": 1}
    ]


def test_metrics_handle_empty_database_gracefully(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    quality = client.get("/api/v1/metrics/summary-quality", headers=ADMIN_HEADERS)
    safety = client.get("/api/v1/metrics/safety", headers=ADMIN_HEADERS)

    assert quality.status_code == 200, quality.text
    assert quality.json()["total_summaries"] == 0
    assert quality.json()["average_citation_coverage"] is None
    assert safety.status_code == 200, safety.text
    assert safety.json()["citation_coverage_average"] is None
    assert safety.json()["safety_gate_status"]["mvp_readiness_status"] == "warning"


def test_sensitive_actions_have_audit_logs(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    patient_id, encounter_id = import_patient(client)
    approved = generate_patient_snapshot(client, patient_id, encounter_id)
    rejected = generate_patient_snapshot(client, patient_id, encounter_id)

    detail = client.get(f"/api/v1/summaries/{approved['summary_id']}", headers=DOCTOR_HEADERS)
    assert detail.status_code == 200
    citation_id = next(
        claim["citations"][0]["citation_id"]
        for section in detail.json()["sections"]
        for claim in section["claims"]
        if claim["citations"]
    )
    assert client.get(f"/api/v1/citations/{citation_id}/source", headers=DOCTOR_HEADERS).status_code == 200
    assert client.patch(
        f"/api/v1/summaries/{approved['summary_id']}/edit",
        headers=DOCTOR_HEADERS,
        json={"edited_summary_text": "Edited for audit coverage.", "edit_comment": "Audit check."},
    ).status_code == 200
    assert client.post(
        f"/api/v1/summaries/{approved['summary_id']}/approve",
        headers=DOCTOR_HEADERS,
        json={"approval_comment": "Audit check approval."},
    ).status_code == 200
    assert client.post(
        f"/api/v1/summaries/{rejected['summary_id']}/reject",
        headers=DOCTOR_HEADERS,
        json={"rejection_reason": "unsupported_claim", "rejection_comment": "Audit check rejection."},
    ).status_code == 200

    with session_factory() as session:
        actions = set(session.scalars(select(AuditLog.action)))
    assert {
        "import_data",
        "generate_summary",
        "view_summary",
        "view_citation",
        "edit_summary",
        "approve_summary",
        "reject_summary",
    }.issubset(actions)
