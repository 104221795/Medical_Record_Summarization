from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib import error as urlerror
from urllib import request as urlrequest

from sqlalchemy import select

from ..persistence_schemas import ModelJobCreateRequest, ModelJobListResponse, ModelJobResponse, ModelReadinessResponse


ModelKind = Literal["deterministic", "hf_seq2seq", "hf_encoder", "sentence_transformer", "ollama", "gemini", "unknown"]


@dataclass(frozen=True)
class ModelCatalogItem:
    provider: str
    display_name: str
    model_name: str
    model_kind: ModelKind
    cache_env: str | None = "HF_HUB_CACHE"
    warmup_supported: bool = True
    external: bool = False


DEFAULT_MODEL_CATALOG: tuple[ModelCatalogItem, ...] = (
    ModelCatalogItem(
        provider="deterministic",
        display_name="Deterministic baseline",
        model_name="deterministic_sentence_baseline",
        model_kind="deterministic",
        cache_env=None,
        warmup_supported=False,
    ),
    ModelCatalogItem(
        provider="bart",
        display_name="BART CNN/DailyMail",
        model_name="facebook/bart-large-cnn",
        model_kind="hf_seq2seq",
    ),
    ModelCatalogItem(
        provider="pegasus",
        display_name="Pegasus PubMed",
        model_name="google/pegasus-pubmed",
        model_kind="hf_seq2seq",
    ),
    ModelCatalogItem(
        provider="minilm",
        display_name="MiniLM retrieval embedder",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kind="sentence_transformer",
    ),
    ModelCatalogItem(
        provider="bertscore",
        display_name="BERTScore evaluator",
        model_name="roberta-large",
        model_kind="hf_encoder",
    ),
    ModelCatalogItem(
        provider="qwen2.5",
        display_name="Qwen2.5 3B via Ollama",
        model_name="ollama/qwen2.5:3b",
        model_kind="ollama",
        cache_env="OLLAMA_MODELS",
    ),
    ModelCatalogItem(
        provider="llama3.2",
        display_name="Llama3.2 3B via Ollama",
        model_name="ollama/llama3.2:3b",
        model_kind="ollama",
        cache_env="OLLAMA_MODELS",
    ),
    ModelCatalogItem(
        provider="gemini2.5_flash_lite",
        display_name="Gemini 2.5 Flash Lite",
        model_name="gemini/gemini-2.5-flash-lite",
        model_kind="gemini",
        cache_env=None,
        external=True,
    ),
)


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
    current_step: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    cancel_requested: bool = False


