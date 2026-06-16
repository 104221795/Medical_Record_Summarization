from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]


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
    load_dotenv(ROOT_DIR / ".env", override=False)
    _apply_dev_defaults(args)

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


def _apply_dev_defaults(args: argparse.Namespace) -> None:
    os.environ.setdefault("HF_HOME", "D:\\hf_cache")
    os.environ.setdefault("HF_HUB_CACHE", "D:\\hf_cache\\hub")
    os.environ.setdefault("HF_DATASETS_CACHE", "D:\\hf_cache\\datasets")
    os.environ.setdefault("TRANSFORMERS_CACHE", "D:\\hf_cache\\hub")
    os.environ.setdefault("OLLAMA_MODELS", "D:\\ollama_models")
    os.environ.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")
    os.environ.setdefault("RAG_EMBEDDING_PROVIDER", "sentence_transformers")
    os.environ.setdefault("RAG_SENTENCE_TRANSFORMERS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    os.environ.setdefault("RAG_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY", "true")
    os.environ.setdefault("RAG_REDIS_URL", "redis://127.0.0.1:6379/0")
    os.environ.setdefault("RAG_RQ_QUEUE_NAME", "clin_summ_jobs")
    os.environ.setdefault("RAG_JOB_FALLBACK_TO_IN_PROCESS", "true")
    os.environ.setdefault("RAG_RQ_REQUIRE_LIVE_WORKER", "true")
    if args.job_backend != "env":
        os.environ["RAG_JOB_BACKEND"] = args.job_backend
    if args.strict_rq:
        os.environ["RAG_JOB_FALLBACK_TO_IN_PROCESS"] = "false"
        os.environ["RAG_RQ_REQUIRE_LIVE_WORKER"] = "true"
    if args.all_models:
        os.environ.setdefault("RUN_REAL_BASELINES", "1")
        os.environ.setdefault("RAG_RUN_REAL_BASELINES", "1")
        os.environ.setdefault("LLM_GATEWAY_MODE", "litellm")
        os.environ.setdefault("LLM_GATEWAY_TIMEOUT_SECONDS", "180")
        os.environ.setdefault("LLM_GATEWAY_TEMPERATURE", "0.1")
        os.environ.setdefault("LLM_GATEWAY_MAX_TOKENS", "384")
        os.environ.setdefault("LLM_GATEWAY_LOCAL_NUM_CTX", "8192")


if __name__ == "__main__":
    main()
