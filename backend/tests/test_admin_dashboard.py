from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.rag import build_rag_service


def test_admin_dashboard_ui_is_served(tmp_path: Path) -> None:
    settings = Settings(environment="test", qdrant_path=tmp_path / "qdrant")
    app = create_app(settings=settings, rag_service=build_rag_service(settings))
    client = TestClient(app)

    page = client.get("/admin/dashboard")
    script = client.get("/admin-assets/app.js")
    styles = client.get("/admin-assets/styles.css")

    assert page.status_code == 200
    assert "Audit, Metrics, and Evaluation Dashboard" in page.text
    assert "No fake dashboard data is used" in page.text
    assert "nurse (should be denied)" in page.text
    assert script.status_code == 200
    assert "/metrics/summary-quality" in script.text
    assert "/audit/logs" in script.text
    assert styles.status_code == 200
