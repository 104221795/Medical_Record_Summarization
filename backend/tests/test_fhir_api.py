import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.rag import build_rag_service


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "fhir_summary_mapping_request.json"
HEADERS = {"X-Tenant-ID": "vinmec-sandbox", "X-User-ID": "clinician-demo"}


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        environment="test",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="fhir_test_chunks",
        embedding_provider="hashing",
        generator_provider="extractive",
    )
    return TestClient(create_app(settings, build_rag_service(settings)))


def test_maps_accepted_summary_to_fhir_r4_transaction_bundle(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    response = client.post(
        "/api/v1/fhir/r4/summary-bundles:map",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 200
    bundle = response.json()["bundle"]
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    assert [item["resource"]["resourceType"] for item in bundle["entry"]] == [
        "Composition",
        "ClinicalImpression",
        "Condition",
    ]
    composition = bundle["entry"][0]["resource"]
    assert composition["status"] == "preliminary"
    assert composition["subject"]["reference"] == "Patient/patient-demo"
    condition = bundle["entry"][2]["resource"]
    assert condition["clinicalStatus"]["coding"][0]["code"] == "active"
    assert condition["verificationStatus"]["coding"][0]["code"] == "provisional"
    assert response.json()["medical_guardrail"]["status"] == "passed"


def test_mock_push_validates_and_acknowledges_transaction_without_persisting(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    mapped = client.post(
        "/api/v1/fhir/r4/summary-bundles:map", headers=HEADERS, json=payload
    ).json()

    response = client.post(
        "/api/v1/fhir/r4/mock-server/$transaction",
        headers=HEADERS,
        json={"destination_base_url": "https://hapi-fhir.sandbox.local/fhir", "bundle": mapped["bundle"]},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "accepted-for-mock-delivery"
    assert result["resources_received"] == 3
    assert result["persisted"] is False


def test_rejects_condition_evidence_outside_submitted_documents(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["conditions"][0]["evidence_document_ids"] = ["unknown-report"]

    response = client.post(
        "/api/v1/fhir/r4/summary-bundles:map",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert "source documents" in response.json()["detail"]


def test_rejects_summary_not_approved_for_fhir_writeback(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["summary_status"] = "blocked"

    response = client.post(
        "/api/v1/fhir/r4/summary-bundles:map",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 422


def test_rejects_summary_with_citation_not_in_retrieved_evidence(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["summary"]["claims"][0]["evidence_ids"] = ["invented-evidence-id"]

    response = client.post(
        "/api/v1/fhir/r4/summary-bundles:map",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 422


def test_guardrail_validation_endpoint_blocks_hallucinated_medication(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/v1/fhir/r4/guardrails:validate",
        headers=HEADERS,
        json={
            "raw_clinical_text": "Dung metformin 500 mg moi ngay.",
            "ai_summary_json": {
                "claims": [{"text": "Dung metformin 1000 mg va amlodipine 5 mg moi ngay."}]
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["allow_emr_writeback"] is False


def test_fhir_writeback_is_blocked_when_summary_adds_new_medication(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["summary"]["claims"].append(
        {
            "text": "Start amlodipine 5 mg daily.",
            "evidence_ids": ["report-2026-05-20-findings-001"],
        }
    )

    response = client.post(
        "/api/v1/fhir/r4/summary-bundles:map",
        headers=HEADERS,
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["status"] == "failed"
    assert response.json()["detail"]["allow_emr_writeback"] is False
    assert "UNSUPPORTED_MEDICATION" in {
        item["code"] for item in response.json()["detail"]["issues"]
    }
