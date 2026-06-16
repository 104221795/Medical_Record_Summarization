from __future__ import annotations

import argparse

from backend.app.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the clinical summarization Redis/RQ worker.")
    parser.add_argument("--queue", default=None, help="RQ queue name. Defaults to RAG_RQ_QUEUE_NAME.")
    parser.add_argument("--redis-url", default=None, help="Redis URL. Defaults to RAG_REDIS_URL.")
    parser.add_argument(
        "--worker-class",
        choices=("simple", "default"),
        default="simple",
        help="Use simple on Windows/local dev; default is better for Unix process isolation.",
    )
    parser.add_argument("--burst", action="store_true", help="Exit when the queue is empty.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    redis_url = args.redis_url or settings.redis_url
    queue_name = args.queue or settings.rq_queue_name

    try:
        from redis import Redis
        from rq import Queue, SimpleWorker, Worker
    except Exception as exc:  # pragma: no cover - exercised in deployment setup
        raise SystemExit(
            "Redis/RQ dependencies are not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    redis_connection = Redis.from_url(redis_url)
    redis_connection.ping()
    queue = Queue(queue_name, connection=redis_connection)
    worker_cls = SimpleWorker if args.worker_class == "simple" else Worker
    worker = worker_cls([queue], connection=redis_connection)
    print(f"Starting RQ worker for queue '{queue_name}' at {redis_url} ({args.worker_class}).")
    worker.work(burst=args.burst)


if __name__ == "__main__":
    main()

