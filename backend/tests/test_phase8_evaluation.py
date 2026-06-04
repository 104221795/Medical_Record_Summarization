from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.services import evaluation_service as evaluation_module
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


def test_evaluation_status_endpoint_reports_three_layers(api_client) -> None:
    client, _session_factory = api_client

    response = client.get("/api/v1/evaluation/status", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["provider"] for item in body["provider_readiness"]} == {
        "deterministic",
        "bart",
        "pegasus",
        "pegasus_pubmed",
        "pegasus_cnn_dailymail",
        "gemini",
    }
    layers = {item["layer"]: item for item in body["evaluation_layers"]}
    assert layers["functional_validation"]["status"] == "runnable"
    assert layers["real_ehr_benchmark"]["status"] == "pending_dataset"
    assert layers["human_evaluation"]["status"] == "runnable"


def test_functional_validation_endpoint_returns_structured_checks(api_client) -> None:
    client, _session_factory = api_client

    response = client.post("/api/v1/evaluation/functional/run", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in {"passed", "partial"}
    check_names = {item["name"] for item in body["checks"]}
    assert {
        "demo_data_seed",
        "patient_list",
        "summary_generation",
        "citation_source",
        "hitl_review",
        "audit_logs",
        "metrics",
    }.issubset(check_names)
    assert all(item["status"] in {"passed", "failed", "not_tested"} for item in body["checks"])


def test_benchmark_status_returns_pending_dataset_when_file_missing(
    api_client,
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _session_factory = api_client
    monkeypatch.setattr(
        evaluation_module,
        "BENCHMARK_DATASET_PATH",
        tmp_path / "missing" / "test.jsonl",
    )
    monkeypatch.setattr(
        evaluation_module,
        "BENCHMARK_OUTPUT_PATH",
        tmp_path / "missing" / "model_comparison.csv",
    )

    response = client.get("/api/v1/evaluation/benchmark/status", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending_dataset"
    assert body["dataset_exists"] is False
    assert "No benchmark result is available yet" in body["message"]


def test_benchmark_status_detects_present_schema_file(
    api_client,
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _session_factory = api_client
    dataset_path = tmp_path / "data" / "processed" / "ehr_benchmark" / "test.jsonl"
    dataset_path.parent.mkdir(parents=True)
    dataset_path.write_text(
        json.dumps(
            {
                "note_id": "note_001",
                "patient_id": "patient_001",
                "encounter_id": "enc_001",
                "source_note": "De-identified source note.",
                "reference_summary": "Reference summary.",
                "dataset": "mimic_iv_note",
                "split": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(evaluation_module, "BENCHMARK_DATASET_PATH", dataset_path)
    monkeypatch.setattr(
        evaluation_module,
        "BENCHMARK_OUTPUT_PATH",
        tmp_path / "results" / "ehr_benchmark" / "model_comparison.csv",
    )

    response = client.get("/api/v1/evaluation/benchmark/status", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dataset_exists"] is True
    assert body["schema_valid"] is True
    assert body["status"] == "ready"


def test_human_evaluation_score_validation_and_summary_aggregation(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = api_client
    patient_id, encounter_id = import_patient(client)
    generated = generate_patient_snapshot(client, patient_id, encounter_id)

    invalid = client.post(
        "/api/v1/evaluation/human",
        headers=ADMIN_HEADERS,
        json={
            "summary_id": generated["summary_id"],
            "factual_correctness_score": 6,
            "completeness_score": 4,
            "conciseness_score": 4,
            "readability_score": 4,
            "citation_usefulness_score": 4,
            "hallucination_risk": "low",
        },
    )
    assert invalid.status_code == 422

    created = client.post(
        "/api/v1/evaluation/human",
        headers=ADMIN_HEADERS,
        json={
            "summary_id": generated["summary_id"],
            "evaluator_name": "Demo evaluator",
            "model_provider": "deterministic",
            "factual_correctness_score": 5,
            "completeness_score": 4,
            "conciseness_score": 4,
            "readability_score": 5,
            "citation_usefulness_score": 5,
            "hallucination_risk": "low",
            "comments": "Citations were useful for demo review.",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["model_provider"] == "deterministic"

    summary = client.get("/api/v1/evaluation/human/summary", headers=ADMIN_HEADERS)
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_evaluations"] >= 1
    assert body["average_factual_correctness_score"] is not None
    risk_counts = {item["key"]: item["count"] for item in body["hallucination_risk_distribution"]}
    assert risk_counts["low"] >= 1

    by_summary = client.get(
        f"/api/v1/evaluation/human/by-summary/{generated['summary_id']}",
        headers=ADMIN_HEADERS,
    )
    assert by_summary.status_code == 200
    assert len(by_summary.json()["evaluations"]) == 1


def test_evaluation_demo_ui_is_served(api_client) -> None:
    client, _session_factory = api_client

    page = client.get("/evaluation-demo")
    script = client.get("/evaluation-assets/app.js")
    styles = client.get("/evaluation-assets/styles.css")

    assert page.status_code == 200
    assert "MVP Evaluation & Demo Control Center" in page.text
    assert "Pending credentialed EHR dataset" in page.text
    assert script.status_code == 200
    assert "/evaluation/status" in script.text
    assert "/evaluation/functional/run" in script.text
    assert styles.status_code == 200
