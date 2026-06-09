from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..persistence_schemas import ModelJobCreateRequest, ModelJobListResponse, ModelJobResponse, ModelReadinessResponse


@dataclass
class ModelJob:
    job_id: str
    job_type: str
    model_provider: str
    model_name: str
    timeout_seconds: int
    payload: dict[str, Any]
    status: str = "queued"
    progress: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    cancel_requested: bool = False


class ModelJobService:
    """Small in-process job scaffold for heavy local model work.

    This is intentionally conservative: it provides API semantics and readiness
    checks before wiring BART/Pegasus/Gemini generation into a durable queue.
    """

    def __init__(self, max_workers: int = 1):
        self._jobs: dict[str, ModelJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="model-job")

    def enqueue(self, payload: ModelJobCreateRequest) -> ModelJobResponse:
        job = ModelJob(
            job_id=str(uuid.uuid4()),
            job_type=payload.job_type,
            model_provider=payload.model_provider,
            model_name=payload.model_name,
            timeout_seconds=payload.timeout_seconds,
            payload=payload.payload,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run_job, job.job_id)
        return self._response(job)

    def get(self, job_id: str) -> ModelJobResponse | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._response(job) if job else None

    def list(self) -> ModelJobListResponse:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return ModelJobListResponse(jobs=[self._response(job) for job in jobs])

    def cancel(self, job_id: str) -> ModelJobResponse | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status in {"completed", "failed", "cancelled", "timed_out"}:
                return self._response(job)
            job.cancel_requested = True
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
            return self._response(job)

    def readiness(self, model_names: list[str]) -> ModelReadinessResponse:
        cache_paths = {
            key: os.environ.get(key)
            for key in ("HF_HOME", "HF_HUB_CACHE", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE")
        }
        hub = Path(cache_paths.get("HF_HUB_CACHE") or "D:/hf_cache/hub")
        models = []
        for model_name in model_names:
            cache_dir = hub / ("models--" + model_name.replace("/", "--"))
            models.append(
                {
                    "model_name": model_name,
                    "cache_dir": str(cache_dir),
                    "cached": cache_dir.exists(),
                    "status": "ready" if cache_dir.exists() else "missing_from_cache",
                }
            )
        return ModelReadinessResponse(cache_paths=cache_paths, models=models)

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                return
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.progress = 0.05
        started = time.perf_counter()
        try:
            self._simulate_or_warmup(job_id, started)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                if job.status in {"cancelled", "timed_out"}:
                    job.error_message = str(exc)
                    return
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.now(UTC)

    def _simulate_or_warmup(self, job_id: str, started: float) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.progress = 0.15
            job_type = job.job_type
            model_name = job.model_name
        if job_type == "model_warmup":
            self._warm_model(job_id, model_name, started)
        else:
            self._simulate_generation(job_id, started)
        with self._lock:
            job = self._jobs[job_id]
            if job.status in {"cancelled", "timed_out"}:
                return
            job.status = "completed"
            job.finished_at = datetime.now(UTC)
            job.progress = 1.0
            job.result = job.result or {
                "message": "Job scaffold completed. Wire generation implementation here before production traffic.",
                "model_provider": job.model_provider,
                "model_name": job.model_name,
            }

    def _warm_model(self, job_id: str, model_name: str, started: float) -> None:
        self._check_cancel_or_timeout(job_id, started)
        if model_name.startswith("sentence-transformers/"):
            from sentence_transformers import SentenceTransformer

            SentenceTransformer(model_name, cache_folder=os.environ.get("HF_HUB_CACHE"), local_files_only=True)
        else:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            cache_dir = os.environ.get("HF_HUB_CACHE", "D:/hf_cache/hub")
            AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
            AutoModelForSeq2SeqLM.from_pretrained(model_name, cache_dir=cache_dir, local_files_only=True)
        with self._lock:
            job = self._jobs[job_id]
            job.progress = 0.9
            job.result = {"message": "Model loaded from local cache.", "model_name": model_name}

    def _simulate_generation(self, job_id: str, started: float) -> None:
        for progress in (0.25, 0.55, 0.85):
            time.sleep(0.05)
            self._check_cancel_or_timeout(job_id, started)
            with self._lock:
                self._jobs[job_id].progress = progress

    def _check_cancel_or_timeout(self, job_id: str, started: float) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                raise RuntimeError("Job cancelled.")
            if time.perf_counter() - started > job.timeout_seconds:
                job.status = "timed_out"
                job.finished_at = datetime.now(UTC)
                raise RuntimeError("Job timed out.")

    @staticmethod
    def _response(job: ModelJob) -> ModelJobResponse:
        return ModelJobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            model_provider=job.model_provider,
            model_name=job.model_name,
            status=job.status,  # type: ignore[arg-type]
            progress=round(job.progress, 4),
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            timeout_seconds=job.timeout_seconds,
            result=job.result,
            error_message=job.error_message,
        )


model_job_service = ModelJobService()
