from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]


def load_runtime_env(
    *,
    enable_model_defaults: bool = True,
    job_backend: str | None = None,
    strict_rq: bool = False,
) -> None:
    """Load the same local runtime defaults for API and worker processes.

    Redis/RQ workers are separate processes, so they do not inherit the helper
    defaults applied by ``scripts.run_backend`` unless we explicitly apply them
    here too.
    """

    load_dotenv(ROOT_DIR / ".env", override=False)
    deployment_mode = _deployment_mode()
    _apply_cache_defaults(deployment_mode)
    _apply_retrieval_defaults(deployment_mode)
    _apply_rq_defaults(deployment_mode)
    if job_backend and job_backend != "env":
        os.environ["RAG_JOB_BACKEND"] = job_backend
    if strict_rq:
        os.environ["RAG_JOB_FALLBACK_TO_IN_PROCESS"] = "false"
        os.environ["RAG_RQ_REQUIRE_LIVE_WORKER"] = "true"
    if enable_model_defaults:
        _apply_model_defaults()


def _apply_cache_defaults(deployment_mode: str) -> None:
    if deployment_mode == "railway":
        os.environ.setdefault("HF_HOME", "/tmp/hf_cache")
        os.environ.setdefault("HF_HUB_CACHE", "/tmp/hf_cache/hub")
        os.environ.setdefault("HF_DATASETS_CACHE", "/tmp/hf_cache/datasets")
        os.environ.setdefault("TRANSFORMERS_CACHE", "/tmp/hf_cache/hub")
        configured_ollama = os.environ.get("OLLAMA_BASE_URL")
        if configured_ollama:
            os.environ.setdefault("OLLAMA_API_BASE", configured_ollama)
        return
    os.environ.setdefault("HF_HOME", "D:\\hf_cache")
    os.environ.setdefault("HF_HUB_CACHE", "D:\\hf_cache\\hub")
    os.environ.setdefault("HF_DATASETS_CACHE", "D:\\hf_cache\\datasets")
    os.environ.setdefault("TRANSFORMERS_CACHE", "D:\\hf_cache\\hub")
    os.environ.setdefault("OLLAMA_MODELS", "D:\\ollama_models")
    os.environ.setdefault("OLLAMA_API_BASE", "http://127.0.0.1:11434")


def _apply_retrieval_defaults(deployment_mode: str) -> None:
    os.environ.setdefault("RAG_EMBEDDING_PROVIDER", "sentence_transformers")
    os.environ.setdefault("RAG_SENTENCE_TRANSFORMERS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    os.environ.setdefault(
        "RAG_SENTENCE_TRANSFORMERS_LOCAL_FILES_ONLY",
        "false" if deployment_mode == "railway" else "true",
    )


def _apply_rq_defaults(deployment_mode: str) -> None:
    os.environ.setdefault("RAG_REDIS_URL", "redis://127.0.0.1:6379/0")
    os.environ.setdefault("RAG_RQ_QUEUE_NAME", "clin_summ_jobs")
    os.environ.setdefault(
        "RAG_JOB_FALLBACK_TO_IN_PROCESS",
        "false" if deployment_mode == "railway" else "true",
    )
    os.environ.setdefault("RAG_RQ_REQUIRE_LIVE_WORKER", "true")
    os.environ.setdefault("RAG_RQ_MAX_RETRIES", "2")
    os.environ.setdefault("RAG_RQ_WORKER_HEARTBEAT_SECONDS", "5")
    os.environ.setdefault("RAG_RQ_WORKER_STALE_SECONDS", "20")


def _apply_model_defaults() -> None:
    os.environ.setdefault("RUN_REAL_BASELINES", "1")
    os.environ.setdefault("RAG_RUN_REAL_BASELINES", "1")
    os.environ.setdefault("LLM_GATEWAY_MODE", "litellm")
    os.environ.setdefault("LLM_GATEWAY_TIMEOUT_SECONDS", "180")
    os.environ.setdefault("LLM_GATEWAY_TEMPERATURE", "0.1")
    os.environ.setdefault("LLM_GATEWAY_MAX_TOKENS", "384")
    os.environ.setdefault("LLM_GATEWAY_LOCAL_NUM_CTX", "8192")
    os.environ.setdefault("OLLAMA_KEEP_ALIVE", "30m")


def _deployment_mode() -> str:
    configured = (
        os.environ.get("DEPLOYMENT_MODE")
        or os.environ.get("RAG_DEPLOYMENT_MODE")
        or ""
    ).strip().lower()
    if configured:
        return configured
    return "railway" if os.environ.get("RAILWAY_ENVIRONMENT") else "local"