class ModelJobService:
    """Job runner for heavyweight model operations.

    The default backend is a small in-process runner for local development and
    tests. When ``RAG_JOB_BACKEND=rq`` is configured, jobs are persisted to the
    database and dispatched to Redis/RQ so long-running model work can survive
    backend restarts and run outside request workers.
    """

    def __init__(self, max_workers: int = 1):
        self._jobs: dict[str, ModelJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="model-job")
        self._db_session_factory: Any | None = None
        self._settings: Any | None = None
        self._rag_service: Any | None = None
        self._summary_model_providers: dict[str, Any] | None = None
        self._gemini_json_client: Any | None = None

    def configure_runtime(
        self,
        *,
        db_session_factory: Any,
        settings: Any,
        rag_service: Any | None = None,
        summary_model_providers: dict[str, Any] | None = None,
        gemini_json_client: Any | None = None,
        mark_interrupted: bool = True,
    ) -> None:
        self._db_session_factory = db_session_factory
        self._settings = settings
        self._rag_service = rag_service
        self._summary_model_providers = summary_model_providers or {}
        self._gemini_json_client = gemini_json_client
        if mark_interrupted:
            self._mark_interrupted_jobs()

    def enqueue(self, payload: ModelJobCreateRequest) -> ModelJobResponse:
        job = ModelJob(
            job_id=str(uuid.uuid4()),
            job_type=payload.job_type,
            model_provider=payload.model_provider,
            model_name=payload.model_name,
            timeout_seconds=payload.timeout_seconds,
            payload=payload.payload,
        )
        if self._use_rq():
            job.current_step = "queued_rq"
            self._persist_job(job)
            return self._enqueue_rq_job(job)
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist_job(job)
        self._executor.submit(self._run_job, job.job_id)
        return self._response(job)

    def enqueue_summary_generation(
        self,
        *,
        patient_id: str,
        request_payload: dict[str, Any],
        tenant_id: str,
        actor_external_id: str,
        model_provider: str,
        timeout_seconds: int = 900,
    ) -> ModelJobResponse:
        job = ModelJob(
            job_id=str(uuid.uuid4()),
            job_type="summary_generation",
            model_provider=model_provider,
            model_name=str(model_provider or "deterministic"),
            timeout_seconds=timeout_seconds,
            payload={
                "patient_id": patient_id,
                "request": request_payload,
                "tenant_id": tenant_id,
                "actor_external_id": actor_external_id,
            },
            current_step="queued",
        )
        if self._use_rq():
            job.current_step = "queued_rq"
            self._persist_job(job)
            return self._enqueue_rq_job(job)
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist_job(job)
        self._executor.submit(self._run_job, job.job_id)
        return self._response(job)

    def enqueue_default_warmups(self, *, timeout_seconds: int = 900) -> ModelJobListResponse:
        responses: list[ModelJobResponse] = []
        for item in DEFAULT_MODEL_CATALOG:
            if not item.warmup_supported:
                continue
            responses.append(
                self.enqueue(
                    ModelJobCreateRequest(
                        job_type="model_warmup",
                        model_provider=item.provider,
                        model_name=item.model_name,
                        timeout_seconds=timeout_seconds,
                        payload={"source": "default_warmup"},
                    )
                )
            )
        return ModelJobListResponse(jobs=responses)

    def get(self, job_id: str) -> ModelJobResponse | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                self._expire_job_if_timed_out(job)
                return self._response(job)
        return self._persisted_response(job_id)

    def list(self) -> ModelJobListResponse:
        persisted = self._list_persisted_jobs()
        if persisted is not None:
            return ModelJobListResponse(jobs=persisted)
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            for job in jobs:
                self._expire_job_if_timed_out(job)
            return ModelJobListResponse(jobs=[self._response(job) for job in jobs])

    def cancel(self, job_id: str) -> ModelJobResponse | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                if job.status in {"completed", "failed", "cancelled", "timed_out"}:
                    return self._response(job)
                job.cancel_requested = True
                if job.status == "queued":
                    job.status = "cancelled"
                    job.finished_at = datetime.now(UTC)
                self._persist_job(job)
                return self._response(job)
        if self._use_rq():
            self._cancel_rq_job(job_id)
        return self._cancel_persisted_job(job_id)

    def readiness(
        self,
        model_names: list[str] | None = None,
        *,
        include_smoke: bool = False,
    ) -> ModelReadinessResponse:
        cache_paths = _cache_path_report()
        requested = model_names or [item.model_name for item in DEFAULT_MODEL_CATALOG]
        models = [
            self._readiness_for_model(model_name, cache_paths=cache_paths, include_smoke=include_smoke)
            for model_name in requested
        ]
        queue_status = self._queue_status()
        return ModelReadinessResponse(
            cache_paths=cache_paths,
            models=models,
            queue_backend=str(queue_status.get("backend") or self._job_backend()),
            queue_name=queue_status.get("queue_name"),
            queue_status=queue_status,
        )

    def reset_for_tests(self) -> None:
        with self._lock:
            self._jobs.clear()

    def run_persisted_job(self, job_id: str) -> ModelJobResponse:
        """Execute a database-persisted job inside an external worker process."""

        job = self._load_persisted_job(job_id)
        if job is None:
            raise RuntimeError(f"Persisted model job '{job_id}' was not found.")
        if job.status in {"completed", "failed", "cancelled", "timed_out"}:
            return self._response(job)
        with self._lock:
            self._jobs[job.job_id] = job
        self._run_job(job.job_id)
        with self._lock:
            return self._response(self._jobs[job.job_id])

    def _job_backend(self) -> str:
        return str(getattr(self._settings, "job_backend", "in_process") or "in_process")

    def _use_rq(self) -> bool:
        return self._job_backend() == "rq"

    def _rq_queue_name(self) -> str:
        return str(getattr(self._settings, "rq_queue_name", "clin_summ_jobs") or "clin_summ_jobs")

    def _redis_url(self) -> str:
        return str(getattr(self._settings, "redis_url", "redis://localhost:6379/0") or "redis://localhost:6379/0")

    def _fallback_to_in_process_enabled(self) -> bool:
        return bool(getattr(self._settings, "job_fallback_to_in_process", True))

    def _submit_in_process_fallback(self, job: ModelJob, reason: str) -> ModelJobResponse:
        job.status = "queued"
        job.progress = 0.0
        job.current_step = "rq_unavailable_fallback_in_process"
        job.error_message = None
        job.payload = {**job.payload, "rq_fallback_reason": reason}
        with self._lock:
            self._jobs[job.job_id] = job
            self._persist_job(job)
        self._executor.submit(self._run_job, job.job_id)
        return self._response(job)

    def _enqueue_rq_job(self, job: ModelJob) -> ModelJobResponse:
        try:
            from redis import Redis
            from rq import Queue
            from rq.worker import Worker

            from ..workers.rq_tasks import run_model_job

            redis_connection = Redis.from_url(self._redis_url())
            redis_connection.ping()
            queue = Queue(self._rq_queue_name(), connection=redis_connection)
            if bool(getattr(self._settings, "rq_require_live_worker", True)):
                workers = Worker.all(connection=redis_connection)
                worker_queues = {
                    worker_queue.name
                    for worker in workers
                    for worker_queue in worker.queues
                }
                windows_worker_count = _windows_worker_count(redis_connection, self._rq_queue_name())
                if self._rq_queue_name() not in worker_queues and windows_worker_count == 0:
                    raise RuntimeError(
                        f"No live RQ worker is registered for queue '{self._rq_queue_name()}'. "
                        "Start one with: python -m scripts.run_rq_worker"
                    )
            queue.enqueue(
                run_model_job,
                job.job_id,
                job_id=job.job_id,
                job_timeout=job.timeout_seconds,
                result_ttl=int(getattr(self._settings, "rq_result_ttl_seconds", 24 * 60 * 60)),
                failure_ttl=int(getattr(self._settings, "rq_failure_ttl_seconds", 7 * 24 * 60 * 60)),
            )
            job.current_step = "queued_rq"
            self._persist_job(job)
            return self._response(job)
        except Exception as exc:
            message = (
                "Redis/RQ job backend is enabled but enqueue failed. "
                f"Check Redis, worker dependencies, and RAG_REDIS_URL. Root error: {type(exc).__name__}: {exc}"
            )
            if self._fallback_to_in_process_enabled():
                return self._submit_in_process_fallback(job, message)
            job.status = "failed"
            job.progress = 0.0
            job.current_step = "rq_enqueue_failed"
            job.error_message = message
            job.finished_at = datetime.now(UTC)
            self._persist_job(job)
            return self._response(job)

    def _cancel_rq_job(self, job_id: str) -> None:
        try:
            from redis import Redis
            from rq.command import send_stop_job_command
            from rq.job import Job

            redis_connection = Redis.from_url(self._redis_url())
            rq_job = Job.fetch(job_id, connection=redis_connection)
            status = str(rq_job.get_status(refresh=True))
            if status == "started":
                send_stop_job_command(redis_connection, job_id)
            else:
                rq_job.cancel()
        except Exception:
            return

    def _queue_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "backend": self._job_backend(),
            "queue_name": self._rq_queue_name() if self._use_rq() else None,
            "enabled": self._use_rq(),
            "redis_url_configured": bool(self._redis_url()),
            "redis_reachable": False,
            "redis_installed": False,
            "rq_installed": False,
            "queued_count": None,
            "worker_count": None,
            "fallback_to_in_process": self._fallback_to_in_process_enabled(),
            "require_live_worker": bool(getattr(self._settings, "rq_require_live_worker", True)),
        }
        if not self._use_rq():
            status["message"] = "Using in-process jobs. Set RAG_JOB_BACKEND=rq to dispatch through Redis/RQ."
            return status
        try:
            from redis import Redis

            status["redis_installed"] = True
        except Exception as exc:
            status["message"] = f"redis package is not installed: {type(exc).__name__}: {exc}"
            return status
        try:
            from rq import Queue
            from rq.worker import Worker

            status["rq_installed"] = True
            redis_connection = Redis.from_url(self._redis_url())
            redis_connection.ping()
            queue = Queue(self._rq_queue_name(), connection=redis_connection)
            status["redis_reachable"] = True
            status["queued_count"] = len(queue)
            rq_worker_count = len(Worker.all(connection=redis_connection))
            windows_worker_count = _windows_worker_count(redis_connection, self._rq_queue_name())
            status["rq_worker_count"] = rq_worker_count
            status["windows_worker_count"] = windows_worker_count
            status["worker_count"] = rq_worker_count + windows_worker_count
            if status["worker_count"] == 0:
                status["message"] = (
                    "Redis is reachable, but no RQ worker is registered. "
                    "Start one with: python -m scripts.run_rq_worker"
                )
            else:
                status["message"] = "Redis/RQ backend is reachable."
        except Exception as exc:
            status["message"] = f"Redis/RQ backend is not reachable: {type(exc).__name__}: {exc}"
        return status

    def _readiness_for_model(
        self,
        model_name: str,
        *,
        cache_paths: dict[str, Any],
        include_smoke: bool,
    ) -> dict[str, Any]:
        item = _catalog_item_for(model_name)
        status = "unknown"
        ready = False
        cached = False
        cache_dir: str | None = None
        health_checks: dict[str, Any] = {}
        message = "No readiness rule is configured for this model."

        if item.model_kind == "deterministic":
            status = "ready"
            ready = True
            cached = True
            message = "Deterministic baseline does not require model cache."
        elif item.model_kind in {"hf_seq2seq", "hf_encoder", "sentence_transformer"}:
            cache_root = cache_paths.get(item.cache_env or "HF_HUB_CACHE", {}).get("value")
            cache_dir_path = _hf_model_cache_dir(item.model_name, cache_root)
            cache_dir = str(cache_dir_path)
            cached = cache_dir_path.exists()
            c_drive = bool(cache_paths.get(item.cache_env or "HF_HUB_CACHE", {}).get("points_to_c_drive"))
            ready = cached and not c_drive
            status = "ready" if ready else ("cache_on_c_drive" if c_drive else "missing_from_cache")
            message = (
                "Model is present in local Hugging Face cache."
                if ready
                else "Model cache is missing or points to C drive. Warmup will use local_files_only."
            )
        elif item.model_kind == "ollama":
            health_checks = _ollama_model_health(_ollama_model_name(item.model_name), include_smoke=include_smoke)
            ready = bool(health_checks.get("ollama_running") and health_checks.get("model_present"))
            cached = bool(health_checks.get("model_present"))
            cache_dir = health_checks.get("ollama_models_dir")
            status = "ready" if ready else ("ollama_offline" if not health_checks.get("ollama_running") else "missing_from_ollama")
            message = _ollama_health_message(item.provider, health_checks)
        elif item.model_kind == "gemini":
            health_checks = _gemini_key_health()
            ready = bool(health_checks.get("api_key_present") and health_checks.get("api_key_format_valid"))
            cached = ready
            status = "ready" if ready else "configuration_required"
            message = str(health_checks.get("message"))

        return {
            "provider": item.provider,
            "display_name": item.display_name,
            "model_name": item.model_name,
            "model_kind": item.model_kind,
            "status": status,
            "ready": ready,
            "cached": cached,
            "cache_dir": cache_dir,
            "warmup_supported": item.warmup_supported,
            "external": item.external,
            "message": message,
            "health_checks": health_checks,
        }

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.cancel_requested or job.status == "cancelled":
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                self._persist_job(job)
                return
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.progress = 0.05
            job.current_step = "starting"
            self._persist_job(job)
        started = time.perf_counter()
        try:
            self._run_job_impl(job_id, started)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                if job.status in {"cancelled", "timed_out"}:
                    job.error_message = str(exc)
                    self._persist_job(job)
                    return
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.now(UTC)
                self._persist_job(job)

    def _run_job_impl(self, job_id: str, started: float) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.progress = 0.15
            job_type = job.job_type
            model_name = job.model_name
        if job_type == "summary_generation":
            self._run_summary_generation(job_id, started)
        elif job_type == "model_warmup":
            self._warm_model(job_id, model_name, started)
        elif job_type == "provider_healthcheck":
            self._provider_healthcheck(job_id, model_name, started)
        elif job_type == "cache_readiness":
            self._cache_readiness(job_id, started)
        else:
            self._simulate_generation(job_id, started)
        with self._lock:
            job = self._jobs[job_id]
            if job.status in {"cancelled", "timed_out"}:
                return
            job.status = "completed"
            job.finished_at = datetime.now(UTC)
            job.progress = 1.0
            job.current_step = job.current_step or "completed"
            job.result = job.result or {
                "message": "Job completed.",
                "model_provider": job.model_provider,
                "model_name": job.model_name,
            }
            self._persist_job(job)

    def _run_summary_generation(self, job_id: str, started: float) -> None:
        if self._db_session_factory is None:
            raise RuntimeError("Summary generation jobs require a configured database session factory.")
        with self._lock:
            job = self._jobs[job_id]
            patient_id = str(job.payload.get("patient_id") or "")
            request_payload = dict(job.payload.get("request") or {})
            tenant_id = str(job.payload.get("tenant_id") or "")
            actor_external_id = str(job.payload.get("actor_external_id") or "")
        self._set_progress(job_id, 0.12, "patient_scope")

        from ..repositories import AuditRepository, SummaryRepository
        from ..services.audit_service import AuditService
        from ..services.deterministic_summary_service import DeterministicSummaryService
        from ..services.safety_service import SafetyService
        from ..persistence_schemas import SummaryGenerateRequest

        request = SummaryGenerateRequest.model_validate(request_payload)
        session = self._db_session_factory()
        try:
            self._check_cancel_or_timeout(job_id, started)
            self._set_progress(job_id, 0.24, "retrieval_quality_gate")
            service = DeterministicSummaryService(
                SummaryRepository(session),
                SafetyService(),
                AuditService(AuditRepository(session)),
                self._settings,
                self._gemini_json_client,
                self._summary_model_providers,
                self._rag_service,
            )
            self._set_progress(job_id, 0.38, "clinical_context_builder")
            self._check_cancel_or_timeout(job_id, started)
            self._set_progress(job_id, 0.54, "provider_generation")
            previous_gateway_timeout = os.environ.get("LLM_GATEWAY_TIMEOUT_SECONDS")
            remaining_timeout = max(5.0, min(float(job.timeout_seconds), self._remaining_timeout(job_id, started) - 2.0))
            os.environ["LLM_GATEWAY_TIMEOUT_SECONDS"] = str(int(remaining_timeout))
            try:
                generated = service.generate(
                    patient_id,
                    request,
                    tenant_id=tenant_id,
                    actor_external_id=actor_external_id,
                )
            finally:
                if previous_gateway_timeout is None:
                    os.environ.pop("LLM_GATEWAY_TIMEOUT_SECONDS", None)
                else:
                    os.environ["LLM_GATEWAY_TIMEOUT_SECONDS"] = previous_gateway_timeout
            self._check_cancel_or_timeout(job_id, started)
            self._set_progress(job_id, 0.86, "citation_validation")
            session.commit()
            self._set_progress(job_id, 0.94, "draft_ready")
            with self._lock:
                job = self._jobs[job_id]
                job.result = {
                    "message": "Draft summary generated asynchronously.",
                    "summary_id": str(generated.summary_id),
                    "patient_id": str(generated.patient_id),
                    "encounter_id": str(generated.encounter_id) if generated.encounter_id else None,
                    "model_provider": generated.model_provider,
                    "model_name": generated.model_name,
                    "generation_flow": generated.generation_flow,
                    "retrieval_quality_gate": generated.retrieval_quality_gate,
                    "citation_coverage": str(generated.citation_coverage) if generated.citation_coverage is not None else None,
                    "unsupported_claim_count": generated.unsupported_claim_count,
                    "conflict_count": generated.conflict_count,
                }
                self._persist_job(job)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _warm_model(self, job_id: str, model_name: str, started: float) -> None:
        item = _catalog_item_for(model_name)
        self._check_cancel_or_timeout(job_id, started)
        with self._lock:
            self._jobs[job_id].progress = 0.3
        if item.model_kind == "deterministic":
            result = {"message": "Deterministic baseline is always ready.", "model_name": item.model_name}
        elif item.model_kind == "sentence_transformer":
            result = self._warm_sentence_transformer(job_id, item, started)
        elif item.model_kind == "hf_encoder":
            result = self._warm_hf_encoder(job_id, item, started)
        elif item.model_kind == "hf_seq2seq":
            result = self._warm_hf_seq2seq(job_id, item, started)
        elif item.model_kind == "ollama":
            result = self._warm_ollama(job_id, item, started)
        elif item.model_kind == "gemini":
            result = self._warm_gemini(job_id, item, started)
        else:
            raise RuntimeError(f"No warmup implementation for model '{model_name}'.")
        with self._lock:
            job = self._jobs[job_id]
            job.progress = 0.92
            job.result = result
            self._persist_job(job)

    def _provider_healthcheck(self, job_id: str, model_name: str, started: float) -> None:
        self._check_cancel_or_timeout(job_id, started)
        cache_paths = _cache_path_report()
        readiness = self._readiness_for_model(model_name, cache_paths=cache_paths, include_smoke=True)
        with self._lock:
            self._jobs[job_id].progress = 0.92
            self._jobs[job_id].result = readiness
            self._persist_job(self._jobs[job_id])

    def _cache_readiness(self, job_id: str, started: float) -> None:
        self._check_cancel_or_timeout(job_id, started)
        payload = self.readiness(include_smoke=False)
        with self._lock:
            self._jobs[job_id].progress = 0.92
            self._jobs[job_id].result = payload.model_dump(mode="json")
            self._persist_job(self._jobs[job_id])

    def _warm_sentence_transformer(
        self,
        job_id: str,
        item: ModelCatalogItem,
        started: float,
    ) -> dict[str, Any]:
        self._check_cancel_or_timeout(job_id, started)
        from sentence_transformers import SentenceTransformer

        cache_folder = os.environ.get("HF_HUB_CACHE") or os.environ.get("HF_HOME") or "D:/hf_cache/hub"
        load_started = time.perf_counter()
        model = SentenceTransformer(item.model_name, cache_folder=cache_folder, local_files_only=True)
        self._check_cancel_or_timeout(job_id, started)
        with self._lock:
            self._jobs[job_id].progress = 0.75
        vector = model.encode(["clinical retrieval warmup"], normalize_embeddings=True)
        return {
            "message": "SentenceTransformer loaded from local cache.",
            "model_name": item.model_name,
            "cache_folder": cache_folder,
            "embedding_dimension": int(vector.shape[-1]),
            "latency_ms": int((time.perf_counter() - load_started) * 1000),
            "local_files_only": True,
        }

    def _warm_hf_encoder(self, job_id: str, item: ModelCatalogItem, started: float) -> dict[str, Any]:
        self._check_cancel_or_timeout(job_id, started)
        from transformers import AutoModel, AutoTokenizer

        cache_dir = os.environ.get("HF_HUB_CACHE", "D:/hf_cache/hub")
        load_started = time.perf_counter()
        AutoTokenizer.from_pretrained(item.model_name, cache_dir=cache_dir, local_files_only=True)
        model = AutoModel.from_pretrained(item.model_name, cache_dir=cache_dir, local_files_only=True)
        return {
            "message": "Encoder/evaluator model loaded from local cache.",
            "model_name": item.model_name,
            "cache_dir": cache_dir,
            "parameter_count": _parameter_count(model),
            "latency_ms": int((time.perf_counter() - load_started) * 1000),
            "local_files_only": True,
        }

    def _warm_hf_seq2seq(self, job_id: str, item: ModelCatalogItem, started: float) -> dict[str, Any]:
        self._check_cancel_or_timeout(job_id, started)
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        cache_dir = os.environ.get("HF_HUB_CACHE", "D:/hf_cache/hub")
        load_started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(item.model_name, cache_dir=cache_dir, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(item.model_name, cache_dir=cache_dir, local_files_only=True)
        self._check_cancel_or_timeout(job_id, started)
        tokens = tokenizer("Warmup: source evidence confirms medication and diagnosis.", return_tensors="pt", truncation=True)
        output = model.generate(**tokens, max_new_tokens=24, num_beams=2)
        text = tokenizer.decode(output[0], skip_special_tokens=True).strip()
        return {
            "message": "Seq2Seq model loaded and generated a smoke output from local cache.",
            "model_name": item.model_name,
            "cache_dir": cache_dir,
            "parameter_count": _parameter_count(model),
            "latency_ms": int((time.perf_counter() - load_started) * 1000),
            "smoke_output_preview": text[:160],
            "local_files_only": True,
        }

    def _warm_ollama(self, job_id: str, item: ModelCatalogItem, started: float) -> dict[str, Any]:
        self._check_cancel_or_timeout(job_id, started)
        base_url = os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434").rstrip("/")
        model_name = _ollama_model_name(item.model_name)
        health = _ollama_model_health(model_name, include_smoke=False)
        if not health.get("ollama_running"):
            raise RuntimeError(f"Ollama is not reachable at {base_url}: {health.get('error') or 'offline'}")
        if not health.get("model_present"):
            raise RuntimeError(f"Ollama model '{model_name}' is not present. Run: ollama pull {model_name}")
        body = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Reply in English. Use exactly: OK_READY",
                },
                {"role": "user", "content": "Warm up clinical summarization model."},
            ],
            "stream": False,
            "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
            "options": {"temperature": 0.0, "num_predict": 16, "num_ctx": 2048},
        }
        warm_started = time.perf_counter()
        response = _http_json(f"{base_url}/api/chat", method="POST", body=body, timeout=min(30.0, self._remaining_timeout(job_id, started)))
        content = _ollama_content(response)
        if not content:
            raise RuntimeError(f"Ollama model '{model_name}' returned an empty warmup response.")
        return {
            "message": "Ollama model responded to warmup prompt.",
            "model_name": model_name,
            "api_base": base_url,
            "ollama_models_dir": os.environ.get("OLLAMA_MODELS") or None,
            "latency_ms": int((time.perf_counter() - warm_started) * 1000),
            "smoke_output_preview": content[:160],
        }

    def _warm_gemini(self, job_id: str, item: ModelCatalogItem, started: float) -> dict[str, Any]:
        self._check_cancel_or_timeout(job_id, started)
        health = _gemini_key_health()
        if not health.get("api_key_present"):
            raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY.")
        if not health.get("api_key_format_valid"):
            raise RuntimeError("Gemini API key is present but does not look valid.")
        return {
            "message": "Gemini key/configuration looks ready. Live cloud warmup is intentionally disabled by default.",
            "model_name": item.model_name,
            "external_call_performed": False,
            "health_checks": health,
        }

    def _simulate_generation(self, job_id: str, started: float) -> None:
        with self._lock:
            job = self._jobs[job_id]
            simulate_seconds = float(job.payload.get("simulate_seconds") or 0.15)
        steps = max(3, int(simulate_seconds / 0.1))
        for index in range(steps):
            time.sleep(min(0.1, max(0.01, simulate_seconds / steps)))
            self._check_cancel_or_timeout(job_id, started)
            with self._lock:
                self._jobs[job_id].progress = min(0.9, 0.2 + ((index + 1) / steps) * 0.7)
                self._jobs[job_id].current_step = "simulated_generation"
                self._persist_job(self._jobs[job_id])
        with self._lock:
            job = self._jobs[job_id]
            job.result = {
                "message": "Simulated generation completed. Use model_warmup/provider_healthcheck for live model operations.",
                "model_provider": job.model_provider,
                "model_name": job.model_name,
                "simulated": True,
            }
            self._persist_job(job)

    def _check_cancel_or_timeout(self, job_id: str, started: float) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                self._persist_job(job)
                raise RuntimeError("Job cancelled.")
            if time.perf_counter() - started > job.timeout_seconds:
                job.status = "timed_out"
                job.finished_at = datetime.now(UTC)
                self._persist_job(job)
                raise RuntimeError("Job timed out.")

    def _set_progress(self, job_id: str, progress: float, current_step: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                raise RuntimeError("Job cancelled.")
            job.progress = max(0.0, min(1.0, progress))
            job.current_step = current_step
            self._persist_job(job)

    def _remaining_timeout(self, job_id: str, started: float) -> float:
        with self._lock:
            timeout_seconds = self._jobs[job_id].timeout_seconds
        return max(1.0, timeout_seconds - (time.perf_counter() - started))

    @staticmethod
    def _response(job: ModelJob) -> ModelJobResponse:
        return ModelJobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            model_provider=job.model_provider,
            model_name=job.model_name,
            status=job.status,  # type: ignore[arg-type]
            progress=round(job.progress, 4),
            current_step=job.current_step,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            timeout_seconds=job.timeout_seconds,
            result=job.result,
            error_message=job.error_message,
        )

    def _persist_job(self, job: ModelJob) -> None:
        if self._db_session_factory is None:
            return
        try:
            from ..models import ModelJobRecord

            session = self._db_session_factory()
            try:
                job_uuid = uuid.UUID(job.job_id)
                record = session.get(ModelJobRecord, job_uuid)
                if record is None:
                    record = ModelJobRecord(job_id=job_uuid)
                    session.add(record)
                record.job_type = job.job_type
                record.model_provider = job.model_provider
                record.model_name = job.model_name
                record.status = job.status
                record.progress = float(job.progress)
                record.current_step = job.current_step
                record.timeout_seconds = job.timeout_seconds
                record.payload = job.payload
                record.result = job.result
                record.error_message = job.error_message
                record.started_at = job.started_at
                record.finished_at = job.finished_at
                record.created_at = job.created_at
                session.commit()
            finally:
                session.close()
        except Exception:
            # Keep local/dev generation working even if the optional job table
            # migration has not been applied yet.
            return

    def _persisted_response(self, job_id: str) -> ModelJobResponse | None:
        if self._db_session_factory is None:
            return None
        try:
            from ..models import ModelJobRecord

            session = self._db_session_factory()
            try:
                record = session.get(ModelJobRecord, uuid.UUID(job_id))
                if record is not None:
                    self._expire_record_if_timed_out(session, record)
                return self._response_from_record(record) if record else None
            finally:
                session.close()
        except Exception:
            return None

    def _load_persisted_job(self, job_id: str) -> ModelJob | None:
        if self._db_session_factory is None:
            return None
        try:
            from ..models import ModelJobRecord

            session = self._db_session_factory()
            try:
                record = session.get(ModelJobRecord, uuid.UUID(job_id))
                return self._job_from_record(record) if record else None
            finally:
                session.close()
        except Exception:
            return None

    def _list_persisted_jobs(self) -> list[ModelJobResponse] | None:
        if self._db_session_factory is None:
            return None
        try:
            from ..models import ModelJobRecord

            session = self._db_session_factory()
            try:
                rows = session.scalars(
                    select(ModelJobRecord).order_by(ModelJobRecord.created_at.desc()).limit(200)
                ).all()
                changed = False
                for row in rows:
                    changed = self._expire_record_if_timed_out(session, row, commit=False) or changed
                if changed:
                    session.commit()
                return [self._response_from_record(row) for row in rows]
            finally:
                session.close()
        except Exception:
            return None

    def _cancel_persisted_job(self, job_id: str) -> ModelJobResponse | None:
        if self._db_session_factory is None:
            return None
        try:
            from ..models import ModelJobRecord

            session = self._db_session_factory()
            try:
                record = session.get(ModelJobRecord, uuid.UUID(job_id))
                if record is None:
                    return None
                if record.status not in {"completed", "failed", "cancelled", "timed_out"}:
                    record.status = "cancelled"
                    record.finished_at = datetime.now(UTC)
                    record.current_step = "cancelled"
                    session.commit()
                return self._response_from_record(record)
            finally:
                session.close()
        except Exception:
            return None

    def _mark_interrupted_jobs(self) -> None:
        if self._use_rq():
            return
        if self._db_session_factory is None:
            return
        try:
            from ..models import ModelJobRecord

            session = self._db_session_factory()
            try:
                rows = session.scalars(
                    select(ModelJobRecord).where(ModelJobRecord.status.in_(["queued", "running"]))
                ).all()
                interrupted_count = 0
                for record in rows:
                    if record.current_step in {"queued_rq", "worker_initializing"}:
                        continue
                    record.status = "failed"
                    record.current_step = "interrupted"
                    record.finished_at = datetime.now(UTC)
                    record.error_message = (
                        "Backend restarted before this in-process job completed. Re-enqueue the job."
                    )
                    interrupted_count += 1
                if interrupted_count:
                    session.commit()
            finally:
                session.close()
        except Exception:
            return

    @staticmethod
    def _job_timeout_anchor(job: ModelJob) -> datetime:
        return _ensure_aware_utc(job.started_at or job.created_at)

    def _expire_job_if_timed_out(self, job: ModelJob) -> bool:
        if job.status in {"completed", "failed", "cancelled", "timed_out"}:
            return False
        elapsed = (datetime.now(UTC) - self._job_timeout_anchor(job)).total_seconds()
        if elapsed <= job.timeout_seconds:
            return False
        job.status = "timed_out"
        job.finished_at = datetime.now(UTC)
        job.current_step = "timed_out"
        job.error_message = (
            f"Job timed out after exceeding timeout_seconds={job.timeout_seconds}. "
            "The provider call may still be shutting down; re-enqueue after checking provider readiness."
        )
        self._persist_job(job)
        return True

    @staticmethod
    def _expire_record_if_timed_out(session: Any, record: Any, *, commit: bool = True) -> bool:
        if record.status in {"completed", "failed", "cancelled", "timed_out"}:
            return False
        anchor = _ensure_aware_utc(record.started_at or record.created_at)
        elapsed = (datetime.now(UTC) - anchor).total_seconds()
        if elapsed <= int(record.timeout_seconds or 900):
            return False
        record.status = "timed_out"
        record.finished_at = datetime.now(UTC)
        record.current_step = "timed_out"
        record.error_message = (
            f"Job timed out after exceeding timeout_seconds={int(record.timeout_seconds or 900)}. "
            "The provider call may still be shutting down; re-enqueue after checking provider readiness."
        )
        if commit:
            session.commit()
        return True

    @staticmethod
    def _response_from_record(record: Any) -> ModelJobResponse:
        return ModelJobResponse(
            job_id=str(record.job_id),
            job_type=record.job_type,
            model_provider=record.model_provider,
            model_name=record.model_name,
            status=record.status,
            progress=round(float(record.progress or 0.0), 4),
            current_step=record.current_step,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            timeout_seconds=record.timeout_seconds,
            result=record.result,
            error_message=record.error_message,
        )

    @staticmethod
    def _job_from_record(record: Any) -> ModelJob:
        return ModelJob(
            job_id=str(record.job_id),
            job_type=record.job_type,
            model_provider=record.model_provider,
            model_name=record.model_name,
            timeout_seconds=int(record.timeout_seconds or 900),
            payload=dict(record.payload or {}),
            status=record.status,
            progress=float(record.progress or 0.0),
            current_step=record.current_step,
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            result=record.result,
            error_message=record.error_message,
        )


