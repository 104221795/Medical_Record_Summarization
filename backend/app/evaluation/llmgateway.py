from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal

import httpx


DEFAULT_GATEWAY_BASE_URL = "http://localhost:4000"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 384
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_LOCAL_NUM_CTX = 8192

GATEWAY_MODEL_ALIASES: dict[str, str] = {
    "qwen2.5": "ollama/qwen2.5:3b",
    "llama3.2": "ollama/llama3.2:3b",
    "gemini2.5_flash_lite": "gemini/gemini-2.5-flash-lite",
}
GATEWAY_MODEL_PROVIDERS = frozenset(GATEWAY_MODEL_ALIASES)
LOCAL_GATEWAY_PROVIDERS = frozenset({"qwen2.5", "llama3.2"})


class LLMGatewayError(RuntimeError):
    """Raised when a gateway-backed model cannot produce a usable response."""


@dataclass(frozen=True)
class GatewayConfig:
    base_url: str = DEFAULT_GATEWAY_BASE_URL
    mode: Literal["proxy", "litellm"] = "proxy"
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    local_num_ctx: int = DEFAULT_LOCAL_NUM_CTX


def generate_llm_summary(prompt: str, model_provider_name: str) -> str:
    """Generate a clinical summary through the centralized LLM gateway.

    The function intentionally exposes only the internal provider name to the
    benchmark. Provider-specific identifiers and safety hyperparameters are
    centralized here so evaluation code cannot silently drift per model.
    """

    provider = _normalize_provider_name(model_provider_name)
    model_name = gateway_model_name(provider)
    config = gateway_config_from_env()
    messages = _summary_messages(prompt)
    try:
        if config.mode == "litellm":
            text = _generate_via_litellm(model_name, provider, messages, config)
        else:
            text = _generate_via_proxy(model_name, provider, messages, config)
    except TimeoutError as exc:
        raise LLMGatewayError(f"{provider} timed out via LLM gateway: {exc}") from exc
    except Exception as exc:
        raise LLMGatewayError(f"{provider} failed via LLM gateway: {exc}") from exc

    cleaned = clean_gateway_output(text)
    if not cleaned:
        raise LLMGatewayError(f"{provider} returned an empty summary.")
    return cleaned


def gateway_model_name(model_provider_name: str) -> str:
    provider = _normalize_provider_name(model_provider_name)
    env_key = "LLM_GATEWAY_" + re.sub(r"[^A-Z0-9]+", "_", provider.upper()).strip("_") + "_MODEL"
    return os.environ.get(env_key) or GATEWAY_MODEL_ALIASES[provider]


def gateway_config_from_env() -> GatewayConfig:
    mode = os.environ.get("LLM_GATEWAY_MODE", "proxy").strip().casefold()
    if mode not in {"proxy", "litellm"}:
        raise LLMGatewayError("LLM_GATEWAY_MODE must be 'proxy' or 'litellm'.")
    return GatewayConfig(
        base_url=os.environ.get("LLM_GATEWAY_BASE_URL", DEFAULT_GATEWAY_BASE_URL).rstrip("/"),
        mode=mode,  # type: ignore[arg-type]
        timeout_seconds=_float_env("LLM_GATEWAY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        temperature=_float_env("LLM_GATEWAY_TEMPERATURE", DEFAULT_TEMPERATURE),
        max_tokens=_int_env("LLM_GATEWAY_MAX_TOKENS", DEFAULT_MAX_TOKENS),
        local_num_ctx=_int_env("LLM_GATEWAY_LOCAL_NUM_CTX", DEFAULT_LOCAL_NUM_CTX),
    )


def clean_gateway_output(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^\s*<\|im_start\|>\s*assistant\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"<\|im_end\|>\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^\s*(assistant|model)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"```(?:text|markdown)?\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.replace("```", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _generate_via_proxy(
    model_name: str,
    provider: str,
    messages: list[dict[str, str]],
    config: GatewayConfig,
) -> str:
    url = f"{config.base_url}/v1/chat/completions"
    payload = _chat_payload(model_name, provider, messages, config, include_local_options=True)
    try:
        response = _post_json(url, payload, config)
    except httpx.HTTPStatusError as exc:
        if provider in LOCAL_GATEWAY_PROVIDERS and exc.response.status_code in {400, 422}:
            payload = _chat_payload(model_name, provider, messages, config, include_local_options=False)
            response = _post_json(url, payload, config)
        else:
            raise
    return _extract_chat_completion_text(response)


def _generate_via_litellm(
    model_name: str,
    provider: str,
    messages: list[dict[str, str]],
    config: GatewayConfig,
) -> str:
    try:
        from litellm import completion
    except ImportError as exc:
        if provider in LOCAL_GATEWAY_PROVIDERS:
            return _generate_via_ollama_native(model_name, provider, messages, config)
        raise LLMGatewayError("litellm is not installed. Use LLM_GATEWAY_MODE=proxy or install litellm.") from exc

    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout": config.timeout_seconds,
    }
    if provider in LOCAL_GATEWAY_PROVIDERS:
        kwargs["num_ctx"] = config.local_num_ctx
    if provider == "gemini2.5_flash_lite" and os.environ.get("GEMINI_API_KEY"):
        kwargs["api_key"] = os.environ["GEMINI_API_KEY"]
    response = completion(**kwargs)
    return str(response.choices[0].message.content or "")


