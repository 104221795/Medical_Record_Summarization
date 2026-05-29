from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.rag import build_rag_service


def test_unified_demo_console_ui_is_served(tmp_path: Path) -> None:
    settings = Settings(environment="test", qdrant_path=tmp_path / "qdrant")
    app = create_app(settings=settings, rag_service=build_rag_service(settings))
    client = TestClient(app)

    page = client.get("/demo-console")
    script = client.get("/demo-console-assets/app.js")
    styles = client.get("/demo-console-assets/styles.css")

    assert page.status_code == 200
    assert "Unified Demo Console" in page.text
    assert "Mock role login" in page.text
    assert "Logout" in page.text
    assert "Demo Setup" in page.text
    assert "Doctor Workspace" in page.text
    assert "Evaluation Center" in page.text
    assert "Draft summary - requires doctor review" in page.text
    assert script.status_code == 200
    assert "/patients" in script.text
    assert "/summaries/" in script.text
    assert "/evaluation/status" in script.text
    assert "ROLE_PROFILES" in script.text
    assert "Only doctor role can perform HITL review actions" in script.text
    assert "X-Tenant-ID" in script.text
    assert "X-User-ID" in script.text
    assert "X-Role-Code" in script.text
    assert styles.status_code == 200
    assert ".metric strong" in styles.text
    assert ".card-body" in styles.text
    assert "overflow-wrap: anywhere" in styles.text
