from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.session import build_engine_from_settings
from backend.app.models import ModelJobRecord


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean stale Redis/RQ job entries using DB job status as source of truth.")
    parser.add_argument("--queue", default=None, help="RQ queue name. Defaults to configured RAG_RQ_QUEUE_NAME.")
    parser.add_argument("--redis-url", default=None, help="Redis URL. Defaults to configured RAG_REDIS_URL.")
    parser.add_argument("--dry-run", action="store_true", help="Report stale entries without removing them.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    queue_name = args.queue or settings.rq_queue_name
    redis_url = args.redis_url or settings.redis_url

    try:
        from redis import Redis
        from rq import Queue
        from rq.registry import DeferredJobRegistry, FailedJobRegistry, StartedJobRegistry
    except Exception as exc:
        raise SystemExit("Redis/RQ dependencies are not installed. Run: python -m pip install -r requirements.txt") from exc

    redis_connection = Redis.from_url(redis_url)
    redis_connection.ping()
    queue = Queue(queue_name, connection=redis_connection)
    engine = build_engine_from_settings(settings)

    report: dict[str, Any] = {
        "queue": queue_name,
        "redis_url": redis_url,
        "dry_run": args.dry_run,
        "removed_queued": [],
        "removed_started_registry": [],
        "removed_failed_registry": [],
        "removed_deferred_registry": [],
        "kept": [],
    }
    with Session(engine) as session:
        for job_id in list(queue.job_ids):
            status = _db_status(session, job_id)
            if status in TERMINAL_STATUSES:
                report["removed_queued"].append({"job_id": job_id, "db_status": status})
                if not args.dry_run:
                    queue.remove(job_id)
            else:
                report["kept"].append({"job_id": job_id, "location": "queue", "db_status": status})

        registry_specs = [
            ("removed_started_registry", StartedJobRegistry(queue_name, connection=redis_connection)),
            ("removed_failed_registry", FailedJobRegistry(queue_name, connection=redis_connection)),
            ("removed_deferred_registry", DeferredJobRegistry(queue_name, connection=redis_connection)),
        ]
        for key, registry in registry_specs:
            for job_id in list(registry.get_job_ids()):
                status = _db_status(session, job_id)
                if status in TERMINAL_STATUSES:
                    report[key].append({"job_id": job_id, "db_status": status})
                    if not args.dry_run:
                        registry.remove(job_id, delete_job=False)
                else:
                    report["kept"].append({"job_id": job_id, "location": key, "db_status": status})

    report["queue_after"] = list(queue.job_ids)
    print(json.dumps(report, indent=2, default=str))


def _db_status(session: Session, job_id: str) -> str | None:
    try:
        record = session.get(ModelJobRecord, uuid.UUID(job_id))
    except ValueError:
        return None
    return str(record.status) if record else None


if __name__ == "__main__":
    main()

