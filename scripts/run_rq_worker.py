from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import threading
import time
import traceback
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db.session import build_engine_from_settings, create_session_factory
from backend.app.models import ModelJobRecord
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
        _run_windows_worker(queue, redis_connection, burst=args.burst, settings=settings)
        return
    worker_cls = {"simple": SimpleWorker, "spawn": SpawnWorker, "default": Worker}[args.worker_class]
    worker = worker_cls([queue], connection=redis_connection)
    print(f"Starting RQ worker for queue '{queue_name}' at {redis_url} ({args.worker_class}).")
    worker.work(burst=args.burst)


def _run_windows_worker(queue, redis_connection, *, burst: bool, settings=None) -> None:
    from backend.app.workers.rq_tasks import run_model_job

    settings = settings or get_settings()
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    heartbeat_key = f"clin_summ:windows_worker:{queue.name}:{worker_id}"
    os.environ["RAG_WINDOWS_WORKER_HEARTBEAT_KEY"] = heartbeat_key
    os.environ["RAG_WINDOWS_WORKER_ID"] = worker_id
    stop_event = threading.Event()
    state_lock = threading.Lock()
    worker_state = {"state": "idle", "job_id": None}
    heartbeat_seconds = int(getattr(settings, "rq_worker_heartbeat_seconds", 5))
    stale_seconds = int(getattr(settings, "rq_worker_stale_seconds", 20))
    session_factory = create_session_factory(build_engine_from_settings(settings))
    recovered = _recover_stale_jobs(
        session_factory,
        redis_connection,
        queue,
        stale_seconds=stale_seconds,
    )
    if recovered:
        print(f"Recovered {recovered} stale persisted job(s).", flush=True)

    def request_shutdown(_signum=None, _frame=None) -> None:
        stop_event.set()

    previous_handlers = {}
    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signum = getattr(signal, signal_name, None)
        if signum is not None:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_shutdown)

    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(
            redis_connection,
            heartbeat_key,
            queue.name,
            worker_id,
            stop_event,
            state_lock,
            worker_state,
            heartbeat_seconds,
            stale_seconds,
        ),
        daemon=True,
        name="clin-summ-worker-heartbeat",
    )
    heartbeat_thread.start()
    print(
        f"Starting Windows-safe Redis worker '{worker_id}' "
        f"for queue '{queue.name}'.",
        flush=True,
    )
    try:
        while not stop_event.is_set():
            raw_job_id = redis_connection.lpop(queue.key) if burst else _blocking_pop(redis_connection, queue.key)
            if raw_job_id is None:
                if burst:
                    print("Queue is empty; worker burst complete.", flush=True)
                    return
                continue
            job_id = raw_job_id.decode("utf-8") if isinstance(raw_job_id, bytes) else str(raw_job_id)
            with state_lock:
                worker_state.update(state="busy", job_id=job_id)
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
            finally:
                with state_lock:
                    worker_state.update(state="idle", job_id=None)
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=max(1.0, heartbeat_seconds + 1.0))
        redis_connection.delete(heartbeat_key)
        os.environ.pop("RAG_WINDOWS_WORKER_HEARTBEAT_KEY", None)
        os.environ.pop("RAG_WINDOWS_WORKER_ID", None)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


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
    stale_seconds: int = 20,
) -> None:
    payload = {
        "worker_id": worker_id,
        "queue": queue_name,
        "state": state,
        "job_id": job_id,
        "heartbeat_at": time.time(),
        "heartbeat_at_iso": datetime.now(UTC).isoformat(),
    }
    redis_connection.set(heartbeat_key, json.dumps(payload), ex=max(stale_seconds * 2, 10))


def _heartbeat_loop(
    redis_connection,
    heartbeat_key: str,
    queue_name: str,
    worker_id: str,
    stop_event: threading.Event,
    state_lock: threading.Lock,
    worker_state: dict,
    heartbeat_seconds: int,
    stale_seconds: int,
) -> None:
    while not stop_event.is_set():
        with state_lock:
            state = str(worker_state["state"])
            job_id = worker_state["job_id"]
        try:
            _write_windows_worker_heartbeat(
                redis_connection,
                heartbeat_key,
                queue_name=queue_name,
                worker_id=worker_id,
                state=state,
                job_id=job_id,
                stale_seconds=stale_seconds,
            )
        except Exception:
            print("Worker heartbeat update failed; Redis may be unavailable.", flush=True)
        stop_event.wait(heartbeat_seconds)


def _recover_stale_jobs(
    session_factory,
    redis_connection,
    queue,
    *,
    stale_seconds: int,
) -> int:
    session = session_factory()
    recovered_ids: list[str] = []
    try:
        rows = session.scalars(
            select(ModelJobRecord).where(ModelJobRecord.status == "running")
        ).all()
        now = datetime.now(UTC)
        for record in rows:
            payload = dict(record.payload or {})
            runtime = dict(payload.get("_job_runtime") or {})
            heartbeat_key = runtime.get("worker_heartbeat_key")
            updated_at = record.updated_at
            if updated_at is not None and updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            age_seconds = (now - (updated_at or record.created_at.replace(tzinfo=UTC))).total_seconds()
            if heartbeat_key and redis_connection.exists(heartbeat_key):
                continue
            if age_seconds < stale_seconds:
                continue
            runtime["recovered_at"] = now.isoformat()
            runtime["recovery_reason"] = "worker heartbeat missing"
            payload["_job_runtime"] = runtime
            record.status = "queued"
            record.current_step = "worker_initializing"
            record.finished_at = None
            record.error_message = None
            record.payload = payload
            recovered_ids.append(str(record.job_id))
        if recovered_ids:
            session.commit()
    finally:
        session.close()

    queued_ids = {
        value.decode("utf-8") if isinstance(value, bytes) else str(value)
        for value in redis_connection.lrange(queue.key, 0, -1)
    }
    for job_id in recovered_ids:
        if job_id not in queued_ids:
            redis_connection.rpush(queue.key, job_id)
    return len(recovered_ids)


if __name__ == "__main__":
    main()