def _cache_path_report() -> dict[str, Any]:
    report: dict[str, Any] = {}
    for key in ("HF_HOME", "HF_HUB_CACHE", "HF_DATASETS_CACHE", "TRANSFORMERS_CACHE", "OLLAMA_MODELS"):
        raw_value = os.environ.get(key)
        path = Path(raw_value) if raw_value else None
        report[key] = {
            "value": str(path) if path else None,
            "exists": bool(path and path.exists()),
            "points_to_c_drive": bool(raw_value and raw_value.lower().startswith("c:")),
        }
    return report


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _windows_worker_count(redis_connection: Any, queue_name: str) -> int:
    pattern = f"clin_summ:windows_worker:{queue_name}:*"
    return sum(1 for _key in redis_connection.scan_iter(match=pattern, count=100))


def _catalog_item_for(model_name: str) -> ModelCatalogItem:
    normalized = model_name.strip()
    for item in DEFAULT_MODEL_CATALOG:
        if normalized in {item.provider, item.model_name, _ollama_model_name(item.model_name)}:
            return item
    if normalized.startswith("ollama/") or normalized in {"qwen2.5:3b", "llama3.2:3b"}:
        provider = normalized.removeprefix("ollama/").split(":", 1)[0]
        return ModelCatalogItem(provider=provider, display_name=normalized, model_name=normalized, model_kind="ollama", cache_env="OLLAMA_MODELS")
    if normalized.startswith("gemini/") or "gemini" in normalized:
        return ModelCatalogItem(provider="gemini", display_name=normalized, model_name=normalized, model_kind="gemini", cache_env=None, external=True)
    if normalized.startswith("sentence-transformers/"):
        return ModelCatalogItem(provider=normalized, display_name=normalized, model_name=normalized, model_kind="sentence_transformer")
    if normalized in {"roberta-large", "bert-base-uncased"}:
        return ModelCatalogItem(provider=normalized, display_name=normalized, model_name=normalized, model_kind="hf_encoder")
    if "/" in normalized:
        return ModelCatalogItem(provider=normalized, display_name=normalized, model_name=normalized, model_kind="hf_seq2seq")
    return ModelCatalogItem(provider=normalized, display_name=normalized, model_name=normalized, model_kind="unknown", warmup_supported=False)


