from __future__ import annotations

import os


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


def normalize_ollama_base_url(value: str | None) -> str:
    """Return a native Ollama base URL without the trailing /api path.

    Local Windows users often configure one of these forms:

    - 127.0.0.1:11434
    - localhost:11434
    - http://127.0.0.1:11434
    - http://127.0.0.1:11434/api

    The readiness and generation code always appends /api/tags or /api/chat, so
    the normalized value must be the host root.
    """

    raw = (value or DEFAULT_OLLAMA_BASE_URL).strip() or DEFAULT_OLLAMA_BASE_URL
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    raw = raw.rstrip("/")
    if raw.endswith("/api"):
        raw = raw[: -len("/api")]
    return raw


def configured_ollama_base_url(*candidates: str | None) -> str:
    """Resolve Ollama URL from explicit candidates, env aliases, or default."""

    for candidate in candidates:
        if candidate:
            return normalize_ollama_base_url(candidate)
    for key in (
        "OLLAMA_API_BASE",
        "OLLAMA_BASE_URL",
        "RAG_OLLAMA_BASE_URL",
        "OLLAMA_HOST",
    ):
        value = os.environ.get(key)
        if value:
            return normalize_ollama_base_url(value)
    return DEFAULT_OLLAMA_BASE_URL


def ollama_model_name(model_name: str) -> str:
    """Strip LiteLLM/Ollama prefixes and return the native Ollama model tag."""

    clean = str(model_name or "").strip()
    for prefix in ("ollama_chat/", "ollama/"):
        if clean.startswith(prefix):
            return clean[len(prefix) :]
    return clean


def ollama_exception_message(exc: BaseException) -> str:
    """Return a concise connection error message for UI/readiness output."""

    reason = getattr(exc, "reason", None)
    if reason:
        return str(reason)
    return str(exc) or type(exc).__name__
