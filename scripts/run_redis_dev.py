from __future__ import annotations

import argparse
import subprocess
import sys

from backend.app.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check or start the local Redis dev container.")
    parser.add_argument("--redis-url", default=None, help="Redis URL to check. Defaults to RAG_REDIS_URL.")
    parser.add_argument("--container-name", default="clin-summ-redis")
    parser.add_argument("--port", default="6379")
    parser.add_argument("--start", action="store_true", help="Start/create Docker Redis if Redis is not reachable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    redis_url = args.redis_url or settings.redis_url
    if _redis_ok(redis_url):
        print(f"Redis reachable: {redis_url}")
        return
    if not args.start:
        raise SystemExit(f"Redis is not reachable at {redis_url}. Add --start to start Docker Redis.")

    _run(["docker", "start", args.container_name], allow_failure=True)
    if not _redis_ok(redis_url):
        _run(
            [
                "docker",
                "run",
                "--name",
                args.container_name,
                "-p",
                f"{args.port}:6379",
                "-d",
                "redis:7",
            ],
            allow_failure=False,
        )
    if not _redis_ok(redis_url):
        raise SystemExit(f"Redis container command ran, but Redis is still not reachable at {redis_url}.")
    print(f"Redis reachable: {redis_url}")


def _redis_ok(redis_url: str) -> bool:
    try:
        from redis import Redis

        connection = Redis.from_url(redis_url)
        return bool(connection.ping())
    except Exception:
        return False


def _run(command: list[str], *, allow_failure: bool) -> None:
    try:
        completed = subprocess.run(command, check=not allow_failure, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise SystemExit("Docker was not found on PATH. Start Redis manually or install Docker Desktop.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        raise SystemExit(stderr) from exc
    if completed.returncode != 0 and not allow_failure:
        sys.stderr.write(completed.stderr)


if __name__ == "__main__":
    main()

