from __future__ import annotations

import uuid
import time
import json
from datetime import UTC, datetime, timedelta

from backend.app.models import ModelJobRecord
from backend.app.services.background_jobs import _windows_worker_status, model_job_service
from backend.app.workers.rq_tasks import _claim_job, _is_transient_error
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


def test_stale_persisted_running_job_is_marked_timed_out(api_client) -> None:
    client, session_factory = api_client
    model_job_service.reset_for_tests()
    job_id = uuid.uuid4()
    session = session_factory()
    try:
        session.add(
            ModelJobRecord(
                job_id=job_id,
                job_type="summary_generation",
                model_provider="qwen2.5",
                model_name="qwen2.5",
                status="running",
                progress=0.54,
                current_step="provider_generation",
                timeout_seconds=1,
                payload={},
                created_at=datetime.now(UTC) - timedelta(minutes=5),
                started_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(f"/api/v1/jobs/{job_id}", headers=ADMIN_HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "timed_out"
    assert body["current_step"] == "timed_out"
    assert "timeout_seconds=1" in body["error_message"]


def test_persisted_job_claim_is_atomic(api_client) -> None:
    _client, session_factory = api_client
    job_id = uuid.uuid4()
    session = session_factory()
    try:
        session.add(
            ModelJobRecord(
                job_id=job_id,
                job_type="summary_generation",
                model_provider="deterministic",
                model_name="deterministic",
                status="queued",
                progress=0.0,
                current_step="queued",
                timeout_seconds=30,
                payload={},
            )
        )
        session.commit()
    finally:
        session.close()

    first_claim = _claim_job(session_factory, str(job_id), worker_id="worker-a", attempt=0)
    duplicate_claim = _claim_job(session_factory, str(job_id), worker_id="worker-b", attempt=0)

    assert first_claim is True
    assert duplicate_claim is False
    session = session_factory()
    try:
        record = session.get(ModelJobRecord, job_id)
        assert record is not None
        assert record.status == "running"
        assert record.current_step == "worker_initializing"
        assert record.payload["_job_runtime"]["worker_id"] == "worker-a"
    finally:
        session.close()


def test_windows_worker_status_ignores_stale_heartbeats(monkeypatch) -> None:
    now = time.time()

    class FakeRedis:
        values = {
            b"live": json.dumps(
                {"worker_id": "live", "state": "idle", "job_id": None, "heartbeat_at": now - 2}
            ).encode(),
            b"stale": json.dumps(
                {"worker_id": "stale", "state": "busy", "job_id": "job", "heartbeat_at": now - 60}
            ).encode(),
        }

        def scan_iter(self, **_kwargs):
            return iter(self.values)

        def get(self, key):
            return self.values.get(key)

    monkeypatch.setattr(time, "time", lambda: now)
    workers = _windows_worker_status(FakeRedis(), "queue", stale_seconds=20)

    assert [worker["worker_id"] for worker in workers] == ["live"]
    assert workers[0]["heartbeat_age_seconds"] == 2.0


def test_transient_provider_error_classification_is_bounded() -> None:
    assert _is_transient_error("Connection refused by Ollama") is True
    assert _is_transient_error("Provider timeout after 30 seconds") is True
    assert _is_transient_error("Retrieval quality gate failed") is False


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
