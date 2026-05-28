from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.fhir_mapper import FhirMapperService
from backend.app.services.rag import build_rag_service


def test_doctor_golden_path_ui_is_served(tmp_path: Path) -> None:
    settings = Settings(environment="test", qdrant_path=tmp_path / "qdrant")
    app = create_app(settings=settings, rag_service=build_rag_service(settings))
    client = TestClient(app)

    page = client.get("/doctor-demo")
    script = client.get("/doctor-assets/app.js")
    styles = client.get("/doctor-assets/styles.css")

    assert page.status_code == 200
    assert "Doctor Golden Path" in page.text
    assert "Draft only" in page.text
    assert "Create demo data" in page.text
    assert "Start Review" in page.text
    assert "Approve Summary" in page.text
    assert "Reject Summary" in page.text
    assert script.status_code == 200
    assert "GET /api/v1/patients" not in script.text
    assert styles.status_code == 200


def test_demo_seed_initializes_schema_and_patient_records(tmp_path: Path) -> None:
    settings = Settings(
        environment="development",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'fresh-demo.db'}",
        qdrant_path=tmp_path / "qdrant",
    )
    app = create_app(settings=settings, rag_service=build_rag_service(settings))
    client = TestClient(app)
    headers = {"X-Tenant-ID": "sandbox", "X-User-ID": "doctor-demo"}

    initial = client.get("/api/v1/patients", headers=headers)
    assert initial.status_code == 503
    assert "schema is not initialized" in initial.json()["detail"]

    seeded = client.post("/api/v1/demo/seed", headers=headers)
    assert seeded.status_code == 201
    assert seeded.json()["created"] is True

    patients = client.get("/api/v1/patients", headers=headers)
    assert patients.status_code == 200
    assert patients.json()["pagination"]["total_items"] == 1


def test_demo_seed_disabled_in_production(tmp_path: Path) -> None:
    settings = Settings(
        environment="production",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'prod-demo.db'}",
        qdrant_path=tmp_path / "qdrant",
        embedding_provider="fastembed",
        qdrant_url="http://localhost:6333",
        medical_nli_required_for_writeback=True,
        medical_nli_model_path=tmp_path / "nli",
    )
    local_rag_settings = Settings(environment="test", qdrant_path=tmp_path / "qdrant-prod-rag")
    app = create_app(
        settings=settings,
        rag_service=build_rag_service(local_rag_settings),
        fhir_mapper_service=FhirMapperService(local_rag_settings),
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/demo/seed",
        headers={"X-Tenant-ID": "sandbox", "X-User-ID": "doctor-demo"},
    )

    assert response.status_code == 403
