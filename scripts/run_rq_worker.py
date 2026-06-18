from __future__ import annotations

import argparse
import json
import os
import socket
import traceback

from backend.app.config import get_settings
from backend.app.runtime_env import load_runtime_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the clinical summarization Redis/RQ worker.")
    parser.add_argument("--queue", default=None, help="RQ queue name. Defaults to RAG_RQ_QUEUE_NAME.")
    parser.add_argument("--redis-url", default=None, help="Redis URL. Defaults to RAG_REDIS_URL.")
    parser.add_argument(
        "--worker-class",
        choices=("windows", "simple", "spawn", "default"),
        default="windows",
        help="Use windows for local heavy model jobs, simple for tiny smoke tests, default/spawn for Unix workers.",
    )
    parser.add_argument("--burst", action="store_true", help="Exit when the queue is empty.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_runtime_env(enable_model_defaults=True, job_backend="rq")
    settings = get_settings()
    redis_url = args.redis_url or settings.redis_url
    queue_name = args.queue or settings.rq_queue_name

    try:
        from redis import Redis
        from rq import Queue, SimpleWorker, SpawnWorker, Worker
    except Exception as exc:  # pragma: no cover - exercised in deployment setup
        raise SystemExit(
            "Redis/RQ dependencies are not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    redis_connection = Redis.from_url(redis_url)
    redis_connection.ping()
    queue = Queue(queue_name, connection=redis_connection)
    if args.worker_class == "windows":
        _run_windows_worker(queue, redis_connection, burst=args.burst)
        return
    worker_cls = {"simple": SimpleWorker, "spawn": SpawnWorker, "default": Worker}[args.worker_class]
    worker = worker_cls([queue], connection=redis_connection)
    print(f"Starting RQ worker for queue '{queue_name}' at {redis_url} ({args.worker_class}).")
    worker.work(burst=args.burst)


def _run_windows_worker(queue, redis_connection, *, burst: bool) -> None:
    from backend.app.workers.rq_tasks import run_model_job

    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    heartbeat_key = f"clin_summ:windows_worker:{queue.name}:{worker_id}"
    os.environ["RAG_WINDOWS_WORKER_HEARTBEAT_KEY"] = heartbeat_key
    _write_windows_worker_heartbeat(
        redis_connection,
        heartbeat_key,
        queue_name=queue.name,
        worker_id=worker_id,
        state="idle",
    )
    print(
        f"Starting Windows-safe Redis worker '{worker_id}' "
        f"for queue '{queue.name}'.",
        flush=True,
    )
    try:
        while True:
            _write_windows_worker_heartbeat(
                redis_connection,
                heartbeat_key,
                queue_name=queue.name,
                worker_id=worker_id,
                state="idle",
            )
            raw_job_id = redis_connection.lpop(queue.key) if burst else _blocking_pop(redis_connection, queue.key)
            if raw_job_id is None:
                if burst:
                    print("Queue is empty; worker burst complete.", flush=True)
                    return
                continue
            job_id = raw_job_id.decode("utf-8") if isinstance(raw_job_id, bytes) else str(raw_job_id)
            _write_windows_worker_heartbeat(
                redis_connection,
                heartbeat_key,
                queue_name=queue.name,
                worker_id=worker_id,
                state="busy",
                job_id=job_id,
            )
            print(f"Running model job {job_id} from queue '{queue.name}'.", flush=True)
            try:
                result = run_model_job(job_id)
                if result.get("status") == "completed":
                    print(f"Completed model job {job_id}.", flush=True)
                else:
                    error_message = result.get("error_message") or (
                        f"Model job ended with status {result.get('status')}"
                    )
                    print(f"Model job {job_id} failed: {error_message}", flush=True)
            except Exception:
                print(traceback.format_exc(), flush=True)
                if burst:
                    raise
            finally:
                _write_windows_worker_heartbeat(
                    redis_connection,
                    heartbeat_key,
                    queue_name=queue.name,
                    worker_id=worker_id,
                    state="idle",
                )
    finally:
        redis_connection.delete(heartbeat_key)
        os.environ.pop("RAG_WINDOWS_WORKER_HEARTBEAT_KEY", None)


def _blocking_pop(redis_connection, queue_key: str):
    item = redis_connection.blpop(queue_key, timeout=5)
    if not item:
        return None
    _key, value = item
    return value


def _write_windows_worker_heartbeat(
    redis_connection,
    heartbeat_key: str,
    *,
    queue_name: str,
    worker_id: str,
    state: str,
    job_id: str | None = None,
) -> None:
    payload = {
        "worker_id": worker_id,
        "queue": queue_name,
        "state": state,
        "job_id": job_id,
    }
    redis_connection.set(heartbeat_key, json.dumps(payload), ex=20 * 60)


if __name__ == "__main__":
    main()
