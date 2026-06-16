from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models import AuditLog, Summary, SummaryReview, SummaryStatus
from backend.tests.summary_test_utils import (
    HEADERS,
    api_client,
    generate_patient_snapshot,
    import_patient,
)


DOCTOR_HEADERS = {**HEADERS, "X-Role-Code": "doctor"}


def _generate_summary(client: TestClient) -> dict:
    patient_id, encounter_id = import_patient(client)
    return generate_patient_snapshot(client, patient_id, encounter_id)


def test_start_review_from_draft_summary(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    generated = _generate_summary(client)

    response = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/review/start",
        headers=DOCTOR_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["previous_status"] == "draft"
    assert body["status"] == "under_review"
    assert body["reviewed_by"]

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None and summary.status == SummaryStatus.UNDER_REVIEW
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "start_review",
                    AuditLog.resource_id == summary.summary_id,
                )
            )
            == 1
        )


def test_edit_summary_preserves_original_and_records_review(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    generated = _generate_summary(client)
    edited_text = "Clinician-edited summary text. Citations reviewed before save."

    response = client.patch(
        f"/api/v1/summaries/{generated['summary_id']}/edit",
        headers=DOCTOR_HEADERS,
        json={
            "edited_summary_text": edited_text,
            "edit_comment": "Corrected wording for readability.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "edited"
    assert body["edit_distance_score"] is not None
    assert body["edit_diff"]
    assert body["edit_diff_summary"]["changed_segments"] >= 1
    assert body["citation_revalidation_required"] is True

    detail = client.get(
        f"/api/v1/summaries/{generated['summary_id']}", headers=DOCTOR_HEADERS
    ).json()
    assert detail["latest_edited_summary_text"] == edited_text
    assert detail["citation_revalidation_required"] is True

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None
        assert summary.summary_text != edited_text
        review = session.scalar(
            select(SummaryReview).where(SummaryReview.summary_id == summary.summary_id)
        )
        assert review is not None
        assert review.edited_summary_text == edited_text
        assert review.edit_distance_score is not None


def test_approve_summary_and_lock_from_normal_editing(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    generated = _generate_summary(client)

    approval = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/approve",
        headers=DOCTOR_HEADERS,
        json={"approval_comment": "Reviewed and approved for clinician workflow use."},
    )

    assert approval.status_code == 200, approval.text
    approved = approval.json()
    assert approved["status"] == "approved"
    assert approved["approved_by"]
    assert approved["approved_at"]

    edit_after_approval = client.patch(
        f"/api/v1/summaries/{generated['summary_id']}/edit",
        headers=DOCTOR_HEADERS,
        json={"edited_summary_text": "Late edit.", "edit_comment": "Should fail."},
    )
    assert edit_after_approval.status_code == 409

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None and summary.status == SummaryStatus.APPROVED
        assert summary.approved_by is not None
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "approve_summary",
                    AuditLog.resource_id == summary.summary_id,
                )
            )
            == 1
        )
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "approve_summary",
                AuditLog.resource_id == summary.summary_id,
            )
        )
        assert audit is not None
        assert audit.metadata_json["summary_id"] == generated["summary_id"]
        assert audit.metadata_json["encounter_id"] == generated["encounter_id"]
        assert audit.metadata_json["provider"] == "deterministic"
        assert audit.metadata_json["model_provider"] == "deterministic"
        assert audit.metadata_json["model_name"] == "deterministic_summary_service"


def test_reject_summary_with_valid_reason(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    generated = _generate_summary(client)

    response = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/reject",
        headers=DOCTOR_HEADERS,
        json={
            "rejection_reason": "wrong_citation",
            "rejection_comment": "The cited source does not support the medication wording.",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "wrong_citation"
    assert body["rejected_at"]

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None and summary.status == SummaryStatus.REJECTED
        assert summary.rejection_reason == "wrong_citation"
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "reject_summary",
                    AuditLog.resource_id == summary.summary_id,
                )
            )
            == 1
        )


def test_reject_summary_without_reason_fails(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    generated = _generate_summary(client)

    response = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/reject",
        headers=DOCTOR_HEADERS,
        json={"rejection_comment": "Missing reason should fail."},
    )

    assert response.status_code == 422


def test_nurse_cannot_approve_summary(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    generated = _generate_summary(client)

    response = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/approve",
        headers={**HEADERS, "X-Role-Code": "nurse", "X-User-ID": "nurse-demo"},
        json={"approval_comment": "Unauthorized approval attempt."},
    )

    assert response.status_code == 403
    assert "Only doctor role" in response.json()["detail"]


def test_invalid_status_transition_fails(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    generated = _generate_summary(client)
    approval = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/approve",
        headers=DOCTOR_HEADERS,
        json={"approval_comment": "Reviewed."},
    )
    assert approval.status_code == 200

    response = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/review/start",
        headers=DOCTOR_HEADERS,
    )

    assert response.status_code == 409
    assert "approved" in response.json()["detail"]


def test_review_history_returns_actions_in_order_and_audits_view(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    generated = _generate_summary(client)
    summary_id = generated["summary_id"]

    assert client.post(f"/api/v1/summaries/{summary_id}/review/start", headers=DOCTOR_HEADERS).status_code == 200
    assert client.patch(
        f"/api/v1/summaries/{summary_id}/edit",
        headers=DOCTOR_HEADERS,
        json={"edited_summary_text": "Edited text for history.", "edit_comment": "Minor edit."},
    ).status_code == 200
    assert client.post(
        f"/api/v1/summaries/{summary_id}/approve",
        headers=DOCTOR_HEADERS,
        json={"approval_comment": "Approved after edit."},
    ).status_code == 200

    response = client.get(
        f"/api/v1/summaries/{summary_id}/reviews",
        headers={**HEADERS, "X-Role-Code": "clinical_admin", "X-User-ID": "clinical-admin-demo"},
    )

    assert response.status_code == 200, response.text
    actions = [review["review_action"] for review in response.json()["reviews"]]
    assert actions == ["start_review", "edit", "approve"]
    edit_review = next(review for review in response.json()["reviews"] if review["review_action"] == "edit")
    assert edit_review["edit_diff"]
    assert edit_review["edit_diff_summary"]["changed_segments"] >= 1

    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "view_review_history",
                    AuditLog.resource_id == uuid.UUID(summary_id),
                )
            )
            == 1
        )
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "view_review_history",
                AuditLog.resource_id == uuid.UUID(summary_id),
            )
        )
        assert audit is not None
        assert audit.metadata_json["summary_id"] == summary_id
        assert audit.metadata_json["provider"] == "deterministic"
        assert audit.metadata_json["model_name"] == "deterministic_summary_service"
        assert audit.metadata_json["status"] == "approved"
