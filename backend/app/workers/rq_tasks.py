from __future__ import annotations

from typing import Any
from datetime import UTC, datetime
import uuid

from ..config import get_settings
from ..db.session import build_engine_from_settings, create_session_factory
from ..models import ModelJobRecord
from ..runtime_env import load_runtime_env
from ..services.background_jobs import ModelJobService
from ..services.rag import build_rag_service


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
    _mark_worker_initializing(session_factory, job_id)
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
    return response.model_dump(mode="json")


def _mark_worker_initializing(session_factory: Any, job_id: str) -> None:
    session = session_factory()
    try:
        record = session.get(ModelJobRecord, uuid.UUID(job_id))
        if record is None or record.status in {"completed", "failed", "cancelled", "timed_out"}:
            return
        record.status = "running"
        record.progress = max(float(record.progress or 0.0), 0.03)
        record.current_step = "worker_initializing"
        record.started_at = record.started_at or datetime.now(UTC)
        session.commit()
    finally:
        session.close()


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
