import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.schemas import CandidateSummary, GeneratedClaim
from backend.app.services.generators import SummaryGenerator
from backend.app.services.rag import build_rag_service
from backend.app.services.telemetry import SummaryTelemetry


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "raw_emr_patient_demo.json"
HEADERS = {"X-Tenant-ID": "vinmec-sandbox", "X-User-ID": "clinician-demo"}


class ContradictingGenerator(SummaryGenerator):
    name = "test-contradicting-generator"

    def generate(self, clinical_question: str, workflow: str, evidence: list) -> CandidateSummary:
        xray = next(item for item in evidence if "pulmonary edema" in item.text.casefold())
        return CandidateSummary(
            claims=[GeneratedClaim(text="Pulmonary edema is present.", evidence_ids=[xray.chunk_id])]
        )


class CapturingTelemetry(SummaryTelemetry):
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


def _client(tmp_path: Path) -> tuple[TestClient, object]:
    settings = Settings(
        environment="test",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="test_clinical_chunks",
        embedding_provider="hashing",
        generator_provider="extractive",
    )
    service = build_rag_service(settings)
    return TestClient(create_app(settings, service)), service


def test_ingest_retrieve_and_local_grounded_summary(tmp_path: Path) -> None:
    client, _service = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    ingest = client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json=payload,
    )
    assert ingest.status_code == 200
    assert ingest.json()["chunks_indexed"] >= 2

    retrieve = client.post(
        "/api/v1/patients/patient-demo/evidence:retrieve",
        headers=HEADERS,
        json={"query": "pulmonary edema", "top_k": 3},
    )
    assert retrieve.status_code == 200
    assert retrieve.json()["evidence"]

    isolated = client.post(
        "/api/v1/patients/other-patient/evidence:retrieve",
        headers=HEADERS,
        json={"query": "pulmonary edema", "top_k": 3},
    )
    assert isolated.status_code == 200
    assert isolated.json()["evidence"] == []

    summary = client.post(
        "/api/v1/patients/patient-demo/summaries:generate",
        headers=HEADERS,
        json={"clinical_question": "pulmonary edema", "workflow": "diagnostic_report"},
    )
    assert summary.status_code == 200
    assert summary.json()["status"] == "accepted"
    assert summary.json()["guardrail"]["citation_coverage"] == 100.0


def test_contradictory_generated_summary_is_withheld(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json=payload,
    )
    service.generator = ContradictingGenerator()

    response = client.post(
        "/api/v1/patients/patient-demo/summaries:generate",
        headers=HEADERS,
        json={"clinical_question": "pulmonary edema", "workflow": "diagnostic_report"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["summary"] is None
    assert response.json()["guardrail"]["issues"][0]["code"] == "POSSIBLE_CONTRADICTION"


def test_citation_summary_returns_sentence_ids_and_highlight_offsets(tmp_path: Path) -> None:
    client, _service = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json=payload,
    )

    response = client.post(
        "/api/v1/patients/patient-demo/summaries:generate-cited",
        headers=HEADERS,
        json={"clinical_question": "pulmonary edema", "workflow": "diagnostic_report"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "accepted"
    sentence = result["sentences"][0]
    assert sentence["summary_sentence"]
    assert sentence["citations"] == [sentence["source_chunks"][0]["citation_id"]]
    assert sentence["source_chunks"][0]["char_end"] > sentence["source_chunks"][0]["char_start"]


def test_citation_summary_does_not_publish_blocked_claims(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json=payload,
    )
    service.generator = ContradictingGenerator()

    response = client.post(
        "/api/v1/patients/patient-demo/summaries:generate-cited",
        headers=HEADERS,
        json={"clinical_question": "pulmonary edema", "workflow": "diagnostic_report"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["sentences"] == []


def test_citation_demo_ui_is_served_from_fastapi(tmp_path: Path) -> None:
    client, _service = _client(tmp_path)

    page = client.get("/citation-demo")
    script = client.get("/citation-assets/app.js")

    assert page.status_code == 200
    assert "Citation-based summary" in page.text
    assert script.status_code == 200
    assert "summaries:generate-cited" in script.text


def test_summary_records_latency_tokens_and_guardrail_telemetry(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    telemetry = CapturingTelemetry()
    service.telemetry = telemetry
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json=payload,
    )

    response = client.post(
        "/api/v1/patients/patient-demo/summaries:generate",
        headers=HEADERS,
        json={"clinical_question": "pulmonary edema", "workflow": "diagnostic_report"},
    )

    assert response.status_code == 200
    event = telemetry.events[0]
    assert event.latency_ms >= 0
    assert event.input_tokens > 0
    assert event.output_tokens > 0
    assert event.status == "accepted"


def test_blocked_summary_records_suspected_hallucination_guardrail_issues(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    telemetry = CapturingTelemetry()
    service.telemetry = telemetry
    service.generator = ContradictingGenerator()
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    client.post(
        "/api/v1/patients/patient-demo/records:ingest",
        headers=HEADERS,
        json=payload,
    )

    client.post(
        "/api/v1/patients/patient-demo/summaries:generate",
        headers=HEADERS,
        json={"clinical_question": "pulmonary edema", "workflow": "diagnostic_report"},
    )

    event = telemetry.events[0]
    assert event.status == "blocked"
    assert event.guardrail.issues[0].code == "POSSIBLE_CONTRADICTION"