def _hf_model_cache_dir(model_name: str, cache_root: str | None) -> Path:
    root = Path(cache_root or os.environ.get("HF_HUB_CACHE") or "D:/hf_cache/hub")
    return root / ("models--" + model_name.replace("/", "--"))


def _ollama_model_name(model_name: str) -> str:
    clean = model_name.strip()
    for prefix in ("ollama_chat/", "ollama/"):
        if clean.startswith(prefix):
            return clean[len(prefix) :]
    return clean


def _ollama_model_health(model_name: str, *, include_smoke: bool) -> dict[str, Any]:
    base_url = os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434").rstrip("/")
    result: dict[str, Any] = {
        "ollama_running": False,
        "model_present": False,
        "model_name": model_name,
        "ollama_models_dir": os.environ.get("OLLAMA_MODELS") or None,
        "api_base": base_url,
        "warmup_status": "not_run",
        "warmup_latency_ms": None,
    }
    try:
        tags = _http_json(f"{base_url}/api/tags", timeout=2.0)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    result["ollama_running"] = True
    names = [
        str(item.get("name") or "")
        for item in tags.get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]
    result["available_models"] = names
    result["model_present"] = model_name in set(names)
    if include_smoke and result["model_present"]:
        result.update(_ollama_smoke(base_url, model_name))
    return result


