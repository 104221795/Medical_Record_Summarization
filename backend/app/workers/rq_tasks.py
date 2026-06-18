from __future__ import annotations

import os
import time
from typing import Any
from datetime import UTC, datetime
import uuid

from sqlalchemy import update

from ..config import get_settings
from ..db.session import build_engine_from_settings, create_session_factory
from ..models import ModelJobRecord
from ..runtime_env import load_runtime_env
from ..services.background_jobs import ModelJobService
from ..services.rag import build_rag_service


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out"}
TRANSIENT_ERROR_MARKERS = (
    "connection refused",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "http 429",
    "http 502",
    "http 503",
    "http 504",
)


def run_model_job(job_id: str) -> dict[str, Any]:
    """RQ task entrypoint for a persisted model job.

    The API process persists job metadata before enqueueing. The worker rebuilds
    runtime dependencies in its own process, executes the same job implementation
    as local development, and writes progress/result updates back to the
    ``model_jobs`` table.
    """

    load_runtime_env(enable_model_defaults=True, job_backend="rq")
    settings = get_settings()
    session_factory = create_session_factory(build_engine_from_settings(settings))
    worker_id = os.environ.get("RAG_WINDOWS_WORKER_ID") or "rq-worker"
    max_retries = int(getattr(settings, "rq_max_retries", 2))

    for attempt in range(max_retries + 1):
        if not _claim_job(session_factory, job_id, worker_id=worker_id, attempt=attempt):
            return _current_job_response(session_factory, job_id)
        service = ModelJobService(max_workers=1)
        service.configure_runtime(
            db_session_factory=session_factory,
            settings=settings,
            rag_service=_LazyRagService(settings),
            summary_model_providers={},
            gemini_json_client=None,
            mark_interrupted=False,
        )
        response = service.run_persisted_job(job_id)
        if response.status != "failed" or attempt >= max_retries:
            return response.model_dump(mode="json")
        if not _is_transient_error(response.error_message):
            return response.model_dump(mode="json")
        _prepare_retry(
            session_factory,
            job_id,
            attempt=attempt + 1,
            max_retries=max_retries,
            error_message=response.error_message,
        )
        time.sleep(min(2**attempt, 5))

    return _current_job_response(session_factory, job_id)


def _claim_job(
    session_factory: Any,
    job_id: str,
    *,
    worker_id: str,
    attempt: int,
) -> bool:
    session = session_factory()
    try:
        record = session.get(ModelJobRecord, uuid.UUID(job_id))
        if record is None or record.status != "queued":
            return False
        payload = dict(record.payload or {})
        runtime = dict(payload.get("_job_runtime") or {})
        runtime.update(
            {
                "worker_id": worker_id,
                "worker_heartbeat_key": os.environ.get("RAG_WINDOWS_WORKER_HEARTBEAT_KEY"),
                "attempt": attempt,
                "claimed_at": datetime.now(UTC).isoformat(),
            }
        )
        payload["_job_runtime"] = runtime
        claim = session.execute(
            update(ModelJobRecord)
            .where(
                ModelJobRecord.job_id == uuid.UUID(job_id),
                ModelJobRecord.status == "queued",
            )
            .values(
                status="running",
                progress=max(float(record.progress or 0.0), 0.03),
                current_step="worker_initializing",
                started_at=record.started_at or datetime.now(UTC),
                finished_at=None,
                error_message=None,
                payload=payload,
            )
        )
        session.commit()
        return claim.rowcount == 1
    finally:
        session.close()


def _prepare_retry(
    session_factory: Any,
    job_id: str,
    *,
    attempt: int,
    max_retries: int,
    error_message: str | None,
) -> None:
    session = session_factory()
    try:
        record = session.get(ModelJobRecord, uuid.UUID(job_id))
        if record is None or record.status != "failed":
            return
        payload = dict(record.payload or {})
        runtime = dict(payload.get("_job_runtime") or {})
        runtime.update(
            {
                "attempt": attempt,
                "max_retries": max_retries,
                "last_transient_error": error_message,
                "retry_scheduled_at": datetime.now(UTC).isoformat(),
            }
        )
        payload["_job_runtime"] = runtime
        record.status = "queued"
        record.current_step = "worker_initializing"
        record.finished_at = None
        record.error_message = None
        record.payload = payload
        session.commit()
    finally:
        session.close()


def _current_job_response(session_factory: Any, job_id: str) -> dict[str, Any]:
    session = session_factory()
    try:
        record = session.get(ModelJobRecord, uuid.UUID(job_id))
        if record is None:
            raise RuntimeError(f"Persisted model job '{job_id}' was not found.")
        return {
            "job_id": str(record.job_id),
            "job_type": record.job_type,
            "model_provider": record.model_provider,
            "model_name": record.model_name,
            "status": record.status,
            "progress": float(record.progress or 0.0),
            "current_step": record.current_step,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "timeout_seconds": record.timeout_seconds,
            "result": record.result,
            "error_message": record.error_message,
        }
    finally:
        session.close()


def _is_transient_error(error_message: str | None) -> bool:
    normalized = str(error_message or "").lower()
    return any(marker in normalized for marker in TRANSIENT_ERROR_MARKERS)


class _LazyRagService:
    def __init__(self, settings: Any):
        self._settings = settings
        self._service: Any | None = None

    def _resolve(self) -> Any:
        if self._service is None:
            self._service = build_rag_service(self._settings)
        return self._service

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)