def _generate_via_ollama_native(
    model_name: str,
    provider: str,
    messages: list[dict[str, str]],
    config: GatewayConfig,
) -> str:
    """Fallback for local Ollama models when LiteLLM is not installed.

    The benchmark still uses the centralized gateway module and the same
    safety hyperparameters; only the local transport changes to Ollama's
    native chat endpoint.
    """

    if provider not in LOCAL_GATEWAY_PROVIDERS:
        raise LLMGatewayError(f"Native Ollama fallback is not supported for {provider}.")
    base_url = os.environ.get("OLLAMA_API_BASE", "http://127.0.0.1:11434").rstrip("/")
    payload = {
        "model": _ollama_model_name(model_name),
        "messages": messages,
        "stream": False,
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "10m"),
        "options": {
            "temperature": config.temperature,
            "num_ctx": config.local_num_ctx,
            "num_predict": config.max_tokens,
        },
    }
    response = _post_json(f"{base_url}/api/chat", payload, config)
    message = response.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(response.get("response") or "")


def _chat_payload(
    model_name: str,
    provider: str,
    messages: list[dict[str, str]],
    config: GatewayConfig,
    *,
    include_local_options: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "stream": False,
    }
    if include_local_options and provider in LOCAL_GATEWAY_PROVIDERS:
        payload["num_ctx"] = config.local_num_ctx
        payload["extra_body"] = {"options": {"num_ctx": config.local_num_ctx}}
    return payload


def _post_json(url: str, payload: dict[str, Any], config: GatewayConfig) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("LLM_GATEWAY_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        raise TimeoutError(str(exc)) from exc


def _extract_chat_completion_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMGatewayError("LLM gateway response did not include choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMGatewayError("LLM gateway returned malformed choice data.")
    message = first.get("message")
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(first.get("text") or "")


def _ollama_model_name(model_name: str) -> str:
    clean = model_name.strip()
    for prefix in ("ollama_chat/", "ollama/"):
        if clean.startswith(prefix):
            return clean[len(prefix) :]
    return clean


def _summary_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a clinical summarization assistant for proxy evaluation. "
                "Use only the supplied retrieved evidence. Preserve diagnoses, medications, timeline, "
                "assessment, and plan. Do not invent clinical facts. Treat missing retrieved evidence as unknown, "
                "not absent. Never infer 'no medications', 'no diagnosis', or 'no plan' unless the evidence "
                "explicitly states that absence."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def _normalize_provider_name(model_provider_name: str) -> str:
    provider = model_provider_name.strip()
    if provider not in GATEWAY_MODEL_ALIASES:
        supported = ", ".join(sorted(GATEWAY_MODEL_ALIASES))
        raise LLMGatewayError(f"Unsupported gateway model '{model_provider_name}'. Supported: {supported}.")
    return provider


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise LLMGatewayError(f"{name} must be a float.") from exc


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise LLMGatewayError(f"{name} must be an integer.") from exc