def _ollama_smoke(base_url: str, model_name: str) -> dict[str, Any]:
    body = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "stream": False,
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
        "options": {"temperature": 0.0, "num_predict": 8, "num_ctx": 1024},
    }
    started = time.perf_counter()
    try:
        payload = _http_json(f"{base_url}/api/chat", method="POST", body=body, timeout=12.0)
    except Exception as exc:
        return {
            "warmup_status": "failed",
            "warmup_latency_ms": int((time.perf_counter() - started) * 1000),
            "warmup_error": f"{type(exc).__name__}: {exc}",
        }
    content = _ollama_content(payload)
    return {
        "warmup_status": "passed" if content else "failed",
        "warmup_latency_ms": int((time.perf_counter() - started) * 1000),
        "warmup_response_preview": content[:80],
    }


def _ollama_content(payload: dict[str, Any]) -> str:
    message = payload.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "").strip()
    return str(payload.get("response") or "").strip()


def _ollama_health_message(provider: str, health: dict[str, Any]) -> str:
    if not health.get("ollama_running"):
        return f"{provider} requires Ollama running at {health.get('api_base')}."
    if not health.get("model_present"):
        return f"{provider} requires local model {health.get('model_name')} in ollama list."
    if health.get("warmup_status") == "failed":
        return f"{provider} model exists but warmup failed: {health.get('warmup_error') or 'empty response'}."
    if health.get("warmup_status") == "passed":
        return f"{provider} passed a live prompt check in {health.get('warmup_latency_ms')} ms."
    return f"{provider} model is present in Ollama."


def _gemini_key_health() -> dict[str, Any]:
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("RAG_GEMINI_API_KEY") or "").strip()
    present = bool(key)
    format_valid = present and len(key) >= 20 and key.startswith("AIza")
    return {
        "api_key_present": present,
        "api_key_format_valid": format_valid,
        "cloud_validation": "not_run",
        "message": (
            "Gemini key is present and format looks valid. Live cloud validation is not run from readiness."
            if format_valid
            else "Gemini key is missing or does not look like a Google API key."
        ),
    }


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urlrequest.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlrequest.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urlerror.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


def _parameter_count(model: Any) -> int:
    try:
        return int(sum(parameter.numel() for parameter in model.parameters()))
    except Exception:
        return 0


model_job_service = ModelJobService()
