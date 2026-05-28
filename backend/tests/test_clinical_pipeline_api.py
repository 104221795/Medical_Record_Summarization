import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.rag import build_rag_service


FHIR_EXAMPLE = (
    Path(__file__).resolve().parents[1] / "examples" / "fhir_clinical_input_bundle.json"
)
HEADERS = {"X-Tenant-ID": "vinmec-sandbox", "X-User-ID": "clinician-demo"}


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="clinical_pipeline_test_chunks",
        embedding_provider="hashing",
        generator_provider="extractive",
    )
    return TestClient(create_app(settings, build_rag_service(settings)))


def test_raw_clinical_notes_endpoint_returns_structured_citation_spans(tmp_path: Path) -> None:
    client = _client(tmp_path)
    notes = (
        "TI\u1ec0N S\u1eec:\nT\u0103ng huy\u1ebft \u00e1p t\u1eeb 2020.\n\n"
        "CH\u1ea8N \u0110O\u00c1N:\nT\u0103ng huy\u1ebft \u00e1p ch\u01b0a ki\u1ec3m so\u00e1t.\n\n"
        "K\u1ebe HO\u1ea0CH:\nTheo d\u00f5i huy\u1ebft \u00e1p t\u1ea1i nh\u00e0."
    )

    response = client.post(
        "/api/v1/clinical-summaries:generate-cited",
        headers=HEADERS,
        json={
            "patient_id": "patient-demo",
            "clinical_notes": notes,
            "clinical_question": "T\u0103ng huy\u1ebft \u00e1p k\u1ebf ho\u1ea1ch",
            "top_k": 4,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "accepted"
    assert result["ingestion"]["chunks_indexed"] >= 3
    citation = result["sentences"][0]["citations"][0]
    assert citation["document_id"] == "clinical-notes-patient-demo"
    assert notes[citation["start_idx"] : citation["end_idx"]] == citation["source_text"]


def test_fhir_bundle_is_validated_ingested_and_summarized(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(FHIR_EXAMPLE.read_text(encoding="utf-8"))

    response = client.post(
        "/api/v1/fhir/r4/bundles:ingest-and-summarize",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["validation_standard"] == "FHIR R4 scoped Pydantic profile"
    assert result["summary"]["patient_id"] == "patient-demo"
    assert result["summary"]["ingestion"]["documents_received"] == 2
    cited_document_ids = {
        citation["document_id"]
        for sentence in result["summary"]["sentences"]
        for citation in sentence["citations"]
    }
    assert "fhir-observation-blood-pressure-demo" in cited_document_ids


def test_fhir_bundle_rejects_observation_for_different_patient(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(FHIR_EXAMPLE.read_text(encoding="utf-8"))
    payload["bundle"]["entry"][2]["resource"]["subject"]["reference"] = "Patient/other"

    response = client.post(
        "/api/v1/fhir/r4/bundles:ingest-and-summarize",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert "Observation" in response.json()["detail"]
