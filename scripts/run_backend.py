from __future__ import annotations

import argparse
import os

from backend.app.runtime_env import load_runtime_env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Medical Record Summarization backend with .env defaults.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument("--reload", action="store_true", help="Enable Uvicorn auto-reload.")
    parser.add_argument(
        "--job-backend",
        choices=("env", "in_process", "rq"),
        default="env",
        help="Override RAG_JOB_BACKEND for this process.",
    )
    parser.add_argument(
        "--strict-rq",
        action="store_true",
        help="Do not fall back to in-process jobs when Redis/RQ is unavailable.",
    )
    parser.add_argument(
        "--all-models",
        dest="all_models",
        action="store_true",
        default=True,
        help="Enable local real baselines and Ollama/Gemini provider test config.",
    )
    parser.add_argument("--no-all-models", dest="all_models", action="store_false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_runtime_env(
        enable_model_defaults=args.all_models,
        job_backend=args.job_backend,
        strict_rq=args.strict_rq,
    )

    from backend.app.config import get_settings
    import uvicorn

    settings = get_settings()
    print(
        "Starting backend "
        f"host={args.host} port={args.port} "
        f"job_backend={settings.job_backend} "
        f"redis_url={settings.redis_url} "
        f"queue={settings.rq_queue_name}"
    )
    print(f"HF_HOME={os.environ.get('HF_HOME') or 'not configured'}")
    print(f"OLLAMA_MODELS={os.environ.get('OLLAMA_MODELS') or 'not configured'}")
    print(f"LLM_GATEWAY_MODE={os.environ.get('LLM_GATEWAY_MODE') or 'proxy'}")
    uvicorn.run(
        "backend.app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )

if __name__ == "__main__":
    main()
