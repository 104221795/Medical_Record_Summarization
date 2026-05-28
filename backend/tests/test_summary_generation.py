from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from backend.app.models import AuditLog, ModelRun, Summary, SummaryStatus
from backend.tests.summary_test_utils import (
    HEADERS,
    api_client,
    generate_patient_snapshot,
    import_patient,
)


def test_generate_patient_snapshot_persists_draft_sections_claims_citations_and_audit(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    patient_id, encounter_id = import_patient(client)

    generated = generate_patient_snapshot(client, patient_id, encounter_id)

    assert generated["patient_id"] == patient_id
    assert generated["encounter_id"] == encounter_id
    assert generated["summary_type"] == "patient_snapshot"
    assert generated["status"] == "draft"
    assert generated["citation_coverage"] is not None
    assert generated["unsupported_claim_count"] >= 1
    assert generated["conflict_count"] == 0

    detail_response = client.get(
        f"/api/v1/summaries/{generated['summary_id']}", headers=HEADERS
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "draft"
    assert [section["section_title"] for section in detail["sections"]] == [
        "Patient Snapshot",
        "Active Problems",
        "Recent Clinical Course",
        "Medications",
        "Labs and Imaging Highlights",
        "Needs Clinician Review",
    ]
    claims = [
        claim
        for section in detail["sections"]
        for claim in section["claims"]
    ]
    assert claims
    supported_claims = [
        claim for claim in claims if claim["support_status"] == "supported"
    ]
    assert supported_claims
    assert all(claim["citation_count"] >= 1 for claim in supported_claims)
    needs_review = detail["sections"][-1]
    assert "Không tìm thấy thông tin trong dữ liệu hiện có." in needs_review["section_text"]
    assert detail["safety_summary"]["unsupported_claim_count"] >= 1

    with session_factory() as session:
        summary = session.get(Summary, uuid.UUID(generated["summary_id"]))
        assert summary is not None
        assert summary.status == SummaryStatus.DRAFT
        assert summary.approved_at is None
        assert summary.model_run_id is not None
        assert session.get(ModelRun, summary.model_run_id).provider == "local"
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "generate_summary")
            )
            == 1
        )


def test_regenerate_creates_new_draft_version_without_overwriting_parent(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_client
    patient_id, encounter_id = import_patient(client)
    first = generate_patient_snapshot(client, patient_id, encounter_id)

    regenerated_response = client.post(
        f"/api/v1/summaries/{first['summary_id']}/regenerate",
        headers=HEADERS,
        json={"reason": "Updated source data available"},
    )

    assert regenerated_response.status_code == 201
    regenerated = regenerated_response.json()
    assert regenerated["old_summary_id"] == first["summary_id"]
    assert regenerated["new_summary_id"] != first["summary_id"]
    assert regenerated["status"] == "draft"
    assert regenerated["version_number"] == 2
    new_detail = client.get(
        f"/api/v1/summaries/{regenerated['new_summary_id']}", headers=HEADERS
    ).json()
    assert new_detail["parent_summary_id"] == first["summary_id"]
    assert new_detail["status"] == "draft"

    with session_factory() as session:
        original = session.get(Summary, uuid.UUID(first["summary_id"]))
        assert original is not None and original.status == SummaryStatus.DRAFT
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "regenerate_summary")
            )
            == 1
        )
