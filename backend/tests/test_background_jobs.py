from __future__ import annotations

import time

from backend.app.services.background_jobs import model_job_service
from backend.tests.summary_test_utils import HEADERS, api_client as api_client, import_patient


ADMIN_HEADERS = {
    **HEADERS,
    "X-Role-Code": "clinical_admin",
    "X-User-ID": "clinical-admin-demo",
}


def test_model_readiness_reports_cache_and_gateway_models(api_client, monkeypatch) -> None:
    client, _session_factory = api_client
    monkeypatch.setenv("HF_HOME", "D:\\hf_cache")
    monkeypatch.setenv("HF_HUB_CACHE", "D:\\hf_cache\\hub")
    monkeypatch.setenv("HF_DATASETS_CACHE", "D:\\hf_cache\\datasets")
    monkeypatch.setenv("TRANSFORMERS_CACHE", "D:\\hf_cache\\hub")
    monkeypatch.setenv("OLLAMA_MODELS", "D:\\ollama_models")

    response = client.get("/api/v1/jobs/readiness", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cache_paths"]["HF_HOME"]["points_to_c_drive"] is False
    assert body["queue_backend"] == "in_process"
    assert body["queue_status"]["enabled"] is False
    providers = {item["provider"] for item in body["models"]}
    assert {"bart", "pegasus", "minilm", "bertscore", "qwen2.5", "llama3.2", "gemini2.5_flash_lite"}.issubset(providers)


def test_simulated_generation_job_completes(api_client) -> None:
    client, _session_factory = api_client
    model_job_service.reset_for_tests()

    response = client.post(
        "/api/v1/jobs",
        headers=ADMIN_HEADERS,
        json={
            "job_type": "summarization_generation",
            "model_provider": "deterministic",
            "model_name": "deterministic_sentence_baseline",
            "timeout_seconds": 5,
            "payload": {"simulate_seconds": 0.05},
        },
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    completed = _wait_for_terminal_job(client, job_id)
    assert completed["status"] == "completed"
    assert completed["result"]["simulated"] is True


def test_completed_job_is_readable_after_in_memory_reset(api_client) -> None:
    client, _session_factory = api_client
    model_job_service.reset_for_tests()

    response = client.post(
        "/api/v1/jobs",
        headers=ADMIN_HEADERS,
        json={
            "job_type": "summarization_generation",
            "model_provider": "deterministic",
            "model_name": "deterministic_sentence_baseline",
            "timeout_seconds": 5,
            "payload": {"simulate_seconds": 0.05},
        },
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    completed = _wait_for_terminal_job(client, job_id)
    assert completed["status"] == "completed"

    model_job_service.reset_for_tests()
    persisted_response = client.get(f"/api/v1/jobs/{job_id}", headers=ADMIN_HEADERS)

    assert persisted_response.status_code == 200, persisted_response.text
    persisted = persisted_response.json()
    assert persisted["job_id"] == job_id
    assert persisted["status"] == "completed"


def test_job_cancel_marks_running_job_cancelled(api_client) -> None:
    client, _session_factory = api_client
    model_job_service.reset_for_tests()

    response = client.post(
        "/api/v1/jobs",
        headers=ADMIN_HEADERS,
        json={
            "job_type": "summarization_generation",
            "model_provider": "deterministic",
            "model_name": "deterministic_sentence_baseline",
            "timeout_seconds": 5,
            "payload": {"simulate_seconds": 2.0},
        },
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    cancel_response = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=ADMIN_HEADERS)

    assert cancel_response.status_code == 200, cancel_response.text
    completed = _wait_for_terminal_job(client, job_id)
    assert completed["status"] in {"cancelled", "completed"}


def test_job_timeout_is_reported(api_client) -> None:
    client, _session_factory = api_client
    model_job_service.reset_for_tests()

    response = client.post(
        "/api/v1/jobs",
        headers=ADMIN_HEADERS,
        json={
            "job_type": "summarization_generation",
            "model_provider": "deterministic",
            "model_name": "deterministic_sentence_baseline",
            "timeout_seconds": 1,
            "payload": {"simulate_seconds": 1.5},
        },
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    completed = _wait_for_terminal_job(client, job_id, timeout_seconds=3.0)
    assert completed["status"] == "timed_out"
    assert "timed out" in completed["error_message"].lower()


def test_async_summary_generation_job_creates_draft(api_client) -> None:
    client, _session_factory = api_client
    model_job_service.reset_for_tests()
    patient_id, encounter_id = import_patient(client)

    response = client.post(
        f"/api/v1/patients/{patient_id}/summaries/generate-async",
        headers=HEADERS,
        json={
            "encounter_id": encounter_id,
            "summary_type": "patient_snapshot",
            "language": "en",
            "model_provider": "deterministic",
        },
    )

    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    completed = _wait_for_terminal_job(client, job_id, timeout_seconds=15.0)
    assert completed["status"] == "completed"
    assert completed["result"]["summary_id"]

    detail_response = client.get(f"/api/v1/summaries/{completed['result']['summary_id']}", headers=HEADERS)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["status"] == "draft"
    assert detail["summary_text"]


def _wait_for_terminal_job(client, job_id: str, *, timeout_seconds: float = 2.0) -> dict:
    deadline = time.perf_counter() + timeout_seconds
    latest: dict | None = None
    while time.perf_counter() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers=ADMIN_HEADERS)
        assert response.status_code == 200, response.text
        latest = response.json()
        if latest["status"] in {"completed", "failed", "cancelled", "timed_out"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish in time: {latest}")
