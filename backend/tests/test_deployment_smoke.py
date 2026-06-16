from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

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


def test_operations_health_and_readiness(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200, health.text
    assert health.json()["status"] == "ok"
    assert ready.status_code in {200, 503}, ready.text
    body = ready.json()
    assert body["clinical_use"] == "staging_demo_only"
    assert "database" in body["checks"]
    assert body["checks"]["database"]["status"] == "pass"


def test_doctor_golden_path_smoke(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    patient_id, encounter_id = import_patient(client)

    patients = client.get("/api/v1/patients", headers=DOCTOR_HEADERS)
    generated = generate_patient_snapshot(client, patient_id, encounter_id)
    review = client.post(
        f"/api/v1/summaries/{generated['summary_id']}/review/start",
        headers=DOCTOR_HEADERS,
    )

    assert patients.status_code == 200, patients.text
    assert patients.json()["items"]
    assert generated["status"] == "draft"
    assert generated["citation_coverage"] is not None
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "under_review"


def test_admin_artifact_and_audit_endpoints_are_graceful(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    benchmark = client.get("/api/v1/evaluation/benchmark/status", headers=ADMIN_HEADERS)
    audit_export = client.get("/api/v1/audit/export", headers=ADMIN_HEADERS)

    assert benchmark.status_code == 200, benchmark.text
    assert "status" in benchmark.json()
    assert audit_export.status_code == 200, audit_export.text
    assert audit_export.json()["phi_safe"] is True
