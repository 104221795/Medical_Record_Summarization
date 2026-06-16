from __future__ import annotations

import argparse
import json
import time

from backend.app.config import get_settings
from backend.app.db.session import build_engine_from_settings, create_session_factory
from backend.app.persistence_schemas import ModelJobCreateRequest
from backend.app.services.background_jobs import ModelJobService


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a tiny Redis/RQ smoke job against the configured database.")
    parser.add_argument("--queue", default=None, help="RQ queue name. Defaults to configured RAG_RQ_QUEUE_NAME.")
    parser.add_argument("--redis-url", default=None, help="Redis URL. Defaults to configured RAG_REDIS_URL.")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--run-worker-burst", action="store_true", help="Run an RQ SimpleWorker burst after enqueueing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_settings = get_settings()
    settings = base_settings.model_copy(
        update={
            "job_backend": "rq",
            "redis_url": args.redis_url or base_settings.redis_url,
            "rq_queue_name": args.queue or base_settings.rq_queue_name,
            "job_fallback_to_in_process": False,
            "rq_require_live_worker": False,
        }
    )
    session_factory = create_session_factory(build_engine_from_settings(settings))
    service = ModelJobService(max_workers=1)
    service.configure_runtime(db_session_factory=session_factory, settings=settings, rag_service=None)
    created = service.enqueue(
        ModelJobCreateRequest(
            job_type="summarization_generation",
            model_provider="deterministic",
            model_name="deterministic_sentence_baseline",
            timeout_seconds=10,
            payload={"simulate_seconds": 0.05, "source": "rq_smoke_test"},
        )
    )
    print(json.dumps({"enqueued": created.model_dump(mode="json")}, indent=2))
    if args.run_worker_burst:
        _run_worker_burst(settings.redis_url, settings.rq_queue_name)
    final = _wait_for_job(service, created.job_id, args.timeout_seconds)
    print(json.dumps({"final": final.model_dump(mode="json") if final else None}, indent=2))
    if final is None or final.status != "completed":
        raise SystemExit(1)


def _run_worker_burst(redis_url: str, queue_name: str) -> None:
    from redis import Redis
    from rq import Queue, SimpleWorker

    redis_connection = Redis.from_url(redis_url)
    queue = Queue(queue_name, connection=redis_connection)
    worker = SimpleWorker([queue], connection=redis_connection)
    worker.work(burst=True)


def _wait_for_job(service: ModelJobService, job_id: str, timeout_seconds: float):
    deadline = time.perf_counter() + timeout_seconds
    latest = None
    while time.perf_counter() < deadline:
        latest = service.get(job_id)
        if latest and latest.status in TERMINAL_STATUSES:
            return latest
        time.sleep(0.2)
    return latest


if __name__ == "__main__":
    main()
